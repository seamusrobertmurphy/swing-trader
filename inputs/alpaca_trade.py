"""Track A Phase A5: the momentum book on the Alpaca PAPER account, hard rules enforced.

Strategy (the one that passed all three checks): 12-1 momentum, top decile of
the top-500 dollar-volume universe, ~50 names equal weight. Cadence: WEEKLY
(operator decision 2026-08-18, after the weekly variant survived the same bars
as monthly with better fold stability; record
outputs/AA-evals/2026-08-18/weekly-factors-20260818.md). A guard refuses a
rebalance within 5 days of the last one (--force overrides), so the book can
never drift to a cadence the evidence has not tested.

Weekly runbook, in order. RUN IT INTRADAY, not overnight: orders submitted
while the market is shut queue into the opening auction, which cost +42.6bp per
fill on 2026-08-26 against +7.3bp for the mid-session batch a week earlier. A
guard now refuses to submit outside the session; --anytime overrides.

    .venv/bin/python inputs/alpaca_data.py download      # refresh bars
    .venv/bin/python inputs/alpaca_trade.py rebalance --execute
    .venv/bin/python inputs/alpaca_trade.py check        # catastrophe stop
    .venv/bin/python inputs/alpaca_trade.py status
    .venv/bin/python inputs/alpaca_execution_report.py   # measured slippage

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

import numpy as np
import pandas as pd

import config
from equity_cluster_cap import CORR_WINDOW, RHO, admit, largest_cluster
from equity_momentum_monthly import (MIN_DOLLAR_VOL, MIN_HISTORY, MIN_NAMES,
                                     MIN_PRICE, SIGNALS, TOP_FRAC, monthly_panel)

REPO = Path(__file__).resolve().parents[1]
TRADE_LOG = REPO / "memory" / "trade-log.md"
BOOK_MD = REPO / "memory" / "alpaca-portfolio.md"
STATE = REPO / "memory" / "alpaca-book-state.json"
MIN_REBALANCE_GAP_DAYS = 5     # weekly cadence, guarded

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
# Universe filter (added 2026-08-25). Alpaca files every ETF under
# AssetClass.US_EQUITY and nothing downstream filtered them, so the first live
# book bought SOXL, KORU and MUU: Direxion 3X, 3X and 2X leveraged funds. That
# breaks the charter's never-margin rule, and it is a selection artifact
# besides, since a 3x fund carries ~3x its sector's trailing return and a
# momentum rank therefore promotes leverage mechanically. Re-running the
# pre-registered monthly test across all three settings (record
# outputs/AA-evals/2026-08-25/) showed 12-1 momentum SURVIVES in every case and
# is marginally STRONGER without funds (+1.132%/month, t 2.59, against
# +1.082%, t 2.53 as deployed), so the exclusion costs no measured edge.
UNIVERSE_EXCLUDE = "funds"

# Correlation-cluster cap (Principle 7), added 2026-08-25. The charter caps any
# group of holdings correlating above 0.7 at 20% of equity. It was never
# enforced, and on 2026-08-25 the live book had 37 of 49 names in one group
# worth 66.6% of equity: chips, memory and optics. That is why a -0.20% week
# for SPY was a -6.25% week for the book.
#
# WHICH DEFINITION. The charter's wording is transitive: A moves with B, B with
# C, so all three are one group even when A and C are unrelated. Measured on
# the real book that definition chains 37 names into a single blob and, applied
# as an admission rule, would refuse almost every buy. This code therefore uses
# the LOCAL rule instead: a candidate is admitted only if the weight already
# held that correlates above RHO *with that candidate* leaves room under the
# cap. It cannot chain, and it still binds hard (50 names at 1.8% means at most
# 11 per group). The transitive reading stays available as a diagnostic in
# equity_cluster_cap.largest_cluster and is printed on every plan.
#
# SYMMETRY FIX, 2026-08-26. The first version of the rule tested only a
# candidate's links back to names already admitted, and never re-tested those
# earlier names as later correlates arrived, so a name admitted early
# accumulated an unbounded neighbourhood. Measured on the book it produced,
# ASX ended with 36.0% of equity correlating above 0.7 with it and ten of the
# fifty holdings sat over the 20% cap; the largest chained group was still 35
# names at 62.6% of equity, against 37 at 66.6% with no cap at all. The cap was
# not being enforced, only its appearance. equity_cluster_cap.admit is now
# symmetric: a candidate is admitted only when neither it nor anything it links
# to breaches the cap afterwards. On the 2026-08-25 formation that holds every
# neighbourhood at or under 19.8% (zero breaches) and cuts the largest chained
# group to 18 names, 32.4% of equity. Cost over 115 months at the live shape:
# the monthly edge falls from 1.444% to 1.379%, about 4.4%, fold pass rates are
# unchanged at 84%/79%, and the verdict stays SURVIVES (record
# outputs/AA-evals/2026-08-26/cluster-cap-symmetric-liveshape-20260826.txt).
# It takes effect at the next rebalance; the live book still carries the
# concentration the asymmetric rule allowed.
CLUSTER_CAP = 0.20


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


def targets(cluster_cap: float | None = None) -> tuple[list[str], pd.Timestamp]:
    """Top-decile names at the latest month-end formation, top-500 liquidity tier."""
    px, dv, dv_med = monthly_panel(UNIVERSE_EXCLUDE)
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
    s = sig.loc[t0, names].sort_values(ascending=False)
    n_target = max(1, int(round(len(names) * TOP_FRAC)))
    if cluster_cap is None:
        cluster_cap = CLUSTER_CAP
    if cluster_cap <= 0:
        return sorted(s.index[:n_target]), t0
    ret = np.log(px[names]).diff()
    pool = s.index[:min(len(s), n_target * 6)]
    corr = ret.loc[:t0, pool].tail(CORR_WINDOW).corr()
    held = admit(list(s.index), corr, n_target, cluster_cap, RHO, 1 - CASH_FLOOR)
    big = largest_cluster(held, corr, RHO)
    w = (1 - CASH_FLOOR) / n_target
    print(f"[cluster] cap {cluster_cap:.0%} at rho>{RHO}: {len(held)} names admitted; "
          f"largest chained group held {big} names = {big * w:.1%} of equity "
          f"(chained view is diagnostic only, the cap is the local rule)")
    return sorted(held), t0


# Execution-window guard (added 2026-08-26). The 2026-08-26 rebalance was
# submitted at 01:08 ET while the market was shut, so all 31 DAY orders queued
# into the opening auction and every one filled inside the first six minutes,
# at +42.6bp mean against the +7.3bp measured on the 2026-08-18 mid-session
# batch. The open is the widest spread and the fastest tape of the day. This
# refuses to submit outside a calm intraday window; --anytime overrides.
OPEN_BUFFER_MIN = 15           # no submitting inside the opening auction
CLOSE_BUFFER_MIN = 15          # nor into the closing auction


def session_gate(clock) -> str | None:
    """Return an abort message when now is a bad moment to send market orders."""
    now = datetime.now(timezone.utc)
    if not clock.is_open:
        return (f"ABORT: the market is shut. DAY orders sent now queue into the "
                f"{clock.next_open:%Y-%m-%d %H:%M %Z} opening auction, which cost this book "
                f"+42.6bp per fill on 2026-08-26 against +7.3bp mid-session. Re-run at least "
                f"{OPEN_BUFFER_MIN} minutes after the open. --anytime overrides.")
    to_close = (clock.next_close - now).total_seconds() / 60
    if to_close < CLOSE_BUFFER_MIN:
        return (f"ABORT: {to_close:.0f} minutes to the close; orders would land in the closing "
                f"auction. Re-run tomorrow intraday. --anytime overrides.")
    return None


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
    top, t0 = targets(getattr(args, 'cluster_cap', None))
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
    if STATE.exists():
        last = datetime.fromisoformat(json.loads(STATE.read_text())["last_rebalance"])
        gap = (datetime.now(timezone.utc) - last).days
        if gap < MIN_REBALANCE_GAP_DAYS and not getattr(args, "force", False):
            raise SystemExit(f"ABORT: last rebalance was {gap} day(s) ago; the tested "
                             f"cadence is weekly (>= {MIN_REBALANCE_GAP_DAYS} days). "
                             f"--force overrides.")
    clock = tc.get_clock()
    if not getattr(args, "anytime", False):
        gate = session_gate(clock)
        if gate:
            raise SystemExit(gate)
    n = submit(tc, sells, buys, adjust)
    STATE.write_text(json.dumps(dict(
        last_rebalance=datetime.now(timezone.utc).isoformat(),
        formation=f"{t0:%Y-%m-%d}", names=len(top), orders=n)))
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
        p.add_argument("--cluster-cap", type=float, default=None,
                       help=f"correlation-cluster cap, share of equity "
                            f"(default {CLUSTER_CAP:.0%}; 0 disables)")
        if name == "rebalance":
            p.add_argument("--execute", action="store_true",
                           help="submit real paper orders (dry-run without it)")
            p.add_argument("--force", action="store_true",
                           help="override the weekly cadence guard")
            p.add_argument("--anytime", action="store_true",
                           help="override the intraday execution-window guard")
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
