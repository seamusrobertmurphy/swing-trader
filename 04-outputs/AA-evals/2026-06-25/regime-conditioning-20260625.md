# Regime conditioning ablation (2026-06-25) -- 5m all-market

Handoff Part 2: one model conditioned on observable regime state (the `f_rg_` block) vs the same model without it. Higher after-cost expectancy or a better worst-era (less reliance on one regime) means conditioning helps.

- regime block: 10 features ['f_rg_rv_short', 'f_rg_rv_long', 'f_rg_vol_regime', 'f_rg_drift_short', 'f_rg_drift_long', 'f_rg_efficiency', 'f_rg_updown', 'f_rg_ret_long', 'f_rg_btc_ret_long', 'f_rg_btc_regime']
- features: baseline 86, conditioned 96

| model | held-out | after-cost/trade | era mean | era worst | eras positive |
| --- | --- | --- | --- | --- | --- |
| baseline (no regime) | AUC 0.515, picks 0.433/base 0.380 | -0.172% | -0.170% | -0.182% | 0/5 |
| conditioned (+f_rg_) | AUC 0.516, picks 0.435/base 0.380 | -0.167% | -0.170% | -0.192% | 0/5 |

**Effect of conditioning** (two separate questions): cross-era STABILITY does not improve (worst-era -0.009pp, era-mean -0.001pp, eras-positive +0); after-cost EDGE improves (+0.005pp/trade). The point of Part 2 is the first: a model that generalizes across regimes rather than memorizing one. Both remain subject to the after-fee GO/NO-GO bar.

## Per-era after-cost (conditioned model)
| era | trades | after-cost/trade | win |
| --- | --- | --- | --- |
| 2017 launch run-up | 0 | - | - |
| 2018 bear | 0 | - | - |
| 2019-20 base | 0 | - | - |
| 2020-21 bull | 8,390 | -0.170% | 0.42 |
| 2021 top + chop | 14,409 | -0.165% | 0.43 |
| 2022 collapse | 24,227 | -0.174% | 0.43 |
| 2023-24 recovery | 5,924 | -0.151% | 0.46 |
| 2025-26 recent | 6,162 | -0.192% | 0.42 |
