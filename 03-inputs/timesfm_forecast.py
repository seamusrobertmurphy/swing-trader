"""TimesFM forecast data for the app's Forecast card, one file per market, candle size and symbol.

    .venv/bin/python 03-inputs/timesfm_forecast.py                 # every symbol and candle size
    .venv/bin/python 03-inputs/timesfm_forecast.py --frames 4h --symbols BTCUSDT

Operator request, 29 September 2026: the Forecast card on the home and C2 pages
shows the trades and market the user's settings select. The card is drawn in the
browser from these files, so it can follow the settings without a server. The
market switch, the chosen coins or stocks and the candle size pick the file; the
take-profit, the stop and the horizon, all from A1, set the trades and how far
ahead each forecast fan reaches, and the scores are recomputed in the browser.

Each file holds, for the most recent 5,000 candles at most (the scored window):
1. time, close, high, low and the 14-candle average true range as a fraction of price;
2. the MACD buy and sell signals of 04-outputs/1A-macd/macd.py over that window;
3. for every signal, the TimesFM 2.5 forecast 72 candles ahead (the horizon limit
   of a demo run) as the median and the 10th and 90th percentiles, fitted on the
   1,024 candles up to the signal only;
4. the forecast from the last closed candle;
5. the 200-candle exponential moving average, MACD, signal line, histogram and
   divergences for the last 360 candles, the part the chart draws.

TimesFM 2.5, https://huggingface.co/google/timesfm-2.5-200m-pytorch, Apache 2.0
weights; 3.0 is not used because its weights are licensed non-commercial only.
Written to site/forecast/<market>/<frame>/<SYMBOL>.json, beside the local build.

Added 30 September 2026, operator's choice of "Show the model's own trades on the
graph": the chart draws the paper trades the model actually took and skipped,
read from the published record (data/forward and data/runs on the gh-pages
branch, copied into site/data first), in place of the MACD signals. Each trade's
entry candle gets its own TimesFM forecast, so the chart shows what TimesFM said
when the model decided. Crypto candles are topped up from Binance's public
market data so the price line reaches the trades; the MACD-signal forecasts are
kept only for the long-run TimesFM score.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
# PyTorch is loaded before demo_run, whose libraries otherwise crash the model
# with a segmentation fault (exit 139), seen on 29 September 2026.
import torch

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "04-outputs" / "1A-macd"))

import build_dataset_1h as bd          # noqa: E402
import demo_run as dr                  # noqa: E402
import macd as mc                      # noqa: E402

OUT = REPO / "site" / "forecast"
HORIZON = 72          # the longest horizon a demo run accepts, demo_run.LIMITS
CONTEXT = 1024
WINDOW = 5000         # candles scored
SHOWN = 360           # candles drawn
BINANCE = REPO / "03-inputs" / "binance-data"
ALPACA = REPO / "03-inputs" / "alpaca-data"
TRADES = REPO / "site" / "data"
# Binance public market data, klines, https://data-api.binance.vision/api/v3/klines
LIVE = "https://data-api.binance.vision/api/v3/klines?symbol={s}&interval={f}&limit=1000"


def refresh_trades() -> None:
    """Copy the published paper trades from the gh-pages branch into site/data."""
    subprocess.run(["git", "fetch", "-q", "origin", "gh-pages"], cwd=REPO, check=True)
    names = subprocess.run(["git", "ls-tree", "-r", "--name-only", "origin/gh-pages", "data"], cwd=REPO,
                           check=True, capture_output=True, text=True).stdout.split()
    for n in names:
        dest = REPO / "site" / n
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(subprocess.run(["git", "show", f"origin/gh-pages:{n}"], cwd=REPO, check=True,
                                        capture_output=True).stdout)


def paper_trades() -> list[dict]:
    """Every scan and run ticket, the scans' own and each user run's, by id."""
    out = {}
    # exFAT leaves ._ companions beside every file written; they are not data.
    for f in sorted(x for x in (TRADES / "forward").glob("*.json") if not x.name.startswith("._")):
        out.update(json.loads(f.read_text()))
    for f in sorted(x for x in (TRADES / "runs").glob("2*.json") if not x.name.startswith("._")):
        r = json.loads(f.read_text())
        for t in r.get("tickets") or []:
            out[t["id"]] = dict(t, config="run:" + str(r.get("name") or "anonymous"))
    return list(out.values())


def top_up(d: pd.DataFrame, symbol: str, frame: str) -> pd.DataFrame:
    """The newest closed candles from the live feed, over the archive's last month."""
    try:
        req = urllib.request.Request(LIVE.format(s=symbol, f=frame), headers={"User-Agent": "swing-trader-forecast/1.0"})
        rows = json.load(urllib.request.urlopen(req, timeout=30))[:-1]       # the last is still forming
    except Exception as e:                                                 # noqa: BLE001
        print(f"  {symbol} {frame}: no top-up ({type(e).__name__})", flush=True)
        return d
    new = pd.DataFrame(dict(datetime=pd.to_datetime([r[0] for r in rows], unit="ms", utc=True),
                            **{c: [float(r[k]) for r in rows] for k, c in
                               enumerate(("open", "high", "low", "close", "volume"), start=1)}))
    return pd.concat([d[d["datetime"] < new["datetime"].min()], new], ignore_index=True)


def load(market: str, frame: str, symbol: str) -> pd.DataFrame | None:
    if market == "equity":
        # Alpaca market data, daily bars, SIP feed, adjustment=all,
        # https://data.alpaca.markets/v2/stocks/bars (stored by alpaca_data.py).
        p = ALPACA / "daily" / f"{symbol}.parquet"
        if not p.exists():
            return None
        d = pd.read_parquet(p)[["datetime", "open", "high", "low", "close", "volume"]]
    else:
        # Binance Vision spot klines, https://data.binance.vision/, packed to Parquet
        # by vision_to_parquet.py; 15-minute candles are summed from 3-minute ones,
        # every longer size from 30-minute ones.
        src = BINANCE / ("parquet_3m" if frame == "15m" else "parquet_30m") / f"{symbol}.parquet"
        if not src.exists():
            return None
        d = pd.read_parquet(src, columns=["datetime", "open", "high", "low", "close", "volume"])
        if frame != "30m":
            d = (d.set_index("datetime").resample(frame.replace("m", "min"))
                 .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
                 .dropna().reset_index())
        d = top_up(d, symbol, frame)
    for c in ("open", "high", "low", "close", "volume"):
        d[c] = d[c].astype("float64")
    return d.reset_index(drop=True)


def model():
    import timesfm
    torch.set_float32_matmul_precision("high")
    m = timesfm.TimesFM_2p5_200M_torch.from_pretrained("google/timesfm-2.5-200m-pytorch")
    m.compile(timesfm.ForecastConfig(max_context=CONTEXT, max_horizon=HORIZON, normalize_inputs=True,
                                     use_continuous_quantile_head=True, fix_quantile_crossing=True,
                                     per_core_batch_size=32))
    return m


def forecast(m, close: np.ndarray, origins: list[int]):
    med, lo, hi = [], [], []
    for k in range(0, len(origins), 64):
        batch = [close[max(0, o + 1 - CONTEXT): o + 1].astype("float32") for o in origins[k:k + 64]]
        p, q = m.forecast(horizon=HORIZON, inputs=batch)
        med.append(p)
        lo.append(q[:, :, 1])
        hi.append(q[:, :, 9])
    return np.concatenate(med), np.concatenate(lo), np.concatenate(hi)


def r6(a) -> list:
    """Six significant figures, which keeps each file small."""
    return [float(f"{v:.6g}") if np.isfinite(v) else None for v in np.asarray(a, dtype=float)]


def export(m, market: str, frame: str, symbol: str, tickets: list[dict]) -> dict | None:
    d = load(market, frame, symbol)
    if d is None or len(d) < 300:
        return None
    sig = mc.compute_signals(d["close"])
    bd.configure(4)
    atr = (bd._atr_pct(d, bd.LABEL["atr_len"]) / 100.0).to_numpy()
    ema = d["close"].ewm(span=200, adjust=True).mean().to_numpy()
    n = len(d)
    w0 = max(0, n - WINDOW)
    first = max(w0, 256)                  # a forecast needs some history behind it
    buys = [int(i) for i in np.flatnonzero(sig["guarded_buy"].to_numpy(bool)) if i >= first]
    sells = [int(i) for i in np.flatnonzero(sig["guarded_sell"].to_numpy(bool)) if i >= first]
    origins = sorted(set(buys + sells))
    close = d["close"].to_numpy()
    # The paper trades on this symbol and candle size, each placed on the candle
    # that closed at its entry: the last candle opened strictly before it.
    opens = (d["datetime"].astype("int64") // 10 ** 9).to_numpy()
    mine = [t for t in tickets if t["market"] == market and t["frame"] == frame
            and t["symbol"].replace("/", "") == symbol]
    trades, at = [], []
    for t in mine:
        e = int(pd.Timestamp(t["entry_time"]).timestamp())
        i = int(np.searchsorted(opens, e, side="left")) - 1
        if i < max(w0, 256):
            continue
        at.append(i)
        stamp = lambda k: int(pd.Timestamp(t[k]).timestamp()) if t.get(k) else None  # noqa: E731
        trades.append(dict(src=t["config"], taken=t["call"] == "BUY", i=i - w0, entry=e, price=t["entry_price"],
                           due=stamp("due"), h=int(t["horizon_bars"]), target=t.get("target"), stop=t.get("stop"),
                           status=t["status"], exit=stamp("exit_time"), exit_price=t.get("exit_price"),
                           after_cost=t.get("after_cost"), how=t.get("how"), model=t.get("model"),
                           score=t.get("score"), group=t.get("confidence"), expected=t.get("expected"),
                           outcome=t.get("outcome"), why=t.get("why")))
    at = sorted(set(at))
    med, lo, hi = forecast(m, close, origins + at + [n - 1])
    s0 = n - min(SHOWN, n - w0)
    rel = lambda idx: [i - w0 for i in idx]          # noqa: E731
    div = lambda col: rel([int(i) for i in np.flatnonzero(sig[col].to_numpy(bool)) if i >= s0])  # noqa: E731
    return dict(
        market=market, frame=frame, symbol=symbol,
        t=[int(x) for x in d["datetime"].iloc[w0:].astype("int64") // 10 ** 9],
        c=r6(close[w0:]), h=r6(d["high"].to_numpy()[w0:]), l=r6(d["low"].to_numpy()[w0:]),
        atr=r6(atr[w0:]), shown=s0 - w0,
        ema=r6(ema[s0:]), macd=r6(sig["macd"].to_numpy()[s0:]), signal=r6(sig["signal"].to_numpy()[s0:]),
        hist=r6(sig["hist"].to_numpy()[s0:]), bull=div("bull_div"), bear=div("bear_div"),
        buys=rel(buys), sells=rel(sells),
        fc={str(o - w0): [r6(med[k]), r6(lo[k]), r6(hi[k])] for k, o in enumerate(origins)},
        tt={str(o - w0): [r6(med[len(origins) + k]), r6(lo[len(origins) + k]), r6(hi[len(origins) + k])]
            for k, o in enumerate(at)},
        trades=trades, live=[r6(med[-1]), r6(lo[-1]), r6(hi[-1])])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--frames", nargs="+", default=None, help="crypto candle sizes, default all nine")
    ap.add_argument("--symbols", nargs="+", default=None)
    ap.add_argument("--traded-only", action="store_true", help="only the files that have paper trades")
    a = ap.parse_args()
    refresh_trades()
    tickets = paper_trades()
    traded = {(t["market"], t["frame"], t["symbol"].replace("/", "")) for t in tickets}
    print(f"{len(tickets)} paper trades on {len(traded)} symbol and candle sizes", flush=True)
    jobs = [("crypto", f, s) for f in (a.frames or dr.FRAMES) for s in dr.COINS]
    jobs += [("equity", "1d", s) for s in dr.STOCKS]
    if a.symbols:
        jobs = [j for j in jobs if j[2] in a.symbols]
    if a.traded_only:
        jobs = [j for j in jobs if j in traded]
    # Files with paper trades first, then the default basket, then the rest.
    rank = lambda j: (0 if j in traded else 1 if j[2] in ("BTCUSDT", "ETHUSDT") else 2)  # noqa: E731
    jobs.sort(key=rank)
    idx = OUT / "index.json"
    OUT.mkdir(parents=True, exist_ok=True)
    m = model()
    t0, done = time.time(), 0
    for market, frame, sym in jobs:
        rec = export(m, market, frame, sym, tickets)
        done += 1
        if rec is None:
            print(f"[{done}/{len(jobs)}] {market} {frame} {sym}: no data", flush=True)
            continue
        dest = OUT / market / frame / f"{sym}.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(rec, separators=(",", ":")))
        index = json.loads(idx.read_text()) if idx.exists() else {}
        have = index.setdefault(market, {}).setdefault(frame, [])
        if sym not in have:
            have.append(sym)
        idx.write_text(json.dumps(index))           # after every file, so the card sees it at once
        print(f"[{done}/{len(jobs)}] {market} {frame} {sym}: {len(rec['trades'])} paper trades, "
              f"{dest.stat().st_size // 1024} KB, {time.time() - t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
