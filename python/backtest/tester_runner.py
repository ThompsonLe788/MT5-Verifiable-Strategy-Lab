"""
tester_runner.py — MT5 Strategy Tester automation.

Tạo .ini file, gọi terminal64.exe, tìm report.
Chi tiết spec: docs/MT5_TESTER_AUTOMATION.md
"""

import configparser
import subprocess
import logging
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Period map (string → MT5 integer)
# ---------------------------------------------------------------------------

PERIOD_MAP: dict[str, int] = {
    "M1": 1, "M5": 5, "M15": 15, "M30": 30,
    "H1": 16385, "H4": 16388, "D1": 16408,
    "W1": 32769, "MN1": 49153,
}


# ---------------------------------------------------------------------------
# MT5TesterRunner
# ---------------------------------------------------------------------------

class MT5TesterRunner:
    """
    Wrapper chạy MT5 Strategy Tester từ Python.

    Args:
        mt5_paths: dict từ configs/mt5_paths.yaml
    """

    def __init__(self, mt5_paths: dict):
        self.terminal_exe  = str(mt5_paths["terminal_exe"])
        self.portable_dir  = Path(mt5_paths["portable_dir"])
        self.files_dir     = self.portable_dir / mt5_paths.get("files_dir", "MQL5/Files")
        self.ini_dir       = Path(mt5_paths.get("tester_ini_dir",   "python/backtest/ini"))
        self.report_dir    = Path(mt5_paths.get("tester_report_dir","python/backtest/reports"))
        self.ini_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # ini file builder
    # ------------------------------------------------------------------

    def build_ini(self, config: dict) -> Path:
        """
        Tạo .ini file từ config dict.

        config keys:
            expert_path   str   — relative từ MQL5/, ví dụ: Experts/EA.ex5
            symbol        str
            period        int   — MT5 period integer (dùng PERIOD_MAP)
            from_date     str   — "YYYY.MM.DD"
            to_date       str   — "YYYY.MM.DD"
            model         int   — 0=every tick, 1=OHLC M1, 2=open price (default 1)
            forward_mode  int   — 0=off, 1=1/2, 2=1/3, 3=custom (default 0)
            deposit       float — (default 10000)
            currency      str   — (default USD)
            leverage      int   — (default 100)
            inputs        dict  — EA input params {name: value}
        """
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        symbol = config["symbol"]
        ini_path = self.ini_dir / f"tester_{symbol}_{ts}.ini"

        cp = configparser.ConfigParser()
        cp.optionxform = str     # preserve case

        cp["Tester"] = {
            "Expert":               config["expert_path"],
            "Symbol":               symbol,
            "Period":               str(config["period"]),
            "Optimization":         "0",
            "Model":                str(config.get("model", 1)),
            "FromDate":             config["from_date"],
            "ToDate":               config["to_date"],
            "ForwardMode":          str(config.get("forward_mode", 0)),
            "Deposit":              str(config.get("deposit", 10000)),
            "Currency":             config.get("currency", "USD"),
            "ProfitInPips":         "0",
            "Leverage":             str(config.get("leverage", 100)),
            "ExecutionMode":        "0",
            "OptimizationCriterion":"0",
        }

        inputs = config.get("inputs", {})
        if inputs:
            cp["TesterInputs"] = {k: str(v) for k, v in inputs.items()}

        with open(ini_path, "w") as f:
            cp.write(f)

        log.debug(f"ini created: {ini_path}")
        return ini_path

    # ------------------------------------------------------------------
    # Runner
    # ------------------------------------------------------------------

    def run(self, ini_path: Path, timeout_seconds: int = 3600) -> bool:
        """
        Gọi terminal64.exe với ini file.
        Returns True nếu process kết thúc bình thường (exit code 0).
        """
        if not Path(self.terminal_exe).exists():
            raise RuntimeError(
                f"terminal64.exe không tìm thấy: {self.terminal_exe}\n"
                "Kiểm tra configs/mt5_paths.yaml → terminal_exe"
            )

        cmd = [self.terminal_exe, f"/config:{ini_path}", "/portable"]
        log.info(f"Launching MT5 tester: {ini_path.name}")

        try:
            result = subprocess.run(cmd, timeout=timeout_seconds, check=False)
            ok = result.returncode == 0
            log.info(f"MT5 exited with code {result.returncode}")
            return ok
        except subprocess.TimeoutExpired:
            log.error(f"MT5 tester timeout after {timeout_seconds}s")
            return False

    # ------------------------------------------------------------------
    # Report / trade log locators
    # ------------------------------------------------------------------

    def find_trade_log(self) -> Path | None:
        """Tìm trade_log.csv do EA ghi trong OnTester()."""
        path = self.files_dir / "trade_log.csv"
        return path if path.exists() else None

    def find_latest_report(self) -> Path | None:
        """Tìm backtest report .htm mới nhất trong tester cache."""
        cache = self.portable_dir / "tester" / "cache"
        if not cache.exists():
            return None
        htm_files = list(cache.glob("*.htm"))
        if not htm_files:
            return None
        return max(htm_files, key=lambda f: f.stat().st_mtime)

    # ------------------------------------------------------------------
    # Full flow
    # ------------------------------------------------------------------

    def run_backtest(self, config: dict, timeout: int = 3600) -> dict:
        """
        Full flow: build ini → run MT5 → locate outputs.

        Returns dict:
            status      "OK" | "FAILED"
            reason      str (nếu FAILED)
            ini_path    str
            trade_log   str | None
            report_path str | None
        """
        ini_path = self.build_ini(config)
        ok = self.run(ini_path, timeout_seconds=timeout)

        result: dict = {"ini_path": str(ini_path)}

        if not ok:
            result["status"] = "FAILED"
            result["reason"] = "MT5 process exited non-zero or timeout"
            return result

        trade_log = self.find_trade_log()
        report    = self.find_latest_report()

        result["status"]      = "OK"
        result["trade_log"]   = str(trade_log) if trade_log else None
        result["report_path"] = str(report) if report else None

        if trade_log is None:
            log.warning("trade_log.csv không tìm thấy — EA cần export trong OnTester()")
        if report is None:
            log.warning("Backtest report .htm không tìm thấy")

        return result
