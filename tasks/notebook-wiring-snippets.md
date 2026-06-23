# Notebook wiring snippets — 03-trader-execution.ipynb

Paste-ready cells for the two TASK_next-model-build pieces. Cell 14 (the Model Training /
stratification-checks narrative) is yours; nothing here touches it. The supporting modules are
already in place and validated: `inputs/split_checks.py` (new) and `inputs/model_assessment_1h.py`
(classification view added).

Finalized decisions the code uses (mirror these in your cell-14 prose so doc and code agree):
base-rate tolerance ±5 pp, PSI 0.10 / 0.25, **KS α = 0.01** (Keller 2025), **SMOTE excluded**,
stratified-random 70/30 holdout as an **optimistic bracket only** (Parente 2026), embargoed
TimeSeriesSplit for CV.

---

## B — Variable Selection

### Cell 12 (markdown) — replace the `## Variable Selection` cell with:

```markdown
## Variable Selection

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

**Why lasso, why the 1-se rule.** The L1 path drives weak coefficients to exactly zero, so the survivors are a genuine subset, not a re-weighting. `lambda.1se`, the most-regularized lambda within one standard error of the minimum-deviance lambda, is the conventional parsimonious choice: it trades a sliver of fit for a smaller, more stable feature set. Selection runs on the TRAIN split only. The saga logistic path is slow at the least-regularized end, so the cell samples 25k training rows, which is plenty for the screening picture. `SELECTED_FEATURES` feeds the head-to-head below: set `feat = SELECTED_FEATURES` and re-run training to use it.
```

### Cell 13 (code) — replace the existing elastic-net cell with:

```python
# Stage ii: elastic-net (glmnet-analogue) variable selection on the TRAINING split ONLY, via
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

    print(f"\nelastic-net kept {len(SELECTED_FEATURES)} of {len(feat)} features at lambda.1se.")
    print("top kept:", ", ".join(f"{n}({v:+.3f})" for n, v in kept[:15]))
    print("interactive coefficient path (open in browser):", p_cph)
    print("\nTo train the head-to-head on this subset: set  feat = SELECTED_FEATURES  then re-run training.")
else:
    SELECTED_FEATURES = []
    print("build the 1h dataset first (see Import Data).")
```

---

## A — Post-split audit

### New code cell — insert IMMEDIATELY AFTER the split cell (`train, test, cut = t1.split(df)`) and BEFORE the scoring cell (`lines, scored = [], []`):

```python
# Post-split DATA-READINESS audit (inputs/split_checks.py): proportionality + drift between TRAIN
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
    print(f"\nimbalance treatment (chosen by Kappa + minority recall): {best}")
    for name, m in imb.items():
        print(f"  {name:9s} kappa {m['kappa']:.3f}  minority-recall {m['minority_recall']:.3f}  "
              f"OOB {m['oob']:.3f}  CV-acc {m['cv_acc_mean']:.3f}+/-{m['cv_acc_std']:.3f}")
    perm = sck.permutation_importance_train(
        train, feat, class_weight=(None if best == "natural" else "balanced"), sample=80000)
    bracket = sck.stratified_holdout_bracket(df, feat, sample=150000)
    print(f"\nstratified-random bracket (OPTIMISTIC, not the headline): "
          f"kappa {bracket['kappa'][0]:.3f}+/-{bracket['kappa'][1]:.3f}")

    rec = sck.write_report(
        table, parts, verdict, imb, best, bracket, perm, out_dir=str(OUTPUTS / "AA-evals"),
        label_meta=(f"Label +{bd.LABEL['tgt_atr']}/-{bd.LABEL['stp_atr']} ATR within "
                    f"{bd.LABEL['horizon_bars']} bars; base rate {df['label'].mean():.3f}."))
    print("split-checks record:", rec)
else:
    print("run the split cell above first (need train / test / feat).")
```

The audit writes `outputs/AA-evals/<date>/split-checks-<date>.md`. The classification view (Kappa,
per-class P/R/F1, confusion, OOB) appears automatically in the Model Assessment record from
`inputs/model_assessment_1h.py` — no extra notebook cell needed there.

---

## Standalone validation (from the project .venv, on your Mac)

```
.venv/bin/python inputs/split_checks.py --sample 200000
.venv/bin/python inputs/variable_selection.py --sample 25000 --l1 1.0
.venv/bin/python inputs/model_assessment_1h.py --models logreg lightgbm
```

## Notes
- `split_checks.py` deps: numpy, pandas, scipy, scikit-learn (all already in `.venv`). `to_markdown()`
  in the report needs `tabulate`; if missing, `pip install tabulate` into the `.venv` (never system).
- Scratch files left in `outputs/` that the sandbox could not delete — safe to `rm` on the Mac:
  `outputs/_nb_edit.py`, `outputs/_val_split_checks.py`, `outputs/_val.log`.
