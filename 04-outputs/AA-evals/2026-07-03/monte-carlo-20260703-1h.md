# Monte Carlo robustness (2026-07-03)

1h trained model (held-out OOS, confident picks). 10,000 simulations on 1,476 after-fee per-trade returns (block=1). Bootstrap = resample with replacement; reorder = shuffle order; sign-flip = no-edge null. ROBUST requires total P5 > 0, p(loss) < 5%, p-value < 0.05.

| metric | actual | P5 (worst) | median | P95 |
| --- | --- | --- | --- | --- |
| total return | -99.75% | -99.93% | -99.76% | -99.16% |
| max drawdown | -99.79% | -99.93% | -99.77% | - |
| Sharpe | -7.71 | -9.56 | -7.72 | - |

- probability of a losing outcome: **100.0%**

- reorder worst-5% max drawdown: **-99.80%** (path dependence)

- sign-flip permutation p-value: **1.0000**


**Verdict: FRAGILE.**

