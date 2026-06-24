# Multi-timeline / multi-resolution training data — build plan

Next steps to build training data across multiple decision frames (daily, 4h, 1h) and multiple
timeframe contexts, so the model can be trained and compared on the frame where after-fee edge
actually survives. Written 2026-06-23, after the 1h evidence settled.

## Why this, and why coarser not finer

Tonight's experiments converged: 1h *direction prediction* is at the efficient-market floor.
- Label-geometry sweep: 11 geometries, all NO-GO, win rate ~2-3 pp below breakeven at every target/stop.
- Longer-horizon (10-20 day) sweep: same sub-breakeven pattern.
- 7-model zoo (incl. 3 GBMs): AUC ~0.50; flexible models overfit (HistGBM ratio 0.35).
- Supertrend baseline + exit sweep + Monte Carlo: NO-GO / FRAGILE (99.7% prob of loss across 10k sims).
- External: the GBBC SuperTrend author states the raw signal is "a coin flip (48%)", "bleeds out on the
  1 hour and below", and "only holds up at the 4-hour and above" (research/GBBC 2026 ...).

So the direction is **coarser decision frames**, where trend survives fees, plus multi-timeframe
context and a regime gate (KER) to trade only efficient trends. And coarser is CHEAP: a 4h frame is
1/4 the rows of 1h, a daily frame 1/24. The whole 1d + 4h + 1h set is < 2x the current 1h cost. Finer
(15m+) is the expensive, evidence-disfavoured direction and is NOT in this plan.

## Already done (the 1h frame)

- Multi-timeframe FEATURES on the 1h frame: `f_4h_`, `f_d1_` (4h + daily RSI/EMA-spread/momentum/
  ATR%/Supertrend), merged causally with `merge_asof` on the higher-tf close time. Validated
  no-lookahead. See `build_dataset_1h.multitf_block`.
- KER regime gate: `f_mst_` (Modern Adaptive Supertrend) carries the Kaufman Efficiency Ratio, the
  chop-vs-trend measure that lets the model trade only efficient-trend regimes.

## Target architecture

- **Decision frames to build:** `1D` (daily), `4h`, `1h` (existing). 15m deferred (needs out-of-core).
- **Per frame:** the same feature blocks, with windows scaled to the interval, plus that frame's own
  higher-timeframe context (daily frame -> weekly/monthly context; 4h frame -> daily/weekly; 1h ->
  4h/daily, done).
- **Storage:** `inputs/binance-data/dataset_<interval>_allmarket.parquet` per frame;
  `inputs/binance-data/klines_<interval>/<SYMBOL>/` per interval; `flow_<interval>.parquet` per interval.

## Progress (4h frame, started 2026-06-23)

- **Builder is interval-aware (step 2 DONE).** `build_dataset_1h.py` now carries `INTERVAL_HOURS` +
  `configure(interval_hours)`, which retunes the interval-sensitive globals IN PLACE (so configs bound
  as function defaults update too): WC wall-clock windows = day-specs x `BARS_PER_DAY`, LABEL horizon =
  2 days x `BARS_PER_DAY`, SCREEN windows + ATR band (daily band / sqrt(bars-per-day): 4h -> 1.0-4.9%),
  `MTF_RULES` per frame (1h->4h+1d, 4h->1d+1w, 1d->1w+1M), and the klines/flow/dataset paths.
  `gap_stats` is interval-aware; `multitf_block` reads `MTF_RULES` at call time. `configure(1)` reproduces
  the shipped 1h frame EXACTLY (regression-checked: globals identical, BTC build frame-equal). Build any
  frame via `build_dataset_1h.py --interval {1,4,24}`.
- **4h download running** as 6 resumable parallel shards over the 600 on-disk survivorship coins
  (`acquire_vision.py download --interval 4h`), into `klines_4h/`. Cached files skip instantly.
- **4h chain validated** on BTC+ETH: 90 features (same design as 1h), daily+weekly MTF context
  (`f_d1_`, `f_w1_`) correctly replacing 1h's 4h+daily, flow joined, no-lookahead confirmed (weekly
  context steps once per 42 bars = 1 week). Base rate 0.262 (below 1h's ~0.31) -- the conservative
  stop-before-target rule penalizes coarser bars, so the 4h LABEL geometry needs its own sweep (step 5).
- **Autonomous finish:** `inputs/binance-data/orchestrate_4h.sh` waits for the shards, aggregates the
  full 4h flow over the on-disk universe, builds `dataset_4h_allmarket.parquet`, validates, and touches
  `_4h_DONE`. Logs to `_orchestrate_4h.log`.

## Steps (ordered)

1. **Download higher-tf klines (cheap, after the current 1h survivorship pull finishes).**
   `acquire_vision.py` already takes `--interval`:
   ```
   .venv/bin/python inputs/acquire_vision.py download --interval 4h
   .venv/bin/python inputs/acquire_vision.py download --interval 1d
   ```
   These are 1/4 and 1/24 the size of the 1h pull. Same survivorship-complete universe.

2. **Make the builder interval-aware.** `build_dataset_1h.py` hard-codes 1h assumptions; generalize:
   - `BARS_PER_DAY = round(24 / interval_hours)` (1h->24, 4h->6, 1d->1).
   - Define WC/HR window families and the LABEL horizon in DAYS, convert to bars via `BARS_PER_DAY`,
     so a "14-day" lookback stays 14 days at every resolution (the wall-clock principle, generalized).
   - Scale the SCREEN windows (qv_window, spread_window) the same way.
   - Parameterize `MTF_RULES` per frame (1h -> 4h+1d; 4h -> 1d+1w; 1d -> 1w+1M).
   - Output `dataset_<interval>_allmarket.parquet`; keep `build_dataset_1h.py` as the 1h instance.
   - Cleanest implementation: a single `build_dataset.py(interval=...)` the three frames call, or an
     `INTERVAL` constant + a thin wrapper per frame. Keep the 1h path byte-identical after the refactor
     (regression-check the row/feature counts).

3. **Aggregate flow per interval:** `flow_data.py --interval 4h` and `--interval 1d` ->
   `flow_<interval>.parquet`.

4. **Build the daily and 4h datasets** (fast — small row counts). Sanity-check dimensions and base rate
   via the chapter-3 EDA cell pointed at each parquet.

5. **Run the full pipeline at each frame** and compare after-fee OOS, head to head:
   split-checks audit -> glmnet variable selection -> train (zoo) -> label sweep -> exit-geometry sweep
   (per-coin trailing) -> model assessment -> Monte Carlo robustness. Same gate at every frame.

6. **Adopt the frame with a demonstrable, ROBUST edge.** Most likely candidate on the evidence: 4h or
   daily, entries gated on high `f_mst_ker_rank` (efficient trend), confluence of features, tight 2R
   exits. If a frame clears both the after-fee GO and the Monte Carlo ROBUST gate, it becomes primary.

## No-lookahead rules (carry to every frame)

- Higher-tf context features: `merge_asof(direction="backward")` on the higher-tf CLOSE time, so a bar
  only ever sees coarser candles already closed (validated pattern in `multitf_block`).
- Never pool rows from different resolutions into one training matrix (different row meanings,
  overlapping information). Each frame is its own dataset; combine only at the SIGNAL level (e.g., a 1h
  entry confirmed by the daily model), never at the row level.
- Embargo and the final-year OOS hold-out are defined in DAYS, so they are identical across frames.

## Cost (from the resolution analysis)

| frame | rows vs 1h | dataset parquet | RAM | klines |
| --- | --- | --- | --- | --- |
| 1D | 1/24 | ~0.2 GB | ~0.3 GB | ~3 GB |
| 4h | 1/4 | ~1.4 GB | ~2 GB | ~18 GB |
| 1h (current) | 1x | ~5 GB | ~8 GB | ~72 GB |

The full multi-frame set is cheaper than one 15m frame would be, and points the right way per the evidence.

## Honest expectation

The goal is to FIND the decision frame where after-fee, survivorship-correct, Monte-Carlo-robust edge
exists — not to add data for its own sake. If none of 1d/4h/1h clears the gate, that is itself the
answer, and the next lever is information (funding/OI/liquidations/order-book), not more resolution.
