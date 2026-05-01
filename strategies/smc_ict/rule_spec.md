# Rule Spec — SMC/ICT Structure

## 1. Parameters

| Parameter | Default | Range | Mô tả |
|---|---|---|---|
| SwingLookback | 10 | 5–20 | Số bar nhìn lại để detect swing high/low |
| OB_MinBodyPct | 0.6 | 0.4–0.8 | Tỷ lệ body/candle tối thiểu của OB candle |
| FVG_MinGapATR | 0.3 | 0.1–0.8 | Kích thước FVG tối thiểu theo ATR |
| SweepATRBuffer | 0.1 | 0.05–0.3 | Khoảng vượt qua swing high/low để tính là sweep |
| OB_MaxAgeBars | 50 | 20–100 | OB hết hạn sau N bars nếu chưa được test |
| SL_OB_Buffer | 0.1 | 0.05–0.3 | SL = đáy OB - SL_OB_Buffer * ATR |
| TP_RR | 2.5 | 1.5–4.0 | Take Profit theo R:R ratio |
| SignalExpiryBars | 6 | 3–12 | Entry signal hết hạn sau N bars nếu không filled |

## 2. Multi-Timeframe Rules

### TF1 — H4 (Bias / Trend)
- **BULL bias**: Chuỗi Higher High + Higher Low, BOS (Break of Structure) xác nhận: close > swing high gần nhất
- **BEAR bias**: Chuỗi Lower High + Lower Low, BOS xuống
- **Conflict**: Nếu TF1 không rõ bias (chop) → không trade

### TF2 — H1 (Entry Zone)
- Xác định Bullish Order Block: candle đỏ (Down) ngay trước impulse tăng mạnh nhất (ít nhất 2 ATR)
- OB valid nếu chưa bị "violated" (giá chưa close dưới đáy OB)
- Xác định FVG (Fair Value Gap): gap giữa Low của candle N và High của candle N-2, phải đủ lớn (>= FVG_MinGapATR * ATR)

### TF3 — M15 (Entry Trigger)
- **Entry signal**: Giá retrace vào vùng OB + FVG trên H1, tạo Bullish Engulfing hoặc Pin Bar trên M15, close phải trên giữa OB
- **Invalidation**: Close M15 dưới đáy OB → cancel tất cả pending orders cho đó

## 3. Entry Rules (IF/THEN)

```
IF  TF1 bias = BULL (BOS xác nhận)
AND TF2 có Bullish OB valid chưa bị violated
AND TF2 có FVG trong vùng OB (hoặc OB chứa FVG)
AND TF3 giá retrace vào OB zone
AND TF3 hình thành Bullish Engulfing hoặc Pin Bar (close >= 60% body)
AND spread <= spread_limit (từ ea_params.yaml)
AND session = London hoặc NewYork
THEN entry LONG at close of M15 trigger candle

entry    = close của M15 trigger candle
sl       = low của OB - SL_OB_Buffer * ATR(14)
tp       = entry + TP_RR * (entry - sl)
invalidation = close M15 dưới đáy OB
```

## 4. SL Policy
- SL bắt buộc trước entry, không có SL thì không mở lệnh
- SL = đáy OB - buffer (không nới rộng sau khi đặt)
- Breakeven cho phép khi giá đạt 1R
- Không trailing SL (giữ cố định để không bị prematurely stop out)

## 5. Position Management
- 1 lệnh / symbol cùng lúc (không pyramid)
- Close khi: TP hit, SL hit, hoặc TF1 bias flip (BOS ngược chiều trên H4)
- Close partial tại 1R để lock profit nếu cấu hình cho phép

## 6. Filters

```text
Spread filter:   reject nếu spread > ea_params.spread_limit
Session filter:  chỉ trade London (07:00–16:00 UTC) và NewYork (12:00–21:00 UTC)
News filter:     không trade 30 phút trước/sau high-impact news (manual hoặc API)
OB age filter:   reject OB già hơn OB_MaxAgeBars
```
