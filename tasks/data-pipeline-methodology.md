# Data pipeline methodology: acquisition, profiling, time-aware splitting

Written 2026-06-21. Implements `tasks/task-request-data-pipeline-methodology.md`. Three
dependent stages produce a survivorship-aware, reproducible data pipeline from raw
acquisition through to the train/test split. The stages run in order because each sets
parameters the next consumes, and the bias they defend against enters at Stage A and is
invisible by Stage C. Code: `inputs/acquire_vision.py`, `inputs/profile_panel.py`,
`inputs/wf_splitter.py`. Stage C reuses the existing `inputs/split_checks.py` for the
post-split readiness audit.

## Why this exists

The model was being trained on a universe built from Binance `exchangeInfo`, which returns
only symbols trading today. Every coin that delisted, was rugged, or quietly died was
dropped before a single file was fetched. A model fit on that list learns the statistics of
survivors and overstates how it would have traded in real time. The crawl this pipeline runs
finds 612 USDT pairs that ever had hourly data against the roughly 433 active today: close to
a third of the real historical opportunity set was missing. The defences are all upstream of
the model and none announce themselves, so they are built as explicit, audited stages.

## Stage A: acquiring archival data that includes dead coins

The data for dead coins is not the problem; `data.binance.vision` retains delisted symbols
for years. The problem is enumeration. `acquire_vision.py` sources the symbol universe from
the archive listing itself rather than a live endpoint.

`crawl_archive_symbols` paginates the S3 listing of `data/spot/monthly/klines/` and returns
every symbol that ever had data, delisted ones included. The vanity host
`data.binance.vision` serves the website rather than the bucket XML, so the crawler hits the
underlying path-style S3 endpoint directly, with a second host as fallback. Leveraged tokens
(UP, DOWN, BULL, BEAR) are recorded but excluded by default because the strategy forbids
them. The crawl returns 612 USDT pairs in about four seconds.

`download_symbol` pulls monthly klines with a daily-file top-up for the current open month,
into `inputs/binance-data/klines_1h/<SYMBOL>/`, exactly where `build_dataset_1h.py` already
reads, so the dead coins land alongside the survivors with no path changes. Every file is
verified against its `.CHECKSUM` SHA-256 companion, with one re-download on mismatch. The
download is resumable: it skips files already on disk, so a stalled pull (the earlier
all-market run died on a read timeout) is simply re-launched, and transient network errors
retry with exponential backoff. Months that 404 are absent because the coin had not listed or
had delisted, which is the lifespan signal Stage B reads, not an error.

Timestamps are normalised per value: Binance switched from millisecond to microsecond stamps
in 2025-01 and a single coin's archives can mix both, so the loader classifies each value by
magnitude rather than assuming one scale across the span.

`snapshot_exchange_info` pulls the live active list once and writes it to a dated file. The
active-versus-delisted partition is only valid as of that date, so the date is part of the
artefact and the survivorship audit must read the dated snapshot, never a live call at
analysis time.

The Stage A.5 guard, `audit_dead_coins`, confirms known-delisted pairs (FTTUSDT, LUNAUSDT,
USTUSDT, SRMUSDT and others) are present in the crawled universe before any downstream
diagnostic is trusted. If none are present, the universe was built from a live list and Stage
A must be redone. All ten checked pairs are present, and FTTUSDT downloads and checksums
cleanly years after its removal, which confirms the dead-coin data is genuinely recoverable.

The heavy pull belongs on the operator's Mac: `python inputs/acquire_vision.py download
--interval 1h`. The crawl, snapshot and audit are quick and run anywhere.

## Stage B: profiling the panel to choose parameters from evidence

`profile_panel.py` measures the panel's properties so every split parameter is justified by a
diagnostic rather than assumed. It reads the raw 1h kline zips one symbol at a time, so the
full panel never has to fit in memory and zero-volume and zero-range bars are counted
faithfully; the aggregated flow table drops zero-volume bars, which would hide exactly the
quality signal the screen wants. Timestamps are tz-aware UTC throughout.

One streaming pass per symbol builds the metadata row that combines three diagnostics.
Coverage and lifespan (B.1): first and last bar, bar count, calendar span, and the
realised-to-expected ratio at hourly frequency. Gap and continuity (B.2): the complete hourly
index is built over each coin's own span, not the global span, or every coin would show
enormous leading and trailing gaps; missing positions are run-length encoded for gap count
and largest gap, and a hole longer than 72 hours flags a halt or delisting rather than
ordinary low-liquidity missingness. Liquidity and quality (B.6): quote-volume distribution,
zero-volume and zero-range bar counts, and the longest stale-price run.

The listing and delisting timeline (B.3) aggregates first and last bars into monthly entries,
exits and a cumulative-active curve. The breadth-over-time curve (B.4) counts, per month, the
coins alive and the coins alive and clearing the coverage cut; the usable window should start
where that count first supports a cross-sectional model. The survivorship audit (B.5)
partitions the panel against the dated snapshot and reports the delisted share and the bar
volume the dead coins contribute; a near-zero delisted share means the panel is contaminated
and Stage A must be revisited.

Point-in-time universe construction (B.7) is the operational guard against look-ahead in
membership. For each fold-open date it builds the eligible set using only information
available at that date: listed at least the minimum history before the open, still trading at
the open, clearing the coverage cut, and passing a trailing quote-volume floor computed over
the months strictly before the open. Lifetime volume is never used, because selecting the top
coins by lifetime volume leaks the future into membership; top-by-volume must mean
top-by-volume-as-of-the-window-open, recomputed forward. The threshold sweep (B.8) varies the
minimum-history and coverage cut-offs across a small grid and reports how many symbols survive
and the per-fold universe size, so a choice that gains or loses a third of the universe under
a small change is made consciously.

The parameter decisions these diagnostics drive (B.9):

- Usable start date: the first month with at least 30 alive-and-eligible coins, from the
  breadth curve. Before that the panel is too thin for a cross-sectional model; a 10-coin
  fold and a 300-coin fold are not equal evidence.
- Minimum history: the longest feature lookback plus the label horizon plus a 30-day buffer,
  read directly from `build_dataset_1h` so it tracks the windows that set it. With the current
  windows that is 3000 + 48 + 720 = 3768 bars, about 157 days. The floor exceeds what the
  pipeline needs to produce one clean labelled observation, with margin.
- Point-of-entry rule: a coin enters at its first valid bar, which mirrors when trading would
  actually begin, rather than having to span the full fold, which would discard information
  and bias toward longer-lived coins. The per-fold universe records membership so coins
  cannot drift in and out invisibly.
- Purge and embargo: max(longest feature lookback, label horizon) = 3000 bars, about 125
  days. This is the value Stage C consumes.

Artefacts are persisted run-timestamped under `inputs/binance-data/profile/<stamp>/`, with a
`latest.txt` pointer: the symbol metadata table, the entry/exit log, the breadth curve, the
timeline, the monthly quote-volume table, the threshold sweep, the per-fold universe lists
(carrying both the `BTCUSDT` and `BTC/USDT` symbol forms so Stage C matches whichever the
dataset uses), the decision summary, and static PNG plots of the timeline, breadth and gap
distribution. Run with `python inputs/profile_panel.py`.

## Stage C: time-aware splitting and evaluation

`wf_splitter.py` replaces any random or stratified split with a forward-chained walk-forward
design. It is the regime-stability companion to `train_model_1h.split`, which holds out a
single final year for the headline GO/NO-GO. Where that asks whether an edge survives the most
recent year, this asks whether the edge is stable across regimes or lives in one.

The objective is to estimate out-of-sample performance under regime drift, not interpolation
within a known distribution. The data-generating process drifts: the 2017-18 ICO mania, the
2021 bull, the 2022 deleveraging and the current regime are different processes. A split that
interleaves test bars among training bars borrows the future to predict the past and yields an
error estimate that will not survive live trading. Stratified sampling is rejected because
forcing similar class proportions across splits by drawing regardless of time destroys the
temporal ordering that is the whole object of interest; it measures interpolation, when the
question is extrapolation forward into an unknown regime. This rationale is exposed as
`wf_splitter.METHODOLOGY` so the notebook renders it verbatim.

`WalkForwardSplitter` produces several out-of-sample folds on calendar boundaries shared
across all coins, in either an expanding scheme (train on all history before the cut) or a
rolling scheme (train on the trailing window). At every cut it purges a band equal to
max(feature lookback, label horizon), read from `build_dataset_1h` so it can never drift from
the features that set it; bars within that distance of the seam share information across the
split. The purge falls on the training side, which is the operative leak in a forward chain
because training is always before test; an `embargo_test_side` flag can also drop the leading
band of each test window, off by default because in a pure forward chain that only discards
out-of-sample evidence. The split is on time, not on coins: a coin appears in both train and
test, but only its earlier bars train and its later bars test. Whole-coin holdout is not used;
it answers a different question and is left as a separately scoped experiment.

Each fold draws its eligible coins from the Stage B point-in-time universe lists, so
membership never depends on the future, falling back to all coins if no profile run is
present. Transforms are fit on train only and applied forward (`scale_fit_apply`); nothing
past the training cutoff leaks backward into features or scaling. `fold_table` reports the
per-fold spans, row counts and coin counts as the composition audit, and
`evaluate_walkforward` fits a model per fold and reports AUC and buy-precision both per fold
and as a coin-count-weighted aggregate, so a thin early fold is not read as equal evidence to
a broad later one. Run with `python inputs/wf_splitter.py --demo-model`.

## Validation

Each stage was smoke-tested end to end. Stage A: the crawl returns 612 historical USDT pairs
against 424 active in a same-day snapshot, a 30.7% delisted share, all ten known-delisted
pairs present, and a checksum-verified download of both a survivor and a delisted coin. Stage
B: the profiler runs over a mixed live/dead sample and writes every artefact plus plots, with
the derived minimum history at 157 days and purge/embargo at 125 days. Stage C: the splitter
yields the expected expanding and rolling folds with the 125-day embargo gap confirmed on
every fold, point-in-time universes correctly restricting membership, and the per-fold
evaluation recovering a planted signal at AUC 0.72 with coin-weighted aggregation. The
smoke-test runtime was the sandbox; the production runtime is the Mac project `.venv`, which
holds lightgbm, scikit-learn and pyarrow.

## What remains

The heavy survivorship-complete download runs on the Mac. Once `klines_1h` holds the full
historical universe, re-aggregate flow, rebuild `dataset_1h_allmarket.parquet`, run
`profile_panel.py` to fix the usable start and minimum history from the real breadth curve,
and run the model chain on the corrected panel. Every after-fee out-of-sample number to date
was computed on the survivor-only panel and should be treated as an upper bound until the
rebuild lands.
