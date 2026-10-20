"""Does the charter's drawdown ramp help the momentum basket? A daily replay.

    .venv/bin/python 03-inputs/drawdown_ramp_test.py

Operator's choice of 19 October 2026, "Test it first". The charter's Principle 4
says that when the rolling 5-day book return is below -5 per cent, the default
size of a new position is cut 1:1 with each further 1 per cent of drawdown, and
recovery reverses it. The live book was at -6.87 per cent that day and the code
did not apply the rule, because it was written for single discretionary trades
and nobody had said what it means for a 50-name basket.

The replay follows the live book as closely as the daily data allow. Each
Monday's close (the first session of the week), the top decile by 12-1 momentum
of the 500 most traded eligible names is held equal weight at 90 per cent of
the account, the rest cash at no interest. Kept names are reset to their
target, new names come in at the target times the ramp's scale, so the ramp
touches only new positions, and the next week's rebalance tops them up once
the scale is back to one. Every change in weight pays 8 basis points, the
measured 7.9 a fill off the open.

Pre-registered on 19 October 2026, before the first run.

    A  no ramp, the book as it trades.
    B  each 1 per cent of 5-day drawdown below -5 per cent cuts new positions
       by 10 per cent of their size, to a floor of zero.
    C  the literal reading, each 1 per cent cuts new positions by 1 per cent.

    A ramp is adopted only if, over the whole history, it has BOTH a higher
    Sharpe ratio and a smaller maximum drawdown than A. Otherwise the ramp is
    switched off for the basket and journaled as an exemption, like the
    3-a-week cap and the -7 per cent stop.

The panel holds only stocks still listed, which flatters all three alike.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import model_metrics as mm                                      # noqa: E402
from equity_momentum_monthly import (MIN_DOLLAR_VOL, MIN_HISTORY,   # noqa: E402
                                     MIN_NAMES, MIN_PRICE, SIGNALS, TOP_FRAC,
                                     monthly_panel)

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "04-outputs" / "AA-evals"
TOP_LIQ = 500
INVESTED = 0.90
COST = 0.0008
TRIGGER = -0.05
RAMPS = {"A no ramp": 0.0, "B 10% per 1%": 10.0, "C 1% per 1%": 1.0}


def scale_of(dd5: float, per: float) -> float:
    if per == 0 or dd5 >= TRIGGER:
        return 1.0
    return max(0.0, 1.0 - per * (TRIGGER - dd5))


def replay(px, dv_med, per: float):
    sig = SIGNALS["mom_12_1"](px)
    hist_ok = px.notna().rolling(MIN_HISTORY, min_periods=MIN_HISTORY).count() >= MIN_HISTORY
    ret = px.pct_change(fill_method=None)
    days = px.index
    week = days.to_period("W")
    rebal = set(days[np.r_[True, week[1:] != week[:-1]]])
    w = pd.Series(dtype=float)
    equity, curve, scales, cost_paid = 1.0, [], [], 0.0
    started = False
    for i, d in enumerate(days):
        if i and len(w):
            r = ret.loc[d, w.index].fillna(0.0)
            growth = float((w * (1 + r)).sum() + (1 - w.sum()))
            w = w * (1 + r) / growth
            equity *= growth
        if d in rebal and i >= MIN_HISTORY:
            elig = (hist_ok.loc[d] & (px.loc[d] >= MIN_PRICE) & (dv_med.loc[d] >= MIN_DOLLAR_VOL)
                    & sig.loc[d].notna())
            names = elig[elig].index
            if len(names) > TOP_LIQ:
                names = dv_med.loc[d, names].nlargest(TOP_LIQ).index
            if len(names) >= MIN_NAMES:
                started = True
                s = sig.loc[d, names].sort_values(ascending=False)
                top = list(s.index[:max(1, int(round(len(names) * TOP_FRAC)))])
                target = INVESTED / len(top)
                # Today's close against the close five sessions earlier.
                dd5 = equity / curve[-5] - 1 if len(curve) >= 5 else 0.0
                k = scale_of(dd5, per)
                new = pd.Series({x: target if x in w.index else target * k for x in top})
                both = new.index.union(w.index)
                turn = float((new.reindex(both, fill_value=0) - w.reindex(both, fill_value=0)).abs().sum())
                equity *= 1 - turn * COST
                cost_paid += turn * COST
                w = new
                scales.append((d, dd5, k))
        if started:
            curve.append(equity)
    idx = [d for d in days if d >= scales[0][0]] if scales else []
    eq = pd.Series(curve, index=idx[:len(curve)])
    return eq, pd.DataFrame(scales, columns=["date", "dd5", "scale"]).set_index("date"), cost_paid


def stats(eq: pd.Series) -> dict:
    r = eq.pct_change().dropna()
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    dd = float((eq / eq.cummax() - 1).min())
    return dict(cagr=float(eq.iloc[-1] ** (1 / yrs) - 1), vol=float(r.std() * np.sqrt(252)),
                sharpe=float(r.mean() / r.std() * np.sqrt(252)), max_dd=dd, final=float(eq.iloc[-1]))


def main() -> int:
    px, dv, dv_med = monthly_panel("none")
    out, curves = {}, {}
    for name, per in RAMPS.items():
        eq, sc, cost = replay(px, dv_med, per)
        st = stats(eq)
        st.update(weeks=len(sc), ramp_weeks=int((sc["scale"] < 1).sum()), cost=cost)
        out[name], curves[name] = st, eq
        print(f"{name:14s} CAGR {st['cagr']:.1%}  vol {st['vol']:.1%}  Sharpe {st['sharpe']:.2f}  "
              f"max drawdown {st['max_dd']:.1%}  grew {st['final']:.2f}x  weeks the ramp bit "
              f"{st['ramp_weeks']} of {st['weeks']}", flush=True)
    a = out["A no ramp"]
    adopt = [n for n in ("B 10% per 1%", "C 1% per 1%")
             if out[n]["sharpe"] > a["sharpe"] and out[n]["max_dd"] > a["max_dd"]]
    verdict = (f"ADOPT {adopt[0]}" if adopt else "SWITCH OFF for the basket")
    print(f"\nVERDICT: {verdict}")

    stamp = datetime.now()
    day = OUT / f"{stamp:%Y-%m-%d}"
    day.mkdir(parents=True, exist_ok=True)
    md = mm.unclobbered(day / f"drawdown-ramp-test-{stamp:%Y%m%d-%H%M%S}.md")
    eq0 = curves["A no ramp"]
    L = [f"# Drawdown ramp on the momentum basket, {stamp:%d %B %Y %H:%M}", "",
         f"A daily replay of the live book from {eq0.index[0]:%d %B %Y} to {eq0.index[-1]:%d %B %Y}, weekly "
         f"rebalances on the first session of each week, top decile of the 500 most traded eligible names "
         f"by 12-1 momentum, 90 per cent invested, 8 basis points on every change in weight. The ramp cuts "
         f"only new positions, and only when the 5-day book return is below -5 per cent.", "",
         f"Verdict, {verdict}. A ramp was to be adopted only with both a higher Sharpe ratio and a smaller "
         f"maximum drawdown than the book without it.", "",
         "| version | growth a year | volatility | Sharpe | maximum drawdown | grew | weeks the ramp bit |",
         "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for n, st in out.items():
        L.append(f"| {n} | {st['cagr']:.1%} | {st['vol']:.1%} | {st['sharpe']:.2f} | {st['max_dd']:.1%} | "
                 f"{st['final']:.2f}x | {st['ramp_weeks']} of {st['weeks']} |")
    L += ["", "The panel holds only stocks still listed, which flatters all three versions alike.", "",
          "Run with `03-inputs/drawdown_ramp_test.py`, whose rule was fixed before the first run.", ""]
    md.write_text("\n".join(L) + "\n", encoding="utf-8")
    pd.DataFrame(curves).to_csv(md.with_suffix(".curves.csv"))
    print(f"record: {md.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
