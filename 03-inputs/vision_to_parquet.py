"""Binance spot candles for every pair ever listed, one Parquet file per pair.

    .venv/bin/python 03-inputs/vision_to_parquet.py --interval 30m
    .venv/bin/python 03-inputs/vision_to_parquet.py --interval 3m --workers 6
    .venv/bin/python 03-inputs/vision_to_parquet.py --interval 3m --symbols BTCUSDT ETHUSDT

Operator request, 26 September 2026: the 30-minute and 3-minute candles of all
612 USDT pairs in the survivorship-complete universe, delisted coins included,
kept as Parquet. Binance publishes one zipped CSV per pair and month; kept as
they arrive, the 1-hour set is 0.8 GB of data spread over 33,614 files, which
the exFAT SSD stores in 33 GB because every file takes a whole block. So each
monthly archive is fetched into memory, checked against its published SHA-256,
and every month of a pair is written as one file, prices and volumes in single
precision with zstd compression. Measured on 26 September 2026, the full 30-minute
history of BTCUSDT, 159,413 candles from 17 August 2017, took 54.7 bytes a candle,
and the 3-minute history of FTTUSDT, 1,036,403 candles, took 31.5.

Source, Binance Vision, https://data.binance.vision/ (acquire_vision.BASE_URL);
the universe is acquire_vision's crawl of the archive listing,
03-inputs/binance-data/universe_vision_USDT_2026-06-23.json. The run can be
stopped and restarted: a pair already written is skipped unless --refresh.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import acquire_vision as av        # noqa: E402

DATA = Path(__file__).resolve().parent / "binance-data"
UNIVERSE = DATA / "universe_vision_USDT_2026-06-23.json"
COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume",
        "trades", "taker_base", "taker_quote", "ignore"]
FLOATS = ["open", "high", "low", "close", "volume", "quote_volume", "taker_base", "taker_quote"]


def _month(raw: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        d = pd.read_csv(z.open(z.namelist()[0]), header=None)
    if not str(d.iloc[0, 0]).lstrip("-").isdigit():          # a header row in some newer files
        d = d.iloc[1:]
    d = d.iloc[:, :12]
    d.columns = COLS[:d.shape[1]]
    t = pd.to_numeric(d["open_time"]).astype("int64")
    # Archives from 2025 give times in microseconds, earlier ones in milliseconds.
    t = np.where(t > 10 ** 14, t // 1000, t)
    out = pd.DataFrame({"datetime": pd.to_datetime(t, unit="ms", utc=True)})
    for c in FLOATS:
        out[c] = pd.to_numeric(d[c]).astype("float32").to_numpy()
    out["trades"] = pd.to_numeric(d["trades"]).astype("int32").to_numpy()
    return out


def _fetch(url: str) -> tuple[bytes | None, str]:
    raw = av._get(url)
    if raw is None:
        return None, "missing"
    ok = av._verify_checksum(raw, url + ".CHECKSUM")
    if ok is False:
        raw = av._get(url)
        if raw is None or av._verify_checksum(raw, url + ".CHECKSUM") is False:
            return None, "badchecksum"
        ok = True
    return raw, "ok" if ok else "nochecksum"


def one(symbol: str, interval: str, out: Path, refresh: bool) -> dict:
    dest = out / f"{symbol}.parquet"
    if dest.exists() and not refresh:
        return dict(symbol=symbol, status="cached")
    today = date.today()
    end = datetime.now(timezone.utc).strftime("%Y-%m")
    parts, counts = [], dict(ok=0, nochecksum=0, missing=0, badchecksum=0)
    for y, m in av._month_iter(av.DEFAULT_START, end):
        raw, st = _fetch(av._kline_url(symbol, f"{y}-{m:02d}", "monthly", interval))
        if raw is None and st == "missing" and (y, m) == (today.year, today.month):
            # The month still open has daily files only, up to yesterday.
            for d in range(1, today.day):
                raw_d, st_d = _fetch(av._kline_url(symbol, f"{y}-{m:02d}-{d:02d}", "daily", interval))
                if raw_d is not None:
                    parts.append(_month(raw_d))
                counts[st_d] = counts.get(st_d, 0) + 1
            continue
        counts[st] += 1
        if raw is not None:
            parts.append(_month(raw))
    if not parts:
        return dict(symbol=symbol, status="empty", **counts)
    df = pd.concat(parts, ignore_index=True).drop_duplicates("datetime").sort_values("datetime")
    tmp = dest.with_suffix(".part")
    df.to_parquet(tmp, index=False, compression="zstd")
    os.replace(tmp, dest)                       # a half-written file is never taken as done
    return dict(symbol=symbol, status="written", rows=len(df), first=str(df["datetime"].iloc[0]),
                last=str(df["datetime"].iloc[-1]), bytes=dest.stat().st_size, **counts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--interval", required=True, help="a Binance kline size, such as 30m or 3m")
    ap.add_argument("--symbols", nargs="+", default=None)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    syms = a.symbols or json.loads(UNIVERSE.read_text())["symbols"]
    out = DATA / f"parquet_{a.interval}"
    out.mkdir(parents=True, exist_ok=True)
    t0, done, results = time.time(), 0, []
    print(f"{len(syms)} pairs, {a.interval} candles, into {out}", flush=True)
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        futs = {pool.submit(one, s, a.interval, out, a.refresh): s for s in syms}
        for f in as_completed(futs):
            done += 1
            try:
                r = f.result()
            except Exception as e:                  # noqa: BLE001
                r = dict(symbol=futs[f], status=f"failed: {type(e).__name__}: {e}")
            results.append(r)
            print(f"[{done}/{len(syms)}] {r['symbol']} {r['status']} {r.get('rows', '')} "
                  f"{time.time() - t0:.0f}s", flush=True)
    manifest = dict(interval=a.interval, written=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    source="https://data.binance.vision/", universe=UNIVERSE.name, pairs=results)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    total = sum(r.get("bytes", 0) for r in results)
    print(f"done: {sum(r['status'] == 'written' for r in results)} written, "
          f"{sum(r['status'] == 'cached' for r in results)} already there, "
          f"{sum(str(r['status']).startswith('failed') for r in results)} failed, "
          f"{total / 1e9:.2f} GB, {time.time() - t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
