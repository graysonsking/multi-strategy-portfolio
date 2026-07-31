"""Sector rotation.

Ranks sector ETFs on a blended score and overweights the leaders. The blend
combines price momentum with an optional sentiment overlay derived from
financial text.

The blend weight is fixed before the backtest rather than optimized on the
sample. Tuning it in sample would produce a number that looks good and does
not survive out of sample.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SECTOR_ETFS = {
    "XLK": "Technology",
    "XLF": "Financials",
    "XLV": "Health Care",
    "XLE": "Energy",
    "XLI": "Industrials",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLU": "Utilities",
    "XLB": "Materials",
    "XLRE": "Real Estate",
    "XLC": "Communication Services",
}


def standardize(scores: pd.Series) -> pd.Series:
    """Cross-sectional Z-score with outlier trimming."""
    s = scores.dropna()
    if len(s) < 2:
        return pd.Series(dtype=float)
    trimmed = s.clip(s.quantile(0.05), s.quantile(0.95))
    sd = trimmed.std(ddof=1)
    return (trimmed - trimmed.mean()) / sd if sd else pd.Series(0.0, index=s.index)


def weights_fn(
    returns: pd.DataFrame,
    date: pd.Timestamp,
    lookback: int = 6,
    top_n: int = 3,
    sentiment: pd.DataFrame | None = None,
    sentiment_weight: float = 0.3,
) -> pd.Series:
    """Overweight the top ranked sectors.

    sentiment: optional DataFrame of sector sentiment scores indexed by date.
        Only rows strictly before `date` are used.
    """
    momentum = standardize((1.0 + returns.tail(lookback)).prod() - 1.0)
    if momentum.empty:
        return pd.Series(dtype=float)

    blended = momentum
    if sentiment is not None and sentiment_weight > 0:
        history = sentiment.loc[sentiment.index < date]
        if not history.empty:
            sent = standardize(history.iloc[-1].reindex(momentum.index))
            if not sent.empty:
                blended = (
                    (1.0 - sentiment_weight) * momentum
                    + sentiment_weight * sent.reindex(momentum.index).fillna(0.0)
                )

    n = min(top_n, len(blended))
    w = pd.Series(0.0, index=returns.columns)
    w[blended.sort_values(ascending=False).head(n).index] = 1.0 / n
    return w
