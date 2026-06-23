# Task Request: Data Acquisition, Sample Profiling, and Time-Aware Splitting for the Crypto OHLCV Model

**Scope:** The full data pipeline of the OHLCV training notebook, from raw acquisition through to the train/test split, plus the methodology documentation that accompanies each stage.

**Dataset:** Hourly OHLCV, ~400 Binance spot pairs, target span 2017-08-17 to present.

**What this task delivers:** A defensible, reproducible, survivorship-aware data pipeline in three stages that run in order: acquire the data (including dead coins), profile it to choose parameters from evidence, then split it time-aware for honest out-of-sample evaluation. Each stage carries a methodology note explaining not just what was done but why, so the design survives review and the next person can follow the reasoning.

**Read this first.** The three stages are dependencies, not options. The splitting design (Stage C) names parameters it does not set: usable start date, minimum history, purge gap, per-fold universe. Those are set by the profiling diagnostics (Stage B). The diagnostics are only honest if the panel actually contains delisted coins, which is the job of acquisition (Stage A). Do not start at Stage C with a convenient dataset; the whole point is that the bias enters at Stage A and is invisible by Stage C.

---

# Stage A — Acquiring archival data that includes dead coins

A model trained only on coins that still trade today learns the statistics of survivors and overstates real-world performance. Every coin that delisted, was rugged, or quietly died is part of the true historical opportunity set, and a backtest that omits them is optimistic in a way that will not survive live capital. In crypto this is severe: Binance lists hundreds of pairs and removes them constantly, and the graveyard is larger than the living set. The acquisition stage exists to get the dead coins into the panel.

## A.1 The core trap

The data is not the problem; the symbol list is. Binance's own public archive at `data.binance.vision` does retain delisted symbols. Historical klines for dead pairs remain downloadable years after the pair stopped trading; the canonical example in Binance's own repository uses `ADABKRW`, a long-delisted pair, and the monthly 1h file still serves. So the dead-coin data exists and is free.

The trap is enumeration. Binance's helper `fetch-all-trading-pairs.sh` and any `exchangeInfo` call return only currently active symbols. Build the download list from those and every delisted coin is excluded before a single file is fetched, reproducing survivorship bias at the acquisition layer no matter how careful the later analysis is. The fix is to source the symbol universe from something that records coins that existed historically, not only coins that trade now.

## A.2 Recommended primary source: Binance Vision

For Binance spot hourly, the exchange's own archive is the right primary source: free, no rate limits on the file store, canonical, checksum-verified.

- Files live under `data.binance.vision/data/spot/monthly/klines/{SYMBOL}/1h/{SYMBOL}-1h-{YYYY}-{MM}.zip`, with daily files under the parallel `daily` path for recent dates not yet rolled into a monthly file.
- Spot history begins 2017-08-17, matching the intended span.
- Every zip ships a `.CHECKSUM` (SHA-256) companion. Verify on download; the archive is occasionally re-issued to correct discovered issues, so checksums also guard against a stale local copy.
- From 2025-01 onward spot timestamps are in microseconds rather than milliseconds. Detect and normalise the timestamp unit per file rather than assuming one scale across the whole span.

The file-pulling mechanics are well covered by the official `binance/binance-public-data` repository and by the `binance_historical_data` Python package, which wraps the same archive. Either is acceptable as the download engine. Neither solves the symbol-list problem; that remains the analyst's responsibility.

## A.3 Building a survivorship-complete symbol list

Since the live endpoints will not name the dead coins, assemble the historical universe by other means:

- **Enumerate the archive directly.** The `klines` directory on `data.binance.vision` lists every symbol that ever had data, delisted ones included. Crawl that listing to obtain the true historical symbol set rather than asking a live endpoint what trades today. This is the most reliable route and keeps you inside the free canonical source.
- **Cross-reference a delisting record.** Binance has published delisting and trading-pair-removal announcements over the years; a list of removed pairs confirms the enumerated set actually contains the dead coins and quantifies how many would otherwise have been missed. This doubles as the active-versus-delisted partition the survivorship audit (B.5) needs.
- **Snapshot the live list once, with a date.** Pull `exchangeInfo` a single time to mark which historical symbols are still active as of a recorded date. That date is part of the artefact; the active/delisted split is only valid as of when the snapshot was taken.

## A.4 Commercial and secondary sources

If the archive-crawl route proves incomplete, or an independent cross-check on the dead coins is wanted, paid vendors capture and retain delisted history:

- **Amberdata** holds Binance spot back to 2017-08-17 and states it captures data the exchange itself does not retain; useful as a reconciliation source or where pairs the free archive has dropped are needed. Commercial licensing.
- **CryptoDataDownload** offers free Binance spot OHLCV CSVs including hourly, plus paid tiers; convenient for spot checks, but verify delisted-pair coverage before relying on it, since aggregators vary in what dead history they keep.
- **Kaggle and similar dataset dumps** exist (multi-coin Binance OHLCV collections), but are typically survivor-only, fixed-snapshot, and often limited to majors. Treat them as convenience samples for prototyping, never as the survivorship-complete panel.

Vendor data must be reconciled to the Binance Vision bars where they overlap before being trusted, since aggregation, gap-filling, and timestamp conventions differ between providers and an unreconciled splice introduces artefacts at the seam.

## A.5 Acquisition caution

The data being free and canonical does not make the pipeline safe. The whole bias survives or dies at the symbol-list step. Audit it explicitly: confirm that known-delisted pairs (a `LUNA`-era casualty, a delisted `BKRW` quote pair) are present in the downloaded panel before trusting any downstream diagnostic. If they are absent, the universe was built from a live list and the acquisition must be redone.

---

# Stage B — Profiling the panel to choose parameters from evidence

The splitting design names parameters it cannot responsibly set without first looking at the data. The panel is unbalanced and dynamic: coins enter and exit at different dates, listings cluster, gaps and halts are common, and breadth changes by an order of magnitude across the span. The operations below measure those properties so every downstream choice is justified by a diagnostic rather than assumed. The output is twofold: summary tables and plots that justify each choice, and persisted artefacts that the splitter and the final report consume directly.

## B.1 Per-symbol coverage and lifespan profile

For every symbol, compute the first bar timestamp, the last bar timestamp, the total bar count, and the calendar span between first and last. Derive the expected bar count for that span at hourly frequency and the realised-to-expected ratio as a coverage figure.

Purpose: establishes when each coin enters and exits, how long it lived, and how complete its record is. Raw material for the entry/exit log and the minimum-history rule.

## B.2 Gap and continuity analysis

Within each symbol, detect missing bars against a complete hourly index over its active span. Quantify the number of gaps, the distribution of gap lengths, and the largest gap. Flag symbols whose gaps indicate trading halts, delisting-then-relisting, or data-vendor holes rather than ordinary low-liquidity missingness.

Purpose: distinguishes a coin with a clean continuous record from one that is nominally long-lived but riddled with holes. A coin can clear a raw bar-count threshold and still be unusable. Continuity, not just count, governs eligibility.

## B.3 Listing and delisting timeline

Aggregate first-bar and last-bar dates across all symbols into entry and exit counts per month. Plot cumulative active symbols over time and net additions per period.

Purpose: reveals when the universe was thin versus broad, where listings cluster, and where delisting waves occur. Primary evidence for choosing the usable start date and for deciding how to treat early sparse windows.

## B.4 Breadth-over-time curve

Compute the count of symbols meeting a minimum-activity condition in each calendar period (present and trading with acceptable coverage in that month). Plot the curve.

Purpose: the usable window should start where breadth first becomes adequate for a cross-sectional model. This curve makes that point visible rather than guessed, and informs whether to weight folds by coin count.

## B.5 Survivorship audit

Cross-check the symbol list against the dated active-pairs snapshot from A.3. Partition symbols into still-active and delisted. Report the share of the panel that is delisted and the bar volume the dead coins contribute.

Purpose: quantifies how much of the dataset is survivor versus non-survivor, and confirms the dead coins are actually present. If the delisted share is near zero, the dataset is contaminated by construction and acquisition (Stage A) must be revisited before any modelling.

## B.6 Liquidity and quality screen

Per symbol, summarise volume distribution, count of zero-volume bars, count of zero-range bars (open equals high equals low equals close), and any stale-price runs. Flag symbols dominated by illiquid or degenerate bars.

Purpose: low-quality symbols inflate the count of nominally usable coins while contributing noise or artefacts. The screen separates tradeable history from technically-present-but-useless history.

## B.7 Point-in-time universe construction

For each candidate fold-open date, build the eligible universe using only information available at that date: symbols already listed, meeting the minimum-history and continuity requirements as of that point, and passing the liquidity screen on trailing data only. Recompute forward for each fold.

Purpose: the operational guard against look-ahead in universe membership. It directly produces the per-fold coin lists the splitter uses, and proves membership never depends on future information. If the universe is instead selected by any criterion measured over the full history (top 400 by lifetime volume, coins that reached some market cap), the future has leaked into sample membership. Top-by-volume must mean top-by-volume-as-of-the-window-open, recomputed forward, not once over the whole span.

## B.8 Threshold sensitivity

Sweep the minimum-history threshold and the coverage/continuity cut-offs across a small grid, and report how many symbols survive at each setting and how the per-fold universe size responds.

Purpose: shows whether the eligible sample is robust to the threshold or balanced on a knife-edge. A choice that loses or gains a third of the universe under a small parameter change must be made consciously, not by default.

## B.9 Parameter decisions these diagnostics drive

The profiling exists to set, with a recorded justification, the parameters the splitter consumes:

- **Usable start date** — from the breadth curve (B.4) and listing timeline (B.3), the point where coin count first supports a cross-sectional model. Expect the 2017–2018 region to hold only BTC, ETH, and a few majors; a model trained there learns from almost nothing and is not comparable to later folds. Either start usable history later (around 2019–2020), weight folds by coin count, or report early folds separately and flag them as thin. Do not treat a 10-coin fold and a 300-coin fold as equal evidence.
- **Minimum-history threshold** — set for a reason, not a round number. A coin needs enough bars to compute its longest-lookback feature, form a valid label, and contribute more than noise to any fold it enters. Floor it above (longest feature window + label horizon + buffer), with a further requirement that the coin be present for some minimum fraction of any fold it joins. The principle: it must exceed what the pipeline needs to produce one clean labelled observation, with margin. Record the value and the windows that set it.
- **Point-of-entry rule** — when a coin lists mid-window, choose one honest option and state it. Either the coin enters at its first valid bar (realistic, mirrors when trading would actually begin) or it must span the full fold to be included (cleaner panel, but discards information and biases toward longer-lived coins, reintroducing a flavour of survivorship). Do not let coins drift in and out invisibly.

## B.10 Artefacts to persist

Consumed by the splitting stage and the final write-up, so they must be saved, not just displayed.

- **Symbol metadata table:** one row per symbol — first/last bar, total bars, span, coverage ratio, gap count, largest gap, active/delisted flag, liquidity flags. The master eligibility record.
- **Entry/exit log:** per-symbol listing and delisting dates. The composition audit trail.
- **Breadth curve:** active-and-eligible symbol count per period.
- **Per-fold universe lists:** the point-in-time eligible symbol set for each fold-open date.
- **Decision summary:** the chosen usable start date, minimum-history threshold, continuity and liquidity cut-offs, and point-of-entry rule, each stated alongside the diagnostic that justified it.

---

# Stage C — Time-aware splitting and evaluation

With the panel acquired and the parameters chosen, replace any random or stratified split with a chronological walk-forward design, and document the rationale in the methodology section.

## C.1 Objective and rationale (methodology cell)

Insert a markdown cell at the top of the splitting section stating the objective plainly: estimate out-of-sample performance under regime drift, not interpolation within a known distribution.

The data-generating process drifts across time. The 2017–2018 ICO mania, the 2021 bull run, the 2022 deleveraging, and the current regime are different processes. A split that interleaves test bars among training bars borrows the future to predict the past and yields an error estimate that will not survive live trading.

State explicitly that stratified sampling is rejected. Stratifying on variance forces similar proportions across splits by drawing observations regardless of position in time, which destroys the temporal ordering that is the whole object of interest. It answers "can the model interpolate within a known distribution"; the question that matters is "can it extrapolate forward into an unknown regime." Only a forward-chained split measures that.

## C.2 Walk-forward splitter

Replace any random or stratified split with an expanding-window (or rolling-window) walk-forward scheme.

- Boundaries are calendar dates shared across all coins.
- Train on the earliest block, validate on the next, test on the most recent holdout; slide forward and repeat to produce several out-of-sample folds spanning different regimes.
- Prefer a custom splitter over `TimeSeriesSplit` given the 400-coin panel; the baseline is fine conceptually but will not handle the panel structure or the purge/embargo below.
- Nothing past the training cutoff may leak backward into features, scaling, or normalisation. Fit all transforms on train only and apply forward.

## C.3 Purge and embargo at every boundary

At each fold cut, drop a gap equal to the longest of the feature lookback window and the label horizon, on both sides of the boundary.

Features built on lookback windows and labels built on forward returns (e.g. next-24-hour return) cause bars near the seam to share information across the split. The gap removes that overlap. This is López de Prado's purging-and-embargo; with overlapping label windows in crypto it matters more than is commonly assumed. Record the chosen gap and the windows that determined it.

## C.4 Split on time, not on coins

All coins share the same calendar boundaries. A given coin appears in both train and test, but only its earlier bars train and its later bars test.

Do not hold out whole coins. Whole-coin holdout answers a different question ("generalise to a coin never traded"); add it only as a separate, explicitly labelled experiment if that objective is actually wanted.

## C.5 Per-fold reporting for regime stability

Report the chosen metric per fold, not pooled. This exposes whether performance is stable or regime-dependent, which a single averaged number hides. Weight or annotate folds by coin count (from B.4) so thin early folds are not read as equal evidence to broad later ones.

---

# Cross-cutting: the recurring pitfall

None of these biases announce themselves. The model trains cleanly, the backtest looks good, and the damage stays invisible until capital is live. The defences are unglamorous and all upstream of the model: include the dead coins, build the symbol universe by enumeration not by live endpoint, fix the minimum-history rule to the pipeline's actual needs, define the universe point-in-time, keep a composition log that can be interrogated, and split forward in time with purge and embargo. Every one of these is a step the model itself cannot recover from if skipped.

---

# Python implementation guidance

The work spans acquisition (network and file I/O), profiling (panel-data aggregation), and splitting (custom cross-validation). It leans on the standard scientific-Python stack. Structure suggested, not prescriptive.

## Libraries

- `pandas` for the panel, group-wise aggregation, and resampling against complete time indices.
- `numpy` for count and ratio arithmetic and the run-length gap computation.
- `pyarrow` with Parquet for storage. With 400 coins of hourly data back to 2017 the raw panel is large; Parquet with per-symbol or per-year partitioning keeps memory and I/O manageable. Avoid CSV for the working store.
- `requests` or `httpx` plus `zipfile` and `hashlib` for the Binance Vision downloader and SHA-256 checksum verification.
- `matplotlib` for the timeline, breadth, and gap-distribution plots. Keep them plain and static; these are diagnostics, not presentation graphics.
- Optionally `polars` or `duckdb` if pandas memory pressure bites at full panel size; the per-symbol aggregations in B.1–B.2 express cleanly in SQL over the Parquet store via DuckDB and may be faster than pandas group-by.

## Shape of the code

Organise as a sequence of pure functions, each taking the panel (or a symbol slice) and returning a table, with thin drivers that run them in order and write artefacts. This keeps each step independently testable and re-runnable.

- **Acquisition:** a symbol-universe builder that crawls the archive listing (A.3); a downloader that pulls monthly 1h klines per symbol with daily-file top-up for the trailing edge and verifies each `.CHECKSUM`; a timestamp-unit normaliser for the 2025-01 ms-to-µs change; a one-shot `exchangeInfo` snapshotter that stamps the active-symbol list with its retrieval date.
- **Loader:** reads the Parquet store and returns a tidy long-format frame indexed by symbol and timestamp.
- **Per-symbol profiler:** grouped by symbol, emits the B.1 coverage row. Use `groupby(symbol).agg(...)` for scalar fields; compute coverage by reindexing each symbol onto a complete `pd.date_range` at hourly frequency over its own span and comparing lengths.
- **Gap analyser:** per symbol, reindex onto the complete hourly index, locate nulls, run a run-length computation over the null mask for gap lengths. A `numpy` diff of the missing-timestamp integer positions gives gap sizes without an explicit loop.
- **Timeline aggregator:** takes first/last dates from the metadata table and produces monthly entry, exit, and cumulative-active series via `resample` or `value_counts` over period bins.
- **Point-in-time universe builder:** a function taking a fold-open date and the metadata table, returning the eligible symbol list by filtering on listed-before-date, trailing-coverage, continuity, and trailing-liquidity conditions. Call across the fold-open grid to produce the per-fold lists.
- **Threshold-sweep driver:** loops the B.8 grid and tabulates survivor counts.
- **Walk-forward splitter:** a custom cross-validation generator yielding train/test index pairs on calendar boundaries, applying the purge/embargo gap, drawing each fold's universe from the point-in-time lists, and fitting transforms on train only.

## Practical cautions

- Build the complete hourly index per symbol over its **own** active span, not over the global span, or every coin will appear to have enormous leading and trailing gaps.
- Treat timestamps as timezone-aware UTC throughout; Binance bars are UTC and mixing naive and aware timestamps corrupts the gap arithmetic silently. Combined with the ms-to-µs change at 2025-01, normalise units at load and confirm with a sanity check on bar spacing.
- For the survivorship audit, the active-pairs list must come from the dated `exchangeInfo` snapshot, never a live call at analysis time; the active/delisted split is only valid as of when the snapshot was taken.
- Keep every threshold a named parameter at the top of its driver, not a literal buried in a function. The sensitivity sweep and the decision summary both depend on these being explicit and recorded.
- Persist artefacts with a run timestamp so a later re-run does not silently overwrite the evidence a decision was based on.

---

# Deliverables checklist

**Stage A — acquisition**
- [ ] Symbol universe built by enumerating the historical archive, not a live endpoint (A.1, A.3)
- [ ] Downloader pulling Binance Vision 1h klines with per-file SHA-256 checksum verification (A.2)
- [ ] Timestamp-unit normaliser for the 2025-01 ms-to-µs change (A.2)
- [ ] Dated active-symbol snapshot from `exchangeInfo`, stored as survivorship-partition basis (A.3)
- [ ] Known-delisted pairs confirmed present in the downloaded panel before trusting diagnostics (A.5)
- [ ] Any vendor/secondary data reconciled to Binance Vision bars at overlap (A.4)

**Stage B — profiling**
- [ ] Per-symbol coverage and lifespan profile (B.1)
- [ ] Gap and continuity analysis with halt/hole flags (B.2)
- [ ] Listing/delisting timeline, monthly entry-exit and cumulative-active (B.3)
- [ ] Breadth-over-time curve (B.4)
- [ ] Survivorship audit with delisted share quantified (B.5)
- [ ] Liquidity and quality screen (B.6)
- [ ] Point-in-time per-fold universe builder, no full-history leakage (B.7)
- [ ] Threshold sensitivity sweep (B.8)
- [ ] Usable start date, minimum-history threshold, point-of-entry rule each chosen and justified (B.9)
- [ ] Symbol metadata table, entry/exit log, breadth curve, per-fold universe lists, decision summary all persisted (B.10)

**Stage C — splitting**
- [ ] Methodology markdown cell: objective, regime-drift rationale, explicit rejection of stratification (C.1)
- [ ] Walk-forward splitter, calendar boundaries, transforms fit on train only (C.2)
- [ ] Purge/embargo gap at every boundary, sized to max(feature lookback, label horizon), value recorded (C.3)
- [ ] Time-based split confirmed; no whole-coin holdout unless separately scoped (C.4)
- [ ] Per-fold metric reporting, folds weighted/annotated by coin count (C.5)

**Cross-cutting**
- [ ] Code organised as pure per-step functions with drivers writing run-timestamped artefacts
- [ ] Every threshold a named, recorded parameter
- [ ] UTC timestamps throughout, unit-normalised and sanity-checked
