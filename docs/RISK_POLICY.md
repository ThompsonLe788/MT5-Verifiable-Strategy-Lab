# RISK_POLICY.md

## 1. Mục tiêu

Bảo vệ tài khoản trước khi tối ưu lợi nhuận.

Nguyên tắc:

```text
Không rõ risk → không trade
Không SL → không trade
Không đủ dữ liệu → không dùng Kelly
Không QA PASS → không demo/live
```

---

## 2. Risk hard rules

```text
SL phải có trước entry
Không nới SL sau khi vào lệnh
Chỉ được:
- Dời SL về break-even
- Dời SL để giảm risk
- Dời SL để khóa lợi nhuận
Không được tăng risk sau entry
```

---

## 3. Risk per trade

Mặc định:

```text
Base risk per trade: 0.25%
Maximum risk per trade: 1.00%
```

Theo trạng thái:

| Trạng thái | Risk |
|---|---|
| Research/demo mới | 0.10%–0.25% |
| Strategy ổn định | 0.25%–0.50% |
| Portfolio đã validate | tối đa 1.00% |
| DD tăng | giảm 50% risk |
| DD vượt ngưỡng | stop |

---

## 4. Drawdown limits

```text
Daily loss limit: 2%–3%
Weekly loss warning: 4%
Max account DD stop: 6%–8%
Emergency stop: 10%
```

Nếu chạm ngưỡng:

```text
Daily loss hit → dừng trade trong ngày
Max DD hit → dừng toàn bộ EA
Emergency stop → tắt trading + alert
```

---

## 5. Portfolio exposure

```text
Max risk per symbol: 1%
Max portfolio open risk: 3%
Max correlated exposure: 2%
```

Không mở thêm lệnh nếu:

```text
Cùng chiều USD exposure quá cao
Nhiều strategy cùng tín hiệu cùng một symbol
Correlation drawdown cao
```

---

## 6. Kelly Criterion

### 6.1 Công thức

```text
f* = (bp - q) / b
```

Trong đó:

```text
b = reward/risk ratio
p = winrate
q = 1 - p
```

### 6.2 Quy định áp dụng

```text
Không dùng Full Kelly live
Chỉ dùng Fractional Kelly
Mặc định: 0.25 Kelly
Tối đa: 0.5 Kelly
Không dùng Kelly nếu sample < 100 trades
Ưu tiên sample >= 300 trades
Kelly phải bị cap bởi max risk
```

### 6.3 Công thức risk thực tế

```text
effective_risk = min(
    base_risk,
    fractional_kelly,
    max_risk_per_trade,
    drawdown_adjusted_risk
)
```

### 6.4 Drawdown adjustment

| Drawdown hiện tại | Kelly multiplier |
|---|---|
| DD < 2% | 1.0 |
| DD 2%–4% | 0.5 |
| DD 4%–6% | 0.25 |
| DD > 6% | 0 |

---

## 7. Lot size

```text
risk_amount = AccountBalance * effective_risk
lot = risk_amount / sl_value_per_lot
```

Điều kiện:

```text
lot >= SYMBOL_VOLUME_MIN
lot <= SYMBOL_VOLUME_MAX
lot phải theo SYMBOL_VOLUME_STEP
```

---

## 8. Stop Loss policy

SL phải được xác định trước entry.

SL hợp lệ nếu:

```text
SL khác 0
SL không quá gần stop level của broker
SL phù hợp với invalidation của strategy
SL value tính được bằng tiền
```

Nếu SL invalid:

```text
BLOCKED_NO_SL
BLOCKED_INVALID_STOPS
```

---

## 9. Take Profit / Exit policy

Mặc định phase đầu:

```text
Không trailing
Không partial close
Không martingale
Không grid
Không DCA
Lệnh đóng khi hit SL/TP hoặc strategy exit rule
```

Có thể thêm sau khi có spec riêng:

```text
Break-even
Trailing stop
Partial close
```

Nhưng không được thêm nếu chưa qua QA.

---

## 10. Execution risk

OrderSend policy:

```text
Max retry: 3
Retry delay: 500 ms
Retry allowed: REQUOTE, PRICE_CHANGED, TRADE_CONTEXT_BUSY
Hard fail: INVALID_STOPS, NOT_ENOUGH_MONEY, MARKET_CLOSED
```

Mọi lỗi phải log:

```text
timestamp,symbol,strategy,action,error_code,error_text
```

---

## 11. Spread filter

Cần hỗ trợ per-symbol spread.

Ví dụ mặc định:

```text
EURUSD: 20 points
GBPUSD: 30 points
USDJPY: 30 points
XAUUSD: 300 points
NAS100: broker-specific
```

Nếu spread vượt ngưỡng:

```text
BLOCKED_SPREAD_HIGH
```

---

## 12. Session filter

Mặc định UTC:

```text
London: 07:00–16:00 UTC
New York: 12:00–21:00 UTC
Overlap: 12:00–16:00 UTC
```

Nếu không nằm trong session cho phép:

```text
BLOCKED_SESSION_CLOSED
```

DST cần được ghi rõ theo broker/timezone trong config.

---

## 13. News filter

Chọn một trong 2 mode:

```text
Mode A: MQL5 Calendar API
Mode B: CSV manual news file
```

No-trade window mặc định:

```text
High-impact news:
- Không vào lệnh 30 phút trước news
- Không vào lệnh 30 phút sau news
```

Nếu news filter active:

```text
BLOCKED_NEWS_FILTER
```

---

## 14. Risk logging

Bắt buộc log mọi quyết định risk:

```csv
ts,symbol,strategy,decision,reason,risk_pct,kelly,dd,daily_pl,spread,session
```

---

## 15. Reject conditions

Strategy bị loại nếu:

```text
Expectancy <= 0
PF < 1.15
Max DD > 15%
OOS fail
Trade count quá thấp
Kelly âm hoặc quá bất ổn
Drawdown overlap cao với portfolio
```

---

## 16. Final principle

```text
Risk policy là luật.
Strategy chỉ là ứng viên.
Không strategy nào được quyền phá risk policy.
```
