# MT5_MASTER.md

> Tài liệu tổng hợp — điểm vào duy nhất để hiểu toàn bộ hệ thống MT5 Quant AI Agent.
> Cập nhật mỗi khi có thay đổi cấu trúc hoặc rule quan trọng.

---

## 1. Mục tiêu hệ thống

```text
Input:  Tên chiến lược trading (Wyckoff, SMC, Mean Reversion,...)
Output: EA MT5 đã được kiểm chứng, chạy demo/live với risk management tự động

Pipeline: Research → Rule hóa → Code → Compile → Backtest → Validate
          → Optimize → Walk-Forward → QA Gate → Deploy Demo
```

**Nguyên tắc bất biến:**
```text
Không SL → không trade
Không OOS → không deploy
Không QA PASS → không demo/live
Agent KHÔNG tự live trade
```

---

## 2. Cấu trúc thư mục

```text
MT5_Verifiable_Strategy_Lab/
│
├── docs/                          ← Tất cả spec và tài liệu
│   ├── MT5_MASTER.md              ← File này (tổng hợp)
│   ├── AGENT_SYSTEM_SPEC.md       ← Thiết kế 11 agents + pipeline
│   ├── RISK_POLICY.md             ← Risk rules (luật, không thay đổi tự động)
│   ├── QA_GATE.md                 ← 17 checklist A→Q, Monte Carlo, Regime
│   ├── UI_UX_SPEC_MT5_EA_INDICATOR.md ← Dashboard, indicator, chart setup
│   ├── MT5_TESTER_AUTOMATION.md   ← Backtest automation (ini + subprocess)
│   ├── MT5_COMPILE_AUTOMATION.md  ← Compile automation (MetaEditor CLI)
│   ├── STRATEGY_SPEC_TEMPLATE.md  ← Template 5 file bắt buộc mỗi strategy
│   ├── MT5_QUANT_PORTFOLIO_PROMPT_PACK_v3.md ← 19 prompt chuẩn
│   └── agents/
│       └── 11_monitoring_agent.md ← Strategy decay detection
│
├── configs/                       ← Config yaml (chỉ Architect được sửa)
│   ├── mt5_paths.yaml             ← Đường dẫn MT5, thư mục output
│   ├── symbols.yaml               ← Universe symbol + spread limit + session
│   ├── risk.yaml                  ← Risk parameters + Kelly + DD limits
│   ├── strategies.yaml            ← Registry strategies + status lifecycle
│   └── optimization.yaml         ← Optuna config + walk-forward + reject rules
│
├── strategies/                    ← Mỗi strategy = 1 folder plugin
│   └── <strategy_name>/
│       ├── hypothesis.md          [BẮT BUỘC]
│       ├── rule_spec.md           [BẮT BUỘC]
│       ├── indicator_spec.md      [BẮT BUỘC]
│       ├── ea_params.yaml         [BẮT BUỘC]
│       ├── optimization_space.yaml [BẮT BUỘC]
│       ├── best_params.json       [TẠO SAU optimize]
│       ├── validation_report.md   [TẠO SAU backtest]
│       └── qa_report.md           [TẠO SAU QA]
│
├── python/
│   ├── orchestrator/
│   │   ├── run_pipeline.py        ← ENTRY POINT chạy pipeline
│   │   └── pipeline_state.py     ← State manager (resume từ step N)
│   ├── mt5_interface/
│   │   └── connector.py          ← Python ↔ MT5 (rates, deals, GV)
│   ├── build/
│   │   └── mql5_compiler.py      ← MetaEditor CLI wrapper
│   ├── backtest/
│   │   ├── tester_runner.py      ← MT5 Strategy Tester automation
│   │   ├── trade_log_parser.py   ← Parse trade_log.csv
│   │   └── walk_forward.py       ← WFO fold generator
│   ├── validator/
│   │   └── monte_carlo.py        ← 1000 sim Monte Carlo
│   └── monitoring/
│       ├── run_monitor.py        ← Daily monitoring agent
│       └── alert.py              ← Alert 3 cấp (WARNING/RISK/CRITICAL)
│
├── mql5/                          ← Source MQL5 (sync với MT5 data folder)
│   ├── Experts/
│   ├── Indicators/
│   └── Include/
│       └── ui/
│           ├── Dashboard.mqh
│           ├── ChartSetup.mqh
│           ├── AlertManager.mqh
│           └── Theme.mqh
│
└── logs/
    ├── trade_log.csv
    ├── decision_log.csv
    ├── error_log.csv
    ├── monitoring_alert.log
    ├── monitoring_report.csv
    └── pipeline_state_<strategy>_<symbol>.json
```

---

## 3. Chạy pipeline

### 3.1 Lần đầu

```bash
# Từ project root
cd python
python orchestrator/run_pipeline.py --strategy wyckoff --symbol XAUUSD
```

### 3.2 Resume sau khi fail

```bash
# Xem pipeline đang ở bước nào
cat logs/pipeline_state_wyckoff_XAUUSD.json

# Resume từ bước 6
python orchestrator/run_pipeline.py --strategy wyckoff --symbol XAUUSD --from-step 6
```

### 3.3 Dry run (chỉ kiểm tra pre-flight)

```bash
python orchestrator/run_pipeline.py --strategy wyckoff --symbol XAUUSD --dry-run
```

### 3.4 Pipeline steps

| Step | Nhiệm vụ | Output |
|---|---|---|
| 1 | Validate strategy spec (5 file) | — |
| 2 | Compile indicators | .ex5 files |
| 3 | Compile EA | .ex5 file |
| 4 | Backtest In-Sample | trade_log.csv |
| 5 | Parse & validate trade log (>= 200 trades) | DataFrame |
| 6 | Quant metrics (PF, DD, Sharpe) | metrics dict |
| 7 | Walk-forward / OOS | wf_results |
| 8 | Monte Carlo 1000 sim | mc metrics |
| 9 | Generate QA report | qa_report.md |

---

## 4. Thêm strategy mới

```text
1. Tạo folder: strategies/<new_strategy>/
2. Tạo 5 file bắt buộc (dùng STRATEGY_SPEC_TEMPLATE.md)
3. Đăng ký trong configs/strategies.yaml (status: research)
4. Viết indicator .mq5 + EA .mq5 (theo rule_spec.md)
5. Chạy pipeline
6. Nếu QA PASS → đổi status sang demo trong strategies.yaml
```

Không cần sửa bất kỳ code core nào.

---

## 5. Strategy lifecycle

```text
research
  → [pipeline pass + human approve]
  → approved
  → [deploy demo]
  → demo
  → [forward test 2–4 tuần, monitoring OK]
  → live (nhỏ)
  → [monitoring ổn định]
  → live (full)

Bất kỳ lúc nào:
  → paused  (monitoring detect decay hoặc human pause)
  → rejected (QA fail, OOS fail, performance xấu)
```

---

## 6. Risk summary

| Rule | Giá trị |
|---|---|
| Base risk/trade | 0.25% |
| Max risk/trade | 1.00% |
| Kelly fraction | 0.25–0.50 |
| Kelly min sample | 100 trades |
| Daily loss limit | 3% |
| Max account DD | 6% |
| Emergency stop | 10% |
| Max portfolio risk | 3% |

Chi tiết: [RISK_POLICY.md](RISK_POLICY.md)

---

## 7. Inter-EA communication

EA instances dùng **MT5 Global Variables** để chia sẻ portfolio state:

```text
QT_20260501_TOTAL_RISK  → tổng open risk %
QT_20260501_DAILY_PL    → daily P/L %
QT_20260501_DD          → current DD %
QT_20260501_OPEN_COUNT  → số lệnh đang mở
QT_20260501_KILL        → 1.0 = kill switch
```

Python Monitoring Agent có thể set KILL = 1.0 để dừng tất cả EA.

---

## 8. QA Gate summary

17 checklist (A → Q). Hard fail nếu thiếu bất kỳ mục nào:

```text
A  Strategy & Rule     G  Optimization    M  Auto Chart Setup
B  Multi-timeframe     H  Walk-forward    N  Logging
C  Indicator           I  Risk            O  Deployment
D  EA Architecture     J  Kelly           P  Monte Carlo (mới)
E  Backtest            K  Portfolio       Q  Regime Test (mới)
F  Quant Metrics       L  UI/UX
```

Minimum thresholds để demo:
```text
Total trades >= 200 | OOS trades >= 50
PF >= 1.15 | Max DD <= 15% | Sharpe > 0.5
Monte Carlo: ruin rate < 1%, p95 DD < 25%
```

Chi tiết: [QA_GATE.md](QA_GATE.md)

---

## 9. Monitoring

Monitoring Agent chạy daily:

```bash
python monitoring/run_monitor.py
```

Phát hiện decay → action tự động:
```text
WARNING  → giảm Kelly 50%
CRITICAL → set KILL via Global Variable + alert
```

Chi tiết: [agents/11_monitoring_agent.md](agents/11_monitoring_agent.md)

---

## 10. Tài liệu tham khảo

| File | Nội dung |
|---|---|
| AGENT_SYSTEM_SPEC.md | 11 agents, pipeline flow, permission model |
| RISK_POLICY.md | Tất cả risk rules, Kelly, SL policy |
| QA_GATE.md | 17 checklist + Monte Carlo + Regime |
| UI_UX_SPEC_MT5_EA_INDICATOR.md | Dashboard, chart setup, indicator UI |
| MT5_TESTER_AUTOMATION.md | Backtest automation kỹ thuật |
| MT5_COMPILE_AUTOMATION.md | Compile automation kỹ thuật |
| STRATEGY_SPEC_TEMPLATE.md | Template 5 file bắt buộc |
| MT5_QUANT_PORTFOLIO_PROMPT_PACK_v3.md | 19 prompt chuẩn cho AI |

---

## 11. Definition of Done — toàn hệ thống

```text
✔ Pipeline Python chạy end-to-end từ config
✔ Ít nhất 1 strategy (Wyckoff) qua full cycle → qa_report.md
✔ EA compile thành công
✔ Backtest có trade_log.csv >= 200 trades
✔ Metrics pass QA thresholds
✔ Walk-forward có kết quả
✔ Monte Carlo ruin rate < 1%
✔ QA report generated
✔ Monitoring Agent chạy được daily
✔ Có thể thêm strategy mới bằng plugin folder, không sửa core
✔ Pipeline resume được từ bước N khi fail
```
