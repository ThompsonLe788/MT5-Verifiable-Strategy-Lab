"""
monte_carlo.py — Monte Carlo simulation + Regime detector.

Chi tiết spec: docs/QA_GATE.md section 10–11
"""

import logging
import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Monte Carlo
# ---------------------------------------------------------------------------

def run_monte_carlo(
    profits: list[float],
    n_simulations: int = 1000,
    initial_capital: float = 10000.0,
    ruin_threshold: float = 0.5,   # mất > 50% vốn = ruin
) -> dict:
    """
    Shuffle thứ tự trades N lần, tính distribution của max DD và final equity.

    Args:
        profits:          list profit/loss mỗi trade ($)
        n_simulations:    số lần shuffle (default 1000)
        initial_capital:  vốn ban đầu
        ruin_threshold:   tỷ lệ vốn mất để coi là ruin (default 0.5 = 50%)

    Returns dict:
        median_max_dd:   trung vị max DD (%) — âm
        p95_max_dd:      percentile 95 max DD (%) — âm
        ruin_rate:       tỷ lệ simulation bị ruin
        median_final:    trung vị equity cuối
        p5_final:        percentile 5 equity cuối (worst case)
        n_simulations:   số sim đã chạy
    """
    if len(profits) < 10:
        log.warning("Monte Carlo: quá ít trades để simulate meaningfully")
        return {
            "median_max_dd": 0.0, "p95_max_dd": 0.0,
            "ruin_rate": 0.0, "median_final": initial_capital,
            "p5_final": initial_capital, "n_simulations": 0,
        }

    arr = np.array(profits, dtype=float)
    ruin_level = initial_capital * (1 - ruin_threshold)

    max_dds   = np.empty(n_simulations)
    finals    = np.empty(n_simulations)
    ruins     = np.empty(n_simulations, dtype=bool)

    rng = np.random.default_rng()

    for i in range(n_simulations):
        shuffled  = rng.permutation(arr)
        equity    = initial_capital + np.cumsum(shuffled)
        peak      = np.maximum.accumulate(equity)
        dd_pct    = (equity - peak) / (peak + 1e-9)

        max_dds[i] = float(dd_pct.min())
        finals[i]  = float(equity[-1])
        ruins[i]   = bool(equity.min() < ruin_level)

    result = {
        "median_max_dd":  float(np.median(max_dds)),
        "p95_max_dd":     float(np.percentile(max_dds, 5)),   # worst 5%
        "ruin_rate":      float(ruins.mean()),
        "median_final":   float(np.median(finals)),
        "p5_final":       float(np.percentile(finals, 5)),
        "n_simulations":  n_simulations,
    }

    log.info(
        f"Monte Carlo ({n_simulations} sim): "
        f"median_DD={result['median_max_dd']:.1%}, "
        f"p95_DD={result['p95_max_dd']:.1%}, "
        f"ruin={result['ruin_rate']:.1%}"
    )
    return result


def check_monte_carlo_pass(mc: dict) -> tuple[bool, list[str]]:
    """
    Kiểm tra kết quả Monte Carlo theo QA_GATE thresholds.

    Returns (passed: bool, failures: list[str])
    """
    failures = []
    if mc.get("ruin_rate", 1.0) >= 0.01:
        failures.append(
            f"Ruin rate={mc['ruin_rate']:.1%} >= 1% threshold"
        )
    if abs(mc.get("p95_max_dd", -1.0)) > 0.25:
        failures.append(
            f"p95 max DD={mc['p95_max_dd']:.1%} < -25% threshold"
        )
    return len(failures) == 0, failures


# ---------------------------------------------------------------------------
# Sensitivity test
# ---------------------------------------------------------------------------

def sensitivity_spread(
    profits: list[float],
    spread_cost_per_trade: float,
    spread_multiplier: float = 1.5,
) -> dict:
    """
    Kiểm tra strategy nếu spread tăng thêm X lần.

    Args:
        spread_cost_per_trade: chi phí spread trung bình mỗi trade ($)
        spread_multiplier:     hệ số tăng (1.5 = tăng 50%)

    Returns dict: expectancy_original, expectancy_stressed, drop_pct
    """
    arr      = np.array(profits)
    extra    = spread_cost_per_trade * (spread_multiplier - 1.0)
    stressed = arr - extra

    exp_orig     = float(arr.mean())
    exp_stressed = float(stressed.mean())
    drop_pct     = (exp_orig - exp_stressed) / (abs(exp_orig) + 1e-9)

    return {
        "expectancy_original": round(exp_orig, 4),
        "expectancy_stressed": round(exp_stressed, 4),
        "drop_pct":            round(drop_pct, 4),
        "spread_multiplier":   spread_multiplier,
    }


# ---------------------------------------------------------------------------
# Regime detector
# ---------------------------------------------------------------------------

def classify_regime(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """
    Phân loại market regime cho từng bar.

    Requires columns: close, high, low
    Returns Series với values: TREND_UP | TREND_DOWN | RANGING | HIGH_VOL

    Phương pháp đơn giản (không cần ADX thực sự):
    - ROC (rate of change) để xác định trend
    - ATR tương đối để xác định volatility
    """
    if not {"close", "high", "low"}.issubset(df.columns):
        raise ValueError("DataFrame cần có cột: close, high, low")

    close = df["close"]
    high  = df["high"]
    low   = df["low"]

    atr   = (high - low).rolling(14).mean()
    atr_ma = atr.rolling(50).mean()
    roc   = close.pct_change(window)

    regime = pd.Series("RANGING", index=df.index, name="regime")

    # HIGH_VOL: ATR hiện tại vượt 1.5x ATR MA
    high_vol_mask = atr > (atr_ma * 1.5)
    regime[high_vol_mask] = "HIGH_VOL"

    # TREND (không override HIGH_VOL)
    trend_up   = (~high_vol_mask) & (roc > 0.03)
    trend_down = (~high_vol_mask) & (roc < -0.03)
    regime[trend_up]   = "TREND_UP"
    regime[trend_down] = "TREND_DOWN"

    return regime


def backtest_per_regime(
    trade_log: pd.DataFrame,
    price_df: pd.DataFrame,
    window: int = 20,
) -> dict[str, dict]:
    """
    Tính metrics cho từng market regime.

    Args:
        trade_log: DataFrame từ parse_trade_log()
        price_df:  OHLCV DataFrame với DatetimeIndex hoặc cột 'timestamp'
        window:    lookback cho regime classification

    Returns:
        dict regime_name → metrics dict
    """
    # Setup price index
    pdf = price_df.copy()
    if "timestamp" in pdf.columns:
        pdf = pdf.set_index("timestamp")
    pdf.index = pd.to_datetime(pdf.index)
    pdf = pdf.sort_index()

    regimes = classify_regime(pdf, window=window)

    # Map mỗi trade → regime tại thời điểm entry
    tl = trade_log.copy()
    tl["timestamp"] = pd.to_datetime(tl["timestamp"])

    def get_regime(ts):
        try:
            return regimes.asof(ts)
        except Exception:
            return "UNKNOWN"

    tl["regime"] = tl["timestamp"].apply(get_regime)

    # Tính metrics mỗi regime
    results = {}
    for regime_name, grp in tl.groupby("regime"):
        n    = len(grp)
        wins = grp[grp["profit"] > 0]
        loss = grp[grp["profit"] <= 0]

        winrate = len(wins) / n if n > 0 else 0
        pf = (
            wins["profit"].sum() / abs(loss["profit"].sum())
            if len(loss) > 0 and loss["profit"].sum() != 0
            else float("inf")
        )

        results[regime_name] = {
            "trades":  n,
            "winrate": round(winrate, 4),
            "pf":      round(float(pf), 4),
        }

    log.info(f"Regime breakdown: {list(results.keys())}")
    return results


def check_regime_pass(regime_results: dict[str, dict]) -> tuple[bool, list[str]]:
    """
    Kiểm tra regime test theo QA_GATE thresholds.

    PASS nếu:
      - Ít nhất 2 regime có >= 30 trades
      - Không có regime nào PF < 0.8
    """
    failures = []
    qualified = {k: v for k, v in regime_results.items() if v["trades"] >= 30}

    if len(qualified) < 2:
        failures.append(
            f"Chỉ {len(qualified)} regime có >= 30 trades "
            f"(cần ít nhất 2). Regimes: {list(regime_results.keys())}"
        )

    for regime, m in qualified.items():
        if m["pf"] < 0.8:
            failures.append(
                f"Regime {regime}: PF={m['pf']:.2f} < 0.8 threshold"
            )

    return len(failures) == 0, failures
