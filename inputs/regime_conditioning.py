"""Regime-conditioning ablation (handoff Part 2): does giving ONE model the observable regime as input
features lift or stabilize the after-cost edge, versus a switchboard of per-regime models?

The handoff's preferred design is to condition a single model on current volatility and trend state
rather than detect-and-swap. build_dataset_1h.regime_block emits that state as the `f_rg_` family
(trailing-vol level + its own-history percentile, trend drift, Kaufman efficiency, up/down breadth,
trailing return, and the BTC market regime), all causal and scale-invariant. This module trains the
same strong model WITH and WITHOUT that block and compares them on the cost-aware, per-era scoreboard,
so the question "did conditioning on regime help" gets a number rather than an opinion.

If the dataset predates the block (no `f_rg_` columns), the features are recomputed from each coin's
klines on the fly, so the ablation runs without waiting for a full rebuild.

Native Python; reuses edge_diagnostics (split, OOF, eras, cost). Writes outputs/AA-evals/<date>/
regime-conditioning-*.md. Run on the .venv:
    .venv/bin/python inputs/regime_conditioning.py --interval 4h     # or 5m once that data is built
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import roc_auc_score

import build_dataset_1h as bd
import train_model as tm
import train_model_1h as t1
import edge_diagnostics as ed
import monte_carlo_1h as mc


def attach_regime(df, klines_root):
    """Return (df_with_rg, rg_cols). If the dataset already carries f_rg_ columns, use them; else
    recompute regime_block from each coin's klines and align by datetime (so the ablation is testable
    before a full rebuild)."""
    rg_cols = [c for c in df.columns if c.startswith("f_rg_")]
    if rg_cols:
        return df, rg_cols
    btc = bd.load_btc_series(klines_root)
    parts = []
    for sym, sub in df.groupby("symbol"):
        o = bd.load_coin(klines_root, sym.replace("/", ""))
        if o.empty:
            continue
        rg = pd.DataFrame(bd.regime_block(o, btc))
        rg["datetime"] = pd.to_datetime(o["datetime"]).values
        merged = sub[["datetime"]].merge(rg, on="datetime", how="left")
        merged.index = sub.index
        parts.append(merged.drop(columns=["datetime"]))
    rgall = pd.concat(parts).reindex(df.index)
    rg_cols = list(rgall.columns)
    df = pd.concat([df, rgall], axis=1)
    return df, rg_cols


def _score(df, feats, n_splits, conf_hi=tm.CONF_HI):
    """Held-out Q1 numbers + the per-era OOF after-cost economics for one feature set."""
    train, test, cut = t1.split(df)
    m = clone(ed.strong_model()).fit(train[feats], train["label"])
    p = m.predict_proba(test[feats])[:, 1]
    y = test["label"].to_numpy().astype(int)
    tr = test["trade_ret"].to_numpy()
    act = p >= conf_hi
    c = ed.cost_frac()
    pos, po = ed.oof_proba(ed.strong_model(), df[feats], df["label"], n_splits)
    eras = ed.q5_eras(df, feats, pos, po)
    nz = [e["exp_after"] for e in eras if e["trades"]]
    return dict(auc=float(roc_auc_score(y, p)) if len(np.unique(y)) > 1 else float("nan"),
                base=float(y.mean()),
                prec=float(y[act].mean()) if act.any() else float("nan"),
                pre=float(np.nanmean(tr[act])) if act.any() else float("nan"),
                post=float(np.nanmean(tr[act]) - c) if act.any() else float("nan"),
                n_act=int(act.sum()),
                trades_after=(tr[act] - c).astype(float),   # held-out confident-trade after-fee returns
                eras=eras,
                era_mean=float(np.mean(nz)) if nz else float("nan"),
                era_worst=float(np.min(nz)) if nz else float("nan"),
                era_pos=int(sum(x > 0 for x in nz)), era_n=len(nz))


def run(df, feat, klines_root, label="", out_dir=None, n_splits=5):
    df, rg_cols = attach_regime(df, klines_root)
    base_feat = [f for f in feat if not f.startswith("f_rg_")]
    cond_feat = base_feat + rg_cols
    base = _score(df, base_feat, n_splits)
    cond = _score(df, cond_feat, n_splits)
    rec = dict(label=label, rg_cols=rg_cols, base=base, cond=cond,
               n_base=len(base_feat), n_cond=len(cond_feat))
    if out_dir:
        rec["md"] = _write(rec, out_dir, label)
    return rec


def _row(d):
    return (f"AUC {d['auc']:.3f} | picks {d['prec']:.3f} vs base {d['base']:.3f} | "
            f"after-cost {d['post']*100:+.3f}%/trade on {d['n_act']:,} | "
            f"eras: mean {d['era_mean']*100:+.3f}%, worst {d['era_worst']*100:+.3f}%, "
            f"{d['era_pos']}/{d['era_n']} positive")


def _write(rec, out_dir, label):
    cd = datetime.now(timezone.utc).strftime("%Y%m%d"); hd = f"{cd[:4]}-{cd[4:6]}-{cd[6:]}"
    run_dir = os.path.join(out_dir, hd); os.makedirs(run_dir, exist_ok=True)
    b, c = rec["base"], rec["cond"]
    lift_post = c["post"] - b["post"]
    lift_worst = c["era_worst"] - b["era_worst"]
    lift_mean = c["era_mean"] - b["era_mean"]
    stability = (lift_worst > 0) or (c["era_pos"] > b["era_pos"]) or (lift_mean > 0)
    edge = lift_post > 0
    L = [f"# Regime conditioning ablation ({hd}) -- {label}\n",
         "Handoff Part 2: one model conditioned on observable regime state (the `f_rg_` block) vs the "
         "same model without it. Higher after-cost expectancy or a better worst-era (less reliance on "
         "one regime) means conditioning helps.\n",
         f"- regime block: {len(rec['rg_cols'])} features {rec['rg_cols']}",
         f"- features: baseline {rec['n_base']}, conditioned {rec['n_cond']}\n",
         "| model | held-out | after-cost/trade | era mean | era worst | eras positive |",
         "| --- | --- | --- | --- | --- | --- |",
         f"| baseline (no regime) | AUC {b['auc']:.3f}, picks {b['prec']:.3f}/base {b['base']:.3f} | "
         f"{b['post']*100:+.3f}% | {b['era_mean']*100:+.3f}% | {b['era_worst']*100:+.3f}% | {b['era_pos']}/{b['era_n']} |",
         f"| conditioned (+f_rg_) | AUC {c['auc']:.3f}, picks {c['prec']:.3f}/base {c['base']:.3f} | "
         f"{c['post']*100:+.3f}% | {c['era_mean']*100:+.3f}% | {c['era_worst']*100:+.3f}% | {c['era_pos']}/{c['era_n']} |",
         f"\n**Effect of conditioning** (two separate questions): cross-era STABILITY "
         f"{'IMPROVES' if stability else 'does not improve'} (worst-era {lift_worst*100:+.3f}pp, "
         f"era-mean {lift_mean*100:+.3f}pp, eras-positive {c['era_pos']-b['era_pos']:+d}); after-cost "
         f"EDGE {'improves' if edge else 'does not lift'} ({lift_post*100:+.3f}pp/trade). The point of "
         "Part 2 is the first: a model that generalizes across regimes rather than memorizing one. Both "
         "remain subject to the after-fee GO/NO-GO bar.\n",
         "## Per-era after-cost (conditioned model)",
         "| era | trades | after-cost/trade | win |", "| --- | --- | --- | --- |"]
    for e in c["eras"]:
        ea = f"{e['exp_after']*100:+.3f}%" if e["trades"] else "-"
        wr = f"{e['win']:.2f}" if e["trades"] else "-"
        L.append(f"| {e['era']} | {e['trades']:,} | {ea} | {wr} |")
    # Monte Carlo robustness of the conditioned model's held-out confident trades: the Stability gate
    # applied to the training regime itself -- is the conditioned edge robust, or one lucky path?
    ct = np.asarray(c.get("trades_after", []), float)
    if len(ct) >= 20:
        s = mc.summary(ct)
        L += ["\n## Monte Carlo robustness (conditioned model, held-out confident trades)",
              f"{len(ct):,} after-fee per-trade returns x {s['n_sims']:,} sims. ROBUST requires total "
              f"P5 > 0, p(loss) < 5%, and sign-flip p-value < 0.05.",
              "| metric | actual | P5 (worst) | median |",
              "| --- | --- | --- | --- |",
              f"| total return | {s['actual_total']:+.2%} | {s['total_p5']:+.2%} | {s['total_p50']:+.2%} |",
              f"| max drawdown | {s['actual_maxdd']:.2%} | {s['maxdd_worst5']:.2%} | {s['maxdd_p50']:.2%} |",
              f"\n- p(loss) **{s['prob_loss']:.1%}**, sign-flip p-value **{s['perm_pvalue']:.4f}**  ->  "
              f"**{mc.verdict(s)}**\n"]
    else:
        L += [f"\n## Monte Carlo robustness\n\n(only {len(ct)} confident held-out trades; need >=20 to "
              "resample. Use a frame/threshold that produces more picks.)\n"]
    md = os.path.join(run_dir, f"regime-conditioning-{cd}.md")
    open(md, "w").write("\n".join(L) + "\n")
    return md


def main():
    p = argparse.ArgumentParser(description="Regime-conditioning ablation (handoff Part 2)")
    p.add_argument("--interval", default="4h", help="decision frame: 5m, 15m, 1h, 4h, 1d")
    p.add_argument("--dataset", default=None)
    p.add_argument("--out", default=os.path.join(tm.OUT, "AA-evals"))
    p.add_argument("--cv-splits", type=int, default=5)
    a = p.parse_args()
    bd.configure(a.interval)
    df = t1.load(a.dataset or bd.DATASET_PATH)
    feat = bd.feature_columns(df)
    print(f"regime-conditioning ablation on {len(df):,} rows, {len(feat)} features ({bd.INTERVAL})\n")
    rec = run(df, feat, bd.DEFAULT_KLINES_ROOT, label=f"{bd.INTERVAL} all-market", out_dir=a.out,
              n_splits=a.cv_splits)
    print("baseline   :", _row(rec["base"]))
    print("conditioned:", _row(rec["cond"]))
    print("record:", rec["md"])


if __name__ == "__main__":
    main()
