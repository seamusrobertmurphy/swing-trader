"""Every chart the control centre draws, one function per chart.

The first design of the page drew nothing at all across fifteen panels, which
the operator reported on 8 September 2026 as the largest of its five defects.
This module is the answer. Each entry in CHARTS is a name, a caption and a
function returning a matplotlib figure; the app serves them as PNG from
/chart/<name>.png and a panel names the ones it wants.

Two rules hold throughout.

A chart reads a saved record or the built panel. Nothing here fits a model or
rebuilds a frame, because a page that refits on every reload is a page nobody
can leave open, and this machine is already deep in swap.

A chart that has nothing to draw says so on the axes rather than raising or
returning an empty box. A blank panel is indistinguishable from a broken one.
"""

from __future__ import annotations

import contextvars
import glob
import json
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")                     # headless, and no style files: the
import matplotlib.pyplot as plt           # exFAT volume scatters ._*.mplstyle
import numpy as np                        # which matplotlib reads and dies on

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "04-outputs" / "AA-evals"

# The cheat sheet's palette, so a colour here means what it means there.
INK, SOFT, RULE = "#16202c", "#4a5866", "#c3cedb"
BLUE, PURPLE, GREEN, ORANGE, NAVY, RED = (
    "#0d5f8a", "#6b3fa0", "#0e7a5f", "#a8560c", "#1c4f8f", "#a01c1c")
SERIES = [BLUE, GREEN, ORANGE, PURPLE, NAVY, RED, SOFT]

# One colour per feature family, held here so a family is the same colour on
# every chart that draws it and the eye can follow one from the composition to
# the importance. Chosen to stay apart on a light ground and not to rely on the
# red-green pair, which is the one a colour-blind reader loses.
FAMILY_COLOUR = {
    "f_wc_":     "#0d5f8a",   # wall-clock windows
    "f_hr_":     "#3f8fbf",   # intraday windows
    "f_ta_":     "#0e7a5f",   # in-house oscillators
    "f_ta_pta_": "#4fae8b",   # pandas-ta block
    "f_tl_":     "#7ec4a6",   # TA-Lib block
    "f_st_":     "#a8560c",   # triple Supertrend
    "f_mst_":    "#d08a3a",   # adaptive Supertrend
    "f_btc_":    "#6b3fa0",   # relative strength against bitcoin
    "f_4h_":     "#8f6fc0",   # four-hour context
    "f_d1_":     "#b09ad8",   # daily context
    "f_w1_":     "#cdbde8",   # weekly context
    "f_flow_":   "#1c4f8f",   # trade-flow imbalance
    "f_rg_":     "#a01c1c",   # regime state
    "f_ms_":     "#c8626b",   # microstructure
}


def _dress(ax):
    """The house styling for one axis, so a figure with two of them matches.

    Split out of _fig on 9 September 2026 for the indicator overlay, which draws
    price above and the MACD below on the same figure; before this the second
    axis carried matplotlib's own defaults and the two halves did not look like
    one chart.
    """
    ax.set_facecolor("white")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(RULE)
    ax.tick_params(colors=SOFT, labelsize=7, length=3)
    ax.yaxis.label.set(color=SOFT, size=7.5)
    ax.xaxis.label.set(color=SOFT, size=7.5)
    ax.title.set(color=INK, size=8.5, fontweight="bold")
    ax.grid(axis="y", color=RULE, alpha=0.35, linewidth=0.6)
    ax.set_axisbelow(True)
    return ax


# The resolution one draw is rendered at, as a multiple of the page's own 110
# dots per inch. A ContextVar, not a plain module-level number, because the app
# serves threaded and two simultaneous requests through a shared global would
# each get whatever scale the other set last.
#
# Scale multiplies the DOTS, never the inches. Multiplying figsize would give a
# larger canvas with the same point-sized text on it, so every label would come
# out proportionally smaller and the chart would be a big picture of small
# writing; multiplying dpi re-rasterises the same drawing at more pixels, so
# every element keeps its share of the frame and the text is genuinely sharper
# rather than magnified.
_SCALE = contextvars.ContextVar("chart_scale", default=1.0)

# The full-page render. 2.4 turns a 462 by 286 pixel chart into 1109 by 686,
# which fills a viewport without producing a file slow to open.
LARGE_SCALE = 2.4


def _fig(w=4.2, h=2.6):
    fig, ax = plt.subplots(figsize=(w, h), dpi=110 * _SCALE.get())
    _dress(ax)
    return fig, ax


def _nothing(ax, why: str):
    """Say what is absent, on the axes, rather than drawing an empty box."""
    ax.text(0.5, 0.5, why, ha="center", va="center", fontsize=7.5,
            color=SOFT, wrap=True, transform=ax.transAxes)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)


def _records(pattern: str, limit: int | None = None) -> list[Path]:
    hits = [Path(p) for p in glob.glob(str(EVALS / pattern))
            if not os.path.basename(p).startswith("._")]
    hits.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return hits[:limit] if limit else hits


def _json(pattern: str, limit: int | None = None) -> list[dict]:
    out = []
    for p in _records(pattern, limit):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return out


# ---------------------------------------------------------------------------
# Raw bars, and the indicator engines that read them.
#
# The built Parquet panels carry symbol, datetime, in_sample, label, trade_ret
# and the feature columns, and nothing else: every feature is a ratio or a flag,
# because a model that spans 600 coins can never see a raw price. So the two
# indicator charts had no price to draw and said so on the axes for weeks. The
# bars themselves were on disk the whole time, in the same binance.vision
# archives the panels were built from, which is what these two helpers reach.
# ---------------------------------------------------------------------------

# Which archive folder holds the bars for each frame the bench offers. The daily
# archive is the unsuffixed one because that is what acquire_vision wrote before
# the interval suffix existed; slice_4h_40k is a cut of the four-hour panel and
# shares its bars. eq1d is absent on purpose: the equity frame comes from Alpaca
# and has no Binance archive behind it.
KLINE_ROOTS = {"5m": "klines_5m", "1h": "klines_1h", "4h": "klines_4h",
               "1d": "klines", "slice_4h_40k": "klines_4h"}


def _interval(frame: str) -> str:
    """The bar size a frame is made of, which is not always its name.

    slice_4h_40k is a cut of the four-hour panel, so a chart drawn on its bars
    is a four-hour chart; titling it "slice_4h_40k bars" names the file rather
    than the bar and reads as a sixth bar size that does not exist.
    """
    if frame == "eq1d":
        return "daily"
    root = KLINE_ROOTS.get(frame, "")
    return root.split("_")[1] if "_" in root else ("1d" if root else frame)

_ENGINES: dict = {}


def _engine(name: str):
    """One of the lab engines, imported by file path and held for the process.

    They live under 04-outputs, which is the notebook's working area and not a
    package, so import by name cannot reach them. Loading by path is what lets
    the panel run the same MACD and confluence code the workflow documents
    rather than a second copy of its arithmetic. Cached because exec_module on
    every page load would re-run three modules for every chart.
    """
    import importlib.util
    import sys

    if name in _ENGINES:
        return _ENGINES[name]
    path = {"macd": REPO / "04-outputs" / "1A-macd" / "macd.py",
            "confluence": REPO / "04-outputs" / "1B-confluence" / "confluence.py",
            "fib": REPO / "04-outputs" / "1C-fibonacci" / "fib.py"}[name]
    spec = importlib.util.spec_from_file_location(f"lab_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"lab_{name}"] = mod
    spec.loader.exec_module(mod)
    _ENGINES[name] = mod
    return mod


def _alpaca_bars(cfg: dict, bars: int):
    """The equity store's own daily bars, for the symbol this run charts.

    One small adjusted-daily Parquet per ticker, written by alpaca_data.py with
    adjustment=ALL, which is the reason the sector funds' December 2025 split
    does not halve the series here the way it did on the dashboard.
    """
    import bench_config as bc
    import pandas as pd

    root = REPO / "03-inputs" / "alpaca-data" / "daily"
    if not root.is_dir():
        return None, "no Alpaca daily store on disk; run the bar download first"
    wanted = [str(cfg["viz"].get("viz_symbol") or "").strip()] + bc.symbols_for(cfg)
    wanted.append(bc.MARKETS["equity"]["benchmark"])
    # Named files rather than a glob: the store holds 2,702 tickers and listing
    # them all cost a third of a second on every page load to find one.
    hit = next(((s, root / f"{bc.canonical(s)}.parquet") for s in wanted
                if s and (root / f"{bc.canonical(s)}.parquet").exists()), None)
    if hit is None:
        return None, (f"none of {', '.join(s for s in wanted if s)} is in the "
                      f"Alpaca daily store")
    pick, path = hit
    d = pd.read_parquet(path,
                        columns=["datetime", "open", "high", "low", "close", "volume"])
    d = (d.dropna(subset=["close"]).sort_values("datetime")
         .tail(bars + 260).reset_index(drop=True))
    # The bars carry a timezone; matplotlib and the engines want a plain stamp.
    d["datetime"] = pd.to_datetime(d["datetime"]).dt.tz_localize(None)
    if len(d) < 60:
        return None, f"{pick} has only {len(d)} daily bars in the store"
    return (bc.canonical(pick), "eq1d"), d


def _klines(cfg: dict, bars: int):
    """The last `bars` raw OHLCV bars for the symbol this run charts.

    Returns (symbol, frame) with a DataFrame, or (None, reason) naming what was
    missing. Only the tail archives are opened: a symbol's four-hour history is
    128 monthly zips and a 400-bar chart needs three of them, so reading the lot
    would cost a third of a second on every page load for nothing.

    The zip reader and the timestamp parser come from build_dataset_1h because
    Binance switched from millisecond to microsecond stamps mid-2025 and some
    symbols carry both inside one folder; a second copy of that rule here is a
    second place for it to be wrong.
    """
    import bench_config as bc
    import build_dataset_1h as bd
    import pandas as pd

    market = cfg["data"].get("market", "crypto")
    frame = cfg["data"].get("frame", "")
    if market == "equity":
        # The engines take any OHLCV frame and never cared where it came from,
        # which is what analysis_charts.py already relies on: the equity store
        # is read here rather than refused, because equities are the market the
        # book actually trades.
        return _alpaca_bars(cfg, bars)
    root = REPO / "03-inputs" / "binance-data" / KLINE_ROOTS.get(frame, "")
    if not KLINE_ROOTS.get(frame) or not root.is_dir():
        return None, f"no kline archive on disk for the {frame} frame"

    folders = {bc.canonical(d.name): d.name for d in root.iterdir() if d.is_dir()}
    wanted = [str(cfg["viz"].get("viz_symbol") or "").strip()] + bc.symbols_for(cfg)
    wanted.append(bc.MARKETS[market]["benchmark"])       # the fallback, never a guess
    pick = next((folders[bc.canonical(s)] for s in wanted
                 if s and bc.canonical(s) in folders), None)
    if pick is None:
        return None, (f"none of {', '.join(s for s in wanted if s)} has bars in "
                      f"{root.name}, which holds {len(folders)} symbols")

    zips = sorted(p for p in (root / pick).glob("*.zip")
                  if not p.name.startswith("._"))
    if not zips:
        return None, f"{pick} has a folder in {root.name} but no archives in it"
    frames, got = [], 0
    for p in reversed(zips):                             # newest month first
        try:
            part = bd._read_kline_zip(str(p))
        except Exception:                                # noqa: BLE001
            continue                                     # a truncated month, not a failure
        frames.append(part)
        got += len(part)
        if got >= bars + 260:        # the slow moving average needs 200 bars of
            break                    # run-up before the first bar it is drawn on
    if not frames:
        return None, f"every archive under {pick} failed to open"
    d = pd.concat(frames[::-1], ignore_index=True)
    d["datetime"] = bd._to_datetime(d["open_time"])
    for c in ("open", "high", "low", "close", "volume"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = (d.dropna(subset=["close"]).drop_duplicates("datetime")
         .sort_values("datetime").tail(bars + 260).reset_index(drop=True))
    return (pick, frame), d


def _macd_cfg(cfg: dict):
    """The MACD engine's own configuration, driven from the Signals section.

    So a change on the panel changes the picture. Left to its defaults the
    engine draws the classic 12/26/9 whatever the panel says, which is the
    failure this exists to stop.
    """
    s = cfg["signals"]
    return _engine("macd").MACDConfig(
        fast=int(s["macd_fast"]), slow=int(s["macd_slow"]),
        signal=int(s["macd_signal"]), noise_k=float(s["macd_noise_k"]),
        confirm_bars=int(s["macd_confirm_bars"]))


def _conf_cfg(cfg: dict):
    """The confluence engine's configuration, likewise from the Signals section."""
    s = cfg["signals"]
    lab = _engine("confluence")
    return lab.ConfluenceConfig(
        ma_fast=int(s["ma_fast"]), ma_slow=int(s["ma_slow"]),
        macd=_macd_cfg(cfg),
        fib=_engine("fib").FibConfig(lookback=int(s["fib_lookback"]),
                                     min_swing_frac=float(s["fib_min_swing_frac"])),
        candle_decay=int(s["candle_decay"]),
        threshold=float(s["confluence_threshold"]))


# ---------------------------------------------------------------------------
# Column A. Data
# ---------------------------------------------------------------------------

def cost_by_frame():
    """What a round trip costs per year of holding, by bar size.

    The fee is flat per trade, so the bar size decides how often it is paid. This
    is the arithmetic that ruled out the five-minute frame and it belongs beside
    the choice of bar size rather than in a panel of its own.
    """
    import bench_config as bc

    cfg = bc.load()
    frames = [("5m", 5), ("15m", 15), ("1h", 60), ("4h", 240), ("1d", 1440)]
    # train_model.COST_PCT: 0.15 per cent round-trip taker fee with the BNB
    # discount plus 0.05 modelled slippage. Restated rather than imported
    # because importing that module pulls scikit-learn and LightGBM into the web
    # process for one float.
    per_trade = 0.20                                   # per cent, round trip
    # The holding period is the label's own horizon, so moving the horizon on
    # this panel moves the chart. Fixed at twenty bars it described a label the
    # bench had not been set to since the horizon field existed.
    horizon = max(1, int(cfg["label"]["horizon_bars"]))
    fig, ax = _fig()
    bars_a_year = [365 * 24 * 60 / m for _n, m in frames]
    cost = [per_trade * (b / horizon) for b in bars_a_year]
    names = [n for n, _m in frames]
    here = _interval(cfg["data"].get("frame", ""))
    cols = [NAVY if n == here else RED if c > 100 else ORANGE if c > 20 else GREEN
            for n, c in zip(names, cost)]
    ax.bar(names, cost, color=cols, width=0.6)
    for x, c in zip(names, cost):
        ax.text(x, c, f"{c:,.0f}%", ha="center", va="bottom", fontsize=7,
                color=INK, fontweight="bold")
    ax.set_yscale("log")
    ax.set_ylabel("fees per year of holding, %")
    ax.set_xlabel("the frame this run is set to is drawn in navy"
                  if here in names else "")
    ax.set_title(f"A round trip costs {per_trade:.2f}%, paid every "
                 f"{horizon} bars")
    fig.tight_layout()
    return fig


def panel_coverage():
    """How many rows each built panel carries, and what it costs to open.

    The row count comes out of the Parquet footer, which is a few kilobytes at
    the end of the file, so a two-gigabyte panel is counted without reading any
    of it. The size is on the bar beside it because on this machine the size is
    the reason a panel is or is not the one to reach for.
    """
    import bench_config as bc
    import pyarrow.parquet as pq

    cfg = bc.load()
    try:
        here = (REPO / bc.dataset_path(cfg)).name
    except ValueError:
        here = ""
    rows = []
    for spec in bc.MARKETS.values():
        for name, rel in spec["frames"].items():
            p = REPO / rel
            if not p.exists():
                continue
            try:
                n = pq.ParquetFile(str(p)).metadata.num_rows
            except Exception:                            # noqa: BLE001
                n = 0                                    # a half-written build
            rows.append((name, n, p.stat().st_size / 2 ** 20, p.name == here))
    fig, ax = _fig()
    if not rows:
        _nothing(ax, "no panel built yet")
        fig.tight_layout(); return fig
    rows.sort(key=lambda r: r[1])
    ax.barh([r[0] for r in rows], [r[1] for r in rows],
            color=[ORANGE if r[3] else BLUE for r in rows], height=0.6)
    for i, (_n, n, mb, _is) in enumerate(rows):
        ax.text(n, i, f"  {n:,} rows, {mb:,.0f} MB", va="center", fontsize=6.5,
                color=INK)
    # Logarithmic, because the panels span 40,000 rows to 5.5 million: on a
    # linear axis the 40k slice, which is the one this machine can actually
    # open, was a bar one pixel wide and its highlight could not be seen.
    ax.set_xscale("log")
    ax.set_xlim(min(r[1] for r in rows if r[1]) * 0.6,
                max(r[1] for r in rows) * 60)
    ax.set_xlabel("rows in the panel, log scale")
    ax.set_title("Panels built; the one this run reads is orange")
    fig.tight_layout()
    return fig


def timeline_span():
    """Where the training window ends and the blind period begins."""
    import bench_config as bc
    import pandas as pd

    fig, ax = _fig(4.2, 2.0)
    cfg = bc.load()
    try:
        path = REPO / bc.dataset_path(cfg)
    except ValueError:
        _nothing(ax, "the chosen bar size does not belong to the chosen market")
        fig.tight_layout(); return fig
    if not path.exists():
        _nothing(ax, f"{path.name} is not built")
        fig.tight_layout(); return fig

    df = pd.read_parquet(path, columns=["datetime"])
    lo, hi = df["datetime"].min(), df["datetime"].max()
    hold = int(cfg["split"]["holdout_days"])
    cut = hi - pd.Timedelta(days=hold)
    span = (hi - lo).days or 1

    ax.barh([0], [(cut - lo).days], left=[0], color=BLUE, height=0.4,
            label="training window")
    ax.barh([0], [hold], left=[(cut - lo).days], color=ORANGE, height=0.4,
            label="blind period")
    ax.set_yticks([])
    ax.set_xlim(0, span)
    ax.set_xlabel(f"days, {lo.date()} to {hi.date()}")
    ax.set_title(f"{span:,} days: {(cut - lo).days:,} to train, {hold} held back")
    ax.legend(fontsize=6.5, frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.35), ncol=2)
    fig.tight_layout()
    return fig


def label_base_rate():
    """The share of bars that hit the take-profit before the stop, by year.

    The barrier's own base rate is what a strategy must beat before fees. On the
    inherited plus two, minus one geometry it sits below the breakeven the same
    geometry implies, so the label loses money by construction.
    """
    import bench_config as bc
    import pandas as pd

    fig, ax = _fig()
    cfg = bc.load()
    try:
        path = REPO / bc.dataset_path(cfg)
    except ValueError:
        _nothing(ax, "no panel selected"); fig.tight_layout(); return fig
    if not path.exists():
        _nothing(ax, f"{path.name} is not built"); fig.tight_layout(); return fig

    df = pd.read_parquet(path, columns=["datetime", "label"])
    by = df.groupby(df["datetime"].dt.year)["label"].mean()
    tgt, stp = cfg["label"]["target_atr"], cfg["label"]["stop_atr"]
    breakeven = stp / (tgt + stp)
    ax.bar([str(y) for y in by.index], by.values,
           color=[GREEN if v >= breakeven else RED for v in by.values], width=0.65)
    ax.axhline(breakeven, color=NAVY, linestyle="--", linewidth=1)
    ax.text(0.99, breakeven, f" breakeven {breakeven:.3f}", ha="right", va="bottom",
            fontsize=6.5, color=NAVY, transform=ax.get_yaxis_transform())
    ax.set_ylabel("share hitting the target first")
    ax.set_title(f"Base rate against breakeven, +{tgt:g} / -{stp:g} ATR")
    fig.tight_layout()
    return fig


def screen_survivors():
    """How many assets clear the liquidity floor, and how the floor moves it."""
    import bench_config as bc
    import pandas as pd

    fig, ax = _fig()
    cfg = bc.load()
    try:
        path = REPO / bc.dataset_path(cfg)
    except ValueError:
        _nothing(ax, "no panel selected"); fig.tight_layout(); return fig
    if not path.exists():
        _nothing(ax, f"{path.name} is not built"); fig.tight_layout(); return fig

    df = pd.read_parquet(path, columns=["symbol", "datetime"])
    per_year = df.groupby(df["datetime"].dt.year)["symbol"].nunique()
    ax.plot(per_year.index, per_year.values, marker="o", color=BLUE, linewidth=1.6,
            markersize=3.5)
    ax.fill_between(per_year.index, 0, per_year.values, color=BLUE, alpha=0.12)
    # Years are whole numbers: left to matplotlib's own locator a five-year span
    # was labelled 2022.0, 2022.5, 2023.0, and half of 2022 is not a year.
    ax.set_xticks(list(per_year.index))
    ax.set_xticklabels([str(y) for y in per_year.index])
    ax.axhline(5, color=ORANGE, linestyle="--", linewidth=1)
    ax.text(0.01, 5, " five-asset floor for a tercile", va="bottom", fontsize=6.5,
            color=ORANGE, transform=ax.get_yaxis_transform())
    ax.set_ylabel("assets present")
    ax.set_title("Assets in the panel, by year")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Column B. Variables
# ---------------------------------------------------------------------------

def family_composition():
    """How many columns each feature family contributes, and which are offered."""
    import bench_config as bc

    fig, ax = _fig()
    cfg = bc.load()
    try:
        path = REPO / bc.dataset_path(cfg)
    except ValueError:
        _nothing(ax, "no panel selected"); fig.tight_layout(); return fig
    if not path.exists():
        _nothing(ax, f"{path.name} is not built"); fig.tight_layout(); return fig

    # The schema alone, not the data. The discarded line that stood here read the
    # entire panel to look at its column names and cost four seconds a page load.
    import pyarrow.parquet as pq
    names = [c for c in pq.ParquetFile(str(path)).schema.names if c.startswith("f_")]
    counts = Counter()
    for c in names:
        for pre in sorted(bc.FAMILIES, key=len, reverse=True):
            if c.startswith(pre):
                counts[pre] += 1
                break
    chosen = set(cfg["features"].get("families") or [])
    fams = sorted(counts, key=counts.get)
    # A colour per family, so a family keeps the same colour wherever it is
    # drawn and the eye can follow one across charts. A family not offered to
    # the model is greyed rather than recoloured, so the distinction that
    # matters stays the loudest thing on the chart.
    cols_ = [FAMILY_COLOUR.get(f, BLUE) if (not chosen or f in chosen) else RULE
             for f in fams]
    ax.barh(fams, [counts[f] for f in fams], color=cols_, height=0.65)
    for i, f in enumerate(fams):
        ax.text(counts[f], i, f" {counts[f]}", va="center", fontsize=7, color=INK)
    ax.set_xlabel("columns")
    ax.set_title(f"{len(names)} features; "
                 + ("every family offered" if not chosen
                    else f"{sum(counts[f] for f in chosen if f in counts)} offered"))
    fig.tight_layout()
    return fig


def family_importance():
    """Permutation importance by family, from the saved feature report.

    The mean rather than the sum, because feature_report.py writes one row per
    column and the families are not the same size: summing gives the TA-Lib
    block fifteen chances to accumulate and relative strength against bitcoin
    seven, which reports how many columns a family has rather than what any of
    them is worth.
    """
    import csv

    fig, ax = _fig()
    hits = _records("*/feature-report-*.csv", 1)
    if not hits:
        _nothing(ax, "no feature report on disk.\nRun it from the panel below.")
        fig.tight_layout(); return fig
    rows = list(csv.DictReader(hits[0].open()))
    head = set(rows[0]) if rows else set()
    # feature_report.py names the permutation column "in_company": how much the
    # Brier score moves when that one column is shuffled with the rest of the
    # model intact. The discarded search for a header containing "perm" or
    # "import" matched nothing in that file, so this chart had been drawing a
    # "no importance column" box against a report that had one all along.
    if not {"feature", "in_company"} <= head:
        _nothing(ax, f"{hits[0].name}\ncarries {', '.join(sorted(head)) or 'no columns'}, "
                     f"not the in_company permutation column")
        fig.tight_layout(); return fig
    vals: dict[str, list] = {}
    for r in rows:
        fam = r.get("family") or ("_".join(r["feature"].split("_")[:2]) + "_")
        try:
            vals.setdefault(fam, []).append(float(r["in_company"]))
        except (TypeError, ValueError):
            continue
    if not vals:
        _nothing(ax, f"{hits[0].name}\nhas no numeric importance in it")
        fig.tight_layout(); return fig
    mean = {f: sum(v) / len(v) for f, v in vals.items()}
    fams = sorted(mean, key=mean.get)[-10:]
    ax.barh(fams, [mean[f] for f in fams],
            color=[FAMILY_COLOUR.get(f, GREEN) for f in fams], height=0.65)
    ax.axvline(0, color=SOFT, linewidth=0.9)
    for i, f in enumerate(fams):
        ax.text(mean[f], i, f" {len(vals[f])} col", va="center", fontsize=6,
                color=SOFT, ha="left" if mean[f] >= 0 else "right")
    best = fams[-1]
    lead = (f", {mean[best] / mean[fams[-2]]:.1f} times the next"
            if len(fams) > 1 and mean[fams[-2]] > 0 else "")
    ax.set_xlabel(f"mean permutation importance, Brier score  ({hits[0].name})")
    ax.xaxis.label.set(size=6)
    ax.set_title(f"{best} leads {len(rows)} features{lead}")
    fig.tight_layout()
    return fig


def univariate_ranking():
    """Each candidate fitted alone against an intercept-only null.

    The likelihood ratio statistic is twice the difference in log-likelihood
    between a model with one predictor and one with none. Under the null it is
    chi-squared on one degree of freedom, so 3.84 is the five per cent point and
    6.63 the one per cent point. Ranked by magnitude, which is what the operator
    asked variable selection to report.
    """
    fig, ax = _fig(4.2, 3.0)
    hits = _records("varselect/univariate-*.json", 1)
    if not hits:
        _nothing(ax, "no univariate screen on disk yet.\n"
                     "Run variable selection from this panel.")
        fig.tight_layout(); return fig
    rows = json.loads(hits[0].read_text())["rows"][:14]
    names = [r["feature"] for r in rows][::-1]
    lrs = [r["lr"] for r in rows][::-1]
    cols = [GREEN if v > 6.63 else ORANGE if v > 3.84 else RULE for v in lrs]
    ax.barh(names, lrs, color=cols, height=0.7)
    for x, c, lab in ((3.84, NAVY, "5%"), (6.63, PURPLE, "1%")):
        ax.axvline(x, color=c, linestyle="--", linewidth=1)
        ax.text(x, len(names) - 0.4, f" {lab}", fontsize=6.5, color=c)
    ax.set_xlabel("likelihood ratio against an intercept-only model")
    ax.set_title("Each predictor alone, ranked")
    ax.tick_params(axis="y", labelsize=6)
    fig.tight_layout()
    return fig


def enet_path():
    """Binomial deviance against the penalty, the glmnet cross-validation curve.

    Read from the numbers the screen saved beside its own figure. Nothing is
    refitted here: one curve is sixty penalties by ten folds, six hundred
    logistic fits, which is a job with a Run button and not a chart.

    Where only the figure is on disk, from a screen that ran before the numbers
    were saved alongside it, that figure is shown instead and the panel says
    which file and when, rather than pointing the reader at a path.
    """
    fig, ax = _fig(4.6, 3.0)
    doc = _json("varselect/cv_curve.json", 1)
    if not doc:
        png = _records("varselect/cv_curve.png", 1)
        if not png:
            _nothing(ax, "no elastic-net screen on disk yet.\n"
                         "Run variable selection from this panel.")
            fig.tight_layout(); return fig
        when = datetime.fromtimestamp(png[0].stat().st_mtime)
        ax.imshow(plt.imread(str(png[0])))
        ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_title(f"As the screen drew it, {when:%d %B %Y}", pad=4)
        fig.tight_layout()
        return fig

    d = doc[0]
    x = np.asarray(d["loglam"], dtype=float)
    mean = np.asarray(d["mean"], dtype=float)
    se = np.asarray(d["se"], dtype=float)
    ax.errorbar(x, mean, yerr=se, fmt="o", ms=2.6, color=RED, ecolor=RULE,
                elinewidth=0.8, capsize=1.5, zorder=3)
    for i, col, lab in ((d["i_min"], NAVY, "best"), (d["i_1se"], PURPLE, "one s.e.")):
        ax.axvline(x[i], color=col, linestyle="--", linewidth=1)
        ax.text(x[i], mean.max(), f" {lab}, {int(d['nonzero'][i])} kept",
                fontsize=6.5, color=col, rotation=90, va="top")
    ax.set_xlabel(r"log($\lambda$), the penalty; harder to the right")
    ax.set_ylabel(d.get("metric", "binomial deviance"))
    top = ax.twiny()                     # glmnet's own top axis: what survives
    top.set_xlim(ax.get_xlim())
    idx = np.linspace(0, len(x) - 1, 8).round().astype(int)
    top.set_xticks(x[idx])
    top.set_xticklabels([str(int(d["nonzero"][i])) for i in idx], fontsize=6)
    top.tick_params(colors=SOFT, length=2)
    for side in ("left", "right", "bottom"):
        top.spines[side].set_visible(False)
    top.spines["top"].set_color(RULE)
    ax.set_title(f"{int(d['nonzero'][d['i_1se']])} of {len(d['names'])} features "
                 f"survive at one standard error", pad=16)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Column C. Modelling
# ---------------------------------------------------------------------------

def split_diagram():
    """Training, embargo and blind, drawn to scale with the fold boundaries."""
    import bench_config as bc

    cfg = bc.load()
    folds = int(cfg["split"]["folds"])
    hold = int(cfg["split"]["holdout_days"])
    fig, ax = _fig(4.2, 2.2)
    total = 100
    blind = min(45, max(8, 100 * hold / max(hold * 3, 365 * 2)))
    train = total - blind - 3
    ax.barh([1], [train], color=BLUE, height=0.35, label="training")
    ax.barh([1], [3], left=[train], color=ORANGE, height=0.35, label="embargo")
    ax.barh([1], [blind], left=[train + 3], color=NAVY, height=0.35, label="blind")
    for k in range(1, folds + 1):
        x = train * k / (folds + 1)
        ax.plot([x, x], [0.55, 0.75], color=SOFT, linewidth=1)
        ax.text(x, 0.45, f"{k}", ha="center", fontsize=6, color=SOFT)
    ax.text(train / 2, 0.3, f"{folds} walk-forward folds", ha="center",
            fontsize=6.5, color=SOFT)
    ax.set_ylim(0.1, 1.4); ax.set_yticks([]); ax.set_xticks([])
    ax.set_title(f"Chronological split, {hold}-day blind period")
    ax.legend(fontsize=6.5, frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, 0.18), ncol=3)
    for s in ax.spines.values():
        s.set_visible(False)
    fig.tight_layout()
    return fig


def error_full_vs_cv():
    """In-sample against held-out error, with the overfit bar drawn."""
    fig, ax = _fig()
    docs = _json("*/bench-2*.json", 6)
    pts = [(r["full"]["rmse"], r["cv"]["rmse"], r["model"], r["rmse_ratio"])
           for d in docs for r in (d.get("scores") or [])
           if isinstance(r.get("full"), dict) and isinstance(r.get("cv"), dict)]
    if not pts:
        _nothing(ax, "no bench run on disk yet.\nRun one from the panel below.")
        fig.tight_layout(); return fig
    bar = 1.1
    for f, c, name, ratio in pts:
        ax.scatter(f, c, s=26, color=RED if ratio > bar else GREEN, zorder=3)
    lo = min(min(p[0] for p in pts), min(p[1] for p in pts)) * 0.95
    hi = max(max(p[0] for p in pts), max(p[1] for p in pts)) * 1.05
    xs = np.linspace(lo, hi, 20)
    ax.plot(xs, xs, color=SOFT, linewidth=0.9, linestyle=":")
    ax.plot(xs, xs * bar, color=NAVY, linewidth=1, linestyle="--")
    ax.text(hi, hi * bar, f" ratio {bar}", fontsize=6.5, color=NAVY,
            ha="right", va="bottom")
    ax.set_xlabel("RMSE in sample"); ax.set_ylabel("RMSE cross-validated")
    ax.set_title(f"{len(pts)} fits. Above the dashed line is rejected")
    fig.tight_layout()
    return fig


def reliability_curve():
    """Stated probability against what happened, from the saved calibration."""
    import csv
    fig, ax = _fig()
    hits = _records("*/calibration-*.csv", 1)
    if not hits:
        _nothing(ax, "no calibration record on disk yet")
        fig.tight_layout(); return fig
    rows = list(csv.DictReader(hits[0].open()))
    series = {}
    for r in rows:
        m = r.get("mapping") or r.get("map") or "raw"
        try:
            series.setdefault(m, []).append(
                (float(r.get("mean_predicted") or r.get("predicted")),
                 float(r.get("observed") or r.get("observed_frequency"))))
        except (TypeError, ValueError):
            continue
    if not series:
        _nothing(ax, f"{hits[0].name}\nhas no reliability columns")
        fig.tight_layout(); return fig
    ax.plot([0, 1], [0, 1], color=SOFT, linestyle=":", linewidth=1)
    for (name, pts), col in zip(sorted(series.items()), SERIES):
        pts.sort()
        ax.plot([p[0] for p in pts], [p[1] for p in pts], marker="o",
                markersize=3, linewidth=1.4, color=col, label=name)
    ax.set_xlabel("stated probability"); ax.set_ylabel("observed frequency")
    ax.set_title("A calibrated line sits on the diagonal")
    ax.legend(fontsize=6.5, frameon=False)
    fig.tight_layout()
    return fig


def sweep_ranking():
    """How often each configuration came first, across every sweep on disk."""
    fig, ax = _fig()
    docs = _json("*/bench-sweep-*.json")
    if not docs:
        _nothing(ax, "no sweep on disk yet")
        fig.tight_layout(); return fig
    wins, seen = Counter(), Counter()
    for d in docs:
        order = sorted(d["rows"], key=lambda r: r["cv"]["rmse"])
        wins[order[0]["name"]] += 1
        for r in order:
            seen[r["name"]] += 1
    names = sorted(seen, key=lambda n: wins[n])
    ax.barh(names, [wins[n] for n in names], color=PURPLE, height=0.65)
    for i, n in enumerate(names):
        ax.text(wins[n], i, f" {wins[n]} of {len(docs)}", va="center",
                fontsize=6.5, color=INK)
    ax.set_xlabel("times ranked first")
    ax.set_title(f"Across {len(docs)} sweeps of {len(seen)} configurations")
    ax.tick_params(axis="y", labelsize=6.5)
    fig.tight_layout()
    return fig


def _sweep_fits() -> list[tuple[dict, dict]]:
    """Every configuration fit on disk, paired with the sweep that produced it.

    The sweep records are the only place in this repository where four hundred
    and fifty-six fits sit side by side with the settings that produced each
    one, which is what makes a question about a setting answerable at all. A row
    missing either error is dropped rather than defaulted, because a fit that did
    not finish must not be counted as one that did.
    """
    out = []
    for d in _json("*/bench-sweep-*.json"):
        for r in d.get("rows") or []:
            if isinstance(r.get("full"), dict) and isinstance(r.get("cv"), dict) \
                    and r["full"].get("rmse") is not None \
                    and r["cv"].get("rmse") is not None:
                out.append((d, r))
    return out


def capacity_vs_error():
    """Whether letting the model fit more helps or hurts, across every sweep.

    A straight line through all of these points is a lie, and it was drawn here
    until 9 September 2026. The six configurations fall into two clusters, one
    unconstrained forest at an in-sample RMSE near 0.12 and five constrained ones
    between 0.37 and 0.49, and a regression across two clusters reports the gap
    between them as a slope. Fitted pooled it came out at +0.068 and the title
    read that more fitting improves held-out error; fitted inside each
    configuration the slope is +1.07 in five of the six, which says something
    else entirely, that in-sample and held-out error move together as the
    condition gets harder. So the line is gone and the clusters are drawn as
    clusters, with the quantity that actually separates them, the overfit ratio,
    on the points themselves.
    """
    fig, ax = _fig(4.8, 2.9)
    fits = _sweep_fits()
    if len(fits) < 4:
        _nothing(ax, "fewer than four configuration fits on disk.\n"
                     "Run a sweep from the panel below.")
        fig.tight_layout(); return fig

    by = {}
    for _d, r in fits:
        by.setdefault(r.get("name") or r.get("model") or "unnamed", []).append(r)
    order = sorted(by, key=lambda n: np.mean([r["full"]["rmse"] for r in by[n]]))
    for name, col in zip(order, SERIES):
        rows = by[name]
        x = np.array([r["full"]["rmse"] for r in rows])
        y = np.array([r["cv"]["rmse"] for r in rows])
        ratio = float(np.mean([r.get("rmse_ratio") or np.nan for r in rows]))
        ax.scatter(x, y, s=9, color=col, alpha=0.45, zorder=2)
        ax.scatter([x.mean()], [y.mean()], s=52, color=col, zorder=4,
                   edgecolor="white", linewidth=0.8,
                   label=f"{name}, ratio {ratio:.2f}")

    lean = min(by, key=lambda n: np.mean([r["full"]["rmse"] for r in by[n]]))
    tight = max(by, key=lambda n: np.mean([r["full"]["rmse"] for r in by[n]]))
    gap = (np.mean([r["cv"]["rmse"] for r in by[tight]])
           - np.mean([r["cv"]["rmse"] for r in by[lean]]))
    lean_ratio = float(np.mean([r.get("rmse_ratio") or np.nan for r in by[lean]]))
    ax.set_xlabel("RMSE in sample, lower means it fitted more")
    ax.set_ylabel("RMSE cross-validated")
    ax.set_title(f"The configuration that memorises most is {abs(gap):.4f} "
                 f"{'better' if gap > 0 else 'worse'} held out, at an overfit "
                 f"ratio of {lean_ratio:.2f}", fontsize=7.4)
    ax.legend(fontsize=6.0, frameon=False, loc="center left",
              bbox_to_anchor=(1.0, 0.5))
    fig.tight_layout()
    return fig


def overfit_vs_error():
    """The overfit ratio against the held-out error it bought, for every fit.

    The house rule rejects a ratio above 1.1 whatever the error, and the whole
    question a reader has when they meet that rule is what it costs them. This
    answers it directly: the ratio on one axis, the held-out error on the other,
    the bar drawn, and every fit on disk placed against both.

    The ratio here is cross-validated error over in-sample error, which is the
    direction the house rule expects. It was documented and computed the other
    way up until the September reorganisation, and a model that overfits badly
    scored 0.91 where the rule looks for 1.10, so a reader applying the rule
    would have passed exactly what it exists to catch.
    """
    fig, ax = _fig(4.8, 2.9)
    fits = _sweep_fits()
    pts = [(r["rmse_ratio"], r["cv"]["rmse"], r.get("name") or r["model"])
           for _d, r in fits if r.get("rmse_ratio") is not None]
    if len(pts) < 4:
        _nothing(ax, "no fit on disk carries an overfit ratio")
        fig.tight_layout(); return fig

    bar = 1.1
    by = {}
    for ratio, cv, name in pts:
        by.setdefault(name, []).append((ratio, cv))
    for name, col in zip(sorted(by), SERIES):
        rows = by[name]
        ax.scatter([r for r, _c in rows], [c for _r, c in rows], s=11,
                   color=col, alpha=0.55, zorder=3, label=name)
    ax.axvline(bar, color=RED, linewidth=1.4, zorder=2)
    ax.text(bar, ax.get_ylim()[1], " rejected to the right", fontsize=6.5,
            color=RED, va="top")
    # Log, because an unconstrained forest lands near four and the whole
    # decision happens between one and one and a bit; on a linear axis the
    # rejected cluster pushes every fit that matters into one column of pixels.
    # Plain numbers on the ticks: the scientific labels matplotlib defaults to
    # print the bar as 1.1 x 10 to the nought, which no reader wants to parse.
    from matplotlib.ticker import FixedLocator, NullFormatter, ScalarFormatter
    ax.set_xscale("log")
    # A log axis ticks by decades, and this one spans a single decade, so the
    # default leaves one label reading 1.0 and nothing else on the axis. The
    # ticks are placed by hand over the range the ratios occupy.
    top = max(r for r, _c, _n in pts)
    ax.xaxis.set_major_locator(FixedLocator(
        [t for t in (1.0, 1.1, 1.25, 1.5, 2.0, 3.0, 4.0, 6.0, 10.0) if t <= top * 1.2]))
    ax.xaxis.set_major_formatter(ScalarFormatter())
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xlabel("overfit ratio, cross-validated error over in-sample")
    ax.set_ylabel("RMSE cross-validated")

    passed = [(r, c) for r, c, _n in pts if r <= bar]
    failed = [(r, c) for r, c, _n in pts if r > bar]
    best_p = min((c for _r, c in passed), default=None)
    best_f = min((c for _r, c in failed), default=None)
    if best_p is None:
        say = f"none of {len(pts)} fits pass the {bar} bar"
    elif best_f is None:
        say = f"all {len(pts)} fits pass the {bar} bar"
    else:
        say = (f"best that passes {best_p:.4f}, best rejected {best_f:.4f}, "
               f"a difference of {best_p - best_f:+.4f}")
    ax.set_title(f"{len(passed)} of {len(pts)} fits pass; " + say, fontsize=7.4)
    ax.legend(fontsize=6.0, frameon=False, loc="center left",
              bbox_to_anchor=(1.0, 0.5))
    fig.tight_layout()
    return fig


# The gap between a sweep's winner and its runner-up is only a result if it is
# larger than the noise between repeats of the same configuration. Each sweep
# record carries cv_rmse_sd, the standard deviation of a configuration's
# held-out error across its own repeats, which is exactly that noise measured
# rather than assumed.
#
# The axis-leverage question, which setting moves the answer further than the
# choice of forest does, is answered on the assessment panel by config_effect.
# It is not repeated here: the same analysis under two names on two panels is
# two things to keep in step, and the first module-level name collision between
# them was found on 9 September 2026 within an hour of both existing.


def tuning_stability():
    """Whether the winning configuration is distinguishable from the runner-up.

    A sweep ranks six configurations on held-out error and names the lowest. That
    name is worth acting on only if the gap to the second-placed configuration is
    larger than the amount the same configuration's own error moves when it is
    refitted, and until now nothing on this page has asked. The records already
    carry the answer: each fit reports cv_rmse_sd across its repeats.

    Drawn as two lines over the sweeps, ordered by the gap. Where the gap falls
    under twice the pooled repeat noise of the two configurations concerned, the
    winner of that sweep is a coin flip and its name should not be carried
    forward.
    """
    fig, ax = _fig(5.0, 2.9)
    docs = [d for d in _json("*/bench-sweep-*.json") if len(d.get("rows") or []) > 1]
    if len(docs) < 4:
        _nothing(ax, "fewer than four sweeps carry two scored configurations,\n"
                     "so there is no winner to compare against a runner-up")
        fig.tight_layout(); return fig

    pairs = []
    for d in docs:
        rows = sorted((r for r in d["rows"]
                       if isinstance(r.get("cv"), dict)
                       and r["cv"].get("rmse") is not None),
                      key=lambda r: r["cv"]["rmse"])
        if len(rows) < 2:
            continue
        gap = rows[1]["cv"]["rmse"] - rows[0]["cv"]["rmse"]
        # A record written before the repeat count was stored carries no
        # standard deviation. Treated as nought it would silently declare every
        # such sweep decisive, so it is dropped instead.
        s0, s1 = rows[0].get("cv_rmse_sd"), rows[1].get("cv_rmse_sd")
        if s0 is None or s1 is None:
            continue
        pairs.append((gap, 2.0 * float(np.hypot(s0, s1)),
                      rows[0].get("name") or rows[0]["model"]))
    if len(pairs) < 4:
        _nothing(ax, f"{len(docs)} sweeps on disk, none of them recording how far\n"
                     "a configuration's error moves between repeats")
        fig.tight_layout(); return fig

    pairs.sort(key=lambda t: t[0])
    x = np.arange(len(pairs))
    gap = np.array([p[0] for p in pairs])
    noise = np.array([p[1] for p in pairs])
    decisive = gap > noise

    ax.fill_between(x, 0, noise, color=RULE, alpha=0.55,
                    label="twice the repeat noise of the two")
    ax.plot(x, gap, color=NAVY, linewidth=1.6,
            label="gap from the winner to the runner-up")
    ax.scatter(x[~decisive], gap[~decisive], s=10, color=RED, zorder=4,
               label="the winner is not separable")
    ax.set_yscale("symlog", linthresh=1e-4)
    ax.set_xlabel("sweeps, ordered by the gap")
    ax.set_ylabel("held-out RMSE")
    ax.set_title(f"The winner is separable from the runner-up in "
                 f"{int(decisive.sum())} of {len(pairs)} sweeps", fontsize=7.8)
    ax.legend(fontsize=6.2, frameon=False, loc="upper left")
    fig.tight_layout()
    return fig


def hyper_response():
    """How each hyperparameter moves the held-out error, over every fit on disk.

    One panel per hyperparameter the sweeps varied, every fit drawn at the value
    it used, with the median across that value marked. The read is the vertical
    scatter against the horizontal shift: where a value's whole column sits on
    top of the next one, that hyperparameter is not what is moving the answer.

    The honest caveat sits on the figure rather than in this docstring, because
    a reader will otherwise take it for a controlled comparison. The six
    configurations are fixed bundles, so a value of one hyperparameter arrives
    with particular values of the others attached, and the columns compare
    bundles rather than settings.
    """
    fits = _sweep_fits()
    if len(fits) < 8:
        fig, ax = _fig()
        _nothing(ax, "fewer than eight configuration fits on disk")
        fig.tight_layout(); return fig

    # Only the keys that actually took more than one value. A key present in
    # every fit at one setting is a constant, and a panel of one column says
    # nothing while taking the width of one that would.
    seen: dict[str, set] = {}
    for _d, r in fits:
        for k, v in (r.get("params") or {}).items():
            if isinstance(v, (int, float, str, bool)):
                seen.setdefault(k, set()).add(v)
    keys = [k for k in sorted(seen, key=lambda k: -len(seen[k])) if len(seen[k]) > 1][:4]
    if not keys:
        fig, ax = _fig()
        _nothing(ax, f"{len(fits)} fits on disk, all at the same hyperparameters.\n"
                     "Sweep a grid from the panel below.")
        fig.tight_layout(); return fig

    fig, axes = plt.subplots(1, len(keys), figsize=(1.75 * len(keys) + 0.9, 2.9),
                             dpi=110, sharey=True)
    axes = np.atleast_1d(axes)
    rng = np.random.RandomState(0)
    for ax, key in zip(axes, keys):
        ax.set_facecolor("white")
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(RULE)
        ax.tick_params(colors=SOFT, labelsize=6.5, length=3)
        ax.grid(axis="y", color=RULE, alpha=0.35, linewidth=0.6)
        ax.set_axisbelow(True)
        vals = sorted(seen[key], key=str)
        for i, v in enumerate(vals):
            ys = np.array([r["cv"]["rmse"] for _d, r in fits
                           if (r.get("params") or {}).get(key) == v])
            if not ys.size:
                continue
            ax.scatter(np.full(ys.size, i) + rng.uniform(-0.16, 0.16, ys.size),
                       ys, s=6, color=BLUE, alpha=0.35, zorder=2)
            med = float(np.median(ys))
            ax.plot([i - 0.30, i + 0.30], [med, med], color=NAVY, linewidth=2.0,
                    zorder=4)
            ax.text(i, med, f" {med:.4f}", fontsize=5.8, color=NAVY,
                    va="bottom", ha="center")
        ax.set_xticks(range(len(vals)))
        # A max_depth of nought is scikit-learn's unlimited written as a number,
        # and printed as "0" it reads as the shallowest tree rather than the
        # deepest one.
        ax.set_xticklabels(["no limit" if (key == "max_depth" and v == 0) else str(v)
                            for v in vals], fontsize=6.3)
        ax.set_title(key, fontsize=7.5, color=INK, fontweight="bold")
    axes[0].set_ylabel("RMSE cross-validated", color=SOFT, size=7.5)
    fig.suptitle(f"{len(fits)} fits. Each value is a bundle of configurations, "
                 f"not a setting varied alone",
                 fontsize=7.8, color=INK, fontweight="bold", y=1.01)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Column D. Results
# ---------------------------------------------------------------------------

def scoreboard():
    """Every fit on disk against the one line that matters, Theil's U2."""
    fig, ax = _fig(4.2, 2.8)
    u2 = [r["blind"]["theil_u2"] for d in _json("*/bench-sweep-*.json")
          for r in d["rows"] if (r.get("blind") or {}).get("theil_u2") is not None]
    u2 += [r["blind"]["theil_u2"] for d in _json("*/bench-2*.json")
           for r in (d.get("scores") or [])
           if (r.get("blind") or {}).get("theil_u2") is not None]
    if not u2:
        _nothing(ax, "no scored fit on disk yet")
        fig.tight_layout(); return fig
    u2 = np.array(u2)
    ax.hist(u2, bins=40, color=BLUE, alpha=0.8)
    ax.axvline(1.0, color=RED, linewidth=1.4)
    ax.text(1.0, ax.get_ylim()[1] * 0.95, " a constant forecast", fontsize=6.5,
            color=RED, va="top")
    beat = int((u2 < 1.0).sum())
    ax.set_xlabel("Theil's U2 on the blind period, lower is better")
    ax.set_ylabel("fits")
    ax.set_title(f"{beat} of {len(u2)} fits beat always predicting the base rate")
    fig.tight_layout()
    return fig


def run_calendar():
    """Every record the project wrote, by the day it belongs to.

    Widened on 9 September 2026. It had counted only bench-*.json and
    model-metrics-*.json: eighty files, seventy-six of them written in one
    evening, so the calendar drew two squares against twenty days of recorded
    work. It now counts every written record and dates each by its dated folder
    rather than its modification time, because the folder is the day the writing
    script named and it survives a copy, where twenty-six of the 259 records
    carry a modification time a day or two off their own folder.
    """
    fig, ax = _fig(5.4, 2.4)
    recs = _evidence_records()
    if not recs:
        _nothing(ax, "no record written under a dated folder yet")
        fig.tight_layout(); return fig

    import datetime as _dt
    days = Counter(r["day"] for r in recs)
    lo, hi = min(days), max(days)
    first = lo - _dt.timedelta(days=lo.weekday())          # the Monday of week one
    weeks = (hi - first).days // 7 + 1
    # Masked rather than zero-filled: a day nobody worked and a day with no
    # record must not be painted the same colour as the lightest working day,
    # which is what nan_to_num did.
    grid = np.ma.masked_all((7, weeks))
    for d, n in days.items():
        grid[d.weekday(), (d - first).days // 7] = n
    cmap = plt.get_cmap("Blues").copy()
    cmap.set_bad("#f2f5f8")
    # Logarithmic, because one evening wrote 178 records and every other day
    # wrote between one and thirteen. On a linear scale that single square took
    # the whole colour range and the other twenty days were indistinguishable
    # from a day nobody worked.
    from matplotlib.colors import LogNorm
    im = ax.imshow(grid, aspect="auto", cmap=cmap,
                   norm=LogNorm(vmin=1, vmax=max(days.values())))
    ax.set_yticks(range(7))
    ax.set_yticklabels(["Mon", "", "Wed", "", "Fri", "", "Sun"], fontsize=6.5)
    # One tick per month, on the week its first record falls in, so a reader can
    # see the June work and the September work as separate blocks.
    seen, ticks, labs = set(), [], []
    for d in sorted(days):
        if d.strftime("%Y-%m") not in seen:
            seen.add(d.strftime("%Y-%m"))
            ticks.append((d - first).days // 7)
            labs.append(d.strftime("%b"))
    ax.set_xticks(ticks); ax.set_xticklabels(labs, fontsize=6.5)
    ax.grid(False)
    bar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    bar.ax.tick_params(labelsize=6, colors=SOFT)
    bar.set_label("records that day", size=6.5, color=SOFT)
    ax.set_title(f"{sum(days.values())} records over {len(days)} working days, "
                 f"{lo:%d %b} to {hi:%d %b}")
    fig.tight_layout()
    return fig


def run_ranking():
    """The best result from each sweep, newest first."""
    fig, ax = _fig(4.2, 2.8)
    docs = _json("*/bench-sweep-*.json", 18)
    if not docs:
        _nothing(ax, "no sweep on disk yet")
        fig.tight_layout(); return fig
    vals, labs = [], []
    for d in docs:
        best = min(d["rows"], key=lambda r: r["cv"]["rmse"])
        u2 = (best.get("blind") or {}).get("theil_u2")
        if u2 is None:
            continue
        vals.append(u2)
        labs.append(str(d.get("stamped", ""))[5:16].replace("T", " "))
    if not vals:
        _nothing(ax, "no blind score in the sweeps on disk")
        fig.tight_layout(); return fig
    order = np.argsort(vals)
    v = [vals[i] for i in order]; lb = [labs[i] for i in order]
    ax.barh(range(len(v)), v, color=[GREEN if x < 1 else RULE for x in v],
            height=0.7)
    ax.axvline(1.0, color=RED, linewidth=1.2)
    ax.set_yticks(range(len(v))); ax.set_yticklabels(lb, fontsize=6)
    ax.set_xlim(min(v) * 0.998, max(max(v) * 1.001, 1.002))
    ax.set_xlabel("blind Theil U2, below one beats a constant")
    ax.set_title("Best of each sweep, ranked")
    fig.tight_layout()
    return fig


def timeline():
    """Every run as background, with the milestones marked on top."""
    import milestones as ms

    import datetime as _dt

    # By week, not by day. At daily resolution the bars were a pixel wide and
    # the labels had to shrink to 5pt to fit, which made a strip nobody could
    # read. Nothing here needs the day: it shows when the approach changed and
    # roughly how busy the work was.
    # 0.40 inches tall, down from 0.62 on 9 September 2026: the timeline now
    # sits inside the masthead band rather than above it, and the whole band is
    # capped at about 37 pixels. The tick and legend sizes come down with it or
    # they collide.
    fig, ax = _fig(19.0, 0.40)
    runs = Counter()
    for p in _records("*/bench-*.json") + _records("*/model-metrics-*.json"):
        d = datetime.fromtimestamp(p.stat().st_mtime).date()
        runs[d - _dt.timedelta(days=d.weekday())] += 1        # the Monday of its week
    marks = ms.load() or ms.seed()
    if not marks:
        _nothing(ax, "no milestones recorded")
        fig.tight_layout(); return fig

    dates = [datetime.strptime(m["date"], "%Y-%m-%d").date() for m in marks]
    weeks = [d - _dt.timedelta(days=d.weekday()) for d in dates]
    lo, hi = min(list(runs) + weeks), max(list(runs) + weeks)
    span = max((hi - lo).days, 7)

    if runs:
        xs = [(w - lo).days for w in runs]
        ax.bar(xs, [runs[w] for w in runs], color=RULE, width=5.0, zorder=1)
    colour = {"design": PURPLE, "data": BLUE, "workflow": GREEN}
    top = max(runs.values()) if runs else 1
    for m, w in zip(marks, weeks):
        x = (w - lo).days
        ax.plot([x, x], [0, top * 1.12], color=colour[m["kind"]], linewidth=1.4,
                zorder=2)
        ax.scatter([x], [top * 1.12], s=22, color=colour[m["kind"]], zorder=3)
    ax.set_ylim(0, top * 1.45)
    ax.set_yticks([])
    # Five labels across the whole span, at a size that reads on a short strip.
    ticks = np.linspace(0, span, 5)
    ax.set_xticks(ticks)
    ax.set_xticklabels([(lo + _dt.timedelta(days=int(t))).strftime("%d %b")
                        for t in ticks], fontsize=6.5)
    ax.tick_params(axis="x", labelsize=6.5, length=1.5, pad=0.5)
    for kind, col in colour.items():
        ax.plot([], [], color=col, linewidth=2.4, label=ms.KINDS[kind])
    ax.legend(fontsize=6.5, frameon=False, ncol=4, loc="upper left",
              handlelength=1.0, columnspacing=0.9, borderpad=0, handletextpad=0.35,
              bbox_to_anchor=(0, 1.62))
    ax.text(1.0, 1.62, f"{sum(runs.values())} runs, {len(marks)} milestones",
            transform=ax.transAxes, fontsize=6.5, color=SOFT, ha="right", va="bottom")
    # Margins set directly: tight_layout cannot place a legend above the axes on
    # a strip this short and warns rather than laying it out. Retuned with the
    # figure height for the 9 September banding.
    fig.subplots_adjust(left=0.008, right=0.996, top=0.60, bottom=0.34)
    return fig


def indicator_overlay():
    """Price with the geometry the three engines put on it, on raw bars.

    Every setting on the Signals section drives this: the MACD spans and its
    noise band, the moving averages, and the Fibonacci lookback. The bars are
    the archive's own, not the built panel's, because the panel carries only
    ratios and flags and has no price in it at all.
    """
    import bench_config as bc

    cfg = bc.load()
    fig, (ax, axm) = plt.subplots(
        2, 1, figsize=(5.4, 3.6), dpi=110, sharex=True,
        height_ratios=[2.1, 1.0])
    _dress(ax); _dress(axm)

    bars = max(120, int(cfg["viz"].get("viz_bars") or 400))
    who, d = _klines(cfg, bars)
    if who is None:
        _nothing(ax, d); _nothing(axm, "")
        fig.tight_layout(); return fig
    sym, frame = who
    show = d.tail(bars).reset_index(drop=True)
    x = show["datetime"]

    # --- the trend geometry, from the Supertrend maths the panels were built on
    import build_dataset_1h as bd
    for period, mult in bd.ST_BANDS:
        _up, line = bd._supertrend_band(d, period, mult)
        ax.plot(x, line[-len(show):], color=ORANGE, linewidth=0.7, alpha=0.8)
    st_label = "Supertrend " + ", ".join(f"{p}/{m:g}" for p, m in bd.ST_BANDS)

    # --- the Fibonacci pocket, measured over the engine's own lookback
    lab_fib = _engine("fib")
    swing = lab_fib.detect_swing(show["high"], show["low"], _conf_cfg(cfg).fib)
    if swing is not None and swing.rng > 0:
        gp_lo, gp_hi = lab_fib.golden_pocket(swing)
        ax.axhspan(gp_lo, gp_hi, color=PURPLE, alpha=0.12, zorder=0)
        ax.text(0.006, gp_lo, " Fibonacci pocket, 0.5 to 0.618", fontsize=6,
                color=PURPLE, va="top", transform=ax.get_yaxis_transform())

    ax.plot(x, show["close"], color=INK, linewidth=1.1, zorder=4)

    # --- the guarded MACD signals, the crossings that cleared the noise band
    sig = _engine("macd").compute_signals(d["close"], _macd_cfg(cfg)).tail(len(show))
    sig.index = show.index
    buy, sell = sig["guarded_buy"], sig["guarded_sell"]
    ax.scatter(x[buy], show["close"][buy], s=24, marker="^", color=GREEN, zorder=5)
    ax.scatter(x[sell], show["close"][sell], s=24, marker="v", color=RED, zorder=5)
    ax.set_ylabel("price, USDT" if frame != "eq1d" else "price, US dollars")
    # Padded so the legend below it has its own line: at the default pad the two
    # were drawn on top of each other.
    ax.set_title(f"{sym}, {_interval(frame)} bars, the last {len(show)}", pad=16)
    # Proxy handles rather than per-line labels: three Supertrend entries and a
    # count on each marker filled the top third of the price panel.
    ax.plot([], [], color=INK, linewidth=1.1, label="close")
    ax.plot([], [], color=ORANGE, linewidth=0.9, label=st_label)
    ax.plot([], [], "^", color=GREEN, markersize=4,
            label=f"guarded buy ({int(buy.sum())})")
    ax.plot([], [], "v", color=RED, markersize=4,
            label=f"guarded sell ({int(sell.sum())})")
    ax.legend(fontsize=6, frameon=False, ncol=4, loc="lower left",
              bbox_to_anchor=(0, 1.02), handlelength=1.2, columnspacing=1.0,
              handletextpad=0.35, borderpad=0)

    # --- the histogram and the band a crossing has to clear to count
    hist, eps = sig["hist"], sig["eps"]
    # Bar width in days, because a datetime axis is numbered in days: passing the
    # Timedelta straight through drew every bar as a hairline.
    span = ((x.iloc[-1] - x.iloc[0]).total_seconds() / 86400.0 / max(len(x) - 1, 1)
            if len(x) > 1 else 1.0)
    axm.bar(x, hist, width=span * 0.9,
            color=[GREEN if v >= 0 else RED for v in hist], alpha=0.55, linewidth=0)
    axm.fill_between(x, -eps, eps, color=SOFT, alpha=0.30, linewidth=0)
    axm.plot(x, sig["macd"], color=NAVY, linewidth=0.9)
    axm.plot(x, sig["signal"], color=ORANGE, linewidth=0.9)
    axm.axhline(0, color=RULE, linewidth=0.8)
    s = cfg["signals"]
    axm.set_ylabel(f"MACD {s['macd_fast']}/{s['macd_slow']}/{s['macd_signal']}")
    axm.text(0.5, -0.42, f"grey band, {s['macd_noise_k']:g} sigma of the histogram: "
                         f"a crossing inside it does not count as a signal",
             transform=axm.transAxes, ha="center", va="top", fontsize=6, color=SOFT)
    axm.tick_params(axis="x", labelsize=6)
    fig.tight_layout()
    return fig


def confluence_agreement():
    """The confluence score's own distribution, from the engine, on raw bars.

    Four methods each vote minus one, nought or plus one: the prevailing MACD
    stance, the moving-average cross, where price sits on the Fibonacci swing,
    and the engulfing candle. Their sum is the score, so it runs from minus four
    to plus four, and the threshold on the Signals section is how much agreement
    has to be there before anything fires. The chart it replaced read
    `f_st_agree` off the built panel, which is a normalised Supertrend vote in
    minus one to plus one and never reaches a threshold of two.
    """
    import bench_config as bc

    fig, ax = _fig(4.6, 2.8)
    cfg = bc.load()
    who, d = _klines(cfg, 1500)
    if who is None:
        _nothing(ax, d); fig.tight_layout(); return fig
    sym, frame = who
    ccfg = _conf_cfg(cfg)
    conf = _engine("confluence").compute_confluence(
        d.tail(1500).reset_index(drop=True), ccfg)
    score = conf["score"]
    thr = float(ccfg.threshold)

    levels = list(range(-4, 5))
    counts = [int((score == v).sum()) for v in levels]
    cols = [GREEN if v >= thr else RED if v <= -thr else RULE for v in levels]
    ax.bar(levels, counts, color=cols, width=0.72)
    for v, c in zip(levels, counts):
        if c:
            ax.text(v, c, f"{c}", ha="center", va="bottom", fontsize=6, color=INK)
    for edge in (-thr, thr):
        ax.axvline(edge, color=NAVY, linestyle="--", linewidth=1)
    fires = int(conf["buy"].sum() + conf["sell"].sum())
    agreed = int((score.abs() >= thr).sum())
    ax.set_xticks(levels)
    ax.set_xlabel("methods agreeing: MACD, moving average, Fibonacci, candle")
    ax.set_ylabel("bars")
    ax.set_title(f"{sym}, {_interval(frame)}: {agreed} of {len(score)} bars reach "
                 f"{thr:g}, {fires} fire")
    fig.tight_layout()
    return fig


def assessment_compact():
    """The last few runs on one axis: held-out error and whether it passed."""
    fig, ax = _fig()
    docs = _json("*/bench-2*.json", 12)
    # Records written before the five-measure change carry a flat rmse rather
    # than the nested full/cv pair, so a bare r["cv"]["rmse"] raised KeyError on
    # them and the panel showed the exception instead of the chart.
    rows = [(str(d.get("stamped", ""))[5:16].replace("T", " "), r)
            for d in docs for r in (d.get("scores") or [])
            if isinstance(r.get("cv"), dict) and r["cv"].get("rmse") is not None]
    if not rows:
        _nothing(ax, "no bench run on disk yet")
        fig.tight_layout(); return fig
    rows = rows[:12][::-1]
    labs = [f"{w}  {r['model'][:12]}" for w, r in rows]
    vals = [r["cv"]["rmse"] for _w, r in rows]
    cols = [RED if r["rejected"] else GREEN for _w, r in rows]
    ax.barh(range(len(vals)), vals, color=cols, height=0.7)
    ax.set_yticks(range(len(vals))); ax.set_yticklabels(labs, fontsize=6)
    ax.set_xlim(min(vals) * 0.97, max(vals) * 1.01)
    ax.set_xlabel("RMSE cross-validated")
    ax.set_title("Recent runs; red failed the overfit bar")
    fig.tight_layout()
    return fig


def fold_coverage():
    """How many rows each walk-forward fold scores, at the current setting."""
    import bench_config as bc

    cfg = bc.load()
    folds = int(cfg["split"]["folds"])
    scheme = cfg["split"]["scheme"]
    fig, ax = _fig()
    edges = np.linspace(0, 100, folds + 2)
    train = [edges[i] if scheme == "expanding" else edges[i] - edges[i - 1]
             for i in range(1, folds + 1)]
    test = [edges[i + 1] - edges[i] for i in range(1, folds + 1)]
    idx = np.arange(1, folds + 1)
    ax.bar(idx, train, color=BLUE, width=0.55, label="trained on")
    ax.bar(idx, test, bottom=train, color=ORANGE, width=0.55, label="scored on")
    ax.set_xticks(idx); ax.set_xlabel("fold")
    ax.set_ylabel("share of the training window, %")
    ax.set_title(f"{folds} {scheme} folds")
    ax.legend(fontsize=6.5, frameon=False)
    fig.tight_layout()
    return fig


def _cross_sectional_rows(path: Path) -> tuple[list, str]:
    """One cross-sectional record's table, as (signal, top, market) per row.

    The record is a fixed-width table printed by cross_sectional_4h.py, not a
    Markdown one. The parser this replaced looked for pipe characters, found
    none in a file that has a nine-column table in it, and reported "carries no
    numeric table"; before that it would have read the first decimal on any
    piped line, whatever column it came from, and labelled it with whatever text
    sat between the first two pipes.
    """
    header, rows = None, []
    for line in path.read_text(errors="replace").splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "signal" and any(p.endswith("_top") for p in parts):
            header = parts
            continue
        if header is None or len(parts) != len(header):
            continue
        try:
            rows.append(dict(zip(header, [parts[0]] + [float(v) for v in parts[1:]])))
        except ValueError:
            header = None                 # the table ended; a later one may start
    if not rows:
        return [], "carries no fixed-width table of signals"
    # Prefer the deciding cell the record itself names, the test fold with the
    # regime gate open. Any other _top/_mkt pair is a fallback for a record
    # written before the gate existed.
    pairs = [(t, t[:-4] + "_mkt") for t in header if t.endswith("_top")]
    pairs = [(t, m) for t, m in pairs if m in header]
    best = next((p for p in pairs if p[0].startswith("te_up")), None) or \
        next((p for p in pairs if p[0].startswith("te_")), None) or \
        (pairs[0] if pairs else None)
    if best is None:
        return [], "has no top-third column paired with a market column"
    top, mkt = best
    return [(r["signal"], r[top], r[mkt]) for r in rows], top


def cross_sectional_spread():
    """Each ranking signal's top third against the market it was ranked within.

    The finding is the gap between the two bars, not either bar alone: relative
    strength ranks assets in an order that holds out of sample, and the top
    third beats the market it was drawn from, while the market's own after-fee
    return is negative enough that the top third stays negative with it. A chart
    of the top third alone would read as a loss and a chart of the spread alone
    would read as an edge, and both would be half the record.
    """
    fig, ax = _fig(4.6, 3.0)
    hits = _records("*/cross-sectional-*.md", 1)
    if not hits:
        _nothing(ax, "no cross-sectional record on disk.\n"
                     "The ranking signal was never disproved; the way of\n"
                     "trading it was killed at 27% of folds against a 60% bar.")
        fig.tight_layout(); return fig
    rows, which = _cross_sectional_rows(hits[0])
    if not rows:
        _nothing(ax, f"{hits[0].name}\n{which}")
        fig.tight_layout(); return fig

    rows.sort(key=lambda r: r[1] - r[2])
    y = np.arange(len(rows))
    ax.barh(y + 0.19, [r[1] for r in rows], height=0.36, color=BLUE,
            label="top third")
    ax.barh(y - 0.19, [r[2] for r in rows], height=0.36, color=RULE,
            label="the market it was ranked within")
    ax.axvline(0, color=SOFT, linewidth=0.9)
    # A gutter is opened on the right for the gap, which is the number the chart
    # is about. Written over the bars it was unreadable, green on dark blue, and
    # written at the far end it landed on the axis tick labels.
    lo, hi = ax.get_xlim()
    gutter = (hi - lo) * 0.17
    ax.set_xlim(lo, hi + gutter)
    for i, r in enumerate(rows):
        gap = r[1] - r[2]
        ax.text(hi + gutter, i, f"{gap:+.3f} ", va="center", ha="right",
                fontsize=6.5, color=GREEN if gap > 0 else RED, fontweight="bold")
    ax.set_yticks(y); ax.set_yticklabels([r[0] for r in rows], fontsize=6.5)
    ax.set_xlabel(f"after-fee return per trade, %  ({which})")
    ax.xaxis.label.set(size=6.5)
    won = sum(1 for r in rows if r[1] > r[2])
    ax.set_title(f"{won} of {len(rows)} beat their own market; "
                 f"{sum(1 for r in rows if r[1] > 0)} clear zero", pad=14)
    ax.legend(fontsize=6.5, frameon=False, ncol=2, loc="lower left",
              bbox_to_anchor=(0, 1.0), handlelength=1.2, borderpad=0)
    fig.tight_layout()
    return fig


def coefficient_intervals():
    """The screened coefficients with their intervals, from the saved screen."""
    fig, ax = _fig()
    hits = _records("varselect/univariate-*.json", 1)
    if not hits:
        _nothing(ax, "no univariate screen on disk yet.\n"
                     "Run variable selection from this panel; it fits each\n"
                     "predictor alone and reports its interval.")
        fig.tight_layout(); return fig
    rows = json.loads(hits[0].read_text())["rows"][:12][::-1]
    names = [r["feature"] for r in rows]
    est = [r["coef"] for r in rows]
    lo = [r["lo"] for r in rows]; hi = [r["hi"] for r in rows]
    y = np.arange(len(names))
    ax.hlines(y, lo, hi, color=NAVY, linewidth=1.8)
    ax.plot(est, y, "o", color=NAVY, markersize=4)
    ax.axvline(0, color=SOFT, linestyle="--", linewidth=0.9)
    ax.set_yticks(y); ax.set_yticklabels(names, fontsize=6)
    ax.set_xlabel("log-odds, with 95 per cent interval")
    ax.set_title("Each predictor alone")
    fig.tight_layout()
    return fig


def kde_separation():
    """The two outcome classes as smooth densities, with the bandwidth's effect.

    Where a histogram of ten bins says the model is miscalibrated in the top
    bin, this says how far apart the classes sit across the whole range, and it
    does so without bin edges. A model with nothing to say puts both curves on
    top of each other around the base rate.

    The overlap is quoted as a range, not a value, and the inset is why.
    Section 6 of 05-research/tasks/proposal-kde-metrics.md measured this exact
    quantity moving from 0.8945 to 0.9664 as the bandwidth went from half
    Silverman's rule to twice it, because a model collapsed toward the base rate
    leaves almost no predicted range for a kernel to resolve. The proposal's
    standing rule is that a kernel number is published with its sensitivity or
    it is not published, so the single figure that stood in this title is now
    the span across that fourfold range with the curve beneath it.
    """
    import kde_metrics as km

    fig, ax = _fig(4.6, 3.0)
    cache = _predictions()
    if cache is None:
        _nothing(ax, "no fitted model to draw from.\nRun the performance panel first.")
        fig.tight_layout(); return fig
    y, p = cache
    grid = np.linspace(0.0, 1.0, 400)
    h = max(km.silverman(p), 1e-3)
    f1 = km.kde(p[y == 1], grid, h); f0 = km.kde(p[y == 0], grid, h)
    a1 = np.trapezoid(f1, grid) or 1; a0 = np.trapezoid(f0, grid) or 1
    f1, f0 = f1 / a1, f0 / a0
    ax.fill_between(grid, 0, f1, color=GREEN, alpha=0.30, label="hit the target")
    ax.fill_between(grid, 0, f0, color=RED, alpha=0.22, label="did not")
    ax.plot(grid, f1, color=GREEN, linewidth=1.3)
    ax.plot(grid, f0, color=RED, linewidth=1.3)
    ax.axvline(float(y.mean()), color=NAVY, linestyle="--", linewidth=1)
    ax.text(float(y.mean()), ax.get_ylim()[1] * 0.96, " base rate", fontsize=6.5,
            color=NAVY, va="top")
    lo, hi = float(np.percentile(p, 0.5)), float(np.percentile(p, 99.5))
    ax.set_xlim(max(0, lo - 0.05), min(1, hi + 0.05))
    ax.set_xlabel("predicted probability")
    ax.set_ylabel("density")
    # Both classes pile up in the middle of the predicted range, so the corners
    # are the only clear ground and the legend and the inset take one each.
    ax.legend(fontsize=6.5, frameon=False, loc="upper right")

    sens = km.bandwidth_sensitivity(y, p)
    ov = [s["overlap"] for s in sens if s["overlap"] is not None]
    if not ov:
        ax.set_title(f"{int((y == 1).sum())} and {int((y == 0).sum())} rows: too "
                     f"few of one class to estimate a density")
        fig.tight_layout(); return fig
    ax.set_title(f"The classes overlap by {min(ov):.3f} to {max(ov):.3f}, "
                 f"depending on the bandwidth")

    # The sensitivity drawn rather than tabulated, in the corner of the chart it
    # qualifies, so the reader cannot take the headline without it.
    ax.set_ylim(0, ax.get_ylim()[1] * 1.10)
    inset = ax.inset_axes((0.10, 0.50, 0.29, 0.35))
    # Opaque, because the density runs under it and a translucent inset over a
    # pair of curves is unreadable in both directions.
    inset.set_facecolor("white")
    inset.patch.set_alpha(1.0)
    inset.plot([s["factor"] for s in sens], ov, "-o", color=PURPLE,
               linewidth=1.2, markersize=3)
    inset.axvline(1.0, color=SOFT, linestyle=":", linewidth=0.9)
    inset.set_ylim(min(ov) - 0.02, min(1.0, max(ov) + 0.02))
    inset.tick_params(colors=SOFT, labelsize=5.5, length=2)
    inset.set_xlabel("half Silverman's rule to twice it",
                     fontsize=5.6, color=SOFT, labelpad=1)
    inset.set_title("overlap against bandwidth", fontsize=5.8, color=SOFT, pad=2)
    for side in inset.spines.values():
        side.set_color(RULE)
        side.set_linewidth(0.6)
    inset.grid(False)
    fig.tight_layout()
    return fig


def kde_spread():
    """How much of the nought-to-one range the model actually uses.

    Every accuracy measure here can be satisfied by a model that never departs
    from the base rate, and several nearly are. This says so directly.

    The two numbers in the title are counted off the predictions themselves, not
    read off the smoothed curve. kde_metrics.spread_of_predictions integrates
    the kernel density to get the mass near the base rate, which makes its
    headline move with the bandwidth; the proposal recommends this measure
    precisely on the grounds that its headline is a quantile and needs no
    bandwidth, so the share is counted here as the share of rows within 0.05 of
    the base rate and the density is drawing only.
    """
    import kde_metrics as km

    fig, ax = _fig(4.4, 2.6)
    cache = _predictions()
    if cache is None:
        _nothing(ax, "no fitted model to draw from")
        fig.tight_layout(); return fig
    y, p = cache
    base = float(y.mean())
    grid = np.linspace(0.0, 1.0, 400)
    dens = km.kde(p, grid, max(km.silverman(p), 1e-3))
    dens = dens / (np.trapezoid(dens, grid) or 1)
    ax.fill_between(grid, 0, dens, color=BLUE, alpha=0.35)
    ax.plot(grid, dens, color=BLUE, linewidth=1.4)
    near = (grid > base - 0.05) & (grid < base + 0.05)
    ax.fill_between(grid[near], 0, dens[near], color=ORANGE, alpha=0.55)
    ax.axvline(base, color=NAVY, linestyle="--", linewidth=1)

    share = float(np.mean(np.abs(p - base) < 0.05))
    q05, q95 = float(np.percentile(p, 5)), float(np.percentile(p, 95))
    lo, hi = float(np.percentile(p, 0.5)), float(np.percentile(p, 99.5))
    ax.set_xlim(max(0, lo - 0.06), min(1, hi + 0.06))
    ax.set_xlabel("predicted probability")
    ax.set_title(f"{share * 100:.0f}% of the rows land within 0.05 of the base "
                 f"rate {base:.3f}")
    # Raised to leave the note a clear strip. A note laid over the density is a
    # note the reader skips, and this one carries the only quantity on the chart
    # that no bandwidth choice can move.
    ax.set_ylim(0, ax.get_ylim()[1] * 1.22)
    ax.text(0.01, 0.985, f"the middle ninety per cent span {q95 - q05:.4f}, "
                         f"from {q05:.3f} to {q95:.3f}, counted off the rows",
            transform=ax.transAxes, fontsize=6.4, color=SOFT, va="top")
    fig.tight_layout()
    return fig


def kde_null_band():
    """The calibration curve against what shuffled labels produce.

    The binned reliability table never had this. A gap of 0.7 in a bin of 235
    rows is a finding or a sample size, and nothing said which.
    """
    import kde_metrics as km

    fig, ax = _fig(4.2, 2.8)
    cache = _predictions()
    if cache is None:
        _nothing(ax, "no fitted model to draw from")
        fig.tight_layout(); return fig
    y, p = cache
    nb = km.null_band(y, p, draws=120)
    g, obs, lo, hi = nb["grid"], nb["observed"], nb["lo"], nb["hi"]
    ax.fill_between(g, lo, hi, color=RULE, alpha=0.55,
                    label="what no signal produces")
    ax.plot(g, obs, color=NAVY, linewidth=1.6, label="observed frequency")
    ax.plot(g, g, color=SOFT, linestyle=":", linewidth=1, label="perfectly calibrated")
    ax.set_xlabel("stated probability"); ax.set_ylabel("observed frequency")
    ax.set_title(f"Outside the band over {nb['share_outside'] * 100:.0f}% of the range")
    # This one number survives the bandwidth where the overlap on the chart
    # beside it does not, because the curve and the band it is judged against
    # are estimated at the same bandwidth: a bandwidth that is wrong is wrong on
    # both sides and the comparison holds. Stating it is still the rule, so a
    # reader can see which bandwidth produced the band and on how many draws.
    ax.text(0.01, 0.99, f"{int(y.size):,} blind rows, {nb['draws']} shuffles, "
                        f"bandwidth {nb['bandwidth']:.4f}",
            transform=ax.transAxes, fontsize=6.2, color=SOFT, va="top")
    ax.legend(fontsize=6.5, frameon=False, loc="lower right")
    fig.tight_layout()
    return fig


_PRED_CACHE: dict = {}


def _predictions():
    """The current configuration's blind-period predictions, fitted once.

    Held for ten minutes. A page that refits on every chart is a page nobody can
    leave open, and three kernel charts on one panel would otherwise fit the
    same model three times.
    """
    import time as _time

    import bench_config as bc
    import bench_run as br
    import train_model_1h as t1

    key = json.dumps(bc.load(), sort_keys=True)
    hit = _PRED_CACHE.get(key)
    if hit and _time.time() - hit[0] < 600:
        return hit[1]
    try:
        cfg = bc.load()
        df, avail = br.load_frame(cfg, log=lambda *a, **k: None)
        feats = br.choose_features(cfg, avail, log=lambda *a, **k: None)
        train, test, _cut = t1.split(df, oos_days=int(cfg["split"]["holdout_days"]))
        if len(train) < 400 or len(test) < 100:
            return None
        est = br.make_estimator(
            (cfg["model"]["estimators"] or ["RF"])[0],
            cfg["model"]["class_weight"],
            (cfg["model"].get("params") or {}).get(
                (cfg["model"]["estimators"] or ["RF"])[0]))
        if est is None:
            return None
        est.fit(train[feats], train["label"])
        got = (test["label"].to_numpy(float),
               est.predict_proba(test[feats])[:, 1])
    except Exception:                                   # noqa: BLE001
        return None
    _PRED_CACHE[key] = (_time.time(), got)
    return got


_FOLD_CACHE: dict = {}


def _fold_frame():
    """The training window as a matrix, ready for one cheap fit per fold.

    Returns the training rows, the offered feature names, the feature matrix and
    the outcome as plain arrays, and the calendar span of the blind period.
    Cached for ten minutes on the configuration, so the two charts that fit per
    fold read the panel once between them rather than once each.

    The matrix is float32 and the row cap is the configuration's own. Nothing
    here opens the full two-gigabyte panel: bench_run.read_capped takes Parquet
    row groups from the end of the file until it has the requested count of
    in-sample rows, which is why a chart can fit a model on this machine at all.
    """
    import time as _time

    import bench_config as bc
    import bench_run as br
    import train_model_1h as t1

    key = json.dumps(bc.load(), sort_keys=True)
    hit = _FOLD_CACHE.get(key)
    if hit and _time.time() - hit[0] < 600:
        return hit[1]
    try:
        cfg = bc.load()
        df, avail = br.load_frame(cfg, log=lambda *a, **k: None)
        feats = br.choose_features(cfg, avail, log=lambda *a, **k: None)
        train, test, _cut = t1.split(df, oos_days=int(cfg["split"]["holdout_days"]))
        # A fold needs enough rows on both sides to say anything. Below this the
        # bootstrap interval is wider than the differences the chart is drawn to
        # show, and a chart that draws noise at full confidence is worse than
        # one that says it has nothing.
        if len(train) < 600 or len(test) < 50:
            return None
        got = (train, feats,
               train[feats].to_numpy(np.float32),
               train["label"].to_numpy(float),
               (test["datetime"].min(), test["datetime"].max()))
    except Exception:                                   # noqa: BLE001
        return None
    _FOLD_CACHE[key] = (_time.time(), got)
    return got


# The seven regimes bench_run.folds_of implements, in the order the picture
# reads best: the two that keep time in order first, then the five that do not.
_REGIMES = ("expanding", "rolling", "kfold", "repeated-kfold",
            "monte-carlo", "bootstrap", "leave-one-out")

# How many fold bands each regime shows. Leave-one-out returns two hundred folds
# and bootstrap twenty-five; drawing them all makes a grey smear, and drawing
# eight of two hundred without saying so misreports the regime, so the count
# displayed and the count generated are both printed beside every band.
_DEMO_BANDS = 8


def regime_demo(scheme: str | None = None, rows: int = 240):
    """Every resampling regime side by side, on the same rows.

    The picture the R package `caret` draws for its own resampling schemes, with
    one difference that matters here: the rows are in time order left to right,
    so a regime that puts a later row in training and an earlier one in test
    shows it as blue to the right of orange. That is the leak, drawn.

    Drawn with imshow rather than a scatter of squares. The scatter that stood
    here took 7.4 seconds and lost leave-one-out entirely: a single scored row
    is one marker of 1.6 points against a band of 240, which rendered as a blank
    blue stripe, so the one regime whose whole character is that it scores a
    single row showed nothing at all. An image cell cannot fall below one pixel,
    so the same fold is now a visible stripe and the figure draws in well under
    a second.

    The repeat and bootstrap counts come from the configuration rather than
    from literals, so the picture is of the regime the run would actually use.
    """
    from matplotlib.colors import ListedColormap

    import bench_config as bc
    import bench_run as br

    schemes = [scheme] if scheme else list(_REGIMES)
    cfg = bc.load()
    k = int(cfg["split"]["folds"])
    reps = int(cfg["split"].get("repeats") or 10)
    boot = int(cfg["split"].get("boot_samples") or 25)
    cmap = ListedColormap(["#ffffff", BLUE, ORANGE])

    fig, axes = plt.subplots(len(schemes), 1, figsize=(6.4, 0.86 * len(schemes) + 0.9),
                             dpi=110, sharex=True)
    if len(schemes) == 1:
        axes = [axes]
    for ax, sch in zip(axes, schemes):
        try:
            # Ask for only as many folds as are drawn. The configured repeats
            # and bootstrap resamples are 10 and 25, and leave-one-out is capped
            # at 200, so generating the full set built thousands of index arrays
            # of which eight were shown. That is the whole of the 29 seconds this
            # chart took, which froze the panel on open.
            folds = br.folds_of(rows, k, sch,
                                repeats=min(reps, _DEMO_BANDS),
                                boot=min(boot, _DEMO_BANDS),
                                limit=_DEMO_BANDS)
        except ValueError:
            folds = []
        shown = folds[:_DEMO_BANDS]
        if not shown:
            _nothing(ax, f"{sch} produced no usable fold at {rows} rows")
            continue
        grid = np.zeros((len(shown), rows))
        for j, (tr, te) in enumerate(shown):
            grid[j, np.clip(tr, 0, rows - 1)] = 1
            grid[j, np.clip(te, 0, rows - 1)] = 2
        ax.imshow(grid, aspect="auto", cmap=cmap, vmin=0, vmax=2,
                  interpolation="nearest", extent=(0, rows, len(shown), 0))
        for j in range(1, len(shown)):
            ax.axhline(j, color="white", linewidth=0.8)
        ax.set_ylabel(sch, rotation=0, ha="right", va="center", fontsize=7.5,
                      color=INK)
        ax.set_yticks([]); ax.grid(False)
        # sharex hides the tick labels on every axes but the last and leaves the
        # tick marks, which on seven stacked bands reads as six rows of stray
        # dashes between the regimes.
        ax.tick_params(bottom=False)
        for side in ("top", "right", "left", "bottom"):
            ax.spines[side].set_visible(False)
        # Time runs left to right, so a fold whose earliest scored row sits
        # before its latest trained row is scoring the model on a stretch of
        # market it has already seen. That is the leak, and it is what separates
        # the two regimes at the top from the five below them.
        leaks = any(len(te) and len(tr) and te.min() < tr.max() for tr, te in folds)
        say = f"{len(folds)} folds"
        if len(folds) > len(shown):
            say += f", {len(shown)} drawn"
        ax.text(rows * 1.01, len(shown) / 2, say, fontsize=6.5, va="bottom",
                ha="left", color=SOFT)
        ax.text(rows * 1.01, len(shown) / 2,
                "keeps time in order" if not leaks else "ignores time",
                fontsize=6.5, va="top", ha="left",
                color=GREEN if not leaks else RED)
    axes[-1].set_xlabel("row, in time order")
    axes[-1].tick_params(bottom=True)
    axes[-1].spines["bottom"].set_visible(True)
    axes[-1].spines["bottom"].set_color(RULE)
    axes[0].set_title(f"Which rows train and which are scored, "
                      f"{k} folds on {rows} rows",
                      fontsize=9, color=INK, fontweight="bold")
    axes[0].plot([], [], "s", color=BLUE, markersize=4, label="trained on")
    axes[0].plot([], [], "s", color=ORANGE, markersize=4, label="scored on")
    axes[0].legend(fontsize=6.5, frameon=False, ncol=2, loc="upper left",
                   bbox_to_anchor=(0, 1.75))
    fig.subplots_adjust(left=0.16, right=0.80, top=0.90, bottom=0.09, hspace=0.30)
    return fig


def regime_advance():
    """The walk-forward advance, one frame per fold, against real dates.

    The frames of the animation the operator asked for, laid out down the page
    rather than played in sequence, because the page serves a chart as a single
    PNG. Each row is one step: the training window in blue, the stretch it is
    then scored on in orange, everything not yet reached in grey, and the blind
    period held back at the right in navy. The axis carries the panel's own
    dates, so this is the split at the scale the run performs it rather than a
    schematic.
    """
    import matplotlib.dates as mdates

    import bench_config as bc
    import bench_run as br

    cfg = bc.load()
    got = _fold_frame()
    if got is None:
        fig, ax = _fig(6.0, 2.4)
        _nothing(ax, "the configured panel is not built, so there are no dates\n"
                     "to advance the folds through")
        fig.tight_layout(); return fig
    train, _feats, _X, _y, test_span = got

    when = train["datetime"].to_numpy()
    k = int(cfg["split"]["folds"])
    scheme = cfg["split"]["scheme"]
    try:
        folds = br.folds_of(len(train), k, scheme,
                            repeats=int(cfg["split"].get("repeats") or 10),
                            boot=int(cfg["split"].get("boot_samples") or 25))
    except ValueError:
        folds = []
    folds = folds[:10]
    if not folds:
        fig, ax = _fig(6.0, 2.4)
        _nothing(ax, f"the {scheme} regime produced no fold on "
                     f"{len(train):,} training rows")
        fig.tight_layout(); return fig

    lo, hi = when.min(), test_span[1]
    fig, ax = _fig(6.4, 0.42 * len(folds) + 1.5)
    for j, (tr, te) in enumerate(folds):
        y = len(folds) - j
        ax.barh([y], [mdates.date2num(hi) - mdates.date2num(lo)],
                left=[mdates.date2num(lo)], height=0.62, color=RULE, alpha=0.30)
        # Drawn as the span each side occupies rather than row by row: a
        # non-chronological regime scatters its rows across the whole window,
        # and a span that covers everything is the honest picture of that.
        for idx, col in ((tr, BLUE), (te, ORANGE)):
            if not len(idx):
                continue
            a, b = when[idx].min(), when[idx].max()
            ax.barh([y], [mdates.date2num(b) - mdates.date2num(a)],
                    left=[mdates.date2num(a)], height=0.62, color=col)
        ax.barh([y], [mdates.date2num(test_span[1]) - mdates.date2num(test_span[0])],
                left=[mdates.date2num(test_span[0])], height=0.62, color=NAVY)
        ax.text(mdates.date2num(lo), y, f" {j + 1} ", va="center", ha="left",
                fontsize=6.5, color="white", fontweight="bold")

    ax.set_yticks([]); ax.set_ylim(0.4, len(folds) + 0.8)
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=6))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    ax.set_xlim(mdates.date2num(lo), mdates.date2num(hi))
    ax.grid(False)
    ax.set_title(f"{len(folds)} {scheme} steps, "
                 f"{str(when.min())[:10]} to {str(test_span[1])[:10]}")
    for lab, col in (("trained on", BLUE), ("scored on", ORANGE),
                     ("not yet reached", RULE), ("blind, never opened", NAVY)):
        ax.plot([], [], "s", color=col, markersize=4, label=lab)
    ax.legend(fontsize=6.5, frameon=False, ncol=4, loc="upper center",
              bbox_to_anchor=(0.5, -0.12))
    fig.tight_layout()
    return fig


# The interval on each fold's held-out error, drawn by resampling that fold's
# own squared errors. A closed-form interval on a root mean square is not worth
# deriving here and the resample costs nothing once the predictions exist.
_BOOT_DRAWS = 400


def _fold_interval(err2: np.ndarray, draws: int = _BOOT_DRAWS, seed: int = 0):
    """The fifth and ninety-fifth percentile of the fold's RMSE, by resampling.

    The estimate is the root of the mean squared error on the scored rows, so
    the interval comes from resampling those rows with replacement rather than
    from a formula. A fold scored on 400 rows and a fold scored on 4,000 then
    carry visibly different widths, which is the whole point of the chart.
    """
    rng = np.random.RandomState(seed)
    n = err2.size
    if n < 20:
        return float("nan"), float("nan")
    idx = rng.randint(0, n, size=(draws, n))
    boot = np.sqrt(err2[idx].mean(axis=1))
    return float(np.percentile(boot, 5)), float(np.percentile(boot, 95))


def regime_uncertainty():
    """How wide the estimate is, fold by fold, as the folds advance through time.

    Operator instruction, 9 September 2026: the demonstrations show temporal
    change in uncertainty rather than a static picture of the folds. The chart
    that stood here plotted the spread of six configurations against the
    timestamp of each sweep, which on a page of seventy-six sweeps run in one
    afternoon put six identical dates on the axis and showed nothing temporal at
    all. It answered a different question, how far apart the configurations sit,
    and that is what error-full-vs-cv on the performance panel is for.

    This fits the folds. One logistic regression per fold on the configured
    panel, standardised and median-imputed inside the pipeline so it is fitted
    on the training side of each fold alone; the estimate is the root mean
    squared error on the rows that fold scores, and the interval is a bootstrap
    of those rows. Plotted against the calendar span each fold is scored on, so
    the estimate and its width both move left to right through the market.

    A logistic regression rather than the configured estimator on purpose. The
    forest takes seconds a fold and the question here is not which model wins,
    it is how much the answer moves between one stretch of market and the next,
    which is a property of the data.
    """
    import matplotlib.dates as mdates

    import bench_config as bc
    import bench_run as br
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    fig, (ax, bx) = plt.subplots(2, 1, figsize=(6.0, 3.9), dpi=110, sharex=True,
                                 gridspec_kw=dict(height_ratios=[2.1, 1]))
    for a in (ax, bx):
        a.set_facecolor("white")
        for side in ("top", "right"):
            a.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            a.spines[side].set_color(RULE)
        a.tick_params(colors=SOFT, labelsize=7, length=3)
        a.yaxis.label.set(color=SOFT, size=7.5)
        a.grid(axis="y", color=RULE, alpha=0.35, linewidth=0.6)
        a.set_axisbelow(True)
    ax.title.set(color=INK, size=8.5, fontweight="bold")

    got = _fold_frame()
    if got is None:
        _nothing(ax, "the configured panel is not built, or its training window\n"
                     "is too short to fold. Choose a built panel on the data card.")
        _nothing(bx, "")
        fig.tight_layout(); return fig
    train, _feats, X, y, _blind = got
    when = train["datetime"].to_numpy()

    cfg = bc.load()
    scheme = cfg["split"]["scheme"]
    k = int(cfg["split"]["folds"])
    try:
        folds = br.folds_of(len(train), k, scheme,
                            repeats=int(cfg["split"].get("repeats") or 10),
                            boot=int(cfg["split"].get("boot_samples") or 25))
    except ValueError:
        folds = []
    # Leave-one-out returns two hundred folds of a single row each. Two hundred
    # fits is affordable but an interval on one scored row is not a quantity, so
    # the cap is on the drawing and the reason is said on the axes below.
    capped = len(folds) > 14
    if capped:
        pick = np.linspace(0, len(folds) - 1, 14).astype(int)
        folds = [folds[i] for i in pick]
    if not folds:
        _nothing(ax, f"the {scheme} regime produced no fold on "
                     f"{len(train):,} training rows")
        _nothing(bx, "")
        fig.tight_layout(); return fig

    mid, est, lo, hi, span, thin = [], [], [], [], [], 0
    for tr, te in folds:
        if len(te) < 20:
            thin += 1
            continue
        m = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                          LogisticRegression(max_iter=200))
        m.fit(X[tr], y[tr])
        e2 = (y[te] - m.predict_proba(X[te])[:, 1]) ** 2
        a, b = _fold_interval(e2)
        if not np.isfinite(a):
            continue
        t0, t1_ = when[te].min(), when[te].max()
        mid.append(mdates.date2num(t0 + (t1_ - t0) / 2))
        span.append((mdates.date2num(t0), mdates.date2num(t1_)))
        est.append(float(np.sqrt(e2.mean()))); lo.append(a); hi.append(b)

    if len(est) < 2:
        _nothing(ax, f"the {scheme} regime scored fewer than twenty rows in every\n"
                     f"fold, so no interval can be put on the estimate")
        _nothing(bx, "")
        fig.tight_layout(); return fig

    mid = np.array(mid); est = np.array(est)
    lo = np.array(lo); hi = np.array(hi)
    width = hi - lo

    # The scored window drawn as a horizontal whisker, so a regime that scatters
    # its test rows across the whole training window says so by drawing a bar
    # that covers it. That is the leak, seen from the uncertainty side.
    for (a, b), e in zip(span, est):
        ax.plot([a, b], [e, e], color=RULE, linewidth=2.2, solid_capstyle="butt",
                zorder=1)
    ax.vlines(mid, lo, hi, color=BLUE, linewidth=2.6, alpha=0.55, zorder=2)
    ax.plot(mid, est, "-o", color=NAVY, linewidth=1.3, markersize=4, zorder=3,
            label="held-out RMSE, one fit per fold")
    ax.plot([], [], color=BLUE, linewidth=2.6, alpha=0.55,
            label="90 per cent bootstrap interval")
    ax.plot([], [], color=RULE, linewidth=2.2, label="the window it scored")
    ax.set_ylabel("held-out RMSE")
    ax.legend(fontsize=6.3, frameon=False, loc="best")

    # A bar width taken from the gap between neighbouring folds collapses to a
    # hairline under a regime whose folds all sit on the same date, which is
    # every regime that ignores time. Floored against the width of the training
    # window instead, so the bar is visible whatever the folds do.
    total = mdates.date2num(when.max()) - mdates.date2num(when.min()) or 30.0
    step = float(np.diff(np.sort(mid)).min()) if len(mid) > 1 else total
    bx.bar(mid, width, width=max(total / 60.0, min(step * 0.7, total / 3.0)),
           color=ORANGE, alpha=0.85)
    bx.set_ylabel("interval width")
    bx.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=6))
    bx.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    bx.tick_params(axis="x", labelsize=7)

    grew = width[-1] / width[0] if width[0] > 0 else float("nan")
    moved = est.max() - est.min()
    note = (f"{len(est)} {scheme} folds. The estimate moves {moved:.4f} across "
            f"them; the interval " +
            ("widens" if grew > 1.05 else "narrows" if grew < 0.95 else "holds") +
            f" by a factor of {grew:.2f}")
    ax.set_title(note)

    bits = []
    # A regime that ignores time gives every fold nearly the whole training
    # window to be scored on, so the folds pile onto one date and the chart
    # looks broken rather than damning. Said out loud instead.
    covered = float(np.median([(b - a) for a, b in span])) / total
    if covered > 0.8:
        bits.append(f"each fold is scored across {covered * 100:.0f} per cent of "
                    f"the training window, so this regime has no ordering to show")
    if capped:
        bits.append("evenly sampled from the regime's full set")
    if thin:
        bits.append(f"{thin} folds scored under twenty rows and are not drawn")
    if bits:
        bx.text(0.0, -0.55, "; ".join(bits) + ".", transform=bx.transAxes,
                fontsize=6.3, color=SOFT, va="top")
    fig.tight_layout()
    return fig


def best_over_time():
    """The best held-out result available on each day the project has run.

    A running minimum, so the line only ever falls. Where it is flat for weeks,
    nothing that was tried in those weeks improved on what was already there,
    which is most of this project's history and worth being able to see.
    """
    fig, ax = _fig(5.4, 2.6)
    pts = []
    for d in _json("*/bench-sweep-*.json") + _json("*/bench-2*.json"):
        stamp = str(d.get("stamped", ""))[:10]
        rows = d.get("rows") or d.get("scores") or []
        vals = [(r.get("blind") or {}).get("theil_u2") for r in rows
                if isinstance(r.get("blind"), dict) and not r.get("rejected")]
        vals = [v for v in vals if v is not None]
        if stamp and vals:
            pts.append((stamp, min(vals)))
    if len(pts) < 3:
        _nothing(ax, "not enough scored runs yet")
        fig.tight_layout(); return fig
    pts.sort()
    running, best = [], float("inf")
    for _st, v in pts:
        best = min(best, v)
        running.append(best)
    x = np.arange(len(pts))
    ax.plot(x, [p[1] for p in pts], "o", markersize=2.5, color=RULE,
            label="each run")
    ax.plot(x, running, color=NAVY, linewidth=1.8, label="best so far")
    ax.axhline(1.0, color=RED, linewidth=1.2)
    ax.text(0, 1.0, " a constant forecast", fontsize=6.5, color=RED, va="bottom")
    idx = np.linspace(0, len(pts) - 1, min(6, len(pts))).astype(int)
    ax.set_xticks(idx); ax.set_xticklabels([pts[i][0][5:] for i in idx], fontsize=6.5)
    ax.set_ylabel("blind Theil U2")
    ax.set_title(f"Best result available on each day, {len(pts)} runs")
    ax.legend(fontsize=6.5, frameon=False)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# The evidence log, read as a history
#
# Two readers shared by the Assessment and Live book panels. Both open only
# saved records: all 76 sweep files come to 803 KB and parse in a third of a
# second, so neither is cached. A cache on a page the operator leaves open goes
# stale the moment a job finishes and then reports the previous run's numbers as
# the current ones, which is worse than re-reading a megabyte.
# ---------------------------------------------------------------------------

_DATED_DIR = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_STAMP_TAIL = re.compile(r"[-_]?\d{6,}.*$")

# The first word of a record's name, mapped to what kind of work it was. A name
# absent here falls to "other" rather than raising, so a record kind invented
# next week appears on the chart instead of taking the panel down.
_RECORD_GROUP = {
    "bench": "configuration sweeps",
    "eval": "model scoring", "model": "model scoring", "sequence": "model scoring",
    "edge": "diagnostics", "monte": "diagnostics", "regime": "diagnostics",
    "calibration": "diagnostics", "label": "diagnostics", "split": "diagnostics",
    "cross": "diagnostics", "funding": "diagnostics", "mst": "diagnostics",
    "feature": "diagnostics", "microstructure": "diagnostics",
    "survivorship": "diagnostics",
    "DAILY": "the book", "execution": "the book", "weekly": "the book",
    "monthly": "the book", "equity": "the book", "portfolio": "the book",
    "committee": "the book", "fund": "the book",
    "RESULTS": "reports", "AUDIT": "reports",
}

_GROUP_COLOUR = {
    "configuration sweeps": PURPLE, "model scoring": BLUE,
    # Reports take the grey rather than a second blue: navy against the blue of
    # model scoring was two lines the eye could not tell apart on one chart.
    "diagnostics": GREEN, "the book": ORANGE, "reports": SOFT, "other": RULE,
}


def _clip(text: str, width: int) -> str:
    """Cut to a word boundary. A hard slice ends labels mid-word."""
    text = " ".join(str(text).split())
    if len(text) <= width:
        return text
    cut = text[:width].rsplit(" ", 1)[0]
    return (cut or text[:width]) + "…"


def _evidence_records() -> list[dict]:
    """Every record written under a dated folder, with the day it belongs to.

    Dated by the folder, not by the modification time. The folder is the day the
    writing script named and it survives a copy or a checkout; twenty-six of the
    259 records carry a modification time a day or two off their own folder,
    which on a calendar puts the work on the wrong square.
    """
    out = []
    for day_dir in sorted(EVALS.glob("2026-*")):
        if not day_dir.is_dir() or not _DATED_DIR.match(day_dir.name):
            continue
        try:
            day = datetime.strptime(day_dir.name, "%Y-%m-%d").date()
        except ValueError:
            continue
        for f in day_dir.iterdir():
            if f.name.startswith("._") or f.suffix.lower() not in (".md", ".json", ".csv"):
                continue
            kind = _STAMP_TAIL.sub("", f.stem).rstrip("-_") or f.stem
            out.append(dict(day=day, kind=kind, name=f.name,
                            group=_RECORD_GROUP.get(kind.split("-")[0], "other")))
    return out


def _sweeps() -> list[dict]:
    """Every configuration sweep on disk, with its condition flattened out.

    One entry per sweep file: the fits it scored, the winner among them, and the
    five axes the sweep session varied. A sweep whose rows carry no cross-
    validated block is dropped rather than half-read, because a sweep written
    before the five-measure change has no held-out error to rank on.
    """
    out = []
    for p in _records("*/bench-sweep-*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        rows = [r for r in (d.get("rows") or [])
                if isinstance(r.get("cv"), dict) and r["cv"].get("rmse") is not None]
        if not rows:
            continue
        cfg = d.get("config") or {}
        data = cfg.get("data") or {}
        split = cfg.get("split") or {}
        model = cfg.get("model") or {}
        fams = (cfg.get("features") or {}).get("families") or []
        out.append(dict(
            stamped=str(d.get("stamped", "")),
            fits=rows,
            winner=min(rows, key=lambda r: r["cv"]["rmse"]),
            weight=str(model.get("class_weight") or "none"),
            symbols=len(str(data.get("symbols") or "").split()),
            families=" ".join(fams) if fams else "all",
            folds=int(split.get("folds") or 0),
            holdout=int(split.get("holdout_days") or 0),
            file=p.name))
    out.sort(key=lambda s: s["stamped"])
    return out


# The five axes the September sweep session varied, in the order the digest
# reports them. Each is (what to call it, which key on a sweep entry).
_SWEEP_AXES = (("class weight", "weight"), ("assets", "symbols"),
               ("feature families", "families"), ("folds", "folds"),
               ("blind period", "holdout"))


# ---------------------------------------------------------------------------
# Column C, panel C1. Assessment: every run compared across configurations.
#
# Performance is one model at one configuration, computed now. These read the
# whole evidence log and ask a different question: whether the thing being tuned
# is the thing that moves the answer.
# ---------------------------------------------------------------------------

def config_effect():
    """Which setting moves held-out error, against how far the models separate.

    For each axis, the winning configuration's held-out error is averaged within
    each level and the span between levels reported. The dashed line is the mean
    distance between the six forest configurations inside a single sweep. An
    axis that reaches past it moves the answer further than choosing the forest
    does, and tuning the forest is then the wrong question.
    """
    fig, ax = _fig(4.6, 2.8)
    sw = _sweeps()
    if len(sw) < 4:
        _nothing(ax, "fewer than four sweeps on disk;\n"
                     "an axis span needs several conditions to mean anything")
        fig.tight_layout(); return fig

    spans, detail = {}, {}
    for label, key in _SWEEP_AXES:
        levels = {}
        for s in sw:
            levels.setdefault(s[key], []).append(s["winner"]["cv"]["rmse"])
        means = {k: float(np.mean(v)) for k, v in levels.items()}
        if len(means) < 2:
            continue
        spans[label] = max(means.values()) - min(means.values())
        best = min(means, key=means.get)
        detail[label] = f"{best} best at {means[best]:.4f}"
    if not spans:
        _nothing(ax, "every sweep on disk ran the same condition,\n"
                     "so no axis has two levels to compare")
        fig.tight_layout(); return fig

    within = float(np.mean([max(r["cv"]["rmse"] for r in s["fits"])
                            - min(r["cv"]["rmse"] for r in s["fits"]) for s in sw]))
    order = sorted(spans, key=spans.get)
    ax.barh(order, [spans[n] for n in order],
            color=[GREEN if spans[n] > within else BLUE for n in order], height=0.6)
    for i, n in enumerate(order):
        ax.text(spans[n], i, f"  {spans[n]:.4f}", va="center", fontsize=6.5, color=INK)
    ax.axvline(within, color=RED, linestyle="--", linewidth=1.2)
    ax.text(within, len(order) - 0.4, f" the models differ by {within:.4f}",
            fontsize=6.5, color=RED, ha="left", va="top")
    ax.set_xlabel("span of the winner's held-out RMSE between levels")
    ax.set_title(f"What moves the answer, across {len(sw)} sweeps")
    ax.tick_params(axis="y", labelsize=7)
    fig.tight_layout()
    return fig


def sweep_grid():
    """The whole designed experiment as one grid, coloured by held-out error.

    Rows are the data condition, columns are the training regime. A row that is
    uniformly dark across every regime says the condition decides the error and
    the regime does not, which is the same finding the axis chart states as a
    number.
    """
    fig, ax = _fig(6.0, 3.0)
    sw = _sweeps()
    if len(sw) < 4:
        _nothing(ax, "fewer than four sweeps on disk;\na grid needs a grid")
        fig.tight_layout(); return fig

    cells: dict = {}
    for s in sw:
        row = f"{s['symbols']} sym  {s['families'][:22]}"
        col = f"{s['folds']}f {s['holdout']}d\n{s['weight']}"
        cells.setdefault((row, col), []).append(s["winner"]["cv"]["rmse"])
    rows = sorted({k[0] for k in cells})
    cols = sorted({k[1] for k in cells})
    grid = np.ma.masked_all((len(rows), len(cols)))
    for (r, c), vals in cells.items():
        grid[rows.index(r), cols.index(c)] = float(np.mean(vals))

    cmap = plt.get_cmap("RdYlGn_r").copy()
    cmap.set_bad("#f2f5f8")                 # never run, not merely low
    im = ax.imshow(grid, aspect="auto", cmap=cmap)
    ax.set_xticks(range(len(cols))); ax.set_xticklabels(cols, fontsize=5.5)
    ax.set_yticks(range(len(rows))); ax.set_yticklabels(rows, fontsize=6)
    ax.grid(False)
    bar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    bar.ax.tick_params(labelsize=6, colors=SOFT)
    bar.set_label("winner's held-out RMSE", size=6.5, color=SOFT)
    filled = int(grid.count())
    ax.set_title(f"{len(rows)} conditions by {len(cols)} regimes, "
                 f"{filled} of {len(rows) * len(cols)} run")
    fig.tight_layout()
    return fig


def overfit_vs_blind():
    """Whether passing the overfit bar predicts beating a constant forecast.

    The house rule rejects a cross-validated over training RMSE ratio above 1.1.
    That rule exists to stop a memorising model being deployed; it does not claim
    to find a good one. This asks the question directly, on every fit on disk,
    and the counts in the corners are the answer.
    """
    fig, ax = _fig(4.6, 2.8)
    fits = [r for s in _sweeps() for r in s["fits"]]
    fits += [r for d in _json("*/bench-2*.json") for r in (d.get("scores") or [])
             if isinstance(r.get("cv"), dict)]
    pts = [(r["rmse_ratio"], (r.get("blind") or {}).get("theil_u2"))
           for r in fits if r.get("rmse_ratio") is not None]
    pts = [(a, b) for a, b in pts if b is not None]
    if len(pts) < 10:
        _nothing(ax, "fewer than ten fits carry both an overfit ratio\n"
                     "and a blind Theil U2")
        fig.tight_layout(); return fig

    x = np.array([p[0] for p in pts]); y = np.array([p[1] for p in pts])
    keep = (x <= 1.1)
    ax.scatter(x[~keep], y[~keep], s=10, color=RULE, alpha=0.6, zorder=2,
               label="rejected as overfit")
    ax.scatter(x[keep], y[keep], s=14, color=BLUE, alpha=0.7, zorder=3,
               label="passed the 1.1 bar")
    ax.axvline(1.1, color=RED, linestyle="--", linewidth=1.2)
    ax.axhline(1.0, color=NAVY, linestyle="--", linewidth=1.2)
    both = int(((x <= 1.1) & (y < 1.0)).sum())
    beat = int((y < 1.0).sum())
    ax.set_xlabel("overfit ratio, cross-validated over training")
    ax.set_ylabel("blind Theil U2")
    ax.set_title(f"{beat} of {len(pts)} fits beat a constant; {both} also passed "
                 f"the overfit bar")
    ax.legend(fontsize=6.5, frameon=False, loc="upper right")
    fig.tight_layout()
    return fig


def weight_paired():
    """The class weight, on matched conditions rather than on averages.

    Every other axis held fixed and only the weight changed, so the two points
    on a line differ in nothing else. This is the comparison the mean of a column
    cannot make, because the balanced and unweighted sweeps did not cover the
    same conditions in the same numbers.
    """
    fig, ax = _fig(4.2, 2.8)
    sw = _sweeps()
    pairs: dict = {}
    for s in sw:
        key = (s["symbols"], s["families"], s["folds"], s["holdout"])
        pairs.setdefault(key, {})[s["weight"]] = s["winner"]["cv"]["rmse"]
    matched = [(k, v["balanced"], v["none"]) for k, v in pairs.items()
               if "balanced" in v and "none" in v]
    if not matched:
        _nothing(ax, "no condition on disk was run both balanced and unweighted,\n"
                     "so the weight cannot be compared like for like")
        fig.tight_layout(); return fig

    for _k, bal, none in matched:
        ax.plot([0, 1], [none, bal], color=RULE, linewidth=0.9, zorder=2)
        ax.scatter([0, 1], [none, bal], s=16, color=[GREEN, RED], zorder=3)
    gap = float(np.mean([b - n for _k, b, n in matched]))
    ax.set_xlim(-0.35, 1.35)
    ax.set_xticks([0, 1]); ax.set_xticklabels(["unweighted", "balanced"], fontsize=7)
    ax.set_ylabel("winner's held-out RMSE")
    ax.set_title(f"{len(matched)} matched conditions; balanced costs "
                 f"{gap:+.4f} RMSE")
    fig.tight_layout()
    return fig


def config_rank_spread():
    """Where each forest configuration places, across every sweep on disk.

    A configuration that is better is better everywhere. One that wins a third of
    the sweeps and comes last in others has been ranked by the condition rather
    than by its own merit, and the box here is how wide that is.
    """
    fig, ax = _fig(4.6, 2.8)
    sw = _sweeps()
    if len(sw) < 4:
        _nothing(ax, "fewer than four sweeps on disk;\n"
                     "a rank distribution needs several to be a distribution")
        fig.tight_layout(); return fig

    ranks: dict = {}
    for s in sw:
        for place, r in enumerate(sorted(s["fits"], key=lambda r: r["cv"]["rmse"]), 1):
            ranks.setdefault(r.get("name") or r.get("model", "?"), []).append(place)
    # Descending mean place, because a horizontal boxplot draws the first entry
    # at the bottom: this puts the best mean place at the top of the panel.
    order = sorted(ranks, key=lambda n: -float(np.mean(ranks[n])))
    box = ax.boxplot([ranks[n] for n in order], vert=False, widths=0.55,
                     patch_artist=True, showfliers=False)
    for patch in box["boxes"]:
        patch.set(facecolor=BLUE, alpha=0.35, edgecolor=NAVY, linewidth=1.0)
    for whisk in box["whiskers"] + box["caps"]:
        whisk.set(color=SOFT, linewidth=0.9)
    for med in box["medians"]:
        med.set(color=NAVY, linewidth=1.4)
    ax.set_yticklabels(order, fontsize=6.5)
    for i, n in enumerate(order, 1):
        firsts = sum(1 for p in ranks[n] if p == 1)
        ax.text(ax.get_xlim()[1], i, f" first {firsts}/{len(sw)}", va="center",
                fontsize=6, color=SOFT)
    ax.set_xlabel("place within its own sweep, 1 is best")
    ax.set_title(f"Rank across {len(sw)} sweeps, best mean place at the top")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Column C, panel C3. The live book: the long history, not the current run.
# ---------------------------------------------------------------------------

def evidence_growth():
    """What the project recorded, cumulatively, over its whole history.

    One line per kind of work, each the evidence log growing. A line that goes
    flat for six weeks is a line of work that stopped, and the flat stretch
    through July and early August is the crypto edge search being closed rather
    than a gap in the record.
    """
    import datetime as _dt

    fig, ax = _fig(5.4, 2.6)
    recs = _evidence_records()
    if not recs:
        _nothing(ax, "no record written under a dated folder yet")
        fig.tight_layout(); return fig

    lo, hi = min(r["day"] for r in recs), max(r["day"] for r in recs)
    span = (hi - lo).days + 1
    groups = sorted({r["group"] for r in recs},
                    key=lambda g: -sum(1 for r in recs if r["group"] == g))
    series = np.zeros((len(groups), span))
    for r in recs:
        series[groups.index(r["group"]), (r["day"] - lo).days] += 1
    cum = np.cumsum(series, axis=1)
    # One step line per group on a logarithmic axis, not a stack. Stacked and
    # linear, the 152 sweep records written on the evening of 8 September took
    # nine tenths of the height and pressed eleven weeks of earlier work into a
    # strip at the bottom, so the chart said only that one night was busy.
    for row, g in zip(cum, groups):
        ax.step(np.arange(span), np.maximum(row, 0.5), where="post",
                color=_GROUP_COLOUR.get(g, RULE), linewidth=1.5, label=g)
    ax.set_yscale("log")
    ax.set_ylim(0.8, max(cum.max() * 1.6, 2))
    idx = np.linspace(0, span - 1, 5).astype(int)
    ax.set_xticks(idx)
    ax.set_xticklabels([(lo + _dt.timedelta(days=int(i))).strftime("%d %b") for i in idx],
                       fontsize=6.5)
    ax.set_ylabel("records written, cumulative, log scale")
    ax.set_title(f"{len(recs)} records over {span} days, by what the work was")
    ax.legend(fontsize=6, frameon=False, loc="upper left", ncol=2)
    fig.tight_layout()
    return fig


def record_kinds():
    """What kinds of evidence exist, and how many days each ran on.

    The count answers how much of a thing was done; the day count answers whether
    it was done once or returned to. A kind with many records on one day is a
    session, and a kind with few records across many days is a habit.
    """
    fig, ax = _fig(4.6, 3.0)
    recs = _evidence_records()
    if not recs:
        _nothing(ax, "no record written under a dated folder yet")
        fig.tight_layout(); return fig

    counts, days = Counter(), {}
    for r in recs:
        counts[r["kind"]] += 1
        days.setdefault(r["kind"], set()).add(r["day"])
    top = [k for k, _c in counts.most_common(14)][::-1]
    ax.barh(top, [counts[k] for k in top],
            color=[_GROUP_COLOUR.get(_RECORD_GROUP.get(k.split("-")[0], "other"), RULE)
                   for k in top], height=0.65)
    ax.set_xscale("log")                      # 152 sweeps against records of one
    for i, k in enumerate(top):
        ax.text(counts[k], i, f"  {counts[k]} on {len(days[k])}d", va="center",
                fontsize=6, color=INK)
    ax.set_xlabel("records, on a log scale")
    ax.set_title(f"{len(counts)} kinds of record, {len(recs)} in all")
    ax.tick_params(axis="y", labelsize=6)
    fig.tight_layout()
    return fig


def milestone_track():
    """Every notable change, on the date it happened and in its own words.

    The companion to the monthly count beside it: that says how fast the approach
    changed, this says what changed and when. A milestone is a change to the
    model design, the input data or the workflow strategy, never a run.
    """
    import datetime as _dt
    import milestones as ms

    fig, ax = _fig(5.4, 4.2)
    marks = ms.load() or ms.seed()
    if not marks:
        _nothing(ax, "no milestone recorded; seed them with milestones.py --seed")
        fig.tight_layout(); return fig

    dated = []
    for m in marks:
        try:
            dated.append((datetime.strptime(m["date"], "%Y-%m-%d").date(), m))
        except (ValueError, KeyError):
            continue                          # a hand-edited entry, not a crash
    if not dated:
        _nothing(ax, "every milestone on disk carries an unreadable date")
        fig.tight_layout(); return fig

    # Sorted on the date alone. Sorting the pairs compares the dicts whenever two
    # milestones share a day, which eight of the eighteen do, and raises.
    dated.sort(key=lambda t: (t[0], t[1].get("kind", "")))
    lo, hi = dated[0][0], dated[-1][0]
    span = max((hi - lo).days, 1)
    colour = {"design": PURPLE, "data": BLUE, "workflow": GREEN}
    y = np.arange(len(dated))[::-1]
    for row, (d, m) in zip(y, dated):
        x = (d - lo).days
        col = colour.get(m.get("kind"), SOFT)
        ax.plot([0, x], [row, row], color=RULE, linewidth=0.6, zorder=1)
        ax.scatter([x], [row], s=26, color=col, zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{d:%d %b}  {_clip(m['what'], 52)}" for d, m in dated],
                       fontsize=5.6)
    ax.set_xlim(-span * 0.02, span * 1.02)
    idx = np.linspace(0, span, 5).astype(int)
    ax.set_xticks(idx)
    ax.set_xticklabels([(lo + _dt.timedelta(days=int(i))).strftime("%d %b") for i in idx],
                       fontsize=6.5)
    for kind, col in colour.items():
        ax.plot([], [], "o", color=col, markersize=4, label=ms.KINDS[kind])
    # Upper right, not lower right: the milestones run bottom right as the work
    # gets more recent, and a legend there sat on top of the last three labels.
    ax.legend(fontsize=6, frameon=False, ncol=1, loc="upper right")
    ax.set_title(f"{len(dated)} notable changes, {lo:%d %b} to {hi:%d %b}")
    fig.tight_layout()
    return fig


def headline_history():
    """Every headline evaluation the project has recorded, against its own bar.

    Read from the historic scoreboard, which is the one file that survives every
    change of frame and metric. Identical rows are collapsed and the repeat count
    kept, because the scoreboard appends a row per render and the same result
    appears many times over.
    """
    fig, ax = _fig(5.4, 2.8)
    path = EVALS / "evaluation-scores.md"
    if not path.exists():
        _nothing(ax, "evaluation-scores.md is not on disk")
        fig.tight_layout(); return fig

    seen: dict = {}
    for line in path.read_text(errors="replace").splitlines():
        if not line.startswith("| 2026-"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 11:
            continue
        try:
            auc = float(cells[4])
        except ValueError:
            continue                          # a header or a separator row
        # The dataset is part of the key and part of the label. Without it the
        # two HistGBM runs of 6 September, one on 40,000 rows and one on 18,552,
        # collapsed into one bar that hid a difference of 0.024 in AUC.
        key = (cells[0], cells[3], cells[2].split("/")[0].strip(), auc, cells[10])
        seen[key] = seen.get(key, 0) + 1
    if not seen:
        _nothing(ax, "evaluation-scores.md carries no readable run row")
        fig.tight_layout(); return fig

    items = sorted(seen.items())              # by date, then model
    labs = [f"{k[0][5:]}  {k[1][:14]}  {k[2]}  x{n}" for k, n in items]
    vals = [k[3] for k, _n in items]
    verdicts = [k[4] for k, _n in items]
    ax.barh(range(len(vals)), vals,
            color=[GREEN if v.upper().startswith("GO") else RULE for v in verdicts],
            height=0.65)
    ax.axvline(0.55, color=RED, linestyle="--", linewidth=1.2)
    ax.text(0.55, len(vals) - 0.4, " the 0.55 bar", fontsize=6.5, color=RED, va="top")
    ax.axvline(0.5, color=SOFT, linewidth=0.9)
    ax.set_yticks(range(len(vals))); ax.set_yticklabels(labs, fontsize=6)
    ax.set_xlim(0.45, max(0.58, max(vals) + 0.02))
    go = sum(1 for v in verdicts if v.upper().startswith("GO"))
    ax.set_xlabel("test AUC; 0.5 is a coin flip")
    ax.set_title(f"{len(items)} headline evaluations, {go} of them a GO")
    fig.tight_layout()
    return fig


def what_has_been_tried():
    """Every configuration axis the project has explored, and how much of each.

    A count of the distinct settings tried on each axis. A one there means the
    axis has never been varied, and an axis never varied is an assumption rather
    than a finding.
    """
    fig, ax = _fig(4.6, 2.6)
    docs = _json("*/bench-sweep-*.json") + _json("*/bench-2*.json")
    if not docs:
        _nothing(ax, "no runs on disk yet")
        fig.tight_layout(); return fig
    axes_ = {
        "bar size": lambda c: c.get("data", {}).get("frame"),
        "symbols": lambda c: c.get("data", {}).get("symbols"),
        "row cap": lambda c: c.get("data", {}).get("rows"),
        "feature families": lambda c: tuple(c.get("features", {}).get("families") or []),
        "folds": lambda c: c.get("split", {}).get("folds"),
        "resampling": lambda c: c.get("split", {}).get("scheme"),
        "blind period": lambda c: c.get("split", {}).get("holdout_days"),
        "class weight": lambda c: c.get("model", {}).get("class_weight"),
        "estimators": lambda c: tuple(c.get("model", {}).get("estimators") or []),
        "label barrier": lambda c: (c.get("label", {}).get("target_atr"),
                                    c.get("label", {}).get("horizon_bars")),
    }
    counts = {}
    for name, fn in axes_.items():
        vals = set()
        for d in docs:
            try:
                vals.add(fn(d.get("config", {})))
            except (TypeError, AttributeError):
                continue
        counts[name] = len(vals - {None})
    order = sorted(counts, key=counts.get)
    cols = [RED if counts[n] <= 1 else ORANGE if counts[n] == 2 else GREEN
            for n in order]
    ax.barh(order, [counts[n] for n in order], color=cols, height=0.65)
    for i, n in enumerate(order):
        ax.text(counts[n], i, f" {counts[n]}", va="center", fontsize=7, color=INK)
    ax.set_xlabel("distinct settings tried")
    ax.set_title("What has been varied, and what has not")
    ax.tick_params(axis="y", labelsize=7)
    fig.tight_layout()
    return fig


def milestones_by_kind():
    """The pace of notable change, by what changed."""
    import milestones as ms

    fig, ax = _fig(4.6, 2.4)
    marks = ms.load() or ms.seed()
    if not marks:
        _nothing(ax, "no milestones recorded")
        fig.tight_layout(); return fig
    months = sorted({m["date"][:7] for m in marks})
    colour = {"design": PURPLE, "data": BLUE, "workflow": GREEN}
    bottom = np.zeros(len(months))
    for kind, col in colour.items():
        vals = np.array([sum(1 for m in marks
                             if m["date"][:7] == mo and m["kind"] == kind)
                         for mo in months], dtype=float)
        ax.bar(months, vals, bottom=bottom, color=col, width=0.6,
               label=ms.KINDS[kind])
        bottom += vals
    ax.set_ylabel("notable changes")
    ax.set_title(f"{len(marks)} milestones over {len(months)} months")
    ax.legend(fontsize=6.5, frameon=False)
    ax.tick_params(axis="x", labelsize=6.5)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# The figure library
#
# The workflow has produced 123 PNG files across sixteen folders and not one was
# reachable from this page. They are not redrawn here; they are listed, so a
# panel can browse the ones that belong to it.
# ---------------------------------------------------------------------------

FIGURE_DIRS = [
    "04-outputs/PNG", "04-outputs/AA-evals", "04-outputs/dashboard",
    "04-outputs/2A-market-screening", "04-outputs/1A-macd",
    "04-outputs/1B-confluence", "04-outputs/1C-fibonacci",
    "04-outputs/2B-atr-band", "04-outputs/2C-position-sizing",
    "04-outputs/2D-edge-fence", "04-outputs/3A-training-test-data",
    "04-outputs/3B-model-training", "04-outputs/3C-model-tuning",
    "04-outputs/3D-stability", "04-outputs/AA-journal", "04-outputs/journal",
]

# Which figures belong on which panel, matched on the file name. A panel shows
# what it is about rather than the whole library, and the library itself is one
# click away on every one of them.
PANEL_FIGURES = {
    "A1": ("coverage", "panel", "acquire", "vision", "archive", "timeline",
           "profile", "breadth", "survivor", "span", "screen", "candidate",
           "cross-sectional", "rank", "market"),
    "A2": ("feature", "importance", "family", "macd", "confluence", "fib",
           "supertrend", "signal", "journal", "indicator", "candle",
           "entry", "exit"),
    # Renumbered on 9 September 2026 when nine panels became six. The patterns
    # did not change; the keys did, and the two merged panels inherit the
    # patterns of every panel they absorbed. Left alone this dict would have
    # kept sending calibration figures to the training-regime panel and pointing
    # three of its keys at panels that no longer exist, silently, because a key
    # nothing looks up raises nothing.
    "B1": ("varselect", "coef", "enet", "univariate", "cv_curve", "path"),
    "B2": ("split", "fold", "walkforward", "walk-forward", "training-test"),
    # C1 Model and scoreboard: the old Performance, Tuning and Scoreboard.
    "C1": ("calibration", "reliability", "roc", "eval-head", "compare",
           "selectivity", "regime", "tuning", "sweep", "importance", "model-",
           "scoreboard", "monte", "carlo"),
    # C2 History: the old Assessment and Live book.
    "C2": ("assessment", "metrics", "daily", "book", "portfolio", "equity",
           "history"),
}

# Figures a panel shows first, by file name, ahead of the newest-first order.
# The reel holds 33 figures on A2 and avax_macd_20260620.png is dated 20 June,
# so it sat well down the cycle and the operator could not find it. Data rather
# than a special case in the ordering code, so pinning another one is a line
# here and no change to figures().
PINNED = {
    "A2": ("avax_macd_20260620.png",),
}


def figures(panel: str | None = None, limit: int | None = None) -> list[dict]:
    """Every figure the workflow has produced, newest first.

    `panel` narrows to the ones whose file name matches that panel's subjects,
    and puts that panel's PINNED names at the front. Nothing is drawn: these are
    files already on disk.

    De-duplicated on the file NAME, not the resolved path. Several figures exist
    twice, avax_macd_20260620.png under both 04-outputs/dashboard/figures and
    04-outputs/PNG, and two identical pictures in one reel is a reel that looks
    stuck.
    """
    want = PANEL_FIGURES.get(panel or "", ()) if panel else ()
    seen, out = set(), []
    for rel in FIGURE_DIRS:
        root = REPO / rel
        if not root.is_dir():
            continue
        for f in root.rglob("*.png"):
            if f.name.startswith("._") or f.name in seen:
                continue
            seen.add(f.name)
            low = f.name.lower()
            if want and not any(w in low for w in want):
                continue
            out.append(dict(rel=str(f.relative_to(REPO)), name=f.name,
                            folder=rel.split("/")[-1],
                            when=datetime.fromtimestamp(f.stat().st_mtime),
                            kb=f.stat().st_size // 1024))
    out.sort(key=lambda d: d["when"], reverse=True)
    pinned = PINNED.get(panel or "", ())
    if pinned:
        rank = {n: i for i, n in enumerate(pinned)}
        out.sort(key=lambda d: rank.get(d["name"], len(rank)))
    return out[:limit] if limit else out


# ---------------------------------------------------------------------------
# Panel A3, a fourth chart. The three already there report one predictor at a
# time; this one asks whether the whole set departs from noise.
# ---------------------------------------------------------------------------

def lr_distribution():
    """Every predictor's likelihood ratio against the curve noise would give.

    The statistic is twice the difference in log-likelihood between a model with
    one predictor and one with none, so under the null it is chi-squared on one
    degree of freedom, whose density is exp(-x/2) / sqrt(2*pi*x). Drawing the
    observed statistics against that curve says in one picture how far the whole
    candidate set sits from noise, which the ranked bars cannot: a ranking is
    always a ranking, even of nothing.
    """
    fig, ax = _fig(4.2, 3.0)
    hits = _records("varselect/univariate-*.json", 1)
    if not hits:
        _nothing(ax, "no univariate screen on disk yet.\n"
                     "Run variable selection from this panel.")
        fig.tight_layout(); return fig
    doc = json.loads(hits[0].read_text())
    lrs = np.array([r["lr"] for r in doc.get("rows", [])
                    if r.get("lr") is not None], dtype=float)
    if lrs.size < 5:
        _nothing(ax, "fewer than five predictors in the record")
        fig.tight_layout(); return fig

    top = float(max(lrs.max(), 8.0))
    ax.hist(lrs, bins=min(20, max(6, lrs.size // 2)), range=(0, top),
            density=True, color=BLUE, alpha=0.75, label="observed")
    # The density is unbounded at zero, so the grid starts just above it.
    grid = np.linspace(0.05, top, 400)
    chi1 = np.exp(-grid / 2.0) / np.sqrt(2.0 * np.pi * grid)
    ax.plot(grid, chi1, color=RED, linewidth=1.4,
            label="chi-squared on 1 degree of freedom")
    for x, c, lab in ((3.84, NAVY, "5%"), (6.63, PURPLE, "1%")):
        ax.axvline(x, color=c, linestyle="--", linewidth=1)
        ax.text(x, ax.get_ylim()[1] * 0.92, f" {lab}", fontsize=6.5, color=c)
    cleared = doc.get("cleared_05")
    chance = doc.get("expected_by_chance")
    ax.set_xlabel("likelihood ratio against an intercept-only model")
    ax.set_ylabel("density")
    ax.set_title(f"{cleared} of {len(lrs)} predictors cleared the five per cent "
                 f"point against {chance:.1f} expected from noise"
                 if cleared is not None and chance is not None
                 else f"{len(lrs)} predictors against the null curve")
    ax.legend(fontsize=6.5, frameon=False, loc="upper right")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Panel C2, three more. C2's question is where everything stands, so these
# summarise the whole set of fits rather than any one comparison. The blind U2
# against the overfit ratio is deliberately NOT here: that is C1's
# overfit-vs-blind and drawing it twice is what this sweep exists to stop.
# ---------------------------------------------------------------------------

def _all_fits() -> list[dict]:
    """Every scored fit on disk, from the sweeps and from the single runs."""
    fits = [r for s in _sweeps() for r in s["fits"]]
    fits += [r for d in _json("*/bench-2*.json") for r in (d.get("scores") or [])
             if isinstance(r.get("cv"), dict)]
    return fits


def rmse_by_verdict():
    """Held-out error, split by whether the fit passed the overfit bar.

    A rejected fit is not the same as a bad fit and the two are constantly
    confused: the bar is on the ratio of cross-validated to training error, not
    on the error itself. Side by side the two distributions say whether the bar
    is selecting for accuracy or against it.
    """
    fig, ax = _fig(4.2, 2.8)
    fits = _all_fits()
    passed = [r["cv"]["rmse"] for r in fits
              if isinstance(r.get("cv"), dict) and r["cv"].get("rmse") is not None
              and not r.get("rejected")]
    failed = [r["cv"]["rmse"] for r in fits
              if isinstance(r.get("cv"), dict) and r["cv"].get("rmse") is not None
              and r.get("rejected")]
    if len(passed) + len(failed) < 10:
        _nothing(ax, "fewer than ten scored fits on disk")
        fig.tight_layout(); return fig

    groups = [(passed, "passes the 1.1 bar", GREEN), (failed, "rejected as overfit", RED)]
    groups = [g for g in groups if g[0]]
    ax.boxplot([g[0] for g in groups], vert=False, widths=0.55,
               tick_labels=[f"{g[1]}\n{len(g[0])} fits" for g in groups],
               patch_artist=True,
               boxprops=dict(facecolor="#eef2f6", color=RULE),
               medianprops=dict(color=INK, linewidth=1.4),
               whiskerprops=dict(color=RULE), capprops=dict(color=RULE),
               flierprops=dict(marker=".", markersize=3, markerfacecolor=SOFT,
                               markeredgecolor="none"))
    for i, (vals, _, col) in enumerate(groups, start=1):
        ax.scatter(vals, np.full(len(vals), i) + np.random.default_rng(0)
                   .uniform(-0.13, 0.13, len(vals)), s=7, color=col, alpha=0.5,
                   zorder=3)
    med = [f"{np.median(g[0]):.4f}" for g in groups]
    ax.set_xlabel("cross-validated RMSE on the held-out folds, lower is better")
    ax.set_title("Held-out error by verdict, medians " + " against ".join(med))
    ax.tick_params(axis="y", labelsize=6.5)
    fig.tight_layout()
    return fig


def fits_by_config():
    """How many fits each named configuration has, and how they were judged.

    The scoreboard table has 456 rows and no reader counts them by eye. This
    says which conditions have been tried often enough to mean anything and
    which rest on a handful of fits.
    """
    fig, ax = _fig(4.2, 2.8)
    counts: dict = {}
    for r in _all_fits():
        name = str(r.get("name") or r.get("model") or "unnamed")
        slot = counts.setdefault(name, [0, 0])
        slot[1 if r.get("rejected") else 0] += 1
    if not counts:
        _nothing(ax, "no scored fit on disk yet")
        fig.tight_layout(); return fig

    order = sorted(counts.items(), key=lambda kv: -(kv[1][0] + kv[1][1]))[:12][::-1]
    names = [_clip(k, 24) for k, _ in order]
    ok = np.array([v[0] for _, v in order], dtype=float)
    bad = np.array([v[1] for _, v in order], dtype=float)
    ax.barh(names, ok, color=GREEN, height=0.7, label="passes the 1.1 bar")
    ax.barh(names, bad, left=ok, color=RULE, height=0.7, label="rejected as overfit")
    ax.set_xlabel("fits on disk")
    ax.set_title(f"{int(ok.sum() + bad.sum())} fits across "
                 f"{len(counts)} named configurations")
    ax.tick_params(axis="y", labelsize=6)
    ax.legend(fontsize=6.5, frameon=False, loc="lower right")
    fig.tight_layout()
    return fig


def best_by_estimator():
    """The best blind Theil U2 each estimator has reached, and on how many tries.

    Theil's U2 compares the model against always forecasting the base rate, so
    one is the line to cross and everything above it lost to a constant. This is
    the standing summary of the whole scoreboard: which estimator has ever got
    anywhere, not which fit won one sweep.
    """
    fig, ax = _fig(4.2, 2.8)
    best: dict = {}
    for r in _all_fits():
        u2 = (r.get("blind") or {}).get("theil_u2")
        if u2 is None:
            continue
        model = str(r.get("model") or "unnamed")
        cur = best.setdefault(model, [u2, 0])
        cur[0] = min(cur[0], float(u2))
        cur[1] += 1
    if not best:
        _nothing(ax, "no fit on disk carries a blind Theil U2")
        fig.tight_layout(); return fig

    order = sorted(best.items(), key=lambda kv: -kv[1][0])
    names = [f"{k}  ({v[1]} fits)" for k, v in order]
    vals = [v[0] for _, v in order]
    ax.barh(names, vals, color=[GREEN if v < 1.0 else RULE for v in vals],
            height=0.7)
    ax.axvline(1.0, color=RED, linewidth=1.4)
    ax.text(1.0, len(names) - 0.4, " a constant forecast", fontsize=6.5, color=RED)
    beat = sum(1 for v in vals if v < 1.0)
    ax.set_xlabel("best Theil's U2 on the blind period, lower is better")
    ax.set_title(f"{beat} of {len(vals)} estimators have ever beaten a constant")
    ax.tick_params(axis="y", labelsize=6.5)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Panel A1. How the cube is assembled, traced out of the source rather than
# drawn from memory: acquire_vision.crawl_archive_symbols for the sources,
# build_dataset_1h.build_coin for the order of the blocks.
# ---------------------------------------------------------------------------

# The feature blocks in the exact order build_coin calls them, with the column
# prefix each one emits. Three of them are joins, the only places another series
# enters a coin's own rows, and they are drawn as arrows from the side.
_CUBE_BLOCKS = (
    ("indicator_block(wc)", "f_wc_", "wall-clock windows", ""),
    ("indicator_block(hr)", "f_hr_", "intraday windows", ""),
    ("extra_ta_block", "f_ta_", "in-house oscillators", ""),
    ("supertrend_block", "f_st_", "triple Supertrend", ""),
    ("pandas_ta_block", "f_ta_pta_", "optional library block", ""),
    ("talib_block", "f_tl_", "optional library block", ""),
    ("flow_block", "f_flow_", "trade-flow imbalance", "the taker-buy flow table"),
    ("btc_block", "f_btc_", "relative strength", "BTC's own bars"),
    ("multitf_block", "f_4h_", "higher-timeframe context", "4h, daily, weekly bars"),
    ("modern_supertrend_block", "f_mst_", "adaptive Supertrend", ""),
    ("regime_block", "f_rg_", "volatility and trend regime", ""),
    ("microstructure_block", "f_ms_", "optional, from hourly bars", ""),
)


def _cube_counts() -> tuple[dict, int, int]:
    """Columns per family and rows in the built panel, from the Parquet footer.

    The footer and the directory listing only. Reading the panel itself is two
    gigabytes on a machine already deep in swap, and this is a diagram.
    """
    per, rows, symbols = {}, 0, 0
    root = REPO / "03-inputs" / "binance-data"
    for frame in ("4h", "1h", "1d"):
        kl = root / f"klines_{frame}"
        if kl.is_dir():
            symbols = sum(1 for d in kl.iterdir() if d.is_dir())
            break
    for frame in ("4h", "1h", "1d", "5m"):
        panel = root / f"dataset_{frame}_allmarket.parquet"
        if not panel.is_file():
            continue
        try:
            import pyarrow.parquet as pq
            meta = pq.ParquetFile(str(panel))
            rows = meta.metadata.num_rows
            for col in meta.schema_arrow.names:
                for pref in FAMILY_COLOUR:
                    if col.startswith(pref):
                        per[pref] = per.get(pref, 0) + 1
                        break
        except Exception:                                   # noqa: BLE001
            per, rows = {}, 0
        break
    return per, rows, symbols


def data_cube():
    """How one coin's rows become the panel, block by block, with its joins.

    The surprise at the end is that the price columns do not survive: open,
    high, low and close are consumed by the feature blocks and never written,
    which is why the indicator overlay had to be rewritten to read the klines
    directly rather than the panel.
    """
    fig, ax = _fig(9.2, 6.4)
    per, rows, symbols = _cube_counts()
    ax.set_xlim(0, 100); ax.set_ylim(0, 100)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.grid(False)

    def box(x, y, w, h, text, face, edge, fontsize=6.4, weight="normal",
            colour=INK):
        ax.add_patch(plt.Rectangle((x, y), w, h, facecolor=face, edgecolor=edge,
                                   linewidth=1.0, zorder=2))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                fontsize=fontsize, color=colour, zorder=3, fontweight=weight,
                linespacing=1.35)

    def arrow(xy_from, xy_to, colour=SOFT, style="-|>", width=1.1, dashed=False):
        ax.annotate("", xy=xy_to, xytext=xy_from,
                    arrowprops=dict(arrowstyle=style, color=colour,
                                    linewidth=width, shrinkA=1, shrinkB=1,
                                    linestyle="--" if dashed else "-"))

    # --- sources -----------------------------------------------------------
    src = ("data.binance.vision archive listing, crawled\n"
           "by acquire_vision.crawl_archive_symbols rather\n"
           "than exchangeInfo: 612 pairs ever listed against\n"
           "about 433 alive, so roughly 31 per cent of the\n"
           "panel is coins that no longer exist. Checksummed\n"
           "monthly zips, and a dated exchangeInfo snapshot"
           + (f"\n{symbols} symbol folders on disk" if symbols else ""))
    box(1, 74, 29, 22, src, "#eef2f6", NAVY, 5.9, "normal", INK)
    box(1, 62, 29, 9, "alpaca_data.py\nadjusted daily equity bars, a separate path",
        "#f6f2ee", ORANGE, 5.9, "normal", INK)

    # --- the profile side branch ------------------------------------------
    box(1, 38, 29, 18,
        "profile_panel.py\nstreams one symbol at a time to measure\ncoverage, gaps, the listing "
        "timeline and\nbreadth, and derives the usable start, the\nminimum history, the purge and "
        "the embargo\n04-outputs/AA-evals/panel-profile/",
        "#f4f0f8", PURPLE, 5.9, "normal", INK)
    # The profile is a side branch. It never adds a column; it sets the screen
    # that decides which rows are in_sample, so its arrow lands on the screen
    # rather than anywhere in the block chain.
    arrow((22, 38), (34.5, 8.0), PURPLE, dashed=True)
    ax.text(8, 20, "sets the screen,\nnot a column", fontsize=5.6,
            color=PURPLE, va="center", ha="left")

    # --- the raw bars ------------------------------------------------------
    box(35, 84, 22, 10, "raw OHLCV bars for one symbol\nbuild_dataset_1h.build_coin()",
        "#ffffff", INK, 6.4, "bold")
    arrow((30, 85), (35, 88))

    # --- the block chain ---------------------------------------------------
    n = len(_CUBE_BLOCKS)
    top, bottom = 82.0, 12.0
    step = (top - bottom) / n
    hgt = step * 0.66
    for i, (fn, pref, what, joins) in enumerate(_CUBE_BLOCKS):
        y = top - (i + 1) * step
        col = FAMILY_COLOUR.get(pref, SOFT)
        cnt = per.get(pref)
        label = (f"{fn}   {pref}{f'   {cnt} cols' if cnt else ''}\n{what}")
        box(35, y, 22, hgt, label, "#ffffff", col, 5.5, "normal", INK)
        arrow((46, y + step), (46, y + hgt), col)
        if joins:
            # A join is another series entering these rows, so it arrives from
            # the side rather than continuing the line down the chain.
            box(60, y, 21, hgt, f"JOIN   {joins}", "#fbf7ee", col, 5.6, "bold", col)
            arrow((60, y + hgt / 2), (57, y + hgt / 2), col, width=1.6)

    # --- what comes out ----------------------------------------------------
    box(35, 3.0, 46, 7,
        "columns stacked; datetime then symbol inserted at the front;\n"
        "in_sample from screen_membership(), label and trade_ret from "
        "compute_label_return()",
        "#eef2f6", NAVY, 5.7, "normal", INK)
    arrow((46, 12), (46, 10.0), NAVY)

    out = ("dataset_<frame>_allmarket.parquet\nsymbol, datetime, in_sample,\n"
           "label, trade_ret, and the features"
           + (f"\n{rows:,} rows on disk" if rows else ""))
    box(84, 30, 15, 16, out, "#ffffff", NAVY, 5.9, "bold", NAVY)
    arrow((81, 6.5), (91.5, 30), NAVY, width=1.4)

    box(84, 52, 15, 16,
        "NO open, high, low or close.\nThe price is not in the cube,\nwhich is why the "
        "indicator\noverlay had to be rewritten\nto read the klines directly",
        "#fdf6f6", RED, 5.7, "bold", RED)
    arrow((91.5, 52), (91.5, 46.5), RED, width=1.4)

    ax.set_title("How one coin's bars become the panel, in the order build_coin "
                 "calls the blocks", fontsize=8.5, color=INK, fontweight="bold")
    fig.subplots_adjust(left=0.01, right=0.99, top=0.94, bottom=0.02)
    return fig


# ---------------------------------------------------------------------------

def _candles(ax, d, width=0.62):
    """Draw real candles. Body from open to close, wick from low to high.

    A line chart hides the thing a trader reads: where the bar opened against
    where it closed, and how far it reached in between. Every price drawing on
    this page was a line until 9 September 2026.
    """
    x = np.arange(len(d))
    o, h, l, c = (d["open"].to_numpy(float), d["high"].to_numpy(float),
                  d["low"].to_numpy(float), d["close"].to_numpy(float))
    up = c >= o
    ax.vlines(x[up], l[up], h[up], color=GREEN, linewidth=0.7)
    ax.vlines(x[~up], l[~up], h[~up], color=RED, linewidth=0.7)
    ax.bar(x[up], (c - o)[up], bottom=o[up], width=width, color=GREEN,
           edgecolor=GREEN, linewidth=0.4)
    ax.bar(x[~up], (c - o)[~up], bottom=o[~up], width=width, color=RED,
           edgecolor=RED, linewidth=0.4)
    return x


def _date_ticks(ax, d, n=6):
    x = np.linspace(0, len(d) - 1, n).astype(int)
    ax.set_xticks(x)
    ax.set_xticklabels([d["datetime"].iloc[i].strftime("%d %b") for i in x],
                       fontsize=6.5)


def candles_volume():
    """Candles with volume beneath, on the bars the run is pointed at."""
    import bench_config as bc

    got = _klines(bc.load(), 180)
    fig, (ax, axv) = plt.subplots(2, 1, figsize=(4.2, 2.9), dpi=110,
                                  sharex=True,
                                  gridspec_kw=dict(height_ratios=[3, 1], hspace=0.05))
    for a in (ax, axv):
        _dress(a)
    if not got:
        _nothing(ax, "no bars for the chosen symbol")
        fig.tight_layout(); return fig
    (sym, frame), d = got
    d = d.tail(140).reset_index(drop=True)
    x = _candles(ax, d)
    up = d["close"].to_numpy(float) >= d["open"].to_numpy(float)
    axv.bar(x[up], d["volume"].to_numpy(float)[up], color=GREEN, width=0.62)
    axv.bar(x[~up], d["volume"].to_numpy(float)[~up], color=RED, width=0.62)
    axv.set_ylabel("volume", fontsize=6.5)
    _date_ticks(axv, d)
    ax.set_title(f"{sym}, {frame} bars, last {len(d)}")
    fig.subplots_adjust(left=0.13, right=0.98, top=0.90, bottom=0.14)
    return fig


def candles_barrier():
    """Candles with the triple barrier drawn on a few entries.

    The label is a modelling decision and this is the picture of it: from a bar,
    a take-profit above, a stop below, both scaled to that bar's own volatility,
    and a time limit to the right. Whichever is touched first is the outcome the
    model is asked to predict.
    """
    import bench_config as bc

    cfg = bc.load()
    # Eighty bars, not 220. The barrier is a box a dozen bars wide, and at 220
    # bars in a 460-pixel card it was a smudge two pixels across. The point of
    # this chart is the shape of the box.
    # _klines reads whole monthly archives, so asking for 80 bars returned 330.
    # Trim after the read; the request only decides how many months are opened.
    got = _klines(cfg, 80)
    fig, ax = _fig(4.2, 2.9)
    if not got:
        _nothing(ax, "no bars for the chosen symbol")
        fig.tight_layout(); return fig
    (sym, frame), d = got
    d = d.tail(80).reset_index(drop=True)
    x = _candles(ax, d)

    tgt = float(cfg["label"]["target_atr"])
    stp = float(cfg["label"]["stop_atr"])
    hor = int(cfg["label"]["horizon_bars"])
    tr = np.maximum(d["high"] - d["low"],
                    np.maximum((d["high"] - d["close"].shift()).abs(),
                               (d["low"] - d["close"].shift()).abs()))
    atr = tr.rolling(14).mean().to_numpy(float)

    starts = [i for i in range(16, len(d) - hor - 1, max(hor + 8, 20))][:3]
    for i in starts:
        if not np.isfinite(atr[i]):
            continue
        c0 = float(d["close"].iloc[i])
        hi, lo = c0 + tgt * atr[i], c0 - stp * atr[i]
        ax.add_patch(plt.Rectangle((i, lo), hor, hi - lo, fill=True,
                                   facecolor=NAVY, alpha=0.07, edgecolor=NAVY,
                                   linewidth=0.8, zorder=0))
        ax.hlines(hi, i, i + hor, color=GREEN, linewidth=0.9, linestyle="--")
        ax.hlines(lo, i, i + hor, color=RED, linewidth=0.9, linestyle="--")
        ax.plot([i], [c0], "o", color=NAVY, markersize=3.5, zorder=3)
    _date_ticks(ax, d)
    ax.set_title(f"The barrier the label draws: +{tgt:g} / -{stp:g} ATR, {hor} bars")
    fig.tight_layout()
    return fig


def candles_regimes():
    """The same bars in four stretches, so a regime is visible as a regime."""
    import bench_config as bc

    got = _klines(bc.load(), 1200)
    fig, axes = plt.subplots(1, 4, figsize=(6.4, 1.9), dpi=110)
    for a in axes:
        _dress(a)
    if not got:
        _nothing(axes[0], "no bars for the chosen symbol")
        fig.tight_layout(); return fig
    (sym, frame), d = got
    n = len(d) // 4
    for a, k in zip(axes, range(4)):
        seg = d.iloc[k * n:(k + 1) * n]
        if len(seg) < 5:
            _nothing(a, "too few bars"); continue
        _candles(a, seg, width=0.8)
        ret = float(seg["close"].iloc[-1] / seg["close"].iloc[0] - 1) * 100
        a.set_title(f"{seg['datetime'].iloc[0]:%b %Y}  {ret:+.0f}%", fontsize=7,
                    color=GREEN if ret >= 0 else RED)
        a.set_xticks([]); a.tick_params(labelsize=6)
    fig.suptitle(f"{sym}, {frame} bars, four consecutive stretches",
                 fontsize=8.5, color=INK, fontweight="bold")
    fig.subplots_adjust(left=0.06, right=0.99, top=0.78, bottom=0.10, wspace=0.32)
    return fig



# ---------------------------------------------------------------------------
# The money, in dollars.
#
# Operator instruction, 9 September 2026: report gains and losses as dollar
# amounts on each position and in total, not only as percentages. A percentage
# on a position says how that holding did; only the dollar says what it did to
# the account, and a 16 per cent fall on a 1.5 per cent weight and a 2 per cent
# fall on a 12 per cent weight are the same money.
#
# The feed is the dashboard's own, written by dashboard_data.py from the live
# Alpaca account: 04-outputs/dashboard/data.json. Nothing here recomputes a
# price or a fill; it reads what the broker reported and states it in dollars.
# The book is a paper account, which every caption says.
# ---------------------------------------------------------------------------

BOOK = REPO / "04-outputs" / "dashboard" / "data.json"


def _book() -> dict:
    """The dashboard feed, or an empty dict if it has never been written."""
    try:
        return json.loads(BOOK.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _usd(v, dp=0) -> str:
    r"""A signed dollar amount for a matplotlib label. -285.45 becomes -\$285.

    The dollar sign is escaped because matplotlib reads a pair of them as
    mathtext and typesets everything between as an equation. The first draw of
    money_curve had two in its title and came out as italic run-together maths
    with the comma and the minus sign reset as operators.
    """
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "n/a"
    sign = "-" if v < 0 else ""
    return f"{sign}\\${abs(v):,.{dp}f}"


def _book_stale() -> str:
    """One line saying when the feed was written, for a caption."""
    m = _book().get("meta") or {}
    return str(m.get("generated_at_pretty") or "never")


def money_by_position():
    """Dollars gained and lost on each holding, largest either way."""
    fig, ax = _fig(4.6, 2.8)
    pos = [r for r in (_book().get("positions") or [])
           if r.get("pl") is not None]
    if not pos:
        _nothing(ax, "No open positions in the feed.\nRun scripts/render_dashboard.sh "
                     "to refresh 04-outputs/dashboard/data.json.")
        fig.tight_layout()
        return fig
    pos.sort(key=lambda r: float(r["pl"]))
    take = pos[:8] + pos[-8:] if len(pos) > 16 else pos
    names = [r["symbol"] for r in take]
    vals = [float(r["pl"]) for r in take]
    y = np.arange(len(take))
    ax.barh(y, vals, color=[GREEN if v >= 0 else RED for v in vals],
            height=0.72, alpha=0.9)
    ax.set_yticks(y); ax.set_yticklabels(names, fontsize=6.5)
    ax.axvline(0, color=INK, linewidth=0.8)
    span = max(abs(min(vals)), abs(max(vals))) or 1.0
    for i, v in enumerate(vals):
        ax.text(v + (0.02 * span if v >= 0 else -0.02 * span), i, _usd(v),
                va="center", ha="left" if v >= 0 else "right",
                fontsize=6, color=INK)
    ax.set_xlim(-span * 1.28, span * 1.28)
    ax.set_xlabel("gain or loss, US dollars")
    won = sum(v for v in (float(r["pl"]) for r in pos) if v > 0)
    lost = sum(v for v in (float(r["pl"]) for r in pos) if v < 0)
    ax.set_title(f"Open positions: {_usd(won)} up, {_usd(lost)} down, "
                 f"{_usd(won + lost)} net")
    ax.grid(axis="x", color=RULE, alpha=0.35, linewidth=0.6)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    return fig


def money_waterfall():
    """Where the account stands in dollars, from the opening deposit."""
    fig, ax = _fig(4.6, 2.6)
    b = _book()
    h, pos = b.get("headline") or {}, b.get("positions") or []
    if not h:
        _nothing(ax, "No account headline in the feed.")
        fig.tight_layout()
        return fig
    won = sum(float(r["pl"]) for r in pos if (r.get("pl") or 0) > 0)
    lost = sum(float(r["pl"]) for r in pos if (r.get("pl") or 0) < 0)
    closed = sum(float(r.get("pl") or 0) for r in (b.get("roundtrips") or []))
    start = float(h.get("start") or 0.0)
    equity = float(h.get("equity") or 0.0)
    other = equity - start - won - lost - closed
    steps = [("Deposited", start, NAVY), ("Winners open", won, GREEN),
             ("Losers open", lost, RED), ("Trades closed", closed, ORANGE),
             ("Fees and rest", other, SOFT), ("Worth now", equity, NAVY)]
    # The bars are drawn on a zoomed axis, not from zero. Each step here is a
    # few thousand dollars against a hundred-thousand-dollar account, so an axis
    # anchored at zero renders every one of them as a hairline; the first draw
    # of this chart was exactly that and unreadable. The floor is stated on the
    # axis label so nobody reads a bar's height as its value.
    x, base, path = np.arange(len(steps)), 0.0, [start]
    for name, v, _ in steps[1:-1]:
        path.append(path[-1] + v)
    path.append(equity)
    lo, hi = min(path), max(path)
    pad = max((hi - lo) * 0.35, abs(equity) * 0.004)
    floor = lo - pad
    for i, (name, v, col) in enumerate(steps):
        if name in ("Deposited", "Worth now"):
            ax.bar(i, v - floor, bottom=floor, color=col, width=0.62, alpha=0.9)
            top, lab = v, _usd(v)
            base = v if name == "Deposited" else base
        else:
            ax.bar(i, v, bottom=base, color=col, width=0.62, alpha=0.9)
            top, lab = base + max(v, 0.0), _usd(v)
            base += v
        ax.text(i, top + (hi - floor) * 0.03, lab, ha="center", fontsize=6.4,
                color=INK, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([s[0] for s in steps], fontsize=6.2, rotation=18,
                       ha="right")
    ax.set_ylim(floor, hi + (hi - floor) * 0.16)
    ax.set_ylabel(f"US dollars, axis from {_usd(floor)}")
    ax.set_title(f"{_usd(equity)} now against {_usd(start)} deposited, "
                 f"{_usd(equity - start)} on the account")
    fig.tight_layout()
    return fig


def money_closed():
    """Dollars realised on finished trades, one bar each and a running total."""
    fig, ax = _fig(4.6, 2.6)
    rt = [r for r in (_book().get("roundtrips") or []) if r.get("pl") is not None]
    if not rt:
        _nothing(ax, "No finished trades in the feed yet.")
        fig.tight_layout()
        return fig
    rt.sort(key=lambda r: str(r.get("sold_at") or ""))
    vals = [float(r["pl"]) for r in rt]
    x = np.arange(len(vals))
    ax.bar(x, vals, color=[GREEN if v >= 0 else RED for v in vals],
           width=0.75, alpha=0.85)
    ax.axhline(0, color=INK, linewidth=0.8)
    ax.set_ylabel("realised, US dollars")
    ax.set_xticks(x[::max(1, len(x) // 8)])
    ax.set_xticklabels([str(rt[i].get("sold_at") or "")[5:10]
                        for i in x[::max(1, len(x) // 8)]], fontsize=6)
    run = ax.twinx()
    _dress(run)
    run.plot(x, np.cumsum(vals), color=NAVY, linewidth=1.4)
    run.set_ylabel("running total, US dollars", color=NAVY)
    run.grid(visible=False)
    total = float(np.sum(vals))
    wins = [v for v in vals if v > 0]
    ax.set_title(f"{len(rt)} trades closed for {_usd(total)}: "
                 f"{len(wins)} up {_usd(sum(wins))}, "
                 f"{len(vals) - len(wins)} down "
                 f"{_usd(sum(v for v in vals if v <= 0))}")
    fig.tight_layout()
    return fig


def money_curve():
    """The account in dollars since it went live, against the deposit line."""
    fig, ax = _fig(4.6, 2.6)
    b = _book()
    curve = b.get("equity_curve") or []
    h = b.get("headline") or {}
    if not curve:
        _nothing(ax, "No equity curve in the feed.")
        fig.tight_layout()
        return fig
    key = "equity" if "equity" in curve[0] else next(
        (k for k in curve[0] if k != "date"), None)
    # Only from the day the book went live. The feed carries the whole series
    # the broker returns, which sits flat at the opening deposit for the ten
    # weeks before the first order, and that flat run took two thirds of the
    # width and made the live part unreadable.
    live = str((b.get("meta") or {}).get("live_from") or "")
    curve = [r for r in curve if str(r.get("date") or "") >= live] or curve
    vals = [float(r[key]) for r in curve if r.get(key) is not None]
    x = np.arange(len(vals))
    start = float(h.get("start") or vals[0])
    ax.plot(x, vals, color=NAVY, linewidth=1.5)
    ax.fill_between(x, start, vals, where=np.array(vals) >= start,
                    color=GREEN, alpha=0.18, interpolate=True)
    ax.fill_between(x, start, vals, where=np.array(vals) < start,
                    color=RED, alpha=0.18, interpolate=True)
    ax.axhline(start, color=SOFT, linewidth=0.9, linestyle="--")
    ax.text(0, start, f" deposited {_usd(start)}", fontsize=6.2, color=SOFT,
            va="bottom")
    ax.set_ylabel("account value, US dollars")
    ax.set_xticks(x[::max(1, len(x) // 6)])
    ax.set_xticklabels([str(curve[i].get("date") or "")[5:10]
                        for i in x[::max(1, len(x) // 6)]], fontsize=6)
    ax.set_title(f"{_usd(vals[-1])} on the paper account, "
                 f"{_usd(vals[-1] - start)} against the deposit")
    fig.tight_layout()
    return fig


CHARTS = {
    "candles-volume": (candles_volume, "Candles with volume beneath"),
    "candles-barrier": (candles_barrier, "The barrier the label draws, on candles"),
    "candles-regimes": (candles_regimes, "Four stretches of the same bars"),
    "data-cube": (data_cube, "How the data cube is assembled"),
    "lr-distribution": (lr_distribution, "The whole candidate set against noise"),
    "rmse-by-verdict": (rmse_by_verdict, "Held-out error, by verdict"),
    "fits-by-config": (fits_by_config, "How many fits each configuration has"),
    "best-by-estimator": (best_by_estimator, "The best each estimator has reached"),
    "cost-by-frame": (cost_by_frame, "What a round trip costs, by bar size"),
    "panel-coverage": (panel_coverage, "Panels built and available"),
    "timeline-span": (timeline_span, "Training window against blind period"),
    "label-base-rate": (label_base_rate, "The barrier's base rate against its breakeven"),
    "screen-survivors": (screen_survivors, "Assets in the panel, by year"),
    "family-composition": (family_composition, "Columns per feature family"),
    "family-importance": (family_importance, "Which families carry weight"),
    "univariate-ranking": (univariate_ranking, "Each predictor alone, by likelihood ratio"),
    "enet-path": (enet_path, "The elastic-net cross-validation curve"),
    "split-diagram": (split_diagram, "The chronological split, to scale"),
    "error-full-vs-cv": (error_full_vs_cv, "In sample against held out"),
    "reliability-curve": (reliability_curve, "Stated probability against what happened"),
    "sweep-ranking": (sweep_ranking, "How often each configuration came first"),
    "capacity-vs-error": (capacity_vs_error, "Does fitting more help"),
    "overfit-vs-error": (overfit_vs_error, "What the overfit bar costs in held-out error"),
    "tuning-stability": (tuning_stability, "Is the winner separable from the runner-up"),
    "hyper-response": (hyper_response, "How each hyperparameter moves held-out error"),
    "assessment-compact": (assessment_compact, "Recent runs and whether they passed"),
    "scoreboard": (scoreboard, "Every fit against a constant forecast"),
    "kde-separation": (kde_separation, "The two outcomes as smooth densities"),
    "kde-spread": (kde_spread, "How much of the range the model uses"),
    "kde-null-band": (kde_null_band, "The calibration curve against no signal"),
    "run-calendar": (run_calendar, "Runs by day"),
    "run-ranking": (run_ranking, "Best of each sweep, ranked"),
    "best-over-time": (best_over_time, "The best result available on each day"),
    "what-has-been-tried": (what_has_been_tried, "Which axes have been varied"),
    "milestones-by-kind": (milestones_by_kind, "The pace of notable change"),
    # C1 Assessment: every run compared across configurations, which is the
    # question Performance cannot answer because it fits one configuration.
    "config-effect": (config_effect, "What moves the answer, by axis"),
    "sweep-grid": (sweep_grid, "The designed experiment as one grid"),
    "overfit-vs-blind": (overfit_vs_blind, "Does passing the overfit bar predict anything"),
    "weight-paired": (weight_paired, "The class weight on matched conditions"),
    "config-rank-spread": (config_rank_spread, "Where each configuration places"),
    # C3 Live book: the long history rather than the current run.
    "evidence-growth": (evidence_growth, "What the project recorded, cumulatively"),
    "record-kinds": (record_kinds, "What kinds of evidence exist"),
    "milestone-track": (milestone_track, "Every notable change, dated"),
    "headline-history": (headline_history, "Every headline evaluation, against its bar"),
    "cross-sectional-spread": (cross_sectional_spread, "Top third against the market"),
    "indicator-overlay": (indicator_overlay, "Price with its trend geometry"),
    "confluence-agreement": (confluence_agreement, "How often the engines agree"),
    "coefficient-intervals": (coefficient_intervals, "Each predictor with its interval"),
    "fold-coverage": (fold_coverage, "What each fold trains and scores on"),
    "regime-demo": (regime_demo, "Every resampling regime on the same rows"),
    "regime-advance": (regime_advance, "The fold advancing through real dates, frame by frame"),
    "regime-uncertainty": (regime_uncertainty,
                           "How wide the estimate is, fold by fold, through time"),
    # The money, in dollars, on the operator's instruction of 9 September 2026.
    "money-by-position": (money_by_position, "Dollars made and lost, by holding"),
    "money-waterfall": (money_waterfall, "Where the money went, in dollars"),
    "money-closed": (money_closed, "Dollars realised on finished trades"),
    "money-curve": (money_curve, "The account in dollars since it went live"),
    "timeline": (timeline, "Every run, with the milestones marked"),
}


def draw(name: str, scale: float = 1.0):
    """One chart as PNG bytes, or None if the name is not known.

    `scale` multiplies the dots per inch, so the full-page view is a genuinely
    higher-resolution render of the same drawing rather than the small one
    stretched. The token is reset in a finally block: a chart that raises must
    not leave the next request drawing at whatever this one asked for.
    """
    import io
    entry = CHARTS.get(name)
    if entry is None:
        return None
    token = _SCALE.set(float(scale))
    try:
        fig = entry[0]()
    except Exception as exc:                            # noqa: BLE001
        # A chart that raises must not take the page down with it. The panel
        # gets a box saying which chart failed and why, which is more use than
        # a broken image icon.
        fig, ax = _fig()
        _nothing(ax, f"{name} could not be drawn:\n{type(exc).__name__}: {exc}")
        fig.tight_layout()
    finally:
        _SCALE.reset(token)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white",
                dpi=fig.dpi)
    plt.close(fig)
    return buf.getvalue()
