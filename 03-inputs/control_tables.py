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

# The feature dictionary is written down rather than worked out here. A
# description of what a column measures comes from reading the block that emits
# it, which no render-time code can do, and a sentence guessed from a column
# name is how f_st_agree came to be charted against a threshold of two when the
# column is a vote normalised onto minus one to plus one and can never reach it.
DICTIONARY = REPO / "04-outputs" / "feature-dictionary" / "feature-dictionary-4h.json"

# What every column means, shown when the pointer rests on the heading and on
# each value. Operator instruction: information appears on hover.
GLOSS = {
    "when": "When the run finished.",
    # The money columns, added 9 September 2026 on the operator's instruction
    # that gains and losses be stated in dollars rather than only in per cent.
    "holding": "The ticker, and whether the position is still open or already sold.",
    "shares": "How many shares the account holds, or held.",
    "paid": "What the shares cost at the fill, in US dollars.",
    "worth now": "What the shares are worth at the latest mark, in US dollars. "
                 "For a closed trade, what they were sold for.",
    "gain or loss": "Worth now minus what was paid, in US dollars. This is the "
                    "money. A 16 per cent fall on a small holding and a 2 per "
                    "cent fall on a large one can be the same dollars.",
    "move": "The same gain or loss as a percentage of what was paid.",
    "share of book": "What fraction of the whole account this holding is.",
    "effect on account": "What this holding did to the whole account, in "
                         "percentage points. The column that adds up.",
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
    # The condition, one column per axis, so each can be sorted on its own.
    "kind": "Whether the record is a single bench run, which fits the chosen "
            "models once, or a sweep, which fits one model at every setting in "
            "a grid.",
    "fits": "How many models the run fitted. A sweep is one run of several fits.",
    "passed": "How many of those fits came in under the 1.1 overfit bar.",
    "configuration": "Which of the six forest settings this fit was: the "
                     "library defaults, the incumbent, more trees, deeper and "
                     "narrower, pruned and subsampled, or every feature offered.",
    "assets": "How many symbols the sweep was fitted on. Blank or 'all' means "
              "the whole panel rather than a named list.",
    "families": "Which feature families were offered to the model. 'all' means "
                "every column in the panel.",
    "folds": "Walk-forward folds the cross-validated column was averaged over. "
             "More folds is a better estimate and a longer wait; across this "
             "sweep session the fold count moved held-out error by 0.0040.",
    "blind days": "How many days at the end of the panel were held back and "
                  "scored once. Never used in training or in tuning.",
    "weight": "Whether the estimator was fitted with a balanced class weight or "
              "left unweighted. The largest single lever measured here: it moves "
              "held-out error 0.0255 on matched conditions.",
    "CV spread": "Standard deviation of the cross-validated RMSE across the "
                 "sweep's repeats. A configuration whose error moves more "
                 "between repeats than between settings has not been separated "
                 "from the noise.",
    # The feature dictionary.
    "column": "The column as it is named in the panel.",
    "family": "The prefix the column shares with its siblings. The Feature "
              "selection form ticks families, not columns, so this is what "
              "decides whether the column is offered at all.",
    "what the family is for": "One line on why the family exists, taken from "
                              "the block that emits it rather than from the "
                              "prefix.",
    "computed in": "The function inside 03-inputs/build_dataset_1h.py that "
                   "emits this column. Open that function to check the row.",
    "what it measures": "What the column is, in plain words, written by reading "
                        "the code that computes it.",
    "window or parameter": "The lookback or the setting the column was built "
                           "with, read from the module's own constants after "
                           "configure() had retuned them for this frame. A "
                           "window given as a literal in the block is not "
                           "retuned per frame, and the row says so.",
    "offered": "Whether the active Feature selection setting offers this column "
               "to the model. Read live from the saved configuration, so it "
               "changes when the form above is saved.",
    "missing": "The share of the panel's rows where the column has no value. A "
               "family a coin cannot produce at all, such as weekly context on "
               "a short history, is filled with nothing when the coins are "
               "stacked, which is where this comes from.",
    "range": "The lowest and the highest value in the panel, read from the "
             "Parquet footer rather than by loading the column.",
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
    """Every run on disk, one row per run, newest first.

    One row per run, where the Scoreboard carries one row per fit. Both read the
    same records and they are not the same table: a sweep is one run of six fits,
    so the Scoreboard's 456 rows are 82 runs, and a run's own best fit is what
    decides whether that configuration replaced the one before it.
    """
    heads = ["when", "kind", "model", "fits", "passed", "config", "RMSE CV",
             "ratio", "verdict", "blind U2", "record"]
    rows = []
    bench, sweeps = _docs("*/bench-2*.json"), _docs("*/bench-sweep-*.json")
    for doc, kind, key in ([(d, "bench run", "scores") for d in bench]
                           + [(d, "sweep", "rows") for d in sweeps]):
        fits = [r for r in (doc.get(key) or []) if isinstance(r.get("cv"), dict)
                and r["cv"].get("rmse") is not None]
        if not fits:
            continue
        best = min(fits, key=lambda r: r["cv"]["rmse"])
        b = best.get("blind") or {}
        rows.append([str(doc.get("stamped", ""))[:16].replace("T", " "), kind,
                     best.get("name") or best.get("model", ""), len(fits),
                     sum(1 for r in fits if not r["rejected"]),
                     _cfg_label(doc.get("config", {})), _n(best["cv"]["rmse"]),
                     _n(best["rmse_ratio"], 3),
                     "rejected" if best["rejected"] else "passes",
                     _n(b.get("theil_u2"), 4),
                     os.path.basename(doc["_file"])])
    rows.sort(key=lambda r: r[0], reverse=True)
    fits = sum(r[3] for r in rows)
    return dict(headings=heads, rows=rows,
                caption=(f"Every run on disk: **{len(rows)} runs**, {fits} model "
                         f"fits between them, newest first, each shown by its own "
                         f"best fit. Performance next door is one run at one "
                         f"configuration; this is all of them, so a configuration "
                         f"can be compared against what it replaced."))


def scoreboard() -> dict:
    """Every configuration fit in every sweep, hundreds of them.

    The condition is spread across its own columns rather than packed into one
    label, because the point of this table is that a reader sorts it. Packed into
    a single string, the four axes the September session varied could not be
    ranked on at all: clicking the heading sorted them alphabetically by the
    number of symbols.
    """
    heads = ["when", "configuration", "model", "assets", "families", "folds",
             "blind days", "weight", "RMSE CV", "CV spread", "ratio", "verdict",
             "blind RMSE", "blind U2", "blind AUC", "U1", "bias", "record"]
    rows = []
    # Counted from the floats, never from the cells. The cells are rounded to
    # three decimals for reading, and counting "below one" off the rounded text
    # scored a U2 of 0.99961 as 1.000 and dropped nine of the forty-two fits
    # that beat a constant, which is the one column on this page that would
    # change what gets traded.
    passed = beat = both = 0
    docs = _docs("*/bench-sweep-*.json")
    for doc in docs:
        when = str(doc.get("stamped", ""))[:16].replace("T", " ")
        cfg = doc.get("config", {})
        data, split, model = (cfg.get("data") or {}, cfg.get("split") or {},
                              cfg.get("model") or {})
        fams = (cfg.get("features") or {}).get("families") or []
        n_sym = len(str(data.get("symbols") or "").split())
        for r in doc.get("rows") or []:
            if not isinstance(r.get("cv"), dict):
                continue
            b = r.get("blind") or {}
            u2 = b.get("theil_u2")
            ok = not r["rejected"]
            passed += ok
            beat += isinstance(u2, (int, float)) and u2 < 1.0
            both += ok and isinstance(u2, (int, float)) and u2 < 1.0
            rows.append([when, r.get("name", ""), r.get("model", ""),
                         n_sym or "all", " ".join(fams) if fams else "all",
                         split.get("folds"), split.get("holdout_days"),
                         model.get("class_weight") or "none",
                         _n(r["cv"]["rmse"]), _n(r.get("cv_rmse_sd"), 5),
                         _n(r["rmse_ratio"], 3),
                         "rejected" if r["rejected"] else "passes",
                         _n(b.get("rmse")), _n(u2, 4), _n(r.get("blind_auc"), 3),
                         _n(b.get("theil_u1"), 3), _n(b.get("theil_bias"), 3),
                         os.path.basename(doc["_file"])])
    return dict(
        headings=heads, rows=rows,
        caption=(f"**{len(rows)} configuration fits** across {len(docs)} sweeps. "
                 f"{passed} passed the overfit bar, **{beat} reached a Theil U2 "
                 f"below one on the blind period**, and {both} did both. That last "
                 f"column is the only one here that would change what gets traded: "
                 f"below one beats always predicting the base rate. Sort by "
                 f"clicking a heading, and rest the pointer on a value for what it "
                 f"means."))


def _panel_stats(path: Path) -> tuple[dict, int]:
    """Missing share and range for every column, from the Parquet footer only.

    Reading the columns themselves is not an option here: the four-hour panel is
    two gigabytes and this machine sits nearly five gigabytes into swap, which
    is what killed the render twice and the tuning sweep five times. Every
    column chunk already carries its null count and its minimum and maximum in
    the file footer, so the whole table costs one metadata read and no data
    pages at all.
    """
    import pyarrow.parquet as pq

    md = pq.ParquetFile(path).metadata
    names = pq.ParquetFile(path).schema_arrow.names
    out: dict[str, dict] = {}
    for i, name in enumerate(names):
        nulls, lo, hi = 0, None, None
        for rg in range(md.num_row_groups):
            stats = md.row_group(rg).column(i).statistics
            if stats is None:                   # a chunk written without stats
                continue                        # tells us nothing, so skip it
            nulls += stats.null_count or 0
            if stats.has_min_max:
                lo = stats.min if lo is None else min(lo, stats.min)
                hi = stats.max if hi is None else max(hi, stats.max)
        out[name] = dict(nulls=nulls, lo=lo, hi=hi)
    return out, md.num_rows


def features() -> dict:
    """Every feature column in the panel, with what it measures and where from.

    The descriptions are read from the checked-in dictionary, never worked out
    here. Only three things are live: whether the active configuration offers
    the column, how often it is missing, and its range.
    """
    if not DICTIONARY.exists():
        return dict(headings=[], rows=[],
                    caption=f"No dictionary on disk at "
                            f"{DICTIONARY.relative_to(REPO)}.")
    doc = json.loads(DICTIONARY.read_text(encoding="utf-8"))
    fams = doc.get("families", {})
    panel = REPO / doc["panel"]

    stats, n_rows = ({}, 0)
    if panel.exists():
        try:
            stats, n_rows = _panel_stats(panel)
        except Exception:                                   # noqa: BLE001
            stats, n_rows = {}, 0

    # Which columns the model is offered, from the saved configuration rather
    # than from the schema's defaults, because the form above this table writes
    # that file and the reader expects the two to agree.
    offered: set[str] = set()
    try:
        import bench_config as bc

        have = [c["column"] for c in doc["columns"]]
        offered = set(bc.resolve_features(bc.load(), have))
    except Exception:                                       # noqa: BLE001
        offered = set()

    heads = ["column", "family", "what the family is for", "computed in",
             "what it measures", "window or parameter", "offered", "missing",
             "range"]
    rows = []
    for c in doc["columns"]:
        st = stats.get(c["column"], {})
        nulls, lo, hi = st.get("nulls"), st.get("lo"), st.get("hi")
        miss = ("n/a" if not n_rows or nulls is None
                else ("none" if nulls == 0 else f"{100 * nulls / n_rows:.2f}%"))
        rng = ("n/a" if lo is None or hi is None
               else f"{lo:.4g} to {hi:.4g}")
        rows.append([c["column"], c["family"],
                     fams.get(c["family"], {}).get("purpose", ""),
                     c["block"], c["measures"], c["window"],
                     "yes" if c["column"] in offered else "no", miss, rng])
    n_on = sum(1 for r in rows if r[6] == "yes")
    return dict(
        headings=heads, rows=rows, record=doc["panel"],
        caption=(f"**{len(rows)} feature columns** in the {doc['frame']} panel, "
                 f"{n_on} of them offered to the model under the settings saved "
                 f"above. Every description was written by reading the block "
                 f"that emits the column, not from its name, and lives in "
                 f"`{DICTIONARY.relative_to(REPO)}` where it can be corrected. "
                 f"The windows are the module's constants after "
                 f"`configure('{doc['frame']}')`, so a dictionary for another "
                 f"frame carries different numbers and, for the "
                 f"higher-timeframe families, different prefixes. Missing share "
                 f"and range are read live from the panel's Parquet footer."))



# ---------------------------------------------------------------------------
# The money, in dollars.
#
# Operator instruction, 9 September 2026. Every other table on this board is
# about model error. This one is about dollars: what each holding gained or
# lost, what every finished trade realised, and what the two come to together.
#
# It reads the dashboard feed at 04-outputs/dashboard/data.json, written by
# dashboard_data.py from the live Alpaca paper account. Nothing is recomputed
# here, no price is fetched and no fill is inferred; the broker's own numbers
# are restated in dollars. The account is paper money and the caption says so.
# ---------------------------------------------------------------------------

BOOK = REPO / "04-outputs" / "dashboard" / "data.json"


def _usd(v, dp=2) -> str:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return ""
    return f"{'-' if v < 0 else ''}${abs(v):,.{dp}f}"


def _pct(v, dp=2) -> str:
    try:
        return f"{float(v) * 100:+.{dp}f}%"
    except (TypeError, ValueError):
        return ""


def money() -> dict:
    """Every holding and every finished trade, in dollars, with a total."""
    try:
        book = json.loads(BOOK.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(headings=[], rows=[],
                    caption="No account feed on disk. Run "
                            "`./scripts/render_dashboard.sh` to write "
                            "04-outputs/dashboard/data.json.")
    heads = ["holding", "shares", "paid", "worth now", "gain or loss", "move",
             "share of book", "effect on account"]
    cost_of = {r["symbol"]: r.get("cost") for r in (book.get("attribution") or [])}
    points_of = {r["symbol"]: r.get("points") for r in (book.get("attribution") or [])}
    rows, open_pl, closed_pl = [], 0.0, 0.0

    for r in sorted(book.get("positions") or [],
                    key=lambda r: -(r.get("pl") or 0)):
        pl = float(r.get("pl") or 0.0)
        open_pl += pl
        paid = cost_of.get(r["symbol"])
        rows.append([f"{r['symbol']} open", f"{float(r.get('qty') or 0):,.3f}",
                     _usd(paid), _usd(r.get("value")), _usd(pl),
                     _pct(r.get("plpc")), _pct(r.get("weight")),
                     _pct((points_of.get(r["symbol"]) or 0) / 100.0)])

    for r in sorted(book.get("roundtrips") or [],
                    key=lambda r: str(r.get("sold_at") or ""), reverse=True):
        pl = float(r.get("pl") or 0.0)
        closed_pl += pl
        qty = float(r.get("qty") or 0.0)
        rows.append([f"{r['symbol']} closed", f"{qty:,.3f}",
                     _usd(qty * float(r.get("buy_price") or 0)),
                     _usd(qty * float(r.get("sell_price") or 0)),
                     _usd(pl), _pct(r.get("plpc")), "", ""])

    h = book.get("headline") or {}
    equity, start = float(h.get("equity") or 0), float(h.get("start") or 0)
    rows.append(["EVERYTHING", "", _usd(start), _usd(equity),
                 _usd(equity - start),
                 _pct((equity - start) / start if start else None), "100.00%",
                 _pct((equity - start) / start if start else None)])
    when = (book.get("meta") or {}).get("generated_at_pretty", "unknown")
    return dict(
        headings=heads, rows=rows,
        caption=(f"**{_usd(equity - start)} on the account**, from "
                 f"{_usd(start)} deposited to {_usd(equity)} now, marked "
                 f"{when}. Open positions come to {_usd(open_pl)} and the "
                 f"{len(book.get('roundtrips') or [])} finished trades to "
                 f"{_usd(closed_pl)}; the difference between those two and the "
                 f"account total is cash movement and fees. This is a paper "
                 f"account and the money is not real."))



def money_strip() -> dict:
    """The dollar headline, for the masthead of every page.

    Small on purpose. The operator asked on 9 September 2026 for dollar amounts
    to be visible rather than buried in a panel, and the header band had already
    been cut by seventy per cent, so this rides in the line that was carrying
    only the repository name.
    """
    try:
        book = json.loads(BOOK.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    h = book.get("headline") or {}
    equity, start = float(h.get("equity") or 0), float(h.get("start") or 0)
    pos = book.get("positions") or []
    op = sum(float(r.get("pl") or 0) for r in pos)
    cl = sum(float(r.get("pl") or 0) for r in (book.get("roundtrips") or []))
    return dict(
        equity=_usd(equity, 0), start=_usd(start, 0),
        change=_usd(equity - start, 0), change_up=(equity - start) >= 0,
        open=_usd(op, 0), open_up=op >= 0, open_n=len(pos),
        closed=_usd(cl, 0), closed_up=cl >= 0,
        closed_n=len(book.get("roundtrips") or []),
        cash=_usd(h.get("cash"), 0),
        when=(book.get("meta") or {}).get("generated_at_pretty", ""))

TABLES = {"performance": performance, "assessment": assessment,
          "scoreboard": scoreboard, "features": features,
          "money": money}


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
