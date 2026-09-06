"""Track A: separate operating companies from exchange-traded funds.

Why this exists (2026-08-25). The A2 universe screen enumerates
``AssetClass.US_EQUITY``, and Alpaca files every ETF, ETN and leveraged fund
under that class. Nothing downstream filtered them, so the 12-1 momentum book
that went live on 2026-08-18 bought SOXL (Direxion Daily Semiconductor Bull
3X), KORU (Direxion Daily MSCI South Korea Bull 3X) and MUU (Direxion Daily MU
Bull 2X). That is a charter conflict (never margin, never leveraged tokens)
AND a selection artifact: a 3x fund carries roughly 3x the trailing 12-month
return of its sector, so a momentum rank promotes leveraged funds
mechanically, in both directions.

Alpaca's Asset carries no ETF flag, so classification is by issuer/product
name, which is reliable for funds and very reliable for the leveraged subset.
Two tiers:

  is_fund      any pooled vehicle: ETF, ETN, closed-end fund, trust, index
  is_levered   the subset with embedded leverage or inverse exposure

Cached to inputs/alpaca-data/asset_classes.json so the panel builders and the
live book read the same list without re-querying the venue.

    .venv/bin/python inputs/equity_universe_filter.py refresh
    .venv/bin/python inputs/equity_universe_filter.py report
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CACHE = REPO / "03-inputs" / "alpaca-data" / "asset_classes.json"

# Issuer and product markers. Ordinary operating companies do not carry these.
_ISSUER_PAT = re.compile(
    r"\b(iShares|SPDR|ProShares|Direxion|Invesco|Vanguard|VanEck|Global X"
    r"|WisdomTree|First Trust|Xtrackers|Schwab Strategic|Franklin FTSE"
    r"|JPMorgan Exchange|Amplify|Roundhill|YieldMax|Defiance|Simplify"
    r"|Innovator|Pacer|ALPS|Sprott|abrdn|Grayscale|Bitwise|Fidelity Wise"
    r"|PIMCO|Janus Henderson|Dimensional|KraneShares|ARK ETF|Tidal)\b", re.I)
# Explicit vehicle markers: unambiguous, no operating company uses them.
_VEHICLE_PAT = re.compile(
    r"\b(ETF|ETN|ETV|ETP|Exchange[- ]Traded|Index Fund|Closed[- ]End"
    r"|Unit Investment|Depositary Receipt)\b", re.I)
# Bare "Trust"/"Fund"/"Portfolio" is ambiguous: every equity REIT and several
# banks carry it (Vornado Realty Trust, Northern Trust Corporation). Treat it
# as a fund marker ONLY when no operating-company marker is also present.
_WEAK_PAT = re.compile(r"\b(Trust|Fund|Portfolio)\b", re.I)
_OPERATING_PAT = re.compile(
    r"\b(Realty|Properties|Property|Hotel|Residential|Industrial|Storage"
    r"|Communities|Centers|Healthcare|Corporation|Corp\.?|Incorporated"
    r"|Inc\.?|Bancorp|Bancshares|Group|Holdings|Company|Partners)\b", re.I)
# Leverage / inverse markers. "Bull 3X" is the Direxion house style; "Ultra",
# "UltraPro", "Short" and "Bear" are the ProShares one.
_LEV_PAT = re.compile(
    r"(\b\d(\.\d)?X\b|\bUltraPro\b|\bUltra\b|\bBull\b|\bBear\b"
    r"|\bInverse\b|\bLeveraged\b|\bShort\b|\b-1X\b)", re.I)


def classify(name: str) -> tuple[bool, bool]:
    """(is_fund, is_levered) from the asset's registered name."""
    name = name or ""
    fund = bool(_ISSUER_PAT.search(name) or _VEHICLE_PAT.search(name))
    if not fund and _WEAK_PAT.search(name) and not _OPERATING_PAT.search(name):
        fund = True          # e.g. "United States Oil Fund, LP"
    lev = fund and bool(_LEV_PAT.search(name))
    return fund, lev


def refresh() -> dict:
    """Query the venue once and cache symbol -> {name, fund, levered}."""
    sys.path.insert(0, str(REPO / "03-inputs"))
    import config
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import GetAssetsRequest
    from alpaca.trading.enums import AssetClass, AssetStatus

    key = (os.environ.get("ALPACA_API_KEY") or config.ALPACA_API_KEY).strip()
    sec = (os.environ.get("ALPACA_API_SECRET") or config.ALPACA_API_SECRET).strip()
    tc = TradingClient(key, sec, paper=True)
    assets = tc.get_all_assets(GetAssetsRequest(
        asset_class=AssetClass.US_EQUITY, status=AssetStatus.ACTIVE))
    out = {}
    for a in assets:
        fund, lev = classify(a.name)
        out[a.symbol] = dict(name=a.name, fund=fund, levered=lev,
                             exchange=str(a.exchange).rsplit(".", 1)[-1])
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(out))
    print(f"cached {len(out)} assets -> {CACHE}  "
          f"funds={sum(v['fund'] for v in out.values())}  "
          f"levered={sum(v['levered'] for v in out.values())}")
    return out


def load() -> dict:
    if not CACHE.exists():
        return refresh()
    return json.loads(CACHE.read_text())


def fund_symbols(levered_only: bool = False) -> set[str]:
    m = load()
    k = "levered" if levered_only else "fund"
    return {s for s, v in m.items() if v[k]}


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    if cmd == "refresh":
        refresh()
        return
    m = load()
    lev = sorted(s for s, v in m.items() if v["levered"])
    print(f"assets classified: {len(m)}")
    print(f"funds: {sum(v['fund'] for v in m.values())}   "
          f"levered/inverse: {len(lev)}")
    print("\nfirst 20 levered:", ", ".join(lev[:20]))


if __name__ == "__main__":
    main()
