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
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import config
from equity_cluster_cap import CORR_WINDOW, RHO, admit, largest_cluster
from equity_momentum_monthly import (MIN_DOLLAR_VOL, MIN_HISTORY, MIN_NAMES,
                                     MIN_PRICE, SIGNALS, TOP_FRAC, monthly_panel)

REPO = Path(__file__).resolve().parents[1]
# A live account keeps its journal, book, state and reports out of the public
# repository (added 2026-10-14). The paper book's files stay where they were
# and stay tracked; a live account's go under LIVE_DIR and LIVE_REPORTS, which
# .gitignore excludes, so real positions and balances are never committed.
MEMORY = REPO / "05-research" / "memory"
LIVE_DIR = MEMORY / "live"
LIVE_REPORTS = REPO / "04-outputs" / "AA-evals" / "live"
_BOOK = MEMORY if config.alpaca_is_paper() else LIVE_DIR
TRADE_LOG = _BOOK / "trade-log.md"
BOOK_MD = _BOOK / "alpaca-portfolio.md"
STATE = _BOOK / "alpaca-book-state.json"
REPORTS = REPO / "04-outputs" / "AA-evals" if config.alpaca_is_paper() else LIVE_REPORTS
MIN_REBALANCE_GAP_DAYS = 5     # weekly cadence, guarded

TOP_LIQ = 500
CASH_FLOOR = 0.10
MAX_POSITION_PCT = 0.05
DAILY_CIRCUIT = -0.03
REBALANCE_BAND = 0.25          # rebalance an existing name only if off target by >25%
# Trim winners (operator decision 2026-10-20): a held name more than
# REBALANCE_BAND above its target is sold back to the target. Adopted by its
# pre-set rule, Sharpe 0.962 against 0.853 and worst fall -34.2% against
# -37.4%, 2017 to 2026 (04-outputs/AA-evals/2026-10-20/trim-winners-test-*.md).
TRIM_WINNERS = True
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


# Paper or live, and where the book started (added 2026-10-14). Every journal
# line said ALPACA-PAPER and every report measured from $100,000, so a live
# account would have labelled real trades as paper and measured them against
# the wrong start. The label now follows the address in use, and the start and
# first-rebalance date are settings, ALPACA_START_EQUITY and ALPACA_LIVE_FROM,
# whose defaults are the paper book's own.
START_EQUITY = float(config.get("ALPACA_START_EQUITY", "100000"))
LIVE_FROM = config.get("ALPACA_LIVE_FROM", "2026-08-18")


def base_url() -> str:
    return (os.environ.get("ALPACA_BASE_URL") or config.ALPACA_BASE_URL).strip()


def is_paper() -> bool:
    return config.alpaca_is_paper()


def book_label() -> str:
    return "ALPACA-PAPER" if is_paper() else "ALPACA-LIVE"


def clients():
    from alpaca.trading.client import TradingClient
    key, secret = config.alpaca_keys()
    base = base_url()
    if not key or not secret:
        raise SystemExit("ABORT: Alpaca keys missing.")
    if "paper" not in base and os.environ.get("LIVE_TRADING") != "true":
        raise SystemExit(f"ABORT: {base} is not the paper endpoint and LIVE_TRADING "
                         f"is not 'true'. The money switch stays off.")
    return TradingClient(key, secret, paper="paper" in base)


# Where the last rebalance date comes from (added 2026-10-14). It used to be
# only the STATE file on whichever machine traded, which breaks the moment a
# second scheduler exists: a GitHub runner starts with no file at all and
# would rebalance again on its first tick, and the laptop cannot see what the
# runner did. The broker sees every order from every machine, so it is the
# record both read. Rebalance orders carry a client order id starting
# ORDER_TAG; orders sent before the tag existed are recognised as any day
# with at least REBALANCE_MIN_ORDERS orders. A catastrophe stop sends one
# order per name, so only five stops on one day could pass for a rebalance,
# and that mistake only delays the next one.
ORDER_TAG = "rb-"
REBALANCE_MIN_ORDERS = 5


def last_rebalance(tc, state: Path | None = None) -> datetime | None:
    """The later of this machine's STATE stamp and the broker's order history.

    state names another book's STATE file, which the tick needs because it
    imports this module on the paper address and asks about the live one."""
    state = state or STATE
    from datetime import timedelta

    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest
    seen = []
    if state.exists():
        seen.append(datetime.fromisoformat(json.loads(state.read_text())["last_rebalance"]))
    orders = tc.get_orders(GetOrdersRequest(
        status=QueryOrderStatus.ALL, limit=500,
        after=datetime.now(timezone.utc) - timedelta(days=35)))
    by_day: dict = {}
    for o in orders:
        if (o.client_order_id or "").startswith(ORDER_TAG):
            seen.append(o.submitted_at)
        by_day.setdefault(o.submitted_at.date(), []).append(o.submitted_at)
    seen += [max(t) for t in by_day.values() if len(t) >= REBALANCE_MIN_ORDERS]
    return max(seen) if seen else None


def journal(line: str) -> None:
    TRADE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(TRADE_LOG, "a", encoding="utf-8") as f:
        f.write(line.rstrip() + "\n")


def buyable(tc) -> set[str]:
    """Symbols the broker will take a dollar-amount buy for today.

    Added 2026-10-14. Every buy is a dollar amount, which Alpaca accepts only
    for assets marked fractionable, and a refusal raised in the middle of
    submit() would leave the book half rebalanced. One call lists every asset.
    """
    # The raw list, not get_all_assets (19 October 2026). alpaca-py checks each
    # exchange against a fixed list, and one stock moving to the new Texas
    # exchange, CECO on TXSE, made the whole call raise and stopped the rebalance.
    from types import SimpleNamespace
    assets = [SimpleNamespace(**a) for a in tc.get("/assets", {"status": "active", "asset_class": "us_equity"})]
    return {a.symbol for a in assets if a.tradable and a.fractionable}


def targets(cluster_cap: float | None = None,
            allowed: set[str] | None = None) -> tuple[list[str], pd.Timestamp]:
    """Top-decile names at the latest month-end formation, top-500 liquidity tier.

    allowed, when given, removes names the broker cannot buy in dollars after
    the decile size is set, so the next-ranked name takes the place.
    """
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
    if allowed is not None:
        dropped = [x for x in s.index[:n_target * 2] if x not in allowed]
        if dropped:
            print(f"[buyable] skipped, not buyable in dollars today: {', '.join(dropped)}")
        s = s[s.index.isin(allowed)]
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
# Raised 15 to 90 on 19 October 2026, workplan item 1. Off the open the book's
# 183 market fills cost 7.9bp mean, 5.2 median. The rebalances sent between
# 10:02 and 10:28 cost 9.2, 5.0, 10.0 and 15.1bp mean, the two sent at 11:13
# and 12:54 cost 4.6 and 3.9, each on 12 to 21 fills. Thin evidence, but it
# points the way the spread is known to go, narrowing through the first hour,
# so the rebalance now waits for the second. Measured again at 24 November.
OPEN_BUFFER_MIN = 90           # no submitting inside the first hour and a half
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


# The drawdown ramp, adopted 19 October 2026 by the rule fixed before its test
# (03-inputs/drawdown_ramp_test.py, record drawdown-ramp-test-20261019-220317).
# When the book is down more than 5 per cent over five sessions, each further
# 1 per cent cuts the size of new positions by 10 per cent; held names and
# their top-ups are untouched, and next week's rebalance tops the new names
# up once the book recovers. In the replay from 2017 it bit in 50 of 510 weeks
# and changed almost nothing, Sharpe 0.845 against 0.840, worst fall 38.8 per
# cent against 38.9, ending 0.15 per cent poorer.
RAMP_TRIGGER = -0.05
RAMP_PER_POINT = 10.0


def ramp_scale(equity: float) -> tuple[float, float | None]:
    """The ramp's multiplier for new buys, and the five-session move behind it."""
    from zoneinfo import ZoneInfo

    try:
        from alpaca_daily_report import equity_curve   # imported here; it imports this module
        curve = equity_curve()
    except Exception as e:  # noqa: BLE001
        print(f"[ramp   ] no equity history ({str(e)[:80]}); new buys at full size")
        return 1.0, None
    prior = curve[curve.index < datetime.now(ZoneInfo("America/New_York")).date()]
    if len(prior) < 5:
        return 1.0, None
    move = equity / float(prior.iloc[-5]) - 1
    if move >= RAMP_TRIGGER:
        return 1.0, move
    return max(0.0, 1.0 - RAMP_PER_POINT * (RAMP_TRIGGER - move)), move


def build_orders(top, equity, cash, positions, max_new=None):
    weight = min((1 - CASH_FLOOR) / len(top), MAX_POSITION_PCT)
    per_name = equity * weight
    sells = [(s, p["qty"]) for s, p in positions.items() if s not in top and p["qty"] > 0]
    buys, adjust, trims = [], [], []
    for sym in top:
        held = positions.get(sym, {}).get("value", 0.0)
        if held == 0:
            buys.append((sym, per_name))
        elif abs(held - per_name) / per_name > REBALANCE_BAND:
            adjust.append((sym, per_name - held))
    if TRIM_WINNERS:
        # A trim is a share count, as every sell is, at the position's own mark.
        for sym, d in [(s, d) for s, d in adjust if d < 0]:
            p = positions[sym]
            trims.append((sym, round(-d / p["value"] * p["qty"], 6)))
    adjust = [(s, d) for s, d in adjust if d > 0]
    if max_new is not None:
        buys = buys[:max_new]
    # never-margin: total new spend cannot exceed free cash after the floor,
    # counting cash freed by the sells and trims at current marks.
    freed = sum(positions[s]["value"] for s, _ in sells) \
        + sum(positions[s]["value"] * q / positions[s]["qty"] for s, q in trims)
    budget = max(0.0, cash + freed - equity * CASH_FLOOR)
    spend = sum(n for _, n in buys) + sum(max(d, 0) for _, d in adjust)
    scale = min(1.0, budget / spend) if spend > 0 else 1.0
    return sells, [(s, n * scale) for s, n in buys], \
        [(s, d * scale) for s, d in adjust], trims, weight, scale


# How long submit() waits for the sells to fill before buying (added
# 2026-10-14). Mid-session market sells in these names fill in seconds.
SELL_WAIT_S = 180


def _wait_for_fills(tc, ids: list) -> int:
    """Wait until the orders are filled or SELL_WAIT_S passes; return how many filled."""
    import time
    deadline = time.monotonic() + SELL_WAIT_S
    left = set(ids)
    while left and time.monotonic() < deadline:
        time.sleep(3)
        for i in list(left):
            st = str(tc.get_order_by_id(i).status).split(".")[-1].lower()
            if st in ("filled", "canceled", "expired", "rejected"):
                left.discard(i)
    return len(ids) - len(left)


# The limit-first test, added 19 October 2026, workplan item 1. A market order
# crosses the whole spread, about 5bp on the typical fill here; a limit at the
# midpoint pays none of it when it fills. Every other name goes limit-first at
# the midpoint of the latest IEX quote, the only live quote the data plan
# serves, waits LIMIT_WAIT_S, and whatever is left is cancelled and resent as
# a market order, so the book never ends the day short a name. The tag's last
# letters say which arm a fill came from, l for a limit fill, lm for its
# market fallback, nothing for the market arm, and alpaca_execution_report
# scores the two arms side by side. Judged at the 24 November rebalance.
LIMIT_TEST = True
LIMIT_WAIT_S = 90
QUOTE_MAX_AGE_S = 120          # an older quote is not a price
QUOTE_MAX_SPREAD_BP = 100      # a quote this wide is one venue's, not the market's
TERMINAL = ("filled", "canceled", "expired", "rejected")


def _status(o) -> str:
    return str(o.status).split(".")[-1].lower()


def _quotes(symbols) -> dict:
    """Midpoint of the latest IEX quote per symbol; a symbol is left out when
    its quote is empty, crossed, stale or wider than QUOTE_MAX_SPREAD_BP."""
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestQuoteRequest
    out = {}
    if not symbols:
        return out
    key, secret = config.alpaca_keys()
    try:
        q = StockHistoricalDataClient(key, secret).get_stock_latest_quote(
            StockLatestQuoteRequest(symbol_or_symbols=list(symbols)))
    except Exception as e:  # noqa: BLE001
        print(f"[quotes ] none served ({str(e)[:80]}); every order goes market")
        return out
    now = datetime.now(timezone.utc)
    for sym, v in q.items():
        bid, ask = float(v.bid_price or 0), float(v.ask_price or 0)
        if bid <= 0 or ask <= 0 or ask < bid:
            continue
        mid = (bid + ask) / 2
        if (ask - bid) / mid * 1e4 > QUOTE_MAX_SPREAD_BP:
            continue
        if (now - v.timestamp).total_seconds() > QUOTE_MAX_AGE_S:
            continue
        out[sym] = mid
    return out


def _limit(mid, side: str):
    """The midpoint rounded toward the near side of the spread, so the order
    sits inside it: down to the cent for a buy, up for a sell."""
    import math
    if mid is None:
        return None
    k = 100 if mid >= 1 else 10000
    v = math.floor(mid * k) if side == "buy" else math.ceil(mid * k)
    return v / k


def _send(tc, sym: str, side: str, amount: float, day: str, limit=None, fallback=False):
    """One order; amount is a share count for a sell and dollars for a buy."""
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest
    size = dict(qty=amount) if side == "sell" else dict(notional=round(amount, 2))
    tag = (f"{ORDER_TAG}{day}-{sym}-{side[0]}"
           + ("l" if limit is not None else "lm" if fallback else ""))
    common = dict(symbol=sym, side=OrderSide.SELL if side == "sell" else OrderSide.BUY,
                  time_in_force=TimeInForce.DAY, client_order_id=tag, **size)
    if limit is not None:
        return tc.submit_order(LimitOrderRequest(limit_price=limit, **common))
    return tc.submit_order(MarketOrderRequest(**common))


def _settle_limits(tc, pending: list, day: str, label: str) -> list:
    """Wait LIMIT_WAIT_S for the limit orders, cancel what is left and resend
    the unfilled part as a market order. pending holds (order id, symbol,
    side, amount); returns the ids of the market orders sent."""
    import time
    left = {oid: rest for oid, *rest in pending}
    deadline = time.monotonic() + LIMIT_WAIT_S
    while left and time.monotonic() < deadline:
        time.sleep(3)
        for oid in list(left):
            if _status(tc.get_order_by_id(oid)) in TERMINAL:
                left.pop(oid)
    sent, kept = [], 0
    for oid, (sym, side, amount) in left.items():
        try:
            tc.cancel_order_by_id(oid)
        except Exception:  # noqa: BLE001
            pass
        o = tc.get_order_by_id(oid)
        for _ in range(10):
            if _status(o) in TERMINAL:
                break
            time.sleep(1)
            o = tc.get_order_by_id(oid)
        if _status(o) not in TERMINAL:
            # Not confirmed cancelled, so a market order now could fill twice.
            # The name waits for the next rebalance and the journal says so.
            print(f"[limits ] {sym} {side} limit order {oid} not cancelled in 10s; left alone")
            journal(f"| {datetime.now(timezone.utc):%Y-%m-%d %H:%M} | {label} {side.upper()} {sym} "
                    f"limit not cancelled, left alone | limit-first test |")
            kept += 1
            continue
        done = float(o.filled_qty or 0)
        rest = amount - done if side == "sell" else amount - done * float(o.filled_avg_price or 0)
        if rest < (1e-6 if side == "sell" else 1):
            continue
        sent.append(_send(tc, sym, side, rest, day, fallback=True).id)
        journal(f"| {datetime.now(timezone.utc):%Y-%m-%d %H:%M} | {label} {side.upper()} {sym} "
                f"{'qty=' + format(rest, 'g') if side == 'sell' else '$' + format(rest, ',.0f')} "
                f"market after limit | limit-first test |")
    print(f"[limits ] {len(pending) - len(left)} of {len(pending)} limit orders filled within "
          f"{LIMIT_WAIT_S}s; {len(sent)} resent as market, {kept} left alone")
    return sent


def submit(tc, sells, buys, adjust, forced=False, trims=()) -> int:
    # The tag lets last_rebalance() find this run from any machine. Alpaca's
    # order reference calls the id unique but does not say what it does with
    # a repeat (checked 2026-10-14), so the cadence guard, not the tag, is
    # what stops a second scheduler trading the same day.
    day = f"{datetime.now(timezone.utc):%Y%m%d}" + ("f" if forced else "")
    label = book_label()
    n, sell_ids, lim = 0, [], []
    out = [(s, q, "momentum rebalance exit") for s, q in sells] \
        + [(s, q, "trim to target") for s, q in trims]
    q = _quotes([x for x, _, _ in out]) if LIMIT_TEST else {}
    for i, (sym, qty, why) in enumerate(out):
        price = _limit(q.get(sym), "sell") if LIMIT_TEST and i % 2 == 0 else None
        o = _send(tc, sym, "sell", qty, day, limit=price)
        sell_ids.append(o.id)
        if price is not None:
            lim.append((o.id, sym, "sell", qty))
        journal(f"| {datetime.now(timezone.utc):%Y-%m-%d %H:%M} | {label} SELL {sym} "
                f"qty={qty:g}{' limit ' + str(price) if price is not None else ''} | {why} |")
        n += 1
    if lim:
        more = _settle_limits(tc, lim, day, label)
        sell_ids += more
        n += len(more)
    # Buys wait for the sells (added 2026-10-14). They used to go in together,
    # so the buys spent money the sells had not yet raised, which a margin
    # account lends without a word. Now the sells fill first and the buys are
    # cut to the cash really there, less the floor, whatever did not fill.
    want = buys + [(s, d) for s, d in adjust if d > 0]
    if sell_ids:
        filled = _wait_for_fills(tc, sell_ids)
        print(f"[sells  ] {filled} of {len(sell_ids)} sells filled before buying")
    acct = tc.get_account()
    room = max(0.0, float(acct.cash) - float(acct.equity) * CASH_FLOOR)
    total = sum(x for _, x in want if x >= 1)
    if total > room:
        print(f"[budget ] buys of ${total:,.0f} cut to the ${room:,.0f} of cash above the floor")
        want = [(s, x * room / total) for s, x in want]
    want = [(x, v) for x, v in want if v >= 1]
    q = _quotes([x for x, _ in want]) if LIMIT_TEST else {}
    lim = []
    for i, (sym, notional) in enumerate(want):
        price = _limit(q.get(sym), "buy") if LIMIT_TEST and i % 2 == 0 else None
        o = _send(tc, sym, "buy", notional, day, limit=price)
        if price is not None:
            lim.append((o.id, sym, "buy", notional))
        journal(f"| {datetime.now(timezone.utc):%Y-%m-%d %H:%M} | {label} BUY {sym} "
                f"${notional:,.0f}{' limit ' + str(price) if price is not None else ''} | momentum top-decile |")
        n += 1
    if lim:
        n += len(_settle_limits(tc, lim, day, label))
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
    top, t0 = targets(getattr(args, 'cluster_cap', None), allowed=buyable(tc))
    print(f"[signal ] formation {t0:%Y-%m-%d}, {len(top)} target names")
    sells, buys, adjust, trims, weight, scale = build_orders(
        top, equity, cash, positions, max_new=args.max_new)
    if circuit:
        buys, adjust = [], []
    ramp, move = ramp_scale(equity)
    if move is not None:
        print(f"[ramp   ] five-session move {move:+.2%}; new positions at {ramp:.0%} of full size"
              + ("" if ramp < 1 else ", the ramp starts below -5%"))
    if ramp < 1:
        buys = [(s, n * ramp) for s, n in buys]
    print(f"[plan   ] weight/name={weight:.2%} (cap {MAX_POSITION_PCT:.0%}, "
          f"floor {CASH_FLOOR:.0%})  sells={len(sells)}  buys={len(buys)}  "
          f"adjusts={len(adjust)}  trims={len(trims)}  budget scale={scale:.2f}")
    for s, q in sells[:10]:
        print(f"    SELL {s} qty {q:g}")
    for s, q in trims:
        print(f"    TRIM {s} qty {q:g}")
    for s, n in buys[:10]:
        print(f"    BUY  {s} ${n:,.0f}")
    if len(sells) > 10 or len(buys) > 10:
        print(f"    ... ({len(sells)} sells, {len(buys)} buys total)")
    if not execute:
        print("\nDRY RUN: nothing submitted. Add --execute to rebalance for real paper orders.")
        return
    last = last_rebalance(tc)
    if last is not None:
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
    n = submit(tc, sells, buys, adjust, forced=getattr(args, "force", False), trims=trims)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(dict(
        last_rebalance=datetime.now(timezone.utc).isoformat(),
        formation=f"{t0:%Y-%m-%d}", names=len(top), orders=n)))
    state = "market open, filling now" if clock.is_open else \
        f"market closed, DAY orders queue for {clock.next_open:%Y-%m-%d %H:%M %Z}"
    print(f"\nSUBMITTED {n} paper orders ({state}).")
    journal(f"| {datetime.now(timezone.utc):%Y-%m-%d %H:%M} | {book_label()} REBALANCE "
            f"{n} orders, formation {t0:%Y-%m-%d}, {len(top)} names, "
            f"weight {weight:.2%} | {state} |")


def cmd_check(_args):
    """Catastrophe stop: close any position 25% below average entry. Run daily."""
    tc = clients()
    fired = 0
    for p in tc.get_all_positions():
        ret = float(p.unrealized_plpc)
        if ret <= CAT_STOP:
            try:
                tc.close_position(p.symbol)
            except Exception as e:  # noqa: BLE001  (the other scheduler got there first)
                print(f"CAT-STOP {p.symbol}: close refused ({e}); left for the next check")
                continue
            journal(f"| {datetime.now(timezone.utc):%Y-%m-%d %H:%M} | {book_label()} "
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
    lines = [f"# Alpaca {'paper' if is_paper() else 'live'} book", "",
             f"Marked {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC. "
             f"Start ${START_EQUITY:,.2f}.", "",
             f"- Equity: ${equity:,.2f} ({equity / START_EQUITY - 1:+.2%})",
             f"- Cash: ${cash:,.2f}  | Day move: {day_move:+.2%}",
             f"- Open positions: {len(positions)}", ""]
    if positions:
        lines += ["| Symbol | Qty | Value |", "|---|---|---|"]
        for s in sorted(positions):
            p = positions[s]
            lines.append(f"| {s} | {p['qty']:g} | ${p['value']:,.2f} |")
    BOOK_MD.parent.mkdir(parents=True, exist_ok=True)
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
