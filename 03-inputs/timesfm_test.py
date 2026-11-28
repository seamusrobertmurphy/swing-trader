"""Test page: TimesFM forecasts drawn over the workflow's MACD signals and trade geometry.

    .venv/bin/python 03-inputs/timesfm_test.py            # build 04-outputs/timesfm-test/
    .venv/bin/python 03-inputs/timesfm_test.py --publish  # also copy it to gh-pages test/

Operator request, 29 September 2026: explore adding Google's TimesFM forecasting
model to the app's predictions, and draw a dark line chart with the MACD, the buy
and sell points and the position geometry built in the trader workflow, so a
reader can see what the model predicted around each turning point. This is the
test version, a page of its own, not yet placed on the app's home or results page.

TimesFM 2.5 (200 million parameters) is used rather than 3.0, because the 3.0
weights are licensed for non-commercial, non-production use only and the app is
public; the 2.5 weights are Apache 2.0. Model card,
https://huggingface.co/google/timesfm-2.5-200m-pytorch, code cloned to
/Volumes/PortableSSD/Github/timesfm (commit e51928e).

What is drawn, per symbol.
1. Closing price with its 200-candle exponential moving average.
2. MACD buy and sell signals, the guarded crossovers of 04-outputs/1A-macd/macd.py.
3. Position geometry for every buy, simulated by exit_geometry_viz.simulate_with_path
   with the workflow's settings: stop 2 ATR below entry, trailing 2 ATR, take-profit
   3 ATR above, 0.1 per cent fee a side, held at most 48 candles.
4. A TimesFM forecast fan from every signal, the median path and the band from the
   10th to the 90th percentile, 12 candles ahead, fitted only on candles up to the
   signal, so each fan is what the model would have said at that moment.
5. The latest forecast from the last closed candle.
6. The MACD line, its signal line and histogram, and the divergences, below.

What is scored, over every signal in the scored period. Direction hit rate, the
share of signals where the forecast's sign over 12 candles matched the realised
sign. Theil's U2, the forecast's root mean squared error on the 12-candle return
divided by that of a no-change forecast, so under one beats standing still. And,
as the integration test, MACD buys split by whether TimesFM agreed (median above
the entry close at 12 candles), with each group's mean return after cost.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "04-outputs" / "1A-macd"))

import build_dataset_1h as bd          # noqa: E402
import exit_geometry_viz as egv        # noqa: E402
import macd as mc                      # noqa: E402

OUT = REPO / "04-outputs" / "timesfm-test"
HORIZON = 12          # candles ahead, the 4-hour frame's label horizon
CONTEXT = 1024        # candles of history each forecast sees
MAX_HOLD = 4 * HORIZON
GEOMETRY = dict(stop_mult=2.0, tp_atr=3.0, trail=2.0, tp_decay=False)   # exit_geometry_viz.render
FEE = 0.001           # per side, as in exit_geometry_viz.render
SHOWN = 360           # candles drawn on the chart
SCORED_YEARS = 3      # signals scored over the most recent three years
SYMBOLS = [("BTCUSDT", "4h", "binance"), ("ETHUSDT", "4h", "binance"),
           ("SOLUSDT", "4h", "binance"), ("SPY", "1d", "alpaca")]

BG, PANEL, GRID, TEXT, MUTED = "#0e1117", "#161b22", "#262d36", "#e6edf3", "#8b949e"
UP, DOWN, PRICE, EMA, FAN = "#3fb950", "#f85149", "#c9d1d9", "#d29922", "#58a6ff"


def load(symbol: str, frame: str, source: str) -> pd.DataFrame:
    if source == "binance":
        # Binance Vision spot klines, 30-minute, https://data.binance.vision/
        # (packed to Parquet by vision_to_parquet.py), summed here to 4-hour candles.
        d = pd.read_parquet(REPO / "03-inputs" / "binance-data" / "parquet_30m" / f"{symbol}.parquet",
                            columns=["datetime", "open", "high", "low", "close", "volume"])
        d = (d.set_index("datetime").resample(frame)
             .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
             .dropna().reset_index())
    else:
        # Alpaca market data, daily bars, SIP feed, adjustment=all,
        # https://data.alpaca.markets/v2/stocks/bars (stored by alpaca_data.py).
        d = pd.read_parquet(REPO / "03-inputs" / "alpaca-data" / "daily" / f"{symbol}.parquet")
        d = d[["datetime", "open", "high", "low", "close", "volume"]]
    for c in ("open", "high", "low", "close", "volume"):
        d[c] = d[c].astype("float64")
    return d.reset_index(drop=True)


def model():
    import timesfm
    import torch
    torch.set_float32_matmul_precision("high")
    m = timesfm.TimesFM_2p5_200M_torch.from_pretrained("google/timesfm-2.5-200m-pytorch")
    m.compile(timesfm.ForecastConfig(max_context=CONTEXT, max_horizon=HORIZON, normalize_inputs=True,
                                     use_continuous_quantile_head=True, fix_quantile_crossing=True,
                                     per_core_batch_size=32))
    return m


def forecast(m, close: np.ndarray, origins: list[int]) -> tuple[np.ndarray, np.ndarray]:
    """Median and 10th to 90th percentile paths from each origin, using candles up to it."""
    med, q = [], []
    for k in range(0, len(origins), 64):
        batch = [close[max(0, o + 1 - CONTEXT): o + 1].astype("float32") for o in origins[k:k + 64]]
        p, qs = m.forecast(horizon=HORIZON, inputs=batch)
        med.append(p)
        q.append(qs[:, :, [1, 9]])
    return np.concatenate(med), np.concatenate(q)


def score(close, origins, med, buys, trades) -> dict:
    """Direction, Theil's U2 against no change, and MACD buys split by TimesFM agreement."""
    ok = [i for i, o in enumerate(origins) if o + HORIZON < len(close)]
    o = np.array([origins[i] for i in ok])
    real = close[o + HORIZON] / close[o] - 1
    pred = med[ok, -1] / close[o] - 1
    hit = float(np.mean(np.sign(pred) == np.sign(real)))
    u2 = float(np.sqrt(np.mean((pred - real) ** 2)) / np.sqrt(np.mean(real ** 2)))
    agree = {origins[i]: med[i, -1] > close[origins[i]] for i in range(len(origins))}
    groups = {"agreed": [], "disagreed": []}
    for t in trades:
        if t["i"] in agree and t["i"] in buys:
            groups["agreed" if agree[t["i"]] else "disagreed"].append(t["ret"])
    split = {k: dict(trades=len(v), mean_pct=round(100 * float(np.mean(v)), 3) if v else None,
                     won_pct=round(100 * float(np.mean(np.array(v) > 0)), 1) if v else None)
             for k, v in groups.items()}
    return dict(signals=len(ok), direction_hit_pct=round(100 * hit, 1), theil_u2=round(u2, 3),
                buys_by_agreement=split)


def build(symbol, frame, source, m):
    d = load(symbol, frame, source)
    close = d["close"].to_numpy()
    sig = mc.compute_signals(d["close"])
    buys = set(np.flatnonzero(sig["guarded_buy"].to_numpy(bool)))
    sells = set(np.flatnonzero(sig["guarded_sell"].to_numpy(bool)))
    bd.configure(4 if frame == "4h" else "1d")
    entries = np.zeros(len(d), bool)
    entries[list(buys)] = True
    trades, _ = egv.simulate_with_path(d, entries, GEOMETRY, FEE, MAX_HOLD)

    start = d["datetime"].iloc[-1] - pd.DateOffset(years=SCORED_YEARS)
    first = int(max((d["datetime"] < start).sum(), CONTEXT // 4))
    origins = sorted(i for i in buys | sells if i >= first)
    last = len(d) - 1
    med, q = forecast(m, close, origins + [last])
    live = dict(median=med[-1].tolist(), low=q[-1, :, 0].tolist(), high=q[-1, :, 1].tolist())
    rec = score(close, origins, med[:-1], buys, trades)
    rec.update(symbol=symbol, frame=frame, candles=len(d),
               first=str(d["datetime"].iloc[0]), last=str(d["datetime"].iloc[-1]))
    return rec, figure(d, sig, buys, sells, trades, origins, med[:-1], q[:-1], live, rec)


def figure(d, sig, buys, sells, trades, origins, med, q, live, rec):
    from plotly.subplots import make_subplots
    lo = len(d) - SHOWN
    x = d["datetime"]
    step = x.iloc[-1] - x.iloc[-2]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.72, 0.28],
                        vertical_spacing=0.03)
    ema = d["close"].ewm(span=200, adjust=True).mean()
    fig.add_scatter(mode="lines", x=x[lo:], y=d["close"][lo:], name="Close", line=dict(color=PRICE, width=1.4))
    fig.add_scatter(mode="lines", x=x[lo:], y=ema[lo:], name="EMA 200", line=dict(color=EMA, width=1, dash="dot"))
    shown_fan = False
    for k, o in enumerate(origins):
        if o < lo:
            continue
        fx = [x[o] + step * h for h in range(0, HORIZON + 1)]
        c0 = d["close"][o]
        up = [c0] + list(q[k, :, 1])
        dn = [c0] + list(q[k, :, 0])
        fig.add_scatter(mode="lines", x=fx + fx[::-1], y=up + dn[::-1], fill="toself", fillcolor="rgba(88,166,255,0.13)",
                        line=dict(width=0), hoverinfo="skip", showlegend=False, legendgroup="fan")
        fig.add_scatter(mode="lines", x=fx, y=[c0] + list(med[k]), line=dict(color=FAN, width=1.3),
                        name="TimesFM from each signal", legendgroup="fan", showlegend=not shown_fan,
                        hovertemplate="forecast %{y:,.2f}<extra></extra>")
        shown_fan = True
    for t in trades:
        if t["i"] < lo or len(t["spath"]) == 0:
            continue
        tx = x[t["i"] + 1: t["i"] + 1 + len(t["spath"])]
        fig.add_scatter(mode="lines", x=tx, y=t["spath"], line=dict(color=DOWN, width=1, shape="hv"), name="Stop",
                        legendgroup="stop", showlegend=False, hoverinfo="skip")
        fig.add_scatter(mode="lines", x=tx, y=t["tpath"], line=dict(color=UP, width=1, dash="dash"), name="Take-profit",
                        legendgroup="tp", showlegend=False, hoverinfo="skip")
        fig.add_scatter(x=[x[t["j"]]], y=[t["exit"]], mode="markers", showlegend=False,
                        marker=dict(symbol="x", size=8, color=UP if t["ret"] > 0 else DOWN),
                        hovertemplate=f"exit, {t['reason']}, {100 * t['ret']:+.2f}% after fees<extra></extra>")
    b = [i for i in sorted(buys) if i >= lo]
    s = [i for i in sorted(sells) if i >= lo]
    fig.add_scatter(x=x[b], y=d["close"][b], mode="markers", name="MACD buy",
                    marker=dict(symbol="triangle-up", size=11, color=UP, line=dict(color=BG, width=1)))
    fig.add_scatter(x=x[s], y=d["close"][s], mode="markers", name="MACD sell",
                    marker=dict(symbol="triangle-down", size=11, color=DOWN, line=dict(color=BG, width=1)))
    fx = [x.iloc[-1] + step * h for h in range(0, HORIZON + 1)]
    c0 = d["close"].iloc[-1]
    fig.add_scatter(mode="lines", x=fx + fx[::-1], y=[c0] + live["high"] + ([c0] + live["low"])[::-1], fill="toself",
                    fillcolor="rgba(210,153,34,0.20)", line=dict(width=0), hoverinfo="skip", showlegend=False)
    fig.add_scatter(mode="lines", x=fx, y=[c0] + live["median"], name="TimesFM now", line=dict(color=EMA, width=2.2),
                    hovertemplate="forecast %{y:,.2f}<extra></extra>")
    # Legend entries for the geometry lines, drawn once.
    fig.add_scatter(mode="lines", x=[None], y=[None], name="Stop, trailing", line=dict(color=DOWN, width=1), legendgroup="stop")
    fig.add_scatter(mode="lines", x=[None], y=[None], name="Take-profit", line=dict(color=UP, width=1, dash="dash"),
                    legendgroup="tp")

    hist = sig["hist"][lo:]
    fig.add_bar(x=x[lo:], y=hist, marker_color=np.where(hist >= 0, UP, DOWN), opacity=0.55,
                name="Histogram", showlegend=False, row=2, col=1)
    fig.add_scatter(mode="lines", x=x[lo:], y=sig["macd"][lo:], name="MACD", line=dict(color=FAN, width=1.2),
                    showlegend=False, row=2, col=1)
    fig.add_scatter(mode="lines", x=x[lo:], y=sig["signal"][lo:], name="Signal line", line=dict(color=EMA, width=1),
                    showlegend=False, row=2, col=1)
    for col, colour, label in (("bull_div", UP, "bullish divergence"), ("bear_div", DOWN, "bearish divergence")):
        idx = [i for i in np.flatnonzero(sig[col].to_numpy(bool)) if i >= lo]
        fig.add_scatter(x=x[idx], y=sig["macd"].iloc[idx], mode="markers", name=label, showlegend=False,
                        marker=dict(symbol="diamond", size=7, color=colour), row=2, col=1)
    fig.update_layout(paper_bgcolor=BG, plot_bgcolor=PANEL, font=dict(color=TEXT, size=12),
                      margin=dict(l=8, r=8, t=8, b=8), height=560, hovermode="x unified",
                      legend=dict(orientation="h", y=1.02, x=0, yanchor="bottom", font=dict(size=11),
                                  bgcolor="rgba(0,0,0,0)"), bargap=0)
    fig.update_xaxes(gridcolor=GRID, zeroline=False, showspikes=True, spikecolor=MUTED, spikethickness=1)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, side="right")
    fig.update_yaxes(title=None, row=2, col=1)
    return fig


def page(recs, figs, stamp) -> str:
    tabs = "".join(f'<button class="tab{" on" if k == 0 else ""}" data-k="{k}">{r["symbol"]} '
                   f'<span>{r["frame"].replace("h", "-hour").replace("1d", "daily")}</span></button>'
                   for k, r in enumerate(recs))
    panes = []
    for k, (r, f) in enumerate(zip(recs, figs)):
        a, dis = r["buys_by_agreement"]["agreed"], r["buys_by_agreement"]["disagreed"]

        def cell(g):
            return (f'{g["trades"]} trades, {g["mean_pct"]:+.2f}% each, {g["won_pct"]:.0f}% won'
                    if g["trades"] else "no trades")
        u2 = r["theil_u2"]
        verdict = "beat" if u2 < 1 else "did not beat"
        panes.append(f'''<section class="pane" data-k="{k}"{"" if k == 0 else " hidden"}>
<div class="chart">{f}</div>
<table><tr><th>Direction right</th><td>{r["direction_hit_pct"]:.1f}% of {r["signals"]} signals over
the last {SCORED_YEARS} years, against 50% for a coin flip</td></tr>
<tr><th>Against no change</th><td>Theil's U2 {u2:.3f}. The forecast {verdict} a forecast that the price
stays where it is, which scores 1.</td></tr>
<tr><th>Buys TimesFM backed</th><td>{cell(a)}</td></tr>
<tr><th>Buys TimesFM doubted</th><td>{cell(dis)}</td></tr></table>
</section>''')
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TimesFM Test</title>
<script src="https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js"></script>
<style>
:root{{--bg:{BG};--panel:{PANEL};--line:{GRID};--text:{TEXT};--muted:{MUTED};--accent:{FAN}}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);
font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:16px}} h1{{font-size:20px;margin:4px 0 6px}}
p{{color:var(--muted);margin:0 0 12px}} .tabs{{display:flex;gap:6px;flex-wrap:wrap;margin:12px 0}}
.tab{{background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:18px;
padding:6px 12px;font:inherit;cursor:pointer}} .tab span{{color:var(--muted);font-size:12px}}
.tab.on{{border-color:var(--accent);background:#1c2a3d}} .chart{{background:var(--panel);
border:1px solid var(--line);border-radius:10px;overflow:hidden}}
table{{width:100%;border-collapse:collapse;margin:12px 0}} th,td{{text-align:left;vertical-align:top;
padding:8px 6px;border-top:1px solid var(--line)}} th{{width:34%;color:var(--muted);font-weight:500}}
.foot{{font-size:12px;margin-top:18px}}
</style></head><body><main>
<h1>TimesFM test</h1>
<p>A trial page, not part of the app yet. Each blue fan is what Google's TimesFM 2.5 forecast
{HORIZON} candles ahead at a MACD buy or sell, using only the candles before it. The gold fan is
its forecast now. Red steps are each buy's trailing stop, green dashes its take-profit, and a
cross marks the exit.</p>
<div class="tabs">{tabs}</div>
{"".join(panes)}
<p class="foot">Built {stamp}. Paper-trading research output, not advice. The shaded band runs from
the 10th to the 90th percentile of the forecast.</p>
</main><script>
document.querySelectorAll('.tab').forEach(function(b){{b.onclick=function(){{
document.querySelectorAll('.tab').forEach(function(t){{t.classList.toggle('on',t===b)}});
document.querySelectorAll('.pane').forEach(function(p){{var on=p.dataset.k===b.dataset.k;p.hidden=!on;
if(on)p.querySelectorAll('.js-plotly-plot').forEach(function(g){{Plotly.Plots.resize(g)}})}})}}}});
</script></body></html>'''


def publish(src: Path) -> None:
    """Copy the page to test/timesfm.html on gh-pages, unlinked from the app."""
    pages = REPO.parent / "pages-test"
    subprocess.run(["git", "fetch", "-q", "origin", "gh-pages"], cwd=REPO, check=True)
    if pages.exists():
        subprocess.run(["git", "worktree", "remove", "--force", str(pages)], cwd=REPO, check=False)
    subprocess.run(["git", "worktree", "add", "-q", "--detach", str(pages), "origin/gh-pages"], cwd=REPO, check=True)
    try:
        (pages / "test").mkdir(exist_ok=True)
        shutil.copy(src, pages / "test" / "timesfm.html")
        subprocess.run(["git", "add", "test/timesfm.html"], cwd=pages, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "TimesFM test page"], cwd=pages, check=True)
        subprocess.run(["git", "push", "-q", "origin", "HEAD:gh-pages"], cwd=pages, check=True)
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(pages)], cwd=REPO, check=False)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--publish", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    m = model()
    recs, figs = [], []
    for sym, frame, source in SYMBOLS:
        r, f = build(sym, frame, source, m)
        print(json.dumps(r), flush=True)
        recs.append(r)
        figs.append(f)
    # The same charts as data, for the app page to draw (demo_site.py --forecast).
    (OUT / "charts.json").write_text(json.dumps(
        [dict(rec=r, fig=json.loads(f.to_json())) for r, f in zip(recs, figs)]))
    figs = [f.to_html(full_html=False, include_plotlyjs=False,
                      config=dict(displaylogo=False, responsive=True)) for f in figs]
    stamp = datetime.now(timezone.utc).strftime("%d %B %Y, %H:%M UTC")
    html = OUT / "timesfm-test.html"
    html.write_text(page(recs, figs, stamp))
    (OUT / "timesfm-test.json").write_text(json.dumps(dict(
        built=stamp, model="google/timesfm-2.5-200m-pytorch", horizon=HORIZON, context=CONTEXT,
        geometry=GEOMETRY, fee_per_side=FEE, scored_years=SCORED_YEARS, symbols=recs), indent=1))
    print(f"wrote {html}")
    if a.publish:
        publish(html)
        print("published to https://seamusrobertmurphy.github.io/swing-trader/test/timesfm.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
