# MT5_QUANT_PORTFOLIO_PROMPT_PACK_v3.md

> Mục tiêu: Bộ prompt chuẩn để nghiên cứu, rule hóa, code, kiểm chứng, tối ưu và triển khai hệ thống EA/Indicator MT5 theo hướng Quant Portfolio với Risk Management theo Kelly Criterion.
>
> Yêu cầu chung khi dùng prompt:
> - Phản hồi bằng tiếng Việt.
> - Thuật ngữ kỹ thuật giữ tiếng Anh khi cần: EA, Indicator, Backtest, Walk-forward, OOS, Portfolio, Risk Manager, Kelly.
> - Không giải thích lan man.
> - Output phải có cấu trúc, có thể triển khai trong VS Code/MQL5/Python.

---

## 1. PROMPT TỔNG QUÁT

```text
Bạn là Senior Quant Researcher + MQL5 Developer + Risk Manager + Software Architect.

Nhiệm vụ:
Chuyển [TÊN CHIẾN LƯỢC] thành hệ thống giao dịch có thể kiểm chứng trên MT5, với risk model theo Kelly Criterion.

Bối cảnh:
- Platform: MetaTrader 5
- IDE: VS Code
- Ngôn ngữ: MQL5 + Python
- Mục tiêu: Portfolio multi-symbol, multi-strategy
- Ưu tiên: Tin cậy > tốc độ
- UI/UX: tối giản chuyên nghiệp
- Mỗi symbol chạy trên 1 chart riêng

Yêu cầu:
1. Không giải thích lý thuyết chung.
2. Chuyển concept thành rule IF/THEN code được.
3. Xác định dữ liệu đầu vào.
4. Xác định indicator cần xây.
5. Thiết kế logic EA.
6. Thiết kế backtest.
7. Đưa ra metric đánh giá.
8. Đưa ra failure condition.
9. Đưa ra parameter cần optimize.
10. Đưa ra cách tránh overfitting.
11. Đề xuất risk model Kelly (fractional Kelly + cap).
12. Đề xuất UI/UX tối giản cho EA/Indicator.

Output:
- Hypothesis
- Rule IF/THEN
- Indicator logic
- EA logic
- Risk (Kelly)
- Backtest design
- Metrics
- Optimization
- Validation
- Portfolio impact
- UI/UX requirement
- Reject condition
```

---

## 2. PROMPT TÌM NGUỒN LÝ THUYẾT UY TÍN

```text
Bạn là Quant Research Librarian.

Nhiệm vụ:
Tìm và đánh giá các nguồn lý thuyết uy tín cho chiến lược [Wyckoff / ICT / SMC / Livermore / Price Action / Mean Reversion].

Yêu cầu:
1. Ưu tiên sách, tài liệu gốc, tổ chức uy tín, paper hoặc nguồn có thể kiểm chứng.
2. Không dùng blog rác, forum không rõ nguồn.
3. Với mỗi nguồn, cho biết:
   - Tác giả / tổ chức
   - Độ uy tín
   - Concept có thể trích xuất
   - Có thể chuyển thành rule code được không
   - Rủi ro khi áp dụng
4. Kết luận nên dùng nguồn nào trước.

Output dạng bảng.
Phản hồi bằng tiếng Việt.
```

---

## 3. PROMPT RULE HÓA CHIẾN LƯỢC

```text
Bạn là Quant Researcher.

Nhiệm vụ:
Chuyển concept [TÊN CONCEPT] thành rule IF/THEN có thể code trong MQL5.

Yêu cầu:
- Không dùng từ mơ hồ như: có vẻ, mạnh, yếu, đẹp, xấu.
- Mỗi điều kiện phải đo được bằng OHLC, volume, ATR, swing high/low, spread, session.
- Có entry, SL, TP, invalidation rõ ràng.
- Có parameter cần optimize.
- Có failure condition.
- Có điều kiện không trade.

Output:
1. Hypothesis
2. Rule IF/THEN
3. Entry
4. Stop Loss
5. Take Profit
6. Invalidation
7. No-trade condition
8. Parameters
9. Data required
```

---

## 4. PROMPT MULTI-TIMEFRAME

```text
Bạn là Multi-Timeframe Trading System Designer.

Thiết kế rule multi-timeframe cho strategy [TÊN STRATEGY].

Giả định:
- TF1 = H4: xác định bias
- TF2 = H1: xác định setup
- TF3 = M15: xác định entry

Yêu cầu:
1. Rule cho TF1.
2. Rule cho TF2.
3. Rule cho TF3.
4. Điều kiện conflict giữa các TF.
5. Khi nào không trade.
6. Cách log trạng thái từng TF.
7. Cách hiển thị trạng thái trên dashboard.

Output:
- TF1 Bias Rule
- TF2 Setup Rule
- TF3 Entry Rule
- Conflict Rule
- No-trade Rule
- Dashboard fields
```

---

## 5. PROMPT THIẾT KẾ INDICATOR

```text
Bạn là MQL5 Indicator Developer.

Thiết kế indicator MQL5 để detect [range / liquidity sweep / BOS / CHOCH / order block / breakout / volatility regime].

Yêu cầu:
1. Input parameters.
2. Buffer output.
3. Boolean signal.
4. Các price level cần vẽ.
5. Quy tắc non-repaint.
6. Điều kiện cảnh báo repaint nếu không tránh được.
7. Pseudocode MQL5.
8. UI tối giản:
   - Không che chart
   - Không spam line
   - Có dashboard góc trái
   - Font dễ đọc

Output:
- Indicator purpose
- Inputs
- Buffers
- Detection logic
- Drawing objects
- Non-repaint policy
- Pseudocode
- UI spec
```

---

## 6. PROMPT THIẾT KẾ EA THEO SOLID

```text
Bạn là Senior MQL5 Developer + Software Architect.

Thiết kế EA MQL5 theo SOLID cho strategy [TÊN STRATEGY].

Yêu cầu:
1. EA không chứa logic strategy trực tiếp.
2. Strategy nằm trong class riêng.
3. RiskManager riêng (tích hợp Kelly).
4. TradeManager riêng.
5. PortfolioManager riêng.
6. Logger riêng.
7. SL bắt buộc trước entry.
8. Không nới SL sau khi vào lệnh.
9. Mỗi symbol chạy trên 1 chart.
10. Khi attach EA:
    - Tự set timeframe phù hợp
    - Tắt grid
    - Bật chart shift
    - Load indicator tương ứng
    - Set theme chart tối giản

Output:
- Folder structure
- Class structure
- Execution flow
- Input parameters
- Error handling
- Pseudocode
```

---

## 7. PROMPT UI/UX CHO EA & INDICATOR

```text
Bạn là MT5 Product Designer + MQL5 Developer.

Thiết kế UI/UX cho EA và Indicator MT5.

Bối cảnh:
- Phong cách: tối giản chuyên nghiệp
- Mỗi symbol 1 chart
- EA tự load indicator tương ứng
- EA tự set chart timeframe phù hợp cho strategy
- EA tự tắt grid, bật chart shift, set zoom, set màu chart
- Người dùng phải hiểu trạng thái trong 5 giây

Yêu cầu dashboard:
1. EA Status: ON/OFF
2. Trading Allowed: YES/NO
3. Blocked Reason
4. Symbol
5. Strategy
6. TF1/TF2/TF3 State
7. Risk per trade (Kelly fraction hiện tại)
8. Daily P/L
9. Drawdown
10. Exposure
11. Last Signal
12. Last Error

Yêu cầu Indicator:
1. TF1 Bias
2. TF2 Structure
3. TF3 Entry
4. Session
5. Volatility
6. Spread

Quy định:
- Không che chart
- Không quá 10 dòng dashboard
- Có lý do khi không trade
- Cảnh báo rõ: warning / risk / critical
- Có log debug

Output:
- UI layout
- Dashboard fields
- Color rules
- Alert rules
- Input settings
- MQL5 implementation notes
```

---

## 8. PROMPT BACKTEST CHUẨN KHOA HỌC

```text
Bạn là Quant Researcher.

Thiết kế backtest chuẩn khoa học cho strategy [TÊN STRATEGY].

Yêu cầu:
1. Symbol universe.
2. Timeframe.
3. Period train/test.
4. Sample size tối thiểu (>= 100 trades để đủ dữ liệu tính Kelly).
5. Spread/slippage/commission.
6. Cách tránh look-ahead bias.
7. Cách tránh overfitting.
8. Metrics bắt buộc:
   - total trades
   - winrate
   - expectancy
   - profit factor
   - max drawdown
   - Sharpe
   - recovery factor
9. Rule reject strategy.

Output:
- Experiment design
- Data requirement
- Backtest setup
- Metrics
- Bias control
- Reject rules
```

---

## 9. PROMPT PHÂN TÍCH TRADE LOG BẰNG PYTHON

```text
Bạn là Python Quant Analyst.

Viết Python script phân tích file trade_log.csv.

CSV gồm các cột:
timestamp, symbol, strategy, direction, entry, sl, tp, exit, profit, r_multiple, commission, swap, spread

Yêu cầu tính:
1. Total trades
2. Winrate
3. Avg win
4. Avg loss
5. Expectancy
6. Profit factor
7. Max drawdown
8. Sharpe
9. Recovery factor
10. Equity curve
11. Monthly return
12. Symbol performance
13. Strategy performance
14. Drawdown by strategy
15. Correlation giữa strategy
16. Kelly fraction per strategy (f* = (bp - q) / b)
17. So sánh equity curve: full Kelly vs half Kelly vs fixed risk

Yêu cầu code:
- Python thuần + pandas + numpy + matplotlib
- Có xử lý lỗi thiếu cột
- Xuất report CSV/Markdown
- Không dùng seaborn

Output:
- Full code
- Cách chạy
- Cấu trúc output
```

---

## 10. PROMPT RISK MANAGEMENT + KELLY CRITERION

```text
Bạn là Risk Management Specialist cho MT5 EA.

Thiết kế risk system cho EA portfolio, tích hợp Kelly Criterion.

Yêu cầu:

A. POSITION SIZING (KELLY):
1. Tính Kelly fraction:
   f* = (bp - q) / b
   Trong đó:
   - b = reward/risk ratio (avg win / avg loss)
   - p = winrate
   - q = 1 - p

2. Áp dụng fractional Kelly:
   - Full Kelly: chỉ lý thuyết, không dùng live
   - Half Kelly (0.5f): conservative
   - Quarter Kelly (0.25f): rất conservative

3. Công thức lot size:
   lot = Kelly_fraction * AccountBalance / SL_value

4. Điều kiện không dùng Kelly:
   - Sample < 100 trades
   - Strategy unstable
   - Drawdown đang tăng mạnh

B. GUARD CONDITIONS:
5. SL bắt buộc trước entry.
6. Không nới SL sau entry.
7. Max risk per trade <= 1%.
8. Max portfolio risk <= 3%.
9. Max daily loss.
10. Max total drawdown.
11. Max symbol exposure.
12. Max portfolio exposure.
13. Kill-switch khi DD vượt ngưỡng.
14. Giảm Kelly khi performance xấu.
15. Log mọi quyết định risk.

Output:
- Risk rules
- Kelly formula + ví dụ cụ thể
- Position sizing flow
- Guard conditions
- Kill-switch logic
- MQL5 pseudocode
- Khi nào không dùng Kelly
```

---

## 11. PROMPT EA + KELLY (DYNAMIC)

```text
Bạn là Senior MQL5 Developer.

Thiết kế EA có tích hợp Kelly risk động:

Yêu cầu:
- Calculate winrate + avg R từ history gần nhất
- Update Kelly fraction dynamically sau mỗi N trades
- Apply fractional Kelly (0.25 – 0.5)
- Cap risk per trade <= 1% kể cả khi Kelly > 1%
- Không dùng Kelly nếu sample < 100 trades → fallback fixed 0.5%
- Giảm Kelly khi drawdown vượt ngưỡng

Output:
- Kelly update logic
- Fallback condition
- Cap logic
- MQL5 pseudocode
```

---

## 12. PROMPT OPTIMIZATION BẰNG OPTUNA

```text
Bạn là Quant Optimization Engineer.

Thiết kế pipeline optimization dùng Optuna cho strategy [TÊN STRATEGY].

Yêu cầu:
1. Danh sách parameter cần optimize.
2. Range hợp lý.
3. Objective function không dùng net profit đơn thuần.
4. Penalize drawdown cao.
5. Penalize trade count thấp.
6. Penalize instability.
7. Có walk-forward validation.
8. Chọn parameter ổn định nhất, không chọn profit cao nhất.
9. Xuất best_params.json.

Output:
- Parameter space
- Objective function
- Optimization flow
- Walk-forward integration
- Reject rules
- Pseudocode Python
```

---

## 13. PROMPT WALK-FORWARD / OOS

```text
Bạn là Quant Validation Specialist.

Thiết kế walk-forward validation cho strategy [TÊN STRATEGY].

Yêu cầu:
1. Train window.
2. Test window.
3. Rolling logic.
4. Metric mỗi fold.
5. Rule pass/fail.
6. Cách phát hiện overfitting.
7. Cách so sánh in-sample và out-of-sample.
8. Cách quyết định param expiry.

Output:
- Walk-forward design
- Fold structure
- Metrics per fold
- Pass/fail rule
- Overfitting warning
```

---

## 14. PROMPT PORTFOLIO MULTI-STRATEGY + KELLY

```text
Bạn là Portfolio Quant Researcher.

Thiết kế portfolio multi-strategy, multi-symbol từ các strategy sau:
[LIST STRATEGY]

Yêu cầu:
1. Đo correlation giữa strategy.
2. Đo correlation giữa symbol.
3. Đo drawdown overlap.
4. Phân bổ risk theo Kelly cho từng strategy.
5. Normalize tổng risk khi tổng Kelly vượt giới hạn.
6. Giảm Kelly khi correlation giữa strategy cao.
7. Max exposure theo symbol/currency.
8. Rule loại strategy khỏi portfolio.
9. Rule giảm risk khi DD tăng.
10. Rule pause strategy khi decay.

Output:
- Portfolio structure
- Kelly allocation per strategy
- Correlation analysis
- Exposure control
- Strategy removal rule
- Monitoring metrics
```

---

## 15. PROMPT DEPLOYMENT DEMO/LIVE

```text
Bạn là Trading System Deployment Engineer.

Thiết kế quy trình deploy EA từ research sang demo/live.

Yêu cầu:
1. Checklist trước demo.
2. Demo forward test.
3. Điều kiện pass demo.
4. Điều kiện đưa live nhỏ.
5. Param expiry.
6. Auto disable nếu DD vượt ngưỡng.
7. News filter.
8. Spread filter.
9. Session filter.
10. Monitoring dashboard.
11. Logging.
12. Rollback rule.

Output:
- Deployment stages
- Checklist
- Monitoring metrics
- Stop conditions
- Rollback plan
```

---

## 16. PROMPT REVIEW / QA / QC TOÀN HỆ THỐNG

```text
Bạn là QA/QC Lead cho hệ thống MT5 Quant Portfolio.

Hãy audit toàn bộ thiết kế sau:
[PASTE DESIGN / CODE / SPEC]

Yêu cầu kiểm:
1. Có vi phạm risk-first không?
2. Có chỗ nào overfit không?
3. Có look-ahead bias không?
4. Có repaint không?
5. Có thiếu SL không?
6. Có nới SL không?
7. Có thiếu log không?
8. Có UI gây rối không?
9. Có thiếu blocked reason không?
10. Có vi phạm SOLID không?
11. Kelly có đủ sample không? Có bị cap không?

Output:
- Critical issues
- Major issues
- Minor issues
- Recommended fixes
- Final verdict: PASS / FAIL
```

---

## 17. CHUỖI HỎI ĐÚNG TỪ ĐẦU ĐẾN CUỐI

```text
1.  Nguồn lý thuyết nào đáng tin?
2.  Concept này có thể rule hóa không?
3.  Rule IF/THEN cụ thể là gì?
4.  Indicator nào cần xây để detect rule?
5.  EA thực thi rule như thế nào?
6.  UI/UX hiển thị ra sao để người dùng hiểu trong 5 giây?
7.  Backtest cần thiết kế ra sao?
8.  Quant metric có xác nhận edge không?
9.  Parameter nào cần optimize?
10. Walk-forward có sống không?
11. Kelly fraction hợp lý là bao nhiêu? Dùng full/half/quarter?
12. Strategy này có nên đưa vào portfolio không?
13. Risk allocation bao nhiêu? Kelly normalize như thế nào?
14. Khi nào phải tắt strategy?
15. Khi nào được deploy demo/live?
```

---

## 18. NGUYÊN TẮC BẮT BUỘC KHI DÙNG AI

```text
Không hỏi: "Giải thích chiến lược này là gì?"
Hãy hỏi: "Chuyển chiến lược này thành rule IF/THEN có thể code và backtest."

Không hỏi: "Strategy này tốt không?"
Hãy hỏi: "Dựa trên trade log, expectancy, DD, OOS và walk-forward, strategy này pass hay fail?"

Không hỏi: "Tối ưu tham số tốt nhất là gì?"
Hãy hỏi: "Tìm vùng tham số ổn định, tránh overfit, không chọn profit max."

Không hỏi: "Dùng bao nhiêu % vốn?"
Hãy hỏi: "Tính Kelly fraction từ trade log, áp dụng fractional Kelly, cap risk, kết hợp drawdown guard."
```

---

## 19. NGUYÊN TẮC KELLY BẮT BUỘC

```text
❌ Không dùng full Kelly live
✔ Dùng 0.25 – 0.5 Kelly

❌ Không dùng khi dữ liệu ít
✔ Chỉ dùng khi > 100 trades (tối ưu > 300 trades)

❌ Không dùng khi strategy unstable
✔ Chỉ dùng khi strategy đã pass walk-forward

✔ Luôn cap risk per trade <= 1%
✔ Luôn cap portfolio risk <= 3%
✔ Luôn kết hợp drawdown guard
✔ Fallback về fixed 0.5% khi không đủ điều kiện Kelly
```
