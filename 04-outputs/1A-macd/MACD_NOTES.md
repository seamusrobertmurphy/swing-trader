# MACD — preserved reference notes

Working notes for the project's MACD metric. Compiled from Commodity.com (Lawrence
Pines), GoodCrypto, and TradingSim, plus the annotated charts collected during
research. Ties back to the implementation in `macd.py`.

MACD stands for Moving Average Convergence Divergence. Gerald Appel, 1970s. It is
a momentum and trend tool, plotted in its own panel below price rather than on the
candles, which keeps the price chart clean.

## Anatomy

Three parts, nothing more.

The MACD line is the 12-period EMA minus the 26-period EMA. The signal line, which
some sources call the trigger line or the EMA line, is the 9-period EMA of the MACD
line. The histogram is the MACD line minus the signal line, drawn as bars around a
zero line.

Because the MACD line is fast EMA minus slow EMA, it crosses its own zero line at
the same moment the 12-EMA crosses the 26-EMA on the price chart. Above zero the
short-term trend leads up; below zero it leads down.

## Three ways to read it

**Crossovers.** The primary signal. A possible buy is the MACD line crossing above
the signal line; a possible sell is the MACD line crossing below it. A second,
slower layer is the zero-line cross: MACD above zero is bullish context, below zero
bearish. The signal-line cross fires earlier than the zero cross and catches more
of the move, at the cost of more false starts.

**Histogram.** The histogram is the distance between the two lines, so it crosses
zero exactly when the lines cross. Its height is momentum. A growing histogram
means the move is accelerating (the source calls this divergence of the lines). A
shrinking histogram means momentum is fading and the lines are converging, which is
the earliest warning of a turn: a histogram rolling over from a peak toward zero
often precedes the actual crossover by several bars. Histogram tops are marked T,
bottoms B, and they track price peaks and troughs closely.

**Divergence.** The highest-value and least mechanical read. Compare the swing
highs and lows of price against the swing highs and lows of the MACD. When they
disagree, momentum is leaving the trend before price shows it. Bearish divergence:
price prints a higher high while MACD prints a lower high, warning an uptrend is
hollow. Bullish divergence: price prints a lower low while MACD prints a higher low,
warning a downtrend is exhausting. Divergence is a reason to protect a position
before profits erode, not a precise entry.

## Divergence and convergence quadrants

![divergence quadrants](/outputs/macd_lab/divergence_matrix.png)

The full taxonomy compares the last two price swings against the matching MACD
swings. Notation: HH higher high, HL higher low, LH lower high, LL lower low.

| Price | MACD | Source term | Standard term | Reading | Action |
|---|---|---|---|---|---|
| Higher high | Lower high | Divergence | Regular bearish | reversal / retracement | SELL |
| Lower high | Higher high | Convergence | Hidden bearish | trend continuation (down) | SELL |
| Higher low | Lower low | Divergence | Hidden bullish | trend continuation (up) | BUY |
| Lower low | Higher low | Convergence | Regular bullish | reversal / retracement | BUY |

Two cautions from the research. First, terminology is not standardised: GoodCrypto
defines "divergence" as price stronger than the indicator and "convergence" as
price weaker, which is the geometry above but the opposite word to how many texts
use them. Read the HH/HL/LH/LL pattern, not the label. Second, a single chart can
show mixed signals: in their BTC example the peaks diverged while the troughs
converged, netting out bearish only because the peak structure dominated. Weigh
both swing series, do not act on one line in isolation.

## Crypto specifics

MACD is well respected and works on BTC and ETH as on any market, but it is one
input, not a system, and no single strategy is right every time. Pair it with
position sizing and a stop.

A practical crypto technique from the research: draw the trendline on the MACD
itself, not only on price. In the May 2021 BTC top, price held a rising trendline
while the MACD was already tracing a falling one. The MACD trendline broke first.
The same setup appears on the SOL 4h chart, price pushing to a higher high into
resistance while the MACD prints a clearly lower high, a textbook bearish
divergence that preceded the stall.

The choice of timeframe is yours and does not change whether MACD works; a 4h or 1h
MACD simply updates faster than a daily one. The real limiter is volatility: the
more violent the asset, the less any indicator forecasts cleanly, so widen
confirmation in fast markets.

## Confirmation pairings (filters)

MACD gives momentum but not overbought/oversold context, so traders confirm its
crossover against a second indicator and only act when both agree. From TradingSim,
in rough order of how selective they are:

| Partner | What it adds | Entry rule | Exit |
|---|---|---|---|
| Relative Vigor Index | closing strength vs range | both cross same direction | MACD opposite cross |
| Money Flow Index | price + volume, few signals | MFI overbought/oversold then MACD cross | MACD opposite cross |
| TEMA (50) | triple-smoothed trend | price breaks TEMA and MACD crosses | contrary signal from both |
| TRIX | momentum oscillator | MACD cross matched by TRIX zero-cross | MACD cross, or looser, TRIX zero-cross |
| Awesome Oscillator | 5/34 SMA momentum | MACD cross confirmed by AO | both turn contrary |
| MA (20) | trend validation | price tests the 20-MA, then MACD crosses up | — |

The shared idea is the guardrail we already build into the metric: do not take a
bare crossover, require corroboration. A second indicator is one form of that; our
epsilon noise band and confirmation bars are another, internal to MACD itself.
MFI's volume gate is the most distinct addition and the strongest candidate to add
next, since the histogram and slope already cover much of what RVI, TRIX, and AO
contribute.

## How this maps to `macd.py`

The current iteration targets these metrics by defining the following variables, including 
`cross_up` and `cross_down` crossover points; as well as `guarded_buy` and `guarded_sell` 
constraints. These were applied as conservative measures around noise which we found 
recommended in majority of readings. Histogram variables were derived for both `hist_slope` 
and `converging` flags to highlight early fade nearing zero. Divergence points were constructed
at swing pivot points for variables of `bear_div` and `bull_div` representing  bearish and bullish 
quadrant data of regular bounds. MACD breaks and hidden divvergence, which are not yet coded, are 
next target. `strength` is compiled from band clearances, slope spikes, zero field, and 
corroboration by divergence, which was numerically viewed as significantly weighted swing series.

![BTC preview](/outputs/macd_lab/preview_btc.png)

## Sources and cross-checks

The readings above are drawn from Commodity.com (Lawrence Pines), GoodCrypto, and
TradingSim, plus Okan Yenigün's "Python Trading Guide: MACD" (Stackademic, 2023),
which implements the same 12/26/9 metric through the `ta` library and repeats the
core points: crossovers, divergence, the zero line, and the caution that MACD lags
and whipsaws in ranging markets. Nothing in it goes past what is built here, but it
gives an independent implementation to check against. Our hand-rolled MACD matches
`ta.trend.MACD` exactly on the MACD line; the signal line differs only during the
first ~150 bars of warmup, where `ta` seeds its EMA differently, and converges to
zero difference thereafter. The two extra annotated charts collected during research
show the same anatomy: a histogram coloured positive and negative around the zero
line, and the MACD line drawn green or red by slope crossing the signal line with a
dot marked at each crossover. Both are the standard picture this code reproduces.
