"""
2A - Universe selection, the four-gate screen (Chapter Two, Controls).

Standalone workbench copy of the screen module. Canonical version lives in the
controls notebook (02-swing-controls.ipynb, cells defining screen_coin / run_screen
/ screen_scatter). Develop here in isolation, fold refinements back into the notebook.

The four gates, scan wide and hold few:
  liquidity  - 24h quote volume in USDT clears a floor       (hard gate)
  atr_band   - latest ATR(14)% sits inside the tradable band (lively, not detonating)
  spread     - top-of-book spread under the ceiling          (fee is the binding cost)
  history    - enough candles to have lived through regimes  (sufficiency)

Output: a dated sample table. With the wiring below it lands as
        outputs/CSV/2A-sample_YYYYMMDD.csv and the scatter as
        outputs/PNG/2A-screen_YYYYMMDD.png.

Run:  python screen.py        (live if ccxt is reachable, else synthetic, offline-safe)
"""

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import ccxt
except ImportError:
    ccxt = None

# CONFIG subset mirrored from the notebook CONFIG (cell 4). Notebook is canonical.
CONFIG = dict(
    atr_length            = 14,
    atr_floor_pct         = 2.5,
    atr_ceiling_pct       = 12.0,
    min_quote_volume_usdt = 30_000_000,
    max_spread_pct        = 0.05,
    min_history           = 120,
    history_limit         = 180,
    scan_top_n            = 25,
)

# Resolve the repo's outputs/ folder from this file's location
# (outputs/2A-universe-screen/screen.py -> outputs/).
OUTPUTS = Path(__file__).resolve().parent.parent


def synthetic_ohlcv(symbol, n=None, seed=None):
    n = n or CONFIG["history_limit"]
    s = abs(hash(symbol)) % (2 ** 32) if seed is None else seed
    rng = np.random.default_rng(s)
    dv = float(rng.uniform(0.01, 0.10))
    rets = rng.normal(0, dv, n)
    close = 100 * np.exp(np.cumsum(rets))
    high = close * (1 + np.abs(rng.normal(0, dv / 2, n)))
    low = close * (1 - np.abs(rng.normal(0, dv / 2, n)))
    openp = np.r_[close[0], close[:-1]]
    vol = rng.uniform(1e6, 5e6, n)
    idx = pd.date_range("2025-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {"open": openp, "high": high, "low": low, "close": close, "volume": vol},
        index=idx,
    )


def _exchange():
    return ccxt.binance() if ccxt is not None else None


def fetch_daily(symbol, limit=None):
    limit = limit or CONFIG["history_limit"]
    ex = _exchange()
    if ex is not None:
        try:
            bars = ex.fetch_ohlcv(symbol, timeframe="1d", limit=limit)
            df = pd.DataFrame(
                bars[:-1],
                columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            return df.set_index("timestamp")
        except Exception:
            pass
    return synthetic_ohlcv(symbol, n=limit)


def fetch_quote_volume(symbol):
    ex = _exchange()
    if ex is not None:
        try:
            return float(ex.fetch_ticker(symbol).get("quoteVolume") or 0.0)
        except Exception:
            pass
    return float(np.random.default_rng(abs(hash(symbol)) % 2 ** 32).uniform(2e6, 2.5e8))


def fetch_spread_pct(symbol):
    ex = _exchange()
    if ex is not None:
        try:
            ob = ex.fetch_order_book(symbol, limit=5)
            bid, ask = ob["bids"][0][0], ob["asks"][0][0]
            mid = (bid + ask) / 2
            return (ask - bid) / mid * 100.0
        except Exception:
            pass
    return float(np.random.default_rng(abs(hash(symbol)) % 2 ** 32 + 7).uniform(0.005, 0.12))


def build_universe(top_n=None):
    top_n = top_n or CONFIG["scan_top_n"]
    ex = _exchange()
    if ex is not None:
        try:
            tk = ex.fetch_tickers()
            usdt = [(s, d.get("quoteVolume") or 0) for s, d in tk.items()
                    if s.endswith("/USDT") and ":" not in s]
            uni = [s for s, _ in sorted(usdt, key=lambda x: -x[1])[:top_n]]
            if uni:
                return uni
        except Exception:
            pass
    print("(offline) using synthetic demo universe")
    return ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT",
            "AVAX/USDT", "LINK/USDT", "LTC/USDT", "DOGE/USDT", "TRX/USDT", "DOT/USDT"]


def compute_atr_pct(df, length=None):
    """Local copy of the ATR% calc; the canonical band view is 2B/atr_band.py."""
    length = length or CONFIG["atr_length"]
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([(h - l).abs(), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    atr = tr.rolling(length).mean()
    return (atr / c) * 100.0


def screen_coin(symbol, cfg=CONFIG):
    """Run the four gates on one coin. Liquidity first (cheap, hard); every number
    is recorded for the table either way."""
    df = fetch_daily(symbol, cfg["history_limit"])
    candle_count = int(len(df))
    quote_vol = fetch_quote_volume(symbol)
    spread = fetch_spread_pct(symbol)
    atr_series = compute_atr_pct(df, cfg["atr_length"])
    atr_pct = float(atr_series.iloc[-1]) if atr_series.notna().any() else float("nan")

    g1 = quote_vol >= cfg["min_quote_volume_usdt"]
    g2 = (cfg["atr_floor_pct"] <= atr_pct <= cfg["atr_ceiling_pct"]) if atr_pct == atr_pct else False
    g3 = spread <= cfg["max_spread_pct"]
    g4 = candle_count >= cfg["min_history"]
    gates = {"liquidity": bool(g1), "atr_band": bool(g2), "spread": bool(g3), "history": bool(g4)}
    passed = all(gates.values())
    fail = "" if passed else ",".join(k for k, v in gates.items() if not v)
    return {"symbol": symbol,
            "quote_volume_24h_usdt": round(quote_vol, 0),
            "atr_pct": round(atr_pct, 3),
            "spread_pct": round(spread, 4),
            "candle_count": candle_count,
            "pass": bool(passed), "fail_reason": fail, **gates}


def run_screen(universe, cfg=CONFIG, save=True):
    rows = []
    for s in universe:
        try:
            rows.append(screen_coin(s, cfg))
        except Exception as e:
            print("skip", s, type(e).__name__, str(e)[:60])
    tab = (pd.DataFrame(rows)
           .sort_values(["pass", "quote_volume_24h_usdt"], ascending=[False, False])
           .reset_index(drop=True))
    if save and len(tab):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        out = OUTPUTS / "CSV"
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"2A-sample_{stamp}.csv"
        tab.to_csv(path, index=False)
        print(f"saved {path}  ({int(tab['pass'].sum())} of {len(tab)} passed)")
    return tab


def screen_scatter(tab, cfg=CONFIG):
    """Liquidity vs volatility scatter; survivors inside the band, above the floor.
    Imports plotly lazily."""
    import plotly.graph_objects as go

    passed = tab[tab["pass"]]
    failed = tab[~tab["pass"]]
    fig = go.Figure()
    for d, name, col in [(failed, "rejected", "#B22222"), (passed, "sample", "#2E8B57")]:
        if len(d):
            fig.add_trace(go.Scatter(
                x=d["atr_pct"], y=d["quote_volume_24h_usdt"], mode="markers+text",
                text=d["symbol"].str.replace("/USDT", ""), textposition="top center",
                textfont=dict(size=9), name=name,
                marker=dict(size=11, color=col, opacity=0.8,
                            line=dict(width=1, color="white"))))
    fig.add_vrect(x0=cfg["atr_floor_pct"], x1=cfg["atr_ceiling_pct"],
                  fillcolor="#2E8B57", opacity=0.07, line_width=0)
    fig.add_vline(x=cfg["atr_floor_pct"], line=dict(color="#2E8B57", dash="dash"))
    fig.add_vline(x=cfg["atr_ceiling_pct"], line=dict(color="#B22222", dash="dash"))
    fig.add_hline(y=cfg["min_quote_volume_usdt"], line=dict(color="#888", dash="dot"),
                  annotation_text="liquidity floor", annotation_position="bottom right")
    fig.update_layout(
        title="Selection screen - liquidity vs volatility (survivors inside the band)",
        template="plotly_white", height=440, yaxis_type="log",
        xaxis_title="daily ATR(14) %", yaxis_title="24h quote volume (USDT, log)",
        margin=dict(l=60, r=20, t=50, b=40))
    return fig


if __name__ == "__main__":
    uni = build_universe()
    print(f"universe ({len(uni)}):", ", ".join(uni[:12]))
    screen = run_screen(uni)
    cols = ["symbol", "quote_volume_24h_usdt", "atr_pct", "spread_pct",
            "candle_count", "pass", "fail_reason"]
    print(screen[cols].to_string(index=False))
