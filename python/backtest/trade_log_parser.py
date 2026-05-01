"""
trade_log_parser.py — Parse và validate trade_log.csv từ EA/backtest.

CSV schema (export từ EA OnTester hoặc live logging):
  timestamp, symbol, strategy, direction, entry, sl, tp, exit,
  profit, r_multiple, commission, swap, spread
"""

import logging
import pandas as pd
import numpy as np
from pathlib import Path

log = logging.getLogger(__name__)

REQUIRED_COLUMNS = {
    "timestamp", "symbol", "strategy", "direction",
    "entry", "sl", "tp", "exit", "profit",
}

OPTIONAL_COLUMNS = {
    "r_multiple", "commission", "swap", "spread",
}

ALL_COLUMNS = REQUIRED_COLUMNS | OPTIONAL_COLUMNS


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_trade_log(csv_path: str) -> pd.DataFrame:
    """
    Đọc trade_log.csv và trả về DataFrame đã validate.

    Raises:
        FileNotFoundError: file không tồn tại
        ValueError: thiếu cột bắt buộc
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"trade_log không tìm thấy: {path}")

    df = pd.read_csv(path)

    # Normalize column names
    df.columns = [c.strip().lower() for c in df.columns]

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"trade_log thiếu cột bắt buộc: {sorted(missing)}\n"
            f"Columns hiện tại: {list(df.columns)}"
        )

    # Parse timestamp
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"])

    # Numeric columns
    for col in ["entry", "sl", "tp", "exit", "profit"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in ["r_multiple", "commission", "swap", "spread"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # Drop rows thiếu data thiết yếu
    before = len(df)
    df = df.dropna(subset=["entry", "exit", "profit"])
    dropped = before - len(df)
    if dropped > 0:
        log.warning(f"Dropped {dropped} rows với missing entry/exit/profit")

    df = df.sort_values("timestamp").reset_index(drop=True)
    log.info(f"Parsed {len(df)} trades từ {path.name}")
    return df


def validate_sample_size(df: pd.DataFrame, min_trades: int = 200) -> bool:
    ok = len(df) >= min_trades
    if not ok:
        log.warning(f"Sample quá ít: {len(df)} trades (cần >= {min_trades})")
    return ok


# ---------------------------------------------------------------------------
# Quant metrics
# ---------------------------------------------------------------------------

def compute_metrics(df: pd.DataFrame) -> dict:
    """
    Tính toàn bộ quant metrics từ trade log.

    Returns dict với:
        total_trades, winrate, avg_win, avg_loss, expectancy,
        profit_factor, max_dd, sharpe, recovery_factor,
        avg_r_multiple (nếu có cột r_multiple)
    """
    if df.empty:
        return {}

    wins   = df[df["profit"] > 0]["profit"]
    losses = df[df["profit"] <= 0]["profit"]

    total    = len(df)
    winrate  = len(wins) / total
    avg_win  = float(wins.mean()) if len(wins) > 0 else 0.0
    avg_loss = float(losses.mean()) if len(losses) > 0 else 0.0  # âm

    gross_profit = float(wins.sum())
    gross_loss   = abs(float(losses.sum()))

    expectancy   = winrate * avg_win + (1 - winrate) * avg_loss
    pf           = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Equity curve & drawdown
    equity   = df["profit"].cumsum()
    peak     = equity.cummax()
    dd_curve = equity - peak
    max_dd   = float(dd_curve.min())          # âm, tính theo $
    max_dd_pct = max_dd / (peak.max() + 1e-9)  # tính theo %

    # Sharpe (annualized, giả sử 252 ngày giao dịch/năm)
    daily = df.set_index("timestamp")["profit"].resample("D").sum()
    sharpe = (
        daily.mean() / (daily.std() + 1e-9) * (252 ** 0.5)
        if len(daily) > 1 else 0.0
    )

    # Recovery factor = gross profit / abs(max_dd $)
    recovery = gross_profit / abs(max_dd) if max_dd != 0 else float("inf")

    result = {
        "total_trades":   total,
        "winrate":        round(winrate, 4),
        "avg_win":        round(avg_win, 4),
        "avg_loss":       round(avg_loss, 4),
        "expectancy":     round(expectancy, 4),
        "profit_factor":  round(pf, 4),
        "gross_profit":   round(gross_profit, 2),
        "gross_loss":     round(gross_loss, 2),
        "max_dd_dollar":  round(max_dd, 2),
        "max_dd_pct":     round(max_dd_pct, 4),
        "sharpe":         round(float(sharpe), 4),
        "recovery_factor":round(recovery, 4),
    }

    if "r_multiple" in df.columns:
        result["avg_r_multiple"] = round(float(df["r_multiple"].mean()), 4)

    return result


def monthly_returns(df: pd.DataFrame) -> pd.DataFrame:
    """Tính lợi nhuận theo từng tháng."""
    return (
        df.set_index("timestamp")["profit"]
        .resample("ME")
        .sum()
        .rename("monthly_profit")
        .reset_index()
    )


def per_strategy_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Tính metrics theo từng strategy nếu có cột 'strategy'."""
    if "strategy" not in df.columns:
        return pd.DataFrame()
    rows = []
    for name, grp in df.groupby("strategy"):
        m = compute_metrics(grp)
        m["strategy"] = name
        rows.append(m)
    return pd.DataFrame(rows)


def per_symbol_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Tính metrics theo từng symbol."""
    if "symbol" not in df.columns:
        return pd.DataFrame()
    rows = []
    for sym, grp in df.groupby("symbol"):
        m = compute_metrics(grp)
        m["symbol"] = sym
        rows.append(m)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Report export
# ---------------------------------------------------------------------------

def export_report(df: pd.DataFrame, output_dir: str = "logs") -> dict[str, str]:
    """
    Xuất metrics ra CSV và Markdown.

    Returns dict filename → path
    """
    out = Path(output_dir)
    out.mkdir(exist_ok=True)

    metrics  = compute_metrics(df)
    monthly  = monthly_returns(df)
    per_strat = per_strategy_metrics(df)
    per_sym  = per_symbol_metrics(df)

    files = {}

    # Metrics CSV
    metrics_path = out / "metrics.csv"
    pd.DataFrame([metrics]).to_csv(metrics_path, index=False)
    files["metrics"] = str(metrics_path)

    # Monthly CSV
    monthly_path = out / "monthly_returns.csv"
    monthly.to_csv(monthly_path, index=False)
    files["monthly"] = str(monthly_path)

    # Per-strategy
    if not per_strat.empty:
        p = out / "strategy_metrics.csv"
        per_strat.to_csv(p, index=False)
        files["strategy_metrics"] = str(p)

    # Per-symbol
    if not per_sym.empty:
        p = out / "symbol_metrics.csv"
        per_sym.to_csv(p, index=False)
        files["symbol_metrics"] = str(p)

    # Markdown summary
    md = _build_markdown(metrics, monthly)
    md_path = out / "validation_report.md"
    md_path.write_text(md)
    files["report"] = str(md_path)

    log.info(f"Report exported: {list(files.values())}")
    return files


def _build_markdown(metrics: dict, monthly: pd.DataFrame) -> str:
    return f"""# Validation Report

## Summary Metrics

| Metric | Value |
|---|---|
| Total trades | {metrics.get('total_trades', 'N/A')} |
| Winrate | {metrics.get('winrate', 0):.1%} |
| Avg win | {metrics.get('avg_win', 0):.4f} |
| Avg loss | {metrics.get('avg_loss', 0):.4f} |
| Expectancy | {metrics.get('expectancy', 0):.4f} |
| Profit Factor | {metrics.get('profit_factor', 0):.2f} |
| Max DD ($) | {metrics.get('max_dd_dollar', 0):.2f} |
| Max DD (%) | {metrics.get('max_dd_pct', 0):.1%} |
| Sharpe | {metrics.get('sharpe', 0):.2f} |
| Recovery Factor | {metrics.get('recovery_factor', 0):.2f} |

## Monthly Returns

{monthly.to_markdown(index=False) if not monthly.empty else 'N/A'}
"""
