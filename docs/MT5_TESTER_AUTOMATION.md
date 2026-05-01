# MT5_TESTER_AUTOMATION.md

**Mục tiêu:** Spec kỹ thuật để Python tự động chạy MT5 Strategy Tester, không cần thao tác GUI.

---

## 1. Tổng quan cơ chế

MT5 hỗ trợ chạy backtest qua command-line bằng file `.ini`. Python tạo file ini, gọi `terminal64.exe`, đợi kết quả, parse output.

```text
Python script
  → tạo tester.ini
  → subprocess.run(terminal64.exe /config:tester.ini)
  → đợi MT5 đóng
  → parse tester_report.htm
  → parse trade_log.csv (export từ report)
  → trả về metrics dict
```

---

## 2. Điều kiện tiên quyết

```text
1. MT5 đã cài, đường dẫn terminal64.exe đã biết
2. EA đã compile thành .ex5, nằm trong MQL5/Experts/
3. Symbol có đủ history trong MT5 Data Center
4. MT5 có thể chạy ở chế độ không có tài khoản đăng nhập (offline history)
```

Config đường dẫn trong `configs/mt5_paths.yaml`:

```yaml
terminal_exe: "C:/Program Files/MetaTrader 5/terminal64.exe"
portable_dir: "C:/Users/<user>/AppData/Roaming/MetaQuotes/Terminal/<ID>"
experts_dir: "MQL5/Experts"
tester_ini_dir: "python/backtest/ini"
tester_report_dir: "python/backtest/reports"
```

---

## 3. Cấu trúc file tester.ini

File ini điều khiển toàn bộ tham số backtest.

### 3.1 Template chuẩn

```ini
[Tester]
Expert=Experts\PortfolioEA_Wyckoff.ex5
Symbol=XAUUSD
Period=M15
Optimization=0
Model=1
FromDate=2020.01.01
ToDate=2023.12.31
ForwardMode=0
Deposit=10000
Currency=USD
ProfitInPips=0
Leverage=100
ExecutionMode=0
OptimizationCriterion=0

[TesterInputs]
EnableTrading=true
MagicNumber=20260501
RiskPerTradePct=0.25
MaxDailyLossPct=3.0
TF1_Bias=16385
TF2_Setup=16388
TF3_Entry=900
EnableWyckoff=true
```

### 3.2 Giải thích các trường quan trọng

| Field | Giá trị | Ý nghĩa |
|---|---|---|
| Expert | đường dẫn .ex5 | Relative từ portable_dir/MQL5 |
| Period | M1/M5/M15/H1/H4/D1 | Timeframe entry (TF3) |
| Model | 0/1/2 | 0=Every tick, 1=OHLC M1, 2=Open price |
| Optimization | 0/1/2 | 0=backtest, 1=optimize, 2=forward |
| ForwardMode | 0/1/2/3 | 0=off, 1=1/2, 2=1/3, 3=custom |
| FromDate | YYYY.MM.DD | Ngày bắt đầu |
| ToDate | YYYY.MM.DD | Ngày kết thúc |

### 3.3 Period enum values

```python
PERIOD_MAP = {
    "M1": 1, "M5": 5, "M15": 15, "M30": 30,
    "H1": 16385, "H4": 16388, "D1": 16408,
    "W1": 32769, "MN1": 49153
}
```

---

## 4. Python: TesterRunner class

```python
# python/backtest/tester_runner.py

import subprocess
import os
import time
import configparser
from pathlib import Path
from datetime import datetime


class MT5TesterRunner:

    def __init__(self, mt5_paths: dict):
        self.terminal_exe = mt5_paths["terminal_exe"]
        self.portable_dir = Path(mt5_paths["portable_dir"])
        self.ini_dir = Path(mt5_paths["tester_ini_dir"])
        self.report_dir = Path(mt5_paths["tester_report_dir"])
        self.ini_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def build_ini(self, config: dict) -> Path:
        """Tạo file .ini từ config dict, trả về path."""
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        ini_path = self.ini_dir / f"tester_{run_id}.ini"

        cp = configparser.ConfigParser()
        cp["Tester"] = {
            "Expert":            config["expert_path"],
            "Symbol":            config["symbol"],
            "Period":            str(config["period"]),
            "Optimization":      "0",
            "Model":             str(config.get("model", 1)),
            "FromDate":          config["from_date"],
            "ToDate":            config["to_date"],
            "ForwardMode":       str(config.get("forward_mode", 0)),
            "Deposit":           str(config.get("deposit", 10000)),
            "Currency":          config.get("currency", "USD"),
            "Leverage":          str(config.get("leverage", 100)),
            "ExecutionMode":     "0",
            "OptimizationCriterion": "0",
        }
        cp["TesterInputs"] = config.get("inputs", {})

        with open(ini_path, "w") as f:
            cp.write(f)

        return ini_path

    def run(self, ini_path: Path, timeout_seconds: int = 3600) -> bool:
        """Chạy MT5 với ini file. Trả về True nếu thành công."""
        cmd = [
            self.terminal_exe,
            f"/config:{ini_path}",
            "/portable",
        ]
        try:
            result = subprocess.run(
                cmd,
                timeout=timeout_seconds,
                check=False,
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False
        except FileNotFoundError:
            raise RuntimeError(f"terminal64.exe không tìm thấy: {self.terminal_exe}")

    def find_latest_report(self) -> Path | None:
        """Tìm report mới nhất trong thư mục tester."""
        tester_reports = self.portable_dir / "tester" / "cache"
        htm_files = list(tester_reports.glob("*.htm"))
        if not htm_files:
            return None
        return max(htm_files, key=lambda f: f.stat().st_mtime)

    def run_backtest(self, config: dict) -> dict:
        """Full flow: tạo ini → chạy MT5 → parse kết quả."""
        ini_path = self.build_ini(config)
        success = self.run(ini_path)

        if not success:
            return {"status": "FAILED", "reason": "MT5 process exited non-zero"}

        report_path = self.find_latest_report()
        if report_path is None:
            return {"status": "FAILED", "reason": "Report not found"}

        return {"status": "OK", "report_path": str(report_path), "ini_path": str(ini_path)}
```

---

## 5. Export trade log từ MT5

MT5 không tự export CSV từ command-line. Có 2 cách:

### 5.1 Cách A — Export từ EA trong OnTester()

EA ghi trade log ra file CSV trong `OnTester()`:

```cpp
void OnTester()
{
   // Được gọi sau khi backtest kết thúc
   ExportTradeLogToCSV("trade_log.csv");
}
```

File được lưu tại `MQL5/Files/trade_log.csv`.

Python đọc từ đường dẫn đó sau khi MT5 đóng.

### 5.2 Cách B — Parse report HTML

MT5 tạo file `.htm` chứa bảng thống kê. Python parse bằng `BeautifulSoup`:

```python
from bs4 import BeautifulSoup

def parse_tester_report(report_path: str) -> dict:
    with open(report_path, encoding="utf-16") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    metrics = {}
    tables = soup.find_all("table")
    # Table đầu tiên: summary metrics
    # Table thứ hai: danh sách trades
    # ... parse theo cấu trúc report MT5
    return metrics
```

**Lưu ý:** Report MT5 encoding là UTF-16.

### 5.3 Cách C — MetaTrader5 Python library (recommended)

```python
import MetaTrader5 as mt5

mt5.initialize()
deals = mt5.history_deals_get(from_date, to_date)
# Trả về danh sách deal objects
mt5.shutdown()
```

Cách này cần MT5 đang chạy và đăng nhập. Phù hợp hơn cho forward test / demo monitor.

**Khuyến nghị:**
- Backtest automation: dùng cách A (EA export CSV trong OnTester)
- Demo/live monitoring: dùng cách C (MT5 Python library)

---

## 6. Python: TradeLogParser

```python
# python/backtest/trade_log_parser.py

import pandas as pd
from pathlib import Path


REQUIRED_COLUMNS = [
    "timestamp", "symbol", "strategy", "direction",
    "entry", "sl", "tp", "exit", "profit",
    "r_multiple", "commission", "swap", "spread"
]


def parse_trade_log(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, parse_dates=["timestamp"])

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    df = df.dropna(subset=["entry", "exit", "profit"])
    return df


def validate_sample_size(df: pd.DataFrame, min_trades: int = 200) -> bool:
    return len(df) >= min_trades
```

---

## 7. Walk-Forward automation

Để chạy N folds walk-forward, Python tạo nhiều ini file với date range khác nhau:

```python
# python/backtest/walk_forward.py

from dateutil.relativedelta import relativedelta
from datetime import date


def generate_wf_folds(
    start: date,
    end: date,
    train_months: int = 12,
    test_months: int = 3
) -> list[dict]:
    """Tạo danh sách (train_from, train_to, test_from, test_to)."""
    folds = []
    cursor = start

    while True:
        train_from = cursor
        train_to = cursor + relativedelta(months=train_months)
        test_from = train_to
        test_to = test_from + relativedelta(months=test_months)

        if test_to > end:
            break

        folds.append({
            "train_from": train_from.strftime("%Y.%m.%d"),
            "train_to":   train_to.strftime("%Y.%m.%d"),
            "test_from":  test_from.strftime("%Y.%m.%d"),
            "test_to":    test_to.strftime("%Y.%m.%d"),
        })
        cursor += relativedelta(months=test_months)

    return folds


def run_walk_forward(runner, base_config: dict, folds: list) -> list:
    results = []
    for i, fold in enumerate(folds):
        print(f"[WF] Fold {i+1}/{len(folds)}: {fold['train_from']} → {fold['test_to']}")

        # IS backtest
        is_config = {**base_config, "from_date": fold["train_from"], "to_date": fold["train_to"]}
        is_result = runner.run_backtest(is_config)

        # OOS backtest
        oos_config = {**base_config, "from_date": fold["test_from"], "to_date": fold["test_to"]}
        oos_result = runner.run_backtest(oos_config)

        results.append({"fold": i+1, "is": is_result, "oos": oos_result})

    return results
```

---

## 8. Error handling

| Tình huống | Xử lý |
|---|---|
| terminal64.exe không tìm thấy | Raise RuntimeError, log đường dẫn |
| MT5 timeout (quá lớn) | subprocess timeout, log cảnh báo, tăng timeout_seconds |
| Report không tìm thấy | Check tester cache path, log, trả về FAILED |
| CSV thiếu cột | ValueError rõ ràng từ parser |
| MT5 cần đăng nhập | Cấu hình demo account trong MT5 trước khi chạy |

---

## 9. Pipeline integration

Trong `python/orchestrator/run_pipeline.py`:

```python
from backtest.tester_runner import MT5TesterRunner
from backtest.trade_log_parser import parse_trade_log, validate_sample_size
import yaml

# Load paths
with open("configs/mt5_paths.yaml") as f:
    mt5_paths = yaml.safe_load(f)

runner = MT5TesterRunner(mt5_paths)

# Backtest config
config = {
    "expert_path": r"Experts\PortfolioEA_Wyckoff.ex5",
    "symbol": "XAUUSD",
    "period": 15,            # M15
    "from_date": "2020.01.01",
    "to_date": "2023.12.31",
    "model": 1,
    "deposit": 10000,
    "inputs": {
        "RiskPerTradePct": "0.25",
        "EnableWyckoff": "true",
    }
}

result = runner.run_backtest(config)

if result["status"] != "OK":
    raise RuntimeError(f"Backtest failed: {result['reason']}")

df = parse_trade_log("MQL5/Files/trade_log.csv")

if not validate_sample_size(df, min_trades=200):
    raise RuntimeError(f"Không đủ sample: {len(df)} trades")
```

---

## 10. Definition of Done

```text
✔ Python tạo được ini file từ config dict
✔ Python gọi terminal64.exe và đợi kết thúc
✔ EA export trade_log.csv trong OnTester()
✔ Python parse trade_log.csv thành DataFrame
✔ Python validate sample size >= 200 trades
✔ Walk-forward tạo được N folds và chạy tuần tự
✔ Mọi lỗi đều được log rõ ràng, không crash silent
```
