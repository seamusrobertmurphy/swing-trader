"""Three-way outcome: bullish, bearish or break-even, scored on money after fees.

    .venv/bin/python 03-inputs/bench_three_way.py
    .venv/bin/python 03-inputs/bench_three_way.py --band 0.002 --models RF LogReg.glm

Operator idea, 16 September 2026. The barrier label calls every trade a win or a
loss, and a trade that ends inside the fee band is a loss to it. This label has
three classes read off the return a trade would actually make under the barrier
geometry: bullish when that return clears the band, bearish when it loses more
than the band, break-even in between. The band defaults to the 0.20 per cent
round-trip cost, so the middle class is exactly the zone where trading changes
nothing but the fee.

Scoring stays on money. Each model gives three probabilities a row; a trade is
taken when bullish is the most likely class, and the record reports the mean
return after cost of the trades taken against the mean of all rows, on walk-
forward folds inside the training window and once on the blind period. Log loss
and accuracy against always guessing the biggest class are reported beside it,
because a model can sort the three classes a little better than chance and
still not find trades that pay.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench_config as bc          # noqa: E402
import bench_run as br             # noqa: E402
import model_metrics as mm         # noqa: E402
import train_model as tm           # noqa: E402
import train_model_1h as t1        # noqa: E402

CLASSES = ("bearish", "break-even", "bullish")


def forward_return(df: pd.DataFrame, horizon: int) -> pd.Series:
    """Close-to-close return over the next `horizon` bars, per symbol.

    The panel carries no price, but f_hr_mom_<k> at bar t is close[t] over
    close[t-k] minus one, so the same column read k bars later is the forward
    return from t. Rows in the last k bars of a symbol have none.
    """
    col = f"f_hr_mom_{horizon}"
    if col not in df.columns:
        cands = sorted((int(c.split("_")[-1]), c) for c in df.columns if c.startswith("f_hr_mom_"))
        if not cands:
            raise SystemExit("no f_hr_mom_ column to rebuild a forward return from")
        horizon, col = min(cands, key=lambda kc: abs(kc[0] - horizon))
    d = df.sort_values(["symbol", "datetime"])
    fwd = d.groupby("symbol")[col].shift(-horizon)
    return fwd.reindex(df.index)


def three_way(trade_ret: pd.Series, band: float) -> pd.Series:
    """0 bearish, 1 break-even, 2 bullish, from a return and a band."""
    r = trade_ret.to_numpy(float)
    out = np.full(len(r), 1, dtype=int)
    out[r > band] = 2
    out[r < -band] = 0
    return pd.Series(out, index=trade_ret.index)


def _scores(y, proba, ret, cost):
    """Log loss, accuracy against the majority, and money for the trades taken."""
    from sklearn.metrics import log_loss
    proba = np.clip(proba, 1e-6, 1 - 1e-6)
    ll = float(log_loss(y, proba, labels=[0, 1, 2]))
    pred = proba.argmax(axis=1)
    acc = float((pred == y).mean())
    majority = float(np.bincount(y, minlength=3).max() / len(y))
    taken = pred == 2
    n_taken = int(taken.sum())
    after = float(ret[taken].mean() - cost) if n_taken else float("nan")
    base = float(ret.mean() - cost)
    # a stricter trade: bullish by a margin over bearish
    edge = proba[:, 2] - proba[:, 0]
    strict = edge > 0.15
    n_strict = int(strict.sum())
    after_strict = float(ret[strict].mean() - cost) if n_strict else float("nan")
    # The top fifth of rows by how far bullish beats bearish: always takes
    # trades, so learners can be compared on money even when none of them
    # ever calls bullish the likeliest class.
    top = edge >= np.quantile(edge, 0.8)
    n_top = int(top.sum())
    after_top = float(ret[top].mean() - cost) if n_top else float("nan")
    return dict(log_loss=ll, accuracy=acc, majority=majority,
                n_taken=n_taken, after_cost=after, base_after_cost=base,
                n_strict=n_strict, after_cost_strict=after_strict,
                n_top=n_top, after_cost_top=after_top,
                hit_bullish=float((y[taken] == 2).mean()) if n_taken else float("nan"))


def run(cfg: dict, estimators: list[str], band: float, cost: float, log=print,
        target: str = "forward") -> dict:
    df, available = br.load_frame(cfg, log=log)
    feats = br.choose_features(cfg, available, log=log)
    if target == "forward":
        df["ret3"] = forward_return(df, int(cfg["label"]["horizon_bars"]))
        df = df[df["ret3"].notna()].reset_index(drop=True)
    else:
        df["ret3"] = df["trade_ret"].astype(float)
    holdout = int(cfg["split"]["holdout_days"])
    embargo = int(cfg["split"]["embargo_bars"] or 0)
    train, test, cut = t1.split(df, oos_days=holdout,
                                embargo_days=max(1, embargo // 6) if embargo else t1.EMBARGO_DAYS)
    for d in (train, test):
        d["label3"] = three_way(d["ret3"], band)
    mix_tr = np.bincount(train["label3"], minlength=3) / len(train)
    mix_te = np.bincount(test["label3"], minlength=3) / len(test)
    log(f"split at {cut.date()}: {len(train):,} training rows, {len(test):,} blind; "
        f"class mix train {mix_tr.round(3).tolist()}, blind {mix_te.round(3).tolist()}")

    rows = []
    cw = cfg["model"]["class_weight"]
    per_model = cfg["model"].get("params") or {}
    folds = br.folds_of(len(train), int(cfg["split"]["folds"]), "expanding",
                        purge=int(cfg["split"].get("purge_bars") or 0))
    for name in estimators:
        est = br.make_estimator(name, cw, per_model.get(name))
        if est is None:
            log(f"  {name}: not available, skipped"); continue
        cv_p, cv_y, cv_r = [], [], []
        for tr, te in folds:
            e = br.make_estimator(name, cw, per_model.get(name))
            e.fit(train.iloc[tr][feats], train.iloc[tr]["label3"])
            p = e.predict_proba(train.iloc[te][feats])
            full = np.zeros((len(te), 3)); full[:, list(e.classes_)] = p
            cv_p.append(full); cv_y.append(train.iloc[te]["label3"].to_numpy())
            cv_r.append(train.iloc[te]["ret3"].to_numpy(float))
        cv = _scores(np.concatenate(cv_y), np.concatenate(cv_p), np.concatenate(cv_r), cost)
        est.fit(train[feats], train["label3"])
        p = est.predict_proba(test[feats])
        full = np.zeros((len(test), 3)); full[:, list(est.classes_)] = p
        blind = _scores(test["label3"].to_numpy(), full, test["ret3"].to_numpy(float), cost)
        rows.append(dict(model=name, cv=cv, blind=blind))
        log(f"  {name:12s} cv log loss {cv['log_loss']:.4f} acc {cv['accuracy']:.3f} vs majority "
            f"{cv['majority']:.3f}; trades taken {cv['n_taken']:,} at {cv['after_cost']*100:+.3f}% "
            f"after cost vs all rows {cv['base_after_cost']*100:+.3f}%; top fifth {cv['after_cost_top']*100:+.3f}%; "
            f"blind top fifth {blind['after_cost_top']*100:+.3f}% on {blind['n_top']:,} trades")
    return dict(rows=rows, cut=str(cut.date()), n_train=len(train), n_test=len(test),
                mix_train=mix_tr.tolist(), mix_blind=mix_te.tolist(), band=band, cost=cost,
                target=target)


def write_record(cfg, res, seconds, log=print) -> Path:
    stamp = datetime.now()
    day = br.RUNS / stamp.strftime("%Y-%m-%d"); day.mkdir(parents=True, exist_ok=True)
    md = mm.unclobbered(day / f"bench-3way-{stamp:%Y%m%d-%H%M%S}.md")
    pct = lambda v: "n/a" if v != v else f"{v*100:+.3f}%"
    L = [f"# Three-way outcome, {stamp:%d %B %Y %H:%M}", "",
         ("Bullish, bearish or break-even, read off the close-to-close return over the horizon"
          if res.get("target") == "forward" else
          "Bullish, bearish or break-even, read off the return a trade would make under the barrier")
         + f"; the break-even band is ±{res['band']*100:.2f} per cent of price and the "
         f"cost charged per trade is {res['cost']*100:.2f} per cent.", "",
         bc.describe(cfg), "",
         f"Split at {res['cut']}: {res['n_train']:,} training rows, {res['n_test']:,} blind. "
         f"Class mix in training, bearish / break-even / bullish: "
         + " / ".join(f"{v:.3f}" for v in res["mix_train"]) + "; blind: "
         + " / ".join(f"{v:.3f}" for v in res["mix_blind"]) + ".", "",
         "## Walk-forward, inside the training window", "",
         "A trade is taken when bullish is the most likely class. After cost is the mean "
         "return of those trades less the cost; all rows is the same for every row, the "
         "market's own drift. Strict takes only rows where bullish beats bearish by 0.15.", "",
         "| model | log loss | accuracy | majority | trades | after cost | all rows | strict trades | strict after cost | top fifth after cost |",
         "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for r in res["rows"]:
        c = r["cv"]
        L.append(f"| {r['model']} | {c['log_loss']:.4f} | {c['accuracy']:.3f} | {c['majority']:.3f} "
                 f"| {c['n_taken']:,} | {pct(c['after_cost'])} | {pct(c['base_after_cost'])} "
                 f"| {c['n_strict']:,} | {pct(c['after_cost_strict'])} | {pct(c['after_cost_top'])} |")
    L += ["", "## Blind period, scored once", "",
          "| model | log loss | accuracy | majority | trades | after cost | all rows | hit rate on bullish | strict trades | strict after cost | top fifth after cost |",
          "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for r in res["rows"]:
        b = r["blind"]
        L.append(f"| {r['model']} | {b['log_loss']:.4f} | {b['accuracy']:.3f} | {b['majority']:.3f} "
                 f"| {b['n_taken']:,} | {pct(b['after_cost'])} | {pct(b['base_after_cost'])} "
                 f"| {b['hit_bullish']:.3f} | {b['n_strict']:,} | {pct(b['after_cost_strict'])} | {pct(b['after_cost_top'])} |")
    best = max(res["rows"], key=lambda r: (r["blind"]["after_cost_top"] if r["blind"]["after_cost_top"] == r["blind"]["after_cost_top"] else -9))
    L += ["", "## Reading", "",
          f"Best on the blind period by money, taking the top fifth of rows by how far bullish beats "
          f"bearish: **{best['model']}** at {pct(best['blind']['after_cost_top'])} per trade after cost on "
          f"{best['blind']['n_top']:,} trades, against {pct(best['blind']['base_after_cost'])} for taking "
          f"every row. " + ("It made money after cost." if best["blind"]["after_cost_top"] > 0
                            else "It did not make money after cost."), "",
          f"Ran in {seconds:.0f} seconds.", "", "```json", json.dumps(cfg, indent=2, sort_keys=True), "```", ""]
    md.write_text("\n".join(L) + "\n", encoding="utf-8")
    md.with_suffix(".json").write_text(json.dumps(dict(stamped=stamp.isoformat(timespec="seconds"),
                                                       kind="three-way", config=cfg, **res),
                                                  indent=2, default=str), encoding="utf-8")
    log(f"record: {md.relative_to(bc.REPO)}")
    return md


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=None)
    ap.add_argument("--band", type=float, default=None, help="break-even half-width, share of price")
    ap.add_argument("--cost", type=float, default=tm.COST_PCT / 100.0, help="cost per trade, share of price")
    ap.add_argument("--estimators", nargs="*", default=None)
    ap.add_argument("--target", default="forward", choices=("forward", "barrier"),
                    help="forward: close-to-close over the horizon; barrier: the trade's return under the barrier")
    a = ap.parse_args()
    t0 = time.time()
    cfg = bc.load(Path(a.config) if a.config else None)
    band = a.band if a.band is not None else float(cfg["label"].get("flat_band") or 0.002)
    ests = a.estimators or cfg["model"]["estimators"] or ["LogReg.glm", "RF", "HistGBM"]
    print(bc.describe(cfg)); print()
    res = run(cfg, ests, band, a.cost, target=a.target)
    write_record(cfg, res, time.time() - t0)
    print(f"done in {time.time() - t0:.0f} seconds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
