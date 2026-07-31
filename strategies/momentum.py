"""Cross-sectional momentum.

Rank assets on trailing return and hold the winners. The formation window
skips the most recent period because short horizon returns tend to reverse,
and including them contaminates the momentum signal with reversal.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def formation_return(returns: pd.DataFrame, lookback: int = 12, skip: int = 1) -> pd.Series:
    """Compound return over the formation window, excluding the skip period."""
    window = returns.iloc[-(lookback + skip): -skip] if skip else returns.tail(lookback)
    return (1.0 + window).prod() - 1.0


def weights_fn(
    returns: pd.DataFrame,
    date: pd.Timestamp,
    lookback: int = 12,
    skip: int = 1,
    top_n: int = 10,
    long_short: bool = False,
) -> pd.Series:
    """Equal weight the top ranked assets.

    long_short: if True, short the bottom `top_n` with offsetting weight so
        the book is dollar neutral.
    """
    scores = formation_return(returns, lookback, skip).dropna()
    if scores.empty:
        return pd.Series(dtype=float)

    n = min(top_n, len(scores) // 2 if long_short else len(scores))
    ranked = scores.sort_values(ascending=False)

    w = pd.Series(0.0, index=returns.columns)
    winners = ranked.head(n).index
    w[winners] = 1.0 / n

    if long_short:
        losers = ranked.tail(n).index
        w[losers] = -1.0 / n

    return w


def weights_fn_risk_adjusted(
    returns: pd.DataFrame,
    date: pd.Timestamp,
    lookback: int = 12,
    skip: int = 1,
    top_n: int = 10,
) -> pd.Series:
    """Momentum ranked on return divided by trailing volatility.

    Scaling by volatility keeps a single high variance name from dominating
    the ranking purely because its return distribution is wider.
    """
    scores = formation_return(returns, lookback, skip)
    vol = returns.tail(lookback).std(ddof=1).replace(0, np.nan)
    adjusted = (scores / vol).dropna()
    if adjusted.empty:
        return pd.Series(dtype=float)

    n = min(top_n, len(adjusted))
    w = pd.Series(0.0, index=returns.columns)
    w[adjusted.sort_values(ascending=False).head(n).index] = 1.0 / n
    return w
