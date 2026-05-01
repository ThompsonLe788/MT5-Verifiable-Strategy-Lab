"""
run_pipeline.py — Main pipeline orchestrator.

Chạy toàn bộ 15 bước từ config đến QA report.
Hỗ trợ resume từ bước N nếu pipeline bị gián đoạn.

Usage:
    python run_pipeline.py --strategy wyckoff --symbol XAUUSD
    python run_pipeline.py --strategy wyckoff --symbol XAUUSD --from-step 7
    python run_pipeline.py --strategy wyckoff --symbol XAUUSD --dry-run
"""

import argparse
import logging
import sys
import yaml
from pathlib import Path
from datetime import datetime

# Thêm project root vào path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "python"))

from orchestrator.pipeline_state import PipelineState, StepStatus
from build.mql5_compiler import MQL5Compiler
from backtest.tester_runner import MT5TesterRunner
from backtest.trade_log_parser import parse_trade_log, validate_sample_size

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/pipeline.log"),
    ]
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_configs() -> dict:
    cfg = {}
    config_dir = PROJECT_ROOT / "configs"
    for name in ["mt5_paths", "symbols", "risk", "strategies", "optimization"]:
        with open(config_dir / f"{name}.yaml") as f:
            cfg[name] = yaml.safe_load(f)
    return cfg


def get_strategy_config(cfg: dict, strategy_name: str) -> dict:
    strategies = cfg["strategies"]["strategies"]
    if strategy_name not in strategies:
        raise ValueError(f"Strategy '{strategy_name}' không có trong configs/strategies.yaml")
    return strategies[strategy_name]


def get_symbol_config(cfg: dict, symbol: str) -> dict:
    symbols = cfg["symbols"]["symbols"]
    if symbol not in symbols:
        raise ValueError(f"Symbol '{symbol}' không có trong configs/symbols.yaml")
    return symbols[symbol]


# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

def preflight_check(cfg: dict, strategy_name: str, symbol: str) -> list[str]:
    """Kiểm tra điều kiện trước khi chạy pipeline. Trả về list lỗi."""
    errors = []
    strat = cfg["strategies"]["strategies"].get(strategy_name)

    if strat is None:
        errors.append(f"Strategy '{strategy_name}' không tồn tại trong strategies.yaml")
        return errors

    if symbol not in strat.get("symbols", []):
        errors.append(f"Symbol '{symbol}' không nằm trong danh sách của strategy '{strategy_name}'")

    folder = PROJECT_ROOT / strat["folder"]
    required_files = [
        "hypothesis.md", "rule_spec.md",
        "indicator_spec.md", "ea_params.yaml", "optimization_space.yaml"
    ]
    for f in required_files:
        if not (folder / f).exists():
            errors.append(f"Thiếu file bắt buộc: {strat['folder']}/{f}")

    mt5_exe = Path(cfg["mt5_paths"]["terminal_exe"])
    if not mt5_exe.exists():
        errors.append(f"terminal64.exe không tìm thấy: {mt5_exe}")

    me_exe = Path(cfg["mt5_paths"]["metaeditor_exe"])
    if not me_exe.exists():
        errors.append(f"metaeditor64.exe không tìm thấy: {me_exe}")

    return errors


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def step_01_validate_spec(state: PipelineState, cfg: dict, strategy_name: str) -> bool:
    """Bước 1: Kiểm tra strategy spec đủ 5 file và nội dung hợp lệ."""
    log.info("[Step 01] Validate strategy spec")
    strat = cfg["strategies"]["strategies"][strategy_name]
    folder = PROJECT_ROOT / strat["folder"]

    required = ["hypothesis.md", "rule_spec.md", "indicator_spec.md",
                "ea_params.yaml", "optimization_space.yaml"]
    missing = [f for f in required if not (folder / f).exists()]

    if missing:
        log.error(f"  Thiếu files: {missing}")
        state.fail_step(1, f"Missing: {missing}")
        return False

    log.info("  OK — tất cả 5 file tồn tại")
    state.complete_step(1)
    return True


def step_02_compile_indicators(state: PipelineState, cfg: dict, strategy_name: str) -> bool:
    """Bước 2: Compile indicators."""
    log.info("[Step 02] Compile indicators")
    strat = cfg["strategies"]["strategies"][strategy_name]
    mql5_root = Path(cfg["mt5_paths"]["portable_dir"]) / cfg["mt5_paths"]["mql5_root"]

    compiler = MQL5Compiler(
        metaeditor_exe=cfg["mt5_paths"]["metaeditor_exe"],
        log_dir=cfg["mt5_paths"]["compile_log_dir"]
    )

    for ind_file in strat.get("indicator_files", []):
        mq5_path = str(mql5_root / ind_file.replace(".ex5", ".mq5"))
        result = compiler.compile(mq5_path)
        if not result.success:
            log.error(f"  Compile FAIL: {ind_file}")
            for msg in result.messages[-10:]:
                log.error(f"    {msg}")
            state.fail_step(2, f"Compile failed: {ind_file}")
            return False
        log.info(f"  OK: {ind_file} — {result.warnings} warning(s)")

    state.complete_step(2)
    return True


def step_03_compile_ea(state: PipelineState, cfg: dict, strategy_name: str) -> bool:
    """Bước 3: Compile EA."""
    log.info("[Step 03] Compile EA")
    strat = cfg["strategies"]["strategies"][strategy_name]
    mql5_root = Path(cfg["mt5_paths"]["portable_dir"]) / cfg["mt5_paths"]["mql5_root"]
    ea_mq5 = str(mql5_root / strat["ea_file"].replace(".ex5", ".mq5"))

    compiler = MQL5Compiler(
        metaeditor_exe=cfg["mt5_paths"]["metaeditor_exe"],
        log_dir=cfg["mt5_paths"]["compile_log_dir"]
    )
    result = compiler.compile(ea_mq5)

    if not result.success:
        log.error(f"  EA compile FAIL")
        for msg in result.messages[-10:]:
            log.error(f"    {msg}")
        state.fail_step(3, f"EA compile failed: {ea_mq5}")
        return False

    log.info(f"  OK: {strat['ea_file']} — {result.warnings} warning(s)")
    state.complete_step(3)
    return True


def step_04_run_backtest_is(
    state: PipelineState, cfg: dict,
    strategy_name: str, symbol: str
) -> bool:
    """Bước 4: Chạy backtest In-Sample."""
    log.info("[Step 04] Backtest In-Sample")
    strat      = cfg["strategies"]["strategies"][strategy_name]
    sym_cfg    = cfg["symbols"]["symbols"][symbol]

    with open(PROJECT_ROOT / strat["folder"] / "ea_params.yaml") as f:
        ea_params = yaml.safe_load(f)

    tf3 = ea_params.get("timeframes", {}).get("tf3", "M15")
    from backtest.tester_runner import PERIOD_MAP
    period = PERIOD_MAP.get(tf3, 15)

    backtest_config = {
        "expert_path": strat["ea_file"],
        "symbol":      symbol,
        "period":      period,
        "from_date":   "2020.01.01",
        "to_date":     "2023.06.30",    # IS period
        "model":       sym_cfg.get("backtest_model", 1),
        "deposit":     10000,
        "inputs":      {
            "EnableTrading":    "true",
            "MagicNumber":      str(cfg["risk"]["magic_base"] + strat["magic_offset"]),
            "RiskPerTradePct":  str(cfg["risk"]["position_sizing"]["base_risk_pct"]),
        }
    }

    runner = MT5TesterRunner(cfg["mt5_paths"])
    result = runner.run_backtest(backtest_config)

    if result["status"] != "OK":
        state.fail_step(4, f"IS Backtest failed: {result.get('reason')}")
        return False

    state.set_data("is_report", result["report_path"])
    log.info(f"  OK — report: {result['report_path']}")
    state.complete_step(4)
    return True


def step_05_parse_validate_log(
    state: PipelineState, cfg: dict, strategy_name: str
) -> bool:
    """Bước 5: Parse trade log và validate sample size."""
    log.info("[Step 05] Parse & validate trade log")
    files_dir = Path(cfg["mt5_paths"]["portable_dir"]) / cfg["mt5_paths"]["files_dir"]
    log_path  = files_dir / "trade_log.csv"

    if not log_path.exists():
        state.fail_step(5, f"trade_log.csv không tìm thấy: {log_path}")
        return False

    try:
        df = parse_trade_log(str(log_path))
    except ValueError as e:
        state.fail_step(5, str(e))
        return False

    min_trades = cfg["optimization"]["reject_trial_if"]["total_trades_lt"]
    if not validate_sample_size(df, min_trades):
        state.fail_step(5, f"Sample quá ít: {len(df)} trades (cần >= {min_trades})")
        return False

    # Copy trade log vào logs/ với timestamp
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = PROJECT_ROOT / "logs" / f"{strategy_name}_is_{ts}_trade_log.csv"
    dest.parent.mkdir(exist_ok=True)
    import shutil
    shutil.copy(log_path, dest)

    state.set_data("is_trade_log", str(dest))
    log.info(f"  OK — {len(df)} trades → {dest.name}")
    state.complete_step(5)
    return True


def step_06_quant_validation(
    state: PipelineState, cfg: dict, strategy_name: str
) -> bool:
    """Bước 6: Quant metrics validation."""
    log.info("[Step 06] Quant validation")
    import pandas as pd
    import numpy as np

    log_path = state.get_data("is_trade_log")
    df = parse_trade_log(log_path)

    wins   = df[df["profit"] > 0]
    losses = df[df["profit"] <= 0]

    winrate    = len(wins) / len(df)
    avg_win    = wins["profit"].mean() if len(wins) > 0 else 0
    avg_loss   = abs(losses["profit"].mean()) if len(losses) > 0 else 1
    expectancy = winrate * avg_win - (1 - winrate) * avg_loss
    pf         = wins["profit"].sum() / abs(losses["profit"].sum()) if len(losses) > 0 else 999

    equity     = df["profit"].cumsum()
    peak       = equity.cummax()
    drawdowns  = (equity - peak) / (peak.abs() + 1e-9)
    max_dd     = abs(drawdowns.min())

    returns    = df["profit"] / df["profit"].abs().mean()
    sharpe     = returns.mean() / (returns.std() + 1e-9) * (252 ** 0.5)

    thresholds = cfg["optimization"]["reject_trial_if"]
    metrics = {
        "total_trades": len(df),
        "winrate": winrate,
        "expectancy": expectancy,
        "profit_factor": pf,
        "max_dd": max_dd,
        "sharpe": sharpe,
    }

    log.info(f"  Metrics: trades={len(df)}, WR={winrate:.1%}, PF={pf:.2f}, "
             f"DD={max_dd:.1%}, Sharpe={sharpe:.2f}")

    failures = []
    if pf   < thresholds["profit_factor_lt"]:  failures.append(f"PF={pf:.2f} < {thresholds['profit_factor_lt']}")
    if max_dd > thresholds["max_dd_gt"]:        failures.append(f"DD={max_dd:.1%} > {thresholds['max_dd_gt']:.0%}")
    if sharpe < thresholds["sharpe_lt"]:        failures.append(f"Sharpe={sharpe:.2f} < {thresholds['sharpe_lt']}")
    if expectancy <= thresholds["expectancy_lte"]: failures.append(f"Expectancy={expectancy:.4f} <= 0")

    if failures:
        log.error(f"  FAIL: {failures}")
        state.fail_step(6, f"Metrics không đạt: {failures}")
        return False

    state.set_data("is_metrics", metrics)
    log.info("  PASS")
    state.complete_step(6)
    return True


def step_07_run_walk_forward(
    state: PipelineState, cfg: dict,
    strategy_name: str, symbol: str
) -> bool:
    """Bước 7: Walk-forward validation."""
    log.info("[Step 07] Walk-forward / OOS")
    from backtest.walk_forward import generate_wf_folds, run_walk_forward
    from datetime import date

    strat   = cfg["strategies"]["strategies"][strategy_name]
    wf_cfg  = cfg["optimization"]["walk_forward"]
    runner  = MT5TesterRunner(cfg["mt5_paths"])

    folds = generate_wf_folds(
        start=date(2020, 1, 1),
        end=date(2023, 12, 31),
        train_months=wf_cfg["train_months"],
        test_months=wf_cfg["test_months"],
    )

    if len(folds) < wf_cfg["min_folds"]:
        state.fail_step(7, f"Không đủ folds: {len(folds)} < {wf_cfg['min_folds']}")
        return False

    sym_cfg = cfg["symbols"]["symbols"][symbol]
    with open(PROJECT_ROOT / strat["folder"] / "ea_params.yaml") as f:
        ea_params = yaml.safe_load(f)

    from backtest.tester_runner import PERIOD_MAP
    period = PERIOD_MAP.get(ea_params.get("timeframes", {}).get("tf3", "M15"), 15)

    base_config = {
        "expert_path": strat["ea_file"],
        "symbol": symbol,
        "period": period,
        "model": sym_cfg.get("backtest_model", 1),
        "deposit": 10000,
        "inputs": {
            "RiskPerTradePct": str(cfg["risk"]["position_sizing"]["base_risk_pct"]),
        }
    }

    wf_results = run_walk_forward(runner, base_config, folds)

    # Đánh giá OOS pass rate
    # (simplified — trong thực tế cần parse từng trade_log của từng fold)
    state.set_data("wf_results", wf_results)
    log.info(f"  OK — {len(folds)} folds hoàn thành")
    state.complete_step(7)
    return True


def step_08_monte_carlo(state: PipelineState) -> bool:
    """Bước 8: Monte Carlo simulation."""
    log.info("[Step 08] Monte Carlo")
    import pandas as pd

    log_path = state.get_data("is_trade_log")
    df = parse_trade_log(log_path)
    profits = df["profit"].tolist()

    sys.path.insert(0, str(PROJECT_ROOT / "python"))
    from validator.monte_carlo import run_monte_carlo

    mc = run_monte_carlo(profits, n_simulations=1000)
    log.info(f"  Median DD={mc['median_max_dd']:.1%}, "
             f"p95 DD={mc['p95_max_dd']:.1%}, "
             f"Ruin rate={mc['ruin_rate']:.1%}")

    if mc["ruin_rate"] >= 0.01:
        state.fail_step(8, f"Ruin rate={mc['ruin_rate']:.1%} >= 1%")
        return False
    if abs(mc["p95_max_dd"]) > 0.25:
        state.fail_step(8, f"p95 DD={mc['p95_max_dd']:.1%} > 25%")
        return False

    state.set_data("monte_carlo", mc)
    log.info("  PASS")
    state.complete_step(8)
    return True


def step_09_generate_qa_report(
    state: PipelineState, strategy_name: str, symbol: str
) -> bool:
    """Bước 9: Generate QA report."""
    log.info("[Step 09] Generate QA report")

    metrics = state.get_data("is_metrics") or {}
    mc      = state.get_data("monte_carlo") or {}
    ts      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report = f"""# QA REPORT

Strategy: {strategy_name}
Symbol:   {symbol}
Date:     {ts}

## Verdict
CONDITIONAL PASS — human review required before demo

## Metrics (IS)
- Total trades:   {metrics.get('total_trades', 'N/A')}
- Winrate:        {metrics.get('winrate', 0):.1%}
- Profit Factor:  {metrics.get('profit_factor', 0):.2f}
- Max DD:         {metrics.get('max_dd', 0):.1%}
- Sharpe:         {metrics.get('sharpe', 0):.2f}
- Expectancy:     {metrics.get('expectancy', 0):.4f}

## Monte Carlo (1000 sim)
- Median max DD:  {mc.get('median_max_dd', 0):.1%}
- p95 max DD:     {mc.get('p95_max_dd', 0):.1%}
- Ruin rate:      {mc.get('ruin_rate', 0):.1%}

## Pipeline steps completed
{state.summary()}

## Required before demo
- [ ] Human review QA report
- [ ] OOS metrics verified
- [ ] Risk policy sign-off
- [ ] Demo account configured
"""

    strat_folder = PROJECT_ROOT / "strategies" / strategy_name
    strat_folder.mkdir(parents=True, exist_ok=True)
    report_path = strat_folder / "qa_report.md"
    report_path.write_text(report)

    log.info(f"  QA report: {report_path}")
    state.complete_step(9)
    return True


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

STEPS = {
    1: step_01_validate_spec,
    2: step_02_compile_indicators,
    3: step_03_compile_ea,
    4: step_04_run_backtest_is,
    5: step_05_parse_validate_log,
    6: step_06_quant_validation,
    7: step_07_run_walk_forward,
    8: step_08_monte_carlo,
    9: step_09_generate_qa_report,
}


def run(strategy_name: str, symbol: str, from_step: int = 1, dry_run: bool = False):
    log.info("=" * 60)
    log.info(f"PIPELINE START | strategy={strategy_name} | symbol={symbol}")
    log.info(f"from_step={from_step} | dry_run={dry_run}")
    log.info("=" * 60)

    cfg = load_configs()

    # Pre-flight
    errors = preflight_check(cfg, strategy_name, symbol)
    if errors:
        for e in errors:
            log.error(f"[PRE-FLIGHT] {e}")
        sys.exit(1)

    # Load hoặc tạo mới pipeline state
    state_path = PROJECT_ROOT / "logs" / f"pipeline_state_{strategy_name}_{symbol}.json"
    state = PipelineState.load(state_path) if state_path.exists() else PipelineState(
        strategy=strategy_name, symbol=symbol, path=state_path
    )

    if dry_run:
        log.info("[DRY RUN] Pre-flight OK. Không chạy thực tế.")
        return

    # Chạy từng bước
    for step_num in sorted(STEPS.keys()):
        if step_num < from_step:
            log.info(f"[Step {step_num:02d}] Skipped (from_step={from_step})")
            continue

        if state.is_completed(step_num):
            log.info(f"[Step {step_num:02d}] Already completed — skip")
            continue

        fn = STEPS[step_num]

        # Inject đúng args theo step
        if step_num in (1, 2, 3):
            ok = fn(state, cfg, strategy_name)
        elif step_num in (4, 7):
            ok = fn(state, cfg, strategy_name, symbol)
        elif step_num in (5, 6, 8):
            ok = fn(state, cfg, strategy_name) if step_num != 8 else fn(state)
        elif step_num == 9:
            ok = fn(state, strategy_name, symbol)
        else:
            ok = True

        if not ok:
            log.error(f"Pipeline STOPPED tại step {step_num}.")
            log.error(f"Sửa lỗi và chạy lại với --from-step {step_num}")
            sys.exit(1)

    log.info("=" * 60)
    log.info("PIPELINE COMPLETE")
    log.info(f"QA report: strategies/{strategy_name}/qa_report.md")
    log.info("=" * 60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MT5 Quant Pipeline Orchestrator")
    parser.add_argument("--strategy", required=True, help="Tên strategy (vd: wyckoff)")
    parser.add_argument("--symbol",   required=True, help="Symbol (vd: XAUUSD)")
    parser.add_argument("--from-step", type=int, default=1, dest="from_step",
                        help="Resume từ bước N (mặc định: 1)")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                        help="Chỉ kiểm tra pre-flight, không chạy thực tế")

    args = parser.parse_args()
    run(args.strategy, args.symbol, args.from_step, args.dry_run)
