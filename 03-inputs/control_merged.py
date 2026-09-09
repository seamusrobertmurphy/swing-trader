"""The two interactive figures that only exist because panels merged.

Operator instruction, 9 September 2026. Nine panels became six, and two of the
six are merges:

    C1 Model and scoreboard   = Performance + Tuning + Scoreboard
    C2 History                = Assessment + Live book

Each merged panel keeps the interactive figure of every panel it absorbed, one
per section, and closes with one more that none of them could have drawn. That
last figure is the point of this module. A merged panel whose closing figure is
one it inherited has not earned the merge: it is the old panel with three
neighbours stacked underneath.

What each of the two adds over what it inherited.

C1 model_explorer. The scoreboard table sorts 456 fits by one column at a time,
which is the only way to interrogate a table and a poor way to compare two
measures. This puts every fit on two axes at once, lets the reader change the
vertical measure between held-out error, Theil's U2 on the blind period, the
area under the curve and the overfit ratio, draws the bar that measure is judged
against, and marks the newest run's own fits as a separate layer. That last
layer is the merge: Performance is one configuration computed now and the
Scoreboard is every configuration ever fitted, and the only figure that keeps
both distinct while showing them together is one that draws the current run
inside the population rather than beside it.

C2 history_explorer. Assessment compares runs across configurations and over
time; the Live book is the history of the project. Both read the same records
and neither drew the two together. This puts every scored fit on a date axis
with its configuration on hover, the best result available on each day as a
line, the milestones as marks above it and the volume of records written as the
background, so a change in the approach and a change in the error can be read
against each other. Neither inherited figure can do that: one has no dates on
its configuration axis, the other has no error on its date axis.

The same two rules as every other drawing on this page. Nothing here fits a
model or opens a panel of market data, because a page that refits on every load
is a page nobody can leave open on an eight-gigabyte machine already deep in
swap. And a figure with nothing to draw says what is missing rather than
rendering empty axes.
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

# The bar each measure is judged against, and which direction is better. Held
# here rather than written into the figure so the button that switches the
# vertical axis switches the reference line with it. A dropdown that changes the
# measure and leaves the 1.1 overfit line where it was would draw the forest's
# blind AUC against the overfit bar, which is a picture of nothing.
MEASURES = {
    "RMSE cross-validated": dict(key=("cv", "rmse"), bar=None,
                                 note="held-out error, lower is better"),
    "Theil U2 on the blind period": dict(key=("blind", "theil_u2"), bar=1.0,
                                         note="below one beats always predicting "
                                              "the base rate"),
    "Area under the curve, blind": dict(key=("blind_auc",), bar=0.5,
                                        note="0.5 is a coin flip"),
    "Overfit ratio": dict(key=("rmse_ratio",), bar=1.1,
                          note="above 1.1 is rejected whatever its error"),
}


def _docs(pattern: str) -> list[dict]:
    """Every JSON record matching a glob, newest name first.

    The "._" guard is not decoration. The repository lives on an exFAT volume,
    which cannot store extended attributes, so macOS drops a companion file
    beside every file it writes; read as JSON each one raises, and without this
    the figure would be built from a list half of whose entries are junk.
    """
    out = []
    for p in sorted(glob.glob(str(EVALS / pattern)), reverse=True):
        if os.path.basename(p).startswith("._"):
            continue
        try:
            d = json.loads(Path(p).read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        d["_file"] = os.path.basename(p)
        out.append(d)
    return out


def _cfg_label(cfg: dict) -> str:
    """The configuration in one line, for a hover box."""
    data = cfg.get("data") or {}
    split = cfg.get("split") or {}
    model = cfg.get("model") or {}
    fams = (cfg.get("features") or {}).get("families") or []
    syms = len(str(data.get("symbols") or "").split()) or "all"
    return (f"{syms} sym · {len(fams) or 'all'} fam · "
            f"{split.get('folds')} folds · {split.get('holdout_days')}d blind · "
            f"weight {model.get('class_weight') or 'none'}")


def _value(row: dict, key: tuple):
    """One measure off a fit, whether it sits at the top level or in a block."""
    cur = row
    for part in key:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur if isinstance(cur, (int, float)) else None


def _fits() -> list[dict]:
    """Every model fit on disk, sweeps and single runs alike.

    One row per fit, not per run: a sweep is one record holding six fits, and
    the whole point of the merged panel is that a fit can be seen inside the
    population of fits rather than only inside its own run.
    """
    out = []
    docs = ([(d, "rows", "sweep") for d in _docs("*/bench-sweep-*.json")]
            + [(d, "scores", "run") for d in _docs("*/bench-2*.json")])
    for doc, key, kind in docs:
        cfg = doc.get("config") or {}
        label = _cfg_label(cfg)
        when = str(doc.get("stamped", ""))[:19].replace("T", " ")
        for row in doc.get(key) or []:
            if not isinstance(row.get("cv"), dict):
                continue
            out.append(dict(
                name=row.get("name") or row.get("model", ""),
                model=row.get("model", ""),
                rejected=bool(row.get("rejected")),
                full=_value(row, ("full", "rmse")),
                label=label, when=when, kind=kind, file=doc["_file"],
                values={m: _value(row, spec["key"]) for m, spec in MEASURES.items()},
            ))
    out.sort(key=lambda r: r["when"])
    return out


# ---------------------------------------------------------------------------
# C1 Model and scoreboard
# ---------------------------------------------------------------------------

def model_explorer() -> str:
    """Every fit ever scored, with this run's own fits marked inside them."""
    import plotly.graph_objects as go

    import control_interactive as ci        # imported here, not at module level:
    # control_interactive registers this function in its own FIGURES table, so a
    # module-level import in this direction closes the circle and neither module
    # loads.

    fits = _fits()
    if not fits:
        return ci._missing("No scored fit is on disk yet. Run the sweep or the "
                           "model zoo from the panel above and this fills in.")

    # "This run" is the newest record on disk, and it is a layer rather than a
    # separate figure because the distinction the operator insisted on is
    # exactly this one: Performance is one configuration computed now,
    # the Scoreboard is all of them, and the reader needs to see where now sits.
    newest = max(r["when"] for r in fits)
    latest = [r for r in fits if r["when"] == newest]
    older = [r for r in fits if r["when"] != newest]

    def axis(rows, measure):
        return [r["values"][measure] for r in rows]

    def hover(rows):
        return [f"<b>{r['name']}</b> · {r['model']}<br>{r['label']}<br>"
                f"{r['when']}<br>"
                + "<br>".join(
                    f"{m}: {'n/a' if r['values'][m] is None else round(r['values'][m], 4)}"
                    for m in MEASURES)
                + f"<br>{r['file']}"
                for r in rows]

    first = "Theil U2 on the blind period"
    colour = [ci.RED if r["rejected"] else
              (ci.GREEN if (r["values"]["Theil U2 on the blind period"] or 9) < 1
               else ci.BLUE) for r in older]

    fig = go.Figure()
    fig.add_trace(go.Scattergl(
        x=[r["full"] for r in older], y=axis(older, first), mode="markers",
        name=f"every fit before today ({len(older)})",
        marker=dict(size=6, color=colour, opacity=0.7, line=dict(width=0)),
        text=hover(older), hovertemplate="%{text}<extra></extra>"))
    fig.add_trace(go.Scattergl(
        x=[r["full"] for r in latest], y=axis(latest, first), mode="markers",
        name=f"the newest run ({len(latest)})",
        marker=dict(size=13, color="rgba(0,0,0,0)", symbol="circle",
                    line=dict(width=2.2, color=ci.NAVY)),
        text=hover(latest), hovertemplate="%{text}<extra></extra>"))

    def shapes_for(measure):
        bar = MEASURES[measure]["bar"]
        if bar is None:
            return []
        return [dict(type="line", xref="paper", x0=0, x1=1, yref="y",
                     y0=bar, y1=bar,
                     line=dict(color=ci.RED, width=1.4, dash="dash"))]

    buttons = []
    for measure, spec in MEASURES.items():
        buttons.append(dict(
            label=measure, method="update",
            args=[{"y": [axis(older, measure), axis(latest, measure)]},
                  {"yaxis": {"title": {"text": f"{measure} — {spec['note']}"}},
                   "shapes": shapes_for(measure)}]))

    fig.update_layout(
        shapes=shapes_for(first),
        updatemenus=[dict(buttons=buttons, direction="down", showactive=True,
                          x=0, xanchor="left", y=1.16, yanchor="top",
                          font=dict(size=10.5), active=1,
                          bgcolor="#f2f5f8", bordercolor=ci.RULE)])
    fig.update_xaxes(title="RMSE in sample — what the model could memorise")
    fig.update_yaxes(title=f"{first} — {MEASURES[first]['note']}")
    return ci._wrap(
        fig, f"{len(fits)} fits, and where the newest run sits among them",
        "Each point is one model at one configuration. Pick the vertical "
        "measure from the box at the top left and the dashed bar moves with it. "
        "Red failed the 1.1 overfit bar, green beat a constant forecast on the "
        "blind period, blue did neither. The ringed points are the newest run "
        "on disk, so the configuration fitted now can be read against every "
        "configuration fitted before it. Hover a point for its settings and all "
        "four measures; drag a box to zoom.")


# ---------------------------------------------------------------------------
# C2 History
# ---------------------------------------------------------------------------

def history_explorer() -> str:
    """Every scored fit on a date axis, with the milestones above it."""
    import plotly.graph_objects as go

    import control_interactive as ci        # see model_explorer: circular import.
    import milestones as ms

    fits = [r for r in _fits() if r["when"]]
    marks = ms.load() or ms.seed()
    volume = Counter()
    for p in glob.glob(str(EVALS / "*/bench-*.json")):
        if os.path.basename(p).startswith("._"):
            continue
        volume[datetime.fromtimestamp(os.path.getmtime(p)).date()] += 1
    if not fits and not marks:
        return ci._missing("Nothing has been recorded yet.")

    first = "Theil U2 on the blind period"

    def series(measure):
        """The fits carrying this measure, and the best available at each date.

        The running best only ever falls, which is the whole reading of the
        line: where it is flat, nothing tried in that stretch improved on what
        was already there. Computed per measure rather than once, because the
        best RMSE and the best U2 are not the same fit.
        """
        got = [r for r in fits if r["values"][measure] is not None]
        best, run = float("inf"), []
        for r in got:
            best = min(best, r["values"][measure])
            run.append(best)
        return got, run

    got, run = series(first)
    if not got:
        return ci._missing("No fit on disk carries a scored measure yet.")

    fig = go.Figure()
    if volume:
        days = sorted(volume)
        fig.add_trace(go.Bar(
            x=days, y=[volume[d] for d in days], name="records written",
            marker_color=ci.RULE, opacity=0.55, yaxis="y2",
            hovertemplate="%{x|%d %b %Y}<br>%{y} records<extra></extra>"))
    fig.add_trace(go.Scattergl(
        x=[r["when"] for r in got], y=[r["values"][first] for r in got],
        mode="markers", name="each fit",
        marker=dict(size=5, color=ci.SOFT, opacity=0.65),
        text=[f"<b>{r['name']}</b> · {r['model']}<br>{r['label']}<br>{r['file']}"
              for r in got],
        hovertemplate="%{text}<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=[r["when"] for r in got], y=run, mode="lines",
        name="best available that day",
        line=dict(color=ci.NAVY, width=2.2),
        hovertemplate="best so far %{y:.4f}<extra></extra>"))

    # The milestones ride above the cloud rather than inside it. They have no
    # error of their own, so any vertical position is a fiction; parking them on
    # one line at the top says that plainly instead of implying a value.
    top = max(r["values"][first] for r in got)
    colour = {"design": ci.PURPLE, "data": ci.BLUE, "workflow": ci.GREEN}
    for kind, col in colour.items():
        got_marks = [m for m in marks if m["kind"] == kind]
        if not got_marks:
            continue
        fig.add_trace(go.Scatter(
            x=[m["date"] for m in got_marks], y=[top * 1.06] * len(got_marks),
            mode="markers", name=ms.KINDS[kind],
            marker=dict(size=11, color=col, symbol="diamond"),
            text=[f"<b>{ms.KINDS[m['kind']]}</b> · {m['date']}<br>{m['what']}"
                  f"<br><i>{m['where']}</i>" for m in got_marks],
            hovertemplate="%{text}<extra></extra>"))

    buttons = []
    for measure, spec in MEASURES.items():
        g, r_ = series(measure)
        if not g:
            continue
        tops = max(v for v in (x["values"][measure] for x in g))
        ys = [None] * (1 if volume else 0)          # the bar trace keeps its own y
        ys += [[x["values"][measure] for x in g], r_]
        ys += [[tops * 1.06] * len([m for m in marks if m["kind"] == k])
               for k in colour if any(m["kind"] == k for m in marks)]
        xs = [None] * (1 if volume else 0)
        xs += [[x["when"] for x in g], [x["when"] for x in g]]
        xs += [[m["date"] for m in marks if m["kind"] == k]
               for k in colour if any(m["kind"] == k for m in marks)]
        buttons.append(dict(
            label=measure, method="update",
            args=[{"x": xs, "y": ys},
                  {"yaxis": {"title": {"text": f"{measure} — {spec['note']}"}}}]))

    fig.update_layout(
        yaxis2=dict(overlaying="y", side="right", showgrid=False,
                    title="records written that day", rangemode="tozero"),
        updatemenus=[dict(buttons=buttons, direction="down", showactive=True,
                          x=0, xanchor="left", y=1.16, yanchor="top",
                          font=dict(size=10.5), active=1,
                          bgcolor="#f2f5f8", bordercolor=ci.RULE)])
    fig.update_xaxes(title="", rangeslider=dict(visible=True))
    fig.update_yaxes(title=f"{first} — {MEASURES[first]['note']}")
    return ci._wrap(
        fig, f"{len(got)} scored fits, {sum(volume.values())} records and "
             f"{len(marks)} milestones on one axis",
        "The whole project on a date axis. Grey points are individual fits and "
        "the navy line is the best result available on that day, so where it is "
        "flat nothing tried in that stretch improved on what was there. The "
        "diamonds are milestones, the few points where the model design, the "
        "input data or the workflow changed; hover one to read what changed and "
        "which file shows it. The pale bars behind are how many records were "
        "written that day. Change the measure at the top left, and drag the "
        "slider underneath to a period.")
