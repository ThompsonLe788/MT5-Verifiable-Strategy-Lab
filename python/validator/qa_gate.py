"""
qa_gate.py — Automated QA Gate (checklist A-Q từ docs/QA_GATE.md).

Phân loại verdict: PASS / CONDITIONAL_PASS / FAIL

Usage:
    # File + config checks only (không cần trade log):
    python validator/qa_gate.py --strategy wyckoff

    # Full check với trade log:
    python validator/qa_gate.py --strategy wyckoff --trade-log logs/trade_log.csv

    # Full check + regime (cần price CSV có cột: timestamp,close,high,low):
    python validator/qa_gate.py --strategy wyckoff --trade-log ... --price-csv ...
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "python"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

log = logging.getLogger(__name__)

VERDICT_PASS             = "PASS"
VERDICT_CONDITIONAL_PASS = "CONDITIONAL_PASS"
VERDICT_FAIL             = "FAIL"

# Thresholds từ QA_GATE.md §5
QUANT_THRESHOLDS = {
    "total_trades_min":  200,
    "oos_trades_min":    50,
    "expectancy_min":    0.0,
    "profit_factor_min": 1.15,
    "max_dd_max":        0.15,
    "sharpe_min":        0.5,
    "oos_degradation_max": 0.50,
}


# ---------------------------------------------------------------------------
# Data structure
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    item:    str         # A, B, C, ...
    label:   str         # mô tả ngắn
    status:  str         # PASS | WARN | FAIL | SKIP
    detail:  str = ""    # thông tin thêm

    def is_fail(self) -> bool:
        return self.status == "FAIL"

    def is_warn(self) -> bool:
        return self.status == "WARN"


@dataclass
class QAReport:
    strategy:   str
    symbol:     str
    generated:  str = field(default_factory=lambda: datetime.utcnow().isoformat())
    checks:     list[CheckResult] = field(default_factory=list)
    verdict:    str = ""
    hard_fails: list[str] = field(default_factory=list)
    metrics:    dict = field(default_factory=dict)

    def add(self, result: CheckResult):
        self.checks.append(result)

    def compute_verdict(self) -> str:
        fails = [c for c in self.checks if c.is_fail()]
        warns = [c for c in self.checks if c.is_warn()]

        if self.hard_fails or fails:
            self.verdict = VERDICT_FAIL
        elif warns:
            self.verdict = VERDICT_CONDITIONAL_PASS
        else:
            self.verdict = VERDICT_PASS
        return self.verdict


# ---------------------------------------------------------------------------
# Helper loaders
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _file_contains(path: Path, *keywords: str) -> bool:
    """True nếu file tồn tại và chứa TẤT CẢ keywords (case-insensitive)."""
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8", errors="replace").lower()
    return all(kw.lower() in text for kw in keywords)


def _strategy_dir(strategy_name: str) -> Path:
    return PROJECT_ROOT / "strategies" / strategy_name


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_A_strategy_rule(strategy_name: str) -> CheckResult:
    """A: Có IF/THEN đo được, entry/SL/TP/invalidation."""
    rule_spec = _strategy_dir(strategy_name) / "rule_spec.md"
    hyp       = _strategy_dir(strategy_name) / "hypothesis.md"

    if not rule_spec.exists():
        return CheckResult("A", "Strategy & Rule", "FAIL", "rule_spec.md không tồn tại")
    if not hyp.exists():
        return CheckResult("A", "Strategy & Rule", "FAIL", "hypothesis.md không tồn tại")

    missing = []
    for keyword in ["entry", "sl", "tp", "invalidation"]:
        if not _file_contains(rule_spec, keyword):
            missing.append(keyword)

    # "source" hoặc "nguồn" (tiếng Việt)
    if not (_file_contains(hyp, "source") or _file_contains(hyp, "nguồn")):
        missing.append("source/hypothesis")

    if missing:
        return CheckResult("A", "Strategy & Rule", "WARN",
                           f"rule_spec.md thiếu keyword: {missing}")
    return CheckResult("A", "Strategy & Rule", "PASS")


def check_B_multi_timeframe(strategy_name: str) -> CheckResult:
    """B: Có TF1/TF2/TF3 và conflict rule."""
    ea_params = _load_yaml(_strategy_dir(strategy_name) / "ea_params.yaml")
    tfs = ea_params.get("timeframes", {})

    missing = [k for k in ("tf1", "tf2", "tf3") if k not in tfs]
    if missing:
        return CheckResult("B", "Multi-timeframe", "FAIL",
                           f"ea_params.yaml thiếu timeframes: {missing}")

    rule_spec = _strategy_dir(strategy_name) / "rule_spec.md"
    if not _file_contains(rule_spec, "tf1", "tf2"):
        return CheckResult("B", "Multi-timeframe", "WARN",
                           "rule_spec.md không đề cập TF1/TF2 conflict rule")

    return CheckResult("B", "Multi-timeframe", "PASS",
                       f"TF1={tfs['tf1']} TF2={tfs['tf2']} TF3={tfs['tf3']}")


def check_C_indicator(strategy_name: str) -> CheckResult:
    """C: Indicator có logic detect, input/output, non-repaint."""
    ind_spec = _strategy_dir(strategy_name) / "indicator_spec.md"
    if not ind_spec.exists():
        return CheckResult("C", "Indicator Spec", "FAIL",
                           "indicator_spec.md không tồn tại")

    missing = []
    for kw in ["non-repaint", "buffer", "input"]:
        if not _file_contains(ind_spec, kw):
            missing.append(kw)

    if missing:
        return CheckResult("C", "Indicator Spec", "WARN",
                           f"indicator_spec.md thiếu: {missing}")
    return CheckResult("C", "Indicator Spec", "PASS")


def check_D_ea_architecture() -> CheckResult:
    """D: SOLID architecture — tách module."""
    required = [
        PROJECT_ROOT / "mql5" / "Include" / "core" / "IStrategy.mqh",
        PROJECT_ROOT / "mql5" / "Include" / "core" / "RiskManager.mqh",
        PROJECT_ROOT / "mql5" / "Include" / "core" / "TradeManager.mqh",
        PROJECT_ROOT / "mql5" / "Include" / "core" / "Logger.mqh",
    ]
    missing = [str(p.name) for p in required if not p.exists()]
    if missing:
        return CheckResult("D", "EA Architecture", "FAIL",
                           f"Thiếu modules: {missing}")
    return CheckResult("D", "EA Architecture", "PASS",
                       "IStrategy/RiskManager/TradeManager/Logger tồn tại")


def check_E_backtest_data(trade_log_path: str | None) -> CheckResult:
    """E: Có dataset, sample size."""
    if not trade_log_path:
        return CheckResult("E", "Backtest Dataset", "SKIP",
                           "trade_log_path không được cung cấp")

    p = Path(trade_log_path)
    if not p.exists():
        return CheckResult("E", "Backtest Dataset", "FAIL",
                           f"trade_log không tìm thấy: {p}")

    try:
        df = pd.read_csv(p)
        n  = len(df)
        if n < QUANT_THRESHOLDS["total_trades_min"]:
            return CheckResult("E", "Backtest Dataset", "FAIL",
                               f"Sample quá ít: {n} trades < {QUANT_THRESHOLDS['total_trades_min']}")
        return CheckResult("E", "Backtest Dataset", "PASS", f"{n} trades")
    except Exception as e:
        return CheckResult("E", "Backtest Dataset", "FAIL", str(e))


def check_F_quant_metrics(metrics: dict) -> list[CheckResult]:
    """F: Winrate, expectancy, PF, DD, Sharpe — multi-check."""
    if not metrics:
        return [CheckResult("F", "Quant Metrics", "SKIP",
                            "metrics không có (cần trade log)")]

    results = []
    checks = [
        ("expectancy",     "Expectancy",     metrics.get("expectancy", 0),
         lambda v: v > QUANT_THRESHOLDS["expectancy_min"],
         f"> {QUANT_THRESHOLDS['expectancy_min']}"),
        ("profit_factor",  "Profit Factor",  metrics.get("profit_factor", 0),
         lambda v: v >= QUANT_THRESHOLDS["profit_factor_min"],
         f">= {QUANT_THRESHOLDS['profit_factor_min']}"),
        ("max_dd_pct",     "Max Drawdown",   abs(metrics.get("max_dd_pct", 1)),
         lambda v: v <= QUANT_THRESHOLDS["max_dd_max"],
         f"<= {QUANT_THRESHOLDS['max_dd_max']:.0%}"),
        ("sharpe",         "Sharpe",         metrics.get("sharpe", 0),
         lambda v: v > QUANT_THRESHOLDS["sharpe_min"],
         f"> {QUANT_THRESHOLDS['sharpe_min']}"),
    ]
    for key, label, val, cond, threshold_str in checks:
        status = "PASS" if cond(val) else "FAIL"
        results.append(CheckResult("F", f"Quant/{label}", status,
                                   f"{val:.4f} (threshold: {threshold_str})"))
    return results


def check_G_optimization(strategy_name: str) -> CheckResult:
    """G: Không dùng net_profit đơn thuần."""
    opt_space = _load_yaml(_strategy_dir(strategy_name) / "optimization_space.yaml")
    objective = opt_space.get("objective", "")

    if "net_profit" in str(objective).lower() and "sharpe" not in str(objective).lower():
        return CheckResult("G", "Optimization Objective", "FAIL",
                           f"Objective là net_profit đơn thuần: '{objective}'")

    if not objective:
        global_opt = _load_yaml(PROJECT_ROOT / "configs" / "optimization.yaml")
        objective  = global_opt.get("objective", {}).get("name", "")

    return CheckResult("G", "Optimization Objective", "PASS",
                       f"objective='{objective}'")


def check_H_walk_forward(wf_results: list[dict] | None) -> CheckResult:
    """H: Walk-forward / OOS."""
    if not wf_results:
        return CheckResult("H", "Walk-Forward / OOS", "SKIP",
                           "wf_results không được cung cấp")

    n_folds  = len(wf_results)
    n_passed = sum(1 for f in wf_results if f.get("oos_passed", False))
    ratio    = n_passed / n_folds if n_folds > 0 else 0

    oos_min = 0.5
    if ratio < oos_min:
        return CheckResult("H", "Walk-Forward / OOS", "FAIL",
                           f"OOS pass rate {ratio:.0%} < {oos_min:.0%} ({n_passed}/{n_folds})")
    return CheckResult("H", "Walk-Forward / OOS", "PASS",
                       f"OOS pass rate {ratio:.0%} ({n_passed}/{n_folds} folds)")


def check_I_risk(cfg: dict) -> CheckResult:
    """I: SL bắt buộc, DD limit, exposure cap."""
    risk     = cfg.get("risk", {})
    dd       = risk.get("drawdown", {})
    exposure = risk.get("exposure", {})
    sl_pol   = risk.get("sl_policy", {})

    missing = []
    if not dd.get("max_account_dd_pct"):
        missing.append("drawdown.max_account_dd_pct")
    if not risk.get("position_sizing", {}).get("base_risk_pct"):
        missing.append("position_sizing.base_risk_pct")
    if not exposure.get("max_portfolio_open_risk_pct"):
        missing.append("exposure.max_portfolio_open_risk_pct")
    if not sl_pol.get("mandatory", False):
        missing.append("sl_policy.mandatory=true")

    if missing:
        return CheckResult("I", "Risk Management", "FAIL",
                           f"Thiếu config: {missing}")
    return CheckResult("I", "Risk Management", "PASS",
                       f"DD limit={dd.get('max_account_dd_pct')}% "
                       f"base_risk={risk['position_sizing']['base_risk_pct']}% "
                       f"portfolio_cap={exposure.get('max_portfolio_open_risk_pct')}%")


def check_J_kelly(cfg: dict) -> CheckResult:
    """J: Fractional Kelly, sample đủ, cap risk."""
    risk = cfg.get("risk", {})
    ps   = risk.get("position_sizing", {})

    # risk.yaml lưu Kelly dưới position_sizing.*
    fraction   = ps.get("kelly_fraction",   ps.get("kelly_max", 1.0))
    max_risk   = ps.get("max_risk_pct",     1.0)
    min_sample = ps.get("kelly_min_sample", 0)
    # DD scaling: có nếu kelly_dd_multiplier tồn tại ở root
    has_dd_scaling = bool(risk.get("kelly_dd_multiplier"))

    issues = []
    if fraction > 0.5:
        issues.append(f"kelly_fraction={fraction} > 0.5 (Full Kelly nguy hiểm)")
    if max_risk > 1.0:
        issues.append(f"max_risk_pct={max_risk}% > 1%")
    if min_sample < 100:
        issues.append(f"kelly_min_sample={min_sample} < 100")
    if not has_dd_scaling:
        issues.append("kelly_dd_multiplier chưa cấu hình (Kelly cần giảm khi DD tăng)")

    if issues:
        return CheckResult("J", "Kelly Criterion", "WARN", "; ".join(issues))
    return CheckResult("J", "Kelly Criterion", "PASS",
                       f"fraction={fraction}, max_risk={max_risk}%, sample={min_sample}")


def check_K_portfolio(cfg: dict) -> CheckResult:
    """K: Portfolio risk cap."""
    risk     = cfg.get("risk", {})
    exposure = risk.get("exposure", {})
    cap      = exposure.get("max_portfolio_open_risk_pct", 0)

    if cap <= 0 or cap > 5:
        return CheckResult("K", "Portfolio Risk", "WARN",
                           f"max_portfolio_open_risk_pct={cap}% (khuyến nghị 2-3%)")
    return CheckResult("K", "Portfolio Risk", "PASS",
                       f"cap={cap}% corr_cap={exposure.get('max_correlated_exposure_pct','?')}%")


def check_L_ui_dashboard() -> CheckResult:
    """L: Dashboard, blocked reason, alert."""
    required = [
        PROJECT_ROOT / "mql5" / "Include" / "ui" / "Dashboard.mqh",
        PROJECT_ROOT / "mql5" / "Include" / "ui" / "AlertManager.mqh",
    ]
    missing = [p.name for p in required if not p.exists()]
    if missing:
        return CheckResult("L", "UI / Dashboard", "FAIL", f"Thiếu: {missing}")

    dash = PROJECT_ROOT / "mql5" / "Include" / "ui" / "Dashboard.mqh"
    if not _file_contains(dash, "reason", "block"):
        return CheckResult("L", "UI / Dashboard", "WARN",
                           "Dashboard.mqh không có blocked reason field")
    return CheckResult("L", "UI / Dashboard", "PASS")


def check_M_chart_setup() -> CheckResult:
    """M: Auto chart setup."""
    cs = PROJECT_ROOT / "mql5" / "Include" / "ui" / "ChartSetup.mqh"
    if not cs.exists():
        return CheckResult("M", "Auto Chart Setup", "WARN",
                           "ChartSetup.mqh không tồn tại")
    return CheckResult("M", "Auto Chart Setup", "PASS")


def check_N_logging() -> CheckResult:
    """N: decision_log, error_log, trade_log."""
    logger = PROJECT_ROOT / "mql5" / "Include" / "core" / "Logger.mqh"
    if not logger.exists():
        return CheckResult("N", "Logging", "FAIL", "Logger.mqh không tồn tại")

    missing = []
    for kw in ["decision", "error", "trade"]:
        if not _file_contains(logger, kw):
            missing.append(kw + "_log")

    if missing:
        return CheckResult("N", "Logging", "WARN",
                           f"Logger.mqh thiếu: {missing}")
    return CheckResult("N", "Logging", "PASS")


def check_O_deployment() -> CheckResult:
    """O: Monitoring và rollback có sẵn."""
    monitor   = PROJECT_ROOT / "python" / "monitoring" / "run_monitor.py"
    alert     = PROJECT_ROOT / "python" / "monitoring" / "alert.py"
    connector = PROJECT_ROOT / "python" / "mt5_interface" / "connector.py"

    missing = [p.name for p in (monitor, alert, connector) if not p.exists()]
    if missing:
        return CheckResult("O", "Deployment / Monitoring", "WARN",
                           f"Thiếu: {missing}")
    return CheckResult("O", "Deployment / Monitoring", "PASS")


def check_P_monte_carlo(trade_log_path: str | None) -> CheckResult:
    """P: Monte Carlo 1000 sim."""
    if not trade_log_path or not Path(trade_log_path).exists():
        return CheckResult("P", "Monte Carlo", "SKIP",
                           "trade_log không có — bỏ qua Monte Carlo")

    try:
        from backtest.trade_log_parser import parse_trade_log
        from validator.monte_carlo import run_monte_carlo

        df      = parse_trade_log(trade_log_path)
        profits = df["profit"].tolist()
        mc      = run_monte_carlo(profits, n_simulations=1000)

        issues = []
        if mc["ruin_rate"] >= 0.01:
            issues.append(f"ruin_rate={mc['ruin_rate']:.1%} >= 1%")
        if abs(mc["p95_max_dd"]) > 0.25:
            issues.append(f"p95 DD={mc['p95_max_dd']:.1%} > 25%")

        detail = (f"ruin={mc['ruin_rate']:.1%} "
                  f"p95_DD={mc['p95_max_dd']:.1%} "
                  f"median_DD={mc['median_max_dd']:.1%}")

        if issues:
            return CheckResult("P", "Monte Carlo", "FAIL",
                               f"{'; '.join(issues)} | {detail}")
        return CheckResult("P", "Monte Carlo", "PASS", detail)

    except Exception as e:
        return CheckResult("P", "Monte Carlo", "FAIL", str(e))


def check_Q_regime(trade_log_path: str | None,
                   price_csv: str | None) -> CheckResult:
    """Q: Regime test — ít nhất 2 regime, mỗi regime >= 30 trades, PF >= 0.8."""
    if not trade_log_path or not price_csv:
        return CheckResult("Q", "Regime Test", "SKIP",
                           "Cần --trade-log và --price-csv")

    try:
        from backtest.trade_log_parser import parse_trade_log
        from validator.monte_carlo import classify_regime, backtest_per_regime, check_regime_pass

        trade_df = parse_trade_log(trade_log_path)
        price_df = pd.read_csv(price_csv, parse_dates=["timestamp"])
        price_df = price_df.set_index("timestamp").sort_index()

        regime_results = backtest_per_regime(trade_df, price_df)
        passed, issues = check_regime_pass(regime_results)

        n_regimes = len(regime_results)
        detail = (f"{n_regimes} regimes: " +
                  ", ".join(f"{r}(n={v['trades']},PF={v.get('pf',0):.2f})"
                            for r, v in regime_results.items()))

        if not passed:
            return CheckResult("Q", "Regime Test", "FAIL",
                               "; ".join(issues) + " | " + detail)
        return CheckResult("Q", "Regime Test", "PASS", detail)

    except Exception as e:
        return CheckResult("Q", "Regime Test", "FAIL", str(e))


# ---------------------------------------------------------------------------
# Hard fail checks
# ---------------------------------------------------------------------------

HARD_FAIL_RULES = [
    ("SL bắt buộc trước entry",
     lambda s, _: not _file_contains(
         _strategy_dir(s) / "rule_spec.md", "sl", "stop loss")),
    ("Không có trade_log",
     lambda _, tl: tl is not None and not Path(tl).exists()),
    ("Không có OOS / Walk-forward",
     lambda s, _: not (_strategy_dir(s) / "optimization_space.yaml").exists()),
    ("Không có source cho hypothesis",
     lambda s, _: not (_file_contains(_strategy_dir(s) / "hypothesis.md", "source")
                       or _file_contains(_strategy_dir(s) / "hypothesis.md", "nguồn"))),
    ("Không có rule IF/THEN",
     lambda s, _: not _file_contains(
         _strategy_dir(s) / "rule_spec.md", "entry")),
]


def run_hard_fail_checks(strategy_name: str,
                         trade_log_path: str | None) -> list[str]:
    fails = []
    for label, fn in HARD_FAIL_RULES:
        try:
            if fn(strategy_name, trade_log_path):
                fails.append(label)
        except Exception:
            pass
    return fails


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_qa_gate(
    strategy_name: str,
    symbol:        str = "N/A",
    trade_log_path: str | None = None,
    price_csv:     str | None = None,
    wf_results:    list[dict] | None = None,
) -> QAReport:
    report = QAReport(strategy=strategy_name, symbol=symbol)

    # Load configs
    cfg = {}
    for name in ["risk", "strategies", "optimization"]:
        p = PROJECT_ROOT / "configs" / f"{name}.yaml"
        cfg[name] = _load_yaml(p)

    # Hard fails
    report.hard_fails = run_hard_fail_checks(strategy_name, trade_log_path)
    if report.hard_fails:
        for hf in report.hard_fails:
            log.error(f"[HARD FAIL] {hf}")

    # Quant metrics (nếu có trade log)
    metrics = {}
    if trade_log_path and Path(trade_log_path).exists():
        try:
            from backtest.trade_log_parser import parse_trade_log, compute_metrics
            df      = parse_trade_log(trade_log_path)
            metrics = compute_metrics(df)
            report.metrics = metrics
        except Exception as e:
            log.warning(f"Không compute metrics: {e}")

    # Run all checks
    report.add(check_A_strategy_rule(strategy_name))
    report.add(check_B_multi_timeframe(strategy_name))
    report.add(check_C_indicator(strategy_name))
    report.add(check_D_ea_architecture())
    report.add(check_E_backtest_data(trade_log_path))
    for r in check_F_quant_metrics(metrics):
        report.add(r)
    report.add(check_G_optimization(strategy_name))
    report.add(check_H_walk_forward(wf_results))
    report.add(check_I_risk(cfg))
    report.add(check_J_kelly(cfg))
    report.add(check_K_portfolio(cfg))
    report.add(check_L_ui_dashboard())
    report.add(check_M_chart_setup())
    report.add(check_N_logging())
    report.add(check_O_deployment())
    report.add(check_P_monte_carlo(trade_log_path))
    report.add(check_Q_regime(trade_log_path, price_csv))

    report.compute_verdict()
    return report


# ---------------------------------------------------------------------------
# Report renderer
# ---------------------------------------------------------------------------

def render_markdown(report: QAReport) -> str:
    ICONS = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌", "SKIP": "⬜"}

    rows = []
    for c in report.checks:
        rows.append(f"| {c.item} | {c.label} | {ICONS.get(c.status, c.status)} {c.status} | {c.detail} |")

    hard_fail_block = ""
    if report.hard_fails:
        hard_fail_block = "\n## ❌ Hard Fail Conditions\n\n" + \
            "\n".join(f"- {hf}" for hf in report.hard_fails) + "\n"

    metrics_block = ""
    if report.metrics:
        m = report.metrics
        metrics_block = f"""
## Quant Metrics

| Metric | Value |
|---|---|
| Total trades | {m.get('total_trades', 'N/A')} |
| Winrate | {m.get('winrate', 0):.1%} |
| Profit Factor | {m.get('profit_factor', 0):.2f} |
| Sharpe | {m.get('sharpe', 0):.2f} |
| Max DD (%) | {m.get('max_dd_pct', 0):.1%} |
| Expectancy | {m.get('expectancy', 0):.4f} |
"""

    verdict_icon = {"PASS": "✅", "CONDITIONAL_PASS": "⚠️", "FAIL": "❌"}.get(report.verdict, "")

    return f"""# QA Report — {report.strategy} / {report.symbol}

Generated: {report.generated}

## Verdict: {verdict_icon} {report.verdict}
{hard_fail_block}
## Checklist A → Q

| Item | Label | Status | Detail |
|---|---|---|---|
{chr(10).join(rows)}
{metrics_block}
## Required Actions

{"None — ready for demo." if report.verdict == VERDICT_PASS else ""}
{"Fix hard fails trước khi tiếp tục." if report.verdict == VERDICT_FAIL else ""}
{"Resolve WARNINGs trước khi demo." if report.verdict == VERDICT_CONDITIONAL_PASS else ""}
"""


def save_report(report: QAReport, strategy_name: str) -> Path:
    out_dir = PROJECT_ROOT / "strategies" / strategy_name
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "qa_report.md"
    path.write_text(render_markdown(report), encoding="utf-8")
    log.info(f"QA report saved: {path}")
    return path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MT5 QA Gate — checklist A-Q")
    parser.add_argument("--strategy",  required=True)
    parser.add_argument("--symbol",    default="N/A")
    parser.add_argument("--trade-log", dest="trade_log", default=None,
                        help="Path đến trade_log.csv (optional)")
    parser.add_argument("--price-csv", dest="price_csv", default=None,
                        help="Path đến OHLC CSV cho regime test (optional)")
    args = parser.parse_args()

    report = run_qa_gate(
        strategy_name  = args.strategy,
        symbol         = args.symbol,
        trade_log_path = args.trade_log,
        price_csv      = args.price_csv,
    )

    path = save_report(report, args.strategy)

    # Print summary
    ICON = {"PASS": "PASS", "CONDITIONAL_PASS": "COND", "FAIL": "FAIL"}
    print(f"\n{'='*55}")
    print(f" QA GATE — {report.strategy} / {report.symbol}")
    print(f" Verdict: {report.verdict}")
    print(f"{'='*55}")
    for c in report.checks:
        icon = {"PASS": "[OK]", "WARN": "[!!]", "FAIL": "[XX]", "SKIP": "[--]"}.get(c.status, "[ ]")
        detail = f" — {c.detail}" if c.detail else ""
        print(f" {icon} {c.item:2s} {c.label}{detail}")
    if report.hard_fails:
        print(f"\n HARD FAILS:")
        for hf in report.hard_fails:
            print(f"   [XX] {hf}")
    print(f"\n Report: {path}\n")
