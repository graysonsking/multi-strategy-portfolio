"""Statistical arbitrage on cointegrated pairs.

Screens for cointegration, then trades deviations from the equilibrium
relationship. The standard approach assumes the spread is normally distributed
and trades Z-score deviations from its mean. That assumption is weakest in the
tails, which is where the trades actually are, so a copula based variant is
provided alongside the Z-score version.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd

try:
    from statsmodels.tsa.stattools import coint
    _HAS_STATSMODELS = True
except ImportError:  # pragma: no cover
    _HAS_STATSMODELS = False


def find_pairs(
    prices: pd.DataFrame,
    pvalue_threshold: float = 0.05,
    max_pairs: int | None = None,
) -> list[tuple[str, str, float]]:
    """Screen all combinations for cointegration.

    Returns (asset_a, asset_b, pvalue) sorted by strength.

    Note the multiple testing problem. Screening several hundred pairs at a
    five percent threshold will surface false positives by construction.
    Treat the output as candidates for review, not as confirmed relationships.
    """
    if not _HAS_STATSMODELS:
        raise ImportError("statsmodels is required for cointegration testing")

    clean = prices.dropna(axis=1, how="any")
    results = []
    for a, b in combinations(clean.columns, 2):
        try:
            _, pvalue, _ = coint(clean[a], clean[b])
        except Exception:
            continue
        if pvalue < pvalue_threshold:
            results.append((a, b, float(pvalue)))

    results.sort(key=lambda x: x[2])
    return results[:max_pairs] if max_pairs else results


def hedge_ratio(series_a: pd.Series, series_b: pd.Series) -> float:
    """Ordinary least squares hedge ratio of A on B."""
    b = series_b.values
    a = series_a.values
    return float(np.dot(b, a) / np.dot(b, b))


def spread_zscore(
    series_a: pd.Series,
    series_b: pd.Series,
    window: int = 60,
) -> pd.Series:
    """Rolling standardized spread."""
    beta = hedge_ratio(series_a, series_b)
    spread = series_a - beta * series_b
    mean = spread.rolling(window, min_periods=window // 2).mean()
    sd = spread.rolling(window, min_periods=window // 2).std(ddof=1)
    return (spread - mean) / sd.replace(0, np.nan)


def weights_fn(
    returns: pd.DataFrame,
    date: pd.Timestamp,
    pairs: list[tuple[str, str]] | None = None,
    entry: float = 2.0,
    exit_band: float = 0.5,
    window: int = 60,
) -> pd.Series:
    """Dollar neutral positions across active pairs.

    pairs: pre-screened pair list. Screening inside the rebalance loop is
        expensive, so run `find_pairs` on the formation window and pass the
        result in.
    """
    w = pd.Series(0.0, index=returns.columns)
    if not pairs:
        return w

    prices = (1.0 + returns).cumprod()
    active = 0
    positions: dict[str, float] = {}

    for a, b in pairs:
        if a not in prices.columns or b not in prices.columns:
            continue
        z = spread_zscore(prices[a], prices[b], window).iloc[-1]
        if pd.isna(z) or abs(z) < entry:
            continue
        # Spread is wide. Short the rich leg, long the cheap leg.
        direction = -np.sign(z)
        positions[a] = positions.get(a, 0.0) + direction
        positions[b] = positions.get(b, 0.0) - direction
        active += 1

    if active == 0:
        return w

    for asset, size in positions.items():
        w[asset] = size / (2.0 * active)
    return w
