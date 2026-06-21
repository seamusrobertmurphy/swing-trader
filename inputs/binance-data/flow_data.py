"""
flow_data.py - scoped Binance historical downloader and daily trade-flow aggregator.

Downloads daily (1d) klines for the model's coin set from data.binance.vision
(free, no API key, no rate limit, deterministic) and aggregates them into a daily
trade-flow imbalance table the model can join as a feature in build_dataset.py.

Why klines and not aggTrades, by default:
  A 1d kline row already carries taker-buy base volume and the trade count, so the
  daily buy-versus-sell pressure is available directly in a few megabytes per coin.
  The multi-gigabyte aggTrades files are only needed if we ever want INTRADAY
  trade-flow resolution. Pass --aggtrades to fetch those as well when that day comes.

What a daily trade-flow imbalance is:
  taker_buy_ratio   = taker_buy_base_volume / volume        (share of volume that
                      lifted the ask, i.e. aggressive buying), in [0, 1]
  flow_imbalance    = 2 * taker_buy_ratio - 1               (signed, in [-1, +1];
                      positive = net aggressive buying on the day)

Outputs (written under this folder, inputs/binance-data/):
  klines/<SYMBOL>/...zip    raw monthly (and trailing-month daily) 1d kline archives
  daily_flow.csv            symbol,date,close,volume,quote_volume,num_trades,
                            taker_buy_base,taker_buy_ratio,flow_imbalance
  aggtrades/<SYMBOL>/...zip  raw aggTrades archives (only when --aggtrades is passed)

Run:
  python flow_data.py                         download + aggregate 1d klines, 10 coins
  python flow_data.py -s BTCUSDT --start 2024-01 --end 2024-03   a scoped slice
  python flow_data.py --aggtrades             ALSO fetch aggTrades (heavy) for later

No API key. No orders. Read-only public data. Plain ASCII output, no icons.
"""

import argparse
import io
import os
import sys
import urllib.error
import urllib.request
import zipfile
from datetime import date, datetime

import pandas as pd

# ----------------------------------------------------------------------------
# Config. COINS mirrors inputs/build_dataset.py so the flow table joins cleanly.
# ----------------------------------------------------------------------------
BASE_URL = "https://data.binance.vision/"
COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "AVAX", "LINK", "LTC", "DOGE"]
DEFAULT_SYMBOLS = [f"{c}USDT" for c in COINS]
INTERVAL = "1d"
DEFAULT_START = "2017-08"   # BTCUSDT spot listing month; earlier 404s skip cleanly
HERE = os.path.dirname(os.path.abspath(__file__))

# Binance spot kline CSV layout (no reliable header in the archives):
#   0 open_time  1 open  2 high  3 low  4 close  5 volume  6 close_time
#   7 quote_volume  8 num_trades  9 taker_buy_base  10 taker_buy_quote  11 ignore
KLINE_COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
              "quote_volume", "num_trades", "taker_buy_base", "taker_buy_quote", "ignore"]


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


def kline_url(symbol, period, kind):
    """period 'YYYY-MM' (monthly) or 'YYYY-MM-DD' (daily); kind in {monthly,daily}."""
    return (f"{BASE_URL}data/spot/{kind}/klines/{symbol}/{INTERVAL}/"
            f"{symbol}-{INTERVAL}-{period}.zip")


def aggtrade_url(symbol, period, kind):
    return (f"{BASE_URL}data/spot/{kind}/aggTrades/{symbol}/"
            f"{symbol}-aggTrades-{period}.zip")


def download_klines(symbol, start_ym, end_ym, out_dir):
    """Download monthly 1d klines; for any month with no monthly file yet (the
    current, still-open month), fall back to that month's daily files. Skips files
    already on disk so reruns are cheap."""
    sym_dir = os.path.join(out_dir, "klines", symbol)
    got = 0
    today = date.today()
    for y, m in month_iter(start_ym, end_ym):
        period = f"{y}-{m:02d}"
        dest = os.path.join(sym_dir, f"{symbol}-{INTERVAL}-{period}.zip")
        if os.path.exists(dest):
            got += 1
            continue
        raw = fetch(kline_url(symbol, period, "monthly"))
        if raw is not None:
            save(raw, dest)
            got += 1
            continue
        # No monthly file: if this is the current (open) month, grab daily files.
        if (y, m) == (today.year, today.month):
            last_day = today.day
            for d in range(1, last_day + 1):
                dperiod = f"{y}-{m:02d}-{d:02d}"
                ddest = os.path.join(sym_dir, f"{symbol}-{INTERVAL}-{dperiod}.zip")
                if os.path.exists(ddest):
                    continue
                draw = fetch(kline_url(symbol, dperiod, "daily"))
                if draw is not None:
                    save(draw, ddest)
    return got


def download_aggtrades(symbol, start_ym, end_ym, out_dir):
    """Heavy. Monthly aggTrades only; the current open month is left to a later
    incremental pass. Skips files already on disk."""
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
    """Binance switched some 2025 archives from ms to microsecond timestamps.
    Detect by magnitude and parse to a date."""
    v = pd.to_numeric(series, errors="coerce")
    unit = "us" if v.dropna().iloc[0] > 1e14 else "ms"
    return pd.to_datetime(v, unit=unit)


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


def aggregate(symbols, out_dir):
    """Roll every downloaded kline zip into one daily trade-flow table."""
    rows = []
    for symbol in symbols:
        sym_dir = os.path.join(out_dir, "klines", symbol)
        if not os.path.isdir(sym_dir):
            continue
        frames = []
        for fn in sorted(os.listdir(sym_dir)):
            if not fn.endswith(".zip"):
                continue
            try:
                frames.append(read_kline_zip(os.path.join(sym_dir, fn)))
            except Exception as e:
                print(f"  skip {fn}: {e}")
        if not frames:
            continue
        d = pd.concat(frames, ignore_index=True)
        d["date"] = _to_datetime(d["open_time"]).dt.date
        for c in ["close", "volume", "quote_volume", "num_trades", "taker_buy_base"]:
            d[c] = pd.to_numeric(d[c], errors="coerce")
        d = d.dropna(subset=["volume"]).drop_duplicates("date").sort_values("date")
        d = d[d["volume"] > 0].copy()
        d["taker_buy_ratio"] = d["taker_buy_base"] / d["volume"]
        d["flow_imbalance"] = 2 * d["taker_buy_ratio"] - 1
        d["symbol"] = f"{symbol[:-4]}/USDT" if symbol.endswith("USDT") else symbol
        rows.append(d[["symbol", "date", "close", "volume", "quote_volume",
                       "num_trades", "taker_buy_base", "taker_buy_ratio",
                       "flow_imbalance"]])
    if not rows:
        print("nothing to aggregate; no kline zips found.")
        return None
    out = pd.concat(rows, ignore_index=True)
    dest = os.path.join(out_dir, "daily_flow.csv")
    out.to_csv(dest, index=False)
    print(f"\nwrote {len(out)} daily rows for {out['symbol'].nunique()} coins -> {dest}")
    print(out.groupby("symbol")["flow_imbalance"].agg(["count", "mean"]).round(3).to_string())
    return out


def main():
    p = argparse.ArgumentParser(description="Scoped Binance kline downloader + daily trade-flow aggregator")
    p.add_argument("-s", "--symbols", nargs="+", default=DEFAULT_SYMBOLS,
                   help="symbols like BTCUSDT (default: the 10 model coins)")
    p.add_argument("--start", default=DEFAULT_START, help="start month YYYY-MM")
    p.add_argument("--end", default=datetime.now().strftime("%Y-%m"), help="end month YYYY-MM")
    p.add_argument("--out", default=HERE, help="output dir (default: this folder)")
    p.add_argument("--aggtrades", action="store_true", help="ALSO download heavy aggTrades archives")
    p.add_argument("--skip-download", action="store_true", help="only re-aggregate what is on disk")
    args = p.parse_args()

    print(f"symbols: {', '.join(args.symbols)}")
    print(f"range:   {args.start} .. {args.end}   interval: {INTERVAL}")
    print(f"out:     {args.out}\n")

    if not args.skip_download:
        for symbol in args.symbols:
            n = download_klines(symbol, args.start, args.end, args.out)
            print(f"{symbol}: {n} kline months on disk")
            if args.aggtrades:
                print(f"{symbol}: fetching aggTrades (heavy)...")
                download_aggtrades(symbol, args.start, args.end, args.out)

    aggregate(args.symbols, args.out)


if __name__ == "__main__":
    main()
