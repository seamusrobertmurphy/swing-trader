"""Live fee-adjusted candidate screen over every Binance USDT spot pair.

One keyless request ranks the whole market by how much raw movement a coin
offers per fee paid: potential = daily range %% / round-trip cost. A coin
whose typical day moves 6%% offers 15x the 0.4%% toll; a majors-only 1.5%%
day offers under 4x. Liquidity floor keeps the book executable.

    .venv/bin/python inputs/candidate_screen.py [--min-qv 30e6] [--top 20]
"""

from __future__ import annotations

import argparse

import pandas as pd
import requests

URLS = ("https://api.binance.com/api/v3/ticker/24hr",
        "https://data-api.binance.vision/api/v3/ticker/24hr")
ROUND_TRIP = 0.004  # 0.2% cost x2 legs of a same-day range capture (conservative)


def fetch() -> pd.DataFrame:
    last = None
    for url in URLS:
        try:
            r = requests.get(url, timeout=20)
            if r.ok:
                return pd.DataFrame(r.json())
        except requests.RequestException as e:
            last = e
    raise SystemExit(f"no 24hr stats: {last}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-qv", type=float, default=30e6,
                    help="min 24h quote volume USDT (screen liquidity floor)")
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    t = fetch()
    t = t[t["symbol"].str.endswith("USDT")]
    for c in ("quoteVolume", "highPrice", "lowPrice", "lastPrice", "count"):
        t[c] = pd.to_numeric(t[c], errors="coerce")
    t = t[(t["quoteVolume"] >= args.min_qv) & (t["lastPrice"] > 0) & (t["count"] > 10000)]
    t["range_pct"] = (t["highPrice"] - t["lowPrice"]) / t["lastPrice"] * 100
    t["potential"] = t["range_pct"] / (ROUND_TRIP * 100)
    out = (t[["symbol", "lastPrice", "quoteVolume", "range_pct", "potential"]]
           .sort_values("potential", ascending=False).head(args.top))
    out["quoteVolume"] = (out["quoteVolume"] / 1e6).round(1)
    out.columns = ["symbol", "last", "qv_musdt", "day_range_pct", "range_per_fee"]
    pd.set_option("display.width", 160)
    print(out.to_string(index=False, float_format=lambda v: f"{v:.4g}"))
    print(f"\n{len(t)} pairs pass the {args.min_qv/1e6:.0f}M USDT liquidity floor; "
          f"potential = 24h range %% / {ROUND_TRIP*100:.1f}%% round trip.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
