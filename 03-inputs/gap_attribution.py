"""Where the paper book's gap to the market came from, by holding and by first week.

    .venv/bin/python 03-inputs/gap_attribution.py

Asked by the operator on 22 October 2026, the second job left on 19 October.
The weekly split is already in live_vs_replay.py; this adds the two parts it
could not give.

By holding. Every filled order since LIVE_FROM is read from the broker. For
each name, dollars made = sells - buys + what is still held at today's price.
The names' dollars sum to the account's change, which is checked. The gap to
the market is that change minus what the start equity would have made in SPY.

First week. The book traded 18 to 21 August under older rules: funds were
still in the universe and there was no cluster cap. Two replays of that week,
both trading at the 18 August close on picks from the 17 August close with
perfect execution, separate what the older rules cost (new-rule replay minus
old-rule replay) from what buying during 18 August cost (old-rule replay minus
the live account). The old-rule picks are checked against the names the book
really bought on 18 August before any of this is reported.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import model_metrics as mm                                       # noqa: E402
from alpaca_trade import (CASH_FLOOR, LIVE_FROM, START_EQUITY, TOP_LIQ,  # noqa: E402
                          UNIVERSE_EXCLUDE, clients)
from equity_momentum_monthly import (MIN_DOLLAR_VOL, MIN_HISTORY,    # noqa: E402
                                     MIN_NAMES, MIN_PRICE, SIGNALS, TOP_FRAC,
                                     monthly_panel)
from live_vs_replay import live_curve, picks, replay              # noqa: E402

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "04-outputs" / "AA-evals"
NY = ZoneInfo("America/New_York")


def all_fills(tc) -> list:
    """Every filled order since LIVE_FROM, paging back through the broker's history."""
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest
    after = pd.Timestamp(LIVE_FROM, tz="UTC") - pd.Timedelta(days=1)
    until, seen, out = None, set(), []
    while True:
        batch = tc.get_orders(GetOrdersRequest(status=QueryOrderStatus.CLOSED, after=after.to_pydatetime(),
                                               until=until, limit=500, direction="desc"))
        new = [o for o in batch if o.id not in seen]
        if not new:
            break
        for o in new:
            seen.add(o.id)
            if o.filled_at is not None and float(o.filled_qty or 0) > 0:
                out.append(o)
        until = min(o.submitted_at for o in new)
        if len(batch) < 500:
            break
    return out


def old_picks(d, px, dv_med, sig, hist_ok) -> list:
    """The pre-25-August rule: the top tenth of the 500 most traded, no cluster cap."""
    elig = (hist_ok.loc[d] & (px.loc[d] >= MIN_PRICE) & (dv_med.loc[d] >= MIN_DOLLAR_VOL)
            & sig.loc[d].notna())
    names = elig[elig].index
    if len(names) > TOP_LIQ:
        names = dv_med.loc[d, names].nlargest(TOP_LIQ).index
    if len(names) < MIN_NAMES:
        return []
    n_target = max(1, int(round(len(names) * TOP_FRAC)))
    return list(sig.loc[d, names].sort_values(ascending=False).index[:n_target])


def main() -> int:
    tc = clients()
    fills = all_fills(tc)
    acct = tc.get_account()
    equity = float(acct.equity)
    held = {p.symbol: float(p.market_value) for p in tc.get_all_positions()}
    pnl = defaultdict(float)
    for o in fills:
        v = float(o.filled_qty) * float(o.filled_avg_price)
        pnl[o.symbol] += v if str(o.side).endswith("SELL") else -v
    for s, v in held.items():
        pnl[s] += v
    by = pd.Series(pnl).sort_values()
    tie = by.sum() - (equity - START_EQUITY)
    print(f"{len(fills)} fills, {len(by)} names; names sum to {by.sum():+,.0f}, account change "
          f"{equity - START_EQUITY:+,.0f}, difference {tie:+,.0f}", flush=True)

    # The market over the same span, from the panel the replays use.
    px, _dv, dv_med = monthly_panel("none")
    px.index = pd.to_datetime(px.index).normalize()
    dv_med.index = px.index
    sig = SIGNALS["mom_12_1"](px)
    hist_ok = px.notna().rolling(MIN_HISTORY, min_periods=MIN_HISTORY).count() >= MIN_HISTORY
    logret = np.log(px).diff()
    start = pd.Timestamp(LIVE_FROM)
    days = px.index[px.index >= start]
    prev = px.index[px.index.get_loc(start) - 1]
    # The account is valued now, so the market is too: SPY from the broker's
    # daily bars, today's bar being the price 25 minutes ago, against the close
    # before the first buy. The panel on disk ends at its last download.
    from alpaca_daily_report import benchmark
    sp = benchmark()
    sp.index = pd.to_datetime(sp.index)
    spy = float(sp.iloc[-1] / sp.loc[prev] - 1)
    asof = sp.index[-1]
    market_dollars = START_EQUITY * spy
    gap = (equity - START_EQUITY) - market_dollars
    print(f"account {equity - START_EQUITY:+,.0f}, SPY on the same money {market_dollars:+,.0f}, gap {gap:+,.0f}")

    # First week, old rules against new rules against live.
    fund_free = set(monthly_panel(UNIVERSE_EXCLUDE)[0].columns)
    first_buys = {o.symbol for o in fills if str(o.side).endswith("BUY")
                  and o.filled_at.astimezone(NY).date() == start.date()}
    old = old_picks(prev, px, dv_med, sig, hist_ok)
    fund_free_cols = [c for c in px.columns if c in fund_free]
    new = picks(prev, px[fund_free_cols], dv_med[fund_free_cols], sig[fund_free_cols],
                hist_ok[fund_free_cols], logret[fund_free_cols])
    match = len(set(old) & first_buys)
    print(f"18 August: live bought {len(first_buys)}, old rule picks {len(old)} ({match} the same), "
          f"new rule picks {len(new)} ({len(set(new) & first_buys)} the same as live)", flush=True)

    week2 = next(d for d in days if d.to_period("W") != start.to_period("W"))
    wdays = days[days < week2]
    end = wdays[-1]
    trade = {start}
    r_old = replay(px, wdays, trade, lambda d: old)
    r_new = replay(px, wdays, trade, lambda d: new)
    live = live_curve(tc, px).reindex(days).ffill()
    w_live = float(live.loc[end] / START_EQUITY - 1)
    w_old = float(r_old.iloc[-1] / START_EQUITY - 1)
    w_new = float(r_new.iloc[-1] / START_EQUITY - 1)
    w_spy = float(px.loc[end, "SPY"] / px.loc[prev, "SPY"] - 1)
    rules, timing = w_new - w_old, w_old - w_live
    print(f"first week to {end:%d %b}: new rules {w_new:+.2%}, old rules {w_old:+.2%}, live {w_live:+.2%}, "
          f"SPY {w_spy:+.2%}; older rules cost {rules:+.2%}, buying during 18 August cost {timing:+.2%}")

    stamp = datetime.now()
    day = OUT / f"{stamp:%Y-%m-%d}"
    day.mkdir(parents=True, exist_ok=True)
    md = mm.unclobbered(day / f"gap-attribution-{stamp:%Y%m%d-%H%M%S}.md")
    pts = lambda v: f"{v / START_EQUITY * 100:+.2f}"
    worst, best = by.head(10), by.tail(10)[::-1]
    losers = by[by < 0]
    k = int(np.searchsorted(-losers.cumsum().values, -gap)) + 1 if gap < 0 else 0
    L = [f"# Where the gap came from, {stamp:%d %B %Y %H:%M}", "",
         f"From {start:%d %B} to {asof:%d %B %Y} the paper account changed by {equity - START_EQUITY:+,.0f} "
         f"dollars, and the same {START_EQUITY:,.0f} dollars in SPY would have changed by "
         f"{market_dollars:+,.0f}, a gap of {gap:+,.0f} dollars or {pts(gap)} points. "
         f"{len(fills)} filled orders over {len(by)} names were read from the broker; the names' dollars sum "
         f"to the account's change to within {abs(tie):,.0f} dollars.", "",
         f"{len(losers)} names lost money and {int((by > 0).sum())} made money. "
         + (f"The {k} worst names alone lost more than the whole gap." if 0 < k <= len(losers) else ""), "",
         "## Ten worst names", "", "| name | dollars | points of the account | still held |",
         "| --- | ---: | ---: | --- |"]
    L += [f"| {s} | {v:+,.0f} | {pts(v)} | {'yes' if s in held else 'no'} |" for s, v in worst.items()]
    L += ["", "## Ten best names", "", "| name | dollars | points of the account | still held |",
          "| --- | ---: | ---: | --- |"]
    L += [f"| {s} | {v:+,.0f} | {pts(v)} | {'yes' if s in held else 'no'} |" for s, v in best.items()]
    L += ["", "## First week", "",
          f"The book bought {len(first_buys)} names on 18 August. Rebuilt from the 17 August close, the rule "
          f"of that week (top tenth of the 500 most traded, funds included, no cluster cap) picks {len(old)} "
          f"names, {match} of them the ones bought; today's rule picks {len(new)}, "
          f"{len(set(new) & first_buys)} of them the ones bought.", "",
          "| version, 18 to " + f"{end:%d} August | change |", "| --- | ---: |",
          f"| Today's rules, bought at the 18 August close | {w_new:+.2%} |",
          f"| That week's rules, bought at the 18 August close | {w_old:+.2%} |",
          f"| The live account | {w_live:+.2%} |", f"| SPY | {w_spy:+.2%} |", "",
          f"The older rules cost {rules:+.2%} of the account that week, and buying during 18 August rather than "
          f"at its close, with real fills, cost {timing:+.2%}. Both replays trade without cost.", "",
          "Run with `03-inputs/gap_attribution.py`.", ""]
    md.write_text("\n".join(L) + "\n", encoding="utf-8")
    by.to_csv(md.with_suffix(".by-name.csv"), header=["dollars"])
    print(f"record: {md.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
