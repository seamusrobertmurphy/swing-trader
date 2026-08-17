# Backup Workplan

Written 2026-08-17, at the operator's direction, after the falsification harness killed the last open crypto candidate (f_mst_dir under the breadth gate, fold pass rates 33% and 27% against the 60% bar; record `outputs/AA-evals/2026-08-17/mst-gate-walkforward-20260817.md`). The year's honest summary: a real, stable cross-sectional edge exists in crypto but sits 5 to 12 basis points under a 15 to 20 basis-point fee wall, and no gate, label, frame, or feature family has closed the gap. Both tracks below attack the wall itself rather than the edge: Track A moves to a venue where the wall is a quarter the height; Track B replaces the assumed cost floor with a measured one.

## Track A

Alpaca US equities, paper first. The fee arithmetic is the whole argument: Alpaca charges no commission, so the round trip on a liquid large cap is the half-spread twice plus slippage plus the SEC and TAF sell-side fees, roughly 2 to 6 basis points against crypto's 15 to 20. Our best crypto cell died 5 basis points short of a 15 basis-point bar; the same edge quality against a 5 basis-point bar clears. Independently, cross-sectional momentum on equities is the most documented factor in finance, so the prior is better than crypto's. The machinery transfers almost whole: every feature family is scale-invariant, the ranking, screen, embargoed split, and the new kill-criteria harness are frame-generic, and the mandate (spot only, never short, never margin) maps cleanly. One equity-specific constraint: the pattern-day-trader rule limits accounts under $25k to three intraday round trips per five days, so holds are one day minimum, which the daily frame already assumes.

### Phase A1

Plumbing, half a session. Verify the `ALPACA_*` variables against the paper endpoint, install `alpaca-py` into the project `.venv` (pip, then clear the exFAT `._` litter), and spike-test: account, market clock, daily bars for SPY. Abort loudly per the environment rule if a key is missing.

### Phase A2

Data, one session. `inputs/alpaca_data.py`: enumerate tradable US equities from the assets endpoint, screen by dollar volume, pull maximum-history daily bars, store per-symbol Parquet under `inputs/alpaca-data/`. Honesty note recorded in the module docstring: Alpaca history is survivor-biased (delisted names absent), the opposite of our survivorship-complete crypto discipline, so every early result is an upper bound and says so; a delisting-complete source is a later upgrade, not a blocker for the first read.

### Phase A3

Features and label, one session. Adapt the 1d frame in `build_dataset_1h.py` behind a source adapter: keep the wall-clock, intraday, extra-TA, Supertrend, and regime families as they are; replace the BTC lead-lag block with SPY lead-lag and beta (`f_spy_`); drop the funding and flow blocks (no equivalents); keep the gap features, which matter more where overnight gaps are real. Re-sweep the label geometry on equity volatility (equity ATRs are a third of crypto's; the +3/-1 over 20 days result does not transfer untested).

### Phase A4

The edge test, one session. The same edge matrix, upgraded by universe depth: hundreds of names support decile ranking at a 50-name floor instead of crypto's thin terciles. Gate on SPY above its trend. Cost model 5 basis points round trip, conservative. Embargoed final-year out-of-sample, scored once, then the walk-forward kill harness (generalize `mst_gate_walkforward.py`) with the same pre-registered criteria: 60% fold pass rate, tradeable gate width, attribution breadth. Decision gate: only a SURVIVES verdict advances to A5.

### Phase A5

Paper execution, one session. `inputs/alpaca_trade.py` against the paper endpoint (a true paper venue, unlike Binance): the hard rules enforced mechanically (5% cap, three new positions per week, 10% cash floor, stops, never short, never margin), holds of at least one day for PDT safety, notification discipline unchanged. `LIVE_TRADING` semantics unchanged and false.

## Track B

Finer-resolution Binance data, 1-minute klines. The standing evidence constrains the purpose: sub-daily decision frames fail the fee wall (the 5m frame is ruled out, 1h is the floor), so 1m data enters as execution timing and measured cost only, never as a decision cadence. The deliverable is replacing the assumed 0.15% achievable round trip with a measured number per coin, and timing entries for whatever signal ever clears.

### Phase B1

Scope, decided a priori. Symbols: the eight scalp majors plus the narrow book, not the full market. Intervals: 1m klines; aggTrades only for BTC and ETH if the kline study proves insufficient. Size: the all-market 5m archive is 936M, so twenty symbols of full-history 1m is an estimated 5 to 15 GB; the SSD has 1.1 TB free. Full-market 1m is explicitly out of scope.

### Phase B2

Acquisition, half a session. `acquire_vision.py` is interval-generic already: `download --interval 1m --symbols ...`, checksummed and resumable, landing in `inputs/binance-data/klines_1m/`.

### Phase B3

Configuration, half a session. Add `"1m": 1` and `"3m": 3` to `_FRAME_MIN`, extend `_SUBHOUR_LABEL` (1m: +1.5/-1.0 ATR within 60 bars) and the ATR-band scaling (divide the daily band by sqrt(1440)). Additive change; regression-check that the 5m, 1h, 4h, and 1d frames build byte-identical.

### Phase B4

The execution study, one session, the point of the track. A maker-fill simulator on 1m bars: place a post-only bid at the decision bar's close, filled when a later bar's low crosses it within the wait window, cancelled otherwise, mirroring `trade_binance.place_entry` exactly. Outputs per coin: fill rate, achieved price versus decision price, and the measured effective round-trip cost including misses. That number either validates `ACHIEVABLE_COST_PCT = 0.15` or corrects it, and every eval that used the scenario inherits the correction. Explicit non-goal, restated: no 1m model, no scalping revival.

## Sequencing

Track A first, then B. A changes which verdicts are possible (the bar drops fourfold); B refines a number that only matters once something clears a bar. The decision gate between them: after A4's out-of-sample read, an operator decision on paper deployment. Both tracks carry pre-registered kill criteria before any run, per the discipline that killed the crypto candidate today. Estimated effort: Track A four to five sessions, Track B two to three.
