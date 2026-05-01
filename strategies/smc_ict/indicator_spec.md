# Indicator Spec — SMC_Structure_Indicator.mq5

## 1. Mục đích

Phát hiện và vẽ các cấu trúc SMC/ICT trên chart:
- BOS (Break of Structure) — xác nhận trend
- Order Blocks (Bullish/Bearish)
- FVG (Fair Value Gap / Imbalance Zone)
- Swing Highs/Lows (liquidity pools)

## 2. Non-repaint Policy

**Bắt buộc:** Tất cả tín hiệu chỉ được tính trên `shift >= 1` (bar đã đóng).
Không được dùng `shift = 0` (bar hiện tại chưa close) cho bất kỳ buffer nào.
Vi phạm non-repaint = strategy reject tự động.

## 3. Buffers

| Buffer | Index | Giá trị | Mô tả |
|---|---|---|---|
| BOS_Direction | 0 | 1.0=Bull / -1.0=Bear / 0=None | BOS direction tại bar đó |
| OB_High | 1 | price hoặc EMPTY_VALUE | Mức trên của Bullish OB gần nhất valid |
| OB_Low | 2 | price hoặc EMPTY_VALUE | Mức dưới của Bullish OB gần nhất valid |
| FVG_High | 3 | price hoặc EMPTY_VALUE | Mức trên FVG gần nhất |
| FVG_Low | 4 | price hoặc EMPTY_VALUE | Mức dưới FVG gần nhất |

## 4. Input Parameters

| Input | Type | Default | Mô tả |
|---|---|---|---|
| InpSwingLookback | int | 10 | Bars nhìn lại để detect swing |
| InpOB_MinBodyPct | double | 0.6 | Body % tối thiểu của OB candle |
| InpFVG_MinGapATR | double | 0.3 | FVG size tối thiểu (multiple of ATR14) |
| InpOB_MaxAgeBars | int | 50 | OB expire sau N bars |
| InpSweepBuffer | double | 0.1 | ATR multiple cho sweep detection |
| InpShowZones | bool | true | Vẽ rectangle OB/FVG zones |
| InpShowBOS | bool | true | Vẽ BOS lines |

## 5. Phát hiện BOS

```
BOS_UP  : close[i] > max(high[i+1..i+SwingLookback]) → buffer[0][i] = 1.0
BOS_DOWN: close[i] < min(low[i+1..i+SwingLookback])  → buffer[0][i] = -1.0
Chỉ tính tại shift >= 1
```

## 6. Phát hiện Order Block

```
Bullish OB: candle đỏ (close < open) ngay trước BOS_UP bar
  OB_High = high của candle đỏ đó
  OB_Low  = low  của candle đỏ đó
  Valid nếu: body >= InpOB_MinBodyPct * (high - low)
  Violated nếu: có close dưới OB_Low sau khi tạo OB
  
Bearish OB: candle xanh trước BOS_DOWN (logic đối xứng)
Buffer ghi giá trị tại bar OB tạo ra, forward-fill đến bar hiện tại nếu còn valid
```

## 7. Phát hiện FVG

```
Bullish FVG tại bar i (shift >= 1):
  FVG_Low  = high[i+2]   (high của candle 2 bars trước)
  FVG_High = low[i]      (low của candle hiện tại)
  Valid nếu: FVG_High - FVG_Low >= InpFVG_MinGapATR * ATR(14)[i]
  
Bearish FVG: đối xứng
```

## 8. Drawing Objects

- **OB Zone**: Rectangle từ OB_Low → OB_High, màu teal (Bullish) / salmon (Bearish), transparency 80%
- **FVG Zone**: Rectangle từ FVG_Low → FVG_High, màu yellow với transparency 85%
- **BOS Line**: Horizontal line tại mức swing bị break, màu green (Bull) / red (Bear)
- **Swing Label**: Text "SH" / "SL" tại swing highs/lows, màu gray

## 9. Performance Notes

- Xóa objects cũ khi OB violated hoặc expired (tránh chart lag)
- Giới hạn số OB hiển thị đồng thời tối đa 5 (gần nhất)
- Không tính toán FVG trên toàn bộ history, chỉ 200 bars gần nhất
