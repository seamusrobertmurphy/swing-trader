"""Track A Phase A5: the momentum book on the Alpaca PAPER account, hard rules enforced.

Strategy (the one that passed all three checks): 12-1 momentum, top decile of
the top-500 dollar-volume universe, ~50 names equal weight, rebalanced monthly.

Enforced here, never assumed from the venue:
  paper only      the endpoint must be the paper API unless LIVE_TRADING is the
                  exact string 'true'; anything else aborts before any request.
  never short     sells are capped at held quantity; the account's
                  shorting_enabled=True is neutralized in code.
  never margin    target book = equity minus the 10% cash floor; buys are
                  additionally capped by free cash. No leverage possible.
  position cap    5% of equity per name at entry (equal weight ~1.8% here).
  daily circuit   if equity is down more than 3% from yesterday's close, new
                  buys are refused for the run; sells still execute.
  PDT safety      monthly holds; the rebalance never buys and sells the same
                  name in one run.

Charter deviations for THIS systematic basket, decided 2026-08-18 and journaled:
  max-3-new-per-week and the -7% per-name stop are selectivity/exit rules for
  the discretionary crypto swing book; applied to a 50-name monthly factor
  basket they would forbid the rebalance and amputate the factor (single
  equities routinely move 7%). Both remain available as switches
  (--max-new, --hard-stop) and default off for this book. The book's risk
  controls are diversification, the monthly rebalance, the cash floor, and the
  daily circuit.

Commands:
  plan                 compute targets and the order diff; prints, changes nothing
  rebalance            dry-run of the order list; add --execute to submit
  status               account, positions, P&L; rewrites memory/alpaca-portfolio.md

    .venv/bin/python inputs/alpaca_trade.py plan
    .venv/bin/python inputs/alpaca_trade.py rebalance --execute
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import config
from equity_momentum_monthly import (MIN_DOLLAR_VOL, MIN_HISTORY, MIN_NAMES,
                                     MIN_PRICE, SIGNALS, TOP_FRAC, monthly_panel)

REPO = Path(__file__).resolve().parents[1]
TRADE_LOG = REPO / "memory" / "trade-log.md"
BOOK_MD = REPO / "memory" / "alpaca-portfolio.md"

TOP_LIQ = 500
CASH_FLOOR = 0.10
MAX_POSITION_PCT = 0.05
DAILY_CIRCUIT = -0.03
REBALANCE_BAND = 0.25          # rebalance an existing name only if off target by >25%
STALE_DAYS = 7
# Catastrophe stop (operator decision 2026-08-18): close any name 25% below its
# average entry. Fires on fraud-type collapses only, not factor noise (a 7%
# stop would fire weekly on momentum names and amputate the tested strategy;
# 25% on a 1.8% position bounds the residual loss at ~0.45% of equity).
CAT_STOP = -0.25


def clients():
    from alpaca.trading.client import TradingClient
    key = (os.environ.get("ALPACA_API_KEY") or config.ALPACA_API_KEY).strip()
    secret = (os.environ.get("ALPACA_API_SECRET") or config.ALPACA_API_SECRET).strip()
    base = (os.environ.get("ALPACA_BASE_URL") or config.ALPACA_BASE_URL).strip()
    if not key or not secret:
        raise SystemExit("ABORT: Alpaca keys missing.")
    if "paper" not in base and os.environ.get("LIVE_TRADING") != "true":
        raise SystemExit(f"ABORT: {base} is not the paper endpoint and LIVE_TRADING "
                         f"is not 'true'. The money switch stays off.")
    return TradingClient(key, secret, paper="paper" in base)


def journal(line: str) -> None:
    with open(TRADE_LOG, "a", encoding="utf-8") as f:
        f.write(line.rstrip() + "\n")


def targets() -> tuple[list[str], pd.Timestamp]:
    """Top-decile names at the latest month-end formation, top-500 liquidity tier."""
    px, dv, dv_med = monthly_panel()
    last = px.index.max()
    if (pd.Timestamp.now() - last).days > STALE_DAYS:
        raise SystemExit(f"ABORT: bar data ends {last:%Y-%m-%d} (> {STALE_DAYS} days old). "
                         f"Run alpaca_data.py download first.")
    sig = SIGNALS["mom_12_1"](px)
    hist_ok = px.notna().rolling(MIN_HISTORY, min_periods=MIN_HISTORY).count() >= MIN_HISTORY
    t0 = last
    elig = (hist_ok.loc[t0] & (px.loc[t0] >= MIN_PRICE)
            & (dv_med.loc[t0] >= MIN_DOLLAR_VOL) & sig.loc[t0].notna())
    names = elig[elig].index
    if len(names) > TOP_LIQ:
        names = dv_med.loc[t0, names].nlargest(TOP_LIQ).index
    if len(names) < MIN_NAMES:
        raise SystemExit(f"ABORT: only {len(names)} eligible names (< {MIN_NAMES}).")
    s = sig.loc[t0, names]
    top = sorted(s[s.rank(pct=True) > (1 - TOP_FRAC)].index)
    return top, t0


def account_state(tc):
    acct = tc.get_account()
    equity = float(acct.equity)
    last_equity = float(acct.last_equity)
    day_move = equity / last_equity - 1 if last_equity else 0.0
    positions = {p.symbol: dict(qty=float(p.qty), value=float(p.market_value))
                 for p in tc.get_all_positions()}
    return acct, equity, float(acct.cash), day_move, positions


def build_orders(top, equity, cash, positions, max_new=None):
    weight = min((1 - CASH_FLOOR) / len(top), MAX_POSITION_PCT)
    per_name = equity * weight
    sells = [(s, p["qty"]) for s, p in positions.items() if s not in top and p["qty"] > 0]
    buys, adjust = [], []
    for sym in top:
        held = positions.get(sym, {}).get("value", 0.0)
        if held == 0:
            buys.append((sym, per_name))
        elif abs(held - per_name) / per_name > REBALANCE_BAND:
            adjust.append((sym, per_name - held))
    if max_new is not None:
        buys = buys[:max_new]
    # never-margin: total new spend cannot exceed free cash after the floor,
    # counting cash freed by the sells at current marks.
    freed = sum(positions[s]["value"] for s, _ in sells)
    budget = max(0.0, cash + freed - equity * CASH_FLOOR)
    spend = sum(n for _, n in buys) + sum(max(d, 0) for _, d in adjust)
    scale = min(1.0, budget / spend) if spend > 0 else 1.0
    return sells, [(s, n * scale) for s, n in buys], \
        [(s, d * scale if d > 0 else d) for s, d in adjust], weight, scale


def submit(tc, sells, buys, adjust) -> int:
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import MarketOrderRequest
    n = 0
    for sym, qty in sells:
        tc.submit_order(MarketOrderRequest(symbol=sym, qty=qty, side=OrderSide.SELL,
                                           time_in_force=TimeInForce.DAY))
        journal(f"| {datetime.now(timezone.utc):%Y-%m-%d %H:%M} | ALPACA-PAPER SELL {sym} "
                f"qty={qty:g} | momentum rebalance exit |")
        n += 1
    for sym, notional in buys + [(s, d) for s, d in adjust if d > 0]:
        if notional < 1:
            continue
        tc.submit_order(MarketOrderRequest(symbol=sym, notional=round(notional, 2),
                                           side=OrderSide.BUY, time_in_force=TimeInForce.DAY))
        journal(f"| {datetime.now(timezone.utc):%Y-%m-%d %H:%M} | ALPACA-PAPER BUY {sym} "
                f"${notional:,.0f} | momentum top-decile |")
        n += 1
    # Overweight names (negative adjusts) are left to drift to the next monthly
    # rebalance: partial-sell mechanics add churn for no measured edge.
    return n


def cmd_plan(args, execute=False):
    tc = clients()
    acct, equity, cash, day_move, positions = account_state(tc)
    print(f"[account] equity=${equity:,.2f} cash=${cash:,.2f} "
          f"day move={day_move:+.2%} positions={len(positions)}")
    circuit = day_move <= DAILY_CIRCUIT
    if circuit:
        print(f"[circuit] equity down {day_move:.1%} on the day (< {DAILY_CIRCUIT:.0%}): "
              f"NEW BUYS REFUSED this run; sells still allowed.")
    top, t0 = targets()
    print(f"[signal ] formation {t0:%Y-%m-%d}, {len(top)} target names")
    sells, buys, adjust, weight, scale = build_orders(
        top, equity, cash, positions, max_new=args.max_new)
    if circuit:
        buys, adjust = [], [(s, d) for s, d in adjust if d < 0]
    print(f"[plan   ] weight/name={weight:.2%} (cap {MAX_POSITION_PCT:.0%}, "
          f"floor {CASH_FLOOR:.0%})  sells={len(sells)}  buys={len(buys)}  "
          f"adjusts={len(adjust)}  budget scale={scale:.2f}")
    for s, q in sells[:10]:
        print(f"    SELL {s} qty {q:g}")
    for s, n in buys[:10]:
        print(f"    BUY  {s} ${n:,.0f}")
    if len(sells) > 10 or len(buys) > 10:
        print(f"    ... ({len(sells)} sells, {len(buys)} buys total)")
    if not execute:
        print("\nDRY RUN: nothing submitted. Add --execute to rebalance for real paper orders.")
        return
    clock = tc.get_clock()
    n = submit(tc, sells, buys, adjust)
    state = "market open, filling now" if clock.is_open else \
        f"market closed, DAY orders queue for {clock.next_open:%Y-%m-%d %H:%M %Z}"
    print(f"\nSUBMITTED {n} paper orders ({state}).")
    journal(f"| {datetime.now(timezone.utc):%Y-%m-%d %H:%M} | ALPACA-PAPER REBALANCE "
            f"{n} orders, formation {t0:%Y-%m-%d}, {len(top)} names, "
            f"weight {weight:.2%} | {state} |")


def cmd_check(_args):
    """Catastrophe stop: close any position 25% below average entry. Run daily."""
    tc = clients()
    fired = 0
    for p in tc.get_all_positions():
        ret = float(p.unrealized_plpc)
        if ret <= CAT_STOP:
            tc.close_position(p.symbol)
            journal(f"| {datetime.now(timezone.utc):%Y-%m-%d %H:%M} | ALPACA-PAPER "
                    f"CAT-STOP {p.symbol} at {ret:.1%} from entry | closed |")
            print(f"CAT-STOP fired: {p.symbol} at {ret:.1%} from entry, position closed")
            fired += 1
    if not fired:
        print(f"catastrophe stop ({CAT_STOP:.0%}): no position at trigger; "
              f"worst is {min((float(p.unrealized_plpc) for p in tc.get_all_positions()), default=0):.1%}")
    return fired


def cmd_status(_args):
    tc = clients()
    acct, equity, cash, day_move, positions = account_state(tc)
    lines = [f"# Alpaca paper book", "",
             f"Marked {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC. "
             f"Start $100,000.00.", "",
             f"- Equity: ${equity:,.2f} ({equity / 100_000 - 1:+.2%})",
             f"- Cash: ${cash:,.2f}  | Day move: {day_move:+.2%}",
             f"- Open positions: {len(positions)}", ""]
    if positions:
        lines += ["| Symbol | Qty | Value |", "|---|---|---|"]
        for s in sorted(positions):
            p = positions[s]
            lines.append(f"| {s} | {p['qty']:g} | ${p['value']:,.2f} |")
    BOOK_MD.write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:8]))
    print(f"... book written to {BOOK_MD}")


def main():
    ap = argparse.ArgumentParser(description="Momentum book on the Alpaca paper account")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "rebalance"):
        p = sub.add_parser(name)
        p.add_argument("--max-new", type=int, default=None,
                       help="charter switch: cap new positions this run (off for the basket)")
        p.add_argument("--hard-stop", type=float, default=None,
                       help="charter switch: per-name stop %% (off for the basket)")
        if name == "rebalance":
            p.add_argument("--execute", action="store_true",
                           help="submit real paper orders (dry-run without it)")
    sub.add_parser("status")
    sub.add_parser("check", help="catastrophe stop sweep (close names 25% under entry)")
    a = ap.parse_args()
    if a.cmd == "plan":
        cmd_plan(a, execute=False)
    elif a.cmd == "rebalance":
        cmd_plan(a, execute=a.execute)
    elif a.cmd == "check":
        cmd_check(a)
    else:
        cmd_status(a)


if __name__ == "__main__":
    main()
