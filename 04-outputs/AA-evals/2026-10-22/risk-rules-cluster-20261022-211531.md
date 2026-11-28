# A tighter limit on similar stocks for the weekly stock book, 22 October 2026 21:15

A daily replay of the live book, trimming on, 98% in stocks, from 17 January 2017 to 19 October 2026.

Verdict, KEEP A 0.7 and 20% (live). Another version was to be adopted only with a higher Sharpe ratio and higher growth a year than the live book, and beating it in at least half the calendar years.

| version | growth a year | volatility | Sharpe | maximum drawdown | grew | cost over the run | stops | weeks in cash | years ahead of live |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A 0.7 and 20% (live) | 27.8% | 31.6% | 0.937 | -36.9% | 10.97x | 11.1% | 233 | 0 |  |
| B 0.5 and 20% | 25.3% | 27.9% | 0.949 | -32.4% | 9.00x | 15.5% | 212 | 0 | 5 of 10 |
| C 0.7 and 10% | 27.1% | 31.1% | 0.930 | -37.1% | 10.35x | 11.9% | 232 | 0 | 5 of 10 |

| year | A 0.7 and 20% (live) | B 0.5 and 20% | C 0.7 and 10% |
| --- | ---: | ---: | ---: |
| 2017 | 22.0% | 23.6% | 24.0% |
| 2018 | -3.8% | -6.6% | -4.3% |
| 2019 | 30.3% | 26.4% | 30.4% |
| 2020 | 98.9% | 107.1% | 102.6% |
| 2021 | 21.2% | 22.0% | 23.6% |
| 2022 | -6.9% | -6.7% | -10.0% |
| 2023 | 26.6% | 24.1% | 27.0% |
| 2024 | 42.4% | 42.5% | 42.3% |
| 2025 | 53.7% | 32.2% | 43.7% |
| 2026 | 15.4% | 11.9% | 14.4% |

Cash earns nothing. The panel holds only stocks still listed, which flatters every version alike.

Run with `03-inputs/risk_rules_test.py`, whose rules were fixed before the first run.

