"""Does the 10 per cent cash floor cost the momentum book its returns?

    .venv/bin/python 03-inputs/cash_floor_test.py

Asked by the operator on 20 October 2026, "please apply ... the 10 per cent
cash floor". The charter keeps at least 10 per cent of the account in cash, so
the live book holds 90 per cent in stocks. In a strategy that grew 27.1 per
cent a year in the replay, that cash was estimated to cost about 2.5 points a
year. The book may not borrow, so the most it can hold is all of it, and a
small buffer is kept because orders fill at prices a little away from the
quote and the never-margin guard needs room.

The replay is trim_winners_test.replay with trimming on, the live rule since
20 October, with the stock share fixed for the whole run.

Pre-registered on 20 October 2026, before the first run.

    A  90 per cent in stocks, the charter's floor.
    B  95 per cent.
    C  98 per cent.

    The most invested of B and C is adopted when, against A, its growth a year
    is higher, its Sharpe ratio is no lower, and its maximum drawdown is no
    more than 3 points deeper. More stock without borrowing must deepen the
    worst fall a little, so a rule demanding a smaller one could not pass by
    construction; 3 points is the allowance. If neither passes, the floor
    stays at 10 per cent.

Cash earns nothing in the replay, which counts against A. The panel holds only
stocks still listed, which flatters all three alike.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import model_metrics as mm                                       # noqa: E402
from alpaca_trade import UNIVERSE_EXCLUDE                        # noqa: E402
from drawdown_ramp_test import stats                             # noqa: E402
from equity_momentum_monthly import MIN_HISTORY, SIGNALS, monthly_panel  # noqa: E402
from live_vs_replay import picks                                 # noqa: E402
from trim_winners_test import replay                             # noqa: E402

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "04-outputs" / "AA-evals"
ARMS = {"A 90% in stocks": 0.90, "B 95% in stocks": 0.95, "C 98% in stocks": 0.98}
DD_ALLOW = 0.03


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
    for name, share in ARMS.items():
        eq, info = replay(px, days, rebal, choose, True, invest=lambda d, s=share: s)
        st = stats(eq)
        st.update(info)
        y = eq.resample("YE").last()
        st["years"] = y.pct_change().fillna(y.iloc[0] / eq.iloc[0] - 1)
        out[name], curves[name] = st, eq
        print(f"{name:16s} CAGR {st['cagr']:.1%}  vol {st['vol']:.1%}  Sharpe {st['sharpe']:.3f}  "
              f"max drawdown {st['max_dd']:.1%}  grew {st['final']:.2f}x  cost {st['cost']:.1%}",
              flush=True)
    a = out["A 90% in stocks"]
    passed = [n for n in ("C 98% in stocks", "B 95% in stocks")
              if out[n]["cagr"] > a["cagr"] and out[n]["sharpe"] >= a["sharpe"]
              and out[n]["max_dd"] >= a["max_dd"] - DD_ALLOW]
    verdict = f"ADOPT {passed[0]}" if passed else "KEEP A, the 10 per cent floor"
    print(f"\nVERDICT: {verdict}")

    stamp = datetime.now()
    day = OUT / f"{stamp:%Y-%m-%d}"
    day.mkdir(parents=True, exist_ok=True)
    md = mm.unclobbered(day / f"cash-floor-test-{stamp:%Y%m%d-%H%M%S}.md")
    L = [f"# Cash floor of the momentum book, {stamp:%d %B %Y %H:%M}", "",
         f"A daily replay of the live book, trimming on, from {days[0]:%d %B %Y} to {days[-1]:%d %B %Y}, "
         f"with 90, 95 and 98 per cent of the account in stocks and the rest in cash earning nothing.", "",
         f"Verdict, {verdict}. The most invested version was to be adopted when its growth a year was "
         f"higher, its Sharpe ratio no lower, and its maximum drawdown no more than 3 points deeper than "
         f"the 90 per cent book.", "",
         "| version | growth a year | volatility | Sharpe | maximum drawdown | grew | cost over the run |",
         "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for n, st in out.items():
        L.append(f"| {n} | {st['cagr']:.1%} | {st['vol']:.1%} | {st['sharpe']:.3f} | {st['max_dd']:.1%} | "
                 f"{st['final']:.2f}x | {st['cost']:.1%} |")
    names = list(out)
    L += ["", "| year | " + " | ".join(names) + " |", "| --- |" + " ---: |" * len(names)]
    for yr in a["years"].index:
        L.append(f"| {yr:%Y} | " + " | ".join(f"{out[n]['years'][yr]:.1%}" for n in names) + " |")
    L += ["", "The panel holds only stocks still listed, which flatters all three versions alike.", "",
          "Run with `03-inputs/cash_floor_test.py`, whose rule was fixed before the first run.", ""]
    md.write_text("\n".join(L) + "\n", encoding="utf-8")
    pd.DataFrame(curves).to_csv(md.with_suffix(".curves.csv"))
    print(f"record: {md.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
