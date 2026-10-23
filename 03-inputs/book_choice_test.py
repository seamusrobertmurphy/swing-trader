"""Which signal, and how many names, should the weekly stock book hold?

    .venv/bin/python 03-inputs/book_choice_test.py signal
    .venv/bin/python 03-inputs/book_choice_test.py names

Asked by the operator on 21 October 2026, "run the momentum signal and number of
names tests". Both use trim_winners_test.replay on the book as it trades from 20
October, trimming on and 98 per cent in stocks, and change one thing each.

signal. The live book ranks by 12-1 momentum, the rise from 12 months to 1 month
ago. Blitz, Huij and Martens (2011, Journal of Empirical Finance 18, 506-521)
ranked instead by residual momentum: each stock's monthly returns over 36 months
were regressed on the Fama-French factors, and the residuals over months t-12 to
t-2 were summed and divided by their standard deviation over the 36 months. The
adaptation here uses
one factor, the equal-weight average of every stock in the panel, because the
Fama-French files are not on disk, and builds the 36 monthly returns from every
21st session ending on the rebalance day, so the signal moves daily as 12-1 does.

names. The live book holds the top tenth, about 50 names. The test holds the top
twentieth (about 25) and the top fifth (about 100), with the same cluster cap.

Pre-registered on 21 October 2026, before the first run.

    signal  B residual momentum is adopted only if, over the period both can
            run, it has a higher Sharpe ratio AND higher growth a year than
            A 12-1 momentum, AND beats it in at least half the calendar years.
    names   A count other than the top tenth is adopted only if it has a
            higher Sharpe ratio AND higher growth a year than the top tenth,
            AND beats it in at least half the calendar years.

Cash earns nothing. The panel holds only stocks still listed, which flatters
every version alike.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import model_metrics as mm                                       # noqa: E402
from alpaca_trade import CASH_FLOOR, CLUSTER_CAP, TOP_LIQ, UNIVERSE_EXCLUDE  # noqa: E402
from drawdown_ramp_test import stats                             # noqa: E402
from equity_cluster_cap import CORR_WINDOW, RHO, admit           # noqa: E402
from equity_momentum_monthly import (MIN_DOLLAR_VOL, MIN_HISTORY,  # noqa: E402
                                     MIN_NAMES, MIN_PRICE, SIGNALS, monthly_panel)
from trim_winners_test import replay                             # noqa: E402

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "04-outputs" / "AA-evals"
SHARE = 1 - CASH_FLOOR
MONTH, WINDOW, SKIP = 21, 36, 1


def residual_momentum(px: pd.DataFrame) -> pd.DataFrame:
    """Residual 12-1 momentum on 36 returns spaced 21 sessions apart."""
    lp = np.log(px.to_numpy(dtype="float64"))
    n, k = lp.shape
    out = np.full((n, k), np.nan, dtype="float32")
    need = MONTH * WINDOW
    for i in range(need, n):
        idx = i - MONTH * np.arange(WINDOW, -1, -1)          # 37 points, oldest first
        r = np.diff(lp[idx], axis=0)                         # 36 x k monthly log returns
        ok = np.isfinite(r).all(axis=0)
        if ok.sum() < MIN_NAMES:
            continue
        rr = r[:, ok]
        m = rr.mean(axis=1)
        mc = m - m.mean()
        beta = (mc[:, None] * (rr - rr.mean(axis=0))).sum(axis=0) / (mc ** 2).sum()
        alpha = rr.mean(axis=0) - beta * m.mean()
        e = rr - alpha - beta * m[:, None]
        sd = e.std(axis=0, ddof=1)
        # Months t-12 to t-2: the 11 returns before the most recent one.
        s = e[WINDOW - 12:WINDOW - SKIP].sum(axis=0) / np.where(sd > 0, sd, np.nan)
        col = np.flatnonzero(ok)
        out[i, col] = s
    return pd.DataFrame(out, index=px.index, columns=px.columns)


def make_choose(px, dv_med, sig, frac, cap=CLUSTER_CAP, rho=RHO):
    hist_ok = px.notna().rolling(MIN_HISTORY, min_periods=MIN_HISTORY).count() >= MIN_HISTORY
    logret = np.log(px).diff()
    cache: dict = {}

    def choose(d):
        if d in cache:
            return cache[d]
        elig = (hist_ok.loc[d] & (px.loc[d] >= MIN_PRICE) & (dv_med.loc[d] >= MIN_DOLLAR_VOL)
                & sig.loc[d].notna())
        names = elig[elig].index
        if len(names) > TOP_LIQ:
            names = dv_med.loc[d, names].nlargest(TOP_LIQ).index
        held = []
        if len(names) >= MIN_NAMES:
            s = sig.loc[d, names].sort_values(ascending=False)
            n_target = max(1, int(round(len(names) * frac)))
            pool = s.index[:min(len(s), n_target * 6)]
            corr = logret.loc[:d, pool].tail(CORR_WINDOW).corr()
            held = admit(list(s.index), corr, n_target, cap, rho, SHARE)
        cache[d] = held
        return held
    return choose


def run(test: str) -> int:
    px, _dv, dv_med = monthly_panel(UNIVERSE_EXCLUDE)
    px.index = pd.to_datetime(px.index).normalize()
    dv_med.index = px.index
    mom = SIGNALS["mom_12_1"](px)
    if test == "signal":
        res = residual_momentum(px)
        arms = {"A 12-1 momentum": (mom, 0.10), "B residual momentum": (res, 0.10)}
        base = "A 12-1 momentum"
        # Both start where the residual signal can first pick a book.
        first_ok = res.notna().sum(axis=1)
        start = first_ok[first_ok >= MIN_NAMES].index[0]
    else:
        arms = {"top twentieth, about 25": (mom, 0.05), "top tenth, about 50 (live)": (mom, 0.10),
                "top fifth, about 100": (mom, 0.20)}
        base = "top tenth, about 50 (live)"
        start = px.index[MIN_HISTORY + 1]
    days = px.index[px.index >= start]
    week = days.to_period("W")
    rebal = set(days[np.r_[True, week[1:] != week[:-1]]])
    choosers = {n: make_choose(px, dv_med, s, f) for n, (s, f) in arms.items()}
    first = max(next(d for d in sorted(rebal) if c(days[days.get_loc(d) - 1])) for c in choosers.values())
    days = days[days >= first]

    out, curves = {}, {}
    for name, choose in choosers.items():
        eq, info = replay(px, days, rebal, choose, True, invest=lambda d: SHARE)
        st = stats(eq)
        st.update(info)
        y = eq.resample("YE").last()
        st["years"] = y.pct_change().fillna(y.iloc[0] / eq.iloc[0] - 1)
        out[name], curves[name] = st, eq
        print(f"{name:28s} CAGR {st['cagr']:.1%}  vol {st['vol']:.1%}  Sharpe {st['sharpe']:.3f}  "
              f"max drawdown {st['max_dd']:.1%}  grew {st['final']:.2f}x  cost {st['cost']:.1%}", flush=True)
    a = out[base]
    passed = []
    for n, st in out.items():
        if n == base:
            continue
        beat = int((st["years"] > a["years"]).sum())
        st["beat"] = beat
        if st["sharpe"] > a["sharpe"] and st["cagr"] > a["cagr"] and beat >= len(a["years"]) / 2:
            passed.append(n)
    verdict = f"ADOPT {max(passed, key=lambda n: out[n]['sharpe'])}" if passed else f"KEEP {base}"
    print(f"\nVERDICT: {verdict}")

    stamp = datetime.now()
    day = OUT / f"{stamp:%Y-%m-%d}"
    day.mkdir(parents=True, exist_ok=True)
    md = mm.unclobbered(day / f"book-choice-{test}-{stamp:%Y%m%d-%H%M%S}.md")
    title = "Momentum signal" if test == "signal" else "Number of names"
    L = [f"# {title} for the weekly stock book, {stamp:%d %B %Y %H:%M}", "",
         f"A daily replay of the live book, trimming on, {SHARE:.0%} in stocks, from {days[0]:%d %B %Y} "
         f"to {days[-1]:%d %B %Y}.", "",
         f"Verdict, {verdict}. Another version was to be adopted only with a higher Sharpe ratio and higher "
         f"growth a year than the live version, and beating it in at least half the calendar years.", "",
         "| version | growth a year | volatility | Sharpe | maximum drawdown | grew | cost over the run "
         "| years ahead of live |",
         "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for n, st in out.items():
        ahead = "" if n == base else f"{st['beat']} of {len(a['years'])}"
        L.append(f"| {n} | {st['cagr']:.1%} | {st['vol']:.1%} | {st['sharpe']:.3f} | {st['max_dd']:.1%} | "
                 f"{st['final']:.2f}x | {st['cost']:.1%} | {ahead} |")
    names = list(out)
    L += ["", "| year | " + " | ".join(names) + " |", "| --- |" + " ---: |" * len(names)]
    for yr in a["years"].index:
        L.append(f"| {yr:%Y} | " + " | ".join(f"{out[n]['years'][yr]:.1%}" for n in names) + " |")
    L += ["", "The panel holds only stocks still listed, which flatters every version alike.", "",
          "Run with `03-inputs/book_choice_test.py`, whose rules were fixed before the first run.", ""]
    md.write_text("\n".join(L) + "\n", encoding="utf-8")
    pd.DataFrame(curves).to_csv(md.with_suffix(".curves.csv"))
    print(f"record: {md.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1] if len(sys.argv) > 1 else "signal"))
