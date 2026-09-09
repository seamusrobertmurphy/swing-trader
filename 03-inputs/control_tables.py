"""The large tables: every test on disk, compiled.

Operator instruction, 9 September 2026. The Performance panel needed a table
compiling every test of the previous run, and the Scoreboard needed populating
with the hundreds of runs already completed rather than a summary of a handful.

Each function returns a dict of headings, rows and a caption, which the page
renders with an explanation on every column. The explanation matters more than
usual here: a column called "U2" means nothing to anyone who has not read the
metric definitions, and this is the page where a number is looked up rather than
derived.

Nothing is computed. Every row is read from a record already written.
"""

from __future__ import annotations

import glob
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "04-outputs" / "AA-evals"

# What every column means, shown when the pointer rests on the heading and on
# each value. Operator instruction: information appears on hover.
GLOSS = {
    "when": "When the run finished.",
    "model": "The estimator, and any hyperparameters set away from the library default.",
    "config": "Which configuration produced the row: the symbols, the folds, the class weight.",
    "RMSE Full": "Root mean squared error in sample, on the training window. "
                 "The optimistic number: it shows what the model can memorise.",
    "RMSE CV": "Root mean squared error walk-forward out-of-fold on the same "
               "training window. The honest one.",
    "MAE CV": "Mean absolute error out-of-fold. Every miss counts once, where "
              "RMSE counts a big miss harder.",
    "MISE CV": "Integrated squared error of the calibration curve. Measures "
               "whether a stated probability means what it says, not whether it "
               "ranks well. A model predicting the base rate for every row "
               "scores near nought here and is useless.",
    "ratio": "Cross-validated RMSE over training RMSE. Above 1.1 is rejected as "
             "overfit whatever its error.",
    "verdict": "Whether it passed that bar.",
    "blind RMSE": "Error on the held-out period, scored once at the end.",
    "blind U2": "Theil's U2 on the held-out period: the model's error over the "
                "error of always predicting the base rate. Below one beats a "
                "constant forecast; at or above one does not.",
    "blind AUC": "Area under the ROC curve on the held-out period. 0.5 is a coin "
                 "flip. It measures ranking, not calibration.",
    "U1": "Theil's accuracy coefficient, bounded on nought to one, nought being "
          "a perfect forecast.",
    "bias": "The share of squared error explained by the forecast's mean sitting "
            "away from the outcome's. Catches a model that is systematically "
            "high or low rather than merely noisy.",
    "n": "Rows the figure was computed on.",
    "record": "The file this row was read from.",
}


def _docs(pattern: str) -> list[dict]:
    out = []
    for p in sorted(glob.glob(str(EVALS / pattern)), reverse=True):
        if os.path.basename(p).startswith("._"):
            continue
        try:
            d = json.loads(Path(p).read_text(encoding="utf-8"))
            d["_file"] = str(Path(p).relative_to(REPO))
            out.append(d)
        except (json.JSONDecodeError, OSError):
            continue
    return out


def _n(v, dp=4):
    if v is None or not isinstance(v, (int, float)):
        return "n/a"
    try:
        if v != v:
            return "n/a"
    except TypeError:
        return "n/a"
    return f"{v:.{dp}f}"


def _cfg_label(cfg: dict) -> str:
    d, s, m = cfg.get("data", {}), cfg.get("split", {}), cfg.get("model", {})
    syms = len(str(d.get("symbols", "")).split()) or "all"
    fams = cfg.get("features", {}).get("families") or []
    return (f"{syms} sym, {d.get('rows') or 'all'} rows, "
            f"{len(fams) or 'all'} fam, {s.get('folds')} folds, "
            f"{s.get('holdout_days')}d blind, weight {m.get('class_weight')}")


def performance() -> dict:
    """Every model fitted in the most recent run, on every measure."""
    docs = _docs("*/bench-2*.json")
    if not docs:
        return dict(headings=[], rows=[], caption="No run on disk yet.")
    doc = docs[0]
    heads = ["model", "RMSE Full", "RMSE CV", "MAE CV", "MISE CV", "ratio",
             "verdict", "blind RMSE", "blind U2", "blind AUC"]
    rows = []
    for r in sorted(doc.get("scores") or [],
                    key=lambda r: (r.get("cv") or {}).get("rmse", 9)):
        if not isinstance(r.get("cv"), dict):
            continue
        f_, c_, b = r["full"], r["cv"], r.get("blind") or {}
        name = r["model"] + ("  " + " ".join(f"{k}={v}" for k, v in r["params"].items())
                             if r.get("params") else "")
        rows.append([name, _n(f_["rmse"]), _n(c_["rmse"]), _n(c_["mae"]),
                     _n(c_["mise"], 5), _n(r["rmse_ratio"], 3),
                     "rejected" if r["rejected"] else "passes",
                     _n(b.get("rmse")), _n(b.get("theil_u2"), 3),
                     _n(r.get("blind_auc"), 3)])
    return dict(
        headings=heads, rows=rows, record=doc["_file"],
        caption=(f"Every model fitted in the most recent run, {doc.get('label') or ''} "
                 f"{_cfg_label(doc.get('config', {}))}. Five measures computed twice "
                 f"on the same predictions, in sample and cross-validated, then once "
                 f"more on the blind period. Rest the pointer on a heading for what "
                 f"the column is."))


def assessment() -> dict:
    """Every run on disk, one row per model, newest first."""
    heads = ["when", "model", "config", "RMSE CV", "ratio", "verdict",
             "blind U2", "record"]
    rows = []
    for doc in _docs("*/bench-2*.json"):
        when = str(doc.get("stamped", ""))[:16].replace("T", " ")
        lab = _cfg_label(doc.get("config", {}))
        for r in doc.get("scores") or []:
            if not isinstance(r.get("cv"), dict):
                continue
            b = r.get("blind") or {}
            rows.append([when, r["model"], lab, _n(r["cv"]["rmse"]),
                         _n(r["rmse_ratio"], 3),
                         "rejected" if r["rejected"] else "passes",
                         _n(b.get("theil_u2"), 3),
                         os.path.basename(doc["_file"])])
    return dict(headings=heads, rows=rows,
                caption=(f"Every bench run on disk, {len(rows)} model fits across "
                         f"{len(_docs('*/bench-2*.json'))} runs, newest first. "
                         f"Performance is one run at one configuration; this is all "
                         f"of them, so a configuration can be compared with what it "
                         f"replaced."))


def scoreboard() -> dict:
    """Every configuration fit in every sweep, hundreds of them."""
    heads = ["when", "model", "config", "RMSE CV", "ratio", "verdict",
             "blind U2", "U1", "bias", "record"]
    rows = []
    for doc in _docs("*/bench-sweep-*.json"):
        when = str(doc.get("stamped", ""))[:16].replace("T", " ")
        lab = _cfg_label(doc.get("config", {}))
        for r in doc.get("rows") or []:
            b = r.get("blind") or {}
            rows.append([when, r.get("name", r.get("model", "")), lab,
                         _n(r["cv"]["rmse"]), _n(r["rmse_ratio"], 3),
                         "rejected" if r["rejected"] else "passes",
                         _n(b.get("theil_u2"), 3), _n(b.get("theil_u1"), 3),
                         _n(b.get("theil_bias"), 3),
                         os.path.basename(doc["_file"])])
    beat = sum(1 for r in rows if r[6] != "n/a" and float(r[6]) < 1.0)
    passed = sum(1 for r in rows if r[5] == "passes")
    return dict(
        headings=heads, rows=rows,
        caption=(f"**{len(rows)} configuration fits** across "
                 f"{len(_docs('*/bench-sweep-*.json'))} sweeps. {passed} passed the "
                 f"overfit bar and **{beat} reached a Theil U2 below one on the "
                 f"blind period**, which is the only column here that would change "
                 f"what gets traded: below one beats always predicting the base "
                 f"rate. Sort by clicking a heading."))


TABLES = {"performance": performance, "assessment": assessment,
          "scoreboard": scoreboard}


def build(name: str) -> dict | None:
    fn = TABLES.get(name)
    if fn is None:
        return None
    try:
        out = fn()
    except Exception as exc:                            # noqa: BLE001
        return dict(headings=[], rows=[],
                    caption=f"This table could not be built: "
                            f"{type(exc).__name__}: {exc}")
    out["gloss"] = {h: GLOSS.get(h, "") for h in out.get("headings", [])}
    return out
