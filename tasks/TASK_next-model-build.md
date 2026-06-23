# TASK request — next model build (data checks + variable selection) — CONTINUATION HANDOVER

Compiled 2026-06-21; updated 2026-06-21 (PM) after the first implementation pass. Two bodies of
work fold into the next full-market model build, on top of the remaining tasks in
`session-handover-2026-06-21-pm.md`:

A. Post-split train/test representativeness and imbalance audit.
B. The glmnet / variable-selection visualizations in `inputs/variable_selection.py`, wired into the
   `03-trader-execution.ipynb` Variable Selection section.

The spec for A and B is unchanged and kept below for reference. What changed is that the modules now
exist and were validated; read the two status blocks first, then the reconciliation items, then pick
up from "Next model: start here."

---

## STATUS — done this implementation pass (2026-06-21 PM)

- **`inputs/split_checks.py` built and validated.** Exposes `audit_split(train, test, feat_cols,
  label_col="label", by="symbol", embargo_days=...)` returning `(table, parts, verdict)`, plus
  `imbalance_comparison(...)`, `permutation_importance_train(...)`, `stratified_holdout_bracket(...)`,
  and `write_report(...)` → `outputs/AA-evals/<date>/split-checks-<date>.md`. Covers all six checks:
  label base-rate (chi-square on the 2x2), binary-feature proportionality (`f_tl_cdl_*` + flags),
  continuous KS + PSI ranked worst-first, panel/coin representation (one-sided coins flagged),
  temporal-integrity embargo re-assert, and a data-readiness PASS/REVIEW/FAIL verdict separate from
  the model GO/NO-GO. Validated end-to-end on a slice of `dataset_1h_allmarket.parquet` (correctly
  flagged a one-sided coin and feature drift) and on synthetic edge cases (permutation importance
  ranked the true signal above noise; the report renders).
- **`inputs/model_assessment_1h.py` extended.** `blind_metrics` now also returns Cohen's Kappa,
  per-class precision/recall/F1, the confusion matrix and OOB; `write_record` renders a
  "Classification view" block beside the existing caret-style Brier table. Compiles clean. After-fee
  Metric 2 still decides GO/NO-GO.
- **Open items resolved (finalized decisions, baked into the code):**
  - Thresholds: base-rate tolerance **±5 pp**, PSI **0.10 / 0.25**, KS **α = 0.01** (Keller 2025
    flags drift with `ks_2samp` at p < 0.01; tightened from the proposed 0.05).
  - Imbalance slate: **natural + `class_weight="balanced"` only. SMOTE excluded** (synthetic
    oversampling of autocorrelated bars interpolates between non-independent states).
  - Stratified-random holdout: **kept as an optimistic bracket only** (Parente 2026 idiom: N
    stratified 70/30 draws, mean ± std), never the headline — time-agnostic shuffling leaks adjacent
    bars and overstates the edge. The temporal final-year OOS remains the only basis for GO/NO-GO.
- **Notebook wiring is OWNED BY SEAMUS.** He authors cell 14 (the Model Training /
  stratification-checks narrative) and pastes the wiring himself. Paste-ready cells are in
  `tasks/notebook-wiring-snippets.md` (Variable Selection markdown + code; the audit code cell that
  goes immediately after `train, test, cut = t1.split(df)`). Do not rewrite cell 14.
- **Environment note:** the project `.venv` is a macOS venv; it cannot be executed from the Linux
  sandbox (its `python` symlink dangles there). Standalone validation must be run on the Mac.

---

## RECONCILIATION — code vs the refined spec (do these first)

1. **Imbalance choice must grade calibration, not just Kappa.** Section A.3 (below) argues that
   because we act on calibrated probabilities above the 0.60 filter, `class_weight="balanced"`
   distorts exactly those probabilities and may HURT; it is a candidate to test, not a default. The
   current `imbalance_comparison` chooses `best` by Kappa then minority recall only. Add a
   calibration grade to the comparison — Brier score and a reliability read on the embargoed
   out-of-fold probabilities for each treatment — and stop auto-preferring `balanced`. Surface
   calibration in the report and let it co-decide the treatment with Kappa and minority recall.
2. **Permutation-importance window.** The spec says permutation importance "on the held-out window";
   the implementation computes it on a temporal inner holdout at the tail of TRAIN to keep the OOS
   year blind. Confirm with Seamus which he wants. If the true OOS window is used, gate it so it runs
   only as a post-GO/NO-GO diagnostic, never during selection.
3. **Audit table emphasis.** The compact `table` interleaves label/binary/continuous rows. Per the
   refined section A, lead the surfaced output with panel and coin composition (the dimension that
   bites first on this unequal-history panel), then drift, then imbalance.
4. **Notebook narrative ↔ code.** Ensure cell 14's prose mirrors the finalized decisions (KS 0.01,
   no SMOTE, PSI 0.10/0.25, ±5 pp, stratified-random as bracket only).

---

## Next model: start here (ordered)

1. Apply reconciliation items 1–3 above to `inputs/split_checks.py` (and the calibration surfacing
   to `write_report`). Re-run the standalone validations.
2. Finish the full-market build per `session-handover-2026-06-21-pm.md` steps 1–2 (complete the 1h
   download to 433/433, re-aggregate flow, rebuild `dataset_1h_allmarket.parquet` at FULL market —
   the parquet on disk is a partial/subset build).
3. Run the split audit as a GATE on the full-market temporal split BEFORE reading GO/NO-GO. A NO-GO
   with large drift means regime change, not absence of edge.
4. Run variable selection (B) on the full dataset to set `SELECTED_FEATURES`.
5. Proceed through the remaining handover steps: Priority 1b label sweep, exit-geometry sweep, model
   assessment (now with the classification view), and the honest full-market OOS GO/NO-GO.

Standalone validation (from the project `.venv`, on the Mac):

```
.venv/bin/python inputs/split_checks.py --sample 200000
.venv/bin/python inputs/variable_selection.py --sample 25000 --l1 1.0
.venv/bin/python inputs/model_assessment_1h.py --models logreg lightgbm
```

`split_checks.py` deps: numpy, pandas, scipy, scikit-learn (in `.venv`); `to_markdown()` in the
report needs `tabulate` (pip into `.venv` if missing, never system).

---

## A. Post-split train/test representativeness and imbalance audit  (spec, retained)

### This is not stratification, and why that matters

In the Bolivia LULC workflow the split is a stratified random partition (`caret::createDataPartition`,
`train_test_split(stratify=y)`), and stratification preserves the response classes' proportions across
train and test by construction. We do the opposite on purpose. `train_model_1h.split()` holds out the
final ~365 days, trains on all prior history, and embargoes the label horizon at the cut. We split by
time precisely so the model is tested on the genuine, unmanipulated future; forcing proportions would
defeat that. So stratification does not apply. What a temporal, multi-coin panel actually needs is an
audit of three distinct things, listed in order of importance for this data.

### 1. Panel and coin composition (most specific to this data)  — IMPLEMENTED (`panel_representation`)

The dataset pools hundreds of coins with very unequal history (BTC to 2017, newer coins ~2 years), so
the pooled model is implicitly weighted toward long-history coins and the regimes they lived through.
This dimension, not response-class balance, is the one that bites first. Code:

- Row share per coin in train and in test; flag coins that dominate the pool.
- Per-coin label base rate, train vs test (volatile coins hit the barrier more often).
- Coins present in only one window (late listings, delistings); they cannot be learned-then-tested
  and must be flagged or excluded.

### 2. Temporal drift between train and the held-out year  — IMPLEMENTED (`base_rate_check`, `binary_feature_check`, `continuous_drift`, `temporal_integrity`)

Because the split is by time, the hold-out can be a different market regime, and a NO-GO accompanied
by large drift points at regime change rather than absence of edge. Code:

- Base-rate (label) shift, overall and per coin: chi-square on the 2x2. Flag at ±5 pp (finalized).
- Continuous-feature drift: `scipy.stats.ks_2samp` plus a Population Stability Index per feature,
  ranked; flag PSI above 0.10 (moderate) and 0.25 (major); KS α = 0.01 (finalized).
- Binary/categorical proportion shift on the `f_tl_cdl_*` candlestick family and regime flags:
  chi-square.
- Temporal integrity: re-assert the embargo (= label horizon) separates the last training label from
  the first test bar; confirm no row sits inside the embargo; print both date spans.

### 3. Label imbalance: test it, do not assume it  — PARTIALLY IMPLEMENTED (see reconciliation item 1)

The barrier label is roughly 0.32 positive. The Bolivia move (compare natural against
`class_weight="balanced"`, plus SMOTE) was made for a classifier that predicts by argmax, where
rebalancing lifts minority recall. We do not predict by argmax: we act on calibrated probabilities
above a 0.60 confidence threshold, and `class_weight="balanced"` distorts exactly those probabilities.
So class-weighting is a candidate to test, not a default, and may well hurt. Code it as a controlled
comparison against the natural distribution (SMOTE excluded, finalized):

- Treatments compared on the same temporal split: natural and `class_weight="balanced"`
  (`compute_class_weight`).
- Graded with Cohen's Kappa, per-class precision/recall/F1 (`precision_recall_fscore_support(
  average=None)`), the confusion matrix, OOB for the forest, AND calibration: does the treatment move
  the probabilities the confidence filter depends on? (Calibration grade still to add — item 1.)
- Cross-validation is embargoed and time-indexed (`TimeSeriesSplit` with a gap equal to the label
  horizon), never shuffled KFold. (Implemented.)
- Any resampling stays inside the training window. (Moot: SMOTE excluded.)

### Feature importance  — IMPLEMENTED with a caveat (see reconciliation item 2)

Permutation importance, preferred over impurity importance (biased toward high-cardinality continuous
features and unreliable under indicator correlation). Currently computed on a temporal inner holdout
of TRAIN to keep the OOS year blind; spec said "held-out window" — confirm.

### The decision still rests on money

Kappa, accuracy, OOB and per-class F1 are diagnostics: they say whether the minority (barrier-hit)
class is learned and whether a treatment helps. They do not decide GO/NO-GO. The after-fee Metric 2
(net expectancy per confident trade, against buy-and-hold and a coin-flip) remains the deciding
number. A treatment is chosen by Kappa, minority recall AND calibration; the model ships only if it
also clears the money metric.

### Where it lives  — DONE

`inputs/split_checks.py` (audit + imbalance + bracket + report). The Kappa / per-class /
confusion-matrix / OOB additions are folded into `inputs/model_assessment_1h.py` so one pass reports
both the calibration view and this classification view. The stratified-random split runs only as an
optimistic bracket that brackets the temporal result from above, never the headline.

---

## B. glmnet / variable-selection visualizations  — MODULE DONE; notebook wiring owned by Seamus

Built in `inputs/variable_selection.py` — native-Python analogues of the R `glmnet` + `coefplot`
workflow, applied to the `f_` features and the binary triple-barrier `label` (`family="binomial"`).
No forestry variables; the R study was the recipe only.

R → Python mapping implemented:

- `useful::build.x` / `build.y` → `build_matrix()` (patsy formula or `y_col`+`x_cols`; glmnet-style
  standardization of continuous columns, 0/1 indicators left raw unless `standardize="all"`).
- `glmnet::cv.glmnet(alpha=1|0|a, nfolds=10)` → `enet_cv()` (k-fold CV over a glmnet-style lambda
  grid; lasso / ridge / elastic net via `l1_ratio`; binomial-deviance or MSE).
- `plot(cv.glmnet)` → `plot_cv_curve()`.
- `coefplot::coefpath` → `plot_coefpath()` (static) and `plot_coefpath_interactive()` (plotly).
- `coefplot::coefplot(lm, sort="magnitude")` → `plot_coef_ci()` (refit survivors unpenalized in
  statsmodels Logit for the 95% CIs sklearn does not give).
- `screen()` returns the variables retained at `lambda.1se` / `lambda.min`.

Notebook workflow (paste-ready cells in `tasks/notebook-wiring-snippets.md`):

1. `build_matrix` from the `f_` features and the label, standardized, on the TRAIN split only.
2. `enet_cv` (lasso, `l1_ratio=1.0`, 10-fold) → CV curve + coefficient path.
3. `plot_cv_curve`, `plot_coefpath` (PNG), `plot_coefpath_interactive` (HTML).
4. `screen` at `lambda.1se` → refit survivors with `plot_coef_ci`; set `SELECTED_FEATURES`.
5. Markdown explainer + per-variable data-dictionary table above each cell (in the snippets).

Dependencies (in `.venv`, never system): `statsmodels`, `patsy`, `plotly`. Cost note: the saga
logistic path is slow at the least-regularized end; the module caps the grid (`eps=1e-2`) and
warm-starts; sample 25k rows for the notebook rather than the full panel.

---

## Sequencing

The split-audit (A) is a gate that runs on the FULL-market temporal split once it is built (handover
step 2), before the GO/NO-GO is read. The variable-selection visuals (B) run on the same built
dataset and inform which features survive into the tuned model. Both depend on the full dataset
existing, so they slot in after the download finishes and `dataset_1h_allmarket.parquet` is rebuilt at
full market. Apply the reconciliation items before treating the audit as final.
