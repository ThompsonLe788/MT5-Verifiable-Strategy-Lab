"""
pipeline_state.py — Quản lý trạng thái pipeline để resume từ bước N.

State được lưu vào JSON sau mỗi bước, cho phép:
  - Resume khi pipeline bị gián đoạn
  - Audit lịch sử các lần chạy
  - Pass data giữa các bước (report paths, metrics,...)
"""

import json
import logging
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class StepStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    SKIPPED   = "skipped"


class PipelineState:
    """
    Lưu và load trạng thái pipeline.

    Cấu trúc JSON:
    {
        "strategy":   "wyckoff",
        "symbol":     "XAUUSD",
        "run_id":     "20260501_103000",
        "created_at": "...",
        "updated_at": "...",
        "steps": {
            "1": {"status": "completed", "completed_at": "...", "error": null},
            "2": {"status": "failed",    "completed_at": null, "error": "msg"},
            ...
        },
        "data": {
            "is_trade_log": "logs/wyckoff_is_..._trade_log.csv",
            "is_metrics":   {"winrate": 0.55, ...},
            ...
        }
    }
    """

    def __init__(self, strategy: str, symbol: str, path: Path):
        self.strategy = strategy
        self.symbol   = symbol
        self.path     = Path(path)
        self.run_id   = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._steps: dict[str, dict] = {}
        self._data:  dict[str, Any]  = {}
        self._created_at = datetime.now().isoformat()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "strategy":   self.strategy,
            "symbol":     self.symbol,
            "run_id":     self.run_id,
            "created_at": self._created_at,
            "updated_at": datetime.now().isoformat(),
            "steps":      self._steps,
            "data":       self._data,
        }
        self.path.write_text(json.dumps(payload, indent=2, default=str))
        log.debug(f"State saved: {self.path}")

    @classmethod
    def load(cls, path: Path) -> "PipelineState":
        """Load state từ file JSON. Raise FileNotFoundError nếu không tồn tại."""
        content = json.loads(Path(path).read_text())
        obj = cls.__new__(cls)
        obj.strategy     = content["strategy"]
        obj.symbol       = content["symbol"]
        obj.path         = Path(path)
        obj.run_id       = content.get("run_id", "unknown")
        obj._steps       = content.get("steps", {})
        obj._data        = content.get("data", {})
        obj._created_at  = content.get("created_at", "")
        log.info(f"State loaded: {path} (run_id={obj.run_id})")
        return obj

    @classmethod
    def load_or_create(cls, path: Path, strategy: str, symbol: str) -> "PipelineState":
        if Path(path).exists():
            return cls.load(path)
        return cls(strategy=strategy, symbol=symbol, path=path)

    # ------------------------------------------------------------------
    # Step management
    # ------------------------------------------------------------------

    def _update_step(self, step: int, status: StepStatus, error: str = None):
        key = str(step)
        self._steps[key] = {
            "status":       status.value,
            "updated_at":   datetime.now().isoformat(),
            "error":        error,
        }
        self.save()

    def start_step(self, step: int):
        self._update_step(step, StepStatus.RUNNING)
        log.debug(f"Step {step} → RUNNING")

    def complete_step(self, step: int):
        self._update_step(step, StepStatus.COMPLETED)
        log.debug(f"Step {step} → COMPLETED")

    def fail_step(self, step: int, error: str):
        self._update_step(step, StepStatus.FAILED, error=error)
        log.error(f"Step {step} → FAILED: {error}")

    def skip_step(self, step: int):
        self._update_step(step, StepStatus.SKIPPED)

    def is_completed(self, step: int) -> bool:
        return self._steps.get(str(step), {}).get("status") == StepStatus.COMPLETED

    def is_failed(self, step: int) -> bool:
        return self._steps.get(str(step), {}).get("status") == StepStatus.FAILED

    def get_step_error(self, step: int) -> str:
        return self._steps.get(str(step), {}).get("error", "")

    # ------------------------------------------------------------------
    # Data passing between steps
    # ------------------------------------------------------------------

    def set_data(self, key: str, value: Any):
        self._data[key] = value
        self.save()

    def get_data(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> str:
        lines = []
        for step_num in sorted(int(k) for k in self._steps):
            s = self._steps[str(step_num)]
            status = s["status"].upper()
            err    = f" — {s['error']}" if s.get("error") else ""
            lines.append(f"  Step {step_num:02d}: {status}{err}")
        return "\n".join(lines) if lines else "  (no steps recorded)"

    def last_completed_step(self) -> int:
        completed = [
            int(k) for k, v in self._steps.items()
            if v["status"] == StepStatus.COMPLETED
        ]
        return max(completed) if completed else 0

    def next_step(self) -> int:
        """Bước tiếp theo cần chạy (sau bước completed cuối, hoặc bước failed)."""
        failed = [
            int(k) for k, v in self._steps.items()
            if v["status"] == StepStatus.FAILED
        ]
        if failed:
            return min(failed)
        return self.last_completed_step() + 1

    def reset(self, from_step: int = 1):
        """Xóa state từ bước N trở đi để chạy lại."""
        to_delete = [k for k in self._steps if int(k) >= from_step]
        for k in to_delete:
            del self._steps[k]
        log.info(f"State reset từ step {from_step} — xóa {len(to_delete)} steps")
        self.save()

    def __repr__(self):
        return (f"PipelineState(strategy={self.strategy}, symbol={self.symbol}, "
                f"run_id={self.run_id}, last_completed={self.last_completed_step()})")
