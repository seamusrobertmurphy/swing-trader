"""Money Flow Index as an entry gate: does skipping overbought candles help after cost?

    .venv/bin/python 03-inputs/mfi_gate_test.py

Operator request, 26 September 2026. The research note 02-runtime/01-trader-metrics
names the Money Flow Index as the strongest next corroboration, because it is the
only one that weighs volume. The gate keeps a candle only when its MFI, on 0 to 1,
is at or below a level: 1 keeps everything, 0.8 skips overbought candles, 0.5
keeps the lower half, 0.2 keeps only oversold ones.

Each preset is run as a user's run is, through demo_run.build_frame, the cost
floor and the preset's own model, fitted on the training years with the gate
applied and scored once on the test year. The record gives, per level, the test
candles kept, what every kept candle earned after cost and what the model's most
confident fifth earned, beside the same figures with the gate off.
"""

from __future__ import annotations

import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench_config as bc          # noqa: E402
import bench_run as br             # noqa: E402
import demo_run as dr              # noqa: E402
import demo_scan as ds             # noqa: E402
import train_model_1h as t1        # noqa: E402

LEVELS = [1.0, 0.8, 0.5, 0.2]
STOCKS = "AAPL MSFT NVDA JPM XOM WMT"


def cases() -> list[tuple[str, dict]]:
    p = json.loads(ds.PRESET_FILE.read_text(encoding="utf-8"))
    out = []
    for key in ("threeway", "quick", "best"):
        cfg, _ = dr.sanitize(ds.as_form(p[key]["crypto"]))
        out.append((f"{p[key]['label']}, crypto", cfg))
    cfg, _ = dr.sanitize(ds.as_form(p["quick"]["equity"]))
    cfg["data"]["symbols"] = STOCKS
    out.append((f"{p['quick']['label']}, stocks", cfg))
    return out


def one(cfg: dict, df, feats, level: float, log) -> dict:
    c = copy.deepcopy(cfg)
    c["screen"]["mfi_max"] = level
    d, _ = br.apply_screen(c, df.copy(), log=lambda *_: None)
    f = br.choose_features(c, feats, log=lambda *_: None)
    lb = c["label"]
    if lb["kind"] == "three-way":
        d["label"] = dr._three_way(d["ret3"].to_numpy(float), float(lb["flat_band"]))
    gap = max(1, int(np.ceil(int(lb["horizon_bars"]) / bc.bars_per_day(c["data"]["frame"]))))
    train, test, cut = t1.split(d, oos_days=int(c["split"]["holdout_days"]), embargo_days=gap)
    train, test, _ = dr.floors(c, train, test, log=log)
    if len(train) < 200 or len(test) < 40:
        return dict(level=level, train=len(train), test=len(test), why="too few candles")
    name = c["model"]["estimators"][0]
    est = br.make_estimator(name, c["model"]["class_weight"], (c["model"].get("params") or {}).get(name))
    est.fit(train[f], train["label"])
    _, earned, rec = dr.fifths(c, est, test, f)
    return dict(level=level, train=len(train), test=len(test), every=rec["every"],
                top=rec["top_fifth"], trades=len(test) // max(1, int(lb["horizon_bars"])), cut=str(cut.date()))


def main() -> int:
    now = datetime.now(timezone.utc)
    folder = bc.REPO / "04-outputs" / "AA-evals" / now.strftime("%Y-%m-%d")
    folder.mkdir(parents=True, exist_ok=True)
    stem = folder / f"mfi-gate-{now:%Y%m%d-%H%M%S}"
    results = []
    for label, cfg in cases():
        print(f"== {label}: {cfg['data']['frame']} candles of {cfg['data']['symbols']}")
        df, _, feats = dr.build_frame(cfg, log=lambda *_: None)
        rows = [one(cfg, df, feats, lv, log=print) for lv in LEVELS]
        results.append(dict(case=label, frame=cfg["data"]["frame"], symbols=cfg["data"]["symbols"],
                            horizon=int(cfg["label"]["horizon_bars"]), kind=cfg["label"]["kind"],
                            model=cfg["model"]["estimators"][0], rows=rows))
        stem.with_suffix(".json").write_text(json.dumps(dict(stamped=now.isoformat(), levels=LEVELS,
                                                             results=results), indent=1))
    pc = lambda v: "" if v is None else f"{v * 100:+.2f}"
    L = [f"# Money flow gate, {now:%Y-%m-%d}", "",
         f"Record `{stem.name}.json`, written by `03-inputs/mfi_gate_test.py`. Each preset was run as a "
         "user's run is, with the cost floor at the 80th percentile, and fitted with the Money Flow Index "
         "gate at each level. Money is per cent per trade after cost on the test year. Separate trades is "
         "the test candles divided by the horizon, because neighbouring trades overlap.", ""]
    for r in results:
        L += [f"## {r['case']}", "",
              f"{r['model']} on {r['frame']} candles of {r['symbols'].replace('USDT', '')}, {r['kind']} "
              f"outcome over {r['horizon']} candles.", "",
              "| MFI at most | Training candles | Test candles | Separate trades | Every candle % | Top fifth % |",
              "|---|---|---|---|---|---|"]
        for x in r["rows"]:
            L.append(f"| {x['level']:g} | {x['train']:,} | {x['test']:,} | {x.get('trades', '')} | "
                     f"{pc(x.get('every'))} | {pc(x.get('top'))} |")
        L.append("")
    stem.with_suffix(".md").write_text("\n".join(L), encoding="utf-8")
    print(stem.with_suffix(".md"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
