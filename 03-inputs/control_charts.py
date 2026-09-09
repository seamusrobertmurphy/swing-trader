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

import glob
import json
import os
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


def _fig(w=4.2, h=2.6):
    fig, ax = plt.subplots(figsize=(w, h), dpi=110)
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
# Column A. Data
# ---------------------------------------------------------------------------

def cost_by_frame():
    """What a round trip costs per year of holding, by bar size.

    The fee is flat per trade, so the bar size decides how often it is paid. This
    is the arithmetic that ruled out the five-minute frame and it belongs beside
    the choice of bar size rather than in a panel of its own.
    """
    frames = [("5m", 5), ("15m", 15), ("1h", 60), ("4h", 240), ("1d", 1440)]
    per_trade = 0.20                                   # per cent, round trip
    fig, ax = _fig()
    bars_a_year = [365 * 24 * 60 / m for _n, m in frames]
    # One round trip every twenty bars is the label's own horizon on the 4h frame.
    cost = [per_trade * (b / 20) for b in bars_a_year]
    names = [n for n, _m in frames]
    cols = [RED if c > 100 else ORANGE if c > 20 else GREEN for c in cost]
    ax.bar(names, cost, color=cols, width=0.6)
    for x, c in zip(names, cost):
        ax.text(x, c, f"{c:,.0f}%", ha="center", va="bottom", fontsize=7,
                color=INK, fontweight="bold")
    ax.set_yscale("log")
    ax.set_ylabel("fees per year of holding, %")
    ax.set_title("A round trip costs 0.20%. The bar size decides how often")
    fig.tight_layout()
    return fig


def panel_coverage():
    """How much history each built panel carries, and how many assets."""
    import bench_config as bc

    rows = []
    for market, spec in bc.MARKETS.items():
        for name, rel in spec["frames"].items():
            p = REPO / rel
            if p.exists():
                rows.append((name, p.stat().st_size / 2 ** 20))
    fig, ax = _fig()
    if not rows:
        _nothing(ax, "no panel built yet")
        fig.tight_layout(); return fig
    rows.sort(key=lambda r: r[1])
    ax.barh([r[0] for r in rows], [r[1] for r in rows], color=BLUE, height=0.6)
    for i, (_n, mb) in enumerate(rows):
        ax.text(mb, i, f" {mb:,.0f} MB", va="center", fontsize=7, color=INK)
    ax.set_xlabel("size on disk, MB")
    ax.set_title("Panels built and available")
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
    cols_ = [BLUE if (not chosen or f in chosen) else RULE for f in fams]
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
    """Permutation importance by family, from the saved feature report."""
    import csv

    fig, ax = _fig()
    hits = _records("*/feature-report-*.csv", 1)
    if not hits:
        _nothing(ax, "no feature report on disk.\nRun it from the panel below.")
        fig.tight_layout(); return fig
    rows = list(csv.DictReader(hits[0].open()))
    key = next((k for k in (rows[0] if rows else {})
                if "perm" in k.lower() or "import" in k.lower()), None)
    name_key = next((k for k in (rows[0] if rows else {})
                     if "feat" in k.lower() or k.lower() == "name"), None)
    if not rows or not key or not name_key:
        _nothing(ax, f"{hits[0].name}\nhas no importance column")
        fig.tight_layout(); return fig
    agg = Counter()
    for r in rows:
        fam = "_".join(r[name_key].split("_")[:2]) + "_"
        try:
            agg[fam] += float(r[key])
        except (TypeError, ValueError):
            continue
    fams = sorted(agg, key=agg.get)[-10:]
    ax.barh(fams, [agg[f] for f in fams], color=GREEN, height=0.65)
    ax.set_xlabel("summed permutation importance")
    ax.set_title(f"Which families carry weight, {hits[0].name[:28]}")
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
    """The elastic-net cross-validation curve, as saved by the screen."""
    fig, ax = _fig()
    png = _records("varselect/cv_curve.png", 1)
    _nothing(ax, "the elastic-net curve is drawn by the screen itself;\n"
                 "see varselect/cv_curve.png" if png else
                 "no elastic-net screen on disk yet")
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


def capacity_vs_error():
    """Whether letting the model fit more helps or hurts, across every sweep."""
    fig, ax = _fig()
    docs = _json("*/bench-sweep-*.json")
    pts = [(r["full"]["rmse"], r["cv"]["rmse"]) for d in docs for r in d["rows"]]
    if len(pts) < 4:
        _nothing(ax, "not enough sweeps on disk yet")
        fig.tight_layout(); return fig
    x = np.array([p[0] for p in pts]); y = np.array([p[1] for p in pts])
    ax.scatter(x, y, s=12, color=BLUE, alpha=0.5, zorder=3)
    k = np.polyfit(x, y, 1)
    xs = np.linspace(x.min(), x.max(), 20)
    ax.plot(xs, np.polyval(k, xs), color=RED, linewidth=1.4)
    ax.set_xlabel("RMSE in sample, lower means it fitted more")
    ax.set_ylabel("RMSE cross-validated")
    ax.set_title("Fitting more in sample costs held-out error"
                 if k[0] < 0 else "More fitting, better held-out error")
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
    """Every run, by day, as a calendar of the last twelve weeks."""
    fig, ax = _fig(4.2, 2.2)
    days = Counter()
    for p in _records("*/bench-*.json") + _records("*/model-metrics-*.json"):
        days[datetime.fromtimestamp(p.stat().st_mtime).date()] += 1
    if not days:
        _nothing(ax, "no run recorded yet")
        fig.tight_layout(); return fig
    end = max(days)
    weeks = 12
    grid = np.full((7, weeks), np.nan)
    for d, n in days.items():
        delta = (end - d).days
        if 0 <= delta < weeks * 7:
            grid[d.weekday(), weeks - 1 - delta // 7] = n
    ax.imshow(np.nan_to_num(grid), aspect="auto", cmap="Blues",
              vmin=0, vmax=max(days.values()))
    ax.set_yticks(range(7))
    ax.set_yticklabels(["Mon", "", "Wed", "", "Fri", "", "Sun"], fontsize=6.5)
    ax.set_xticks([]); ax.grid(False)
    ax.set_title(f"{sum(days.values())} runs over {len(days)} days, to {end}")
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

    fig, ax = _fig(11.0, 1.9)
    runs = Counter()
    for p in _records("*/bench-*.json") + _records("*/model-metrics-*.json"):
        runs[datetime.fromtimestamp(p.stat().st_mtime).date()] += 1
    marks = ms.load() or ms.seed()
    if not marks:
        _nothing(ax, "no milestones recorded")
        fig.tight_layout(); return fig

    dates = [datetime.strptime(m["date"], "%Y-%m-%d").date() for m in marks]
    lo, hi = min(dates + list(runs) or dates), max(dates + list(runs) or dates)
    span = max((hi - lo).days, 1)

    if runs:
        xs = [(d - lo).days for d in runs]
        ax.bar(xs, [runs[d] for d in runs], color=RULE, width=1.2, zorder=1)
    colour = {"design": PURPLE, "data": BLUE, "workflow": GREEN}
    top = max(runs.values()) if runs else 1
    for m, d in zip(marks, dates):
        x = (d - lo).days
        ax.plot([x, x], [0, top * 1.15], color=colour[m["kind"]], linewidth=1.1,
                zorder=2)
        ax.scatter([x], [top * 1.15], s=16, color=colour[m["kind"]], zorder=3)
    ax.set_ylim(0, top * 1.45)
    ticks = np.linspace(0, span, 7)
    ax.set_xticks(ticks)
    ax.set_xticklabels([str(lo + __import__("datetime").timedelta(days=int(t)))[2:]
                        for t in ticks], fontsize=6.5)
    ax.set_ylabel("runs a day", fontsize=7)
    ax.set_title(f"{sum(runs.values())} runs and {len(marks)} milestones, "
                 f"{lo} to {hi}")
    for kind, col in colour.items():
        ax.plot([], [], color=col, linewidth=2, label=ms.KINDS[kind])
    ax.legend(fontsize=6.5, frameon=False, ncol=3, loc="upper left")
    fig.tight_layout()
    return fig


def indicator_overlay():
    """Price with its trend geometry, for the first symbol in the run.

    What the indicator engines actually see. Drawn from the built panel rather
    than recomputed, so this is the same series the features came from.
    """
    import bench_config as bc
    import pandas as pd

    fig, ax = _fig(4.2, 2.6)
    cfg = bc.load()
    try:
        path = REPO / bc.dataset_path(cfg)
    except ValueError:
        _nothing(ax, "no panel selected"); fig.tight_layout(); return fig
    if not path.exists():
        _nothing(ax, f"{path.name} is not built"); fig.tight_layout(); return fig

    import pyarrow.parquet as pq
    have = set(pq.ParquetFile(str(path)).schema.names)
    want = [c for c in ("symbol", "datetime", "close", "f_st_agree", "f_mst_dir")
            if c in have]
    if "close" not in want:
        _nothing(ax, "this panel carries features but not the raw close,\n"
                     "so the price line cannot be drawn from it")
        fig.tight_layout(); return fig
    df = pd.read_parquet(path, columns=want)
    syms = bc.symbols_for(cfg)
    pick = None
    if syms:
        canon = {bc.canonical(v): v for v in df["symbol"].unique()}
        pick = next((canon[bc.canonical(s)] for s in syms
                     if bc.canonical(s) in canon), None)
    pick = pick or df["symbol"].iloc[-1]
    d = df[df["symbol"] == pick].tail(400)
    ax.plot(d["datetime"], d["close"], color=INK, linewidth=1.0)
    if "f_st_agree" in d.columns:
        up = d[d["f_st_agree"] > 0]
        ax.scatter(up["datetime"], up["close"], s=4, color=GREEN, zorder=3,
                   label="all trends agree, up")
        ax.legend(fontsize=6.5, frameon=False, loc="upper left")
    ax.set_title(f"{pick}, last {len(d)} bars")
    ax.tick_params(axis="x", labelrotation=0, labelsize=6)
    fig.tight_layout()
    return fig


def confluence_agreement():
    """How often the indicator engines agree, across the panel.

    The confluence score counts how many of the methods point the same way at a
    bar. A score that is almost always zero says the engines rarely agree, and a
    threshold of two is then rarely met.
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
    import pyarrow.parquet as pq
    have = [c for c in pq.ParquetFile(str(path)).schema.names
            if c in ("f_st_agree", "f_mst_dir", "f_d1_st_up")]
    if not have:
        _nothing(ax, "this panel carries no agreement column")
        fig.tight_layout(); return fig
    d = pd.read_parquet(path, columns=have)
    thr = float(cfg["signals"].get("confluence_threshold", 2.0))
    vals = d[have[0]].dropna()
    uniq = sorted(vals.unique())[:12]
    counts = [int((vals == u).sum()) for u in uniq]
    cols = [GREEN if u >= thr else RULE for u in uniq]
    ax.bar([str(u) for u in uniq], counts, color=cols, width=0.65)
    ax.set_xlabel(have[0]); ax.set_ylabel("bars")
    ax.set_title(f"Agreement across the panel; {thr:g} is the threshold to fire")
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


def cross_sectional_spread():
    """Top third against bottom third, from the saved cross-sectional records."""
    fig, ax = _fig()
    hits = _records("*/cross-sectional-*.md", 1)
    if not hits:
        _nothing(ax, "no cross-sectional record on disk.\n"
                     "The ranking signal was never disproved; the way of\n"
                     "trading it was killed at 27% of folds against a 60% bar.")
        fig.tight_layout(); return fig
    import re as _re
    nums = []
    for line in hits[0].read_text(errors="replace").splitlines():
        if "|" not in line:
            continue
        found = _re.findall(r"-?\d+\.\d+", line)
        if len(found) >= 2:
            nums.append((line.split("|")[1].strip()[:18], float(found[0])))
    if not nums:
        _nothing(ax, f"{hits[0].name}\ncarries no numeric table")
        fig.tight_layout(); return fig
    nums = sorted(nums, key=lambda t: t[1])[-12:]
    ax.barh([n for n, _v in nums], [v for _n, v in nums],
            color=[GREEN if v > 0 else RED for _n, v in nums], height=0.65)
    ax.axvline(0, color=SOFT, linewidth=0.9)
    ax.set_title(f"From {hits[0].name[:30]}")
    ax.tick_params(axis="y", labelsize=6)
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
    """The two outcome classes as smooth densities over the predicted range.

    Where a histogram of ten bins says the model is miscalibrated in the top
    bin, this says how far apart the classes sit across the whole range, and it
    does so without bin edges. A model with nothing to say puts both curves on
    top of each other around the base rate.
    """
    import bench_run as br
    import bench_config as bc
    import kde_metrics as km
    import train_model_1h as t1

    fig, ax = _fig(4.2, 2.8)
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
    sep = km.class_separation(y, p)
    lo, hi = float(np.percentile(p, 0.5)), float(np.percentile(p, 99.5))
    ax.set_xlim(max(0, lo - 0.05), min(1, hi + 0.05))
    ax.set_xlabel("predicted probability")
    ax.set_ylabel("density")
    ax.set_title(f"Classes overlap by {sep['overlap']:.3f}; one is indistinguishable")
    ax.legend(fontsize=6.5, frameon=False)
    fig.tight_layout()
    return fig


def kde_spread():
    """How much of the nought-to-one range the model actually uses.

    Every accuracy measure here can be satisfied by a model that never departs
    from the base rate, and several nearly are. This says so directly.
    """
    import kde_metrics as km

    fig, ax = _fig(4.2, 2.4)
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
    sp = km.spread_of_predictions(p, base)
    ax.axvline(base, color=NAVY, linestyle="--", linewidth=1)
    lo, hi = float(np.percentile(p, 0.5)), float(np.percentile(p, 99.5))
    ax.set_xlim(max(0, lo - 0.06), min(1, hi + 0.06))
    ax.set_xlabel("predicted probability")
    ax.set_title(f"{sp['mass_near_base'] * 100:.0f}% of the mass within 0.05 of "
                 f"the base rate")
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
    ax.legend(fontsize=6.5, frameon=False)
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


def regime_demo(scheme: str | None = None, rows: int = 240):
    """Every resampling regime side by side, on the same rows.

    The picture the R package `caret` draws for its own resampling schemes, with
    one difference that matters here: the rows are in time order left to right,
    so a regime that puts a later row in training and an earlier one in test
    shows it as blue to the right of orange. That is the leak, drawn.
    """
    import bench_config as bc
    import bench_run as br

    schemes = [scheme] if scheme else [
        "expanding", "rolling", "kfold", "repeated-kfold",
        "monte-carlo", "bootstrap", "leave-one-out"]
    cfg = bc.load()
    k = int(cfg["split"]["folds"])

    fig, axes = plt.subplots(len(schemes), 1, figsize=(6.2, 1.0 * len(schemes) + 0.7),
                             dpi=110, sharex=True)
    if len(schemes) == 1:
        axes = [axes]
    for ax, sch in zip(axes, schemes):
        try:
            folds = br.folds_of(rows, k, sch, repeats=3, boot=6)[:8]
        except ValueError:
            folds = []
        for j, (tr, te) in enumerate(folds):
            grid = np.zeros(rows)
            grid[np.clip(tr, 0, rows - 1)] = 1
            grid[np.clip(te, 0, rows - 1)] = 2
            for val, col in ((1, BLUE), (2, ORANGE)):
                xs = np.where(grid == val)[0]
                if len(xs):
                    ax.scatter(xs, np.full(len(xs), j), s=1.6, color=col, marker="s")
        ax.set_ylabel(sch, rotation=0, ha="right", va="center", fontsize=7,
                      color=INK)
        ax.set_yticks([]); ax.set_ylim(-0.8, max(len(folds), 1) - 0.2)
        ax.grid(False)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        # Time runs left to right, so any orange left of blue is a fold scored on
        # a row that sits before rows the model trained on.
        leaks = any(len(te) and len(tr) and te.min() < tr.max() for tr, te in folds)
        ax.text(rows * 1.005, max(len(folds), 1) / 2 - 0.5,
                "keeps time in order" if not leaks else "ignores time",
                fontsize=6.5, va="center",
                color=GREEN if not leaks else RED)
    axes[-1].set_xlabel("row, in time order")
    axes[0].set_title("Which rows train, and which are scored, in each regime",
                      fontsize=9, color=INK, fontweight="bold")
    axes[0].plot([], [], "s", color=BLUE, markersize=4, label="trained on")
    axes[0].plot([], [], "s", color=ORANGE, markersize=4, label="scored on")
    axes[0].legend(fontsize=6.5, frameon=False, ncol=2, loc="upper left",
                   bbox_to_anchor=(0, 1.9))
    fig.tight_layout()
    return fig


def regime_uncertainty():
    """How the spread of the estimate changes as the folds move forward in time.

    Operator instruction, 9 September 2026: the demonstrations show temporal
    change in uncertainty rather than a static picture of the folds. Each fold
    is scored on a different stretch of market, so the fold-to-fold spread is
    the honest width of the estimate, and it moves.
    """
    fig, ax = _fig(4.6, 2.8)
    docs = _json("*/bench-sweep-*.json", 40)
    series = []
    for d in docs:
        stamp = str(d.get("stamped", ""))[:10]
        vals = [r["cv"]["rmse"] for r in d.get("rows", []) if isinstance(r.get("cv"), dict)]
        if len(vals) > 2:
            series.append((stamp, float(np.mean(vals)), float(np.std(vals, ddof=1)),
                           int(d.get("config", {}).get("split", {}).get("folds") or 0)))
    if len(series) < 3:
        _nothing(ax, "not enough sweeps to show how the spread moves")
        fig.tight_layout(); return fig
    series.sort()
    x = np.arange(len(series))
    mean = np.array([s[1] for s in series])
    sd = np.array([s[2] for s in series])
    ax.fill_between(x, mean - sd, mean + sd, color=BLUE, alpha=0.20,
                    label="spread across configurations")
    ax.plot(x, mean, color=NAVY, linewidth=1.4, label="mean held-out error")
    ax.set_xticks(np.linspace(0, len(series) - 1, min(6, len(series))).astype(int))
    ax.set_xticklabels([series[i][0][5:] for i in
                        np.linspace(0, len(series) - 1, min(6, len(series))).astype(int)],
                       fontsize=6.5)
    ax.set_ylabel("held-out RMSE")
    ax.set_title(f"Uncertainty across {len(series)} sweeps, and how it moves")
    ax.legend(fontsize=6.5, frameon=False)
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
    "A1": ("coverage", "panel", "acquire", "vision", "archive"),
    "A2": ("timeline", "profile", "breadth", "survivor", "span"),
    "A3": ("screen", "candidate", "cross-sectional", "rank", "market"),
    "B1": ("feature", "importance", "family"),
    "B2": ("macd", "confluence", "fib", "supertrend", "signal", "journal",
           "indicator", "candle", "entry", "exit"),
    "B3": ("varselect", "coef", "enet", "univariate", "cv_curve", "path"),
    "C1": ("split", "fold", "walkforward", "walk-forward", "training-test"),
    "C2": ("calibration", "reliability", "roc", "eval-head", "compare",
           "selectivity", "regime"),
    "C3": ("tuning", "sweep", "importance", "model-"),
    "D1": ("assessment", "metrics", "scoreboard"),
    "D2": ("equity", "scoreboard", "monte", "carlo"),
    "D3": ("daily", "book", "portfolio", "equity", "history"),
}


def figures(panel: str | None = None, limit: int | None = None) -> list[dict]:
    """Every figure the workflow has produced, newest first.

    `panel` narrows to the ones whose file name matches that panel's subjects.
    Nothing is drawn: these are files already on disk.
    """
    want = PANEL_FIGURES.get(panel or "", ()) if panel else ()
    seen, out = set(), []
    for rel in FIGURE_DIRS:
        root = REPO / rel
        if not root.is_dir():
            continue
        for f in root.rglob("*.png"):
            if f.name.startswith("._") or f.resolve() in seen:
                continue
            seen.add(f.resolve())
            low = f.name.lower()
            if want and not any(w in low for w in want):
                continue
            out.append(dict(rel=str(f.relative_to(REPO)), name=f.name,
                            folder=rel.split("/")[-1],
                            when=datetime.fromtimestamp(f.stat().st_mtime),
                            kb=f.stat().st_size // 1024))
    out.sort(key=lambda d: d["when"], reverse=True)
    return out[:limit] if limit else out


def figure_folders() -> list[tuple[str, int]]:
    counts = Counter(f["folder"] for f in figures())
    return sorted(counts.items(), key=lambda t: -t[1])


# ---------------------------------------------------------------------------

CHARTS = {
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
    "cross-sectional-spread": (cross_sectional_spread, "Top third against the market"),
    "indicator-overlay": (indicator_overlay, "Price with its trend geometry"),
    "confluence-agreement": (confluence_agreement, "How often the engines agree"),
    "coefficient-intervals": (coefficient_intervals, "Each predictor with its interval"),
    "fold-coverage": (fold_coverage, "What each fold trains and scores on"),
    "regime-demo": (regime_demo, "Every resampling regime on the same rows"),
    "regime-uncertainty": (regime_uncertainty, "How the spread of the estimate moves"),
    "timeline": (timeline, "Every run, with the milestones marked"),
}


def draw(name: str):
    """One chart as PNG bytes, or None if the name is not known."""
    import io
    entry = CHARTS.get(name)
    if entry is None:
        return None
    try:
        fig = entry[0]()
    except Exception as exc:                            # noqa: BLE001
        # A chart that raises must not take the page down with it. The panel
        # gets a box saying which chart failed and why, which is more use than
        # a broken image icon.
        fig, ax = _fig()
        _nothing(ax, f"{name} could not be drawn:\n{type(exc).__name__}: {exc}")
        fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buf.getvalue()
