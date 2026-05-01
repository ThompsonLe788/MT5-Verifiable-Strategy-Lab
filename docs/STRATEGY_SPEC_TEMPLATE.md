# STRATEGY_SPEC_TEMPLATE.md

**Mục tiêu:** Template chuẩn cho tất cả file trong `strategies/<name>/`. Agent nào cũng phải tuân theo schema này.

> Mỗi strategy là một folder. Không đủ 5 file bắt buộc → không được code EA.

---

## Cấu trúc folder strategy

```text
strategies/<strategy_name>/
├── hypothesis.md           [BẮT BUỘC]
├── rule_spec.md            [BẮT BUỘC]
├── indicator_spec.md       [BẮT BUỘC]
├── ea_params.yaml          [BẮT BUỘC]
├── optimization_space.yaml [BẮT BUỘC]
├── validation_report.md    [TẠO SAU backtest]
├── qa_report.md            [TẠO SAU QA gate]
└── README.md               [TÙY CHỌN]
```

---

## FILE 1: hypothesis.md

```markdown
# Hypothesis — <STRATEGY_NAME>

## 1. Nguồn lý thuyết

| Nguồn | Tác giả | Độ uy tín | Concept trích xuất |
|---|---|---|---|
| <tên sách/paper> | <tác giả> | HIGH/MEDIUM/LOW | <concept> |

## 2. Hypothesis chính

**Phát biểu:**
> <Phát biểu rõ ràng: "Khi X xảy ra trên TF1, Y xảy ra trên TF2, thì Z xảy ra trên TF3 với xác suất cao hơn random">

**Edge giả định:**
- Lý do thị trường tạo ra edge này:
- Lý do edge có thể biến mất:

## 3. Symbol universe dự kiến

```text
Symbols: XAUUSD, EURUSD, ...
Timeframe entry (TF3): M15
```

## 4. Điều kiện reject hypothesis (trước khi code)

```text
- Nếu edge phụ thuộc vào pattern mà chỉ xảy ra < 20 lần/năm → reject
- Nếu không đo được bằng OHLC/volume/ATR → reject
- Nếu cần "judgment" của trader → reject
```

## 5. Trạng thái

```text
Ngày tạo:
Người tạo:
Status: DRAFT / APPROVED / REJECTED
Approved by:
```
```

---

## FILE 2: rule_spec.md

```markdown
# Rule Spec — <STRATEGY_NAME>

> Mọi điều kiện phải đo được bằng OHLC, ATR, volume, swing high/low, spread, session.
> Không dùng từ mơ hồ.

## 1. Multi-Timeframe Assignment

| TF | Timeframe | Nhiệm vụ |
|---|---|---|
| TF1 | H4 | Xác định bias |
| TF2 | H1 | Xác định setup |
| TF3 | M15 | Xác định entry |

## 2. TF1 — Bias Rule

```text
BULL bias khi:
  - <điều kiện đo được, ví dụ: Close[0] > EMA(50) trên H4>
  - <điều kiện 2>

BEAR bias khi:
  - <điều kiện đo được>

RANGE khi:
  - Không thỏa BULL và BEAR
```

## 3. TF2 — Setup Rule

```text
SETUP LONG khi:
  - TF1 bias = BULL
  - <điều kiện TF2 cụ thể>

SETUP SHORT khi:
  - TF1 bias = BEAR
  - <điều kiện TF2 cụ thể>

NONE khi:
  - Không thỏa điều kiện trên
```

## 4. TF3 — Entry Rule

```text
ENTRY LONG khi:
  - TF2 = SETUP LONG
  - <trigger entry cụ thể, ví dụ: Candle breakout + close>

ENTRY SHORT khi:
  - TF2 = SETUP SHORT
  - <trigger entry cụ thể>
```

## 5. Stop Loss

```text
SL LONG: <mô tả cụ thể, ví dụ: Below swing low của TF3, tối thiểu 1 ATR(14)>
SL SHORT: <mô tả cụ thể>

SL minimum distance: <X> points hoặc <X> * ATR
SL maximum distance: <X> * ATR (nếu vượt → không trade)
```

## 6. Take Profit

```text
TP1: <mức giá hoặc R-multiple, ví dụ: 2R từ entry>
TP2: <nếu có partial close sau này>

Exit rule khác: <ví dụ: đóng lệnh nếu TF2 flip>
```

## 7. Invalidation

```text
Signal bị invalidate khi:
  - <điều kiện xảy ra sau khi signal hình thành nhưng trước khi entry>
  - Ví dụ: Price đã vượt qua SL level trước khi order filled
```

## 8. No-trade conditions

```text
Không trade khi:
  - TF1 ≠ bias rõ ràng (RANGE)
  - Spread > <ngưỡng>
  - Session không phải London/NY
  - High-impact news trong vòng 30 phút
  - Daily DD đã chạm giới hạn
  - Candle size > 3 * ATR(14) (volatility spike)
```

## 9. Parameters

| Parameter | Default | Range | Ý nghĩa |
|---|---|---|---|
| <param_1> | <val> | <min>–<max> | <mô tả> |
| <param_2> | <val> | <min>–<max> | <mô tả> |

## 10. Data required

```text
OHLCV: TF1, TF2, TF3
ATR(14): TF3
Swing high/low: TF2, TF3
Volume: TF3 (nếu cần)
Spread: real-time
Session time: UTC
News: calendar
```

## 11. Trạng thái

```text
Ngày tạo:
Status: DRAFT / APPROVED / REJECTED
Review notes:
```
```

---

## FILE 3: indicator_spec.md

```markdown
# Indicator Spec — <STRATEGY_NAME>

## 1. Danh sách indicator cần xây

| Indicator | Nhiệm vụ | Non-repaint |
|---|---|---|
| <IndicatorName>.mq5 | <detect gì> | YES/NO + lý do |

## 2. Spec từng indicator

### <IndicatorName>

**Inputs:**
```cpp
input int    Period = 14;
input double Threshold = 0.5;
// ...
```

**Buffers:**
```cpp
// Buffer 0: signal (1=long, -1=short, 0=none)
// Buffer 1: level giá (SL level, zone boundary,...)
```

**Detection logic (pseudocode):**
```text
IF <điều kiện> THEN
  Buffer[0][i] = 1
ELSE IF <điều kiện> THEN
  Buffer[0][i] = -1
ELSE
  Buffer[0][i] = 0
```

**Non-repaint policy:**
```text
Chỉ set buffer khi candle đã closed (shift=1 hoặc OnCalculate với prev_calculated)
Không dùng candle hiện tại (shift=0) để confirm signal
```

**Drawing objects:**
```text
- Vẽ gì: <zone, line, label>
- Giới hạn số object: max <N>
- Màu: theo bảng màu chuẩn
```

**UI dashboard (indicator):**
```text
Bias: UP/DOWN/RANGE
Structure: BOS/CHOCH/NONE
Volatility: LOW/NORMAL/HIGH
```
```

---

## FILE 4: ea_params.yaml

```yaml
# ea_params.yaml — <STRATEGY_NAME>

strategy:
  name: "<StrategyName>"
  version: "1.0"
  symbol: "XAUUSD"
  magic_base: 20260501

timeframes:
  tf1: "H4"
  tf2: "H1"
  tf3: "M15"

risk:
  risk_per_trade_pct: 0.25
  max_daily_loss_pct: 3.0
  max_symbol_exposure_pct: 1.0
  max_portfolio_risk_pct: 3.0

filters:
  enable_spread_filter: true
  max_spread_points: 300
  enable_session_filter: true
  enable_news_filter: true
  sessions:
    - name: "London"
      start_utc: "07:00"
      end_utc:   "16:00"
    - name: "NewYork"
      start_utc: "12:00"
      end_utc:   "21:00"

strategy_params:
  # <param_1>: <default_value>
  # <param_2>: <default_value>

ui:
  show_dashboard: true
  dashboard_font_size: 10
  dashboard_corner: "RIGHT_UPPER"
  auto_setup_chart: true
  auto_load_indicators: true
```

---

## FILE 5: optimization_space.yaml

```yaml
# optimization_space.yaml — <STRATEGY_NAME>

objective: "sharpe_penalized"
# Objective không dùng net_profit đơn thuần
# sharpe_penalized = Sharpe * (1 - DD/max_allowed_dd) * log(trade_count)

reject_if:
  total_trades_lt: 200
  profit_factor_lt: 1.15
  max_dd_gt: 0.15
  sharpe_lt: 0.5

parameters:
  - name: "<param_1>"
    type: "int"       # int / float / bool
    min: 5
    max: 50
    step: 5
  - name: "<param_2>"
    type: "float"
    min: 0.5
    max: 3.0
    step: 0.5

walk_forward:
  train_months: 12
  test_months: 3
  min_folds: 4
  oos_pass_ratio: 0.5   # ít nhất 50% folds phải pass OOS

stability_criteria:
  # Chọn vùng param ổn định, không phải điểm profit cao nhất
  # Dùng cluster analysis hoặc plateau detection
  method: "plateau"
  plateau_tolerance_pct: 10   # param lân cận ±10% vẫn cho kết quả tương đương
```

---

## Checklist trước khi chuyển sang code

```text
hypothesis.md:
  ✔ Có nguồn lý thuyết uy tín
  ✔ Phát biểu hypothesis rõ ràng
  ✔ Không có từ mơ hồ
  ✔ Status = APPROVED

rule_spec.md:
  ✔ Có TF1/TF2/TF3 rule
  ✔ Mọi điều kiện đo được bằng data
  ✔ Có entry/SL/TP/invalidation rõ
  ✔ Có no-trade conditions
  ✔ Status = APPROVED

indicator_spec.md:
  ✔ Liệt kê đủ indicator cần xây
  ✔ Có input/buffer/logic
  ✔ Có non-repaint policy

ea_params.yaml:
  ✔ Đúng symbol/TF
  ✔ Risk params hợp lệ
  ✔ Filters đầy đủ

optimization_space.yaml:
  ✔ Objective function không phải net_profit
  ✔ Có reject thresholds
  ✔ Có walk-forward config
```

Nếu thiếu bất kỳ mục nào → **Coder Agent từ chối code**.
