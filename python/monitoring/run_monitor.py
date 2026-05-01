"""
run_monitor.py — Daily Monitoring Agent.

So sánh live/demo performance vs OOS benchmark.
Phát hiện decay, trigger action (giảm risk / pause / alert).

Usage:
    python monitoring/run_monitor.py --strategy wyckoff
    python monitoring/run_monitor.py --strategy wyckoff --resume
"""

import argparse
import json
import logging
import sys
import yaml
import pandas as pd
from datetime import datetime, date
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "python"))

from backtest.trade_log_parser import parse_trade_log, compute_metrics
from monitoring.alert import send_alert, SEVERITY_WARNING, SEVERITY_RISK, SEVERITY_CRITICAL, SEVERITY_NORMAL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(PROJECT_ROOT / "logs" / "monitor.log"),
    ]
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_risk_config() -> dict:
    with open(PROJECT_ROOT / "configs" / "risk.yaml") as f:
        return yaml.safe_load(f)


def load_oos_benchmark(strategy_name: str) -> dict:
    """Đọc OOS metrics từ strategies/<name>/metrics.csv hoặc validation_report.md."""
    metrics_csv = PROJECT_ROOT / "strategies" / strategy_name / "metrics.csv"
    if metrics_csv.exists():
        df = pd.read_csv(metrics_csv)
        if "type" in df.columns:
            oos_rows = df[df["type"] == "OOS"]
            if not oos_rows.empty:
                row = oos_rows.iloc[-1]
                return {
                    "winrate":       float(row.get("winrate", 0)),
                    "profit_factor": float(row.get("profit_factor", 1)),
                    "expectancy":    float(row.get("expectancy", 0)),
                }

    # Fallback: đọc từ metrics.csv không phân loại IS/OOS
    if metrics_csv.exists():
        df = pd.read_csv(metrics_csv)
        if not df.empty:
            row = df.iloc[-1]
            return {
                "winrate":       float(row.get("winrate", 0)),
                "profit_factor": float(row.get("profit_factor", 1)),
                "expectancy":    float(row.get("expectancy", 0)),
            }

    log.warning(f"OOS benchmark không tìm thấy cho {strategy_name} — dùng defaults")
    return {"winrate": 0.5, "profit_factor": 1.2, "expectancy": 0.1}


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def rolling_metrics(df: pd.DataFrame, window: int = 50) -> dict:
    recent = df.tail(window)
    if len(recent) == 0:
        return {"window": window, "trades": 0, "winrate": 0, "expectancy": 0, "profit_factor": 0}
    return {**compute_metrics(recent), "window": window, "trades": len(recent)}


def current_dd(df: pd.DataFrame) -> float:
    """Max drawdown hiện tại tính từ peak equity (%)."""
    if df.empty:
        return 0.0
    equity = df["profit"].cumsum()
    peak   = equity.cummax()
    dd     = (equity - peak) / (peak.abs().replace(0, 1e-9))
    return float(abs(dd.iloc[-1]) * 100)


def decay_check(live: dict, oos: dict, cfg: dict) -> tuple[str, dict]:
    """
    So sánh live vs OOS. Trả về (severity, detail_dict).
    """
    mon = cfg.get("monitoring", {})
    warn_wr  = mon.get("decay_warning_winrate_drop",  0.08)
    crit_wr  = mon.get("decay_critical_winrate_drop", 0.15)
    warn_pf  = mon.get("decay_warning_pf_drop",       0.25)
    crit_pf  = mon.get("decay_critical_pf",           0.75)

    wr_drop = oos["winrate"]       - live.get("winrate", 0)
    pf_drop = oos["profit_factor"] - live.get("profit_factor", 0)
    exp_val = live.get("expectancy", 0)

    detail = {
        "oos_winrate": oos["winrate"],
        "live_winrate": live.get("winrate", 0),
        "winrate_drop": wr_drop,
        "oos_pf":       oos["profit_factor"],
        "live_pf":      live.get("profit_factor", 0),
        "pf_drop":      pf_drop,
        "expectancy":   exp_val,
    }

    if wr_drop > crit_wr or live.get("profit_factor", 1) < crit_pf or exp_val <= 0:
        return SEVERITY_CRITICAL, detail
    if wr_drop > warn_wr or pf_drop > warn_pf:
        return SEVERITY_WARNING, detail
    return SEVERITY_NORMAL, detail


def check_param_expiry(strategy_name: str, max_months: int = 6) -> bool:
    params_path = PROJECT_ROOT / "strategies" / strategy_name / "best_params.json"
    if not params_path.exists():
        return False   # belum dioptimize, bukan expired
    try:
        data = json.loads(params_path.read_text())
        optimized_at = datetime.fromisoformat(
            data.get("optimized_at", "2000-01-01")
        )
        age_months = (datetime.utcnow() - optimized_at).days / 30
        return age_months > max_months
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def pause_via_gv(strategy_name: str, magic_base: int, reason: str):
    """
    Set KILL switch via MT5 Global Variable.
    Cần MT5 đang chạy và connector.
    """
    try:
        from mt5_interface.connector import get_connector
        import yaml as _yaml
        with open(PROJECT_ROOT / "configs" / "mt5_paths.yaml") as f:
            paths = _yaml.safe_load(f)
        with get_connector(paths) as conn:
            key = f"QT_{magic_base}_KILL"
            conn.gv_set(key, 1.0)
            log.critical(f"[MONITOR] KILL switch set: {key} = 1.0 | reason: {reason}")
    except Exception as e:
        log.error(f"[MONITOR] Không set KILL switch (MT5 không connect): {e}")
        log.critical(f"[MONITOR] Manual action required: pause {strategy_name}")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def append_report(row: dict, log_dir: Path):
    log_dir.mkdir(exist_ok=True)
    report_path = log_dir / "monitoring_report.csv"
    header = not report_path.exists()
    pd.DataFrame([row]).to_csv(report_path, mode="a", header=header, index=False)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_monitoring(strategy_name: str):
    log.info(f"[MONITOR] Start — strategy={strategy_name}")
    cfg      = load_risk_config()
    mon_cfg  = cfg.get("monitoring", {})
    log_dir  = PROJECT_ROOT / "logs"

    # 1. Load live trade log
    log_path = log_dir / "trade_log.csv"
    if not log_path.exists():
        send_alert(SEVERITY_WARNING, strategy_name,
                   "trade_log.csv không tìm thấy", str(log_dir))
        return

    try:
        df_all = parse_trade_log(str(log_path))
    except Exception as e:
        send_alert(SEVERITY_RISK, strategy_name, f"Parse trade log lỗi: {e}", str(log_dir))
        return

    df = df_all[df_all["strategy"].str.lower() == strategy_name.lower()] \
         if "strategy" in df_all.columns else df_all

    min_trades = 20
    if len(df) < min_trades:
        send_alert(SEVERITY_NORMAL, strategy_name,
                   f"Chưa đủ data: {len(df)} trades (cần >= {min_trades})", str(log_dir))
        return

    # 2. Rolling metrics
    window      = mon_cfg.get("rolling_window_trades", 50)
    live_mets   = rolling_metrics(df, window)
    dd_now      = current_dd(df)

    # 3. OOS benchmark
    oos_bench   = load_oos_benchmark(strategy_name)

    # 4. Decay check
    severity, detail = decay_check(live_mets, oos_bench, cfg)

    # 5. DD override
    if dd_now > cfg.get("drawdown", {}).get("max_account_dd_pct", 6.0):
        severity = SEVERITY_CRITICAL
        detail["dd_breach"] = dd_now

    # 6. Param expiry check
    max_months = mon_cfg.get("param_expiry_months", 6)
    if check_param_expiry(strategy_name, max_months):
        send_alert(SEVERITY_WARNING, strategy_name,
                   f"Params đã quá {max_months} tháng — cần re-optimize", str(log_dir))

    # 7. Build message
    msg = (
        f"WR={live_mets.get('winrate', 0):.1%} "
        f"(OOS={oos_bench['winrate']:.1%}) | "
        f"PF={live_mets.get('profit_factor', 0):.2f} "
        f"(OOS={oos_bench['profit_factor']:.2f}) | "
        f"DD={dd_now:.1f}% | trades={live_mets['trades']}"
    )
    send_alert(severity, strategy_name, msg, str(log_dir))

    # 8. Action on CRITICAL
    if severity == SEVERITY_CRITICAL:
        magic_base = cfg.get("magic_base", 20260501)
        pause_via_gv(strategy_name, magic_base, msg)

    # 9. Write report row
    row = {
        "timestamp":    datetime.utcnow().isoformat(),
        "strategy":     strategy_name,
        "severity":     severity,
        "live_trades":  live_mets.get("total_trades", 0),
        "live_winrate": round(live_mets.get("winrate", 0), 4),
        "live_pf":      round(live_mets.get("profit_factor", 0), 4),
        "oos_winrate":  round(oos_bench["winrate"], 4),
        "oos_pf":       round(oos_bench["profit_factor"], 4),
        "current_dd":   round(dd_now, 4),
    }
    append_report(row, log_dir)
    log.info(f"[MONITOR] Done — severity={severity}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MT5 Monitoring Agent")
    parser.add_argument("--strategy", required=True, help="Tên strategy (vd: wyckoff)")
    args = parser.parse_args()

    logging.getLogger().handlers[1].baseFilename  # ensure log dir exists
    run_monitoring(args.strategy)
