"""Fetch hourly candles, compute guarded MACD, and emit one interactive HTML.

Run:  python macd_lab/build_macd_charts.py
Out:  macd_lab/macd-dashboard.html   (self-contained; opens in any browser)

Data: live hourly OHLCV via ccxt/Binance for the project's 10-coin universe.
If the network or exchange is unavailable it falls back to the local
outputs/BTCUSDT_1h_raw.csv so the script always produces something.

The chart is a single figure with a symbol dropdown. For each symbol:
  top panel  - price candles, with guarded buy/sell triangles and
               bullish/bearish divergence diamonds
  low panel  - MACD line, signal ("EMA") line, and a 4-colour histogram that
               encodes convergence (fading) vs divergence (building) momentum
"""

from __future__ import annotations

import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from macd import MACDConfig, compute_signals  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT_HTML = os.path.join(HERE, "macd-dashboard.html")


def _find_data(name="BTCUSDT_1h_raw.csv"):
    """Locate the offline-fallback CSV near this file, robust to folder moves."""
    d = HERE
    for _ in range(5):
        for cand in (os.path.join(d, name), os.path.join(d, "outputs", name)):
            if os.path.isfile(cand):
                return cand
        d = os.path.dirname(d)
    return os.path.join(REPO, name)


FALLBACK_CSV = _find_data()

UNIVERSE = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
            "ADA/USDT", "AVAX/USDT", "LINK/USDT", "LTC/USDT", "DOGE/USDT"]
TIMEFRAME = "1h"
BARS = 2000            # ~83 days of hourly bars; enough for divergence context
CFG = MACDConfig()     # 12/26/9 with default guardrails


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
def fetch_hourly(symbol: str, bars: int = BARS) -> pd.DataFrame | None:
    """Paginate hourly OHLCV back `bars` candles. None on any failure."""
    try:
        import ccxt
    except Exception:
        return None
    try:
        ex = ccxt.binance({"enableRateLimit": True})
        tf_ms = ex.parse_timeframe(TIMEFRAME) * 1000
        since = ex.milliseconds() - bars * tf_ms
        rows: list[list] = []
        while len(rows) < bars:
            batch = ex.fetch_ohlcv(symbol, TIMEFRAME, since=since, limit=1000)
            if not batch:
                break
            rows += batch
            since = batch[-1][0] + tf_ms
            if len(batch) < 1000:
                break
            time.sleep(ex.rateLimit / 1000)
        if not rows:
            return None
        df = pd.DataFrame(rows, columns=["time", "open", "high", "low",
                                         "close", "volume"])
        df = df.drop_duplicates("time").sort_values("time")
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        # drop the final, still-forming candle
        return df.iloc[:-1].reset_index(drop=True)
    except Exception as e:
        print(f"  ! {symbol}: {type(e).__name__}: {str(e)[:80]}")
        return None


def load_fallback() -> dict[str, pd.DataFrame]:
    df = pd.read_csv(FALLBACK_CSV, parse_dates=["time"])
    return {"BTC/USDT (local)": df}


def gather() -> dict[str, pd.DataFrame]:
    data: dict[str, pd.DataFrame] = {}
    for sym in UNIVERSE:
        df = fetch_hourly(sym)
        if df is not None and len(df) > CFG.slow + CFG.signal + 5:
            data[sym] = df
            print(f"  + {sym}: {len(df)} bars  "
                  f"({df['time'].iloc[0]:%Y-%m-%d} -> {df['time'].iloc[-1]:%Y-%m-%d})")
    if not data:
        print("  live fetch unavailable - using local fallback")
        data = load_fallback()
    return data


# --------------------------------------------------------------------------- #
# Histogram colours: encode convergence vs divergence
# --------------------------------------------------------------------------- #
def hist_colors(hist: pd.Series) -> list[str]:
    up_strong, up_soft = "#26a69a", "#8fd6cd"      # >0 building / >0 fading
    dn_strong, dn_soft = "#ef5350", "#f4a6a4"      # <0 building / <0 fading
    rising = hist.diff().fillna(0) >= 0
    cols = []
    for h, r in zip(hist, rising):
        if h >= 0:
            cols.append(up_strong if r else up_soft)
        else:
            cols.append(dn_strong if not r else dn_soft)
    return cols


def summarise(sig: pd.DataFrame, df: pd.DataFrame) -> str:
    last = sig.iloc[-1]
    state = "MACD &gt; signal (bullish)" if last["macd"] > last["signal"] \
        else "MACD &lt; signal (bearish)"
    zero = "below zero" if last["macd"] < 0 else "above zero"
    nb, ns = int(sig["guarded_buy"].sum()), int(sig["guarded_sell"].sum())
    return (f"{state}, {zero} &nbsp;|&nbsp; last close {df['close'].iloc[-1]:,.4g} "
            f"&nbsp;|&nbsp; guarded signals: {nb} buy / {ns} sell")


# --------------------------------------------------------------------------- #
# Figure
# --------------------------------------------------------------------------- #
def build(data: dict[str, pd.DataFrame]) -> "object":
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.04,
        row_heights=[0.62, 0.38],
        subplot_titles=("Price", "MACD (12 / 26 / 9)"),
    )

    symbols = list(data.keys())
    trace_owner: list[int] = []   # which symbol each trace belongs to
    summaries: list[str] = []

    for si, sym in enumerate(symbols):
        df = data[sym].reset_index(drop=True)
        sig = compute_signals(df["close"], CFG)
        t = df["time"]
        gbuy = sig["guarded_buy"].values
        gsell = sig["guarded_sell"].values
        bear = sig["bear_div"].values
        bull = sig["bull_div"].values
        vis = (si == 0)

        def add(tr):
            fig.add_trace(tr, row=add.row, col=1)
            trace_owner.append(si)

        # ---- price panel (row 1) ----
        add.row = 1
        add(go.Candlestick(
            x=t, open=df["open"], high=df["high"], low=df["low"], close=df["close"],
            name="price", visible=vis, showlegend=False,
            increasing_line_color="#26a69a", decreasing_line_color="#ef5350"))
        add(go.Scatter(
            x=t[gbuy], y=df["low"][gbuy] * 0.995, mode="markers", name="guarded buy",
            marker=dict(symbol="triangle-up", size=11, color="#1b7d6f",
                        line=dict(width=1, color="white")),
            visible=vis, showlegend=(si == 0),
            hovertemplate="GUARDED BUY<br>%{x}<extra></extra>"))
        add(go.Scatter(
            x=t[gsell], y=df["high"][gsell] * 1.005, mode="markers", name="guarded sell",
            marker=dict(symbol="triangle-down", size=11, color="#c62828",
                        line=dict(width=1, color="white")),
            visible=vis, showlegend=(si == 0),
            hovertemplate="GUARDED SELL<br>%{x}<extra></extra>"))
        add(go.Scatter(
            x=t[bear], y=df["high"][bear] * 1.012, mode="markers", name="bearish divergence",
            marker=dict(symbol="diamond", size=9, color="#ad1457"),
            visible=vis, showlegend=(si == 0),
            hovertemplate="BEARISH DIVERGENCE<br>%{x}<extra></extra>"))
        add(go.Scatter(
            x=t[bull], y=df["low"][bull] * 0.988, mode="markers", name="bullish divergence",
            marker=dict(symbol="diamond", size=9, color="#00838f"),
            visible=vis, showlegend=(si == 0),
            hovertemplate="BULLISH DIVERGENCE<br>%{x}<extra></extra>"))

        # ---- MACD panel (row 2) ----
        add.row = 2
        add(go.Bar(
            x=t, y=sig["hist"], name="histogram", marker_color=hist_colors(sig["hist"]),
            visible=vis, showlegend=False,
            hovertemplate="hist %{y:.4g}<extra></extra>"))
        add(go.Scatter(
            x=t, y=sig["macd"], name="MACD line", line=dict(color="#1565c0", width=1.4),
            visible=vis, showlegend=(si == 0)))
        add(go.Scatter(
            x=t, y=sig["signal"], name="signal (EMA) line",
            line=dict(color="#ef6c00", width=1.4),
            visible=vis, showlegend=(si == 0)))

        summaries.append(f"<b>{sym}</b> &nbsp; {summarise(sig, df)}")

    # zero line on the MACD panel
    fig.add_hline(y=0, line=dict(color="#9e9e9e", width=1, dash="dot"), row=2, col=1)

    # ---- dropdown: toggle visibility per symbol + retitle ----
    buttons = []
    for si, sym in enumerate(symbols):
        visible = [trace_owner[k] == si for k in range(len(trace_owner))]
        buttons.append(dict(
            label=sym, method="update",
            args=[{"visible": visible},
                  {"title.text": f"Guarded MACD — {summaries[si]}"}]))

    fig.update_layout(
        title=dict(text=f"Guarded MACD — {summaries[0]}", x=0.01, xanchor="left",
                   font=dict(size=15)),
        updatemenus=[dict(buttons=buttons, direction="down", x=0.0, xanchor="left",
                          y=1.16, yanchor="top", showactive=True,
                          bgcolor="#f5f5f5", bordercolor="#cccccc")],
        template="plotly_white",
        height=820, margin=dict(l=60, r=30, t=110, b=40),
        legend=dict(orientation="h", y=1.07, x=0.18, font=dict(size=11)),
        hovermode="x unified",
        xaxis2=dict(rangeslider=dict(visible=True, thickness=0.05)),
    )
    fig.update_xaxes(rangeslider_visible=False, row=1, col=1)
    fig.update_yaxes(title_text="price", row=1, col=1)
    fig.update_yaxes(title_text="MACD", row=2, col=1)
    return fig


def main() -> None:
    print("Fetching hourly candles ...")
    data = gather()
    print(f"Building dashboard for {len(data)} symbol(s) ...")
    fig = build(data)
    fig.write_html(OUT_HTML, include_plotlyjs=True, full_html=True,
                   config={"scrollZoom": True, "displaylogo": False})
    print(f"Wrote {OUT_HTML}")


if __name__ == "__main__":
    main()
