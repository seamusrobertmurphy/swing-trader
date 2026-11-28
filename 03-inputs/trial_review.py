"""Every figure behind the write-up of the paper stock trial, 18 August to 3 November 2026.

    .venv/bin/python 03-inputs/trial_review.py

Asked by the operator on 4 November 2026, "yes write up the trial", after the book
was stopped and sold overnight on 3 November. Everything is read from the broker
at run time, except the nine-year replay, which is the curve the momentum check
saved on 19 October (`04-outputs/AA-evals/2026-10-19/momentum-check-20261019-222230.curves.csv`).

    1. The account, every fill, and each name's dollars, tied to the account.
    2. Daily closes of the book, SPY and MTUM, the Friday readings, and how the
       book moved against both.
    3. The overnight sale against the 3 November close and the 4 November open.
    4. Trading cost on every regular-session fill, against the minute bar's VWAP.
    5. How often the replay of the same rule did as badly over the same length.
    6. One figure, the three curves and the gap against the kill line.

Closing equity is the broker's 16:00 New York record (`last_equity` and the daily
portfolio history agree on it), not a reading taken later in the evening.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from alpaca_daily_report import _keys, benchmark, equity_curve, rebalances  # noqa: E402
from alpaca_trade import KILL_LINE, KILL_TAG, LIVE_FROM, START_EQUITY, clients  # noqa: E402
from gap_attribution import all_fills  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "04-outputs" / "AA-evals" / "2026-11-04"
REPLAY = REPO / "04-outputs" / "AA-evals" / "2026-10-19" / "momentum-check-20261019-222230.curves.csv"
ET = ZoneInfo("America/New_York")
LAST_CLOSE = pd.Timestamp("2026-11-03")
# Colours from the dataviz reference palette, validated for three series on a light surface.
BOOK, MARKET, FUND = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def account_and_names(tc) -> tuple[dict, list]:
    acct = tc.get_account()
    fills = all_fills(tc)
    pnl, n = defaultdict(float), defaultdict(int)
    for o in fills:
        v = float(o.filled_qty) * float(o.filled_avg_price)
        sell = str(o.side).endswith("SELL")
        n["sell" if sell else "buy"] += 1
        pnl[o.symbol] += v if sell else -v
    by = pd.Series(pnl).sort_values()
    by.to_csv(OUT / "trial-review-by-name.csv", header=["dollars"])
    k, s, b = _keys()
    import requests
    acts = requests.get(f"{b}/v2/account/activities", params=dict(activity_types="DIV,FEE", page_size=100),
                        headers={"APCA-API-KEY-ID": k, "APCA-API-SECRET-KEY": s}, timeout=30).json()
    extra = defaultdict(float)
    for a in acts:
        extra[a["activity_type"]] += float(a.get("net_amount") or 0)
    return dict(equity=float(acct.equity), cash=float(acct.cash), last_equity=float(acct.last_equity),
                positions=len(tc.get_all_positions()), open_orders=len(tc.get_orders()),
                fills=len(fills), buys=n["buy"], sells=n["sell"], names=len(by),
                names_lost=int((by < 0).sum()), names_made=int((by > 0).sum()),
                names_sum=float(by.sum()), dividends=extra["DIV"], fees=extra["FEE"],
                worst10=by.head(10).round(0).to_dict(), best10=by.tail(10)[::-1].round(0).to_dict()), fills


def curves() -> tuple[dict, pd.DataFrame]:
    eq = equity_curve()
    eq.index = pd.to_datetime(eq.index)
    spy, mtum = benchmark("SPY"), benchmark("MTUM")
    for x in (spy, mtum):
        x.index = pd.to_datetime(x.index)
    live = pd.Timestamp(LIVE_FROM)
    days = spy.index[(spy.index >= live) & (spy.index <= LAST_CLOSE)]
    c = pd.DataFrame({"book": eq.reindex(days) / START_EQUITY * 100,
                      "spy": spy.reindex(days) / spy.loc[live] * 100,
                      "mtum": mtum.reindex(days) / mtum.loc[live] * 100})
    c["gap"] = c["book"] - c["spy"]
    c.to_csv(OUT / "trial-review-curves.csv")
    r = c[["book", "spy", "mtum"]].pct_change().dropna()
    peak = c["book"].idxmax()
    fridays = c[(c.index.weekday == 4) | (c.index == LAST_CLOSE)]
    return dict(sessions=len(days), returns=len(r), up_days=int((r["book"] > 0).sum()),
                vol_book=float(r["book"].std() * np.sqrt(252)), vol_spy=float(r["spy"].std() * np.sqrt(252)),
                vol_mtum=float(r["mtum"].std() * np.sqrt(252)),
                beta_spy=float(np.cov(r["book"], r["spy"])[0, 1] / r["spy"].var()),
                beta_mtum=float(np.cov(r["book"], r["mtum"])[0, 1] / r["mtum"].var()),
                corr_mtum=float(r["book"].corr(r["mtum"])), corr_spy=float(r["book"].corr(r["spy"])),
                worst_day=[str(r["book"].idxmin().date()), float(r["book"].min())],
                best_day=[str(r["book"].idxmax().date()), float(r["book"].max())],
                peak=[str(peak.date()), float(c["book"].max() * START_EQUITY / 100)],
                worst_gap=[str(c["gap"].idxmin().date()), float(c["gap"].min())],
                close=c.loc[LAST_CLOSE].round(4).to_dict(),
                fridays=fridays.round(2).reset_index(names="day").astype({"day": str}).to_dict("records")), c


def overnight_sale(fills) -> dict:
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    k, s, _ = _keys()
    kill = [o for o in fills if (o.client_order_id or "").startswith(KILL_TAG) and str(o.side).endswith("SELL")]
    syms = sorted({o.symbol for o in kill})
    bars = StockHistoricalDataClient(k, s).get_stock_bars(StockBarsRequest(
        symbol_or_symbols=syms, timeframe=TimeFrame.Day, start=datetime(2026, 11, 3, tzinfo=timezone.utc),
        end=datetime.now(timezone.utc) - timedelta(minutes=25))).data
    rows = []
    for o in kill:
        bb = {x.timestamp.astimezone(ET).date(): x for x in bars[o.symbol]}
        q, f = float(o.filled_qty), float(o.filled_avg_price)
        rows.append(dict(symbol=o.symbol, tag=o.client_order_id, qty=q, fill=f,
                         filled=str(o.filled_at.astimezone(ET)),
                         close_3nov=float(bb[date(2026, 11, 3)].close), open_4nov=float(bb[date(2026, 11, 4)].open),
                         last_4nov=float(bb[date(2026, 11, 4)].close)))
    t = pd.DataFrame(rows)
    t["vs_close_bp"] = (t["fill"] / t["close_3nov"] - 1) * 1e4
    t.to_csv(OUT / "trial-review-overnight-sale.csv", index=False)
    v = lambda col: float((t["qty"] * t[col]).sum())
    return dict(orders=len(t), names=len(syms), proceeds=v("fill"), at_close_3nov=v("close_3nov"),
                at_open_4nov=v("open_4nov"), at_last_4nov=v("last_4nov"),
                within_3pct_of_close=int((t["vs_close_bp"] >= -300).sum()),
                worst_vs_close=[t.loc[t["vs_close_bp"].idxmin(), "symbol"], float(t["vs_close_bp"].min())],
                last_fill=str(t["filled"].max()))


def trading_cost(fills) -> dict:
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    k, s, _ = _keys()
    dc = StockHistoricalDataClient(k, s)
    rows = []
    for o in fills:
        if (o.client_order_id or "").startswith(KILL_TAG):
            continue
        t = o.filled_at.replace(second=0, microsecond=0)
        try:
            bars = dc.get_stock_bars(StockBarsRequest(symbol_or_symbols=o.symbol, timeframe=TimeFrame.Minute,
                                                      start=t - timedelta(minutes=1), end=t)).data[o.symbol]
            bar = {x.timestamp.astimezone(timezone.utc).replace(second=0, microsecond=0): x for x in bars}.get(t)
        except Exception:  # noqa: BLE001
            bar = None
        if bar is None:
            continue
        ref, fill = float(bar.vwap), float(o.filled_avg_price)
        sell = str(o.side).endswith("SELL")
        rows.append(dict(symbol=o.symbol, side="sell" if sell else "buy", tag=o.client_order_id or "",
                         day=str(o.filled_at.astimezone(ET).date()),
                         slip_bp=((ref - fill) / ref if sell else (fill - ref) / ref) * 1e4,
                         notional=fill * float(o.filled_qty)))
    t = pd.DataFrame(rows)
    t.to_csv(OUT / "trial-review-fill-cost.csv", index=False)
    part = lambda x: dict(n=len(x), mean=float(x["slip_bp"].mean()), median=float(x["slip_bp"].median()))
    return dict(**part(t), dollars=float((t["slip_bp"] / 1e4 * t["notional"]).sum()),
                traded=float(t["notional"].sum()), before_26oct=part(t[t["day"] < "2026-10-26"]),
                from_26oct=part(t[t["day"] >= "2026-10-26"]))


def replay_odds(n: int, close_gap: float, final_gap: float, close_book: float, final_book: float) -> dict:
    c = pd.read_csv(REPLAY, index_col=0, parse_dates=True)
    w = c.pct_change(n).dropna()
    w["excess"] = w["book"] - w["spy"]
    below = w["excess"] <= KILL_LINE
    starts = w.index[below & ~below.shift(1, fill_value=False)]
    share = lambda col, v: float((w[col] <= v).mean())
    return dict(replay=[str(c.index[0].date()), str(c.index[-1].date())], windows=len(w), sessions=n,
                mean_excess=float(w["excess"].mean()), sd_excess=float(w["excess"].std()),
                mean_book=float(w["book"].mean()), sd_book=float(w["book"].std()),
                excess_close=share("excess", close_gap), excess_final=share("excess", final_gap),
                excess_kill=share("excess", KILL_LINE), book_close=share("book", close_book),
                book_final=share("book", final_book), kill_starts=[str(d.date()) for d in starts],
                worst_excess=[str(w["excess"].idxmin().date()), float(w["excess"].min())])


def figure(c: pd.DataFrame, final_book: float, final_gap: float) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                         "xtick.color": INK2, "ytick.color": INK2, "text.color": INK})
    fig, (a, g) = plt.subplots(2, 1, figsize=(9, 7), sharex=True, gridspec_kw=dict(height_ratios=[3, 2]),
                               facecolor="#fcfcfb")
    after = LAST_CLOSE + pd.Timedelta(hours=23)
    for col, colour, name in (("book", BOOK, "Paper book"), ("mtum", FUND, "MTUM, momentum fund"),
                              ("spy", MARKET, "SPY, the market")):
        a.plot(c.index, c[col], color=colour, lw=2, label=name)
        a.annotate(f"{name} {c[col].iloc[-1]:.1f}", (c.index[-1], c[col].iloc[-1]), xytext=(6, 0),
                   textcoords="offset points", va="center", color=INK, fontsize=9)
    a.plot([c.index[-1], after], [c["book"].iloc[-1], final_book], color=BOOK, lw=2, ls=":")
    a.scatter([after], [final_book], s=64, color=BOOK, edgecolor="#fcfcfb", linewidth=2, zorder=3)
    a.annotate(f"after the overnight sale {final_book:.1f}", (after, final_book), xytext=(6, -2),
               textcoords="offset points", va="center", color=INK, fontsize=9)
    a.set_title("What 100 dollars became, from the 18 August close", loc="left", fontsize=11, color=INK)
    a.legend(loc="lower left", frameon=False, fontsize=9)
    g.plot(c.index, c["gap"], color=BOOK, lw=2)
    g.plot([c.index[-1], after], [c["gap"].iloc[-1], final_gap], color=BOOK, lw=2, ls=":")
    g.scatter([after], [final_gap], s=64, color=BOOK, edgecolor="#fcfcfb", linewidth=2, zorder=3)
    g.annotate(f"{final_gap:.1f} after the sale", (after, final_gap), xytext=(6, 0),
               textcoords="offset points", va="center", color=INK, fontsize=9)
    g.axhline(KILL_LINE * 100, color=INK2, lw=1, ls="--")
    g.annotate("kill line, -15 points", (c.index[0], KILL_LINE * 100), xytext=(0, 4),
               textcoords="offset points", color=INK2, fontsize=9)
    g.axhline(0, color=GRID, lw=1)
    g.set_title("Book minus the market, in percentage points", loc="left", fontsize=11, color=INK)
    for ax in (a, g):
        ax.set_facecolor("#fcfcfb")
        ax.grid(axis="y", color=GRID, lw=0.8)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    g.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    g.set_xlim(c.index[0] - pd.Timedelta(days=1), after + pd.Timedelta(days=13))
    fig.tight_layout()
    fig.savefig(OUT / "trial-review.png", dpi=150, facecolor="#fcfcfb")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    tc = clients()
    acct, fills = account_and_names(tc)
    daily, c = curves()
    final_book = acct["equity"] / START_EQUITY * 100
    final_gap = final_book - c["spy"].iloc[-1]
    res = dict(account=acct, daily=daily, sale=overnight_sale(fills), cost=trading_cost(fills),
               odds=replay_odds(daily["returns"], c["gap"].iloc[-1] / 100, final_gap / 100,
                                c["book"].iloc[-1] / 100 - 1, final_book / 100 - 1),
               rebalances={k: v for k, v in rebalances().items() if k != "days_since"})
    res["final"] = dict(book=final_book - 100, gap=final_gap, factor=c["mtum"].iloc[-1] - c["spy"].iloc[-1],
                        version=final_book - c["mtum"].iloc[-1])
    figure(c, final_book, final_gap)
    (OUT / "trial-review-numbers.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    print(json.dumps(res, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
