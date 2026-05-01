# UI/UX SPEC — MT5 EA & Indicator

**Project:** MT5 Quant Portfolio — Forex / XAUUSD / Multi-strategy  
**Mode:** Mỗi symbol chạy trên một chart riêng  
**UI Style:** Tối giản chuyên nghiệp  
**Audience:** Trader / Quant researcher / EA operator  
**Version:** v1.0  

---

## 1. Mục tiêu UI/UX

EA và Indicator phải giúp người dùng hiểu trạng thái hệ thống trong vòng **5 giây** sau khi mở chart.

Người dùng phải thấy ngay:

1. EA đang bật hay tắt.
2. Symbol hiện tại là gì.
3. Strategy nào đang chạy.
4. Có được phép trade hay không.
5. Nếu không trade thì vì sao.
6. Risk hiện tại có an toàn không.
7. Bias của 3 timeframe là gì.
8. Lệnh hiện tại thuộc strategy nào.
9. Có lỗi execution / filter / risk nào không.

Nguyên tắc chính:

```text
Không rối mắt.
Không che chart.
Không vẽ quá nhiều object.
Không để EA im lặng khi không vào lệnh.
Không dùng màu sắc gây nhiễu.
```

---

## 2. Mô hình vận hành chart

### 2.1 Mỗi symbol một chart

Quy định:

```text
1 chart = 1 symbol = 1 EA instance
```

Ví dụ:

```text
Chart 1: XAUUSD + PortfolioEA
Chart 2: EURUSD + PortfolioEA
Chart 3: GBPUSD + PortfolioEA
Chart 4: USDJPY + PortfolioEA
```

Không dùng một chart để trade toàn bộ symbol trong giai đoạn đầu vì:

- Dễ debug hơn.
- Dễ nhìn trạng thái từng symbol hơn.
- Giảm rủi ro nhầm context.
- Dễ kiểm tra indicator tương ứng.
- Dễ kiểm soát UI trên từng chart.

---

## 3. Quy định tự động cấu hình chart khi attach EA

Khi người dùng attach EA vào chart, EA phải tự động thực hiện các bước sau.

### 3.1 Auto chart setup

EA phải tự động:

```text
1. Tắt grid.
2. Bật chart shift.
3. Bật auto scroll nếu cần.
4. Set zoom level phù hợp.
5. Chuyển chart sang candlestick.
6. Set màu chart theo theme tối giản.
7. Set timeframe phù hợp theo strategy (ví dụ: strategy Wyckoff → TF3 = M15).
8. Load indicator tương ứng với strategy.
9. Hiển thị dashboard góc phải trên.
10. Kiểm tra symbol/timeframe hợp lệ.
11. Log trạng thái khởi động.
```

### 3.2 Chart properties cần set

MQL5 gợi ý:

```cpp
ChartSetInteger(0, CHART_SHOW_GRID, false);
ChartSetInteger(0, CHART_SHIFT, true);
ChartSetInteger(0, CHART_AUTOSCROLL, true);
ChartSetInteger(0, CHART_MODE, CHART_CANDLES);
ChartSetInteger(0, CHART_SCALE, 3);
```

### 3.3 Chart shift

Bắt buộc bật chart shift để dashboard và trade labels không đè lên nến cuối.

```text
CHART_SHIFT = true
```

Nếu có cấu hình khoảng shift:

```text
Chart shift size: 20%–30%
```

---

## 4. Quy định load indicator tự động

### 4.1 EA phải tự load indicator theo strategy

Ví dụ:

| Strategy | Indicator cần load |
|---|---|
| Wyckoff | Wyckoff_Phase_Indicator.ex5 |
| SMC | SMC_Structure_Indicator.ex5 |
| ICT | Liquidity_Sweep_Indicator.ex5 |
| Livermore | Breakout_Trend_Indicator.ex5 |
| Mean Reversion | Volatility_Regime_Indicator.ex5 |

### 4.2 Logic load indicator

```text
IF EnableWyckoff = true
THEN load Wyckoff_Phase_Indicator

IF EnableSMC = true
THEN load SMC_Structure_Indicator

IF EnableICT = true
THEN load Liquidity_Sweep_Indicator
```

### 4.3 Quy định nếu indicator không load được

EA phải:

```text
1. Không trade.
2. Hiển thị lỗi trên dashboard.
3. Ghi log lỗi.
4. Không crash.
```

Ví dụ dashboard:

```text
EA: ON
Trading: BLOCKED
Reason: Indicator load failed: Wyckoff_Phase_Indicator
```

---

## 5. UI style: tối giản chuyên nghiệp

### 5.1 Nguyên tắc thiết kế

```text
Ít màu.
Ít chữ.
Trạng thái rõ.
Ưu tiên debug nhanh.
Không biến chart thành màn hình trang trí.
```

### 5.2 Layout chuẩn

```text
Góc phải trên: EA Dashboard
Góc trái trên: Indicator Status
Giữa chart: chỉ cảnh báo nghiêm trọng
Trên chart: entry / SL / TP label tối giản
```

### 5.3 Không được phép

```text
Không dùng quá 5 màu chính.
Không dùng font quá nhỏ.
Không vẽ quá nhiều vùng supply/demand.
Không vẽ arrow dày đặc.
Không che nến hiện tại.
Không repaint mà không cảnh báo.
```

---

## 6. Bảng màu chuẩn

| Trạng thái | Màu | Ý nghĩa |
|---|---|---|
| OK / Allowed | Green | Được phép / hợp lệ |
| Blocked / Error | Red | Bị chặn / lỗi |
| Warning | Orange | Cảnh báo |
| Waiting | Yellow | Chờ điều kiện |
| Neutral | Gray | Trung tính |
| Text | White / Light gray | Nội dung chính |

Quy định:

```text
Không dùng màu neon quá sáng.
Không dùng nền dashboard trong suốt hoàn toàn nếu chữ khó đọc.
Nền dashboard nên là đen/xám đậm, opacity vừa phải.
```

---

## 7. EA Dashboard — nội dung bắt buộc

Dashboard phải ngắn, chia 3 nhóm.

### 7.1 Nhóm 1 — Status

```text
EA: ON/OFF
Trading: ALLOWED/BLOCKED
Reason: [blocked reason]
Symbol: XAUUSD
Strategy: Wyckoff
```

### 7.2 Nhóm 2 — Signal

```text
TF1: H4 UP / DOWN / RANGE
TF2: H1 SETUP / NONE
TF3: M15 READY / WAIT / INVALID
Last Signal: BUY / SELL / NONE
```

### 7.3 Nhóm 3 — Risk

```text
Risk: 0.25%
Today P/L: -0.40%
Daily DD: 0.80% / 3.00%
Open Trades: 1
Spread: OK / HIGH
```

---

## 8. Dashboard mẫu

```text
EA: ON
Trading: BLOCKED
Reason: Spread too high
Symbol: XAUUSD
Strategy: Wyckoff Breakout

TF1 H4: UP
TF2 H1: RANGE
TF3 M15: WAIT
Last Signal: NONE

Risk: 0.25%
Today P/L: -0.35%
Daily DD: 0.80/3.00%
Spread: HIGH
```

---

## 9. Indicator UI — nội dung bắt buộc

Indicator không cần dashboard lớn. Chỉ cần trạng thái ngắn.

```text
Bias: UP / DOWN / RANGE
Structure: BOS / CHOCH / NONE
Liquidity: SWEPT / NONE
Volatility: LOW / NORMAL / HIGH
Session: LONDON / NY / OFF
```

### 9.1 Vẽ trên chart

Indicator chỉ vẽ các object cần thiết:

```text
1. Range high/low.
2. Liquidity level gần nhất.
3. BOS/CHOCH label.
4. Entry zone nếu có.
5. SL/TP level nếu EA đang có lệnh.
```

### 9.2 Giới hạn số object

```text
Max historical zones displayed: 3–5
Max arrows displayed: 20 gần nhất
Max labels displayed: 10 gần nhất
```

Mục tiêu: giữ chart sạch.

---

## 10. Quy định trạng thái Trading Allowed / Blocked

EA phải luôn xác định rõ trạng thái.

### 10.1 Trading Allowed

Chỉ `ALLOWED` khi tất cả đúng:

```text
EA enabled
AutoTrading enabled
Indicator loaded
Spread OK
Session OK
News filter OK
Risk OK
Daily DD OK
TF alignment OK
Signal valid
```

### 10.2 Trading Blocked

Nếu không trade, phải có lý do cụ thể.

Danh sách reason chuẩn:

```text
BLOCKED_SPREAD_HIGH
BLOCKED_NEWS_FILTER
BLOCKED_SESSION_CLOSED
BLOCKED_DAILY_LOSS_LIMIT
BLOCKED_MAX_DD_LIMIT
BLOCKED_NO_SL
BLOCKED_TF_CONFLICT
BLOCKED_NO_SIGNAL
BLOCKED_INDICATOR_LOAD_FAILED
BLOCKED_SYMBOL_NOT_ALLOWED
BLOCKED_INVALID_INPUT
BLOCKED_TRADE_CONTEXT_BUSY
```

Không dùng reason mơ hồ như:

```text
BLOCKED_UNKNOWN
CONDITION_NOT_MET
ERROR
```

Nếu thật sự không biết, dùng:

```text
BLOCKED_UNKNOWN_WITH_ERROR_CODE
```

và ghi `GetLastError()`.

---

## 11. Quy định input EA

Input phải chia nhóm rõ ràng.

### 11.1 General

```cpp
input bool   EnableTrading = true;
input long   MagicNumber = 20260501;
input string CommentPrefix = "QT_PORTFOLIO";
```

### 11.2 Symbol

```cpp
input bool RestrictToCurrentSymbol = true;
input string AllowedSymbols = "XAUUSD,EURUSD,GBPUSD,USDJPY";
```

### 11.3 Timeframes

```cpp
input ENUM_TIMEFRAMES TF1_Bias = PERIOD_H4;
input ENUM_TIMEFRAMES TF2_Setup = PERIOD_H1;
input ENUM_TIMEFRAMES TF3_Entry = PERIOD_M15;
```

### 11.4 Strategy

```cpp
input bool EnableWyckoff = true;
input bool EnableSMC = false;
input bool EnableICT = false;
input bool EnableLivermore = false;
input bool EnableMeanReversion = false;
```

### 11.5 Risk

```cpp
input double RiskPerTradePct = 0.25;
input double MaxDailyLossPct = 3.0;
input double MaxSymbolExposurePct = 1.0;
input double MaxPortfolioRiskPct = 3.0;
```

### 11.6 Filters

```cpp
input bool EnableSpreadFilter = true;
input int MaxSpreadPoints = 300;

input bool EnableSessionFilter = true;
input bool EnableNewsFilter = true;
```

### 11.7 UI / Dashboard

```cpp
input bool ShowDashboard = true;
input int DashboardFontSize = 10;
input ENUM_BASE_CORNER DashboardCorner = CORNER_RIGHT_UPPER;
input bool AutoSetupChart = true;
input bool AutoLoadIndicators = true;
input bool HideGridOnInit = true;
input bool EnableChartShift = true;
```

---

## 12. Quy định validate input

EA phải kiểm tra input khi `OnInit()`.

### 12.1 Reject ngay nếu

```text
RiskPerTradePct <= 0
RiskPerTradePct > 2
MaxDailyLossPct <= 0
MaxDailyLossPct > 10
TF1_Bias <= TF2_Setup
TF2_Setup <= TF3_Entry
AllowedSymbols empty
No strategy enabled
```

### 12.2 Warning nhưng vẫn chạy

```text
MaxSpreadPoints quá cao
DashboardFontSize quá nhỏ
NewsFilter disabled
SessionFilter disabled
```

---

## 13. Quy định trải nghiệm lỗi

Khi có lỗi, EA phải xử lý theo thứ tự:

```text
1. Dừng trade.
2. Hiển thị reason trên dashboard.
3. Ghi log.
4. Không tự xóa chart object quan trọng.
5. Không spam alert liên tục.
```

### 13.1 Alert throttling

Một lỗi giống nhau không được alert liên tục mỗi tick.

Quy định:

```text
Minimum alert interval: 60 giây
```

### 13.2 Alert 3 cấp

| Cấp | Màu | Ý nghĩa | Ví dụ |
|---|---|---|---|
| Warning | Vàng | Cần chú ý, chưa ảnh hưởng trade | Spread tăng nhẹ, session sắp đóng |
| Risk | Cam | Giảm hiệu quả, có thể block trade | Spread cao, DD gần ngưỡng |
| Critical | Đỏ | Dừng trade ngay, cần can thiệp | DD vượt ngưỡng, indicator load fail, kill-switch |

Quy định hiển thị:

```text
Warning  → đổi màu chữ dashboard sang vàng
Risk     → đổi màu chữ dashboard sang cam + ghi log
Critical → đổi màu chữ dashboard sang đỏ + ghi log + block trade
```

---

## 14. Trade label trên chart

Khi có lệnh, EA phải hiển thị tối giản:

```text
BUY #ticket | Wyckoff | Risk 0.25%
SL: 2340.50
TP1: 2352.00
```

Không cần hiển thị quá nhiều thông tin.

### 14.1 SL/TP lines

```text
Entry line: trung tính
SL line: đỏ
TP line: xanh
```

### 14.2 Khi đóng lệnh

Giữ label lịch sử tối đa:

```text
Last closed trades shown: 5
```

---

## 15. Logging chuẩn UI/UX

Mỗi quyết định quan trọng phải ghi log.

### 15.1 File log

```text
logs/decision_log.csv
logs/error_log.csv
logs/trade_log.csv
```

### 15.2 decision_log.csv

Header:

```csv
ts,symbol,timeframe,strategy,signal,decision,reason,risk_pct,spread,session,tf1_state,tf2_state,tf3_state
```

Ví dụ:

```csv
2026-05-01 10:15:00,XAUUSD,M15,Wyckoff,BUY,BLOCKED,BLOCKED_SPREAD_HIGH,0.25,420,LONDON,UP,RANGE,READY
```

---

## 16. Quy định non-repaint

Indicator phải khai báo rõ:

```text
Signal chỉ xác nhận khi candle đóng.
Không dùng candle hiện tại để xác nhận signal nếu chưa đóng.
Nếu dùng realtime preview thì phải label là PREVIEW, không phải SIGNAL.
```

Dashboard phải phân biệt:

```text
PREVIEW_SIGNAL
CONFIRMED_SIGNAL
```

EA chỉ trade theo:

```text
CONFIRMED_SIGNAL
```

---

## 17. Quy định template chart

Nên có template chuẩn:

```text
templates/QT_Minimal_Professional.tpl
```

Template gồm:

```text
Grid off
Candlestick mode
Dark background
Chart shift on
Minimal colors
No default indicators
```

EA có thể dùng template nếu phù hợp, nhưng không phụ thuộc hoàn toàn vào template. Nếu template thiếu, EA vẫn phải tự set chart cơ bản.

---

## 18. Quy định mỗi symbol một chart

### 18.1 Magic number

Mỗi symbol nên có MagicNumber riêng hoặc MagicNumber base + symbol hash.

Ví dụ:

```text
Base magic: 20260501
XAUUSD magic: 2026050101
EURUSD magic: 2026050102
GBPUSD magic: 2026050103
```

### 18.2 Chart title / label

Dashboard phải hiển thị rõ symbol.

```text
Symbol: XAUUSD
Magic: 2026050101
```

---

## 19. Quy định user journey

### 19.1 Khi attach EA lần đầu

Người dùng kỳ vọng:

```text
1. Chart tự sạch hơn.
2. Grid biến mất.
3. Dashboard hiện lên.
4. Indicator được load.
5. EA báo trạng thái ALLOWED hoặc BLOCKED rõ lý do.
```

### 19.2 Khi không vào lệnh

Người dùng phải biết lý do ngay.

Ví dụ:

```text
Trading: BLOCKED
Reason: TF conflict
```

### 19.3 Khi có signal

Dashboard hiển thị:

```text
Last Signal: BUY CONFIRMED
Decision: EXECUTED / BLOCKED
```

### 19.4 Khi có lỗi

Dashboard hiển thị:

```text
Last Error: OrderSend failed 4756
Action: Trading paused
```

---

## 20. Definition of Done — UI/UX

EA/Indicator đạt chuẩn khi:

```text
✔ Attach EA vào chart → tự tắt grid.
✔ Chart shift tự bật.
✔ Dashboard hiện đúng vị trí.
✔ Indicator tương ứng tự load.
✔ Không có indicator → EA không trade và báo lỗi.
✔ Không vào lệnh → luôn có reason.
✔ Risk hiển thị rõ.
✔ TF1/TF2/TF3 hiển thị rõ.
✔ Không che nến.
✔ Không spam object.
✔ Không spam alert.
✔ Có log decision.
✔ Người dùng hiểu trạng thái trong 5 giây.
```

---

## 21. Quy trình test UI/UX

### Test 1 — Attach EA

Kỳ vọng:

```text
Grid off
Chart shift on
Candlestick mode
Dashboard visible
Indicator loaded
```

### Test 2 — Indicator missing

Kỳ vọng:

```text
Trading blocked
Reason: Indicator load failed
No trade opened
Error logged
```

### Test 3 — Spread high

Kỳ vọng:

```text
Trading blocked
Reason: Spread too high
```

### Test 4 — TF conflict

Kỳ vọng:

```text
Trading blocked
Reason: TF conflict
```

### Test 5 — Valid signal

Kỳ vọng:

```text
Signal confirmed
Risk calculated
SL set before entry
Order sent
Trade label shown
```

---

## 22. Kiến trúc module UI đề xuất

```text
include/ui/
├── ChartSetup.mqh
├── Dashboard.mqh
├── ChartObjects.mqh
├── AlertManager.mqh
└── Theme.mqh
```

### 22.1 ChartSetup.mqh

Nhiệm vụ:

```text
Set grid off
Set chart shift
Set candles
Set zoom
Apply minimal theme
```

### 22.2 Dashboard.mqh

Nhiệm vụ:

```text
Render EA status
Render signal state
Render risk state
Render blocked reason
```

### 22.3 ChartObjects.mqh

Nhiệm vụ:

```text
Draw entry line
Draw SL/TP lines
Draw zones
Delete old objects safely
```

### 22.4 AlertManager.mqh

Nhiệm vụ:

```text
Throttle alerts
Avoid repeated messages
Log critical warnings
```

### 22.5 Theme.mqh

Nhiệm vụ:

```text
Define colors
Define font size
Define object spacing
```

---

## 23. MQL5 pseudocode — OnInit flow

```cpp
int OnInit()
{
   ValidateInputs();

   if(AutoSetupChart)
      SetupChartMinimalProfessional();

   if(AutoLoadIndicators)
   {
      bool ok = LoadStrategyIndicators();
      if(!ok)
      {
         SetTradingBlocked("BLOCKED_INDICATOR_LOAD_FAILED");
         RenderDashboard();
         return INIT_SUCCEEDED;
      }
   }

   RenderDashboard();
   LogDecision("INIT", "EA initialized");

   return INIT_SUCCEEDED;
}
```

---

## 24. MQL5 pseudocode — OnTick flow

```cpp
void OnTick()
{
   UpdateMarketState();
   UpdateSignalState();
   UpdateRiskState();

   string blockReason = GetBlockReason();

   if(blockReason != "")
   {
      SetTradingBlocked(blockReason);
      RenderDashboard();
      LogDecision("BLOCKED", blockReason);
      return;
   }

   if(HasConfirmedSignal())
   {
      ExecuteTradeWithPredefinedSL();
      RenderTradeLabels();
      LogDecision("EXECUTED", "Trade opened");
   }

   RenderDashboard();
}
```

---

## 25. Nguyên tắc cuối cùng

```text
UI không phải để làm đẹp.
UI để giảm lỗi vận hành.
Dashboard không phải để khoe thông tin.
Dashboard để trả lời: EA có được trade không, nếu không thì vì sao.
```
