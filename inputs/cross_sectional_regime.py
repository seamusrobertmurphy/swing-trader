"""Frame-generic regime-gated cross-sectional ranking (successor to cross_sectional_regime_4h.py).

Same question as the 4h original: does the top third by relative strength clear ZERO after fees
when deployed only on bars where BTC is trending up (cash otherwise)? Differences:

  - --interval picks the frame (4h, 1d, ...); the dataset is dataset_<interval>_allmarket.parquet.
  - The regime column is chosen by WALL-CLOCK, not by name: f_btc_mom_* windows are fixed bar
    counts, so 168 bars is 28 days on 4h but 5.5 months on 1d. We pick the window closest to
    28 days for the configured frame (1d -> f_btc_mom_24, 4h -> f_btc_mom_168).
  - Signals come from cross_sectional_4h.candidate_signals discovery (momentum/trend families),
    optionally restricted with --signals.
  - MIN_ROWS scales with bars/day so the daily frame is not filtered into silence.

Honest, after-fee. No orders. Plain ASCII. Run from inputs/ with the repo venv.
"""
from __future__ import annotations

import argparse
import os

import pandas as pd

import build_dataset_1h as bd
import cross_sectional_4h as cs
import train_model as tm
import train_model_1h as t1

COST = tm.COST_PCT / 100.0
TARGET_REGIME_DAYS = 28


def pick_regime_col(df, frame_hours: float) -> str:
    moms = [c for c in df.columns if c.startswith("f_btc_mom_")]
    if not moms:
        raise SystemExit("no f_btc_mom_* columns in dataset")
    return min(moms, key=lambda c: abs(int(c.rsplit("_", 1)[1]) * frame_hours / 24 - TARGET_REGIME_DAYS))


def gated_edge(frame, sig, regime, min_rows):
    d = frame[[sig, "datetime", "trade_ret", "label", regime]].dropna()
    cnt = d.groupby("datetime")[sig].transform("size")
    d = d[cnt >= cs.MIN_COINS]
    if len(d) < min_rows:
        return None
    pct = d.groupby("datetime")[sig].rank(pct=True, method="average")
    d = d.assign(top=pct > (1 - cs.TOP_FRAC), btc_up=d[regime] > 0)
    out = {}
    for reg, mask in (("up", d["btc_up"]), ("dn", ~d["btc_up"])):
        sub = d[mask]
        topsub = sub[sub["top"]]
        out[reg] = dict(
            mkt=round((sub["trade_ret"].mean() - COST) * 100, 3) if len(sub) else float("nan"),
            top=round((topsub["trade_ret"].mean() - COST) * 100, 3) if len(topsub) else float("nan"),
            n_top=len(topsub),
        )
    out["gate_open"] = round(float(d["btc_up"].mean()), 2)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", default="1d")
    ap.add_argument("--signals", nargs="+", default=None,
                    help="restrict to these columns (default: discovered candidates)")
    args = ap.parse_args()

    bd.configure(args.interval)
    frame_hours = bd._FRAME_MIN[bd.INTERVAL] / 60.0
    min_rows = max(150, int(cs.MIN_ROWS * 4 / frame_hours))
    path = os.path.join(bd.BINANCE_DATA, f"dataset_{args.interval}_allmarket.parquet")
    print(f"loading {os.path.basename(path)} ...", flush=True)
    df = t1.load(path)
    feat = [c for c in df.columns if c.startswith("f_")]
    regime = pick_regime_col(df, frame_hours)
    sigs = args.signals or cs.candidate_signals(df, feat)
    train, test, cut = t1.split(df)
    print(f"frame={args.interval} ({frame_hours:g}h bars)  OOS cut={cut}  regime={regime}>0  "
          f"min_rows={min_rows}  candidates={len(sigs)}\n", flush=True)

    rows = []
    for sig in sigs:
        if sig == regime or sig not in df.columns:
            continue
        tr = gated_edge(train, sig, regime, min_rows)
        te = gated_edge(test, sig, regime, min_rows)
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
    print(f"REGIME-GATED CROSS-SECTIONAL EDGE, {args.interval} frame (after {tm.COST_PCT:.2f}% fee).")
    print("Deciding cell: te_up_top (TEST, BTC-up regime).")
    print("=" * 104)
    if board.empty:
        print("no usable signal.")
        return
    board = board.sort_values("te_up_top", ascending=False).reset_index(drop=True)
    print(board.head(20).to_string(index=False))

    b = board.iloc[0]
    print("\n" + "=" * 104)
    print(f"BEST: {b['signal']}  gate open {b['gate_open']:.0%} of bars")
    print(f"  TEST  BTC-up : top-third {b['te_up_top']:+.3f}%/trade  (regime market {b['te_up_mkt']:+.3f}%)")
    print(f"  TEST  BTC-dn : top-third {b['te_dn_top']:+.3f}%/trade  (regime market {b['te_dn_mkt']:+.3f}%)")
    print(f"  TRAIN BTC-up : top-third {b['tr_up_top']:+.3f}%/trade")
    print("=" * 104)
    clears = b["te_up_top"] > 0
    stable = (b["tr_up_top"] > 0) == (b["te_up_top"] > 0)
    if clears and stable:
        print("  => GO CANDIDATE: clears zero after fees in the BTC-up regime, train/test consistent.")
        print("     Next: non-overlapping top-K portfolio backtest with cash-when-gate-closed,")
        print("     per-fold stability, and buy&hold/BTC benchmarks.")
    elif clears:
        print("  => FRAGILE: clears zero on TEST but train disagrees; treat as unproven.")
    else:
        print("  => NOT CLEARED on this frame; compare against the 4h PARTIAL and stack the next lever")
        print("     (stricter gate: BTC-up AND breadth; or longer-horizon exits).")
    return board


if __name__ == "__main__":
    main()
