"""Post-split proportionality / drift audit + imbalance comparison for the 1h frame.

Adapts Seamus's Winrock Bolivia LULC Random-Forest proportionality workflow,
which lives in that project rather than this repo, to the trader's BINARY,
TEMPORALLY-split triple-barrier label. It is a DATA-READINESS gate, reported
SEPARATELY from the model GO/NO-GO, and it runs AFTER the split and BEFORE any
score is read.

Why this is not the Bolivia check verbatim
-------------------------------------------
The Bolivia split is a stratified RANDOM partition (caret::createDataPartition /
train_test_split(stratify=y)); its proportion table proves the random draw kept
class shares. Our split is TEMPORAL: train_model_1h.split() holds out the final
~365 days out-of-sample, trains on all prior history, and embargoes the label
horizon at the cut. We split on time deliberately, so we cannot stratify -- which
is exactly why a representativeness / drift audit between train and OOS is needed:

  - label shift      : did the base rate move train -> test?
  - covariate shift  : did feature distributions move?
  - panel composition: is every coin in both windows?

A NO-GO on the after-fee scoreboard can mean "no edge" OR "the OOS year was a
different regime than the training years." Those demand opposite responses, and
this audit is what tells them apart.

Thresholds (finalized 2026-06-21, grounded in the sources Seamus pointed to)
---------------------------------------------------------------------------
  - base-rate tolerance : +/- 5 percentage points  (Keller 2025's 5pp
                          degradation alarm; the TASK proposal)
  - PSI                 : 0.10 moderate, 0.25 major  (credit-risk industry standard)
  - KS alpha            : 0.01  (Keller 2025 flags feature drift with
                          scipy.stats.ks_2samp at p < 0.01, not 0.05)

Imbalance comparison (the Bolivia idea, translated)
---------------------------------------------------
Natural distribution vs class_weight="balanced" head-to-head on the SAME training
window, graded by Cohen's Kappa, per-class precision/recall/F1, the confusion
matrix, the OOB score (RandomForest), CALIBRATION (Brier score + Expected
Calibration Error on the embargoed out-of-fold probabilities), and EMBARGOED
TimeSeriesSplit CV (gap = label horizon) -- never shuffled KFold, which leaks on
ordered bars. SMOTE is deliberately excluded: synthetic oversampling of
autocorrelated financial bars interpolates between non-independent market states.
The strategy acts on calibrated probabilities above a 0.60 confidence filter, NOT
on argmax, so class_weight="balanced" distorts exactly those probabilities and is
a candidate to test, not a default. The treatment is chosen by the best average
rank across Kappa, minority (barrier-hit) recall AND Brier (calibration), tie-broken
by Brier -- so calibration can overturn a Kappa/recall win. The model still ships
only if it clears the after-fee Metric 2.

Validation splits
-----------------
  - headline : temporal final-year OOS (train_model_1h.split), embargo = label
               horizon. Keller's "time-based split, no shuffling." This is the
               ONLY basis for the model GO/NO-GO.
  - bracket  : repeated stratified-random 70/30 holdout (Parente 2026 idiom: N
               stratified draws, mean +/- std). A TIME-AGNOSTIC, OPTIMISTIC upper
               bound that brackets the temporal result from above. It is never
               the headline: shuffling autocorrelated bars leaks adjacent market
               states across the split and inflates the score.

No orders, no trading. Plain ASCII. Run from the project .venv:
    .venv/bin/python inputs/split_checks.py --sample 200000
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

# ----------------------------------------------------------------- thresholds
BASE_RATE_TOL_PP = 5.0     # flag if base rate moves more than this many pp train->test
PSI_MODERATE = 0.10        # moderate population shift
PSI_MAJOR = 0.25           # major population shift
KS_ALPHA = 0.01            # Kolmogorov-Smirnov significance (Keller 2025)

LABEL_COL = "label"
TIME_COL = "datetime"
GROUP_COL = "symbol"


# ----------------------------------------------------------------- primitives
def psi(expected, actual, bins: int = 10, eps: float = 1e-6) -> float:
    """Population Stability Index between a baseline (expected = train) and a
    comparison (actual = test) sample, using quantile bin edges from the baseline.
    PSI ~ sum (a% - e%) * ln(a% / e%). 0 = identical; >0.10 moderate; >0.25 major."""
    e = np.asarray(expected, float); e = e[np.isfinite(e)]
    a = np.asarray(actual, float); a = a[np.isfinite(a)]
    if len(e) < bins or len(a) < bins:
        return float("nan")
    edges = np.unique(np.quantile(e, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:                       # (near-)constant feature, nothing to drift
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    e_pct = np.histogram(e, edges)[0].astype(float); e_pct /= e_pct.sum()
    a_pct = np.histogram(a, edges)[0].astype(float); a_pct /= a_pct.sum()
    e_pct = np.clip(e_pct, eps, None); a_pct = np.clip(a_pct, eps, None)
    return float(np.sum((a_pct - e_pct) * np.log(a_pct / e_pct)))


def _is_binary(s: pd.Series) -> bool:
    u = pd.unique(pd.Series(s).dropna())
    try:
        return set(np.asarray(u, float)) <= {0.0, 1.0}
    except (TypeError, ValueError):
        return False


def expected_calibration_error(y_true, p_pred, bins: int = 10) -> float:
    """Expected Calibration Error: the row-weighted mean gap between predicted
    probability and observed frequency across `bins` equal-width probability bins.
    0 = perfectly calibrated. We act on calibrated probabilities above the 0.60
    confidence filter, so a treatment that inflates ECE is distorting exactly the
    number the strategy trades on -- the reason calibration co-decides the choice."""
    y = np.asarray(y_true, float); p = np.asarray(p_pred, float)
    m = np.isfinite(y) & np.isfinite(p)
    y, p = y[m], p[m]
    if len(y) == 0:
        return float("nan")
    edges = np.linspace(0.0, 1.0, bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    ece = 0.0
    for b in range(bins):
        sel = idx == b
        if not sel.any():
            continue
        ece += (sel.mean()) * abs(p[sel].mean() - y[sel].mean())
    return float(ece)


# --------------------------------------------------------------- check 1: label
def base_rate_check(train, test, label_col=LABEL_COL, by=GROUP_COL,
                    tol_pp=BASE_RATE_TOL_PP) -> pd.DataFrame:
    """Base rate (mean label) in train vs test, overall and per coin, with a
    chi-square on the 2x2 (pos/neg x train/test). Flags |delta| beyond tol_pp."""
    from scipy.stats import chi2_contingency

    def one(scope, ytr, yte):
        ntr, nte = len(ytr), len(yte)
        ptr, pte = float(ytr.mean()), float(yte.mean())
        table = np.array([[ytr.sum(), ntr - ytr.sum()],
                          [yte.sum(), nte - yte.sum()]], float)
        try:
            p = float(chi2_contingency(table)[1])
        except ValueError:
            p = float("nan")
        delta_pp = (pte - ptr) * 100.0
        return dict(scope=scope, n_train=ntr, n_test=nte, train_rate=ptr, test_rate=pte,
                    delta_pp=delta_pp, p_value=p, flag=abs(delta_pp) > tol_pp)

    rows = [one("ALL", train[label_col], test[label_col])]
    if by and by in train.columns and by in test.columns:
        for s in sorted(set(train[by]) | set(test[by])):
            ytr = train.loc[train[by] == s, label_col]
            yte = test.loc[test[by] == s, label_col]
            if len(ytr) and len(yte):
                rows.append(one(s, ytr, yte))
    return pd.DataFrame(rows)


# ----------------------------------------------------- check 2: binary features
def binary_feature_check(train, test, feat_cols, tol_pp=BASE_RATE_TOL_PP,
                         alpha=KS_ALPHA) -> pd.DataFrame:
    """For every 0/1 feature (regime flags, the f_tl_cdl_* candlestick family),
    compare the share of 1s train vs test with a chi-square on the 2x2 and flag
    a shift beyond tol_pp. The closest analogue to the Bolivia class-share table."""
    from scipy.stats import chi2_contingency
    rows = []
    for c in feat_cols:
        if not _is_binary(train[c]):
            continue
        atr, ate = train[c].dropna(), test[c].dropna()
        ntr, nte = len(atr), len(ate)
        if ntr == 0 or nte == 0:
            continue
        ptr, pte = float(atr.mean()), float(ate.mean())
        table = np.array([[atr.sum(), ntr - atr.sum()],
                          [ate.sum(), nte - ate.sum()]], float)
        try:
            p = float(chi2_contingency(table)[1])
        except ValueError:
            p = float("nan")
        delta_pp = (pte - ptr) * 100.0
        rows.append(dict(feature=c, train_share=ptr, test_share=pte, delta_pp=delta_pp,
                         p_value=p, flag=abs(delta_pp) > tol_pp))
    out = pd.DataFrame(rows)
    return out.sort_values("delta_pp", key=lambda s: s.abs(), ascending=False).reset_index(drop=True) \
        if len(out) else out


# ------------------------------------------------- check 3: continuous drift
def continuous_drift(train, test, feat_cols, ks_alpha=KS_ALPHA,
                     psi_mod=PSI_MODERATE, psi_major=PSI_MAJOR,
                     ks_max=50000, seed=0) -> pd.DataFrame:
    """Per continuous feature: a two-sample Kolmogorov-Smirnov test and a PSI
    between train and test, ranked by PSI (worst first). Flags PSI >= moderate or
    KS p < alpha. KS is sampled to ks_max rows per side for speed; PSI uses all."""
    from scipy.stats import ks_2samp
    rng = np.random.default_rng(seed)
    rows = []
    for c in feat_cols:
        if _is_binary(train[c]):
            continue
        a = train[c].to_numpy(float); a = a[np.isfinite(a)]
        b = test[c].to_numpy(float); b = b[np.isfinite(b)]
        if len(a) < 10 or len(b) < 10:
            continue
        sa = a if len(a) <= ks_max else rng.choice(a, ks_max, replace=False)
        sb = b if len(b) <= ks_max else rng.choice(b, ks_max, replace=False)
        ks, p = ks_2samp(sa, sb)
        pv = psi(a, b)
        sev = "major" if pv >= psi_major else ("moderate" if pv >= psi_mod else "ok")
        rows.append(dict(feature=c, ks_stat=float(ks), ks_p=float(p), psi=float(pv),
                         severity=sev, flag=bool(pv >= psi_mod or p < ks_alpha)))
    out = pd.DataFrame(rows)
    return out.sort_values("psi", ascending=False).reset_index(drop=True) if len(out) else out


# ----------------------------------------------- check 4: panel representation
def panel_representation(train, test, by=GROUP_COL) -> pd.DataFrame:
    """Confirm each symbol appears in both windows and report row shares. A coin
    on only one side cannot be learned-then-tested, so it is flagged."""
    tr = train[by].value_counts(); te = test[by].value_counts()
    rows = []
    for s in sorted(set(tr.index) | set(te.index)):
        ntr, nte = int(tr.get(s, 0)), int(te.get(s, 0))
        rows.append(dict(symbol=s, n_train=ntr, n_test=nte,
                         train_share=ntr / max(len(train), 1),
                         test_share=nte / max(len(test), 1),
                         in_both=(ntr > 0 and nte > 0), flag=not (ntr > 0 and nte > 0)))
    return pd.DataFrame(rows).sort_values("n_train", ascending=False).reset_index(drop=True)


# ------------------------------------------------- check 5: temporal integrity
def temporal_integrity(train, test, embargo_days, time_col=TIME_COL) -> dict:
    """Re-assert the embargo (= label horizon) separates the last training label
    from the first test bar; print both date spans so the cut is auditable."""
    tr_max, te_min = train[time_col].max(), test[time_col].min()
    gap = (te_min - tr_max) / pd.Timedelta(days=1)
    return dict(train_start=train[time_col].min(), train_end=tr_max,
                test_start=te_min, test_end=test[time_col].max(),
                gap_days=float(gap), embargo_days=float(embargo_days),
                embargo_respected=bool(gap >= embargo_days), flag=bool(gap < embargo_days))


# --------------------------------------------------------------- orchestrator
def audit_split(train, test, feat_cols, label_col=LABEL_COL, by=GROUP_COL,
                embargo_days=2, tol_pp=BASE_RATE_TOL_PP, ks_alpha=KS_ALPHA,
                psi_mod=PSI_MODERATE, psi_major=PSI_MAJOR):
    """Run checks 1-6 and return (table, parts, verdict). `table` is the compact
    caret-style proportionality readout; `parts` holds the per-check DataFrames;
    `verdict` is the data-readiness call, SEPARATE from the model GO/NO-GO."""
    base = base_rate_check(train, test, label_col, by, tol_pp)
    binf = binary_feature_check(train, test, feat_cols, tol_pp, ks_alpha)
    cont = continuous_drift(train, test, feat_cols, ks_alpha, psi_mod, psi_major)
    panel = panel_representation(train, test, by)
    temporal = temporal_integrity(train, test, embargo_days)

    # compact caret-style table: one row per checked item
    trows = []
    b0 = base.iloc[0]
    trows.append(dict(check="label base-rate", item="ALL",
                      train_stat=round(b0["train_rate"], 4), test_stat=round(b0["test_rate"], 4),
                      delta=round(b0["delta_pp"], 2), p_or_psi=round(b0["p_value"], 4),
                      flag="DRIFT" if b0["flag"] else "ok"))
    for _, r in binf.iterrows():
        trows.append(dict(check="binary feature", item=r["feature"],
                          train_stat=round(r["train_share"], 4), test_stat=round(r["test_share"], 4),
                          delta=round(r["delta_pp"], 2), p_or_psi=round(r["p_value"], 4),
                          flag="DRIFT" if r["flag"] else "ok"))
    for _, r in cont.iterrows():
        trows.append(dict(check="continuous PSI/KS", item=r["feature"],
                          train_stat=round(r["ks_stat"], 4), test_stat=round(r["ks_p"], 4),
                          delta=round(r["psi"], 4), p_or_psi=r["severity"],
                          flag="DRIFT" if r["flag"] else "ok"))
    table = pd.DataFrame(trows)

    # data-readiness verdict (NOT the model GO/NO-GO)
    reasons = []
    if temporal["flag"]:
        reasons.append(f"embargo violated (gap {temporal['gap_days']:.1f}d < {embargo_days}d)")
    one_sided = panel.loc[panel["flag"], "symbol"].tolist()
    if one_sided:
        reasons.append(f"{len(one_sided)} coin(s) present on only one side: {', '.join(one_sided[:6])}")
    if bool(base.iloc[0]["flag"]):
        reasons.append(f"overall base rate moved {base.iloc[0]['delta_pp']:+.1f}pp (> {tol_pp}pp)")
    n_major = int((cont["severity"] == "major").sum()) if len(cont) else 0
    n_mod = int((cont["severity"] == "moderate").sum()) if len(cont) else 0
    n_cont = max(len(cont), 1)
    if n_major:
        reasons.append(f"{n_major} feature(s) with MAJOR drift (PSI >= {psi_major})")
    if n_mod / n_cont > 0.25:
        reasons.append(f"{n_mod}/{n_cont} features with moderate drift (PSI >= {psi_mod})")
    n_coin_drift = int(base.iloc[1:]["flag"].sum()) if len(base) > 1 else 0
    if n_coin_drift:
        reasons.append(f"{n_coin_drift} coin(s) with base-rate drift > {tol_pp}pp")

    hard = temporal["flag"] or bool(one_sided)
    soft = bool(base.iloc[0]["flag"]) or n_major or (n_mod / n_cont > 0.25) or n_coin_drift
    status = "FAIL" if hard else ("REVIEW" if soft else "PASS")
    verdict = dict(status=status, reasons=reasons,
                   n_major_drift=n_major, n_moderate_drift=n_mod, n_continuous=len(cont),
                   n_binary=len(binf), n_coin_base_drift=n_coin_drift,
                   embargo_respected=temporal["embargo_respected"])
    parts = dict(base=base, binary=binf, continuous=cont, panel=panel, temporal=temporal)
    return table, parts, verdict


# ------------------------------------------- imbalance comparison (TRAIN only)
def imbalance_comparison(train, feat_cols, label_col=LABEL_COL, time_col=TIME_COL,
                         n_splits=5, embargo_bars=48, sample=None, seed=0, rf_kw=None):
    """Natural vs class_weight='balanced' head-to-head on the TRAIN window, scored
    by embargoed TimeSeriesSplit out-of-fold predictions (gap = label horizon).
    Returns (results, best). No SMOTE.

    The choice is NOT auto-preferring `balanced`. Because the strategy acts on
    calibrated probabilities above a 0.60 confidence filter -- not on argmax --
    class_weight='balanced' distorts exactly those probabilities and may HURT. So
    each treatment is also graded on calibration: the Brier score and the Expected
    Calibration Error of its embargoed out-of-fold probabilities. The winner is the
    treatment with the best AVERAGE rank across three equally weighted criteria --
    Kappa (higher), minority recall (higher), and Brier (lower) -- ties broken by
    Brier, since calibration is what the confidence filter depends on. Calibration
    can therefore overturn a Kappa/recall win, which is the point of the gate."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.metrics import (cohen_kappa_score, precision_recall_fscore_support,
                                 confusion_matrix, accuracy_score, brier_score_loss)
    tr = train.sort_values(time_col)
    if sample and len(tr) > sample:
        tr = tr.tail(sample)                                # keep most-recent, in order
    X = tr[feat_cols].astype(float).fillna(0.0).reset_index(drop=True)
    y = tr[label_col].astype(int).reset_index(drop=True)
    rf_kw = rf_kw or dict(n_estimators=300, max_depth=8, min_samples_leaf=50,
                          n_jobs=-1, random_state=seed)
    tscv = TimeSeriesSplit(n_splits=n_splits)
    results = {}
    for name, cw in (("natural", None), ("balanced", "balanced")):
        oy, op, oprob, accs = [], [], [], []
        for tr_idx, te_idx in tscv.split(X):
            if embargo_bars > 0 and len(tr_idx) > embargo_bars:
                tr_idx = tr_idx[:-embargo_bars]            # embargo the fold boundary
            m = RandomForestClassifier(class_weight=cw, **rf_kw)
            m.fit(X.iloc[tr_idx], y.iloc[tr_idx])
            pred = m.predict(X.iloc[te_idx])
            prob = m.predict_proba(X.iloc[te_idx])[:, 1]   # P(barrier-hit) for calibration
            oy.append(y.iloc[te_idx].to_numpy()); op.append(pred); oprob.append(prob)
            accs.append(accuracy_score(y.iloc[te_idx], pred))
        yv, pv, qv = np.concatenate(oy), np.concatenate(op), np.concatenate(oprob)
        pr, rc, f1, _ = precision_recall_fscore_support(yv, pv, average=None, labels=[0, 1],
                                                        zero_division=0)
        oob_kw = dict(rf_kw); oob_kw.update(oob_score=True, bootstrap=True)
        moob = RandomForestClassifier(class_weight=cw, **oob_kw).fit(X, y)
        results[name] = dict(kappa=float(cohen_kappa_score(yv, pv)),
                             precision=pr, recall=rc, f1=f1,
                             confusion=confusion_matrix(yv, pv, labels=[0, 1]),
                             cv_acc_mean=float(np.mean(accs)), cv_acc_std=float(np.std(accs)),
                             oob=float(getattr(moob, "oob_score_", float("nan"))),
                             minority_recall=float(rc[1]),
                             brier=float(brier_score_loss(yv, qv)),
                             ece=expected_calibration_error(yv, qv))
    best = _choose_imbalance(results)
    return results, best


def _choose_imbalance(results: dict) -> str:
    """Pick the treatment by best AVERAGE rank across Kappa (high), minority recall
    (high) and Brier (low), tie-broken by Brier. Calibration thus co-decides with
    Kappa and recall rather than `balanced` winning on recall alone."""
    names = list(results)
    def ranks(key, better_high=True):
        order = sorted(names, key=lambda n: results[n][key], reverse=better_high)
        return {n: i for i, n in enumerate(order)}          # 0 = best
    rk = ranks("kappa", True); rr = ranks("minority_recall", True); rb = ranks("brier", False)
    return min(names, key=lambda n: (rk[n] + rr[n] + rb[n], results[n]["brier"]))


def permutation_importance_train(train, feat_cols, label_col=LABEL_COL, time_col=TIME_COL,
                                 class_weight="balanced", sample=None, top=15, seed=0, rf_kw=None,
                                 oos=None):
    """Permutation importance (preferred over impurity for correlated features).

    DEFAULT (selection-safe): fit on the front of the TRAIN window and score on a
    temporal inner holdout at the tail of TRAIN, so the final-year OOS stays blind
    and this can inform feature selection without leakage.

    POST-DECISION DIAGNOSTIC: pass `oos` (the true held-out test frame) to score
    importance on the genuine OOS window. This is gated on purpose -- it touches the
    hold-out, so it must run ONLY after the GO/NO-GO is read, never during feature
    selection. The returned frame carries a `scored_on` column recording which
    window was used so the provenance is auditable."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.inspection import permutation_importance
    tr = train.sort_values(time_col)
    if sample and len(tr) > sample:
        tr = tr.tail(sample)
    rf_kw = rf_kw or dict(n_estimators=200, max_depth=8, min_samples_leaf=50,
                          n_jobs=-1, random_state=seed)
    if oos is not None:
        # post-GO/NO-GO diagnostic: fit on all of TRAIN, score on the true OOS window
        Xtr = tr[feat_cols].astype(float).fillna(0.0).reset_index(drop=True)
        ytr = tr[label_col].astype(int).reset_index(drop=True)
        oo = oos.sort_values(time_col)
        if sample and len(oo) > sample:
            oo = oo.tail(sample)
        Xte = oo[feat_cols].astype(float).fillna(0.0).reset_index(drop=True)
        yte = oo[label_col].astype(int).reset_index(drop=True)
        scored_on = "OOS (post-decision)"
    else:
        X = tr[feat_cols].astype(float).fillna(0.0).reset_index(drop=True)
        y = tr[label_col].astype(int).reset_index(drop=True)
        cut = int(len(X) * 0.8)
        Xtr, ytr, Xte, yte = X.iloc[:cut], y.iloc[:cut], X.iloc[cut:], y.iloc[cut:]
        scored_on = "TRAIN inner holdout (selection-safe)"
    m = RandomForestClassifier(class_weight=class_weight, **rf_kw).fit(Xtr, ytr)
    r = permutation_importance(m, Xte, yte, n_repeats=5,
                               random_state=seed, scoring="roc_auc", n_jobs=-1)
    imp = pd.DataFrame(dict(feature=feat_cols, importance=r.importances_mean,
                            std=r.importances_std)).sort_values("importance", ascending=False)
    imp["scored_on"] = scored_on
    return imp.head(top).reset_index(drop=True)


# ---------------------------------------- stratified-random bracket (Parente)
def stratified_holdout_bracket(df, feat_cols, label_col=LABEL_COL, n_repeats=10,
                               test_size=0.3, sample=None, seed=0, rf_kw=None):
    """OPTIMISTIC, time-agnostic upper bound: N stratified-random 70/30 holdouts
    (Parente 2026 idiom), report mean +/- std of Kappa/accuracy/minority recall.
    Brackets the temporal result from above; NEVER the headline."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import cohen_kappa_score, accuracy_score, recall_score
    d = df.sample(sample, random_state=seed) if (sample and len(df) > sample) else df
    X = d[feat_cols].astype(float).fillna(0.0); y = d[label_col].astype(int)
    rf_kw = rf_kw or dict(n_estimators=300, max_depth=8, min_samples_leaf=50, n_jobs=-1)
    kap, acc, mrec = [], [], []
    for i in range(n_repeats):
        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=test_size, stratify=y,
                                              random_state=seed + i)
        params = dict(rf_kw); params["random_state"] = seed + i      # avoid double random_state
        m = RandomForestClassifier(class_weight="balanced", **params).fit(Xtr, ytr)
        p = m.predict(Xte)
        kap.append(cohen_kappa_score(yte, p)); acc.append(accuracy_score(yte, p))
        mrec.append(recall_score(yte, p, pos_label=1, zero_division=0))
    agg = lambda a: (float(np.mean(a)), float(np.std(a)))
    return dict(n_repeats=n_repeats, test_size=test_size,
                kappa=agg(kap), accuracy=agg(acc), minority_recall=agg(mrec))


# --------------------------------------------------------------- md report
def _fmt_imb(results, best):
    lines = ["| treatment | Kappa | minority recall | Brier (cal) | ECE (cal) | OOB | CV acc (mean+/-std) |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for name, r in results.items():
        star = " (chosen)" if name == best else ""
        lines.append(f"| {name}{star} | {r['kappa']:.3f} | {r['minority_recall']:.3f} | "
                     f"{r['brier']:.4f} | {r['ece']:.4f} | "
                     f"{r['oob']:.3f} | {r['cv_acc_mean']:.3f}+/-{r['cv_acc_std']:.3f} |")
    return "\n".join(lines)


def write_report(table, parts, verdict, imb=None, best=None, bracket=None, perm=None,
                 out_dir=None, label_meta=None):
    """Write the audit to outputs/AA-evals/<date>/split-checks-<date>.md."""
    out_dir = out_dir or os.path.join(os.path.dirname(__file__), "..", "04-outputs", "AA-evals")
    cd = datetime.now(timezone.utc).strftime("%Y%m%d")
    hd = f"{cd[:4]}-{cd[4:6]}-{cd[6:]}"
    run_dir = os.path.join(out_dir, hd); os.makedirs(run_dir, exist_ok=True)
    path = os.path.join(run_dir, f"split-checks-{cd}.md")
    t = parts["temporal"]
    L = [f"# Split checks ({hd}) -- data-readiness audit, 1h frame\n",
         "Proportionality / drift audit between the temporal train and the final-year "
         "out-of-sample hold-out. This is a DATA-READINESS gate, SEPARATE from the model "
         "GO/NO-GO. Thresholds: base-rate +/-5pp, PSI 0.10/0.25, KS alpha 0.01.\n",
         f"**Data-readiness verdict: {verdict['status']}**",
         ("- " + "\n- ".join(verdict["reasons"])) if verdict["reasons"] else "- no flags raised", ""]
    if label_meta:
        L.append(label_meta + "\n")
    L += ["## Temporal integrity",
          f"- train: {t['train_start']} -> {t['train_end']}",
          f"- test : {t['test_start']} -> {t['test_end']}",
          f"- gap {t['gap_days']:.2f}d vs embargo {t['embargo_days']:.0f}d -> "
          f"{'OK' if t['embargo_respected'] else 'VIOLATED'}\n"]

    # Panel / coin composition leads: on this unequal-history panel it is the
    # dimension that bites first (long-history coins dominate the pooled model).
    panel = parts["panel"]
    onesided = panel[panel["flag"]]
    base = parts["base"]
    coin_base = base.iloc[1:] if len(base) > 1 else base.iloc[0:0]
    n_coin_drift = int(coin_base["flag"].sum()) if len(coin_base) else 0
    dominant = panel.sort_values("train_share", ascending=False).head(8)[
        ["symbol", "n_train", "n_test", "train_share", "test_share"]].round(4)
    L += ["## Panel and coin composition (leads -- the dimension most specific to this data)",
          f"- coins in train: {(panel['n_train'] > 0).sum()}, "
          f"in test: {(panel['n_test'] > 0).sum()}, "
          f"one-sided (cannot be learned-then-tested): {len(onesided)}",
          f"- coins with base-rate drift > {BASE_RATE_TOL_PP:.0f}pp train->test: {n_coin_drift}",
          "",
          "Dominant coins by train row-share (pooled model is implicitly weighted toward these):",
          dominant.to_markdown(index=False) if len(dominant) else "(no coins)", ""]
    if len(onesided):
        L += ["One-sided coins (flagged, exclude or handle): "
              + ", ".join(onesided["symbol"].astype(str).tolist()[:20])
              + (" ..." if len(onesided) > 20 else ""), ""]

    drifted = parts["continuous"][parts["continuous"]["flag"]] if len(parts["continuous"]) else parts["continuous"]
    L += ["## Continuous-feature drift (worst by PSI)",
          (drifted.head(15).to_markdown(index=False) if len(drifted) else "- none flagged"), ""]
    L += ["## Proportionality table (label + binary features, compact)",
          table.to_markdown(index=False) if len(table) else "(no rows)", ""]
    if imb is not None:
        L += ["## Imbalance comparison (natural vs class_weight, embargoed TS-CV, no SMOTE)",
              _fmt_imb(imb, best),
              f"\nChosen by best average rank across Kappa, minority recall and Brier "
              f"(calibration), tie-broken by Brier: **{best}**. Brier and ECE grade whether a "
              "treatment distorts the probabilities the 0.60 confidence filter trades on; "
              "`balanced` is a candidate, not a default. Diagnostic only -- the after-fee "
              "Metric 2 still decides GO/NO-GO.\n"]
    if perm is not None and len(perm):
        scored_on = perm["scored_on"].iloc[0] if "scored_on" in perm.columns else "TRAIN inner holdout"
        L += [f"## Permutation importance (chosen model, AUC drop) -- scored on {scored_on}",
              perm.to_markdown(index=False), ""]
    if bracket is not None:
        bk = bracket
        L += ["## Stratified-random holdout bracket (Parente idiom -- OPTIMISTIC, not the headline)",
              f"- {bk['n_repeats']} stratified {int((1-bk['test_size'])*100)}/{int(bk['test_size']*100)} draws",
              f"- Kappa {bk['kappa'][0]:.3f} +/- {bk['kappa'][1]:.3f}; "
              f"accuracy {bk['accuracy'][0]:.3f} +/- {bk['accuracy'][1]:.3f}; "
              f"minority recall {bk['minority_recall'][0]:.3f} +/- {bk['minority_recall'][1]:.3f}",
              "- Time-agnostic, so it leaks adjacent bars and overstates the edge; it brackets "
              "the temporal number from above and is never the basis for GO/NO-GO.\n"]
    open(path, "w").write("\n".join(L) + "\n")
    return path


# --------------------------------------------------------------- CLI driver
def main():
    p = argparse.ArgumentParser(description="Post-split proportionality / drift audit (1h frame)")
    p.add_argument("--dataset", default=None, help="dataset path (default: build_dataset_1h.DATASET_PATH)")
    p.add_argument("--sample", type=int, default=0, help="row cap for the imbalance models (0 = all)")
    p.add_argument("--no-imbalance", action="store_true", help="skip the imbalance comparison")
    p.add_argument("--no-bracket", action="store_true", help="skip the stratified-random bracket")
    p.add_argument("--no-perm", action="store_true", help="skip permutation importance")
    p.add_argument("--out", default=None, help="AA-evals dir (default: outputs/AA-evals)")
    a = p.parse_args()

    import build_dataset_1h as bd
    import train_model_1h as t1
    df = t1.load(a.dataset or bd.DATASET_PATH)
    feat = bd.feature_columns(df)
    train, test, cut = t1.split(df)
    embargo_bars = int(bd.LABEL["horizon_bars"])
    print(f"audit: train {len(train):,} / test {len(test):,} rows, {len(feat)} features, "
          f"cut {pd.Timestamp(cut).date()}, embargo {t1.EMBARGO_DAYS}d")

    table, parts, verdict = audit_split(train, test, feat, embargo_days=t1.EMBARGO_DAYS)
    print(f"\nDATA-READINESS: {verdict['status']}")
    for r in verdict["reasons"]:
        print("  -", r)

    # lead with panel / coin composition: the dimension that bites first here
    panel = parts["panel"]; onesided = panel[panel["flag"]]
    print("\nPANEL/COIN COMPOSITION (leads):")
    print(f"  coins train {(panel['n_train'] > 0).sum()} / test {(panel['n_test'] > 0).sum()}, "
          f"one-sided {len(onesided)}, coin base-rate drift {verdict['n_coin_base_drift']}")
    dom = panel.sort_values("train_share", ascending=False).head(8)
    print("  dominant by train share: "
          + ", ".join(f"{r.symbol} {r.train_share:.3f}" for r in dom.itertuples()))
    print("\n" + (table.to_string(index=False) if len(table) else "(no table rows)"))

    imb = best = bracket = perm = None
    samp = a.sample or None
    if not a.no_imbalance:
        print("\nimbalance comparison (natural vs class_weight, embargoed TS-CV)...")
        imb, best = imbalance_comparison(train, feat, embargo_bars=embargo_bars, sample=samp)
        print(_fmt_imb(imb, best))
        if not a.no_perm:
            perm = permutation_importance_train(train, feat, class_weight=(None if best == "natural" else "balanced"),
                                                sample=samp)
    if not a.no_bracket:
        print("\nstratified-random holdout bracket (optimistic, not the headline)...")
        bracket = stratified_holdout_bracket(df, feat, sample=samp)
        print(f"  Kappa {bracket['kappa'][0]:.3f} +/- {bracket['kappa'][1]:.3f}")

    lm = (f"Label: +{bd.LABEL['tgt_atr']}/-{bd.LABEL['stp_atr']} ATR within "
          f"{bd.LABEL['horizon_bars']} bars; base rate {df[LABEL_COL].mean():.3f}.")
    path = write_report(table, parts, verdict, imb, best, bracket, perm,
                        out_dir=a.out, label_meta=lm)
    print("\nreport:", path)


if __name__ == "__main__":
    main()
