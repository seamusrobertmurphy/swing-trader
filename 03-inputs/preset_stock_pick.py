"""Choose each preset's stocks from the 20 the demo offers, on their test-year result.

    .venv/bin/python 03-inputs/preset_stock_pick.py

Operator request, 30 September 2026. Every preset's stock version had been given
AAPL, MSFT and NVDA, typed in on 26 September without any test behind them. Each
preset is now run on all 20 stocks as a user's run is (demo_run.build_frame, the
screen, the cost floor and the preset's own model), and the stocks are ranked by
what the model's most confident fifth earned after cost on walk-forward folds
inside the training years: four expanding folds, each fitted on the years before
it with the horizon as an embargo and scored on the next block. The three best
stocks with at least 20 such candles were kept at first (record of 30 September
2026, 17:00 UTC). The operator then chose, the same day, to pick on the test year
instead: "we definitely want to pick the presents based on best test results."
The model is fitted on the training years and scored once on the test year, and
the three stocks whose candles in the pooled top fifth of ratings earned most
after cost, with at least 10 such candles, are chosen. The training-fold ranking
is kept in the record beside it. Because the test year chose them, its figures
for the chosen stocks are not a fair test; the paper trades that settle after the
choice are the check.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench_config as bc          # noqa: E402
import bench_run as br             # noqa: E402
import demo_run as dr              # noqa: E402
import demo_scan as ds             # noqa: E402
import train_model_1h as t1        # noqa: E402

FOLDS = 4
KEEP = 3
MIN_CANDLES = 20
MIN_TEST = 10


def prepared(cfg):
    df, _, feats = dr.build_frame(cfg, log=lambda *_: None)
    d, _ = br.apply_screen(cfg, df.copy(), log=lambda *_: None)
    f = br.choose_features(cfg, feats, log=lambda *_: None)
    lb = cfg["label"]
    if lb["kind"] == "three-way":
        d["label"] = dr._three_way(d["ret3"].to_numpy(float), float(lb["flat_band"]))
    gap = max(1, int(np.ceil(int(lb["horizon_bars"]) / bc.bars_per_day(cfg["data"]["frame"]))))
    train, test, cut = t1.split(d, oos_days=int(cfg["split"]["holdout_days"]), embargo_days=gap)
    train, test, _ = dr.floors(cfg, train, test, log=lambda *_: None)
    return train, test, f, gap, cut


def fit(cfg, rows, f):
    name = cfg["model"]["estimators"][0]
    est = br.make_estimator(name, cfg["model"]["class_weight"], (cfg["model"].get("params") or {}).get(name))
    est.fit(rows[f], rows["label"])
    return est


def earned(cfg, rows):
    ret = "ret3" if cfg["label"]["kind"] == "three-way" else "trade_ret"
    return rows[ret].to_numpy(float) - dr.cost_of("equity")


def top_fifth(scores, money, sym):
    """Per stock, what its candles in the pooled top fifth of ratings earned."""
    top = scores >= np.quantile(scores, 0.8)
    t = pd.DataFrame(dict(sym=sym[top], money=money[top]))
    return t.groupby("sym")["money"].agg(["mean", "count"])


def pick(key, entry):
    cfg, _ = dr.sanitize(ds.as_form(entry["equity"]))
    cfg["data"]["symbols"] = " ".join(dr.STOCKS)
    train, test, f, gap, cut = prepared(cfg)
    col = "symbol" if "symbol" in train.columns else "coin"
    days = np.sort(train["datetime"].unique())
    edges = [days[int(len(days) * k / (FOLDS + 1))] for k in range(1, FOLDS + 1)] + [days[-1] + np.timedelta64(1, "s")]
    s_all, m_all, y_all = [], [], []
    for a, b in zip(edges[:-1], edges[1:]):
        fit_rows = train[train["datetime"] < a - pd.Timedelta(days=gap)]
        score_rows = train[(train["datetime"] >= a) & (train["datetime"] < b)]
        if len(fit_rows) < 200 or len(score_rows) < 40:
            continue
        est = fit(cfg, fit_rows, f)
        s_all.append(dr.rating(cfg, est, score_rows[f]))
        m_all.append(earned(cfg, score_rows))
        y_all.append(score_rows[col].to_numpy())
    folds = top_fifth(np.concatenate(s_all), np.concatenate(m_all), np.concatenate(y_all))
    folds = folds[folds["count"] >= MIN_CANDLES].sort_values("mean", ascending=False)
    by_folds = list(folds.index[:KEEP])

    est = fit(cfg, train, f)
    ts, tm, ty = dr.rating(cfg, est, test[f]), earned(cfg, test), test[col].to_numpy()
    edge = np.quantile(ts, 0.8)
    ranked = top_fifth(ts, tm, ty)
    ranked = ranked[ranked["count"] >= MIN_TEST].sort_values("mean", ascending=False)
    chosen = list(ranked.index[:KEEP])
    mine = np.isin(ty, chosen)
    check = dict(
        chosen_top_fifth=float(tm[mine & (ts >= edge)].mean()) if (mine & (ts >= edge)).any() else None,
        chosen_candles=int((mine & (ts >= edge)).sum()),
        all_top_fifth=float(tm[ts >= edge].mean()), all_candles=int((ts >= edge).sum()),
        chosen_every=float(tm[mine].mean()), all_every=float(tm.mean()))
    return dict(key=key, label=entry["label"], model=cfg["model"]["estimators"][0], kind=cfg["label"]["kind"],
                chosen=chosen, basis="test year", chosen_by_training_folds=by_folds, cut=str(cut.date()),
                test_ranking=[dict(symbol=s, top_fifth=float(r["mean"]), candles=int(r["count"]))
                              for s, r in ranked.iterrows()],
                folds=[dict(symbol=s, top_fifth=float(r["mean"]), candles=int(r["count"])) for s, r in folds.iterrows()],
                test=check)


def main() -> int:
    presets = json.loads(ds.PRESET_FILE.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    folder = bc.REPO / "04-outputs" / "AA-evals" / now.strftime("%Y-%m-%d")
    folder.mkdir(parents=True, exist_ok=True)
    stem = folder / f"preset-stocks-{now:%Y%m%d-%H%M%S}"
    out = []
    for key in ("best", "threeway", "quick"):
        r = pick(key, presets[key])
        print(r["label"], r["chosen"], json.dumps(r["test"]), flush=True)
        out.append(r)
        stem.with_suffix(".json").write_text(json.dumps(dict(stamped=now.isoformat(), results=out), indent=1))
    pc = lambda v: "" if v is None else f"{100 * v:+.2f}"          # noqa: E731
    L = [f"# Preset stocks, {now:%Y-%m-%d}", "",
         f"Record `{stem.name}.json`, written by `03-inputs/preset_stock_pick.py`. Each preset's stock version was "
         f"run on the 20 stocks the demo offers, fitted on the training years and scored once on the test year. The "
         f"{KEEP} stocks whose candles in the model's most confident fifth earned most after cost in the test year, "
         f"with at least {MIN_TEST} such candles, were chosen, at the operator's instruction of 30 September 2026. "
         "The test year chose them, so its figures for them are not a fair test; the paper trades that settle "
         f"afterwards are. The ranking on {FOLDS} walk-forward folds inside the training years is given beside it. "
         "Money is per cent per candle after cost, over overlapping holds.", ""]
    for r in out:
        t = r["test"]
        L += [f"## {r['label']}", "",
              f"{r['model']}, {r['kind']} outcome. Chosen on the test year after {r['cut']}: "
              f"{', '.join(r['chosen'])}, whose top fifth earned {pc(t['chosen_top_fifth'])} "
              f"({t['chosen_candles']} candles) against {pc(t['all_top_fifth'])} on all 20 ({t['all_candles']}). "
              f"The training folds would have chosen {', '.join(r['chosen_by_training_folds'])}.", "",
              "| Stock | Top fifth, test year % | Candles | Top fifth, training folds % | Candles |",
              "|---|---|---|---|---|"]
        tf = {x["symbol"]: x for x in r["folds"]}
        L += [f"| {x['symbol']} | {pc(x['top_fifth'])} | {x['candles']} | "
              f"{pc(tf[x['symbol']]['top_fifth']) if x['symbol'] in tf else ''} | "
              f"{tf[x['symbol']]['candles'] if x['symbol'] in tf else ''} |" for x in r["test_ranking"]]
        L.append("")
    stem.with_suffix(".md").write_text("\n".join(L), encoding="utf-8")
    print(stem.with_suffix(".md"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
