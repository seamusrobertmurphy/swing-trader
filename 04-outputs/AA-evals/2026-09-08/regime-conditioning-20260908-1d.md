# Regime conditioning ablation (2026-09-08) -- 1d all-market

Handoff Part 2: one model conditioned on observable regime state (the `f_rg_` block) vs the same model without it. Higher after-cost expectancy or a better worst-era (less reliance on one regime) means conditioning helps.

- regime block: 10 features ['f_rg_rv_short', 'f_rg_rv_long', 'f_rg_vol_regime', 'f_rg_drift_short', 'f_rg_drift_long', 'f_rg_efficiency', 'f_rg_updown', 'f_rg_ret_long', 'f_rg_btc_ret_long', 'f_rg_btc_regime']
- features: baseline 94, conditioned 104

| model | held-out | after-cost/trade | era mean | era worst | eras positive |
| --- | --- | --- | --- | --- | --- |
| baseline (no regime) | AUC 0.521, picks 0.173/base 0.147 | -1.072% | +1.527% | -3.839% | 2/4 |
| conditioned (+f_rg_) | AUC 0.525, picks 0.171/base 0.147 | -1.220% | +1.876% | -2.373% | 3/4 |

**Effect of conditioning** (two separate questions): cross-era STABILITY IMPROVES (worst-era +1.466pp, era-mean +0.349pp, eras-positive +1); after-cost EDGE does not lift (-0.149pp/trade). The point of Part 2 is the first: a model that generalizes across regimes rather than memorizing one. Both remain subject to the after-fee GO/NO-GO bar.

## Per-era after-cost (conditioned model)
| era | trades | after-cost/trade | win |
| --- | --- | --- | --- |
| 2017 launch run-up | 0 | - | - |
| 2018 bear | 0 | - | - |
| 2019-20 base | 0 | - | - |
| 2020-21 bull | 0 | - | - |
| 2021 top + chop | 70 | +8.923% | 0.57 |
| 2022 collapse | 604 | -2.373% | 0.21 |
| 2023-24 recovery | 370 | +0.613% | 0.35 |
| 2025-26 recent | 597 | +0.342% | 0.30 |

## Monte Carlo robustness & model performance (conditioned model, held-out confident trades)
**Model performance** -- the same caret-style scoreboard as the model-assessment table. RMSE and MAE are on predicted probabilities (RMSE = sqrt(Brier)); Full = in-sample on the training window, CV = time-series out-of-fold, RMSEratio = CV RMSE / Full RMSE (near 1 = stable, above 1.1 = rejected as overfit). Lower RMSE and higher AUC are better.
| metric | baseline | conditioned |
| --- | --- | --- |
| held-out AUC | 0.5210 | 0.5252 |
| held-out RMSE (sqrt Brier) | 0.4743 | 0.4665 |
| held-out MAE | 0.4256 | 0.4212 |
| Brier score | 0.2250 | 0.2176 |
| Full RMSE (in-sample) | 0.3171 | 0.3084 |
| CV RMSE (time-series OOF) | 0.4482 | 0.4475 |
| RMSEratio (CV / Full) | 1.413 | 1.451 |

**Resampling robustness** -- 374 after-fee per-trade returns x 10,000 sims. ROBUST requires total P5 > 0, p(loss) < 5%, and sign-flip p-value < 0.05.
| metric | actual | P5 (worst) | median | P95 |
| --- | --- | --- | --- | --- |
| total return | -99.74% | -99.98% | -99.75% | -96.25% |
| max drawdown | -99.93% | -99.98% | -99.82% | - |
| Sharpe | -2.70 | -4.65 | -2.72 | - |

- p(loss) **100.0%**, sign-flip p-value **0.9963**  ->  **FRAGILE**

