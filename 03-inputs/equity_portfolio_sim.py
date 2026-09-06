"""Track A: implementable portfolio simulation of the surviving momentum edge.

The factor test proved the spread exists; this answers whether a real book can
hold it. Pre-registered design: 12-1 momentum, top decile of the top-500
dollar-volume universe (the tier where the edge was largest and delisting bias
smallest), equal weight, rebalanced at month-end closes, long-only, no margin.

Costs are charged on MEASURED turnover, not assumed: each month the fraction of
the book replaced pays the round trip (5bp base, 10bp stress), so a sticky
month is nearly free and a full flip pays in full. Reported against the
universe equal-weight market and SPY buy-and-hold: growth, volatility, Sharpe,
max drawdown, worst months, per-year table, turnover. The mandate's 10% cash
floor scales returns by 0.9; shown as a separate line, not silently applied.

Survivorship note stays: live names only; the stress test bounded, not erased,
that caveat.

    .venv/bin/python inputs/equity_portfolio_sim.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from equity_momentum_monthly import (MIN_DOLLAR_VOL, MIN_HISTORY, MIN_NAMES,
                                     MIN_PRICE, SIGNALS, TOP_FRAC, monthly_panel)

TOP_LIQ = 500
COSTS_RT = (0.0005, 0.0010)
CASH_FLOOR = 0.10


def simulate(px, dv_med, month_ends):
    sig = SIGNALS["mom_12_1"](px)
    hist_ok = px.notna().rolling(MIN_HISTORY, min_periods=MIN_HISTORY).count() >= MIN_HISTORY
    prev = set()
    rows = []
    for i in range(len(month_ends) - 1):
        t0, t1 = month_ends[i], month_ends[i + 1]
        elig = (hist_ok.loc[t0] & (px.loc[t0] >= MIN_PRICE)
                & (dv_med.loc[t0] >= MIN_DOLLAR_VOL) & sig.loc[t0].notna())
        names = elig[elig].index
        if len(names) > TOP_LIQ:
            names = dv_med.loc[t0, names].nlargest(TOP_LIQ).index
        if len(names) < MIN_NAMES:
            continue
        s = sig.loc[t0, names]
        top = set(s[s.rank(pct=True) > (1 - TOP_FRAC)].index)
        fwd = px.loc[t1, names] / px.loc[t0, names] - 1.0
        turnover = 1.0 - (len(top & prev) / len(top)) if prev else 1.0
        rows.append(dict(month=t1, n_top=len(top), turnover=turnover,
                         gross=float(fwd.loc[list(top)].mean()),
                         mkt=float(fwd.mean())))
        prev = top
    return pd.DataFrame(rows).set_index("month")


def stats(r: pd.Series, label: str) -> dict:
    eq = (1 + r).cumprod()
    peak = eq.cummax()
    dd = (eq / peak - 1).min()
    yrs = len(r) / 12
    cagr = float(eq.iloc[-1] ** (1 / yrs) - 1)
    vol = float(r.std() * np.sqrt(12))
    return dict(strategy=label, cagr=f"{cagr:.1%}", vol=f"{vol:.1%}",
                sharpe=round(float(r.mean() / r.std() * np.sqrt(12)), 2),
                max_dd=f"{dd:.1%}", worst_mo=f"{r.min():.1%}",
                best_mo=f"{r.max():.1%}", final=f"{float(eq.iloc[-1]):.2f}x")


def main():
    px, dv, dv_med = monthly_panel()
    month_ends = px.groupby(px.index.to_period("M")).apply(lambda g: g.index.max()).to_list()
    sim = simulate(px, dv_med, month_ends)
    spy = (px.loc[sim.index, "SPY"].pct_change()
           .fillna(px.loc[sim.index[0], "SPY"] / px.loc[month_ends[0], "SPY"] - 1))

    print(f"\nmonths={len(sim)}  names/month={sim['n_top'].mean():.0f}  "
          f"mean turnover={sim['turnover'].mean():.0%}/month "
          f"(median {sim['turnover'].median():.0%})")

    rows = []
    for rt in COSTS_RT:
        net = sim["gross"] - sim["turnover"] * rt
        rows.append(stats(net, f"momentum net @{rt * 1e4:.0f}bp RT"))
        if rt == COSTS_RT[0]:
            net_floor = net * (1 - CASH_FLOOR)
            rows.append(stats(net_floor, "  same, 10% cash floor"))
            base = net
    rows.append(stats(sim["mkt"] - sim["turnover"].mean() * COSTS_RT[0] * 0,
                      "universe market (no cost)"))
    rows.append(stats(spy, "SPY buy-and-hold"))
    pd.set_option("display.width", 200)
    print("\n" + pd.DataFrame(rows).to_string(index=False))

    yr = pd.DataFrame({"momentum": base, "market": sim["mkt"], "spy": spy})
    yearly = ((1 + yr).groupby(yr.index.year).prod() - 1)
    print("\nPER YEAR (net @5bp)")
    print((yearly * 100).round(1).to_string())

    worst = base.nsmallest(5)
    print("\nWORST 5 MONTHS (net @5bp): "
          + ", ".join(f"{d:%Y-%m} {v:.1%}" for d, v in worst.items()))
    print(f"\ncapacity note: {TOP_LIQ}-name universe with median 63d dollar volume >= "
          f"${MIN_DOLLAR_VOL / 1e6:.0f}M per name; ~50 positions of 2% each. At any book "
          f"size this side of tens of millions, position sizes are far below 1% of daily "
          f"volume; capacity is not the constraint.")


if __name__ == "__main__":
    main()
