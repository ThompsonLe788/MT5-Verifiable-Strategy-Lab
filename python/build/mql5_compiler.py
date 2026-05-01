"""
mql5_compiler.py — MetaEditor64.exe CLI wrapper.

Compile .mq5 → .ex5 và parse compile log.
Chi tiết spec: docs/MT5_COMPILE_AUTOMATION.md
"""

import re
import subprocess
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from shutil import copy2

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CompileError:
    file: str
    line: int
    column: int
    code: int
    message: str

    def __str__(self):
        return f"{Path(self.file).name}({self.line},{self.column}): error {self.code}: {self.message}"


@dataclass
class CompileResult:
    success: bool
    errors: int
    warnings: int
    error_list: list[CompileError] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    log_path: str = ""
    elapsed_ms: int = 0

    def __str__(self):
        status = "OK" if self.success else "FAIL"
        return f"[{status}] errors={self.errors}, warnings={self.warnings}"


# ---------------------------------------------------------------------------
# Log parser
# ---------------------------------------------------------------------------

_ERROR_PATTERN = re.compile(
    r"(.+?)\((\d+),(\d+)\)\s*:\s*error\s+(\d+)\s*:\s*(.+)"
)
_RESULT_PATTERN = re.compile(
    r"Result:\s*(\d+)\s*error[s]?,\s*(\d+)\s*warning[s]?",
    re.IGNORECASE,
)


def _parse_log(log_path: Path) -> CompileResult:
    if not log_path.exists():
        return CompileResult(
            success=False, errors=1, warnings=0,
            messages=["Log file not found after compile"],
            log_path=str(log_path),
        )

    for encoding in ("utf-16-le", "utf-16", "utf-8"):
        try:
            content = log_path.read_text(encoding=encoding, errors="replace")
            break
        except Exception:
            continue
    else:
        content = ""

    messages = [ln.strip() for ln in content.splitlines() if ln.strip()]
    errors, warnings = 0, 0
    error_list: list[CompileError] = []

    for line in messages:
        m = _RESULT_PATTERN.search(line)
        if m:
            errors   = int(m.group(1))
            warnings = int(m.group(2))

        m = _ERROR_PATTERN.match(line)
        if m:
            error_list.append(CompileError(
                file=m.group(1).strip(),
                line=int(m.group(2)),
                column=int(m.group(3)),
                code=int(m.group(4)),
                message=m.group(5).strip(),
            ))

    return CompileResult(
        success=(errors == 0),
        errors=errors,
        warnings=warnings,
        error_list=error_list,
        messages=messages,
        log_path=str(log_path),
    )


# ---------------------------------------------------------------------------
# Compiler
# ---------------------------------------------------------------------------

class MQL5Compiler:
    """
    Wrapper gọi MetaEditor64.exe để compile .mq5 → .ex5.

    Args:
        metaeditor_exe: đường dẫn tuyệt đối tới metaeditor64.exe
        log_dir: thư mục lưu compile logs có timestamp
        max_retries: số lần retry tối đa khi compile fail
    """

    def __init__(
        self,
        metaeditor_exe: str,
        log_dir: str = "python/build/logs",
        max_retries: int = 0,      # pipeline quyết định retry, không tự retry
    ):
        self.metaeditor_exe = str(metaeditor_exe)
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.max_retries = max_retries

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compile(self, mq5_path: str, timeout: int = 120) -> CompileResult:
        """
        Compile một file .mq5.

        Returns:
            CompileResult với success=True nếu 0 errors.
        """
        mq5 = Path(mq5_path).resolve()

        if not mq5.exists():
            return CompileResult(
                success=False, errors=1, warnings=0,
                messages=[f"File not found: {mq5}"],
            )

        log.info(f"Compiling: {mq5.name}")
        start = datetime.now()

        try:
            proc = subprocess.run(
                [self.metaeditor_exe, f"/compile:{mq5}", "/log"],
                timeout=timeout,
                capture_output=True,
            )
        except subprocess.TimeoutExpired:
            return CompileResult(
                success=False, errors=1, warnings=0,
                messages=[f"Compile timeout after {timeout}s: {mq5.name}"],
            )
        except FileNotFoundError:
            raise RuntimeError(
                f"MetaEditor64.exe không tìm thấy: {self.metaeditor_exe}\n"
                "Kiểm tra configs/mt5_paths.yaml → metaeditor_exe"
            )

        elapsed = int((datetime.now() - start).total_seconds() * 1000)
        log_path = mq5.with_suffix(".log")
        result = _parse_log(log_path)
        result.elapsed_ms = elapsed

        # Archive log với timestamp
        self._archive_log(log_path, mq5.stem)

        if result.success:
            log.info(f"  OK ({elapsed}ms) — {result.warnings} warning(s): {mq5.name}")
        else:
            log.error(f"  FAIL ({elapsed}ms) — {result.errors} error(s): {mq5.name}")
            for err in result.error_list:
                log.error(f"    {err}")

        return result

    def compile_all(
        self,
        mq5_paths: list[str],
        timeout: int = 120,
    ) -> dict[str, CompileResult]:
        """
        Compile danh sách file theo thứ tự.
        Dừng ngay khi có file nào fail (dependency order).

        Returns:
            dict path → CompileResult
        """
        results: dict[str, CompileResult] = {}
        for path in mq5_paths:
            result = self.compile(path, timeout=timeout)
            results[path] = result
            if not result.success:
                log.error(f"Compile pipeline stopped tại: {Path(path).name}")
                break
        return results

    def get_error_summary(self, results: dict[str, CompileResult]) -> list[str]:
        """Trả về danh sách lỗi gọn để gửi về Coder Agent."""
        lines = []
        for path, result in results.items():
            if not result.success:
                lines.append(f"=== {Path(path).name} ===")
                for err in result.error_list:
                    lines.append(f"  {err}")
        return lines

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _archive_log(self, log_path: Path, stem: str):
        if not log_path.exists():
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = self.log_dir / f"{ts}_{stem}.log"
        try:
            copy2(log_path, dest)
        except Exception as e:
            log.warning(f"Không archive log: {e}")

    def append_compile_summary(self, results: dict[str, CompileResult]):
        """Ghi compile_summary.csv."""
        csv_path = self.log_dir / "compile_summary.csv"
        header = not csv_path.exists()
        ts = datetime.now().isoformat()

        with open(csv_path, "a") as f:
            if header:
                f.write("timestamp,file,errors,warnings,status\n")
            for path, r in results.items():
                status = "OK" if r.success else "FAIL"
                f.write(f"{ts},{Path(path).name},{r.errors},{r.warnings},{status}\n")
