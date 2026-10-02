"""Scan: current signals from the three presets across a whole market.

    python 03-inputs/demo_scan.py --out site/data
    python 03-inputs/demo_scan.py --out site/data --market crypto --coins BTCUSDT ETHUSDT

Operator request, 26 September 2026 (round two, task 5): the home page ranks
current signals from the proven presets for the chosen market, ordered by
expected profit after cost, and says how many candidates it searched. A
scheduled workflow, demo-scan.yml, runs this every four hours.

For each preset and market it does four things.

1. Builds the preset's labelled candles for every symbol in the demo's list,
   through demo_run.build_frame, the same download and features a user's run
   reads, with the preset's own settings from demo_presets.json.
2. Fits the preset's model on the training window and scores the test year
   once. The test year's scores are cut into fifths, and each fifth's mean
   return after cost is what a score in that fifth has earned.
3. Refits on every labelled candle and rates the newest closed candle of each
   symbol. The expected move is the test-year mean of the fifth its score falls
   in. The call is BUY when the score clears the level that pays, as in
   demo_run.tickets, and that fifth earned money after cost on the test year;
   otherwise no trade, because the book never shorts.
4. Writes data/scan/latest.json with every signal, the preset's test-year
   record, and the last 180 closes of each symbol for the Compare chart.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench_config as bc          # noqa: E402
import bench_run as br             # noqa: E402
import build_dataset_1h as bd      # noqa: E402
import demo_run as dr              # noqa: E402
import train_model_1h as t1        # noqa: E402

PRESET_FILE = Path(__file__).resolve().parent / "demo_presets.json"
HISTORY = 180                      # closes kept per symbol for Compare
# Longer histories for A1's Explore chart, round two task 21, in their own file
# so the home page does not load them: two years of daily candles, 90 days of
# four-hour ones. Times are minutes since 1970 to keep the file small.
LONG = {"1d": 730, "4h": 540}
ROWS = 120_000                     # labelled candles per preset; the scan is not a user's run


def _bar(cfg: dict) -> float:
    """The score a call must beat: break-even for the barrier, 0 for three-way."""
    lb = cfg["label"]
    if lb["kind"] == "barrier":
        return float(lb["stop_atr"]) / (float(lb["stop_atr"]) + float(lb["target_atr"]))
    return 0.0


def _pays(cfg: dict, s: np.ndarray) -> np.ndarray:
    return s > _bar(cfg)


def scan_preset(key: str, cfg: dict, market: str, symbols: list[str], log=print) -> dict:
    cfg = copy.deepcopy(cfg)
    cfg["data"].update(market=market, symbols=" ".join(symbols), rows=ROWS)
    df, latest, feats = dr.build_frame(cfg, log=log)
    df, _ = br.apply_screen(cfg, df, log=log)
    feats = br.choose_features(cfg, feats, log=log)
    lb = cfg["label"]
    if lb["kind"] == "three-way":
        df["label"] = dr._three_way(df["ret3"].to_numpy(float), float(lb["flat_band"]))
    bpd = bc.bars_per_day(cfg["data"]["frame"])
    gap = max(1, int(np.ceil(int(lb["horizon_bars"]) / bpd)))
    train, test, cut = t1.split(df, oos_days=int(cfg["split"]["holdout_days"]), embargo_days=gap)
    train, test, floor = dr.floors(cfg, train, test, log=log)
    name = cfg["model"]["estimators"][0]
    params = (cfg["model"].get("params") or {}).get(name)
    est = br.make_estimator(name, cfg["model"]["class_weight"], params).fit(train[feats], train["label"])
    edges, earned, rec = dr.fifths(cfg, est, test, feats)
    record = dict(test_from=str(cut.date()), fifths=earned, model=name, **rec)
    # Refit on every labelled candle, as demo_run.tickets does, and rate the newest.
    est = br.make_estimator(name, cfg["model"]["class_weight"], params).fit(df[feats], df["label"])
    if latest.empty:
        return dict(record=record, signals=[])
    s_now = dr.rating(cfg, est, latest[feats])
    # The newest candle must clear the same cost floor and relative-volume rule.
    likely = _pays(cfg, s_now)
    passed = np.asarray(floor["keep"](latest) if len(floor) > 1 else np.ones(len(latest)), bool)
    pays = likely & passed
    frame, h = cfg["data"]["frame"], int(lb["horizon_bars"])
    candle = timedelta(minutes=bd._FRAME_MIN[frame])
    out = []
    for i, (_, row) in enumerate(latest.iterrows()):
        if market == "equity":
            opened = (pd.Timestamp(row["datetime"]).tz_localize("America/New_York")
                      + pd.Timedelta(hours=16)).tz_convert("UTC")
            expires = (opened.tz_convert("America/New_York") + pd.offsets.BDay(h)).tz_convert("UTC")
        else:
            opened = pd.Timestamp(row["datetime"]).tz_localize("UTC") + candle
            expires = opened + candle * h
        q = int(np.digitize([s_now[i]], edges)[0])
        # BUY needs both: the score clears the level that pays, and scores like
        # it earned money after cost on the test year.
        clears = earned[q] is not None and earned[q] > dr.edge_floor(cfg)
        buy = bool(pays[i]) and clears
        out.append(dict(symbol=row["symbol"], preset=key, frame=frame, horizon=h, model=name,
                        call="BUY" if buy else "NO TRADE", score=round(float(s_now[i]), 4),
                        confidence=q + 1, expected=earned[q], price=float(row["close"]),
                        atr=float(row["atr_frac"]), generated=opened.isoformat(),
                        rvol=round(float(np.exp(row["f_rv_slot"])), 2) if pd.notna(row.get("f_rv_slot")) else None,
                        spread=round(float(row["f_cost_spread"]), 4) if pd.notna(row.get("f_cost_spread")) else None,
                        expires=expires.isoformat(),
                        # Why this call, operator request of 30 September 2026: the three
                        # checks a scan applies (a scan has no top-third rule).
                        why=dict(group=q + 1, expected=earned[q], score=round(float(s_now[i]), 4),
                                 bar=round(_bar(cfg), 4), likely=bool(likely[i]), filters=bool(passed[i]),
                                 floor=dr.edge_floor(cfg), clears=bool(clears))))
    log(f"{key} {market}: {len(out)} rated, test year from {record['test_from']}, top fifth "
        f"{(record['top_fifth'] or 0) * 100:+.2f}% against {record['every'] * 100:+.2f}% for every candle")
    return dict(record=record, signals=out)


def history(market: str, frame: str, symbols: list[str], n: int = HISTORY, short: bool = True) -> dict:
    """The last closes and 24-hour volume of each symbol, from the files build_frame wrote."""
    out = {}
    for s in symbols:
        try:
            if market == "equity":
                import build_dataset_equity as be
                d = be.load_symbol(s)
                vol = d["close"] * d["volume"]
            else:
                d = bd.load_coin(str(dr.DATA_ROOT / bc.KLINE_ROOTS[frame]), s)
                vol = d["quote_volume"] if "quote_volume" in d.columns else d["close"] * d["volume"]
                vol = vol.rolling(bc.bars_per_day(frame), min_periods=1).sum()
        except Exception:                               # noqa: BLE001
            continue
        if d.empty:
            continue
        tail = d.tail(n)
        key = s if market == "equity" else f"{s[:-4]}/USDT"
        if short:
            out[key] = dict(t=[pd.Timestamp(x).strftime("%Y-%m-%dT%H:%M") for x in tail["datetime"]],
                            c=[round(float(x), 8) for x in tail["close"]],
                            volume24=float(vol.iloc[-1]))
        else:
            out[key] = dict(m=[int(pd.Timestamp(x).timestamp() // 60) for x in tail["datetime"]],
                            c=[float(f"{float(x):.6g}") for x in tail["close"]])
    return out


# Rotated test slots, round two task 12 of 26 September 2026: each scan adds one
# configuration per market from this grid, the one with the fewest forward
# tickets so far, so the whole grid is forward-tested rather than only the
# presets. It starts from the Quick and simple preset and changes these four.
GRID = dict(learner=list(bc.ESTIMATORS), kind=["barrier", "three-way"],
            frame=dict(crypto=["1h", "4h", "1d"], equity=["1d"]), horizon=[12, 24])
SUMMARY_URL = "https://seamusrobertmurphy.github.io/swing-trader/data/forward-summary.json"
NAMES = {"RF": "Random forest", "LogReg.glm": "Logistic regression", "LogReg.enet": "Elastic-net logistic",
         "LightGBM": "LightGBM", "HistGBM": "Histogram boosting", "GBM.classic": "Gradient boosting"}


def slot_id(market: str, frame: str, kind: str, horizon: int, learner: str) -> str:
    return f"rot:{market}:{frame}:{kind}:{horizon}:{learner}"


def rotation(market: str, base: dict) -> tuple[str, str, dict]:
    """The grid configuration with the fewest forward tickets, and its settings."""
    import itertools
    import urllib.request
    try:
        req = urllib.request.Request(SUMMARY_URL + f"?t={int(time.time())}",
                                     headers={"user-agent": "swing-trader-demo-scan"})
        with urllib.request.urlopen(req, timeout=30) as r:
            seen = {k: v.get("issued", 0) for k, v in json.loads(r.read()).get("configs", {}).items()}
    except Exception:                                   # noqa: BLE001
        seen = {}
    grid = list(itertools.product(GRID["frame"][market], GRID["kind"], GRID["horizon"], GRID["learner"]))
    turn = int(time.time() // (4 * 3600))              # breaks ties differently each scan
    pick = min(range(len(grid)), key=lambda i: (seen.get(slot_id(market, *grid[i]), 0), (i - turn) % len(grid)))
    frame, kind, horizon, learner = grid[pick]
    cfg = copy.deepcopy(base)
    cfg["data"]["frame"] = frame
    cfg["label"].update(kind=kind, horizon_bars=horizon)
    if kind == "three-way":
        cfg["label"]["flat_band"] = 0.01
    cfg["model"].update(estimators=[learner], params={}, tune="")
    size = {"1h": "1-hour", "4h": "4-hour", "1d": "1-day"}[frame]
    label = f"Test slot: {NAMES[learner]}, {'three-way' if kind == 'three-way' else 'win or loss'}, {size} over {horizon}"
    return slot_id(market, frame, kind, horizon, learner), label, cfg


def forward_tickets(cfg: dict, config: str, signals: list[dict], market: str) -> list[dict]:
    """Every signal as a paper ticket, settled hourly by demo_mark like a user's."""
    lb, now = cfg["label"], datetime.now(timezone.utc).isoformat(timespec="seconds")
    out = []
    for s in signals:
        t = dict(id=f"{config}|{s['symbol']}|{s['generated']}", config=config, market=market, frame=s["frame"],
                 symbol=s["symbol"], entry_time=s["generated"], entry_price=s["price"], horizon_bars=s["horizon"],
                 due=s["expires"], outcome=lb["kind"], model=s["model"], score=s["score"],
                 expected=s["expected"], confidence=s["confidence"], call=s["call"], issued=now, status="open",
                 why=s.get("why"))
        if lb["kind"] == "barrier":
            t.update(target=s["price"] * (1 + float(lb["target_atr"]) * s["atr"]),
                     stop=s["price"] * (1 - float(lb["stop_atr"]) * s["atr"]))
        out.append(t)
    return out


def as_form(cfg: dict) -> dict:
    """A preset's settings in the shape the page posts: model settings one field each."""
    c = copy.deepcopy(cfg)
    for model, ps in (c["model"].pop("params", None) or {}).items():
        c["model"].update({f"{model}.{k}": v for k, v in (ps or {}).items()})
    return c


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="the site's data folder")
    ap.add_argument("--market", choices=("crypto", "equity", "both"), default="both")
    ap.add_argument("--coins", nargs="+", default=None, help="a shorter list, for a trial")
    a = ap.parse_args()
    presets = json.loads(PRESET_FILE.read_text(encoding="utf-8"))
    # The volume floor reads the job's own downloads, as in demo_run.main.
    br._archive_root = lambda c: (dr.DATA_ROOT / "alpaca" / "daily" if c["data"].get("market") == "equity"
                                  else dr.DATA_ROOT / bc.KLINE_ROOTS[c["data"]["frame"]])
    t0, doc = time.time(), dict(generated=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                markets={})
    markets = ("crypto", "equity") if a.market == "both" else (a.market,)
    long_doc = dict(generated=doc["generated"], markets={})
    forward: list[dict] = []
    for market in markets:
        universe = (a.coins or dr.COINS) if market == "crypto" else dr.STOCKS
        m = dict(searched=len(universe), presets={}, signals=[], history={}, failed=[])
        runs = []
        for key, p in presets.items():
            cfg, _ = dr.sanitize(as_form(p[market]))
            runs.append((key, p["label"], cfg, f"preset:{key}:{market}"))
        base, _ = dr.sanitize(as_form(presets["quick"][market]))
        cid, label, cfg = rotation(market, base)
        runs.append(("rotation", label, cfg, cid))
        for key, label, cfg, cid in runs:
            try:
                got = scan_preset(key, cfg, market, universe)
            except (SystemExit, Exception) as e:                    # noqa: BLE001
                m["failed"].append(dict(preset=key, why=f"{type(e).__name__}: {e}"))
                print(f"{key} {market}: left out, {e}")
                continue
            for sig in got["signals"]:
                sig.update(config=cid, label=label)
            m["presets"][key] = dict(label=label, config=cid, frame=cfg["data"]["frame"],
                                     horizon=int(cfg["label"]["horizon_bars"]), **got["record"])
            m["signals"] += got["signals"]
            forward += forward_tickets(cfg, cid, got["signals"], market)
            frame = cfg["data"]["frame"]
            for sym, hist in history(market, frame, universe).items():
                m["history"].setdefault(sym, {})[frame] = hist
            if frame in LONG:
                for sym, hist in history(market, frame, universe, LONG[frame], short=False).items():
                    long_doc["markets"].setdefault(market, {}).setdefault(sym, {})[frame] = hist
        m["signals"].sort(key=lambda r: -(r["expected"] if r["expected"] is not None else -9))
        doc["markets"][market] = m
    doc["seconds"] = round(time.time() - t0)
    out = Path(a.out) / "scan"
    out.mkdir(parents=True, exist_ok=True)
    (out / "latest.json").write_text(json.dumps(doc, default=str), encoding="utf-8")
    (out / "history.json").write_text(json.dumps(long_doc, separators=(",", ":")), encoding="utf-8")
    # New forward tickets, merged into data/forward/ by publish.sh through demo_mark.
    (Path(a.out) / "forward_new.json").write_text(json.dumps(forward, default=str), encoding="utf-8")
    print(f"forward tickets issued: {len(forward)}")
    print(f"scan written, {doc['seconds']} seconds, {out / 'latest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
