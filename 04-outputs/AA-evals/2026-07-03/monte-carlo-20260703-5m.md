# Monte Carlo robustness (2026-07-03)

5m trained model (held-out OOS, confident picks). 10,000 simulations on 398 after-fee per-trade returns (block=1). Bootstrap = resample with replacement; reorder = shuffle order; sign-flip = no-edge null. ROBUST requires total P5 > 0, p(loss) < 5%, p-value < 0.05.

| metric | actual | P5 (worst) | median | P95 |
| --- | --- | --- | --- | --- |
| total return | -41.76% | -51.25% | -41.75% | -30.28% |
| max drawdown | -43.38% | -51.76% | -42.65% | - |
| Sharpe | -4.84 | -6.85 | -4.86 | - |

- probability of a losing outcome: **100.0%**

- reorder worst-5% max drawdown: **-44.50%** (path dependence)

- sign-flip permutation p-value: **1.0000**


**Verdict: FRAGILE.**

