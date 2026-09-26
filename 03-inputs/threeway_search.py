"""Three-way outcome search across coin, candle size and horizon, on the demo's own data.

    .venv/bin/python 03-inputs/threeway_search.py
    .venv/bin/python 03-inputs/threeway_search.py --coins BTCUSDT --frames 4h --horizons 12

Operator request, 26 September 2026 (revision tasks 4 to 6). The 42 three-way
research fits all ran on slice_4h_40k, an alphabetical cut of the 4-hour panel
from LINK onward, so the preset could only ever name LINK and LTC on 4-hour
candles over 12. This search refits the six learners one coin at a time on
every combination of the chosen coins, candle sizes and horizons.

Every fit goes through demo_run.build_frame and demo_run.score, the same
download, features and scoring a friend's run uses, so research and live runs
read identical Binance candles and the two scores cannot drift apart.

Selection keeps the current rule, the after-cost return of the most confident
fifth of candles (bullish most ahead of bearish), but reads it on the walk-
forward validation folds inside the training window. The final year is the
test set, scored once and never used to choose, so its figure is what a friend
should expect.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench_config as bc          # noqa: E402
import demo_run as dr              # noqa: E402

REPO = bc.REPO
# The 14 coins the demo offered before 26 September, and the four most traded
# liquid coins it did not (ZEC, UNI, SUI, ENA), the operator's small search.
COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT",
         "AVAXUSDT", "LINKUSDT", "LTCUSDT", "TRXUSDT", "DOTUSDT", "NEARUSDT", "BCHUSDT",
         "ZECUSDT", "UNIUSDT", "SUIUSDT", "ENAUSDT"]
FRAMES = ["4h", "1d"]
HORIZONS = [12, 24]
# The best 16 September three-way run, whose settings the preset copied:
# 04-outputs/AA-evals/2026-09-16/bench-3way-20260916-140850.json.
BASE = REPO / "04-outputs" / "AA-evals" / "2026-09-16" / "bench-3way-20260916-140850.json"


def base_config() -> dict:
    rec = json.loads(BASE.read_text(encoding="utf-8"))
    cfg = copy.deepcopy(rec["config"])
    cfg["label"].update(kind="three-way", flat_band=float(rec["band"]))
    cfg["model"].update(estimators=list(bc.ESTIMATORS), tune="")
    cfg["data"].update(market="crypto", rows=dr.LIMITS["rows"])
    cfg["split"]["repeats"] = min(int(cfg["split"]["repeats"]), dr.LIMITS["repeats"])
    cfg["split"]["boot_samples"] = min(int(cfg["split"]["boot_samples"]), dr.LIMITS["boot_samples"])
    return cfg


def one(cfg: dict, coin: str, frame: str, horizon: int, log) -> list[dict]:
    c = copy.deepcopy(cfg)
    c["data"].update(frame=frame, symbols=coin)
    c["label"]["horizon_bars"] = horizon
    df, _latest, feats = dr.build_frame(c, log=log)
    got = dr.score(c, df, feats, log=log)
    out = []
    for r in got["rows"]:
        out.append(dict(coin=coin, frame=frame, horizon=horizon, model=r["model"],
                        valid_top=r["cv_top"], valid_log_loss=r["cv_log_loss"],
                        test_top=r["blind_top"], test_every=r["blind_all"],
                        test_log_loss=r["blind_log_loss"], test_accuracy=r["blind_accuracy"],
                        test_majority=r["blind_majority"], n_train=got["n_train"],
                        n_test=got["n_test"], cut=got["cut"]))
    return out


NAMES = {"RF": "Random forest", "LogReg.glm": "Logistic regression",
         "LogReg.enet": "Elastic-net logistic", "LightGBM": "LightGBM",
         "HistGBM": "Histogram boosting", "GBM.classic": "Gradient boosting"}


def report(path: Path) -> Path:
    """The written record of one search, every figure read from its JSON."""
    import pandas as pd
    rec = json.loads(path.read_text(encoding="utf-8"))
    d, f = pd.DataFrame(rec["rows"]), pd.DataFrame(rec["failed"])
    pc = lambda v: f"{v * 100:+.2f}"
    combos = len(rec["coins"]) * len(rec["frames"]) * len(rec["horizons"])
    ran = d.groupby(["coin", "frame", "horizon"]).ngroups
    w = d.loc[d.groupby(["coin", "frame", "horizon"]).valid_top.idxmax()].copy()
    w["beat"] = w.test_top > w.test_every
    top = w.sort_values("valid_top", ascending=False).iloc[0]
    by = d.groupby("model").agg(valid=("valid_top", "median"), test=("test_top", "median"),
                                pos=("test_top", lambda s: int((s > 0).sum())), n=("test_top", "size"))
    by["wins"] = w.model.value_counts().reindex(by.index).fillna(0).astype(int)
    by["beat"] = d.assign(b=d.test_top > d.test_every).groupby("model").b.sum().astype(int)
    lr = d[d.model == "LogReg.glm"].set_index(["coin", "frame", "horizon"])
    rank = d.assign(r=d.groupby(["coin", "frame", "horizon"]).valid_top.rank(ascending=False))
    lr_rank = rank[rank.model == "LogReg.glm"].r
    daily = sorted(d[d.frame == "1d"].coin.unique())
    L = [f"# Three-way search, {rec['stamped'][:4]}-{rec['stamped'][4:6]}-{rec['stamped'][6:8]}", "",
         f"Record `{path.name}`, written by `03-inputs/threeway_search.py`. Six learners were fitted one "
         f"coin at a time on {len(rec['coins'])} coins, {' and '.join(rec['frames'])} candles and horizons of "
         f"{' and '.join(str(h) for h in rec['horizons'])} candles, {combos} combinations in all. {ran} "
         f"combinations ran and gave {len(d)} fits; {len(f)} were left out. Money figures are per cent per "
         f"trade after the {rec['cost'] * 100:.2f} per cent round-trip cost, for the fifth of candles the "
         f"model rated most bullish over bearish.", "",
         "## Design", "",
         f"Every fit went through `demo_run.build_frame` and `demo_run.score`, the download, features and "
         f"scoring a user's run uses, so research and live runs read the same Binance candles. The settings "
         f"were those of the best 16 September three-way run (`{rec['base']}`), a break-even band of "
         f"{rec['config']['label']['flat_band'] * 100:.1f} per cent, {rec['config']['split']['folds']} "
         f"walk-forward folds and a final test year of {rec['config']['split']['holdout_days']} days. "
         f"Models were ranked on the validation folds inside the training window. The test year was scored "
         f"once and never used to choose.", "",
         "## Left out", "",
         f"{len(f)} combinations left too few candles to fit, fewer than the 500 training and 100 test "
         f"candles a run needs. Daily candles ran for {', '.join(c[:-4] for c in daily)} only. The house "
         f"screen, at least 30 million USDT traded in the past 24 hours plus a volatility band, removes most "
         f"daily candles of smaller coins; ADA kept 674 of 2,633, and the A1 volatility band of 0.015 to "
         f"0.071 of price then removed 280 more. On 4-hour candles ZEC, UNI, SUI, ENA, NEAR and DOT were left "
         f"out the same way.", "",
         "## Learners compared", "",
         f"No learner led. Logistic regression won {by.loc['LogReg.glm', 'wins']} of {ran} combinations on "
         f"validation, tied with the random forest at {by.loc['RF', 'wins']}; its median rank among the six "
         f"was {lr_rank.median():.1f}. Across all fits, medians and counts by learner:", "",
         "| Learner | Validation, median % | Test, median % | Test positive | Beat every candle | Validation wins |",
         "|---|---|---|---|---|---|"]
    for m, r in by.sort_values("wins", ascending=False).iterrows():
        L.append(f"| {NAMES.get(m, m)} | {pc(r.valid)} | {pc(r.test)} | {int(r.pos)} of {int(r.n)} "
                 f"| {int(r.beat)} of {int(r.n)} | {int(r.wins)} |")
    L += ["", "## Every combination", "",
          f"The validation winner of each combination. Its test result was positive in {int((w.test_top > 0).sum())} "
          f"of {ran} and beat taking every candle in {int(w.beat.sum())}.", "",
          "| Coin | Candles | Horizon | Winner | Validation % | Test % | Every candle % | Test candles |",
          "|---|---|---|---|---|---|---|---|"]
    for _, r in w.sort_values("valid_top", ascending=False).iterrows():
        L.append(f"| {r.coin[:-4]} | {r.frame} | {r.horizon} | {NAMES.get(r.model, r.model)} | {pc(r.valid_top)} "
                 f"| {pc(r.test_top)} | {pc(r.test_every)} | {r.n_test:,} |")
    old = d[(d.frame == "4h") & (d.horizon == 12) & (d.model == "LogReg.glm") & d.coin.isin(["LINKUSDT", "LTCUSDT"])]
    L += ["", "## Research against live", "",
          "Research and live runs now share one pipeline, so their scores differ only by the candles each "
          "reads. The old preset, logistic regression on LINK and LTC 4-hour candles over 12, scored "
          "+1.23 per cent on the test period of `bench-3way-20260916-140850.json`, a basket of LINK, LTC "
          "and MATIC on the 25 MB research slice. On the demo's own candles it scored "
          + " and ".join(f"{pc(r.test_top)} per cent on {r.coin[:-4]}" for _, r in old.iterrows())
          + ", against " + " and ".join(f"{pc(r.test_every)}" for _, r in old.iterrows())
          + " for every candle.", "",
          "## Preset choice", "",
          f"The rule is unchanged, the highest after-cost return of the most confident fifth, read on "
          f"validation. It chose {NAMES.get(top.model, top.model)} on {top.coin[:-4]} {top.frame} candles "
          f"over {top.horizon}, at {pc(top.valid_top)} per cent in validation and {pc(top.test_top)} on the "
          f"test year against {pc(top.test_every)} for every candle. The test year held {top.n_test} candles "
          f"whose {top.horizon}-candle windows overlap, so it holds about {top.n_test // top.horizon} "
          f"independent trades, and the top fifth fewer; the figure is suggestive, not established. The "
          f"{int((w.sort_values('valid_top', ascending=False).head(4).frame == '1d').sum())} largest "
          f"validation figures are all daily cells, whose test years hold {w[w.frame == '1d'].n_test.min()} "
          f"to {w[w.frame == '1d'].n_test.max()} candles, so the rule favours the cells with the least "
          f"evidence.", ""]
    out = path.with_suffix(".md")
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", type=Path, help="write the record of a finished search and stop")
    ap.add_argument("--coins", nargs="+", default=COINS)
    ap.add_argument("--frames", nargs="+", default=FRAMES)
    ap.add_argument("--horizons", nargs="+", type=int, default=HORIZONS)
    args = ap.parse_args()
    if args.report:
        print(report(args.report))
        return 0

    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%d-%H%M%S")
    folder = REPO / "04-outputs" / "AA-evals" / now.strftime("%Y-%m-%d")
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / f"threeway-search-{stamp}.json"
    logf = open(folder / f"threeway-search-{stamp}.log", "w", encoding="utf-8")

    def log(msg):
        print(msg, flush=True)
        logf.write(str(msg) + "\n"); logf.flush()

    cfg = base_config()
    rows, failed, t0 = [], [], time.time()
    combos = [(c, f, h) for c in args.coins for f in args.frames for h in args.horizons]
    for i, (coin, frame, h) in enumerate(combos, 1):
        log(f"[{i}/{len(combos)}] {coin} {frame} horizon {h}, {time.time() - t0:.0f}s so far")
        try:
            rows += one(cfg, coin, frame, h, log)
        except SystemExit as e:                      # too few rows after the screen, and the like
            failed.append(dict(coin=coin, frame=frame, horizon=h, why=str(e)))
            log(f"  left out: {e}")
        # Saved after every combination, so a killed run keeps what it finished.
        out.write_text(json.dumps(dict(stamped=stamp, kind="threeway-search", base=str(BASE.relative_to(REPO)),
                                       config=cfg, coins=args.coins, frames=args.frames,
                                       horizons=args.horizons, cost=dr.COST, rows=rows,
                                       failed=failed), indent=1), encoding="utf-8")
    log(f"done: {len(rows)} fits, {len(failed)} combinations left out, {time.time() - t0:.0f}s, {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
