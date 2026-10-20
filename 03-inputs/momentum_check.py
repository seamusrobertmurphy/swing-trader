"""How unusual is the momentum book's recent fall? Its own history since 2017.

    .venv/bin/python 03-inputs/momentum_check.py

Asked by the operator on 19 October 2026, after the replay showed the book's
rules, traded perfectly, fell 10.85 per cent in the week to 16 October against
1.97 per cent for the market. Today's picks, rebalanced on the first session of
every week with no cost, are replayed from the first week the panel allows,
and the recent figures are placed in that history.

Every name is reset to an equal 1.8 per cent each week, as the August backtest
was built. The live rule never trims a winner, and replayed for nine years that
left five names holding 25 per cent of the book and room for only 37, a book
nothing like the two-month-old live one, whose largest holding was 2.6 per cent.

    1. The week to 16 October, ranked among every week.
    2. The 44 sessions since 18 August against the market, ranked among every
       44-session stretch.
    3. The fall from the book's peak now, against its falls before.
    4. What followed the weeks as bad or worse, over the next 4 and 13 weeks.
       This describes the book's past; it is not a forecast.

The panel holds only stocks still listed, which flatters the book's history.
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
from build_dataset_equity import load_symbol                     # noqa: E402
from equity_momentum_monthly import MIN_HISTORY, SIGNALS, monthly_panel  # noqa: E402
from live_vs_replay import picks                                # noqa: E402

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "04-outputs" / "AA-evals"
WINDOW = 44
RECENT = pd.Timestamp("2026-10-16")
INVESTED = 0.90


def equal_weight(px, days, trade_days, choose) -> pd.Series:
    """Daily value of the book reset to equal weights on trade_days, no cost."""
    ret = px.pct_change(fill_method=None)
    w, value, out = pd.Series(dtype=float), 1.0, []
    for d in days:
        if len(w):
            r = ret.loc[d, w.index].fillna(0.0)
            growth = float((w * (1 + r)).sum() + (1 - w.sum()))
            w = w * (1 + r) / growth
            value *= growth
        if d in trade_days:
            top = choose(days[days.get_loc(d) - 1])
            if top:
                w = pd.Series(INVESTED / len(top), index=top)
        out.append(value)
    return pd.Series(out, index=days)


def main() -> int:
    px, dv, dv_med = monthly_panel(UNIVERSE_EXCLUDE)
    px.index = pd.to_datetime(px.index).normalize()
    dv_med.index = px.index
    sig = SIGNALS["mom_12_1"](px)
    hist_ok = px.notna().rolling(MIN_HISTORY, min_periods=MIN_HISTORY).count() >= MIN_HISTORY
    logret = np.log(px).diff()
    days = px.index[MIN_HISTORY + 1:]
    week = days.to_period("W")
    on_time = set(days[np.r_[True, week[1:] != week[:-1]]])
    book = equal_weight(px, days, on_time, lambda d: picks(d, px, dv_med, sig, hist_ok, logret))
    book = book[book.ne(book.iloc[0]).idxmax() - pd.Timedelta(days=1):] if (book != book.iloc[0]).any() else book
    s = load_symbol("SPY").set_index("datetime")["close"]
    s.index = pd.to_datetime(s.index).normalize()
    spy = s.reindex(book.index).ffill()

    wk = pd.DataFrame({"book": book, "spy": spy}).groupby(book.index.to_period("W")).last()
    wr = wk.pct_change().dropna()
    wr["excess"] = wr["book"] - wr["spy"]
    rw = RECENT.to_period("W")
    this = wr.loc[rw]
    rank_b = int((wr["book"] <= this["book"]).sum())
    rank_x = int((wr["excess"] <= this["excess"]).sum())

    lr = pd.DataFrame({"book": book, "spy": spy}).pct_change(WINDOW).dropna()
    lr["excess"] = lr["book"] - lr["spy"]
    now = lr.iloc[-1]
    pct_x = float((lr["excess"] <= now["excess"]).mean())

    dd = book / book.cummax() - 1
    dd_now = float(dd.iloc[-1])
    troughs = dd.groupby((dd == 0).cumsum()).min()
    deeper = int((troughs <= dd_now).sum())

    bad = wr.index[(wr["book"] <= this["book"]) & (wr.index != rw)]
    after = []
    for w in bad:
        i = wk.index.get_loc(w)
        row = dict(week=w)
        for n in (4, 13):
            if i + n < len(wk):
                b = wk["book"].iloc[i + n] / wk["book"].iloc[i] - 1
                m = wk["spy"].iloc[i + n] / wk["spy"].iloc[i] - 1
                row[f"book_{n}"], row[f"excess_{n}"] = b, b - m
        after.append(row)
    A = pd.DataFrame(after)
    yrs = (book.index[-1] - book.index[0]).days / 365.25
    cagr = float((book.iloc[-1] / book.iloc[0]) ** (1 / yrs) - 1)
    spy_cagr = float((spy.iloc[-1] / spy.iloc[0]) ** (1 / yrs) - 1)

    print(f"replay {book.index[0]:%Y-%m-%d} to {book.index[-1]:%Y-%m-%d}: {cagr:+.1%} a year, SPY {spy_cagr:+.1%}")
    print(f"week to {RECENT:%d %b}: book {this['book']:+.2%} (rank {rank_b} of {len(wr)} weeks from the bottom), "
          f"against SPY {this['excess']:+.2%} (rank {rank_x})")
    print(f"last {WINDOW} sessions against SPY {now['excess']:+.2%}, at the {pct_x:.0%} point of every stretch")
    print(f"fall from peak now {dd_now:.1%}; {deeper} earlier falls went as deep or deeper")
    print(A.round(4).to_string())

    stamp = datetime.now()
    day = OUT / f"{stamp:%Y-%m-%d}"
    day.mkdir(parents=True, exist_ok=True)
    md = mm.unclobbered(day / f"momentum-check-{stamp:%Y%m%d-%H%M%S}.md")
    p = lambda v: "n/a" if v != v else f"{v:+.2%}"
    L = [f"# Momentum check, {stamp:%d %B %Y %H:%M}", "",
         f"Today's picks, reset to equal weights every week on time with no cost, were replayed from {book.index[0]:%d %B %Y} "
         f"to {book.index[-1]:%d %B %Y}. The replay grew {cagr:+.1%} a year against {spy_cagr:+.1%} for SPY, "
         f"over {len(wr)} weeks.", "",
         f"The week to {RECENT:%d %B}, the book fell {abs(this['book']):.2%}, the {rank_b}th worst of {len(wr)} weeks, "
         f"and trailed SPY by {abs(this['excess']):.2%}, the {rank_x}th worst.", "",
         f"Over the last {WINDOW} sessions, since 18 August, the book was {p(now['excess'])} against SPY. "
         f"{pct_x:.0%} of all {WINDOW}-session stretches since {book.index[0]:%Y} were as bad or worse.", "",
         f"The book now sits {abs(dd_now):.1%} below its peak. {deeper} of its {len(troughs)} earlier falls "
         f"went as deep or deeper.", "",
         "## After weeks as bad", "",
         "What the book did in the 4 and 13 weeks after each earlier week as bad or worse. This is its past, "
         "not a forecast.", "",
         "| week | next 4 weeks | against SPY | next 13 weeks | against SPY |", "| --- | ---: | ---: | ---: | ---: |"]
    for r in A.itertuples():
        L.append(f"| {r.week.end_time:%d %b %Y} | {p(getattr(r, 'book_4', np.nan))} | {p(getattr(r, 'excess_4', np.nan))} "
                 f"| {p(getattr(r, 'book_13', np.nan))} | {p(getattr(r, 'excess_13', np.nan))} |")
    L += ["", "The panel holds only stocks still listed, which flatters the book's history.", "",
          "Run with `03-inputs/momentum_check.py`.", ""]
    md.write_text("\n".join(L) + "\n", encoding="utf-8")
    book.to_frame("book").join(spy.rename("spy")).to_csv(md.with_suffix(".curves.csv"))
    print(f"record: {md.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
