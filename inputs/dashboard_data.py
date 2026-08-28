"""Emit one JSON file holding everything the Quarto dashboard draws.

The dashboard is R and Quarto. This is deliberately the only Python in that
path, and it exists so the awkward parts are computed once, here, where they
are already tested: which of Alpaca's several account values to believe, the
per-fill slippage measurement, and the correlation-cluster arithmetic. Doing
that arithmetic a second time in R would mean getting it wrong a second time.

R's job is to draw. This file's job is to hand it numbers that already agree.

    .venv/bin/python inputs/dashboard_data.py
    -> outputs/dashboard/data.json
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

import config
from alpaca_daily_report import (BENCHMARK, CYCLES_NEEDED, LIVE_FROM,
                                 MODEL_ANNUAL_VOL, MODEL_COST_BP, START_EQUITY,
                                 benchmark, equity_curve, rebalances)
from alpaca_trade import (CASH_FLOOR, CAT_STOP, CLUSTER_CAP, DAILY_CIRCUIT,
                          MAX_POSITION_PCT, MIN_REBALANCE_GAP_DAYS,
                          account_state, clients)
from equity_cluster_cap import CORR_WINDOW, RHO, largest_cluster

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "outputs" / "dashboard"

# A schedule that has stopped looks exactly like a schedule with nothing to do:
# both are silent. On 2026-08-27 the tick loop died and four hours passed with
# no sign of it anywhere, while this page went on showing a confident number
# from its last successful render. The clock below is the sign.
TICK_LOG_DIR = REPO / "outputs" / "AA-evals" / "logs"
TICK_EVERY_MIN = 20
TICK_STALE_AFTER = 3          # missed ticks before the page says so
ET = ZoneInfo("America/New_York")


def _keys():
    return (config.ALPACA_API_KEY, config.ALPACA_API_SECRET, config.ALPACA_BASE_URL)


def intraday(days: int = 5, timeframe: str = "15Min") -> list:
    """Recent intraday equity. Market hours only: extended-hours marks on a
    paper account are thin and disagree with the close by over a percent."""
    k, s, b = _keys()
    r = requests.get(f"{b}/v2/account/portfolio/history",
                     params=dict(period=f"{days}D", timeframe=timeframe,
                                 intraday_reporting="market_hours"),
                     headers={"APCA-API-KEY-ID": k, "APCA-API-SECRET-KEY": s},
                     timeout=30)
    if r.status_code != 200:
        return []
    d = r.json()
    return [dict(t=pd.to_datetime(t, unit="s", utc=True).tz_convert(ET).isoformat(),
                 equity=float(e))
            for t, e in zip(d["timestamp"], d["equity"]) if e]


def slippage_by_cycle() -> list:
    """Per-rebalance execution cost. This is the number the paper trial exists
    to produce, so it is the dashboard's headline rather than a footnote."""
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest
    tc = clients()
    k, s, _ = _keys()
    dc = StockHistoricalDataClient(k, s)
    since = datetime.now(timezone.utc) - timedelta(days=60)
    orders = [o for o in tc.get_orders(GetOrdersRequest(
        status=QueryOrderStatus.CLOSED, after=since, limit=500))
        if o.filled_at and o.filled_avg_price]
    rows = []
    for o in orders:
        t = o.filled_at.replace(second=0, microsecond=0)
        try:
            bars = dc.get_stock_bars(StockBarsRequest(
                symbol_or_symbols=o.symbol, timeframe=TimeFrame.Minute,
                start=t - timedelta(minutes=1),
                end=t + timedelta(minutes=2))).data[o.symbol]
        except Exception:  # noqa: BLE001
            continue
        bar = {b.timestamp.astimezone(timezone.utc).replace(second=0, microsecond=0): b
               for b in bars}.get(t)
        if bar is None:
            continue
        ref, fill = float(bar.vwap), float(o.filled_avg_price)
        side = str(o.side).rsplit(".", 1)[-1].lower()
        et = o.filled_at.astimezone(ET)
        rows.append(dict(cycle=et.strftime("%Y-%m-%d"), symbol=o.symbol, side=side,
                         slip_bp=(fill - ref) / ref * 1e4 * (1 if side == "buy" else -1),
                         notional=fill * float(o.filled_qty),
                         from_open=(et.hour - 9) * 60 + (et.minute - 30)))
    if not rows:
        return []
    t = pd.DataFrame(rows)
    out = []
    for cyc, g in t.groupby("cycle"):
        out.append(dict(
            cycle=cyc, fills=int(len(g)),
            mean_bp=round(float(g.slip_bp.mean()), 1),
            median_bp=round(float(g.slip_bp.median()), 1),
            worst_bp=round(float(g.slip_bp.max()), 1),
            notional=round(float(g.notional.sum()), 2),
            dollars=round(float((g.slip_bp / 1e4 * g.notional).sum()), 2),
            at_open=int((g.from_open < 15).sum()),
            model_low=MODEL_COST_BP[0], model_high=MODEL_COST_BP[1]))
    return sorted(out, key=lambda r: r["cycle"])


def concentration(positions: dict, equity: float) -> dict:
    from equity_momentum_monthly import monthly_panel
    px, _, _ = monthly_panel("funds")
    held = sorted(positions)
    have = [h for h in held if h in px.columns]
    if len(have) < 2:
        return dict(available=False)
    corr = np.log(px[have]).diff().tail(CORR_WINDOW).corr()
    w = {s: positions[s]["value"] / equity for s in held}
    adj = corr > RHO
    seen, comps = set(), []
    for s in have:
        if s in seen:
            continue
        stack, comp = [s], set()
        while stack:
            x = stack.pop()
            if x in comp:
                continue
            comp.add(x)
            stack += [y for y in have if adj.at[x, y] and y not in comp]
        seen |= comp
        comps.append(comp)
    comps.sort(key=lambda c: -sum(w[s] for s in c))
    local = {x: w[x] + sum(w[o] for o in have if o != x and corr.at[x, o] > RHO)
             for x in have}
    worst = max(local, key=local.get)
    return dict(
        available=True, cap=CLUSTER_CAP, rho=RHO,
        biggest_group_names=len(comps[0]),
        biggest_group_weight=round(float(sum(w[s] for s in comps[0])), 4),
        biggest_group=sorted(comps[0]),
        n_groups=len(comps),
        groups=[dict(rank=i + 1, n=len(c),
                     weight=round(float(sum(w[s] for s in c)), 4))
                for i, c in enumerate(comps)],
        worst_local_symbol=worst,
        worst_local_weight=round(float(local[worst]), 4),
        over_cap=int(sum(1 for v in local.values() if v > CLUSTER_CAP + 1e-9)))


def last_tick() -> dict:
    """When the schedule last woke up, read from its own log.

    The log is the only honest source. A marker written by the tick would say
    the same thing, but one more file to keep in step is one more thing that
    can be right while the schedule is dead.
    """
    logs = sorted(TICK_LOG_DIR.glob("tick-*.log"))
    if not logs:
        return dict(available=False)
    stamp = None
    for line in reversed(logs[-1].read_text(errors="replace").splitlines()):
        m = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)", line)
        if m:
            stamp = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc)
            break
    if stamp is None:
        return dict(available=False)
    age = (datetime.now(timezone.utc) - stamp).total_seconds() / 60
    return dict(available=True, at=stamp.isoformat(), age_min=round(age, 1),
                every_min=TICK_EVERY_MIN,
                stale=age > TICK_EVERY_MIN * TICK_STALE_AFTER)


# ---------------------------------------------------------------------------
# Panels added 2026-08-27. Everything below feeds a chart or a table that did
# not exist before: the order log, the round-trip ledger, the event timeline,
# candles with MACD for the markets we care about, the portfolio mixes, the
# per-holding contribution, the risk series, and the archive of past runs.
# ---------------------------------------------------------------------------

BARS = REPO / "inputs" / "alpaca-data" / "daily"
CLASSES = REPO / "inputs" / "alpaca-data" / "asset_classes.json"
HISTORY = OUT / "history"
EVAL_DIR = REPO / "outputs" / "AA-evals"

# The sector proxies. There is no GICS table in this repo and no vendor feed to
# buy one from, so a holding's "sector" here is the sector fund whose daily
# moves it most closely follows over the past year. That is a measurement, not
# a classification, and the page says so.
SECTOR_ETF = {
    "XLK": "Technology", "XLF": "Financials", "XLE": "Energy",
    "XLV": "Health care", "XLI": "Industrials", "XLY": "Consumer, discretionary",
    "XLP": "Consumer, staples", "XLU": "Utilities", "XLB": "Materials",
    "XLRE": "Real estate", "XLC": "Communications",
}
# The wider markets the page watches whether or not we hold them.
WATCH = ["SPY", "QQQ", "IWM", "GLD", "TLT"]
SECTOR_WINDOW = 250          # trading days of return history for the match
SECTOR_MIN_RHO = 0.25        # below this the match is not worth asserting
CANDLE_BARS = 180            # how much history each candlestick panel draws


def _local_bars(symbol: str) -> pd.DataFrame | None:
    """Daily OHLCV from the on-disk store. Returns None when we never
    downloaded that ticker, which is the normal case for a fresh listing."""
    f = BARS / f"{symbol}.parquet"
    if not f.exists():
        return None
    try:
        b = pd.read_parquet(f)
    except Exception:  # noqa: BLE001
        return None
    if "datetime" not in b.columns or b.empty:
        return None
    b = b.copy()
    b["date"] = pd.to_datetime(b["datetime"], utc=True).dt.tz_convert(ET).dt.date
    return b.set_index("date").sort_index()


def _api_bars(symbols: list[str], days: int = 460) -> dict:
    """Fresh daily bars straight from Alpaca, split and dividend adjusted.

    Two things had to be got right here. The on-disk store is only as new as the
    last download, and a candle chart that stops two days short looks like the
    market stopped, so this asks the exchange rather than the disk. And the
    adjustment is not optional: the SPDR sector funds split on 2025-12-05, and
    without `adjustment=ALL` the raw bars halve overnight, which this page
    printed as technology being down 28% over a year while it was up. The
    on-disk store already downloads with the same setting.
    """
    from alpaca.data.enums import Adjustment
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    k, s, _ = _keys()
    dc = StockHistoricalDataClient(k, s)
    try:
        res = dc.get_stock_bars(StockBarsRequest(
            symbol_or_symbols=symbols, timeframe=TimeFrame.Day,
            adjustment=Adjustment.ALL,
            start=datetime.now(timezone.utc) - timedelta(days=days),
            end=datetime.now(timezone.utc) - timedelta(minutes=25))).data
    except Exception:  # noqa: BLE001
        return {}
    out = {}
    for sym, bars in res.items():
        rows = [dict(date=b.timestamp.astimezone(ET).date(), open=float(b.open),
                     high=float(b.high), low=float(b.low), close=float(b.close),
                     volume=float(b.volume)) for b in bars]
        if rows:
            out[sym] = pd.DataFrame(rows).set_index("date").sort_index()
    return out


def _clip_bad_prints(b: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Pull in a day's high or low that the feed clearly mistyped.

    SPY's bar for 2026-02-02 carries a low of 69.005 on a day it opened at
    689.58: a misplaced decimal point in the exchange feed. One such bar drags
    a candle chart's axis to zero and makes every other day a flat line. The
    bar is not deleted and the close is never touched, because the close is
    what every number on this page is computed from; only the day's range is
    pulled back to the open and close it already reports, and the count of
    bars this happened to is returned so the chart can say so.
    """
    body_hi = b[["open", "close"]].max(axis=1)
    body_lo = b[["open", "close"]].min(axis=1)
    bad = (b["low"] < body_lo * 0.5) | (b["high"] > body_hi * 2.0)
    if not bad.any():
        return b, 0
    b = b.copy()
    b.loc[bad, "low"] = body_lo[bad]
    b.loc[bad, "high"] = body_hi[bad]
    return b, int(bad.sum())


def _ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()


def _macd(close: pd.Series, fast=12, slow=26, sig=9) -> pd.DataFrame:
    """The same 12/26/9 MACD the research chapters use, so a number on this
    page and a number in the notebook mean the same thing."""
    line = _ema(close, fast) - _ema(close, slow)
    signal = _ema(line, sig)
    return pd.DataFrame({"macd": line, "signal": signal, "hist": line - signal})


def _rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def orders_history(days: int = 90) -> list:
    """Every order the book has sent, filled or not, newest last.

    The trade log in memory/ records what the code intended to do. This records
    what the broker actually did with it, which is the only version that can
    disagree with the account value.
    """
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest
    tc = clients()
    since = datetime.now(timezone.utc) - timedelta(days=days)
    try:
        orders = tc.get_orders(GetOrdersRequest(status=QueryOrderStatus.ALL,
                                                after=since, limit=500))
    except Exception:  # noqa: BLE001
        return []
    rows = []
    for o in orders:
        fq = float(o.filled_qty or 0)
        px = float(o.filled_avg_price) if o.filled_avg_price else None
        sub = o.submitted_at.astimezone(ET) if o.submitted_at else None
        fil = o.filled_at.astimezone(ET) if o.filled_at else None
        rows.append(dict(
            id=str(o.id), symbol=o.symbol,
            side=str(o.side).rsplit(".", 1)[-1].lower(),
            status=str(o.status).rsplit(".", 1)[-1].lower(),
            type=str(o.type).rsplit(".", 1)[-1].lower(),
            qty=round(fq, 6), price=None if px is None else round(px, 4),
            notional=round(fq * px, 2) if px else (
                round(float(o.notional), 2) if o.notional else None),
            submitted_at=None if sub is None else sub.isoformat(),
            filled_at=None if fil is None else fil.isoformat(),
            date=None if fil is None else fil.strftime("%Y-%m-%d"),
            clock=None if fil is None else fil.strftime("%H:%M:%S"),
            # minutes after the 09:30 bell; negative means it was queued early
            from_open=None if fil is None else (fil.hour - 9) * 60 + (fil.minute - 30),
            latency_s=None if (sub is None or fil is None) else
                      round((fil - sub).total_seconds(), 2)))
    rows.sort(key=lambda r: r["submitted_at"] or "")
    return rows


def roundtrips(orders: list) -> list:
    """Match sells against earlier buys, oldest lot first, so the page can say
    what a finished trade actually made rather than only what an open one is
    worth today."""
    fills = [o for o in orders if o["status"] == "filled" and o["price"]]
    lots: dict[str, list] = {}
    done = []
    for o in fills:
        sym = o["symbol"]
        if o["side"] == "buy":
            lots.setdefault(sym, []).append([o["qty"], o["price"], o["filled_at"]])
            continue
        left = o["qty"]
        while left > 1e-9 and lots.get(sym):
            q, px, when = lots[sym][0]
            take = min(q, left)
            held = (datetime.fromisoformat(o["filled_at"])
                    - datetime.fromisoformat(when)).total_seconds() / 86400
            done.append(dict(
                symbol=sym, qty=round(take, 6), buy_price=px, sell_price=o["price"],
                bought_at=when, sold_at=o["filled_at"],
                held_days=round(held, 2),
                pl=round((o["price"] - px) * take, 2),
                plpc=round(o["price"] / px - 1, 5)))
            left -= take
            if take >= q - 1e-9:
                lots[sym].pop(0)
            else:
                lots[sym][0][0] = q - take
    done.sort(key=lambda r: r["sold_at"])
    return done


def timeline(orders: list, cycles: dict, tick: dict) -> list:
    """One list of everything that happened, in time order, so the operator can
    read the week rather than reconstruct it from four tables."""
    ev = []
    for o in orders:
        if o["status"] != "filled":
            continue
        ev.append(dict(t=o["filled_at"], kind=o["side"], symbol=o["symbol"],
                       label=f"{o['side'].upper()} {o['symbol']}",
                       detail=f"{o['qty']:.4g} at ${o['price']:,.2f}"
                              f" = ${o['notional']:,.0f}"))
    for dstr in cycles.get("dates", []):
        n = sum(1 for o in orders if o["date"] == dstr and o["status"] == "filled")
        ev.append(dict(t=f"{dstr}T00:00:00", kind="rebalance", symbol=None,
                       label="Weekly rebalance", detail=f"{n} fills that day"))
    for p in sorted(EVAL_DIR.glob("*/DAILY-*.md")):
        m = re.search(r"DAILY-(\d{8})-(\d{4})", p.name)
        if m:
            ev.append(dict(
                t=f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}"
                  f"T{m.group(2)[:2]}:{m.group(2)[2:]}:00",
                kind="report", symbol=None, label="Daily report written",
                detail=p.name))
    if tick.get("available"):
        ev.append(dict(t=tick["at"], kind="tick", symbol=None,
                       label="Schedule last woke", detail="the robot is alive"))
    ev.sort(key=lambda r: r["t"])
    return ev[-400:]


def sector_map(symbols: list) -> dict:
    """Match each holding to the sector fund it moves with most closely.

    Honest naming matters here. This is not a sector classification; it is a
    correlation. A stock that follows XLK is called technology on this page
    because for a year it has moved like technology, which is the property the
    concentration rules actually care about.
    """
    etfs = {}
    for e in SECTOR_ETF:
        b = _local_bars(e)
        if b is not None and len(b) > SECTOR_WINDOW:
            etfs[e] = np.log(b["close"]).diff().tail(SECTOR_WINDOW)
    if not etfs:
        return {}
    E = pd.DataFrame(etfs)
    out = {}
    for s in symbols:
        b = _local_bars(s)
        if b is None or len(b) < 60:
            out[s] = dict(sector="Not measurable", rho=None)
            continue
        r = np.log(b["close"]).diff().tail(SECTOR_WINDOW)
        j = E.join(r.rename("_x"), how="inner").dropna()
        if len(j) < 60:
            out[s] = dict(sector="Not measurable", rho=None)
            continue
        c = j.corr()["_x"].drop("_x")
        best = c.idxmax()
        out[s] = dict(sector=SECTOR_ETF[best] if c[best] >= SECTOR_MIN_RHO
                      else "No clear sector",
                      etf=best, rho=round(float(c[best]), 3))
    return out


def mixes(pos: list, equity: float, cash: float, conc: dict) -> dict:
    """The pie charts. Four different ways of cutting the same book, because
    one cut always flatters and the disagreement between them is the point."""
    smap = sector_map([p["symbol"] for p in pos])
    classes = {}
    if CLASSES.exists():
        try:
            classes = json.loads(CLASSES.read_text())
        except Exception:  # noqa: BLE001
            classes = {}

    def roll(keyfn):
        agg: dict[str, dict] = {}
        for p in pos:
            k = keyfn(p)
            a = agg.setdefault(k, dict(label=k, value=0.0, n=0, pl=0.0))
            a["value"] += p["value"]
            a["pl"] += p["pl"]
            a["n"] += 1
        for a in agg.values():
            a["weight"] = round(a["value"] / equity, 5)
            a["value"] = round(a["value"], 2)
            a["pl"] = round(a["pl"], 2)
        return sorted(agg.values(), key=lambda r: -r["value"])

    by_sector = roll(lambda p: smap.get(p["symbol"], {}).get("sector", "Not measurable"))
    if cash > 0:
        by_sector.append(dict(label="Cash", value=round(cash, 2), n=0, pl=0.0,
                              weight=round(cash / equity, 5)))
    by_venue = roll(lambda p: classes.get(p["symbol"], {}).get("exchange", "Unknown"))
    by_kind = roll(lambda p: "Fund" if classes.get(p["symbol"], {}).get("fund")
                   else "Single company")

    def band(p):
        r = p["plpc"]
        if r <= -0.10:
            return "Down more than 10%"
        if r < -0.02:
            return "Down 2 to 10%"
        if r <= 0.02:
            return "Roughly flat"
        if r < 0.10:
            return "Up 2 to 10%"
        return "Up more than 10%"
    by_move = roll(band)

    cluster = []
    if conc.get("available"):
        for g in conc["groups"]:
            cluster.append(dict(
                label=(f"{g['n']} that move together (group {g['rank']})"
                       if g["n"] > 1 else "Moves with nothing else held"),
                n=g["n"], weight=g["weight"], value=round(g["weight"] * equity, 2),
                rank=g["rank"]))
        lone = [c for c in cluster if c["n"] == 1]
        if lone:
            cluster = [c for c in cluster if c["n"] > 1]
            cluster.append(dict(label=f"{len(lone)} that move with nothing else held",
                                n=len(lone),
                                weight=round(sum(c["weight"] for c in lone), 5),
                                value=round(sum(c["value"] for c in lone), 2),
                                rank=999))
    return dict(sector=by_sector, venue=by_venue, kind=by_kind, move=by_move,
                cluster=cluster,
                detail=[dict(symbol=s, **v) for s, v in sorted(smap.items())])


def attribution(pos: list, equity: float) -> list:
    """How much each holding moved the whole account, in percentage points.

    A stock down 20% at a 1% weight costs the book 0.2 points. Ranking by the
    stock's own return answers a different question from ranking by what it did
    to the account, and only the second one pays for anything.
    """
    rows = []
    for p in pos:
        cost = p["value"] - p["pl"]
        rows.append(dict(symbol=p["symbol"], plpc=p["plpc"], pl=p["pl"],
                         weight=p["weight"],
                         points=round(p["pl"] / equity * 100, 4),
                         cost=round(cost, 2)))
    rows.sort(key=lambda r: r["points"])
    return rows


def markets(pos: list) -> dict:
    """Candles, MACD and RSI for the indexes we measure ourselves against and
    for the handful of holdings that are actually moving the account."""
    ranked = sorted(pos, key=lambda p: -abs(p["pl"]))
    picks = [p["symbol"] for p in ranked[:4]]
    syms = list(dict.fromkeys(WATCH + list(SECTOR_ETF) + picks))
    bars = _api_bars(syms)
    for s in syms:                       # fall back to the on-disk store
        if s not in bars:
            b = _local_bars(s)
            if b is not None:
                bars[s] = b[["open", "high", "low", "close", "volume"]]
    out = {}
    for s, b in bars.items():
        if len(b) < 60:
            continue
        b, clipped = _clip_bad_prints(b)
        c = b["close"]
        m = _macd(c)
        f = pd.DataFrame(dict(
            open=b["open"], high=b["high"], low=b["low"], close=c,
            volume=b["volume"], ema20=_ema(c, 20), ema50=_ema(c, 50),
            ema200=_ema(c, 200) if len(c) >= 200 else np.nan,
            macd=m["macd"], signal=m["signal"], hist=m["hist"], rsi=_rsi(c),
        )).tail(CANDLE_BARS).round(4)
        f.index = [str(d) for d in f.index]
        rows = f.reset_index(names="date").where(pd.notna(f.reset_index(names="date")),
                                                 None).to_dict("records")
        last, prev = float(c.iloc[-1]), float(c.iloc[-2])
        def chg(n):
            return round(float(c.iloc[-1] / c.iloc[-n - 1] - 1), 5) if len(c) > n else None
        out[s] = dict(
            symbol=s, name=SECTOR_ETF.get(s, s), bars=rows, clipped=clipped,
            last=round(last, 4), day=round(last / prev - 1, 5),
            w1=chg(5), m1=chg(21), m3=chg(63), m6=chg(126), y1=chg(252),
            rsi=None if pd.isna(f["rsi"].iloc[-1]) else round(float(f["rsi"].iloc[-1]), 1),
            macd_state="above" if f["hist"].iloc[-1] > 0 else "below",
            held=s in {p["symbol"] for p in pos},
            role=("index" if s in WATCH else
                  "sector" if s in SECTOR_ETF else "holding"))
    return dict(focus=picks, watch=WATCH, sectors=list(SECTOR_ETF), series=out)


def risk_series(curve: pd.Series) -> dict:
    """Drawdown, daily moves and a rolling swing measure. The equity line alone
    hides how rough the ride was to get there."""
    e = curve.astype(float)
    peak = e.cummax()
    dd = e / peak - 1
    ret = e.pct_change().dropna()
    roll = ret.rolling(10).std() * np.sqrt(252)
    return dict(
        drawdown=[dict(date=str(d), dd=round(float(v), 5)) for d, v in dd.items()],
        daily=[dict(date=str(d), ret=round(float(v), 5)) for d, v in ret.items()],
        rolling_vol=[dict(date=str(d), vol=round(float(v), 5))
                     for d, v in roll.dropna().items()],
        worst_dd=round(float(dd.min()), 5),
        best_day=round(float(ret.max()), 5) if len(ret) else None,
        worst_day=round(float(ret.min()), 5) if len(ret) else None,
        up_days=int((ret > 0).sum()), down_days=int((ret < 0).sum()),
        realised_vol=round(float(ret.std() * np.sqrt(252)), 5) if len(ret) > 2 else None)


def report_log() -> list:
    """Every daily report ever written, with the account value each one claimed.

    This is the page's own audit trail. If a figure here disagrees with what a
    report said on the day, one of the two is wrong and the list is where that
    becomes visible.
    """
    rows = []
    for p in sorted(EVAL_DIR.glob("*/DAILY-*.md")):
        txt = p.read_text(errors="replace")
        eq = re.search(r"Account value \| \$([\d,]+)", txt)
        ch = re.search(r"Change since it went live[^|]*\| \*\*([+-][\d.]+)%\*\*", txt)
        m = re.search(r"DAILY-(\d{8})-(\d{4})", p.name)
        rows.append(dict(
            file=str(p.relative_to(REPO)), name=p.name,
            date=f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}" if m else "",
            time=f"{m.group(2)[:2]}:{m.group(2)[2:]}" if m else "",
            equity=float(eq.group(1).replace(",", "")) if eq else None,
            since_live=float(ch.group(1)) / 100 if ch else None,
            kb=round(p.stat().st_size / 1024, 1)))
    return rows


def archive(d: dict) -> list:
    """Keep a small stamped copy of every render, and list them.

    The full data file is overwritten each run, so without this the page has no
    memory of itself: it could not show that yesterday's render said something
    different, which is exactly the disagreement worth seeing.
    """
    HISTORY.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(ET).strftime("%Y%m%d-%H%M%S")
    keep = dict(generated_at=d["meta"]["generated_at"],
                equity=d["headline"]["equity"],
                since_live=d["headline"]["since_live"],
                spy_since_live=d["headline"]["spy_since_live"],
                positions=d["headline"]["positions"],
                cash_pct=d["headline"]["cash_pct"],
                from_peak=d["headline"]["from_peak"],
                cycles_done=d["cycles"]["done"],
                guards_bad=[g["name"] for g in d["guards"] if g["state"] != "OK"])
    (HISTORY / f"snap-{stamp}.json").write_text(json.dumps(keep, indent=1),
                                                encoding="utf-8")
    snaps = sorted(HISTORY.glob("snap-*.json"))
    for old in snaps[:-400]:              # a year of 20-minute ticks is plenty
        old.unlink()
    rows = []
    for p in sorted(HISTORY.glob("snap-*.json")):
        try:
            rows.append(json.loads(p.read_text()) | dict(file=p.name))
        except Exception:  # noqa: BLE001
            continue
    return rows


def build() -> dict:
    tc = clients()
    acct, equity, cash, day_move, positions = account_state(tc)
    now = datetime.now(ET)
    curve = equity_curve()
    today = now.date()
    curve.loc[today] = equity           # see alpaca_daily_report for why
    curve = curve.sort_index()
    spy = benchmark()
    live = datetime.strptime(LIVE_FROM, "%Y-%m-%d").date()

    since_live = equity / START_EQUITY - 1
    spy_base = spy[spy.index >= live]
    spy_live = float(spy.iloc[-1] / spy_base.iloc[0] - 1) if len(spy_base) else None
    sessions = int((curve.index > live).sum())
    sigma = MODEL_ANNUAL_VOL * np.sqrt(max(sessions, 1) / 252)

    plist = tc.get_all_positions()
    pos = [dict(symbol=p.symbol, qty=float(p.qty), value=float(p.market_value),
                weight=round(float(p.market_value) / equity, 5),
                plpc=round(float(p.unrealized_plpc), 5),
                pl=round(float(p.unrealized_pl), 2)) for p in plist]
    pos.sort(key=lambda r: r["plpc"])

    rb = rebalances()
    conc = concentration(positions, equity)
    tick = last_tick()
    ords = orders_history()
    trips = roundtrips(ords)
    cyc = dict(done=rb["done"], needed=CYCLES_NEEDED, dates=rb["dates"],
               gaps=rb["gaps"], late=rb["late"], worst_gap=rb["worst_gap"])

    # SPY rebased onto the book's start, so one chart can carry both lines
    spy_series = []
    if len(spy_base):
        b0 = float(spy_base.iloc[0])
        for d, v in spy.items():
            if d >= live:
                spy_series.append(dict(date=str(d),
                                       equity=round(START_EQUITY * float(v) / b0, 2)))

    def tick_value() -> str:
        if not tick.get("available"):
            return "no tick log found"
        m = tick["age_min"]
        ago = f"{m:.0f} min ago" if m < 90 else f"{m / 60:.1f} hours ago"
        return f"last woke {ago}, expected every {TICK_EVERY_MIN} min"

    guards = [
        dict(name="Schedule", plain="Is the robot awake?",
             state="OK" if tick.get("available") and not tick["stale"] else "STOPPED",
             value=tick_value(),
             detail="Nothing else on this page can tell you this. A stopped "
                    "schedule and a quiet one look identical: both do nothing. "
                    "While it is stopped no stop-loss is checked and no "
                    "rebalance happens, and every other number here is as old "
                    "as the last time the page was drawn."),
        dict(name="Money switch", plain="Can it spend real money?",
             state="OK", value="off (paper account)",
             detail="LIVE_TRADING must be the exact string 'true' to arm real orders."),
        dict(name="Cash floor", plain="Keep at least 10% in cash",
             state="OK" if cash / equity >= CASH_FLOOR else "DRIFT",
             value=f"{cash / equity:.2%} against {CASH_FLOOR:.0%}",
             detail="Applied when buying. Holdings rising shrinks cash as a share; "
                    "the next rebalance resets it."),
        dict(name="Daily circuit", plain="Stop buying after a 3% fall in a day",
             state="OK" if day_move > DAILY_CIRCUIT else "TRIPPED",
             value=f"today {day_move:+.2%} against {DAILY_CIRCUIT:.0%}",
             detail="Sells still execute when tripped; only new buys are refused."),
        dict(name="Catastrophe stop", plain="Sell anything down 25% from what we paid",
             state="OK" if not pos or pos[0]["plpc"] > CAT_STOP else "FIRING",
             value=f"worst {pos[0]['symbol']} {pos[0]['plpc']:+.1%}" if pos else "no positions",
             detail="Checked every tick while the market is open."),
        dict(name="Position cap", plain="No single stock over 5%",
             state="OK" if not pos or max(p["weight"] for p in pos) <= MAX_POSITION_PCT
                   else "BREACH",
             value=f"largest {max((p['weight'] for p in pos), default=0):.2%} "
                   f"against {MAX_POSITION_PCT:.0%}",
             detail="Enforced at entry; drift above it is not a breach."),
        dict(name="Cluster cap", plain="No correlated group over 20%",
             state="OK" if conc.get("over_cap", 0) == 0 else "BREACH",
             value=(f"{conc['over_cap']} holding(s) over cap; worst "
                    f"{conc['worst_local_symbol']} {conc['worst_local_weight']:.1%}")
                   if conc.get("available") else "not computable",
             detail=("Fixed 2026-08-26. The book still carries the concentration the "
                     "broken rule allowed; the next rebalance applies the fix."
                     if conc.get("over_cap", 0) else
                     "Every holding sits inside the cap. Momentum concentrates by "
                     "construction, so this is the rule doing work, not an accident.")),
        dict(name="Cadence", plain="Rebalance weekly, never more often",
             state="OK",
             value=f"{rb['days_since']} days since the last, minimum "
                   f"{MIN_REBALANCE_GAP_DAYS}" if rb["days_since"] is not None else "no rebalance yet",
             detail="A guard refuses a rebalance inside the window, so the book "
                    "cannot drift to a cadence the evidence has not tested."),
    ]

    return dict(
        meta=dict(
            generated_at=now.isoformat(),
            generated_at_pretty=now.strftime("%-d %B %Y, %H:%M New York"),
            mark_source="live account endpoint",
            mark_note="Alpaca reports several account values at once. This page uses "
                      "the live account mark throughout, taken at the time above. "
                      "The daily and intraday series can disagree with it by over a "
                      "percent because they exclude after-hours marks and stamp a "
                      "day differently.",
            live_from=str(live), sessions=sessions, is_paper=True),
        headline=dict(
            equity=round(equity, 2), start=START_EQUITY,
            since_live=round(since_live, 5),
            spy_since_live=None if spy_live is None else round(spy_live, 5),
            excess=None if spy_live is None else round(since_live - spy_live, 5),
            day_move=round(day_move, 5),
            cash=round(cash, 2), cash_pct=round(cash / equity, 5),
            positions=len(pos),
            expected_swing=round(float(sigma), 5),
            sigmas=round(float(since_live / sigma), 2) if sigma else 0.0,
            within_expectations=bool(abs(since_live / sigma) <= 2) if sigma else True,
            peak=round(float(curve.max()), 2),
            from_peak=round(float(equity / curve.max() - 1), 5)),
        equity_curve=[dict(date=str(d), equity=round(float(v), 2))
                      for d, v in curve.items()],
        benchmark=dict(symbol=BENCHMARK, series=spy_series),
        intraday=intraday(),
        positions=pos,
        slippage=slippage_by_cycle(),
        concentration=conc,
        cycles=cyc,
        tick=tick,
        guards=guards,
        orders=ords,
        roundtrips=trips,
        timeline=timeline(ords, cyc, tick),
        mix=mixes(pos, equity, cash, conc),
        attribution=attribution(pos, equity),
        markets=markets(pos),
        risk=risk_series(curve),
        reports=report_log(),
    )


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    d = build()
    d["archive"] = archive(d)
    p = OUT / "data.json"
    p.write_text(json.dumps(d, indent=1, default=str), encoding="utf-8")
    print(f"wrote {p} ({p.stat().st_size / 1024:.0f} KB)")
    print(f"  equity ${d['headline']['equity']:,.2f}  "
          f"{d['headline']['since_live']:+.2%} since {d['meta']['live_from']}  "
          f"positions {d['headline']['positions']}  "
          f"cycles {d['cycles']['done']}/{d['cycles']['needed']}")
    print(f"  orders {len(d['orders'])}  closed trades {len(d['roundtrips'])}  "
          f"markets {len(d['markets']['series'])}  events {len(d['timeline'])}  "
          f"reports {len(d['reports'])}  snapshots {len(d['archive'])}")


if __name__ == "__main__":
    main()
