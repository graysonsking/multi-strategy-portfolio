"""Tests for portfolio construction."""

import numpy as np
import pandas as pd
import pytest

from src import optimizer


@pytest.fixture
def returns():
    rng = np.random.default_rng(42)
    idx = pd.date_range("2015-01-31", periods=120, freq="ME")
    cols = [f"A{i}" for i in range(8)]
    return pd.DataFrame(rng.normal(0.008, 0.04, (120, 8)), index=idx, columns=cols)


def test_equal_weight_sums_to_one(returns):
    w = optimizer.equal_weight(returns)
    assert w.sum() == pytest.approx(1.0)
    assert w.nunique() == 1


@pytest.mark.parametrize("fn", ["minimum_variance", "risk_parity", "inverse_volatility"])
def test_weights_sum_to_one(returns, fn):
    w = optimizer.get(fn)(returns)
    assert w.sum() == pytest.approx(1.0, abs=1e-6)


@pytest.mark.parametrize("fn", ["minimum_variance", "risk_parity"])
def test_long_only_has_no_negative_weights(returns, fn):
    w = optimizer.get(fn)(returns)
    assert (w >= -1e-8).all()


def test_min_variance_beats_equal_weight_in_sample(returns):
    cov = optimizer.covariance(returns)
    mv = optimizer.minimum_variance(returns)
    ew = optimizer.equal_weight(returns)
    var_mv = mv.values @ cov.values @ mv.values
    var_ew = ew.values @ cov.values @ ew.values
    assert var_mv <= var_ew + 1e-12


def test_risk_parity_equalizes_contributions(returns):
    cov = optimizer.covariance(returns)
    w = optimizer.risk_parity(returns)
    rc = optimizer.risk_contributions(w, cov)
    assert (rc.max() - rc.min()) < 1e-3


def test_ledoit_wolf_is_better_conditioned(returns):
    sample = optimizer.covariance(returns, "sample")
    shrunk = optimizer.covariance(returns, "ledoit_wolf")
    assert np.linalg.cond(shrunk.values) < np.linalg.cond(sample.values)


def test_max_weight_constraint_binds(returns):
    w = optimizer.minimum_variance(returns, max_weight=0.20)
    assert w.max() <= 0.20 + 1e-6


def test_unknown_optimizer_raises():
    with pytest.raises(KeyError):
        optimizer.get("does_not_exist")
