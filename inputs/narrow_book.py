"""Narrow tradeable book: rank broadly, trade narrowly.

The attribution record shows the gated cross-sectional edge is carried by a
minority of coins (23/59 positive on 2026-08-16, top five carrying 30pp) while
reliable bleeders (SOL, XRP, PEPE) rank into the cohort and lose money. This
script intersects the two evidence sources and writes the whitelist that the
execution layer (trade_binance.py) enforces on entries:

  1. Historical carriers: coins with positive OOS gate-on contribution AND at
     least MIN_APPEARANCES cohort memberships (one-shot wonders are lottery
     tickets, not evidence), from edge_attribution.attribution().
  2. Live executability: pairs currently passing the candidate screen's
     liquidity floor (24h quote volume >= 30M USDT).

Criteria are decided a priori and recorded in the output; membership is
re-derived, never hand-edited. Rerun after each new attribution record.

    .venv/bin/python inputs/narrow_book.py --interval 4h --signal f_d1_st_up --gate btc+breadth
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone

import pandas as pd

import candidate_screen as screen
import edge_attribution as attr
import train_model as tm

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BOOK_PATH = os.path.join(REPO, "memory", "narrow-book.json")

MIN_APPEARANCES = 3     # a priori: contribution must rest on repeated membership
MIN_QV_USDT = 30e6      # the repo-standard liquidity floor


def build(interval: str, signal: str, gate: str, cost_pct: float) -> dict:
    g = attr.attribution(interval, signal, gate, cost_pct)
    carriers = g[(g["contrib_pct"] > 0) & (g["appearances"] >= MIN_APPEARANCES)]

    t = screen.fetch()
    t = t[t["symbol"].str.endswith("USDT")]
    for c in ("quoteVolume", "lastPrice"):
        t[c] = pd.to_numeric(t[c], errors="coerce")
    liquid = set(t.loc[t["quoteVolume"] >= MIN_QV_USDT, "symbol"])

    rows = []
    for slash_sym, r in carriers.iterrows():
        binance_pair = slash_sym.replace("/", "")
        rows.append({
            "pair": binance_pair,
            "appearances": int(r["appearances"]),
            "mean_net_pct": float(r["mean_net_pct"]),
            "win_rate": float(r["win_rate"]),
            "contrib_pct": float(r["contrib_pct"]),
            "liquid_now": binance_pair in liquid,
        })
    book = sorted((r for r in rows if r["liquid_now"]),
                  key=lambda r: -r["contrib_pct"])
    dropped = sorted((r for r in rows if not r["liquid_now"]),
                     key=lambda r: -r["contrib_pct"])
    return {
        "stamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "evidence": {"interval": interval, "signal": signal, "gate": gate,
                     "cost_pct": cost_pct, "min_appearances": MIN_APPEARANCES,
                     "min_qv_usdt": MIN_QV_USDT},
        "book": book,
        "dropped_illiquid": dropped,
    }


def load_book() -> list[str] | None:
    """Whitelisted Binance pairs, or None when no book has been built."""
    if not os.path.exists(BOOK_PATH):
        return None
    return [r["pair"] for r in json.load(open(BOOK_PATH))["book"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", default="4h")
    ap.add_argument("--signal", default="f_d1_st_up")
    ap.add_argument("--gate", default="btc+breadth")
    ap.add_argument("--cost", type=float, default=tm.COST_PCT)
    args = ap.parse_args()

    res = build(args.interval, args.signal, args.gate, args.cost)
    with open(BOOK_PATH, "w") as f:
        json.dump(res, f, indent=2)

    pd.set_option("display.width", 160)
    print(f"\nNARROW BOOK ({len(res['book'])} pairs) -> {BOOK_PATH}")
    if res["book"]:
        print(pd.DataFrame(res["book"]).to_string(index=False))
    if res["dropped_illiquid"]:
        print(f"\ndropped for liquidity ({len(res['dropped_illiquid'])}): "
              + ", ".join(r["pair"] for r in res["dropped_illiquid"]))


if __name__ == "__main__":
    main()
