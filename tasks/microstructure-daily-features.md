# Microstructure Daily Features

Planned 2026-08-16, build after the first 1d dataset and its edge matrix land, so the baseline is read before the feature set changes. Operator direction: use higher-resolution data. Evidence constraint: sub-daily decision frames fail the fee wall (1h floor, 5m ruled out, 4h short by 5-10bp), so resolution enters as features for the daily frame and as execution timing, never as the decision cadence.

## Feature Families

All computed from existing on-disk 1h data (klines_1h, flow_1h.parquet), aggregated per coin per day, causal, scale-invariant, prefix `f_ms_`:

1. Flow imbalance: daily sum and 7d mean of taker-buy minus taker-sell share from flow_1h; the only order-flow signal available offline.
2. Range construction: close position within the day's range, up-hour vs down-hour volume split, realized vol from hourly returns vs daily range (the Garman-Klass/Parkinson family, using what a daily bar alone cannot see).
3. Volume concentration: Herfindahl of hourly volume shares (pump days concentrate; healthy accumulation spreads).
4. Gap behaviour: overnight-equivalent hour-to-hour jumps beyond k sigma, count and signed sum.

## Wiring

`build_dataset_1h.py` gets an optional `microstructure_block(day_df, hourly_df)` in the 1d frame path only; requires the 1h archive present for the coin, else NaN (in-house baseline never depends on it). Then rerun `cross_sectional_regime.py --interval 1d` with the new candidates against the same gates on the after-fee scoreboard.

## Execution Timing

Separate track: once a daily signal fires, the 5m frame (exists for the 8 majors) times the entry inside the day; measured as achieved-fill improvement vs the daily open, not as a signal. Feeds the maker-entry layer in `trade_binance.py`.

## Candidate Narrowing

`inputs/candidate_screen.py` (live fee-adjusted range screen; extend to trailing 30d averaging) intersected with `inputs/edge_attribution.py` (which coins carried the OOS gated edge) defines the narrow tradeable book. Rank broadly, trade narrowly.
