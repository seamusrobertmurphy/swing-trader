# Session handover, 2026-06-21: 1-hour all-market data reset, CLAUDE.md and notebook reconciliation

Hand this to a fresh session. It records what this session decided and finished, the design
decisions still open for the 1-hour dataset build, and the planned next steps. It supersedes
the data-foundation parts of `tasks/session-handoff-2026-06-20.md`; that file's evaluation and
exit-geometry detail still stands.

---

## 1. What this session finished (done, in the repo)

- **Priority 0, notebook reconciliation (Option A), done and validated.** Added a
  `build_models(have_lgbm)` helper to `inputs/train_model.py` so the script and notebook share
  one estimator list. Rewrote `03-trader-execution/03-trader-execution.ipynb` into a thin driver
  that imports `split`, `confidence_filtered`, `evaluate`, `build_models`, `CONF_HI/CONF_LO/
  COST_PCT/EMBARGO_DAYS` from `train_model` and calls `eval_report.write_comparison`, so every
  notebook run now produces Metric 2 (P&L after costs), Metric 3 (regime AUC), `model_metrics.txt`
  and a full AA-evals record, identical to the script. Validated end to end on a subsample into a
  scratch dir (no pollution of the real `outputs/AA-evals`): the index row, the Metric 2 and 3
  sections, all five charts, and the PDF/DOCX all generated.

- **CLAUDE.md hard-rules fixed (8 edits), at Seamus's request.** Paper-trading line now describes
  the Binance testnet plus the `LIVE_TRADING` switch; the daily loss cap drops ClickUp and reads
  as a rolling 24 hours; gap-risk reframed as a 15 percent move within a day; leveraged/inverse
  ETF clauses trimmed; the Alpaca + `scripts/binance.sh` line replaced by `inputs/trade_binance.py`
  with the Binance money-switch kept; the -7 percent stop and 10 percent trail marked provisional
  pending the exit-geometry tuning, trail moved to Binance; the journal/memory lines keep the
  discipline but note the file layout is unbuilt. Seamus separately rewrote the mandate himself to
  crypto-first ("swing and day trader portfolio of spot crypto through Binance, possibly US
  equities through Alpaca later"), updated the env keys, and dropped one principle. NOTE: he keeps
  "day trader" in the mandate, so do not assume swing-only. He owns CLAUDE.md and directs specific
  edits; do not make sweeping unrequested changes. Review map: `tasks/claude-md-review-2026-06-20.md`.

- **README ten-coin confusion fixed.** The Chapter Two Controls section now shows the real
  four-gate screen output for 2026-06-20 (28 USDT pairs scanned, 9 passed) with the live metrics,
  built from `outputs/CSV/2A-sample_20260620.csv`. The Chapter One ten-coin table is relabelled as
  an illustration over the fixed training set, not the live scan, pointing down to the four-gate
  screen.

- **unCoded comparison written:** `tasks/uncoded-comparison-2026-06-20.md`, including a live-
  execution and security checklist Seamus asked to revisit later.

---

## 2. Design decisions made this session

- **Coin set: the full market, not the fixed ten.** Train on all ~433 active USDT spot pairs
  (measured live), point-in-time screened: each (coin, bar) row is kept only if it would have
  passed the four-gate screen as of that bar's date. This matches training to the dynamic trading
  universe and reduces survivorship bias. The fixed-10 list in `build_dataset.py` is decoupled
  from the live screen (it is a hand-picked large-cap list; the live screen on 2026-06-20 passed
  ZEC/TAO/NEAR and dropped DOGE/ADA/LINK). Survivorship is reduced but not cured, since fully
  delisted coins are gone even from the archives.

- **Bar interval: 1 hour.** Seamus chose the hourly frame deliberately, to analyse crypto intraday.
  All ~433 coins on 1h is about 0.7 GB zipped and trains in roughly 20 to 60 minutes under the
  point-in-time screen. The 2TB drive handles every interval up to 1-minute; only tick/1-second
  strains it.

- **Cost is a label and execution choice, not a data choice.** Bar interval is observation
  resolution; it does not force trade frequency or target size. Round-trip cost (~0.20 percent on
  Binance with BNB) is paid per trade and is fixed, so cost-versus-edge depends on the target size
  and turnover, which the label and execution set. So 1h data carries no cost penalty by itself;
  we pair it with a cost-defensible label and selective execution. Keller's "intraday edge dies on
  cost" was about his small intraday target, not about hourly data.

- **Source: offline data.binance.vision kline archives + ccxt top-up.** Established this session
  that ccxt `fetch_ohlcv` returns only the six OHLCV fields and is the SAME price data as the
  archives, just live and rate-limited. The archives' real value is reproducibility, the taker-buy
  flow columns that ccxt drops (the `flow_imbalance` feature), and cheap bulk download of MANY
  coins. They do not give more history.

- **Features: add pandas-ta.** Broaden the feature set with the `pandas-ta` library (Keller says
  feature breadth is where the AUC gap likely sits). Keep only what improves the after-fee result
  out-of-sample. Also join the daily/hourly `flow_imbalance` as a feature.

- **Exit-geometry sweep additions (Priority 1).** Add per-split trailing stops and a time-decaying
  take-profit ("sell time curve") as variants in the exit-geometry sweep, scored on the same
  after-fee scoreboard. Reconcile the three forked exit configs once the sweep settles.

- **Cadence and tooling.** Run about once a day, Seamus runs it himself or lightly schedules it,
  most likely no Claude Code Routines; dropping Perplexity and ClickUp. (Subject to revision if an
  intraday/day-trading sleeve is pursued, since the mandate still says "day trader".)

---

## 3. Open design decisions the 1-hour build forces (settle before/while building)

1. **The 1-hour label geometry.** The current triple-barrier label is +10% before -5% within 20
   DAYS. On hourly bars the horizon must be expressed in hours/bars and the target/stop chosen for
   the new frame. Make it configurable (target, stop, horizon-in-bars) and sweep it (this is
   Priority 1b). A cost-defensible starting point keeps a large-ish target so the ~0.20% cost stays
   small relative to it; the exact numbers are to be calibrated, not assumed.

2. **Feature windows scaled to 1 hour.** The existing EMA windows (14/91/125), RSI(14), ATR(14),
   realized-vol(7/30) are counts of BARS. On daily bars they are days; on hourly bars they become
   hours. They must be rethought for the 1h frame (for example, multiply by ~24 to keep the same
   wall-clock lookback, or choose new intraday-appropriate windows).

3. **Point-in-time screen without historical spread.** The live four-gate screen uses top-of-book
   spread, which klines do NOT contain. A historical screen replay can only use liquidity (rolling
   quote volume), ATR band, and history; the spread gate must be dropped or approximated for the
   point-in-time membership. Decide the adaptation.

---

## 4. Work planned next (the 1-hour build)

1. **Extend the downloader to 1-hour.** `inputs/binance-data/flow_data.py` is hardcoded to
   `INTERVAL = "1d"` (line 51); it needs an `--interval` argument and an interval-aware aggregate
   (it currently buckets by calendar date, which collapses 24 hourly bars into one). Fetch the coin
   list from Binance `exchangeInfo` (all active USDT spot pairs) rather than the fixed ten. Pull 1h
   klines for all coins into `inputs/binance-data/klines_1h/<SYMBOL>/`. ~0.7 GB zipped, thousands of
   small requests, so run it on the Mac, not the sandbox (45-second cap). Validate first on 2-3
   coins.

2. **Point-in-time screen replay.** Build a function that, per bar-date, marks which coins would
   have passed the (spread-free) screen, to assemble point-in-time membership over the wide set.

3. **Refactor `build_dataset.py` for the 1h frame.** Read the offline 1h archives, compute the
   features (existing ones with 1h-appropriate windows, plus pandas-ta families and flow), compute
   the configurable 1h triple-barrier label, apply the point-in-time membership, write the new
   dataset. Keep the current ccxt 1d path revertible.

4. **Retrain and measure.** Run `train_model.py` on the 1h dataset for a first honest after-fee
   number (Metric 2), land it in AA-evals, then run the label sweep (1b) and the exit-geometry
   sweep (1) on the new frame.

---

## 5. Key technical facts established this session

- 433 active USDT spot pairs on Binance now (measured via ccxt `load_markets`).
- Data size, full market, full history, by interval (zipped / point-in-time training rows / train
  time): 1d ~30 MB / 30-90k / 1-3 min; 4h ~0.2 GB / 0.2-0.5M / 5-15 min; 1h ~0.7 GB / 0.7-2M /
  20-60 min; 15m ~3 GB / 3-9M / hours; 1m ~40-50 GB / 40-130M / impractical with current tree
  models; tick/1s hundreds of GB to a few TB.
- A Binance daily kline row is ~141 bytes, 12 columns; ccxt `fetch_ohlcv` keeps only 6.
- `config.py` reads Alpaca + Binance keys from the macOS Keychain. The "Canada" note in it is a
  comment on the ALPACA line only; Seamus's Binance is registered in Ireland (EU, MiCAR), so
  Binance access is fine.
- The current dataset `inputs/binance-data/dataset_ccxt_10coins_2017-2026.csv` is 26,772 rows, 10
  coins, daily, built via ccxt; all 32 features and the label are COMPUTED in `build_dataset.py`
  from OHLCV, not pulled.

---

## 6. Standing constraints (unchanged)

No live trading; `LIVE_TRADING` stays off; spot only; never short, options, margin, futures,
leveraged tokens; never average down (so unCoded's DCA/dip-rebuy is deliberately NOT adopted).
Measure every change on the out-of-sample, after-fee scoreboard; keep only what beats buy-and-hold
and a coin-flip. Plain words and ASCII, no emojis or icons. Explain plainly; Seamus is learning the
methods and wants terms defined and repo facts confirmed before decisions. Work in new/revertible
files; do not touch `config.py`, `requirements.txt`, or `day-metrics.ipynb` unless asked. Seamus
owns CLAUDE.md.

---

## 7. Task list state at handover

Done: build_models helper; notebook Option A reconciliation; notebook validation. Open: extend
downloader to 1h; point-in-time screen replay; build_dataset 1h refactor (pandas-ta + flow +
configurable 1h label); retrain on 1h; label sweep (1b); exit-geometry sweep with per-split TSL and
time-curve variants (1). See `tasks/uncoded-comparison-2026-06-20.md` and
`tasks/session-handoff-2026-06-20.md` for the carried-forward detail.
