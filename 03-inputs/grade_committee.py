"""Grade the TradingAgents committee's ratings against what the market did.

WHY THIS EXISTS. The committee produced eight ratings on 16 August 2026 and none
was ever scored. A rating nobody grades is an opinion, not a signal, and the
whole reason for journalling them was to put them on the same after-fee,
out-of-sample bar as every other candidate in this repository.

WHAT IT ASKS, three separate questions, because a rating can be right in one
sense and useless in another.

  direction   Underweight and Sell say the thing will fall. Did it fall?
  selection   Underweight also says "hold less of this than of the market". Did
              it underperform the benchmark? On this book the benchmark is
              bitcoin, matching the benchmark_ticker the wrapper configures.
  spread      A rating carries information only if the coins it liked beat the
              coins it disliked. If every rating is the same, the set has no
              spread and cannot be traded whatever its accuracy.

WHAT IT CANNOT ANSWER. Eight ratings on one day is not a sample. The result
below is a first read that decides whether the layer is worth more API spend,
never a verdict on the framework.

    .venv/bin/python 03-inputs/grade_committee.py
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model_metrics as mm      # noqa: E402

LOG = mm.REPO / "05-research" / "memory" / "ta-decisions.md"
BENCH = "BTC/USDT"

# The wrapper's Yahoo-collision overrides, so a rating maps back to the pair we trade.
PAIR = {"BTC-USD": "BTC/USDT", "ETH-USD": "ETH/USDT", "SOL-USD": "SOL/USDT",
        "SUI20947-USD": "SUI/USDT", "DOGE-USD": "DOGE/USDT", "NEAR-USD": "NEAR/USDT",
        "PEPE24478-USD": "PEPE/USDT", "PEPE-USD": "PEPE/USDT"}

# What each rating claims will happen, as a sign. Hold claims nothing.
CLAIM = {"Buy": +1, "Overweight": +1, "Hold": 0, "Underweight": -1, "Sell": -1}


def read_ratings(path=LOG) -> pd.DataFrame:
    text = open(path, errors="ignore").read()
    rows = []
    for block in text.split("<!-- ENTRY_END -->"):
        m = re.search(r"\[(\d{4}-\d{2}-\d{2}) \| ([^|]+) \| ([^|]+) \| ([^\]]+)\]", block)
        if not m:
            continue
        tgt = re.search(r"\*\*Price Target\*\*:\s*([0-9.eE+-]+)", block)
        hor = re.search(r"\*\*Time Horizon\*\*:\s*(.+)", block)
        rows.append(dict(date=m.group(1), symbol=m.group(2).strip(),
                         rating=m.group(3).strip(), status=m.group(4).strip(),
                         target=float(tgt.group(1)) if tgt else float("nan"),
                         horizon=hor.group(1).strip() if hor else ""))
    return pd.DataFrame(rows)


def fetch(pairs, start, days=40) -> dict:
    import ccxt
    ex = ccxt.binance({"enableRateLimit": True})
    since = ex.parse8601(f"{start}T00:00:00Z")
    out = {}
    for p in sorted(set(pairs)):
        o = ex.fetch_ohlcv(p, "1d", since=since, limit=days)
        d = pd.DataFrame(o, columns=["ts", "o", "h", "l", "c", "v"])
        d["date"] = pd.to_datetime(d.ts, unit="ms").dt.strftime("%Y-%m-%d")
        out[p] = d.set_index("date")["c"]
    return out


def grade(rat: pd.DataFrame, px: dict) -> pd.DataFrame:
    rows = []
    bench = px[BENCH]
    for _, r in rat.iterrows():
        pair = PAIR.get(r.symbol)
        if pair is None or pair not in px:
            continue
        s = px[pair]
        entry_dates = [d for d in s.index if d >= r.date]
        if not entry_dates:
            continue
        d0, d1 = entry_dates[0], s.index[-1]
        p0, p1 = float(s[d0]), float(s[d1])
        b0, b1 = float(bench[d0]), float(bench[d1])
        ret = (p1 / p0 - 1) * 100
        bret = (b1 / b0 - 1) * 100
        rel = ret - bret
        claim = CLAIM.get(r.rating, 0)
        rows.append(dict(
            symbol=r.symbol, pair=pair, rating=r.rating, claim=claim,
            entry=p0, latest=p1, target=r.target,
            ret_pct=ret, bench_pct=bret, rel_pct=rel,
            # Underweight/Sell is right on direction if the price fell.
            direction_right=(claim < 0 and ret < 0) or (claim > 0 and ret > 0) if claim else None,
            # And right on selection if it underperformed the benchmark.
            selection_right=(claim < 0 and rel < 0) or (claim > 0 and rel > 0) if claim else None,
            # Did price move toward the stated target, or away from it?
            toward_target=(abs(p1 - r.target) < abs(p0 - r.target)) if pd.notna(r.target) else None,
            horizon=r.horizon, days=(pd.Timestamp(d1) - pd.Timestamp(d0)).days))
    return pd.DataFrame(rows)


def write_record(g: pd.DataFrame, out_dir) -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    day = os.path.join(str(out_dir), datetime.now().strftime("%Y-%m-%d"))
    os.makedirs(day, exist_ok=True)
    path = os.path.join(day, f"committee-grading-{stamp}.md")
    graded = g[g["claim"] != 0]
    n = len(graded)
    dir_hit = int(graded["direction_right"].sum())
    sel_hit = int(graded["selection_right"].sum())
    tgt_hit = int(g["toward_target"].astype("boolean").fillna(False).sum())

    # The question the operator actually asked: did listening help or hurt? The
    # summaries asked for trims of 25 to 40 per cent on Underweight, so 30 is the
    # midpoint, and a Sell exits. PEPE is deduplicated first, because the Yahoo
    # collision put the same coin in the set twice and would double count it.
    u = g.drop_duplicates(subset="pair", keep="first").copy()
    u["trim"] = u["rating"].map({"Underweight": 0.30, "Sell": 1.00, "Hold": 0.0}).fillna(0.0)
    held = float(u["ret_pct"].mean())
    followed = float((u["ret_pct"] * (1 - u["trim"])).mean())
    days = int(g["days"].max())

    L = [f"# Grading the committee's August ratings ({datetime.now():%d %B %Y})\n",
         f"Eight ratings were produced on 16 August 2026 and never scored. This is the first "
         f"scoring, {days} days later, against Binance daily closes.\n",
         "Three questions are asked separately. **Direction** asks whether a coin the committee "
         "wanted less of actually fell. **Selection** asks whether it underperformed bitcoin, which "
         "is the benchmark the wrapper configures and the only question that matters to a book that "
         "must hold something. **Spread** asks whether the ratings distinguished between coins at "
         "all, because a set of identical ratings carries no information however accurate it is.\n",
         "## Every rating\n",
         "| coin | rating | price on 16 Aug | price now | its move | bitcoin's move | versus bitcoin | fell? | lagged bitcoin? |",
         "| --- | --- | ---: | ---: | ---: | ---: | ---: | :-: | :-: |"]
    for _, r in g.iterrows():
        tick = lambda b: "-" if b is None or pd.isna(b) else ("yes" if b else "no")
        L.append(f"| {r['pair'].replace('/USDT','')} | {r['rating']} | {r['entry']:,.6g} | "
                 f"{r['latest']:,.6g} | {r['ret_pct']:+.1f}% | {r['bench_pct']:+.1f}% | "
                 f"{r['rel_pct']:+.1f}% | {tick(r['direction_right'])} | {tick(r['selection_right'])} |")

    L.append("\n## The score\n")
    L.append(f"- **Direction: {dir_hit} of {n}.** The committee asked for less of {n} coins. "
             f"{dir_hit} of them fell.")
    L.append(f"- **Selection: {sel_hit} of {n}.** {sel_hit} of them underperformed bitcoin.")
    L.append(f"- **Price targets: {tgt_hit} of {len(g)}.** Price moved toward the stated target in "
             f"{tgt_hit} cases and away from it in {len(g)-tgt_hit}.")
    L.append(f"\n**What listening would have cost.** An equal-weight basket of the "
             f"{len(u)} distinct coins, simply held, returned {held:+.2f} per cent over the window. "
             f"Trimming each position as the committee asked, 30 per cent on Underweight and a full "
             f"exit on Sell, returned {followed:+.2f} per cent. Following the committee cost "
             f"{followed-held:+.2f} percentage points in {days} days, before any fee for making "
             f"the trims.")

    counts = g["rating"].value_counts()
    L.append("\n## Spread\n")
    L.append("| rating | count |")
    L.append("| --- | ---: |")
    for k, v in counts.items():
        L.append(f"| {k} | {v} |")
    bear = int(sum(v for k, v in counts.items() if CLAIM.get(k, 0) < 0))
    L.append(f"\n{bear} of {len(g)} ratings were bearish and none was bullish. A rating that never "
             f"varies cannot rank one coin above another, so even a perfect hit rate would leave a "
             f"long-only book with nothing to act on.\n")

    best = g.loc[g["rel_pct"].idxmax()]
    worst = g.loc[g["rel_pct"].idxmin()]
    L.append(f"Best and worst against bitcoin: {best['pair'].replace('/USDT','')} at "
             f"{best['rel_pct']:+.1f}% and {worst['pair'].replace('/USDT','')} at "
             f"{worst['rel_pct']:+.1f}%, both rated {best['rating']} and {worst['rating']} "
             f"respectively.\n")

    L.append("## Caveats that would change the reading\n")
    L.append("1. Eight ratings on one day is not a sample. Nothing here is a verdict on the "
             "framework; it decides whether the layer earns more API spend.")
    L.append(f"2. Several stated horizons have not elapsed. The bitcoin call was written for "
             f"two to four months and has had {days} days. The Solana call, at two to four weeks, "
             f"is the only one comfortably inside its own window.")
    L.append("3. Two entries rate the same asset. `PEPE-USD` and `PEPE24478-USD` are both PEPE, "
             "the second being a Yahoo ticker-collision override, and the committee gave them "
             "different ratings in the same run.")
    L.append("4. No fee is charged here because no trade was placed. Any real use of these ratings "
             "would pay the same round trip as everything else, which is the bar that has killed "
             "every other crypto candidate.\n")

    csv = os.path.join(day, f"committee-grading-{stamp}.csv")
    g.to_csv(csv, index=False)
    L.append(f"Full table: `{os.path.relpath(csv, mm.REPO)}`\n")
    open(path, "w").write("\n".join(L) + "\n")
    return path


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default=str(mm.EVALS))
    a = p.parse_args()
    rat = read_ratings()
    print(f"{len(rat)} ratings read from {LOG.relative_to(mm.REPO)}")
    px = fetch([PAIR[s] for s in rat.symbol if s in PAIR] + [BENCH], rat.date.min())
    g = grade(rat, px)
    print(g[["symbol", "rating", "ret_pct", "bench_pct", "rel_pct",
             "direction_right", "selection_right"]].to_string(index=False))
    print("\nrecord:", write_record(g, a.out))


if __name__ == "__main__":
    main()
