# Priority 0 walk-forward results

Generated 2026-06-20T02:44:59+00:00 (UTC). Research and validation only. No live trading; no orders were placed.

## What was built

Two pieces, in one module (inputs/walkforward.py):

- P0.1 trade-exit simulator (simulate_exit): given an entry and the
  following daily bars, walks forward bar by bar and returns the exit
  price, date, reason, and after-fee return.
- P0.2 walk-forward backtest: rolls train/test windows per coin with an
  embargo, scores the test window once, aggregates only the out-of-sample
  after-fee result, and compares against buy-and-hold and a coin flip.

## Signal and exit rules

Entry signal: the MACD signal-line cross-up already defined in
compute_signals (cross_up), gated to the ATR tradable band [2.5%, 12.0%].
This is the simplest honest choice and reuses the live notebook's
definition without the leakage risk of the four-vote model machinery.

Exit precedence per bar (conservative), from CONFIG:
  1. ATR stop-loss, checked first: entry * (1 - 1.5 * daily_atr_pct/100).
  2. take-profit: entry * (1 + 3.0/100).
  3. time stop: exit at close after 10 bars.
  (Optional MACD cross-down signal exit is implemented but OFF by default.)
If both stop and target sit inside one bar's [low, high], the STOP is taken.
Net return = gross - 0.15% fee - 0.05% slippage = gross - 0.20% round trip.

## Windows and embargo

Train 365 days, test 90 days, sliding forward by one test window. A 20-day embargo
straddles the train/test cut (last embargo days of train dropped; test
starts embargo days after the cut), so no test trade can peek into training.
The signal+exit are frozen, so there is no per-window threshold tuning to
overfit; the test window is scored exactly once. Full daily history per coin
spans the 2017-2026 bull, bear and sideways regimes.

## Headline out-of-sample, after-fee numbers

Aggregate across all coins and all test windows:

  signal strategy : trades=766  expectancy/trade=+0.0289%  win-rate=74.0%  median/trade=+2.800%
  signal net per test window = +0.0840%
  buy-and-hold    : per-window net average = +35.1292%
  coin-flip       : expectancy/trade = -0.2123% (avg over 5 seeds)

Coin-flip by seed (expectancy/trade %): 11:-0.429, 23:+0.027, 37:-0.087, 51:-0.445, 73:-0.127

Exit-reason breakdown (out-of-sample, after fees):
  stop_loss    n= 168  mean net=-8.522%
  take_profit  n= 562  mean net=+2.800%
  time_stop    n=  36  mean net=-3.325%
Read: take-profits are frequent and small (+TP-cost each); stop-losses
are rarer but large on these volatile coins, and the asymmetry cancels
the win-rate. A high win-rate here is not an edge.

Note on the buy-and-hold comparison: buy-and-hold holds for the whole
90-day test window, so its per-window net captures entire moves, while the
signal is exposed only for short bursts (a few bars per trade). The two are
not exposure-matched; buy-and-hold is structurally favoured here and the
ten survivors flatter it further. The signal would need a strong per-trade
edge to overcome that, and it does not.

## Per-coin out-of-sample (after fees)

coin       windows  trades   exp/trade   win%    BH(win avg)   flip/trade
--------------------------------------------------------------------------
BTC             31      91     +0.189%   67.0     +16.409%     +0.192%
ETH             31      99     +0.030%   74.7     +18.470%     +0.201%
SOL             19      58     +0.433%   81.0     +11.582%     -0.816%
BNB             30      78     +0.999%   80.8     +40.370%     -0.503%
XRP             28      76     -1.219%   61.8     +19.330%     -0.472%
ADA             28      85     -0.406%   71.8     +25.573%     -0.442%
AVAX            19      45     +0.000%   75.6      +9.911%     -0.264%
LINK            25      75     -0.129%   77.3     +12.970%     +0.029%
LTC             30      94     +0.353%   77.7      +7.775%     -0.376%
DOGE            23      65     +0.041%   75.4    +206.897%     +0.077%

History span per coin (first -> last, bars):
  BTC    2017-08-17 -> 2026-06-19  (3229 bars)
  ETH    2017-08-17 -> 2026-06-19  (3229 bars)
  SOL    2020-08-11 -> 2026-06-19  (2139 bars)
  BNB    2017-11-06 -> 2026-06-19  (3148 bars)
  XRP    2018-05-04 -> 2026-06-19  (2969 bars)
  ADA    2018-04-17 -> 2026-06-19  (2986 bars)
  AVAX   2020-09-22 -> 2026-06-19  (2097 bars)
  LINK   2019-01-16 -> 2026-06-19  (2712 bars)
  LTC    2017-12-13 -> 2026-06-19  (3111 bars)
  DOGE   2019-07-05 -> 2026-06-19  (2542 bars)

## Verdict

  positive after-fee edge?   True
  beats coin-flip (clear)?   True
  beats buy-and-hold?        False

  GO/NO-GO: NO-GO

NO-GO. The MACD cross-up signal, traded with these ATR exits and after
realistic round-trip costs, does not show a clear out-of-sample edge over
both baselines across regimes. This matches the project's standing NO-GO
(Chapter One AUC ~0.51, no demonstrated edge). It is a valid, useful
result: it says do not trade this configuration, and it gives a clean
scoreboard to measure future improvements against (threshold tuning, a
better label, regime features). Do not present this as tradeable.

## Caveats and assumptions

- Stop/target fills are assumed at the exact stop/target price; intrabar
  gaps could fill worse. Slippage is modelled as a flat percent, not
  size- or volatility-dependent.
- One position at a time per entry; no portfolio-level position cap is
  enforced in the backtest (the live notebook caps concurrency separately).
- Entries are confined to each test window; an exit may run a few bars past
  the window edge, which is realistic and does not leak training data.
- The ATR-band gate reduces trade count; without it there are more trades
  but the same honest measurement applies. Switch via USE_ATR_BAND_GATE.
- Daily bars only; no intraday timing. Survivorship: the ten coins are all
  survivors, which flatters buy-and-hold more than the signal.
