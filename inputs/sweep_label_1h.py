"""Priority 1b: label-geometry sweep on the 1h all-market frame.

The question (from the handoffs, sections 2.5 / 1b): does a fixed +10%/-5%/20d-style label
survive contact with crypto's own volatility, or is a volatility-scaled barrier better, and at
what (target, stop, horizon)? Here the label is the ATR-scaled triple barrier from
build_dataset_1h.compute_label_return, swept over a grid of (tgt_atr, stp_atr, horizon_bars).

Design that keeps it honest and cheap:
  - Features are computed ONCE per coin (the expensive part), on the full 1h candidate set
    (in-house + pandas-ta + TA-Lib + flow), then held fixed across all grid cells. So the
    label decision is not confounded by re-deriving features, and tomorrow's variable-
    selection pass runs on a settled label.
  - For each grid cell only the label and its realized return are recomputed, then a LightGBM
    is trained on the final-year-out split (data-standard) and scored on the after-fee Metric 2
    (eval_report._pnl): net expectancy per trade, win rate, t-stat, plus test AUC and the
    confidence-filtered precision against that cell's own base rate.
  - Each cell's breakeven win rate is S/(S+T) in ATR units = stp/(stp+tgt); the table lets you
    read actual vs breakeven directly, the same lopsided-geometry test as the exit side.

Outputs: a ranked per-run record under outputs/AA-evals/<date>/label-sweep-<date>.md, and the
best cell appended to evaluation-scores.md (evaluation type "label sweep") so it sits beside
the head-to-head runs for comparison. Plain ASCII; no orders.

Run (full grid, from the project .venv on the Mac):
  .venv/bin/python inputs/sweep_label_1h.py
Validate on a dev slice with a small grid:
  python inputs/sweep_label_1h.py --klines-root /tmp/multi1h/klines_1h \
      --flow /tmp/multi1h/flow_1h.csv --targets 2.0 3.0 --stops 1.0 --horizons 48 \
      --out /tmp/multi1h/AA-evals
"""
from __future__ import annotations

import argparse
import math
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import sklearn.base
from sklearn.metrics import roc_auc_score

import build_dataset_1h as b1
import train_model as tm
import eval_report as er

OOS_DAYS = 365
GRID = dict(targets=[1.5, 2.0, 3.0], stops=[1.0, 1.5], horizons=[24, 48, 96])  # ATR mults / bars


def precompute(klines_root: str, flow_csv: str, symbols=None):
    """Load each coin, compute the full feature set once, and keep the OHLCV for per-cell
    label recompute. Applies the same quality gate and point-in-time membership as the build."""
    flow = b1.read_frame(flow_csv) if flow_csv else None      # Parquet-preferred (dtypes preserved)
    symbols = symbols or b1.list_symbols(klines_root)
    min_needed = max(max(b1.WC["mom"]), b1.WC["rv_long"], b1.WC["bb"]) + max(GRID["horizons"])
    coins = []
    for sym in symbols:
        d = b1.load_coin(klines_root, sym)
        if len(d) < min_needed or not b1.passes_quality(b1.gap_stats(d)):
            continue
        slash = f"{sym[:-4]}/USDT" if sym.endswith("USDT") else sym
        feats = {}
        feats.update(b1.indicator_block(d, "wc", b1.WC))
        feats.update(b1.indicator_block(d, "hr", b1.HR))
        feats.update(b1.extra_ta_block(d))
        feats.update(b1.pandas_ta_block(d))
        feats.update(b1.talib_block(d))
        feats.update(b1.flow_block(d, flow, slash))
        coins.append(dict(slash=slash, d=d, feat=pd.DataFrame(feats, index=d.index),
                          insample=b1.screen_membership(d).values, dt=d["datetime"].values))
        print(f"  precomputed {sym}: {len(d)} bars")
    if not coins:
        raise SystemExit("no coins precomputed; check klines_root")
    feat_cols = [c for c in coins[0]["feat"].columns if c.startswith("f_")]
    return coins, feat_cols


def score_cell(coins, feat_cols, tgt, stp, hzn, cost_frac, conf_hi):
    """Recompute the label for this geometry, train LightGBM on the final-year split, score."""
    cfg = dict(tgt_atr=tgt, stp_atr=stp, horizon_bars=hzn, atr_len=b1.LABEL["atr_len"])
    frames = []
    for c in coins:
        lab, tret = b1.compute_label_return(c["d"], cfg)
        df = c["feat"].copy()
        df["datetime"] = c["dt"]
        df["in_sample"] = c["insample"]
        df["label"] = lab.values
        df["trade_ret"] = tret.values
        df = df.dropna(subset=[*feat_cols, "label", "trade_ret"])
        frames.append(df[df["in_sample"]])
    data = pd.concat(frames, ignore_index=True).sort_values("datetime").reset_index(drop=True)
    cut = data["datetime"].max() - pd.Timedelta(days=OOS_DAYS)
    emb = pd.Timedelta(days=max(1, math.ceil(hzn / b1.BARS_PER_DAY)))
    train = data[data["datetime"] <= cut - emb]
    test = data[data["datetime"] > cut]
    if len(train) < 500 or len(test) < 200 or train["label"].nunique() < 2:
        return None
    mdl = sklearn.base.clone(dict(tm.build_models(True))["LightGBM"])
    mdl.fit(train[feat_cols], train["label"])
    prob = mdl.predict_proba(test[feat_cols])[:, 1]
    base = float(test["label"].mean())
    auc = roc_auc_score(test["label"], prob) if test["label"].nunique() > 1 else float("nan")
    conf = prob >= conf_hi
    prec = float(test["label"][conf].mean()) if conf.sum() else float("nan")
    pnl = er._pnl(prob, test["trade_ret"].values, conf_hi, cost_frac)
    breakeven = stp / (stp + tgt)            # ATR-unit breakeven win rate
    return dict(tgt=tgt, stp=stp, hzn=hzn, base=base, auc=auc, trades=pnl["n"], prec=prec,
                net=pnl["expectancy"], winrate=pnl["winrate"], tstat=pnl.get("tstat", float("nan")),
                breakeven=breakeven, test_rows=len(test), train_rows=len(train), n_feat=len(feat_cols))


def _fmt(r):
    pct = (r["prec"] / r["base"] - 1) * 100 if r["base"] else float("nan")
    return [f"+{r['tgt']}/-{r['stp']} ATR", f"{r['hzn']}b ({r['hzn']//b1.BARS_PER_DAY}d)",
            f"{r['base']:.3f}", f"{r['auc']:.3f}", f"{r['trades']:,}", f"{r['prec']:.3f}",
            f"{pct:+.1f}%", f"{r['net']*100:+.3f}%", f"{r['winrate']:.1%}",
            f"{r['breakeven']:.1%}", f"{r['tstat']:+.2f}"]


def write_record(results, evals_dir):
    os.makedirs(evals_dir, exist_ok=True)
    cd = datetime.now(timezone.utc).strftime("%Y%m%d")
    hd = f"{cd[:4]}-{cd[4:6]}-{cd[6:]}"
    run_dir = os.path.join(evals_dir, hd)
    os.makedirs(run_dir, exist_ok=True)
    stem = f"label-sweep-{cd}"
    ranked = sorted(results, key=lambda r: (np.isfinite(r["net"]), r["net"]), reverse=True)
    headers = ["geometry", "horizon", "base rate", "test AUC", "trades", "precision",
               "precision change", "net P&L/trade", "win rate", "breakeven win", "t-stat"]
    lines = [f"# Priority 1b: label-geometry sweep ({hd})\n",
             "ATR-scaled triple-barrier label swept over (target, stop, horizon). The model and "
             "split are fixed; only the label changes per row. Net P&L/trade is after the 0.20% "
             "round-trip cost on the model's confident trades (prob >= 0.60). 'breakeven win' is "
             "stop/(stop+target) in ATR units -- a geometry is lopsided when its actual win rate "
             "sits at or below breakeven. Ranked by net P&L/trade, best first.\n",
             "| " + " | ".join(headers) + " |",
             "| " + " | ".join("---" for _ in headers) + " |"]
    for r in ranked:
        lines.append("| " + " | ".join(_fmt(r)) + " |")
    best = ranked[0]
    verdict = "GO" if (np.isfinite(best["net"]) and best["net"] > 0 and best["tstat"] > 2
                       and best["prec"] > best["base"]) else "NO-GO"
    lines.append(f"\n**Best by net P&L/trade:** +{best['tgt']}/-{best['stp']} ATR over "
                 f"{best['hzn']} bars -> net {best['net']*100:+.3f}%/trade, win {best['winrate']:.1%} "
                 f"vs breakeven {best['breakeven']:.1%}, t-stat {best['tstat']:+.2f}, AUC "
                 f"{best['auc']:.3f}. Verdict: {verdict}.\n")
    md_path = os.path.join(run_dir, f"{stem}.md")
    with open(md_path, "w") as fh:
        fh.write("\n".join(lines) + "\n")

    # one consolidated index row for the best cell
    pct = (best["prec"] / best["base"] - 1) * 100 if best["base"] else float("nan")
    ds_label = (f"{best['test_rows']:,}r / {best['n_feat']}f | best +{best['tgt']}/-{best['stp']}"
                f"ATR {best['hzn']}b")
    er._update_index(evals_dir, [hd, "label sweep", ds_label, "LightGBM", f"{best['auc']:.3f}",
                                 f"{best['prec']:.3f}", f"{best['base']:.3f}", f"{pct:+.1f}%",
                                 f"{best['net']*100:+.2f}%", f"{best['trades']:,}", verdict,
                                 f"[md]({hd}/{stem}.md)"])
    return md_path, ranked, best, verdict


def main():
    p = argparse.ArgumentParser(description="Priority 1b label-geometry sweep (1h frame)")
    p.add_argument("--klines-root", default=b1.DEFAULT_KLINES_ROOT)
    p.add_argument("--flow", default=b1.DEFAULT_FLOW_CSV)
    p.add_argument("--symbols", nargs="+", default=None)
    p.add_argument("--targets", nargs="+", type=float, default=GRID["targets"])
    p.add_argument("--stops", nargs="+", type=float, default=GRID["stops"])
    p.add_argument("--horizons", nargs="+", type=int, default=GRID["horizons"])
    p.add_argument("--out", default=os.path.join(tm.OUT, "AA-evals"))
    a = p.parse_args()

    cost_frac = tm.COST_PCT / 100.0
    coins, feat_cols = precompute(a.klines_root, a.flow, a.symbols)
    print(f"features held fixed: {len(feat_cols)}; grid = "
          f"{len(a.targets)}x{len(a.stops)}x{len(a.horizons)} cells\n")
    results = []
    for tgt in a.targets:
        for stp in a.stops:
            for hzn in a.horizons:
                r = score_cell(coins, feat_cols, tgt, stp, hzn, cost_frac, tm.CONF_HI)
                if r is None:
                    print(f"  +{tgt}/-{stp} ATR {hzn}b: skipped (insufficient split)")
                    continue
                results.append(r)
                print(f"  +{tgt}/-{stp} ATR {hzn}b: base {r['base']:.3f} AUC {r['auc']:.3f} "
                      f"net {r['net']*100:+.3f}%/trade win {r['winrate']:.1%} "
                      f"(breakeven {r['breakeven']:.1%}) t {r['tstat']:+.2f} n {r['trades']}")
    if not results:
        raise SystemExit("no sweep cells produced a result")
    md_path, ranked, best, verdict = write_record(results, a.out)
    print(f"\nbest geometry: +{best['tgt']}/-{best['stp']} ATR over {best['hzn']} bars "
          f"-> net {best['net']*100:+.3f}%/trade, verdict {verdict}")
    print(f"sweep record: {md_path}")


if __name__ == "__main__":
    main()
