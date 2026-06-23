# Session handover — 2026-06-21 (PM)

Continues `session-handover-2026-06-21.md`. The 1h all-market pipeline is built, documented, and validated on a dev subset. What remains is to run it on the full market and settle the label, the variables, and the exit geometry. State at handover, then the remaining tasks in order.

## State at handover

- **Pipeline complete and documented.** `build_dataset_1h.py`, `train_model_1h.py`, `sweep_label_1h.py`, `model_assessment_1h.py`, and `eval_report.py` are in place. The five feature blocks (in-house wall-clock, in-house intraday, in-house extra TA, optional pandas-ta, optional TA-Lib, plus flow) all compute; pandas-ta and TA-Lib live in the `.venv` as candidate-only layers. Chapter 3 (`03-trader-execution.ipynb`) documents the whole chain in plain language with per-cell variable dictionaries.
- **Storage is Parquet.** `read_frame`/`write_frame` prefer `.parquet`, fall back to `.csv`, `--csv` writes a companion. `flow_1h.csv` (1148MB) was converted to `flow_1h.parquet` (437MB, 10,285,772 rows) this session. Note this conversion is a stopgap against the *incomplete* flow file; the aggregate step in `run_auto_eval.sh` regenerates `flow_1h.parquet` from the complete archives once the download finishes, so it will be overwritten — that is fine.
- **Validated on a 9-coin dev subset:** 584,957 rows, 61 features, base rate ~0.318. First after-fee number was NO-GO (breakeven-geometry leak). Expected — that is exactly what the 1b label sweep exists to fix.
- **Download is INCOMPLETE.** 337 of 433 coin folders are on disk (96 left). The pull stopped on a `TimeoutError: read operation timed out` — a transient network read timeout from `data.binance.vision`, not a logic error. The downloader is resumable and skips what is already on disk. **The full-market dataset has therefore not been built; the only dataset on disk is the dev subset.**

## Remaining tasks, in order

1. **Finish the full-market 1h download.** Resume with `.venv/bin/python inputs/binance-data/flow_data.py --interval 1h --all-market` (skips coins already pulled; ~96 remain). It died on a network read timeout, so wrap it in a retry loop or bump the socket timeout if it stalls again. Confirm 433/433 coin folders before proceeding.

2. **Aggregate, build, train the full market.** This is already wired: `zsh tasks/run_auto_eval.sh` waits for the download to finish, then re-aggregates flow to `flow_1h.parquet`, builds `dataset_1h_allmarket.parquet` (full market, not the subset), and trains LightGBM (RandomForest does not scale to millions of rows on the first pass). Logs to `tasks/auto_eval.log`; result lands in `outputs/AA-evals/evaluation-scores.md`. Each step is idempotent.

3. **Priority 1b: settle the label geometry.** `.venv/bin/python inputs/sweep_label_1h.py` runs the ATR target/stop/horizon grid with features held fixed per coin and scores each cell on after-fee Metric 2 plus the breakeven-win readout. Pick the geometry that clears the after-fee, OOS GO gate and reconcile it into `build_dataset_1h.LABEL`. The default +2/-1 ATR over 48 bars is provisional until this settles.

4. **Variable selection workflow.** The planned next-day pass: elastic-net (glmnet-analogue) lambda/gamma path filters, likelihood-ratio tests for the logistic models, and permutation importance for the trees. Integrate into the Chapter 3 Variable Selection section. The brief was explicit not to fear too many candidate variables — the after-fee OOS scoreboard is the pruner.

5. **Exit-geometry sweep.** Add per-coin/per-split trailing stops and a time-decaying take-profit, scored on the same after-fee scoreboard, and reconcile the three forked exit configs. This is what finally settles the provisional −7% hard stop and 10% trailing stop in `CLAUDE.md` (and the 5%/ATR-8.5% mismatch noted there).

6. **Model assessment on the full data.** Run `inputs/model_assessment_1h.py` for the caret-style Full/CV RMSE (Brier) table with the RMSEratio overfit flag, and file it alongside the AA-evals record.

7. **Honest GO/NO-GO on full-market OOS.** Only adopt a change if it beats both buy-and-hold and a coin-flip on the final-year, after-fee, out-of-sample scoreboard. Record the verdict; do not trade on a NO-GO.

## Optional / housekeeping

- Seamus floated building the dataset on a nightly cron or routine. Once steps 1–3 settle, this is a clean candidate to schedule.
- After the full download completes and flow re-aggregates, the stopgap `flow_1h.csv` can be deleted (it is git-ignored and deprecated by the Parquet).
- Clear exFAT `._` files from `.venv` if matplotlib throws the `0xb0` error again: `find /Volumes/PortableSSD/Github/day-trader/.venv -name '._*' -delete`.
- Notebooks must run from the **Python (day-trader .venv)** Jupyter kernel, not system python, or imports (joblib, lightgbm) fail.

## Guardrails unchanged

No live trading; `LIVE_TRADING` stays off. Spot only — never short, options, margin, futures, or leveraged tokens. Never average down. Do not edit `inputs/config.py` (Keychain), `inputs/requirements.txt`, or `01-trader-metrics`/`02-trader-controls` unless asked. MacPorts, never Homebrew. Seamus owns `CLAUDE.md`/`INDEX.md` — append, don't rewrite.
