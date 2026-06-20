"""
2B - ATR volatility band (Chapter Two, Controls).

Standalone workbench copy of the ATR-band module. The canonical version lives in
the controls notebook (02-swing-controls.ipynb, cell with compute_atr_pct and
atr_band_figure); this file lets you develop and run the module in isolation, then
fold any refinement back into the notebook.

What it computes:
  - ATR(14) as a percent of price (TR = max(H-L, |H-Cprev|, |L-Cprev|);
    ATR = simple moving average of TR; atr_pct = ATR / price * 100).
  - The tradable band: a floor (below it a coin cannot reach the take-profit in the
    window) and a ceiling (above it a coin gaps through stops and targets).

Where it feeds: 2A uses the latest atr_pct as the band gate; 2C uses it to size.

Run:  python atr_band.py            (uses live data if ccxt is reachable, else
                                      deterministic synthetic data so it runs offline)
"""

import numpy as np
import pandas as pd

try:
    import ccxt
except ImportError:
    ccxt = None

# CONFIG subset mirrored from the notebook CONFIG (cell 4). Keep in sync by hand;
# the notebook is canonical.
CONFIG = dict(
    atr_length     = 14,
    atr_floor_pct  = 2.5,
    atr_ceiling_pct= 12.0,
    history_limit  = 180,
)


def synthetic_ohlcv(symbol, n=None, daily_vol=None, seed=None):
    """Deterministic fake OHLCV for offline demo. Seeded by symbol."""
    n = n or CONFIG["history_limit"]
    s = abs(hash(symbol)) % (2 ** 32) if seed is None else seed
    rng = np.random.default_rng(s)
    dv = daily_vol if daily_vol is not None else float(rng.uniform(0.01, 0.10))
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


def fetch_daily(symbol, limit=None, allow_synthetic=True):
    """Daily OHLCV, unclosed bar dropped. Falls back to synthetic if offline."""
    limit = limit or CONFIG["history_limit"]
    if ccxt is not None:
        try:
            ex = ccxt.binance()
            bars = ex.fetch_ohlcv(symbol, timeframe="1d", limit=limit)
            df = pd.DataFrame(
                bars[:-1],
                columns=["timestamp", "open", "high", "low", "close", "volume"],
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            return df.set_index("timestamp")
        except Exception:
            if not allow_synthetic:
                raise
    return synthetic_ohlcv(symbol, n=limit)


def compute_atr_pct(df, length=None):
    """ATR(length) as a percent of price."""
    length = length or CONFIG["atr_length"]
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([(h - l).abs(), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    atr = tr.rolling(length).mean()
    return (atr / c) * 100.0


def in_band(atr_pct_value, cfg=CONFIG):
    """True if a coin's latest ATR% sits inside the tradable band."""
    if atr_pct_value != atr_pct_value:  # NaN
        return False
    return cfg["atr_floor_pct"] <= atr_pct_value <= cfg["atr_ceiling_pct"]


def atr_band_figure(symbol, cfg=CONFIG):
    """Live-guardrail view: ATR(14)% over time against the tradable band.
    Imports plotly lazily so the compute path runs without it installed."""
    import plotly.graph_objects as go

    df = fetch_daily(symbol)
    atr_pct = compute_atr_pct(df)
    lo, hi = cfg["atr_floor_pct"], cfg["atr_ceiling_pct"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=atr_pct.index, y=atr_pct, name="ATR(14) %",
                             line=dict(color="#0B3D66", width=1.6)))
    fig.add_hrect(y0=lo, y1=hi, fillcolor="#2E8B57", opacity=0.10, line_width=0,
                  annotation_text="tradable band", annotation_position="top left")
    fig.add_hline(y=lo, line=dict(color="#2E8B57", dash="dash"),
                  annotation_text=f"floor {lo}%")
    fig.add_hline(y=hi, line=dict(color="#B22222", dash="dash"),
                  annotation_text=f"ceiling {hi}%")
    fig.update_layout(
        title=f"{symbol} - daily ATR% vs tradable band (selection + live guardrail)",
        template="plotly_white", height=360,
        yaxis_title="ATR(14) as % of price", xaxis_title=None,
        margin=dict(l=40, r=20, t=50, b=30))
    return fig


if __name__ == "__main__":
    symbol = "BTC/USDT"
    df = fetch_daily(symbol)
    atr = compute_atr_pct(df)
    latest = float(atr.dropna().iloc[-1])
    print(f"{symbol}: ATR(14) latest = {latest:.2f}%  "
          f"band [{CONFIG['atr_floor_pct']}, {CONFIG['atr_ceiling_pct']}]  "
          f"-> {'inside' if in_band(latest) else 'outside'}")
