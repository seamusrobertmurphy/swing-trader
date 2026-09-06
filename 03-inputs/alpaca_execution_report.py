"""Track A execution report: measured slippage on the paper book's real fills.

The paper trial's one job is proving that real execution matches the modeled
costs (5-10bp round trip). This measures it per fill: each filled order's
average price is compared against the minute bar containing the fill
(VWAP), so overnight gaps and intraday drift are excluded and only the true
cost of crossing the spread remains. Buys pay positive slippage when filling
above VWAP; sells when filling below.

Run after any rebalance; append-only record per run.

TIMING. This cannot be run immediately after a rebalance. The paper
subscription refuses minute bars newer than about 15 minutes ("subscription
does not permit querying recent SIP data"), so the reference VWAP for a fill
does not exist yet and every fill is skipped. Found 2026-08-27, when the tick
ran it 21 seconds after the fills and it crashed. The tick now defers it to a
later wake-up; run it by hand at least SIP_DELAY_MIN minutes after the fills.

    .venv/bin/python inputs/alpaca_execution_report.py [--days 1]
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone

import pandas as pd
from zoneinfo import ZoneInfo

import config
from alpaca_trade import clients

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "04-outputs", "AA-evals")

# How long the data plan withholds a minute bar. The refusal is decided by the
# END of the requested window, not by the fill: measured 2026-08-27, a window
# ending 14:06 was refused at 14:20 while the same window ending 14:05 was
# served. So the window must end at the fill minute and nothing later, and the
# wait is the plan's 15 minutes plus a margin for a slow clock.
SIP_DELAY_MIN = 17


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=1)
    a = ap.parse_args()

    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    tc = clients()
    key = (os.environ.get("ALPACA_API_KEY") or config.ALPACA_API_KEY).strip()
    secret = (os.environ.get("ALPACA_API_SECRET") or config.ALPACA_API_SECRET).strip()
    dc = StockHistoricalDataClient(key, secret)

    since = datetime.now(timezone.utc) - timedelta(days=a.days)
    orders = tc.get_orders(GetOrdersRequest(status=QueryOrderStatus.CLOSED,
                                            after=since, limit=500))
    filled = [o for o in orders if o.filled_at is not None and o.filled_avg_price]
    if not filled:
        print("no filled orders in the window")
        return

    rows, skipped = [], []
    for o in filled:
        t = o.filled_at.replace(second=0, microsecond=0)
        try:
            bars = dc.get_stock_bars(StockBarsRequest(
                symbol_or_symbols=o.symbol, timeframe=TimeFrame.Minute,
                start=t - timedelta(minutes=1), end=t)).data[o.symbol]
            # The reference must be the bar CONTAINING the fill. Taking bars[0]
            # off a start of t-1min took the PRECEDING minute instead, so on a
            # fast tape the report charged one minute of drift as spread cost.
            # Found 2026-08-26: it moved that run's median from +12.5bp to
            # +29.9bp. Alpaca stamps a minute bar with the minute it opens.
            by_min = {b.timestamp.astimezone(timezone.utc).replace(
                second=0, microsecond=0): b for b in bars}
            bar = by_min.get(t)
            if bar is None:
                skipped.append("no bar stamped for the fill minute")
                continue
            ref = float(bar.vwap)
        except Exception as e:  # noqa: BLE001
            skipped.append(str(e))
            continue
        fill = float(o.filled_avg_price)
        side = str(o.side).rsplit(".", 1)[-1].lower()
        slip_bp = ((fill - ref) / ref if side == "buy" else (ref - fill) / ref) * 1e4
        notional = fill * float(o.filled_qty)
        et = o.filled_at.astimezone(ZoneInfo("America/New_York"))
        mins = (et.hour - 9) * 60 + (et.minute - 30) if et.hour >= 9 else None
        rows.append(dict(symbol=o.symbol, side=side, fill=fill, ref_vwap=round(ref, 4),
                         slip_bp=round(slip_bp, 1), notional=round(notional, 2),
                         fill_et=et.strftime("%H:%M"), minutes_from_open=mins))

    t = pd.DataFrame(rows)
    if t.empty:
        # Previously this fell through and died with KeyError: 'slip_bp' on an
        # empty frame, which named the symptom and hid the cause.
        newest = max(o.filled_at for o in filled)
        age = (datetime.now(timezone.utc) - newest).total_seconds() / 60
        why = skipped[0] if skipped else "no reason recorded"
        print(f"{len(filled)} fills found, none measurable: {why}")
        if "recent SIP" in why or age < SIP_DELAY_MIN:
            print(f"The newest fill is {age:.0f} minutes old and the data plan "
                  f"withholds bars for about {SIP_DELAY_MIN}. Re-run in "
                  f"{max(0, SIP_DELAY_MIN - age):.0f} minutes.")
        return

    pd.set_option("display.width", 160)
    # Exchange time, not UTC: after 20:00 New York a UTC stamp files the
    # evening's report under tomorrow's date.
    stamp = datetime.now(ZoneInfo("America/New_York"))
    dollar_cost = float((t["slip_bp"] / 1e4 * t["notional"]).sum())
    summary = (f"fills={len(t)}  mean slippage={t['slip_bp'].mean():+.1f}bp  "
               f"median={t['slip_bp'].median():+.1f}bp  worst={t['slip_bp'].max():+.1f}bp  "
               f"notional=${t['notional'].sum():,.0f}  cost=${dollar_cost:+,.2f}")
    # Fills in the opening minutes are the expensive ones: widest spreads and
    # fastest tape of the day. Measured 2026-08-26 (all 31 fills inside the
    # first six minutes) at +42.5bp mean against +7.3bp for the 2026-08-18
    # mid-session batch. Submitting a rebalance while the market is shut queues
    # DAY orders into the opening auction, so the runbook must be run intraday.
    open_et = [r for r in rows if r["minutes_from_open"] is not None
               and r["minutes_from_open"] < 15]
    timing = ""
    if open_et:
        share = len(open_et) / len(rows)
        mean_open = sum(r["slip_bp"] for r in open_et) / len(open_et)
        timing = (f"\nWARNING: {len(open_et)} of {len(rows)} fills ({share:.0%}) landed in the "
                  f"first 15 minutes of the session, at {mean_open:+.1f}bp mean. The opening "
                  f"auction is the widest spread of the day; run the rebalance intraday.")
    print(summary)
    if timing:
        print(timing)
    print(t.sort_values("slip_bp", ascending=False).head(10).to_string(index=False))

    day_dir = os.path.join(OUT_DIR, f"{stamp:%Y-%m-%d}")
    os.makedirs(day_dir, exist_ok=True)
    path = os.path.join(day_dir, f"execution-report-{stamp:%Y%m%d-%H%M}.md")
    with open(path, "w") as f:
        f.write(f"# Execution report {stamp:%Y-%m-%d %H:%M} New York\n\n"
                f"Per-fill slippage vs the fill-minute VWAP (spread cost only; gaps and "
                f"drift excluded). Modeled round trip: 5-10bp.\n\n{summary}\n{timing}\n\n"
                + t.sort_values("slip_bp", ascending=False).to_string(index=False) + "\n")
    print(f"\nrecord: {path}")


if __name__ == "__main__":
    main()
