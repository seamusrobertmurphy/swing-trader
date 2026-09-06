"""Hyperparameter sweep for the trend-life target, with a before and after.

WHY THIS EXISTS. Settings were being chosen by hand and never compared, so when
a number moved nobody could say whether the tuning caused it or whether it would
have moved anyway. This runs every combination through the same walk-forward
folds, scores each one the same way, and marks the settings the baseline started
from so every other row reads as better or worse than the incumbent.

WHAT IT MEASURES PER TRIAL. Both errors, not one. The training RMSE says how well
those settings fit data they were shown. The cross-validated RMSE says how well
they did on the stretch of time after it. A trial can improve the first while
wrecking the second, which is what overfitting looks like from the inside, and a
sweep that only records the second cannot show you that happening.

Each fold is fitted once and predicted twice, on its own training slice and on
the block after it, so both numbers cost one fit rather than two.

HONEST LIMIT. Tuning is scored on the training window only. The blind final
stretch is never touched here, because a setting chosen by looking at the blind
data is no longer blind and the number it produces is not evidence.

    .venv/bin/python inputs/trend_life_tune.py --frame 4h --coins 40 --folds 3
"""
from __future__ import annotations

import argparse
import itertools
import sys
import time

import numpy as np

import model_metrics as mm
from trend_life_baseline import PANELS, load

# The settings trend_life_baseline.py runs with. Present in the grid below, so
# the sweep always contains its own incumbent and the comparison is like for
# like rather than against a remembered number.
BASELINE = dict(learning_rate=0.06, max_depth=6, max_iter=300, min_samples_leaf=100)

GRID = dict(
    learning_rate=[0.03, 0.06, 0.12],
    max_depth=[4, 6, 10],
    max_iter=[300],
    min_samples_leaf=[100],
)


def combos(grid: dict) -> list:
    keys = list(grid)
    return [dict(zip(keys, v)) for v in itertools.product(*[grid[k] for k in keys])]


def score_params(X, y, params: dict, folds: int) -> dict:
    """One settings combination, scored on walk-forward folds.

    Returns the mean training RMSE, the mean held-out RMSE, and the ratio between
    them, which is the overfit test: above 1.1 the settings memorised.
    """
    from sklearn.ensemble import HistGradientBoostingRegressor

    tr_rmse, cv_rmse, cv_mae, cv_mape, per_fold = [], [], [], [], []
    for k, (tr_end, te_s, te_e) in enumerate(mm.walk_forward_folds(len(y), folds), 1):
        m = HistGradientBoostingRegressor(early_stopping=False, random_state=0,
                                          **params).fit(X[:tr_end], y[:tr_end])
        tr_rmse.append(mm.rmse(y[:tr_end], m.predict(X[:tr_end])))
        pte = m.predict(X[te_s:te_e])
        e = mm.errors(y[te_s:te_e], pte)
        cv_rmse.append(e["rmse"]); cv_mae.append(e["mae"])
        if e["mape"] is not None:
            cv_mape.append(e["mape"])
        per_fold.append(dict(fold=k, n=int(te_e - te_s), rmse=e["rmse"]))

    train = float(np.mean(tr_rmse)) if tr_rmse else None
    cv = float(np.mean(cv_rmse)) if cv_rmse else None
    ratio = (cv / train) if (train and cv) else float("nan")
    return dict(
        params=params,
        train_rmse=train, cv_rmse=cv,
        cv_mae=float(np.mean(cv_mae)) if cv_mae else None,
        cv_mape=float(np.mean(cv_mape)) if len(cv_mape) == len(cv_rmse) else None,
        ratio=ratio,
        overfit=bool(np.isfinite(ratio) and ratio > mm.RMSE_RATIO_REJECT),
        is_baseline=all(params.get(k) == v for k, v in BASELINE.items()),
        folds=per_fold,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame", default="4h", choices=sorted(PANELS))
    ap.add_argument("--coins", type=int, default=40)
    ap.add_argument("--folds", type=int, default=3)
    ap.add_argument("--rows", type=int, default=250_000)
    a = ap.parse_args()

    path, label = PANELS[a.frame]
    t0 = time.time()
    df, feat = load(path, a.coins)
    if len(df) > a.rows:
        df = df.iloc[-a.rows:].reset_index(drop=True)
    X = df[feat].to_numpy(np.float32)
    y = df["y"].to_numpy(np.float32)

    trials_in = combos(GRID)
    print(f"panel {label}: {len(df):,} rows, {df.symbol.nunique()} coins, {len(feat)} features")
    print(f"sweep: {len(trials_in)} settings x {a.folds} folds = "
          f"{len(trials_in) * a.folds} fits\n")

    trials = []
    for i, p in enumerate(trials_in, 1):
        t = score_params(X, y, p, a.folds)
        trials.append(t)
        tag = "  <- the settings we already use" if t["is_baseline"] else ""
        print(f"  {i:2d}/{len(trials_in)}  lr={p['learning_rate']:<5} depth={p['max_depth']:<3} "
              f"train RMSE {t['train_rmse']:6.3f}  CV RMSE {t['cv_rmse']:6.3f}  "
              f"ratio {t['ratio']:.3f}{tag}")

    ranked = sorted(trials, key=lambda t: t["cv_rmse"])
    best = ranked[0]
    base = next((t for t in trials if t["is_baseline"]), None)

    rec = mm.write_tuning_record(
        trials, frame=a.frame,
        target="bars until the Supertrend flips",
        target_kind="regression",
        panel=f"{label}, {df.symbol.nunique()} coins, {len(df):,} rows",
        baseline=BASELINE,
        note=f"{len(trials)} settings, {a.folds} walk-forward folds each. "
             "Scored on the training window only; the blind stretch is untouched.")

    print(f"\nbest by held-out RMSE: lr={best['params']['learning_rate']} "
          f"depth={best['params']['max_depth']}  CV RMSE {best['cv_rmse']:.3f}  "
          f"ratio {best['ratio']:.3f}"
          f"{'  (still rejected as overfit)' if best['overfit'] else ''}")
    if base:
        d = base["cv_rmse"] - best["cv_rmse"]
        pct = 100 * d / base["cv_rmse"]
        verdict = ("tuning HELPED" if d > 0 else
                   "tuning did NOT help; the settings we already use are best")
        print(f"settings we already use: CV RMSE {base['cv_rmse']:.3f}, "
              f"ratio {base['ratio']:.3f}")
        print(f"{verdict}: {abs(d):.3f} bars, {abs(pct):.1f} per cent")
    print(f"\nrecord: {rec}   [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    sys.exit(main())
