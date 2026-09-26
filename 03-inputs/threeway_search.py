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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--coins", nargs="+", default=COINS)
    ap.add_argument("--frames", nargs="+", default=FRAMES)
    ap.add_argument("--horizons", nargs="+", type=int, default=HORIZONS)
    args = ap.parse_args()

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
