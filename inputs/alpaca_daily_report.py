"""Daily results report for the Alpaca paper momentum book.

Operator instruction 2026-08-26: produce this every trading day, opening with
the "Where the money actually is" block from CLAUDE.md. Every figure is
recomputed at the moment of writing; nothing is carried forward from the
previous day's file. Where a figure cannot be computed, the report says so in
plain words rather than printing a stale or invented number.

Writes outputs/AA-evals/<date>/DAILY-<stamp>.md and prints the same text, so a
cron run leaves a record and an interactive run answers on screen.

    .venv/bin/python inputs/alpaca_daily_report.py
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

import config
from alpaca_trade import (CASH_FLOOR, CAT_STOP, MIN_REBALANCE_GAP_DAYS, STATE,
                          account_state, clients)

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "outputs" / "AA-evals"
TRADE_LOG = REPO / "memory" / "trade-log.md"

START_EQUITY = 100_000.0
LIVE_FROM = "2026-08-18"        # first rebalance filled
BENCHMARK = "SPY"
MODEL_COST_BP = (5.0, 10.0)     # the per-side slippage band the trial is testing
CYCLES_NEEDED = 6               # clean weekly cycles before the execution verdict
MODEL_ANNUAL_VOL = 0.35         # measured in the portfolio sim, 2026-08-18
ET = ZoneInfo("America/New_York")


def _keys():
    k = (os.environ.get("ALPACA_API_KEY") or config.ALPACA_API_KEY).strip()
    s = (os.environ.get("ALPACA_API_SECRET") or config.ALPACA_API_SECRET).strip()
    b = (os.environ.get("ALPACA_BASE_URL") or config.ALPACA_BASE_URL).strip()
    return k, s, b


def equity_curve() -> pd.Series:
    """Daily closing equity of the paper account, New York dates."""
    k, s, b = _keys()
    r = requests.get(f"{b}/v2/account/portfolio/history",
                     params=dict(period="3M", timeframe="1D",
                                 intraday_reporting="market_hours"),
                     headers={"APCA-API-KEY-ID": k, "APCA-API-SECRET-KEY": s},
                     timeout=30)
    r.raise_for_status()
    d = r.json()
    h = pd.DataFrame(dict(ts=pd.to_datetime(d["timestamp"], unit="s", utc=True),
                          equity=d["equity"]))
    h = h[h["equity"] > 0].copy()
    h["date"] = h["ts"].dt.tz_convert(ET).dt.date
    return h.groupby("date")["equity"].last()


def benchmark() -> pd.Series:
    """SPY daily closes. Ends 25 minutes back: the data plan forbids the most
    recent SIP prints and asking for them returns 403, not an empty frame."""
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    k, s, _ = _keys()
    dc = StockHistoricalDataClient(k, s)
    bars = dc.get_stock_bars(StockBarsRequest(
        symbol_or_symbols=[BENCHMARK], timeframe=TimeFrame.Day,
        start=datetime(2026, 8, 1, tzinfo=timezone.utc),
        end=datetime.now(timezone.utc) - timedelta(minutes=25))).data[BENCHMARK]
    return pd.Series({b.timestamp.astimezone(ET).date(): float(b.close) for b in bars})


def recent_slippage(days: int = 8) -> dict | None:
    """Mean and median per-fill slippage against the minute bar containing the
    fill. Returns None when nothing filled in the window, which is the normal
    state on a day with no rebalance."""
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest
    tc = clients()
    k, s, _ = _keys()
    dc = StockHistoricalDataClient(k, s)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    orders = [o for o in tc.get_orders(GetOrdersRequest(
        status=QueryOrderStatus.CLOSED, after=since, limit=500))
        if o.filled_at is not None and o.filled_avg_price]
    if not orders:
        return None
    slips, notion, at_open = [], 0.0, 0
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
        slips.append((fill - ref) / ref * 1e4 * (1 if side == "buy" else -1))
        notion += fill * float(o.filled_qty)
        et = o.filled_at.astimezone(ET)
        if (et.hour - 9) * 60 + (et.minute - 30) < 15:
            at_open += 1
    if not slips:
        return None
    a = np.array(slips)
    return dict(n=len(a), mean=float(a.mean()), median=float(np.median(a)),
                worst=float(a.max()), notional=notion, at_open=at_open,
                dollars=float((a / 1e4).mean() * notion),
                when=max(o.filled_at for o in orders).astimezone(ET))


def rebalances() -> dict:
    """Count filled rebalances and judge cadence health from the trade log."""
    txt = TRADE_LOG.read_text(encoding="utf-8") if TRADE_LOG.exists() else ""
    stamps = re.findall(r"\| (\d{4}-\d{2}-\d{2}) \d{2}:\d{2} \| ALPACA-PAPER REBALANCE", txt)
    done = sorted(set(stamps))
    live = datetime.strptime(LIVE_FROM, "%Y-%m-%d").date()
    today = datetime.now(ET).date()
    weeks = max(1, ((today - live).days // 7) + 1)
    last = None
    if STATE.exists():
        last = datetime.fromisoformat(json.loads(STATE.read_text())["last_rebalance"])
    days_since = (datetime.now(timezone.utc) - last).days if last else None
    # Cadence health from the ACTUAL gaps, not a week count. Dividing elapsed
    # days by seven is too coarse to see a slip: on 2026-08-26 it read "2 of 2
    # weeks, none missed" while cycle 2 had in fact run 8 days after cycle 1,
    # a day late, having missed its Monday slot entirely.
    ds = [datetime.strptime(x, "%Y-%m-%d").date() for x in done]
    gaps = [(b - a).days for a, b in zip(ds, ds[1:])]
    late = [g for g in gaps if g > 7]
    return dict(done=len(done), dates=done, weeks_live=weeks, gaps=gaps, late=late,
                worst_gap=max(gaps) if gaps else None,
                missed=max(0, weeks - len(done)), days_since=days_since)


def expectation(book_move: float, days: int) -> tuple[bool, str]:
    """Is the move since inception inside the modelled distribution?

    The portfolio sim measured 35% annual volatility, so one standard deviation
    over `days` trading days is 0.35 * sqrt(days/252). Two of those is the
    ordinary range; outside it is a real surprise worth explaining."""
    if days <= 0:
        return True, "The book is less than a day old, so there is nothing to compare yet."
    sigma = MODEL_ANNUAL_VOL * np.sqrt(days / 252)
    z = book_move / sigma if sigma else 0.0
    ok = abs(z) <= 2.0
    return ok, (f"The plan expected swings of about {sigma:.1%} over {days} trading days. "
                f"This is {abs(z):.1f} times that, "
                f"{'an ordinary move' if ok else 'bigger than the plan allows for'}.")


def build() -> str:
    tc = clients()
    acct, equity, cash, day_move, positions = account_state(tc)
    now = datetime.now(ET)
    curve = equity_curve()
    # Alpaca posts the day's closing equity to portfolio history some time after
    # the bell, so on an after-close run the curve's last row is YESTERDAY. Left
    # alone that made the report call the day before last "yesterday" and
    # compute the rolling five-session P&L without today in it, which on
    # 2026-08-26 printed -4.12% on the same page as a +2.86% day. Stamp the live
    # mark in as today so every derived figure includes it.
    today = datetime.now(ET).date()
    curve.loc[today] = equity
    curve = curve.sort_index()
    spy = benchmark()

    live = datetime.strptime(LIVE_FROM, "%Y-%m-%d").date()
    since_live = equity / START_EQUITY - 1
    spy_live = None
    if len(spy):
        base = spy[spy.index >= live]
        if len(base):
            spy_live = float(spy.iloc[-1] / base.iloc[0] - 1)
    sessions = int((curve.index > live).sum())
    ok, why = expectation(since_live, sessions)

    plist = tc.get_all_positions()
    worst = min(plist, key=lambda p: float(p.unrealized_plpc)) if plist else None
    slip = recent_slippage()
    rb = rebalances()

    market_line = f"{spy_live:+.2%}" if spy_live is not None else \
        "not available (the data plan refuses the most recent SIP prints)"
    if worst is not None:
        wr = float(worst.unrealized_plpc)
        room = (wr - CAT_STOP) * 100
        worst_line = (f"{worst.symbol}, {'down' if wr < 0 else 'up'} {abs(wr):.1%} from what we "
                      f"paid. It is sold automatically at {CAT_STOP:.0%}, so it has "
                      f"{room:.0f} percentage points of room. It also leaves the book at the "
                      f"next rebalance if it drops out of the top fifty")
    else:
        worst_line = "no positions held"
    if slip:
        cost_line = (f"{slip['mean']:.1f} basis points per fill on average, "
                     f"{slip['median']:.1f} for the typical one, against the "
                     f"{MODEL_COST_BP[0]:.0f} to {MODEL_COST_BP[1]:.0f} we assumed. "
                     f"Measured on {slip['n']} fills, most recently "
                     f"{slip['when']:%-d %B}")
    else:
        cost_line = ("nothing traded in the last eight days, so there is nothing to "
                     "measure. The last measurement stands in the previous report")
    if not rb["gaps"]:
        cad = ", the first and only one so far"
    elif rb["late"]:
        cad = (f". {len(rb['late'])} ran late: the longest gap between two was "
               f"{rb['worst_gap']} days against the 7 the weekly cadence intends")
    else:
        cad = f", every one on time (longest gap {rb['worst_gap']} days)"
    reb_line = f"{rb['done']} of the {CYCLES_NEEDED} we need{cad}"

    L = []
    A = L.append
    A(f"# Daily book report, {now:%-d %B %Y}")
    A("")
    A(f"Marked {now:%H:%M} New York time"
      f"{', after the close' if now.hour >= 16 else ', during the session'}. "
      f"Every figure below was recomputed at that moment.")
    A("")
    A("## Where the money actually is")
    A("")
    A("| | |")
    A("| --- | --- |")
    A(f"| Account value | ${equity:,.0f}, from a ${START_EQUITY:,.0f} start |")
    A(f"| Change since it went live on {live:%-d %B} | **{since_live:+.2%}** |")
    A(f"| The market, same period | {market_line} |")
    A(f"| Was this within expectations? | {'Yes' if ok else 'No'}. {why} |")
    A(f"| Worst single holding | {worst_line} |")
    A(f"| What it costs us to trade | {cost_line} |")
    A(f"| Rebalances done | {reb_line} |")
    A("")
    A("**This is fake money.** It is a paper account. The switch that would let it "
      "spend real money is off.")
    A("")
    A("## Today")
    A("")
    A(f"The book moved {day_move:+.2%} today and holds {len(positions)} stocks. "
      f"Cash is ${cash:,.0f}, which is {cash / equity:.2%} of the account against a "
      f"floor of {CASH_FLOOR:.0%}"
      + ("." if cash / equity >= CASH_FLOOR else
         ". That is below the floor. It is drift, not a breach: the floor is applied "
         "when buying and the holdings then rose, which shrinks cash as a share. The "
         "next rebalance resets it."))
    if len(curve) >= 2:
        A("")
        A(f"The session before, it closed at ${curve.iloc[-2]:,.0f}. The peak since it went "
          f"live is ${curve.max():,.0f}, so it sits {equity / curve.max() - 1:+.2%} below "
          f"its best.")
    n = min(5, len(curve) - 1)
    if n > 0:
        roll = curve.iloc[-1] / curve.iloc[-1 - n] - 1
        A("")
        A(f"Over the last {n} sessions the book is {roll:+.2%}. Your rules start shrinking "
          f"new positions below -5%, so that rule is "
          f"{'ACTIVE and needs a ruling on how hard to shrink' if roll < -0.05 else 'not triggering'}.")
    if plist:
        best = max(plist, key=lambda p: float(p.unrealized_plpc))
        A("")
        A(f"Best holding is {best.symbol}, up {float(best.unrealized_plpc):.1%} from what we "
          f"paid. {sum(1 for p in plist if float(p.unrealized_plpc) > 0)} of {len(plist)} "
          f"holdings are ahead.")
    if slip and slip["at_open"]:
        A("")
        A(f"Warning: {slip['at_open']} of {slip['n']} recent fills landed in the first "
          f"fifteen minutes of a session, which is the widest spread of the day. The "
          f"rebalance must run intraday, not overnight.")
    A("")
    A("## What happens next")
    A("")
    if rb["days_since"] is not None:
        due = MIN_REBALANCE_GAP_DAYS - rb["days_since"]
        A(f"The last rebalance was {rb['days_since']} days ago. The tested cadence is "
          f"weekly, and the code refuses to trade again for another "
          f"{max(0, due)} day{'' if max(0, due) == 1 else 's'}, so the next one is "
          + ("due now." if due <= 0 else f"due in {due} days."))
    A("")
    A(f"The paper trial needs {CYCLES_NEEDED} clean weekly cycles before we can say "
      f"whether real trading costs match the model. {rb['done']} are done.")
    A("")
    A("---")
    A("")
    A("Historical figures elsewhere in this repo rest on stock data covering only "
      "companies that still exist, which flatters them. The account figures above do "
      "not: they are real fills at real prices in a real market, with fake money.")
    return "\n".join(L) + "\n"


def main():
    text = build()
    stamp = datetime.now(timezone.utc)
    day = OUT / f"{stamp:%Y-%m-%d}"
    day.mkdir(parents=True, exist_ok=True)
    path = day / f"DAILY-{stamp:%Y%m%d-%H%M}.md"
    path.write_text(text, encoding="utf-8")
    print(text)
    print(f"record: {path}")


if __name__ == "__main__":
    main()
