# Rule Spec — SMC/ICT Structure

## 1. Glossary (các khái niệm riêng của SMC/ICT)

| Khái niệm | Định nghĩa |
|---|---|
| **BOS** (Break of Structure) | Close vượt qua swing high/low — xác nhận trend đang tiếp tục |
| **CHoCH** (Change of Character) | Sau BOS_UP, giá tạo LL (lower low) dưới swing low trước đó — báo hiệu trend đảo chiều. Khác BOS: CHoCH xảy ra ngược chiều bias hiện tại |
| **Order Block (OB)** | Candle cuối cùng ngược chiều ngay trước impulse move mạnh (≥ 2 ATR). Đây là vùng còn tồn đọng lệnh institutional |
| **FVG** (Fair Value Gap) | Gap giữa `high[i+2]` và `low[i]` — vùng imbalance, thị trường có xu hướng return-to-fill |
| **Liquidity Pool** | Chuỗi swing highs/lows ngang nhau (equal highs/lows) — nơi tập trung stop loss của retail. Thị trường sweep trước khi đảo |
| **Liquidity Sweep** | Giá vượt qua liquidity pool một lượng nhỏ rồi đảo chiều ngay — thanh lý stop loss để lấy thanh khoản |
| **Discount Zone** | Vùng giá < 50% của impulse leg gần nhất — entry LONG chỉ trong discount (OTE concept) |
| **OB Violated** | Giá close dưới đáy OB → OB mất hiệu lực, exit ngay |

---

## 2. Parameters

| Parameter | Default | Range | Mô tả |
|---|---|---|---|
| SwingLookback | 10 | 5–20 | Bars nhìn lại để detect swing H/L |
| OB_MinBodyPct | 0.6 | 0.4–0.8 | Body % tối thiểu của OB candle |
| FVG_MinGapATR | 0.3 | 0.1–0.8 | Kích thước FVG tối thiểu theo ATR |
| SweepATRBuffer | 0.1 | 0.05–0.3 | ATR multiple giá vượt liquidity pool để tính là sweep |
| EqualHL_ATRTol | 0.1 | 0.05–0.2 | ATR tolerance để 2 swing được coi là "equal" (liquidity pool) |
| OB_MaxAgeBars | 50 | 20–100 | OB expire sau N bars chưa được test |
| SL_OB_Buffer | 0.1 | 0.05–0.3 | SL = đáy OB − SL_OB_Buffer × ATR |
| TP_RR | 2.5 | 1.5–4.0 | Full TP theo R:R (nếu không có CHoCH sớm hơn) |
| PartialClose_R | 1.0 | 0.8–1.5 | Đóng 50% lệnh tại N × R |
| SignalExpiryBars | 6 | 3–12 | Signal hết hạn sau N bars M15 nếu không filled |

---

## 3. Multi-Timeframe Rules

### TF1 — H4 (Macro Bias)
- **BULL bias**: BOS_UP xác nhận (close H4 > swing high gần nhất trong SwingLookback bars)
- **BEAR bias**: BOS_DOWN xác nhận
- **Bias reset**: CHoCH xảy ra trên H4 → reset bias về NEUTRAL, không trade hướng cũ nữa
- **NEUTRAL/Chop**: Không có BOS rõ ràng → skip hoàn toàn, không tìm entry

### TF2 — H1 (Entry Zone)
- Sau khi H4 bias = BULL:
  - Tìm **Bullish OB** trên H1: candle đỏ cuối cùng trước impulse tăng ≥ 2 ATR, body ≥ OB_MinBodyPct
  - Tìm **Bullish FVG** trong hoặc liền kề OB zone
  - Xác định **Liquidity Pool** (equal highs) phía trên — mục tiêu sweep
  - Xác nhận **Liquidity Sweep** đã xảy ra: giá vượt equal highs > SweepATRBuffer × ATR rồi close ngược lại trong vòng 3 bars
- CHoCH trên H1 (LL dưới swing low gần nhất sau BOS_UP) → exit lệnh đang mở ngay

### TF3 — M15 (Entry Trigger)
- Sau sweep xác nhận trên H1, chờ giá retrace về OB+FVG zone
- Entry conditions:
  1. Bid đang nằm trong OB zone (ob_lo ≤ bid ≤ ob_hi)
  2. Bid < midpoint của impulse leg trên H1 (**Discount Zone**)
  3. Bar đã đóng (shift=1) tạo Bullish Engulfing hoặc Pin Bar (body ≥ 60% range, close ≥ giữa OB)
- Invalidation tức thì: close M15 < ob_lo → cancel entry, OB violated

---

## 4. Entry Logic (IF/THEN)

```
PRE-CONDITION (kiểm tra 1 lần khi H1 bar mới):
  IF  H4 bias = BULL (BOS_UP, chưa có CHoCH)
  AND H1 có Bullish OB valid (chưa violated)
  AND H1 có Bullish FVG trong vùng OB
  AND H1 Liquidity Sweep đã xảy ra (equal highs bị sweep, close ngược lại)
  THEN SET flag: awaiting_entry = TRUE, timeout = now + SignalExpiryBars bars M15

ENTRY (kiểm tra mỗi bar M15 khi awaiting_entry = TRUE):
  IF  awaiting_entry = TRUE
  AND bid ∈ [ob_lo, ob_hi]
  AND bid < impulse_midpoint   ← Discount Zone
  AND M15 bar[1] là Bullish Engulf / Pin Bar
  AND close[1] ≥ (ob_lo + ob_hi) / 2
  AND spread ≤ spread_limit
  THEN:
    entry = close[1]
    sl    = ob_lo − SL_OB_Buffer × ATR14
    tp    = entry + TP_RR × (entry − sl)
    lots  = full_size (sẽ partial close sau)
    awaiting_entry = FALSE
```

---

## 5. SL Policy

- SL bắt buộc đặt trước khi lệnh mở — không mở lệnh nếu thiếu SL
- SL = đáy OB − buffer, không nới rộng sau entry
- **Không trailing SL** — SMC OB là invalidation level, trailing sẽ xung đột với logic đó
- SL → Breakeven (BE) ngay sau khi partial close tại 1R

---

## 6. Position Management (đặc thù SMC — khác Wyckoff)

```
Sau khi lệnh mở:

BƯỚC 1 — Partial Close tại 1R:
  IF profit ≥ PartialClose_R × risk_amount:
    Close 50% lot size
    Move SL → entry price (breakeven)

BƯỚC 2 — Exit triggers (theo dõi mỗi bar H1):
  EXIT nếu bất kỳ điều kiện nào:
  (a) CHoCH trên H1: close H1 < swing_low_since_entry  ← primary exit
  (b) OB violated:  close H1 < ob_lo                   ← invalidation exit
  (c) TP hit: price ≥ tp (phần còn lại sau partial)
  (d) SL hit: price ≤ sl (kể cả BE sau partial)

KHÔNG dùng:
  × TF1 bias flip để exit (quá chậm — CHoCH H1 đã cho tín hiệu sớm hơn)
  × Trailing SL
  × Time-based exit
```

---

## 7. Filters

```text
Spread filter:     reject nếu spread > spread_limit_points (EURUSD=20, GBPUSD=30)
Session filter:    chỉ London (07:00–16:00 UTC) và NewYork (12:00–21:00 UTC)
Discount filter:   bid phải < 50% của impulse leg gần nhất trên H1
Sweep filter:      liquidity sweep phải đã xảy ra trên H1 trước khi tìm entry
OB age filter:     OB già hơn OB_MaxAgeBars bars → bỏ qua
Signal expiry:     awaiting_entry timeout sau SignalExpiryBars M15 bars
```

---

## 8. Invalidation Conditions

```text
Ngay lập tức (cancel entry):
  - Close M15 < ob_lo (OB violated trước khi entry)
  - CHoCH xuất hiện trên H1 trong khi awaiting_entry
  - Timeout (SignalExpiryBars trôi qua)

Trong khi có lệnh:
  - Close H1 < swing_low_since_entry (CHoCH) → exit
  - Close H1 < ob_lo (OB violated) → exit
  - H4 CHoCH (không dùng để exit ngay, dùng để block entry mới)
```
