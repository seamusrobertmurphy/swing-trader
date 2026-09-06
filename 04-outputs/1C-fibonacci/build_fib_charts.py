"""Fetch hourly candles, auto-anchor a Fibonacci swing, emit one interactive HTML.

Run:  python fib_lab/build_fib_charts.py
Out:  fib_lab/fib-dashboard.html   (self-contained; opens in any browser)

Mirrors macd_lab/build_macd_charts.py: same live ccxt fetch with a local
fallback, same symbol-dropdown pattern. For each coin it finds the dominant
recent swing, draws the retracement grid and the golden pocket on the price, and
projects the extension targets in the direction of the latest leg.
"""

from __future__ import annotations

import os
import sys
import time

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fib import (FibConfig, detect_swing, retracement_levels,        # noqa: E402
                 extension_levels, golden_pocket)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT_HTML = os.path.join(HERE, "fib-dashboard.html")


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
BARS = 1000
CFG = FibConfig()

# colour ramp for the retracement lines, shallow -> deep
RETR_COLOR = {0.0: "#9e9e9e", 0.236: "#42a5f5", 0.382: "#26a69a",
              0.5: "#fb8c00", 0.618: "#e53935", 0.786: "#8e24aa", 1.0: "#9e9e9e"}


def fetch_hourly(symbol: str, bars: int = BARS) -> pd.DataFrame | None:
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
        return df.iloc[:-1].reset_index(drop=True)
    except Exception as e:
        print(f"  ! {symbol}: {type(e).__name__}: {str(e)[:80]}")
        return None


def gather() -> dict[str, pd.DataFrame]:
    data: dict[str, pd.DataFrame] = {}
    for sym in UNIVERSE:
        df = fetch_hourly(sym)
        if df is not None and len(df) > 30:
            data[sym] = df
            print(f"  + {sym}: {len(df)} bars")
    if not data:
        print("  live fetch unavailable - using local fallback")
        df = pd.read_csv(FALLBACK_CSV, parse_dates=["time"])
        data = {"BTC/USDT (local)": df}
    return data


def hline(x0, x1, y, color, dash, name, width=1.4, text=None):
    import plotly.graph_objects as go
    return go.Scatter(
        x=[x0, x1], y=[y, y], mode="lines+text" if text else "lines",
        line=dict(color=color, width=width, dash=dash),
        text=[None, text], textposition="top left",
        textfont=dict(size=10, color=color),
        name=name, hovertemplate=f"{name}: {y:,.4g}<extra></extra>")


def build(data: dict[str, pd.DataFrame]):
    import plotly.graph_objects as go

    fig = go.Figure()
    symbols = list(data.keys())
    owner: list[int] = []
    titles: list[str] = []

    for si, sym in enumerate(symbols):
        df = data[sym].reset_index(drop=True)
        sw = detect_swing(df["high"], df["low"], CFG)
        t = df["time"]
        x1 = t.iloc[-1]
        vis = (si == 0)

        def add(tr):
            fig.add_trace(tr)
            owner.append(si)

        add(go.Candlestick(
            x=t, open=df["open"], high=df["high"], low=df["low"], close=df["close"],
            name="price", visible=vis, showlegend=False,
            increasing_line_color="#26a69a", decreasing_line_color="#ef5350"))

        if sw is None:
            titles.append(f"<b>{sym}</b> no clear swing")
            continue

        x0 = t.iloc[min(sw.lo_idx, sw.hi_idx)]
        retr = retracement_levels(sw, CFG)
        ext = extension_levels(sw, CFG)
        gp_lo, gp_hi = golden_pocket(sw)

        # golden pocket shading (0.5 - 0.618)
        add(go.Scatter(
            x=[x0, x1, x1, x0], y=[gp_lo, gp_lo, gp_hi, gp_hi], fill="toself",
            mode="lines", line=dict(width=0), fillcolor="rgba(255,193,7,0.18)",
            name="golden pocket", visible=vis, showlegend=(si == 0),
            hoverinfo="skip"))

        # retracement grid
        for r, price in retr.items():
            add(hline(x0, x1, price, RETR_COLOR.get(r, "#777"),
                      "solid" if r in (0.0, 1.0) else "dot",
                      f"{r*100:.1f}%", width=1.6 if r in (0.5, 0.618) else 1.2,
                      text=f"{r*100:.1f}%  {price:,.4g}"))
            owner[-1] = si

        # extension targets, dashed, in the leg direction
        for E, price in ext.items():
            add(hline(x0, x1, price, "#5e35b1", "dash", f"ext {E*100:.1f}%",
                      width=1.1, text=f"ext {E*100:.1f}%  {price:,.4g}"))
            owner[-1] = si

        # the swing leg itself
        add(go.Scatter(
            x=[t.iloc[sw.lo_idx], t.iloc[sw.hi_idx]], y=[sw.lo, sw.hi],
            mode="lines+markers", line=dict(color="#212121", width=1.2, dash="dot"),
            marker=dict(size=7, color="#212121"), name="swing",
            visible=vis, showlegend=(si == 0), hoverinfo="skip"))

        leg = "up-leg (retr = support, targets above)" if sw.up \
            else "down-leg (retr = resistance, targets below)"
        titles.append(f"<b>{sym}</b> &nbsp; {leg} &nbsp;|&nbsp; "
                      f"swing {sw.lo:,.4g} -> {sw.hi:,.4g} "
                      f"({sw.rng / sw.hi * 100:.1f}%) &nbsp;|&nbsp; "
                      f"last {df['close'].iloc[-1]:,.4g}")

    buttons = []
    for si, sym in enumerate(symbols):
        visible = [owner[k] == si for k in range(len(owner))]
        buttons.append(dict(label=sym, method="update",
                            args=[{"visible": visible},
                                  {"title.text": f"Fibonacci — {titles[si]}"}]))

    fig.update_layout(
        title=dict(text=f"Fibonacci — {titles[0]}", x=0.01, xanchor="left",
                   font=dict(size=14)),
        updatemenus=[dict(buttons=buttons, direction="down", x=0.0, xanchor="left",
                          y=1.13, yanchor="top", showactive=True,
                          bgcolor="#f5f5f5", bordercolor="#cccccc")],
        template="plotly_white", height=780, margin=dict(l=60, r=30, t=95, b=40),
        legend=dict(orientation="h", y=1.05, x=0.22, font=dict(size=10)),
        xaxis=dict(rangeslider=dict(visible=True, thickness=0.05)),
        yaxis=dict(title="price"),
    )
    return fig


def main() -> None:
    print("Fetching hourly candles ...")
    data = gather()
    print(f"Building Fibonacci dashboard for {len(data)} symbol(s) ...")
    fig = build(data)
    fig.write_html(OUT_HTML, include_plotlyjs=True, full_html=True,
                   config={"scrollZoom": True, "displaylogo": False})
    print(f"Wrote {OUT_HTML}")


if __name__ == "__main__":
    main()
