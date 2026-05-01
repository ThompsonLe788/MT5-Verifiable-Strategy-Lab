# Agent 11 — Monitoring Agent

**Nhiệm vụ:** Theo dõi performance live/demo, phát hiện strategy decay, so sánh với OOS benchmark, trigger action tự động.

---

## 1. Vị trí trong pipeline

```text
[10 Deployment Agent] → EA chạy demo/live
                              ↓
                    [11 Monitoring Agent]  ← chạy scheduled (daily/weekly)
                              ↓
              ┌───────────────┼───────────────┐
           Normal          Warning          Critical
           (tiếp tục)    (giảm risk)    (pause + alert)
```

---

## 2. Trigger schedule

```text
Daily check:   Mỗi ngày sau khi thị trường đóng (00:30 UTC)
Weekly check:  Thứ Hai 01:00 UTC (review tuần trước)
On-demand:     Python CLI / n8n trigger
```

---

## 3. Input

```text
Bắt buộc:
  logs/trade_log.csv              ← trades live/demo đang chạy
  strategies/<name>/validation_report.md  ← OOS benchmark metrics
  configs/risk.yaml               ← ngưỡng alert/action

Tùy chọn:
  MT5 Global Variables            ← đọc qua connector.py
  account equity history          ← qua connector.get_closed_deals()
```

---

## 4. Metrics tính toán

### 4.1 Rolling window metrics

Tính trên N trades gần nhất (mặc định N=50):

```python
def rolling_metrics(df: pd.DataFrame, window: int = 50) -> dict:
    recent = df.tail(window)
    wins   = recent[recent["profit"] > 0]
    losses = recent[recent["profit"] <= 0]

    winrate     = len(wins) / len(recent) if len(recent) > 0 else 0
    avg_win     = wins["profit"].mean() if len(wins) > 0 else 0
    avg_loss    = abs(losses["profit"].mean()) if len(losses) > 0 else 1
    expectancy  = (winrate * avg_win) - ((1 - winrate) * avg_loss)
    pf          = wins["profit"].sum() / abs(losses["profit"].sum()) if len(losses) > 0 else 999

    return {
        "window":     window,
        "trades":     len(recent),
        "winrate":    winrate,
        "expectancy": expectancy,
        "profit_factor": pf,
    }
```

### 4.2 So sánh live vs OOS benchmark

```python
def decay_check(live: dict, oos_benchmark: dict) -> dict:
    """
    Trả về severity: NORMAL / WARNING / CRITICAL
    """
    winrate_drop = oos_benchmark["winrate"] - live["winrate"]
    pf_drop      = oos_benchmark["profit_factor"] - live["profit_factor"]
    exp_drop     = oos_benchmark["expectancy"] - live["expectancy"]

    if winrate_drop > 0.15 or pf_drop > 0.5 or exp_drop < 0:
        severity = "CRITICAL"
    elif winrate_drop > 0.08 or pf_drop > 0.25:
        severity = "WARNING"
    else:
        severity = "NORMAL"

    return {
        "severity":      severity,
        "winrate_drop":  winrate_drop,
        "pf_drop":       pf_drop,
        "exp_drop":      exp_drop,
    }
```

### 4.3 Drawdown monitor

```python
def current_dd(df: pd.DataFrame) -> float:
    """Tính drawdown hiện tại từ peak equity."""
    equity_curve = df["profit"].cumsum()
    peak = equity_curve.cummax()
    dd   = (equity_curve - peak) / (peak.abs() + 1e-9)
    return float(dd.iloc[-1])
```

---

## 5. Action rules

| Điều kiện | Severity | Action |
|---|---|---|
| Winrate drop < 8%, PF > 1.0 | NORMAL | Ghi log, không làm gì |
| Winrate drop 8–15% hoặc PF 0.75–1.0 | WARNING | Giảm Kelly 50%, gửi alert |
| Winrate drop > 15% hoặc PF < 0.75 hoặc expectancy < 0 | CRITICAL | Pause strategy, set KILL via GV, gửi alert |
| Daily DD > 3% | CRITICAL | Pause all EA ngày hôm đó |
| Total DD > 6% | CRITICAL | Pause + yêu cầu human review |

### 5.1 Pause strategy

```python
def pause_strategy(connector, magic_base: int, reason: str):
    """Set kill switch via MT5 Global Variable."""
    kill_key = f"QT_{magic_base}_KILL"
    connector.gv_set(kill_key, 1.0)
    logger.critical(f"[MONITORING] Strategy paused: {reason}")
```

### 5.2 Resume strategy

```python
def resume_strategy(connector, magic_base: int):
    """Human hoặc agent xác nhận → clear kill switch."""
    kill_key = f"QT_{magic_base}_KILL"
    connector.gv_set(kill_key, 0.0)
    logger.info(f"[MONITORING] Strategy resumed")
```

---

## 6. Alert output

Alert ghi vào file và stdout. Extension sau có thể thêm Telegram/email.

```python
# python/monitoring/alert.py

import logging
from datetime import datetime
from pathlib import Path

def send_alert(severity: str, strategy: str, message: str, log_dir: str = "logs"):
    ts = datetime.utcnow().strftime("%Y-%m-%d %Human:%M:%S")
    line = f"[{ts}] [{severity}] [{strategy}] {message}"

    log_path = Path(log_dir) / "monitoring_alert.log"
    with open(log_path, "a") as f:
        f.write(line + "\n")

    if severity == "CRITICAL":
        logging.critical(line)
    elif severity == "WARNING":
        logging.warning(line)
    else:
        logging.info(line)
```

---

## 7. Full monitoring run (Python)

```python
# python/monitoring/run_monitor.py

import yaml
import pandas as pd
from pathlib import Path
from mt5_interface.connector import get_connector
from monitoring.alert import send_alert

def load_oos_benchmark(strategy_name: str) -> dict:
    """Đọc metrics từ validation_report.md (hoặc metrics.csv)."""
    path = Path(f"strategies/{strategy_name}/metrics.csv")
    if not path.exists():
        raise FileNotFoundError(f"OOS metrics không tìm thấy: {path}")
    df = pd.read_csv(path)
    # Lấy hàng OOS
    oos = df[df["type"] == "OOS"].iloc[-1]
    return {
        "winrate": float(oos["winrate"]),
        "profit_factor": float(oos["profit_factor"]),
        "expectancy": float(oos["expectancy"]),
    }

def run_monitoring(strategy_name: str, magic_base: int, mt5_paths: dict):
    # 1. Load live trade log
    log_path = Path("logs/trade_log.csv")
    if not log_path.exists():
        send_alert("WARNING", strategy_name, "trade_log.csv không tìm thấy")
        return

    df = pd.read_csv(log_path, parse_dates=["timestamp"])
    df_strategy = df[df["strategy"] == strategy_name]

    if len(df_strategy) < 20:
        send_alert("NORMAL", strategy_name, f"Chưa đủ data: {len(df_strategy)} trades")
        return

    # 2. Tính rolling metrics
    live_metrics = rolling_metrics(df_strategy, window=50)

    # 3. Load OOS benchmark
    oos_benchmark = load_oos_benchmark(strategy_name)

    # 4. Decay check
    result = decay_check(live_metrics, oos_benchmark)
    severity = result["severity"]

    # 5. DD check
    dd = current_dd(df_strategy)
    if dd < -0.06:
        severity = "CRITICAL"
        result["reason"] = f"DD = {dd:.1%} vượt ngưỡng 6%"

    # 6. Action
    msg = (
        f"winrate={live_metrics['winrate']:.1%} (OOS={oos_benchmark['winrate']:.1%}), "
        f"PF={live_metrics['profit_factor']:.2f} (OOS={oos_benchmark['profit_factor']:.2f}), "
        f"DD={dd:.1%}"
    )
    send_alert(severity, strategy_name, msg)

    if severity == "CRITICAL":
        with get_connector(mt5_paths) as conn:
            pause_strategy(conn, magic_base, msg)

    # 7. Ghi monitoring report
    report = {
        "timestamp": pd.Timestamp.utcnow(),
        "strategy": strategy_name,
        "severity": severity,
        "live_trades": live_metrics["trades"],
        "live_winrate": live_metrics["winrate"],
        "live_pf": live_metrics["profit_factor"],
        "oos_winrate": oos_benchmark["winrate"],
        "oos_pf": oos_benchmark["profit_factor"],
        "current_dd": dd,
    }
    out = Path("logs/monitoring_report.csv")
    pd.DataFrame([report]).to_csv(
        out, mode="a", header=not out.exists(), index=False
    )
```

---

## 8. Param expiry check

Strategy params có thể expire sau thời gian optimize. Monitoring Agent kiểm tra:

```python
def check_param_expiry(strategy_name: str, max_months: int = 6) -> bool:
    """True nếu params đã quá hạn và cần re-optimize."""
    params_path = Path(f"strategies/{strategy_name}/best_params.json")
    if not params_path.exists():
        return True

    import json, datetime
    with open(params_path) as f:
        data = json.load(f)

    optimize_date = datetime.datetime.fromisoformat(data.get("optimized_at", "2000-01-01"))
    age_months = (datetime.datetime.utcnow() - optimize_date).days / 30

    if age_months > max_months:
        send_alert("WARNING", strategy_name,
                   f"Params đã {age_months:.0f} tháng, cần re-optimize")
        return True
    return False
```

---

## 9. Không được làm

```text
❌ Không tự thay đổi params EA đang chạy
❌ Không tự restart EA
❌ Không tự live trade
❌ Không set KILL mà không ghi log lý do
❌ Không resume strategy mà không có human confirmation (CRITICAL cases)
```

---

## 10. Output files

```text
logs/monitoring_alert.log       ← tất cả alert
logs/monitoring_report.csv      ← history mỗi lần chạy
```

`monitoring_report.csv` header:
```csv
timestamp,strategy,severity,live_trades,live_winrate,live_pf,oos_winrate,oos_pf,current_dd
```

---

## 11. Definition of Done

```text
✔ Chạy được daily scheduled
✔ So sánh đúng live metrics vs OOS benchmark
✔ Phát hiện decay (winrate drop > 15% hoặc PF < 0.75)
✔ Set KILL via Global Variable khi CRITICAL
✔ Ghi alert log rõ severity + reason
✔ Ghi monitoring_report.csv sau mỗi run
✔ Không tự resume — chờ human
✔ Kiểm tra param expiry mỗi tuần
```
