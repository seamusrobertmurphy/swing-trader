"""Fetch Binance USDT-perp funding-rate history from the public archive.

Funding rates are a direct, mechanical read on positioning: perpetual longs pay
shorts when the perp trades rich to spot, and vice versa. Sustained positive
funding marks crowded longs; deeply negative funding marks capitulation. This
is information the spot-price pipeline cannot derive, intended as a candidate
regime/feature family (f_fund_*) for the daily frame.

Source: data.binance.vision futures/um monthly fundingRate zips (one small file
per symbol-month, keyless). Resumable: existing files are skipped. 404 means
the contract did not exist that month, which is expected and skipped silently.

    .venv/bin/python inputs/fetch_funding.py BTC ETH SOL ...
"""

import sys
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent / "binance-data" / "funding"
URL = ("https://data.binance.vision/data/futures/um/monthly/fundingRate/"
       "{pair}/{pair}-fundingRate-{ym}.zip")
START = (2019, 9)  # Binance UM futures launch


def months():
    y, m = START
    today = date.today()
    while (y, m) <= (today.year, today.month):
        yield f"{y}-{m:02d}"
        m += 1
        if m > 12:
            y, m = y + 1, 1


# Sub-cent coins trade UM futures as thousand-unit contracts.
_THOUSAND = {"PEPE", "SHIB", "BONK", "FLOKI", "SATS", "RATS", "LUNC", "XEC"}


def fetch(base: str) -> tuple[int, int]:
    b = base.upper()
    pair = f"1000{b}USDT" if b in _THOUSAND else f"{b}USDT"
    out = ROOT / pair
    out.mkdir(parents=True, exist_ok=True)
    got = missing = 0
    for ym in months():
        dest = out / f"{pair}-fundingRate-{ym}.zip"
        if dest.exists():
            got += 1
            continue
        r = requests.get(URL.format(pair=pair, ym=ym), timeout=30)
        if r.status_code == 404:
            missing += 1
            continue
        r.raise_for_status()
        dest.write_bytes(r.content)
        got += 1
    return got, missing


def main() -> int:
    bases = sys.argv[1:] or ["BTC", "ETH", "SOL", "SUI", "TON", "DOGE", "NEAR", "PEPE"]
    for b in bases:
        got, missing = fetch(b)
        print(f"{b.upper()}USDT: {got} months on disk, {missing} pre-listing months absent",
              flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
