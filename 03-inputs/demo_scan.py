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
ROWS = 120_000                     # labelled candles per preset; the scan is not a user's run


def _score(cfg: dict, est, x: pd.DataFrame) -> np.ndarray:
    """The preset's score: P(win) for the barrier, P(bullish) minus P(bearish) for three-way."""
    proba, classes = est.predict_proba(x), list(est.classes_)
    if cfg["label"]["kind"] == "barrier":
        return proba[:, classes.index(1)] if 1 in classes else np.zeros(len(x))
    full = np.zeros((len(x), 3))
    full[:, classes] = proba
    return full[:, 2] - full[:, 0]


def _pays(cfg: dict, s: np.ndarray) -> np.ndarray:
    lb = cfg["label"]
    if lb["kind"] == "barrier":
        return s > float(lb["stop_atr"]) / (float(lb["stop_atr"]) + float(lb["target_atr"]))
    return s > 0


def scan_preset(key: str, cfg: dict, market: str, symbols: list[str], log=print) -> dict:
    cfg = copy.deepcopy(cfg)
    cfg["data"].update(market=market, symbols=" ".join(symbols), rows=ROWS)
    df, latest, feats = dr.build_frame(cfg, log=log)
    df, _ = br.apply_screen(cfg, df, log=log)
    feats = br.choose_features(cfg, feats, log=log)
    lb, cost = cfg["label"], dr.cost_of(market)
    three = lb["kind"] == "three-way"
    if three:
        df["label"] = dr._three_way(df["ret3"].to_numpy(float), float(lb["flat_band"]))
    ret = "ret3" if three else "trade_ret"
    bpd = bc.bars_per_day(cfg["data"]["frame"])
    gap = max(1, int(np.ceil(int(lb["horizon_bars"]) / bpd)))
    train, test, cut = t1.split(df, oos_days=int(cfg["split"]["holdout_days"]), embargo_days=gap)
    name = cfg["model"]["estimators"][0]
    params = (cfg["model"].get("params") or {}).get(name)
    est = br.make_estimator(name, cfg["model"]["class_weight"], params).fit(train[feats], train["label"])
    s_test, r_test = _score(cfg, est, test[feats]), test[ret].to_numpy(float) - cost
    edges = np.quantile(s_test, [0.2, 0.4, 0.6, 0.8])
    fifth = np.digitize(s_test, edges)
    earned = [float(r_test[fifth == q].mean()) if (fifth == q).any() else None for q in range(5)]
    record = dict(test_from=str(cut.date()), test_candles=len(test), every=float(r_test.mean()),
                  top_fifth=earned[4], fifths=earned, model=name)
    # Refit on every labelled candle, as demo_run.tickets does, and rate the newest.
    est = br.make_estimator(name, cfg["model"]["class_weight"], params).fit(df[feats], df["label"])
    if latest.empty:
        return dict(record=record, signals=[])
    s_now = _score(cfg, est, latest[feats])
    pays = _pays(cfg, s_now)
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
        buy = bool(pays[i]) and earned[q] is not None and earned[q] > 0
        out.append(dict(symbol=row["symbol"], preset=key, frame=frame, horizon=h, model=name,
                        call="BUY" if buy else "NO TRADE", score=round(float(s_now[i]), 4),
                        confidence=q + 1, expected=earned[q], price=float(row["close"]),
                        atr=float(row["atr_frac"]), generated=opened.isoformat(),
                        expires=expires.isoformat()))
    log(f"{key} {market}: {len(out)} rated, test year from {record['test_from']}, top fifth "
        f"{(record['top_fifth'] or 0) * 100:+.2f}% against {record['every'] * 100:+.2f}% for every candle")
    return dict(record=record, signals=out)


def history(market: str, frame: str, symbols: list[str]) -> dict:
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
        tail = d.tail(HISTORY)
        key = s if market == "equity" else f"{s[:-4]}/USDT"
        out[key] = dict(t=[pd.Timestamp(x).strftime("%Y-%m-%dT%H:%M") for x in tail["datetime"]],
                        c=[round(float(x), 8) for x in tail["close"]],
                        volume24=float(vol.iloc[-1]))
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
    for market in markets:
        universe = (a.coins or dr.COINS) if market == "crypto" else dr.STOCKS
        m = dict(searched=len(universe), presets={}, signals=[], history={}, failed=[])
        for key, p in presets.items():
            cfg, _ = dr.sanitize(as_form(p[market]))
            try:
                got = scan_preset(key, cfg, market, universe)
            except (SystemExit, Exception) as e:                    # noqa: BLE001
                m["failed"].append(dict(preset=key, why=f"{type(e).__name__}: {e}"))
                print(f"{key} {market}: left out, {e}")
                continue
            m["presets"][key] = dict(label=p["label"], frame=cfg["data"]["frame"],
                                     horizon=int(cfg["label"]["horizon_bars"]), **got["record"])
            m["signals"] += got["signals"]
            frame = cfg["data"]["frame"]
            for sym, hist in history(market, frame, universe).items():
                m["history"].setdefault(sym, {})[frame] = hist
        m["signals"].sort(key=lambda r: -(r["expected"] if r["expected"] is not None else -9))
        doc["markets"][market] = m
    doc["seconds"] = round(time.time() - t0)
    out = Path(a.out) / "scan"
    out.mkdir(parents=True, exist_ok=True)
    (out / "latest.json").write_text(json.dumps(doc, default=str), encoding="utf-8")
    print(f"scan written, {doc['seconds']} seconds, {out / 'latest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
