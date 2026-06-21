# TASK request — next model build (data checks + variable selection)

Compiled 2026-06-21. Two bodies of work to fold into the next full-market model build, on top of the remaining tasks in `session-handover-2026-06-21-pm.md`:

A. Post-split train/test representativeness and imbalance audit (new requirement). The Winrock Bolivia LULC Random-Forest workflow (saved verbatim at `tasks/ref-bolivia-lulc-rf-proportionality.py`) was the starting point, but its stratification idea does not transfer to a temporal, multi-coin panel; section A reframes it as a panel-composition, drift, and imbalance audit.

B. The glmnet / variable-selection visualizations now built in `inputs/variable_selection.py` — wire them into the `03-trader-execution.ipynb` Variable Selection section.

---

## A. Post-split train/test representativeness and imbalance audit

### This is not stratification, and why that matters

In the Bolivia LULC workflow the split is a stratified random partition (`caret::createDataPartition`, `train_test_split(stratify=y)`), and stratification preserves the response classes' proportions across train and test by construction. We do the opposite on purpose. `train_model_1h.split()` holds out the final ~365 days, trains on all prior history, and embargoes the label horizon at the cut. We split by time precisely so the model is tested on the genuine, unmanipulated future; forcing proportions would defeat that. So stratification does not apply. What a temporal, multi-coin panel actually needs is an audit of three distinct things, listed in order of importance for this data.

### 1. Panel and coin composition (most specific to this data)

The dataset pools hundreds of coins with very unequal history (BTC to 2017, newer coins ~2 years), so the pooled model is implicitly weighted toward long-history coins and the regimes they lived through. This dimension, not response-class balance, is the one that bites first. Code:

- Row share per coin in train and in test; flag coins that dominate the pool.
- Per-coin label base rate, train vs test (volatile coins hit the barrier more often).
- Coins present in only one window (late listings, delistings); they cannot be learned-then-tested and must be flagged or excluded.

### 2. Temporal drift between train and the held-out year

Because the split is by time, the hold-out can be a different market regime, and a NO-GO accompanied by large drift points at regime change rather than absence of edge. Code:

- Base-rate (label) shift, overall and per coin: two-proportion z-test or `scipy.stats.chi2_contingency`. Propose flag at ±5 absolute percentage points (confirm).
- Continuous-feature drift: `scipy.stats.ks_2samp` plus a Population Stability Index per feature, ranked; flag PSI above 0.10 (moderate) and 0.25 (major).
- Binary and categorical proportion shift on the `f_tl_cdl_*` candlestick family and any regime flags: chi-square goodness-of-fit.
- Temporal integrity: re-assert the embargo (equal to the label horizon) separates the last training label from the first test bar; confirm no row sits inside the embargo; print both date spans.

### 3. Label imbalance: test it, do not assume it

The barrier label is roughly 0.32 positive. The Bolivia move (compare natural against `class_weight="balanced"`, plus SMOTE) was made for a classifier that predicts by argmax, where rebalancing lifts minority recall. We do not predict by argmax: we act on calibrated probabilities above a 0.60 confidence threshold, and `class_weight="balanced"` distorts exactly those probabilities. So class-weighting is a candidate to test, not a default, and may well hurt. Code it as a controlled comparison against the natural distribution, with SMOTE as a third, flagged option:

- Treatments compared on the same temporal split: natural, `class_weight="balanced"` (`compute_class_weight`), and (flagged) SMOTE fit strictly within the training fold.
- Graded with Cohen's Kappa, per-class precision, recall and F1 (`precision_recall_fscore_support(average=None)`), the confusion matrix, OOB for the forest, and calibration: does the treatment move the probabilities the confidence filter depends on?
- Cross-validation is embargoed and time-indexed (`TimeSeriesSplit` with a gap equal to the label horizon, or purged walk-forward), never shuffled KFold, which leaks on ordered bars.
- Any resampling stays inside the training window, never across the embargo or into the hold-out.

### Feature importance

Permutation importance on the held-out window, preferred over impurity importance, which is biased toward high-cardinality continuous features and unreliable under the correlation among our indicators.

### The decision still rests on money

Kappa, accuracy, OOB and per-class F1 are diagnostics: they say whether the minority (barrier-hit) class is learned and whether a treatment helps. They do not decide GO/NO-GO. The after-fee Metric 2 (net expectancy per confident trade, against buy-and-hold and a coin-flip) remains the deciding number. A model can post a respectable Kappa and still lose money on its confident subset after fees, and the reverse. So a treatment is chosen by Kappa, minority recall and calibration; the model ships only if it also clears the money metric.

### Where it lives

A new `inputs/split_checks.py` exposing `audit_split(train, test, feat_cols, label_col="label", by="symbol")` that returns the three-part table (panel composition, drift, imbalance) and a data-readiness verdict separate from the model GO/NO-GO, written to `outputs/AA-evals/<date>/split-checks-<date>.md` and surfaced in the notebook. Fold the Kappa, per-class, confusion-matrix and OOB additions into `inputs/model_assessment_1h.py`, which already produces the caret-style Brier table, so one pass reports both the calibration view and this classification view. A stratified-random split may be run as an optimistic sanity baseline that brackets the temporal result from above, never as the headline.

### Open items for Seamus

- Confirm thresholds: base-rate tolerance (proposed ±5 pp), PSI cutoffs (0.10 and 0.25), KS alpha.
- Confirm the imbalance slate: natural plus class-weight only, or also SMOTE (within-train)?
- Confirm whether to run the stratified-random sanity baseline alongside the temporal split.

---

## B. glmnet / variable-selection visualizations

Built this session in `inputs/variable_selection.py` — native-Python analogues of the R `glmnet` + `coefplot` workflow, applied to the day-trader 1h feature set (the `f_` features) and the binary triple-barrier `label` (`family="binomial"`). No forestry variables are used; the R study was the recipe only.

R → Python mapping implemented:

- `useful::build.x` / `build.y` → `build_matrix()` (patsy formula or `y_col`+`x_cols`; glmnet-style standardization of continuous columns, 0/1 indicators left raw unless `standardize="all"`).
- `glmnet::cv.glmnet(alpha=1|0|a, nfolds=10)` → `enet_cv()` (k-fold CV over a glmnet-style lambda grid; lasso / ridge / elastic net via `l1_ratio`; binomial-deviance or MSE).
- `plot(cv.glmnet)` → `plot_cv_curve()` (metric vs log-lambda, red dots + grey 1-se whiskers, dotted `lambda.min` / `lambda.1se`, nonzero-coefficient counts on the top axis).
- `coefplot::coefpath` → `plot_coefpath()` (static, labeled) and `plot_coefpath_interactive()` (plotly: hover labels + range slider, standing in for the dygraphs range selector in the R widget).
- `coefplot::coefplot(lm, sort="magnitude")` → `plot_coef_ci()` (refit the screened survivors unpenalized in statsmodels OLS/Logit to recover the 95% CIs sklearn does not give; dot-and-whisker sorted by magnitude).
- `screen()` returns the variables retained at `lambda.1se` / `lambda.min` — the variable-screening output.

Workflow to wire into the notebook Variable Selection section:

1. Build the design matrix from the `f_` features and the label, standardized.
2. `enet_cv` (lasso, `l1_ratio=1.0`, 10-fold) → CV curve + coefficient path.
3. `plot_cv_curve`, `plot_coefpath` (PNG), `plot_coefpath_interactive` (HTML) — both static and interactive per the agreed output.
4. `screen` at `lambda.1se` → refit the survivors with `plot_coef_ci` for the magnitude-sorted CI plot.
5. Markdown explainer + per-variable data-dictionary table above each code cell, matching the existing notebook convention.

Dependencies (installed into `.venv` this session, never system): `statsmodels`, `patsy`, `plotly`.

Run / validate standalone:

```
.venv/bin/python inputs/variable_selection.py --sample 25000 --l1 1.0
# figures -> outputs/AA-evals/varselect/{cv_curve.png, coefpath.png, coefpath.html, coef_ci.png}
```

Note on cost: logistic elastic-net paths use sklearn's `saga` solver, which is slow at the least-regularized end. The module caps the lambda grid (`eps=1e-2`) and warm-starts down the path; for the notebook, sample rows (25k is plenty for the screening picture) rather than running the full panel.

---

## Sequencing

The split-audit (A) is a gate that should run on the FULL-market train/test split once it is built (handover step 2), before the GO/NO-GO is read. The variable-selection visuals (B) run on the same built dataset and inform which features survive into the tuned model. Both depend on the full dataset existing, so they slot in after the download finishes and `dataset_1h_allmarket.parquet` is rebuilt at full market.
