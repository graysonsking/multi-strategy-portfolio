# Methodology

This document records the design decisions behind the framework and the reasoning for each. The intent is that anyone reading the results can judge whether they believe them.

---

## 1. Separation of Concerns

The framework splits into four independent layers.

| Layer | Responsibility | Module |
|---|---|---|
| Data | Loading, alignment, caching | `src/` loaders |
| Signal | Turning history into a view | `strategies/` |
| Construction | Turning a view into weights | `src/optimizer.py` |
| Accounting | Turning weights into returns | `src/portfolio.py`, `src/backtest.py` |

The benefit is comparability. Because every strategy runs through the same engine with the same cost model and the same rebalance schedule, differences in measured performance come from the signal rather than from differences in test harness.

---

## 2. Avoiding Look-Ahead Bias

This is the failure mode that ruins most backtests, and it is subtle enough that it usually gets in by accident.

**The guard.** The engine slices history inside `Backtester.run` before calling the strategy:

```python
history = self.asset_returns.loc[self.asset_returns.index < date]
```

The comparison is strictly less than, not less than or equal. A strategy physically cannot see the rebalance date's own return because it is never passed. This is enforced by a test in `tests/test_backtest.py` that records every window handed to a strategy and asserts the last observation predates the rebalance date.

**Why it is in the engine and not the strategy.** If each strategy did its own slicing, every new strategy would be a fresh opportunity to make the mistake. Centralizing it means the guarantee holds for code that has not been written yet.

**Signal timing.** Signals computed from data through date `t` are applied to returns beginning at `t+1`. In `Portfolio`, this is the `.shift(1)` on weights before multiplying by returns.

---

## 3. Survivorship Bias

Backtesting today's index constituents over a historical window measures the performance of companies that were successful enough to still be in the index. That is not a strategy result, it is a selection effect.

The engine accepts an optional `universe` callable returning point-in-time membership:

```python
bt.run(weights_fn, universe=lambda d: membership.constituents_on(d))
```

Without it, the full column set is used at every rebalance. Any published result should state which mode was used.

---

## 4. Covariance Estimation

The sample covariance matrix has roughly `N(N+1)/2` free parameters estimated from `T x N` observations. As `N` approaches `T`, the estimate becomes badly conditioned and eventually singular.

This matters because an optimizer will exploit estimation error. Minimum variance optimization loads onto assets whose sample covariance understates their true risk, which is exactly the set of assets where the estimate is most wrong. The in-sample variance looks excellent and the out-of-sample result is poor.

**Ledoit-Wolf shrinkage** is the default. It combines the sample estimate with a structured target using an analytically derived shrinkage intensity that minimizes expected squared error. The result is always positive definite and better conditioned. A test in `tests/test_optimizer.py` asserts the condition number improves.

The tradeoff is bias. Shrinkage moves the estimate away from the sample toward the target, so if the sample happens to be accurate, shrinkage hurts. In practice at realistic `N/T` ratios it helps substantially.

---

## 5. Weighting Schemes

| Scheme | Estimates required | Sensitivity to error |
|---|---|---|
| Equal weight | None | None |
| Inverse volatility | Variances only | Low |
| Risk parity | Full covariance | Moderate |
| Minimum variance | Full covariance | Moderate |
| Mean variance | Covariance and means | High |

Equal weight is the benchmark for a reason. It requires no estimation and is therefore immune to estimation error. Any optimizer that cannot beat 1/N out of sample is not adding value, and many do not.

Mean variance is the most fragile because expected returns are the hardest quantity to estimate. The sample mean of returns has enormous standard error at any realistic sample length. Small changes in the mean estimate produce large changes in optimal weights. Raising `risk_aversion` reduces the weight the optimizer places on the mean estimate relative to the covariance structure.

**Risk parity versus inverse volatility.** Inverse volatility ignores correlation. Risk parity solves numerically for weights where each asset contributes an equal share of total portfolio variance, accounting for the correlation structure. When correlations are uniform the two coincide.

---

## 6. Transaction Costs

Costs are charged on turnover at each rebalance:

```
cost = turnover x (cost_bps / 10,000)
```

Turnover is half the sum of absolute weight changes, so a complete liquidation and reinvestment reads as 1.0 rather than 2.0.

The default is 10 basis points one way. This is reasonable for large-cap equity and too optimistic for small caps or anything with wide spreads. Cost sensitivity is worth checking directly, since a strategy that only works at zero cost is not a strategy. Turnover is reported in every summary table for this reason.

**Not modeled:** market impact, borrow cost and availability for shorts, capacity constraints, and taxes. Strategies with high turnover or short exposure will look better here than they would in practice.

---

## 7. Performance Measurement

Standard statistics are in `src/risk.py`. Two beyond the usual set:

**Effective N** is the inverse Herfindahl index of portfolio weights. It answers how many positions the portfolio effectively holds rather than how many it nominally holds. A cap-weighted index of 500 names with heavy top-end concentration can have an effective N in the low double digits. This is the cleanest single measure of whether a weighting scheme actually delivers diversification.

**Conditional VaR** is reported alongside VaR. VaR states a threshold; CVaR states the average loss once that threshold is breached. For distributions with fat tails, which is all financial return distributions, the difference is the part that matters.

Sharpe ratios are reported but should be read with caution. They assume returns are adequately described by mean and variance, which understates risk for strategies with negatively skewed payoffs. Max drawdown and CVaR are the checks.

---

## 8. What This Framework Does Not Do

Stated plainly so results are not over-read:

- No market impact or capacity modeling. Results assume trades fill at the reference price.
- No borrow cost or short availability constraints.
- Point-in-time universe support exists but must be supplied by the caller.
- Backtested results reflect one path through history. They are not out-of-sample evidence in the sense that matters, since the strategies were designed with knowledge of that history.
- Parameter choices are fixed ex ante rather than optimized, which limits overfitting but does not eliminate it. The strategy set itself was chosen by someone who knows what has worked.

---

## References

Ledoit, O. and Wolf, M. (2004). A well-conditioned estimator for large-dimensional covariance matrices. *Journal of Multivariate Analysis*.

DeMiguel, V., Garlappi, L., and Uppal, R. (2009). Optimal versus naive diversification: how inefficient is the 1/N portfolio strategy? *Review of Financial Studies*.

Maillard, S., Roncalli, T., and Teiletche, J. (2010). The properties of equally weighted risk contribution portfolios. *Journal of Portfolio Management*.

Jegadeesh, N. and Titman, J. (1993). Returns to buying winners and selling losers. *Journal of Finance*.
