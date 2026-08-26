"""Track A: canonical monthly cross-sectional factors, non-overlapping holds.

The A4 read established that equity costs are affordable and the open question
is selection stability measured sanely. This test removes the two artifacts the
first pass carried: signals are fixed A PRIORI from the literature (nothing is
picked on any score of ours), and holds are non-overlapping calendar months, so
each month is one independent observation instead of twenty overlapping ones.

Signals, all pre-registered here:
  mom_12_1   return from t-252 to t-21 trading days (the canonical factor,
             skip-month included)
  mom_6_1    return from t-126 to t-21 (secondary)
  low_vol    negative trailing 252-day realized vol (secondary; top decile =
             calmest names)

Construction per month-end: universe = names with 260+ days of history, price
>= $3, median 63-day dollar volume >= $20M at formation (survivor-biased, as
stamped everywhere in this layer); rank; hold the top decile equal-weight for
the next month; charge the full 0.05% round trip every month (full-turnover
upper bound on cost). Score the monthly top-minus-universe spread and absolute
net against the same 60% half-year fold bars as the kill harness, plus a
monthly hit rate and a t-statistic on the spread.

    .venv/bin/python inputs/equity_momentum_monthly.py
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd

from build_dataset_equity import DAILY, list_symbols, load_symbol
from equity_universe_filter import fund_symbols

COST = 0.0005          # full round trip charged every month (turnover upper bound)
TOP_FRAC = 0.10
MIN_NAMES = 50
MIN_HISTORY = 260
MIN_PRICE = 3.0
MIN_DOLLAR_VOL = 20e6
PASS_RATE = 0.60

SIGNALS = {
    "mom_12_1": lambda px: px.shift(21) / px.shift(252) - 1.0,
    "mom_6_1": lambda px: px.shift(21) / px.shift(126) - 1.0,
    "low_vol": lambda px: -np.log(px).diff().rolling(252).std(),
}


def monthly_panel(exclude: str = "none") -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Wide monthly close / signal-eligibility inputs from the raw daily files.

    exclude: "none" keeps the original 2026-08-18 universe (ETFs included, as
    the first SURVIVES verdict was computed); "levered" drops leveraged and
    inverse funds only; "funds" drops every pooled vehicle, leaving operating
    companies. See equity_universe_filter for why this switch exists.
    """
    drop = set()
    if exclude == "levered":
        drop = fund_symbols(levered_only=True)
    elif exclude == "funds":
        drop = fund_symbols()
    if drop:
        print(f"universe filter {exclude!r}: excluding {len(drop)} symbols", flush=True)
    closes, dollars = {}, {}
    for sym in list_symbols():
        if sym in drop:
            continue
        d = load_symbol(sym)
        if len(d) < MIN_HISTORY:
            continue
        s = d.set_index("datetime")
        closes[sym] = s["close"]
        dollars[sym] = s["quote_volume"]
    px = pd.DataFrame(closes).sort_index()
    dv = pd.DataFrame(dollars).sort_index()
    print(f"panel: {px.shape[1]} names x {px.shape[0]} days", flush=True)
    return px, dv, dv.rolling(63, min_periods=40).median()


def run_signal(name, fn, px, dv_med, month_ends):
    sig = fn(px)
    hist_ok = px.notna().rolling(MIN_HISTORY, min_periods=MIN_HISTORY).count() >= MIN_HISTORY
    rows = []
    for i in range(len(month_ends) - 1):
        t0, t1 = month_ends[i], month_ends[i + 1]
        elig = (hist_ok.loc[t0] & (px.loc[t0] >= MIN_PRICE)
                & (dv_med.loc[t0] >= MIN_DOLLAR_VOL) & sig.loc[t0].notna())
        names = elig[elig].index
        if len(names) < MIN_NAMES:
            continue
        s = sig.loc[t0, names]
        top = s[s.rank(pct=True) > (1 - TOP_FRAC)].index
        fwd = px.loc[t1, names] / px.loc[t0, names] - 1.0
        rows.append(dict(month=t1, n=len(names), n_top=len(top),
                         top=float(fwd.loc[top].mean()) - COST,
                         mkt=float(fwd.mean()) - COST))
    m = pd.DataFrame(rows).set_index("month")
    m["spread"] = m["top"] - m["mkt"]
    return m


def fold_verdict(m: pd.DataFrame) -> dict:
    fold = m.index.year.astype(str) + np.where(m.index.month <= 6, "H1", "H2")
    f = m.groupby(fold).agg(months=("top", "size"), top=("top", "mean"),
                            mkt=("mkt", "mean"), spread=("spread", "mean"))
    el = f[f["months"] >= 3]
    abs_rate = float((el["top"] > 0).mean())
    sel_rate = float((el["spread"] > 0).mean())
    t = float(m["spread"].mean() / (m["spread"].std() / np.sqrt(len(m))))
    return dict(folds=f, eligible=len(el), abs_rate=abs_rate, sel_rate=sel_rate,
                mean_spread=float(m["spread"].mean()), tstat=t,
                hit=float((m["spread"] > 0).mean()),
                survives=abs_rate >= PASS_RATE and sel_rate >= PASS_RATE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", action="store_true", help="print per-fold tables")
    ap.add_argument("--exclude", choices=("none", "levered", "funds"), default="none",
                    help="universe filter: drop leveraged funds, or all funds")
    a = ap.parse_args()

    px, dv, dv_med = monthly_panel(a.exclude)
    month_ends = px.groupby(px.index.to_period("M")).apply(lambda g: g.index.max()).to_list()

    print(f"\nmonth-ends: {len(month_ends)}  cost {COST:.4%}/month (full-turnover bound)  "
          f"top {TOP_FRAC:.0%} at {MIN_NAMES}-name floor\n")
    summary = []
    for name, fn in SIGNALS.items():
        m = run_signal(name, fn, px, dv_med, month_ends)
        v = fold_verdict(m)
        summary.append(dict(signal=name, months=len(m),
                            mean_top=round(float(m['top'].mean()) * 100, 3),
                            mean_mkt=round(float(m['mkt'].mean()) * 100, 3),
                            spread=round(v["mean_spread"] * 100, 3),
                            hit=round(v["hit"], 2), tstat=round(v["tstat"], 2),
                            abs_rate=f"{v['abs_rate']:.0%}",
                            sel_rate=f"{v['sel_rate']:.0%}",
                            verdict="SURVIVES" if v["survives"] else "KILLED"))
        if a.folds:
            print(f"--- {name} folds")
            print((v["folds"] * pd.Series({"months": 1, "top": 100, "mkt": 100,
                                           "spread": 100})).round(3).to_string(), "\n")
    board = pd.DataFrame(summary)
    pd.set_option("display.width", 200)
    print("=" * 100)
    print(f"MONTHLY FACTOR TEST [exclude={a.exclude}], non-overlapping holds, after {COST:.2%}/month. "
          f"%%/month columns. Bars: abs and sel >= {PASS_RATE:.0%} of half-year folds.")
    print("=" * 100)
    print(board.to_string(index=False))
    print("\nsurvivorship caveat: live names only; every number an upper bound.")


if __name__ == "__main__":
    main()
