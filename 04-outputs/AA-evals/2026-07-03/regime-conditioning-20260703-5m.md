# Regime conditioning ablation (2026-07-03) -- 5m (30,000-row sample)

Handoff Part 2: one model conditioned on observable regime state (the `f_rg_` block) vs the same model without it. Higher after-cost expectancy or a better worst-era (less reliance on one regime) means conditioning helps.

- regime block: 10 features ['f_rg_rv_short', 'f_rg_rv_long', 'f_rg_vol_regime', 'f_rg_drift_short', 'f_rg_drift_long', 'f_rg_efficiency', 'f_rg_updown', 'f_rg_ret_long', 'f_rg_btc_ret_long', 'f_rg_btc_regime']
- features: baseline 86, conditioned 96

| model | held-out | after-cost/trade | era mean | era worst | eras positive |
| --- | --- | --- | --- | --- | --- |
| baseline (no regime) | AUC 0.516, picks 0.402/base 0.391 | -0.215% | -0.206% | -0.252% | 0/5 |
| conditioned (+f_rg_) | AUC 0.503, picks 0.378/base 0.391 | -0.238% | -0.217% | -0.252% | 0/5 |

**Effect of conditioning** (two separate questions): cross-era STABILITY IMPROVES (worst-era +0.000pp, era-mean -0.010pp, eras-positive +0); after-cost EDGE does not lift (-0.023pp/trade). The point of Part 2 is the first: a model that generalizes across regimes rather than memorizing one. Both remain subject to the after-fee GO/NO-GO bar.

## Per-era after-cost (conditioned model)
| era | trades | after-cost/trade | win |
| --- | --- | --- | --- |
| 2017 launch run-up | 0 | - | - |
| 2018 bear | 0 | - | - |
| 2019-20 base | 0 | - | - |
| 2020-21 bull | 146 | -0.247% | 0.37 |
| 2021 top + chop | 282 | -0.204% | 0.41 |
| 2022 collapse | 603 | -0.252% | 0.34 |
| 2023-24 recovery | 816 | -0.184% | 0.28 |
| 2025-26 recent | 1,108 | -0.196% | 0.35 |

## Monte Carlo robustness & model performance (conditioned model, held-out confident trades)
**Model performance** -- the same caret-style scoreboard as the model-assessment table. RMSE and MAE are on predicted probabilities (RMSE = sqrt(Brier)); Full = in-sample on the training window, CV = time-series out-of-fold, RMSEratio = Full / CV (near 1 = stable, well below 1 = overfit). Lower RMSE and higher AUC are better.
| metric | baseline | conditioned |
| --- | --- | --- |
| held-out AUC | 0.5158 | 0.5033 |
| held-out RMSE (sqrt Brier) | 0.5027 | 0.5039 |
| held-out MAE | 0.4954 | 0.4966 |
| Brier score | 0.2527 | 0.2539 |
| Full RMSE (in-sample) | 0.4267 | 0.4267 |
| CV RMSE (time-series OOF) | 0.5053 | 0.5054 |
| RMSEratio (Full / CV) | 0.844 | 0.844 |

**Resampling robustness** -- 502 after-fee per-trade returns x 10,000 sims. ROBUST requires total P5 > 0, p(loss) < 5%, and sign-flip p-value < 0.05.
| metric | actual | P5 (worst) | median | P95 |
| --- | --- | --- | --- | --- |
| total return | -69.88% | -74.67% | -69.89% | -64.34% |
| max drawdown | -70.24% | -74.67% | -69.97% | - |
| Sharpe | -11.47 | -13.50 | -11.51 | - |

- p(loss) **100.0%**, sign-flip p-value **1.0000**  ->  **FRAGILE**

