# Do sequence models have anything to offer this target?

Measured 6 September 2026 on the crypto 4-hour panel, 250,000 rows, 40 coins,
three walk-forward folds, predicting bars until the Supertrend flips.

## The question

A sequence model such as a GRU has exactly one advantage over a tree. A tree
reads one row and knows nothing about the row above it, so everything it knows
about the past has to be written into that row by a person. A sequence model
reads the raw run of recent bars and builds its own summary.

So the value of a GRU here depends entirely on whether the 90 hand-built
features are already a good summary of the past. That is measurable, and this is
the measurement.

## What was run

The same tree, the same folds, three feature sets.

| What the model was given | Miss on data it had not seen (RMSE, in bars) |
| --- | ---: |
| the 90 engineered features | 24.213 |
| the 90 engineered features plus the raw last 24 bars | 24.153 |
| the raw last 24 bars, nothing else | 24.247 |
| always guess the average | 26.477 |

## What it found

Adding the raw recent past on top of the engineered features improved the miss
by 0.060 bars, which is 0.25 per cent.

The line that settles it is the third one. Twenty-four raw lagged returns, with
no feature engineering at all, matched 90 engineered features to within 0.034
bars. The two representations carry the same information, and both stop at the
same wall near 24.2.

A GRU exists to find structure in the raw sequence that a human summary misses.
Here the raw sequence and the human summary arrive at the same answer, so there
is no gap for it to close.

## The number that reframes the work

The largest difference between any two of the three approaches is 0.094 bars.
The spread between folds inside a single approach runs from 22.28 in the calm
stretch to 26.11 in the rough one, a range of 3.83 bars.

Which stretch of time the model is asked about matters 41 times more than which
representation it is given.

## Standing

This is a proxy, not a GRU. A sequence model could in principle learn a
representation that neither 90 engineered features nor 24 raw lags found. The
measurement does not rule that out; it makes it much less likely, and it prices
the attempt at two to three days against a gap measured at 0.25 per cent.

Read alongside the two findings that came before it. Seven models sat at a coin
flip on direction. Nine tuning settings were all rejected on trend life, with
the tuning curve asking for a smaller model rather than a larger one. The
bottleneck is the target and the data, not the model, the settings, or the
features.

Reproduce with the lag comparison described above against
`inputs/trend_life_baseline.py` and `inputs/model_metrics.py`.
