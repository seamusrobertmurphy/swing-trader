"""Falsification harness for the one positive OOS cell: f_mst_dir under btc+breadth.

The cell (2026-08-17, records edge-matrix-1d-swept-label / microstructure-1d)
clears zero only on the blind year, loses in training, rests on ~15 trades, and
moved from +1.37 to +0.04%/trade when the OOS cut shifted two weeks. That is
the profile of a regime artifact (see the June entry-earliness kill), so this
harness is built to make it fail fast. Only survival earns further work.

Kill criteria, fixed BEFORE the run:
  K1  fewer than 60% of eligible gate-open half-year folds positive (eligible =
      at least MIN_FOLD_TRADES top-cohort rows while the gate is open), or
  K2  no tradeable gate width (open on >= 10% of bars) shows a positive
      all-history gate-on top-third after cost.

Panels:
  A  half-year walk-forward: per-fold gate-on top-third net %/trade, all history.
  B  gate-width sensitivity: breadth threshold x {btc-up, no-btc}, open rate vs
     all-history and OOS-year net.
  C  per-coin attribution of the gate-on top cohort (concentration check).

Per-trade means over a multi-bar horizon overlap and are autocorrelated; the
half-year folds are the honesty device. Long-only, after-fee, no orders.

    .venv/bin/python inputs/mst_gate_walkforward.py --interval 1d
    .venv/bin/python inputs/mst_gate_walkforward.py --interval 4h
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime

import pandas as pd

import build_dataset_1h as bd
import cross_sectional_4h as cs
import cross_sectional_regime as xr
import train_model as tm
import train_model_1h as t1

MIN_FOLD_TRADES = 8
PASS_RATE = 0.60
TRADEABLE_OPEN = 0.10
BREADTH_GRID = (0.3, 0.4, 0.5, 0.6)


def prep(df, sig):
    """Rank the cross-section: per-bar top-third membership at the 5-coin floor."""
    d = df[[sig, "symbol", "datetime", "trade_ret"]].dropna().copy()
    cnt = d.groupby("datetime")[sig].transform("size")
    d = d[cnt >= cs.MIN_COINS]
    pct = d.groupby("datetime")[sig].rank(pct=True, method="average")
    d["top"] = pct > (1 - cs.TOP_FRAC)
    return d


def breadth_series(df, bcol):
    return (df[bcol] > 0).groupby(df["datetime"]).transform("mean")


def fold_table(d, gate, cost):
    d = d.assign(gate=gate.reindex(d.index))
    d["fold"] = d["datetime"].dt.year.astype(str) + d["datetime"].dt.month.map(
        lambda m: "H1" if m <= 6 else "H2")
    rows = []
    for fold, sub in d.groupby("fold", sort=True):
        on_top = sub[sub["gate"] & sub["top"]]
        rows.append(dict(
            fold=fold, open_rate=round(float(sub["gate"].mean()), 2),
            n_top=len(on_top),
            net=round((on_top["trade_ret"].mean() - cost) * 100, 3) if len(on_top) else float("nan"),
            mkt=round((sub.loc[sub["gate"], "trade_ret"].mean() - cost) * 100, 3)
                if sub["gate"].any() else float("nan"),
        ))
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", default="1d")
    ap.add_argument("--signal", default="f_mst_dir")
    ap.add_argument("--cost", type=float, default=tm.ACHIEVABLE_COST_PCT)
    a = ap.parse_args()
    cost = a.cost / 100.0

    bd.configure(a.interval)
    frame_hours = bd._FRAME_MIN[bd.INTERVAL] / 60.0
    path = os.path.join(bd.BINANCE_DATA, f"dataset_{a.interval}_allmarket.parquet")
    print(f"loading {os.path.basename(path)} ...", flush=True)
    df = t1.load(path)
    regime_col = xr.pick_regime_col(df, frame_hours)
    bcol = next(c for c in xr.BREADTH_CANDIDATES if c in df.columns)
    _, _, cut = t1.split(df)
    print(f"frame={a.interval}  signal={a.signal}  cost={a.cost}%  btc col={regime_col}  "
          f"breadth col={bcol}  OOS cut={cut}", flush=True)

    d = prep(df, a.signal)
    btc_up = df[regime_col] > 0
    breadth = breadth_series(df, bcol)

    # -- Panel A: half-year walk-forward at the incumbent gate (btc AND breadth>0.5)
    gate = btc_up & (breadth > 0.5)
    folds = fold_table(d, gate, cost)
    eligible = folds[folds["n_top"] >= MIN_FOLD_TRADES]
    pos = int((eligible["net"] > 0).sum())
    rate = pos / len(eligible) if len(eligible) else float("nan")
    print("\nPANEL A  half-year walk-forward, gate = btc-up AND breadth>0.5")
    print(folds.to_string(index=False))
    print(f"eligible folds (n_top>={MIN_FOLD_TRADES}): {len(eligible)}  positive: {pos}  "
          f"pass rate: {rate:.0%}  (K1 kills below {PASS_RATE:.0%})")

    # -- Panel B: gate-width sensitivity
    print("\nPANEL B  gate width vs edge (all-history and OOS-year gate-on top-third net %/trade)")
    rows = []
    oos = d["datetime"] >= cut
    for use_btc in (True, False):
        for bmin in BREADTH_GRID:
            g = (btc_up if use_btc else pd.Series(True, index=df.index)) & (breadth > bmin)
            dg = d.assign(gate=g.reindex(d.index))
            on_top = dg[dg["gate"] & dg["top"]]
            on_top_oos = on_top[on_top["datetime"] >= cut]
            rows.append(dict(
                btc="on" if use_btc else "off", breadth_min=bmin,
                open_rate=round(float(dg["gate"].mean()), 2),
                n_top=len(on_top),
                net_all=round((on_top["trade_ret"].mean() - cost) * 100, 3) if len(on_top) else float("nan"),
                n_oos=len(on_top_oos),
                net_oos=round((on_top_oos["trade_ret"].mean() - cost) * 100, 3) if len(on_top_oos) else float("nan"),
            ))
    widths = pd.DataFrame(rows)
    print(widths.to_string(index=False))
    tradeable = widths[widths["open_rate"] >= TRADEABLE_OPEN]
    k2_survives = bool((tradeable["net_all"] > 0).any())
    print(f"tradeable widths (open>={TRADEABLE_OPEN:.0%}): {len(tradeable)}  "
          f"with positive all-history edge: {int((tradeable['net_all'] > 0).sum())}  "
          f"(K2 kills at zero)")

    # -- Panel C: attribution of the incumbent gate's top cohort
    dg = d.assign(gate=gate.reindex(d.index))
    on_top = dg[dg["gate"] & dg["top"]].copy()
    on_top["net"] = on_top["trade_ret"] - cost
    g3 = on_top.groupby("symbol")["net"].agg(["size", "mean", "sum"])
    g3.columns = ["n", "mean_net", "total_net"]
    g3 = (g3 * pd.Series({"n": 1, "mean_net": 100, "total_net": 100})).round(3)
    g3 = g3.sort_values("total_net", ascending=False)
    n_pos = int((g3["total_net"] > 0).sum())
    top5 = float(g3["total_net"].head(5).sum())
    total = float(g3["total_net"].sum())
    print(f"\nPANEL C  attribution, incumbent gate, all history: {len(g3)} coins, "
          f"{n_pos} positive; top-5 carry {top5:+.1f}pp of {total:+.1f}pp")
    print(g3.head(8).to_string())

    # -- Verdict
    k1_survives = (len(eligible) > 0) and (rate >= PASS_RATE)
    print("\n" + "=" * 90)
    if k1_survives and k2_survives:
        print(f"VERDICT: SURVIVES both kill criteria on {a.interval} "
              f"(fold pass {rate:.0%}, tradeable-width edge exists). Earned the next test.")
    else:
        why = []
        if not k1_survives:
            why.append(f"K1: fold pass rate {rate:.0%} < {PASS_RATE:.0%}" if len(eligible)
                       else "K1: no eligible folds")
        if not k2_survives:
            why.append("K2: no tradeable gate width with positive all-history edge")
        print(f"VERDICT: KILLED on {a.interval} ({'; '.join(why)}). Journal as a closed artifact.")
    print("=" * 90)


if __name__ == "__main__":
    main()
