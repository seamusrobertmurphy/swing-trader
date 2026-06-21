"""1h-frame training and honest after-fee scoring (all-market frame).

Thin sibling of train_model.py. It reuses the SAME estimator list, the SAME evaluate()
and confidence filter, and the SAME cost constants, so the 1h and daily tracks can never
disagree on method. The only differences are the 1h-specific data handling, per the
2026-06-21 data standards (tasks/data-standards.md):

  - Loads the 1h dataset (build_dataset_1h.DATASET_PATH), time column `datetime`.
  - Selects features by the `f_` prefix (the in-house 1h feature set), not a fixed list.
  - Trains only on the point-in-time `in_sample` rows.
  - Split: hold out the final OOS_DAYS (~1 year) out-of-sample, train on ALL prior
    history (years, not capped), with an embargo equal to the label horizon so the last
    training labels cannot peek across the cut. The test set is scored once.

The daily train_model.py is untouched and remains the 1d path. Writes the same AA-evals
record. Plain ASCII; no orders; honest GO/NO-GO.
"""
from __future__ import annotations

import math
import os

import pandas as pd

import train_model as tm          # build_models, evaluate, CONF_HI/LO, COST_PCT, OUT, HAVE_LGBM
import build_dataset_1h as b1     # DATASET_PATH, LABEL, BARS_PER_DAY, feature_columns
import eval_report

OOS_DAYS = 365                                                    # >= 1 year held out
EMBARGO_DAYS = max(1, math.ceil(b1.LABEL["horizon_bars"] / b1.BARS_PER_DAY))  # = label horizon
REGIME_FEATURE = "f_wc_rv_long"   # 1h volatility proxy for Metric 3 regime-stratified AUC


def load(path: str = b1.DATASET_PATH) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["datetime"]).sort_values("datetime").reset_index(drop=True)
    if "in_sample" in df.columns:
        df = df[df["in_sample"]].reset_index(drop=True)
    return df


def split(df: pd.DataFrame, oos_days: int = OOS_DAYS, embargo_days: int = EMBARGO_DAYS):
    """Hold out the final `oos_days` out-of-sample; train on ALL prior history; embargo the
    label horizon at the cut so training labels (which look forward) cannot peek past it."""
    cut = df["datetime"].max() - pd.Timedelta(days=oos_days)
    embargo = pd.Timedelta(days=embargo_days)
    train = df[df["datetime"] <= cut - embargo].copy()
    test = df[df["datetime"] > cut].copy()
    return train, test, cut


def main(path: str = b1.DATASET_PATH, out_dir: str | None = None, only_models: list | None = None):
    df = load(path)
    feat = b1.feature_columns(df)
    train, test, cut = split(df)
    if len(train) == 0 or len(test) == 0:
        raise SystemExit(f"empty split (train {len(train)}, test {len(test)}); need >1yr+horizon of history")

    Xtr, ytr = train[feat], train["label"]
    Xte, yte = test[feat], test["label"]
    base_tr, base_te = ytr.mean(), yte.mean()

    span = lambda d: f"{d['datetime'].min().date()} -> {d['datetime'].max().date()}"
    lines = ["trader 1h all-market buy-signal model -- honest train/test report",
             "=" * 60,
             f"features ({len(feat)}) selected by f_ prefix",
             f"split: hold out final {OOS_DAYS}d as OOS, embargo +/- {EMBARGO_DAYS}d, cut {pd.Timestamp(cut).date()}",
             f"train: {len(train):7d} rows  {span(train)}  base rate {base_tr:.3f}",
             f"test : {len(test):7d} rows  {span(test)}  base rate {base_te:.3f}"]

    models = tm.build_models(tm.HAVE_LGBM)
    if only_models:
        keep = {m.lower() for m in only_models}
        models = [(n, mdl) for (n, mdl) in models if any(k in n.lower() for k in keep)]
    if not models:
        raise SystemExit(f"no models matched {only_models}")
    if not tm.HAVE_LGBM:
        lines.append("(LightGBM not installed: skipped Tier 1.)")

    scored = []
    for name, mdl in models:
        prec, m = tm.evaluate(name, mdl, Xtr, ytr, Xte, yte, base_te, lines)
        scored.append((prec, name, mdl, m))

    _, best_name, _, best = max(scored, key=lambda t: t[0])
    margin = best["prec"] - base_te
    go = (best["prec"] > base_te + 0.05) and (best["auc"] > 0.55)
    verdict = "GO (edge survives out-of-sample)" if go else "NO-GO (no demonstrable edge -- do not trade)"
    lines += ["\n" + "=" * 60,
              f"chosen model: {best_name} (test buy-precision {best['prec']:.3f}, "
              f"base rate {base_te:.3f}, lift {margin:+.3f}, AUC {best['auc']:.3f})",
              f"HONESTY GATE: {verdict}",
              "Note: Metric 2 (P&L after costs) in the AA-evals record is the deciding number."]
    print("\n".join(lines))

    meta = dict(dataset_rows=len(df), n_features=len(feat), train_rows=len(train),
                test_rows=len(test), base_rate=float(base_te),
                cut=str(pd.Timestamp(cut).date()), embargo=EMBARGO_DAYS,
                conf_hi=tm.CONF_HI, conf_lo=tm.CONF_LO, chosen=best_name,
                verdict="GO" if go else "NO-GO",
                regime_vol=test[REGIME_FEATURE].tolist() if REGIME_FEATURE in test.columns else None,
                trade_ret=test["trade_ret"].tolist() if "trade_ret" in test.columns else None,
                cost_pct=tm.COST_PCT)
    out = out_dir or os.path.join(tm.OUT, "AA-evals")
    rec = eval_report.write_comparison(out, [m for (_, _, _, m) in scored], yte, meta)
    print("evaluation record:", rec["md"])


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Train + score the 1h all-market model")
    p.add_argument("--dataset", default=b1.DATASET_PATH)
    p.add_argument("--out", default=None, help="AA-evals dir (default: outputs/AA-evals)")
    p.add_argument("--models", nargs="+", default=None,
                   help="subset of model names to run, e.g. LightGBM (default: all three)")
    a = p.parse_args()
    main(a.dataset, a.out, a.models)
