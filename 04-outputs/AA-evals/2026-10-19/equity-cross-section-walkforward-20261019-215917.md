# Stock cross-section, kill harness, 19 October 2026 21:59

From April 2017 to July 2026, 112 month-ends on the stock panel, each month's eligible names were ranked by the signal and the top third held to the next month-end, charged 0.16 per cent. The spread is that return less the return of every eligible name. Median names a month 1472.

Candidate f_mst_dist, KILLED. 9 of 19 half-year folds had a positive spread (47% against the 60 per cent bar), and the mean monthly spread was -0.088%, t = -0.52, positive in 52% of months.

Control, 12-1 momentum, SURVIVES. 13 of 19 folds positive (68%), mean monthly spread +0.203%, t = 1.15.

The candidate's monthly spread correlated 0.42 with the control's, and on average 45% of the candidate's top third was also in momentum's top third.

## Folds

| fold | months | candidate top after cost | market | candidate spread | momentum spread |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2017H1 | 3 | +0.732% | +0.941% | -0.209% | -0.227% |
| 2017H2 | 6 | +2.010% | +1.890% | +0.120% | +0.467% |
| 2018H1 | 6 | +0.998% | +0.632% | +0.366% | +0.578% |
| 2018H2 | 6 | -2.212% | -1.782% | -0.430% | -0.377% |
| 2019H1 | 6 | +1.799% | +3.156% | -1.357% | +0.088% |
| 2019H2 | 6 | +0.880% | +1.325% | -0.446% | -0.205% |
| 2020H1 | 6 | -0.499% | -0.841% | +0.342% | +0.928% |
| 2020H2 | 6 | +5.401% | +4.656% | +0.744% | +0.368% |
| 2021H1 | 6 | +3.365% | +2.882% | +0.483% | +0.012% |
| 2021H2 | 6 | +0.386% | +0.646% | -0.260% | +0.086% |
| 2022H1 | 6 | -3.039% | -3.404% | +0.364% | +0.451% |
| 2022H2 | 6 | -0.262% | +1.157% | -1.419% | +0.244% |
| 2023H1 | 6 | +1.560% | +1.877% | -0.317% | -0.759% |
| 2023H2 | 6 | +1.070% | +1.555% | -0.485% | -0.312% |
| 2024H1 | 6 | +0.318% | +0.860% | -0.543% | +0.716% |
| 2024H2 | 6 | +1.456% | +1.427% | +0.030% | +0.421% |
| 2025H1 | 6 | +0.480% | +0.872% | -0.392% | -0.138% |
| 2025H2 | 6 | +2.869% | +1.717% | +1.152% | +0.358% |
| 2026H1 | 6 | +3.747% | +2.376% | +1.371% | +2.110% |
| 2026H2 | 1 | -6.359% | -1.205% | -5.154% | -5.960% |

The panel holds only stocks still listed, so both legs are flattered; the spread less so.

Run with `03-inputs/equity_cross_section_walkforward.py`, whose criteria were fixed before the first run.

