"""Should the weekly rebalance trim winners back to their target? A daily replay.

    .venv/bin/python 03-inputs/trim_winners_test.py

Asked by the operator on 19 October 2026, answered 20 October. The live book
never trims. alpaca_trade.build_orders computes a sale for every held name more
than 25 per cent above its 1.8 per cent target, and submit() drops it ("left to
drift"), so a winner can grow without limit while it stays in the top tenth.

The replay follows the live book as yesterday's live_vs_replay.py does, from
2017 to today on the daily closes. On the first session of each week, names are
picked with live_vs_replay.picks (12-1 momentum on the previous close, funds
excluded, the 500 most traded eligible names, the top tenth, admitted under the
20 per cent cluster cap), held at 90 per cent of the account divided by their
count, with 10 per cent cash. Names that leave are sold, new names are bought
at the target times the drawdown ramp now live (10 per cent less per 1 per cent
of five-session loss below -5 per cent), and a held name below 75 per cent of
its target is topped up. Every dollar traded pays 8 basis points, the measured
7.9 a fill off the open. Buys never spend the 10 per cent cash floor.

Pre-registered on 20 October 2026, before the first run.

    A  no trim, the book as it trades.
    B  trim, a held name more than 25 per cent above its target is sold back
       to the target, the sale build_orders already computes.

    B is adopted only if, over the whole history, it has BOTH a higher Sharpe
    ratio and a smaller maximum drawdown than A, after its extra cost.
    Otherwise the live rule is left as it is.

The panel holds only stocks still listed, which flatters both alike.
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
from drawdown_ramp_test import scale_of, stats                   # noqa: E402
from equity_momentum_monthly import MIN_HISTORY, SIGNALS, monthly_panel  # noqa: E402
from live_vs_replay import picks                                 # noqa: E402

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "04-outputs" / "AA-evals"
COST = 0.0008
RAMP_PER = 10.0
ARMS = {"A no trim": False, "B trim": True}


def replay(px, days, rebal, choose, trim: bool, invest=None):
    """invest(d) is the share of the account held in stocks on rebalance day d;
    None holds the live 90 per cent."""
    cash, shares, out = 1.0, {}, []
    weeks, trimmed, cost_paid, top_w = 0, 0, 0.0, []
    for d in days:
        if d in rebal:
            prev = days[days.get_loc(d) - 1] if days.get_loc(d) else None
            top = choose(prev) if prev is not None else []
            if top:
                weeks += 1
                p = px.loc[d]
                value = cash + sum(q * p[s] for s, q in shares.items() if p[s] == p[s])
                share = (1 - CASH_FLOOR) if invest is None else invest(d)
                target = value * share / len(top)
                dd5 = value / out[-5] - 1 if len(out) >= 5 else 0.0
                k = scale_of(dd5, RAMP_PER)
                traded = 0.0
                for s in [s for s in shares if s not in top]:
                    px_s = p[s] if p[s] == p[s] else 0.0
                    traded += shares[s] * px_s
                    cash += shares.pop(s) * px_s
                if trim:
                    for s in list(shares):
                        held = shares[s] * p[s]
                        if p[s] == p[s] and held > target * (1 + REBALANCE_BAND):
                            sell = held - target
                            shares[s] -= sell / p[s]
                            cash += sell
                            traded += sell
                            trimmed += 1
                for s in top:
                    if p[s] != p[s]:
                        continue
                    held = shares.get(s, 0.0) * p[s]
                    want = target * k if s not in shares else target
                    if s not in shares or held < target * (1 - REBALANCE_BAND):
                        buy = min(want - held, max(0.0, cash - value * (1 - share)))
                        if buy > 0:
                            shares[s] = shares.get(s, 0.0) + buy / p[s]
                            cash -= buy
                            traded += buy
                cash -= traded * COST
                cost_paid += traded * COST / value
        p = px.loc[d]
        vals = {s: q * p[s] for s, q in shares.items() if p[s] == p[s]}
        val = cash + sum(vals.values())
        out.append(val)
        if vals:
            top_w.append(max(vals.values()) / val)
    eq = pd.Series(out, index=days)
    return eq, dict(weeks=weeks, trims=trimmed, cost=cost_paid,
                    max_w=float(max(top_w)) if top_w else 0.0,
                    end_w=float(top_w[-1]) if top_w else 0.0)


def main() -> int:
    px, _dv, dv_med = monthly_panel(UNIVERSE_EXCLUDE)
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

    days = px.index[MIN_HISTORY + 1:]
    week = days.to_period("W")
    rebal = set(days[np.r_[True, week[1:] != week[:-1]]])
    first = next(d for d in sorted(rebal) if choose(days[days.get_loc(d) - 1]))
    days = days[days >= first]
    out, curves = {}, {}
    for name, trim in ARMS.items():
        eq, info = replay(px, days, rebal, choose, trim)
        st = stats(eq)
        st.update(info)
        y = eq.resample("YE").last()
        st["years"] = y.pct_change().fillna(y.iloc[0] / eq.iloc[0] - 1)
        out[name], curves[name] = st, eq
        print(f"{name:10s} CAGR {st['cagr']:.1%}  vol {st['vol']:.1%}  Sharpe {st['sharpe']:.3f}  "
              f"max drawdown {st['max_dd']:.1%}  grew {st['final']:.2f}x  cost {st['cost']:.1%}  "
              f"largest name ever {st['max_w']:.1%}, today {st['end_w']:.1%}  trims {st['trims']}",
              flush=True)
    a, b = out["A no trim"], out["B trim"]
    adopt = b["sharpe"] > a["sharpe"] and b["max_dd"] > a["max_dd"]
    verdict = "ADOPT B trim" if adopt else "KEEP A, the live rule"
    beat = int((b["years"] > a["years"]).sum())
    print(f"\nB beat A in {beat} of {len(a['years'])} calendar years\nVERDICT: {verdict}")

    stamp = datetime.now()
    day = OUT / f"{stamp:%Y-%m-%d}"
    day.mkdir(parents=True, exist_ok=True)
    md = mm.unclobbered(day / f"trim-winners-test-{stamp:%Y%m%d-%H%M%S}.md")
    L = [f"# Trimming winners in the momentum basket, {stamp:%d %B %Y %H:%M}", "",
         f"A daily replay of the live book from {days[0]:%d %B %Y} to {days[-1]:%d %B %Y}, weekly "
         f"rebalances on the first session of each week, names picked as the live code picks them "
         f"under the 20 per cent cluster cap, 90 per cent invested, the drawdown ramp on new names, "
         f"8 basis points on every dollar traded. A never sells a winner down; B sells any name more "
         f"than 25 per cent above its target back to the target.", "",
         f"Verdict, {verdict}. B was to be adopted only with both a higher Sharpe ratio and a smaller "
         f"maximum drawdown than A, after its extra cost.", "",
         "| version | growth a year | volatility | Sharpe | maximum drawdown | grew | cost over the run "
         "| largest single name, ever | largest single name, last day | trims |",
         "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for n, st in out.items():
        L.append(f"| {n} | {st['cagr']:.1%} | {st['vol']:.1%} | {st['sharpe']:.3f} | {st['max_dd']:.1%} | "
                 f"{st['final']:.2f}x | {st['cost']:.1%} | {st['max_w']:.1%} | {st['end_w']:.1%} | "
                 f"{st['trims']} |")
    L += ["", "| year | A no trim | B trim |", "| --- | ---: | ---: |"]
    for yr in a["years"].index:
        L.append(f"| {yr:%Y} | {a['years'][yr]:.1%} | {b['years'][yr]:.1%} |")
    L += ["", f"B beat A in {beat} of {len(a['years'])} calendar years.", "",
          "The panel holds only stocks still listed, which flatters both versions alike.", "",
          "Run with `03-inputs/trim_winners_test.py`, whose rule was fixed before the first run.", ""]
    md.write_text("\n".join(L) + "\n", encoding="utf-8")
    pd.DataFrame(curves).to_csv(md.with_suffix(".curves.csv"))
    print(f"record: {md.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
