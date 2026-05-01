# Hypothesis — SMC/ICT Structure

## 1. Nguồn lý thuyết

| Nguồn | Tác giả | Độ uy tín | Concept trích xuất |
|---|---|---|---|
| Inner Circle Trader (ICT) Mentorship 2022 | Michael J. Huddleston | HIGH | Order Blocks, FVG, Liquidity Sweep, Optimal Trade Entry (OTE) |
| "Smart Money Concepts" community adaptation | Adaptation từ ICT | MEDIUM | BOS (Break of Structure), CHoCH (Change of Character), Inducement |
| "The Alchemy of Finance" (Soros) | George Soros | MEDIUM | Market reflexivity — lý do OB vẫn hiệu quả khi đủ market maker |
| Order Flow Institute | Brandon Williams | MEDIUM | Volume footprint xác nhận OB validity |

## 2. Hypothesis chính

**Phát biểu:**
> Trong một up-trend (BOS xác nhận trên H4), sau khi giá thực hiện Liquidity Sweep (sweep High hoặc equal highs), retrace về vùng bullish Order Block gần nhất trên H1 và tạo Bullish Engulfing / FVG fill trên M15 cung cấp edge dương — xác suất tiếp tục theo H4 trend cao hơn xác suất reversal, với R:R >= 2:1 khi SL đặt dưới đáy OB.

**Edge giả định:**
- Market makers tạo ra OB tại các vùng có institutional orders còn tồn đọng — giá sẽ return-to-fill những orders này trước khi tiếp tục
- Liquidity sweep loại bỏ retail stop orders, tạo ra nguồn lực cho move tiếp theo
- FVG (Fair Value Gap) là vùng imbalance — thị trường có xu hướng return-to-fill trước khi continuation

**Edge có thể biến mất nếu:**
- OB bị invalidated bởi structure break trước khi giá reach
- High volatility news event override institutional flow
- Broker spread quá lớn làm mất lợi thế R:R

## 3. Symbol universe

```text
Primary:   EURUSD — liquidity cao, OB pattern rõ, spread thấp
Secondary: GBPUSD — volatile hơn, OB sweep thường dramatic hơn
Timeframe entry (TF3): M15
```

## 4. Điều kiện reject hypothesis (trước khi code)

```text
- Nếu không detect được BOS rõ ràng trên H4 → không đủ điều kiện entry
- Nếu OB không có volume spike xác nhận (tùy broker data) → dùng candle pattern thay thế
- Nếu backtest IS < 200 trades → không đủ sample
- Nếu 80%+ trades đến từ 1 tháng duy nhất → data bias
```

## 5. Trạng thái

```text
Ngày tạo: 2026-05-02
Người tạo: System
Status: RESEARCH — chưa backtest
```
