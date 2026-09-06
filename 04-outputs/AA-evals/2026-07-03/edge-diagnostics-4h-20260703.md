# Edge diagnostics (2026-07-03) -- 4h (60,000-row sample)

## Q1. Pre-cost edge (held-out, fees stripped)
- base rate 0.256 (majority-class accuracy 0.744, informational only)
- model: AUC 0.542 (vs 0.50), accuracy 0.583
- model picks: precision 0.315 vs base 0.256  ->  beats the real balance: True
- 1-bar persistence baseline: precision 0.260, pre-cost -0.078%/trade
- model pre-cost mean return per acted trade +0.223% on 1,007 trades; after-cost +0.023% (cost 0.20% round trip)
- **gate: PASS - a pre-cost edge exists to chase** (beats base True, beats persistence True)

## Q5. Edge stability across eras (after-cost, time-series out-of-fold)
| era | trades | after-cost / trade | win rate |
| --- | --- | --- | --- |
| 2017 launch run-up | 0 | - | - |
| 2018 bear | 0 | - | - |
| 2019-20 base | 0 | - | - |
| 2020-21 bull | 0 | - | - |
| 2021 top + chop | 0 | - | - |
| 2022 collapse | 1,257 | +0.006% | 0.37 |
| 2023-24 recovery | 1,225 | +0.055% | 0.40 |
| 2025-26 recent | 2,043 | -0.080% | 0.37 |

## Q6. Selectivity (after-cost return per trade vs confidence threshold)
![selectivity](edge-diagnostics-selectivity-4h-20260703.png)

| threshold | trades | after-cost / trade | total after-cost | win rate |
| --- | --- | --- | --- | --- |
| 0.450 | 25,758 | -0.165% | -4244.6% | 0.36 |
| 0.491 | 18,773 | -0.119% | -2242.3% | 0.37 |
| 0.532 | 12,229 | -0.046% | -560.2% | 0.37 |
| 0.573 | 6,951 | +0.008% | +53.2% | 0.38 |
| 0.614 | 3,531 | -0.011% | -39.5% | 0.38 |
| 0.655 | 1,481 | -0.035% | -51.4% | 0.37 |
| 0.695 | 596 | +0.060% | +36.0% | 0.38 |
| 0.736 | 211 | -0.130% | -27.5% | 0.39 |
| 0.777 | 71 | -0.130% | -9.3% | 0.44 |
| 0.818 | 22 | -0.998% | -21.9% | 0.36 |
| 0.859 | 4 | -0.329% | -1.3% | 0.50 |
| 0.900 | 1 | -5.156% | -5.2% | 0.00 |

**Selectivity reading:** after-cost return per trade rises AND crosses zero -- at p>=0.695 it is +0.060% on 596 trades. A selective operating point clears fees: tune that confidence threshold OUT-OF-SAMPLE (walk-forward) with a minimum-trade floor, judged on TOTAL after-cost P&L (best so far at p>=0.573), not per-trade alone. This is operating-point tuning, not a model retrain.

