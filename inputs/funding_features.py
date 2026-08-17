"""Funding-rate features (f_fund_*) from the Binance UM archive in binance-data/funding/.

Perpetual funding is mechanically forced crowding information: longs pay shorts
when the perp trades rich to spot. Neutral is 0.01% per 8h payment (0.0003/day).
Sustained rich funding marks crowded longs; deeply negative funding marks
capitulation. None of this is derivable from spot price.

Two products, both causal (a daily row uses only payments stamped that day or
earlier; payments land 00/08/16 UTC, before the daily close):

  per_coin(base)      daily frame: f_fund_day (sum of the day's payments),
                      f_fund_7d / f_fund_30d (rolling means of the daily sum),
                      f_fund_pctl (7d mean's percentile in its trailing year).
  market(bases)       cross-coin mean of f_fund_7d -> the crowding gate series;
                      gate open when funding is at or below ``crowded`` (default
                      2x neutral, i.e. 0.0006/day).

Coverage note: features exist only for coins present in the funding archive
(the tradeable-8 as of 2026-08-16). Joins elsewhere yield NaN, so treat
per-coin funding as a majors-only ranker until the full-universe pull lands.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent / "binance-data" / "funding"
NEUTRAL_DAILY = 0.0003          # 3 x 0.01% payments
DEFAULT_CROWDED = 2 * NEUTRAL_DAILY


def _pair_dir(base: str) -> Path | None:
    for cand in (f"{base.upper()}USDT", f"1000{base.upper()}USDT"):
        d = ROOT / cand
        if d.is_dir():
            return d
    return None


def load_payments(base: str) -> pd.DataFrame:
    """All funding payments for one coin: columns ts (UTC), rate."""
    d = _pair_dir(base)
    if d is None:
        raise FileNotFoundError(f"no funding archive for {base} under {ROOT}")
    frames = []
    for z in sorted(d.glob("*.zip")):
        with zipfile.ZipFile(z) as zf:
            frames.append(pd.read_csv(zf.open(zf.namelist()[0])))
    if not frames:
        # An empty dir is a partial/failed fetch (the full-universe pull creates
        # dirs before their first zip lands); treat as absent, not as a crash.
        raise FileNotFoundError(f"funding archive for {base} is empty at {d}")
    raw = pd.concat(frames, ignore_index=True)
    return pd.DataFrame({
        "ts": pd.to_datetime(raw["calc_time"], unit="ms"),
        "rate": raw["last_funding_rate"].astype(float),
    }).sort_values("ts").reset_index(drop=True)


def per_coin(base: str) -> pd.DataFrame:
    """Daily f_fund_* features for one coin, indexed by date."""
    p = load_payments(base)
    daily = p.set_index("ts")["rate"].resample("1D").sum().rename("f_fund_day").to_frame()
    daily["f_fund_7d"] = daily["f_fund_day"].rolling(7, min_periods=3).mean()
    daily["f_fund_30d"] = daily["f_fund_day"].rolling(30, min_periods=10).mean()
    daily["f_fund_pctl"] = daily["f_fund_7d"].rolling(365, min_periods=60).rank(pct=True)
    daily.index.name = "date"
    return daily


def market(bases: list[str] | None = None) -> pd.DataFrame:
    """Cross-coin mean daily funding: the market crowding series.

    Returns date-indexed frame with market_fund_7d and gate_open (True when
    funding is not crowded-long, i.e. <= DEFAULT_CROWDED).
    """
    bases = bases or sorted(p.name.replace("1000", "").replace("USDT", "")
                            for p in ROOT.iterdir() if p.is_dir())
    cols = {}
    for b in bases:
        try:
            cols[b] = per_coin(b)["f_fund_7d"]
        except FileNotFoundError:
            continue
    wide = pd.DataFrame(cols)
    out = pd.DataFrame({"market_fund_7d": wide.mean(axis=1)})
    out["gate_open"] = out["market_fund_7d"] <= DEFAULT_CROWDED
    return out


if __name__ == "__main__":
    m = market()
    recent = m.tail(5)
    print(recent)
    btc = per_coin("BTC").tail(3)
    print(btc)
