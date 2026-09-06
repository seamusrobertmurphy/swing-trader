# Monte Carlo robustness (2026-06-27)

triple-Supertrend baseline (OOS). 10,000 simulations on 1,926 after-fee per-trade returns (block=1). Bootstrap = resample with replacement; reorder = shuffle order; sign-flip = no-edge null. ROBUST requires total P5 > 0, p(loss) < 5%, p-value < 0.05.

| metric | actual | P5 (worst) | median | P95 |
| --- | --- | --- | --- | --- |
| total return | -92.41% | -99.62% | -92.57% | +57.57% |
| max drawdown | -94.98% | -99.79% | -97.31% | - |
| Sharpe | -0.43 | -2.07 | -0.44 | - |

- probability of a losing outcome: **91.6%**

- reorder worst-5% max drawdown: **-98.88%** (path dependence)

- sign-flip permutation p-value: **0.6645**


**Verdict: FRAGILE.**

