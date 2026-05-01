# AGENT_SYSTEM_SPEC.md

## 1. Mục tiêu

Thiết kế hệ thống AI Agent cho dự án MT5 Quant Forex chạy trên Windows + VS Code + Python.

Mục tiêu:

```text
Research strategy
→ Rule hóa
→ Sinh indicator/EA MQL5
→ Backtest MT5
→ Quant validation
→ Optimization
→ Portfolio selection
→ Risk/Kelly
→ QA gate
→ Demo deployment
```

Nguyên tắc:

```text
Agent được tự động research/code/backtest/validate.
Agent KHÔNG được tự động live trade nếu chưa qua QA_GATE.
```

---

## 2. Tool stack

```text
OS: Windows
IDE: VS Code
Trading platform: MetaTrader 5
Language: MQL5 + Python
AI tools: Claude + ChatGPT/Copilot
Automation: Python script first, n8n optional later
```

---

## 3. Cấu trúc project chuẩn

```text
MT5-Quant-Agent-System/
├── docs/
│   ├── AGENT_SYSTEM_SPEC.md
│   ├── QA_GATE.md
│   ├── RISK_POLICY.md
│   ├── STRATEGY_SPEC.md
│   └── MT5_MASTER.md
│
├── agents/
│   ├── 01_research_agent.md
│   ├── 02_rule_agent.md
│   ├── 03_mql5_coder_agent.md
│   ├── 04_backtest_agent.md
│   ├── 05_quant_validator_agent.md
│   ├── 06_optimizer_agent.md
│   ├── 07_risk_agent.md
│   ├── 08_portfolio_agent.md
│   ├── 09_qa_qc_agent.md
│   └── 10_deployment_agent.md
│
├── mql5/
│   ├── Experts/
│   ├── Indicators/
│   └── Include/
│
├── python/
│   ├── orchestrator/
│   ├── research/
│   ├── backtest/
│   ├── optimizer/
│   ├── validator/
│   ├── portfolio/
│   └── reports/
│
├── strategies/
│   ├── wyckoff/
│   ├── smc_ict/
│   ├── livermore/
│   ├── mean_reversion/
│   └── breakout/
│
├── configs/
│   ├── symbols.yaml
│   ├── strategies.yaml
│   ├── risk.yaml
│   ├── optimization.yaml
│   └── mt5_paths.yaml
│
└── logs/
```

---

## 4. Danh sách agent

### 4.1 Research Agent

Nhiệm vụ:

```text
Tìm nguồn uy tín
Trích xuất hypothesis
Chấm điểm hypothesis
Không bịa strategy
```

Input:

```text
strategy_family
symbol_group
timeframe_group
source_constraints
```

Output:

```text
hypothesis_list.md
source_map.md
research_score.csv
```

Không được làm:

```text
Không viết code MQL5
Không kết luận có edge nếu chưa backtest
```

---

### 4.2 Rule Agent

Nhiệm vụ:

```text
Chuyển hypothesis thành IF/THEN
Biến mọi điều kiện thành dữ liệu đo được
Tạo entry/SL/TP/invalidation/no-trade
```

Output:

```text
strategies/<strategy>/rule_spec.md
```

PASS nếu:

```text
Có IF/THEN rõ
Có biến OHLC/ATR/volume/spread/session
Không dùng từ mơ hồ
```

---

### 4.3 MQL5 Coder Agent

Nhiệm vụ:

```text
Viết indicator
Viết EA
Viết module Include
Tuân thủ SOLID
```

Input:

```text
rule_spec.md
indicator_spec.md
ui_spec.md
risk_policy.md
```

Output:

```text
.mq5
.mqh
compile_log.txt
```

Không được làm:

```text
Không tự đổi rule
Không tự bỏ SL
Không tự sửa risk policy
```

---

### 4.4 Backtest Agent

Nhiệm vụ:

```text
Chạy MT5 Strategy Tester
Export trade log/report
```

Input:

```text
EA compiled
symbol
timeframe
date_range
params
```

Output:

```text
backtest_report.html
trade_log.csv
signal_log.csv
```

---

### 4.5 Quant Validator Agent

Nhiệm vụ:

```text
Phân tích trade_log.csv
Tính expectancy, winrate, PF, DD, Sharpe
Đánh giá edge
```

Output:

```text
validation_report.md
metrics.csv
equity_curve.png
```

---

### 4.6 Optimizer Agent

Nhiệm vụ:

```text
Tối ưu parameter bằng Optuna/MT5
Không chọn net profit đơn thuần
Chọn vùng parameter ổn định
```

Output:

```text
best_params.json
optimization_report.md
```

---

### 4.7 Risk Agent

Nhiệm vụ:

```text
Tính position size
Tính Fractional Kelly
Áp dụng max DD, daily loss, exposure cap
```

Output:

```text
risk_decision.json
risk_report.md
```

---

### 4.8 Portfolio Agent

Nhiệm vụ:

```text
Đo correlation giữa strategy/symbol
Chọn strategy đưa vào portfolio
Phân bổ risk
```

Output:

```text
portfolio_allocation.json
portfolio_report.md
```

---

### 4.9 QA/QC Agent

Nhiệm vụ:

```text
Audit logic, code, risk, UI, backtest
Chấm PASS/FAIL
```

Output:

```text
qa_report.md
```

Không qua QA thì không deploy.

---

### 4.10 Deployment Agent

Nhiệm vụ:

```text
Chuẩn bị demo deployment
Không tự live
Kiểm checklist trước khi bật EA
```

Output:

```text
deployment_checklist.md
```

---

## 5. Strategy plugin architecture

Hệ thống phải cho phép thêm strategy mới mà không phá core.

### 5.1 Mỗi strategy là một module riêng

```text
strategies/<strategy_name>/
├── hypothesis.md
├── rule_spec.md
├── indicator_spec.md
├── ea_params.yaml
├── optimization_space.yaml
├── validation_report.md
└── README.md
```

### 5.2 Quy tắc thêm strategy mới

Muốn thêm strategy mới, phải tạo tối thiểu:

```text
1. hypothesis.md
2. rule_spec.md
3. indicator_spec.md
4. ea_params.yaml
5. optimization_space.yaml
```

Không đủ 5 file trên → không được code.

### 5.3 Interface chung

Mọi strategy phải tuân thủ interface:

```cpp
class IStrategy
{
public:
   virtual bool CheckSignal(int &signalType) = 0;
   virtual double GetSLPrice() = 0;
   virtual double GetTPPrice() = 0;
   virtual bool IsConflict() = 0;
   virtual string GetTF1State() = 0;
   virtual string GetTF2State() = 0;
   virtual string GetTF3State() = 0;
   virtual string GetStrategyName() = 0;
};
```

---

## 6. Python orchestration flow

```text
python/orchestrator/run_pipeline.py
```

Flow:

```text
1. Load config
2. Run Research Agent
3. Run Rule Agent
4. Generate indicator/EA prompt
5. Run code generation
6. Compile MQL5
7. Run MT5 backtest
8. Parse trade log
9. Run quant validation
10. Run optimizer
11. Run walk-forward/OOS
12. Run portfolio analysis
13. Run risk/Kelly
14. Run QA gate
15. Generate final report
```

---

## 7. Inter-EA Portfolio State (Global Variables)

Thiết kế "1 chart = 1 EA instance" tạo ra vấn đề: EA trên XAUUSD không biết EA trên EURUSD đang có bao nhiêu open risk. Giải pháp: dùng **MT5 Global Variables** làm shared state.

### 7.1 Cơ chế

```text
MT5 Global Variables là key-value store dùng chung giữa tất cả EA/script đang chạy.
Không cần file, không cần pipe. Atomic read/write.
```

### 7.2 Naming convention

```text
Prefix: QT_<magic_base>_<field>
Ví dụ với magic_base = 20260501:

QT_20260501_TOTAL_RISK     → tổng open risk % hiện tại (sum của tất cả EA)
QT_20260501_DAILY_PL       → daily P/L % của portfolio
QT_20260501_DD             → current drawdown %
QT_20260501_OPEN_COUNT     → số lệnh đang mở toàn portfolio
QT_20260501_TS             → timestamp lần ghi cuối (unix seconds)
QT_20260501_KILL           → 1.0 = kill switch active, 0.0 = normal
```

### 7.3 MQL5 pseudocode — EA ghi state

```cpp
// Mỗi EA ghi contribution của mình vào global sau mỗi open/close order

void UpdatePortfolioGlobalVars()
{
   string prefix = "QT_" + IntegerToString(MagicNumberBase);

   // Tính open risk của EA này (trên symbol này)
   double myOpenRisk = CalculateMyOpenRisk();

   // Đọc tổng hiện tại
   double totalRisk = GlobalVariableGet(prefix + "_TOTAL_RISK");

   // Ghi lại (tổng đã trừ contribution cũ, cộng mới)
   // NOTE: cần mutex pattern — dùng GlobalVariableTemp để atomic
   GlobalVariableSet(prefix + "_TOTAL_RISK", totalRisk);
   GlobalVariableSet(prefix + "_TS", (double)TimeCurrent());
}

bool IsKillSwitchActive()
{
   string key = "QT_" + IntegerToString(MagicNumberBase) + "_KILL";
   if(GlobalVariableExists(key))
      return GlobalVariableGet(key) == 1.0;
   return false;
}
```

### 7.4 Python đọc state (connector.py đã implement)

```python
with get_connector(mt5_paths) as conn:
    state = conn.get_portfolio_state(magic_base=20260501)
    print(state["total_open_risk"])   # tổng risk đang mở
    print(state["daily_pl_pct"])      # daily P/L
```

### 7.5 Quy định ghi/đọc

```text
✔ Mỗi EA ghi state sau mỗi sự kiện: open order, close order, SL hit, TP hit
✔ Mỗi EA đọc TOTAL_RISK trước khi mở lệnh mới
✔ Nếu TOTAL_RISK + myNewRisk > MaxPortfolioRisk → BLOCKED
✔ Nếu KILL = 1.0 → tất cả EA dừng trade ngay
✔ Python Monitoring Agent có thể set KILL = 1.0 qua connector.gv_set()
```

### 7.6 Race condition

```text
MT5 Global Variables là single-threaded per terminal → không có race condition
giữa các EA instances trong cùng 1 terminal.
```

---

## 8. Agent permission model

| Area | Read | Write |
|---|---|---|
| docs/ | All agents | QA/Architect only |
| strategies/ | All agents | Research/Rule/Coder |
| mql5/ | Coder/QA | Coder only |
| python/ | Quant/Optimizer/QA | Quant/Optimizer |
| configs/ | All agents | Architect only |
| logs/ | All agents | Runtime only |

---

## 8. Hard rules

```text
Không SL → không trade
Không OOS → không deploy
Không QA PASS → không demo/live
Không đủ sample → không dùng Kelly
Không dùng Full Kelly live
Không tối ưu bằng net profit đơn thuần
Không sửa risk policy tự động
Không để agent tự live trade
```

---

## 9. Definition of Done

Hệ thống agent đạt chuẩn khi:

```text
✔ Có pipeline Python chạy được từ config
✔ Có ít nhất 1 strategy qua full cycle
✔ Có trade_log.csv
✔ Có validation_report.md
✔ Có qa_report.md
✔ Có risk/Kelly report
✔ Có demo deployment checklist
✔ Có thể thêm strategy mới bằng plugin folder
```
