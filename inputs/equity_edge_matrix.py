"""Track A Phase A4: the equity cross-sectional edge matrix.

The crypto edge matrix re-asked for equities, with the three things that change:

  universe depth   hundreds of names per bar, so the long cohort is the top
                   DECILE at a 50-name floor, not crypto's tercile at 5.
  cost             commission-free venue; the round trip is spreads plus
                   slippage plus the sell-side SEC/TAF fees. Default 0.05%
                   (conservative for the 20M-dollar-volume screen), with a
                   0.10% stress column so the verdict never rests on the
                   optimistic number.
  gate             SPY standing in the market seat: deploy only when SPY
                   momentum is positive (the f_btc_mom_* columns ARE SPY here,
                   see build_dataset_equity), optionally AND cross-sectional
                   breadth above half.

Survivorship caveat inherited: live names only, every number an upper bound.
Verdicts follow the same discipline: a positive OOS cell is only a candidate
for the walk-forward kill harness, never a GO by itself.

    .venv/bin/python inputs/equity_edge_matrix.py [--gate spy+breadth] [--cost 0.05]
"""
from __future__ import annotations

import argparse
import os

import pandas as pd

import cross_sectional_4h as cs
import train_model_1h as t1
from build_dataset_equity import DATASET, ROOT

TOP_FRAC = 0.10
MIN_NAMES = 50
REGIME_COL_TARGET_BARS = 24        # ~28 wall-clock days of trading bars
BREADTH_COL = "f_w1_st_up"


def build_gate(df, kind, regime_col):
    if kind == "none":
        return pd.Series(True, index=df.index)
    parts = []
    if "spy" in kind:
        parts.append(df[regime_col] > 0)
    if "breadth" in kind:
        breadth = (df[BREADTH_COL] > 0).groupby(df["datetime"]).transform("mean")
        parts.append(breadth > 0.5)
    gate = parts[0]
    for p in parts[1:]:
        gate = gate & p
    return gate


def gated_edge(frame, sig, gate, cost):
    d = frame[[sig, "datetime", "trade_ret"]].assign(gate=gate.loc[frame.index]).dropna()
    cnt = d.groupby("datetime")[sig].transform("size")
    d = d[cnt >= MIN_NAMES]
    if d.empty:
        return None
    pct = d.groupby("datetime")[sig].rank(pct=True, method="average")
    d = d.assign(top=pct > (1 - TOP_FRAC))
    out = {}
    for reg, mask in (("on", d["gate"]), ("off", ~d["gate"])):
        sub = d[mask]
        topsub = sub[sub["top"]]
        out[reg] = dict(
            mkt=round((sub["trade_ret"].mean() - cost) * 100, 3) if len(sub) else float("nan"),
            top=round((topsub["trade_ret"].mean() - cost) * 100, 3) if len(topsub) else float("nan"),
            n_top=len(topsub))
    out["gate_open"] = round(float(d["gate"].mean()), 2)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", default="spy+breadth",
                    choices=["spy", "breadth", "spy+breadth", "none"])
    ap.add_argument("--cost", type=float, default=0.05, help="round trip in %%")
    ap.add_argument("--signals", nargs="+", default=None)
    args = ap.parse_args()
    cost = args.cost / 100.0

    print(f"loading {os.path.basename(DATASET)} ...", flush=True)
    df = t1.load(DATASET)
    feat = [c for c in df.columns if c.startswith("f_")]
    moms = [c for c in df.columns if c.startswith("f_btc_mom_")]
    regime_col = min(moms, key=lambda c: abs(int(c.rsplit("_", 1)[1]) - REGIME_COL_TARGET_BARS))
    sigs = args.signals or cs.candidate_signals(df, feat)
    gate = build_gate(df, args.gate, regime_col)
    train, test, cut = t1.split(df)
    print(f"equities 1d  OOS cut={cut}  gate={args.gate} (SPY col {regime_col})  "
          f"cost={args.cost}%  top {TOP_FRAC:.0%} at {MIN_NAMES}-name floor  "
          f"candidates={len(sigs)}\n", flush=True)

    rows = []
    for sig in sigs:
        if sig == regime_col or sig not in df.columns:
            continue
        tr = gated_edge(train, sig, gate, cost)
        te = gated_edge(test, sig, gate, cost)
        if tr is None or te is None:
            continue
        rows.append(dict(signal=sig, gate_open=te["gate_open"],
                         tr_on_top=tr["on"]["top"], tr_on_mkt=tr["on"]["mkt"],
                         te_on_top=te["on"]["top"], te_on_mkt=te["on"]["mkt"],
                         te_on_n=te["on"]["n_top"], te_off_top=te["off"]["top"]))
    board = pd.DataFrame(rows)
    pd.set_option("display.width", 220, "display.max_columns", 30)
    print("=" * 108)
    print(f"EQUITY CROSS-SECTIONAL EDGE, 1d, gate={args.gate}, after {args.cost:.2f}% cost. "
          f"Deciding cell: te_on_top.")
    print("=" * 108)
    if board.empty:
        print("no usable signal.")
        return
    board = board.sort_values("te_on_top", ascending=False).reset_index(drop=True)
    print(board.head(20).to_string(index=False))
    b = board.iloc[0]
    print("\n" + "=" * 108)
    print(f"BEST: {b['signal']}  gate open {b['gate_open']:.0%}")
    print(f"  TEST  gate-on : top-decile {b['te_on_top']:+.3f}%/trade  (gated market {b['te_on_mkt']:+.3f}%)")
    print(f"  TRAIN gate-on : top-decile {b['tr_on_top']:+.3f}%/trade")
    print("=" * 108)
    clears, stable = b["te_on_top"] > 0, (b["tr_on_top"] > 0) == (b["te_on_top"] > 0)
    if clears and stable:
        print("  => CANDIDATE: clears after cost, train/test consistent. Next: the walk-forward")
        print("     kill harness (60% fold pass, tradeable width, attribution breadth).")
    elif clears:
        print("  => FRAGILE: clears on TEST only; treat as unproven.")
    else:
        print("  => NOT CLEARED at this gate/cost.")
    return board


if __name__ == "__main__":
    main()
