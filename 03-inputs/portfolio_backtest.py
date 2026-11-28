"""Non-overlapping gated top-third portfolio backtest on the after-fee scoreboard.

The regime evals measure per-trade edge; this measures the thing you would
actually run: at each block boundary (block = label horizon, so trades never
overlap), if the gate is open, enter the top third of the cross-section by the
chosen signal, realize each coin's ``trade_ret`` minus cost, compound the
cohort mean; if the gate is shut, hold cash (0% for the block). Benchmarked
against BTC buy-and-hold over the same window, train and test reported apart.

Sweeps entry frequency (every 1, 2, 3 blocks — fewer entries, fewer tolls) and
takes the gate/cost/composite options from cross_sectional_regime. Honest,
after-fee, no orders.

    .venv/bin/python inputs/portfolio_backtest.py --interval 4h --signal f_d1_st_up \
        --gate btc+breadth --cost 0.20
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd

import build_dataset_1h as bd
import cross_sectional_4h as cs
import cross_sectional_regime as xr
import train_model as tm
import train_model_1h as t1


def block_series(frame, sig, gate, cost, horizon_bars, every=1):
    """Equity curve over non-overlapping blocks. Returns (dates, equity, n_deployed)."""
    d = frame[[sig, "datetime", "trade_ret"]].assign(gate=gate.loc[frame.index]).dropna()
    cnt = d.groupby("datetime")[sig].transform("size")
    d = d[cnt >= cs.MIN_COINS]
    if d.empty:
        return None
    bars = np.sort(d["datetime"].unique())
    step = horizon_bars * every
    eq, curve, dates, deployed = 1.0, [], [], 0
    for i in range(0, len(bars), step):
        bar = bars[i]
        rows = d[d["datetime"] == bar]
        if rows.empty:
            continue
        if bool(rows["gate"].iloc[0]) and rows["gate"].mean() > 0.5:
            pct = rows[sig].rank(pct=True)
            top = rows[pct > (1 - cs.TOP_FRAC)]
            if len(top):
                eq *= 1.0 + float(top["trade_ret"].mean()) - cost
                deployed += 1
        dates.append(pd.Timestamp(bar))
        curve.append(eq)
    return pd.Series(curve, index=dates), deployed


def btc_buyhold(klines_root, dates):
    d = bd.load_coin(klines_root, "BTCUSDT")
    px = d.set_index(pd.to_datetime(d["datetime"]))["close"]
    px = px.reindex(pd.DatetimeIndex(dates), method="ffill")
    return px / px.iloc[0]


def maxdd(curve: pd.Series) -> float:
    return float((curve / curve.cummax() - 1).min())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", default="4h")
    ap.add_argument("--signal", default=None, help="default: composite if available, else f_d1_st_up")
    ap.add_argument("--gate", default="btc+breadth",
                    choices=["btc", "breadth", "btc+breadth", "btc+funding", "none"])
    ap.add_argument("--cost", type=float, default=tm.COST_PCT)
    args = ap.parse_args()
    cost = args.cost / 100.0

    bd.configure(args.interval)
    frame_hours = bd._FRAME_MIN[bd.INTERVAL] / 60.0
    horizon = bd.LABEL["horizon_bars"]
    path = os.path.join(bd.BINANCE_DATA, f"dataset_{args.interval}_allmarket.parquet")
    print(f"loading {os.path.basename(path)} ...", flush=True)
    df = t1.load(path)
    regime_col = xr.pick_regime_col(df, frame_hours)
    comp = xr.add_composite(df)
    sig = args.signal or comp or "f_d1_st_up"
    gate = xr.build_gate(df, args.gate, regime_col)
    train, test, cut = t1.split(df)
    print(f"frame={args.interval}  signal={sig}  gate={args.gate}  cost={args.cost}%  "
          f"horizon={horizon} bars  OOS cut={cut}\n", flush=True)

    for name, block in (("TRAIN", train), ("TEST", test)):
        for every in (1, 2, 3):
            res = block_series(block, sig, gate, cost, horizon, every)
            if res is None:
                continue
            curve, deployed = res
            if len(curve) < 3:
                continue
            bench = btc_buyhold(bd.DEFAULT_KLINES_ROOT, curve.index)
            years = max((curve.index[-1] - curve.index[0]).days / 365.25, 1e-9)
            print(f"{name} every={every}: blocks={len(curve)} deployed={deployed} "
                  f"return={curve.iloc[-1]-1:+.1%} (ann {curve.iloc[-1]**(1/years)-1:+.1%}) "
                  f"maxDD={maxdd(curve):+.1%} | BTC buy&hold {float(bench.iloc[-1])-1:+.1%} "
                  f"maxDD {maxdd(bench):+.1%}")
        print()


if __name__ == "__main__":
    main()
