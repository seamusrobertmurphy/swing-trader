# Integration log — ClaudeTrader, Supertrend, survivorship, notebook wiring (2026-06-23)

What changed this session, where it lives, and how it plugs into the Chapter 3 workflow.
Companion to `CLAUDE.md` (Build log) and `tasks/data-pipeline-methodology.md`.

## 1. ClaudeTrader installed into the project .venv

`pip install -e` of `/Volumes/PortableSSD/Github/SuperTrendTradingBot/ClaudeTrader` into
`day-trader/.venv` (Python 3.12). Core deps only; the `[llm]`/`[rag]`/`[nlp]` extras
(anthropic, chromadb, torch) were deliberately NOT installed.

- **Namespace caveat.** The package exposes GENERIC top-level names — `utils`, `core`,
  `models`, `strategies`, `tests` — via an editable finder. `import claudetrader` does NOT
  work (no such namespace); use `from utils import performance, risk`. day-trader has no
  top-level modules by those names today, so there is no collision, but treat the names as
  reserved and import behind an alias (`from utils import performance as ct_perf`).
- **README overstates the package.** `agents/`, `rag/`, `nlp/`, `api/` do NOT exist; the
  `claudetrader=core.engine:main` console script and the REST/WebSocket sections do not run.
  The real, tested surface is `utils/` (backtest, risk, performance, indicators, data_fetcher),
  `strategies/` (BaseStrategy + SuperTrend/RL/MultiFactor/Hybrid), and `tests/` (34 tests).
- **What we actually use.** `utils.performance.compute_metrics` (Sharpe/Sortino/Calmar/maxDD/
  profit factor) and `utils.risk` (ATR exits, trailing stop) — the after-fee metric layer the
  exit-geometry sweep needs. The LLM layer is ignored.

## 2. Supertrend indicator -> `f_st_` feature block

Ported the triple-Supertrend math from `inputs/supertrend.py` (the live bot) into
`inputs/build_dataset_1h.py` as `supertrend_block()` (called inside `build_coin`, between the
in-house TA and pandas-ta blocks). Seven causal, scale-invariant features, prefix `f_st_`:

- `f_st_dist_1/2/3` — signed distance from close to each band's active Supertrend line / close.
- `f_st_agree` — signed band-agreement score in {-1, -1/3, +1/3, +1}.
- `f_st_uptrend` — 1.0 when all three bands agree on an uptrend.
- `f_st_flip` — +1 the bar agreement turns up, -1 when it turns down.
- `f_st_ema200_dist` — distance to the EMA-200 trend gate / close.

Bands `(12,3),(10,1),(11,2)` and EMA-200, identical to the bot. Smoke-tested on BTCUSDT
(77,389 bars): zero NaN, ranges sane, `f_st_agree` takes exactly its four values. Adds no
dataset shrinkage. It is a candidate only; the after-fee OOS scoreboard prunes it. Distinct
from `f_ta_` (ADX/DMI/Aroon) and `f_tl_` (SAR) — the ATR-channel flip the model otherwise lacks.

**To activate:** rebuild the dataset (`.venv/bin/python inputs/build_dataset_1h.py`); the
block joins automatically. Feature count goes 61 -> 68.

## 3. Triple-Supertrend rules baseline -> `inputs/baseline_supertrend_1h.py`

The benchmark the model must beat. Trades the SAME signal as the live bot (long-only spot,
enter when all three bands agree AND close > EMA-200, exit when agreement breaks), on each
coin's final-year OOS slice, after 10 bps/side fees. Reuses `build_dataset_1h._supertrend_band`
(single source of truth with the `f_st_` features) and scores through ClaudeTrader's
`utils.performance.compute_metrics` + optional `utils.risk` ATR trailing stop.

Run: `.venv/bin/python inputs/baseline_supertrend_1h.py [-s BTCUSDT ...] [--trail]`.
Writes `inputs/binance-data/baseline_supertrend_oos.csv`. First read on BTC/ETH/BNB: beats
buy-and-hold 2/3 by dodging drawdown, but negative Sharpe and the ATR trail makes it worse —
NO-GO, the honest benchmark result. Not an executor: no keys, no orders, unaffected by
`LIVE_TRADING`.

## 4. Why the dataset is 47 coins, not 433

`dataset_1h_allmarket.parquet` covers **47 coins**, not the ~433 the chapter prose claims.
Diagnosis (replicated the build gates over the flow table):

- The quality gates are NOT the cull — they would pass ~323 coins (10 fail min-bars, 2 fail
  gap-ratio, 4 fail max-gap).
- The 47 are a clean SUBSET of the ~323 that should pass, all long-history coins.
- The parquet is dated **June 21**; today's Run All produced the June-23 panel profile but did
  NOT rebuild the dataset.
- The raw download is itself incomplete: 337 coins in the flow table, 384 kline folders, vs the
  ~433 active / 612 historical target.

So the 47-coin file is a stale partial build over a hand-picked long-history subset. Every model
number off it is an upper bound twice over (subset + survivorship). **Gating next step: re-run
`build_dataset_1h.py` over the full `klines_1h/` once the survivorship pull lands (expect 300+
coins).**

## 5. Survivorship-bias fix (in progress)

Root cause: the dataset is built from `klines_1h/`, which holds only currently-active coins
(`decision_summary.json` reports `n_delisted: 0`). The fix is Stage A `acquire_vision.py`:
enumerate the historical universe from the `data.binance.vision` archive (612 USDT pairs vs 424
active = **30.7% delisted**) and download the dead coins alongside the survivors.

Launched 2026-06-23: `acquire_vision.py download --interval 1h` (resumable, checksum-verified),
writing dead-coin folders into `klines_1h/`. Log: `inputs/binance-data/_acquire_vision_download.log`.
**When it finishes, rebuild the dataset and re-profile** (Stage B will then report a non-zero
delisted share), and only then are the after-fee numbers free of survivorship bias.

## 6. Chapter 3 notebook wiring (`03-trader-execution.ipynb`)

- **New EDA cell** (after the Feature Variables summary): label balance by year, per-coin base
  rate + history + panel share, most-correlated feature pairs (redundancy), most label-separating
  features, and a correlation heatmap. Read-only on the in-sample rows.
- **Variable Selection rewired** to the glmnet tools in `inputs/variable_selection.py`
  (`enet_cv` -> `plot_cv_curve` + `plot_coefpath` + `plot_coefpath_interactive` + `screen` at
  lambda.1se + `plot_coef_ci`). The old cell ran a plain sklearn elastic-net that kept 61/61
  (no actual selection) and drew nothing; now it produces the CV deviance curve, coefficient
  paths (static + interactive HTML), and a refit 95%-CI dot-whisker, into
  `outputs/AA-evals/varselect/`.
- **Model Assessment cell fixed.** It globbed `AA-evals/*/model-assessment-*.md`, which never
  existed, so it always printed "no record yet". Hardened: render the persisted record if present,
  ELSE run an inline `ma.assess(only=["logreg","lightgbm"])` and render the table directly, so the
  cell always shows a result. The persisted record comes from
  `.venv/bin/python inputs/model_assessment_1h.py`.

## 7. CLAUDE.md directive recorded

Added "Notebook integration (authoring convention)": helper scripts in `inputs/` are to be
trimmed so their essential logic reads inline in the notebooks; notebooks must stand on their own
as a legible demonstration of every key operation, relaxing the earlier "knobs live in the
scripts" stance while keeping one source of truth for heavy/duplicated logic.
