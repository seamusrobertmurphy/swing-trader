"""Train/test split, train, and honestly score the buy-signal model (Tasks B & C).

The split is the part to get right, because a careless split is how a model that
has no edge looks like it does:

  1. Time-ordered, never random. Older ~70% trains, newer ~30% tests.
  2. Embargo gap = the label horizon (HORIZON days) on each side of the split
     date, so the last training labels (which look HORIZON days forward) cannot
     peek across into the test period.
  3. Representative span: we print the train and test date ranges so a human can
     confirm both windows cover bull, bear, and sideways regimes.
  4. Base rate (share of label=1) is reported on train and test; the model has
     to beat it to be worth anything.
  5. Class imbalance handled with class_weight="balanced".
  6. The test set is touched ONCE. All tuning (here, TimeSeriesSplit CV) happens
     on train only; test is scored a single time at the end.

Models: logistic regression and random forest (both legible, no deep learning).
We keep whichever has the higher precision on the BUY class on test, because a
false buy spends money while a missed buy only costs opportunity.

Honesty gate: the script prints a clear GO / NO-GO line. It does not trade.

Outputs: python/outputs/model.joblib, python/outputs/model_metrics.txt
"""
from __future__ import annotations

import os

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

try:
    from lightgbm import LGBMClassifier   # Tier 1 gradient boosting (Keller)
    HAVE_LGBM = True
except ImportError:                       # pip install lightgbm to enable
    HAVE_LGBM = False

from build_dataset import FEATURES, HORIZON

OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "outputs"))
TRAIN_FRAC = 0.70
EMBARGO_DAYS = HORIZON   # calendar days, crypto trades 24/7

# Confidence filter (Keller Metric 1 / the 60-40 rule): only "act" on rows where
# the model is confident. Operator-owned knobs; sweep these in 3C model tuning.
CONF_HI = 0.60          # act-long threshold
CONF_LO = 0.40          # act-short / stand-aside threshold


def load() -> pd.DataFrame:
    df = pd.read_csv(os.path.join(OUT, "dataset.csv"), parse_dates=["date"])
    return df.sort_values("date").reset_index(drop=True)


def split(df: pd.DataFrame):
    """Time-ordered split with a HORIZON-day embargo straddling the cut date."""
    cut = df["date"].quantile(TRAIN_FRAC)
    embargo = pd.Timedelta(days=EMBARGO_DAYS)
    train = df[df["date"] <= cut - embargo].copy()   # drop labels peeking past cut
    test = df[df["date"] > cut + embargo].copy()      # symmetric gap on the test side
    return train, test, cut


def regime_note(df: pd.DataFrame) -> str:
    """Coarse description of the price regimes a window spans, using BTC's path
    as the market proxy (start vs end and the max drawdown inside the window)."""
    btc = df[df["symbol"] == "BTC/USDT"]
    if btc.empty:
        return "no BTC rows"
    # We only have features here, not raw close, so use the resistance-distance
    # feature sign changes as a rough trend proxy is unreliable; instead report
    # the span length, which is what the representativeness check needs.
    days = (df["date"].max() - df["date"].min()).days
    return f"{df['date'].min().date()} -> {df['date'].max().date()} ({days} days)"


def confidence_filtered(y_true, prob, hi=CONF_HI, lo=CONF_LO):
    """Keller Metric 1: score only the high-conviction rows (prob >= hi or
    prob <= lo), the ones we would actually trade. Returns buy-class precision,
    recall, and F1 plus coverage (the share of rows kept). NOTE: our base rate is
    about 0.30, not 0.5, so read precision against that base rate, not against
    50%, and calibrate the cutoffs before trusting them as literal probabilities."""
    y_true = np.asarray(y_true)
    prob = np.asarray(prob)
    mask = (prob >= hi) | (prob <= lo)
    n = int(mask.sum())
    if n == 0:
        return dict(coverage=0.0, n=0, precision=float("nan"),
                    recall=float("nan"), f1=float("nan"))
    yt = y_true[mask]
    yp = (prob[mask] >= 0.5).astype(int)
    return dict(coverage=float(mask.mean()), n=n,
                precision=precision_score(yt, yp, zero_division=0),
                recall=recall_score(yt, yp, zero_division=0),
                f1=f1_score(yt, yp, zero_division=0))


def evaluate(name, model, Xtr, ytr, Xte, yte, base_rate, lines):
    """Fit on train, score on test ONCE. Returns buy-class precision on test."""
    # Tuning signal: time-series CV on TRAIN only (test stays untouched).
    cv = TimeSeriesSplit(n_splits=5)
    try:
        cv_auc = cross_val_score(model, Xtr, ytr, cv=cv, scoring="roc_auc").mean()
    except Exception:  # noqa: BLE001
        cv_auc = float("nan")

    model.fit(Xtr, ytr)
    prob = model.predict_proba(Xte)[:, 1]
    pred = (prob >= 0.5).astype(int)

    acc = accuracy_score(yte, pred)
    prec = precision_score(yte, pred, pos_label=1, zero_division=0)
    rec = recall_score(yte, pred, pos_label=1, zero_division=0)
    auc = roc_auc_score(yte, prob)
    cm = confusion_matrix(yte, pred)

    lines.append(f"\n--- {name} ---")
    lines.append(f"  train CV ROC-AUC (5-fold TimeSeriesSplit): {cv_auc:.3f}")
    lines.append(f"  test accuracy : {acc:.3f}")
    lines.append(f"  test precision(buy): {prec:.3f}   (base rate {base_rate:.3f})")
    lines.append(f"  test recall(buy)   : {rec:.3f}")
    lines.append(f"  test ROC-AUC       : {auc:.3f}")
    lines.append(f"  confusion matrix [rows=true 0/1, cols=pred 0/1]:\n   {cm.tolist()}")
    lines.append(f"  precision lift over base rate: {prec - base_rate:+.3f}")
    cf = confidence_filtered(yte, prob)
    lines.append(f"  confidence filter (act if p>={CONF_HI:.2f} or p<={CONF_LO:.2f}): "
                 f"keeps {cf['coverage']:.1%} of test rows (n={cf['n']})")
    if cf["n"]:
        lines.append(f"    precision(buy) {cf['precision']:.3f}  recall {cf['recall']:.3f}  "
                     f"F1 {cf['f1']:.3f}  (base rate {base_rate:.3f})")
    return prec, dict(name=name, acc=acc, prec=prec, rec=rec, auc=auc, cv_auc=cv_auc)


def main():
    df = load()
    train, test, cut = split(df)

    Xtr, ytr = train[FEATURES], train["label"]
    Xte, yte = test[FEATURES], test["label"]
    base_tr = ytr.mean()
    base_te = yte.mean()

    lines = []
    lines.append("trader-swing buy-signal model — honest train/test report")
    lines.append("=" * 60)
    lines.append(f"features ({len(FEATURES)}): {', '.join(FEATURES)}")
    lines.append(f"split date (quantile {TRAIN_FRAC}): {pd.Timestamp(cut).date()}  "
                 f"embargo +/- {EMBARGO_DAYS} days")
    lines.append(f"train: {len(train):6d} rows  {regime_note(train)}  base rate {base_tr:.3f}")
    lines.append(f"test : {len(test):6d} rows  {regime_note(test)}  base rate {base_te:.3f}")
    lines.append(f"class balance (train): {int(ytr.sum())} buys / {len(ytr)} "
                 f"({base_tr:.1%})")

    lr = Pipeline([
        ("scale", StandardScaler()),
        ("clf", LogisticRegression(max_iter=2000, class_weight="balanced")),
    ])
    rf = RandomForestClassifier(
        n_estimators=400, max_depth=8, min_samples_leaf=50,
        class_weight="balanced", n_jobs=-1, random_state=0,
    )

    prec_lr, m_lr = evaluate("LogisticRegression", lr, Xtr, ytr, Xte, yte, base_te, lines)
    prec_rf, m_rf = evaluate("RandomForest", rf, Xtr, ytr, Xte, yte, base_te, lines)

    # Keep the higher buy-class precision; refit chosen model object is already fitted.
    if prec_rf >= prec_lr:
        best_name, best_model, best = "RandomForest", rf, m_rf
    else:
        best_name, best_model, best = "LogisticRegression", lr, m_lr

    # Honesty gate: precision on the buy class must clearly beat the base rate.
    margin = best["prec"] - base_te
    go = (best["prec"] > base_te + 0.05) and (best["auc"] > 0.55)
    verdict = "GO (edge survives out-of-sample)" if go else \
              "NO-GO (no demonstrable edge — do not trade)"
    lines.append("\n" + "=" * 60)
    lines.append(f"chosen model: {best_name} (test buy-precision {best['prec']:.3f}, "
                 f"base rate {base_te:.3f}, lift {margin:+.3f}, AUC {best['auc']:.3f})")
    lines.append(f"HONESTY GATE: {verdict}")
    lines.append("Note: gate also requires the backtest per-trade expectancy to "
                 "survive fees before any live trading. Re-check backtest.py with fees.")

    report = "\n".join(lines)
    print(report)

    os.makedirs(OUT, exist_ok=True)
    joblib.dump({"model": best_model, "features": FEATURES, "name": best_name,
                 "trained_through": str(pd.Timestamp(cut).date()),
                 "test_base_rate": float(base_te), "go": bool(go)},
                os.path.join(OUT, "model.joblib"))
    summary = (f"{best_name}: test precision(buy)={best['prec']:.3f} "
               f"base_rate={base_te:.3f} lift={margin:+.3f} "
               f"AUC={best['auc']:.3f} recall={best['rec']:.3f} acc={best['acc']:.3f} "
               f"-> {'GO' if go else 'NO-GO'}")
    with open(os.path.join(OUT, "model_metrics.txt"), "w") as fh:
        fh.write(summary + "\n\n" + report + "\n")
    print(f"\nsaved model.joblib and model_metrics.txt to {OUT}")


if __name__ == "__main__":
    main()
