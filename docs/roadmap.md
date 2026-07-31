# Roadmap

Current state and planned work. Kept honest so the repository does not overstate what is finished.

## Status

| Component | State |
|---|---|
| Walk-forward backtest engine | Complete, tested |
| Look-ahead guard | Complete, enforced by test |
| Covariance estimation (sample, Ledoit-Wolf) | Complete, tested |
| Weighting schemes (equal, inverse vol, min var, mean var, risk parity) | Complete, tested |
| Performance and risk statistics | Complete, tested |
| Transaction cost model | Complete, turnover based |
| Momentum strategy | Complete |
| Sector rotation strategy | Complete, sentiment overlay optional |
| Macro tilt strategy | Interface complete, requires macro data source |
| Statistical arbitrage | Interface complete, pair screening is expensive |
| Point-in-time universe support | Interface complete, requires membership source |
| Data loaders | Complete |
| Published results | Complete |

## Near Term

1. **Cost sensitivity analysis.** Sweep the cost assumption and report the break-even level for each strategy. A strategy that only works below 5 bps should be labeled as such.
2. **Macro data source.** Connect FRED with vintage aware retrieval so the macro strategy is testable without look-ahead on revisions.

## Medium Term

3. **Point-in-time membership.** Reuse the reconstruction approach from the S&P 500 concentration research repo so survivorship bias can be turned off by default rather than by argument.
4. **Strategy combination.** Allocate across strategies rather than testing them in isolation. The interesting question is whether the combination has a better risk profile than its components, which requires modeling the correlation between strategy return streams.
5. **Constraint layer.** Sector caps, position limits, and turnover budgets applied uniformly across optimizers rather than passed per call.
6. **Walk-forward parameter selection.** Currently parameters are fixed ex ante. A nested walk-forward that selects parameters on a trailing window would be more realistic, at the cost of a much slower run.

## Longer Term

7. **Factor attribution.** Decompose strategy returns against standard factor models to separate genuine alpha from factor exposure that could be obtained more cheaply.
8. **Regime conditioning.** Test whether strategy performance is stable across volatility and rate regimes, or whether aggregate statistics are hiding a strategy that works in one environment only.
9. **Capacity estimation.** Model market impact as a function of position size against average daily volume, and estimate the capital level at which each strategy stops working.

## Explicitly Out of Scope

- Live trading and order routing. This is research code.
- Intraday data and execution modeling.
- Options and non-linear payoffs.
