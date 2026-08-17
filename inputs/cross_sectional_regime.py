"""Frame-generic regime-gated cross-sectional ranking (successor to cross_sectional_regime_4h.py).

Does the top third by relative strength clear ZERO after fees when deployed
only in a favorable regime, standing in cash otherwise? Extensions over the
4h original:

  --interval   frame (4h, 1d, ...); loads dataset_<interval>_allmarket.parquet.
  --gate       btc            BTC ~28-day momentum > 0 (wall-clock matched per frame)
               breadth        > half the cross-section in an uptrend that bar
               btc+breadth    both (the stricter gate the 4h PARTIAL called for)
               btc+funding    BTC-up AND market funding not crowded-long
               none           ungated reference
  --cost       per-round-trip cost %, default the repo's standard; re-run at the
               achievable rate (BNB discount + maker entries) to price execution
               engineering into the verdict.
  --composite  adds a composite signal: the mean cross-sectional percentile
               rank of the stable momentum/trend family.
  --signals    restrict candidates; default is discovery.

The regime column is chosen by WALL-CLOCK, not name: f_btc_mom_* windows are
fixed bar counts (168 bars = 28 days on 4h but 5.5 months on 1d), so the window
closest to 28 days is picked per frame. Honest, after-fee. No orders.
"""
from __future__ import annotations

import argparse
import os

import pandas as pd

import build_dataset_1h as bd
import cross_sectional_4h as cs
import train_model as tm
import train_model_1h as t1

TARGET_REGIME_DAYS = 28
COMPOSITE_FAMILY = ("f_mst_dir", "f_d1_st_up", "f_w1_st_up", "f_st_dist_2",
                    "f_btc_rel_mom_168", "f_hr_mom_72")
BREADTH_CANDIDATES = ("f_d1_st_up", "f_w1_st_up", "f_mst_dir")


def pick_regime_col(df, frame_hours: float) -> str:
    moms = [c for c in df.columns if c.startswith("f_btc_mom_")]
    if not moms:
        raise SystemExit("no f_btc_mom_* columns in dataset")
    return min(moms, key=lambda c: abs(int(c.rsplit("_", 1)[1]) * frame_hours / 24 - TARGET_REGIME_DAYS))


def build_gate(df, kind: str, regime_col: str) -> pd.Series:
    """Boolean per-row deployment gate."""
    if kind == "none":
        return pd.Series(True, index=df.index)
    parts = []
    if "btc" in kind:
        parts.append(df[regime_col] > 0)
    if "breadth" in kind:
        bcol = next((c for c in BREADTH_CANDIDATES if c in df.columns), None)
        if bcol is None:
            raise SystemExit(f"no breadth column among {BREADTH_CANDIDATES}")
        breadth = (df[bcol] > 0).groupby(df["datetime"]).transform("mean")
        parts.append(breadth > 0.5)
    if "funding" in kind:
        import funding_features as ff
        mkt = ff.market()
        dates = pd.to_datetime(df["datetime"]).dt.normalize()
        open_by_date = mkt["gate_open"].reindex(dates.unique())
        # Missing funding history (early years / archive lag) counts as open:
        # the gate only CLOSES on observed crowding.
        mapped = dates.map(open_by_date.fillna(True))
        parts.append(mapped.astype(bool))
    if not parts:
        raise SystemExit(f"unknown gate {kind!r}")
    gate = parts[0]
    for p in parts[1:]:
        gate = gate & p
    return gate


def add_composite(df) -> str | None:
    have = [c for c in COMPOSITE_FAMILY if c in df.columns]
    if len(have) < 2:
        return None
    ranks = [df.groupby("datetime")[c].rank(pct=True) for c in have]
    df["f_x_composite"] = sum(ranks) / len(ranks)
    return "f_x_composite"


def gated_edge(frame, sig, gate, cost, min_rows):
    d = frame[[sig, "datetime", "trade_ret", "label"]].assign(gate=gate.loc[frame.index]).dropna()
    cnt = d.groupby("datetime")[sig].transform("size")
    d = d[cnt >= cs.MIN_COINS]
    if len(d) < min_rows:
        return None
    pct = d.groupby("datetime")[sig].rank(pct=True, method="average")
    d = d.assign(top=pct > (1 - cs.TOP_FRAC))
    out = {}
    for reg, mask in (("on", d["gate"]), ("off", ~d["gate"])):
        sub = d[mask]
        topsub = sub[sub["top"]]
        out[reg] = dict(
            mkt=round((sub["trade_ret"].mean() - cost) * 100, 3) if len(sub) else float("nan"),
            top=round((topsub["trade_ret"].mean() - cost) * 100, 3) if len(topsub) else float("nan"),
            n_top=len(topsub),
        )
    out["gate_open"] = round(float(d["gate"].mean()), 2)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", default="1d")
    ap.add_argument("--gate", default="btc",
                    choices=["btc", "breadth", "btc+breadth", "btc+funding", "none"])
    ap.add_argument("--cost", type=float, default=tm.COST_PCT,
                    help="round-trip cost in %% (default repo standard)")
    ap.add_argument("--composite", action="store_true")
    ap.add_argument("--signals", nargs="+", default=None)
    args = ap.parse_args()
    cost = args.cost / 100.0

    bd.configure(args.interval)
    frame_hours = bd._FRAME_MIN[bd.INTERVAL] / 60.0
    min_rows = max(150, int(cs.MIN_ROWS * 4 / frame_hours))
    path = os.path.join(bd.BINANCE_DATA, f"dataset_{args.interval}_allmarket.parquet")
    print(f"loading {os.path.basename(path)} ...", flush=True)
    df = t1.load(path)
    feat = [c for c in df.columns if c.startswith("f_")]
    regime_col = pick_regime_col(df, frame_hours)
    sigs = args.signals or cs.candidate_signals(df, feat)
    if args.composite:
        comp = add_composite(df)
        if comp:
            sigs = [comp] + list(sigs)
    gate = build_gate(df, args.gate, regime_col)
    train, test, cut = t1.split(df)
    print(f"frame={args.interval} ({frame_hours:g}h bars)  OOS cut={cut}  gate={args.gate} "
          f"(btc col {regime_col})  cost={args.cost}%  min_rows={min_rows}  "
          f"candidates={len(sigs)}\n", flush=True)

    rows = []
    for sig in sigs:
        if sig == regime_col or sig not in df.columns:
            continue
        tr = gated_edge(train, sig, gate, cost, min_rows)
        te = gated_edge(test, sig, gate, cost, min_rows)
        if tr is None or te is None:
            continue
        rows.append(dict(
            signal=sig, gate_open=te["gate_open"],
            tr_on_top=tr["on"]["top"], tr_on_mkt=tr["on"]["mkt"],
            te_on_top=te["on"]["top"], te_on_mkt=te["on"]["mkt"], te_on_n=te["on"]["n_top"],
            te_off_top=te["off"]["top"], te_off_mkt=te["off"]["mkt"],
        ))
    board = pd.DataFrame(rows)
    pd.set_option("display.width", 220, "display.max_columns", 30)
    print("=" * 108)
    print(f"REGIME-GATED CROSS-SECTIONAL EDGE, {args.interval} frame, gate={args.gate}, "
          f"after {args.cost:.2f}% cost. Deciding cell: te_on_top.")
    print("=" * 108)
    if board.empty:
        print("no usable signal.")
        return
    board = board.sort_values("te_on_top", ascending=False).reset_index(drop=True)
    print(board.head(20).to_string(index=False))

    b = board.iloc[0]
    print("\n" + "=" * 108)
    print(f"BEST: {b['signal']}  gate open {b['gate_open']:.0%} of bars")
    print(f"  TEST  gate-on : top-third {b['te_on_top']:+.3f}%/trade  (gated market {b['te_on_mkt']:+.3f}%)")
    print(f"  TEST  gate-off: top-third {b['te_off_top']:+.3f}%/trade  (market {b['te_off_mkt']:+.3f}%)")
    print(f"  TRAIN gate-on : top-third {b['tr_on_top']:+.3f}%/trade")
    print("=" * 108)
    clears = b["te_on_top"] > 0
    stable = (b["tr_on_top"] > 0) == (b["te_on_top"] > 0)
    if clears and stable:
        print("  => GO CANDIDATE: clears zero after cost in the deployed regime, train/test consistent.")
        print("     Next: portfolio_backtest.py with this gate/signal/cost for the turnover sweep.")
    elif clears:
        print("  => FRAGILE: clears on TEST only; treat as unproven.")
    else:
        print("  => NOT CLEARED with this gate/cost. Try a stricter gate, the achievable-cost")
        print("     scenario (--cost), or the coarser frame.")
    return board


if __name__ == "__main__":
    main()
