# Three-way outcome, kill harness, 19 October 2026 21:37

The 4-hour panel, 125,232 screened rows on 312 coins from 16 December 2017 to 19 June 2026, was split into half-year folds. Each fold was scored by a logistic regression trained on every earlier row, with a break-even band of 0.20 per cent and 0.20 per cent cost a trade. A trade was taken when P(bullish) minus P(bearish) reached the training rows' own top fifth, and only once the previous trade on that coin had run its 48 hours.

Verdict, KILLED. The mean trade made -0.185% after cost.

Across all folds 6,745 trades averaged -0.185% after cost, standard deviation +7.839%, t = -1.94. Taking every screened row on the same non-overlapping rule averaged -0.262% on 20,651 trades, which is what the market gave without the model.

## Folds

| fold | training rows | coins | trades | after cost | trades won | every row | every-row trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2020H1 | 6,066 | 15 | 143 | +0.076% | 58% | -0.008% | 417 |
| 2020H2 | 8,765 | 23 | 150 | +1.418% | 53% | +0.762% | 594 |
| 2021H1 | 12,399 | 93 | 473 | -1.313% | 42% | +1.474% | 1185 |
| 2021H2 | 17,605 | 135 | 759 | +0.518% | 53% | -0.316% | 2843 |
| 2022H1 | 32,171 | 116 | 849 | -2.009% | 38% | -1.701% | 2028 |
| 2022H2 | 44,048 | 68 | 273 | +0.211% | 45% | -0.117% | 1266 |
| 2023H1 | 51,886 | 92 | 449 | -0.021% | 48% | -0.210% | 1450 |
| 2023H2 | 60,836 | 119 | 565 | +0.453% | 46% | +0.528% | 1328 |
| 2024H1 | 68,560 | 157 | 719 | +0.018% | 50% | -0.354% | 2479 |
| 2024H2 | 82,733 | 143 | 720 | +0.435% | 51% | +0.159% | 2294 |
| 2025H1 | 95,393 | 114 | 584 | +0.238% | 48% | -0.674% | 1980 |
| 2025H2 | 106,752 | 99 | 569 | -0.143% | 45% | -0.626% | 1871 |
| 2026H1 | 118,823 | 61 | 492 | -0.461% | 43% | -0.526% | 916 |

A fold is eligible with at least 8 trades. 13 were eligible and 8 of them were positive after cost.

## Coins

The ten coins that added most and the five that took most, summed after cost.

| coin | trades | mean after cost | sum after cost |
| --- | ---: | ---: | ---: |
| NEAR/USDT | 116 | +1.378% | +159.830% |
| TRX/USDT | 238 | +0.635% | +151.191% |
| DOGE/USDT | 232 | +0.630% | +146.137% |
| WLD/USDT | 44 | +2.924% | +128.661% |
| SHIB/USDT | 131 | +0.891% | +116.724% |
| ETH/USDT | 378 | +0.257% | +97.308% |
| WIF/USDT | 36 | +2.609% | +93.923% |
| SEI/USDT | 26 | +3.375% | +87.756% |
| AVAX/USDT | 172 | +0.466% | +80.073% |
| PNUT/USDT | 4 | +18.581% | +74.325% |
| ATOM/USDT | 87 | -1.264% | -109.961% |
| XRP/USDT | 292 | -0.392% | -114.501% |
| CHZ/USDT | 46 | -2.729% | -125.526% |
| ICP/USDT | 44 | -3.169% | -139.417% |
| GALA/USDT | 48 | -3.526% | -169.244% |

81 of 220 coins summed above zero.

Ran in 52 seconds with `03-inputs/threeway_walkforward.py`, whose kill criteria were fixed before the first run.

