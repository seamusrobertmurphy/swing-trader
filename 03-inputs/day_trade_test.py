"""Can a same-day trade make money after cost, on stocks or on crypto?

    .venv/bin/python 03-inputs/day_trade_test.py stocks
    .venv/bin/python 03-inputs/day_trade_test.py crypto

Asked by the operator on 21 October 2026, after six months in which no day trade
or scalp had ever been scored: "That doesn't offer any performance evaluation of
scalping or day trades." Every trade here opens and closes on the same day,
long only, as the charter allows, on the 3-minute bars already on disk.

    stocks  03-inputs/alpaca-data/min3, 356 screened US names, regular session,
            New York time, 2016 to 2026.
    crypto  03-inputs/binance-data/parquet_3m, 586 USDT pairs, the day is the
            UTC calendar day, 2017 to 2026, a pair counted only on days its
            median daily turnover over the previous 30 days was at least
            30 million USDT, the screen the crypto book uses.

Two rules, the same on both markets, fixed on 21 October 2026 before the first
run.

    R1  intraday momentum. When the return from the previous day's last close
        to the close of the first 30 minutes is positive, buy at the close of
        the bar that ends 30 minutes before the day's last bar closes and sell
        at the day's last close. After Gao, Han, Li and Zhou (2018), who found
        the first half hour predicted the last half hour on the S&P 500 fund.
    R2  opening range breakout. The first 30 minutes set a high. The first
        later bar to trade above it buys at that high, or at the bar's open if
        it opened above, and sells at the day's last close.

Cost per round trip: stocks 16 basis points, twice the 7.9 measured a fill off
the open; crypto 15 basis points, the achievable round trip in
trade_binance.ACHIEVABLE_COST_PCT.

Scoring. Each day's trades are averaged into one equal-weight daily return, so
a day with 300 trades counts once. A rule passes when the mean daily return
after cost is above zero with a t-statistic of at least 2, AND at least 60 per
cent of half-year folds are positive after cost, the bar every candidate here
has faced. The stock names are those listed today, which flatters both rules.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import model_metrics as mm                                       # noqa: E402

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "04-outputs" / "AA-evals"
MARKETS = {
    "stocks": dict(root=REPO / "03-inputs" / "alpaca-data" / "min3", tz="America/New_York",
                   start="09:30", cost=0.0016, vol_col=None),
    "crypto": dict(root=REPO / "03-inputs" / "binance-data" / "parquet_3m", tz="UTC",
                   start="00:00", cost=0.0015, vol_col="quote_volume"),
}
MIN_TURNOVER = 30e6
BAR = pd.Timedelta(minutes=3)


def trades_of(path: Path, m: dict) -> pd.DataFrame:
    cols = ["datetime", "open", "high", "close"] + ([m["vol_col"]] if m["vol_col"] else [])
    b = pd.read_parquet(path, columns=cols)
    b["t"] = b.pop("datetime").dt.tz_convert(m["tz"])
    b["day"] = b["t"].dt.tz_localize(None).dt.normalize()
    b["mins"] = (b["t"] - b["t"].dt.normalize()).dt.total_seconds() / 60
    open_min = int(m["start"][:2]) * 60 + int(m["start"][3:])
    b["k"] = ((b["mins"] - open_min) / 3).round().astype(int)
    g = b.groupby("day")
    n_full = int(b.loc[b["k"] >= 0, "k"].max()) if len(b) else 0
    # Only complete days: bars from the open to the usual last bar.
    full = g["k"].agg(["min", "max", "count"])
    full = full[(full["min"] == 0) & (full["max"] == n_full) & (full["count"] >= 0.9 * (n_full + 1))].index
    b = b[b["day"].isin(full)]
    if b.empty:
        return pd.DataFrame()
    piv_c = b.pivot_table(index="day", columns="k", values="close", aggfunc="last")
    piv_h = b.pivot_table(index="day", columns="k", values="high", aggfunc="last")
    piv_o = b.pivot_table(index="day", columns="k", values="open", aggfunc="last")
    first_close = piv_c[9]
    last_close = piv_c[n_full]
    prev_close = last_close.shift(1)
    entry_r1 = piv_c[n_full - 10]
    r1_sig = first_close / prev_close - 1 > 0
    r1 = (last_close / entry_r1 - 1).where(r1_sig)
    hi = piv_h.loc[:, 0:9].max(axis=1)
    later_h = piv_h.loc[:, 10:n_full]
    broke = later_h.gt(hi, axis=0)
    first_k = broke.idxmax(axis=1).where(broke.any(axis=1))
    r2 = pd.Series(np.nan, index=piv_c.index)
    for d, k in first_k.dropna().items():
        o = piv_o.at[d, k]
        px = max(hi[d], o) if o == o else hi[d]
        r2[d] = last_close[d] / px - 1
    out = pd.DataFrame({"R1": r1, "R2": r2})
    if m["vol_col"]:
        turnover = b.groupby("day")[m["vol_col"]].sum()
        ok = turnover.rolling(30, min_periods=20).median().shift(1) >= MIN_TURNOVER
        out = out[ok.reindex(out.index, fill_value=False)]
    out.index.name = "day"
    return out.astype("float32")


def score(daily: pd.Series) -> dict:
    daily = daily.dropna()
    t = daily.mean() / daily.std() * np.sqrt(len(daily)) if len(daily) > 1 else 0.0
    half = daily.groupby([daily.index.year, (daily.index.month - 1) // 6]).mean()
    return dict(days=len(daily), mean=float(daily.mean()), t=float(t),
                folds=len(half), pos=int((half > 0).sum()),
                year=float((1 + daily).prod() ** (252 / len(daily)) - 1) if len(daily) else 0.0)


def main() -> int:
    market = sys.argv[1] if len(sys.argv) > 1 else "stocks"
    m = MARKETS[market]
    files = sorted(p for p in m["root"].glob("*.parquet") if not p.name.startswith("._"))
    parts = []
    for i, p in enumerate(files, 1):
        try:
            t = trades_of(p, m)
        except Exception as e:                                    # noqa: BLE001
            print(f"skip {p.stem}: {e}", flush=True)
            continue
        if len(t):
            t["sym"] = p.stem
            parts.append(t.reset_index())
        if i % 50 == 0:
            print(f"{i} of {len(files)} files", flush=True)
    tr = pd.concat(parts, ignore_index=True)
    res, lines = {}, []
    for rule in ("R1", "R2"):
        x = tr[["day", "sym", rule]].dropna()
        gross = x.groupby("day")[rule].mean()
        net = (x[rule] - m["cost"]).groupby(x["day"]).mean()
        st = score(net)
        st.update(trades=len(x), names=x["sym"].nunique(), gross=float(gross.mean()),
                  trade_net=float((x[rule] - m["cost"]).mean()))
        st["pass"] = st["mean"] > 0 and st["t"] >= 2 and st["pos"] >= 0.6 * st["folds"]
        res[rule] = st
        lines.append(f"{rule}: {st['trades']:,} trades on {st['names']} names over {st['days']} days; "
                     f"mean trade before cost {x[rule].mean():+.3%}, after cost {st['trade_net']:+.3%}; "
                     f"daily book after cost {st['mean']:+.3%}, t {st['t']:.2f}, "
                     f"{st['pos']} of {st['folds']} half-years positive -> "
                     f"{'PASS' if st['pass'] else 'FAIL'}")
        print(lines[-1], flush=True)

    stamp = datetime.now()
    day = OUT / f"{stamp:%Y-%m-%d}"
    day.mkdir(parents=True, exist_ok=True)
    md = mm.unclobbered(day / f"day-trade-test-{market}-{stamp:%Y%m%d-%H%M%S}.md")
    names = {"R1": "Intraday momentum, last 30 minutes", "R2": "Opening range breakout"}
    L = [f"# Day trades on {market}, {stamp:%d %B %Y %H:%M}", "",
         f"Same-day, long-only trades on 3-minute bars, {tr['day'].min():%d %B %Y} to "
         f"{tr['day'].max():%d %B %Y}, {m['cost'] * 1e4:.0f} basis points a round trip. A rule passes "
         f"with a positive mean daily return after cost, a t-statistic of at least 2, and at least 60 "
         f"per cent of half-year folds positive.", "",
         "| rule | trades | names | mean trade before cost | mean trade after cost "
         "| daily book after cost | t | half-years positive | growth a year | verdict |",
         "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for r, st in res.items():
        L.append(f"| {names[r]} | {st['trades']:,} | {st['names']} | {st['trade_net'] + m['cost']:+.3%} | "
                 f"{st['trade_net']:+.3%} | {st['mean']:+.3%} | {st['t']:.2f} | {st['pos']} of "
                 f"{st['folds']} | {st['year']:+.1%} | {'PASS' if st['pass'] else 'FAIL'} |")
    L += ["", "Run with `03-inputs/day_trade_test.py`, whose rules were fixed before the first run.", ""]
    md.write_text("\n".join(L) + "\n", encoding="utf-8")
    tr.to_parquet(md.with_suffix(".trades.parquet"))
    print(f"record: {md.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
