"""Track A preflight: prove the Alpaca paper plumbing end to end, loudly.

Checks, in order: keys present (Keychain via config, env override), the paper
trading account answers and is active, the market clock answers, and the data
API returns real SPY daily bars. Any failure exits 1 with the reason, per the
environment rule: a missing credential aborts before anything else runs.
Read-only throughout; no orders. Exit 0 means Phase A1 plumbing is proven.

    .venv/bin/python inputs/alpaca_check.py
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

import config


def main() -> int:
    key, secret = config.alpaca_keys()
    base = (os.environ.get("ALPACA_BASE_URL") or config.ALPACA_BASE_URL).strip()
    if not key or not secret:
        # config.require prints where it looked and what is missing, and its
        # message is platform-correct: the Keychain hint is macOS-only and
        # would be useless on the Linux box this repo now has to run on.
        config.require(*(("ALPACA_API_KEY", "ALPACA_API_SECRET") if config.alpaca_is_paper()
                         else ("ALPACA_LIVE_API_KEY", "ALPACA_LIVE_API_SECRET")))
        return 1
    # Read only, so it checks a live account as readily as the paper one
    # (changed 2026-10-14); only alpaca_trade.py can place an order.
    paper = config.alpaca_is_paper()
    print(f"[address] {base} ({'paper' if paper else 'LIVE, read only here'})")

    from alpaca.trading.client import TradingClient
    tc = TradingClient(key, secret, paper=paper)
    acct = tc.get_account()
    print(f"[account] status={acct.status}  equity=${float(acct.equity):,.2f}  "
          f"cash=${float(acct.cash):,.2f}  PDT-flagged={acct.pattern_day_trader}  "
          f"shorting_enabled={acct.shorting_enabled}")
    # The broker-side guards the live audit asks the holder to set (decision
    # 2). Read raw, because alpaca-py 0.43.4 crashes parsing this endpoint.
    cfg = tc.get("/account/configurations")
    mult, noshort = str(cfg.get("max_margin_multiplier")), cfg.get("no_shorting")
    print(f"[settings] max_margin_multiplier={mult}  no_shorting={noshort}"
          + ("" if (mult == "1" and noshort) or paper else
             "   <- set to 1 and true in the Alpaca dashboard before trading"))
    if str(acct.status) != "AccountStatus.ACTIVE":
        print(f"ABORT: account status {acct.status} is not ACTIVE.")
        return 1

    clock = tc.get_clock()
    print(f"[clock]   market_open={clock.is_open}  next_open={clock.next_open}  "
          f"next_close={clock.next_close}")

    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    dc = StockHistoricalDataClient(key, secret)
    req = StockBarsRequest(symbol_or_symbols="SPY", timeframe=TimeFrame.Day,
                           start=datetime.now(timezone.utc) - timedelta(days=30))
    bars = dc.get_stock_bars(req).df
    if bars.empty:
        print("ABORT: data API returned no SPY bars.")
        return 1
    last = bars.iloc[-1]
    last_ts = bars.index[-1][1] if isinstance(bars.index[0], tuple) else bars.index[-1]
    print(f"[data]    SPY daily bars: {len(bars)} rows, latest {last_ts:%Y-%m-%d} "
          f"close={float(last['close']):.2f} volume={int(last['volume']):,}")

    print("\nPhase A1 plumbing PROVEN: account, clock, and data all answer on the paper stack.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
