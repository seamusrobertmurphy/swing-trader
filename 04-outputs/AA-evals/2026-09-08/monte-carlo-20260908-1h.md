# Monte Carlo robustness (2026-09-08)

1h trained model (held-out OOS, confident picks). 10,000 simulations on 1,511 after-fee per-trade returns (block=1). Bootstrap = resample with replacement; reorder = shuffle order; sign-flip = no-edge null. ROBUST requires total P5 > 0, p(loss) < 5%, p-value < 0.05.

| metric | actual | P5 (worst) | median | P95 |
| --- | --- | --- | --- | --- |
| total return | -99.72% | -99.92% | -99.72% | -99.02% |
| max drawdown | -99.72% | -99.92% | -99.74% | - |
| Sharpe | -7.38 | -9.22 | -7.39 | - |

- probability of a losing outcome: **100.0%**

- reorder worst-5% max drawdown: **-99.77%** (path dependence)

- sign-flip permutation p-value: **1.0000**


**Verdict: FRAGILE.**

