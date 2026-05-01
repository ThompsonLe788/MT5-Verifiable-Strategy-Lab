# MT5_COMPILE_AUTOMATION.md

**Mục tiêu:** Spec kỹ thuật để Python tự động compile file `.mq5` → `.ex5` bằng MetaEditor, không cần mở GUI.

---

## 1. Tổng quan cơ chế

```text
Python script
  → gọi MetaEditor64.exe /compile:"path.mq5" /log
  → đợi process kết thúc
  → đọc compile log
  → parse: 0 errors → PASS, errors > 0 → FAIL
  → trả về compile_result dict
```

---

## 2. Điều kiện tiên quyết

```text
1. MT5 đã cài, MetaEditor64.exe tồn tại
2. File .mq5 đúng đường dẫn tuyệt đối
3. Các file .mqh được include nằm đúng vị trí trong MQL5/Include/
4. Không cần MT5 đang chạy để compile
```

Config trong `configs/mt5_paths.yaml`:

```yaml
metaeditor_exe: "C:/Program Files/MetaTrader 5/metaeditor64.exe"
mql5_root: "C:/Users/<user>/AppData/Roaming/MetaQuotes/Terminal/<ID>/MQL5"
compile_log_dir: "python/build/logs"
```

---

## 3. MetaEditor command-line syntax

```text
metaeditor64.exe /compile:"<absolute_path_to_mq5>" /log
```

Flags:
| Flag | Ý nghĩa |
|---|---|
| /compile | Đường dẫn tuyệt đối tới file .mq5 |
| /log | Ghi log ra file cùng thư mục với .mq5 |
| /portable | Dùng data folder portable (nếu cần) |

MetaEditor tạo file log cùng tên với .mq5, extension `.log`, cùng thư mục.

Ví dụ:
```text
compile: C:\...\MQL5\Experts\PortfolioEA_Wyckoff.mq5
log:     C:\...\MQL5\Experts\PortfolioEA_Wyckoff.log
```

---

## 4. Python: MQL5Compiler class

```python
# python/build/mql5_compiler.py

import subprocess
import re
from pathlib import Path
from dataclasses import dataclass


@dataclass
class CompileResult:
    success: bool
    errors: int
    warnings: int
    messages: list[str]
    log_path: str


class MQL5Compiler:

    def __init__(self, metaeditor_exe: str, log_dir: str):
        self.metaeditor_exe = metaeditor_exe
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def compile(self, mq5_path: str, timeout: int = 120) -> CompileResult:
        mq5 = Path(mq5_path).resolve()
        if not mq5.exists():
            return CompileResult(
                success=False, errors=1, warnings=0,
                messages=[f"File not found: {mq5}"],
                log_path=""
            )

        cmd = [self.metaeditor_exe, f"/compile:{mq5}", "/log"]

        try:
            subprocess.run(cmd, timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            return CompileResult(
                success=False, errors=1, warnings=0,
                messages=["Compile timeout"],
                log_path=""
            )
        except FileNotFoundError:
            raise RuntimeError(f"MetaEditor not found: {self.metaeditor_exe}")

        log_path = mq5.with_suffix(".log")
        return self._parse_log(log_path)

    def _parse_log(self, log_path: Path) -> CompileResult:
        if not log_path.exists():
            return CompileResult(
                success=False, errors=1, warnings=0,
                messages=["Log file not found after compile"],
                log_path=str(log_path)
            )

        # MetaEditor log encoding: UTF-16 LE
        try:
            content = log_path.read_text(encoding="utf-16-le", errors="replace")
        except Exception:
            content = log_path.read_text(encoding="utf-8", errors="replace")

        messages = [line.strip() for line in content.splitlines() if line.strip()]

        # Pattern: "Result: N error(s), N warning(s)"
        errors = 0
        warnings = 0
        for line in messages:
            m = re.search(r"(\d+) error", line, re.IGNORECASE)
            if m:
                errors = int(m.group(1))
            m = re.search(r"(\d+) warning", line, re.IGNORECASE)
            if m:
                warnings = int(m.group(1))

        return CompileResult(
            success=(errors == 0),
            errors=errors,
            warnings=warnings,
            messages=messages,
            log_path=str(log_path)
        )

    def compile_all(self, mq5_paths: list[str]) -> dict[str, CompileResult]:
        """Compile nhiều file, trả về dict path → result."""
        results = {}
        for path in mq5_paths:
            results[path] = self.compile(path)
        return results
```

---

## 5. Parse log — format mẫu

MetaEditor log thường có dạng:

```text
; MetaEditor log
; 2026.05.01 10:30:00
C:\...\PortfolioEA_Wyckoff.mq5 : information: compiling...
C:\...\Include\RiskManager.mqh : information: compiling...
C:\...\PortfolioEA_Wyckoff.mq5(145,12) : error 0: 'OrderSend' - wrong parameters count
C:\...\PortfolioEA_Wyckoff.mq5 : Result: 1 error(s), 2 warning(s)
```

Parser cần extract:
- Dòng chứa `error`: lấy file, line number, message
- Dòng `Result:`: lấy tổng error/warning

---

## 6. Structured error output

```python
@dataclass
class CompileError:
    file: str
    line: int
    column: int
    code: int
    message: str


def parse_error_lines(messages: list[str]) -> list[CompileError]:
    errors = []
    # Pattern: file.mq5(line,col) : error CODE: message
    pattern = re.compile(
        r"(.+?)\((\d+),(\d+)\)\s*:\s*error\s+(\d+):\s*(.+)"
    )
    for msg in messages:
        m = pattern.match(msg)
        if m:
            errors.append(CompileError(
                file=m.group(1).strip(),
                line=int(m.group(2)),
                column=int(m.group(3)),
                code=int(m.group(4)),
                message=m.group(5).strip()
            ))
    return errors
```

---

## 7. Pipeline integration

```python
# Trong run_pipeline.py — step 6: Compile MQL5

from build.mql5_compiler import MQL5Compiler
import yaml

with open("configs/mt5_paths.yaml") as f:
    paths = yaml.safe_load(f)

compiler = MQL5Compiler(
    metaeditor_exe=paths["metaeditor_exe"],
    log_dir=paths["compile_log_dir"]
)

targets = [
    f"{paths['mql5_root']}/Indicators/Wyckoff_Phase_Indicator.mq5",
    f"{paths['mql5_root']}/Experts/PortfolioEA_Wyckoff.mq5",
]

results = compiler.compile_all(targets)

for path, result in results.items():
    if not result.success:
        print(f"[COMPILE FAIL] {path}")
        for msg in result.messages:
            print(f"  {msg}")
        raise RuntimeError("Compile failed — pipeline stopped")
    else:
        print(f"[COMPILE OK] {path} — {result.warnings} warning(s)")
```

---

## 8. Retry policy khi compile lỗi

Compile lỗi thường do:
1. Include file chưa có → phải generate trước
2. Syntax error trong code AI sinh ra → cần loop lại Coder Agent

```text
Retry flow:
  compile FAIL
    → extract error messages
    → gửi error messages + file path về Coder Agent
    → Coder Agent sửa
    → compile lại
    → tối đa 3 lần retry
    → sau 3 lần vẫn FAIL → escalate to human
```

Không được tự ý thay đổi logic hoặc bỏ SL khi sửa compile error.

---

## 9. Dependency compile order

MQL5 có Include dependencies. Phải compile theo đúng thứ tự:

```text
Thứ tự compile:
1. Include/*.mqh       (không compile độc lập, nhưng kiểm tra syntax)
2. Indicators/*.mq5    (indicator trước)
3. Experts/*.mq5       (EA sau — phụ thuộc indicator và include)
```

Python phải biết dependency graph. Đơn giản nhất:

```python
COMPILE_ORDER = [
    "Include/ui/Theme.mqh",           # skip (mqh không compile thành ex5)
    "Indicators/Wyckoff_Phase_Indicator.mq5",
    "Experts/PortfolioEA_Wyckoff.mq5",
]
```

---

## 10. Log lưu trữ

Sau mỗi compile run, copy log về `python/build/logs/`:

```text
python/build/logs/
├── 20260501_103000_Wyckoff_Phase_Indicator.log
├── 20260501_103010_PortfolioEA_Wyckoff.log
└── compile_summary.csv
```

`compile_summary.csv` header:
```csv
timestamp,file,errors,warnings,status
```

---

## 11. Definition of Done

```text
✔ Python gọi MetaEditor64.exe với đúng path
✔ Log được đọc và parse ra errors/warnings
✔ Compile PASS khi errors = 0
✔ Compile FAIL khi errors > 0, có danh sách lỗi chi tiết
✔ Retry flow có giới hạn 3 lần
✔ Compile order đúng: Include → Indicator → EA
✔ Log được lưu với timestamp
✔ Pipeline dừng rõ ràng nếu compile fail
```
