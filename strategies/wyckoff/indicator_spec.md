# Indicator Spec — Wyckoff Breakout

## 1. Danh sách indicator cần xây

| Indicator | Nhiệm vụ | Non-repaint |
|---|---|---|
| Wyckoff_Phase_Indicator.mq5 | Detect range, Spring, phase trên H4 + BOS trên H1 | YES |

## 2. Wyckoff_Phase_Indicator

### Inputs

```cpp
input int    RangeLookback    = 20;     // Bars H4 tìm range
input double RangeMinATR      = 1.0;    // Range height min × ATR(14)
input double SpringATRBuffer  = 0.2;    // ATR buffer dưới spring
input int    BOS_SwingBars    = 10;     // Bars H1 tìm swing high cho BOS
input double VolumeRatio      = 1.2;    // Volume xác nhận BOS vs MA(20)
input bool   UseVolumeFilter  = true;   // false = bỏ volume filter
```

### Buffers

```cpp
// Buffer 0: TF1 Phase  (1=BULL, -1=BEAR, 0=RANGE)
// Buffer 1: Spring level price
// Buffer 2: AR (Trading Range High) price
// Buffer 3: SC (Trading Range Low) price
// Buffer 4: TF2 BOS signal (1=BOS_LONG, 0=none)
```

### Detection logic (pseudocode)

```text
// ---- TF1: H4 Range Detection ----
FOR each H4 bar (shift >= 1, đã đóng):
  sc = lowest Low trong [i, i+RangeLookback]
  ar = highest High trong [sc_bar, sc_bar+RangeLookback]
  range_height = ar - sc

  IF range_height >= RangeMinATR * ATR14_H4[i]:
    // Tìm Spring: candle có Low < sc nhưng Close > sc
    spring_found = FALSE
    FOR each bar từ sc_bar đến ar_bar:
      IF Low[j] < sc AND Close[j] > sc:
        spring_found = TRUE
        spring_level = Low[j]
        BREAK

    IF spring_found:
      Buffer0[i] = BULL  // 1
      Buffer1[i] = spring_level
      Buffer2[i] = ar
      Buffer3[i] = sc
    ELSE:
      Buffer0[i] = RANGE  // 0
  ELSE:
    Buffer0[i] = RANGE  // 0

// ---- TF2: H1 BOS Detection ----
FOR each H1 bar (shift >= 1):
  IF Buffer0 mapped to this H1 bar == BULL:
    swing_high_H1 = Max(High[i+1..i+BOS_SwingBars])
    IF Close[i] > swing_high_H1:
      IF UseVolumeFilter:
        vol_ok = Volume[i] > VolumeRatio * MA(Volume, 20)[i]
      ELSE:
        vol_ok = TRUE
      IF vol_ok:
        Buffer4[i] = 1   // BOS_LONG confirmed
```

### Non-repaint policy

```text
Chỉ set buffer khi candle shift >= 1 (đã đóng hoàn toàn).
Không set buffer cho shift = 0 (candle hiện tại chưa đóng).
Spring detection chỉ xác nhận khi candle spring đã đóng.
BOS chỉ xác nhận khi candle BOS đã đóng.

Dashboard phân biệt rõ:
  PREVIEW_SIGNAL  → chỉ cảnh báo, EA không trade
  CONFIRMED_SIGNAL → EA được phép trade
```

### Drawing objects

```text
Vẽ trên H4 chart:
  - Rectangle: Trading Range (SC → AR, màu xanh nhạt, opacity thấp)
  - Arrow down (màu đỏ): Spring location
  - Label "BOS" (màu xanh): vị trí BOS trên H1
  - Horizontal line: AR level (đứt, màu xanh)
  - Horizontal line: SC level (đứt, màu đỏ)

Giới hạn:
  Max zones hiển thị: 3 gần nhất
  Max labels: 10 gần nhất
  Không vẽ object lên candle hiện tại
```

### Dashboard (indicator, góc trái trên)

```text
[Wyckoff]
Phase:    BULL / RANGE / BEAR
Spring:   DETECTED / NONE
BOS H1:   CONFIRMED / PENDING / NONE
Range:    2340.00 – 2365.00
ATR H4:   12.50
Session:  LONDON
```

### UI spec

```text
Font size: 9
Color text: White trên nền xám đậm (rgba 30,30,30,200)
Không dùng quá 3 màu drawing object
Không che candle hiện tại
```
