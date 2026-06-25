"""Edge diagnostics (Q1 / Q5 / Q6 of the model-diagnostic handoff), frame-agnostic.

Answers three questions the cost-aware scoreboard leaves implicit, reusing the SAME split, cost and
confidence machinery as train_model_1h / model_assessment_1h so methods cannot disagree:

  Q1  Is there a PRE-COST edge at all?  Strip fees, report the held-out model's directional AUC and
      accuracy and its mean trade return per acted trade, against TWO honest baselines: a coin-flip at
      the actual class base rate (not 50%) and a true 1-bar PERSISTENCE rule ("next bar = last bar",
      reconstructed from the coin's own close). If the model beats neither before costs, the problem is
      features/architecture and nothing downstream matters.

  Q5  Is the edge stable across REGIMES, or an artifact of one era?  Time-series out-of-fold
      probabilities across all history, bucketed into measurable eras (2018 bear, 2021 bull, 2022
      collapse, recent), each reporting after-cost expectancy per trade, win rate and trade count.

  Q6  Is SELECTIVITY available?  Sweep the confidence threshold and plot after-cost return per trade
      against it. If the curve rises as the model trades less, the path is selectivity, not a new
      architecture.

Pre-cost vs after-cost is the Q1/Q2 split: after-cost per trade = trade_ret - COST_PCT/100.

Native Python (sklearn + lightgbm if present). Writes outputs/AA-evals/<date>/edge-diagnostics-*.md
plus a selectivity PNG. Run on the project .venv:
    .venv/bin/python inputs/edge_diagnostics.py --interval 4h
    .venv/bin/python inputs/edge_diagnostics.py --interval 5m            # once the 5m data is built
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import TimeSeriesSplit

try:
    from lightgbm import LGBMClassifier
    HAVE_LGBM = True
except ImportError:
    HAVE_LGBM = False

import build_dataset_1h as bd
import train_model as tm
import train_model_1h as t1

# Measurable, contemporaneous eras (boundaries are dates, not narrative): each row covers [start, end).
ERAS = [("2017 launch run-up", "2017-08", "2018-01"),
        ("2018 bear",          "2018-01", "2019-04"),
        ("2019-20 base",       "2019-04", "2020-10"),
        ("2020-21 bull",       "2020-10", "2021-05"),
        ("2021 top + chop",    "2021-05", "2021-11"),
        ("2022 collapse",      "2021-11", "2023-01"),
        ("2023-24 recovery",   "2023-01", "2024-06"),
        ("2025-26 recent",     "2024-06", "2027-01")]


def strong_model():
    """One capable, scalable classifier for the diagnostics (LightGBM if available, else HistGBM)."""
    if HAVE_LGBM:
        return LGBMClassifier(n_estimators=400, num_leaves=31, learning_rate=0.05, max_depth=6,
                              min_child_samples=100, subsample=0.8, colsample_bytree=0.8,
                              subsample_freq=5, class_weight="balanced", random_state=0,
                              n_jobs=-1, verbosity=-1)
    return HistGradientBoostingClassifier(max_iter=400, learning_rate=0.05, max_depth=6,
                                          max_leaf_nodes=31, l2_regularization=1.0,
                                          class_weight="balanced", random_state=0)


def cost_frac():
    return tm.COST_PCT / 100.0                                  # 0.20% -> 0.002 per round trip


def persistence_act(df, klines_root):
    """True 1-bar persistence ('next bar = last bar'): act-long on bar t when the coin's own previous
    close-to-close return was positive. Reconstructed from each coin's close, aligned by datetime, so
    it is the honest momentum baseline the model must beat (causal, no future)."""
    act = np.zeros(len(df), bool)
    pos = {sym: i for i, sym in enumerate(df["symbol"].to_numpy())}  # not used; clarity only
    for sym, sub in df.groupby("symbol"):
        o = bd.load_coin(klines_root, sym.replace("/", ""))
        if o.empty:
            continue
        ret = o.assign(datetime=pd.to_datetime(o["datetime"])).set_index("datetime")["close"].pct_change()
        r = ret.reindex(pd.to_datetime(sub["datetime"]).to_numpy()).to_numpy()
        act[df.index.get_indexer(sub.index)] = np.nan_to_num(r) > 0
    return act


def oof_proba(est, X, y, n_splits=5):
    """Time-series out-of-fold probabilities across history. Returns (positions, p_oof): `positions`
    are positional row indices into X for the predicted blocks (expanding TimeSeriesSplit, no leak)."""
    yv = y.to_numpy() if hasattr(y, "to_numpy") else np.asarray(y)
    pos, pr = [], []
    for tr_idx, te_idx in TimeSeriesSplit(n_splits=n_splits).split(X):
        m = clone(est).fit(X.iloc[tr_idx], yv[tr_idx])
        pr.append(m.predict_proba(X.iloc[te_idx])[:, 1])
        pos.append(te_idx)
    return np.concatenate(pos), np.concatenate(pr)


def q1_pre_cost(df, feat, klines_root, conf_hi=tm.CONF_HI):
    """Q1: pre-cost held-out edge vs the base-rate coin flip and the 1-bar persistence baseline."""
    train, test, cut = t1.split(df)
    m = clone(strong_model()).fit(train[feat], train["label"])
    p = m.predict_proba(test[feat])[:, 1]
    y = test["label"].to_numpy().astype(int)
    tr = test["trade_ret"].to_numpy()
    base = float(y.mean())
    auc = float(roc_auc_score(y, p)) if len(np.unique(y)) > 1 else float("nan")
    acc = float(((p >= 0.5).astype(int) == y).mean())
    flip_acc = max(base, 1 - base)                              # majority-class accuracy (informational)
    # model acted trades (act-long), PRE vs AFTER cost, plus the precision of those picks
    act = p >= conf_hi
    pre = float(np.nanmean(tr[act])) if act.any() else float("nan")
    post = pre - cost_frac()
    prec_act = float(y[act].mean()) if act.any() else float("nan")   # win rate of the model's picks
    # 1-bar persistence baseline on the same test rows
    pa = persistence_act(test, klines_root)
    persist_acc = float((pa.astype(int) == y).mean())
    persist_pre = float(np.nanmean(tr[pa])) if pa.any() else float("nan")
    persist_prec = float(y[pa].mean()) if pa.any() else float("nan")
    return dict(base=base, auc=auc, acc=acc, flip_acc=flip_acc, prec_act=prec_act,
                persist_acc=persist_acc, persist_pre=persist_pre, persist_prec=persist_prec,
                n_act=int(act.sum()), pre=pre, post=post,
                cut=str(pd.Timestamp(cut).date()), n_test=len(test))


def q5_eras(df, feat, pos, p, conf_hi=tm.CONF_HI):
    """Q5: after-cost economics per measurable era, on the time-series OOF predictions."""
    sub = df.iloc[pos]
    dt = pd.to_datetime(sub["datetime"]).to_numpy()
    tr = sub["trade_ret"].to_numpy()
    act = p >= conf_hi
    c = cost_frac()
    rows = []
    for name, a, b in ERAS:
        m = act & (dt >= np.datetime64(a)) & (dt < np.datetime64(b))
        n = int(m.sum())
        if n == 0:
            rows.append(dict(era=name, trades=0, exp_after=float("nan"), win=float("nan")))
            continue
        net = tr[m] - c
        rows.append(dict(era=name, trades=n, exp_after=float(net.mean()),
                         win=float((net > 0).mean())))
    return rows


def q6_selectivity(df, feat, pos, p, n_steps=12):
    """Q6: after-cost return per trade as the confidence threshold rises (selectivity curve)."""
    sub = df.iloc[pos]
    tr = sub["trade_ret"].to_numpy()
    c = cost_frac()
    base = float(df["label"].mean())
    thresholds = np.linspace(max(0.45, base), 0.90, n_steps)
    rows = []
    for thr in thresholds:
        act = p >= thr
        n = int(act.sum())
        net = (tr[act] - c)
        rows.append(dict(threshold=float(thr), trades=n,
                         exp_after=float(net.mean()) if n else float("nan"),
                         win=float((net > 0).mean()) if n else float("nan")))
    return rows


def _plot_selectivity(rows, title, out_png):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    t = [r["threshold"] for r in rows]
    e = [r["exp_after"] * 100 for r in rows]
    n = [r["trades"] for r in rows]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.axhline(0, color="#888", lw=0.8, ls="--")
    ax.plot(t, e, "-o", color="#1b9e77", label="after-cost return per trade (%)")
    ax.set_xlabel("confidence threshold (act-long when p >= threshold)")
    ax.set_ylabel("after-cost return per trade (%)", color="#1b9e77")
    ax2 = ax.twinx()
    ax2.plot(t, n, "-s", color="#7570b3", alpha=0.5, label="trades")
    ax2.set_ylabel("trades", color="#7570b3")
    ax.set_title(title)
    fig.tight_layout()
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    fig.savefig(out_png, dpi=140)
    plt.close(fig)
    return out_png


def run(df, feat, klines_root, label="", out_dir=None, n_splits=5):
    """All three diagnostics; returns a dict and (if out_dir) writes a markdown record + a PNG."""
    q1 = q1_pre_cost(df, feat, klines_root)
    pos, p = oof_proba(strong_model(), df[feat], df["label"], n_splits)
    q5 = q5_eras(df, feat, pos, p)
    q6 = q6_selectivity(df, feat, pos, p)
    rec = dict(q1=q1, q5=q5, q6=q6, label=label, n_oof=len(pos))
    if out_dir:
        rec["md"], rec["png"] = _write(rec, out_dir, label)
    return rec


def _write(rec, out_dir, label):
    cd = datetime.now(timezone.utc).strftime("%Y%m%d"); hd = f"{cd[:4]}-{cd[4:6]}-{cd[6:]}"
    run_dir = os.path.join(out_dir, hd); os.makedirs(run_dir, exist_ok=True)
    png = _plot_selectivity(rec["q6"], f"Selectivity -- {label}",
                            os.path.join(run_dir, f"edge-diagnostics-selectivity-{cd}.png"))
    q1 = rec["q1"]
    # Honest pre-cost gate for an imbalanced, class-balanced ranker: rank better than chance (AUC),
    # pick winners above the base rate (precision of acted trades), and make money before fees -- and
    # beat the 1-bar persistence rule. Raw accuracy vs the majority class is NOT the gate (a balanced
    # model trades accuracy for minority recall), only reported for transparency.
    beats_base = (q1["auc"] > 0.50) and (q1["prec_act"] > q1["base"]) and (q1["pre"] > 0)
    beats_persist = q1["pre"] > q1["persist_pre"]
    gate = beats_base and beats_persist
    L = [f"# Edge diagnostics ({hd}) -- {label}\n",
         "## Q1. Pre-cost edge (held-out, fees stripped)",
         f"- base rate {q1['base']:.3f} (majority-class accuracy {q1['flip_acc']:.3f}, informational only)",
         f"- model: AUC {q1['auc']:.3f} (vs 0.50), accuracy {q1['acc']:.3f}",
         f"- model picks: precision {q1['prec_act']:.3f} vs base {q1['base']:.3f}  ->  beats the real balance: "
         f"{q1['prec_act'] > q1['base']}",
         f"- 1-bar persistence baseline: precision {q1['persist_prec']:.3f}, pre-cost {q1['persist_pre']*100:+.3f}%/trade",
         f"- model pre-cost mean return per acted trade {q1['pre']*100:+.3f}% on {q1['n_act']:,} trades; "
         f"after-cost {q1['post']*100:+.3f}% (cost {tm.COST_PCT:.2f}% round trip)",
         f"- **gate: {'PASS - a pre-cost edge exists to chase' if gate else 'FAIL - no pre-cost edge; the problem is features/architecture, not costs'}** "
         f"(beats base {beats_base}, beats persistence {beats_persist})\n",
         "## Q5. Edge stability across eras (after-cost, time-series out-of-fold)",
         "| era | trades | after-cost / trade | win rate |", "| --- | --- | --- | --- |"]
    for r in rec["q5"]:
        ea = f"{r['exp_after']*100:+.3f}%" if r["trades"] else "-"
        wr = f"{r['win']:.2f}" if r["trades"] else "-"
        L.append(f"| {r['era']} | {r['trades']:,} | {ea} | {wr} |")
    L += ["\n## Q6. Selectivity (after-cost return per trade vs confidence threshold)",
          f"![selectivity]({os.path.basename(png)})\n",
          "| threshold | trades | after-cost / trade | win rate |", "| --- | --- | --- | --- |"]
    for r in rec["q6"]:
        ea = f"{r['exp_after']*100:+.3f}%" if r["trades"] else "-"
        wr = f"{r['win']:.2f}" if r["trades"] else "-"
        L.append(f"| {r['threshold']:.3f} | {r['trades']:,} | {ea} | {wr} |")
    rising = [r for r in rec["q6"] if r["trades"]]
    verdict = ("rises - selectivity helps" if len(rising) >= 2 and rising[-1]["exp_after"] > rising[0]["exp_after"]
               else "flat/falls - selectivity does not rescue it")
    L.append(f"\n**Selectivity reading:** after-cost return per trade {verdict}.\n")
    md = os.path.join(run_dir, f"edge-diagnostics-{cd}.md")
    open(md, "w").write("\n".join(L) + "\n")
    return md, png


def main():
    p = argparse.ArgumentParser(description="Edge diagnostics (Q1 pre-cost, Q5 regimes, Q6 selectivity)")
    p.add_argument("--interval", default="4h", help="decision frame: 5m, 15m, 1h, 4h, 1d")
    p.add_argument("--dataset", default=None, help="defaults to the interval's dataset_<frame>_allmarket.parquet")
    p.add_argument("--out", default=os.path.join(tm.OUT, "AA-evals"))
    p.add_argument("--cv-splits", type=int, default=5)
    a = p.parse_args()
    bd.configure(a.interval)
    path = a.dataset or bd.DATASET_PATH
    df = t1.load(path)
    feat = bd.feature_columns(df)
    print(f"edge diagnostics on {len(df):,} in-sample rows, {len(feat)} features ({bd.INTERVAL} frame)\n")
    rec = run(df, feat, bd.DEFAULT_KLINES_ROOT, label=f"{bd.INTERVAL} all-market", out_dir=a.out,
              n_splits=a.cv_splits)
    q1 = rec["q1"]
    print(f"Q1 pre-cost: AUC {q1['auc']:.3f}, acc {q1['acc']:.3f} vs flip {q1['flip_acc']:.3f} / "
          f"persist {q1['persist_acc']:.3f}; pre {q1['pre']*100:+.3f}% after {q1['post']*100:+.3f}%/trade")
    print("record:", rec["md"])


if __name__ == "__main__":
    main()
