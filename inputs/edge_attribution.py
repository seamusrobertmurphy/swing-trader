"""Per-coin attribution of the gated cross-sectional edge: where does it live?

Answers "which coins should the narrow tradeable book hold" with evidence:
for the chosen signal/gate, every OOS gate-on top-third membership is credited
to its coin: appearances, mean after-fee trade return, and total contribution
(equal-weight within each block, compounding ignored). Coins that appear often
AND contribute positively are the high-potential candidates; coins that rank
into the cohort but bleed are the ones a narrower book drops.

    .venv/bin/python inputs/edge_attribution.py --interval 4h --signal f_d1_st_up --gate btc+breadth
"""
from __future__ import annotations

import argparse
import os

import pandas as pd

import build_dataset_1h as bd
import cross_sectional_4h as cs
import cross_sectional_regime as xr
import train_model as tm
import train_model_1h as t1


def attribution(interval: str, signal: str, gate_name: str, cost_pct: float) -> pd.DataFrame:
    """Per-coin OOS gate-on top-third attribution table, sorted by contribution."""
    cost = cost_pct / 100.0
    bd.configure(interval)
    frame_hours = bd._FRAME_MIN[bd.INTERVAL] / 60.0
    path = os.path.join(bd.BINANCE_DATA, f"dataset_{interval}_allmarket.parquet")
    print(f"loading {os.path.basename(path)} ...", flush=True)
    df = t1.load(path)
    regime_col = xr.pick_regime_col(df, frame_hours)
    gate = xr.build_gate(df, gate_name, regime_col)
    _, test, cut = t1.split(df)

    d = test[[signal, "symbol", "datetime", "trade_ret"]].assign(
        gate=gate.loc[test.index]).dropna()
    cnt = d.groupby("datetime")[signal].transform("size")
    d = d[cnt >= cs.MIN_COINS]
    pct = d.groupby("datetime")[signal].rank(pct=True, method="average")
    top = d[(pct > (1 - cs.TOP_FRAC)) & d["gate"]].copy()
    top["net"] = top["trade_ret"] - cost
    top["w"] = 1.0 / top.groupby("datetime")["symbol"].transform("size")
    top["contrib"] = top["net"] * top["w"]

    g = top.groupby("symbol").agg(
        appearances=("net", "size"),
        mean_net_pct=("net", lambda s: round(s.mean() * 100, 3)),
        win_rate=("net", lambda s: round(float((s > 0).mean()), 2)),
        contrib_pct=("contrib", lambda s: round(s.sum() * 100, 2)),
    ).sort_values("contrib_pct", ascending=False)

    print(f"OOS cut={cut}  signal={signal}  gate={gate_name}  cost={cost_pct}%")
    print(f"gate-on top-cohort rows: {len(top)} across {top['datetime'].nunique()} bars, "
          f"{g.shape[0]} distinct coins\n")
    return g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", default="4h")
    ap.add_argument("--signal", default="f_d1_st_up")
    ap.add_argument("--gate", default="btc+breadth")
    ap.add_argument("--cost", type=float, default=tm.COST_PCT)
    args = ap.parse_args()

    g = attribution(args.interval, args.signal, args.gate, args.cost)
    pd.set_option("display.width", 160)
    print("TOP CONTRIBUTORS (the evidence-based narrow book):")
    print(g.head(12).to_string())
    print("\nBLEEDERS (ranked in, lost money):")
    print(g.tail(8).to_string())
    pos = g[g["contrib_pct"] > 0]
    print(f"\n{len(pos)}/{len(g)} coins contribute positively; "
          f"top 5 coins carry {g['contrib_pct'].head(5).sum():.1f}pp of "
          f"{g['contrib_pct'].sum():.1f}pp total.")
    return g


if __name__ == "__main__":
    main()
