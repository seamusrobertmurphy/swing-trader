# Monte Carlo robustness (2026-07-03)

4h trained model (held-out OOS, confident picks). 10,000 simulations on 2,010 after-fee per-trade returns (block=1). Bootstrap = resample with replacement; reorder = shuffle order; sign-flip = no-edge null. ROBUST requires total P5 > 0, p(loss) < 5%, p-value < 0.05.

| metric | actual | P5 (worst) | median | P95 |
| --- | --- | --- | --- | --- |
| total return | -90.30% | -99.24% | -90.28% | +32.92% |
| max drawdown | -99.64% | -99.56% | -95.79% | - |
| Sharpe | -0.65 | -2.30 | -0.65 | - |

- probability of a losing outcome: **92.7%**

- reorder worst-5% max drawdown: **-98.04%** (path dependence)

- sign-flip permutation p-value: **0.7403**


**Verdict: FRAGILE.**

