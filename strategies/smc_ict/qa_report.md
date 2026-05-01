# QA Report — smc_ict / EURUSD

Generated: 2026-05-01T18:23:22.931340

## Verdict: ✅ PASS

## Checklist A → Q

| Item | Label | Status | Detail |
|---|---|---|---|
| A | Strategy & Rule | ✅ PASS |  |
| B | Multi-timeframe | ✅ PASS | TF1=H4 TF2=H1 TF3=M15 |
| C | Indicator Spec | ✅ PASS |  |
| D | EA Architecture | ✅ PASS | IStrategy/RiskManager/TradeManager/Logger tồn tại |
| E | Backtest Dataset | ⬜ SKIP | trade_log_path không được cung cấp |
| F | Quant Metrics | ⬜ SKIP | metrics không có (cần trade log) |
| G | Optimization Objective | ✅ PASS | objective='sharpe_penalized' |
| H | Walk-Forward / OOS | ⬜ SKIP | wf_results không được cung cấp |
| I | Risk Management | ✅ PASS | DD limit=6.0% base_risk=0.25% portfolio_cap=3.0% |
| J | Kelly Criterion | ✅ PASS | fraction=0.25, max_risk=1.0%, sample=100 |
| K | Portfolio Risk | ✅ PASS | cap=3.0% corr_cap=2.0% |
| L | UI / Dashboard | ✅ PASS |  |
| M | Auto Chart Setup | ✅ PASS |  |
| N | Logging | ✅ PASS |  |
| O | Deployment / Monitoring | ✅ PASS |  |
| P | Monte Carlo | ⬜ SKIP | trade_log không có — bỏ qua Monte Carlo |
| Q | Regime Test | ⬜ SKIP | Cần --trade-log và --price-csv |

## Required Actions

None — ready for demo.


