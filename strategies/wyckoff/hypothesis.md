# Hypothesis — Wyckoff Breakout

## 1. Nguồn lý thuyết

| Nguồn | Tác giả | Độ uy tín | Concept trích xuất |
|---|---|---|---|
| "The Wyckoff Method" (original course) | Richard D. Wyckoff (1931) | HIGH | Phase A-E, Accumulation/Distribution, Cause & Effect |
| "Trades About to Happen" | David H. Weis | HIGH | Wyckoff wave, volume analysis, spring/upthrust |
| "The Undeclared Secrets That Drive the Stock Market" | Tom Williams (VSA) | MEDIUM | Volume Spread Analysis — phái sinh từ Wyckoff |
| CMT Curriculum Level 2 | CMT Association | HIGH | Wyckoff schematics chuẩn hóa |

## 2. Hypothesis chính

**Phát biểu:**
> Sau khi thị trường hoàn thành giai đoạn Accumulation (cấu trúc range rõ ràng: SC, AR, ST, Spring hoặc LPS), một lần breakout khỏi Trading Range trên H4 với volume xác nhận trên H1 và M15 cung cấp edge dương — xác suất tiếp tục lên cao hơn xác suất thất bại, với R:R >= 2:1 khi SL đặt dưới Spring/LPS.

**Edge giả định:**
- Institutional accumulation tạo ra supply/demand imbalance, làm cơ sở cho giá tiếp tục sau breakout
- Retail traders thường bị shakeout tại Spring — EA vào sau khi retail đã bị loại
- Lý do edge có thể biến mất: thị trường thay đổi cấu trúc (chuyển sang distribution), news override, spread quá cao

## 3. Symbol universe

```text
Primary:   XAUUSD (Gold) — range rõ, volume data phong phú, H4 structure rõ
Secondary: EURUSD, GBPUSD
Timeframe entry (TF3): M15
```

## 4. Điều kiện reject hypothesis (trước khi code)

```text
- Nếu range duration < 20 bars H4 → quá ngắn, không đủ accumulation
- Nếu Spring không thể detect bằng swing low + volume — reject
- Nếu backtest IS < 200 trades → không đủ sample
```

## 5. Trạng thái

```text
Ngày tạo: 2026-05-01
Người tạo: System
Status: APPROVED
```
