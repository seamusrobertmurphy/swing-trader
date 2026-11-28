"""A one-page run report and its signals table, written at the end of a demo run.

    import demo_report
    record["report"] = demo_report.write(record, cfg, scored, out)

Operator request, 26 September 2026 (round three, task 5). The report gives the
run's settings, every symbol assessed with the call made on it, the price of
the strongest signals with their entry and horizon marked, the validation and
test scores of every model fitted, links to each symbol's chart and to the
glossary, and a link back to the run's paper trades, which settle over the
coming days. While the app is public the symbols link to TradingView chart
pages, never to an order screen, and the footer says the report is a
paper-trading research output and not advice.
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench_config as bc          # noqa: E402
import build_dataset_1h as bd      # noqa: E402
import demo_run as dr              # noqa: E402

SITE = "https://seamusrobertmurphy.github.io/swing-trader/"
GLOSSARY = "https://github.com/seamusrobertmurphy/swing-trader/blob/main/docs/glossary.md"
TERMS = [("candle", "candle"), ("horizon", "horizon"), ("after-cost return", "after-cost-return"),
         ("taken and skipped", "taken-and-skipped"), ("validation set", "validation-set"),
         ("test set", "test-set"), ("Theil's U2", "theils-u2"), ("edge floor", "edge-floor")]
NAMES = {"RF": "Random forest", "LogReg.glm": "Logistic regression", "LogReg.enet": "Elastic-net logistic",
         "LightGBM": "LightGBM", "HistGBM": "Histogram boosting", "GBM.classic": "Gradient boosting"}
SIZES = {"15m": "15-minute", "30m": "30-minute", "1h": "1-hour", "2h": "2-hour", "4h": "4-hour",
         "6h": "6-hour", "8h": "8-hour", "12h": "12-hour", "1d": "1-day"}
INK, MUTED, BLUE, ORANGE = "#32302f", "#8a8378", "#1f6fb2", "#c9772e"


def preset_name(cfg: dict) -> str:
    """The preset a run's settings match, or custom settings."""
    try:
        presets = json.loads((Path(__file__).resolve().parent / "demo_presets.json").read_text())
    except (OSError, ValueError):
        return "custom settings"
    mk = cfg["data"].get("market", "crypto")
    mine = (tuple(cfg["model"]["estimators"]), cfg["data"]["frame"], cfg["label"]["kind"],
            int(cfg["label"]["horizon_bars"]), sorted(cfg["data"]["symbols"].replace("/", "").split()))
    for p in presets.values():
        c = p[mk]
        syms = c["data"]["symbols"]
        syms = syms.split() if isinstance(syms, str) else syms
        theirs = (tuple(c["model"]["estimators"]), c["data"]["frame"], c["label"]["kind"],
                  int(c["label"]["horizon_bars"]), sorted(s.replace("/", "") for s in syms))
        if mine == theirs:
            return f"the {p['label']} preset"
    return "custom settings"


def closes(cfg: dict, symbol: str, n: int = 90) -> pd.DataFrame:
    frame = cfg["data"]["frame"]
    if cfg["data"].get("market") == "equity":
        import build_dataset_equity as be
        d = be.load_symbol(symbol)
    else:
        d = bd.load_coin(str(dr.DATA_ROOT / bc.KLINE_ROOTS[frame]), symbol.replace("/", ""))
    return d[["datetime", "close"]].tail(n)


def chart_url(symbol: str, market: str) -> str:
    return (f"https://www.tradingview.com/symbols/{symbol}/" if market == "equity"
            else f"https://www.tradingview.com/symbols/BINANCE-{symbol.replace('/', '')}/")


def write(record: dict, cfg: dict, scored: dict, out: Path) -> dict:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    run_id, market = record["run_id"], cfg["data"].get("market", "crypto")
    folder = out / "runs" / run_id
    folder.mkdir(parents=True, exist_ok=True)
    tix = sorted(record.get("tickets", []), key=lambda t: -(t.get("score") or 0))

    # The signals table, in full, as CSV.
    cols = ["symbol", "call", "direction", "confidence", "expected_after_cost", "score", "entry_time",
            "entry_price", "expires", "model", "timeframe", "horizon_candles"]
    with open(folder / "signals.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for t in tix:
            taken = t["call"] == "BUY"
            w.writerow([t["symbol"], "taken" if taken else "skipped", "up" if taken else "none",
                        t.get("confidence"), t.get("expected"), t.get("score"), t["entry_time"],
                        t["entry_price"], t["due"], t.get("model"), t.get("frame"), t.get("horizon_bars")])

    fig = plt.figure(figsize=(8.5, 11))
    fig.patch.set_facecolor("white")
    y = 0.965
    fig.text(0.06, y, "Swing-trader run report", fontsize=16, weight="bold", color=INK)
    started = datetime.fromisoformat(record["started"]).strftime("%d %B %Y, %H:%M UTC")
    head = [f"Run {run_id}, {started}, by {record.get('name') or 'anonymous'}.",
            f"{'US stocks on Alpaca' if market == 'equity' else 'Crypto on Binance'}, "
            f"{SIZES.get(cfg['data']['frame'], cfg['data']['frame'])} candles, {preset_name(cfg)}.",
            f"Model fitted {NAMES.get(record.get('chosen'), record.get('chosen'))}, "
            f"{'three-way' if cfg['label']['kind'] == 'three-way' else 'win or loss'} over "
            f"{cfg['label']['horizon_bars']} candles; test set from {record.get('cut')}, "
            f"{record.get('n_train', 0):,} training and {record.get('n_test', 0):,} test candles."]
    for i, line in enumerate(head):
        fig.text(0.06, y - 0.03 - i * 0.02, line, fontsize=9, color=INK)

    # Signals. The table's height follows its rows, and everything below it
    # starts where it ends, so a short table leaves no gap.
    rows_n = min(len(tix), 20)
    th = 0.03 + 0.0175 * (rows_n + 1)
    top_y = 0.86
    ax = fig.add_axes([0.06, top_y - th, 0.88, th])
    ax.axis("off")
    ax.set_title("Signals, every symbol assessed", loc="left", fontsize=11, color=INK)
    rows = [[t["symbol"], "Taken" if t["call"] == "BUY" else "Skipped", "Up" if t["call"] == "BUY" else "None",
             f"{t.get('confidence', '')} of 5",
             "" if t.get("expected") is None else f"{t['expected'] * 100:+.2f}%",
             pd.Timestamp(t["due"]).strftime("%d %b %H:%M")] for t in tix[:20]]
    if rows:
        tb = ax.table(cellText=rows, colLabels=["Symbol", "Call", "Direction", "Confidence",
                                                "Expected after cost", "Expires, UTC"],
                      loc="upper left", cellLoc="left", colLoc="left",
                      colWidths=[0.15, 0.12, 0.12, 0.14, 0.22, 0.2])
        tb.auto_set_font_size(False)
        tb.set_fontsize(7.5)
        tb.scale(1, 1.15)
        for (r, c), cell in tb.get_celld().items():
            cell.set_edgecolor("#e6e3dd")
            if r == 0:
                cell.set_text_props(weight="bold", color=MUTED)

    # Price of the strongest signals, with entry and horizon marked.
    chart_top = top_y - th - 0.05
    ax = fig.add_axes([0.08, chart_top - 0.22, 0.86, 0.22])
    top = [t for t in tix if t["call"] == "BUY"][:3] or tix[:3]
    for i, t in enumerate(top):
        try:
            d = closes(cfg, t["symbol"])
        except Exception:                               # noqa: BLE001
            continue
        if d.empty:
            continue
        x = pd.to_datetime(d["datetime"]).dt.tz_localize(None)
        yv = d["close"].to_numpy(float) / float(d["close"].iloc[0]) * 100
        col = [BLUE, ORANGE, "#2f7d62"][i % 3]
        ax.plot(x, yv, color=col, linewidth=1.3, label=t["symbol"])
        entry, due = pd.Timestamp(t["entry_time"]).tz_localize(None), pd.Timestamp(t["due"]).tz_localize(None)
        ax.scatter([entry], [yv[-1]], color=col, zorder=5, s=18)
        ax.axvspan(entry, due, color=col, alpha=0.08)
    ax.set_title("Price of the strongest signals, first candle = 100; the shaded span is each "
                 "trade's horizon", loc="left", fontsize=9.5, color=INK)
    ax.tick_params(labelsize=7, colors=MUTED)
    for s_ in ax.spines.values():
        s_.set_color("#e6e3dd")
    if top:
        ax.legend(fontsize=7, frameon=False, loc="upper left")

    # Validation against test scores, ranked on validation.
    score_top = chart_top - 0.22 - 0.06
    ax = fig.add_axes([0.3, max(0.14, score_top - 0.17), 0.64, min(0.17, score_top - 0.14)])
    three = cfg["label"]["kind"] == "three-way"
    models = record.get("models") or []
    key_v, key_t = ("cv_top", "blind_top") if three else ("cv_u2", "blind_u2")
    ms = [m for m in models if m.get(key_v) is not None and m.get(key_t) is not None]
    ms.sort(key=lambda m: (-m[key_v] if three else m[key_v]))
    ms = ms[:8][::-1]
    lab = [NAMES.get(m["model"], m["model"]) + (" " + ",".join(f"{k}={v}" for k, v in m["params"].items())
                                                 if m.get("params") else "") for m in ms]
    scale = 100 if three else 1
    # Bars run from the reference line, 0 per cent or a U2 of 1, so the
    # differences between models are visible rather than lost against zero.
    base = 0 if three else 1
    yy = np.arange(len(ms))
    ax.barh(yy + 0.18, [m[key_v] * scale - base for m in ms], left=base, height=0.34, color=BLUE, label="validation")
    ax.barh(yy - 0.18, [m[key_t] * scale - base for m in ms], left=base, height=0.34, color=ORANGE, label="test set")
    ax.set_yticks(yy)
    ax.set_yticklabels([s[:38] for s in lab], fontsize=6.5)
    ax.tick_params(axis="x", labelsize=7, colors=MUTED)
    ax.axvline(0 if three else 1, color=MUTED, linewidth=0.8, linestyle="--")
    ax.set_title(("Top fifth after cost, per cent" if three else "Theil's U2, below 1 beats a constant guess")
                 + ", validation against test", loc="left", fontsize=9.5, color=INK)
    ax.set_ylim(-0.7, max(len(ms), 3) - 0.3)             # one model does not fill the box
    ax.legend(fontsize=7, frameon=False, loc="upper right")
    for s_ in ax.spines.values():
        s_.set_color("#e6e3dd")

    # Links, follow-up and the footer.
    x0, yl = 0.06, 0.115
    fig.text(x0, yl, "Charts:", fontsize=8, color=MUTED)
    x = x0 + 0.06
    for t in tix[:10]:
        txt = fig.text(x, yl, t["symbol"].replace("/USDT", ""), fontsize=8, color=BLUE,
                       url=chart_url(t["symbol"], market))
        txt.set_url(chart_url(t["symbol"], market))
        x += 0.012 * (len(t["symbol"].replace("/USDT", "")) + 2)
    fig.text(x0, yl - 0.018, "Glossary:", fontsize=8, color=MUTED)
    for i, (word, slug) in enumerate(TERMS):
        fig.text(x0 + 0.075 + 0.2 * (i % 4), yl - 0.018 - 0.015 * (i // 4), word, fontsize=8, color=BLUE,
                 url=f"{GLOSSARY}#{slug}")
    yl -= 0.015
    fig.text(x0, yl - 0.042, "These paper trades settle over the coming days. See how they did on the "
             "Ledger page:", fontsize=8.5, color=INK)
    fig.text(x0, yl - 0.058, f"{SITE}#panel-C2", fontsize=8.5, color=BLUE, url=f"{SITE}#panel-C2")
    fig.text(x0, 0.012, "A paper-trading research output from a public demo, not investment advice. "
             "No order was placed.", fontsize=7.5, color=MUTED)
    fig.savefig(folder / "report.pdf")
    plt.close(fig)
    return dict(pdf=f"runs/{run_id}/report.pdf", csv=f"runs/{run_id}/signals.csv")
