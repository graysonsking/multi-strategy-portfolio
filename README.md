[README.md](https://github.com/user-attachments/files/30569156/README.md)
# Multi-Strategy Portfolio

A quantitative research framework for building, backtesting, and combining systematic trading strategies under a shared risk and portfolio construction layer.

The goal is separation of concerns. Data loading, signal generation, portfolio construction, and performance measurement are independent modules. Any strategy that produces a weight vector can be dropped into the same backtest engine and compared on identical terms.

---

## Contents

- [Design](#design)
- [Repository Layout](#repository-layout)
- [Strategies](#strategies)
- [Portfolio Construction](#portfolio-construction)
- [Backtest Methodology](#backtest-methodology)
- [Installation](#installation)
- [Usage](#usage)
- [Results](#results)
- [Limitations](#limitations)
- [License](#license)

---

## Design

Every strategy implements the same interface:

```python
def weights_fn(returns: pd.DataFrame, date: pd.Timestamp, **params) -> pd.Series:
    """Return target portfolio weights for `date` using only data available at `date`."""
```

The engine handles rebalancing, transaction costs, and performance attribution. This means a new strategy requires one function, not a new backtester.

```
Data Layer  ->  Signal Layer  ->  Portfolio Construction  ->  Backtest Engine  ->  Reporting
```

---

## Repository Layout

```
multi-strategy-portfolio/
|
|-- README.md
|-- LICENSE
|-- .gitignore
|-- requirements.txt
|
|-- src/
|   |-- __init__.py
|   |-- backtest.py
|   |-- optimizer.py
|   |-- portfolio.py
|   `-- risk.py
|
|-- strategies/
|   |-- __init__.py
|   |-- macro.py
|   |-- momentum.py
|   |-- sector_rotation.py
|   `-- stat_arb.py
|
|-- docs/
|   |-- methodology.md
|   `-- roadmap.md
|
|-- results/
|   `-- .gitkeep
|
|-- tests/
|   |-- __init__.py
|   |-- test_backtest.py
|   |-- test_optimizer.py
|   `-- test_risk.py
```

---

## Strategies

| Strategy | Signal | Universe | Rebalance |
|---|---|---|---|
| Cross-sectional momentum | 12 month return skipping the most recent month | Equity | Monthly |
| Mean reversion | Z-score of price against a rolling mean | Equity | Weekly |
| Risk parity | Inverse volatility contribution | Multi-asset ETF | Monthly |
| Minimum variance | Ledoit-Wolf shrunk covariance | Equity | Monthly |
| Sentiment overlay | FinBERT score on financial text | Sector ETF | Monthly |

Fill in or trim this table to match what is actually in `strategies/`.

---

## Portfolio Construction

Available weighting schemes:

- **Equal weight** — baseline with no estimation error
- **Mean variance** — Markowitz optimization with optional long-only and turnover constraints
- **Minimum variance** — Ledoit-Wolf shrinkage on the covariance matrix to reduce estimation noise
- **Risk parity** — equal marginal risk contribution, solved numerically
- **Inverse volatility** — simple risk-based scaling

Shrinkage matters here. Sample covariance matrices are badly conditioned when the number of assets approaches the number of observations, and the optimizer will load onto whatever the estimation error favors. Ledoit-Wolf pulls the estimate toward a structured target and produces materially more stable weights out of sample.

---

## Backtest Methodology

- **Walk-forward only.** Parameters are estimated on a trailing window and applied forward. No in-sample fitting.
- **Point-in-time universe.** Constituents reflect membership as of the rebalance date to avoid survivorship bias.
- **Transaction costs.** Applied per unit of turnover at each rebalance.
- **Lagged signals.** Signals computed at close on date `t` are traded at `t+1` open.

| Parameter | Default |
|---|---|
| Backtest window | 2000-01-01 to 2025-12-31 |
| Estimation window | 60 months |
| Rebalance frequency | Monthly |
| Transaction cost | 10 bps per side |

---

## Installation

```bash
git clone https://github.com/graysonsking/multi-strategy-portfolio.git
cd multi-strategy-portfolio

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

---

## Usage

Run a single strategy:

```bash
python -m src.backtest.run --strategy momentum --start 2000-01-01 --end 2025-12-31
```

Compare weighting schemes on the same universe:

```bash
python -m src.backtest.run --compare equal_weight,min_variance,risk_parity
```

Use the engine directly:

```python
from src.backtest import Backtester
from strategies.momentum import weights_fn

bt = Backtester(
    start="2000-01-01",
    end="2025-12-31",
    rebalance="M",
    cost_bps=10,
)

result = bt.run(weights_fn)
print(result.summary())
result.plot_equity_curve()
```

---

## Tests

```bash
python -m pytest tests -q
```

27 tests covering the look-ahead guard, optimizer constraints, covariance conditioning, and cost accounting.

## Results

Replace the placeholder values below with output from your own runs. Do not publish numbers you have not reproduced.

| Strategy | CAGR | Volatility | Sharpe | Max Drawdown | Turnover |
|---|---|---|---|---|---|
| Equal weight | — | — | — | — | — |
| Momentum | — | — | — | — | — |
| Minimum variance | — | — | — | — | — |
| Risk parity | — | — | — | — | — |
| S&P 500 benchmark | — | — | — | — | — |

Add an equity curve image here once generated:

```markdown
![Equity curves](docs/images/equity_curves.png)
```

---

## Limitations

- Backtested results do not account for market impact, borrow cost, or capacity constraints.
- Point-in-time membership is reconstructed from public change histories and may contain small errors around index events.
- Sentiment signals depend on model outputs that were trained on text distributions that may differ from the test period.

---

## License

MIT. See [LICENSE](LICENSE).

---

*This repository is research code. It is not investment advice and is not intended for live trading.*
