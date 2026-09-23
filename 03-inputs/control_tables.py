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

W = "https://en.wikipedia.org/wiki/"   # definitions are linked here
import os
import re
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
    "model": "The model, and any settings changed from the library default.",
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
            "models once, or a comparison run, which fits one model at every setting in "
            "a grid.",
    "fits": "How many models the run fitted. A comparison run is one run of several fits.",
    "passed": "How many of those fits came in under the 1.1 overfit bar.",
    "configuration": "Which of the six forest settings this fit was: the "
                     "library defaults, the incumbent, more trees, deeper and "
                     "narrower, pruned and subsampled, or every feature offered.",
    "assets": "How many symbols the comparison run was fitted on. Blank or 'all' means "
              "the whole panel rather than a named list.",
    "families": "Which feature families were offered to the model. 'all' means "
                "every column in the panel.",
    "folds": "Walk-forward folds the cross-validated column was averaged over. "
             "More folds is a better estimate and a longer wait; across this "
             "comparison run session the fold count moved held-out error by 0.0040.",
    "blind days": "How many days at the end of the panel were held back and "
                  "scored once. Never used in training or in tuning.",
    "weight": "Whether the model was fitted with a balanced class weight or "
              "left unweighted. The largest single lever measured here: it moves "
              "held-out error 0.0255 on matched conditions.",
    "CV spread": "Standard deviation of the cross-validated RMSE across the "
                 "comparison run's repeats. A configuration whose error moves more "
                 "between repeats than between settings has not been separated "
                 "from the noise.",
    # The feature dictionary.
    "Binance, crypto": "The crypto venue: Binance spot, read from the public archives.",
    "Alpaca, US equities": "The equity venue: Alpaca's paper account on the SIP feed.",
    "Gate": "The screen a name must pass before it is offered to the model or the book.",
    "Rule": "The rule, in one or two words.", "Rationale": "Why the rule exists.",
    "Family": "The prefix the columns share.", "Description": "What the family is, in plain words.",
    "Columns": "How many columns the family has in the current file.",
    "Engine": "The indicator engine.", "Description": "What it does, in plain words.", "Default": "The setting as shipped.",
    "Step": "One stage of variable selection.", "Regime": "How the training window is cut into folds.",
    "Time order": "Whether later rows can never sit in training while earlier ones are scored.",
    "Result": "The regime comparison run on the memorising forest, 16 September 2026.",
    "Model": "The model.", "Description": "The model in plain words.",
    "16 September result": "From the model comparison run, class weight none.",
    "Score": "A measure on the board.", "Description": "In plain words.", "Benchmarks": "What it must clear.",
    "Settings": "Every setting the model accepts, as named in Choose Settings.",
    "Kept": "A kind of record.",
    "What it says": "The rule in plain words. Provisional means the exit-geometry comparison run has not settled it.",
    "Rationale": "What the rule protects against, in one line.",
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


# performance() was removed on 22 September 2026. It printed the same fits as
# the Results table 840 pixels below it, under different names for the same four
# quantities: "RMSE CV" against "RMSE, held out", "ratio" against "overfit
# ratio". Results was added on 21 September because Performance sat under the
# run output, and Performance was never removed, so the panel printed one run
# twice in full. Its two columns Results lacked, MAE and MISE on the held-out
# folds, moved into tuning(); its four charts stay on the panel.


def assessment() -> dict:
    """Every run on disk, one row per run, newest first.

    One row per run, where the Scoreboard carries one row per fit. Both read the
    same records and they are not the same table: a comparison run is one run of six fits,
    so the Scoreboard's 456 rows are 82 runs, and a run's own best fit is what
    decides whether that configuration replaced the one before it.
    """
    heads = ["when", "kind", "model", "fits", "passed", "config", "RMSE CV",
             "ratio", "verdict", "blind U2", "record"]
    rows = []
    bench, sweeps = _docs("*/bench-2*.json"), _docs("*/bench-sweep-*.json")
    for doc, kind, key in ([(d, "bench run", "scores") for d in bench]
                           + [(d, "comparison run", "rows") for d in sweeps]):
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
    """Every configuration fit in every comparison run, hundreds of them.

    The condition is spread across its own columns rather than packed into one
    label, because the point of this table is that a reader sorts it. Packed into
    a single string, the four axes the September session varied could not be
    ranked on at all: clicking the heading sorted them alphabetically by the
    number of symbols.
    """
    heads = ["when", "configuration", "model", "assets", "families", "folds",
             "blind days", "weight", "RMSE CV", "CV spread", "ratio", "cap", "verdict",
             "blind RMSE", "blind U2", "blind AUC", "U1", "bias", "record"]
    rows = []
    # Counted from the floats, never from the cells. The cells are rounded to
    # three decimals for reading, and counting "below one" off the rounded text
    # scored a U2 of 0.99961 as 1.000 and dropped nine of the forty-two fits
    # that beat a constant, which is the one column on this page that would
    # change what gets traded.
    passed = beat = both = 0
    # BOTH kinds of record, not just the comparison runs. Until 22 September
    # 2026 this read "*/bench-sweep-*.json" alone while the recommendation in
    # bench_config._all_records read both patterns, so one panel showed "Best
    # of 556 fits so far" beside a table headed "499 fits", and the record the
    # panel recommended was not necessarily in the table beneath it. A
    # scoreboard that omits the fit it is recommending is not a scoreboard.
    #
    # The two kinds keep their fits under different keys, which is why the
    # narrow glob was there: a comparison run writes "rows", a single run
    # writes "scores". The row shape itself is the same.
    graded: list[dict] = []
    docs = _docs("*/bench-sweep-*.json") + _docs("*/bench-2*.json")
    docs.sort(key=lambda d: str(d.get("stamped", "")), reverse=True)
    for doc in docs:
        when = str(doc.get("stamped", ""))[:16].replace("T", " ")
        cfg = doc.get("config", {})
        data, split, model = (cfg.get("data") or {}, cfg.get("split") or {},
                              cfg.get("model") or {})
        fams = (cfg.get("features") or {}).get("families") or []
        n_sym = len(str(data.get("symbols") or "").split())
        for r in (doc.get("rows") or doc.get("scores") or []):
            if not isinstance(r.get("cv"), dict):
                continue
            b = r.get("blind") or {}
            u2 = b.get("theil_u2")
            cap = model.get("reject_ratio")
            # The verdict is only meaningful beside the bar that produced it.
            # bench_run.py:962 judges "rejected" against cfg.model.reject_ratio,
            # which is a per-run setting: rows scored in September were judged
            # at 1.1 and rows scored today may be judged at 1.3, and the table
            # showed one green "passes" for both. Recording the cap makes the
            # column comparable across rows.
            ok = not r.get("rejected", False)
            graded.append(dict(when=when, model=r.get("model", ""),
                               name=r.get("name", ""), ok=ok,
                               u2=u2 if isinstance(u2, (int, float)) else None))
            passed += ok
            beat += isinstance(u2, (int, float)) and u2 < 1.0
            both += ok and isinstance(u2, (int, float)) and u2 < 1.0
            rows.append([when, r.get("name", ""), r.get("model", ""),
                         n_sym or "all", " ".join(fams) if fams else "all",
                         split.get("folds"), split.get("holdout_days"),
                         model.get("class_weight") or "none",
                         _n(r["cv"]["rmse"]), _n(r.get("cv_rmse_sd"), 5),
                         _n(r.get("rmse_ratio"), 3),
                         _n(cap, 2) if cap is not None else "n/a",
                         "rejected" if not ok else "passes",
                         _n(b.get("rmse")), _n(u2, 4), _n(r.get("blind_auc"), 3),
                         _n(b.get("theil_u1"), 3), _n(b.get("theil_bias"), 3),
                         os.path.basename(doc["_file"])])
    # Did the last run improve on the best we had? Operator, 22 September 2026:
    # "the ultimate objective is to run a model and improve our trading every
    # time. The tab doesn't show this." The panel counted fits and never said
    # whether the newest one was any good, so the comparison is computed here,
    # over the fits that passed the overfit bar, on the blind period's Theil's
    # U2, where below 1 beats always guessing the base rate.
    #
    # A fit that failed the overfit bar is not eligible to be the best, because
    # its blind score was produced by a model the house rule already rejects.
    ranked = [g for g in graded if g["u2"] is not None and g["ok"]]
    best = min(ranked, key=lambda g: g["u2"]) if ranked else None
    newest_stamp = graded[0]["when"] if graded else None
    newest = [g for g in ranked if g["when"] == newest_stamp]
    last = min(newest, key=lambda g: g["u2"]) if newest else None
    prior = [g for g in ranked if g["when"] != newest_stamp]
    prior_best = min(prior, key=lambda g: g["u2"]) if prior else None
    if last is None:
        verdict = "The last run has no fit that passed the overfit bar."
    elif prior_best is None:
        verdict = "This is the first fit on record that passed the overfit bar."
    elif last["u2"] < prior_best["u2"]:
        verdict = (f"The last run improved on every run before it, "
                   f"{last['u2']:.4f} against {prior_best['u2']:.4f}.")
    else:
        verdict = (f"The last run did not improve on the best so far, "
                   f"{last['u2']:.4f} against {prior_best['u2']:.4f} from "
                   f"{prior_best['when']}.")
    return dict(
        headings=heads, rows=rows,
        # The four numbers the panel now opens with. They were only ever in this
        # caption, which is rendered as the heading's tooltip, so the summary of
        # the whole accumulated record was invisible. Operator answer, 22
        # September 2026: success in a session is comparing runs against each
        # other, so the standing of the record is the panel's first statement.
        standing=dict(fits=len(rows), runs=len(docs), passed=passed,
                      beat=beat, both=both, verdict=verdict,
                      best=best, last=last),
        caption=(f"{len(rows)} fits from {len(docs)} comparison runs; {passed} passed "
                 f"the overfit bar, {beat} beat the base rate on the blind period "
                 f"and {both} did both. Click a heading to sort."))


def _panel_stats(path: Path) -> tuple[dict, int]:
    """Missing share and range for every column, from the Parquet footer only.

    Reading the columns themselves is not an option here: the four-hour panel is
    two gigabytes and this machine sits nearly five gigabytes into swap, which
    is what killed the render twice and the tuning comparison run five times. Every
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
        caption=(f"{len(rows)} columns in the {doc['frame']} file, {n_on} of them offered to "
                 f"the model under the saved settings."))



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

def venues() -> dict:
    """The two markets side by side, in the order the tools beside them are used."""
    B = '<a href="https://data.binance.vision/" target="_blank">public archive</a>'
    X = '<a href="https://api.binance.com/api/v3/exchangeInfo" target="_blank">exchange information</a>'
    A = '<a href="https://docs.alpaca.markets/docs/historical-api" target="_blank">price history</a>'
    rows = [
        ("Market",
         f"669 coin pairs priced in USDT ever listed on Binance, 487 still trading on 6 Sep 2026; "
         f"the current test uses 3. Read from Binance's {B} of monthly price files, checked "
         f"against its checksums, with the coin list from Binance's {X}. History as far back as "
         "each coin goes, bitcoin from 2017. Coins later delisted are kept, so results are not flattered.",
         f"2,660 US stocks passed the screen out of 12,571 listed (26 Aug 2026); 2,547 are in the "
         f"built file; 50 are held. Read from Alpaca's {A} on the SIP feed, every US exchange's "
         "trades combined, adjusted for splits and dividends, from 2016. Delisted stocks are "
         "missing, so every result is a little flattered; a test that removed stocks at random "
         "did not change the finding."),
        ("Timeframes",
         "Candles of 5 minutes, for scalping, trades of about two hours; 1 hour, for day trading; "
         "4 hours, for swing trades held a few days, the timeframe most work here used; and 1 day, "
         "for positions held for weeks, with the fewest fees. One builder makes all four.",
         "Daily candles only, for positions held for weeks and rebalanced once a week. Alpaca also "
         "serves 1, 5, 15 and 60 minute candles; they have not been downloaded, because the one "
         "strategy that beat its costs trades weekly."),
        ("Trading hours",
         "All day, every day.",
         "Weekdays 09:30 to 16:00 New York. The first 15 minutes cost 42.6 bp a trade against 7.6 "
         "after, so never trade then."),
        ("Trading cost",
         "0.15 per cent of the trade for a buy and its sell together, with maker orders and the "
         "BNB fee discount; 0.20 assumed in tests.",
         "5 to 10 bp (hundredths of a per cent) assumed; measured 6.1 bp a fill on average, 3.3 "
         "typical, over 41 fills to 14 Sep 2026."),
        ("Result",
         "No crypto strategy has beaten its costs on unseen data. Ranking coins by strength works, "
         "but the fee eats it.",
         "Buying last year's strongest stocks beat the market by 1.0 per cent a month on unseen "
         "data (t 2.41, to 5 Sep 2026)."),
    ]
    return dict(headings=["", "Binance, crypto", "Alpaca, US equities"],
                rows=[list(r) for r in rows], caption="", html=True)


def screening() -> dict:
    """The gates a name passes before it is offered, per venue, in plain words."""
    rows = [
        ("Liquidity",
         "At least 30 million USDT traded in the last 24 hours, so a position can be "
         "bought and sold without moving the price.",
         "At least 20 million dollars traded on a typical day, and a share price of at "
         "least 3 dollars."),
        ("Volatility band",
         'How far the price moves in a typical day, as a share of price, measured by '
         '<a href="https://en.wikipedia.org/wiki/Average_true_range" target="_blank">ATR</a>, '
         'the Average True Range: the average over 14 days of each day\'s low-to-high range. '
         'Daily candles 2.5 to 12 per cent; 4 hours 1.0 to 4.9; 1 hour 0.5 to 2.5; '
         '5 minutes 0.15 to 0.71. Too little and there is nothing to catch; too much and '
         'the stop is hit by noise.',
         "1 to 8 per cent a day."),
        ("History",
         "At least 157 days of candles, so every input the model needs exists.",
         "No missing days in the trading calendar."),
        ("Spread",
         'The <a href="https://en.wikipedia.org/wiki/Bid%E2%80%93ask_spread" target="_blank">gap</a> '
         "between the best buy and sell price. At most 0.05 per cent when "
         "trading live; in backtests, estimated from candle ranges, at most 0.5 per cent.",
         "Not checked; the combined feed's quotes are tight for stocks that pass the "
         "volume gate."),
        ("Survivorship",
         '<a href="https://en.wikipedia.org/wiki/Survivorship_bias" target="_blank">Delisted</a> '
         "coins are kept, and each candle counts only the coins that existed "
         "at that time.",
         "Delisted stocks are missing; a test that dropped stocks at random still held "
         "the finding."),
        ("Regime",
         "Only trade when bitcoin's own trend is up.", "None."),
        ("Narrow book",
         "Only coins that made money on unseen data under that gate and pass the live "
         "liquidity check.",
         "The top tenth of stocks by twelve-month return, 50 names."),
        ("Fee floor",
         "What a buy and its sell cost together when the app places the orders on "
         "Binance through its API key: 0.15 per cent of the trade with maker orders and "
         "the BNB discount, 0.20 assumed in tests. A strategy must earn more than this "
         "per trade or it loses money.",
         "What a buy and its sell cost together when the app places the orders on "
         "Alpaca through its API key: 5 to 10 bp assumed, 6.1 bp a fill measured. About "
         "one twentieth of the crypto cost."),
    ]
    return dict(headings=["Gate", "Binance, crypto", "Alpaca, US equities"],
                rows=[list(r) for r in rows], caption="", html=True)


def rules() -> dict:
    """The book's hard rules, and whether each one is switched on.

    Rewritten 20 September 2026. The table had a rule and a reason and no way
    to tell the two kinds apart: a rule the code enforces on every order, and a
    rule written in the charter that the basket actually trading has switched
    off. Four of the fourteen were in the second group and the table said
    nothing, so a reader would have believed a stop was protecting a position
    when no stop existed. The third column is that answer, and every value in
    it was read out of 03-inputs/alpaca_trade.py rather than recalled.

    Ordered by what bites first on a real order: what may never be done, then
    how large, then how concentrated, then when trading halts, then when a
    position is closed, then the rules that govern research rather than orders.
    """
    K = f'<a href="{W}Kelly_criterion" target="_blank">Kelly</a>'
    ON = "In force, in code"
    rows = [
        ("Direction",
         "Buy only. Never short, never on margin, never a leveraged fund.",
         "A long-only cash book cannot lose more than it holds. Leveraged funds "
         "were bought once by accident, on 25 August 2026, because Alpaca files "
         "every exchange-traded fund as an ordinary equity and nothing filtered "
         "them; a momentum ranking promotes a 3x fund mechanically, since it "
         "carries about three times its sector's trailing return.",
         f"{ON}. New spend is capped at free cash above the 10 per cent floor, "
         "and funds are excluded from the universe."),
        ("Money switch",
         "No order reaches a real account until LIVE_TRADING is set to true in "
         "the environment for that run. Anything else, including unset, is false.",
         "One deliberate switch between reading the market and spending money, "
         "in one place, that has to be typed.",
         f"{ON}. The run aborts if the endpoint is not the paper one."),
        ("Position size",
         "No single name may exceed 5 per cent of the account when it is bought.",
         "One name cannot sink the book.",
         f"{ON}. The live basket holds 50 names at 1.8 per cent, well inside it."),
        ("Bet size",
         f"Size a discretionary entry at half the {K} fraction, the size that "
         "grows money fastest for the odds on offer, and a quarter when only the "
         "minimum number of signals agree.",
         "Size to the evidence rather than to conviction. Full Kelly ruins the "
         "account on a mis-estimated edge.",
         "Not in force. The basket is equal weight by design, so nothing in the "
         "live path computes a Kelly fraction."),
        ("Big pitch",
         "One position at a time may go to 10 per cent, and only with a reward "
         "at least three times the risk, a named cause for the mispricing and a "
         "written exit condition.",
         "A rare chance deserves more money, but only when the case is written "
         "down before the order and can be checked afterwards.",
         "Never used. No position has been taken above 5 per cent."),
        ("Concentration",
         "Any group of holdings that move together, correlating above 0.7, is "
         "capped at 20 per cent of the account.",
         "The sector cap catches the obvious concentration; this catches two "
         "different sectors that move as one. It was written in the charter and "
         "not enforced until 26 August 2026, and on the book that day 37 of 49 "
         "names were one group worth 66.6 per cent of equity, which is why a "
         "week SPY spent down 0.20 per cent cost the book 6.25 per cent.",
         f"{ON} since 26 August 2026. Admission is symmetric, so a name admitted "
         "early is re-tested as later correlates arrive; the first version "
         "tested only one direction and enforced the appearance of the cap."),
        ("Cash floor",
         "At least 10 per cent of the account stays in cash.",
         "Always able to act, and never accidentally on margin.",
         f"{ON}. It sets the buying budget on every rebalance."),
        ("Daily halt",
         "No new orders once the last 24 hours have cost 3 per cent of the "
         "account. Existing stops keep working.",
         "Stops a bad day compounding into a decision made badly.",
         f"{ON}. The rebalance refuses to place orders when it trips."),
        ("Catastrophe stop",
         "Close any name trading 25 per cent below its average entry.",
         "It fires on a collapse, not on factor noise. A 7 per cent stop fires "
         "most weeks on momentum names and amputates the strategy that was "
         "tested; 25 per cent on a 1.8 per cent position bounds the loss at "
         "about 0.45 per cent of the account.",
         f"{ON}. Swept by the check command on every scheduled run."),
        ("Hard stop",
         "Sell when price falls a set number of typical daily moves below the "
         "buy price. The charter's figure is 7 per cent.",
         "Cuts a losing trend short before it becomes a hole.",
         "Switched off for the basket, by the operator's decision of 18 August "
         "2026, and replaced by the 25 per cent catastrophe stop above. The "
         "number in ATR is still unsettled: the code carries 5 per cent on the "
         "label and an ATR stop averaging about 8.5 per cent."),
        ("Trailing stop",
         "Sell when price falls a set number of typical daily moves below its "
         "highest point since the buy. The charter's figure is 10 per cent.",
         "Lets a winner run and keeps most of what it made.",
         "Switched off for the basket, same decision and same reason. How far "
         "the stop should trail is still being measured."),
        ("Losing week",
         "After a 5 per cent loss over the rolling week, each new position "
         "shrinks by 1 per cent of its size for every further 1 per cent lost.",
         "Shrinks the book as losses mount instead of only blocking new orders, "
         "which is the difference between a brake and a switch.",
         "Not in force. Nothing in the live path computes a rolling weekly "
         "drawdown."),
        ("New positions",
         "At most 3 new positions a week.",
         "Forces selectivity on a discretionary book.",
         "Switched off for the basket. A weekly rebalance of 50 names cannot "
         "obey it and the cap would forbid the rebalance itself."),
        ("Averaging down",
         "Never add to a losing position.",
         "A loser is sold or held, never fed.",
         "Not in force for the basket, and this is a real conflict rather than "
         "an oversight. The rebalance tops a name back up to equal weight when "
         "it drifts more than 25 per cent below target, which is buying the "
         "faller by construction."),
        ("Anchoring",
         "The price paid never enters the decision to hold or sell.",
         "Decide on what happens next, not on what was paid.",
         f"{ON}. Entry price is read for three things only: the catastrophe "
         "stop, realised profit and loss, and tax."),
        ("Fees",
         "Maker orders and the exchange's own fee discount, measured from the "
         "account on every run rather than assumed.",
         "The fee is the adversary. On crypto the measured 0.15 per cent round "
         "trip closes half the gap to breaking even; on equities the measured "
         "6.1 basis points a fill is about one twentieth of it.",
         f"{ON}. Every run reads the account's own fee tier."),
        ("The bar",
         "Nothing is traded unless it beats a coin flip, beats buying and "
         "holding, and beats its own fees on data held back and scored once.",
         "A strategy that cannot pay its fee is not a strategy. This is the "
         "rule that has killed every crypto candidate so far.",
         f"{ON} as a process rule. One equity strategy has cleared it: buying "
         "last year's strongest stocks, by 1.0 per cent a month."),
    ]
    return dict(headings=["Rule", "Description", "Rationale", "In force"],
                rows=[list(r) for r in rows], caption="", html=True)


def families() -> dict:
    """Every feature family in plain words, with its column count from the dictionary."""
    counts = {}
    if DICTIONARY.exists():
        try:
            doc = json.loads(DICTIONARY.read_text(encoding="utf-8"))
            for fam, info in (doc.get("families") or {}).items():
                cols = info.get("columns") if isinstance(info, dict) else info
                counts[fam] = len(cols) if isinstance(cols, (list, dict)) else ""
        except (json.JSONDecodeError, OSError):
            pass
    rows = [
        ("f_btc_", "How the coin moved against bitcoin, and how bitcoin itself moved. The only "
                   "family not built from the coin's own price, and the strongest measured, by three times."),
        ("f_wc_", "Trend, momentum and volatility over windows of days, converted to candles."),
        ("f_hr_", "The same measures over short windows of a few candles."),
        ("f_st_", f'Three <a href="{W}Average_true_range" target="_blank">ATR</a>-based Supertrend '
                  "lines, fast to slow, and how many agree the trend is up."),
        ("f_mst_", "An adaptive Supertrend whose width follows how cleanly price is trending."),
        ("f_ta_", "Classic oscillators: Williams %R, Stochastic, CCI, CMF, MFI, ADX, Aroon."),
        ("f_ta_pta_", "More oscillators from the pandas-ta library: PPO, TRIX, Vortex, CMO, Fisher, Chande Kroll."),
        ("f_tl_", "TA-Lib extras: Parabolic SAR, MESA, Ultimate Oscillator, Hilbert cycle, candle patterns. "
                  "Eight of the ten useless columns found in September were candle patterns."),
        ("f_4h_, f_d1_, f_w1_", "The same trend measures read from the bigger timeframes above the one traded."),
        ("f_flow_", "Whether buyers or sellers were hitting the market, from Binance's taker-buy share."),
        ("f_rg_", "The state of the market: recent volatility, its rank against its own past, trend efficiency."),
        ("f_ms_", "Fine-grained price behaviour from hourly candles, for daily frames."),
    ]
    return dict(headings=["Family", "Description"],
                rows=[[f, w] for f, w in rows], caption="", html=True)


def engines() -> dict:
    """The four indicator engines: what each is, how it is read, and its settings."""
    rows = [
        ("MACD",
         f'<a href="{W}MACD" target="_blank">Moving average convergence divergence</a>. Take a '
         "fast average of price (12 candles) and a slow one (26); MACD is the fast minus the slow, "
         "positive when price is rising faster than its longer trend. A signal line, the 9-candle "
         "average of MACD, smooths it. MACD crossing above the signal line is a buy, below it a "
         "sell. A divergence, price making a new high while MACD does not, warns the move is tiring.",
         "Fast span, slow span, signal span; a noise band that ignores crosses smaller than a set "
         "fraction of the histogram's usual size; confirm candles, how many candles a cross must hold."),
        ("Supertrend",
         "A line drawn a set number of typical daily moves (ATR) below price while the trend is up "
         "and above it while the trend is down. When price closes through the line, the trend "
         "flips and the line jumps to the other side. Three of them run at once, fast to slow, "
         "and the count that agree is a strength score; a fourth adapts its width to how cleanly "
         "price is trending.", "Three bands, fixed; the adaptive band's width follows trend efficiency."),
        ("Moving averages",
         "Two averages of the closing price over a fixed number of candles, one fast and one "
         "slow. Price sitting above the slow average is an uptrend and below it a downtrend, "
         "which is the cheapest statement of trend there is; the fast average crossing the slow "
         "one marks the turn. It lags by construction, roughly half the window, so it confirms a "
         "trend rather than catching its start, and in a sideways market it crosses back and "
         "forth and pays fees for nothing. That is why it votes in the confluence score instead "
         "of trading alone.",
         "Fast span and slow span, both in candles; 20 and 50 are the usual pair on a swing "
         "chart, 50 and 200 on a position chart."),
        ("Fibonacci",
         f'<a href="{W}Fibonacci_retracement" target="_blank">Retracement levels</a>. Find the '
         "last swing from a low to a high, and draw lines at 38, 50 and 62 per cent of the way "
         "back down. Price often pauses or turns at them, which gives entries after a pullback "
         "and places for a stop.", "Lookback, how many candles back to find the swing; ignore "
         "swings smaller than a set fraction of price."),
        ("Confluence",
         "A count of how many engines say the same direction at the same candle, MACD, the "
         "Supertrend lines, a Fibonacci level and a candle pattern. A signal fires only when the "
         "count reaches the score, so no single indicator trades alone.",
         "Score to fire; how many candles a candle pattern stays counted after it forms."),
    ]
    return dict(headings=["Engine", "Description", "Settings"], rows=[list(r) for r in rows], caption="", html=True)


def selection_steps() -> dict:
    """What variable selection does, step by step."""
    rows = [
        ("Univariate", "Each column is fitted alone against an intercept-only model and tested by "
                       "likelihood ratio: does it explain the outcome at all?",
         "Ranks columns by strength; catches nothing that only works beside others."),
        ("Elastic net", f'A <a href="{W}Elastic_net_regularization" target="_blank">penalised regression</a> '
                        "on all columns at once that shrinks weak ones to exactly zero.",
         "Decides which survive together; the coefficient path shows the order they drop out."),
        ("Penalty rule", "min takes the penalty with the lowest cross-validated error; 1se takes "
                         "the strongest penalty within one standard error of it.",
         "1se keeps fewer columns and generalises better."),
        ("Refit", "The survivors are refitted without penalty for confidence intervals.",
         "A sign that flips when neighbours are added is the finding."),
        ("Training only", "Every step runs on the training window; the blind period is never opened.",
         "So the screen cannot peek at the answer."),
    ]
    return dict(headings=["Step", "Description", "Rationale"], rows=[list(r) for r in rows], caption="", html=True)


def regimes() -> dict:
    """The seven resampling regimes, and what the September comparison run found for each."""
    rows = [
        ("Expanding", "The training window grows; each fold is scored on what follows.", "yes",
         "The house regime. Claimed error within 0.01 of the blind period."),
        ("Rolling", "The training window slides; old history drops out.", "yes",
         "Within 0.01 of the blind period."),
        ("K-fold", "Random equal blocks, each scored once.", "no",
         "Claimed error 0.09 below what the blind period found on a memorising forest."),
        ("Repeated k-fold", "K-fold reshuffled and repeated.", "no", "Same leak, ten times."),
        ("Leave-one-out", "Every scored row is fitted on all the others, neighbours included.", "no",
         "The most flattering: 0.12 below the blind period."),
        ("Monte Carlo", "Repeated random splits at 75 per cent training.", "no", "0.10 below."),
        ("Bootstrap", "Resample with replacement, score the rows left out.", "no", "0.09 below."),
    ]
    return dict(headings=["Regime", "Description", "Time order", "Result"],
                rows=[list(r) for r in rows], caption="")


def learners() -> dict:
    """The six models: what each is, how it works, what it is good for, and its settings."""
    import bench_config as bc
    desc = {
        "LogReg.glm": f'<a href="{W}Logistic_regression" target="_blank">Logistic regression</a>. '
                      "Adds up the columns with a weight each and turns the sum into a probability. "
                      "Simple, fast, stable, easy to read; best when the signal is roughly a straight "
                      "line through the inputs and the data is small.",
        "LogReg.enet": "Logistic regression with an elastic-net penalty, which shrinks weak columns "
                       "towards zero and drops the weakest. Best when there are many columns and few "
                       "matter; the most reliable model on this board so far.",
        "RF": f'<a href="{W}Random_forest" target="_blank">Random forest</a>. Hundreds of decision '
              "trees, each grown on a random slice of rows and columns, with their votes averaged. "
              "Handles bends and interactions between columns, hard to overfit when the trees are "
              "kept shallow; favoured for tabular data with mixed signals.",
        "HistGBM": f'<a href="{W}Gradient_boosting" target="_blank">Gradient boosting</a>, '
                   "histogram version. Trees fitted one after another, each correcting the last, "
                   "with the columns binned for speed. Strongest on large, clean tables; memorises "
                   "noisy price data unless heavily restrained.",
        "LightGBM": "Gradient boosting from Microsoft, growing trees leaf by leaf rather than level "
                    "by level. Fastest on wide data; same appetite for memorising noise as HistGBM.",
        "GBM.classic": "scikit-learn's original gradient booster. Slower, depth-wise trees, no class "
                       "weight. A baseline for the two above.",
    }
    rows = []
    for m in ("LogReg.glm", "LogReg.enet", "RF", "HistGBM", "LightGBM", "GBM.classic"):
        labels = [re.sub(r"\s*\(.*?\)\s*$", "", f.label).strip() for f in bc.param_fields(m)]
        rows.append([m, desc.get(m, ""), "; ".join(labels) + "."])
    return dict(headings=["Model", "Description", "Settings"], rows=rows, caption="", html=True)


def scores() -> dict:
    """Every score on the board, what it means, and the bar it must clear."""
    rows = [
        ("RMSE", "Root mean squared error of the predicted probability against the 0 or 1 outcome. "
                 "Lower is better; 0.5 is guessing.", "Reported in sample, cross-validated and blind."),
        ("Overfit ratio", "Cross-validated RMSE over training RMSE: how much worse the model does "
                          "on rows it did not see.", "Rejected above 1.1, whatever its error."),
        ("Theil's U2", "The model's error over the error of always guessing the base rate.",
         "Under 1 means it beat a constant guess. This is the only score that would change what gets traded."),
        ("AUC", "How well the model ranks winners above losers, 0.5 is a coin flip.", "Above 0.55 to matter."),
        ("Calibration error", "How far a stated probability sits from how often the outcome happens.",
         "0.03 after Platt scaling; 0.23 raw with the balanced class weight."),
        ("After-fee return", "Mean return per trade taken, less the cost.", "Positive on unseen data, or it does not ship."),
        ("Pass rate", "Share of half-year folds where the strategy made money.", "At least 0.6."),
    ]
    return dict(headings=["Score", "Description", "Benchmarks"], rows=[list(r) for r in rows], caption="")


def ledger() -> dict:
    """What the ledger holds."""
    rows = [
        ("Runs", "Every scored fit on disk, 460 and counting, each with the settings that produced it."),
        ("Milestones", "The 18 points where the design, the data or the workflow changed; not runs."),
        ("The book", "The paper account in dollars: open and closed positions, cash, and the curve since it went live on 18 August 2026."),
        ("Reports", "The daily book report and the execution report, one file a day under a dated folder."),
    ]
    return dict(headings=["Kept", "Description"], rows=[list(r) for r in rows], caption="")


def _repeat_spread(docs: list[dict]) -> str:
    """How far the score moves when the settings do not move at all.

    Stated only when the last two runs happened to be identical, which is luck.
    Every record on disk carrying this run's exact configuration is a repeat
    measurement of it, and the spread of their best scores is the floor under
    which no improvement can be believed. Without it a reader cannot tell a
    real gain of 0.002 from the bench shuffling its own folds.
    """
    if not docs:
        return ""
    want = json.dumps(docs[0].get("config") or {}, sort_keys=True, default=str)
    same = [_best_u2(d) for d in docs
            if json.dumps(d.get("config") or {}, sort_keys=True, default=str) == want]
    same = [v for v in same if isinstance(v, (int, float))]
    if len(same) < 2:
        return ("Only this run has been scored on these exact settings, so there "
                "is no repeat to measure the bench's own randomness against. Run "
                "it again unchanged and the panel will say how far it moves.")
    lo, hi = min(same), max(same)
    return (f"These exact settings have been run {len(same)} times. The best "
            f"score came out between {lo:.4f} and {hi:.4f}, a spread of "
            f"{hi - lo:.4f}, which is this bench's own randomness: an "
            f"improvement smaller than that is not an improvement.")


def _what_changed(docs: list[dict]) -> str:
    """What is different about this run from the one before it.

    The panel said what this run used and what it scored and left the reader to
    hold the previous run in their head to see which of the two facts explains
    the other. The whole point of a session is to change something and see the
    number move, so the thing that changed is named.
    """
    if len(docs) < 2:
        return "This is the first run on record, so there is nothing to compare it with."
    now, then = docs[0].get("config") or {}, docs[1].get("config") or {}
    moved = []
    for sec in sorted(set(now) | set(then)):
        a, b = now.get(sec) or {}, then.get(sec) or {}
        if not isinstance(a, dict) or not isinstance(b, dict):
            continue
        for key in sorted(set(a) | set(b)):
            was, is_ = b.get(key), a.get(key)
            if was == is_:
                continue
            # A nested block such as the per-model parameters is reported as
            # the block that moved, not as a wall of every leaf inside it.
            if isinstance(was, dict) or isinstance(is_, dict):
                moved.append(f"{sec} {key} settings changed")
                continue
            moved.append(f"{sec} {key} {_fmt(was)} to {_fmt(is_)}")
    when = str(docs[1].get("stamped", "")).replace("T", " ")[:16]
    # The change and the score move belong in one sentence. A run that changed
    # nothing and moved 0.0015 is the measurement of this bench's own noise,
    # and without it no improvement smaller than that can be believed.
    move = _score_move(docs)
    if not moved:
        # The sentence about what that difference means belongs to
        # _repeat_spread, which says it from every repeat on record rather than
        # from whichever two runs happened to land next to each other.
        return (f"Nothing was changed since the run of {when}: every setting is "
                f"the same.{move}")
    head = (f"Changed since the run of {when}: " if len(moved) <= 8 else
            f"{len(moved)} settings changed since the run of {when}, among them ")
    return head + "; ".join(moved[:8]) + "." + move


def _best_u2(doc: dict):
    """The lowest blind score among a record's fits that passed the bar."""
    vals = [(r.get("blind") or {}).get("theil_u2")
            for r in (doc.get("scores") or doc.get("rows") or [])
            if not r.get("rejected", False)]
    vals = [v for v in vals if isinstance(v, (int, float))]
    return min(vals) if vals else None


def _score_move(docs: list[dict]) -> str:
    """This run's best blind score against the previous run's, as a move."""
    a, b = _best_u2(docs[0]), _best_u2(docs[1])
    if a is None or b is None:
        return ""
    d = a - b
    if abs(d) < 5e-5:
        return f" The score stayed at {a:.4f}."
    return (f" The score went from {b:.4f} to {a:.4f}, "
            f"{'better' if d < 0 else 'worse'} by {abs(d):.4f}.")


def _fmt(v) -> str:
    if v is None or v == "":
        return "nothing"
    if isinstance(v, list):
        return ", ".join(str(x) for x in v) or "nothing"
    return str(v)


def _comparable(board: dict, cfg: dict) -> tuple[list[float], list[str]]:
    """The blind scores of the fits scored on this run's own shape.

    Same asset count, same fold count, same blind window, same class weight,
    and passing the overfit bar. Those are the fits a rank can honestly place
    this run among; the rest of the record answers a different question.
    """
    heads = board.get("headings") or []
    need = ("assets", "folds", "blind days", "weight")
    if not all(h in heads for h in need) or "blind U2" not in heads:
        return [], []
    cols = [heads.index(h) for h in need]
    u_col = heads.index("blind U2")
    v_col = heads.index("verdict") if "verdict" in heads else None
    data, sp, md = (cfg.get("data") or {}, cfg.get("split") or {},
                    cfg.get("model") or {})
    syms = len(str(data.get("symbols") or "").split())
    mine = [str(syms or "all"), str(sp.get("folds")),
            str(sp.get("holdout_days")), str(md.get("class_weight") or "none")]
    vals: list[float] = []
    for r in (board.get("rows") or []):
        if [str(r[c]) for c in cols] != mine:
            continue
        if v_col is not None and str(r[v_col]) != "passes":
            continue
        try:
            vals.append(float(r[u_col]))
        except (TypeError, ValueError):
            continue
    return vals, mine


def _like_for_like(board: dict, cfg: dict, total: int) -> str:
    """How much of the field this run is actually comparable with.

    The rank is over every fit any run ever wrote, and those runs used
    different assets, different fold counts and different blind windows. Saying
    "434 of 572" without saying how many of the 572 were scored the same way
    invites the reader to read a rank as a like-for-like placing when most of
    the field is not.
    """
    heads = board.get("headings") or []
    need = ("assets", "folds", "blind days", "weight")
    if not all(h in heads for h in need):
        return ""
    cols = [heads.index(h) for h in need]
    data, sp, md = (cfg.get("data") or {}, cfg.get("split") or {},
                    cfg.get("model") or {})
    syms = len(str(data.get("symbols") or "").split())
    mine = [str(syms or "all"), str(sp.get("folds")),
            str(sp.get("holdout_days")), str(md.get("class_weight") or "none")]
    same = sum(1 for r in (board.get("rows") or [])
               if [str(r[c]) for c in cols] == mine)
    if not same or not total:
        return ""
    return (f"{same:,} of the {total:,} were scored on the same shape as this "
            f"run, {mine[0]} assets over {mine[1]} folds against a "
            f"{mine[2]}-day blind period; the rest used a different one, so the "
            f"rank is a position in the whole record rather than a like-for-like "
            f"placing.")


def _panels_line(read_from: str) -> str:
    """Which panel owns which part of the one settings file.

    "Where were they saved" has two true answers and the reader needs both: the
    file the run opened, and the panel whose Save button put each part of it
    there. Naming only the file leaves them hunting six panels for the box.
    """
    try:
        import control_registry as reg
        bits = [f"{c.key} {c.title} wrote {', '.join(c.all_sections)}"
                for c in reg.CARDS if c.all_sections]
        return read_from + ". " + "; ".join(bits) + "."
    except Exception:                                   # noqa: BLE001
        return read_from


def _describe(cfg: dict) -> str:
    """The run's own settings as one sentence, from the record's copy."""
    try:
        import bench_config as bc
        return bc.describe(cfg)
    except Exception:                                   # noqa: BLE001
        return _cfg_label(cfg)


def run_report() -> dict:
    """What the last run did, in sentences, with nothing left to infer.

    Operator, 22 September 2026, in these words: if it is not clear what the
    control centre is doing, where it is grabbing the code, where it is saving
    it, and how the model is being evaluated against the other models, the work
    is not done. Four questions, four sentences, in that order.

    Everything here comes out of the record the run itself wrote. Nothing is
    reconstructed from the form, because a panel that describes a run from its
    own controls describes the run it would launch now, not the one that ran.
    """
    docs = _docs("*/bench-2*.json")
    if not docs:
        return dict(ran="No run on disk yet.",
                    steps=[], verdict="", rank="")
    doc = docs[0]
    fits = doc.get("scores") or doc.get("rows") or []
    cfg = doc.get("config") or {}
    when = str(doc.get("stamped", "")).replace("T", " ")[:16]
    label = doc.get("label") or "no label"

    # 1. Which script ran. A record written before the command was recorded
    # says so, rather than printing a bare path as if it were the whole line.
    cmd = doc.get("command")
    cmd_why = ("The command the Run button composed, recorded by the run itself, "
               "not rebuilt from the form afterwards.")
    if not cmd:
        cmd = "03-inputs/bench_run.py, arguments not recorded"
        cmd_why = ("This record was written before runs kept their own command "
                   "line. The next run records it in full.")
    # 2. Which settings, and where they live.
    read_from = doc.get("config_read_from") or "04-outputs/AA-evals/bench/config.json"
    # 3. Where the record went.
    md_ = doc.get("record_md") or os.path.relpath(doc["_file"], REPO).replace(".json", ".md")
    js_ = doc.get("record_json") or os.path.relpath(doc["_file"], REPO)
    figs = [f.get("file", "") for f in (doc.get("figures") or [])]

    secs = doc.get("elapsed_s")
    took = f" It took {secs:,.0f} seconds." if isinstance(secs, (int, float)) else ""
    steps = [
        ("Which code ran", f"{cmd}", cmd_why),
        # The full sentence, not the shorthand. _cfg_label writes "2 sym, 6000
        # rows, 3 fam" and the operator's standing rule is no shorthand column
        # names and no internal abbreviations on the page.
        ("Which settings it used", _describe(cfg),
         "Every setting in the file below, exactly as the panels saved it, read "
         "once at the start of the run and embedded in its record."),
        ("Where the settings were saved", _panels_line(read_from),
         "One file. Every Save button on every panel writes its own section of "
         "it, and the run reads the whole file once at the start."),
        ("What changed since last time",
         _what_changed(docs) + " " + _repeat_spread(docs),
         "The settings of this run against the settings of the one before it, "
         "read from the two records rather than from the panel, so a score that "
         "moved can be put beside the thing that moved it."),
        ("Where the result was written", md_,
         f"The readable record. The same numbers in {js_}"
         + (f", and {len(figs)} figure(s) beside it." if figs else ".")),
    ]

    # 4. How it scored, against every other fit on record.
    board = scoreboard()
    st = board.get("standing") or {}
    best = st.get("best") or {}
    lines = []
    # The three bars are stated and never added up. A reader was left to decide
    # for themselves whether a fit that passed one and missed two is usable,
    # which is the panel handing back the judgement it exists to make.
    def _usable(r) -> str:
        u = (r.get("blind") or {}).get("theil_u2")
        ok = not r.get("rejected", False)
        met = bool(r.get("fold_bar_met"))
        beat = isinstance(u, (int, float)) and u < 1.0
        if ok and met and beat:
            return "worth trading on this evidence"
        if not ok:
            return "not usable: it fits its training rows too closely"
        if not beat:
            return "not usable: it did no better than guessing the average"
        return "not usable: it did not hold up across enough folds"
    for r in fits:
        u2 = (r.get("blind") or {}).get("theil_u2")
        ok = not r.get("rejected", False)
        cap = (cfg.get("model") or {}).get("reject_ratio")
        rate, scored_n = r.get("fold_pass_rate"), r.get("folds_scored") or 0
        bar = (cfg.get("screen") or {}).get("fold_bar")
        bits = []
        if isinstance(u2, (int, float)):
            bits.append(f"scored {u2:.4f} on the blind period, "
                        + ("better than always guessing the average"
                           if u2 < 1 else "worse than always guessing the average, "
                           "which scores 1.0000"))
        bits.append(f"overfit ratio {_n(r.get('rmse_ratio'), 3)} against a cap of "
                    f"{_n(cap, 2)}, so it {'passes' if ok else 'is rejected'}")
        if scored_n and isinstance(rate, (int, float)) and rate == rate:
            # The bar is a share of the folds and was printed as "0.60" beside
            # a count, "0 of 2", so the reader had a count and a decimal in one
            # breath with nothing saying they are the same quantity.
            need = (f", where the bar of {float(bar) * 100:.0f} per cent needs "
                    f"{int(-(-float(bar) * scored_n // 1))}"
                    if isinstance(bar, (int, float)) else "")
            bits.append(f"{int(round(rate * scored_n))} of {scored_n} folds beat a "
                        f"constant{need}")
        lines.append(f"{r.get('model', '?')} is {_usable(r)}. It "
                     + "; ".join(bits) + ".")

    # The rank is over every fit the record holds, so "better than the others"
    # is a count, not an impression.
    rows = board.get("rows") or []
    u2_col = board["headings"].index("blind U2") if "blind U2" in board.get("headings", []) else None
    ranked = []
    if u2_col is not None:
        for row in rows:
            try:
                ranked.append(float(row[u2_col]))
            except (TypeError, ValueError):
                continue
    # Every model the record holds, at its own best. "Compared to the other
    # models" was answered only as a rank among 572 anonymous fits, which says
    # where this run sits and nothing about what the alternatives are worth.
    # One row per model, its best blind score, and whether this run beat it.
    heads_ = board.get("headings") or []
    m_col = heads_.index("model") if "model" in heads_ else None
    w_col = heads_.index("when") if "when" in heads_ else 0
    # Only fits that passed the overfit bar, the same eligibility the standing
    # uses. Counting the rejected ones too gave this table 0.9779 for the forest
    # beside a standing that said 0.9800: one panel, two bests.
    v_col = heads_.index("verdict") if "verdict" in heads_ else None
    per: dict[str, dict] = {}
    # A model every one of whose fits was rejected has no row in the table
    # above, so a reader sees three models and concludes three exist. The
    # record knows six. The ones with nothing eligible are named beneath it.
    rejected_only: dict[str, str] = {}
    if m_col is not None and u2_col is not None:
        for row in rows:
            if v_col is not None and str(row[v_col]) != "passes":
                rejected_only.setdefault(str(row[m_col]).strip().lower(),
                                         str(row[m_col]))
                continue
            try:
                v = float(row[u2_col])
            except (TypeError, ValueError):
                continue
            name = str(row[m_col])
            key = name.strip().lower()
            # The name as the NEWEST record spells it, and the rows arrive
            # newest first. Taking it from whichever fit happened to be best
            # printed "RF" in the verdict and "rf" in the table beneath it:
            # one model, two spellings, on one panel.
            got = per.setdefault(key, dict(model=name, n=0, best=None, when=""))
            got["n"] += 1
            if got["best"] is None or v < got["best"]:
                got["best"], got["when"] = v, str(row[w_col])
    mine = [(r.get("blind") or {}).get("theil_u2") for r in fits]
    mine = [m for m in mine if isinstance(m, (int, float))]
    rank = ""
    if mine and ranked:
        b = min(mine)
        place = sum(1 for v in ranked if v < b) + 1
        beat_n = sum(1 for v in ranked if v < 1.0)
        share = place / len(ranked)
        where = ("the best of them" if place == 1 else
                 "in the best tenth" if share <= 0.10 else
                 "in the better half" if share <= 0.50 else
                 "in the worse half")
        # Like for like first, because that is the comparison that means
        # something, then the whole record as context. Until 22 September 2026
        # only the whole-record rank was given: it placed this run 434 of 572
        # when 3 of the 572 had been scored the same way.
        peers, shape = _comparable(board, cfg)
        if len(peers) >= 3:
            place2 = sum(1 for v in peers if v < b) + 1
            first = (f"Against the {len(peers):,} fits scored the same way, "
                     f"{shape[0]} assets over {shape[1]} folds against a "
                     f"{shape[2]}-day blind period, this run is {place2:,}, and "
                     f"the best of them scored {min(peers):.4f}.")
            # "was" reads wrong above a plural; the branch above is the one
            # that has to agree, and it does.
        else:
            # peers counts this run's own fit, so the others are one fewer.
            others = max(len(peers) - 1, 0)
            first = (("No other fit on record" if others == 0 else
                      "Only one other fit on record" if others == 1 else
                      f"Only {others:,} other fits on record")
                     + f" was scored the same way, {shape[0]} assets over "
                       f"{shape[1]} folds against a {shape[2]}-day blind period, "
                       f"which is too few to rank among, so the comparison that "
                       f"stands is against a constant guess, which scores 1.0000."
                     if shape else "")
        rank = (first
                + f" Across the whole record, which mixes shapes, it is "
                  f"{place:,} of {len(ranked):,}, {where}, and {beat_n:,} of "
                  f"those {len(ranked):,} beat a constant guess."
                + (f" The lowest ever is {best.get('u2'):.4f}, by "
                   f"{per.get(str(best.get('model', '')).strip().lower(), {}).get('model', best.get('model'))}"
                   f" on {best.get('when')}."
                   if best.get("u2") is not None else "")).strip()

    ran_now = {str(r.get("model", "")).strip().lower() for r in fits}
    mine_by = {str(r.get("model", "")).strip().lower():
               (r.get("blind") or {}).get("theil_u2") for r in fits}
    models = []
    for key, g in sorted(per.items(), key=lambda kv: kv[1]["best"]):
        now = mine_by.get(key)
        models.append(dict(
            model=g["model"], fits=g["n"], best=g["best"], when=g["when"],
            this_run=(f"{now:.4f}" if isinstance(now, (int, float)) else ""),
            ran=key in ran_now,
            beat_own=(isinstance(now, (int, float)) and now <= g["best"] + 1e-12)))

    none_eligible = sorted(v for k, v in rejected_only.items() if k not in per)
    if none_eligible:
        models_note = (
            f"{len(per)} of {len(per) + len(none_eligible)} models on record have "
            f"a fit that passed the overfit bar. "
            + (", ".join(none_eligible[:-1]) + " and " + none_eligible[-1]
               if len(none_eligible) > 1 else none_eligible[0])
            + (" have none, so they are not in the table above."
               if len(none_eligible) > 1 else
               " has none, so it is not in the table above."))
    else:
        models_note = (f"Every one of the {len(per)} models on record has a fit "
                       f"that passed the overfit bar.")

    # Which rows the blind score was measured on, by name and by count.
    sp = (cfg.get("split") or {})
    blind_note = ""
    if sp.get("holdout_days"):
        blind_note = (f"The blind period is the last {sp['holdout_days']} days of the "
                      f"panel, held out of every fold and scored once.")
    return dict(
        ran=f"{label}, finished {when}.{took}",
        # The record is named on the panel and could not be opened from it.
        # The link goes through the control centre's own record viewer, which
        # is the same one the evidence log uses.
        record_link=md_,
        steps=steps, verdict=" ".join(lines),
        rank=rank, models=models, models_note=models_note,
        blind_note=blind_note,
        standing_verdict=st.get("verdict", ""))


def tuning() -> dict:
    """The last run's candidates, laid out the way caret prints a fit.

    Operator instruction, 21 September 2026: there was no clear results view and
    no way to find the tuning parameters. The Performance table existed but sat
    under the run output, and it pushed the hyperparameters into the model's own
    name, where the column width truncated them to "RF  max_depth=4 min_sa".

    caret's print.train is the shape borrowed here, from
    05-research/research/caret-package.pdf, caret 7.0-1: a line saying how the
    resampling was done, then one row per candidate with ONE COLUMN PER TUNING
    PARAMETER and the metrics beside them, then a sentence naming the metric
    used to choose and the values the final model used. The parameters get their
    own columns because that is the question the table answers: which setting
    moved the number.

    The metrics are this repository's, not caret's. Accuracy and Kappa say
    nothing useful about a barrier label at a 0.26 base rate; held-out RMSE on
    the probability, the overfit ratio and Theil's U2 on the blind period do.
    """
    docs = _docs("*/bench-2*.json")
    if not docs:
        return dict(headings=[], rows=[],
                    caption="No run on disk yet. Press Run the test.")
    doc = docs[0]
    rows_in = doc.get("scores") or []
    if not rows_in:
        return dict(headings=[], rows=[], caption="The last run scored nothing.")

    cfg = doc.get("config") or {}
    sp, md = cfg.get("split", {}), cfg.get("model", {})

    # Every parameter any candidate set, in the order they first appear, so a
    # grid over two parameters gets two columns and a plain scorecard gets none.
    par_names: list[str] = []
    for r in rows_in:
        for k in (r.get("params") or {}):
            if k not in par_names:
                par_names.append(k)

    heads = ["model"] + par_names + [
        "RMSE, held out", "RMSE, in sample", "MAE, held out", "MISE, held out",
        "overfit ratio", "verdict",
        "folds beating a constant", "RMSE, blind", "U2, blind", "AUC, blind"]
    out = []
    for r in sorted(rows_in, key=lambda r: r["cv"]["rmse"]):
        par = r.get("params") or {}
        fold = ("n/a" if not r.get("folds_scored")
                else f"{sum(1 for u in r['fold_u2'] if u < 1.0)} of {r['folds_scored']}")
        out.append([r["model"]] + [str(par.get(k, "")) for k in par_names] + [
            f"{r['cv']['rmse']:.4f}", f"{r['full']['rmse']:.4f}",
            f"{r['cv']['mae']:.4f}", f"{r['cv']['mise']:.5f}",
            f"{r['rmse_ratio']:.3f}", "rejected" if r["rejected"] else "passes",
            fold, f"{r['blind']['rmse']:.4f}",
            f"{r['blind']['theil_u2']:.3f}", f"{r['blind_auc']:.3f}"])

    passing = [r for r in rows_in if not r.get("rejected")]
    # The winner the record itself named, and the rule that chose it, rather
    # than this table re-deciding and possibly disagreeing with the record.
    named = doc.get("chosen")
    best = next((r for r in rows_in if r["model"] == named), None) \
        or min(passing or rows_in, key=lambda r: r["cv"]["rmse"])
    by = doc.get("chosen_by") or "the lowest held-out error among those that passed"
    chose = ", ".join(f"{k} = {v}" for k, v in (best.get("params") or {}).items())
    n_boot = sp.get("boot_samples")
    how = {"expanding": f"walk-forward, expanding window, {sp.get('folds')} folds",
           "rolling": f"walk-forward, rolling window, {sp.get('folds')} folds",
           "kfold": f"{sp.get('folds')}-fold, time ignored",
           "repeated-kfold": f"{sp.get('folds')}-fold repeated {sp.get('repeats')} times, time ignored",
           "leave-one-out": "leave one out, time ignored",
           "monte-carlo": f"{sp.get('repeats')} random splits at 75 per cent, time ignored",
           "bootstrap": f"{n_boot} bootstrap draws, scored out of bag, time ignored",
           }.get(sp.get("scheme"), str(sp.get("scheme")))
    purge = sp.get("purge_bars") or 0

    # One short line, then the detail in smaller type. Operator, 21 September
    # 2026: "there is too much crap everywhere". The first version of this put
    # the verdict, three reasons, the resampling, the blind period, the class
    # weight and the selection rule into a single four-hundred-character
    # sentence, which is the complaint rather than the fix.
    beat = best["blind"]["theil_u2"] < 1.0
    passed = not best.get("rejected")
    folds_ok = best.get("fold_bar_met")
    scored = bool(best.get("folds_scored"))
    n_ok = sum((beat, passed, bool(folds_ok) or not scored))
    verdict = "WORTH KEEPING" if n_ok == 3 else ("NOT YET" if n_ok else "NO")
    good = [w for w, ok in (("beat a constant guess", beat),
                            ("passed the overfit bar", passed),
                            ("cleared the fold bar", folds_ok if scored else None))
            if ok]
    bad = [w for w, ok in (("did not beat a constant guess", beat),
                           ("failed the overfit bar", passed),
                           ("missed the fold bar", folds_ok if scored else None))
           if ok is False]
    cap = (f"{verdict}. {best['model']} "
           + " and ".join(filter(None, [", ".join(good), ", ".join(bad)])) + ".")

    detail = (f"{how}"
              + (f", purging {purge} bars" if purge else "")
              + f". Blind period {sp.get('holdout_days')} days, scored once. "
              f"Class weight {md.get('class_weight')}. "
              f"Chosen by {by}. "
              f"Unseen error {best['blind']['theil_u2']:.3f} times a constant guess, "
              f"overfit ratio {best['rmse_ratio']:.3f} against "
              f"{md.get('reject_ratio')}"
              + (f", {best['fold_pass_rate'] * 100:.0f} per cent of folds beat a "
                 f"constant against a bar of "
                 f"{float(best.get('fold_bar', 0)) * 100:.0f} per cent"
                 if scored else "") + ".")

    return dict(headings=heads, rows=out, caption=cap, detail=detail,
                record=doc.get("_file", ""))


TABLES = {"tuning": tuning, "assessment": assessment,
          "scoreboard": scoreboard, "features": features,
          "money": money, "venues": venues, "screening": screening,
          "rules": rules, "families": families, "engines": engines,
          "selection_steps": selection_steps, "regimes": regimes,
          "models": learners, "scores": scores, "ledger": ledger}


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
    # Captions were written with Markdown emphasis and the template renders them
    # as raw HTML, so **-$715.44 on the account** printed with its asterisks
    # showing. Converted here, once, rather than in four captions.
    out["caption"] = re.sub(r"\*\*(.+?)\*\*", r"\1",
                            out.get("caption", ""))
    return out
