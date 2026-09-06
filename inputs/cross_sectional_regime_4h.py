"""Regime-gated cross-sectional ranking: does the top third clear ZERO after fees when we only
deploy in a favorable (BTC-trending-up) regime? (4h frame.)

cross_sectional_4h.py established that relative strength is real and stable (the top third beats
the bottom third for most momentum/trend signals) but long-only still loses, because the universe's
after-fee baseline is about -0.38%/trade. The most direct lever to lift the absolute level above
zero without shorting (forbidden by the brief) is a MARKET-REGIME GATE: rank and hold the strongest
third only on bars where Bitcoin itself is trending up, and stand in cash otherwise.

This tests exactly that. Regime = f_btc_mom_168 > 0 (BTC's own ~28-day momentum, causal, market-wide
so identical across coins at each bar). For each candidate signal it reports the top-third after-fee
edge and the market baseline, split by BTC-up vs BTC-down, on TRAIN and TEST, plus how much of the
time the gate is open. The deciding number is the TEST top-third edge in the BTC-up regime: if it
clears zero and is train/test stable, the regime-gated long-the-strongest portfolio is a GO candidate.

Honest, after-fee. No orders. Plain ASCII.
"""
from __future__ import annotations
import os
import pandas as pd

import build_dataset_1h as bd
import train_model_1h as t1
import train_model as tm
import cross_sectional_4h as cs

COST = tm.COST_PCT / 100.0
REGIME = "f_btc_mom_168"          # BTC ~28d momentum; >0 == favorable (BTC trending up)
SIGNALS = ["f_mst_dir", "f_btc_corr_168", "f_d1_st_up", "f_hr_mom_72", "f_st_dist_2"]


def gated_edge(frame, sig):
    """Top-third after-fee edge and market baseline, split by BTC regime, for one signal/block."""
    cols = [sig, "datetime", "trade_ret", "label", REGIME]
    d = frame[cols].dropna()
    cnt = d.groupby("datetime")[sig].transform("size")
    d = d[cnt >= cs.MIN_COINS]
    if len(d) < cs.MIN_ROWS:
        return None
    pct = d.groupby("datetime")[sig].rank(pct=True, method="average")
    d = d.assign(top=pct > (1 - cs.TOP_FRAC), btc_up=d[REGIME] > 0)
    out = {}
    for reg, mask in (("up", d["btc_up"]), ("dn", ~d["btc_up"])):
        sub = d[mask]
        topsub = sub[sub["top"]]
        out[reg] = dict(
            mkt=round((sub["trade_ret"].mean() - COST) * 100, 3) if len(sub) else float("nan"),
            top=round((topsub["trade_ret"].mean() - COST) * 100, 3) if len(topsub) else float("nan"),
            n_top=len(topsub),
        )
    out["gate_open"] = round(float(d["btc_up"].mean()), 2)     # share of bars BTC is up
    return out


def main():
    bd.configure(4)
    path = os.path.join(bd.BINANCE_DATA, "dataset_4h_allmarket.parquet")
    print(f"loading {os.path.basename(path)} ...", flush=True)
    df = t1.load(path)
    if REGIME not in df.columns:
        raise SystemExit(f"{REGIME} not in dataset")
    train, test, cut = t1.split(df)
    print(f"OOS split at {cut}  |  regime = {REGIME} > 0 (BTC trending up)\n", flush=True)

    rows = []
    for sig in SIGNALS:
        if sig not in df.columns:
            print(f"skip {sig} (absent)")
            continue
        tr = gated_edge(train, sig)
        te = gated_edge(test, sig)
        if tr is None or te is None:
            continue
        rows.append(dict(
            signal=sig, gate_open=te["gate_open"],
            tr_up_top=tr["up"]["top"], tr_up_mkt=tr["up"]["mkt"],
            te_up_top=te["up"]["top"], te_up_mkt=te["up"]["mkt"], te_up_n=te["up"]["n_top"],
            te_dn_top=te["dn"]["top"], te_dn_mkt=te["dn"]["mkt"],
        ))
    board = pd.DataFrame(rows)
    pd.set_option("display.width", 220, "display.max_columns", 30)
    print("=" * 104)
    print("REGIME-GATED CROSS-SECTIONAL EDGE (after 0.20%% fee). up=BTC-up regime, dn=BTC-down.")
    print("top=top-third long cohort, mkt=all coins that regime. Deciding cell: te_up_top (TEST, gate open).")
    print("=" * 104)
    print(board.to_string(index=False))

    if board.empty:
        print("\nno usable signal.")
        return
    board = board.sort_values("te_up_top", ascending=False).reset_index(drop=True)
    b = board.iloc[0]
    ungated_mkt = -0.382                              # the all-regime baseline from cross_sectional_4h
    print("\n" + "=" * 104)
    print(f"BEST: {b['signal']}  gate open {b['gate_open']:.0%} of bars")
    print(f"  TEST  BTC-up : top-third {b['te_up_top']:+.3f}%/trade  (regime market {b['te_up_mkt']:+.3f}%)")
    print(f"  TEST  BTC-dn : top-third {b['te_dn_top']:+.3f}%/trade  (regime market {b['te_dn_mkt']:+.3f}%)")
    print(f"  TRAIN BTC-up : top-third {b['tr_up_top']:+.3f}%/trade")
    print(f"  reference    : ungated all-regime market baseline {ungated_mkt:+.3f}%/trade")
    print("=" * 104)
    clears = b["te_up_top"] > 0
    stable = (b["tr_up_top"] > 0) == (b["te_up_top"] > 0)
    if clears and stable:
        print("  => GO CANDIDATE: regime-gated long-the-strongest clears zero after fees in the BTC-up")
        print("     regime, train/test consistent. Next: non-overlapping top-K portfolio backtest with the")
        print("     cash-when-gate-closed rule, per-fold stability, and a buy&hold/BTC benchmark.")
    elif b["te_up_top"] > b["te_up_mkt"] and b["te_up_top"] > ungated_mkt:
        print("  => PARTIAL: the gate lifts the top-third edge well above the ungated baseline and beats the")
        print("     regime market, but does not yet clear zero. Stack the next lever (longer-horizon label/")
        print("     exit, or a stricter gate e.g. BTC-up AND breadth) before a portfolio backtest.")
    else:
        print("  => NO-GO: the BTC-up gate does not lift the top-third above zero or beyond the baseline.")
    return board


if __name__ == "__main__":
    main()
