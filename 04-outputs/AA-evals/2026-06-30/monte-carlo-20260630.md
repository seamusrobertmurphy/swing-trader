# Monte Carlo robustness (2026-06-30)

trained model (held-out OOS, confident picks). 10,000 simulations on 4,190 after-fee per-trade returns (block=1). Bootstrap = resample with replacement; reorder = shuffle order; sign-flip = no-edge null. ROBUST requires total P5 > 0, p(loss) < 5%, p-value < 0.05.

| metric | actual | P5 (worst) | median | P95 |
| --- | --- | --- | --- | --- |
| total return | -100.00% | -100.00% | -100.00% | -100.00% |
| max drawdown | -100.00% | -100.00% | -100.00% | - |
| Sharpe | -12.55 | -14.41 | -12.55 | - |

- probability of a losing outcome: **100.0%**

- reorder worst-5% max drawdown: **-100.00%** (path dependence)

- sign-flip permutation p-value: **1.0000**


**Verdict: FRAGILE.**

