# Session handoff and task request: model tuning, with the evaluation and data work that now supports it

Written 2026-06-20. Hand this to a fresh session and say "read this, then start at Priority 1."
It supersedes `tasks/next-steps.md` for the model track and folds that file's rule-strategy
work in where the two tracks meet. Nothing here is discarded; the morning draft is preserved
and cross-referenced.

The purpose of this document is to carry the session's decisions across a context boundary
without losing them. It records four things: where we are and where the day is meant to go,
the methodology we settled (evaluation metrics, scoring, bookkeeping, formatting, exit
geometry, the label-target question, the new historical data), the remaining tasks in
priority order, and a filepath index so nothing has to be hunted for.

---

## 1. Where we are, and where the rest of the day should go

Two parallel tracks share one scoreboard. The rule strategy (MACD cross with ATR exits)
lives in `walkforward.py` and reads NO-GO. The machine-learning model (LightGBM on 32
scale-invariant features) lives in `build_dataset.py` and `train_model.py` and also reads
NO-GO, but only by a hair, and it now has a complete, honest evaluation harness behind it.
This session finished that harness. All four of Keller's evaluation metrics are built and
running, the scores are bookkept in a central hub, the costs are confirmed and baked in, and
a new historical trade-flow data source has been built and tested.

The destination for the rest of the day is model tuning, specifically the exit geometry
sweep (Priority 1 below). This is the one diagnosed leak, it is cheap to test, and it is
where Seamus's statistical expertise should go: choosing and reading the parameter grid,
judging significance, and deciding when a result is real rather than noise. The tuning menu
in section 4 lists every knob, its file, its current value, and a Keller-informed range, so
the statistical work has a concrete surface to act on.

Current grounded numbers, so a fresh session can tell whether it has improved anything:

- Model (`train_model.py`, single 70/30 time split, 20-day embargo): LightGBM chosen, test
  ROC-AUC about 0.520, NO-GO. Metric 2 P&L after costs: about +0.20 percent net per trade,
  win rate about 36.8 percent, per-trade Sharpe about 0.028, t-stat about +1.05, which is not
  significant (|t| < 2). The model's selection nudges expectancy positive versus trading
  everything (about -0.13 percent net), but it is inside the noise band.
- Rule strategy (`walkforward.py`, 766 out-of-sample trades): expectancy about +0.03 percent
  per trade, win rate about 74 percent, ATR stops averaging about -8.5 percent cancelling
  frequent +2.8 to +3 percent take-profits. NO-GO, does not beat buy-and-hold.
- Dataset (`inputs/binance-data/dataset_ccxt_10coins_2017-2026.csv`): 26,772 labeled rows, 10 coins, 2017-12-15 to
  2026-05-31, base rate (label = 1) about 0.325.

The one rule still holds: measure everything against the out-of-sample, after-fee scoreboard,
and keep only changes that beat both buy-and-hold and a coin-flip. No paper or live trading
until something clears that bar. `LIVE_TRADING` stays off.

---

## 2. Methodological updates settled this session

### 2.1 The four evaluation metrics (all built)

Keller argues accuracy is useless for trading models and names what matters instead. All four
are now implemented, mostly in `inputs/eval_report.py`, driven from `inputs/train_model.py`.

- Metric 1, precision and recall at the decision threshold. We only score the trades we would
  actually take: probability at or above 0.60 (act long) or at or below 0.40 (stand aside or,
  in Keller, short). The 40 to 60 band is ignored. The confidence filter keeps roughly 58
  percent of LightGBM rows. Implemented as `confidence_filtered()`.
- Metric 2, simulated P&L after costs. This is the metric that decides. For every row the
  model is confident on, we take the realized triple-barrier return (`trade_ret`, written by
  `build_dataset.py`: +0.10 if the target is hit first, -0.05 if the stop is hit first, else
  the day-20 close return), subtract the round-trip cost, and report per-trade expectancy, win
  rate, per-trade Sharpe, a t-stat, and an additive (cumsum, one unit per trade) equity curve.
  Implemented as `_pnl()` and `_chart_equity()`.
- Metric 3, regime-stratified AUC. AUC split by volatility tercile (low, medium, high), so a
  model that only works in calm or only in chaos is exposed. Implemented as `_regime_auc()`,
  fed by `f_rv_30`.
- Metric 4, transaction costs. Not a separate report but a discipline: costs are inside
  Metric 2's objective, never bolted on after. See 2.6 for the confirmed numbers.

A correction worth remembering: Metric 2's first version compounded returns multiplicatively
(cumprod), which produced a misleading -99.9 percent drawdown because the triple-barrier
signals overlap in time and cannot all be held as one compounding book. It was rebuilt as
per-trade statistics with an additive equity curve. If anyone reintroduces compounding, they
must first resolve the overlapping-position problem honestly.

### 2.2 Evaluation scoring and bookkeeping (the AA-evals hub)

Results are collected centrally, mirroring the AA-journal pattern, so learning accumulates
instead of scattering. The hub is `outputs/AA-evals/`. The index is
`evaluation-scores.md`, a single consolidated table, one row per evaluation run, plus a
`.pdf` and a `.docx` of the same. Each run also drops a dated per-run record, and results are
filed into date-named subfolders. The index columns are: date, evaluation type, dataset, best
model, test AUC, Best Model Precision, Always Buys Precision, Precision Change (percent), Net
P&L/trade, trades, verdict, record.

Three column names were deliberately chosen for plainness and should be kept: "Always Buys
Precision" is the base rate, the precision a dumb model that buys everything would get; "Best
Model Precision" is our chosen model's precision on the trades it takes; "Precision Change
(percent)" is the multiplicative lift of the second over the first, `(prec / base - 1) * 100`.
"Best model" replaced "chosen"; "evaluation type" replaced "type"; "head-to-head" replaced
"bake-off" in prose.

### 2.3 File formatting decisions

The PDF was reordered to put the results table first and the definitions and glossary below
it, because the old definitions-first layout was clunky to read. The glossary has three
sections: what counts as a buy (the triple-barrier label), how precision is scored (true and
false positives), and what the columns mean. A `.docx` was added as a second output in the
same table-first order, for editing. Throughout: plain words, ASCII only, no emojis, no
decorative icons, no symbol-arrows. This is a standing preference, not a one-off.

### 2.4 Exit geometry: the concepts, the leak, and how 3C will measure it

A stop and a take-profit are the two exits that bound a single trade. The stop is the floor on
how much one trade can lose; the take-profit is the ceiling on how much it can gain. Their
ratio is the reward-to-risk shape of the trade. A take-profit of 10 percent against a stop of
5 percent is a 2:1 shape; a take-profit of 3 percent against an average stop of 8.5 percent is
about 1:2.8, the inverse.

"Lopsided" has a precise meaning: every geometry implies a breakeven win rate, the fraction of
trades you must win just to cover the losers. For a take-profit T against a stop S it is
S / (S + T). The rule strategy's 3 percent take-profit against its roughly 8.5 percent ATR
stop implies a breakeven win rate of 8.5 / (8.5 + 3) = about 74 percent. The strategy's actual
win rate is about 74 percent. It is sitting exactly on its own breakeven line, so after costs
it loses. That is Keller's wide-stop leak, quantified: rare large losers cancel frequent small
winners. Position sizing cannot fix this, because sizing equalizes the dollars at risk, not
the reward-to-risk ratio; a smaller position on a volatile coin still loses S percent of itself
when stopped. Only the geometry fixes the geometry.

How 3C reports the fix. Each candidate (stop, take-profit) pair is run through `walkforward.py`,
which appends one row per variant to `outputs/experiment_log.csv` and writes every
out-of-sample trade to `outputs/walkforward_trades.csv`. A pair "is not lopsided" when its
implied breakeven win rate sits comfortably below the strategy's actual hit rate, leaving
positive expectancy after the 0.20 percent cost, a per-trade Sharpe and t-stat that clear
noise (target |t| > 2), and a result that beats both buy-and-hold and a coin-flip over the
same out-of-sample window. The same expectancy, win rate, and t-stat are what Metric 2 reports
for the model track in `evaluation-scores`. So both tracks are graded on the same geometry and
the same costs.

The geometry is currently forked across three places, and reconciling them is part of the
tuning, not a bug to silently patch:

- `walkforward.py` CONFIG: take_profit_pct 3.0, stop_atr_mult 1.5 (about 8.5 percent in
  practice), hold_window_days_max 10. This is the rule-strategy backtest and the NO-GO numbers.
- `02-trader-controls.ipynb` CONFIG: updated this session to take_profit_pct 10.0,
  hold_window_days_max 20, to match the model's label as a preliminary estimate. stop is still
  ATR-based (stop_atr_mult 1.5), annotated as an open 3C question.
- The model label in `build_dataset.py`: +10 percent before -5 percent within 20 days.

These are deliberately not yet unified. When 3C settles a geometry, update all three together
plus the README, in one pass, so they never silently drift.

### 2.5 The label target is ours, not Keller's, and not a consensus value

This was raised directly and deserves a permanent, honest record. Our model predicts "+10
percent before -5 percent within 20 days." That target is a design choice. It is not Keller's,
and it is not a scientific consensus number.

What Keller actually uses (verified in the report, `create_labels(forward_hours=4,
threshold=0.005)`): a label of 1 if price rises more than 0.5 percent in the next 4 hours.
Intraday. A plain forward-return threshold, not a triple barrier. He trades both long and
short (position -1 when probability is below 0.40), and annualizes Sharpe with sqrt(365 x 24),
which only makes sense on hourly bars. Keller's edge, where he finds one, is short-horizon
momentum measured in hours.

Our design is deliberately different and the difference is principled, not accidental. The
mandate in `CLAUDE.md` is swing and long-horizon, long-only, no shorts, no leverage. So we use
a triple-barrier label (the method is López de Prado's, which is standard and real) over a
20-day swing horizon. The triple-barrier method is well founded; the specific numbers, +10 and
-5 and 20 days, are operator-chosen starting points, not crypto-calibrated and not derived from
evidence. That is exactly the gap worth being uneasy about.

There is a defensible reason the swing frame sidesteps Keller's central warning. Keller's own
arithmetic is the heart of his paper: a 52 percent win rate on 0.5 percent intraday moves earns
about +0.02 percent gross per trade, against a round-trip cost of about 0.30 percent, so the
intraday edge is eaten by costs and goes net negative. A 10 percent target against a 0.20
percent cost is fifty times the cost, so the swing horizon is far more forgiving on costs. The
honest tension is that we borrowed Keller's features, his metrics, and his 60/40 confidence
filter, but not his horizon or his label, and a fresh session should hold both facts at once:
the swing frame is cost-defensible and mandate-compliant, and the exact target numbers are
unvalidated.

This is empirically testable from the Binance data we already have, and should be a tuning
experiment, not an assumption. Sweep the label over a grid of (target, stop, horizon) using
the existing `compute_label_return()` machinery, and for each cell report the base rate, the
realized expectancy after cost, and the implied versus actual win rate. Crypto context to keep
in mind while reading that sweep: the screened coins carry daily ATR roughly 2.5 to 12 percent,
so a 5 percent stop is only one to two daily ranges away, close enough that ordinary noise
trips it, which is consistent with the base rate of 0.325, meaning the target is reached only
about a third of the time and the stop or the clock takes the rest. The crypto markets do move
differently from conventional finance, and the right response is to calibrate the target to the
coins' own volatility rather than to inherit a number.

### 2.6 Confirmed cost and fee structure

Binance.com global spot, Regular User tier. Maker and taker are both 0.10 percent, or 0.075
percent each side with the BNB 25 percent discount. We assume BNB is used: 0.075 percent per
side is 0.15 percent round trip, plus 0.05 percent slippage, for `COST_PCT` = 0.20 percent
total drag per trade. This is set in `train_model.py` (ROUND_TRIP_FEE_PCT 0.15, SLIPPAGE_PCT
0.05) and as round_trip_fee_pct and expected_slippage_pct in the controls notebook. Note
Keller assumes 0.10 percent per side with no BNB discount, hence his 0.30 percent round trip;
our lower figure is the BNB discount, and it should be revisited if we ever stop holding BNB.

### 2.7 Historical trade-flow data: built and tested this session

A new scoped downloader and aggregator is at `inputs/binance-data/flow_data.py`, tested and
working. It pulls daily (1d) klines for the 10 model coins from data.binance.vision (free, no
API key, no rate limit, deterministic) and rolls them into `daily_flow.csv` with, per coin per
day, the taker-buy ratio and a signed flow imbalance in [-1, +1].

The overlooked efficiency, which answers the question of whether we have fully used the Binance
public-data documentation: a 1d kline row already carries taker-buy base volume and the trade
count. So a daily trade-flow imbalance, taker_buy_base / volume, is available directly in a few
megabytes per coin, without ever downloading the multi-gigabyte aggTrades archives. The repo's
own `download-trade.py` and `download-aggTrade.py` default to all symbols and all intervals,
which would be tens of gigabytes; scoping to ten coins and the 1d interval, and reading
taker-buy volume straight from the kline, is the cheap path. The aggTrades archives are only
needed if we later want intraday trade-flow resolution; `flow_data.py --aggtrades` fetches them
when that day comes. A second, related efficiency: these same 1d kline archives could replace
the live ccxt fetch in `build_dataset.py`, making the dataset build fully offline and
reproducible instead of network-dependent. That is a candidate refactor, not yet done.

Storage, given the 2TB drive: keep the compressed kline zips under
`inputs/binance-data/klines/<SYMBOL>/` (a few megabytes per coin), and the aggTrades zips, if
ever fetched, under `inputs/binance-data/aggtrades/<SYMBOL>/` (tens of gigabytes for the full
history of ten coins, still comfortable on 2TB). Keep the compressed raw so any resolution can
be recomputed later, and the small `daily_flow.csv` is what `build_dataset.py` will join.

The integration step is not yet done: `build_dataset.py` does not yet read `daily_flow.csv`.
Adding flow_imbalance as a feature, one feature, measured out-of-sample, keep only if it
improves the after-fee result, is Priority 2.1 below.

---

## 3. Remaining tasks, in priority order

### Priority 0: sync the Chapter Three notebook to the scripts (do before tuning)

`03-trader-execution.ipynb` has drifted from `train_model.py` and `eval_report.py`: it
reimplements the modeling inline and is missing Metric 2 (P&L after costs), Metric 3
(regime-stratified AUC), the AA-evals bookkeeping, the cost constants, and the moved data path.
The full delta list and ready-to-paste fixes are in `tasks/notebook-reconciliation-2026-06-20.md`.
Do the recommended Option A (make the notebook a thin driver over the scripts) first, so every
tuning run from the notebook is recorded in AA-evals from the start. Otherwise tuning done in the
notebook produces weaker, unlogged numbers.

### Priority 1: exit-geometry tuning (the day's focus, where statistics goes)

This is the diagnosed leak (2.4) and the cheapest high-leverage change. Sweep stop and
take-profit together through `walkforward.py`, with cost inside the objective, logging one row
per variant to `experiment_log.csv`. The statistical work: design the grid, decide the
significance bar, read the breakeven-versus-actual win rate for each pair, and judge whether
any pair clears both baselines for real rather than by overfitting the test window. The same
sweep should be mirrored on the model track via Metric 2 so the chosen geometry is the one the
label is built on. Done when we can say, with a t-stat behind it, whether a non-lopsided pair
exists.

### Priority 1b: calibrate the label target to crypto volatility

Run the (target, stop, horizon) sweep described in 2.5 through `compute_label_return()`. Decide
whether +10/-5/20 survives contact with the coins' own ATR or whether a volatility-scaled
target (for example +2 ATR before -1 ATR) is better. This and Priority 1 are the same question
seen from the label side and the exit side; settle them together, then unify the three forked
configs from 2.4.

### Priority 2: sharpen the inputs, one feature at a time

1. Join the new daily flow imbalance (`daily_flow.csv`) into `build_dataset.py` as one feature;
   regenerate the dataset; rerun `train_model.py`; keep only if Metric 2 improves out-of-sample.
2. Regime and market context: the ATR band as a feature, trend strength, distance from a long
   moving average, whether volatility is rising, and Bitcoin's trend and volatility as
   market-wide context. This addresses the non-stationarity gap.
3. Multiple timeframes: weekly indicators for the bigger trend alongside the daily.
4. Move the model from a single 70/30 split to a rolling walk-forward, which also yields a
   cleaner regime-stratified Metric 3.

### Priority 3: only after the core clears the bar

Per-coin models; the optional aggTrades intraday flow; paper-trading wiring (Alpaca paper,
Binance testnet); a tiny live allocation last, behind the single safety switch, reviewed
weekly. The longer rule-strategy list in `tasks/next-steps.md` Priority 2 and 3 still stands
and should be read alongside this.

### Harness and hygiene (when convenient)

Model gap slippage in the backtest (fills are assumed exactly at stop or target); add a
portfolio concurrency cap to match the live three-to-four position limit; add a buy-and-hold
baseline measured only over the periods the signal is actually in the market. The README is
broadly stale, it predates the AA-evals hub, Metric 2, the 32-feature set, and the CONFIG
changes, and has some broken image paths; bring it current in one pass after Priority 1 settles
the geometry, so it does not document numbers that are about to change.

---

## 4. Model-tuning parameter menu (the concrete surface for statistical work)

Every knob, its file, its current value, and a Keller-informed range. `train_model.py` takes
about 44 seconds, close to a 45-second cap; run it alone.

Exit geometry (the Priority 1 sweep), in `walkforward.py` CONFIG and mirrored in the label:

- take_profit_pct: now 3.0 in walkforward, 10.0 in the controls notebook and label. Sweep, for
  example, 3 to 15.
- stop_atr_mult: 1.5 (about 8.5 percent realized). Sweep tighter, for example 0.75 to 2.0, and
  test a fixed-percent stop against the ATR stop.
- hold_window_days_max / HORIZON: 10 in walkforward, 20 in the label. Sweep 5 to 30.
- consider a trailing take-profit against the fixed take-profit.

Confidence filter (Metric 1), in `train_model.py`:

- CONF_HI 0.60, CONF_LO 0.40. Keller's defaults. Widening to 0.65/0.35 trades fewer, surer
  trades; narrowing trades more. Read the effect on Metric 2 expectancy and trade count
  together.

Model hyperparameters (LightGBM), in `train_model.py`:

- n_estimators 600, num_leaves 31, learning_rate 0.05, max_depth 6, min_child_samples 100,
  subsample 0.8, colsample_bytree 0.8, subsample_freq 5, class_weight balanced. These are
  conservative anti-overfit settings. Tune against the TimeSeriesSplit CV on the training set
  only; the test set is touched once.

Split and embargo, in `train_model.py`:

- TRAIN_FRAC for the time-ordered split, EMBARGO_DAYS = HORIZON. Moving to a rolling
  walk-forward is the Priority 2 change.

Cost, in `train_model.py`:

- COST_PCT 0.20 (0.15 fee plus 0.05 slippage). Stress-test the conclusion at 0.30 (no BNB) and
  at higher slippage; an edge that only survives at the lowest cost assumption is fragile.

---

## 5. Filepath index

The Keller report:

- `/Volumes/PortableSSD/Github/day-trader/research/Keller 2025 Machine Learning Models That Actually Work in Crypto Trading.md`
- `/Volumes/PortableSSD/Github/day-trader/research/Keller 2025 Machine Learning Models That Actually Work in Crypto Trading.pdf`

The model pipeline (Chapter Three, all editable .py, not notebooks):

- `/Volumes/PortableSSD/Github/day-trader/inputs/build_dataset.py` (features + triple-barrier label + trade_ret)
- `/Volumes/PortableSSD/Github/day-trader/inputs/train_model.py` (split, head-to-head, 60/40 filter, drives eval)
- `/Volumes/PortableSSD/Github/day-trader/inputs/eval_report.py` (the AA-evals writer; all four metrics)
- `/Volumes/PortableSSD/Github/day-trader/inputs/walkforward.py` (rule-strategy backtest and the exit-geometry sweep harness)

The evaluation hub and data:

- `/Volumes/PortableSSD/Github/day-trader/outputs/AA-evals/evaluation-scores.md` (and `.pdf`, `.docx`)
- `/Volumes/PortableSSD/Github/day-trader/inputs/binance-data/dataset_ccxt_10coins_2017-2026.csv` (26,772 rows, 32 features; the training set, moved here from outputs/CSV this session and conceptually a model input)
- `/Volumes/PortableSSD/Github/day-trader/outputs/3B-model-training/` (model.joblib, model_metrics.txt)
- `/Volumes/PortableSSD/Github/day-trader/outputs/experiment_log.csv`, `walkforward_trades.csv`, `walkforward_results.md`
- `/Volumes/PortableSSD/Github/day-trader/outputs/2A-market-screening/spread-options/` (four spread visual options + NOTES.md)

Historical trade-flow data (new this session):

- `/Volumes/PortableSSD/Github/day-trader/inputs/binance-data/flow_data.py` (scoped downloader + daily aggregator)
- `/Volumes/PortableSSD/Github/day-trader/inputs/binance-data/daily_flow.csv` (currently a BTC-only test slice; rerun for all 10)
- `/Volumes/PortableSSD/Github/day-trader/inputs/binance-data/` (the repo's own download-trade.py, download-aggTrade.py, README.md)
- `/Volumes/PortableSSD/Github/binance-public-data/` (the cloned Binance public-data repo: python/utility.py, python/enums.py, shell/)

Notebooks (canonical, Seamus works from these; paste-in unless authorized to edit):

- `/Volumes/PortableSSD/Github/day-trader/01-trader-metrics/01-trader-metrics.ipynb`
- `/Volumes/PortableSSD/Github/day-trader/02-trader-controls/02-trader-controls.ipynb`
- `/Volumes/PortableSSD/Github/day-trader/03-trader-execution/03-trader-execution.ipynb`

Governing documents and prior task files:

- `/Volumes/PortableSSD/Github/day-trader/CLAUDE.md` (the agent identity and hard rules)
- `/Volumes/PortableSSD/Github/day-trader/tasks/next-steps.md` (the morning draft; rule-strategy focus)
- `/Volumes/PortableSSD/Github/day-trader/tasks/keller-integration.md` (the Keller review and integration plan)
- `/Volumes/PortableSSD/Github/day-trader/tasks/controls-design.md`, `repo-organization.md`

---

## 6. Standing constraints (do not violate)

No live trading; place no orders; leave `LIVE_TRADING` off; spot only, never futures, never
margin, never leveraged tokens; never short. Work in new files and keep existing work
revertible. Do not touch `inputs/config.py` (keys only, read from the macOS Keychain),
`inputs/requirements.txt`, or `day-metrics.ipynb` unless asked. Plain words and ASCII only, no
emojis or decorative icons, no excited or opaque terminology; "market" or "market reference"
for the screened pool, "sample" for the selected coins. Be honest about edge: never present a
NO-GO result as tradeable, and guard against lookahead with the embargo and the score-once
discipline.

---

## 7. Open questions still to settle

DISCUSS WITH SEAMUS FIRST, after he has reviewed this task list and before any Priority 2 data
work begins: which Binance training data is actually the right kind and granularity for our
operations. We have not explored this, and it matters because the data choice constrains
everything downstream. The current training set is daily (1d) OHLCV pulled via ccxt, built for
the swing horizon. The open sub-questions: whether a swing book is best served by daily bars or
whether 4-hour or 1-hour bars would sharpen entries and exits without tipping into day trading;
whether we intend a day-trading sleeve at all, since that needs intraday bars (1m to 1h) and
probably the aggTrades order-flow, a much larger data commitment; which Binance public-data
product fits each need (klines for OHLCV and the cheap taker-buy flow, aggTrades only for
intraday flow detail, order-book depth only by forward capture); and the fact that the horizon,
the bar interval, and the label geometry must all agree, which ties this directly to Priority 1b.
Settle the data granularity with Seamus before committing to the Priority 2 feature and flow work.

The exact target, stop, and horizon (Priority 1 and 1b will decide). Whether the daily flow
feature earns its place. The Alpaca crypto commission, the one missing fee number, and whether
the Alpaca account is direct, self-directed, and cash-only. The trading coin set's intersection
with the execution venue, since Alpaca's crypto list is narrower than Binance. Whether to
refactor `build_dataset.py` onto the offline kline archives instead of the live ccxt fetch.
