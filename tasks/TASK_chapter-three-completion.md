# TASK: Complete Chapter Three end-to-end, through model evaluation into hyperparameter tuning

Written 2026-06-21. For the next working agent. Run everything from the project `.venv`
(MacPorts python 3.12); never the system interpreter. MacPorts only, never Homebrew.

## Where things stand

The chapter-three notebook `03-trader-execution/03-trader-execution.ipynb` now runs clean
end-to-end on real data. The current dataset is a top-47 liquid-coin subset of the 1h
all-market frame: `inputs/binance-data/dataset_1h_allmarket.parquet`, 1,640,660 rows,
458,539 in-sample, 61 features, base rate 0.31, zero NaN. The head-to-head training cell
produced NO-GO across LogReg, RandomForest, and LightGBM: AUC ~0.50-0.51, precision lift
under one point over base, net P&L -0.38%/trade after fees. That is the expected "no edge
on the inherited label yet" result, not a bug. The full ~433-coin download is still
resuming in the background; a full-market rebuild can happen once it finishes.

Sections still to complete in the notebook: Model Tuning, Model Assessment, Stability.
These currently only render the scoreboard and point at scripts; they have not been run on
this data.

## Objective

Take chapter three the rest of the way: run the full chain through to a real model
evaluation, then begin hyperparameter tuning. Concretely, produce a demonstrable,
after-fee out-of-sample verdict and a tuned configuration that is at least defensible
against buy-and-hold and a coin flip.

## Tasks, in order

1. Confirm the starting point. Run the notebook top to bottom on the current dataset to
   reproduce the NO-GO baseline (LightGBM AUC ~0.51). Use the LightGBM-only model set for
   any full-market-scale step; the full zoo is fine on the subsampled training set but
   RandomForest does not scale to the full row count.

2. Model Tuning, label geometry (Priority 1b). Run `inputs/sweep_label_1h.py`: sweep the
   ATR-scaled triple barrier (target ATR, stop ATR, horizon-in-bars) around the current
   default (+2 / -1 / 48 bars). Features are computed once per coin and only the label is
   recomputed per cell. Read off the after-fee Metric 2 and breakeven-win line. Keep the
   cells that beat both buy-and-hold and a coin flip out of sample.

3. Model Tuning, exit geometry. Run `inputs/walkforward.py`: per-coin/per-split trailing
   stop and time-decaying take-profit, scored on the same after-fee scoreboard. Reconcile
   the three forked exit configs and the provisional -7% hard stop / 10% trail.

4. Model Assessment. Run `inputs/model_assessment_1h.py`: the caret-style Full/CV Brier
   table with the RMSEratio overfit flag. Flag any model whose CV error diverges from its
   full-fit error.

5. Hyperparameter tuning. With the best label and exit geometry fixed, tune the LightGBM
   hyperparameters (num_leaves, learning_rate, max_depth, min_child_samples, subsample,
   colsample_bytree, n_estimators) against the final-year out-of-sample split with the
   label-horizon embargo. Score once on the held-out year; do not peek. Record the search.

6. Stability. Complete the Stability section: confirm the chosen configuration holds across
   regimes (the regime-stratified AUC already in eval_report) and across coins, not just in
   aggregate.

Every run appends a row to `outputs/AA-evals/evaluation-scores.md`. The PDF and DOCX
exports now generate too (reportlab and python-docx are installed in the .venv).

## Done when

A single configuration (label geometry, exit geometry, tuned LightGBM) is scored once on
the final-year out-of-sample, after fees, and either clears the honesty gate (precision
beats base by more than 0.05 and AUC clears 0.55, P&L positive after costs) with a GO, or
is documented as a reasoned NO-GO with the specific next lever to pull. Write a short
session handover in `tasks/` summarising what was swept, what won, and the final verdict.

## Guardrails

Run from `.venv`. Score out of sample once, with the embargo; keep only changes that beat
buy-and-hold and a coin flip after fees. Read-only on the scripts where possible: knobs
live in the scripts so the notebook cannot drift. If matplotlib throws a `0xb0`
UnicodeDecodeError or `._` files clutter the tree, clear them:
`find /Volumes/PortableSSD/Github/day-trader/.venv -name '._*' -delete`. Optionally rebuild
on the full ~433-coin market once the background download finishes, then re-run the chain.
