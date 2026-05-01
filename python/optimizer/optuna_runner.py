"""
optuna_runner.py — Optuna-based parameter optimization.

Objective: sharpe_penalized = Sharpe * (1 - DD/max_dd) * log10(max(trades, 1))
Stability: plateau selection — best region, not best single point.

Usage:
    python optimizer/optuna_runner.py --strategy wyckoff --symbol XAUUSD
    python optimizer/optuna_runner.py --strategy wyckoff --symbol XAUUSD --trials 100
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np
import optuna
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "python"))

from backtest.trade_log_parser import compute_metrics, parse_trade_log
from backtest.tester_runner import MT5TesterRunner

optuna.logging.set_verbosity(optuna.logging.WARNING)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class TrialResult:
    trial_number: int
    params: dict
    metrics: dict
    objective: float
    rejected: bool
    reject_reason: str = ""


@dataclass
class OptimizationResult:
    strategy: str
    symbol: str
    best_params: dict
    best_objective: float
    best_metrics: dict
    n_trials: int
    n_completed: int
    n_rejected: int
    optimized_at: str
    stability_score: float = 0.0
    top_trials: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_opt_space(strategy_name: str) -> dict:
    path = PROJECT_ROOT / "strategies" / strategy_name / "optimization_space.yaml"
    if not path.exists():
        raise FileNotFoundError(f"optimization_space.yaml không tìm thấy: {path}")
    with open(path) as f:
        return yaml.safe_load(f)


def load_global_opt_config() -> dict:
    path = PROJECT_ROOT / "configs" / "optimization.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Objective function
# ---------------------------------------------------------------------------

def compute_sharpe_penalized(metrics: dict, max_dd_allowed: float = 0.15) -> float:
    """
    sharpe_penalized = Sharpe * (1 - DD/max_dd) * log10(max(trades, 1))
    """
    sharpe  = metrics.get("sharpe", 0.0)
    dd_pct  = abs(metrics.get("max_dd_pct", 0.0))
    trades  = max(metrics.get("total_trades", 0), 1)

    dd_penalty      = max(0.0, 1.0 - dd_pct / max_dd_allowed)
    trade_log_bonus = np.log10(trades)

    return float(sharpe * dd_penalty * trade_log_bonus)


def check_hard_reject(metrics: dict, reject_cfg: dict) -> tuple[bool, str]:
    """Return (rejected, reason). Nếu bất kỳ điều kiện nào vi phạm → reject."""
    checks = [
        (
            metrics.get("total_trades", 0) < reject_cfg.get("total_trades_lt", 0),
            f"trades={metrics.get('total_trades',0)} < {reject_cfg.get('total_trades_lt',0)}",
        ),
        (
            metrics.get("profit_factor", 0) < reject_cfg.get("profit_factor_lt", 0),
            f"PF={metrics.get('profit_factor',0):.2f} < {reject_cfg.get('profit_factor_lt',0)}",
        ),
        (
            abs(metrics.get("max_dd_pct", 1)) > reject_cfg.get("max_dd_gt", 1),
            f"DD={abs(metrics.get('max_dd_pct',0)):.1%} > {reject_cfg.get('max_dd_gt',0):.1%}",
        ),
        (
            metrics.get("sharpe", 0) < reject_cfg.get("sharpe_lt", 0),
            f"Sharpe={metrics.get('sharpe',0):.2f} < {reject_cfg.get('sharpe_lt',0)}",
        ),
        (
            metrics.get("expectancy", 0) <= reject_cfg.get("expectancy_lte", 0),
            f"Expectancy={metrics.get('expectancy',0):.4f} <= {reject_cfg.get('expectancy_lte',0)}",
        ),
    ]
    for violated, reason in checks:
        if violated:
            return True, reason
    return False, ""


# ---------------------------------------------------------------------------
# Param suggestion
# ---------------------------------------------------------------------------

def suggest_params(trial: optuna.Trial, param_specs: list[dict]) -> dict:
    """Map optimization_space.yaml param specs → Optuna suggestions."""
    params = {}
    for p in param_specs:
        name  = p["name"]
        ptype = p["type"]
        lo, hi = p["min"], p["max"]
        step   = p.get("step")

        if ptype == "int":
            params[name] = trial.suggest_int(name, lo, hi, step=step or 1)
        elif ptype == "float":
            if step:
                # Discretize: suggest int index then scale
                n_steps = round((hi - lo) / step)
                idx     = trial.suggest_int(f"{name}_idx", 0, n_steps)
                params[name] = round(lo + idx * step, 10)
            else:
                params[name] = trial.suggest_float(name, lo, hi)
        elif ptype == "categorical":
            params[name] = trial.suggest_categorical(name, p["choices"])
        else:
            raise ValueError(f"Param type không hỗ trợ: {ptype}")

    return params


# ---------------------------------------------------------------------------
# Plateau stability
# ---------------------------------------------------------------------------

def select_stable_params(
    trial_results: list[TrialResult],
    param_specs: list[dict],
    plateau_tolerance_pct: float = 10.0,
    top_n: int = 20,
) -> tuple[dict, float]:
    """
    Chọn vùng param ổn định thay vì chọn điểm cao nhất đơn lẻ.

    Thuật toán:
    1. Lấy top_n trials theo objective.
    2. Với mỗi trial, đếm bao nhiêu trial khác trong top_n có param
       lân cận ±plateau_tolerance_pct VÀ objective tương đương.
    3. Chọn trial có density cao nhất (ổn định nhất).

    Returns: (best_params, stability_score)
    """
    completed = [r for r in trial_results if not r.rejected and r.objective > -900]
    if not completed:
        return {}, 0.0

    completed.sort(key=lambda r: r.objective, reverse=True)
    top = completed[:top_n]

    if len(top) == 1:
        return top[0].params, 1.0

    # Normalize params to [0,1] for distance calc
    def normalize(params: dict) -> np.ndarray:
        vec = []
        for p in param_specs:
            val = params.get(p["name"], p.get("min", 0))
            lo, hi = float(p.get("min", 0)), float(p.get("max", 1))
            norm = (float(val) - lo) / (hi - lo + 1e-12)
            vec.append(norm)
        return np.array(vec)

    tol = plateau_tolerance_pct / 100.0
    best_trial, best_density = top[0], 0

    for candidate in top:
        c_vec  = normalize(candidate.params)
        density = sum(
            1 for other in top
            if np.all(np.abs(normalize(other.params) - c_vec) <= tol)
        )
        if density > best_density:
            best_density = density
            best_trial   = candidate

    stability_score = best_density / len(top)
    return best_trial.params, stability_score


# ---------------------------------------------------------------------------
# Core optimizer
# ---------------------------------------------------------------------------

class OptunaRunner:
    """
    Run Optuna optimization cho một strategy + symbol.

    backtest_fn: Callable[[dict], dict]
        Nhận params dict, trả về metrics dict (từ compute_metrics).
        Mặc định: dùng MT5TesterRunner.
    """

    def __init__(
        self,
        strategy_name: str,
        symbol: str,
        start_date: str,
        end_date: str,
        backtest_fn: Callable[[dict], dict] | None = None,
    ):
        self.strategy_name = strategy_name
        self.symbol        = symbol
        self.start_date    = start_date
        self.end_date      = end_date

        self.opt_space  = load_opt_space(strategy_name)
        self.global_cfg = load_global_opt_config()

        reject_cfg = self.opt_space.get(
            "reject_trial_if",
            self.global_cfg.get("reject_trial_if", {}),
        )
        self.reject_cfg  = reject_cfg
        self.param_specs = self.opt_space.get("parameters", [])
        self.max_dd_cfg  = reject_cfg.get("max_dd_gt", 0.15)

        self.backtest_fn = backtest_fn or self._default_backtest_fn
        self._trial_results: list[TrialResult] = []

    def _default_backtest_fn(self, params: dict) -> dict:
        """
        Gọi MT5TesterRunner với params và trả về metrics.
        Cần strategies/<name>/ea_params.yaml cho base config.
        """
        ea_params_path = PROJECT_ROOT / "strategies" / self.strategy_name / "ea_params.yaml"
        with open(ea_params_path) as f:
            base_cfg = yaml.safe_load(f)

        mt5_cfg = {
            "symbol":     self.symbol,
            "from_date":  self.start_date,
            "to_date":    self.end_date,
            "ea":         base_cfg.get("ea_file", f"PortfolioEA_{self.strategy_name}.ex5"),
            "params":     params,
            "period":     base_cfg.get("timeframes", {}).get("tf1", "H1"),
        }

        runner = MT5TesterRunner(PROJECT_ROOT)
        result = runner.run_backtest(mt5_cfg)

        if result.get("status") != "ok" or not result.get("trade_log"):
            return {}

        try:
            df = parse_trade_log(result["trade_log"])
            return compute_metrics(df)
        except Exception as e:
            log.debug(f"Parse metrics lỗi: {e}")
            return {}

    def _objective(self, trial: optuna.Trial) -> float:
        params  = suggest_params(trial, self.param_specs)
        metrics = {}
        try:
            metrics = self.backtest_fn(params)
        except Exception as e:
            log.debug(f"Trial {trial.number} backtest exception: {e}")

        if not metrics:
            self._trial_results.append(
                TrialResult(trial.number, params, {}, -999.0, True, "backtest failed")
            )
            return -999.0

        rejected, reason = check_hard_reject(metrics, self.reject_cfg)
        if rejected:
            self._trial_results.append(
                TrialResult(trial.number, params, metrics, -999.0, True, reason)
            )
            return -999.0

        obj = compute_sharpe_penalized(metrics, self.max_dd_cfg)
        self._trial_results.append(
            TrialResult(trial.number, params, metrics, obj, False)
        )
        return obj

    def run(
        self,
        n_trials: int | None = None,
        timeout_hours: float | None = None,
    ) -> OptimizationResult:
        gcfg    = self.global_cfg.get("optuna", {})
        n_trials     = n_trials or gcfg.get("n_trials", 200)
        timeout_secs = (timeout_hours or gcfg.get("timeout_hours", 4)) * 3600

        sampler_name = gcfg.get("sampler", "TPE")
        sampler = (
            optuna.samplers.CmaEsSampler() if sampler_name == "CmaEs"
            else optuna.samplers.RandomSampler() if sampler_name == "Random"
            else optuna.samplers.TPESampler(seed=42)
        )
        pruner = optuna.pruners.MedianPruner() \
            if gcfg.get("pruner") == "MedianPruner" \
            else optuna.pruners.NopPruner()

        study = optuna.create_study(
            direction="maximize",
            sampler=sampler,
            pruner=pruner,
        )

        log.info(
            f"[OPTIMIZER] Start — strategy={self.strategy_name} symbol={self.symbol} "
            f"trials={n_trials} timeout={timeout_hours or gcfg.get('timeout_hours',4)}h"
        )
        t0 = time.time()
        study.optimize(
            self._objective,
            n_trials=n_trials,
            timeout=timeout_secs,
            n_jobs=gcfg.get("n_jobs", 1),
            show_progress_bar=False,
        )
        elapsed = time.time() - t0

        completed = [r for r in self._trial_results if not r.rejected]
        rejected  = [r for r in self._trial_results if r.rejected]

        stab_cfg = self.opt_space.get("stability", {})
        plateau_tol = stab_cfg.get("plateau_tolerance_pct", 10.0)
        top_n       = stab_cfg.get("cluster_n", 5) * 4  # top_n = cluster_n * 4

        best_params, stability = select_stable_params(
            self._trial_results, self.param_specs, plateau_tol, top_n
        )

        # Lookup best metrics for chosen params
        best_tr = next(
            (r for r in completed if r.params == best_params),
            completed[0] if completed else None,
        )
        best_metrics  = best_tr.metrics if best_tr else {}
        best_obj      = best_tr.objective if best_tr else -999.0

        # Top-10 trials for report
        top_trials = sorted(
            [asdict(r) for r in completed],
            key=lambda x: x["objective"],
            reverse=True,
        )[:10]

        result = OptimizationResult(
            strategy       = self.strategy_name,
            symbol         = self.symbol,
            best_params    = best_params,
            best_objective = round(best_obj, 6),
            best_metrics   = best_metrics,
            n_trials       = len(self._trial_results),
            n_completed    = len(completed),
            n_rejected     = len(rejected),
            optimized_at   = datetime.now(timezone.utc).isoformat(),
            stability_score= round(stability, 4),
            top_trials     = top_trials,
        )

        log.info(
            f"[OPTIMIZER] Done — completed={len(completed)} rejected={len(rejected)} "
            f"elapsed={elapsed:.0f}s best_obj={best_obj:.4f} stability={stability:.2f}"
        )
        return result


# ---------------------------------------------------------------------------
# Persist results
# ---------------------------------------------------------------------------

def save_best_params(result: OptimizationResult, strategy_name: str) -> Path:
    out_dir = PROJECT_ROOT / "strategies" / strategy_name
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        **result.best_params,
        "optimized_at":  result.optimized_at,
        "best_objective": result.best_objective,
        "stability_score": result.stability_score,
        "n_trials":       result.n_trials,
        "n_completed":    result.n_completed,
        "symbol":         result.symbol,
    }
    path = out_dir / "best_params.json"
    path.write_text(json.dumps(payload, indent=2))
    log.info(f"[OPTIMIZER] best_params saved → {path}")
    return path


def save_optimization_report(result: OptimizationResult, strategy_name: str) -> Path:
    out_dir = PROJECT_ROOT / "strategies" / strategy_name
    out_dir.mkdir(parents=True, exist_ok=True)

    m = result.best_metrics
    rows = []
    for t in result.top_trials:
        rows.append({
            "trial":     t["trial_number"],
            "objective": round(t["objective"], 4),
            "winrate":   t["metrics"].get("winrate", ""),
            "PF":        t["metrics"].get("profit_factor", ""),
            "sharpe":    t["metrics"].get("sharpe", ""),
            "dd_pct":    t["metrics"].get("max_dd_pct", ""),
            "trades":    t["metrics"].get("total_trades", ""),
        })
    top_df = pd.DataFrame(rows)

    md = f"""# Optimization Report — {strategy_name} / {result.symbol}

Generated: {result.optimized_at}

## Summary

| Item | Value |
|---|---|
| Trials run | {result.n_trials} |
| Completed (pass) | {result.n_completed} |
| Rejected | {result.n_rejected} |
| Best objective | {result.best_objective:.4f} |
| Stability score | {result.stability_score:.2f} |

## Best Parameters

```json
{json.dumps(result.best_params, indent=2)}
```

## Best Metrics

| Metric | Value |
|---|---|
| Total trades | {m.get('total_trades', 'N/A')} |
| Winrate | {m.get('winrate', 0):.1%} |
| Profit Factor | {m.get('profit_factor', 0):.2f} |
| Sharpe | {m.get('sharpe', 0):.2f} |
| Max DD (%) | {m.get('max_dd_pct', 0):.1%} |
| Expectancy | {m.get('expectancy', 0):.4f} |

## Top 10 Trials

{top_df.to_markdown(index=False) if not top_df.empty else 'N/A'}
"""
    path = out_dir / "optimization_report.md"
    path.write_text(md)
    log.info(f"[OPTIMIZER] Report saved → {path}")
    return path


# ---------------------------------------------------------------------------
# Walk-forward integration
# ---------------------------------------------------------------------------

def run_wfo_optimization(
    strategy_name: str,
    symbol: str,
    full_start: str,
    full_end: str,
    backtest_fn: Callable[[dict, str, str], dict],
    n_trials_per_fold: int = 100,
) -> list[dict]:
    """
    Walk-forward optimization: tối ưu trên IS, validate trên OOS mỗi fold.

    backtest_fn(params, from_date, to_date) → metrics dict

    Returns list of fold results với IS/OOS metrics.
    """
    from backtest.walk_forward import generate_wf_folds

    opt_space = load_opt_space(strategy_name)
    wf_cfg    = opt_space.get("walk_forward", {})
    train_mo  = wf_cfg.get("train_months", 12)
    test_mo   = wf_cfg.get("test_months", 3)
    oos_pass  = wf_cfg.get("oos_pass_ratio", 0.5)

    folds     = generate_wf_folds(full_start, full_end, train_mo, test_mo)
    min_folds = wf_cfg.get("min_folds", 4)

    if len(folds) < min_folds:
        raise ValueError(
            f"Không đủ folds: {len(folds)} < {min_folds}. "
            f"Extend date range hoặc giảm min_folds."
        )

    fold_results = []

    for fold in folds:
        log.info(
            f"[WFO] Fold {fold.index}: IS={fold.train_from}→{fold.train_to} "
            f"OOS={fold.test_from}→{fold.test_to}"
        )

        def is_backtest_fn(params: dict) -> dict:
            return backtest_fn(params, fold.train_from, fold.train_to)

        runner = OptunaRunner(
            strategy_name=strategy_name,
            symbol=symbol,
            start_date=fold.train_from,
            end_date=fold.train_to,
            backtest_fn=is_backtest_fn,
        )
        is_result = runner.run(n_trials=n_trials_per_fold)

        oos_metrics = backtest_fn(is_result.best_params, fold.test_from, fold.test_to)

        is_obj  = is_result.best_objective
        oos_obj = compute_sharpe_penalized(
            oos_metrics, runner.max_dd_cfg
        ) if oos_metrics else -999.0

        oos_degradation = (
            (is_obj - oos_obj) / (abs(is_obj) + 1e-9)
            if is_obj > 0 else 1.0
        )

        max_deg = opt_space.get("walk_forward", {}).get(
            "oos_degradation_max",
            load_global_opt_config().get("walk_forward", {}).get("oos_degradation_max", 0.5),
        )
        passed = oos_degradation <= max_deg

        fold_results.append({
            "fold":             fold.index,
            "train_from":       fold.train_from,
            "train_to":         fold.train_to,
            "test_from":        fold.test_from,
            "test_to":          fold.test_to,
            "best_params":      is_result.best_params,
            "is_objective":     round(is_obj, 4),
            "oos_objective":    round(oos_obj, 4),
            "oos_degradation":  round(oos_degradation, 4),
            "oos_passed":       passed,
            "is_metrics":       is_result.best_metrics,
            "oos_metrics":      oos_metrics,
        })

    pass_ratio = sum(1 for f in fold_results if f["oos_passed"]) / len(fold_results)
    log.info(
        f"[WFO] Complete — {len(fold_results)} folds, "
        f"pass_ratio={pass_ratio:.0%} (need >={oos_pass:.0%})"
    )
    return fold_results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Optuna Optimizer for MT5 Strategies")
    parser.add_argument("--strategy", required=True, help="Tên strategy (vd: wyckoff)")
    parser.add_argument("--symbol",   required=True, help="Symbol (vd: XAUUSD)")
    parser.add_argument("--from",     dest="from_date", default="2020-01-01")
    parser.add_argument("--to",       dest="to_date",   default="2023-12-31")
    parser.add_argument("--trials",   type=int, default=None)
    parser.add_argument("--dry-run",  action="store_true",
                        help="Skip backtest, dùng random metrics để test pipeline")
    args = parser.parse_args()

    if args.dry_run:
        import random
        def dry_run_fn(params: dict) -> dict:
            return {
                "total_trades":  random.randint(100, 500),
                "winrate":       random.uniform(0.45, 0.65),
                "profit_factor": random.uniform(0.9, 2.0),
                "sharpe":        random.uniform(-0.5, 2.0),
                "max_dd_pct":    random.uniform(0.03, 0.20),
                "expectancy":    random.uniform(-0.1, 0.5),
            }
        backtest_fn = dry_run_fn
    else:
        backtest_fn = None  # dùng default MT5TesterRunner

    runner = OptunaRunner(
        strategy_name=args.strategy,
        symbol=args.symbol,
        start_date=args.from_date,
        end_date=args.to_date,
        backtest_fn=backtest_fn,
    )

    result = runner.run(n_trials=args.trials)
    save_best_params(result, args.strategy)
    save_optimization_report(result, args.strategy)

    print(f"\nBest objective : {result.best_objective:.4f}")
    print(f"Stability score: {result.stability_score:.2f}")
    print(f"Best params    : {json.dumps(result.best_params, indent=2)}")
