# TASK: crossover-event detector, then ML train/test pipeline

Written 2026-06-18. Handoff so a fresh session can continue without re-deriving context.

## Where the crossover stands now

"Crossover" currently means a **state** (is the fast average above the slow), not an
**event** (the day the fast crosses the slow). It exists in two places with two
different definitions, which is the confusion to fix:

- `python/ccxt-daily-signals.ipynb`, engine cell (`def calculate_indicator`):
  `ema_cross = EMA_14 > kalman`. Reported as column `EMA_gt_Kalman`. Feeds buy/sell.
  This compares EMA-14 to the **Kalman line**, not the 91 EMA.
- `python/inputs/backtest.py`: `crossover = EMA14 > EMA91` (the original template's
  definition).

The crossover-**event** detector and the 91/125 EMAs are **not yet in the notebook**.

## Task 1 — build the crossover-event detector (tier 1, do first)

Keep it simple. In the engine cell of `ccxt-daily-signals.ipynb`:

1. Compute EMA 14, 91, 125 (his three EMAs).
2. Use ONE crossover definition everywhere: fast (14) vs slow (91).
3. Add two clear values:
   - state: `ema_cross = EMA14 > EMA91`
   - event: `cross_event` = `"golden"` (14 crosses **above** 91 on the latest bar),
     `"death"` (crosses **below**), else `"none"`.
4. Rename column `EMA_gt_Kalman` -> `EMA_Cross`; add `Cross_Event`. Update the
   ranking cell (cell that sorts on `'EMA_gt_Kalman'`).
5. Verify the notebook still runs top to bottom.

Note: changing `ema_cross` from EMA-vs-Kalman to EMA14>EMA91 also changes the buy/sell
gate. Confirm that is wanted (it matches the original template and the backtest).

## Task 1b — candle-shape flags: doji / dragonfly / gravestone (tier 1)

Single-candle indecision features. No library needed. In the engine cell of
`ccxt-daily-signals.ipynb`, paste this block **above** the line
`buy  = amat and ema_cross and above_kalman`:

```python
# Candle shape: doji / dragonfly / gravestone (single-candle indecision)
o, h, l, c = df["open"].iloc[-1], df["high"].iloc[-1], df["low"].iloc[-1], df["close"].iloc[-1]
rng   = h - l
body  = abs(c - o)
upper = h - max(o, c)
lower = min(o, c) - l
doji       = bool(rng > 0 and body <= 0.10 * rng)                       # tiny body
dragonfly  = bool(doji and lower >= 0.6 * rng and upper <= 0.10 * rng)  # long lower shadow
gravestone = bool(doji and upper >= 0.6 * rng and lower <= 0.10 * rng)  # long upper shadow
```

Then add to the `row = dict(...)` (change the `Low_gt_Kalman=above_kalman)` line):

```python
               EMA_gt_Kalman=ema_cross, Low_gt_Kalman=above_kalman,
               Doji=doji, Dragonfly=dragonfly, Gravestone=gravestone)
```

Notes: a doji is a *context* signal (only meaningful after a strong prior trend) and
needs next-candle confirmation. Dragonfly = potential bullish reversal after a decline;
gravestone = potential bearish reversal after a rally. Treat as candidate features to
grade in the backtest, not standalone triggers. Thresholds (10% body, 60% shadow) are
tunable.

## Task 1c — MACD (12,26,9) crossover (tier 1, a key focus metric)

MACD line = EMA12 - EMA26; signal = EMA9 of the MACD line. Buy = MACD crosses
**above** signal (strongest when both < 0); sell = crosses **below**. In the engine
cell of `ccxt-daily-signals.ipynb`, paste **above** `buy  = amat and ema_cross and above_kalman`:

```python
# MACD (12,26,9): line, signal, and the crossover events
macd_line   = df["close"].ewm(span=12, adjust=False).mean() - df["close"].ewm(span=26, adjust=False).mean()
signal_line = macd_line.ewm(span=9, adjust=False).mean()
macd, sig           = macd_line.iloc[-1], signal_line.iloc[-1]
macd_prev, sig_prev = macd_line.iloc[-2], signal_line.iloc[-2]
macd_buy  = bool(macd_prev <= sig_prev and macd > sig)   # bullish cross (stronger if macd < 0)
macd_sell = bool(macd_prev >= sig_prev and macd < sig)   # bearish cross
macd_below_zero = bool(macd < 0)
```

Add to the `row = dict(...)`:

```python
               MACD=round(float(macd),4), MACD_Signal=round(float(sig),4),
               MACD_Buy=macd_buy, MACD_Sell=macd_sell, MACD_below_zero=macd_below_zero)
```

Notes: `pandas-ta-classic` also has `df.ta.macd()` (columns MACD_12_26_9 / MACDh / MACDs)
if you prefer the df.ta.* style; the explicit version above is used because the
crossover event needs the previous bar's values. Grade it in the backtest like the rest;
the "below zero" flag is a candidate filter to test, not an assumed truth.

## Task 2 — ML train/test pipeline (next, bigger; needs care)

Goal: train a model on the metrics and assess accuracy on **blind** (out-of-sample) data.

Key requirements the user flagged:
- Train and test must be **time-split**, no leakage (no future data in training).
- Sets must be representative and noise-aware.
- Use `breakout_events.csv` (win/loss labels) + the indicators as features.

## Files

- Notebook: `python/ccxt-daily-signals.ipynb` (config knobs in top "Configure" cell:
  EXCHANGE, SANDBOX, TIMEFRAME, LIMIT, TOP_N)
- Backtest engine: `python/inputs/backtest.py`
- Backtest output: `python/outputs/breakout_events.csv` (309 events, 20 coins, ~3 yrs)

## Honest result so far (don't trade yet)

Breakout + crossover + volume: ~57% win in-sample, fell to ~48% out-of-sample on a
small (31-event) test set. Average return per trade stayed slightly positive only
because of the 2:1 target/stop, not predictive power. No fees/slippage modeled.
Not yet a demonstrated edge.
