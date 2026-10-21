# Day trades on stocks, 21 October 2026 16:21

Same-day, long-only trades on 3-minute bars, 04 January 2016 to 25 September 2026, 16 basis points a round trip. A rule passes with a positive mean daily return after cost, a t-statistic of at least 2, and at least 60 per cent of half-year folds positive.

| rule | trades | names | mean trade before cost | mean trade after cost | daily book after cost | t | half-years positive | growth a year | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Intraday momentum, last 30 minutes | 437,204 | 356 | -0.011% | -0.171% | -0.168% | -33.63 | 0 of 22 | -34.6% | FAIL |
| Opening range breakout | 502,574 | 356 | +0.049% | -0.111% | -0.188% | -10.10 | 1 of 22 | -38.4% | FAIL |

Run with `03-inputs/day_trade_test.py`, whose rules were fixed before the first run.

