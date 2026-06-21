import json

NB = "03-trader-execution/03-trader-execution.ipynb"
nb = json.load(open(NB))

def lines(s):
    return s.splitlines(keepends=True)

# ---------------------------------------------------------------- cell 12: Variable Selection (md)
cell12 = """## Variable Selection

Stage ii: prune the broad candidate set to the subset that earns its place, BEFORE the head-to-head and before any hyperparameter tuning, using the TRAINING window only so the final-year hold-out stays blind (otherwise the blind score is no longer blind).

This is wired to `inputs/variable_selection.py`, a native-Python re-implementation of the R `glmnet` + `coefplot` elastic-net screening idiom, applied to the `f_` feature set and the binary triple-barrier `label` (`family="binomial"`). The R study was the recipe only; no forestry variables are used.

| R (glmnet / coefplot) | Python (`variable_selection.py`) | what it gives |
| --- | --- | --- |
| `useful::build.x` / `build.y` | `build_matrix()` | design matrix; continuous cols z-scored, 0/1 indicators left raw |
| `cv.glmnet(alpha=1, nfolds=10)` | `enet_cv(l1_ratio=1.0, n_folds=10)` | k-fold CV over a glmnet-style lambda grid; lambda.min / lambda.1se |
| `plot(cv.glmnet)` | `plot_cv_curve()` | binomial deviance vs log-lambda, 1-se whiskers, nonzero counts |
| `coefplot::coefpath` | `plot_coefpath()` / `plot_coefpath_interactive()` | coefficient trajectories (PNG + interactive HTML with range slider) |
| `coefplot::coefplot(sort="magnitude")` | `plot_coef_ci()` | survivors refit unpenalized (statsmodels Logit) for a 95% CI dot-whisker |
| variables kept at `lambda.1se` | `screen()` | the screened subset, into `SELECTED_FEATURES` |

**Why lasso, why the 1-se rule.** The L1 path drives weak coefficients to exactly zero, so the survivors are a genuine subset, not a re-weighting. `lambda.1se`, the most-regularized lambda within one standard error of the minimum-deviance lambda, is the conventional parsimonious choice: it trades a sliver of fit for a smaller, more stable feature set. Selection runs on the TRAIN split only. The saga logistic path is slow at the least-regularized end, so the cell samples 25k training rows, which is plenty for the screening picture. `SELECTED_FEATURES` feeds the head-to-head below: set `feat = SELECTED_FEATURES` and re-run training to use it."""

# ---------------------------------------------------------------- cell 13: Variable Selection (code)
cell13 = '''# Stage ii: elastic-net (glmnet-analogue) variable selection on the TRAINING split ONLY, via
# inputs/variable_selection.py end-to-end (build_matrix -> enet_cv -> CV curve + coef paths ->
# screen at lambda.1se -> refit survivors for 95% CIs). The blind final year is never touched.
import importlib, variable_selection as vs
importlib.reload(vs)
from IPython.display import Image, display

VARSEL_DIR = OUTPUTS / "AA-evals" / "varselect"
VARSEL_DIR.mkdir(parents=True, exist_ok=True)

if df is not None and feat:
    tr_vs, _te_vs, _cut = t1.split(df)                          # select on TRAIN; OOS stays blind
    samp = tr_vs.dropna(subset=[*feat, "label"])
    if len(samp) > 25000:                                       # saga path is slow; 25k screens fine
        samp = samp.sample(25000, random_state=0)
    X, y, _ = vs.build_matrix(samp, y_col="label", x_cols=feat, standardize=True)
    res = vs.enet_cv(X, y, family="binomial", l1_ratio=1.0, n_folds=10, verbose=False)
    print(f"lasso path on {len(samp):,} TRAIN rows x {len(feat)} features.")
    print(f"lambda.min={res['lambda_min']:.4g} (nonzero {int(res['nonzero'][res['i_min']])}), "
          f"lambda.1se={res['lambda_1se']:.4g} (nonzero {int(res['nonzero'][res['i_1se']])})")

    p_cv  = vs.plot_cv_curve(res, str(VARSEL_DIR / "cv_curve.png"))
    p_cp  = vs.plot_coefpath(res, str(VARSEL_DIR / "coefpath.png"))
    p_cph = vs.plot_coefpath_interactive(res, str(VARSEL_DIR / "coefpath.html"))
    display(Image(filename=p_cv)); display(Image(filename=p_cp))

    kept = vs.screen(res, "1se") or vs.screen(res, "min")        # survivors, largest |coef| first
    SELECTED_FEATURES = [n for n, _ in kept]
    ci_cols = (SELECTED_FEATURES or [n for n, _ in vs.screen(res, "min")])[:12]
    p_ci = vs.plot_coef_ci(samp, "binomial", str(VARSEL_DIR / "coef_ci.png"),
                           y_col="label", x_cols=ci_cols,
                           title="Screened coefficients (logit, 95% CI)")
    display(Image(filename=p_ci))

    print(f"\\nelastic-net kept {len(SELECTED_FEATURES)} of {len(feat)} features at lambda.1se.")
    print("top kept:", ", ".join(f"{n}({v:+.3f})" for n, v in kept[:15]))
    print("interactive coefficient path (open in browser):", p_cph)
    print("\\nTo train the head-to-head on this subset: set  feat = SELECTED_FEATURES  then re-run training.")
else:
    SELECTED_FEATURES = []
    print("build the 1h dataset first (see Import Data).")'''

# ---------------------------------------------------------------- cell 14: Model Training (md, reconciled)
cell14 = """## Model Training

Train on all history before the final-year cut, score once on the held-out final year. Three models compete: logistic regression, random forest, LightGBM (Tier 1). Each is reported at the 0.5 threshold and under the 60/40 confidence filter (Keller Metric 1); read precision against the base rate, well below 0.5. The full record, Metric 1, Metric 2 (P&L after the 0.20% cost), and Metric 3 (AUC by volatility regime), is written to `outputs/AA-evals/` by `eval_report.write_comparison`, tagged "head-to-head (1h)", so it sits beside the other runs in `evaluation-scores.md`.

### Post-split data-readiness audit (runs after the split, before any score)

Implemented in `inputs/split_checks.py` and called in the cell right after the split below. It is a DATA-READINESS gate, reported SEPARATELY from the model GO/NO-GO. Our split is temporal, not random: the final ~365 days are held out and the label horizon is embargoed at the cut, so we cannot stratify. The honest translation of "did the split preserve proportions" for a temporal split is a representativeness and drift audit between train and the blind year. A NO-GO on the after-fee scoreboard then has two readings, no edge or an OOS year in a different regime than training, and only this audit tells them apart.

Thresholds are finalized to the sources this project follows: base-rate tolerance plus or minus 5 percentage points (Keller's 5-pp degradation alarm), PSI 0.10 moderate and 0.25 major (the credit-risk industry standard), and KS alpha 0.01 (Keller 2025 flags feature drift with `ks_2samp` at p < 0.01, not 0.05).

- **Label shift.** Base rate (mean label) train vs test, overall and per coin, with a chi-square on the 2x2; flag moves beyond 5 pp.
- **Binary-feature proportionality.** Chi-square on each 0/1 feature (the `f_tl_cdl_*` candlestick family, regime flags), the closest analogue to the Bolivia class-distribution table.
- **Continuous-feature drift.** Kolmogorov-Smirnov plus a Population Stability Index per feature, ranked worst first; flag PSI at or above 0.10 (moderate) or 0.25 (major), or KS p < 0.01.
- **Panel representation.** Each coin present on both sides, with row shares; one-sided coins flagged.
- **Temporal integrity.** Re-assert the embargo (equal to the label horizon) separates the last train label from the first test bar; print both date spans.

### Imbalance handling

The barrier label is roughly 0.32 positive. We compare, head to head on the same training window, the natural distribution against `class_weight="balanced"`. SMOTE is excluded: synthetic oversampling of autocorrelated bars interpolates between non-independent market states. Each treatment is graded by Cohen's Kappa, per-class precision, recall and F1, the confusion matrix, the OOB score (forest), and embargoed TimeSeriesSplit cross-validation (gap equal to the label horizon), never shuffled KFold, which leaks on ordered bars. The treatment is chosen by Kappa and minority (barrier-hit) recall, and the correction is applied inside the training window only.

A repeated stratified-random 70/30 holdout (the Parente 2026 idiom: N draws, mean plus or minus std) runs alongside as an optimistic bracket only. Being time-agnostic it leaks adjacent bars and overstates the edge, so it brackets the temporal result from above and never decides anything.

| produced by the audit cell | meaning |
| --- | --- |
| `verdict["status"]` | data-readiness PASS, REVIEW or FAIL (separate from the model GO/NO-GO) |
| `table` | compact proportionality readout (check, item, train and test stat, delta, p or PSI, flag) |
| `imb`, `best` | imbalance comparison and the treatment chosen by Kappa plus minority recall |
| `bracket` | optimistic stratified-random Kappa (mean plus or minus std), not the headline |
| `split-checks-<date>.md` | the full record under `outputs/AA-evals/<date>/` |

Kappa, accuracy, OOB and per-class F1 are diagnostics: they tell us whether imbalance handling and minority-class learning work. The after-fee Metric 2 (net expectancy per confident trade, against buy-and-hold and a coin-flip) remains the deciding number."""

# ---------------------------------------------------------------- new audit code cell (after split)
audit = '''# Post-split DATA-READINESS audit (inputs/split_checks.py): proportionality + drift between TRAIN
# and the blind final year, the natural-vs-class_weight imbalance comparison (embargoed TS-CV, no
# SMOTE), and the optimistic stratified-random bracket. This verdict is SEPARATE from the GO/NO-GO.
import importlib, split_checks as sck
importlib.reload(sck)

if df is not None and feat and len(train) and len(test):
    table, parts, verdict = sck.audit_split(train, test, feat, embargo_days=t1.EMBARGO_DAYS)
    print(f"DATA-READINESS: {verdict['status']}")
    for r in (verdict["reasons"] or ["no flags raised"]):
        print("  -", r)
    display(table)

    EMB_BARS = int(bd.LABEL["horizon_bars"])               # embargo the TS-CV folds by the label horizon
    imb, best = sck.imbalance_comparison(train, feat, embargo_bars=EMB_BARS, sample=150000)
    print(f"\\nimbalance treatment (chosen by Kappa + minority recall): {best}")
    for name, m in imb.items():
        print(f"  {name:9s} kappa {m['kappa']:.3f}  minority-recall {m['minority_recall']:.3f}  "
              f"OOB {m['oob']:.3f}  CV-acc {m['cv_acc_mean']:.3f}+/-{m['cv_acc_std']:.3f}")
    perm = sck.permutation_importance_train(
        train, feat, class_weight=(None if best == "natural" else "balanced"), sample=80000)
    bracket = sck.stratified_holdout_bracket(df, feat, sample=150000)
    print(f"\\nstratified-random bracket (OPTIMISTIC, not the headline): "
          f"kappa {bracket['kappa'][0]:.3f}+/-{bracket['kappa'][1]:.3f}")

    rec = sck.write_report(
        table, parts, verdict, imb, best, bracket, perm, out_dir=str(OUTPUTS / "AA-evals"),
        label_meta=(f"Label +{bd.LABEL['tgt_atr']}/-{bd.LABEL['stp_atr']} ATR within "
                    f"{bd.LABEL['horizon_bars']} bars; base rate {df['label'].mean():.3f}."))
    print("split-checks record:", rec)
else:
    print("run the split cell above first (need train / test / feat).")'''

# NOTE: cell 14 (the Model Training / stratification-checks narrative) is being authored by Seamus.
# We deliberately DO NOT rewrite it here. `cell14` above is kept only as a reference draft. We touch
# only the Variable Selection cells (12, 13) and insert the audit CODE cell after the split.
_ = cell14  # reference draft, intentionally unused

# locate the cells by content (indices may shift while the notebook is edited) -- fail loudly if stale
def find(pred, what):
    hits = [i for i, c in enumerate(nb["cells"]) if pred(c)]
    if len(hits) != 1:
        raise SystemExit(f"expected exactly one {what}, found {hits}; aborting to avoid clobbering")
    return hits[0]

i_vs_md = find(lambda c: c["cell_type"] == "markdown" and "".join(c["source"]).startswith("## Variable Selection"),
               "Variable Selection markdown")
i_vs_code = find(lambda c: c["cell_type"] == "code" and "variable selection on the TRAINING split" in "".join(c["source"]),
                 "Variable Selection code cell")
i_split = find(lambda c: c["cell_type"] == "code" and "t1.split(df)" in "".join(c["source"]) and "train, test, cut" in "".join(c["source"]),
               "split code cell")

# guard: don't double-insert the audit cell if it is already present
if any("split_checks" in "".join(c["source"]) for c in nb["cells"]):
    raise SystemExit("an audit cell referencing split_checks already exists; aborting")

nb["cells"][i_vs_md]["source"] = lines(cell12)
nb["cells"][i_vs_code]["source"] = lines(cell13)

new_cell = {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": lines(audit)}
nb["cells"].insert(i_split + 1, new_cell)   # right after the split cell

json.dump(nb, open(NB, "w"), indent=1, ensure_ascii=False)
print(f"OK: rewrote VarSel md[{i_vs_md}] + code[{i_vs_code}]; inserted audit cell after split[{i_split}].")
print("cells now:", len(nb["cells"]))
