"""Macro tilted allocation.

Standardizes macroeconomic indicators into Z-scores, maps them onto asset
class exposures, and tilts a baseline allocation toward the assets favored by
the current macro regime.

Macro data is revised after publication. Using the current vintage of a series
across a historical backtest hands the model information it could not have had
at the time. Where vintage data is available it should be used. Where it is
not, lag the series by its typical publication delay. `PUBLICATION_LAG` below
holds those defaults.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Months of delay between the reference period and first publication.
PUBLICATION_LAG = {
    "INDPRO": 1,
    "CPIAUCSL": 1,
    "UNRATE": 1,
    "T10Y2Y": 0,
    "DTWEXBGS": 0,
}

# Sign of each asset class response to a positive move in the indicator.
EXPOSURE_MAP = {
    "growth": {"equity": 1.0, "credit": 0.5, "treasury": -0.5, "commodity": 0.5},
    "inflation": {"equity": -0.3, "credit": -0.3, "treasury": -1.0, "commodity": 1.0},
    "rates": {"equity": -0.5, "credit": -0.5, "treasury": -1.0, "commodity": -0.3},
    "dollar": {"equity": -0.2, "credit": 0.0, "treasury": 0.3, "commodity": -1.0},
}


def rolling_zscore(series: pd.Series, window: int = 60) -> pd.Series:
    """Point-in-time standardization against trailing history.

    A full sample Z-score would use the mean and standard deviation of the
    entire period, including the future. This uses a trailing window only.
    """
    mean = series.rolling(window, min_periods=window // 2).mean()
    sd = series.rolling(window, min_periods=window // 2).std(ddof=1)
    return (series - mean) / sd.replace(0, np.nan)


def composite_score(
    macro_data: pd.DataFrame,
    date: pd.Timestamp,
    window: int = 60,
) -> pd.Series:
    """Composite macro score per asset class as of `date`."""
    history = macro_data.loc[macro_data.index < date]
    if history.empty:
        return pd.Series(dtype=float)

    z = history.apply(rolling_zscore, window=window).iloc[-1]

    scores: dict[str, float] = {}
    for factor, exposures in EXPOSURE_MAP.items():
        if factor not in z.index or pd.isna(z[factor]):
            continue
        for asset, sign in exposures.items():
            scores[asset] = scores.get(asset, 0.0) + sign * z[factor]
    return pd.Series(scores)


def weights_fn(
    returns: pd.DataFrame,
    date: pd.Timestamp,
    macro_data: pd.DataFrame | None = None,
    baseline: pd.Series | None = None,
    tilt: float = 0.25,
    window: int = 60,
) -> pd.Series:
    """Tilt a baseline allocation by the macro composite score.

    macro_data: DataFrame of macro indicators indexed by date, with columns
        matching the keys of EXPOSURE_MAP. Must already be lagged for
        publication delay.
    baseline: starting allocation. Defaults to equal weight.
    tilt: maximum fractional deviation from baseline.
    """
    assets = returns.columns
    base = baseline.reindex(assets).fillna(0.0) if baseline is not None else pd.Series(
        1.0 / len(assets), index=assets
    )

    if macro_data is None:
        return base

    scores = composite_score(macro_data, date, window).reindex(assets).fillna(0.0)
    spread = scores.abs().max()
    if not spread or np.isnan(spread):
        return base

    adjusted = base * (1.0 + tilt * scores / spread)
    adjusted = adjusted.clip(lower=0.0)
    total = adjusted.sum()
    return adjusted / total if total else base
