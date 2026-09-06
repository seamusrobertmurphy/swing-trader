# Fibonacci — preserved reference notes

Working notes for the Fibonacci retracement and extension tool in `fib_lab/`.
Written so the mechanics are clear enough to rebuild from scratch in another repo.
The code in `fib.py` follows these notes one-to-one.

## The idea

After a strong move, price rarely runs in a straight line. It pulls back, then
often continues. Decades of chart-watching found those pullbacks tend to stall and
reverse near a handful of ratios drawn from the Fibonacci sequence. Lay those
ratios as horizontal lines across the last clean swing and you get a grid of likely
support and resistance. Extend the same ratios past the swing and you get target
levels for where a continuation might reach.

It is a self-fulfilling, attention-based tool. The levels work partly because
enough traders watch the same ones and place orders there. That is a real edge and
also its limit: it is context, not a trigger.

## Where the ratios come from

The sequence is 1, 1, 2, 3, 5, 8, 13, 21, 34, 55 and on. Each term divided by the
next converges on 0.618, the inverse of the golden ratio 1.618. A term divided by
the one two places along gives 0.382. The square root of 0.618 is 0.786. The 0.5
level is not Fibonacci at all; it is the plain halfway point, kept because markets
respect it. Extensions are the same family above one: 1.272 is the square root of
1.618, 1.618 is the golden ratio itself, 2.618 is its square.

The retracements used here are 23.6, 38.2, 50, 61.8, 78.6 percent. The extensions
are 127.2, 161.8, 200, 261.8 percent.

## All the math

Take the two extremes of the chosen swing, the low and the high, and let the range
be high minus low.

```
retracement(r) = high - r * range        # r from 0 to 1
up_extension(E)   = low  + E * range      # E above 1, a target above the high
down_extension(E) = high - E * range      # E above 1, a target below the low
```

At r equal to 0 the line sits on the high, at 1 on the low, at 0.5 exactly halfway.
The retracement lines are the same horizontal prices no matter the trend; only the
reading changes. In an uptrend they are support the pullback may bounce from. In a
downtrend they are resistance a bounce may stall at. Extensions are drawn in the
direction the latest leg is travelling, up-leg targets above, down-leg below.

## The golden pocket

The band between the 0.5 and 0.618 retracements is where traders concentrate, often
called the golden pocket. A pullback that holds there and turns is the cleanest
continuation entry the tool offers, with a stop just past the 0.786 or the swing
origin. `fib.py` returns this band directly and the dashboard shades it.

## Anchoring the swing

Everything depends on which two points you pick, and that is the judgement the tool
automates. The default auto-anchor takes the highest high and lowest low of the
last `lookback` bars and decides direction by recency: whichever extreme printed
more recently sets the active leg. This matches the "auto fib" most charting tools
draw. A larger `lookback` locks onto a bigger, slower swing; a smaller one tracks
the latest move. On the BTC hourly preview a 240-bar window caught the June 10 low
to June 15 high, and price was sitting on the 61.8 percent line, the textbook spot
to watch. When in doubt, anchor to the move everyone can see: the most obvious
swing on the chart is the one most orders cluster around.

## How to trade it, honestly

It is a where tool, not a when tool. Price reaching the 61.8 percent line says
nothing on its own; price reaching it and printing a reversal candle, or turning
there while another indicator confirms, is the signal. The natural pairing in this
project is the guarded MACD: a Fibonacci level gives the price location, a guarded
MACD cross or a divergence at that level gives the timing. Confluence, the same
level showing up from two independent methods, is worth more than either alone.

Levels fail. In a strong trend price slices through 38.2 and 50 without pausing; in
a violent market, the deeper the volatility the less any level holds, the same
caveat the MACD notes carry. Treat a broken level as information too: a clean break
and close beyond the 78.6 percent line usually means the swing is dead and the move
is reversing, not retracing.

## How this maps to `fib.py`

`FibConfig` holds the ratios, the `lookback`, and a `min_swing_frac` noise filter.
`detect_swing` returns the anchor and its direction. `retracement_levels` and
`extension_levels` apply the formulae above; `golden_pocket` returns the 0.5 to
0.618 band; `nearest_level` finds the line price is closest to. `fib_features`
gives five scale-invariant causal columns for the model, recomputing the swing in a
trailing window at every bar so nothing peeks ahead: where price sits in the swing,
its distance to the nearest line, whether it is in the golden pocket, the leg
direction, and the swing size relative to price. `build_fib_charts.py` draws all of
it per coin with a symbol dropdown, the same shape as the MACD dashboard.
