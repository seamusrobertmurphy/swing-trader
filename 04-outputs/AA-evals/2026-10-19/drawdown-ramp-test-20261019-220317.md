# Drawdown ramp on the momentum basket, 19 October 2026 22:03

A daily replay of the live book from 17 January 2017 to 19 October 2026, weekly rebalances on the first session of each week, top decile of the 500 most traded eligible names by 12-1 momentum, 90 per cent invested, 8 basis points on every change in weight. The ramp cuts only new positions, and only when the 5-day book return is below -5 per cent.

Verdict, ADOPT B 10% per 1%. A ramp was to be adopted only with both a higher Sharpe ratio and a smaller maximum drawdown than the book without it.

| version | growth a year | volatility | Sharpe | maximum drawdown | grew | weeks the ramp bit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A no ramp | 24.7% | 32.7% | 0.84 | -38.9% | 8.57x | 0 of 510 |
| B 10% per 1% | 24.6% | 32.4% | 0.84 | -38.8% | 8.56x | 50 of 510 |
| C 1% per 1% | 24.6% | 32.6% | 0.84 | -38.9% | 8.57x | 50 of 510 |

The panel holds only stocks still listed, which flatters all three versions alike.

Run with `03-inputs/drawdown_ramp_test.py`, whose rule was fixed before the first run.

