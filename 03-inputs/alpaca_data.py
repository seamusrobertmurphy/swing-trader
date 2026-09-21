"""Track A Phase A2: the Alpaca US-equity daily-bar data layer.

Two subcommands, mirroring the Binance pipeline's acquire stage:

  universe    enumerate active, tradable US equities on the major exchanges,
              screen by trailing-30-day median dollar volume and a price floor,
              and write a dated universe snapshot CSV.
  download    pull maximum-history daily bars (split+dividend adjusted) for the
              screened universe into per-symbol Parquet under
              inputs/alpaca-data/daily/. Resumable: symbols whose file is
              already current are skipped.

SURVIVORSHIP CAVEAT, written where it cannot be missed: the assets endpoint
lists only names alive today, so delisted equities are absent and every result
built on this layer is an upper bound on a survivorship-complete panel. This is
the opposite of the Binance archive discipline (which recovers dead coins) and
is accepted for the first read only; a delisting-complete source is the later
upgrade. The universe snapshot records the bias note alongside the counts.

Feed honesty: the account may only be entitled to IEX (a few percent of
consolidated volume), which understates dollar volume. The module probes SIP
first and falls back to IEX, and stamps WHICH feed the snapshot and every
download manifest used, so no later reader mistakes IEX volume for consolidated.

    .venv/bin/python inputs/alpaca_data.py universe
    .venv/bin/python inputs/alpaca_data.py download
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import pandas as pd

import config

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "alpaca-data"))
DAILY = os.path.join(ROOT, "daily")
HISTORY_START = datetime(2016, 1, 1, tzinfo=timezone.utc)   # IEX/SIP coverage floor on Alpaca

# The bar sizes this layer will pull, each with its own folder and its own
# sensible history. Added 20 September 2026: until then TimeFrame.Day was
# written into the request in two places and there was no flag, so the board
# offered one US equity frame and no way to make another.
#
# The default start differs by bar size and that is a size decision, not a
# coverage one. One bar a day for 2,660 names since 2016 is 5.2 GB on disk; a
# US session is 6.5 hours, so hourly is about seven times that and one-minute
# bars are 390 a day, near two terabytes. Intraday therefore starts later by
# default and --start overrides it.
TIMEFRAMES = {
    "1d":  dict(amount=1, unit="Day",    folder="daily",     start=HISTORY_START),
    "1h":  dict(amount=1, unit="Hour",   folder="hourly",    start=datetime(2021, 1, 1, tzinfo=timezone.utc)),
    "30m": dict(amount=30, unit="Minute", folder="min30",    start=datetime(2023, 1, 1, tzinfo=timezone.utc)),
    "15m": dict(amount=15, unit="Minute", folder="min15",    start=datetime(2023, 1, 1, tzinfo=timezone.utc)),
    "5m":  dict(amount=5, unit="Minute",  folder="min5",     start=datetime(2024, 1, 1, tzinfo=timezone.utc)),
    "1m":  dict(amount=1, unit="Minute",  folder="min1",     start=datetime(2025, 1, 1, tzinfo=timezone.utc)),
}


def store_dir(timeframe: str = "1d") -> str:
    """Where one bar size's per-symbol files live."""
    if timeframe not in TIMEFRAMES:
        raise SystemExit(f"unknown bar size {timeframe!r}; "
                         f"choose one of {', '.join(TIMEFRAMES)}")
    return os.path.join(ROOT, TIMEFRAMES[timeframe]["folder"])


def _timeframe(timeframe: str):
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    spec = TIMEFRAMES[timeframe]
    return TimeFrame(spec["amount"], getattr(TimeFrameUnit, spec["unit"]))
MIN_DOLLAR_VOL = 20e6      # median trailing-30d dollar volume floor
MIN_PRICE = 3.0            # penny-stock floor
MIN_BARS_30D = 15          # a name must actually trade
BATCH = 200                # symbols per bars request
EXCHANGES = {"NYSE", "NASDAQ", "ARCA", "AMEX", "BATS"}


def _keys():
    key = (os.environ.get("ALPACA_API_KEY") or config.ALPACA_API_KEY).strip()
    secret = (os.environ.get("ALPACA_API_SECRET") or config.ALPACA_API_SECRET).strip()
    if not key or not secret:
        raise SystemExit("ABORT: Alpaca keys missing (Keychain + env both empty).")
    return key, secret


def _clients():
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.trading.client import TradingClient
    key, secret = _keys()
    return TradingClient(key, secret, paper=True), StockHistoricalDataClient(key, secret)


def _probe_feed(dc, timeframe: str = "1d"):
    """SIP if entitled, else IEX. Stamped into everything downstream.

    Probed at the bar size actually being pulled, because entitlement can differ
    between daily and intraday and a daily probe would promise consolidated
    minute bars the account may not be served.
    """
    from alpaca.data.enums import DataFeed
    from alpaca.data.requests import StockBarsRequest
    try:
        dc.get_stock_bars(StockBarsRequest(
            symbol_or_symbols="SPY", timeframe=_timeframe(timeframe), feed=DataFeed.SIP,
            start=datetime.now(timezone.utc) - timedelta(days=7)))
        return DataFeed.SIP, "sip"
    except Exception:
        return DataFeed.IEX, "iex"


def _bars(dc, symbols, start, feed, timeframe: str = "1d"):
    from alpaca.data.enums import Adjustment
    from alpaca.data.requests import StockBarsRequest
    req = StockBarsRequest(symbol_or_symbols=list(symbols), timeframe=_timeframe(timeframe),
                           start=start, adjustment=Adjustment.ALL, feed=feed)
    return dc.get_stock_bars(req)


def list_assets(tc):
    from alpaca.trading.enums import AssetClass, AssetStatus
    from alpaca.trading.requests import GetAssetsRequest
    assets = tc.get_all_assets(GetAssetsRequest(
        asset_class=AssetClass.US_EQUITY, status=AssetStatus.ACTIVE))
    keep = [a for a in assets
            if a.tradable and str(a.exchange).rsplit(".", 1)[-1] in EXCHANGES
            and a.symbol.isalnum()]          # drops units/warrants/preferred suffix forms
    return keep


def cmd_universe(args) -> int:
    tc, dc = _clients()
    feed, feed_name = _probe_feed(dc, "1d")
    assets = list_assets(tc)
    print(f"assets: {len(assets)} active tradable US equities on {sorted(EXCHANGES)} "
          f"(feed={feed_name})", flush=True)

    start = datetime.now(timezone.utc) - timedelta(days=45)
    rows = []
    syms = [a.symbol for a in assets]
    for i in range(0, len(syms), BATCH):
        batch = syms[i:i + BATCH]
        try:
            data = _bars(dc, batch, start, feed).data
        except Exception as e:  # noqa: BLE001
            print(f"  batch {i // BATCH}: {type(e).__name__}, retrying once", flush=True)
            time.sleep(5)
            data = _bars(dc, batch, start, feed).data
        for sym, bars in data.items():
            if not bars:
                continue
            close = pd.Series([b.close for b in bars], dtype=float)
            vol = pd.Series([b.volume for b in bars], dtype=float)
            rows.append(dict(symbol=sym, n_bars=len(bars),
                             last_close=float(close.iloc[-1]),
                             med_dollar_vol=float((close * vol).median())))
        if i // BATCH % 10 == 0:
            print(f"  screened {min(i + BATCH, len(syms))}/{len(syms)}", flush=True)
        time.sleep(0.3)                      # stay far inside the rate limit

    t = pd.DataFrame(rows)
    t["pass"] = ((t["med_dollar_vol"] >= args.min_dv) & (t["last_close"] >= MIN_PRICE)
                 & (t["n_bars"] >= MIN_BARS_30D))
    os.makedirs(ROOT, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = os.path.join(ROOT, f"universe_{stamp}.csv")
    t.sort_values("med_dollar_vol", ascending=False).to_csv(path, index=False)
    with open(os.path.join(ROOT, "universe_latest.txt"), "w") as f:
        f.write(path + "\n")
    meta = dict(stamp=stamp, feed=feed_name, assets_active=len(assets),
                screened=len(t), passing=int(t["pass"].sum()),
                min_dollar_vol=args.min_dv, min_price=MIN_PRICE,
                survivorship_note="assets endpoint lists live names only; delisted "
                                  "equities absent; results are upper bounds")
    with open(os.path.join(ROOT, f"universe_{stamp}.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(f"\nuniverse: {meta['passing']}/{len(t)} pass "
          f"(median $vol >= {args.min_dv / 1e6:.0f}M, price >= ${MIN_PRICE}, feed={feed_name})")
    print(f"wrote {path}")
    return 0


def cmd_download(args) -> int:
    _, dc = _clients()
    feed, feed_name = _probe_feed(dc, getattr(args, "timeframe", "1d"))
    if args.symbols:
        syms = [s.upper() for s in args.symbols]
    else:
        # universe_latest.txt has historically held an absolute path, which the
        # 2026-09 folder rename turned into a dangling one. Read it, but fall back
        # to the same basename under ROOT so a move cannot break the pointer again.
        latest = open(os.path.join(ROOT, "universe_latest.txt")).read().strip()
        if not os.path.exists(latest):
            latest = os.path.join(ROOT, os.path.basename(latest))
        u = pd.read_csv(latest)
        syms = list(u.loc[u["pass"], "symbol"])
    tf = getattr(args, "timeframe", "1d")
    out_dir = store_dir(tf)
    start = (pd.Timestamp(args.start, tz="UTC").to_pydatetime()
             if getattr(args, "start", None) else TIMEFRAMES[tf]["start"])
    os.makedirs(out_dir, exist_ok=True)

    fresh_after = datetime.now(timezone.utc) - timedelta(days=5)
    todo = []
    for s in syms:
        p = os.path.join(out_dir, f"{s}.parquet")
        if os.path.exists(p):
            try:
                last = pd.Timestamp(pd.read_parquet(p, columns=["datetime"])["datetime"].max())
                if last.tz is None:
                    last = last.tz_localize("UTC")
                if last >= fresh_after:
                    continue
            except Exception:  # noqa: BLE001
                pass
        todo.append(s)
    print(f"download: {len(todo)}/{len(syms)} symbols need {tf} bars "
          f"(rest current; feed={feed_name}, adjustment=all, start {start:%Y-%m-%d}, "
          f"into {os.path.relpath(out_dir, os.path.dirname(ROOT))})", flush=True)

    written = 0
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        try:
            data = _bars(dc, batch, start, feed, tf).data
        except Exception as e:  # noqa: BLE001
            print(f"  batch {i // BATCH}: {type(e).__name__}, retrying once", flush=True)
            time.sleep(5)
            data = _bars(dc, batch, start, feed, tf).data
        for sym, bars in data.items():
            if not bars:
                continue
            d = pd.DataFrame([dict(datetime=b.timestamp, open=b.open, high=b.high,
                                   low=b.low, close=b.close, volume=b.volume,
                                   trade_count=b.trade_count, vwap=b.vwap)
                              for b in bars]).sort_values("datetime")
            d.to_parquet(os.path.join(out_dir, f"{sym}.parquet"), index=False)
            written += 1
        print(f"  {min(i + BATCH, len(todo))}/{len(todo)} done ({written} files)", flush=True)
        time.sleep(0.3)

    name = ("download_manifest.json" if tf == "1d"
            else f"download_manifest_{tf}.json")
    with open(os.path.join(ROOT, name), "w") as f:
        json.dump(dict(stamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                       timeframe=tf, feed=feed_name, adjustment="all",
                       start=f"{start:%Y-%m-%d}", symbols=len(syms),
                       written=written), f, indent=2)
    print(f"\nwrote {written} symbol files under {out_dir}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Alpaca daily-bar data layer (Track A Phase A2)")
    sub = p.add_subparsers(dest="cmd", required=True)
    pu = sub.add_parser("universe", help="enumerate + screen the live US-equity universe")
    pu.add_argument("--min-dv", type=float, default=MIN_DOLLAR_VOL,
                    help="median trailing-30d dollar-volume floor (default 20e6)")
    pd_ = sub.add_parser("download", help="pull max-history bars for the screened set")
    pd_.add_argument("--symbols", nargs="+", default=None)
    pd_.add_argument("--timeframe", default="1d", choices=list(TIMEFRAMES),
                     help="bar size (default 1d). Intraday sizes start later by "
                          "default because of their size on disk; see --start.")
    pd_.add_argument("--start", default=None,
                     help="first bar, YYYY-MM-DD. Default is the bar size's own: "
                          + ", ".join(f"{k} from {v['start']:%Y-%m-%d}"
                                      for k, v in TIMEFRAMES.items()))
    a = p.parse_args()
    return cmd_universe(a) if a.cmd == "universe" else cmd_download(a)


if __name__ == "__main__":
    sys.exit(main())
