"""Fetch hourly candles, run the confluence engine, emit one interactive HTML.

Run:  python confluence_lab/build_confluence.py
Out:  confluence_lab/confluence-dashboard.html

Three stacked panels per coin, with a symbol dropdown:
  1. price candles, the fast/slow MAs, and confluence buy/sell triangles
  2. an agreement ribbon - one row per method (MACD, MA, Fibonacci, Candle),
     green where that method is bullish, red bearish, grey neutral, so you can
     see at a glance WHICH methods lined up behind each fire
  3. the weighted composite score with the +/- threshold bands

Same fetch + fallback + dropdown pattern as the macd and fib dashboards.
"""

from __future__ import annotations

import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from confluence import ConfluenceConfig, compute_confluence, backtest  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT_HTML = os.path.join(HERE, "confluence-dashboard.html")


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
CFG = ConfluenceConfig()


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
        if df is not None and len(df) > 60:
            data[sym] = df
            print(f"  + {sym}: {len(df)} bars")
    if not data:
        print("  live fetch unavailable - using local fallback")
        df = pd.read_csv(FALLBACK_CSV, parse_dates=["time"])
        data = {"BTC/USDT (local)": df}
    return data


def build(data: dict[str, pd.DataFrame]):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.035,
        row_heights=[0.55, 0.22, 0.23],
        subplot_titles=("Price, MAs, and confluence signals",
                        "Method agreement (green bullish / red bearish)",
                        "Weighted confluence score"))

    methods = ["MACD", "MA", "Fibonacci", "Candle"]
    ribbon_scale = [[0.0, "#ef5350"], [0.5, "#eeeeee"], [1.0, "#26a69a"]]
    symbols = list(data.keys())
    owner: list[int] = []
    titles: list[str] = []

    for si, sym in enumerate(symbols):
        df = data[sym].reset_index(drop=True)
        conf = compute_confluence(df, CFG)
        bt = backtest(df, conf)
        t = df["time"]
        buy = conf["buy"].values
        sell = conf["sell"].values
        vis = (si == 0)

        def add(tr, row):
            fig.add_trace(tr, row=row, col=1)
            owner.append(si)

        # row 1: price + MAs + signals
        add(go.Candlestick(x=t, open=df["open"], high=df["high"], low=df["low"],
                           close=df["close"], name="price", visible=vis,
                           showlegend=False, increasing_line_color="#26a69a",
                           decreasing_line_color="#ef5350"), 1)
        add(go.Scatter(x=t, y=df["close"].rolling(CFG.ma_fast).mean(),
                       name=f"MA{CFG.ma_fast}", line=dict(color="#42a5f5", width=1),
                       visible=vis, showlegend=(si == 0)), 1)
        add(go.Scatter(x=t, y=df["close"].rolling(CFG.ma_slow).mean(),
                       name=f"MA{CFG.ma_slow}", line=dict(color="#ab47bc", width=1),
                       visible=vis, showlegend=(si == 0)), 1)
        add(go.Scatter(x=t[buy], y=df["low"][buy] * 0.99, mode="markers",
                       name="confluence BUY",
                       marker=dict(symbol="triangle-up", size=13, color="#1b7d6f",
                                   line=dict(width=1, color="white")),
                       visible=vis, showlegend=(si == 0),
                       hovertemplate="BUY %{x}<extra></extra>"), 1)
        add(go.Scatter(x=t[sell], y=df["high"][sell] * 1.01, mode="markers",
                       name="confluence SELL",
                       marker=dict(symbol="triangle-down", size=13, color="#c62828",
                                   line=dict(width=1, color="white")),
                       visible=vis, showlegend=(si == 0),
                       hovertemplate="SELL %{x}<extra></extra>"), 1)

        # row 2: agreement ribbon (4 x N heatmap)
        z = np.vstack([conf["st_macd"], conf["st_ma"],
                       conf["st_fib"], conf["st_candle"]])
        add(go.Heatmap(x=t, y=methods, z=z, zmin=-1, zmax=1, colorscale=ribbon_scale,
                       showscale=False, visible=vis,
                       hovertemplate="%{y}: %{z}<extra>%{x}</extra>"), 2)

        # row 3: composite score
        add(go.Scatter(x=t, y=conf["score"], name="score", fill="tozeroy",
                       line=dict(color="#5e35b1", width=1.2),
                       fillcolor="rgba(94,53,177,0.15)",
                       visible=vis, showlegend=False), 3)

        titles.append(
            f"<b>{sym}</b> &nbsp; in-sample: strat {bt['return_pct']:+.1f}% vs "
            f"hold {bt['buyhold_pct']:+.1f}% &nbsp;|&nbsp; {bt['trades']} trades, "
            f"win {bt['win_rate']:.0f}%, maxDD {bt['max_drawdown_pct']:.1f}%")

    fig.add_hline(y=CFG.threshold, line=dict(color="#1b7d6f", width=1, dash="dot"),
                  row=3, col=1)
    fig.add_hline(y=-CFG.threshold, line=dict(color="#c62828", width=1, dash="dot"),
                  row=3, col=1)

    buttons = []
    for si, sym in enumerate(symbols):
        visible = [owner[k] == si for k in range(len(owner))]
        buttons.append(dict(label=sym, method="update",
                            args=[{"visible": visible},
                                  {"title.text": f"Confluence — {titles[si]}"}]))

    fig.update_layout(
        title=dict(text=f"Confluence — {titles[0]}", x=0.01, xanchor="left",
                   font=dict(size=13)),
        updatemenus=[dict(buttons=buttons, direction="down", x=0.0, xanchor="left",
                          y=1.14, yanchor="top", showactive=True,
                          bgcolor="#f5f5f5", bordercolor="#cccccc")],
        template="plotly_white", height=900, margin=dict(l=70, r=30, t=100, b=40),
        legend=dict(orientation="h", y=1.06, x=0.2, font=dict(size=10)),
        xaxis3=dict(rangeslider=dict(visible=True, thickness=0.04)),
    )
    fig.update_xaxes(rangeslider_visible=False, row=1, col=1)
    fig.update_yaxes(title_text="price", row=1, col=1)
    fig.update_yaxes(title_text="score", row=3, col=1)
    return fig


def main() -> None:
    print("Fetching hourly candles ...")
    data = gather()
    print(f"Running confluence for {len(data)} symbol(s) ...")
    fig = build(data)
    fig.write_html(OUT_HTML, include_plotlyjs=True, full_html=True,
                   config={"scrollZoom": True, "displaylogo": False})
    print(f"Wrote {OUT_HTML}")


if __name__ == "__main__":
    main()
