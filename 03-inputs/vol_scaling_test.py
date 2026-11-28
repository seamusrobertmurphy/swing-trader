"""Does shrinking the momentum book when its own swings are large raise returns?

    .venv/bin/python 03-inputs/vol_scaling_test.py

Asked by the operator on 20 October 2026, "What development tasks or
improvements can we make today that will yield us an improvement in our trading
returns?" Momentum is known to crash after its own volatility rises, and
scaling a momentum portfolio down when its recent volatility is high was found
to avoid most of those crashes (Barroso and Santa-Clara 2015, Journal of
Financial Economics 116, 111-120; Daniel and Moskowitz 2016, Journal of
Financial Economics 122, 221-247). Barroso and Santa-Clara scaled a long-short
portfolio to a fixed volatility target from its realised volatility over the
previous six months. The book here is long only and may not borrow, so the
adaptation only ever scales down from the live 90 per cent.

The replay is trim_winners_test.replay with trimming on, the live rule since
20 October. Arm A runs first, and its daily returns are the strategy's own
volatility signal, so the signal does not depend on the scaling it drives.

Pre-registered on 20 October 2026, before the first run.

    A  the live book, 90 per cent in stocks.
    B  on each rebalance day d, the stock share is 90 per cent times
       min(1, target / sigma), where sigma is the annualised standard
       deviation of A's daily returns over the 126 sessions before d, and the
       target is the median of every sigma before d, so nothing is chosen with
       hindsight. Until 252 sigmas exist, B holds 90 per cent. Shrinking works
       through the existing rules: a name more than 25 per cent above its new
       target is trimmed, so a cut of less than a fifth sells nothing.

    B is adopted only if, over the whole history, it has a higher Sharpe
    ratio, a smaller maximum drawdown AND growth a year no lower than A,
    because the operator asked for returns, not only for less risk.

Cash earns nothing in the replay, which counts against B. The panel holds only
stocks still listed, which flatters both alike.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import model_metrics as mm                                       # noqa: E402
from alpaca_trade import CASH_FLOOR, UNIVERSE_EXCLUDE            # noqa: E402
from drawdown_ramp_test import stats                             # noqa: E402
from equity_momentum_monthly import MIN_HISTORY, SIGNALS, monthly_panel  # noqa: E402
from live_vs_replay import picks                                 # noqa: E402
from trim_winners_test import replay                             # noqa: E402

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "04-outputs" / "AA-evals"
WINDOW = 126
BURN = 252


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

    eq_a, info_a = replay(px, days, rebal, choose, True)
    vol = eq_a.pct_change().rolling(WINDOW).std() * np.sqrt(252)
    # Shift one session so the reading on day d uses returns up to d-1 only.
    vol = vol.shift(1)
    target = vol.expanding().median()
    seen = vol.notna().cumsum()
    share = ((1 - CASH_FLOOR) * np.minimum(1.0, target / vol)).where(seen >= BURN, 1 - CASH_FLOOR)
    share = share.fillna(1 - CASH_FLOOR)
    eq_b, info_b = replay(px, days, rebal, choose, True, invest=lambda d: float(share.loc[d]))

    out, curves = {}, {"A live book": eq_a, "B volatility scaled": eq_b}
    on_rebal = share[share.index.isin(rebal)]
    for name, eq, info in (("A live book", eq_a, info_a), ("B volatility scaled", eq_b, info_b)):
        st = stats(eq)
        st.update(info)
        y = eq.resample("YE").last()
        st["years"] = y.pct_change().fillna(y.iloc[0] / eq.iloc[0] - 1)
        out[name] = st
        print(f"{name:20s} CAGR {st['cagr']:.1%}  vol {st['vol']:.1%}  Sharpe {st['sharpe']:.3f}  "
              f"max drawdown {st['max_dd']:.1%}  grew {st['final']:.2f}x  cost {st['cost']:.1%}",
              flush=True)
    a, b = out["A live book"], out["B volatility scaled"]
    adopt = b["sharpe"] > a["sharpe"] and b["max_dd"] > a["max_dd"] and b["cagr"] >= a["cagr"]
    verdict = "ADOPT B volatility scaled" if adopt else "KEEP A, the live book"
    beat = int((b["years"] > a["years"]).sum())
    cut = int((on_rebal < 1 - CASH_FLOOR - 1e-9).sum())
    print(f"\nstock share on rebalance days: mean {on_rebal.mean():.1%}, lowest {on_rebal.min():.1%}, "
          f"below 90% in {cut} of {len(on_rebal)} weeks; today {share.iloc[-1]:.1%}")
    print(f"B beat A in {beat} of {len(a['years'])} calendar years\nVERDICT: {verdict}")

    stamp = datetime.now()
    day = OUT / f"{stamp:%Y-%m-%d}"
    day.mkdir(parents=True, exist_ok=True)
    md = mm.unclobbered(day / f"vol-scaling-test-{stamp:%Y%m%d-%H%M%S}.md")
    L = [f"# Volatility scaling of the momentum book, {stamp:%d %B %Y %H:%M}", "",
         f"A daily replay of the live book, trimming on, from {days[0]:%d %B %Y} to {days[-1]:%d %B %Y}. "
         f"B holds 90 per cent times min(1, target over sigma) in stocks, sigma the annualised volatility "
         f"of A's daily returns over the previous {WINDOW} sessions and the target the median of every "
         f"earlier sigma, after Barroso and Santa-Clara (2015).", "",
         f"Verdict, {verdict}. B was to be adopted only with a higher Sharpe ratio, a smaller maximum "
         f"drawdown and growth a year no lower than A.", "",
         "| version | growth a year | volatility | Sharpe | maximum drawdown | grew | cost over the run |",
         "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for n, st in out.items():
        L.append(f"| {n} | {st['cagr']:.1%} | {st['vol']:.1%} | {st['sharpe']:.3f} | {st['max_dd']:.1%} | "
                 f"{st['final']:.2f}x | {st['cost']:.1%} |")
    L += ["", f"B's stock share on rebalance days averaged {on_rebal.mean():.1%}, fell as low as "
          f"{on_rebal.min():.1%}, was below 90 per cent in {cut} of {len(on_rebal)} weeks, and reads "
          f"{share.iloc[-1]:.1%} on the last day.", "",
          "| year | A live book | B volatility scaled |", "| --- | ---: | ---: |"]
    for yr in a["years"].index:
        L.append(f"| {yr:%Y} | {a['years'][yr]:.1%} | {b['years'][yr]:.1%} |")
    L += ["", f"B beat A in {beat} of {len(a['years'])} calendar years.", "",
          "Cash earns nothing in the replay, which counts against B. The panel holds only stocks still "
          "listed, which flatters both versions alike.", "",
          "Run with `03-inputs/vol_scaling_test.py`, whose rule was fixed before the first run.", ""]
    md.write_text("\n".join(L) + "\n", encoding="utf-8")
    pd.DataFrame(curves | {"B stock share": share}).to_csv(md.with_suffix(".curves.csv"))
    print(f"record: {md.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
