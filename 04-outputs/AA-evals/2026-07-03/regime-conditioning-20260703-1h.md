# Regime conditioning ablation (2026-07-03) -- 1h (30,000-row sample)

Handoff Part 2: one model conditioned on observable regime state (the `f_rg_` block) vs the same model without it. Higher after-cost expectancy or a better worst-era (less reliance on one regime) means conditioning helps.

- regime block: 10 features ['f_rg_rv_short', 'f_rg_rv_long', 'f_rg_vol_regime', 'f_rg_drift_short', 'f_rg_drift_long', 'f_rg_efficiency', 'f_rg_updown', 'f_rg_ret_long', 'f_rg_btc_ret_long', 'f_rg_btc_regime']
- features: baseline 61, conditioned 71

| model | held-out | after-cost/trade | era mean | era worst | eras positive |
| --- | --- | --- | --- | --- | --- |
| baseline (no regime) | AUC 0.515, picks 0.314/base 0.306 | -0.349% | -0.119% | -0.206% | 0/4 |
| conditioned (+f_rg_) | AUC 0.516, picks 0.296/base 0.306 | -0.387% | -0.146% | -0.209% | 0/4 |

**Effect of conditioning** (two separate questions): cross-era STABILITY does not improve (worst-era -0.003pp, era-mean -0.027pp, eras-positive +0); after-cost EDGE does not lift (-0.038pp/trade). The point of Part 2 is the first: a model that generalizes across regimes rather than memorizing one. Both remain subject to the after-fee GO/NO-GO bar.

## Per-era after-cost (conditioned model)
| era | trades | after-cost/trade | win |
| --- | --- | --- | --- |
| 2017 launch run-up | 0 | - | - |
| 2018 bear | 0 | - | - |
| 2019-20 base | 0 | - | - |
| 2020-21 bull | 0 | - | - |
| 2021 top + chop | 236 | -0.058% | 0.36 |
| 2022 collapse | 731 | -0.137% | 0.34 |
| 2023-24 recovery | 689 | -0.180% | 0.34 |
| 2025-26 recent | 1,097 | -0.209% | 0.34 |

## Monte Carlo robustness & model performance (conditioned model, held-out confident trades)
**Model performance** -- the same caret-style scoreboard as the model-assessment table. RMSE and MAE are on predicted probabilities (RMSE = sqrt(Brier)); Full = in-sample on the training window, CV = time-series out-of-fold, RMSEratio = Full / CV (near 1 = stable, well below 1 = overfit). Lower RMSE and higher AUC are better.
| metric | baseline | conditioned |
| --- | --- | --- |
| held-out AUC | 0.5148 | 0.5159 |
| held-out RMSE (sqrt Brier) | 0.4999 | 0.4973 |
| held-out MAE | 0.4893 | 0.4859 |
| Brier score | 0.2499 | 0.2473 |
| Full RMSE (in-sample) | 0.4243 | 0.4186 |
| CV RMSE (time-series OOF) | 0.4978 | 0.4968 |
| RMSEratio (Full / CV) | 0.852 | 0.843 |

**Resampling robustness** -- 467 after-fee per-trade returns x 10,000 sims. ROBUST requires total P5 > 0, p(loss) < 5%, and sign-flip p-value < 0.05.
| metric | actual | P5 (worst) | median | P95 |
| --- | --- | --- | --- | --- |
| total return | -84.94% | -92.18% | -85.02% | -69.91% |
| max drawdown | -84.70% | -92.51% | -86.03% | - |
| Sharpe | -4.43 | -6.31 | -4.45 | - |

- p(loss) **100.0%**, sign-flip p-value **1.0000**  ->  **FRAGILE**

