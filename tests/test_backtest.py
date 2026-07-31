"""Tests for the walk-forward engine. The look-ahead guard matters most."""

import numpy as np
import pandas as pd
import pytest

from src import optimizer
from src.backtest import Backtester, normalize_freq


@pytest.fixture
def returns():
    rng = np.random.default_rng(3)
    idx = pd.date_range("2010-01-31", periods=180, freq="ME")
    cols = [f"A{i}" for i in range(6)]
    return pd.DataFrame(rng.normal(0.006, 0.04, (180, 6)), index=idx, columns=cols)


def test_frequency_alias_normalizes():
    assert normalize_freq("M") in ("M", "ME")
    assert normalize_freq("Q") in ("Q", "QE")


def test_strategy_never_sees_future_data(returns):
    """The engine must slice history strictly before the rebalance date."""
    seen = []

    def spy(history, date):
        seen.append((history.index.max(), date))
        return optimizer.equal_weight(history)

    Backtester(returns, lookback=24).run(spy)
    assert seen, "strategy was never called"
    for last_obs, rebal_date in seen:
        assert last_obs < rebal_date


def test_lookback_window_is_respected(returns):
    lengths = []

    def spy(history, date):
        lengths.append(len(history))
        return optimizer.equal_weight(history)

    Backtester(returns, lookback=36).run(spy)
    assert max(lengths) <= 36


def test_costs_reduce_returns(returns):
    def momentum(history, date):
        score = (1 + history.tail(6)).prod() - 1
        w = pd.Series(0.0, index=history.columns)
        w[score.sort_values(ascending=False).head(2).index] = 0.5
        return w

    free = Backtester(returns, lookback=24, cost_bps=0).run(momentum)
    costly = Backtester(returns, lookback=24, cost_bps=50).run(momentum)
    assert costly.returns.sum() < free.returns.sum()


def test_turnover_is_zero_for_static_allocation(returns):
    bt = Backtester(returns, lookback=24)
    p = bt.run(lambda h, d: optimizer.equal_weight(h))
    # After the initial purchase, an unchanged target implies no trading.
    assert p.turnover.iloc[1:].max() == pytest.approx(0.0, abs=1e-9)


def test_empty_result_raises(returns):
    with pytest.raises(ValueError):
        Backtester(returns, lookback=10_000, min_history=10_000).run(
            lambda h, d: optimizer.equal_weight(h)
        )


def test_non_datetime_index_rejected():
    df = pd.DataFrame(np.random.rand(50, 3))
    with pytest.raises(TypeError):
        Backtester(df)
