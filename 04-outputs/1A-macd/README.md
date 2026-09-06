# macd_lab — guarded MACD metric and chart

A self-contained extension of the MACD the project already computes in
`inputs/build_dataset.py`. It is isolated in this folder and touches none of the
existing scripts, notebook, config, or model, so the operator can adopt it
piecemeal.

## What it adds

The base metric is unchanged: MACD line is EMA(12) minus EMA(26), the signal
line is the 9-period EMA of that, and the histogram is the gap between them. The
recursion matches the existing code to 13 decimal places, verified against the
project's own `outputs/BTCUSDT_1h.csv`.

On top of that it builds three things the raw metric lacks.

First, the windows are tunable. Everything reads from one `MACDConfig`, so a
faster 8/21/5 variant for crypto's volatility is a one-line change rather than a
rewrite.

Second, the crossover signal is guarded. A bare "MACD crosses its signal line"
event fires constantly in chop, most of it noise near the zero line. The guard
suppresses any cross whose histogram sits inside an error band, where the band is
sized to the histogram's own recent volatility (`noise_k` standard deviations
over `noise_window` bars) rather than a fixed price amount, and it requires the
histogram to hold its new sign for `confirm_bars` bars. On six months of hourly
BTC this filtered 81 percent of raw sell crosses and 82 percent of raw buys,
keeping only the high-conviction ones, and the guarded set is always a strict
subset of the raw crosses. This is the sell guardrail you flagged.

Third, it detects divergence. When price prints a higher high but MACD prints a
lower high, the uptrend is losing strength (bearish); the mirror case is bullish.
Pivots are confirmed `pivot_window` bars after they form, and the signal is
stamped at that confirmation bar, so nothing in the output ever peeks ahead. A
divergence that lines up with a guarded cross raises that cross's conviction
score.

Every column is causal: recomputing on a truncated history leaves the earlier
signals bit-for-bit identical, which the verification step checks directly.

## The chart

`macd-dashboard.html` is one interactive figure with a dropdown over all ten
coins (single selectable symbol, as requested). Price candles sit on top with
guarded buy and sell triangles and divergence diamonds; the MACD panel below
carries the line, the signal line, and a four-colour histogram. The colours
encode the convergence reading directly: a bar is bright when momentum is
building and pale when it is fading toward zero, which is the early-warning the
histogram is meant to give. Hover is unified across both panels and there is a
range slider for scrubbing. The file embeds plotly inline, so it opens with no
internet.

`preview_btc.png` is a static matplotlib cross-check of the same signals.

## Run it

```
python macd_lab/build_macd_charts.py
```

It pulls fresh hourly candles via ccxt for BTC ETH SOL BNB XRP ADA AVAX LINK LTC
DOGE and rewrites the HTML. Hourly is the right cadence here: a daily MACD only
updates once a day, too slow to act on intraday, whereas the hourly bar closes
every hour. If the exchange is unreachable it falls back to the local
`outputs/BTCUSDT_1h_raw.csv` and still produces a chart. To refresh on a
schedule, wire this one command into a cron or a scheduled task.

## Feeding the model

`macd.macd_features(df)` returns twelve scale-invariant, causal columns built to
the project's "no raw price in a feature" rule, so they drop straight into
`compute_features`:

| column | meaning |
|---|---|
| `f_macd_hist` | histogram / close (matches the existing feature) |
| `f_macd_line` | MACD line / close |
| `f_macd_signal` | signal line / close |
| `f_macd_below_zero` | MACD line below zero (flag) |
| `f_macd_cross_state` | MACD above its signal line (flag) |
| `f_macd_bars_since_cross` | bars since the last crossover, scaled by the slow span |
| `f_macd_hist_slope` | one-bar change in the histogram / close |
| `f_macd_guarded_buy` | guarded bullish crossover (flag) |
| `f_macd_guarded_sell` | guarded bearish crossover (flag) |
| `f_macd_bear_div` | confirmed bearish divergence (flag) |
| `f_macd_bull_div` | confirmed bullish divergence (flag) |
| `f_macd_strength` | conviction score, minus one to plus one |

Integration is two lines:

```python
from macd_lab.macd import macd_features, MACDConfig
df = df.join(macd_features(df, MACDConfig()))
```

## Honest limits

MACD lags by construction; the signal line is an average of an average, so the
guarded sell confirms a turn rather than calling its top, visible in the preview
where the June 18 sell lands on the drop, not before it. The guardrails cut false
signals but raise this lag, the classic trade-off. None of this is a backtested
edge: it is a cleaner, better-instrumented indicator, not a strategy. Size, fees,
and the go/no-go decision remain the operator's, and nothing here arms an order
or touches the live switch.
