"""Live against replay: did the paper book lose because of the strategy or the execution?

    .venv/bin/python 03-inputs/live_vs_replay.py

Asked by the operator on 19 October 2026, after the paper book fell 6 per cent
since 18 August while the market was flat. The book's own rules are replayed
over the same days from the daily closes on disk, twice.

    On time    rebalanced on the first session of every week, as designed.
    As traded  rebalanced on the days the book really traded, read off the
               broker's order history.

Both pick names exactly as alpaca_trade.targets does today: 12-1 momentum on
the close before the rebalance, funds excluded, the 500 most traded eligible
names, the top tenth, admitted under the 20 per cent cluster cap, 1.8 per cent
each and 10 per cent cash. Names that leave are sold, new names bought, and a
held name is topped up only when it has fallen more than 25 per cent below its
target, as the live code does. Trades are made at the rebalance day's close and
cost nothing, so the replay is the strategy with perfect execution.

The gaps then split the loss three ways. On time minus as traded is what the
late rebalances cost. As traded minus the live account is what execution cost:
fills during the day instead of at the close, trading cost, the names the
broker would not buy in dollars, and the first week, which ran before the
cluster cap and the fund exclusion existed. What is left is the strategy.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import model_metrics as mm                                       # noqa: E402
from alpaca_trade import (CASH_FLOOR, CLUSTER_CAP, LIVE_FROM, REBALANCE_BAND,  # noqa: E402
                          REBALANCE_MIN_ORDERS, START_EQUITY, TOP_LIQ,
                          UNIVERSE_EXCLUDE, clients)
from equity_cluster_cap import CORR_WINDOW, RHO, admit           # noqa: E402
from equity_momentum_monthly import (MIN_DOLLAR_VOL, MIN_HISTORY,    # noqa: E402
                                     MIN_NAMES, MIN_PRICE, SIGNALS, TOP_FRAC,
                                     monthly_panel)

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "04-outputs" / "AA-evals"


def picks(d, px, dv_med, sig, hist_ok, logret) -> list:
    """The names targets() would choose with data up to the close of day d."""
    elig = (hist_ok.loc[d] & (px.loc[d] >= MIN_PRICE) & (dv_med.loc[d] >= MIN_DOLLAR_VOL)
            & sig.loc[d].notna())
    names = elig[elig].index
    if len(names) > TOP_LIQ:
        names = dv_med.loc[d, names].nlargest(TOP_LIQ).index
    if len(names) < MIN_NAMES:
        return []
    s = sig.loc[d, names].sort_values(ascending=False)
    n_target = max(1, int(round(len(names) * TOP_FRAC)))
    pool = s.index[:min(len(s), n_target * 6)]
    corr = logret.loc[:d, pool].tail(CORR_WINDOW).corr()
    return admit(list(s.index), corr, n_target, CLUSTER_CAP, RHO, 1 - CASH_FLOOR)


def replay(px, days, trade_days, choose) -> pd.Series:
    """Daily value of the book traded on trade_days at the close, no cost."""
    cash, shares, out = START_EQUITY, {}, []
    for i, d in enumerate(days):
        if d in trade_days:
            prev = days[days.get_loc(d) - 1]
            top = choose(prev)
            if top:
                value = cash + sum(q * px.at[d, s] for s, q in shares.items() if px.at[d, s] == px.at[d, s])
                target = value * (1 - CASH_FLOOR) / len(top)
                for s in [s for s in shares if s not in top]:
                    p = px.at[d, s]
                    cash += shares.pop(s) * (p if p == p else 0.0)
                for s in top:
                    held = shares.get(s, 0.0) * px.at[d, s]
                    if s not in shares or held < target * (1 - REBALANCE_BAND):
                        buy = min(target - held, max(0.0, cash - value * CASH_FLOOR))
                        if buy > 0 and px.at[d, s] == px.at[d, s]:
                            shares[s] = shares.get(s, 0.0) + buy / px.at[d, s]
                            cash -= buy
        val = cash + sum(q * px.at[d, s] for s, q in shares.items() if px.at[d, s] == px.at[d, s])
        out.append(val)
    return pd.Series(out, index=days)


def live_days(tc) -> list:
    """Days the broker filled at least REBALANCE_MIN_ORDERS orders, in New York dates."""
    from zoneinfo import ZoneInfo

    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest
    start = pd.Timestamp(LIVE_FROM, tz="UTC") - pd.Timedelta(days=1)
    orders = tc.get_orders(GetOrdersRequest(status=QueryOrderStatus.CLOSED, after=start.to_pydatetime(), limit=500))
    by = pd.Series([o.filled_at.astimezone(ZoneInfo("America/New_York")).date()
                    for o in orders if o.filled_at is not None]).value_counts()
    return sorted(pd.Timestamp(d) for d, n in by.items() if n >= REBALANCE_MIN_ORDERS)


def live_curve(tc, px) -> pd.Series:
    """The account's closing equity, with today's close valued from the positions."""
    from alpaca_daily_report import equity_curve
    c = equity_curve()
    c.index = pd.to_datetime(c.index)
    last = px.index.max()
    if last not in c.index:
        acct = tc.get_account()
        pos = tc.get_all_positions()
        c.loc[last] = float(acct.cash) + sum(float(p.qty) * px.at[last, p.symbol] for p in pos)
    return c.sort_index()


def main() -> int:
    px, dv, dv_med = monthly_panel(UNIVERSE_EXCLUDE)
    px.index = pd.to_datetime(px.index).normalize()
    dv_med.index = px.index
    sig = SIGNALS["mom_12_1"](px)
    hist_ok = px.notna().rolling(MIN_HISTORY, min_periods=MIN_HISTORY).count() >= MIN_HISTORY
    logret = np.log(px).diff()
    cache: dict = {}

    def choose(d):
        if d not in cache:
            cache[d] = picks(d, px, dv_med, sig, hist_ok, logret)
        return cache[d]

    start = pd.Timestamp(LIVE_FROM)
    days = px.index[px.index >= start]
    week = days.to_period("W")
    on_time = set(days[np.r_[True, week[1:] != week[:-1]]])
    tc = clients()
    traded = set(d for d in live_days(tc) if d in days)
    print(f"{len(days)} sessions from {days[0]:%Y-%m-%d} to {days[-1]:%Y-%m-%d}; "
          f"{len(on_time)} on-time rebalances, {len(traded)} as traded: "
          + ", ".join(f"{d:%m-%d}" for d in sorted(traded)), flush=True)
    a = replay(px, days, on_time, choose)
    b = replay(px, days, traded, choose)
    live = live_curve(tc, px).reindex(days).ffill()
    spy = px.loc[days, "SPY"] / px.loc[days[0], "SPY"] * START_EQUITY if "SPY" in px.columns else None
    if spy is None:
        from alpaca_daily_report import benchmark
        sp = benchmark()
        sp.index = pd.to_datetime(sp.index)
        sp = sp.reindex(days).ffill()
        spy = sp / sp.iloc[0] * START_EQUITY
    ret = lambda s: float(s.iloc[-1] / START_EQUITY - 1)
    R = dict(on_time=ret(a), as_traded=ret(b), live=ret(live), spy=ret(spy))
    timing = R["on_time"] - R["as_traded"]
    execution = R["as_traded"] - R["live"]
    for k, v in R.items():
        print(f"{k:10s} {v:+.2%}")
    print(f"late rebalances cost {timing:+.2%}; execution cost {execution:+.2%}; "
          f"the strategy itself, on time, against the market {R['on_time'] - R['spy']:+.2%}")

    # Week by week, so a single bad week is visible.
    wk = pd.DataFrame({"on time": a, "as traded": b, "live": live, "market": spy})
    weekly = wk.groupby(wk.index.to_period("W")).last().pct_change()
    weekly.iloc[0] = wk.groupby(wk.index.to_period("W")).last().iloc[0] / START_EQUITY - 1

    stamp = datetime.now()
    day = OUT / f"{stamp:%Y-%m-%d}"
    day.mkdir(parents=True, exist_ok=True)
    md = mm.unclobbered(day / f"live-vs-replay-{stamp:%Y%m%d-%H%M%S}.md")
    p = lambda v: f"{v:+.2%}"
    L = [f"# Live against replay, {stamp:%d %B %Y %H:%M}", "",
         f"From {days[0]:%d %B} to {days[-1]:%d %B %Y}, {len(days)} sessions, the book's own rules were "
         f"replayed from the daily closes on disk with perfect execution, once rebalanced every week on time "
         f"and once on the {len(traded)} days the book really traded.", "",
         "| version | change since 18 August |", "| --- | ---: |",
         f"| Replay, rebalanced on time | {p(R['on_time'])} |",
         f"| Replay, rebalanced when the book did | {p(R['as_traded'])} |",
         f"| The live paper account | {p(R['live'])} |",
         f"| The market, SPY | {p(R['spy'])} |", "",
         f"The late rebalances cost {p(timing)}. Execution, meaning fills during the day instead of at the "
         f"close, trading cost, names the broker would not buy and the first week's older rules, cost "
         f"{p(execution)}. The strategy itself, traded on time and perfectly, did {p(R['on_time'] - R['spy'])} "
         f"against the market.", "",
         "## Week by week", "",
         "| week ending | replay on time | replay as traded | live | market |", "| --- | ---: | ---: | ---: | ---: |"]
    for w, r in weekly.iterrows():
        L.append(f"| {w.end_time:%d %b} | {p(r['on time'])} | {p(r['as traded'])} | {p(r['live'])} | {p(r['market'])} |")
    L += ["", "Rebalance days as traded: " + ", ".join(f"{d:%d %b}" for d in sorted(traded)) + ".", "",
          "Run with `03-inputs/live_vs_replay.py`.", ""]
    md.write_text("\n".join(L) + "\n", encoding="utf-8")
    wk.to_csv(md.with_suffix(".curves.csv"))
    print(f"record: {md.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
