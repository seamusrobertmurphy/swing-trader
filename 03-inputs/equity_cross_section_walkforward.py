"""Kill harness for the cross-sectional trend ranking on stocks, monthly holds, half-year folds.

    .venv/bin/python 03-inputs/equity_cross_section_walkforward.py

Workplan of 19 October 2026, item 4. In June 2026 the crypto cross-section
showed that ranking coins by a trend signal sorts them, 25 of 42 signals with a
top third ahead of the bottom third in both periods, and the most robust was
the Modern Adaptive Supertrend direction, f_mst_dir. Long-only it lost because
the crypto market itself fell. Stocks drift up, so this asks whether the same
ranking adds anything on the stock panel, which it has never been run on.

Pre-registered on 19 October 2026, before the first run.

    Candidate  f_mst_dist, the signed distance of the close from the adaptive
               Supertrend line, the continuous form of f_mst_dir, so that
               ranking into thirds does not collapse on ties. One signal only.
    Control    12-1 momentum, the signal the book trades, which passed the
               August test, scored here so a broken harness shows itself.
    Universe   at each month-end, names with 260 days of history, a close of
               at least $3 and a 63-day median dollar volume of at least $20
               million, and at least 50 names in the month, as in
               equity_momentum_monthly.py.
    Hold       the top third by the signal, equal weight, bought at the
               month-end close and sold at the next, so no two holds overlap.
    Cost       0.16 per cent a month on the top third, the measured 7.9 basis
               points a fill off the open, both ways, as if every name turned
               over. The market leg is every eligible name, charged nothing.
    Spread     the top third's return after cost minus the market's.

Kill criteria.

    K1  fewer than 60 per cent of half-year folds with a positive mean spread,
        where a fold is eligible with at least 3 months.
    K2  the mean monthly spread is zero or below.

Either one kills it. The panel holds only stocks still listed, so every figure
is an upper bound, which flatters both legs alike and the spread less.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import model_metrics as mm                                     # noqa: E402
from equity_momentum_monthly import (MIN_DOLLAR_VOL, MIN_HISTORY,  # noqa: E402
                                     MIN_NAMES, MIN_PRICE, monthly_panel)

REPO = Path(__file__).resolve().parents[1]
PANEL = REPO / "03-inputs" / "alpaca-data" / "dataset_eq1d_allmarket.parquet"
OUT = REPO / "04-outputs" / "AA-evals"
CANDIDATE = "f_mst_dist"
COST = 0.0016
TOP_FRAC = 1.0 / 3.0
PASS_RATE = 0.60
MIN_FOLD_MONTHS = 3


def candidate_wide(px: pd.DataFrame) -> pd.DataFrame:
    """The candidate signal as a date by name table, read one row group at a time."""
    import pyarrow.parquet as pq
    pf = pq.ParquetFile(PANEL)
    parts = [pf.read_row_group(g, columns=["symbol", "datetime", CANDIDATE]).to_pandas()
             for g in range(pf.num_row_groups)]
    d = pd.concat(parts, ignore_index=True)
    d[CANDIDATE] = d[CANDIDATE].astype("float32")
    w = d.pivot_table(index="datetime", columns="symbol", values=CANDIDATE, aggfunc="last")
    w.index = pd.to_datetime(w.index).tz_localize(None).normalize()
    return w.reindex(index=px.index, columns=px.columns)


def months(sig: pd.DataFrame, px: pd.DataFrame, dv_med: pd.DataFrame, ends: list) -> pd.DataFrame:
    hist_ok = px.notna().rolling(MIN_HISTORY, min_periods=MIN_HISTORY).count() >= MIN_HISTORY
    rows = []
    for t0, t1 in zip(ends[:-1], ends[1:]):
        elig = (hist_ok.loc[t0] & (px.loc[t0] >= MIN_PRICE) & (dv_med.loc[t0] >= MIN_DOLLAR_VOL)
                & sig.loc[t0].notna() & px.loc[t1].notna())
        names = elig[elig].index
        if len(names) < MIN_NAMES:
            continue
        s = sig.loc[t0, names]
        top = s[s.rank(pct=True) > (1 - TOP_FRAC)].index
        fwd = px.loc[t1, names] / px.loc[t0, names] - 1.0
        rows.append(dict(month=t1, names=len(names), top_n=len(top),
                         top=float(fwd.loc[top].mean()) - COST, mkt=float(fwd.mean()), picks=set(top)))
    m = pd.DataFrame(rows).set_index("month")
    m["spread"] = m["top"] - m["mkt"]
    return m


def verdict(m: pd.DataFrame) -> dict:
    fold = m.index.year.astype(str) + np.where(m.index.month <= 6, "H1", "H2")
    f = m.groupby(fold).agg(months=("top", "size"), top=("top", "mean"), mkt=("mkt", "mean"),
                            spread=("spread", "mean"))
    el = f[f["months"] >= MIN_FOLD_MONTHS]
    pos = int((el["spread"] > 0).sum())
    rate = pos / len(el) if len(el) else float("nan")
    mean = float(m["spread"].mean())
    t = mean / (m["spread"].std(ddof=1) / np.sqrt(len(m))) if len(m) > 1 else float("nan")
    return dict(folds=f, eligible=len(el), positive=pos, rate=rate, mean=mean, tstat=float(t),
                hit=float((m["spread"] > 0).mean()), k1=len(el) > 0 and rate >= PASS_RATE, k2=mean > 0)


def write(res: dict) -> Path:
    stamp = datetime.now()
    day = OUT / f"{stamp:%Y-%m-%d}"
    day.mkdir(parents=True, exist_ok=True)
    md = mm.unclobbered(day / f"equity-cross-section-walkforward-{stamp:%Y%m%d-%H%M%S}.md")
    pct = lambda v: "n/a" if v != v else f"{v*100:+.3f}%"
    c, k, m = res["cand"], res["ctrl"], res["m"]
    word = lambda v: "SURVIVES" if v["k1"] and v["k2"] else "KILLED"
    L = [f"# Stock cross-section, kill harness, {stamp:%d %B %Y %H:%M}", "",
         f"From {m.index.min():%B %Y} to {m.index.max():%B %Y}, {len(m)} month-ends on the stock panel, "
         f"each month's eligible names were ranked by the signal and the top third held to the next "
         f"month-end, charged {COST*100:.2f} per cent. The spread is that return less the return of "
         f"every eligible name. Median names a month {int(m['names'].median())}.", "",
         f"Candidate {CANDIDATE}, {word(c)}. {c['positive']} of {c['eligible']} half-year folds had a "
         f"positive spread ({c['rate']:.0%} against the 60 per cent bar), and the mean monthly spread was "
         f"{pct(c['mean'])}, t = {c['tstat']:.2f}, positive in {c['hit']:.0%} of months.", "",
         f"Control, 12-1 momentum, {word(k)}. {k['positive']} of {k['eligible']} folds positive "
         f"({k['rate']:.0%}), mean monthly spread {pct(k['mean'])}, t = {k['tstat']:.2f}.", "",
         f"The candidate's monthly spread correlated {res['corr']:.2f} with the control's, and on average "
         f"{res['overlap']:.0%} of the candidate's top third was also in momentum's top third.", "",
         "## Folds", "",
         "| fold | months | candidate top after cost | market | candidate spread | momentum spread |",
         "| --- | ---: | ---: | ---: | ---: | ---: |"]
    kf = k["folds"]
    for name, r in c["folds"].iterrows():
        ks = kf.loc[name, "spread"] if name in kf.index else float("nan")
        L.append(f"| {name} | {int(r['months'])} | {pct(r['top'])} | {pct(r['mkt'])} | {pct(r['spread'])} | {pct(ks)} |")
    L += ["", "The panel holds only stocks still listed, so both legs are flattered; the spread less so.",
          "", "Run with `03-inputs/equity_cross_section_walkforward.py`, whose criteria were fixed "
          "before the first run.", ""]
    md.write_text("\n".join(L) + "\n", encoding="utf-8")
    log_csv = md.with_suffix(".months.csv")
    m.drop(columns=["picks"]).join(res["mk"][["spread"]].rename(columns={"spread": "momentum_spread"})).to_csv(log_csv)
    print(f"record: {md.relative_to(REPO)}")
    return md


def main() -> int:
    px, dv, dv_med = monthly_panel("none")
    px.index = pd.to_datetime(px.index).tz_localize(None).normalize() if px.index.tz is not None \
        else pd.to_datetime(px.index).normalize()
    dv_med.index = px.index
    sig = candidate_wide(px)
    last = sig.dropna(how="all").index.max()
    px, dv_med, sig = px.loc[:last], dv_med.loc[:last], sig.loc[:last]
    ends = px.groupby(px.index.to_period("M")).apply(lambda g: g.index.max()).to_list()
    print(f"{len(ends)} month-ends to {last:%Y-%m-%d}; candidate covers "
          f"{int(sig.notna().any().sum())} names", flush=True)
    m = months(sig, px, dv_med, ends)
    mom = px.shift(21) / px.shift(252) - 1.0
    mk = months(mom, px, dv_med, ends)
    c, k = verdict(m), verdict(mk)
    j = m[["spread", "picks"]].join(mk[["spread", "picks"]], rsuffix="_k", how="inner")
    corr = float(j["spread"].corr(j["spread_k"]))
    overlap = float(np.mean([len(a & b) / len(a) for a, b in zip(j["picks"], j["picks_k"]) if a]))
    for name, v in (("candidate " + CANDIDATE, c), ("control 12-1 momentum", k)):
        print(f"{name}: {'SURVIVES' if v['k1'] and v['k2'] else 'KILLED'}  folds {v['positive']}/{v['eligible']} "
              f"({v['rate']:.0%}), mean spread {v['mean']*100:+.3f}%/month, t {v['tstat']:.2f}")
    print(f"correlation of spreads {corr:.2f}, overlap of picks {overlap:.0%}")
    write(dict(cand=c, ctrl=k, m=m, mk=mk, corr=corr, overlap=overlap))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
