"""Do a per-name stop or a market switch raise the weekly stock book's returns?

    .venv/bin/python 03-inputs/risk_rules_test.py stop
    .venv/bin/python 03-inputs/risk_rules_test.py market

Asked by the operator on 21 October 2026, "do everything", after the replay
showed the book's falls past 20 per cent, the latest from July 2026 at -37.

The replay is trim_winners_test.replay extended to act on every session, on the
book as it trades from 21 October: 50 names by 12-1 momentum under the cluster
cap, trimming on, 98 per cent in stocks, 8 basis points on every dollar traded.

stop. Han, Zhou and Zhu (2014 working paper, "Taming Momentum Crashes: A Simple
Stop-Loss Strategy") sold a momentum stock once it fell a fixed amount and held
the money in cash until the next rebalance. Here a held name is sold at the
close of the first session on which it closes at or below its average purchase
price less the stop. It may be bought again at the next weekly rebalance if it
is still picked.

    A  no stop, the live book.
    B  10 per cent stop.
    C  20 per cent stop.

market. On each rebalance day, when SPY's close is below its average close over
the previous 200 sessions, the book sells everything and holds cash until a
rebalance day finds SPY back above it.

    A  no switch, the live book.
    B  200-day switch.

Pre-registered on 21 October 2026, before the first run. A version is adopted
only if it has a higher Sharpe ratio AND higher growth a year than A, AND beats
A in at least half the calendar years; among several that pass, the highest
Sharpe ratio wins.

Cash earns nothing, which counts against every rule that holds cash. The panel
holds only stocks still listed, which flatters every version alike.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import model_metrics as mm                                       # noqa: E402
from alpaca_trade import CASH_FLOOR, REBALANCE_BAND, UNIVERSE_EXCLUDE  # noqa: E402
from book_choice_test import make_choose                         # noqa: E402
from drawdown_ramp_test import scale_of, stats                   # noqa: E402
from equity_momentum_monthly import MIN_HISTORY, SIGNALS, monthly_panel  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "04-outputs" / "AA-evals"
SHARE = 1 - CASH_FLOOR
COST = 0.0008
RAMP_PER = 10.0


def replay(px, days, rebal, choose, stop=None, risk_off=None):
    cash, shares, basis, out = 1.0, {}, {}, []
    cost_paid, stops, off_weeks = 0.0, 0, 0
    for d in days:
        p = px.loc[d]
        traded = 0.0
        if stop is not None:
            for s in list(shares):
                if p[s] == p[s] and p[s] <= basis[s] * (1 - stop):
                    v = shares.pop(s) * p[s]
                    basis.pop(s)
                    cash += v
                    traded += v
                    stops += 1
        if d in rebal:
            i = days.get_loc(d)
            top = choose(days[i - 1]) if i else []
            if risk_off is not None and risk_off(d):
                top, off_weeks = [], off_weeks + 1
                for s in list(shares):
                    v = shares.pop(s) * (p[s] if p[s] == p[s] else 0.0)
                    basis.pop(s)
                    cash += v
                    traded += v
            if top:
                value = cash + sum(q * p[s] for s, q in shares.items() if p[s] == p[s])
                target = value * SHARE / len(top)
                dd5 = value / out[-5] - 1 if len(out) >= 5 else 0.0
                k = scale_of(dd5, RAMP_PER)
                for s in [s for s in shares if s not in top]:
                    v = shares.pop(s) * (p[s] if p[s] == p[s] else 0.0)
                    basis.pop(s)
                    cash += v
                    traded += v
                for s in list(shares):
                    held = shares[s] * p[s]
                    if p[s] == p[s] and held > target * (1 + REBALANCE_BAND):
                        sell = held - target
                        shares[s] -= sell / p[s]
                        cash += sell
                        traded += sell
                for s in top:
                    if p[s] != p[s]:
                        continue
                    held = shares.get(s, 0.0) * p[s]
                    want = target * k if s not in shares else target
                    if s not in shares or held < target * (1 - REBALANCE_BAND):
                        buy = min(want - held, max(0.0, cash - value * (1 - SHARE)))
                        if buy > 0:
                            q0 = shares.get(s, 0.0)
                            q1 = buy / p[s]
                            basis[s] = (basis.get(s, 0.0) * q0 + buy) / (q0 + q1)
                            shares[s] = q0 + q1
                            cash -= buy
                            traded += buy
        if traded:
            value = cash + sum(q * p[s] for s, q in shares.items() if p[s] == p[s])
            cash -= traded * COST
            cost_paid += traded * COST / max(value, 1e-9)
        out.append(cash + sum(q * p[s] for s, q in shares.items() if p[s] == p[s]))
    return pd.Series(out, index=days), dict(cost=cost_paid, stops=stops, off_weeks=off_weeks)


def main() -> int:
    test = sys.argv[1] if len(sys.argv) > 1 else "stop"
    px, _dv, dv_med = monthly_panel(UNIVERSE_EXCLUDE)
    px.index = pd.to_datetime(px.index).normalize()
    dv_med.index = px.index
    choose = make_choose(px, dv_med, SIGNALS["mom_12_1"](px), 0.10)
    days = px.index[MIN_HISTORY + 1:]
    week = days.to_period("W")
    rebal = set(days[np.r_[True, week[1:] != week[:-1]]])
    first = next(d for d in sorted(rebal) if choose(days[days.get_loc(d) - 1]))
    days = days[days >= first]

    if test == "stop":
        arms = {"A no stop (live)": {}, "B 10% stop": {"stop": 0.10}, "C 20% stop": {"stop": 0.20}}
    else:
        spy = pd.read_parquet(REPO / "03-inputs" / "alpaca-data" / "daily" / "SPY.parquet")
        spy = spy.set_index(pd.to_datetime(spy["datetime"]).dt.tz_localize(None).dt.normalize())["close"]
        # The switch reads the previous session's close against its 200-session mean.
        below = (spy < spy.rolling(200).mean()).shift(1).reindex(days).fillna(False).astype(bool)
        arms = {"A no switch (live)": {}, "B 200-day switch": {"risk_off": lambda d: bool(below.loc[d])}}
    base = next(iter(arms))

    out, curves = {}, {}
    for name, kw in arms.items():
        eq, info = replay(px, days, rebal, choose, **kw)
        st = stats(eq)
        st.update(info)
        y = eq.resample("YE").last()
        st["years"] = y.pct_change().fillna(y.iloc[0] / eq.iloc[0] - 1)
        out[name], curves[name] = st, eq
        print(f"{name:20s} CAGR {st['cagr']:.1%}  vol {st['vol']:.1%}  Sharpe {st['sharpe']:.3f}  "
              f"max drawdown {st['max_dd']:.1%}  grew {st['final']:.2f}x  cost {st['cost']:.1%}  "
              f"stops {st['stops']}  weeks in cash {st['off_weeks']}", flush=True)
    a = out[base]
    passed = []
    for n, st in out.items():
        if n == base:
            continue
        st["beat"] = int((st["years"] > a["years"]).sum())
        if st["sharpe"] > a["sharpe"] and st["cagr"] > a["cagr"] and st["beat"] >= len(a["years"]) / 2:
            passed.append(n)
    verdict = f"ADOPT {max(passed, key=lambda n: out[n]['sharpe'])}" if passed else f"KEEP {base}"
    print(f"\nVERDICT: {verdict}")

    stamp = datetime.now()
    day = OUT / f"{stamp:%Y-%m-%d}"
    day.mkdir(parents=True, exist_ok=True)
    md = mm.unclobbered(day / f"risk-rules-{test}-{stamp:%Y%m%d-%H%M%S}.md")
    title = "Stop on each holding" if test == "stop" else "Market switch"
    L = [f"# {title} for the weekly stock book, {stamp:%d %B %Y %H:%M}", "",
         f"A daily replay of the live book, trimming on, {SHARE:.0%} in stocks, from {days[0]:%d %B %Y} "
         f"to {days[-1]:%d %B %Y}.", "",
         f"Verdict, {verdict}. Another version was to be adopted only with a higher Sharpe ratio and higher "
         f"growth a year than the live book, and beating it in at least half the calendar years.", "",
         "| version | growth a year | volatility | Sharpe | maximum drawdown | grew | cost over the run "
         "| stops | weeks in cash | years ahead of live |",
         "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for n, st in out.items():
        ahead = "" if n == base else f"{st['beat']} of {len(a['years'])}"
        L.append(f"| {n} | {st['cagr']:.1%} | {st['vol']:.1%} | {st['sharpe']:.3f} | {st['max_dd']:.1%} | "
                 f"{st['final']:.2f}x | {st['cost']:.1%} | {st['stops']} | {st['off_weeks']} | {ahead} |")
    names = list(out)
    L += ["", "| year | " + " | ".join(names) + " |", "| --- |" + " ---: |" * len(names)]
    for yr in a["years"].index:
        L.append(f"| {yr:%Y} | " + " | ".join(f"{out[n]['years'][yr]:.1%}" for n in names) + " |")
    L += ["", "Cash earns nothing. The panel holds only stocks still listed, which flatters every version "
          "alike.", "", "Run with `03-inputs/risk_rules_test.py`, whose rules were fixed before the first run.", ""]
    md.write_text("\n".join(L) + "\n", encoding="utf-8")
    pd.DataFrame(curves).to_csv(md.with_suffix(".curves.csv"))
    print(f"record: {md.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
