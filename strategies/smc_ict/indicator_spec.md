# Indicator Spec — SMC_Structure_Indicator.mq5

## 1. Mục đích

Phát hiện và publish các cấu trúc SMC/ICT qua indicator buffers để EA đọc:
- **BOS** (Break of Structure) — trend continuation
- **CHoCH** (Change of Character) — trend reversal signal, EA dùng để EXIT
- **Order Blocks** — vùng institutional orders còn tồn đọng
- **FVG** (Fair Value Gap) — vùng imbalance
- **Liquidity Pools** — equal highs/lows, nơi tập trung stop loss

> CHoCH phải là buffer riêng — EA phân biệt BOS (vào lệnh) và CHoCH (thoát lệnh). Không gộp chung.

---

## 2. Non-repaint Policy

**Bắt buộc:** Tất cả giá trị buffer chỉ được ghi tại `shift >= 1` (bar đã đóng hoàn toàn).  
`shift = 0` (bar đang hình thành) bị cấm tuyệt đối cho mọi buffer.  
Vi phạm non-repaint = strategy auto-reject tại QA Gate.

---

## 3. Buffers

| Index | Tên | Giá trị | Mô tả |
|---|---|---|---|
| 0 | Structure_Signal | `2.0`=BOS_UP / `1.0`=CHoCH_UP / `-1.0`=CHoCH_DOWN / `-2.0`=BOS_DOWN / `0`=None | BOS vs CHoCH phân biệt rõ |
| 1 | OB_High | price / `EMPTY_VALUE` | Đỉnh Bullish OB valid gần nhất (forward-filled) |
| 2 | OB_Low | price / `EMPTY_VALUE` | Đáy Bullish OB valid gần nhất |
| 3 | FVG_High | price / `EMPTY_VALUE` | Đỉnh Bullish FVG gần nhất (overlap với OB) |
| 4 | FVG_Low | price / `EMPTY_VALUE` | Đáy Bullish FVG gần nhất |

**Lưu ý đọc buffer từ EA:**
- `Structure_Signal[i] == 2.0` → BOS_UP tại bar i → xác nhận trend UP, tìm OB
- `Structure_Signal[i] == 1.0` → CHoCH_UP (sau downtrend, bắt đầu up) → không dùng trực tiếp để trade
- `Structure_Signal[i] == -1.0` → **CHoCH_DOWN = EXIT SIGNAL** cho lệnh LONG đang mở
- `OB_High[i] != EMPTY_VALUE` → có OB valid tại thời điểm bar i, EA dùng OB_High/OB_Low để xác định entry zone và SL

---

## 4. Input Parameters

| Input | Type | Default | Mô tả |
|---|---|---|---|
| InpSwingLookback | int | 10 | Bars nhìn lại để detect swing H/L |
| InpOB_MinBodyPct | double | 0.6 | Body/range ratio tối thiểu của OB candle |
| InpFVG_MinGapATR | double | 0.3 | FVG size tối thiểu (× ATR14) |
| InpOB_MaxAgeBars | int | 50 | OB expire nếu chưa được test sau N bars |
| InpEqualHL_ATRTol | double | 0.1 | Tolerance để 2 swing được coi là "equal" (× ATR) |
| InpShowZones | bool | true | Vẽ OB/FVG rectangles lên chart |
| InpShowStructure | bool | true | Vẽ BOS/CHoCH labels và lines |
| InpShowLiquidity | bool | true | Đánh dấu equal highs/lows (liquidity pools) |

---

## 5. Phát hiện BOS vs CHoCH

```
Xét tại bar i (shift >= 1), với bias_state là trạng thái tích lũy:

BOS_UP (Structure_Signal = 2.0):
  close[i] > swing_high(high, i+1, SwingLookback)
  VÀ bias_state != BULL  → xác nhận chuyển sang BULL
  → bias_state = BULL
  → Tìm OB ngay trước bar này

CHoCH_DOWN (Structure_Signal = -1.0):
  bias_state = BULL
  VÀ close[i] < swing_low(low, i+1, SwingLookback)
  → bias_state = BEAR (hoặc NEUTRAL)
  → EA đọc đây là EXIT SIGNAL cho lệnh LONG

BOS_DOWN (Structure_Signal = -2.0):
  close[i] < swing_low(low, i+1, SwingLookback)
  VÀ bias_state != BEAR → xác nhận chuyển sang BEAR

CHoCH_UP (Structure_Signal = 1.0):
  bias_state = BEAR
  VÀ close[i] > swing_high(high, i+1, SwingLookback)
  → báo hiệu có thể đảo BEAR→BULL
```

**Tại sao quan trọng:** BOS và CHoCH đều là "close vượt swing" nhưng ngữ nghĩa khác nhau:
- BOS = break cùng chiều trend → continuation
- CHoCH = break ngược chiều trend → reversal warning

---

## 6. Phát hiện Order Block

```
Bullish OB tại bar ob_bar (shift >= 1):
  Điều kiện:
    - close[ob_bar] < open[ob_bar]  (candle đỏ)
    - body/range ≥ InpOB_MinBodyPct
    - Có BOS_UP trong vòng 3 bars SAU ob_bar (ob_bar là "last down candle before up impulse")
    - Impulse sau OB ≥ 2 × ATR14

  OB_High = high[ob_bar]
  OB_Low  = low[ob_bar]
  
  Violated nếu: có close < OB_Low sau khi OB được tạo
  Expired nếu: age > OB_MaxAgeBars bars chưa được test

Forward-fill: OB_High/OB_Low giữ giá trị từ bar OB tạo ra đến bar hiện tại (nếu still valid)
```

---

## 7. Phát hiện FVG

```
Bullish FVG tại bar i (shift >= 1):
  FVG_Low  = high[i+2]
  FVG_High = low[i]
  Valid nếu FVG_High > FVG_Low
  VÀ (FVG_High - FVG_Low) >= InpFVG_MinGapATR × ATR14[i]

Chỉ lưu FVG nếu nó overlap hoặc liền kề OB hiện tại:
  overlap = (FVG_Low < OB_High) AND (FVG_High > OB_Low)

Forward-fill tương tự OB
```

---

## 8. Phát hiện Liquidity Pool (Equal Highs/Lows)

```
Equal Highs tại bar i:
  Tìm swing_high gần nhất tại bar j (j > i)
  Nếu |high[i] - high[j]| <= InpEqualHL_ATRTol × ATR14[i]
  → Đánh dấu là Liquidity Pool (vẽ dashed line)

Indicator vẽ label "EQH" tại equal highs, "EQL" tại equal lows
EA không đọc buffer cho liquidity — EA dùng logic riêng để detect sweep
(Indicator vẽ cho trader quan sát thôi)
```

---

## 9. Drawing Objects

| Đối tượng | Hình dạng | Màu | Điều kiện |
|---|---|---|---|
| OB Zone | Rectangle | Teal (Bullish) / Salmon (Bearish) | InpShowZones=true |
| FVG Zone | Rectangle | Gold, opacity 80% | InpShowZones=true |
| BOS Label | Text "BOS ↑/↓" + hline | LimeGreen / Tomato | InpShowStructure=true |
| CHoCH Label | Text "CHoCH ↓/↑" + hline | Orange (cảnh báo) | InpShowStructure=true |
| EQH/EQL Line | Dashed hline | Silver | InpShowLiquidity=true |

**CHoCH dùng màu khác BOS** — trader phải phân biệt được ngay lập tức.

---

## 10. Performance Notes

- Tối đa 5 OB zones và 5 FVG zones hiển thị đồng thời (gần nhất)
- Xóa objects khi OB violated hoặc expired
- Chỉ tính 200 bars gần nhất trong OnCalculate
- CHoCH labels giữ tối đa 10 cái gần nhất (tránh lag)
