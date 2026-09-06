"""The number the sequence model has to beat: how long does this trend have left?

WHAT IT PREDICTS. For every bar, how many bars until the Supertrend line flips
to the other side. A long answer means a trend worth riding. A short answer
means chop, which is where Supertrend loses money, because a market that saws
across its line keeps firing entries and every entry pays a fee.

The target is counted straight off history with no judgement call: walk forward
from each bar until f_st_uptrend changes value, and count. Bars whose flip never
arrives inside the panel are dropped rather than guessed, so no row is scored
against a number nobody knows.

WHY A TREE MODEL FIRST. This is the baseline, not the answer. It sees one bar at
a time and has no memory of the shape of the last few days, which is exactly the
thing an LSTM or a GRU is supposed to add. If the sequence model cannot beat
these numbers on the same folds and the same target, the sequence structure was
not what was missing and we have saved ourselves the training time.

    .venv/bin/python inputs/trend_life_baseline.py --frame 4h --coins 60
"""
from __future__ import annotations

import argparse
import sys
import time

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

import model_metrics as mm

PANELS = {
    "4h": ("03-inputs/binance-data/dataset_4h_allmarket.parquet", "crypto 4h"),
    "1d": ("03-inputs/binance-data/dataset_1d_allmarket.parquet", "crypto daily"),
    "eq1d": ("03-inputs/alpaca-data/dataset_eq1d_allmarket.parquet", "US equities daily"),
}

# Beyond this the answer stops being useful: "the trend lasts longer than a
# fortnight" and "longer than a year" lead to the same decision, and the long
# tail would otherwise dominate a squared error.
MAX_HORIZON = 120


def bars_to_flip(uptrend: np.ndarray) -> np.ndarray:
    """Count forward from each bar to the next change in trend direction.

    Vectorised: find every bar where the direction changes, then for each row ask
    which flip is the next one along. A row-by-row version of this took minutes
    per coin on a panel of four million bars; this takes milliseconds.

    Rows with no flip ahead of them get NaN, because the answer is not in the
    data and guessing it would be inventing the label.
    """
    u = np.asarray(uptrend, float).ravel()
    n = u.size
    if n < 2:
        return np.full(n, np.nan)
    flips = np.flatnonzero(u[1:] != u[:-1]) + 1        # indices where it changed
    if flips.size == 0:
        return np.full(n, np.nan)
    idx = np.arange(n)
    pos = np.searchsorted(flips, idx, side="right")    # first flip strictly after i
    out = np.full(n, np.nan)
    inside = pos < flips.size
    out[inside] = flips[pos[inside]] - idx[inside]
    return out


def load(panel_path: str, coins: int, feats_max: int | None = None):
    """Read the panel one symbol group at a time, keeping memory flat.

    The 4h panel is 1.9 GB on disk and this machine has 8 GB shared with the
    graphics chip, so the whole thing is never held at once.
    """
    pf = pq.ParquetFile(panel_path)
    names = pf.schema_arrow.names
    feat = [c for c in names if c.startswith("f_")]
    if feats_max:
        feat = feat[:feats_max]
    # f_st_uptrend is itself an f_ column, so a plain concatenation asks parquet
    # for it twice and every later lookup returns a two-column frame.
    keep = list(dict.fromkeys(["symbol", "datetime", "f_st_uptrend"] + feat))

    df = pq.read_table(panel_path, columns=keep).to_pandas()
    counts = df.groupby("symbol").size().sort_values(ascending=False)
    chosen = list(counts.index[:coins])
    df = df[df["symbol"].isin(chosen)].sort_values(["symbol", "datetime"])

    parts = []
    for _sym, g in df.groupby("symbol", sort=False):
        g = g.copy()
        g["y"] = bars_to_flip(g["f_st_uptrend"].to_numpy())
        parts.append(g)
    out = pd.concat(parts, ignore_index=True)
    out = out[out["y"].notna() & (out["y"] <= MAX_HORIZON)]
    out = out.sort_values("datetime").reset_index(drop=True)
    return out, feat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame", default="4h", choices=sorted(PANELS))
    ap.add_argument("--coins", type=int, default=60)
    ap.add_argument("--splits", type=int, default=5)
    ap.add_argument("--rows", type=int, default=400_000,
                    help="cap on training rows; the M1 has 8 GB shared with its GPU")
    a = ap.parse_args()

    path, label = PANELS[a.frame]
    t0 = time.time()
    df, feat = load(path, a.coins)
    if len(df) > a.rows:
        df = df.iloc[-a.rows:].reset_index(drop=True)   # keep the most recent window
    print(f"panel {label}: {len(df):,} rows, {df.symbol.nunique()} coins, {len(feat)} features")
    print(f"target: bars until the Supertrend flips. "
          f"median {df.y.median():.0f}, mean {df.y.mean():.1f}, "
          f"range {df.y.min():.0f} to {df.y.max():.0f}")

    X = df[feat].to_numpy(np.float32)
    y = df["y"].to_numpy(np.float32)

    from sklearn.ensemble import HistGradientBoostingRegressor

    def fresh():
        return HistGradientBoostingRegressor(
            max_iter=300, learning_rate=0.06, max_depth=6,
            min_samples_leaf=100, early_stopping=False, random_state=0)

    # In-sample fit: what the model can memorise.
    full = fresh().fit(X, y)
    p_full = full.predict(X)

    # Walk-forward folds: what it manages on bars it has not seen.
    folds = []
    for k, (tr_end, te_s, te_e) in enumerate(mm.walk_forward_folds(len(df), a.splits), 1):
        m = fresh().fit(X[:tr_end], y[:tr_end])
        pf_ = m.predict(X[te_s:te_e])
        folds.append((y[te_s:te_e], pf_))
        print(f"  fold {k}: trained on {tr_end:,}, scored {te_e - te_s:,}, "
              f"RMSE {mm.rmse(y[te_s:te_e], pf_):.2f}")

    scored = mm.score_run(y, p_full, folds)

    # The reference every error is read against: predicting the training mean
    # for every single bar. A model that cannot beat this has learned nothing.
    naive_p = np.full(len(y), float(np.mean(y)))
    naive = mm.errors(y, naive_p)

    row = dict(model="HistGradientBoosting (baseline, one bar at a time)",
               params=dict(max_iter=300, learning_rate=0.06, max_depth=6,
                           min_samples_leaf=100),
               **scored)
    naive_row = dict(model="Always guess the average", params={},
                     train=naive, cv=naive, folds=[], rmse_ratio=1.0,
                     overfit=False, reject_above=mm.RMSE_RATIO_REJECT)

    rec = mm.write_record([row, naive_row], frame=a.frame,
                          target="bars until the Supertrend flips",
                          target_kind="regression",
                          panel=f"{label}, {df.symbol.nunique()} coins, {len(df):,} rows",
                          note="Tree baseline for the sequence models to beat. "
                               "One bar at a time, no memory of recent shape.")

    print(f"\n  train  RMSE {scored['train']['rmse']:.3f}  MAE {scored['train']['mae']:.3f}  "
          f"MAPE {scored['train']['mape']:.1f}%")
    print(f"  CV     RMSE {scored['cv']['rmse']:.3f}  MAE {scored['cv']['mae']:.3f}  "
          f"MAPE {scored['cv']['mape']:.1f}%")
    print(f"  ratio  {scored['rmse_ratio']:.3f}  "
          f"({'REJECTED, overfit' if scored['overfit'] else 'stable'}, "
          f"reject above {mm.RMSE_RATIO_REJECT})")
    print(f"  naive  RMSE {naive['rmse']:.3f}  MAE {naive['mae']:.3f}  "
          f"MAPE {naive['mape']:.1f}%   (always guess the average)")
    print(f"\nrecord: {rec}   [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    sys.exit(main())
