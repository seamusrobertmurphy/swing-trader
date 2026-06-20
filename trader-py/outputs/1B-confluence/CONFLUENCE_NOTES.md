# Confluence engine — notes and honest results

One signal built from four. Each method reads the same candles and is reduced to a
stance at every bar: +1 bullish, -1 bearish, 0 neutral. The composite is their
weighted sum. A trade fires only when enough of them agree. This is the guardrail
idea from the MACD work carried across indicators: no single method trades, the
agreement does.

## The four votes

MACD uses the guarded crossover from `macd_lab`, carried forward as a regime: after
a guarded buy the stance stays +1 until a guarded sell flips it. MA crossover is
the plain fast-over-slow test from the MA-crossover notebook, +1 when the 20-period
SMA is above the 50, -1 below. Fibonacci is contextual: on a rising leg, price
pulled back into the 0.5-0.618 golden pocket votes +1 (buy the dip); on a falling
leg, price bounced into that pocket votes -1 (sell the rip); otherwise 0. Candles
are the corrected engulfing pattern from the candle notebook, +1 on a bullish
engulfing and -1 on bearish, held live for a few bars then allowed to lapse.

The candle notebook had a real bug, a positional column rename that swapped open and
close, so its pattern logic was reading the wrong fields. The version here uses the
standard engulfing definition on the correct columns.

## The rule

```
score = w_macd*MACD + w_ma*MA + w_fib*Fib + w_candle*Candle      (weights default 1)
BUY  fires when score first reaches +threshold   (default +2)
SELL fires when score first reaches -threshold   (default -2)
```

Threshold 2 means at least two methods agree and nothing strong opposes. Raise it
to 3 for stricter agreement and fewer trades. Everything is causal: each stance at
bar i uses only bars up to i, so the backtest reflects what was knowable live. Fires
are edge-triggered on the score crossing the threshold, so the dashboard shows more
markers than the long-flat backtest executes, since a second buy while already long
does not open a new position.

## Honest results, in-sample

Hourly data, the ten-coin universe, about 1000 bars (~41 days), 0.1% fee per side,
long-flat, threshold 2. This window was a broad crypto downtrend.

| coin | strategy | buy & hold | trades | win % | max DD |
|---|---|---|---|---|---|
| BTC | -1.4% | -21.3% | 4 | 50 | -7.3% |
| ETH | -9.2% | -26.1% | 5 | 20 | -16.1% |
| SOL | -19.8% | -22.1% | 6 | 33 | -36.9% |
| BNB | -0.9% | -9.9% | 5 | 40 | -6.7% |
| XRP | -6.3% | -17.9% | 4 | 50 | -15.5% |
| ADA | -16.9% | -38.2% | 5 | 20 | -22.0% |
| AVAX | -8.0% | -33.6% | 6 | 33 | -16.7% |
| LINK | -19.7% | -20.3% | 7 | 29 | -25.4% |
| LTC | -10.1% | -23.4% | 4 | 25 | -17.1% |
| DOGE | -9.2% | -22.6% | 3 | 33 | -15.1% |
| mean | -10.1% | -23.5% | | | |

Read it plainly. The engine lost money on every coin, but lost roughly half of what
holding lost, because staying flat through the downtrend avoided the worst of it.
That is a drawdown-reduction property, not an edge. Beating buy-and-hold by being
absent during a fall is easy and does not survive into a rising or sideways market,
where sitting flat means missing gains. Win rates of 20 to 50 percent confirm there
is no demonstrated predictive skill here yet. This matches the project's standing
NO-GO finding: cleaner instrumentation, still no proven edge.

These are in-sample numbers over a single short, one-directional window. They tell
you the rule does something coherent, not that it will keep working.

## What would make this honest enough to consider

Walk-forward is the next step the data has now earned: split each coin's history
into rolling train and test segments, choose the weights and threshold on train
only, score once on the untouched test segment, repeat forward, and report only the
out-of-sample aggregate with fees. Test across regimes, not just this falling one,
so a bull and a sideways stretch are included. Add a stop and a take-profit, since a
flat-long rule with no risk control flatters drawdown. Only if the out-of-sample,
multi-regime, after-fees result clearly beats both buy-and-hold and a coin-flip is
any of this worth real money, and even then the operator owns the decision and the
live switch stays off.

## Files

`confluence.py` holds `ConfluenceConfig` (windows, weights, threshold), the four
stance functions, `compute_confluence`, and the `backtest`. `build_confluence.py`
draws the three-panel dashboard with the agreement ribbon. It imports `macd_lab` and
`fib_lab` directly, so those two folders must sit alongside this one.
