# Regime conditioning ablation (2026-07-03) -- 4h (30,000-row sample)

Handoff Part 2: one model conditioned on observable regime state (the `f_rg_` block) vs the same model without it. Higher after-cost expectancy or a better worst-era (less reliance on one regime) means conditioning helps.

- regime block: 10 features ['f_rg_rv_short', 'f_rg_rv_long', 'f_rg_vol_regime', 'f_rg_drift_short', 'f_rg_drift_long', 'f_rg_efficiency', 'f_rg_updown', 'f_rg_ret_long', 'f_rg_btc_ret_long', 'f_rg_btc_regime']
- features: baseline 90, conditioned 100

| model | held-out | after-cost/trade | era mean | era worst | eras positive |
| --- | --- | --- | --- | --- | --- |
| baseline (no regime) | AUC 0.544, picks 0.329/base 0.262 | +0.256% | +0.092% | +0.052% | 3/3 |
| conditioned (+f_rg_) | AUC 0.536, picks 0.311/base 0.262 | +0.110% | +0.148% | +0.115% | 3/3 |

**Effect of conditioning** (two separate questions): cross-era STABILITY IMPROVES (worst-era +0.063pp, era-mean +0.056pp, eras-positive +0); after-cost EDGE does not lift (-0.146pp/trade). The point of Part 2 is the first: a model that generalizes across regimes rather than memorizing one. Both remain subject to the after-fee GO/NO-GO bar.

## Per-era after-cost (conditioned model)
| era | trades | after-cost/trade | win |
| --- | --- | --- | --- |
| 2017 launch run-up | 0 | - | - |
| 2018 bear | 0 | - | - |
| 2019-20 base | 0 | - | - |
| 2020-21 bull | 0 | - | - |
| 2021 top + chop | 0 | - | - |
| 2022 collapse | 495 | +0.148% | 0.40 |
| 2023-24 recovery | 632 | +0.181% | 0.40 |
| 2025-26 recent | 995 | +0.115% | 0.38 |

## Monte Carlo robustness & model performance (conditioned model, held-out confident trades)
**Model performance** -- the same caret-style scoreboard as the model-assessment table. RMSE and MAE are on predicted probabilities (RMSE = sqrt(Brier)); Full = in-sample on the training window, CV = time-series out-of-fold, RMSEratio = Full / CV (near 1 = stable, well below 1 = overfit). Lower RMSE and higher AUC are better.
| metric | baseline | conditioned |
| --- | --- | --- |
| held-out AUC | 0.5443 | 0.5359 |
| held-out RMSE (sqrt Brier) | 0.4822 | 0.4820 |
| held-out MAE | 0.4661 | 0.4659 |
| Brier score | 0.2325 | 0.2323 |
| Full RMSE (in-sample) | 0.4032 | 0.4015 |
| CV RMSE (time-series OOF) | 0.4835 | 0.4824 |
| RMSEratio (Full / CV) | 0.834 | 0.832 |

**Resampling robustness** -- 492 after-fee per-trade returns x 10,000 sims. ROBUST requires total P5 > 0, p(loss) < 5%, and sign-flip p-value < 0.05.
| metric | actual | P5 (worst) | median | P95 |
| --- | --- | --- | --- | --- |
| total return | +9.72% | -76.74% | +6.44% | +428.04% |
| max drawdown | -76.17% | -85.76% | -62.68% | - |
| Sharpe | 0.56 | -1.18 | 0.53 | - |

- p(loss) **47.4%**, sign-flip p-value **0.2908**  ->  **FRAGILE**

