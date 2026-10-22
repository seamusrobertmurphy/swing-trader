# Market switch for the weekly stock book, 21 October 2026 17:12

A daily replay of the live book, trimming on, 98% in stocks, from 17 January 2017 to 19 October 2026.

Verdict, KEEP A no switch (live). Another version was to be adopted only with a higher Sharpe ratio and higher growth a year than the live book, and beating it in at least half the calendar years.

| version | growth a year | volatility | Sharpe | maximum drawdown | grew | cost over the run | stops | weeks in cash | years ahead of live |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A no switch (live) | 28.2% | 32.2% | 0.935 | -37.2% | 11.28x | 10.6% | 0 | 0 |  |
| B 200-day switch | 18.2% | 28.0% | 0.738 | -37.3% | 5.10x | 10.2% | 0 | 86 | 0 of 10 |

| year | A no switch (live) | B 200-day switch |
| --- | ---: | ---: |
| 2017 | 21.7% | 21.7% |
| 2018 | -3.3% | -9.4% |
| 2019 | 30.5% | 3.4% |
| 2020 | 92.6% | 78.5% |
| 2021 | 23.2% | 23.1% |
| 2022 | -6.9% | -8.7% |
| 2023 | 26.4% | 12.8% |
| 2024 | 43.1% | 42.4% |
| 2025 | 54.1% | 34.5% |
| 2026 | 19.4% | 3.2% |

Cash earns nothing. The panel holds only stocks still listed, which flatters every version alike.

Run with `03-inputs/risk_rules_test.py`, whose rules were fixed before the first run.

