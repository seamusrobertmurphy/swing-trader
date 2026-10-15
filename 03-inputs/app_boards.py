"""The workflow's three indicator boards, built for the public app.

Added 14 October 2026 at the operator's word, the last of the parity items
between the app and the README's Trend Signals section. The MACD, confluence
and Fibonacci engines under `04-outputs/1A-macd`, `1B-confluence` and
`1C-fibonacci` are run unchanged, through `analysis_charts.engines()`, on the
same coins and stocks the app's Forecast card offers, on daily candles. Each
board keeps its own symbol menu.

    .venv/bin/python 03-inputs/app_boards.py

Writes site/boards/{crypto,equity}/{macd,confluence,fibonacci}.html and
site/boards/index.json. `demo_site.py --forecast --publish` copies them to
gh-pages, and the page loads one only when a visitor opens it. Run locally,
because the crypto candles come from the local Binance Vision store.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "03-inputs"))

import analysis_charts as ac  # noqa: E402
import demo_run as dr  # noqa: E402
import timesfm_forecast as tf  # noqa: E402

OUT = REPO / "site" / "boards"
HISTORY = 760          # daily candles per symbol, as the dashboard's boards use
BOARDS = [("macd", "macd_fig"), ("confluence", "conf_fig"), ("fibonacci", "fib_fig")]


def frames(market: str, symbols: list[str]) -> dict:
    """Daily OHLCV in the shape the engines take: a naive `time` and lower-case columns."""
    out = {}
    for s in symbols:
        d = tf.load(market, "1d", s)
        if d is None or len(d) < 60:
            print(f"  {market} {s}: no daily candles, left out", flush=True)
            continue
        d = d.tail(HISTORY).rename(columns={"datetime": "time"})
        d["time"] = d["time"].dt.tz_localize(None) if d["time"].dt.tz is not None else d["time"]
        out[s.replace("USDT", "")] = d[["time", "open", "high", "low", "close", "volume"]].reset_index(drop=True)
    return out


def tidy(fig, key: str) -> None:
    """Fit a board to the app's dark card without touching the engine.

    The symbol menu was styled for a white page and showed as a blank white box.
    The Fibonacci engine draws its level lines without a `visible` flag, so every
    symbol's levels showed at once and pulled the price scale to zero; the first
    menu entry's own visibility list is applied, and its key, one entry per level
    per symbol, is hidden because each line carries its label on the chart."""
    menus = fig.layout.updatemenus
    if menus:
        # The menu gets its own line under the title, which it otherwise covered.
        # A menu's height is in plot units only, so 72 pixels above the plot is worked out from the figure's height.
        plot = (fig.layout.height or 800) - 110 - 40
        fig.update_layout(updatemenus=[dict(m.to_plotly_json(), bgcolor="#161b22", bordercolor="#262d36",
                                            font=dict(color="#e6edf3"), y=1 + 72 / plot, yanchor="top")
                                       for m in menus],
                          title=dict(y=0.985, yref="container", yanchor="top"), margin=dict(t=110))
        first = menus[0].buttons[0].args[0].get("visible")
        if first and len(first) == len(fig.data):
            for tr, v in zip(fig.data, first):
                tr.visible = v
    if key == "fibonacci":
        fig.update_layout(showlegend=False)


def main() -> int:
    eng = ac.engines()
    index = dict(built=datetime.now(timezone.utc).isoformat(timespec="minutes"), boards={})
    for market, symbols in (("crypto", dr.COINS), ("equity", dr.STOCKS)):
        data = frames(market, symbols)
        print(f"{market}: daily candles for {len(data)} of {len(symbols)}", flush=True)
        (OUT / market).mkdir(parents=True, exist_ok=True)
        for key, mod in BOARDS:
            fig = eng[mod].build(data)
            # The colours the dashboard gives these boards, which match the app's dark card.
            fig.update_layout(template="plotly_dark", paper_bgcolor="#0e1117", plot_bgcolor="#161b22",
                              font=dict(color="#e6edf3"), margin=dict(l=50, r=20, t=70, b=40))
            tidy(fig, key)
            p = OUT / market / f"{key}.html"
            # On a phone the key stacked over the price, so it is hidden there; the app's note explains the marks.
            fig.write_html(str(p), include_plotlyjs="cdn", full_html=True,
                           config=dict(displaylogo=False, responsive=True),
                           post_script="if (window.innerWidth < 600) Plotly.relayout('{plot_id}', "
                                       "{showlegend: false, 'margin.l': 40, 'margin.r': 8});")
            index["boards"][f"{market}/{key}"] = dict(height=int(fig.layout.height or 800),
                                                      symbols=list(data), mb=round(p.stat().st_size / 1e6, 1))
            print(f"  wrote {p.relative_to(REPO)} ({p.stat().st_size / 1e6:.1f} MB)", flush=True)
    (OUT / "index.json").write_text(json.dumps(index, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
