# Swing Trader 

Currently, a read-only crypto market scanner. It pulls live public price data, computes a
stack of technical indicators, ranks coins by a composite signal, and saves
dated reports. It does not place trades, the live switch stays off by design until model trained and margins are clear of strict thresholds.

![Guarded MACD preview for BTC/USDT, hourly](outputs/PNG/preview_btc.png)

*Guarded MACD on BTC/USDT (hourly). Green triangles mark guarded buys, red mark
guarded sells; the lower panel shows the MACD line, signal line, and histogram.*

## Table of Contents

- [Overview](#overview)
- [Signal Journal](#signal-journal)
- [Environment Setup](#environment-setup)
- [Import Data](#import-data)
- [Analyze Data](#analyze-data)
- [Rank Data](#rank-data)
- [Trader Metrics](#trader-metrics)
  - [MACD Trends](#macd-trends)
  - [Divergence and Convergence Quadrants](#divergence-and-convergence-quadrants)
  - [MACD in Crypto Markets](#macd-in-crypto-markets)
  - [Corroborating Metrics](#corroborating-metrics)
  - [Summary Metrics](#summary-metrics)
  - [Entry Points](#entry-points)
  - [Exit Points](#exit-points)
  - [Four Vote Scoring](#four-vote-scoring)
  - [Honest Cynicism Check](#honest-cynicism-check)
- [Trader Controls](#trader-controls)
  - [Four Gate Screening](#four-gate-screening)
  - [ATR Volatility Band](#atr-volatility-band)
  - [Position Sizing](#position-sizing)
  - [Net-edge Fee Fence](#net-edge-fee-fence)
- [Trader Execution](#trader-execution)
  - [Survivorship-Complete Data Pipeline](#survivorship-complete-data-pipeline)
  - [Multi-Resolution Frames](#multi-resolution-frames)
  - [Entry and Exit Visualizations](#entry-and-exit-visualizations)
  - [Model Assessment](#model-assessment)
  - [Edge Diagnostics](#edge-diagnostics)
  - [Regime Conditioning](#regime-conditioning)
  - [Cross-Sectional Relative Strength](#cross-sectional-relative-strength)
  - [Walkforward Test](#walkforward-test)
- [Project Status and Roadmap](#project-status-and-roadmap)
  - [Next Steps](#next-steps)
  - [Appendix: Key Concepts](#appendix-key-concepts)  
  - [Report Generation](#report-generation)

## Overview

trader-py is a research system for selective swing trading on crypto, and it is
analysis-only: it reads live public prices, decides what is worth trading and how
much, and tests whether any of it makes money after fees. It places no trades. The
live switch stays off until a configuration clears strict out-of-sample thresholds.

The work is organised into three chapters, and the rest of this README follows that
order:

- **Metrics (Chapter One)** measures the market: the indicator stack (Kalman,
  Bollinger, Ichimoku, AMAT, RSI, choppiness, MACD) and the Four Vote scoring that
  ranks coins. See Environment Setup through Final Metrics.
- **Controls (Chapter Two)** decides what is tradable and bounds the bet: the weekly
  four-gate screen, the ATR volatility band, position sizing, and the net-edge fee
  fence. See Controls.
- **Execution (Chapter Three)** proves the strategy out-of-sample and, only if it
  earns it, runs it for real: the walk-forward validation and the status. See
  Walkforward Validation and Project Status.

The honest current state is NO-GO: the strategy has no demonstrated edge yet. What
exists is the scoreboard that can prove or kill each change, one logged run at a
time. Nothing trades. The Signal Journal below is the quickest way to watch the
model reason on real candles.

## Data and Model Design (multi-resolution all-market frame, updated 2026-06-24)

The model track was rebuilt this cycle and has since gone multi-resolution. The earlier design trained
on a fixed ten coins of daily bars; it now trains on the **full historical USDT spot market**,
survivorship-complete, across several bar sizes. The change and its rationale:

- **Universe: survivorship-complete, ~612 pairs.** `inputs/acquire_vision.py` enumerates the full
  historical USDT universe by crawling the `data.binance.vision` archive listing (612 pairs, about 31%
  of them delisted) rather than `exchangeInfo`, which only sees the ~433 alive today and silently drops
  every dead coin. Each (coin, bar) row is point-in-time screened, kept only if it would have passed the
  four-gate screen as of that bar. Including the dead coins is what makes the panel honest: a strategy
  that looks brilliant on the survivors can collapse once the coins that went to zero are back in.
- **Resolution: 1h, 4h, and a 5m scalp probe.** Bar size is observation resolution, not trade
  frequency. The original frame is 1h; the working frame is now **4h**, added because 1h direction sits
  at the efficient-market floor and coarser bars amortize the fixed round-trip cost over a larger move.
  A **5m** scalp frame was added for a select set of liquid, lively coins as a research probe (below).
  Each frame is its own dataset (`dataset_<frame>_allmarket.parquet`); signals combine only at the
  signal level, never by pooling rows across resolutions. A daily frame is planned.
- **History and source: longest available, exchange-grade.** Full history per coin (BTC back to 2017),
  pulled offline from the official `data.binance.vision` monthly archives, checksum-verified and
  resumable, with ccxt only as a live top-up for the still-forming bar. Every coin passes a gap gate (at
  most 2% of bars missing, no single gap over 72 hours) before training, and datasets are stored as
  Parquet to preserve dtypes. See `tasks/data-standards.md` and `tasks/data-pipeline-methodology.md`.
- **Features: a broad, causal, scale-invariant candidate set.** Two window families (a wall-clock
  family scaled to the frame and a shorter frame-native one), an in-house indicator block (Williams %R,
  Stochastic, CCI, CMF, MFI, ADX/DMI, Aroon), the trade-flow imbalance, and optional pandas-ta and
  TA-Lib layers. Added this cycle: a triple-Supertrend block (`f_st_`), a BTC lead-lag and
  relative-strength block (`f_btc_`, the first family not derived from the coin's own price), a causal
  multi-timeframe block (`f_4h_`/`f_d1_`/`f_w1_`), a Modern Adaptive Supertrend with a Kaufman
  efficiency regime gate (`f_mst_`), and a regime-state block (`f_rg_`: trailing volatility and its
  own-history percentile, trend drift, efficiency, up/down breadth, trailing return, and the BTC market
  regime). Every feature is causal and scale-invariant; an elastic-net variable-selection pass prunes
  before final fitting.
- **Label: ATR-scaled triple barrier.** A configurable +k ATR before -m ATR within N bars (default +2 /
  -1 ATR over 48 bars on the hour-plus frames; a shorter +1.5 / -1.0 ATR scalp barrier on the 5m
  frame), calibrated to each coin's own volatility rather than a fixed target.
- **Split: honest out-of-sample.** Hold out the final ~1 year, train on all prior history, embargo one
  label horizon at the cut, score the test set once. A forward-chained walk-forward splitter
  (`inputs/wf_splitter.py`, anchored and rolling, with purge and embargo) gives the cross-validation
  distribution alongside the single holdout.

Every change is judged on one after-fee, out-of-sample scoreboard (`outputs/AA-evals/`) and kept only
if it beats both buy-and-hold and a coin-flip. The honest current state remains NO-GO; the single most
promising opening is cross-sectional relative strength (see Trader Execution).

## Signal Journal

The signal journal is the fastest way to see what the model actually sees and does.
For any coin it finds every entry and exit the MACD logic produced, draws the daily
candles with the moving averages and marks each signal, then writes a table beside
the chart noting the trend, RSI, volatility, and whether the fee fence would let
that trade fire. Each coin's study sheet is a self-contained HTML page, so a visual
library builds up every time the screen runs and you can watch the model reason on
real candles rather than trust it blind.

Where to find it: the generator is the `save_journal` function in
`day-controls.ipynb`; the saved study sheets are in `outputs/AA-journal/`, one HTML
file per coin. A static example is below; open the HTML for the interactive chart
and the full table of actions.

![Signal journal example, BTC/USDT](outputs/PNG/avax_macd_20260620.png)

*Signal journal for BTC/USDT: candles with model entries (green) and exits (red) on
top, MACD beneath. The HTML version adds a row-by-row table logging each signal's
trend, RSI, volatility, and whether the fee fence would have allowed the trade.*

## Environment Setup

Dependencies are pinned in `inputs/requirements.txt` and reinstalled on each fresh kernel,
`venv` also committed. The core libraries are `ccxt` (data), `pandas-ta` (indicators), `pykalman` (smoothing), and `plotly` (charts). Run the setup cell once per session to rebuild the environment and configure graphics.

## Import Data

Live OHLCV candles are sourced from a chosen exchange. Five filters control the
scan. The initial selection is the top `TOP_N` spot `/USDT` pairs ranked by quote volume;
each extra symbol adds roughly a second.

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `EXCHANGE` | `binance` | Source exchange (105 supported by CCXT) |
| `SANDBOX` | `False` | Testnet / fake money toggle |
| `TIMEFRAME` | `1d` | Candle size (1m … 1w) |
| `LIMIT` | `300` | Candles pulled per coin (max 1000) |
| `TOP_N` | `20` | Most-traded pairs to scan |

## Analyze Data

Each coin is scored on its latest candle against several lenses:

- **Kalman filter** smooths price noise and marks close-of-day strength.
- **Bollinger Bands (14)** show volatility; narrowing is quiet, flaring is volatile.
- **Ichimoku spans (9, 26)** map trend direction over the medium term.
- **AMAT** flags whether fast and slow averages are aligned (1 = trending).
- **RSI** gauges speed; above 70 is overbought, below 30 oversold.
- **Choppiness** separates clean trend (low) from inertia (high).
- **Candle shapes** detect doji, dragonfly, and gravestone reversal hints.
- **MACD (12, 26, 9)** tracks momentum through crossovers and histogram slope.

The base buy flag requires AMAT trending, EMA-14 above the Kalman mean, and the
low above the Kalman mean. The sell flag is the mirror.

## Rank Data

In this initial signal layer of chapter 1, the engine scans the market reference of the most
liquid USDT spot pairs, computes the indicator stack for each, and draws the results
into one table, skipping symbols too new to have full indicator history rather than
hiding them. Buys are sorted to the top by the buy flag and then by lowest RSI or most
oversold first. In this ranking, sells are the mirror below, ranked by the sell flag and highest RSI. The top name is charted with its Kalman and EMA-14 lines, and the table is saved as a dated CSV
(`outputs/CSV/DailySignals_<date>.csv`). This ranking is upstream of
and separate from the Chapter Two market screening and from the Chapter Three model training. The table below is a legacy illustration over ten long-history large-cap coins, kept only to show the live-scan format; it is **not** the model's training set. The model no longer trains on a fixed ten coins: since the multi-resolution rebuild it trains on the **full survivorship-complete USDT spot market** across the 5m, 1h, and 4h frames (see Data and Model Design and Trader Execution above). The scan that scopes the wider live market down to a tradable sample is the four-gate screen shown under Controls below. This snapshot is from 2026-06-20, a broadly down day where no coin cleared the buy gate, so all ten read as sells, ranked by RSI.

| Coin | Close    | RSI  | Chop | AMAT | EMA>Kalman | Low>Kalman | Signal |
|------|---------:|-----:|-----:|:----:|:----------:|:----------:|:------:|
| SOL  | 69.74    | 42.3 | 46.9 | no   | no         | no         | sell   |
| LINK | 7.95     | 40.5 | 47.6 | no   | no         | no         | sell   |
| XRP  | 1.1359   | 39.3 | 45.4 | no   | no         | no         | sell   |
| BNB  | 581.42   | 38.7 | 51.5 | no   | no         | no         | sell   |
| ETH  | 1711.19  | 38.6 | 45.1 | no   | no         | no         | sell   |
| LTC  | 44.07    | 37.7 | 56.0 | no   | no         | no         | sell   |
| BTC  | 63543.91 | 37.4 | 50.6 | no   | no         | no         | sell   |
| DOGE | 0.0836   | 33.7 | 50.4 | no   | no         | no         | sell   |
| ADA  | 0.1621   | 30.9 | 49.3 | no   | no         | no         | sell   |
| AVAX | 5.896    | 22.3 | 53.2 | no   | no         | no         | sell   |

When any coin clears the buy gate it floats to the top, lowest RSI first.

## Trader Metrics

Three interactive dashboards visualise the indicator stack; static snapshots are
embedded below, and the interactive HTML in `outputs/HTML/` opens in any browser.

![MACD dashboard, static snapshot](outputs/PNG/macd-dashboard.png)

*MACD dashboard, BTC/USDT default view: price candles with guarded buy/sell
triangles and divergence diamonds, the MACD line, signal line, and histogram.*

![Fibonacci dashboard, static snapshot](/outputs/PNG/fib-dashboard.png)

*Fibonacci dashboard, BTC/USDT: retracement and extension levels auto-anchored to
the latest swing, with the golden pocket shaded.*

![Confluence dashboard, static snapshot](outputs/PNG/confluence-dashboard.png)

*Confluence dashboard, BTC/USDT: price with the 20- and 50-MA and buy/sell markers,
the method-agreement panel, and the weighted score against the thresholds.*

### MACD Trends

MACD (Moving Average Convergence Divergence) tracks changing momentum: the speed
of acceleration or decay in a price trend. Because the MACD line moves faster than
the slow average, the two lines cross as the 12-EMA crosses the 26-EMA. A cross
above the zero line signals a bullish turn, below signals bearish. Earlier
crossovers offer more potential than the zero line but carry more false starts.
The histogram beneath measures the gap between the lines: a growing histogram
means accelerating momentum, a shrinking one means a likely turn. Divergence,
the hardest read, compares the swing of price highs and lows against the matching
MACD swings and is used mainly to protect a position before a change rather than
to time a precise entry.

### Divergence and Convergence Quadrants

The full taxonomy reads the last two price swings against the matching MACD
swings, using the HH / HL / LH / LL pattern rather than the labels, since
terminology is not standardised across sources.

![MACD divergence and convergence quadrants](outputs/PNG/divergence_matrix.png)

*The four price-versus-oscillator swing relationships. The left pair resolves to
SELL, the right pair to BUY. Read the swing structure, not the label.*

A single chart can show mixed signals, so weigh both the peak and trough series
and never act on one line in isolation.

### MACD in Crypto Markets

MACD is well respected in BTC and ETH markets but is never read alone. It pairs
with position sizing and an expected stop. A useful crypto technique draws the
trendline on the MACD itself, not only on price: in the May 2021 BTC top, price
held a rising trendline while the MACD was already tracing a falling one, and the
MACD trendline broke first. Faster timeframes update sooner (a 4h or 1h MACD
moves quicker than a daily one), but the real limiter is volatility: the more
violent the asset, the more its forecast leans on corroboration.

### Corroborating Metrics

MACD reads momentum well but signals overbought and oversold poorly, so a
crossover is confirmed against a second indicator and acted on only when both
agree. Candidate partners include the Relative Vigor Index, Money Flow Index,
TEMA, TRIX, the Awesome Oscillator, and a 20-period MA. The shared idea is the
guardrail already built into the metric: never take a bare crossover. The Money
Flow Index, with its volume gate, is the strongest candidate to add next.

### Summary Metrics

The current iteration defines `cross_up` and `cross_down` crossover points, plus
`guarded_buy` and `guarded_sell` constraints that add a conservative noise band.
Histogram variables (`hist_slope`, converging flags) flag early fades near zero,
and `bear_div` / `bull_div` capture the divergence quadrants. MACD breaks and
hidden divergence are not yet coded and are the next target. Overall `strength`
is compiled from band clearances, slope spikes, the zero field, and divergence
corroboration, with the swing series weighted most heavily.

### Entry Points

Buy candidates are displayed first, with Kalman flags shown and the lowest RSI
scores at the top.

A live daily scan (snapshot 2026-06-20) ranks the ten-coin sample, most oversold
first. On this date a broad downtrend left no coin clearing all three buy gates
(AMAT trending, EMA-14 above the Kalman mean, the low above the Kalman mean), so
these are the oversold names to watch, not confirmed buys. The patient strategy
sits out when nothing qualifies.

| Coin | Close | RSI | Chop | AMAT | EMA>Kalman | Low>Kalman |
|---|---|---|---|---|---|---|
| AVAX | 5.896 | 22.3 | 53.2 | no | no | no |
| ADA | 0.1621 | 30.9 | 49.3 | no | no | no |
| DOGE | 0.0836 | 33.7 | 50.4 | no | no | no |
| BTC | 63543.9 | 37.4 | 50.6 | no | no | no |
| LTC | 44.07 | 37.7 | 56.0 | no | no | no |

### Exit Points

Sell candidates mirror the entries: coins trending down with prices below the
Kalman mean, weakest names at the top.

In the same scan all ten coins flagged as sell candidates (price below the Kalman
mean, the fast average below it, AMAT not trending), ranked by RSI. A downtrend
that puts the whole sample on the sell side is exactly when the engine stays
flat, which is the drawdown-reduction behaviour the cynicism check measured.

| Coin | Close | RSI | Chop | AMAT | EMA>Kalman | Low>Kalman |
|---|---|---|---|---|---|---|
| SOL | 69.74 | 42.3 | 46.9 | no | no | no |
| LINK | 7.95 | 40.5 | 47.6 | no | no | no |
| XRP | 1.1359 | 39.3 | 45.4 | no | no | no |
| BNB | 581.42 | 38.7 | 51.5 | no | no | no |
| ETH | 1711.19 | 38.6 | 45.1 | no | no | no |
| LTC | 44.07 | 37.7 | 56.0 | no | no | no |
| BTC | 63543.9 | 37.4 | 50.6 | no | no | no |
| DOGE | 0.0836 | 33.7 | 50.4 | no | no | no |
| ADA | 0.1621 | 30.9 | 49.3 | no | no | no |
| AVAX | 5.896 | 22.3 | 53.2 | no | no | no |

Each scan is saved as a dated CSV in `outputs/` (latest: `outputs/DailySignals_latest.csv`).

### Four Vote Scoring

The composite decision is the **Four Votes** system. Each component casts +1
(buy), -1 (sell), or 0 (neutral):

- **MACD** holds a regime: a guarded crossover sets the stance and keeps it until the opposite guarded crossover flips it.
- **MA crossover** votes +1 when the 20-period SMA is above the 50, -1 below.
- **Fibonacci** is contextual: a pullback into the 0.5–0.618 golden pocket on a rising leg votes +1, a bounce into it on a falling leg votes -1, otherwise 0.
- **Candles** vote +1 on a bullish engulf, -1 on bearish, held live for a few bars.

The four votes are summed into a weighted score, and a trade fires when the score
first crosses the threshold:

```
score = w_macd*MACD + w_ma*MA + w_fib*Fib + w_candle*Candle   (weights default 1)
BUY  when score first reaches +threshold   (default +2)
SELL when score first reaches -threshold   (default -2)
```

Two-point agreement is the standard rule; the stricter three-point version is used
when a setup has fewer trades to learn from. The score is a net total rather than a
head-count: a +2 can be two buy votes and no sells, or three buys against one sell.

![Fibonacci preview with auto-anchored swing](outputs/PNG/preview_fib.png)

*Fibonacci levels auto-anchored to the latest swing on BTC/USDT (hourly). The
shaded band is the 0.5–0.618 golden pocket; dotted lines mark retracement and
extension levels.*

![Confluence preview with vote agreement and composite score](outputs/PNG/preview_confluence.png)

*The confluence view: price with the 20- and 50-MA and buy/sell markers, a panel
showing where MACD, MA, Fibonacci, and Candle votes agree, and the composite
score against the +2 / -2 thresholds.*

A note on the candle vote: an earlier bug renamed a column by position and
swapped the open and close prices, so the pattern read the wrong data. This
version fixes that and uses the standard engulfing definition on the correct
columns.

### Honest Cynicism Check

An hourly backtest over ten coins (~41 days, 0.1% fee per side, long-flat,
threshold 2) ran through a broad crypto downtrend.

| Coin | Strategy | Buy & Hold | Trades | Win % | Max DD |
|------|----------|-----------|--------|-------|--------|
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
| **Mean** | **-10.1%** | **-23.5%** | | | |

Read plainly: the engine lost money on every coin but roughly half of what
holding lost, because staying flat through the downtrend avoided the worst of it.
That is drawdown reduction, not edge. Beating buy-and-hold by being absent during
a fall does not survive into a rising or sideways market. Win rates of 20–50%
confirm no demonstrated predictive skill yet.

Two notes on method, true of every backtest here: it only ever uses information
available at the time, with no peeking ahead, and a second buy signal while a
position is already open does not start a new trade, which is why the dashboards
show more markers than the backtest actually trades.

## Trader Controls

Chapter Two is the governance layer: it decides which coins are tradable and how
large each bet may be, wrapping the Chapter One signal so the model proposes and the
operator-owned fences dispose. The functions live in `day-controls.ipynb`, and four
computational controls do the work.

### Four Gate Screening

A four-gate screen scopes the tradable market before the model sees a coin. Each
candidate must clear four gates: liquidity (24-hour quote volume), the ATR band
(lively enough, not detonating), spread (tight enough that the fee is the binding
cost), and history (enough candles to have lived through several regimes). The
survivors are a dated candidate table; the rule is scan wide, hold few.

This same four-gate logic now does double duty and was generalized, not replaced. It
runs live each week here (Chapter Two), and it is also replayed **point-in-time across
all history** (`screen_membership` in `inputs/build_dataset_1h.py`) to build each frame's
in-sample training mask: a (coin, bar) row enters the 5m / 1h / 4h dataset only if it
would have passed the screen as of that bar. So the screen is what connects the live
decision layer to the full-market model training, with the ATR band recalibrated per
frame and the spread gate approximated by a Corwin-Schultz estimator where the historical
archives carry no top-of-book quote.

![Four-gate screen, live Binance slice](outputs/PNG/2A-screen_20260620.png)
![Four-gate spread, live Binance slice](outputs/PNG/2A-spread_20260620.png)

*The four-gate screen on a live Binance slice: green names clear liquidity, the ATR
band, spread, and history; the rest are rejected with the reason recorded.*

The screen ranks the most-traded USDT spot pairs by 24-hour quote volume (the top 25 to
30), then applies the four gates. The live run of 2026-06-20 scanned 28 pairs; 9 cleared
all four gates and become the initial target sample to analyse more deeply, and the next
step narrows that sample to the three or four strongest as held positions. The full scan,
with each coin's metrics and the gate any rejected coin failed, is below (saved as
`outputs/CSV/2A-sample_20260620.csv`). This is the actual screen output, not a hand-picked
list: the passing names change with the market, which is why ZEC, TAO, and NEAR clear here
while DOGE, ADA, and LINK do not.

| Coin | 24h Vol $M | ATR % | Spread | Candles | Liq (>=$30M) | ATR (2.5-12%) | Spread (<=0.05) | History (>=120) | Result |
|---|---:|---:|---:|---:|:--:|:--:|:--:|:--:|---|
| BTC | 875.0 | 3.33 | 0.0 | 179 | yes | yes | yes | yes | **sample** |
| ETH | 279.0 | 4.72 | 0.0006 | 179 | yes | yes | yes | yes | **sample** |
| SOL | 131.0 | 5.63 | 0.0143 | 179 | yes | yes | yes | yes | **sample** |
| ZEC | 93.0 | 11.18 | 0.0021 | 179 | yes | yes | yes | yes | **sample** |
| XRP | 81.0 | 5.08 | 0.0088 | 179 | yes | yes | yes | yes | **sample** |
| BNB | 56.0 | 3.5 | 0.0017 | 179 | yes | yes | yes | yes | **sample** |
| AVAX | 49.0 | 6.9 | 0.0168 | 179 | yes | yes | yes | yes | **sample** |
| TAO | 38.0 | 9.74 | 0.0438 | 179 | yes | yes | yes | yes | **sample** |
| NEAR | 36.0 | 10.15 | 0.0461 | 179 | yes | yes | yes | yes | **sample** |
| USDC | 902.0 | 0.11 | 0.001 | 179 | yes | no | yes | yes | reject (atr_band) |
| NIGHT | 236.0 | 9.29 | 0.0322 | 101 | yes | yes | yes | no | reject (history) |
| RE | 184.0 | n/a | 0.0549 | 2 | yes | no | no | no | reject (atr_band,spread,history) |
| USD1 | 148.0 | 0.07 | 0.001 | 179 | yes | no | yes | yes | reject (atr_band) |
| WLD | 83.0 | 14.27 | 0.0165 | 179 | yes | no | yes | yes | reject (atr_band) |
| TRX | 42.0 | 1.63 | 0.031 | 179 | yes | no | yes | yes | reject (atr_band) |
| XPL | 31.0 | 12.49 | 0.1011 | 179 | yes | no | no | yes | reject (atr_band,spread) |
| XLM | 30.0 | 9.19 | 0.0468 | 179 | no | yes | yes | yes | reject (liquidity) |
| HEI | 24.0 | 23.33 | 0.1821 | 179 | no | no | no | yes | reject (liquidity,atr_band,spread) |
| DOGE | 19.0 | 4.79 | 0.012 | 179 | no | yes | yes | yes | reject (liquidity) |
| SUI | 19.0 | 6.55 | 0.014 | 179 | no | yes | yes | yes | reject (liquidity) |
| MEGA | 17.0 | 14.15 | 0.0184 | 51 | no | no | yes | no | reject (liquidity,atr_band,history) |
| SYN | 16.0 | 14.23 | 0.215 | 179 | no | no | no | yes | reject (liquidity,atr_band,spread) |
| ENA | 16.0 | 9.94 | 0.1142 | 179 | no | yes | no | yes | reject (liquidity,spread) |
| XAUT | 15.0 | 2.32 | 0.0002 | 86 | no | no | yes | no | reject (liquidity,atr_band,history) |
| BICO | 14.0 | 6.98 | 0.2699 | 179 | no | yes | no | yes | reject (liquidity,spread) |
| ASTER | 14.0 | 6.17 | 0.1586 | 179 | no | yes | no | yes | reject (liquidity,spread) |
| ADA | 14.0 | 6.71 | 0.0616 | 179 | no | yes | no | yes | reject (liquidity,spread) |
| EUR | 13.0 | 0.46 | 0.0087 | 179 | no | no | yes | yes | reject (liquidity,atr_band) |

Gate thresholds, from the screen config: liquidity is 24-hour quote volume at or above
$30M; the ATR band is 2.5 to 12 percent; spread is at or below 0.05; history is at least
120 daily candles. Scan wide, hold few.

### ATR Volatility Band

ATR(14) read as a percent of price, doing two jobs with one metric: a selection
filter that admits or rejects a coin from the sample, and a live guardrail that
keeps the model out of a coin that has drifted out of the tradable band. The floor
sits above the net-edge requirement; the ceiling sits below where a coin gaps through
its stops.

### Position Sizing

Each position is sized so the dollar risk is roughly constant across coins: a calmer
coin earns a larger clip, a livelier one a smaller clip, capped at a fraction of the
account and floored at the venue minimum. At a small account this favours a few
larger positions over many tiny ones that waste edge on fees.

### Net-edge Fee Fence

A trade is refused unless its expected move, after the round-trip fee and slippage,
clears a minimum-edge floor. It is a fence, not an alarm: it refuses rather than
warns, and it is measured on net, not gross. Together with the trades-per-day cap and
the out-of-sample validation of Chapter Three, it forms the three stacked defences
that make volume-hiding, burying thin losing trades in churn, impossible by
construction.

## Trader Execution

Chapter Three is the laboratory. It builds the survivorship-complete dataset, engineers the features,
trains and grades the model meant to power the entries, and tests it the hard way, out of sample and
after fees. The work lives in `03-trader-execution.ipynb` and the modules in `inputs/`. The short
version of the verdict: 1h direction sits at the efficient-market floor, 4h carries a little more signal
but still does not clear costs, and the one genuinely stable opening is cross-sectional relative
strength.

### Survivorship-Complete Data Pipeline

Three modules build the panel. Stage A (`inputs/acquire_vision.py`) enumerates the full historical USDT
universe by crawling the `data.binance.vision` archive listing, 612 pairs against the ~433 alive today,
so the roughly 31% of coins that delisted are included rather than silently dropped; it is a
checksum-verified, resumable downloader with a dated `exchangeInfo` snapshot and a survivorship
partition. Stage B (`inputs/profile_panel.py`) streams one symbol at a time to profile coverage, gaps,
the listing timeline, breadth, and liquidity, and derives the usable start, the minimum history, and
the purge/embargo from the diagnostics. Stage C (`inputs/wf_splitter.py`) is the forward-chained
walk-forward splitter, anchored and rolling, with shared calendar boundaries, train-side purge and
embargo, and point-in-time per-fold universes, the regime-stability companion to the single final-year
split. Methodology in `tasks/data-pipeline-methodology.md`.

### Multi-Resolution Frames

Each bar size is its own dataset. The original 1h frame is kept but superseded by the **4h** working
frame, built survivorship-complete (`dataset_4h_allmarket.parquet`, ~567 coins). The frame comparison
(`inputs/multiframe_eval.py`) is clear: 4h carries more signal than 1h (AUC about 0.55 versus 0.51) and
the daily and weekly context helps, but every setup is still NO-GO after fees. A **5m scalp frame** was
then added as a research probe for eleven liquid, lively coins (BTC, ETH, SOL, SUI, TON, DOGE, NEAR,
PEPE, CHIP, TAO, BNB), chosen by a move-over-spread-plus-fees ranking (`outputs/scalp_ranked.csv`);
`build_dataset_1h.configure()` accepts the `5m` and `15m` labels with a short scalp barrier and an ATR
band recalibrated to the bar. Scalping contradicts the swing thesis and the controls layer rules it out
on the fee wall, so it is held to the same after-fee bar as everything else
(`tasks/scalp-5m-build-2026-06-24.md`).

### Entry and Exit Visualizations

So the entry and exit points the model is trained on can be read by eye, the notebook draws them on real
candles (single source `inputs/exit_geometry_viz.py`). A gallery shows several coins as OHLCV
candlesticks with volume, overlaid with the trend geometry the entry rule reads (three Supertrend
trailing bands and the EMA-200) and the entries and exits marked, the exits coloured by which barrier
closed the trade. A set of historical views walks the same rule across years and regimes, across
timeline lengths, and zoomed into the largest individual winners and losers, each annotated with the
trend drivers that fired it. Every chart carries a written guide on how to read it.

### Model Assessment

A caret-style scorecard (`inputs/model_assessment_1h.py`) grades a zoo of models, three gradient
boosters, logistic regression, a random forest, and a stacking ensemble, two ways: in-sample (Full) and
time-series cross-validated. Because the label is binary, the error is RMSE on the predicted
probabilities, which is the square root of the Brier score, the caret-style classification RMSE, and the
RMSEratio (Full over CV) flags overfitting. The cross-validation is expanding-window TimeSeriesSplit,
never random folds, and the final year stays a single blind test.

### Edge Diagnostics

A leakage audit came first, because leakage is the usual reason a crypto model looks alive in backtest
and dies live. Reading the label, scaling, feature, and split code, all three vectors are clean: the
label is forward-aligned, scaling is fit train-only inside the pipeline, the features are causal, and
the split carries a label-horizon embargo. So the NO-GO is real, not an artifact.
`inputs/edge_diagnostics.py` then answers three questions: whether there is a pre-cost edge against a
coin flip at the real base rate and a one-bar persistence baseline (Q1), whether the edge is stable
across measurable eras or concentrated in one (Q5), and whether raising the confidence threshold lifts
after-cost return per trade (Q6, selectivity). The recurring shape is profit concentrated in the bull
regime and a selectivity curve that rises as the model trades less.

### Regime Conditioning

The handoff's preferred fix for regime concentration is to condition one model on observable regime
state rather than build a switchboard. `build_dataset_1h.regime_block` adds that state as the `f_rg_`
family, all causal: trailing volatility and its own-history percentile, trend drift, a Kaufman
efficiency, up/down breadth, the trailing return, and the BTC market regime.
`inputs/regime_conditioning.py` runs the ablation, the same model with and without that block, and
reports two things separately, whether conditioning improves cross-era stability and whether it lifts
the after-cost edge. On the dev slice it clearly improved generalization (more eras profitable, the
worst era less bad) while the headline after-cost still sat below the fee line: a generalization fix,
not a free edge.

### Cross-Sectional Relative Strength

The one stable opening. Instead of asking whether a coin will rise, the hard direction question,
cross-sectional ranking (`inputs/cross_sectional_4h.py`) asks which coins are strongest right now
relative to the rest and bets strong against weak. Ranking the thin point-in-time universe into
terciles, relative strength is real and broad: most momentum and trend signals show a positive,
train-and-test sign-stable gap between the top and bottom thirds, and the top third beats the market. It
is not yet a green light, because the universe's after-fee baseline is negative and the best top third,
while it beats the market, still sits below zero. The edge is real but drowned by the negative baseline,
categorically different from the time-series entry work that had no stable signal at all. The levers to
lift it above zero, with no shorting allowed, are a market-regime gate, a less fee-punishing label, or a
longer-horizon frame.

## Project Status and Roadmap

As of 2026-06-24 the model track is multi-resolution and survivorship-complete, described under "Data
and Model Design" and "Trader Execution" above. The verdict is unchanged in direction and sharper in
detail: NO-GO, but now well diagnosed.

The headline is that 1h direction prediction sits at the efficient-market floor. The model zoo lands at
an AUC near 0.50, the default +2/-1 ATR label has slightly negative expectancy before fees (base rate
about 0.31 against a one-third breakeven), and a Monte Carlo on the Supertrend baseline shows a 99.7%
probability of loss across ten thousand simulations. Moving to the 4h frame lifts AUC to about 0.55 and
reduces the bleed, but every setup is still negative after the round-trip cost. An entry-sharpening
investigation was a journaled dead end. The leakage audit is clean, so this floor is real rather than a
measurement artifact.

The single most promising result is cross-sectional relative strength: the top third of the universe by
several trend and momentum signals stably beats the bottom third and the market, though the best basket
still sits below zero after fees, drowned by a negative universe baseline rather than absent. Regime
conditioning, giving one model the volatility and trend state as inputs, improves cross-era
generalization but does not by itself cross the fee line. The value of the cycle is the scoreboard and
the diagnostics: every change is now measured out-of-sample and after fees, one logged row at a time, in
`outputs/AA-evals/`.

The earlier daily ten-coin walkforward is kept as the baseline the new frames must beat. Across 766
out-of-sample trades, expectancy was about plus 0.03 percent per trade with a 74 percent win rate, but
ATR stop-losses averaging minus 8.5 percent cancelled the frequent plus 2.8 percent take-profits: a hair
better than a coin flip, not better than buy-and-hold.

### Next Steps

The current plan lives in `tasks/task-request-cross-sectional-edge.md`,
`tasks/multi-resolution-build-plan.md`, and the dated session briefs:

- Build the cross-sectional edge out under a market-regime gate (deploy only when BTC trends up), the
  one place a real, stable signal appeared.
- Rebuild the 4h and 5m datasets so the regime-state (`f_rg_`) features are native, then run the
  full-market edge diagnostics and the regime-conditioning ablation for the real verdict.
- Settle the exit and label geometry on the after-fee scoreboard (`inputs/sweep_label_1h.py`,
  `inputs/exit_geometry_1h.py`), and complete the 5m scalp probe on the eleven selected coins, held to
  the same out-of-sample after-fee bar.

No live trading anywhere. The safety switch stays off until a configuration clearly beats buy-and-hold
and a coin-flip, out-of-sample and after fees.

### Appendix Key Concepts

#### How we test it fairly

We give the strategy a year of history to settle into, then test it on the next
three months it has never seen, then slide the window forward and repeat through
every kind of market. The 20-day gap between the learning period and the test
period is a quarantine: because a single trade can last up to twenty days, without
that gap a trade begun during training could spill into the test window and leak
information, so the two are walled off. The signal and exits are frozen and the
test window is scored once, so there is no fiddling until the number looks good.

#### The entry rule, in plain terms

The buy trigger is the moment the MACD line crosses above its signal line, the
green triangles on the dashboards above, which is the model's way of saying
momentum just turned upward. Gating to the ATR band puts a doorman in front of
that trigger: the coin is only allowed through if its typical daily move sits
between 2.5 and 12 percent. Below 2.5 it is too sleepy to ever reach a profit;
above 12 it is too wild and will blow through the exits. So the rule is, buy on
the upward cross, but only on coins lively enough to be worth it and not so
violent they are uncontrollable.

#### The exit rules, in plain terms

Three exits, whichever happens first. The stop-loss is the safety hatch, set at
1.5 times the coin's normal daily move below the entry; if price falls that far,
the loss is cut. On a coin that swings about 6 percent a day, that stop sits
roughly 9 percent down, which is exactly why the losers are so large and exactly
the thing Priority 1 will attack. The take-profit is the reward hatch: if price
rises 3 percent above the entry, the position is sold and banked. The time stop is
the patience limit: if neither hatch is reached within ten days, the trade is
closed anyway and the money freed, because a trade that has not worked in ten days
is dead weight. Stop checked before the target means that on a day wild enough to
have touched both levels, we pessimistically assume the loss happened, so the
results are never flattered.

### Report Generation

```
quarto render day-metrics.ipynb --to html --no-execute
quarto render day-metrics.ipynb --to docx --no-execute
quarto render day-metrics.ipynb --to pdf  --no-execute
```
