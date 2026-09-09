"""The interactive figure at the foot of every panel.

Operator instruction, 9 September 2026: an interactive visualisation in the last
row at the bottom of the page. Every other drawing on this page is a PNG, which
is right for a strip you glance at and wrong for the one figure you actually
interrogate: a static chart cannot be zoomed into, a series cannot be switched
off, and a point cannot be asked what it is.

One plotly figure per panel, emitted as a self-contained HTML fragment. Plotly's
own library is written once into 03-inputs/control_static/plotly.min.js and
referenced, rather than repeated in every fragment: at about 3.5 MB a copy,
nine panels would add thirty megabytes to a page for one library.

The same two rules as the PNG charts. Nothing here fits a model or reads a whole
panel, because a page that refits on every load is a page nobody can leave open.
And a figure with nothing to draw says what is missing rather than rendering an
empty set of axes.
"""

from __future__ import annotations

import glob
import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "04-outputs" / "AA-evals"
STATIC = REPO / "03-inputs" / "control_static"

INK, SOFT, RULE = "#16202c", "#4a5866", "#c3cedb"
BLUE, PURPLE, GREEN, ORANGE, NAVY, RED = (
    "#0d5f8a", "#6b3fa0", "#0e7a5f", "#a8560c", "#1c4f8f", "#a01c1c")

LAYOUT = dict(
    template="simple_white",
    margin=dict(l=48, r=16, t=34, b=38),
    height=330,
    font=dict(family="Helvetica Neue, Helvetica, Arial, sans-serif",
              size=11, color=INK),
    title=dict(font=dict(size=13)),
    hoverlabel=dict(font=dict(size=11)),
    legend=dict(orientation="h", y=-0.18, font=dict(size=10)),
)


def ensure_library() -> bool:
    """Write plotly's own script beside the stylesheet, once.

    Referenced by every fragment rather than embedded in each. Nine copies of a
    3.5 MB library is thirty megabytes of page for one library, which is the
    difference between a page that opens and one that does not.
    """
    dest = STATIC / "plotly.min.js"
    if dest.exists() and dest.stat().st_size > 1_000_000:
        return True
    try:
        from plotly.offline import get_plotlyjs
    except ImportError:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(get_plotlyjs(), encoding="utf-8")
    return True


def _docs(pattern: str, limit: int | None = None) -> list[dict]:
    out = []
    paths = sorted(glob.glob(str(EVALS / pattern)), reverse=True)
    for p in paths[:limit] if limit else paths:
        if os.path.basename(p).startswith("._"):
            continue
        try:
            d = json.loads(Path(p).read_text(encoding="utf-8"))
            d["_file"] = os.path.basename(p)
            out.append(d)
        except (json.JSONDecodeError, OSError):
            continue
    return out


def _wrap(fig, title: str, note: str) -> str:
    """One figure as a fragment, with what it is and how to use it."""
    from plotly.io import to_html

    fig.update_layout(**LAYOUT, title_text=title)
    body = to_html(fig, include_plotlyjs=False, full_html=False,
                   config=dict(displaylogo=False, responsive=True,
                               modeBarButtonsToRemove=["select2d", "lasso2d"]))
    return (f'<div class="interactive"><div class="inote">{note}</div>{body}</div>')


def _missing(why: str) -> str:
    return f'<div class="interactive"><div class="inote">{why}</div></div>'


# ---------------------------------------------------------------------------
# One figure per panel
# ---------------------------------------------------------------------------

def _scatter_fits(hover_extra=None):
    """Every configuration fit on disk as one interactive scatter.

    Shared by the panels that ask a question about the whole body of runs. The
    hover is the point of it: 456 fits on a static chart is a cloud, and the
    only useful thing to do with a cloud is ask a point what it was.
    """
    import plotly.graph_objects as go

    xs, ys, txt, col = [], [], [], []
    for d in _docs("*/bench-sweep-*.json"):
        cfg = d.get("config", {})
        lab = (f"{len(str(cfg.get('data', {}).get('symbols', '')).split()) or 'all'} sym, "
               f"{cfg.get('split', {}).get('folds')} folds, "
               f"{cfg.get('split', {}).get('holdout_days')}d blind, "
               f"weight {cfg.get('model', {}).get('class_weight')}")
        for r in d.get("rows", []):
            if not isinstance(r.get("cv"), dict) or not isinstance(r.get("full"), dict):
                continue
            u2 = (r.get("blind") or {}).get("theil_u2")
            xs.append(r["full"]["rmse"])
            ys.append(r["cv"]["rmse"])
            col.append(RED if r["rejected"] else (GREEN if (u2 or 9) < 1 else BLUE))
            txt.append(f"<b>{r.get('name', r.get('model', ''))}</b><br>{lab}<br>"
                       f"ratio {r['rmse_ratio']:.3f}<br>"
                       f"blind U2 {u2 if u2 is None else round(u2, 4)}<br>"
                       f"{d['_file']}")
    if not xs:
        return None
    fig = go.Figure(go.Scattergl(
        x=xs, y=ys, mode="markers",
        marker=dict(size=6, color=col, opacity=0.75,
                    line=dict(width=0)),
        text=txt, hovertemplate="%{text}<extra></extra>", name="fits"))
    lo = min(min(xs), min(ys)) * 0.97
    hi = max(max(xs), max(ys)) * 1.03
    fig.add_shape(type="line", x0=lo, y0=lo, x1=hi, y1=hi,
                  line=dict(color=SOFT, dash="dot", width=1))
    fig.add_shape(type="line", x0=lo, y0=lo * 1.1, x1=hi, y1=hi * 1.1,
                  line=dict(color=NAVY, dash="dash", width=1))
    fig.update_xaxes(title="RMSE in sample")
    fig.update_yaxes(title="RMSE cross-validated")
    return fig


def data_explorer() -> str:
    """A1: how much of each panel is usable, over time, by symbol."""
    import plotly.graph_objects as go
    import pandas as pd

    import bench_config as bc

    cfg = bc.load()
    try:
        path = REPO / bc.dataset_path(cfg)
    except ValueError:
        return _missing("The chosen bar size does not belong to the chosen market.")
    if not path.exists():
        return _missing(f"{path.name} is not built.")

    df = pd.read_parquet(path, columns=["symbol", "datetime", "label", "in_sample"])
    df["month"] = df["datetime"].dt.to_period("M").dt.to_timestamp()
    grp = df.groupby(["month", "symbol"]).agg(rows=("label", "size"),
                                              base=("label", "mean")).reset_index()
    top = (grp.groupby("symbol")["rows"].sum().sort_values(ascending=False)
           .head(12).index.tolist())
    fig = go.Figure()
    for i, sym in enumerate(top):
        d = grp[grp["symbol"] == sym]
        fig.add_trace(go.Scatter(
            x=d["month"], y=d["rows"], name=sym, mode="lines",
            line=dict(width=1.4),
            hovertemplate=(f"<b>{sym}</b><br>%{{x|%b %Y}}<br>%{{y}} bars<br>"
                           "base rate %{customdata:.3f}<extra></extra>"),
            customdata=d["base"]))
    fig.update_xaxes(title="month", rangeslider=dict(visible=True))
    fig.update_yaxes(title="bars in the panel")
    return _wrap(fig, "Coverage by month and symbol",
                 "The twelve symbols with most history in the panel this run is "
                 "pointed at. Drag the slider to a period; click a name in the key "
                 "to hide it; hover a point for that month's base rate. A symbol "
                 "whose line starts late was not listed, and one that stops was "
                 "delisted, which is what survivorship bias looks like when the "
                 "archive is complete.")


def feature_explorer() -> str:
    """A2: every feature, its own AUC against its stability, hoverable."""
    import csv

    import plotly.graph_objects as go

    hits = sorted(glob.glob(str(EVALS / "*/feature-report-*.csv")), reverse=True)
    hits = [h for h in hits if not os.path.basename(h).startswith("._")]
    if not hits:
        return _missing("No feature report on disk. Run it from the panel above.")
    with open(hits[0], newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        return _missing(f"{os.path.basename(hits[0])} is empty.")

    def num(r, *names, default=None):
        for n in names:
            if n in r and r[n] not in ("", None):
                try:
                    return float(r[n])
                except ValueError:
                    continue
        return default

    name_k = next((k for k in rows[0] if "feat" in k.lower() or k.lower() == "name"), None)
    if name_k is None:
        return _missing(f"{os.path.basename(hits[0])} has no feature-name column.")

    xs, ys, sz, txt, col = [], [], [], [], []
    fam_colour = {}
    palette = [BLUE, GREEN, ORANGE, PURPLE, NAVY, RED, "#3f8fbf", "#4fae8b"]
    for r in rows:
        auc = num(r, "auc", "univariate_auc", "AUC")
        stab = num(r, "stability", "sign_stability", "steady", default=0.0)
        imp = num(r, "permutation", "perm_importance", "importance", default=0.0)
        if auc is None:
            continue
        fam = "_".join(r[name_k].split("_")[:2]) + "_"
        fam_colour.setdefault(fam, palette[len(fam_colour) % len(palette)])
        xs.append(auc); ys.append(stab)
        sz.append(6 + 60 * max(imp, 0) / (max(abs(imp), 1e-9) if imp else 1))
        col.append(fam_colour[fam])
        txt.append(f"<b>{r[name_k]}</b><br>family {fam}<br>AUC {auc:.4f}<br>"
                   f"stability {stab:.2f}<br>importance {imp:.5f}")
    if not xs:
        return _missing("The feature report has no AUC column to plot.")
    fig = go.Figure(go.Scatter(
        x=xs, y=ys, mode="markers",
        marker=dict(size=[min(s, 26) for s in sz], color=col, opacity=0.8,
                    line=dict(width=0)),
        text=txt, hovertemplate="%{text}<extra></extra>"))
    fig.add_vline(x=0.5, line=dict(color=RED, width=1, dash="dash"))
    fig.update_xaxes(title="area under the curve, alone (0.5 is a coin flip)")
    fig.update_yaxes(title="share of folds pointing the same way")
    return _wrap(fig, f"{len(xs)} features: how good alone, and how steady",
                 "Every offered column. Left of the red line a feature is worse "
                 "than a coin flip on its own; low on the axis it changed sign "
                 "between folds, which is a regime rather than a feature. Colour "
                 "is the family, size is permutation importance. Hover any point "
                 "for its name and numbers; box-select to zoom.")


def selection_explorer() -> str:
    """A3: the univariate screen, every predictor with its interval."""
    import plotly.graph_objects as go

    hits = sorted(glob.glob(str(EVALS / "varselect/univariate-*.json")), reverse=True)
    hits = [h for h in hits if not os.path.basename(h).startswith("._")]
    if not hits:
        return _missing("No univariate screen on disk. Run it from the panel above.")
    doc = json.loads(Path(hits[0]).read_text(encoding="utf-8"))
    rows = sorted(doc["rows"], key=lambda r: r["coef"])
    names = [r["feature"] for r in rows]
    est = [r["coef"] for r in rows]
    lo = [r["coef"] - r["lo"] for r in rows]
    hi = [r["hi"] - r["coef"] for r in rows]
    col = [GREEN if r["lr"] > 6.63 else ORANGE if r["lr"] > 3.84 else RULE
           for r in rows]
    txt = [f"<b>{r['feature']}</b><br>estimate {r['coef']:+.4f}<br>"
           f"95% interval {r['lo']:+.4f} to {r['hi']:+.4f}<br>"
           f"likelihood ratio {r['lr']:.2f}<br>"
           f"p {'< 0.001' if r['p'] < 0.001 else format(r['p'], '.3f')}<br>"
           f"{r['n']:,} rows" for r in rows]
    fig = go.Figure(go.Scatter(
        x=est, y=names, mode="markers",
        error_x=dict(type="data", symmetric=False, array=hi, arrayminus=lo,
                     color=NAVY, thickness=1.2, width=0),
        marker=dict(size=7, color=col, line=dict(width=0)),
        text=txt, hovertemplate="%{text}<extra></extra>"))
    fig.add_vline(x=0, line=dict(color=SOFT, width=1, dash="dash"))
    fig.update_layout(height=max(330, 16 * len(names)))
    fig.update_xaxes(title="log-odds, with its 95 per cent interval")
    return _wrap(fig, f"{doc['cleared_05']} of {len(rows)} cleared the five per cent point",
                 f"Each predictor fitted alone against an intercept-only model. "
                 f"Green cleared one per cent, amber five, grey neither. "
                 f"{doc['expected_by_chance']:.0f} would clear five per cent from "
                 f"noise alone at this many tests, so read the ranking rather than "
                 f"any single p-value. An interval crossing zero is a predictor "
                 f"whose direction the data does not settle.")


def regime_explorer() -> str:
    """B1: which rows train and which are scored, regime by regime, zoomable."""
    import plotly.graph_objects as go

    import bench_config as bc
    import bench_run as br

    cfg = bc.load()
    k = int(cfg["split"]["folds"])
    rows = 300
    schemes = ["expanding", "rolling", "kfold", "repeated-kfold",
               "monte-carlo", "bootstrap", "leave-one-out"]
    fig = go.Figure()
    y = 0
    ticks, labels = [], []
    for sch in schemes:
        try:
            folds = br.folds_of(rows, k, sch, repeats=3, boot=6)[:6]
        except ValueError:
            continue
        if not folds:
            continue
        ticks.append(y + len(folds) / 2)
        leaks = any(len(te) and len(tr) and te.min() < tr.max() for tr, te in folds)
        labels.append(f"{sch} {'✓' if not leaks else '✗'}")
        for tr, te in folds:
            for xs, col, what in ((tr, BLUE, "trained on"), (te, ORANGE, "scored on")):
                u = sorted(set(int(v) for v in xs))
                fig.add_trace(go.Scattergl(
                    x=u, y=[y] * len(u), mode="markers",
                    marker=dict(size=3, color=col, symbol="square"),
                    hovertemplate=f"{sch}<br>row %{{x}}<br>{what}<extra></extra>",
                    showlegend=False))
            y += 1
        y += 0.6
    if not ticks:
        return _missing("No resampling regime produced a fold at this setting.")
    fig.update_yaxes(tickvals=ticks, ticktext=labels, autorange="reversed")
    fig.update_xaxes(title="row, in time order")
    fig.update_layout(height=430)
    return _wrap(fig, "Which rows train and which are scored, in each regime",
                 "Rows run left to right in time. A tick means the regime keeps "
                 "time in order; a cross means it does not, and orange sitting "
                 "left of blue is a fold scored on a row that comes before rows "
                 "the model trained on. Returns are autocorrelated, so that is a "
                 "leak. Zoom into any stretch to see it row by row.")


def performance_explorer() -> str:
    """B2: the reliability curve for every mapping, over the predicted range."""
    import csv

    import plotly.graph_objects as go

    hits = sorted(glob.glob(str(EVALS / "*/calibration-*.csv")), reverse=True)
    hits = [h for h in hits if not os.path.basename(h).startswith("._")]
    if not hits:
        return _missing("No calibration record on disk.")
    with open(hits[0], newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    series: dict[str, list] = {}
    for r in rows:
        m = r.get("mapping") or r.get("map") or "raw"
        try:
            series.setdefault(m, []).append((
                float(r.get("mean_predicted") or r.get("predicted")),
                float(r.get("observed") or r.get("observed_frequency")),
                int(float(r.get("n") or r.get("count") or 0))))
        except (TypeError, ValueError):
            continue
    if not series:
        return _missing(f"{os.path.basename(hits[0])} has no reliability columns.")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="perfect",
                             line=dict(color=SOFT, dash="dot", width=1)))
    for (name, pts), col in zip(sorted(series.items()),
                                [BLUE, GREEN, ORANGE, PURPLE]):
        pts.sort()
        fig.add_trace(go.Scatter(
            x=[p[0] for p in pts], y=[p[1] for p in pts], mode="lines+markers",
            name=name, line=dict(color=col, width=1.8),
            marker=dict(size=[max(5, min(22, (p[2] or 1) ** 0.4)) for p in pts]),
            customdata=[p[2] for p in pts],
            hovertemplate=(f"<b>{name}</b><br>stated %{{x:.3f}}<br>"
                           "happened %{y:.3f}<br>%{customdata:,} rows"
                           "<extra></extra>")))
    fig.update_xaxes(title="stated probability")
    fig.update_yaxes(title="observed frequency")
    return _wrap(fig, "Does a stated probability mean what it says",
                 "A calibrated line sits on the diagonal. The marker is sized by "
                 "how many rows fell in that band, which matters: the largest gaps "
                 "reported in this repository came from bands holding a few dozen "
                 "rows. Hover any point for its count.")


def tuning_explorer() -> str:
    """B3: every configuration fit, in sample against held out."""
    fig = _scatter_fits()
    if fig is None:
        return _missing("No sweep on disk yet.")
    return _wrap(fig, "Every configuration fit on disk",
                 "Each point is one model at one configuration. The dotted line "
                 "is equal error in and out of sample; the dashed line is the 1.1 "
                 "overfit bar, and anything above it is rejected however low its "
                 "error. Red failed that bar, green beat a constant forecast on "
                 "the blind period, blue did neither. Hover for the settings "
                 "behind a point; box-select to zoom.")


def assessment_explorer() -> str:
    """C1: how the best result moved, run by run."""
    import plotly.graph_objects as go

    pts = []
    for d in _docs("*/bench-sweep-*.json") + _docs("*/bench-2*.json"):
        when = str(d.get("stamped", ""))[:19].replace("T", " ")
        rows = d.get("rows") or d.get("scores") or []
        for r in rows:
            b = r.get("blind") or {}
            if b.get("theil_u2") is None or r.get("rejected"):
                continue
            pts.append((when, b["theil_u2"], r.get("name", r.get("model", "")),
                        d["_file"]))
    if len(pts) < 3:
        return _missing("Not enough scored runs yet.")
    pts.sort()
    best, running = float("inf"), []
    for _w, v, _n, _f in pts:
        best = min(best, v)
        running.append(best)
    fig = go.Figure()
    fig.add_trace(go.Scattergl(
        x=[p[0] for p in pts], y=[p[1] for p in pts], mode="markers",
        marker=dict(size=5, color=RULE), name="each fit",
        text=[f"<b>{p[2]}</b><br>{p[3]}<br>blind U2 {p[1]:.4f}" for p in pts],
        hovertemplate="%{text}<extra></extra>"))
    fig.add_trace(go.Scatter(x=[p[0] for p in pts], y=running, mode="lines",
                             line=dict(color=NAVY, width=2), name="best so far"))
    fig.add_hline(y=1.0, line=dict(color=RED, width=1.4),
                  annotation_text="a constant forecast", annotation_position="top left")
    fig.update_yaxes(title="blind Theil U2, lower is better")
    return _wrap(fig, f"{len(pts)} passing fits, and the best available at each moment",
                 "The line only ever falls: it is the best result available on "
                 "that day. Where it is flat, nothing tried in that stretch "
                 "improved on what was already there. Below the red line beats "
                 "always predicting the base rate.")


def scoreboard_explorer() -> str:
    """C2: the distribution of every fit against a constant forecast."""
    import plotly.graph_objects as go

    vals, txt = [], []
    for d in _docs("*/bench-sweep-*.json"):
        cfg = d.get("config", {})
        lab = (f"{cfg.get('split', {}).get('folds')} folds, "
               f"weight {cfg.get('model', {}).get('class_weight')}")
        for r in d.get("rows", []):
            u2 = (r.get("blind") or {}).get("theil_u2")
            if u2 is None:
                continue
            vals.append(u2)
            txt.append(f"{r.get('name','')} · {lab}")
    if not vals:
        return _missing("No scored fit on disk yet.")
    fig = go.Figure(go.Histogram(x=vals, nbinsx=60, marker_color=BLUE,
                                 hovertemplate="U2 %{x:.3f}<br>%{y} fits<extra></extra>"))
    fig.add_vline(x=1.0, line=dict(color=RED, width=2),
                  annotation_text="a constant forecast")
    beat = sum(1 for v in vals if v < 1.0)
    fig.update_xaxes(title="Theil's U2 on the blind period")
    fig.update_yaxes(title="fits")
    return _wrap(fig, f"{beat} of {len(vals)} fits beat always predicting the base rate",
                 "Everything ever scored, in one distribution. Left of the red "
                 "line a model did better than a constant forecast of the base "
                 "rate; right of it, worse. Drag across a stretch to zoom into "
                 "the tail.")


def livebook_explorer() -> str:
    """C3: the whole history, runs and milestones together."""
    import plotly.graph_objects as go

    import milestones as ms

    runs = Counter()
    for p in sorted(glob.glob(str(EVALS / "*/bench-*.json"))):
        if os.path.basename(p).startswith("._"):
            continue
        runs[datetime.fromtimestamp(os.path.getmtime(p)).date()] += 1
    marks = ms.load() or ms.seed()
    if not runs and not marks:
        return _missing("Nothing recorded yet.")
    fig = go.Figure()
    if runs:
        days = sorted(runs)
        fig.add_trace(go.Bar(x=days, y=[runs[d] for d in days],
                             marker_color=RULE, name="runs",
                             hovertemplate="%{x|%d %b %Y}<br>%{y} runs<extra></extra>"))
    colour = {"design": PURPLE, "data": BLUE, "workflow": GREEN}
    top = max(runs.values()) if runs else 1
    for kind, col in colour.items():
        got = [m for m in marks if m["kind"] == kind]
        if not got:
            continue
        fig.add_trace(go.Scatter(
            x=[datetime.strptime(m["date"], "%Y-%m-%d") for m in got],
            y=[top * 1.15] * len(got), mode="markers",
            marker=dict(size=11, color=col, symbol="diamond"),
            name=ms.KINDS[kind],
            text=[f"<b>{ms.KINDS[m['kind']]}</b> · {m['date']}<br>"
                  f"{m['what']}<br><i>{m['where']}</i>" for m in got],
            hovertemplate="%{text}<extra></extra>"))
    fig.update_xaxes(title="", rangeslider=dict(visible=True))
    fig.update_yaxes(title="runs a day")
    return _wrap(fig, f"{sum(runs.values())} runs and {len(marks)} milestones",
                 "The grey bars are runs and the diamonds are milestones: the few "
                 "points where the model design, the input data or the workflow "
                 "changed. Hover a diamond to read what changed and which file "
                 "shows it. Drag the slider to a period.")


# Keyed by panel for a panel's closing figure and by section name for a figure
# inside a merged panel. Nine panels became six on 9 September 2026 and the keys
# moved with them: what was A3 is B1, what was B1 is B2, and the five figures of
# the old B2, B3, C1, C2 and C3 now sit inside the two merged panels under the
# name of the section they belong to. Nothing was dropped in the move, which is
# the point: a merged panel keeps the interactive figure of every panel it
# absorbed and adds one of its own.
FIGURES = {
    "A1": data_explorer,
    "A2": feature_explorer,
    "B1": selection_explorer,
    "B2": regime_explorer,
    # The two closing figures of the merged panels. They live in
    # control_merged.py because each one exists only because the merge happened,
    # and a panel whose closing figure is one it inherited has not earned the
    # merge. Imported inside the lambda-free helpers below rather than at module
    # level: control_merged reads this module's colours and wrapper, so a
    # module-level import in this direction closes the circle.
    "C1": lambda: _merged().model_explorer(),
    "C2": lambda: _merged().history_explorer(),
    # Inside C1 Model and scoreboard.
    "performance": performance_explorer,
    "tuning": tuning_explorer,
    "scoreboard": scoreboard_explorer,
    # Inside C2 History.
    "assessment": assessment_explorer,
    "livebook": livebook_explorer,
}


def _merged():
    import control_merged
    return control_merged


def build(panel: str) -> str | None:
    """The interactive figure for one panel, or one section of a merged panel."""
    fn = FIGURES.get(panel)
    if fn is None:
        return None
    if not ensure_library():
        return _missing("plotly is not installed in this environment.")
    try:
        return fn()
    except Exception as exc:                            # noqa: BLE001
        # A figure that raises must not take the panel down with it. The reader
        # gets the failure named, which is more use than a blank space.
        return _missing(f"This figure could not be built: "
                        f"{type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# Variable selection carries three figures rather than one. Operator
# instruction, 9 September 2026: the univariate ranking already here, the
# elastic-net coefficient path, which variable_selection has drawn since it was
# written and nothing had ever displayed, and a multivariate fit that redoes
# itself as columns are ticked. They answer one question three ways, so they
# belong on one panel: what each predictor is worth alone, the order in which
# predictors survive a penalty, and what their estimates become once several are
# in together. Built in control_varselect so this module keeps one figure per
# panel; appended rather than edited into FIGURES above so the two can be read
# separately.
#
# Keyed by the panel's title rather than by its letter. The panel was A3 when
# this was written and became B1 the same afternoon when the lanes were merged,
# and a hard-coded letter would have left the three figures registered against a
# panel that no longer exists, silently, since a key nothing looks up raises
# nothing.
# ---------------------------------------------------------------------------

def selection_panel() -> str:
    import control_varselect as cvs

    return selection_explorer() + cvs.fragment()


def _selection_key(default: str = "B1") -> str:
    try:
        import control_registry as reg

        for card in reg.CARDS:
            if card.title.strip().lower() == "variable selection":
                return card.key
    except Exception:                                   # noqa: BLE001
        pass
    return default


FIGURES[_selection_key()] = selection_panel
