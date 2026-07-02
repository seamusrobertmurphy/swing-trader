# INDEX.md

File index and build log for the trading-routine repo. Updated at the start and end of every working session.

## Files

| Path                              | Purpose                                                          |
|-----------------------------------|------------------------------------------------------------------|
| `CLAUDE.md`                       | Agent identity, hard rules, boot order, env var contract         |
| `INDEX.md`                        | This file                                                        |
| `README.md`                       | Human-facing project overview, layout, deployment steps          |
| `tasks/TASK_trading-routine-setup-task.md` | Original task brief; do not edit                        |
| `tasks/TASK_quant-principles-addendum.md`  | Extends the original brief with the twelve quant principles |
| `research/synthesis-quant-methods.md` | Distilled quant operating principles, with citations          |
| `research/authoritative-references.md` | Curated reading list for the synthesis                       |
| `research/AQR Words from the Wise Ed Thorp.pdf` | Source: AQR interview with Ed Thorp, January 2018 |
| `research/Ed Thorp's Trading Strategy Explained - Macro Ops.pdf` | Source: Macro Ops profile of Thorp's strategy |
| `research/DynamicRepDerman.pdf`       | Source: Derman and Taleb, Illusions of Dynamic Replication (2005) |
| `research/Black–Scholes model - Wikipedia.pdf` | Source: Wikipedia reference on Black-Scholes              |
| `research/How the Black Scholes Formula uses probability theory ... LinkedIn.pdf` | Source: LinkedIn post on BS probability theory |
| `research/black-scholes-formula-tutorial-01.txt` | Source: BS tutorial video transcript                  |
| `research/black-scholes-formula-tutorial-02.txt` | Source: BS / Thorp documentary transcript             |
| `research/rl-applicability-assessment.md` | Memo: which parts of the imported RL repo map to the brief and which do not |
| `research/equity-feature-adaptation.md`   | Translation of the source indicator design to a US-equity swing feature set |
| `research/rl_reference/README.md`         | Provenance and boundary note for the imported RL source            |
| `research/rl_reference/indicators.py`     | Imported: pandas-ta feature pipeline (RSI, ATR, MA slopes, distances, spread) |
| `research/rl_reference/trading_env.py`    | Imported: Gymnasium env, position-persistent, discrete OPEN/CLOSE/HOLD with SL/TP grid |
| `research/rl_reference/train_agent.py`    | Imported: PPO training, checkpointing, OOS-equity-based selection  |
| `research/rl_reference/test_agent.py`     | Imported: deterministic OOS evaluation harness                     |
| `research/rl_reference/requirements.txt`  | Imported: pinned upstream dependencies, re-encoded UTF-8           |
| `research/rl_reference/transcript-notes.md` | Author's video walkthrough distilled into study notes            |
| `.gitignore`                      | Block secrets, OS cruft, editor files                            |
| `memory/strategy.md`              | Rule set: signals, sizing, exits. Rewritten only on Fridays.     |
| `memory/portfolio.md`             | Current holdings, cash, last-known equity                        |
| `memory/trade-log.md`             | Append-only ledger of every trade with rationale and outcome     |
| `memory/research-log.md`          | Dated research notes from pre-market and ad hoc                  |
| `memory/learnings.md`             | Carry-forward insights and mistakes to avoid                     |
| `memory/weekly-review.md`         | Latest Friday review                                             |
| `routines/pre-market.md`          | 6:00 AM CT — research and draft trade ideas                      |
| `routines/market-open.md`         | 8:30 AM CT — execute drafted trades, set stops                   |
| `routines/midday.md`              | 12:00 PM CT — cut losers, tighten winners                        |
| `routines/market-close.md`        | 3:00 PM CT — mark-to-market, EOD summary to ClickUp              |
| `routines/weekly-review.md`       | 4:00 PM Fri — week review, self-grade, strategy edits            |
| `skills/research.md`              | How to use Perplexity, what to look for                          |
| `skills/trade-decision.md`        | Buy/sell/hold criteria, position-sizing math                     |
| `skills/trade-execute.md`         | Alpaca order placement contract                                  |
| `skills/journal.md`               | How to write back to memory files                                |
| `skills/notify.md`                | ClickUp post format                                              |
| `scripts/alpaca.sh`               | curl wrappers for the Alpaca REST API                            |
| `scripts/perplexity.sh`           | curl wrapper for Perplexity                                      |
| `scripts/clickup.sh`              | curl wrapper for ClickUp                                         |
| `scripts/bootstrap.sh`            | One-shot host-shell setup: git init + first commit               |
| `01-trader-metrics/01-trader-metrics.ipynb`   | Chapter 1 notebook — trader metrics                  |
| `02-trader-controls/02-trader-controls.ipynb` | Chapter 2 notebook — risk controls and position sizing |
| `03-trader-execution/03-trader-execution.ipynb` | Chapter 3 notebook — 1h model build/train/assess, fully documented (Import, Data Processing, Model Features, Variable Selection, Training, Tuning, Assessment, Stability) |
| `inputs/acquire_vision.py`        | Stage A: survivorship-complete acquisition — crawls the `data.binance.vision` archive listing for the full historical USDT universe (dead coins included), checksum-verified resumable downloader, dated `exchangeInfo` snapshot, dead-coin presence guard |
| `inputs/profile_panel.py`         | Stage B: panel profiling — coverage/gaps/timeline/breadth/survivorship/liquidity diagnostics; derives usable start, min history, purge/embargo; persists run-stamped artefacts + point-in-time per-fold universes |
| `inputs/wf_splitter.py`           | Stage C: forward-chained walk-forward splitter — calendar boundaries, purge/embargo = max(feature lookback, label horizon), point-in-time per-fold universes, train-only transforms, coin-weighted per-fold reporting |
| `inputs/build_dataset_1h.py`      | 1h all-market build: in-house/breadth/flow blocks + `f_st_` Supertrend + `f_btc_` BTC lead-lag + `f_4h_`/`f_d1_` multi-timeframe (causal) + `f_mst_` Modern Adaptive Supertrend (KER); ATR triple-barrier label, PIT screen, gap gate, Parquet |
| `inputs/train_model_1h.py`        | 1h train + after-fee scoring; final-year OOS split, embargo = label horizon, scores once |
| `inputs/sweep_label_1h.py`        | Priority 1b label-geometry sweep (ATR target/stop/horizon grid), features fixed per coin |
| `inputs/model_assessment_1h.py`   | caret-style Full/CV RMSE (Brier) + RMSEratio table; zoo of 3 GBMs (LightGBM/HistGBM/classic) + LogReg/RF/stacking; `tune()` hyperparameter grid (`--tune`) |
| `inputs/baseline_supertrend_1h.py`| Triple-Supertrend rules baseline — after-fee OOS benchmark via ClaudeTrader metrics |
| `inputs/exit_geometry_1h.py`      | 1h exit-geometry sweep: per-coin trailing stops + time-decay take-profit + lo/mid/hi regime breakdown |
| `inputs/monte_carlo_1h.py`        | Monte Carlo robustness on after-fee per-trade returns (bootstrap + reorder + sign-flip null → verdict) |
| `inputs/eval_report.py`           | AA-evals record writer; head-to-head and label-sweep rows, `eval_type`/`dataset_label` |
| `inputs/build_dataset.py`         | Daily fixed-universe build (kept, superseded by the 1h frame)    |
| `inputs/train_model.py`           | Shared estimator list, `evaluate`, confidence filter, cost constants (daily path) |
| `inputs/backtest.py`, `inputs/walkforward.py` | Backtest and walk-forward harnesses                  |
| `inputs/trade_binance.py`         | Binance spot order layer; refuses orders unless `LIVE_TRADING=true` |
| `inputs/config.py`                | Secrets/config from macOS Keychain (do not edit)                 |
| `inputs/binance-data/flow_data.py`| Downloader/aggregator: `--interval`/`--all-market`, taker-buy flow |
| `inputs/binance-data/dataset_1h_allmarket.parquet` | Built dataset (stale 47-coin June-21 build; full survivorship-complete rebuild pending — do not report numbers off it) |
| `inputs/binance-data/flow_1h.parquet` | 1h taker-buy flow table (Parquet; CSV deprecated)            |
| `outputs/AA-evals/evaluation-scores.md` | After-fee GO/NO-GO scoreboard (also .docx/.pdf)            |
| `tasks/data-standards.md`         | 1h crypto data standards (gap gate, PIT screen, OOS split)       |
| `tasks/build-decisions-2026-06-21.md` | Design-decision record for the 1h all-market pivot           |
| `tasks/run_auto_eval.sh`          | One-shot wrapper: download → aggregate → build → train           |
| `tasks/session-handover-2026-06-21-pm.md` | June-21 handover: remaining tasks                         |
| `tasks/autonomous-overnight-progress.md` | **Latest handover (2026-06-23):** overnight-run state, NO-GO diagnosis, reprioritized pipeline — next model starts here |
| `tasks/integration-2026-06-23-claudetrader-supertrend.md` | ClaudeTrader install + Supertrend/feature integration log |
| `tasks/multi-resolution-build-plan.md` | Next steps: build daily/4h/1h decision frames + multi-timeframe context |
| `research/GBBC 2026 SuperTrend Indicator Strategy Net Profit 323k.md` | Source: Modern Adaptive Supertrend [GBB] Pine indicator + video transcript |

## Build log

A running record of work done on this repo. Newest at the top.

### 2026-06-23 — Feature & model upgrades; honest NO-GO diagnosis; multi-resolution plan (handoff)

- **ClaudeTrader** installed editable into `.venv` — its `utils/` (Sharpe/Sortino/Calmar/maxDD; ATR exits/sizing/trailing; no-lookahead event backtester) is reused (`from utils import performance, risk, backtest`); the engine/RAG/LLM/strategy layers are mock (`data_fetcher` returns a random walk) and NOT integrated. Detail in `tasks/integration-2026-06-23-claudetrader-supertrend.md`.
- **Four new causal feature families** in `build_dataset_1h.py`, validated + documented in ch3 "Feature Integration": `f_st_` (triple-Supertrend), `f_btc_` (BTC lead-lag / relative strength — first non-price family), `f_4h_`/`f_d1_` (multi-timeframe context, `merge_asof` causal, no-lookahead verified), `f_mst_` (Modern Adaptive Supertrend [GBB] with the KER regime gate; commit filter cuts false flips ~80%). Dropped the duplicate `f_wc_rv_short`. 61 → ~84 features on rebuild.
- **Model zoo beyond LightGBM**: three gradient boosters (LightGBM, HistGBM, classic GBM) + LogReg.glm/enet + RF + stacking; caret-style `tune()` (TimeSeriesSplit grid → `model-tuning-*.md`). Fixed a stacking crash (`cv=TimeSeriesSplit`→`cv=3`) that had blocked every assessment record, and a `sweep_label_1h` KeyError on flow-less coins.
- **New eval tools** (all → `outputs/AA-evals/`): `baseline_supertrend_1h.py`, `exit_geometry_1h.py` (per-coin trailing + time-decay TP + regime breakdown), `monte_carlo_1h.py` (bootstrap + reorder + sign-flip null robustness gate, in ch3 Stability).
- **Diagnosis:** 1h direction is at the efficient-market floor. Label-geometry + longer-horizon sweeps all NO-GO, win rate ~2-3pp below breakeven; the +2/-1 ATR label has negative unconditional expectancy (base 0.313 < breakeven 0.333). Zoo AUC ~0.50; Monte Carlo on the Supertrend baseline = 99.7% prob of loss across 10k sims. Confirmed by the GBBC SuperTrend author (coin-flip 48%, bleeds out at 1h, holds at 4h+). Edge needs a different PROBLEM, not more tuning.
- **Notebook tidy-up:** ch3 section titles `###` and ≤2 words; new EDA cell; Variable Selection rewired to glmnet visuals; Model Assessment inlined + fixed to always render; Feature Integration + Monte Carlo cells. ch1/ch2 got Supertrend Integration cells; headings shortened to ≤3 words.
- **Survivorship pull** running (539/612, dead coins landing); auto-rebuild monitor armed. On-disk dataset is still the stale 47-coin June-21 build — do NOT report numbers off it.
- **Next model:** pick up from `tasks/autonomous-overnight-progress.md` (reprioritized: label sweep first, then 4h+ frame + KER regime gate + cross-sectional framing) and `tasks/multi-resolution-build-plan.md`.

### 2026-06-21 — 1h all-market pipeline built; Parquet storage; notebook documented

- Pivoted the model track to the 1-hour, full active USDT spot market (~433 pairs) frame per the June-21 handover (supersedes June-20). Hard rules recorded in `CLAUDE.md` "Data and model design" and in `tasks/data-standards.md` / `tasks/build-decisions-2026-06-21.md`.
- `inputs/build_dataset_1h.py`: offline kline reader, five feature blocks (in-house wall-clock `f_wc_` and intraday `f_hr_`, in-house extra TA `f_ta_`, optional pandas-ta `f_ta_pta_`, optional TA-Lib `f_tl_`, flow `f_flow_`), a configurable ATR-scaled triple-barrier label, a point-in-time screen with a Corwin-Schultz spread proxy, and a data-quality gap gate. In-house baseline always computes, so the build never hard-depends on pandas-ta or TA-Lib.
- Reversed the earlier pandas-ta drop: pandas-ta and TA-Lib (prebuilt wheel) are installed into the project `.venv` as optional candidate-only layers; the after-fee OOS scoreboard prunes them.
- Added `inputs/train_model_1h.py` (final-year OOS split, embargo = label horizon, reuses `train_model.evaluate`), `inputs/sweep_label_1h.py` (Priority 1b label-geometry grid), and `inputs/model_assessment_1h.py` (caret-style Full/CV RMSE/Brier table with RMSEratio overfit flag). Extended `inputs/eval_report.py` to tag each run with `eval_type`/`dataset_label`.
- Converted dataset/flow storage to Parquet via `read_frame`/`write_frame` (Parquet-preferred, CSV fallback, `--csv` opt-in). Killed a recurring CSV→str timestamp bug that broke the split; also fixed a flow-merge dtype mismatch and mixed-precision timestamp parsing in `flow_data.py`. Measured: dataset 645MB→250MB, `flow_1h` 1148MB→437MB (10,285,772 rows, 53s convert).
- Documented the whole pipeline in `03-trader-execution/03-trader-execution.ipynb` (plain-language Import / Data Processing / Model Features sections, per-cell variable-dictionary tables, a script-provenance cell, and a "Why Parquet" explainer). Updated `01`/`02` notebooks and `README.md` for the new design.
- Validated end-to-end on a 9-coin dev subset (584,957 rows, 61 features, base rate ~0.318); first after-fee number was NO-GO (breakeven-geometry leak) — expected, hence the 1b label sweep.
- Environment fixes: cleared ~29k exFAT `._` AppleDouble files from `.venv` (matplotlib `0xb0` crash); registered a `.venv` Jupyter kernel so notebooks import from the venv, not system python.
- **Open:** the full ~433-coin download is incomplete (337/433 coin folders on disk, process stopped) so the full-market dataset is not yet built. Remaining work captured in `tasks/session-handover-2026-06-21-pm.md`.

### 2026-05-11 — RL repo scanned, imported as reference, integrated by memo

- Scanned `~/repos/ReinforcementTrading_Part_1`: four-file PPO-on-Gymnasium project trained on EURUSD hourly bars with discrete OPEN/CLOSE/HOLD actions across an SL/TP grid.
- Imported the four source files plus a re-encoded `requirements.txt` to `research/rl_reference/`. Wrote a `README.md` documenting provenance and boundary — the runtime does not read this code.
- Wrote `research/rl-applicability-assessment.md`: a memo mapping the source against the twelve principles and the hard rules. The trained agent itself does not belong in the runtime (it shorts, leverages, day-trades, and reward-shapes against the entry price). Three method patterns survive translation: the relative-feature design in `indicators.py`, the OOS-equity-based model selection in `train_agent.py`, and the friction model in `trading_env.py`. Two Friday-review candidates surfaced for the user to pursue or refuse: a backtest harness modelled on the train/test split pattern, and a relative-feature library for the research skill.
- Wrote `research/equity-feature-adaptation.md`: the relative-feature design translated to US equities. Eight technical features expressed as percent or unitless quantities, five fundamental features expressed as within-sub-industry z-scores or differentials against the 10-year Treasury, four market-context features tying to the existing VIX noise filter and the 60-day correlation budget. The note is research-grade, not yet runtime.
- Wrote `research/rl_reference/transcript-notes.md`: distillation of the author's video walkthrough at https://www.youtube.com/watch?v=oW4hgB1vIoY. Connects the spoken explanation to the actual imported files, flags where the spoken parameters (50k timesteps, 60/90/120 SL grid) differ from the current code (600k timesteps, 5–120 SL grid), and preserves the author's own list of limitations.
- No changes to `routines/`, `skills/`, `scripts/`, `memory/`, or the boot order. The integration is research-grade only.

### 2026-05-11 — Quant principles layered onto the brief

- Read the four primary sources in `research/`: the AQR interview with Ed Thorp, the Macro Ops profile, Derman and Taleb's 2005 paper on the illusions of dynamic replication, and the two Black-Scholes tutorial transcripts.
- Wrote `research/synthesis-quant-methods.md`: twelve operating principles distilled from the sources and the canonical literature they rest on (Kelly, Markowitz, Fama-French, Jegadeesh-Titman, Carhart, Asness-Moskowitz-Pedersen, Ilmanen, Taleb, Mandelbrot, Tversky-Kahneman, Damodaran, Pedersen). Each principle states the source, the mechanism, and the application to this long-only swing book.
- Wrote `research/authoritative-references.md`: curated reading list, full citations, organised by sub-area (sizing, portfolio theory, market efficiency, derivatives, risk, practitioner accounts, data sources).
- Wrote `tasks/TASK_quant-principles-addendum.md`: extension of the original task brief recording what changes in CLAUDE.md, what changes (proposed) in strategy.md via the next Friday weekly review, and what does not change.
- Edited `CLAUDE.md`: added a Principles section between the identity preamble and the hard rules, and refined the hard rules to encode half-Kelly default sizing inside the 5% cap, the rolling-week drawdown ramp, the 15% gap-risk sizing margin, the anchoring prohibition, the 20% correlation-cluster cap, the VIX noise filter, and the 10% fat-pitch exception with its three required conditions. The original ceilings (5%, 3%, 7%, 10%, 10%) are preserved.
- `memory/strategy.md` deliberately left untouched. The convention reserves it for the Friday weekly-review routine; the addendum sketches the expected translation for that routine to adopt, refine, or reject.

### 2026-05-11 — Strategy seeded

- Filled `memory/strategy.md` with brief-default rules: universe, entry signals (with negative overrides), exit signals, sizing, risk, disallowed list, benchmarks. Change log opened inside the file.

### 2026-05-11 — Repo reorganisation

- User moved `TASK_trading-routine-setup-task.md` from the repo root into a new `tasks/` subfolder. File table above updated.
- No other structural changes. Memory, routine, skill, and script files all in place at original paths.

### 2026-05-11 — Initial scaffold

- Created `CLAUDE.md` with agent identity, hard rules, boot order, env-var contract, commit and notification discipline.
- Created `INDEX.md` (this file).
- Created `README.md` covering layout, env vars by name, routine schedule, deployment steps for Claude Desktop.
- Created `memory/` with starter templates for `strategy.md`, `portfolio.md`, `trade-log.md`, `research-log.md`, `learnings.md`, `weekly-review.md`. Strategy is a skeleton with placeholders, awaiting user fill-in.
- Created `routines/` with five prompt files matching the cron table in the brief.
- Created `skills/` with `research.md`, `trade-decision.md`, `trade-execute.md`, `journal.md`, `notify.md`.
- Created `scripts/` with `alpaca.sh`, `perplexity.sh`, `clickup.sh` as thin curl wrappers reading env vars.
- Added `.gitignore`.
- Attempted local `git init`. The Cowork bash sandbox cannot write to `.git/` on this mount (host enforces immutability). Wrote `scripts/bootstrap.sh` as a one-shot for the user to run from the host shell.

What remains, owned by the user:
- Run `bash scripts/bootstrap.sh` from the host shell to finalise the local git repo.
- Provide Alpaca paper key + secret, Perplexity key, ClickUp token + list ID.
- Fill in `memory/strategy.md` or approve a starter strategy in a future session.
- Create a private GitHub repo, push `main`, wire up Claude Code Routines per the README.
- Smoke-test each of the five routines with **Run Now** before letting cron drive.

## Working agreement

At the start of every session in this repo, the working agent:
1. Reads `CLAUDE.md` and this file end-to-end.
2. Skims the latest entries in `memory/trade-log.md` and `memory/learnings.md` if the user's request touches strategy or trade behaviour.
3. Updates the relevant task list if work is non-trivial.

At the end of every session, the working agent:
1. Updates this file's build log with what was done.
2. Updates `CLAUDE.md`'s build-log section with the same date entry.
3. Commits.
