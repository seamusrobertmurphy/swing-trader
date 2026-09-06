"""Multi-timeline training and evaluation.

Assess the potential of the multi-resolution data expansions -- the new 4h frame and the
multi-timeframe CONTEXT features -- on the same honest, after-fee, final-year out-of-sample
scoreboard used everywhere else in the project.

Two axes:

  1. FRAME comparison. Train and score one model on the 1h frame and one on the 4h frame,
     head to head. Each frame is its own dataset; rows are NEVER pooled across resolutions
     (forbidden by tasks/multi-resolution-build-plan.md -- different row meanings, overlapping
     information). "Multiple timelines simultaneously" enters as context FEATURES inside one
     frame's rows, which is the canonical multi-resolution-TRAINING design (multi-resolution
     trading would add fee drag and 4-24x the rows for no demonstrated benefit).

  2. TIMELINE ABLATION (on a frame that carries higher-tf context, i.e. 4h). Does adding the
     daily+weekly context (f_d1_, f_w1_) and the cross-asset BTC lead-lag (f_btc_) lift OOS
     performance over a native-only model trained on the same rows? This isolates exactly what
     the multiple-timeline data buys, holding the rows and split fixed.

Reuses train_model_1h.split (final-year OOS, embargo = label horizon) and
train_model.build_models/evaluate, plus the shared 0.20% round-trip cost. The deciding number
is the after-fee expectancy of the high-confidence long signals -- the rows we would actually
trade -- not raw accuracy. No orders; honest GO/NO-GO. Plain ASCII.
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd

import build_dataset_1h as bd
import train_model as tm
import train_model_1h as t1

# Context vs cross-asset vs native feature families. Higher-timeframe context is the coarser
# candle structure each bar sits inside; cross-asset is the BTC lead-lag (the only family not
# derived from the coin's own price). "Native" is everything computed from the coin's own frame.
CTX_PREFIXES = ("f_d1_", "f_w1_", "f_4h_", "f_mo_")
XASSET_PREFIXES = ("f_btc_",)
CONF_HI = tm.CONF_HI
COST = tm.COST_PCT / 100.0           # 0.20% round-trip as a return fraction


def subset(feat, drop_ctx=False, drop_xasset=False):
    out = feat
    if drop_ctx:
        out = [c for c in out if not c.startswith(CTX_PREFIXES)]
    if drop_xasset:
        out = [c for c in out if not c.startswith(XASSET_PREFIXES)]
    return out


def lgbm():
    """A fresh LightGBM estimator (the project's Tier-1 model) for each fit."""
    for name, mdl in tm.build_models(tm.HAVE_LGBM):
        if "lightgbm" in name.lower():
            return mdl
    # fallback: strongest available tree model
    for name, mdl in tm.build_models(tm.HAVE_LGBM):
        if "forest" in name.lower():
            return mdl
    raise SystemExit("no tree model available")


def after_fee_long_edge(prob, trade_ret, hi=CONF_HI):
    """The decision-relevant number: if we acted on the model's high-confidence long signals
    (prob >= hi), what is the average realised return after the round-trip cost? trade_ret is
    the realised gross return under the barrier. Returns (net_edge, n_acted, coverage)."""
    prob = np.asarray(prob, float)
    tr = np.asarray(trade_ret, float)
    act = prob >= hi
    ok = act & np.isfinite(tr)
    n = int(ok.sum())
    if n == 0:
        return float("nan"), 0, 0.0
    return float(tr[ok].mean() - COST), n, float(act.mean())


def run_cell(label, df, feat, split_fn):
    """Train LightGBM on one (frame, feature-set) and return its OOS scoreboard row."""
    train, test, cut = split_fn(df)
    Xtr, ytr = train[feat], train["label"]
    Xte, yte = test[feat], test["label"]
    base = yte.mean()
    _, m = tm.evaluate(label, lgbm(), Xtr, ytr, Xte, yte, base, lines=[])
    net, n_act, cov = after_fee_long_edge(m["prob"], test["trade_ret"].values)
    return dict(setup=label, n_feat=len(feat), test_rows=len(test), base=round(base, 3),
                auc=round(m["auc"], 3), prec=round(m["prec"], 3), lift=round(m["prec"] - base, 3),
                conf_prec=round(m["conf"]["precision"], 3) if m["conf"]["n"] else float("nan"),
                conf_cov=round(m["conf"]["coverage"], 3),
                net_edge_pct=round(net * 100, 3), n_acted=n_act)


def evaluate_frame(interval_hours, dataset_path, ablate=True):
    """Score a frame and (optionally) ablate its multi-timeline families on identical rows."""
    bd.configure(interval_hours)
    df = t1.load(dataset_path)                       # in-sample rows only
    feat_all = bd.feature_columns(df)
    has_ctx = any(c.startswith(CTX_PREFIXES) for c in feat_all)
    has_xa = any(c.startswith(XASSET_PREFIXES) for c in feat_all)
    rows = []
    tag = bd.INTERVAL
    if ablate and (has_ctx or has_xa):
        rows.append(run_cell(f"{tag}: native only", df, subset(feat_all, True, True), t1.split))
        if has_ctx:
            rows.append(run_cell(f"{tag}: native + MTF ctx", df, subset(feat_all, False, True), t1.split))
        if has_xa:
            rows.append(run_cell(f"{tag}: native + BTC xasset", df, subset(feat_all, True, False), t1.split))
    rows.append(run_cell(f"{tag}: ALL features", df, feat_all, t1.split))
    return rows


def main():
    import argparse
    p = argparse.ArgumentParser(description="Multi-timeline frame comparison + context ablation")
    p.add_argument("--frames", nargs="+", default=["4", "1"],
                   help="interval hours to evaluate, e.g. 4 1 (default both)")
    a = p.parse_args()

    paths = {1: os.path.join(bd.BINANCE_DATA, "dataset_1h_allmarket.parquet"),
             4: os.path.join(bd.BINANCE_DATA, "dataset_4h_allmarket.parquet")}

    all_rows = []
    for f in a.frames:
        ih = int(f)
        path = paths[ih]
        if bd.read_frame(path) is None:
            print(f"skip {ih}h: no dataset at {path}")
            continue
        print(f"\n=== evaluating {ih}h frame: {os.path.basename(path)} ===")
        all_rows += evaluate_frame(ih, path, ablate=True)

    board = pd.DataFrame(all_rows)
    pd.set_option("display.width", 200, "display.max_columns", 20)
    print("\n" + "=" * 78)
    print("MULTI-TIMELINE SCOREBOARD (final-year OOS, after 0.20% round-trip cost)")
    print("net_edge_pct = avg after-fee return of the high-confidence (p>=%.2f) long signals" % CONF_HI)
    print("=" * 78)
    print(board.to_string(index=False))

    # honest verdict: any setup with a positive after-fee edge AND AUC that beats a coin flip
    win = board[(board["net_edge_pct"] > 0) & (board["auc"] > 0.55)]
    print("\nVERDICT:")
    if len(win):
        print("  GO candidates (positive after-fee edge and AUC>0.55):")
        print(win[["setup", "auc", "net_edge_pct", "n_acted"]].to_string(index=False))
    else:
        print("  NO-GO at every setup: no feature set clears a positive after-fee edge with AUC>0.55.")
        best = board.loc[board["net_edge_pct"].idxmax()]
        print(f"  best after-fee edge: {best['setup']} at {best['net_edge_pct']:+.3f}% "
              f"(AUC {best['auc']}, n={best['n_acted']})")
    # did the multi-timeline context help, holding rows fixed?
    print("\nMULTI-TIMELINE LIFT (4h frame, same rows):")
    fr = board[board["setup"].str.startswith("4h")].set_index("setup")
    if "4h: native only" in fr.index and "4h: ALL features" in fr.index:
        d_auc = fr.loc["4h: ALL features", "auc"] - fr.loc["4h: native only", "auc"]
        d_net = fr.loc["4h: ALL features", "net_edge_pct"] - fr.loc["4h: native only", "net_edge_pct"]
        print(f"  ALL vs native-only:  dAUC {d_auc:+.3f}   d(after-fee edge) {d_net:+.3f}pp")
        print("  => the multi-timeline data " + ("ADDS measurable OOS signal." if (d_auc > 0.005 or d_net > 0)
              else "does NOT lift OOS performance on this frame."))
    return board


if __name__ == "__main__":
    main()
