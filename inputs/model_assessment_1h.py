"""Model assessment table (caret-style) for the 1h frame -- tuning-stage comparison.

Mirrors the forestry caretEnsemble assessment (Full-model vs cross-validated error, plus an
RMSEratio that flags overfit), adapted to a binary label. Because the target is 0/1, RMSE and MAE
are computed on the predicted PROBABILITIES: RMSE on probabilities is sqrt(Brier score) -- exactly
the "classification RMSE" caret reports -- and MAE is the mean absolute probability error.

  - Full   = fit on the training window, score in-sample (the optimistic fit).
  - CV     = time-series out-of-fold error on the training window. NOT random k-fold: financial
             bars are autocorrelated, so random folds leak the future into the past. We walk
             expanding TimeSeriesSplit folds and score each fold's held-out block.
  - RMSEratio = Full RMSE / CV RMSE. Near 1 = the in-sample and out-of-fold errors agree (stable);
             well below 1 = CV error much larger than the in-sample fit (overfit).

The final ~1 year stays a single blind test (never touched during selection/tuning); for the best
model by CV RMSE we also report blind-test AUC, confident-trade precision, and after-fee Metric 2,
and append one 'tuning' row to outputs/AA-evals/evaluation-scores.md so it sits beside the other runs.

Native Python (sklearn + lightgbm); no R/caret needed. SVM and kernel regressions from the forestry
zoo are omitted here because they do not scale to millions of 1h rows; the scalable classifiers and
an elastic-net stacking ensemble stand in for them. Plain ASCII; no orders.

Run (full, from the project .venv):  .venv/bin/python inputs/model_assessment_1h.py
Validate on a dev slice:  python inputs/model_assessment_1h.py --dataset /tmp/multi1h/dataset_1h_multi.csv \
                              --models logreg lightgbm --out /tmp/multi1h/AA-evals
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, StackingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

try:
    from lightgbm import LGBMClassifier
    HAVE_LGBM = True
except ImportError:
    HAVE_LGBM = False

import build_dataset_1h as bd
import train_model as tm
import train_model_1h as t1
import eval_report as er

CV_SPLITS = 5


def model_zoo(only=None):
    """The classification analogues of the forestry zoo, with a hyperparameter label per row.
    Linear models are wrapped in a StandardScaler pipeline; trees take raw features."""
    def lin(**kw):
        return Pipeline([("scale", StandardScaler()),
                         ("clf", LogisticRegression(max_iter=5000, class_weight="balanced", **kw))])
    zoo = []
    zoo.append(("LogReg.glm", lin(C=1.0), "C=1.0"))
    zoo.append(("LogReg.enet", lin(penalty="elasticnet", solver="saga", l1_ratio=0.5, C=0.1),
                "l1_ratio=0.5 C=0.1"))
    zoo.append(("RF", RandomForestClassifier(n_estimators=400, max_depth=8, min_samples_leaf=50,
                                             class_weight="balanced", n_jobs=-1, random_state=0),
                "mtry=auto ntree=400 depth=8"))
    if HAVE_LGBM:
        zoo.append(("LightGBM", LGBMClassifier(n_estimators=600, num_leaves=31, learning_rate=0.05,
                                              max_depth=6, min_child_samples=100, subsample=0.8,
                                              colsample_bytree=0.8, subsample_freq=5,
                                              class_weight="balanced", random_state=0, n_jobs=-1,
                                              verbosity=-1),
                    "leaves=31 lr=0.05 n=600"))
    # Elastic-net stacking ensemble (the caretEnsemble analogue): base models stacked under a
    # logistic elastic-net meta-learner (alpha/lambda -> l1_ratio/C).
    base = [("lr", lin(C=1.0)),
            ("rf", RandomForestClassifier(n_estimators=200, max_depth=8, min_samples_leaf=50,
                                          n_jobs=-1, random_state=0))]
    if HAVE_LGBM:
        base.append(("gbm", LGBMClassifier(n_estimators=300, num_leaves=31, learning_rate=0.05,
                                           random_state=0, n_jobs=-1, verbosity=-1)))
    meta = LogisticRegression(penalty="elasticnet", solver="saga", l1_ratio=0.5, C=0.1, max_iter=5000)
    zoo.append(("Ensemble.stack", StackingClassifier(estimators=base, final_estimator=meta,
                                                      cv=TimeSeriesSplit(3), n_jobs=-1),
                "stack: lr+rf+gbm, enet meta (l1=0.5 C=0.1)"))
    if only:
        keep = {m.lower() for m in only}
        zoo = [(n, e, h) for (n, e, h) in zoo if any(k in n.lower() for k in keep)]
    return zoo


def _rmse(y, p):
    return float(np.sqrt(np.mean((np.asarray(p) - np.asarray(y)) ** 2)))


def _mae(y, p):
    return float(np.mean(np.abs(np.asarray(p) - np.asarray(y))))


def _proba(est, X):
    return est.predict_proba(X)[:, 1]


def ts_cv_oof(est, X, y, n_splits=CV_SPLITS):
    """Time-series out-of-fold probabilities: walk expanding TimeSeriesSplit folds, fit on the
    train block, predict the held-out block. Returns (y_oof, p_oof) over the predicted blocks.
    (cross_val_predict cannot be used because TimeSeriesSplit is not a partition.)"""
    from sklearn.base import clone
    yv = y.to_numpy() if hasattr(y, "to_numpy") else np.asarray(y)
    yt, pt = [], []
    for tr_idx, te_idx in TimeSeriesSplit(n_splits=n_splits).split(X):
        m = clone(est)
        m.fit(X.iloc[tr_idx], yv[tr_idx])
        pt.append(_proba(m, X.iloc[te_idx]))
        yt.append(yv[te_idx])
    return np.concatenate(yt), np.concatenate(pt)


def assess(df, feat, only=None, cv_splits=CV_SPLITS):
    """Build the caret-style row set on the TRAINING window; keep the blind year aside."""
    train, test, cut = t1.split(df)
    Xtr, ytr = train[feat], train["label"]
    rows = []
    for name, est, hp in model_zoo(only):
        from sklearn.base import clone
        full = clone(est).fit(Xtr, ytr)            # in-sample fit
        p_full = _proba(full, Xtr)
        y_cv, p_cv = ts_cv_oof(est, Xtr, ytr, cv_splits)
        full_rmse, cv_rmse = _rmse(ytr, p_full), _rmse(y_cv, p_cv)
        rows.append(dict(model=name, hp=hp,
                         full_mae=_mae(ytr, p_full), full_rmse=full_rmse,
                         cv_mae=_mae(y_cv, p_cv), cv_rmse=cv_rmse,
                         rmse_ratio=(full_rmse / cv_rmse if cv_rmse else float("nan")),
                         est=est))
        print(f"  {name:16s} full RMSE {full_rmse:.4f}  CV RMSE {cv_rmse:.4f}  "
              f"ratio {rows[-1]['rmse_ratio']:.3f}")
    return rows, train, test, cut


def blind_metrics(est, train, test, feat, cost_frac, conf_hi):
    """Fit the chosen model on train, score the blind final year once: AUC, confident-trade
    precision vs base rate, after-fee Metric 2, AND the classification view (Cohen's Kappa,
    per-class precision/recall/F1, confusion matrix, OOB) -- the Bolivia-workflow diagnostics
    folded in so one assessment pass reports both the probability-calibration and the
    classification picture. The after-fee Metric 2 still decides GO/NO-GO."""
    from sklearn.base import clone
    from sklearn.metrics import (cohen_kappa_score, precision_recall_fscore_support,
                                 confusion_matrix)
    e = clone(est)
    if isinstance(e, RandomForestClassifier):
        e.set_params(oob_score=True, bootstrap=True)        # OOB is free during the same fit
    m = e.fit(train[feat], train["label"])
    prob = _proba(m, test[feat])
    yte = test["label"].to_numpy()
    base = float(yte.mean())
    auc = roc_auc_score(yte, prob) if len(np.unique(yte)) > 1 else float("nan")
    conf = prob >= conf_hi
    prec = float(yte[conf].mean()) if conf.sum() else float("nan")
    pnl = er._pnl(prob, test["trade_ret"].to_numpy(), conf_hi,
                  cost_frac) if "trade_ret" in test.columns else {"n": 0, "expectancy": float("nan")}
    pred = (prob >= 0.5).astype(int)                         # classification view at 0.5
    pr, rc, f1, _ = precision_recall_fscore_support(yte, pred, average=None, labels=[0, 1],
                                                    zero_division=0)
    return dict(base=base, auc=auc, prec=prec, trades=pnl["n"], net=pnl.get("expectancy", float("nan")),
                kappa=float(cohen_kappa_score(yte, pred)),
                precision=pr.tolist(), recall=rc.tolist(), f1=f1.tolist(),
                confusion=confusion_matrix(yte, pred, labels=[0, 1]).tolist(),
                oob=float(getattr(m, "oob_score_", float("nan"))))


def write_record(rows, blind, meta, evals_dir):
    os.makedirs(evals_dir, exist_ok=True)
    cd = datetime.now(timezone.utc).strftime("%Y%m%d")
    hd = f"{cd[:4]}-{cd[4:6]}-{cd[6:]}"
    run_dir = os.path.join(evals_dir, hd); os.makedirs(run_dir, exist_ok=True)
    stem = f"model-assessment-{cd}"
    ranked = sorted(rows, key=lambda r: r["cv_rmse"])              # lower CV RMSE = better
    headers = ["model", "hyperparameters", "Full MAE", "Full RMSE", "CV MAE", "CV RMSE", "RMSEratio"]
    lines = [f"# Model assessment ({hd}) -- caret-style, 1h frame\n",
             "RMSE/MAE are on predicted probabilities (RMSE = sqrt(Brier), the caret-style "
             "classification RMSE). Full = in-sample on the training window; CV = time-series "
             "out-of-fold on the training window; RMSEratio = Full RMSE / CV RMSE (near 1 = stable, "
             "well below 1 = overfit). The final year is held out as a single blind test (below). "
             "Ranked by CV RMSE, best first.\n",
             "| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for r in ranked:
        lines.append(f"| {r['model']} | {r['hp']} | {r['full_mae']:.4f} | {r['full_rmse']:.4f} | "
                     f"{r['cv_mae']:.4f} | {r['cv_rmse']:.4f} | {r['rmse_ratio']:.3f} |")
    best = ranked[0]
    lines.append(f"\n**Best by CV RMSE:** {best['model']} (CV RMSE {best['cv_rmse']:.4f}, RMSEratio "
                 f"{best['rmse_ratio']:.3f}).\n")
    lines.append("**Blind final-year test of the best model** (scored once): "
                 f"AUC {blind['auc']:.3f}, precision(buy|p>=0.60) {blind['prec']:.3f} vs base rate "
                 f"{blind['base']:.3f}, net P&L/trade {blind['net']*100:+.3f}% on {blind['trades']:,} "
                 f"trades.\n")
    if "kappa" in blind:                                     # classification view (Bolivia diagnostics)
        cm = blind["confusion"]
        lines += ["**Classification view** (blind test, 0.5 threshold) -- diagnostics for whether the "
                  "minority (barrier-hit) class is learned; the after-fee Metric 2 above remains the "
                  f"GO/NO-GO. Cohen's Kappa {blind['kappa']:.3f}; OOB {blind['oob']:.3f} (RandomForest only).\n",
                  "| class | precision | recall | F1 |",
                  "| --- | --- | --- | --- |",
                  f"| 0 (no-hit) | {blind['precision'][0]:.3f} | {blind['recall'][0]:.3f} | {blind['f1'][0]:.3f} |",
                  f"| 1 (barrier-hit) | {blind['precision'][1]:.3f} | {blind['recall'][1]:.3f} | {blind['f1'][1]:.3f} |",
                  f"\nConfusion matrix [true x pred]: TN {cm[0][0]:,}, FP {cm[0][1]:,}, "
                  f"FN {cm[1][0]:,}, TP {cm[1][1]:,}.\n"]
    md_path = os.path.join(run_dir, f"{stem}.md")
    open(md_path, "w").write("\n".join(lines) + "\n")

    pct = (blind["prec"] / blind["base"] - 1) * 100 if blind["base"] else float("nan")
    verdict = "GO" if (np.isfinite(blind["net"]) and blind["net"] > 0
                       and blind["prec"] > blind["base"] and blind["auc"] > 0.55) else "NO-GO"
    er._update_index(evals_dir, [hd, "tuning",
                                 f"{meta['rows']:,}r / {meta['n_feat']}f (1h all-market)",
                                 best["model"], f"{blind['auc']:.3f}", f"{blind['prec']:.3f}",
                                 f"{blind['base']:.3f}", f"{pct:+.1f}%", f"{blind['net']*100:+.2f}%",
                                 f"{blind['trades']:,}", verdict, f"[md]({hd}/{stem}.md)"])
    return md_path, best, verdict


def main():
    p = argparse.ArgumentParser(description="Caret-style model assessment table (1h frame)")
    p.add_argument("--dataset", default=bd.DATASET_PATH)
    p.add_argument("--models", nargs="+", default=None, help="subset, e.g. logreg lightgbm")
    p.add_argument("--cv-splits", type=int, default=CV_SPLITS)
    p.add_argument("--out", default=os.path.join(tm.OUT, "AA-evals"))
    a = p.parse_args()

    df = t1.load(a.dataset)
    feat = bd.feature_columns(df)
    print(f"assessing on {len(df):,} in-sample rows, {len(feat)} features\n")
    rows, train, test, cut = assess(df, feat, a.models, a.cv_splits)
    best_row = min(rows, key=lambda r: r["cv_rmse"])
    blind = blind_metrics(best_row["est"], train, test, feat, tm.COST_PCT / 100.0, tm.CONF_HI)
    md_path, best, verdict = write_record(rows, blind, dict(rows=len(df), n_feat=len(feat)), a.out)
    print(f"\nbest by CV RMSE: {best['model']} (RMSEratio {best['rmse_ratio']:.3f})  "
          f"blind net {blind['net']*100:+.3f}%/trade  verdict {verdict}")
    print("assessment record:", md_path)


if __name__ == "__main__":
    main()
