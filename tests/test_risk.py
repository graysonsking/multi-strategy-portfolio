"""Tests for performance and risk statistics."""

import numpy as np
import pandas as pd
import pytest

from src import risk


@pytest.fixture
def flat_returns():
    idx = pd.date_range("2020-01-31", periods=36, freq="ME")
    return pd.Series(0.01, index=idx)


def test_cagr_matches_compounding(flat_returns):
    expected = 1.01 ** 12 - 1
    assert risk.cagr(flat_returns) == pytest.approx(expected, rel=1e-9)


def test_zero_volatility_on_constant_returns(flat_returns):
    assert risk.annualized_volatility(flat_returns) == pytest.approx(0.0)


def test_no_drawdown_when_always_positive(flat_returns):
    assert risk.max_drawdown(flat_returns) == pytest.approx(0.0)


def test_drawdown_recovers_to_zero():
    r = pd.Series([0.0, -0.5, 1.0], index=pd.date_range("2020-01-31", periods=3, freq="ME"))
    dd = risk.drawdown_series(r)
    assert dd.min() == pytest.approx(-0.5)
    assert dd.iloc[-1] == pytest.approx(0.0)


def test_effective_n_equal_weight():
    w = pd.Series(0.1, index=[f"A{i}" for i in range(10)])
    assert risk.effective_n(w) == pytest.approx(10.0)


def test_effective_n_falls_with_concentration():
    concentrated = pd.Series([0.9] + [0.1 / 9] * 9, index=[f"A{i}" for i in range(10)])
    assert risk.effective_n(concentrated) < 2.0


def test_herfindahl_bounds():
    w = pd.Series(0.25, index=list("ABCD"))
    assert risk.herfindahl(w) == pytest.approx(0.25)


def test_cvar_not_above_var():
    rng = np.random.default_rng(0)
    r = pd.Series(rng.normal(0, 0.05, 500))
    assert risk.conditional_var(r) <= risk.historical_var(r)


def test_beta_of_series_against_itself_is_one():
    rng = np.random.default_rng(1)
    r = pd.Series(rng.normal(0, 0.03, 200))
    assert risk.beta(r, r) == pytest.approx(1.0)
