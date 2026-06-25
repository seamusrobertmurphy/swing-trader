# 5-minute scalp frame: build brief (2026-06-24)

Operator decision: add a higher-resolution **5-minute** decision frame to explore scalping, built for a
**select set of eight coins** chosen by a move-over-cost screen rather than the full market. This brief
records the coins, the pipeline changes, the exact build commands (run on the Mac, in the `.venv`), and
the honest caveats. It does not change the swing/day-trade frames; 1h/4h/1d are untouched.

## The eight coins (locked)

Chosen by ranking the active universe on `move / (spread + round-trip fee)`, where move is recent 1h ATR
scaled to a 5-minute bar (~ATR_1h / sqrt(12)), spread is the Corwin-Schultz high-low proxy (klines carry
no top-of-book spread), and the round-trip fee is 0.15% (BNB-discounted taker). Full ranking in
`outputs/scalp_ranked.csv`.

    BTCUSDT  ETHUSDT  SOLUSDT  SUIUSDT  TONUSDT  DOGEUSDT  NEARUSDT  PEPEUSDT

BTC/ETH/SOL are the deep-liquidity anchors and the benchmark; SUI/TON/DOGE/NEAR/PEPE carry the per-bar
move a scalp needs. CHIP and TAO are strong alternates if the set is widened.

## Pipeline changes (done, validated)

All in `inputs/build_dataset_1h.py`, additive and backward-compatible (the 1h/4h/1d frames are byte-for-
byte identical; regression-checked):

- `configure()` now accepts an interval **label** (`5m`, `15m`, `1h`, `4h`, `1d`) as well as the old int
  hours. `5m`/`15m` are the sub-hour scalp frames. `INTERVAL_HOURS` becomes a float for sub-hour frames
  (5m = 0.0833) and stays an int for hour+ frames.
- New frame config: `_FRAME_MIN` (minutes per bar), per-frame `_SCREEN_ATR_BAND` (5m band 0.15-0.71%,
  the daily 2.5-12% band scaled by 1/sqrt(288)), `_MTF_RULES` (5m and 15m look up to **1h + 4h**, new
  `f_h1_` prefix), and a sub-hour **scalp label** `_SUBHOUR_LABEL`.
- The scalp label replaces the day-scaled 2-day barrier with a short one: 5m = **+1.5 / -1.0 ATR within
  24 bars (~2 hours)**; 15m = 16 bars (~4 hours). Starting values, to be swept like the hour+ label.
- The wall-clock feature family stays day-defined (real-time lookback preserved), so at 5m it spans many
  bars (a 125-day EMA is 36,000 bars); the intraday `f_hr_` family is frame-native and is the scalp-
  relevant part. A coin needs ~120 days of 5m history before the slow features populate.
- CLI: `build_dataset_1h.py --interval 5m` (the arg now takes labels). `acquire_vision.py` already
  accepts `--interval 5m --symbols ...` with no change.

Validated: `configure('5m')` sets BARS_PER_DAY 288, the scalp label, the 0.15-0.71% ATR band, 1h/4h MTF
context, and `klines_5m`/`dataset_5m_allmarket.parquet` storage; `build_coin` runs end-to-end on
synthetic 5m bars producing all feature families plus the new `f_h1_`/`f_4h_` blocks.

## Build commands (run on the Mac, from the repo root, in the .venv)

    cd /Volumes/PortableSSD/Github/day-trader

    # 1. Download 5m klines for the eight coins (exchange-direct, checksummed, resumable)
    .venv/bin/python inputs/acquire_vision.py download --interval 5m \
        --symbols BTCUSDT ETHUSDT SOLUSDT SUIUSDT TONUSDT DOGEUSDT NEARUSDT PEPEUSDT

    # 2. Build the 5m dataset -> inputs/binance-data/dataset_5m_allmarket.parquet
    .venv/bin/python inputs/build_dataset_1h.py --interval 5m \
        -s BTCUSDT ETHUSDT SOLUSDT SUIUSDT TONUSDT DOGEUSDT NEARUSDT PEPEUSDT

    # 3. (optional) 5m trade-flow table, adds the f_flow_ features; the build runs fine without it
    .venv/bin/python inputs/binance-data/flow_data.py --interval 5m \
        -s BTCUSDT ETHUSDT SOLUSDT SUIUSDT TONUSDT DOGEUSDT NEARUSDT PEPEUSDT
    # then re-run step 2 so the build joins flow_5m

Rough footprint: ~3-4M rows across the eight coins (BTC ~945k 5m bars since 2017; SUI/TON/PEPE shorter),
a few hundred MB of raw zips, the built Parquet far smaller.

## Honest caveats (carry these into the analysis)

- This contradicts the swing thesis and the controls layer, which explicitly rules out scalping on the
  fee wall. It is a research probe with a high prior against it, not a pivot. It clears only if the
  out-of-sample, after-fee result beats both buy-and-hold and a coin flip, same bar as everything else.
- The move/cost ratio is **under 1 on the conservative proxy spread** and only **~1-1.9 with realistic
  tight spreads**, so a single 5m bar barely covers the round trip. Scalping math only survives with
  **maker fills**; taker fees through the scheduled poller is a slow bleed.
- Klines hide the spread. The honest 5m backtest needs real top-of-book spread and slippage from the
  aggregated-trades archives; the Corwin-Schultz proxy understates tradeability for the liquid names.
- Direction prediction is already at the efficiency floor at 1h and gets noisier finer; expect the 5m
  edge, if any, to come from microstructure (flow, regime), not from the same trend features.

## Next steps after the data lands

1. Reprofile the eight coins at 5m (gap gate, real ATR band, base rate of the scalp label).
2. Sweep the scalp label geometry (target/stop/horizon) on the after-fee scoreboard.
3. Re-run the suitability screen with **live top-of-book spreads** (ccxt, on the Mac) to confirm the set.
4. Wire a 5m section into notebook 3 once the dataset exists (frame comparison vs 1h/4h).
