"""Kill harness for the three-way outcome on non-overlapping holds, half-year folds.

    .venv/bin/python 03-inputs/threeway_walkforward.py
    .venv/bin/python 03-inputs/threeway_walkforward.py --cost 0.0015 --band 0.01

Workplan of 19 October 2026, item 3. The three-way outcome (bench_three_way.py,
16 September 2026) made +1.09 per cent a trade after 0.20 per cent cost on one
blind year, on 3 coins, from overlapping 48-hour windows. This asks whether it
holds on every coin the 4-hour panel screens in, period after period, with each
trade's window closed before the next one on that coin opens.

The anchor is reproduced exactly where it can be: logistic regression as the
bench builds it (LogReg.glm, median imputing, scaling, no class weight), the
f_st_, f_wc_ and f_hr_ families, a 12-bar horizon, a break-even band of 0.2 per
cent and 0.20 per cent cost a trade, and a trade taken in the top fifth of rows
by P(bullish) minus P(bearish). Two things differ, both on purpose.

1. The forward return is read off the full panel, 12 bars later by the clock.
   The anchor shifted the screened rows by 12, and a coin that drops out of the
   screen and back in makes that 12 rows later but not 12 bars later.
2. The top-fifth line is the 80th percentile of the training rows' own scores,
   fixed before the fold is seen. The anchor took the fifth of the blind year
   itself, which looks ahead.

Kill criteria, fixed BEFORE the first run on 19 October 2026.

    K1  fewer than 60 per cent of eligible half-year folds positive after cost,
        where a fold is eligible with at least MIN_FOLD_TRADES trades.
    K2  the mean of every trade across all folds is zero or below after cost.

Either one kills it, and a killed result closes the crypto track under the
workplan. Long-only, no orders, no stop inside the window.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench_run as br                 # noqa: E402
import model_metrics as mm             # noqa: E402
from bench_three_way import three_way  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
PANEL = REPO / "03-inputs" / "binance-data" / "dataset_4h_allmarket.parquet"
OUT = REPO / "04-outputs" / "AA-evals"
FAMILIES = ("f_st_", "f_wc_", "f_hr_")
HORIZON = 12                 # bars of 4 hours, so 48 hours
BAR = pd.Timedelta(hours=4)
MIN_FOLD_TRADES = 8
PASS_RATE = 0.60
MIN_TRAIN_ROWS = 5000
TOP_SHARE = 0.20


def load(log=print) -> tuple[pd.DataFrame, list[str]]:
    """Screened rows with their features and the 12-bar forward return.

    Two passes, because the panel is 2 GB on disk, this machine has 8 GB, and a
    coin's rows are spread over several row groups. The first reads four small
    columns of every row and works out the forward return over the whole file;
    the second reads the features one row group at a time and keeps only the
    screened rows that have one."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    pf = pq.ParquetFile(PANEL)
    feats = [c for c in pf.schema_arrow.names if c.startswith(FAMILIES)]
    mom = f"f_hr_mom_{HORIZON}"
    small = pa.concat_tables([pf.read_row_group(g, columns=["symbol", "datetime", "in_sample", mom])
                              for g in range(pf.num_row_groups)])
    d = pd.DataFrame({"symbol": small["symbol"].dictionary_encode().to_pandas(),
                      "datetime": small["datetime"].to_pandas(),
                      "in_sample": small["in_sample"].to_numpy(zero_copy_only=False).astype(bool),
                      mom: small[mom].to_numpy(zero_copy_only=False)})
    del small
    d = d.sort_values(["symbol", "datetime"], kind="stable")
    g_sym = d.groupby("symbol", observed=True)
    later = g_sym["datetime"].shift(-HORIZON)
    fwd = g_sym[mom].shift(-HORIZON)
    # Twelve bars later by the clock, so the window has no gap in it.
    d["fwd"] = fwd.where(later - d["datetime"] == HORIZON * BAR)
    d = d.sort_index()
    keep = (d["in_sample"] & d["fwd"].notna()).to_numpy()
    fwd_all = d["fwd"].to_numpy()
    del d, g_sym, later, fwd
    parts, off = [], 0
    for g in range(pf.num_row_groups):
        t = pf.read_row_group(g, columns=["symbol", "datetime"] + feats)
        n = t.num_rows
        m = keep[off:off + n]
        part = t.filter(pa.array(m)).to_pandas()
        part["fwd"] = fwd_all[off:off + n][m]
        part[feats] = part[feats].astype("float32")
        parts.append(part)
        log(f"  row group {g}: {len(part):,} screened rows with a full 48-hour window")
        off += n
        del t
    df = pd.concat(parts, ignore_index=True)
    df["symbol"] = df["symbol"].astype(str)
    df = df.sort_values("datetime").reset_index(drop=True)
    return df[["symbol", "datetime", "fwd"] + feats], feats


def non_overlapping(rows: pd.DataFrame) -> pd.DataFrame:
    """Per coin, take a row only once the previous trade's 48 hours have passed."""
    keep = []
    for _, g in rows.sort_values("datetime").groupby("symbol", sort=False):
        free = None
        for i, t in zip(g.index, g["datetime"]):
            if free is None or t >= free:
                keep.append(i)
                free = t + HORIZON * BAR
    return rows.loc[keep]


def half_years(df: pd.DataFrame) -> list[pd.Timestamp]:
    first, last = df["datetime"].min(), df["datetime"].max()
    starts = pd.date_range(f"{first.year}-01-01", last, freq="6MS")
    return [s for s in starts if s > first]


def run(band: float, cost: float, log=print) -> dict:
    t0 = time.time()
    log(f"reading {PANEL.relative_to(REPO)}")
    df, feats = load(log)
    df["label3"] = three_way(df["fwd"], band).to_numpy()
    log(f"{len(df):,} screened rows, {df['symbol'].nunique()} coins, "
        f"{df['datetime'].min():%Y-%m-%d} to {df['datetime'].max():%Y-%m-%d}, {len(feats)} features")
    folds, trades, base_trades = [], [], []
    for s in half_years(df):
        e = s + pd.DateOffset(months=6)
        # Training labels look 48 hours ahead, so they must end before the fold.
        train = df[df["datetime"] < s - HORIZON * BAR]
        test = df[(df["datetime"] >= s) & (df["datetime"] < e)]
        if len(train) < MIN_TRAIN_ROWS or test.empty or train["label3"].nunique() < 3:
            continue
        est = br.make_estimator("LogReg.glm", None, None)
        est.fit(train[feats], train["label3"])
        col = {c: k for k, c in enumerate(est.classes_)}

        def edge(x):
            p = est.predict_proba(x[feats])
            return p[:, col[2]] - p[:, col[0]]
        line = float(np.quantile(edge(train), 1 - TOP_SHARE))
        test = test.assign(edge=edge(test))
        picks = non_overlapping(test[test["edge"] >= line])
        every = non_overlapping(test)
        net = picks["fwd"] - cost
        bnet = every["fwd"] - cost
        name = f"{s.year}{'H1' if s.month <= 6 else 'H2'}"
        folds.append(dict(fold=name, train_rows=len(train), test_rows=len(test), coins=test["symbol"].nunique(),
                          trades=len(picks), net=float(net.mean()) if len(picks) else float("nan"),
                          won=float((net > 0).mean()) if len(picks) else float("nan"),
                          every=float(bnet.mean()) if len(every) else float("nan"), every_n=len(every)))
        trades.append(picks.assign(fold=name, net=net))
        base_trades.append(every.assign(fold=name, net=bnet))
        f = folds[-1]
        log(f"  {name}: trained on {len(train):,}, {f['trades']} trades at {f['net']*100:+.3f}% after cost, "
            f"every row {f['every']*100:+.3f}% on {f['every_n']}")
    T = pd.concat(trades) if trades else pd.DataFrame(columns=["net"])
    B = pd.concat(base_trades) if base_trades else pd.DataFrame(columns=["net"])
    F = pd.DataFrame(folds)
    elig = F[F["trades"] >= MIN_FOLD_TRADES]
    pos = int((elig["net"] > 0).sum())
    rate = pos / len(elig) if len(elig) else float("nan")
    mean = float(T["net"].mean()) if len(T) else float("nan")
    sd = float(T["net"].std(ddof=1)) if len(T) > 1 else float("nan")
    tstat = mean / (sd / np.sqrt(len(T))) if len(T) > 1 and sd > 0 else float("nan")
    k1 = len(elig) > 0 and rate >= PASS_RATE
    k2 = mean > 0
    by_coin = (T.groupby("symbol")["net"].agg(["size", "mean", "sum"]).sort_values("sum", ascending=False)
               if len(T) else pd.DataFrame())
    return dict(folds=F, trades=T, base=B, eligible=len(elig), positive=pos, rate=rate, mean=mean, sd=sd,
                tstat=tstat, base_mean=float(B["net"].mean()) if len(B) else float("nan"),
                k1=k1, k2=k2, by_coin=by_coin, band=band, cost=cost, rows=len(df),
                coins=df["symbol"].nunique(), first=df["datetime"].min(), last=df["datetime"].max(),
                seconds=time.time() - t0)


def write(res: dict, log=print) -> Path:
    stamp = datetime.now()
    day = OUT / f"{stamp:%Y-%m-%d}"
    day.mkdir(parents=True, exist_ok=True)
    md = mm.unclobbered(day / f"threeway-walkforward-{stamp:%Y%m%d-%H%M%S}.md")
    pct = lambda v: "n/a" if v != v else f"{v*100:+.3f}%"
    F = res["folds"]
    verdict = "SURVIVES" if res["k1"] and res["k2"] else "KILLED"
    why = []
    if not res["k1"]:
        why.append(f"{res['positive']} of {res['eligible']} eligible folds positive, "
                   f"{res['rate']:.0%} against the 60 per cent bar")
    if not res["k2"]:
        why.append(f"the mean trade made {pct(res['mean'])} after cost")
    L = [f"# Three-way outcome, kill harness, {stamp:%d %B %Y %H:%M}", "",
         f"The 4-hour panel, {res['rows']:,} screened rows on {res['coins']} coins from "
         f"{res['first']:%d %B %Y} to {res['last']:%d %B %Y}, was split into half-year folds. Each fold "
         f"was scored by a logistic regression trained on every earlier row, with a break-even band of "
         f"{res['band']*100:.2f} per cent and {res['cost']*100:.2f} per cent cost a trade. A trade was taken "
         f"when P(bullish) minus P(bearish) reached the training rows' own top fifth, and only once the "
         f"previous trade on that coin had run its 48 hours.", "",
         f"Verdict, {verdict}. " + ("Both kill criteria were cleared." if verdict == "SURVIVES"
                                    else "; ".join(why).capitalize() + "."), "",
         f"Across all folds {len(res['trades']):,} trades averaged {pct(res['mean'])} after cost, standard "
         f"deviation {pct(res['sd'])}, t = {res['tstat']:.2f}. Taking every screened row on the same "
         f"non-overlapping rule averaged {pct(res['base_mean'])} on {len(res['base']):,} trades, which is "
         f"what the market gave without the model.", "",
         "## Folds", "",
         "| fold | training rows | coins | trades | after cost | trades won | every row | every-row trades |",
         "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for r in F.itertuples():
        L.append(f"| {r.fold} | {r.train_rows:,} | {r.coins} | {r.trades} | {pct(r.net)} | "
                 f"{'n/a' if r.won != r.won else f'{r.won:.0%}'} | {pct(r.every)} | {r.every_n} |")
    L += ["", f"A fold is eligible with at least {MIN_FOLD_TRADES} trades. {res['eligible']} were eligible and "
          f"{res['positive']} of them were positive after cost.", "", "## Coins", "",
          "The ten coins that added most and the five that took most, summed after cost.", "",
          "| coin | trades | mean after cost | sum after cost |", "| --- | ---: | ---: | ---: |"]
    bc = res["by_coin"]
    if len(bc):
        for sym, r in pd.concat([bc.head(10), bc.tail(5)]).iterrows():
            L.append(f"| {sym} | {int(r['size'])} | {pct(r['mean'])} | {pct(r['sum'])} |")
        L += ["", f"{int((bc['sum'] > 0).sum())} of {len(bc)} coins summed above zero."]
    L += ["", f"Ran in {res['seconds']:.0f} seconds with `03-inputs/threeway_walkforward.py`, whose kill "
          f"criteria were fixed before the first run.", ""]
    md.write_text("\n".join(L) + "\n", encoding="utf-8")
    F.to_csv(md.with_suffix(".folds.csv"), index=False)
    log(f"record: {md.relative_to(REPO)}")
    return md


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--band", type=float, default=0.002, help="break-even half-width, share of price")
    ap.add_argument("--cost", type=float, default=0.002, help="cost per trade, share of price")
    a = ap.parse_args()
    res = run(a.band, a.cost)
    print(f"\nVERDICT: {'SURVIVES' if res['k1'] and res['k2'] else 'KILLED'}  "
          f"fold pass {res['positive']}/{res['eligible']} ({res['rate']:.0%}), "
          f"mean trade {res['mean']*100:+.3f}% after cost, t {res['tstat']:.2f}, "
          f"every row {res['base_mean']*100:+.3f}%")
    write(res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
