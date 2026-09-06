"""Track A Phase A3: the equity 1d frame, built through the Binance frame builder.

One adapter, not a fork: each Alpaca daily-bar parquet is reshaped into the
exact frame `build_dataset_1h.load_coin` produces, and `build_coin` then runs
unchanged, so every causal, scale-invariant feature family (wall-clock,
intraday, extra-TA, Supertrend, adaptive Supertrend, multi-timeframe weekly and
monthly context, regime state) transfers to equities without a second code path.

Equity-specific translations, each decided here and stamped in the manifest:

  market factor   SPY stands in the BTC seat, so in THIS dataset the f_btc_*
                  and f_rg_btc_* columns mean the SPY market factor. Column
                  names are kept so every downstream tool (candidate_signals,
                  the edge matrix, the kill harness) works unmodified.
  label           the crypto-swept +3/-1 ATR over 20 bars as the starting
                  geometry; ATR units self-scale to equity volatility, and the
                  A4 sweep re-tests it before any verdict.
  screen          dollar-volume floor 20M (matches the universe screen), ATR
                  band 1.0-8.0% (equities run a third of crypto's daily ATR;
                  the crypto 1d band of 2.5-12% would reject most large caps).
  quality gate    the crypto gap gate assumes bars every calendar day and would
                  read every weekend as a hole; here a symbol passes if it has
                  at least 97% of SPY's trading days over its own span and no
                  single hole longer than 10 trading days.
  flow/funding    absent for equities; those blocks contribute nothing, the
                  same pattern as flow-less coins.

Survivorship caveat inherited from the data layer: live names only, results
are upper bounds. No orders.

    .venv/bin/python inputs/build_dataset_equity.py [--symbols AAPL MSFT ...]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import build_dataset_1h as b1

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "alpaca-data"))
DAILY = os.path.join(ROOT, "daily")
DATASET = os.path.join(ROOT, "dataset_eq1d_allmarket.parquet")

LABEL_GEOMETRY = dict(tgt_atr=3.0, stp_atr=1.0, horizon_bars=20)
SCREEN_OVERRIDES = dict(min_quote_volume_usdt=20_000_000,
                        atr_floor_pct=1.0, atr_ceiling_pct=8.0)
MIN_PRESENCE = 0.97
MAX_HOLE_TDAYS = 10


def load_symbol(sym: str) -> pd.DataFrame:
    """One Alpaca parquet reshaped to the load_coin frame contract."""
    p = os.path.join(DAILY, f"{sym}.parquet")
    if not os.path.exists(p):
        return pd.DataFrame()
    try:
        d = pd.read_parquet(p)
    except Exception as e:  # noqa: BLE001  (truncated download or exFAT litter)
        print(f"  skip {sym}: unreadable parquet ({type(e).__name__})")
        return pd.DataFrame()
    ts = pd.to_datetime(d["datetime"], utc=True)
    d = d.assign(datetime=ts.dt.tz_convert("America/New_York").dt.normalize()
                 .dt.tz_localize(None))
    vwap = d["vwap"].where(d["vwap"] > 0, d["close"])
    out = pd.DataFrame({
        "datetime": d["datetime"],
        "open": d["open"].astype(float), "high": d["high"].astype(float),
        "low": d["low"].astype(float), "close": d["close"].astype(float),
        "volume": d["volume"].astype(float),
        "quote_volume": (vwap * d["volume"]).astype(float),   # dollar volume
        "num_trades": d["trade_count"].astype(float),
        "taker_buy_base": np.nan,                             # no equity equivalent
    })
    return (out.dropna(subset=["close", "volume"]).drop_duplicates("datetime")
            .sort_values("datetime").reset_index(drop=True))


def market_series() -> pd.Series:
    spy = load_symbol("SPY")
    if spy.empty:
        raise SystemExit("SPY parquet missing; run alpaca_data.py download --symbols SPY first")
    idx = pd.to_datetime(spy["datetime"]).astype("datetime64[ns]")
    return pd.Series(spy["close"].to_numpy(float), index=idx)


def calendar_quality(d: pd.DataFrame, tdays: pd.DatetimeIndex) -> tuple[bool, str]:
    span = tdays[(tdays >= d["datetime"].iloc[0]) & (tdays <= d["datetime"].iloc[-1])]
    if not len(span):
        return False, "no overlap with SPY calendar"
    presence = len(d) / len(span)
    pos = span.searchsorted(pd.to_datetime(d["datetime"]).to_numpy())
    hole = int(np.diff(pos).max()) if len(pos) > 1 else 1
    if presence < MIN_PRESENCE:
        return False, f"presence {presence:.2f} < {MIN_PRESENCE}"
    if hole > MAX_HOLE_TDAYS:
        return False, f"hole of {hole} trading days"
    return True, ""


def list_symbols() -> list[str]:
    return sorted(f[:-8] for f in os.listdir(DAILY)
                  if f.endswith(".parquet") and not f.startswith("._"))


def build(symbols: list[str] | None = None) -> pd.DataFrame:
    b1.configure("1d")
    b1.LABEL.update(LABEL_GEOMETRY)
    b1.SCREEN.update(SCREEN_OVERRIDES)
    spy = market_series()
    tdays = pd.DatetimeIndex(spy.index)
    symbols = symbols or list_symbols()
    min_needed = max(max(b1.WC["mom"]), b1.WC["rv_long"], b1.WC["bb"]) + b1.LABEL["horizon_bars"]
    frames, skipped = [], 0
    for sym in symbols:
        d = load_symbol(sym)
        if len(d) < min_needed:
            skipped += 1
            continue
        ok, why = calendar_quality(d, tdays)
        if not ok:
            print(f"  skip {sym}: {why}")
            skipped += 1
            continue
        coin = b1.build_coin(d, sym, None, spy)
        feat_cols = b1.feature_columns(coin)
        coin = coin.dropna(subset=[*feat_cols, "label", "trade_ret"])
        if len(coin):
            # ~2,700 equities against crypto's ~550: float32 halves the panel's
            # footprint so the concat fits an 8 GB machine. Rank/threshold
            # consumers are precision-insensitive at this scale.
            coin[feat_cols] = coin[feat_cols].astype("float32")
            coin["trade_ret"] = coin["trade_ret"].astype("float32")
            frames.append(coin)
    if not frames:
        raise SystemExit("no equities built; is the download complete?")
    data = pd.concat(frames, ignore_index=True)
    data["label"] = data["label"].astype(int)
    data["in_sample"] = data["in_sample"].astype(bool)
    print(f"built {data['symbol'].nunique()} equities ({skipped} skipped), "
          f"{len(data)} rows, {len(b1.feature_columns(data))} features, "
          f"base rate {data['label'].mean():.3f}")
    return data


def main() -> int:
    ap = argparse.ArgumentParser(description="Equity 1d dataset via the shared frame builder")
    ap.add_argument("--symbols", nargs="+", default=None)
    ap.add_argument("--out", default=DATASET)
    a = ap.parse_args()
    data = build(a.symbols)
    out = b1.write_frame(data, a.out)
    with open(os.path.join(ROOT, "dataset_manifest.json"), "w") as f:
        json.dump(dict(stamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                       rows=len(data), symbols=int(data["symbol"].nunique()),
                       features=len(b1.feature_columns(data)),
                       base_rate=round(float(data["label"].mean()), 4),
                       label=LABEL_GEOMETRY, screen=SCREEN_OVERRIDES,
                       market_factor="SPY (in f_btc_* column names)",
                       survivorship="live names only; upper bound"), f, indent=2)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
