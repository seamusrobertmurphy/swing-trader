"""Track A execution report: measured slippage on the paper book's real fills.

The paper trial's one job is proving that real execution matches the modeled
costs (5-10bp round trip). This measures it per fill: each filled order's
average price is compared against the minute bar covering the fill moment
(VWAP), so overnight gaps and intraday drift are excluded and only the true
cost of crossing the spread remains. Buys pay positive slippage when filling
above VWAP; sells when filling below.

Run after any rebalance; append-only record per run.

    .venv/bin/python inputs/alpaca_execution_report.py [--days 1]
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone

import pandas as pd

import config
from alpaca_trade import clients

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "AA-evals")


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

    rows = []
    for o in filled:
        t = o.filled_at.replace(second=0, microsecond=0)
        try:
            bars = dc.get_stock_bars(StockBarsRequest(
                symbol_or_symbols=o.symbol, timeframe=TimeFrame.Minute,
                start=t - timedelta(minutes=1), end=t + timedelta(minutes=2))).data[o.symbol]
            ref = float(bars[0].vwap)
        except Exception:  # noqa: BLE001
            continue
        fill = float(o.filled_avg_price)
        side = str(o.side).rsplit(".", 1)[-1].lower()
        slip_bp = ((fill - ref) / ref if side == "buy" else (ref - fill) / ref) * 1e4
        notional = fill * float(o.filled_qty)
        rows.append(dict(symbol=o.symbol, side=side, fill=fill, ref_vwap=round(ref, 4),
                         slip_bp=round(slip_bp, 1), notional=round(notional, 2)))

    t = pd.DataFrame(rows)
    pd.set_option("display.width", 160)
    stamp = datetime.now(timezone.utc)
    dollar_cost = float((t["slip_bp"] / 1e4 * t["notional"]).sum())
    summary = (f"fills={len(t)}  mean slippage={t['slip_bp'].mean():+.1f}bp  "
               f"median={t['slip_bp'].median():+.1f}bp  worst={t['slip_bp'].max():+.1f}bp  "
               f"notional=${t['notional'].sum():,.0f}  cost=${dollar_cost:+,.2f}")
    print(summary)
    print(t.sort_values("slip_bp", ascending=False).head(10).to_string(index=False))

    day_dir = os.path.join(OUT_DIR, f"{stamp:%Y-%m-%d}")
    os.makedirs(day_dir, exist_ok=True)
    path = os.path.join(day_dir, f"execution-report-{stamp:%Y%m%d-%H%M}.md")
    with open(path, "w") as f:
        f.write(f"# Execution report {stamp:%Y-%m-%d %H:%M} UTC\n\n"
                f"Per-fill slippage vs the fill-minute VWAP (spread cost only; gaps and "
                f"drift excluded). Modeled round trip: 5-10bp.\n\n{summary}\n\n"
                + t.sort_values("slip_bp", ascending=False).to_string(index=False) + "\n")
    print(f"\nrecord: {path}")


if __name__ == "__main__":
    main()
