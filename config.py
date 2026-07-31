"""Run configuration.

Everything you would want to change lives here. `run_results.py` reads this
and does not need editing.

Credentials are read from a `.env` file in this same folder. See `.env.example`.
The default run needs no credentials at all: yfinance is unauthenticated.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent / ".env")
except ImportError:  # dotenv is optional
    pass


# ============================================================== credentials
# Not required for the default run. Leave blank unless you are wiring up the
# macro strategy, which needs a free FRED key from
# https://fredaccount.stlouisfed.org/apikeys

FRED_API_KEY = os.getenv("FRED_API_KEY", "")

# Only needed if you later swap the data source from yfinance to Alpaca.
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET", "")


# ================================================================= universe
# Twelve liquid ETFs spanning equity, duration, credit, and real assets.
# Changing this changes every number in the output, so the list is written
# into results/summary.md on each run rather than left implicit.

UNIVERSE = [
    "SPY",   # US large cap
    "IWM",   # US small cap
    "EFA",   # Developed international
    "EEM",   # Emerging markets
    "TLT",   # Long Treasuries
    "IEF",   # Intermediate Treasuries
    "LQD",   # Investment grade credit
    "HYG",   # High yield credit
    "TIP",   # Inflation protected
    "GLD",   # Gold
    "DBC",   # Broad commodities
    "VNQ",   # REITs
]

# Benchmarks are constant-weight portfolios rebalanced monthly, charged the
# same transaction costs as the strategies. A single-asset spec is buy and
# hold. Every ticker used here must also appear in UNIVERSE above.
#
# SPY alone is the opportunity cost reference: what you gave up by
# diversifying. 60/40 is the peer reference: whether the optimizers beat the
# naive multi-asset default, which is the question this repo actually asks.

BENCHMARKS = {
    "SPY buy and hold": {"SPY": 1.00},
    "60/40 SPY/IEF": {"SPY": 0.60, "IEF": 0.40},
}

# Beta, tracking error, and information ratio are measured against this one.
PRIMARY_BENCHMARK = "SPY buy and hold"


# ============================================================ backtest knobs

START = "2007-01-01"   # DBC and TIP both have history from 2006/2007
END = None             # None means through today

LOOKBACK = 60          # months of history handed to each strategy
REBALANCE = "ME"        # month end
COST_BPS = 10.0        # one way, charged on turnover
MIN_HISTORY = 60       # months required before the first trade

MOMENTUM_TOP_N = 4     # holdings out of 12
MOMENTUM_LOOKBACK = 12
MOMENTUM_SKIP = 1

MINVAR_MAX_WEIGHT = 0.30   # position cap on the minimum variance optimizer
COV_METHOD = "ledoit_wolf"  # "sample" or "ledoit_wolf"


# ==================================================================== paths

ROOT = Path(__file__).parent
CACHE_DIR = ROOT / "cache"
RESULTS_DIR = ROOT / "results"
FIGURES_DIR = ROOT / "docs" / "images"
