"""Which inputs carry signal, and which are dead weight.

WHY THIS EXISTS. The repository had feature-importance charts and no feature
table. A picture cannot be quoted, compared between frames or checked a month
later, so every statement about which inputs help rested on reading a bar off a
PNG. This computes the numbers and persists them.

WHAT IT MEASURES, three things, because no single one is trustworthy alone.

  alone       Each feature on its own, scored by AUC against the label. AUC is
              the chance that a randomly chosen winning bar was ranked above a
              randomly chosen losing one, so 0.50 is a coin flip and the
              direction does not matter: 0.42 is as informative as 0.58, just
              inverted. Reported as |AUC - 0.50|, the distance from useless.
  stable      The same score computed inside each walk-forward fold. A feature
              that helps in one stretch of market and hurts in the next is not
              a feature, it is a regime. Reported as the share of folds landing
              on the same side of 0.50 as the whole-window score.
  in company  Permutation importance from one gradient booster: shuffle the
              column, see how much the model's Brier score worsens. This catches
              a feature that is useless alone and valuable alongside others, and
              it also exposes the opposite, a feature that duplicates one the
              model already has.

EVERYTHING IS COMPUTED ON THE TRAINING WINDOW ONLY. The blind final year is
never opened here. A feature chosen by looking at the blind year has spent it.

    .venv/bin/python 03-inputs/feature_report.py --frames 4h 1d --rows 120000
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from collections import defaultdict
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_dataset_1h as bd          # noqa: E402
import model_metrics as mm             # noqa: E402
import train_model_1h as t1            # noqa: E402

# What each prefix is, in words, so the record does not make the reader decode it.
FAMILIES = {
    "f_wc_":   "the coin's own price over day-length windows",
    "f_hr_":   "the coin's own price over intraday windows",
    "f_ta_pta_": "pandas-ta indicators",
    "f_ta_":   "in-house indicators (Williams %R, stochastic, CCI, money flow, ADX, Aroon)",
    "f_tl_":   "TA-Lib extras (parabolic SAR, MESA, Hilbert cycle, candle patterns)",
    "f_st_":   "triple Supertrend",
    "f_mst_":  "adaptive Supertrend with the efficiency gate",
    "f_btc_":  "strength relative to the market (bitcoin, or SPY on shares)",
    "f_4h_":   "the four-hour picture",
    "f_h1_":   "the one-hour picture",
    "f_d1_":   "the daily picture",
    "f_w1_":   "the weekly picture",
    "f_rg_":   "regime state (volatility, drift, breadth)",
    "f_flow_": "buy and sell order flow",
    "f_ms_":   "microstructure",
}


def family_of(col: str) -> str:
    for p in sorted(FAMILIES, key=len, reverse=True):
        if col.startswith(p):
            return p
    return "other"


def single_auc(x: pd.Series, y: pd.Series) -> float:
    """AUC of one column. NaN where the column is constant or all-missing."""
    ok = x.notna()
    if ok.sum() < 500:
        return float("nan")
    xs, ys = x[ok], y[ok]
    if xs.nunique() < 2 or ys.nunique() < 2:
        return float("nan")
    return float(roc_auc_score(ys, xs))


def score_frame(frame: str, rows_cap: int, folds: int, perm_repeats: int) -> dict | None:
    bd.configure(frame)
    # configure() retunes bd's globals for the frame, DATASET_PATH among them.
    path = bd.DATASET_PATH if frame != "eq1d" else os.path.join(
        os.path.dirname(bd.BINANCE_DATA), "alpaca-data", "dataset_eq1d_allmarket.parquet")
    if not os.path.exists(path) and not os.path.exists(path.replace(".parquet", ".csv")):
        print(f"[{frame}] no dataset built; skipped")
        return None

    t0 = time.time()
    df = t1.load(path)
    feat = bd.feature_columns(df)
    train, _test, cut = t1.split(df)
    del df
    if rows_cap and len(train) > rows_cap:
        # Most recent rows, so the report describes the market as it is now, and
        # still in time order because the fold split below depends on it.
        train = train.tail(rows_cap)
    train = train.sort_values("datetime")
    y = train["label"].astype(int)
    X = train[feat]
    print(f"[{frame}] {len(train):,} training rows to {cut.date()}, {len(feat)} features, "
          f"base rate {y.mean():.3f}")

    # --- alone, and stable across folds -------------------------------------
    whole = {c: single_auc(X[c], y) for c in feat}
    bounds = np.linspace(0, len(train), folds + 1).astype(int)
    agree = defaultdict(int)
    counted = defaultdict(int)
    for i in range(folds):
        sl = slice(bounds[i], bounds[i + 1])
        yf = y.iloc[sl]
        for c in feat:
            a = single_auc(X[c].iloc[sl], yf)
            w = whole[c]
            if np.isnan(a) or np.isnan(w):
                continue
            counted[c] += 1
            if (a - 0.5) * (w - 0.5) > 0:
                agree[c] += 1

    # --- in company ---------------------------------------------------------
    # One bounded booster. class_weight is deliberately left off here: this asks
    # which columns the model leans on, not how it should be calibrated.
    n_fit = min(len(train), 60_000)
    fit_idx = slice(len(train) - n_fit, len(train))
    pipe = Pipeline([("impute", SimpleImputer(strategy="median")),
                     ("clf", HistGradientBoostingClassifier(
                         max_iter=200, learning_rate=0.06, max_depth=6,
                         min_samples_leaf=100, random_state=0))])
    pipe.fit(X.iloc[fit_idx], y.iloc[fit_idx])
    perm_n = min(20_000, n_fit)
    pi = permutation_importance(
        pipe, X.iloc[fit_idx].tail(perm_n), y.iloc[fit_idx].tail(perm_n),
        n_repeats=perm_repeats, random_state=0, n_jobs=1,
        scoring="neg_brier_score")

    out = pd.DataFrame({
        "feature": feat,
        "family": [family_of(c) for c in feat],
        "auc": [whole[c] for c in feat],
        "alone": [abs(whole[c] - 0.5) if not np.isnan(whole[c]) else np.nan for c in feat],
        "stable": [agree[c] / counted[c] if counted[c] else np.nan for c in feat],
        "in_company": pi.importances_mean,
        "missing_pct": [float(X[c].isna().mean() * 100) for c in feat],
    }).sort_values("in_company", ascending=False).reset_index(drop=True)
    print(f"[{frame}] scored in {time.time()-t0:.0f}s")
    return dict(frame=frame, table=out, rows=len(train), cut=str(cut.date()),
                base=float(y.mean()), n_feat=len(feat))


def write_record(results: list, out_dir: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    day = os.path.join(out_dir, datetime.now().strftime("%Y-%m-%d"))
    os.makedirs(day, exist_ok=True)
    path = os.path.join(day, f"feature-report-{stamp}.md")
    L = [f"# Which inputs carry signal ({datetime.now():%d %B %Y})\n",
         "Computed on the training window of each frame. The blind final year was not opened.\n",
         "Three columns, and none of them is trustworthy alone. **alone** is how far a feature's "
         "own AUC sits from 0.500, a coin flip, so 0.020 means it ranks winners above losers 52 per "
         "cent of the time by itself. **stable** is the share of walk-forward folds in which it "
         "pointed the same way as it did over the whole window, so 0.40 means it changed sides in "
         "three folds out of five and is a regime rather than a feature. **in company** is how much "
         "worse the model's Brier score gets when that one column is shuffled, which catches a "
         "feature that is useless alone and useful beside others, and equally a feature that "
         "duplicates something the model already has.\n"]
    for r in results:
        t = r["table"]
        L.append(f"\n## The {r['frame']} frame\n")
        L.append(f"{r['rows']:,} training rows to {r['cut']}, {r['n_feat']} features, "
                 f"base rate {r['base']:.3f}.\n")

        fam = (t.groupby("family")
                .agg(n=("feature", "size"), alone=("alone", "mean"),
                     stable=("stable", "mean"), in_company=("in_company", "mean"),
                     missing=("missing_pct", "mean"))
                .sort_values("in_company", ascending=False))
        L.append("### By family\n")
        L.append("| family | what it is | inputs | alone | stable | in company | missing % |")
        L.append("| --- | --- | ---: | ---: | ---: | ---: | ---: |")
        for k, row in fam.iterrows():
            L.append(f"| `{k}` | {FAMILIES.get(k, 'unclassified')} | {int(row['n'])} | "
                     f"{row['alone']:.4f} | {row['stable']:.2f} | {row['in_company']:+.5f} | "
                     f"{row['missing']:.1f} |")

        L.append("\n### The ten the model leans on hardest\n")
        L.append("| feature | family | alone | stable | in company |")
        L.append("| --- | --- | ---: | ---: | ---: |")
        for _, row in t.head(10).iterrows():
            L.append(f"| `{row['feature']}` | `{row['family']}` | {row['alone']:.4f} | "
                     f"{row['stable']:.2f} | {row['in_company']:+.5f} |")

        n_zero = int((t["in_company"].abs() < 1e-5).sum())
        L.append("\n### The ten the model does not use\n")
        L.append(f"Shuffling any of these changed the model's score by less than one part in a "
                 f"hundred thousand, so the model is not reading them at all. "
                 f"{n_zero} of {len(t)} features sit in that band.\n")
        L.append("| feature | family | alone | stable | in company |")
        L.append("| --- | --- | ---: | ---: | ---: |")
        for _, row in t.tail(10).iloc[::-1].iterrows():
            L.append(f"| `{row['feature']}` | `{row['family']}` | {row['alone']:.4f} | "
                     f"{row['stable']:.2f} | {row['in_company']:+.5f} |")

        dead = t[(t["stable"] < 0.6) & t["stable"].notna()]
        L.append(f"\n**{len(dead)} of {len(t)} features held their direction in fewer than three "
                 f"folds out of five.** Those are the ones that describe a period rather than a "
                 f"market.\n")
        csv = os.path.join(day, f"feature-report-{r['frame']}-{stamp}.csv")
        t.to_csv(csv, index=False)
        L.append(f"Full table: `{os.path.relpath(csv, mm.REPO)}`\n")

    open(path, "w").write("\n".join(L) + "\n")
    return path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--frames", nargs="+", default=["4h"])
    p.add_argument("--rows", type=int, default=120_000)
    p.add_argument("--folds", type=int, default=5)
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--out", default=str(mm.EVALS))
    a = p.parse_args()

    results = []
    for f in a.frames:
        r = score_frame(f, a.rows, a.folds, a.repeats)
        if r:
            results.append(r)
    if not results:
        raise SystemExit("no frame produced a table")
    print("\nrecord:", write_record(results, a.out))


if __name__ == "__main__":
    main()
