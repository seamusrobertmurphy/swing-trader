# Regime conditioning ablation (2026-09-08) -- 4h all-market

Handoff Part 2: one model conditioned on observable regime state (the `f_rg_` block) vs the same model without it. Higher after-cost expectancy or a better worst-era (less reliance on one regime) means conditioning helps.

- regime block: 10 features ['f_rg_rv_short', 'f_rg_rv_long', 'f_rg_vol_regime', 'f_rg_drift_short', 'f_rg_drift_long', 'f_rg_efficiency', 'f_rg_updown', 'f_rg_ret_long', 'f_rg_btc_ret_long', 'f_rg_btc_regime']
- features: baseline 90, conditioned 100

| model | held-out | after-cost/trade | era mean | era worst | eras positive |
| --- | --- | --- | --- | --- | --- |
| baseline (no regime) | AUC 0.549, picks 0.273/base 0.254 | -0.382% | -0.112% | -0.378% | 1/4 |
| conditioned (+f_rg_) | AUC 0.555, picks 0.282/base 0.254 | -0.235% | -0.040% | -0.369% | 1/4 |

**Effect of conditioning** (two separate questions): cross-era STABILITY IMPROVES (worst-era +0.009pp, era-mean +0.072pp, eras-positive +0); after-cost EDGE improves (+0.147pp/trade). The point of Part 2 is the first: a model that generalizes across regimes rather than memorizing one. Both remain subject to the after-fee GO/NO-GO bar.

## Per-era after-cost (conditioned model)
| era | trades | after-cost/trade | win |
| --- | --- | --- | --- |
| 2017 launch run-up | 0 | - | - |
| 2018 bear | 0 | - | - |
| 2019-20 base | 0 | - | - |
| 2020-21 bull | 0 | - | - |
| 2021 top + chop | 760 | +0.536% | 0.45 |
| 2022 collapse | 2,650 | -0.151% | 0.36 |
| 2023-24 recovery | 3,378 | -0.175% | 0.36 |
| 2025-26 recent | 3,592 | -0.369% | 0.33 |

## Monte Carlo robustness & model performance (conditioned model, held-out confident trades)
**Model performance** -- the same caret-style scoreboard as the model-assessment table. RMSE and MAE are on predicted probabilities (RMSE = sqrt(Brier)); Full = in-sample on the training window, CV = time-series out-of-fold, RMSEratio = CV RMSE / Full RMSE (near 1 = stable, above 1.1 = rejected as overfit). Lower RMSE and higher AUC are better.
| metric | baseline | conditioned |
| --- | --- | --- |
| held-out AUC | 0.5486 | 0.5551 |
| held-out RMSE (sqrt Brier) | 0.4844 | 0.4831 |
| held-out MAE | 0.4703 | 0.4673 |
| Brier score | 0.2346 | 0.2334 |
| Full RMSE (in-sample) | 0.4322 | 0.4280 |
| CV RMSE (time-series OOF) | 0.4805 | 0.4800 |
| RMSEratio (CV / Full) | 1.112 | 1.122 |

**Resampling robustness** -- 1,807 after-fee per-trade returns x 10,000 sims. ROBUST requires total P5 > 0, p(loss) < 5%, and sign-flip p-value < 0.05.
| metric | actual | P5 (worst) | median | P95 |
| --- | --- | --- | --- | --- |
| total return | -99.48% | -99.95% | -99.49% | -94.68% |
| max drawdown | -99.72% | -99.96% | -99.63% | - |
| Sharpe | -2.97 | -4.64 | -2.98 | - |

- p(loss) **100.0%**, sign-flip p-value **0.9979**  ->  **FRAGILE**

