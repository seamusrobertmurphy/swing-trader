"""Friends demo: one visitor's settings, fresh prices, a scored model and paper tickets.

    DEMO_CONFIG='{"data": {...}, ...}' python 03-inputs/demo_run.py \
        --run-id 20260924-abc123 --name Alice --out site/data

Operator design, 24 September 2026: friends configure a model and a market on
the public control centre, press Run, and each run leaves paper trading data
behind, with no one handling the API keys or the code. The page sends the saved
settings through a relay to the demo-run GitHub Actions workflow, which runs
this script. It does four things.

1. Cleans the settings. Every section goes through bench_config.coerce, which
   drops any field the schema does not name, and then through LIMITS, so a
   visitor cannot ask a free runner for a job it cannot finish.
2. Downloads the prices. Monthly Binance archives from data.binance.vision and
   the bars since the last archive from data-api.binance.vision, the public
   market-data mirror, which needs no key and answers from the US.
3. Builds the features with build_dataset_1h.build_coin, under the visitor's
   own barrier, and scores the chosen models exactly as Run the test does,
   through bench_run.score_estimator, against a blind period.
4. Refits the chosen model on every labelled row and rates the newest closed
   bar of each coin. Each rating becomes a paper ticket: an entry price and
   time, the take-profit and stop the label was trained on, and a due time.
   demo_mark.py settles the tickets once they are due.

Crypto only. Equities need Alpaca keys, which would live in the workflow's
secrets, and are left for a second version.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import re
import sys
import time
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench_config as bc          # noqa: E402
import bench_run as br             # noqa: E402
import build_dataset_1h as bd      # noqa: E402
import train_model as tm           # noqa: E402
import train_model_1h as t1        # noqa: E402

REPO = bc.REPO
DATA_ROOT = Path(os.environ.get("DEMO_DATA_ROOT", str(REPO / "demo-cache")))
COST = tm.COST_PCT / 100.0          # 0.20 per cent round trip
# A stock buy and sell together, 0.10 per cent: 5.0 bp of slippage a fill on
# average over 21 paper fills, 04-outputs/AA-evals/2026-09-22/
# execution-report-20260922-1032.md, twice, and Alpaca charges no commission.
COST_STOCK = 0.0010


def cost_of(market: str) -> float:
    return COST_STOCK if market == "equity" else COST

# Binance spot klines, data.binance.vision, https://data.binance.vision/
# (acquire_vision.BASE_URL); the monthly archive path is the documented layout.
ARCHIVE = "https://data.binance.vision/data/spot/monthly/klines/{s}/{f}/{s}-{f}-{m}.zip"
# Binance public market data mirror, https://data-api.binance.vision/
# (paper_trade.py already reads its ticker endpoint); klines take no key.
LIVE = "https://data-api.binance.vision/api/v3/klines?symbol={s}&interval={f}&startTime={t}&limit=1000"

# Every liquid Binance USDT pair, operator's choice of 26 September 2026: a
# 30-day median of at least 10 million USDT traded a day and two years of
# history, so any basket drawn from them has a training window and a test
# year. Stablecoins, gold and tokenised stocks are left out. The list is
# written by refresh_coins() and committed, so the page and the runner agree.
COIN_FILE = Path(__file__).resolve().parent / "demo_coins.json"
COIN_FLOOR, COIN_YEARS = 10_000_000.0, 2
NOT_COINS = {"USDC", "USD1", "RLUSD", "FDUSD", "U", "TUSD", "USDP", "DAI", "EUR", "XAUT", "PAXG"}
COINS = json.loads(COIN_FILE.read_text(encoding="utf-8"))["coins"]
# Binance candle sizes the feature builder handles (build_dataset_1h._FRAME_MIN).
# The minute sizes below 15 and the weekly and monthly ones are left out: the
# first would not finish inside a free runner's 30 minutes, and the second
# leave too few candles for a test year.
FRAMES = ("15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d")

# US stocks and funds for the demo, operator request 25 September 2026: large,
# liquid names with daily history on Alpaca back to 2016, so any basket drawn
# from them has a training window and a blind year. SPY is also the market
# factor, in the seat bitcoin takes for crypto. Stocks run on daily bars only.
STOCKS = ["SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA",
          "JPM", "V", "XOM", "UNH", "JNJ", "WMT", "HD", "KO", "BAC", "COST"]
STOCK_FRAMES = ("1d",)
# Alpaca Market Data API v2, historical stock bars, split and dividend adjusted,
# https://docs.alpaca.markets/docs/historical-api (the link the A1 Datasets
# table already cites). The keys come from the ALPACA_API_KEY and
# ALPACA_API_SECRET secrets on GitHub, or the Keychain on the operator's Mac.
ALPACA_BARS = "https://data.alpaca.markets/v2/stocks/bars"
STOCK_START = "2016-01-01"

# What a free runner can finish inside the workflow's 30-minute limit. The
# served board has none of these, because it runs on the operator's machine.
LIMITS = dict(symbols=6, rows=30000, folds=5, repeats=3, boot_samples=10,
              holdout=(60, 365), estimators=3, grid=9, trees=400, depth=16,
              leaves=127, sel_sample=10000, sel_folds=5, horizon=(2, 72),
              atr=(0.25, 10.0), band=(0.0, 0.05), fits=30)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def sanitize(raw: dict) -> tuple[dict, list[str]]:
    """The visitor's settings, typed by the schema and held inside LIMITS.

    Returns the configuration and one plain line for every value that was
    changed, which the run record prints so the visitor sees what ran.
    """
    cfg = bc.defaults()
    for section in bc.SECTIONS:
        part = raw.get(section) if isinstance(raw, dict) else None
        if isinstance(part, dict):
            cfg[section].update(bc.coerce(section, part))
    notes: list[str] = []

    def clamp(sec, key, lo, hi, what):
        v = cfg[sec].get(key)
        if not isinstance(v, (int, float)):
            return
        w = min(max(v, lo), hi)
        if w != v:
            notes.append(f"{what} {v} was held to {w}")
            cfg[sec][key] = type(v)(w)

    d = cfg["data"]
    if d.get("market") not in ("crypto", "equity"):
        notes.append(f"market {d.get('market')} is not offered in the demo, so crypto was used")
        d["market"] = "crypto"
    stocks = d["market"] == "equity"
    frames, universe = (STOCK_FRAMES, STOCKS) if stocks else (FRAMES, COINS)
    if d.get("frame") not in frames:
        fallback = "1d" if stocks else "4h"
        notes.append(f"timeframe {d.get('frame')} is not offered for "
                     f"{'stocks' if stocks else 'crypto'} in the demo, so {fallback} was used")
        d["frame"] = fallback
    # A quick-pick bundle names coins, so for stocks only typed symbols count.
    asked = [bc.canonical(s) for s in (str(d.get("symbols") or "").split() if stocks
                                       else bc.symbols_for(cfg))]
    keep = [s for s in asked if s in universe][:LIMITS["symbols"]]
    dropped = [s for s in asked if s not in keep]
    if dropped:
        notes.append(f"not in the demo's list of {'stocks' if stocks else 'coins'} or over its "
                     f"limit of {LIMITS['symbols']}, so left out: {', '.join(dropped)}")
    d["symbols"] = " ".join(keep or (["AAPL", "MSFT", "NVDA"] if stocks else ["BTCUSDT", "ETHUSDT"]))
    if stocks:
        # The stock screen of build_dataset_equity: a dollar-volume floor of
        # 20 million a day and a daily range of 1 to 8 per cent of price. The
        # crypto band would drop the calm large companies.
        sc = cfg["screen"]
        want = dict(atr_low=0.01, atr_high=0.08, min_quote_volume=20_000_000.0)
        moved = [k for k, v in want.items() if float(sc.get(k) or 0) != v]
        if moved:
            notes.append("the screen was set for stocks, a daily range of 1 to 8 per cent of "
                         "price and 20 million dollars traded a day")
            sc.update(want)
    if not d.get("rows") or d["rows"] > LIMITS["rows"]:
        notes.append(f"history to load was held to {LIMITS['rows']:,} candles")
        d["rows"] = LIMITS["rows"]

    sp = cfg["split"]
    clamp("split", "holdout_days", *LIMITS["holdout"], "test days")
    clamp("split", "folds", 2, LIMITS["folds"], "folds")
    clamp("split", "repeats", 1, LIMITS["repeats"], "repeats")
    clamp("split", "boot_samples", 2, LIMITS["boot_samples"], "bootstrap samples")
    clamp("split", "purge_bars", 0, 200, "purge bars")
    clamp("split", "embargo_bars", 0, 200, "embargo bars")
    clamp("split", "train_fraction", 0.5, 0.9, "training share")
    if sp.get("scheme") == "leave-one-out":
        notes.append(f"leave-one-out was capped at {LIMITS['fits']} fits")

    lb = cfg["label"]
    clamp("label", "horizon_bars", *LIMITS["horizon"], "horizon")
    clamp("label", "target_atr", *LIMITS["atr"], "take-profit")
    clamp("label", "stop_atr", *LIMITS["atr"], "stop")
    clamp("label", "flat_band", *LIMITS["band"], "break-even band")
    if lb.get("kind") not in ("barrier", "three-way"):
        lb["kind"] = "barrier"

    md = cfg["model"]
    ests = [e for e in (md.get("estimators") or []) if e in bc.ESTIMATORS] or ["RF", "LogReg.glm"]
    if len(ests) > LIMITS["estimators"]:
        notes.append(f"models were held to the first {LIMITS['estimators']}: "
                     + ", ".join(ests[:LIMITS['estimators']]))
    md["estimators"] = ests[:LIMITS["estimators"]]
    if md.get("tune"):
        clamp("model", "tune_length", 0, 3, "how hard to tune")
    for model, params in (md.get("params") or {}).items():
        for k in list(params):
            v = params[k]
            cap = {"n_estimators": LIMITS["trees"], "max_iter": LIMITS["trees"],
                   "max_depth": LIMITS["depth"], "num_leaves": LIMITS["leaves"],
                   "max_leaf_nodes": LIMITS["leaves"]}.get(k)
            if cap and isinstance(v, (int, float)) and v > cap:
                notes.append(f"{model} {k} {v} was held to {cap}")
                params[k] = cap
    clamp("model", "reject_ratio", 1.0, 3.0, "overfit ratio cap")

    clamp("selection", "sel_sample", 2000, LIMITS["sel_sample"], "screen rows")
    clamp("selection", "sel_folds", 3, LIMITS["sel_folds"], "screen folds")
    return cfg, notes


# ---------------------------------------------------------------------------
# Prices
# ---------------------------------------------------------------------------

def _get(url: str, tries: int = 3) -> bytes | None:
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 * (i + 1))
        except Exception:                               # noqa: BLE001
            time.sleep(2 * (i + 1))
    return None


def live_bars(symbol: str, frame: str, start_ms: int) -> list[list]:
    """Closed bars from start_ms to now, paged 1,000 at a time."""
    out, t = [], int(start_ms)
    now_ms = int(time.time() * 1000)
    while True:
        raw = _get(LIVE.format(s=symbol, f=frame, t=t))
        rows = json.loads(raw) if raw else []
        rows = [r for r in rows if int(r[6]) < now_ms]      # drop the bar still forming
        out += rows
        if len(rows) < 999:
            return out
        t = int(rows[-1][0]) + 1


def refresh_coins(log=print) -> list[str]:
    """Rewrite demo_coins.json from Binance's own exchange list and daily candles."""
    import statistics
    # Binance public market data mirror, https://data-api.binance.vision/
    base = "https://data-api.binance.vision/api/v3/"

    def ask(path):
        raw = _get(base + path, tries=6)
        if raw is None:
            raise SystemExit(f"Binance did not answer {path}; the coin list was left as it was")
        return json.loads(raw)

    info = ask("exchangeInfo?permissions=SPOT")
    day24 = {t["symbol"]: float(t["quoteVolume"]) for t in ask("ticker/24hr")}
    since = (datetime.now(timezone.utc) - timedelta(days=365 * COIN_YEARS)).timestamp() * 1000
    keep = []
    for s in info["symbols"]:
        sym, asset = s["symbol"], s["baseAsset"]
        if (s["quoteAsset"] != "USDT" or s["status"] != "TRADING" or asset in NOT_COINS
                or not sym.isascii()):
            continue
        if day24.get(sym, 0) < COIN_FLOOR / 3:       # skip the thin pairs before asking for candles
            continue
        median = statistics.median(float(r[7]) for r in ask(f"klines?symbol={sym}&interval=1d&limit=30"))
        first = ask(f"klines?symbol={sym}&interval=1d&startTime=0&limit=1")[0][0]
        if median >= COIN_FLOOR and first <= since:
            keep.append((median, sym, datetime.fromtimestamp(first / 1000, timezone.utc).strftime("%Y-%m-%d")))
    coins = [s for _, s, _ in sorted(keep, reverse=True)]
    # The first daily candle of each coin, for the page's History to load line.
    first_day = {s: d for _, s, d in keep}
    COIN_FILE.write_text(json.dumps(dict(
        coins=coins, first=first_day, floor=COIN_FLOOR, years=COIN_YEARS,
        written=datetime.now(timezone.utc).strftime("%Y-%m-%d")), indent=1) + "\n", encoding="utf-8")
    log(f"{len(coins)} coins written to {COIN_FILE.name}")
    return coins


def fetch(symbol: str, frame: str, days: int, log=print) -> Path:
    """Monthly archives back `days`, then the bars since, into the archive layout.

    The layout is the one build_dataset_1h.load_coin and bench_run's volume
    floor read, one folder of zips per symbol, so neither needs changing.
    """
    folder = DATA_ROOT / bc.KLINE_ROOTS[frame] / symbol
    folder.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc)
    first = (today - timedelta(days=days)).replace(day=1)
    month, got = first, 0
    this_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    while month < this_month:
        m = month.strftime("%Y-%m")
        f = folder / f"{symbol}-{frame}-{m}.zip"
        if not f.exists():
            raw = _get(ARCHIVE.format(s=symbol, f=frame, m=m))
            if raw:
                f.write_bytes(raw)
                got += 1
        month = (month + timedelta(days=32)).replace(day=1)
    # The archive for the month just ended can lag by a few days, so the live
    # read starts at the end of the newest archive on disk rather than at the
    # first of this month.
    have = sorted(p for p in folder.glob(f"{symbol}-{frame}-????-??.zip"))
    start = this_month
    if have:
        last = have[-1].stem.rsplit("-", 2)
        start = (datetime(int(last[-2]), int(last[-1]), 1, tzinfo=timezone.utc)
                 + timedelta(days=32)).replace(day=1)
    rows = live_bars(symbol, frame, int(start.timestamp() * 1000))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{symbol}-{frame}-recent.csv",
                   "\n".join(",".join(str(v) for v in r) for r in rows))
    (folder / f"{symbol}-{frame}-recent.zip").write_bytes(buf.getvalue())
    log(f"  {symbol} {frame}: {got} archive months fetched, {len(rows):,} recent bars")
    return folder.parent


def _alpaca_keys() -> tuple[str, str]:
    key = os.environ.get("ALPACA_API_KEY", "").strip()
    secret = os.environ.get("ALPACA_API_SECRET", "").strip()
    if not (key and secret):
        try:
            import config                       # the Keychain, on the operator's Mac
            key, secret = config.ALPACA_API_KEY.strip(), config.ALPACA_API_SECRET.strip()
        except Exception:                       # noqa: BLE001
            pass
    if not (key and secret):
        raise SystemExit("stock prices need the Alpaca keys, and none were found")
    return key, secret


def stock_bars(symbols: list[str], start: str, log=print) -> dict[str, list[dict]]:
    """Daily bars for every symbol from `start`, split and dividend adjusted.

    The consolidated feed first and the IEX feed if the account is not served
    it. The request ends twenty minutes ago, because a free account may not
    read the newest consolidated quarter hour.
    """
    import requests
    key, secret = _alpaca_keys()
    head = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    end = (datetime.now(timezone.utc) - timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for feed in ("sip", "iex"):
        out: dict[str, list[dict]] = {s: [] for s in symbols}
        token, ok = None, True
        while True:
            q = dict(symbols=",".join(symbols), timeframe="1Day", start=start, end=end,
                     adjustment="all", feed=feed, limit=10000)
            if token:
                q["page_token"] = token
            r = requests.get(ALPACA_BARS, headers=head, params=q, timeout=60)
            if r.status_code == 403 and feed == "sip":
                ok = False
                break
            r.raise_for_status()
            j = r.json()
            for s, rows in (j.get("bars") or {}).items():
                out.setdefault(s, []).extend(rows)
            token = j.get("next_page_token")
            if not token:
                break
        if ok:
            log(f"  stock prices from Alpaca, {feed} feed, "
                f"{sum(len(v) for v in out.values()):,} daily bars")
            return out
    raise SystemExit("Alpaca served no stock prices")


def stock_rows(bars: list[dict]) -> list[list]:
    """Alpaca daily bars as kline rows, [open ms, open, high, low, close, volume,
    close ms], each bar closing at 16:00 New York, the shape demo_mark settles on.
    The day still trading is left out."""
    ny = "America/New_York"
    today = pd.Timestamp.now(tz=ny)
    out = []
    for b in bars:
        day = pd.Timestamp(b["t"]).tz_convert(ny).normalize()
        shut = day + pd.Timedelta(hours=16)
        if shut + pd.Timedelta(minutes=15) > today:
            continue
        out.append([int((day + pd.Timedelta(hours=9, minutes=30)).timestamp() * 1000),
                    b["o"], b["h"], b["l"], b["c"], b["v"], int(shut.timestamp() * 1000) - 1])
    return out


def build_stock_frame(cfg: dict, log=print) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """The stock twin of build_frame, through build_dataset_equity.

    The bars are written as that module's parquet store, so its reader, its
    calendar check and its SPY market factor run unchanged.
    """
    import build_dataset_equity as be
    syms = cfg["data"]["symbols"].split()
    be.ROOT = str(DATA_ROOT / "alpaca")
    be._TF = "1d"
    store = Path(be.store_dir("1d"))
    store.mkdir(parents=True, exist_ok=True)
    log(f"prices, 1d, {len(syms)} stocks and SPY, from {STOCK_START}")
    got = stock_bars(sorted(set(syms) | {"SPY"}), STOCK_START, log=log)
    for s, bars in got.items():
        rows = stock_rows(bars)
        if not rows:
            continue
        pd.DataFrame({
            "datetime": pd.to_datetime([r[0] for r in rows], unit="ms", utc=True),
            "open": [r[1] for r in rows], "high": [r[2] for r in rows],
            "low": [r[3] for r in rows], "close": [r[4] for r in rows],
            "volume": [r[5] for r in rows],
            "vwap": [b.get("vw", b["c"]) for b in bars][:len(rows)],
            "trade_count": [b.get("n", 0) for b in bars][:len(rows)],
        }).to_parquet(store / f"{s}.parquet", index=False)
    bd.configure("1d")
    lb = cfg["label"]
    bd.LABEL.update(tgt_atr=float(lb["target_atr"]), stp_atr=float(lb["stop_atr"]),
                    horizon_bars=int(lb["horizon_bars"]))
    bd.SCREEN.update(dict(be.SCREEN_OVERRIDES, atr_floor_pct=1.0, atr_ceiling_pct=8.0))
    spy = be.market_series()
    tdays = pd.DatetimeIndex(spy.index)
    labelled, latest = [], []
    for s in syms:
        d = be.load_symbol(s)
        if d.empty:
            log(f"  {s}: no bars, left out")
            continue
        ok, why = be.calendar_quality(d, tdays)
        if not ok:
            log(f"  {s}: left out, {why}")
            continue
        coin = bd.build_coin(d, s, None, spy)
        coin["close"] = d["close"].values
        coin["atr_frac"] = (bd._atr_pct(d, bd.LABEL["atr_len"]) / 100.0).values
        if lb["kind"] == "three-way":
            h = int(lb["horizon_bars"])
            coin["ret3"] = (d["close"].shift(-h) / d["close"] - 1.0).values
        feats = bd.feature_columns(coin)
        last = coin.dropna(subset=feats).tail(1)
        if len(last):
            latest.append(last)
        need = [*feats, "trade_ret" if lb["kind"] == "barrier" else "ret3"]
        coin = coin.dropna(subset=need)
        labelled.append(coin[coin["in_sample"]])
        log(f"  {s}: {len(coin):,} labelled rows, {int(coin['in_sample'].sum()):,} pass the house screen")
    if not labelled:
        raise SystemExit("no stock could be built")
    df = pd.concat(labelled, ignore_index=True).sort_values("datetime").reset_index(drop=True)
    df = df.tail(int(cfg["data"]["rows"])).reset_index(drop=True)
    df["label"] = df["label"].astype(int)
    new = pd.concat(latest, ignore_index=True) if latest else pd.DataFrame()
    return df, new, bd.feature_columns(df)


# ---------------------------------------------------------------------------
# Frame
# ---------------------------------------------------------------------------

def build_frame(cfg: dict, log=print) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Labelled rows for training and scoring, and the newest bar of each coin."""
    if cfg["data"].get("market") == "equity":
        return build_stock_frame(cfg, log=log)
    frame = cfg["data"]["frame"]
    syms = cfg["data"]["symbols"].split()
    bd.configure(frame)
    lb = cfg["label"]
    bd.LABEL.update(tgt_atr=float(lb["target_atr"]), stp_atr=float(lb["stop_atr"]),
                    horizon_bars=int(lb["horizon_bars"]))
    bpd = bc.bars_per_day(frame)
    # Enough days for the longest feature window, the training rows, the blind
    # period and a margin.
    days = int(int(cfg["split"]["holdout_days"]) + 140
               + math.ceil(int(cfg["data"]["rows"]) / max(1, len(syms) * bpd)) + 30)
    days = min(days, 3200)
    log(f"prices, {frame}, {len(syms)} coins and bitcoin, about {days} days")
    root = None
    for s in sorted(set(syms) | {"BTCUSDT"}):
        root = fetch(s, frame, days, log=log)
    btc = bd.load_btc_series(str(root))
    labelled, latest = [], []
    for s in syms:
        d = bd.load_coin(str(root), s)
        if d.empty:
            log(f"  {s}: no bars, left out")
            continue
        slash = f"{s[:-4]}/USDT"
        flow = d[["datetime"]].copy()
        flow["symbol"] = slash
        flow["taker_buy_ratio"] = (d["taker_buy_base"] / d["volume"].replace(0, np.nan)).values
        flow["flow_imbalance"] = 2 * flow["taker_buy_ratio"] - 1
        coin = bd.build_coin(d, slash, flow, btc)
        coin["close"] = d["close"].values
        coin["atr_frac"] = (bd._atr_pct(d, bd.LABEL["atr_len"]) / 100.0).values
        if lb["kind"] == "three-way":
            h = int(lb["horizon_bars"])
            fwd = d["close"].shift(-h) / d["close"] - 1.0
            coin["ret3"] = fwd.values
        feats = bd.feature_columns(coin)
        last = coin.dropna(subset=feats).tail(1)
        if len(last):
            latest.append(last)
        need = [*feats, "trade_ret" if lb["kind"] == "barrier" else "ret3"]
        coin = coin.dropna(subset=need)
        labelled.append(coin[coin["in_sample"]])
        log(f"  {s}: {len(coin):,} labelled rows, {int(coin['in_sample'].sum()):,} pass the house screen")
    if not labelled:
        raise SystemExit("no coin could be built")
    df = pd.concat(labelled, ignore_index=True).sort_values("datetime").reset_index(drop=True)
    df = df.tail(int(cfg["data"]["rows"])).reset_index(drop=True)
    df["label"] = df["label"].astype(int)
    new = pd.concat(latest, ignore_index=True) if latest else pd.DataFrame()
    return df, new, bd.feature_columns(df)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _three_way(ret: np.ndarray, band: float) -> np.ndarray:
    y = np.ones(len(ret), dtype=int)
    y[ret > band] = 2
    y[ret < -band] = 0
    return y


def score(cfg: dict, df: pd.DataFrame, feats: list[str], log=print) -> dict:
    """Every chosen model against the blind period, and the one chosen to trade."""
    df, screen_info = br.apply_screen(cfg, df, log=log)
    feats = br.choose_features(cfg, feats, log=log)
    holdout = int(cfg["split"]["holdout_days"])
    embargo = int(cfg["split"]["embargo_bars"] or 0)
    bpd = bc.bars_per_day(cfg["data"]["frame"])
    gap_days = max(1, math.ceil((embargo or int(cfg["label"]["horizon_bars"])) / bpd))
    train, test, cut = t1.split(df, oos_days=holdout, embargo_days=gap_days)
    if len(train) < 500 or len(test) < 100:
        raise SystemExit(f"the split leaves {len(train):,} training rows and {len(test):,} "
                         f"test rows; load more history or shorten the test period")
    log(f"split at {cut.date()}: {len(train):,} training rows, {len(test):,} test")
    feats = br.cap_features(cfg, train, feats, log=log)
    feats, _sel = br.screen_variables(cfg, train, feats, log=log)
    per_model = cfg["model"].get("params") or {}
    rows = []
    if cfg["label"]["kind"] == "barrier":
        full = []
        for name in cfg["model"]["estimators"]:
            got = br.score_estimator(name, per_model.get(name), cfg, train, test, feats, log=log)
            if got:
                full.append(got[0])
        win, rule = br.choose_winner(full, cfg)
        for r in full:
            rows.append(dict(model=r["model"], params=r["params"], ratio=r["rmse_ratio"],
                             rejected=bool(r["rejected"]), cv_rmse=r["cv"]["rmse"],
                             cv_u2=r["cv"]["theil_u2"], blind_u2=r["blind"]["theil_u2"],
                             blind_rmse=r["blind"]["rmse"], blind_mae=r["blind"]["mae"],
                             blind_bias=r["blind"]["theil_bias"],
                             blind_auc=r["blind_auc"], fold_pass=r["fold_pass_rate"]))
        pick = next((r for r in rows if win is not None and r["model"] == win["model"]), None)
    else:
        import bench_three_way as b3
        band = float(cfg["label"]["flat_band"])
        for d_ in (train, test):
            d_["label"] = _three_way(d_["ret3"].to_numpy(float), band)
        for name in cfg["model"]["estimators"]:
            cw = cfg["model"]["class_weight"]
            folds = br.folds_of(len(train), int(cfg["split"]["folds"]), cfg["split"]["scheme"],
                                repeats=int(cfg["split"].get("repeats") or 3),
                                boot=int(cfg["split"].get("boot_samples") or 5),
                                purge=int(cfg["split"].get("purge_bars") or 0),
                                limit=LIMITS["fits"])
            cv_p, cv_y, cv_r = [], [], []
            for tr, te in folds:
                e = br.make_estimator(name, cw, per_model.get(name))
                if e is None:
                    break
                e.fit(train.iloc[tr][feats], train.iloc[tr]["label"])
                p = np.zeros((len(te), 3)); p[:, list(e.classes_)] = e.predict_proba(train.iloc[te][feats])
                cv_p.append(p); cv_y.append(train.iloc[te]["label"].to_numpy())
                cv_r.append(train.iloc[te]["ret3"].to_numpy(float))
            if not cv_p:
                continue
            est = br.make_estimator(name, cw, per_model.get(name)).fit(train[feats], train["label"])
            p = np.zeros((len(test), 3)); p[:, list(est.classes_)] = est.predict_proba(test[feats])
            fee = cost_of(cfg["data"].get("market"))
            cv = b3._scores(np.concatenate(cv_y), np.vstack(cv_p), np.concatenate(cv_r), fee)
            bl = b3._scores(test["label"].to_numpy(), p, test["ret3"].to_numpy(float), fee)
            rows.append(dict(model=name, params=per_model.get(name) or {}, cv_log_loss=cv["log_loss"],
                             cv_top=cv["after_cost_top"], blind_log_loss=bl["log_loss"],
                             blind_top=bl["after_cost_top"], blind_all=bl["base_after_cost"],
                             blind_accuracy=bl["accuracy"], blind_majority=bl["majority"]))
            log(f"  {name}: cv top fifth {cv['after_cost_top']*100:+.3f}%, test top fifth "
                f"{bl['after_cost_top']*100:+.3f}% against {bl['base_after_cost']*100:+.3f}% for every row")
        pick = min(rows, key=lambda r: r["cv_log_loss"]) if rows else None
        rule = "the lowest cross-validated log loss"
    if pick is None:
        raise SystemExit("no model could be fitted")
    log(f"chosen to trade: {pick['model']}, by {rule}")
    return dict(rows=rows, pick=pick, rule=rule, cut=str(cut.date()), n_train=len(train),
                n_test=len(test), feats=feats, screen=screen_info, train=train, test=test,
                all_rows=pd.concat([train, test], ignore_index=True))


# ---------------------------------------------------------------------------
# Pictures
# ---------------------------------------------------------------------------

# Operator request, 26 September 2026: each user's run draws its own model
# pictures, which C2 shows after the run, so a user sees the result of their
# own design rather than the operator's research figures.
# The account curve is left out: it compounds each candle's trade after the
# last although neighbouring trades share most of their window, which
# overstates every swing many times over.
PICTURES = ("selectivity", "reliability", "importance")
NAMES = {"RF": "Random forest", "LogReg.glm": "Logistic regression",
         "LogReg.enet": "Elastic-net logistic regression", "LightGBM": "LightGBM",
         "HistGBM": "Histogram gradient boosting", "GBM.classic": "Gradient boosting"}


def _bullish():
    from sklearn.base import BaseEstimator, ClassifierMixin

    class Bullish(ClassifierMixin, BaseEstimator):
        """A three-way model read as the chance of a bullish candle, for the pictures."""

        def __init__(self, est=None):
            self.est = est
            self.classes_ = np.array([0, 1])

        def fit(self, *a, **k):
            return self

        def predict_proba(self, x):
            p = np.zeros((len(x), 3))
            p[:, list(self.est.classes_)] = self.est.predict_proba(x)
            return np.c_[1 - p[:, 2], p[:, 2]]
    return Bullish


def pictures(cfg: dict, scored: dict, run_id: str, out: Path, log=print) -> list[dict]:
    """The chosen model's pictures on the run's own test period, one PNG each."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import bench_figures as bf
    train, test, feats = scored["train"], scored["test"].copy(), scored["feats"]
    name = scored["pick"]["model"]
    est = br.make_estimator(name, cfg["model"]["class_weight"],
                            (cfg["model"].get("params") or {}).get(name))
    est.fit(train[feats], train["label"])
    if cfg["label"]["kind"] == "three-way":
        # Bullish against the rest, on the forward return the label was read from.
        est = _bullish()(est)
        test["label"] = (test["label"] == 2).astype(int)
        test["trade_ret"] = test["ret3"]
    p = est.predict_proba(test[feats])[:, 1]
    ctx = dict(est=est, test=test, feats=feats, model=NAMES.get(name, name), p_blind=p,
               y_blind=test["label"].to_numpy(), cost=cost_of(cfg["data"].get("market")))
    folder = out / "runs" / run_id
    folder.mkdir(parents=True, exist_ok=True)
    t, drawn = bf._theme(cfg), []
    for panel in PICTURES:
        try:
            fig = bf.PANELS[panel](cfg, t, ctx)
            fig.savefig(folder / f"{panel}.png", facecolor=t["bg"], bbox_inches="tight", dpi=110)
            plt.close(fig)
            drawn.append(dict(panel=panel, file=f"runs/{run_id}/{panel}.png", what=bf.WHAT[panel]))
        except Exception as e:                          # noqa: BLE001
            log(f"  picture {panel} not drawn: {type(e).__name__}: {e}")
    log(f"pictures: {len(drawn)} drawn")
    return drawn


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------

def tickets(cfg: dict, scored: dict, latest: pd.DataFrame, run_id: str, name: str, log=print) -> list[dict]:
    """One paper ticket per coin: the model's call on its newest closed bar.

    The chosen model is refitted on every labelled row, training and blind
    together, because the blind period has done its job once it is scored and
    the newest months are the ones most like tomorrow. The call is BUY for the
    top third of the basket by the model's score, provided the score clears the
    level that pays: for the barrier, a win probability above the break-even
    stop over target plus stop; for three-way, bullish more likely than bearish.
    Every other coin is a PASS, and a PASS is settled too, so the record says
    what the coins the model declined would have made.
    """
    if latest.empty:
        return []
    pick, feats = scored["pick"], scored["feats"]
    data = scored["all_rows"]
    est = br.make_estimator(pick["model"], cfg["model"]["class_weight"], pick.get("params"))
    est.fit(data[feats], data["label"])
    proba = est.predict_proba(latest[feats])
    classes = list(est.classes_)
    lb = cfg["label"]
    if lb["kind"] == "barrier":
        p_win = proba[:, classes.index(1)] if 1 in classes else np.zeros(len(latest))
        score_ = p_win
        breakeven = float(lb["stop_atr"]) / (float(lb["stop_atr"]) + float(lb["target_atr"]))
        pays = p_win > breakeven
    else:
        full = np.zeros((len(latest), 3)); full[:, classes] = proba
        score_ = full[:, 2] - full[:, 0]
        pays = score_ > 0
    order = np.argsort(-score_)
    top = set(order[:max(1, len(latest) // 3)])
    frame = cfg["data"]["frame"]
    bar = timedelta(hours={"1h": 1, "4h": 4, "1d": 24}[frame])
    h = int(lb["horizon_bars"])
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out = []
    stocks = cfg["data"].get("market") == "equity"
    for i, (_, row) in enumerate(latest.iterrows()):
        if stocks:
            # A stock's daily bar closes at 16:00 New York, and its horizon is
            # counted in trading days.
            opened = (pd.Timestamp(row["datetime"]).tz_localize("America/New_York")
                      + pd.Timedelta(hours=16)).tz_convert("UTC")
            due = (opened.tz_convert("America/New_York") + pd.offsets.BDay(h)).tz_convert("UTC")
        else:
            opened = pd.Timestamp(row["datetime"]).tz_localize("UTC") + bar   # the bar's close
            due = opened + bar * h
        c, a = float(row["close"]), float(row["atr_frac"])
        t = dict(id=f"{run_id}-{row['symbol'].split('/')[0]}", run_id=run_id, name=name,
                 issued=now, market="equity" if stocks else "crypto", frame=frame, symbol=row["symbol"],
                 entry_time=opened.isoformat(), entry_price=c, horizon_bars=h,
                 due=due.isoformat(), outcome=lb["kind"], model=pick["model"],
                 score=round(float(score_[i]), 4),
                 call="BUY" if (i in top and bool(pays[i])) else "PASS",
                 screened=bool(row.get("in_sample", True)), status="open")
        if lb["kind"] == "barrier":
            t.update(target=c * (1 + float(lb["target_atr"]) * a),
                     stop=c * (1 - float(lb["stop_atr"]) * a))
        out.append(t)
        log(f"  {t['symbol']:10s} {t['call']:4s} score {t['score']:+.3f} at {c:g}, due {t['due'][:16]}")
    return out


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--name", default="")
    ap.add_argument("--config-env", default="DEMO_CONFIG",
                    help="the environment variable holding the settings as JSON")
    ap.add_argument("--out", required=True, help="the site's data folder")
    a = ap.parse_args()
    if not re.fullmatch(r"[0-9]{8}-[0-9]{6}-[a-z0-9]{6}", a.run_id):
        raise SystemExit("run id must look like 20260924-153000-abc123")
    name = re.sub(r"[^\w .'-]", "", a.name)[:40].strip() or "anonymous"
    t0 = time.time()
    try:
        raw = json.loads(os.environ.get(a.config_env) or "{}")
    except json.JSONDecodeError:
        raw = {}
    cfg, notes = sanitize(raw)
    for n in notes:
        print(f"  held: {n}")
    # The same cap bench_run's leave-one-out already has, lowered for a free runner.
    _folds = br.folds_of
    br.folds_of = lambda *x, **k: _folds(*x, **{**k, "limit": min(k.get("limit") or LIMITS["fits"], LIMITS["fits"])})
    # The volume floor reads the demo's own downloads, never the operator's archives.
    br._archive_root = lambda c: (DATA_ROOT / "alpaca" / "daily" if c["data"].get("market") == "equity"
                                  else DATA_ROOT / bc.KLINE_ROOTS[c["data"]["frame"]])
    out = Path(a.out)
    (out / "runs").mkdir(parents=True, exist_ok=True)
    record = dict(run_id=a.run_id, name=name, started=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  config=cfg, held=notes, status="failed")
    try:
        df, latest, feats = build_frame(cfg)
        scored = score(cfg, df, feats)
        tix = tickets(cfg, scored, latest, a.run_id, name)
        record.update(status="done", cut=scored["cut"], n_train=scored["n_train"],
                      n_test=scored["n_test"], models=scored["rows"], chosen=scored["pick"]["model"],
                      rule=scored["rule"], features=len(scored["feats"]), tickets=tix)
        try:
            record["figures"] = pictures(cfg, scored, a.run_id, out)
        except Exception as e:                          # noqa: BLE001
            print(f"  pictures not drawn: {type(e).__name__}: {e}")
    except SystemExit as e:
        record["error"] = str(e)
    except Exception as e:                              # noqa: BLE001
        record["error"] = f"{type(e).__name__}: {e}"
    record["seconds"] = round(time.time() - t0)
    (out / "runs" / f"{a.run_id}.json").write_text(json.dumps(record, indent=1, default=str))
    print(f"{record['status']}: {out / 'runs' / (a.run_id + '.json')} in {record['seconds']} seconds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
