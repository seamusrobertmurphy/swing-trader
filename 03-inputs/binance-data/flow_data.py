"""
flow_data.py - scoped Binance historical downloader and trade-flow aggregator.

Downloads klines for a coin set from data.binance.vision (free, no API key, no
rate limit, deterministic) and aggregates them into a per-bar trade-flow imbalance
table the model can join as a feature in build_dataset.py.

Interval-aware. The default is daily (1d), which preserves the original behaviour
byte-for-byte (klines/<SYMBOL>/..., daily_flow.csv, one row per calendar date). Pass
--interval 1h to pull hourly bars instead; those land in klines_1h/<SYMBOL>/... and
aggregate to flow_1h.csv with one row per HOUR (the hourly bars are NOT collapsed to a
single calendar date). The flow arithmetic is identical at every interval, because a
kline row carries taker-buy volume regardless of how long the bar is.

Coin set. By default the ten model coins (mirrors build_dataset.py). Pass --all-market
to instead fetch every active USDT spot pair from Binance exchangeInfo, which is the
dynamic trading universe the point-in-time screen replays against (~433 pairs as of
2026-06). -s overrides both.

Why klines and not aggTrades, by default:
  A kline row already carries taker-buy base volume and the trade count, so the
  buy-versus-sell pressure for that bar is available directly in a few megabytes per
  coin per interval. The multi-gigabyte aggTrades files are only needed if we ever want
  finer-than-bar trade-flow resolution. Pass --aggtrades to fetch those as well.

What a trade-flow imbalance is (per bar):
  taker_buy_ratio   = taker_buy_base_volume / volume        (share of volume that
                      lifted the ask, i.e. aggressive buying), in [0, 1]
  flow_imbalance    = 2 * taker_buy_ratio - 1               (signed, in [-1, +1];
                      positive = net aggressive buying on the bar)

Outputs (written under this folder, inputs/binance-data/):
  klines/<SYMBOL>/...zip       raw 1d kline archives        (interval 1d)
  klines_1h/<SYMBOL>/...zip    raw 1h kline archives        (interval 1h)
  daily_flow.csv               symbol,date,close,volume,...   (interval 1d)
  flow_1h.csv                  symbol,datetime,close,volume,...(interval 1h)
  aggtrades/<SYMBOL>/...zip     raw aggTrades archives (only when --aggtrades is passed)

Run:
  python flow_data.py                                  1d klines, 10 coins (default)
  python flow_data.py --interval 1h                    1h klines, 10 coins
  python flow_data.py --interval 1h --all-market       1h klines, all USDT spot pairs
  python flow_data.py -s BTCUSDT --interval 1h --start 2024-01 --end 2024-03
  python flow_data.py --aggtrades                      ALSO fetch aggTrades (heavy)

No API key. No orders. Read-only public data. Plain ASCII output, no icons.
"""

import argparse
import io
import json
import os
import urllib.error
import urllib.request
import zipfile
from datetime import date, datetime

import pandas as pd

# ----------------------------------------------------------------------------
# Config. COINS mirrors inputs/build_dataset.py so the flow table joins cleanly.
# ----------------------------------------------------------------------------
BASE_URL = "https://data.binance.vision/"
EXCHANGE_INFO_URL = "https://api.binance.com/api/v3/exchangeInfo"
COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "AVAX", "LINK", "LTC", "DOGE"]
DEFAULT_SYMBOLS = [f"{c}USDT" for c in COINS]
DEFAULT_INTERVAL = "1d"
DEFAULT_START = "2017-08"   # BTCUSDT spot listing month; earlier 404s skip cleanly
HERE = os.path.dirname(os.path.abspath(__file__))

# Binance spot kline CSV layout (no reliable header in the archives):
#   0 open_time  1 open  2 high  3 low  4 close  5 volume  6 close_time
#   7 quote_volume  8 num_trades  9 taker_buy_base  10 taker_buy_quote  11 ignore
KLINE_COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
              "quote_volume", "num_trades", "taker_buy_base", "taker_buy_quote", "ignore"]


def klines_subdir(interval):
    """Where raw kline zips live for an interval. 1d keeps the original 'klines'
    folder (so existing downloads are not orphaned); other intervals get their own
    'klines_<interval>' folder so resolutions never mix."""
    return "klines" if interval == "1d" else f"klines_{interval}"


def month_iter(start_ym, end_ym):
    """Yield (year, month) from start_ym to end_ym inclusive, both 'YYYY-MM'."""
    sy, sm = (int(x) for x in start_ym.split("-"))
    ey, em = (int(x) for x in end_ym.split("-"))
    y, m = sy, sm
    while (y, m) <= (ey, em):
        yield y, m
        m += 1
        if m > 12:
            m, y = 1, y + 1


def fetch(url):
    """Return raw bytes for url, or None on 404 / not-yet-published."""
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    except urllib.error.URLError as e:
        print(f"  network error on {url}: {e}")
        return None


def save(raw, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        f.write(raw)


def fetch_all_usdt_spot_symbols():
    """Every active USDT spot pair from Binance exchangeInfo: status TRADING,
    quoteAsset USDT, spot trading allowed. This is the dynamic trading universe the
    point-in-time screen replays against. Returns a sorted list like ['BTCUSDT', ...]."""
    try:
        with urllib.request.urlopen(EXCHANGE_INFO_URL, timeout=60) as r:
            info = json.loads(r.read())
    except (urllib.error.URLError, ValueError) as e:
        print(f"could not fetch exchangeInfo ({e}); falling back to the 10 model coins")
        return list(DEFAULT_SYMBOLS)
    syms = []
    for s in info.get("symbols", []):
        if (s.get("quoteAsset") == "USDT"
                and s.get("status") == "TRADING"
                and s.get("isSpotTradingAllowed", False)):
            syms.append(s["symbol"])
    return sorted(set(syms))


def kline_url(symbol, period, kind, interval):
    """period 'YYYY-MM' (monthly) or 'YYYY-MM-DD' (daily); kind in {monthly,daily}."""
    return (f"{BASE_URL}data/spot/{kind}/klines/{symbol}/{interval}/"
            f"{symbol}-{interval}-{period}.zip")


def aggtrade_url(symbol, period, kind):
    return (f"{BASE_URL}data/spot/{kind}/aggTrades/{symbol}/"
            f"{symbol}-aggTrades-{period}.zip")


def download_klines(symbol, start_ym, end_ym, out_dir, interval):
    """Download monthly klines for the interval; for any month with no monthly file
    yet (the current, still-open month), fall back to that month's daily files. Skips
    files already on disk so reruns are cheap."""
    sym_dir = os.path.join(out_dir, klines_subdir(interval), symbol)
    got = 0
    today = date.today()
    for y, m in month_iter(start_ym, end_ym):
        period = f"{y}-{m:02d}"
        dest = os.path.join(sym_dir, f"{symbol}-{interval}-{period}.zip")
        if os.path.exists(dest):
            got += 1
            continue
        raw = fetch(kline_url(symbol, period, "monthly", interval))
        if raw is not None:
            save(raw, dest)
            got += 1
            continue
        # No monthly file: if this is the current (open) month, grab daily files.
        if (y, m) == (today.year, today.month):
            last_day = today.day
            for d in range(1, last_day + 1):
                dperiod = f"{y}-{m:02d}-{d:02d}"
                ddest = os.path.join(sym_dir, f"{symbol}-{interval}-{dperiod}.zip")
                if os.path.exists(ddest):
                    continue
                draw = fetch(kline_url(symbol, dperiod, "daily", interval))
                if draw is not None:
                    save(draw, ddest)
    return got


def download_aggtrades(symbol, start_ym, end_ym, out_dir):
    """Heavy. Monthly aggTrades only; the current open month is left to a later
    incremental pass. Skips files already on disk. aggTrades have no interval."""
    sym_dir = os.path.join(out_dir, "aggtrades", symbol)
    got = 0
    for y, m in month_iter(start_ym, end_ym):
        period = f"{y}-{m:02d}"
        dest = os.path.join(sym_dir, f"{symbol}-aggTrades-{period}.zip")
        if os.path.exists(dest):
            got += 1
            continue
        raw = fetch(aggtrade_url(symbol, period, "monthly"))
        if raw is not None:
            save(raw, dest)
            got += 1
            print(f"    {period}: {len(raw)/1e6:.1f} MB")
    return got


def _to_datetime(series):
    """Binance switched mid-2025 from millisecond to microsecond timestamps, so a single
    coin's archives can MIX both units. Classify per value (us > 1e14 > ms), normalise the
    ms values up to us, then parse once -- deciding the unit from only the first row misreads
    later microsecond values as ms and overflows."""
    v = pd.to_numeric(series, errors="coerce")
    v_us = v.where(v > 1e14, v * 1000)
    return pd.to_datetime(v_us, unit="us")


def read_kline_zip(path):
    """Read one kline zip into a DataFrame, tolerating an optional header row."""
    with zipfile.ZipFile(path) as z:
        name = z.namelist()[0]
        raw = z.read(name)
    # Sniff a header: if the first cell is not numeric, the file has column names.
    first = raw[:64].decode("utf-8", "ignore").split(",")[0].strip()
    header = 0 if first and not first.replace(".", "").isdigit() else None
    df = pd.read_csv(io.BytesIO(raw), header=header, names=KLINE_COLS)
    return df


def aggregate(symbols, out_dir, interval):
    """Roll every downloaded kline zip into one per-bar trade-flow table. For 1d the
    time key is the calendar date and the output is daily_flow.csv (unchanged). For
    sub-daily intervals the time key is the full bar-open timestamp and the output is
    flow_<interval>.csv, so 24 hourly bars are kept as 24 rows, not collapsed to one."""
    daily = (interval == "1d")
    time_col = "date" if daily else "datetime"
    rows = []
    for symbol in symbols:
        sym_dir = os.path.join(out_dir, klines_subdir(interval), symbol)
        if not os.path.isdir(sym_dir):
            continue
        frames = []
        for fn in sorted(os.listdir(sym_dir)):
            if not fn.endswith(".zip") or fn.startswith("._"):   # skip macOS AppleDouble files
                continue
            try:
                frames.append(read_kline_zip(os.path.join(sym_dir, fn)))
            except Exception as e:
                print(f"  skip {fn}: {e}")
        if not frames:
            continue
        d = pd.concat(frames, ignore_index=True)
        ts = _to_datetime(d["open_time"])
        d[time_col] = ts.dt.date if daily else ts
        for c in ["close", "volume", "quote_volume", "num_trades", "taker_buy_base"]:
            d[c] = pd.to_numeric(d[c], errors="coerce")
        d = d.dropna(subset=["volume"]).drop_duplicates(time_col).sort_values(time_col)
        d = d[d["volume"] > 0].copy()
        d["taker_buy_ratio"] = d["taker_buy_base"] / d["volume"]
        d["flow_imbalance"] = 2 * d["taker_buy_ratio"] - 1
        d["symbol"] = f"{symbol[:-4]}/USDT" if symbol.endswith("USDT") else symbol
        rows.append(d[["symbol", time_col, "close", "volume", "quote_volume",
                       "num_trades", "taker_buy_base", "taker_buy_ratio",
                       "flow_imbalance"]])
    if not rows:
        print("nothing to aggregate; no kline zips found.")
        return None
    out = pd.concat(rows, ignore_index=True)
    if daily:
        dest = os.path.join(out_dir, "daily_flow.csv")     # legacy daily path stays CSV
        out.to_csv(dest, index=False)
    else:
        dest = os.path.join(out_dir, f"flow_{interval}.parquet")   # Parquet: smaller, exact dtypes
        out.to_parquet(dest, index=False)
    print(f"\nwrote {len(out)} {interval} rows for {out['symbol'].nunique()} coins -> {dest}")
    print(out.groupby("symbol")["flow_imbalance"].agg(["count", "mean"]).round(3).to_string())
    return out


def main():
    p = argparse.ArgumentParser(description="Scoped Binance kline downloader + trade-flow aggregator")
    p.add_argument("-s", "--symbols", nargs="+", default=None,
                   help="symbols like BTCUSDT (default: the 10 model coins; ignored if --all-market)")
    p.add_argument("--all-market", action="store_true",
                   help="fetch every active USDT spot pair from Binance exchangeInfo")
    p.add_argument("-i", "--interval", default=DEFAULT_INTERVAL,
                   help="kline interval, e.g. 1d (default), 1h, 4h, 15m")
    p.add_argument("--start", default=DEFAULT_START, help="start month YYYY-MM")
    p.add_argument("--end", default=datetime.now().strftime("%Y-%m"), help="end month YYYY-MM")
    p.add_argument("--out", default=HERE, help="output dir (default: this folder)")
    p.add_argument("--aggtrades", action="store_true", help="ALSO download heavy aggTrades archives")
    p.add_argument("--skip-download", action="store_true", help="only re-aggregate what is on disk")
    args = p.parse_args()

    if args.all_market:
        symbols = fetch_all_usdt_spot_symbols()
    elif args.symbols:
        symbols = args.symbols
    else:
        symbols = list(DEFAULT_SYMBOLS)

    label = "all-market" if args.all_market else f"{len(symbols)} symbols"
    print(f"symbols: {label}" + ("" if args.all_market else f" ({', '.join(symbols)})"))
    print(f"range:   {args.start} .. {args.end}   interval: {args.interval}")
    print(f"out:     {args.out}\n")

    if not args.skip_download:
        for i, symbol in enumerate(symbols, 1):
            n = download_klines(symbol, args.start, args.end, args.out, args.interval)
            print(f"[{i}/{len(symbols)}] {symbol}: {n} kline months on disk")
            if args.aggtrades:
                print(f"{symbol}: fetching aggTrades (heavy)...")
                download_aggtrades(symbol, args.start, args.end, args.out)

    aggregate(symbols, args.out, args.interval)


if __name__ == "__main__":
    main()
