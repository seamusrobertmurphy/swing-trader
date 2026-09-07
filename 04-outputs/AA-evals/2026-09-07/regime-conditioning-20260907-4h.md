# Regime conditioning ablation (2026-09-07) -- 4h all-market

Handoff Part 2: one model conditioned on observable regime state (the `f_rg_` block) vs the same model without it. Higher after-cost expectancy or a better worst-era (less reliance on one regime) means conditioning helps.

- regime block: 10 features ['f_rg_rv_short', 'f_rg_rv_long', 'f_rg_vol_regime', 'f_rg_drift_short', 'f_rg_drift_long', 'f_rg_efficiency', 'f_rg_updown', 'f_rg_ret_long', 'f_rg_btc_ret_long', 'f_rg_btc_regime']
- features: baseline 90, conditioned 100

| model | held-out | after-cost/trade | era mean | era worst | eras positive |
| --- | --- | --- | --- | --- | --- |
| baseline (no regime) | AUC 0.549, picks 0.273/base 0.254 | -0.382% | -0.202% | -0.316% | 0/3 |
| conditioned (+f_rg_) | AUC 0.555, picks 0.282/base 0.254 | -0.235% | -0.240% | -0.399% | 0/3 |

**Effect of conditioning** (two separate questions): cross-era STABILITY does not improve (worst-era -0.083pp, era-mean -0.038pp, eras-positive +0); after-cost EDGE improves (+0.147pp/trade). The point of Part 2 is the first: a model that generalizes across regimes rather than memorizing one. Both remain subject to the after-fee GO/NO-GO bar.

## Per-era after-cost (conditioned model)
| era | trades | after-cost/trade | win |
| --- | --- | --- | --- |
| 2017 launch run-up | 0 | - | - |
| 2018 bear | 0 | - | - |
| 2019-20 base | 0 | - | - |
| 2020-21 bull | 0 | - | - |
| 2021 top + chop | 0 | - | - |
| 2022 collapse | 2,069 | -0.399% | 0.32 |
| 2023-24 recovery | 3,503 | -0.126% | 0.37 |
| 2025-26 recent | 3,579 | -0.195% | 0.35 |

## Monte Carlo robustness & model performance (conditioned model, held-out confident trades)
**Model performance** -- the same caret-style scoreboard as the model-assessment table. RMSE and MAE are on predicted probabilities (RMSE = sqrt(Brier)); Full = in-sample on the training window, CV = time-series out-of-fold, RMSEratio = Full / CV (near 1 = stable, well below 1 = overfit). Lower RMSE and higher AUC are better.
| metric | baseline | conditioned |
| --- | --- | --- |
| held-out AUC | 0.5486 | 0.5551 |
| held-out RMSE (sqrt Brier) | 0.4844 | 0.4831 |
| held-out MAE | 0.4703 | 0.4673 |
| Brier score | 0.2346 | 0.2334 |
| Full RMSE (in-sample) | 0.4322 | 0.4280 |
| CV RMSE (time-series OOF) | 0.4793 | 0.4793 |
| RMSEratio (Full / CV) | 0.902 | 0.893 |

**Resampling robustness** -- 1,807 after-fee per-trade returns x 10,000 sims. ROBUST requires total P5 > 0, p(loss) < 5%, and sign-flip p-value < 0.05.
| metric | actual | P5 (worst) | median | P95 |
| --- | --- | --- | --- | --- |
| total return | -99.48% | -99.95% | -99.49% | -94.68% |
| max drawdown | -99.72% | -99.96% | -99.63% | - |
| Sharpe | -2.97 | -4.64 | -2.98 | - |

- p(loss) **100.0%**, sign-flip p-value **0.9979**  ->  **FRAGILE**

