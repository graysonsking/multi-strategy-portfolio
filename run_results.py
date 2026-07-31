"""Reproduce the published results.

Loads price data, runs every strategy and benchmark through the identical
walk-forward schedule, and writes the summary table and figures.

    python run_results.py              # real data
    python run_results.py --offline    # synthetic data, tests the plumbing
    python run_results.py --start 2010-01-01 --cost-bps 25

Settings live in `config.py`. Everything in the README results section comes
from this script. If a number is in the README and this script does not
produce it, the number is wrong.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

import config
from src import optimizer, risk
from src.backtest import Backtester
from strategies import momentum


# --------------------------------------------------------------- data layer


def load_prices(tickers, start, end):
    """Adjusted closes, cached to parquet so reruns need no network."""
    config.CACHE_DIR.mkdir(exist_ok=True)
    key = config.CACHE_DIR / f"prices_{start}_{end or 'latest'}_{len(tickers)}.parquet"

    if key.exists():
        print(f"cache hit: {key.name}  (delete to force refresh)")
        return pd.read_parquet(key)

    try:
        import yfinance as yf
    except ImportError:
        sys.exit("yfinance not installed. Run: python -m pip install yfinance")

    print(f"downloading {len(tickers)} tickers from {start}...")
    raw = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)

    if raw is None or raw.empty:
        sys.exit(
            "yfinance returned nothing. Check your connection, or run with "
            "--offline to verify the rest of the pipeline works."
        )

    prices = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw
    prices = prices.dropna(axis=1, how="all").sort_index()

    missing = set(tickers) - set(prices.columns)
    if missing:
        print(f"warning: no data for {sorted(missing)}")

    prices.to_parquet(key)
    print(f"cached to {key.name}")
    return prices


def synthetic_prices(tickers, start, periods=300):
    """Deterministic fake data. Exercises the pipeline without a network."""
    rng = np.random.default_rng(0)
    idx = pd.date_range(start, periods=periods, freq="ME")
    drift = rng.uniform(0.002, 0.008, len(tickers))
    vol = rng.uniform(0.02, 0.06, len(tickers))
    shocks = rng.standard_normal((periods, len(tickers))) * vol + drift
    return pd.DataFrame(
        100 * np.exp(np.cumsum(shocks, axis=0)), index=idx, columns=tickers
    )


def to_monthly_returns(prices):
    return prices.resample("ME").last().pct_change().dropna(how="all")


# --------------------------------------------------------------- benchmarks


def fixed_weight_benchmark(returns, spec, cost_bps):
    """Return stream for a constant-weight portfolio rebalanced every period.

    Weights drift with returns inside the period and are reset to target at
    the next one. Turnover is the drift that has to be traded away, charged
    at the same rate the strategies pay, so the benchmark does not get a free
    pass the strategies are denied. A single asset spec is buy and hold: it
    cannot drift away from its own target, so turnover is zero after the
    initial purchase.

    Returns (net_returns, turnover).
    """
    cols = [c for c in spec if c in returns.columns]
    if not cols:
        return None, None

    target = np.array([spec[c] for c in cols], dtype=float)
    target = target / target.sum()

    R = returns[cols].fillna(0.0).to_numpy()
    net = np.zeros(len(R))
    turn = np.zeros(len(R))

    # Start flat so the initial purchase is charged, matching how the
    # backtester treats a strategy's first set of weights.
    drifted = np.zeros(len(cols))

    for t in range(len(R)):
        turn[t] = np.abs(target - drifted).sum() / 2.0
        net[t] = float(target @ R[t]) - turn[t] * cost_bps / 1e4
        grown = target * (1.0 + R[t])
        total = grown.sum()
        drifted = grown / total if total > 0 else target.copy()

    return pd.Series(net, index=returns.index), pd.Series(turn, index=returns.index)


# --------------------------------------------------------------- strategies


def build_strategies():
    """Display name -> weights_fn matching the backtest contract.

    The optimizers take only `returns`, so they are wrapped to accept and
    ignore `date`. The engine has already sliced the history to exclude
    anything at or after the rebalance date, so the date carries no
    information the optimizer needs.
    """
    return {
        "Equal weight": lambda r, d: optimizer.equal_weight(r),
        "Inverse volatility": lambda r, d: optimizer.inverse_volatility(r),
        "Minimum variance": lambda r, d: optimizer.minimum_variance(
            r, cov_method=config.COV_METHOD, max_weight=config.MINVAR_MAX_WEIGHT
        ),
        "Risk parity": lambda r, d: optimizer.risk_parity(r, cov_method=config.COV_METHOD),
        "Momentum": lambda r, d: momentum.weights_fn(
            r,
            d,
            lookback=config.MOMENTUM_LOOKBACK,
            skip=config.MOMENTUM_SKIP,
            top_n=config.MOMENTUM_TOP_N,
        ),
    }


# ---------------------------------------------------------------- reporting

README_COLS = ["CAGR", "Volatility", "Sharpe", "Max Drawdown", "Avg Turnover"]
PCT_COLS = ["CAGR", "Volatility", "Max Drawdown", "VaR 95", "CVaR 95", "Hit Rate"]


def format_table(stats):
    out = pd.DataFrame(index=stats.index)
    for col in stats.columns:
        if col in PCT_COLS:
            vals = (stats[col] * 100).round(2).astype(str) + "%"
        else:
            vals = stats[col].round(2).astype(str)
        out[col] = vals.where(stats[col].notna(), "—")
    out.index.name = "Strategy"
    return out


def write_figures(curves, draws, bench_curves, bench_draws):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    bench_styles = [("black", "--"), ("dimgray", "-.")]

    fig, ax = plt.subplots(figsize=(11, 6))
    for name, curve in curves.items():
        curve.plot(ax=ax, linewidth=1.4, label=name)
    for i, (name, curve) in enumerate(bench_curves.items()):
        color, style = bench_styles[i % len(bench_styles)]
        curve.plot(ax=ax, linewidth=1.7, linestyle=style, color=color, label=name)
    ax.set_yscale("log")
    ax.set_ylabel("Growth of 1.00 (log scale)")
    ax.set_xlabel("")
    ax.set_title("Strategy equity curves, net of transaction costs")
    ax.legend(frameon=False, fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(config.FIGURES_DIR / "equity_curves.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 4.5))
    for name, dd in draws.items():
        dd.plot(ax=ax, linewidth=1.2, label=name)
    for i, (name, dd) in enumerate(bench_draws.items()):
        color, style = bench_styles[i % len(bench_styles)]
        dd.plot(ax=ax, linewidth=1.5, linestyle=style, color=color, label=name)
    ax.set_ylabel("Drawdown")
    ax.set_xlabel("")
    ax.set_title("Drawdown from prior peak")
    ax.legend(frameon=False, fontsize=9, ncol=4)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(config.FIGURES_DIR / "drawdowns.png", dpi=150)
    plt.close(fig)

    print(f"wrote {config.FIGURES_DIR / 'equity_curves.png'}")
    print(f"wrote {config.FIGURES_DIR / 'drawdowns.png'}")


def write_results(stats, meta):
    config.RESULTS_DIR.mkdir(exist_ok=True)
    stats.to_csv(config.RESULTS_DIR / "summary.csv")

    formatted = format_table(stats)
    lines = [
        "# Backtest Results",
        "",
        "Generated by `run_results.py`. Do not edit by hand.",
        "",
        "## Run parameters",
        "",
    ]
    lines += [f"- **{k}:** {v}" for k, v in meta.items()]
    lines += ["", "## Full summary", "", formatted.to_markdown(), ""]
    (config.RESULTS_DIR / "summary.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"wrote {config.RESULTS_DIR / 'summary.csv'}")
    print(f"wrote {config.RESULTS_DIR / 'summary.md'}")

    print("\n" + "=" * 70)
    print("PASTE THIS INTO THE README RESULTS SECTION")
    print("=" * 70 + "\n")
    print(formatted[README_COLS].to_markdown())
    print("\n![Equity curves](docs/images/equity_curves.png)\n")


# ------------------------------------------------------------------ driver


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=config.START)
    ap.add_argument("--end", default=config.END)
    ap.add_argument("--lookback", type=int, default=config.LOOKBACK)
    ap.add_argument("--cost-bps", type=float, default=config.COST_BPS)
    ap.add_argument("--offline", action="store_true", help="synthetic data")
    args = ap.parse_args()

    if args.offline:
        print("OFFLINE MODE: synthetic data. The numbers are meaningless.\n")
        prices = synthetic_prices(config.UNIVERSE, args.start)
    else:
        prices = load_prices(config.UNIVERSE, args.start, args.end)

    returns = to_monthly_returns(prices)
    print(f"\n{returns.shape[0]} months, {returns.shape[1]} assets")
    print(f"{returns.index[0]:%Y-%m} to {returns.index[-1]:%Y-%m}\n")

    if returns.shape[0] <= args.lookback:
        sys.exit(
            f"only {returns.shape[0]} months of data but lookback is "
            f"{args.lookback}. Use an earlier --start or a shorter --lookback."
        )

    engine = Backtester(
        asset_returns=returns,
        lookback=args.lookback,
        rebalance=config.REBALANCE,
        cost_bps=args.cost_bps,
        min_history=config.MIN_HISTORY,
    )

    print("running strategies...")
    portfolios = list(engine.compare(build_strategies()).values())

    # Trim to the live trading window.
    #
    # Portfolio.returns spans the full sample, and every month before a
    # strategy's first rebalance is an exact zero because it holds nothing
    # yet. Those months are absence, not flat performance. Leaving them in
    # annualizes real growth over a longer window than it was earned in,
    # shrinks measured volatility, and lets the benchmarks bank a market
    # history no strategy here traded through.
    first_trade = max(p.weights.index[0] for p in portfolios)
    print(f"first rebalance {first_trade:%Y-%m}; statistics start there\n")

    # Benchmarks, on the same window and paying the same costs.
    bench_returns, bench_turnover = {}, {}
    for name, spec in config.BENCHMARKS.items():
        r, turn = fixed_weight_benchmark(returns, spec, args.cost_bps)
        if r is None:
            print(f"warning: skipping benchmark {name}, assets not in universe")
            continue
        bench_returns[name] = r.loc[first_trade:]
        bench_turnover[name] = turn.loc[first_trade:]

    if config.PRIMARY_BENCHMARK not in bench_returns:
        sys.exit(f"primary benchmark '{config.PRIMARY_BENCHMARK}' could not be built")
    primary = bench_returns[config.PRIMARY_BENCHMARK]

    rows, curves, draws = {}, {}, {}
    for p in portfolios:
        r = p.returns.loc[first_trade:]
        s = risk.summary(r, benchmark=primary, periods_per_year=12)
        s["Avg Turnover"] = float(p.turnover.loc[first_trade:].mean())
        s["Avg Effective N"] = float(p.effective_n.loc[first_trade:].mean())
        rows[p.name] = s
        curves[p.name] = (1.0 + r).cumprod().rename(p.name)
        draws[p.name] = risk.drawdown_series(r)

    bench_curves, bench_draws = {}, {}
    for name, r in bench_returns.items():
        is_primary = name == config.PRIMARY_BENCHMARK
        s = risk.summary(
            r, benchmark=None if is_primary else primary, periods_per_year=12
        )
        s["Avg Turnover"] = float(bench_turnover[name].mean())
        s["Avg Effective N"] = float(len(config.BENCHMARKS[name]))
        rows[name] = s
        bench_curves[name] = (1.0 + r).cumprod().rename(name)
        bench_draws[name] = risk.drawdown_series(r)

    stats = pd.DataFrame(rows).T

    meta = {
        "Universe": ", ".join(config.UNIVERSE),
        "Data sample": f"{returns.index[0]:%Y-%m} to {returns.index[-1]:%Y-%m}",
        "Trading period": (
            f"{first_trade:%Y-%m} to {returns.index[-1]:%Y-%m}. "
            f"The first {args.lookback} months are the estimation burn-in and "
            f"are excluded from all statistics, benchmarks included."
        ),
        "Rebalance": "Monthly, month end",
        "Estimation window": f"{args.lookback} months trailing",
        "Transaction cost": (
            f"{args.cost_bps:.0f} bps one way, on turnover. Charged to the "
            "benchmarks on the same basis."
        ),
        "Benchmarks": "; ".join(
            f"{n} ({', '.join(f'{k} {v:.0%}' for k, v in s.items())})"
            for n, s in config.BENCHMARKS.items()
        ),
        "Beta, TE and IR measured against": config.PRIMARY_BENCHMARK,
        "Covariance": config.COV_METHOD,
        "Min variance cap": f"{config.MINVAR_MAX_WEIGHT:.0%} per asset",
        "Momentum": (
            f"top {config.MOMENTUM_TOP_N} of {len(config.UNIVERSE)}, "
            f"{config.MOMENTUM_LOOKBACK} month formation, "
            f"{config.MOMENTUM_SKIP} month skip"
        ),
        "Survivorship": "Not corrected. Fixed ETF list, all currently listed.",
        "Data source": "Synthetic" if args.offline else "yfinance, adjusted closes",
    }

    write_results(stats, meta)
    write_figures(curves, draws, bench_curves, bench_draws)


if __name__ == "__main__":
    main()
