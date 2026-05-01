# QA_GATE.md

## 1. Mục tiêu

QA_GATE là cổng bắt buộc trước khi cho phép một strategy/EA đi từ research sang demo.

Không qua QA_GATE thì:

```text
Không demo
Không live
Không optimize tiếp bằng tiền thật
```

---

## 2. Verdict

QA có 3 mức:

```text
PASS
CONDITIONAL PASS
FAIL
```

Quy định:

```text
PASS: được demo với risk nhỏ
CONDITIONAL PASS: phải sửa gap trước
FAIL: không được chạy
```

---

## 3. Checklist A → O

| Mục | Hạng mục | PASS nếu |
|---|---|---|
| A | Strategy & Rule | Có IF/THEN đo được, entry/SL/TP/invalidation |
| B | Multi-timeframe | Có TF1/TF2/TF3 và conflict rule |
| C | Indicator | Có logic detect, input/output, non-repaint |
| D | EA Architecture | Tuân thủ SOLID, tách module |
| E | Backtest | Có dataset, spread/slippage, sample size |
| F | Quant Metrics | Có winrate, expectancy, PF, DD, Sharpe |
| G | Optimization | Không dùng net profit đơn thuần |
| H | Validation | Có walk-forward/OOS |
| I | Risk | SL bắt buộc, DD limit, exposure cap |
| J | Kelly | Fractional Kelly, sample đủ, cap risk |
| K | Portfolio | Có correlation và risk allocation |
| L | UI/UX | Dashboard, blocked reason, alert |
| M | Auto Chart Setup | Tắt grid, chart shift, load indicator |
| N | Logging | decision_log, error_log, trade_log |
| O | Deployment | demo checklist, rollback, monitoring |
| P | Monte Carlo | 1000 sim, median DD <= threshold, ruin rate < 1% |
| Q | Regime Test | Test qua ít nhất 1 trending + 1 ranging period |

---

## 4. Hard fail conditions

Bất kỳ lỗi nào dưới đây = FAIL ngay:

```text
Không có SL trước entry
Có logic nới SL sau entry
Indicator repaint nhưng không cảnh báo
Không có trade_log
Không có OOS
Không có DD limit
Không có blocked reason
Không có source cho hypothesis
Không có rule IF/THEN
Không có invalidation condition
```

---

## 5. Minimum quantitative thresholds

Mức tối thiểu để được demo:

```text
Total trades: >= 200
OOS trades: >= 50
Expectancy: > 0
Profit Factor: >= 1.15
Max DD: <= 15%
Sharpe: > 0.5
OOS performance không giảm quá 50% so với IS
```

Lưu ý:

```text
Đây là ngưỡng tối thiểu để demo, không phải để live lớn.
```

---

## 6. Kelly QA

Kelly chỉ PASS nếu:

```text
Sample >= 100 trades
Ưu tiên >= 300 trades
Full Kelly không dùng live
Fractional Kelly <= 0.5
Risk per trade cap <= 1%
Portfolio risk cap <= 3%
Kelly giảm khi drawdown tăng
```

Fail nếu:

```text
Dùng Full Kelly live
Dùng Kelly khi sample < 100
Không có drawdown guard
Không có cap risk
```

---

## 7. UI/UX QA

PASS nếu dashboard trả lời được trong 5 giây:

```text
EA đang ON/OFF?
Có trade được không?
Nếu không, vì sao?
Strategy nào?
Risk bao nhiêu?
DD hiện tại?
TF1/TF2/TF3 trạng thái gì?
```

Fail nếu:

```text
EA không trade nhưng không có reason
Dashboard che chart
Alert spam liên tục
Không phân biệt PREVIEW_SIGNAL và CONFIRMED_SIGNAL
```

---

## 8. Deployment gate

Trước demo:

```text
Compile không lỗi
Backtest pass
OOS pass
QA pass
Risk policy pass
UI pass
Log pass
```

Trước live nhỏ:

```text
Demo forward test >= 2–4 tuần
Không lỗi execution nghiêm trọng
DD demo trong ngưỡng
Performance không lệch quá mạnh so với OOS
```

---

## 9. QA report format

```text
# QA REPORT

Strategy:
Symbol:
Timeframe:
Version:
Date:

## Verdict
PASS / CONDITIONAL PASS / FAIL

## Critical Issues
...

## Major Issues
...

## Minor Issues
...

## Metrics
...

## Required Fixes
...

## Final Decision
...
```

---

## 10. Monte Carlo QA (Mục P)

### 10.1 Mục đích

Monte Carlo kiểm tra **robustness** — strategy có sống được nếu thứ tự trades khác đi không? Một strategy tốt không phụ thuộc vào "chuỗi hên" cụ thể.

### 10.2 Phương pháp

```python
# python/validator/monte_carlo.py

import numpy as np
import pandas as pd

def run_monte_carlo(
    profits: list[float],
    n_simulations: int = 1000,
    initial_capital: float = 10000.0,
) -> dict:
    results = []
    for _ in range(n_simulations):
        shuffled = np.random.permutation(profits)
        equity = initial_capital + np.cumsum(shuffled)
        peak   = np.maximum.accumulate(equity)
        dd     = (equity - peak) / peak
        max_dd = float(dd.min())
        final  = float(equity[-1])
        ruin   = float(equity.min()) < initial_capital * 0.5   # mất > 50%
        results.append({"max_dd": max_dd, "final": final, "ruin": ruin})

    df = pd.DataFrame(results)
    return {
        "median_max_dd":  float(df["max_dd"].median()),
        "p95_max_dd":     float(df["max_dd"].quantile(0.95)),
        "ruin_rate":      float(df["ruin"].mean()),
        "median_final":   float(df["final"].median()),
        "n_simulations":  n_simulations,
    }
```

### 10.3 Pass/Fail thresholds

```text
PASS nếu:
  median max DD   <= 15%
  p95 max DD      <= 25%
  ruin rate       < 1%   (< 10 simulations trong 1000 bị ruin)

FAIL nếu:
  ruin rate       >= 1%
  p95 max DD      > 25%
```

### 10.4 Sensitivity test (bổ sung)

```text
Chạy thêm với spread tăng 50% so với backtest:
  Nếu expectancy drop > 30% → WARNING
  Nếu expectancy âm        → FAIL
```

---

## 11. Regime Test QA (Mục Q)

### 11.1 Mục đích

Strategy phải được test trong ít nhất 2 market regime khác nhau để tránh overfitting vào 1 giai đoạn thị trường.

### 11.2 Phân loại regime

```python
# python/validator/regime_detector.py

import pandas as pd
import numpy as np

def classify_regime(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """
    Phân loại từng bar thành: TREND_UP / TREND_DOWN / RANGING / HIGH_VOL

    df cần có cột: close, high, low
    """
    close = df["close"]
    high  = df["high"]
    low   = df["low"]

    # ADX proxy: dùng ATR và price range
    atr   = (high - low).rolling(14).mean()
    roc   = close.pct_change(window)
    hurst = close.rolling(window).std() / close.rolling(window).mean()

    regime = pd.Series("RANGING", index=df.index)
    regime[roc > 0.03]  = "TREND_UP"
    regime[roc < -0.03] = "TREND_DOWN"
    regime[atr > atr.rolling(50).mean() * 1.5] = "HIGH_VOL"

    return regime
```

### 11.3 Backtest per regime

```python
def backtest_per_regime(trade_log: pd.DataFrame, price_df: pd.DataFrame) -> dict:
    """Tính metrics cho từng regime."""
    regimes = classify_regime(price_df)
    trade_log = trade_log.copy()
    trade_log["regime"] = trade_log["timestamp"].map(
        lambda ts: regimes.asof(ts) if ts in regimes.index else "UNKNOWN"
    )

    results = {}
    for regime, group in trade_log.groupby("regime"):
        wins   = group[group["profit"] > 0]
        losses = group[group["profit"] <= 0]
        results[regime] = {
            "trades":   len(group),
            "winrate":  len(wins) / len(group) if len(group) > 0 else 0,
            "pf":       wins["profit"].sum() / abs(losses["profit"].sum())
                        if len(losses) > 0 else 999,
        }
    return results
```

### 11.4 Pass/Fail

```text
PASS nếu:
  Strategy được test trong ít nhất 2 regime (ví dụ: TREND + RANGING)
  Mỗi regime có ít nhất 30 trades
  Không có regime nào có PF < 0.8 (tức là không thua nặng trong 1 regime cụ thể)

FAIL nếu:
  Toàn bộ trades đến từ 1 regime duy nhất
  Có regime nào có PF < 0.8

WARNING nếu:
  Một regime có PF 0.8–1.0 → cần ghi rõ trong QA report
```

---

## 12. Rule cuối

```text
QA Gate không phải thủ tục.
QA Gate là nơi chặn EA xấu trước khi nó chạm tài khoản.
Monte Carlo và Regime Test là lớp bảo vệ cuối cùng chống overfitting.
```
