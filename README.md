# MT5 Verifiable Strategy Lab

A disciplined framework for researching, coding, and verifying algorithmic trading strategies on MetaTrader 5 — with a full automated pipeline from idea to QA-gated EA.

## Philosophy

> No SL → no trade. No OOS → no deploy. No QA PASS → no live.

Every strategy must pass a 17-item QA gate (A–Q) including out-of-sample validation, Monte Carlo stress test, and regime detection before it can be deployed even to demo.

## Pipeline

```
Research → Rule Spec → MQL5 Code → Compile → Backtest
         → Walk-Forward → QA Gate (A–Q) → Deploy Demo
```

Run the full pipeline (dry-run, no MT5 required):
```bash
python python/orchestrator/run_pipeline.py --strategy wyckoff --symbol XAUUSD --dry-run
```

Run QA gate only:
```bash
python python/validator/qa_gate.py --strategy wyckoff --symbol XAUUSD
```

## Project Structure

```
├── configs/                    # YAML config (symbols, risk, strategies, paths)
├── docs/                       # System specs and agent design
│   ├── AGENT_SYSTEM_SPEC.md    # 11-agent architecture
│   ├── RISK_POLICY.md          # Risk rules (immutable)
│   ├── QA_GATE.md              # 17-item checklist + Monte Carlo + Regime
│   ├── MT5_MASTER.md           # Single entry point to understand the system
│   └── ...
├── mql5/
│   ├── Experts/                # EA source (.mq5)
│   ├── Indicators/             # Custom indicators
│   └── Include/core/           # Shared: IStrategy, RiskManager, TradeManager
├── python/
│   ├── orchestrator/           # Pipeline runner + state machine (resume from step N)
│   ├── build/                  # MQL5 compiler wrapper
│   ├── backtest/               # MT5 tester runner, walk-forward, trade log parser
│   ├── validator/              # QA gate (A–Q), Monte Carlo
│   ├── optimizer/              # Optuna hyperparameter search
│   ├── monitoring/             # Live strategy decay detection
│   └── mt5_interface/          # Python ↔ MT5 connector
└── strategies/
    ├── wyckoff/                # Spring/Upthrust strategy
    └── smc_ict/                # Smart Money Concepts / ICT strategy
```

## Strategies

### Wyckoff Spring/Upthrust
- **Timeframe:** H4 bias → H1 entry → M15 trigger
- **Entry:** Spring (false break below support) or Upthrust (false break above resistance)
- **Exit:** H1 bias flip (Upthrust signal on longs, vice versa)
- **MQL5:** `mql5/Experts/PortfolioEA_Wyckoff.mq5` + `mql5/Indicators/Wyckoff_Phase_Indicator.mq5`

### SMC/ICT
- **Timeframe:** H4 structure → H1 order block + liquidity sweep → M15 trigger
- **Entry:** BOS on H4 → liquidity sweep of equal highs/lows → OB+FVG in discount zone → M15 engulfing
- **Position mgmt:** Partial close 50% at 1R → SL to breakeven → hold for CHoCH exit
- **Exit:** CHoCH on H1 (reversal signal) or OB violated (close below order block)
- **MQL5:** `mql5/Experts/PortfolioEA_SMC.mq5` + `mql5/Indicators/SMC_Structure_Indicator.mq5`

## Key Design Decisions

- **Each strategy has unique logic** — no shared entry/exit template across strategies
- **Portfolio-aware risk** — EAs read a shared global variable for total open risk, refuse new trades if portfolio exposure limit is hit
- **Agent-assisted, human-approved** — AI agents research and code; humans approve before any live deployment
- **Fully auditable** — every step produces artifacts (compile log, backtest report, QA report, walk-forward folds)

## Requirements

```bash
pip install pyyaml pandas numpy optuna
```

MT5 and MetaEditor are only required for actual compile/backtest steps (not for dry-run or QA gate).

## License

MIT
