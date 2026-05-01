# Rule Spec — Wyckoff Breakout

> Mọi điều kiện đo được bằng OHLC, ATR, swing high/low, volume, spread, session.

## 1. Multi-Timeframe Assignment

| TF | Timeframe | Nhiệm vụ |
|---|---|---|
| TF1 | H4 | Xác định Wyckoff phase + trading range |
| TF2 | H1 | Xác định setup (LPS hoặc BOS confirmation) |
| TF3 | M15 | Xác định entry (breakout candle) |

---

## 2. TF1 — Bias Rule (H4)

```text
BULL bias (Accumulation detected) khi:
  A. Range established:
     - Swing Low (SC) = lowest low trong 20 bars trước
     - Swing High (AR) = highest high trong 20 bars sau SC
     - Range height = AR - SC >= 1.0 * ATR(14) trên H4
     - Range duration >= 20 bars H4

  B. Spring / Last Point of Support:
     - Có candle Close < SC level nhưng Close lại trên SC trước khi bar đóng
       (tức là: Low[i] < SC AND Close[i] > SC — wick xuống dưới SC)
     - Spring phải nằm trong range duration

  C. Không có lần nào Close vượt AR level (chưa breakout thực sự)

BEAR bias (Distribution detected):
  - Mirror của BULL (đổi SC → AR, Spring → Upthrust)
  - [Không implement giai đoạn đầu — chỉ LONG]

RANGE khi:
  - Không thỏa BULL hoặc BEAR
  - Range height < 1.0 * ATR(14) → range quá hẹp, không đủ
```

---

## 3. TF2 — Setup Rule (H1)

```text
SETUP LONG khi:
  - TF1 bias = BULL
  - Có BOS (Break of Structure) trên H1:
      Close[0] > Swing High của 10 bars gần nhất trên H1
  - Volume của BOS candle > 1.2 * Volume MA(20) trên H1
      (nếu volume không available — bỏ volume filter)

SETUP NONE khi:
  - TF1 ≠ BULL
  - BOS chưa xảy ra
  - Volume quá thấp
```

---

## 4. TF3 — Entry Rule (M15)

```text
ENTRY LONG khi:
  - TF2 = SETUP LONG
  - Pullback sau BOS: Close retrace về EMA(21) trên M15
      (±0.3 * ATR(14) từ EMA)
  - Entry candle Close > Open (bullish candle)
  - Entry chỉ valid trong session London hoặc NewYork
  - Spread tại thời điểm entry <= MaxSpreadPoints

Cụ thể:
  IF TF2 = SETUP_LONG
  AND abs(Close[0] - EMA21[0]) <= 0.3 * ATR14[0]  (pullback về EMA)
  AND Close[0] > Open[0]                            (xanh)
  AND spread <= config.max_spread
  AND session IN (London, NewYork)
  THEN ENTRY_LONG
```

---

## 5. Stop Loss

```text
SL LONG:
  SL = Low của Spring candle (TF1) - 0.2 * ATR(14) trên TF3
  Minimum distance: 1.0 * ATR(14) từ entry
  Maximum distance: 3.0 * ATR(14) từ entry

  IF SL_distance > 3 * ATR → BLOCKED (quá xa, không trade)
  IF SL_distance < 1 * ATR → SL = entry - 1 * ATR (enforce minimum)
```

---

## 6. Take Profit

```text
TP1 (mặc định phase đầu):
  TP = entry + 2 * SL_distance   (R:R = 2:1)

Không partial close giai đoạn đầu.
Không trailing stop giai đoạn đầu.
Exit rule khác: đóng lệnh nếu H4 bias flip sang RANGE hoặc BEAR.
```

---

## 7. Invalidation

```text
Signal bị invalidate sau khi hình thành (nhưng trước khi entry):
  - Giá break xuống dưới Spring low thêm > 1 * ATR → range broken, không còn valid
  - H4 bias thay đổi trước khi M15 entry trigger

Signal hết hạn sau:
  - 8 bars M15 (2 giờ) mà không có entry → signal expired
```

---

## 8. No-trade conditions

```text
Không trade khi:
  - TF1 ≠ BULL (RANGE hoặc không xác định)
  - Spread > MaxSpreadPoints (300 points cho XAUUSD)
  - Session = OFF (không phải London/NY)
  - High-impact news trong vòng 30 phút
  - Daily DD đã chạm giới hạn (từ Risk Manager)
  - Candle size M15 > 3 * ATR(14) (volatility spike — reject entry)
  - Account không đủ margin
  - SL distance > 3 * ATR(14)
```

---

## 9. Parameters cần optimize

| Parameter | Default | Range | Ý nghĩa |
|---|---|---|---|
| RangeLookback | 20 | 10–40 (step 5) | Số bars H4 tìm range |
| RangeMinATR | 1.0 | 0.5–2.0 (step 0.5) | Range height tối thiểu × ATR |
| SpringATRBuffer | 0.2 | 0.1–0.5 (step 0.1) | SL dưới spring thêm × ATR |
| EMA_Period | 21 | 13–34 (step 4) | EMA pullback reference |
| PullbackATRTol | 0.3 | 0.1–0.5 (step 0.1) | Tolerance pullback về EMA |
| SL_MaxATR | 3.0 | 2.0–4.0 (step 0.5) | Max SL distance × ATR |
| TP_RR | 2.0 | 1.5–3.0 (step 0.5) | R:R ratio |
| SignalExpiryBars | 8 | 4–16 (step 4) | Bars M15 trước khi signal expire |

---

## 10. Data required

```text
OHLCV: H4, H1, M15
ATR(14): H4, M15
EMA(21): M15
Swing High/Low: H4, H1
Volume: H1 (optional — fallback nếu không có)
Spread: real-time M15
Session time: UTC
News: high-impact calendar
```

---

## 11. Trạng thái

```text
Ngày tạo: 2026-05-01
Status: APPROVED
```
