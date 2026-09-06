"""Stability test for the early bullish-trend entry: does its edge hold across periods, or was
the one OOS-positive year just a Bitcoin bull leg? (4h frame, half-year folds.)

The earliness test (entry_earliness_4h.py) found the EARLY entry (BTC-trend-up + coin-momentum,
first confluence bar, ~5 bars / 20h before the Supertrend flip) is the only cohort with a
positive after-fee edge on the final OOS year (+0.006%/trade) -- but it is NEGATIVE in-sample,
the signature of a regime artifact rather than a durable edge. The deciding question, per the
honesty mandate: is the edge present in MOST half-year periods, or only when Bitcoin itself was
trending?

This slices the whole 4h panel into calendar half-years and, per fold, reports the after-fee
edge of EARLY vs LATE vs unconditional, the trade count, and BTC's own trend state (share of
bars with f_btc_mom_168 > 0). A durable edge shows EARLY > 0 and EARLY > LATE across many folds
and across both BTC-up and BTC-down regimes. An artifact shows EARLY positive only where the
BTC-up share is high. Honest, after-fee. No orders. Plain ASCII.
"""
from __future__ import annotations
import os
import pandas as pd

import build_dataset_1h as bd
import train_model_1h as t1
import train_model as tm
import entry_earliness_4h as ee          # reuse build_signals / cost

COST = tm.COST_PCT / 100.0
MIN_N = 40                                # min trades in a fold for its edge to be readable


def edge(d):
    return (d["trade_ret"].mean() - COST) * 100 if len(d) else float("nan")


def main():
    bd.configure(4)
    path = os.path.join(bd.BINANCE_DATA, "dataset_4h_allmarket.parquet")
    print(f"loading {os.path.basename(path)} ...", flush=True)
    df = t1.load(path)
    df = ee.build_signals(df)
    df = df.dropna(subset=["trade_ret", "label"])
    btc_up = (df["f_btc_mom_168"] if "f_btc_mom_168" in df else df["f_btc_mom_6"]) > 0
    df["_btc_up"] = btc_up.values

    # half-year fold label, e.g. 2023H1
    dt = df["datetime"].dt
    df["fold"] = dt.year.astype(str) + "H" + ((dt.month > 6).astype(int) + 1).astype(str)

    rows = []
    for fold, g in df.groupby("fold"):
        e_all = edge(g)
        late = g[g["sig_late"]]; early = g[g["sig_early"]]; ek = g[g["sig_early_ker"]]
        rows.append(dict(
            fold=fold, bars=len(g), btc_up_share=round(float(g["_btc_up"].mean()), 2),
            uncond=round(e_all, 3),
            late_n=len(late), late_edge=round(edge(late), 3),
            early_n=len(early), early_edge=round(edge(early), 3),
            ek_n=len(ek), ek_edge=round(edge(ek), 3),
        ))
    board = pd.DataFrame(rows).sort_values("fold").reset_index(drop=True)
    pd.set_option("display.width", 200, "display.max_columns", 30)
    print("\n" + "=" * 92)
    print("PER-FOLD after-fee edge (%%/trade). edge cells with n<%d are noise; read with btc_up_share."
          % MIN_N)
    print("=" * 92)
    print(board.to_string(index=False))

    # verdict: among readable folds, how often EARLY is positive and beats LATE, split by BTC regime
    rd = board[board["early_n"] >= MIN_N].copy()
    pos = (rd["early_edge"] > 0).mean()
    beat = (rd["early_edge"] > rd["late_edge"]).mean()
    btc_up_folds = rd[rd["btc_up_share"] >= 0.5]
    btc_dn_folds = rd[rd["btc_up_share"] < 0.5]
    print("\n" + "=" * 92)
    print("STABILITY VERDICT (readable folds, early_n >= %d: %d folds)" % (MIN_N, len(rd)))
    print("=" * 92)
    print(f"  EARLY edge > 0           in {pos:.0%} of folds")
    print(f"  EARLY edge > LATE edge   in {beat:.0%} of folds")
    if len(btc_up_folds):
        print(f"  EARLY edge > 0 | BTC-up folds   ({len(btc_up_folds)}): "
              f"{(btc_up_folds['early_edge'] > 0).mean():.0%}  "
              f"(mean edge {btc_up_folds['early_edge'].mean():+.3f}%)")
    if len(btc_dn_folds):
        print(f"  EARLY edge > 0 | BTC-down folds ({len(btc_dn_folds)}): "
              f"{(btc_dn_folds['early_edge'] > 0).mean():.0%}  "
              f"(mean edge {btc_dn_folds['early_edge'].mean():+.3f}%)")
    durable = pos >= 0.6 and beat >= 0.6 and (len(btc_dn_folds) == 0 or
              (btc_dn_folds["early_edge"] > 0).mean() >= 0.5)
    print("\n  => " + ("DURABLE: EARLY edge holds across folds and BTC regimes -- worth wiring "
          "into the bot's entry." if durable else
          "NOT DURABLE: EARLY's positive edge is concentrated (likely BTC-up regime), not a "
          "stand-alone entry edge. Keep the BTC-trend gate as a REGIME FILTER, not a signal."))
    return board


if __name__ == "__main__":
    main()
