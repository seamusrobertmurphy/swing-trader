"""Track A: the walk-forward kill harness for an equity edge-matrix candidate.

Equities drift upward and this data layer is survivor-biased, so an absolute
after-cost positive is a low bar that market beta plus bias can clear on their
own. Two questions are therefore scored per half-year fold, and BOTH carry the
60% pass bar fixed before the run:

  K1a  absolute: gate-on top-decile net per trade > 0
  K1b  selection: top-decile minus the gated market > 0 (the part beta and
       survivorship cannot fake within a fold)

Plus the attribution breadth check. A candidate that passes K1a but fails K1b
is an index fund with extra steps, not an edge.

    .venv/bin/python inputs/equity_walkforward.py --signal f_hr_ema_fast_mid
"""
from __future__ import annotations

import argparse

import pandas as pd

import train_model_1h as t1
from build_dataset_equity import DATASET
from equity_edge_matrix import MIN_NAMES, TOP_FRAC, REGIME_COL_TARGET_BARS, build_gate

MIN_FOLD_TRADES = 100
PASS_RATE = 0.60


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--signal", default="f_hr_ema_fast_mid")
    ap.add_argument("--gate", default="spy+breadth")
    ap.add_argument("--cost", type=float, default=0.05)
    a = ap.parse_args()
    cost = a.cost / 100.0

    print(f"loading equity dataset ...", flush=True)
    df = t1.load(DATASET)
    moms = [c for c in df.columns if c.startswith("f_btc_mom_")]
    regime_col = min(moms, key=lambda c: abs(int(c.rsplit("_", 1)[1]) - REGIME_COL_TARGET_BARS))
    gate = build_gate(df, a.gate, regime_col)

    d = df[[a.signal, "symbol", "datetime", "trade_ret"]].dropna().copy()
    cnt = d.groupby("datetime")[a.signal].transform("size")
    d = d[cnt >= MIN_NAMES]
    pct = d.groupby("datetime")[a.signal].rank(pct=True, method="average")
    d["top"] = pct > (1 - TOP_FRAC)
    d["gate"] = gate.reindex(d.index)
    d["fold"] = d["datetime"].dt.year.astype(str) + d["datetime"].dt.month.map(
        lambda m: "H1" if m <= 6 else "H2")

    rows = []
    for fold, sub in d.groupby("fold", sort=True):
        on = sub[sub["gate"]]
        on_top = on[on["top"]]
        if not len(on):
            continue
        net = (on_top["trade_ret"].mean() - cost) * 100 if len(on_top) else float("nan")
        mkt = (on["trade_ret"].mean() - cost) * 100
        rows.append(dict(fold=fold, open_rate=round(float(sub["gate"].mean()), 2),
                         n_top=len(on_top), net=round(net, 3), mkt=round(mkt, 3),
                         spread=round(net - mkt, 3)))
    folds = pd.DataFrame(rows)
    print(f"\nsignal={a.signal}  gate={a.gate}  cost={a.cost}%  "
          f"top {TOP_FRAC:.0%} at {MIN_NAMES}-name floor")
    print(folds.to_string(index=False))

    el = folds[folds["n_top"] >= MIN_FOLD_TRADES]
    abs_rate = float((el["net"] > 0).mean()) if len(el) else float("nan")
    sel_rate = float((el["spread"] > 0).mean()) if len(el) else float("nan")
    print(f"\neligible folds (n_top>={MIN_FOLD_TRADES}): {len(el)}")
    print(f"K1a absolute  : {int((el['net'] > 0).sum())}/{len(el)} positive = {abs_rate:.0%}")
    print(f"K1b selection : {int((el['spread'] > 0).sum())}/{len(el)} positive spread = {sel_rate:.0%}")

    on_top = d[d["gate"] & d["top"]].copy()
    on_top["net"] = on_top["trade_ret"] - cost
    g = on_top.groupby("symbol")["net"].sum().sort_values(ascending=False) * 100
    pos = int((g > 0).sum())
    print(f"attribution   : {pos}/{len(g)} names positive; "
          f"top-5 carry {g.head(5).sum():+.1f}pp of {g.sum():+.1f}pp")

    print("\n" + "=" * 90)
    if len(el) and abs_rate >= PASS_RATE and sel_rate >= PASS_RATE:
        print(f"VERDICT: SURVIVES (absolute {abs_rate:.0%}, selection {sel_rate:.0%}, both >= "
              f"{PASS_RATE:.0%}). Earned the next test; survivorship caveat still applies.")
    else:
        why = []
        if not len(el):
            why.append("no eligible folds")
        else:
            if abs_rate < PASS_RATE:
                why.append(f"K1a absolute {abs_rate:.0%} < {PASS_RATE:.0%}")
            if sel_rate < PASS_RATE:
                why.append(f"K1b selection {sel_rate:.0%} < {PASS_RATE:.0%}")
        print(f"VERDICT: KILLED ({'; '.join(why)}).")
    print("=" * 90)


if __name__ == "__main__":
    main()
