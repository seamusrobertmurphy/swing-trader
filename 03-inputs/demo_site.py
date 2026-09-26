"""Build the friends demo page and publish it to the gh-pages branch.

    .venv/bin/python 03-inputs/demo_site.py                    # build site/index.html
    .venv/bin/python 03-inputs/demo_site.py --relay URL --publish

Operator design, 24 September 2026: friends configure A1 to C2 on a public
page, press Run, and the run is done for them, with no one seeing the API keys
or the code. The page is the control centre as control_export renders it, with
four differences.

1. The settings stay editable. Save keeps them in the visitor's own browser,
   and they come back on the next visit.
2. Code, commands and the workflow listing are removed.
3. C1 carries a Run block. It sends the saved settings to the relay, a small
   Cloudflare Worker that holds the only GitHub token, which starts the
   demo-run workflow. The page then waits for data/runs/<id>.json.
4. The front page opens on the paper tickets every friend's runs have left,
   read from data/index.json, which the workflows rebuild.

The page is built here, on the machine that holds the records its charts are
drawn from, and pushed to gh-pages. The workflows write only under data/, so
publishing the page never touches the tickets and the tickets never touch the
page.
"""

from __future__ import annotations

import argparse
import json
import html as _html
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import control_export as ce        # noqa: E402
import control_registry as reg     # noqa: E402
from control_centre import app     # noqa: E402

REPO = reg.REPO
SITE = REPO / "site"
PLOTLY = REPO / "03-inputs" / "control_static" / "plotly.min.js"
PAGES_URL = "https://seamusrobertmurphy.github.io/swing-trader/"


def panel_chunk(page: str) -> str:
    """A panel from its masthead to its own scripts, keeping the figure's code.

    control_export.panel_body stops at the first bare script tag, which is the
    interactive figure's Plotly.newPlot call, so the export shows an empty box
    where each figure should be. Here the cut is at the page's last script
    instead, and only the two code blocks after the figure are removed.
    """
    a = page.find("</header>")
    if a < 0:
        return ""
    a += len("</header>")
    b = page.rfind("<script>")
    chunk = page[a:b if b > a else len(page)]
    chunk = re.sub(r'<div class="crumb">.*?</div>', "", chunk, count=1, flags=re.S)
    return chunk


def drop_blocks(body: str, opening: str) -> str:
    """Remove every div that starts with `opening`, with everything nested in it.

    A regular expression cannot match nested divs, so the close is found by
    counting opening and closing tags from the start of the block.
    """
    while True:
        i = body.find(opening)
        if i < 0:
            return body
        depth, j = 0, i
        for m in re.finditer(r"<div\b|</div>", body[i:]):
            depth += 1 if m.group(0) == "<div" else -1
            if depth == 0:
                j = i + m.end()
                break
        else:
            return body
        body = body[:i] + body[j:]


# The operator's own last run and the buttons that launch the operator's
# scripts. A friend's runs are on the board, and C1 has the demo's Run block.
OWN_RUN_BLOCKS = ('<div class="block runreport"', '<div class="block section results-first"',
                  '<div class="block leadjob"')


def strip_code(body: str) -> str:
    """Everything that shows code, a command, a script or a job of the served page."""
    # The two code listings at the foot of every panel, and the hidden target
    # of Show all code. Each is a block from its heading to the next block.
    for title in ("Run code", "The workflow"):
        body = re.sub(r'<div class="block"[^>]*>\s*<h3[^>]*>' + title + r'</h3>.*?(?=<div class="block"|</section>|$)',
                      "", body, flags=re.S)
    body = re.sub(r'<div class="block" id="workflowcode" hidden>.*?</div>', "", body, flags=re.S)
    # Job forms, their blocks, the console and its Output block: they launch
    # scripts on the operator's machine. C1 gets the demo's own Run block.
    body = re.sub(r'<div class="block">\s*<h3>[^<]*</h3>\s*<p class="note"[^>]*>.*?</p>\s*'
                  r'<form class="runform".*?</form>\s*</div>', "", body, flags=re.S)
    body = re.sub(r'<form class="runform".*?</form>', "", body, flags=re.S)
    body = re.sub(r'<div class="block">\s*<h3>Output</h3>.*?<p class="note"[^>]*>.*?</p>\s*</div>',
                  "", body, flags=re.S)
    body = re.sub(r'<div class="console".*?</div>', "", body, flags=re.S)
    body = re.sub(r"<pre\b.*?</pre>", "", body, flags=re.S)
    body = re.sub(r"<code\b[^>]*>(.*?)</code>", r"\1", body, flags=re.S)
    body = re.sub(r'<button[^>]*>\s*Show all code\s*</button>', "", body, flags=re.S)
    body = re.sub(r'<a[^>]*>\s*Show all code\s*</a>', "", body, flags=re.S)
    # Buttons that only the served page can act on. Save stays; the page's own
    # script keeps it in the browser. Load best as defaults stays too.
    body = re.sub(r'<button(?![^>]*\b(?:loadrec|saveall-btn)\b)[^>]*>.*?</button>', "", body, flags=re.S)
    # Links into the served page are dead on a static site.
    body = re.sub(r'<a href="/(?:record|file|card)/[^"]*">(.*?)</a>', r"\1", body, flags=re.S)
    for opening in OWN_RUN_BLOCKS:
        body = drop_blocks(body, opening)
    # Settings the served page reveals by script once a model is ticked.
    body = re.sub(r'(<form class="cfgform".*?</form>)',
                  lambda m: m.group(1).replace(" hidden>", ">").replace(" hidden ", " "),
                  body, flags=re.S)
    return body


# The Run block sits on the front page, B2 and C1, operator request 25
# September 2026, so it is marked by class, and the script drives every copy.
RUN_BLOCK = """
<div class="block demo-run">
  <h3>Run your model</h3>
  <p class="note">Sends your saved settings, trains your model on fresh prices and issues a paper
  ticket per coin or stock, in about five minutes. Nothing is bought or sold.</p>
  <div class="demo-row">
    <input class="demo-name" type="text" maxlength="40" aria-label="Your name"
           placeholder="Your name, shown beside your tickets">
    <button class="btn demo-go" type="button">Run Model</button>
  </div>
  <p class="note demo-status"></p>
  <p class="note"><a class="demo-results" href="#panel-C2">See results and paper tickets</a></p>
</div>
"""

# Three presets at the start of every page, operator request 25 September
# 2026, so a friend can fill every setting in one tap and run. The buttons are
# written here and filled by the script from window.__PRESETS__.
QUICK_BLOCK = """
<div class="block demo-quick">
  <h3>Quick start</h3>
  <p class="note">Choose crypto or US stocks on <a href="#panel-A1">A1</a>, pick a preset to fill every
  setting, then press Run Model{where}.</p>
  <div class="demo-presets">{buttons}</div>
  <p class="note demo-blurb"></p>
</div>
"""


def quick_block(where: str) -> str:
    buttons = "".join(f'<button class="btn demo-preset" type="button" data-preset="{k}">{p["label"]}</button>'
                      for k, p in presets().items())
    return QUICK_BLOCK.format(where=where, buttons=buttons)


def _flat(cfg: dict) -> dict:
    """A configuration as {field name: value}, the names the forms carry."""
    out = {}
    for vals in cfg.values():
        if not isinstance(vals, dict):
            continue
        for k, v in vals.items():
            if k == "params" and isinstance(v, dict):
                for model, params in v.items():
                    out.update({f"{model}.{pk}": pv for pk, pv in (params or {}).items()})
            else:
                out[k] = v
    return out


def _for_demo(cfg: dict) -> dict:
    """A configuration cut to what a demo run offers, as demo_run.sanitize would."""
    import demo_run as dr
    d = cfg["data"]
    stocks = d.get("market") == "equity"
    d["market"] = "equity" if stocks else "crypto"
    if d.get("frame") not in (dr.STOCK_FRAMES if stocks else dr.FRAMES):
        d["frame"] = "1d" if stocks else "4h"
    syms = d["symbols"].split() if isinstance(d.get("symbols"), str) else list(d.get("symbols") or [])
    d["symbols"] = [s for s in syms if s.replace("/", "") in (dr.STOCKS if stocks else dr.COINS)]
    d["rows"] = min(int(d.get("rows") or dr.LIMITS["rows"]), dr.LIMITS["rows"])
    # Inside the demo's limits already, so a preset's run reports nothing held.
    sp, sel = cfg["split"], cfg["selection"]
    sp["repeats"] = min(int(sp.get("repeats") or 1), dr.LIMITS["repeats"])
    sp["boot_samples"] = min(int(sp.get("boot_samples") or 2), dr.LIMITS["boot_samples"])
    sel["sel_sample"] = min(max(int(sel.get("sel_sample") or 2000), 2000), dr.LIMITS["sel_sample"])
    sel["sel_folds"] = min(max(int(sel.get("sel_folds") or 3), 3), dr.LIMITS["sel_folds"])
    return cfg


def _coins(cfg: dict) -> str:
    names = [s.split("/")[0] for s in cfg["data"]["symbols"]]
    return ", ".join(names[:-1]) + " and " + names[-1] if len(names) > 1 else "".join(names)


_PRESETS: dict | None = None
OTHER_DATA = "Research used other data, so your run can score differently."


def presets() -> dict:
    """The three findings, operator's choice of 25 September 2026.

    Each is read from the record it comes from, so the numbers in its note are
    the record's: the best fit on record from bench_config.recommended, the
    best three-way run from the bench-3way records, and a quick configuration
    built on the library defaults.
    """
    global _PRESETS
    if _PRESETS is not None:
        return _PRESETS
    import copy
    import glob
    import json
    import bench_config as bc

    best, prov = bc.recommended()
    best = _for_demo(copy.deepcopy(best))

    top, n_three = None, 0
    for path in glob.glob(str(REPO / "04-outputs" / "AA-evals" / "*" / "bench-3way-*.json")):
        try:
            rec = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for row in rec.get("rows") or []:
            v = (row.get("blind") or {}).get("after_cost_top")
            n_three += v is not None
            if v is not None and (top is None or v > top[0]):
                top = (v, row["model"], rec)
    # The count C1's record states, from the same function, so the page gives
    # one number for the three-way research fits.
    import control_tables as ct
    n_three = (ct._three_way_standing() or {}).get("fits", n_three)
    three = copy.deepcopy(top[2]["config"])
    three["label"].update(kind="three-way", flat_band=top[2]["band"])
    three["model"].update(estimators=[top[1]], params={}, tune="")
    three = _for_demo(three)

    quick = bc.defaults()
    quick["data"].update(frame="4h", symbols="BTC/USDT ETH/USDT SOL/USDT", rows=8000)
    quick["selection"]["run_selection"] = False
    quick["split"].update(scheme="expanding", folds=3)
    quick["model"].update(estimators=["LogReg.enet"], class_weight="none", params={}, tune="")
    quick = _for_demo(quick)

    # The stock twin of each preset, operator's choice of 26 September 2026:
    # the same learner, weighting and training setup, on what stocks require,
    # daily bars, the stock screen and the stock pipeline's own trade of +3
    # against -1 ATR within 20 trading days (build_dataset_equity.FRAMES).
    def stock(cfg):
        s = copy.deepcopy(cfg)
        s["data"].update(market="equity", frame="1d", symbols="AAPL MSFT NVDA")
        s["label"].update(target_atr=3.0, stop_atr=1.0, horizon_bars=20)
        s["screen"].update(atr_low=0.01, atr_high=0.08, min_quote_volume=20_000_000.0)
        return _for_demo(s)

    def stock_blurb(cfg, what):
        return (f"The crypto preset's {what} on daily bars of {_coins(cfg)}, each trade held up to "
                f"{cfg['label']['horizon_bars']} trading days. No stock result for it yet.")

    bars = {"1h": "1-hour", "4h": "4-hour", "1d": "daily"}
    names = {"RF": "Random forest", "LogReg.glm": "Logistic regression",
             "LogReg.enet": "Elastic-net logistic regression"}
    sb, st, sq = stock(best), stock(three), stock(quick)
    _PRESETS = {
        # Settings and the reason each was chosen, never a score the demo has
        # not reproduced; operator's choice of 26 September 2026. Quick and
        # simple rests on the six-learner comparison without class weighting,
        # 04-outputs/AA-evals/2026-09-16/bench-sweep-20260916-062912.json.
        "best": dict(label="Best on record", flat=_flat(best), stock=_flat(sb),
                     stock_blurb=stock_blurb(sb, "random forest"), blurb=(
            f"{names.get(best['model']['estimators'][0], best['model']['estimators'][0])} on "
            f"{bars[best['data']['frame']]} bars of {_coins(best)}. Chosen because in research it had "
            f"the lowest error on unseen data of the {prov.get('n_passing', 0):,} fits, out of "
            f"{prov.get('n_fits', 0):,}, that passed the overfit check. {OTHER_DATA}")),
        "threeway": dict(label="Three-way outcome", flat=_flat(three), stock=_flat(st),
                         stock_blurb=stock_blurb(st, "up, down or flat call"), blurb=(
            f"{names.get(top[1], top[1])} calls each {bars[three['data']['frame']]} bar up, down or flat over "
            f"the next {three['label']['horizon_bars']} bars, on {_coins(three)}. Chosen because its most "
            f"confident picks made the most after cost of the {n_three} three-way research fits. {OTHER_DATA}")),
        "quick": dict(label="Quick and simple", flat=_flat(quick), stock=_flat(sq),
                      stock_blurb=stock_blurb(sq, "elastic-net logistic regression"), blurb=(
            f"{names['LogReg.enet']} on {_coins(quick)}, the latest {quick['data']['rows']:,} "
            f"{bars[quick['data']['frame']]} candles, trained in time order. Chosen because it had the "
            f"lowest error on unseen data of the six learners compared in research on 16 September. "
            f"{OTHER_DATA}")),
    }
    return _PRESETS

# C2, operator review of 25 September 2026. A visitor arrives here after a
# run, so the page opens on what it is for and on the results, carries no
# presets, and keeps the operator's own research folded shut at the foot. The
# stock account, the long tables and the evidence log are left to the served
# board, where they belong.
C2_GUIDE = """
<div class="block demo-guide">
  <h3>About this page</h3>
  <p>Your results are here. Paper tickets, just below, lists every run by every friend, newest
  first, with yours highlighted.</p>
  <p>Each run rates every coin or stock it was given. BUY means the model ranked it among its best
  and expected it to pay; PASS means it did not. Every ticket is then followed on real prices until
  it reaches its target, its stop or its due time, and After cost shows the result less trading
  cost, 0.20 per cent for crypto and 0.10 per cent for stocks. An open ticket has no result yet. Nothing is bought or sold.</p>
  <p>The Performance Log at the foot of the page is the operator's own research, folded shut. It is
  not your run.</p>
  <p class="note">To run again, go to <a href="#panel-B2">B2</a> or <a href="#panel-C1">C1</a>
  and press Run Model.</p>
</div>
"""

# The four scores the Model scores chart can show, one at a time on one axis.
METRICS = [
    ("rmse", "RMSE", "Root mean squared error of the predicted chance of a win on the test year, in "
     "percentage points. Lower is better."),
    ("mae", "MAE", "Mean absolute error of the predicted chance of a win on the test year, in "
     "percentage points. Lower is better."),
    ("u2", "Theil's U2", "RMSE on the test year divided by the RMSE of always predicting the average "
     "outcome. Below 1 beats that constant guess."),
    ("ratio", "Overfit ratio", "Cross-validated RMSE divided by training RMSE. Above 1.1 the model "
     "has fitted noise in its training data and is rejected."),
]

DICTIONARY = """
<div class="demo-dict">
  <h4>What the columns mean</h4>
  <dl>
    <dt>Issued</dt><dd>when the run rated it, Pacific time</dd>
    <dt>Symbol</dt><dd>the coin or stock rated</dd>
    <dt>Timeframe</dt><dd>the length of one price candle the model read</dd>
    <dt>Call</dt><dd>BUY or PASS, as above</dd>
    <dt>Score</dt><dd>the model's rating, higher is stronger</dd>
    <dt>Entry</dt><dd>the price at the close of the rated candle, where the paper trade starts</dd>
    <dt>Due</dt><dd>when the ticket closes if it reaches neither its target nor its stop</dd>
    <dt>Result</dt><dd>target, stop or time, whichever came first, or open</dd>
    <dt>After cost</dt><dd>the ticket's return less trading cost, 0.20 per cent for crypto and 0.10 for stocks</dd>
    <dt>Model</dt><dd>the learner the run chose; RMSE and Theil's U2 as in Model scores</dd>
  </dl>
</div>
"""

BOARD = """
<div class="block demo-board" id="demo-board">
  <h3>Paper tickets</h3>
  <div id="demo-totals" class="demo-totals">Loading.</div>
  <details class="demo-counts"><summary>Runs and open tickets</summary><p class="note" id="demo-counts"></p></details>
  <div class="demo-charts">
    <div class="demo-chart"><h4>Picks against passes</h4>
      <p class="note">Running total after cost of every settled ticket, what the models picked against what they passed on.</p>
      <div id="demo-chart-pay"></div><p class="note demo-empty" id="demo-empty-pay"></p></div>
    <div class="demo-chart"><h4>Model scores</h4>
      <div class="demo-metrics">__METRIC_BUTTONS__</div>
      <p class="note" id="demo-metric-note"></p>
      <div id="demo-chart-runs"></div><p class="note demo-empty" id="demo-empty-runs"></p></div>
    <div class="demo-chart"><h4>What carries the book</h4>
      <div class="demo-metrics"><button class="btn demo-carry on" type="button" data-carry="model">By model</button><button class="btn demo-carry" type="button" data-carry="symbol">By coin or stock</button></div>
      <p class="note">Total after cost of every settled BUY ticket. Bars to the right carried the book; bars to the left dragged it.</p>
      <div id="demo-chart-carry"></div><p class="note demo-empty" id="demo-empty-carry"></p></div>
  </div>
  __DICTIONARY__
  <div class="demo-tables" id="demo-tables" hidden>
    <div><h4>Tickets</h4><div id="demo-tickets"></div>
      <button class="btn demo-more" type="button" data-table="tickets" hidden>Show all</button></div>
    <div><h4>Runs</h4><div id="demo-runs"></div>
      <button class="btn demo-more" type="button" data-table="runs" hidden>Show all</button></div>
  </div>
</div>
""".replace("__METRIC_BUTTONS__", "".join(
    f'<button class="btn demo-metric" type="button" data-metric="{k}">{label}</button>'
    for k, label, _ in METRICS)).replace("__DICTIONARY__", DICTIONARY)

REPO_URL = "https://github.com/seamusrobertmurphy/swing-trader"

RESEARCH_FOLD = """
<details class="block demo-research">
  <summary>Performance Log</summary>
  <p>__FITS__ research fits scored by the operator, plus <span id="demo-count-runs">0</span>
  runs by new users, and counting. The bars in Model scores are the research fits.</p>
  <p>The operator's own paper account of US stocks is reported every trading day by a scheduled
  job, one file a day named DAILY with its date, kept on GitHub in
  <a href="__REPO__/tree/main/04-outputs/AA-evals" target="_blank" rel="noopener">04-outputs/AA-evals</a>,
  where any report can be opened or downloaded.</p>
  <p>The chart below marks the milestones, the points where the model design, the data or the
  workflow changed, as diamonds over the research runs a day. What each change found is in the
  <a href="__REPO__#findings" target="_blank" rel="noopener">Findings section of the README</a>.</p>
  __LIVEBOOK__
</details>
""".replace("__REPO__", REPO_URL)


def take_block(body: str, opening: str) -> str:
    """The div that starts with `opening`, with everything nested in it."""
    i = body.find(opening)
    if i < 0:
        return ""
    depth = 0
    for m in re.finditer(r"<div\b|</div>", body[i:]):
        depth += 1 if m.group(0) == "<div" else -1
        if depth == 0:
            return body[i:i + m.end()]
    return ""


def research_fits() -> list:
    """Every scored research fit as [when, model, rmse, mae, u2, ratio].

    Read from the same bench records, in the same way, as the scoreboard on
    the served board, so the grey dots are the scoreboard's rows.
    """
    import control_tables as ct
    out = []
    for doc in ct._docs("*/bench-sweep-*.json") + ct._docs("*/bench-2*.json"):
        when = str(doc.get("stamped", ""))[:16].replace("T", " ")
        for r in (doc.get("rows") or doc.get("scores") or []):
            b = r.get("blind") or {}
            if not isinstance(r.get("cv"), dict) or "rmse" not in r["cv"] or b.get("rmse") is None:
                continue
            nums = [b.get("rmse"), b.get("mae"), b.get("theil_u2"), r.get("rmse_ratio")]
            out.append([when, r.get("model", "")] +
                       [round(float(v), 4) if isinstance(v, (int, float)) else None for v in nums])
    return sorted(out)


def c2_page(chunk: str) -> str:
    """C2 as the demo shows it: guide, tickets, charts, dictionary, research folded."""
    m = re.search(r'<div class="interactive-block">\s*<h4[^>]*>Live book</h4>', chunk)
    live = take_block(chunk, m.group(0)).replace(">Live book</h4>", ">Milestones</h4>") if m else ""
    fold = RESEARCH_FOLD.replace("__FITS__", f"{len(research_fits()):,}").replace("__LIVEBOOK__", live)
    return C2_GUIDE + BOARD + fold


DEMO_CSS = """
.demo-run, .demo-board { border:1px solid #c3cedb; border-top:3px solid #0e7a5f; padding:6px 10px; margin:6px 0; background:#fff; }
.demo-board h3 { margin:0 0 2px 0; }
.demo-board .note { margin:0 0 4px 0; }
.demo-totals { margin:2px 0 !important; }
.demo-totals div { padding:3px 8px !important; }
.demo-totals b { font-size:14px !important; }
.demo-row { display:flex; gap:8px; align-items:center; margin:8px 0; }
.demo-row input { flex:0 1 260px; padding:4px 6px; }
.demo-totals { display:flex; flex-wrap:wrap; gap:10px; margin:8px 0; }
.demo-totals div { background:#e8eef4; border-radius:3px; padding:6px 10px; min-width:120px; }
.demo-totals b { display:block; font-size:18px; color:#0b2038; }
.demo-tables { display:grid; grid-template-columns:3fr 2fr; gap:14px; }
.demo-tables[hidden] { display:none; }
.demo-tables table { width:100%; border-collapse:collapse; font-size:12px; }
.demo-tables th, .demo-tables td { padding:3px 5px; border-bottom:1px solid #e3e9ef; text-align:left; white-space:nowrap; }
.demo-tables .mine td { background:#fff7df; }
.demo-tables .pos { color:#0e7a5f; font-weight:700; } .demo-tables .neg { color:#a01c1c; font-weight:700; }
.demo-scroll { max-height:420px; overflow:auto; }
@media (max-width: 900px) { .demo-tables { grid-template-columns:1fr; } }
.saved.demo-ok { color:#0e7a5f; font-weight:700; }
/* Operator, 24 September 2026: too much height above the six panels. The
   second row of A1 to C2 arrows repeated the steps the title bar can carry,
   so the front page shows them in the title bar and drops the row, and the
   timeline band is held lower. */
.sheet.front > .flow { display:none; }
.sheet.front .flowbar { display:flex; }
.topband { height:5vh; min-height:40px; max-height:56px; }
/* Quick start, the Run block on three pages, and fewer settings, operator
   request 25 September 2026. A model's own settings show only while it is
   ticked, and a row whose settings were all removed gives its table the
   full width. */
.demo-presets { display:flex; flex-wrap:wrap; gap:8px; margin:8px 0 4px 0; }
.demo-blurb:empty { display:none; }
.demo-front { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin:4px 0 8px 0; flex:0 0 auto; }
.demo-front > .block { margin:0 !important; }
/* The front page's own Quick start and Run block belong to the grid, so they
   leave with it when a panel opens; each panel carries its own. */
.sheet:not(.front) .demo-front { display:none !important; }
/* The two charts above the tickets, operator request 25 September 2026. */
.demo-charts { display:grid; grid-template-columns:1fr 1fr; gap:14px; margin:6px 0 12px 0; }
.demo-chart h4 { margin:4px 0 2px 0; }
.demo-chart .note { margin:0 0 4px 0; }
.demo-empty:empty { display:none; }
.demo-metrics { display:flex; flex-wrap:wrap; gap:6px; margin:4px 0; }
.demo-metric { padding:5px 12px !important; font-size:12.5px !important; }
.demo-metric.on { background:#fbf6ea !important; box-shadow:inset 0 0 0 2px #c99a2e; }
.demo-dict { margin:6px 0 10px 0; }
.demo-dict h4 { margin:4px 0; }
.demo-dict dl { display:grid; grid-template-columns:max-content 1fr; gap:2px 12px; margin:0; font-size:12.5px; }
.demo-dict dt { font-weight:700; } .demo-dict dd { margin:0; }
.demo-more { margin:6px 0 0 0; }
.demo-more[hidden] { display:none; }
details.demo-research > summary { cursor:pointer; font-weight:700; font-size:15px; padding:4px 0; }
details.demo-research p { font-size:13.5px; line-height:1.5; }
@media (max-width: 900px) { .demo-charts { grid-template-columns:1fr; } }
.demo-guide p { margin:0 0 6px 0; }
.hyperblock:not(.on) { display:none !important; }
.briefrow:not(:has(> .tools)) { grid-template-columns:1fr; }
.loadnote { margin-left:8px; font-size:12.5px; }
/* Revision tasks 9 and 10, 26 September 2026. A chart drawn while C2 was
   hidden took Plotly's default 700 px and stretched its grid column past a
   phone's edge, and iPhone Safari then enlarged the text in that over-wide
   block. Columns may now shrink, and Safari's text enlarging is off. */
html { -webkit-text-size-adjust:100%; text-size-adjust:100%; }
.demo-charts { grid-template-columns:repeat(auto-fit, minmax(300px, 1fr)); }
.demo-charts > * { min-width:0; overflow:hidden; }
.demo-chart .note { font-size:13.5px; line-height:1.5; }
.demo-totals div span { display:block; font-weight:600; }
.demo-totals div small { display:block; font-size:12.5px; color:#8a8378; margin-top:2px; max-width:240px; }
details.demo-counts { margin:0 0 6px 0; }
details.demo-counts > summary { cursor:pointer; font-size:13px; color:#2f6f62; }
@media (max-width: 900px) { .demo-charts { grid-template-columns:minmax(0, 1fr); } }
"""

DEMO_SCRIPT = r"""
<script>
(function(){
// On a phone each table row is shown as a card; every cell carries its
// column's name so the card can print it above the value.
function labelTables(){
  document.querySelectorAll('table').forEach(function(t){
    var head = t.querySelector('thead tr') || t.querySelector('tr');
    if (!head || !head.querySelector('th')) return;
    var names = Array.from(head.children).map(function(c){ return c.textContent.trim(); });
    t.querySelectorAll('tr').forEach(function(r){
      if (r === head) return;
      Array.from(r.children).forEach(function(c, i){ if (names[i]) c.setAttribute('data-label', names[i]); });
    });
  });
}
labelTables();
// Interactive figures are drawn at a fixed width; on a phone each is redrawn
// at the width of its box.
function fitFigures(){
  if (window.innerWidth > 760 || !window.Plotly) return;
  document.querySelectorAll('.js-plotly-plot').forEach(function(el){
    var w = el.parentElement && el.parentElement.clientWidth;
    if (w && Math.abs(el.clientWidth - w) > 4) Plotly.relayout(el, {width: w, autosize: false});
  });
}
window.addEventListener('load', fitFigures);
window.addEventListener('hashchange', function(){ setTimeout(fitFigures, 50); });
var RELAY = __RELAY__;
var KEY = 'swingtrader.demo.settings';
var MINE = 'swingtrader.demo.runs';
function store(k, v){ try{ localStorage.setItem(k, JSON.stringify(v)); }catch(e){} }
function fetchStore(k, d){ try{ return JSON.parse(localStorage.getItem(k)) || d; }catch(e){ return d; } }

// Every settings form on every panel, as {section: {field: value}}. A form
// posts only its own fields, so sections spread over several forms merge.
function collect(){
  var cfg = {};
  document.querySelectorAll('form.cfgform').forEach(function(f){
    var sec = f.getAttribute('data-section'); if(!sec) return;
    var out = cfg[sec] = cfg[sec] || {};
    f.querySelectorAll('input[name], select[name], textarea[name]').forEach(function(el){
      if (el.type === 'checkbox') { out[el.name] = el.checked ? 'on' : '0'; }
      else if (el.tagName === 'SELECT' && el.multiple) {
        out[el.name] = Array.from(el.selectedOptions).map(function(o){ return o.value; });
      } else { out[el.name] = el.value; }
    });
  });
  return cfg;
}
function restore(cfg){
  document.querySelectorAll('form.cfgform').forEach(function(f){
    var sec = cfg[f.getAttribute('data-section')]; if(!sec) return;
    f.querySelectorAll('input[name], select[name], textarea[name]').forEach(function(el){
      if (!(el.name in sec)) return;
      var v = sec[el.name];
      if (el.type === 'checkbox') el.checked = (v === 'on' || v === true);
      else if (el.tagName === 'SELECT' && el.multiple) Array.from(el.options).forEach(function(o){ o.selected = (v || []).indexOf(o.value) >= 0; });
      else el.value = v;
    });
  });
}
// Presets and Load best fit settings as defaults, operator request 25
// September 2026. BASE is every field as the page was built, so a preset
// starts from the same place whatever the visitor changed before it.
var PRESETS = window.__PRESETS__ || {};
var PKEY = 'swingtrader.demo.preset';
var NKEY = 'swingtrader.demo.name';
function flatNow(){
  var o = {};
  document.querySelectorAll('form.cfgform [name]').forEach(function(el){
    if (el.type === 'checkbox') o[el.name] = el.checked;
    else if (el.tagName === 'SELECT' && el.multiple) o[el.name] = Array.from(el.selectedOptions).map(function(x){ return x.value; });
    else o[el.name] = el.value;
  });
  return o;
}
// A single choice takes the value only if the list offers it, so a setting
// the demo does not carry leaves the box as it was rather than blank.
function pick(el, v){
  var want = typeof v === 'boolean' ? (v ? ['on', 'true', '1', 'yes'] : ['0', 'off', 'false', 'no']) : [String(v)];
  var opts = Array.from(el.options).map(function(o){ return o.value; });
  for (var i = 0; i < want.length; i++) if (opts.indexOf(want[i]) >= 0) { el.value = want[i]; return; }
}
function fill(flat){
  document.querySelectorAll('form.cfgform [name]').forEach(function(el){
    if (!(el.name in flat)) return;
    var v = flat[el.name];
    if (el.type === 'checkbox') el.checked = (v === true || v === 'on');
    else if (el.tagName === 'SELECT' && el.multiple) {
      var want = (Array.isArray(v) ? v : String(v).split(/\s+/)).map(String);
      Array.from(el.options).forEach(function(o){ o.selected = want.indexOf(o.value) >= 0; });
    } else if (el.tagName === 'SELECT') pick(el, v);
    else el.value = (v === null || v === undefined) ? '' : String(v);
  });
  syncMarket(asList(flat.symbols));
  syncModels();
}
// Only the ticked models show their own settings.
function syncModels(){
  var sel = document.querySelector('form.cfgform select[name="estimators"]');
  if (!sel) return;
  var on = Array.from(sel.selectedOptions).map(function(o){ return o.value; });
  document.querySelectorAll('.hyperblock[data-model]').forEach(function(b){
    b.classList.toggle('on', on.indexOf(b.getAttribute('data-model')) >= 0);
  });
}
// Crypto or US stocks, 26 September 2026. The symbol list and the timeframes
// follow the market, and stocks run on daily bars only, as the runner does.
var UNIVERSE = window.__UNIVERSE__ || {};
var DEFAULTS = {crypto: ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'], equity: ['AAPL', 'MSFT', 'NVDA']};
function syncMarket(prefer){
  var m = document.querySelector('form.cfgform select[name="market"]');
  var sy = document.querySelector('form.cfgform select[name="symbols"]');
  var fr = document.querySelector('form.cfgform select[name="frame"]');
  if (!m || !sy) return;
  var mk = m.value === 'equity' ? 'equity' : 'crypto', list = UNIVERSE[mk] || [];
  var want = (prefer || Array.from(sy.selectedOptions).map(function(o){ return o.value; }))
    .filter(function(v){ return list.indexOf(v) >= 0; });
  if (!want.length) want = DEFAULTS[mk];
  if (sy.getAttribute('data-market') !== mk) {
    sy.innerHTML = list.map(function(v){ return '<option value="' + v + '">' + v + '</option>'; }).join('');
    sy.setAttribute('data-market', mk);
  }
  Array.from(sy.options).forEach(function(o){ o.selected = want.indexOf(o.value) >= 0; });
  if (fr) {
    Array.from(fr.options).forEach(function(o){ o.disabled = mk === 'equity' && o.value !== '1d'; });
    if (mk === 'equity') fr.value = '1d';
  }
  var bundle = document.querySelector('form.cfgform select[name="bundle"]');
  var bf = bundle && bundle.closest('.field');
  if (bf) bf.style.display = mk === 'equity' ? 'none' : '';
}
function asList(v){ return v == null ? null : (Array.isArray(v) ? v : String(v).split(/\s+/).filter(Boolean)); }
// Each preset has a crypto and a stock version, and the Market box decides
// which one a tap applies, operator's choice of 26 September 2026.
function onStocks(){ var m = document.querySelector('form.cfgform select[name="market"]'); return !!m && m.value === 'equity'; }
function markPreset(key){
  document.querySelectorAll('.demo-preset').forEach(function(b){ b.classList.toggle('on', b.getAttribute('data-preset') === key); });
  var p = PRESETS[key];
  document.querySelectorAll('.demo-blurb').forEach(function(s){
    s.textContent = p ? (onStocks() ? p.stock_blurb : p.blurb) + ' Filled and saved.' : ''; });
}
function applyPreset(key){
  var p = PRESETS[key]; if (!p) return;
  var stocks = onStocks();
  fill(BASE); fill(stocks ? p.stock : p.flat);
  store(KEY, collect()); store(PKEY, key);
  markPreset(key);
}
var BASE = flatNow();
var SAVED = fetchStore(KEY, {});
restore(SAVED);
syncMarket(asList((SAVED.data || {}).symbols));
syncModels();
// With a preset on, changing the market applies that preset's twin.
document.querySelectorAll('form.cfgform select[name="market"]').forEach(function(s){
  s.addEventListener('change', function(){
    var k = fetchStore(PKEY, '');
    if (k && PRESETS[k]) applyPreset(k); else syncMarket(null);
  });
});
markPreset(fetchStore(PKEY, ''));
document.querySelectorAll('.demo-preset').forEach(function(b){
  b.addEventListener('click', function(){ applyPreset(b.getAttribute('data-preset')); });
});
document.querySelectorAll('.loadrec').forEach(function(b){
  b.addEventListener('click', function(){
    applyPreset('best');
    var n = b.parentElement && b.parentElement.querySelector('.loadnote');
    if (n) n.textContent = 'Loaded and saved. Skip ahead to B2 or C1 and press Run Model.';
  });
});
document.querySelectorAll('select[name="estimators"]').forEach(function(s){ s.addEventListener('change', syncModels); });
document.querySelectorAll('form.cfgform').forEach(function(f){
  f.addEventListener('submit', function(ev){
    ev.preventDefault();
    store(KEY, collect()); store(PKEY, ''); markPreset('');
    document.querySelectorAll('.saved').forEach(function(s){ s.textContent = ''; });
    var s = f.querySelector('.saved');
    if (s) { s.textContent = 'Saved in this browser.'; s.classList.add('demo-ok'); }
  });
});

function pct(v){ return (v === null || v === undefined) ? '' : ((v >= 0 ? '+' : '') + (v * 100).toFixed(2) + '%'); }
function esc(s){ return String(s == null ? '' : s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
// Times are shown in Pacific time, operator request 25 September 2026; the
// records keep UTC. A stamp without a zone is read as UTC.
function utc(s){ return /[zZ]|[+-]\d\d:?\d\d$/.test(s) ? s : s + 'Z'; }
function when(s){
  if (!s) return '';
  var d = new Date(utc(s)); if (isNaN(d)) return s.replace('T', ' ').slice(0, 16);
  return d.toLocaleString('en-CA', {timeZone: 'America/Vancouver', month: 'short', day: 'numeric',
                                    hour: '2-digit', minute: '2-digit', hour12: false, timeZoneName: 'short'});
}
// The same moment as a plain Pacific stamp, for a chart axis.
function pt(s){
  var d = new Date(utc(s)); if (isNaN(d)) return s;
  return d.toLocaleString('sv-SE', {timeZone: 'America/Vancouver', hour12: false}).slice(0, 16);
}

// The two charts above the tickets. Blue and orange passed the colour-blind
// and contrast checks on the white card; the page's own green read as grey.
var BLUE = '#1f6fb2', ORANGE = '#c9772e', INK = '#32302f', MUTED = '#8a8378', GRID = '#eeeae4';
function day(s){ return s ? s.slice(0, 10) : ''; }
function plotBase(ytitle){
  return {height: 230, margin: {l: 48, r: 12, t: 8, b: 36}, dragmode: false, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
          font: {family: 'Jost, Helvetica Neue, Arial, sans-serif', size: 12, color: INK}, showlegend: true,
          legend: {orientation: 'h', x: 0, y: 1.12, font: {size: 12}},
          xaxis: {gridcolor: GRID, linecolor: GRID, tickfont: {color: MUTED}, type: 'date', fixedrange: true},
          yaxis: {fixedrange: true, gridcolor: GRID, zerolinecolor: MUTED, tickfont: {color: MUTED}, title: {text: ytitle, font: {size: 11, color: MUTED}}},
          hoverlabel: {bgcolor: '#ffffff', bordercolor: GRID, font: {color: INK}}};
}
// No zoom or pan: on a phone a touch zoomed in on nothing and lost the reader.
var PCONF = {displayModeBar: false, responsive: true, scrollZoom: false, doubleClick: false};
function drawCharts(ix, mine){
  if (!window.Plotly) return;
  var pay = document.getElementById('demo-chart-pay'), runs = document.getElementById('demo-chart-runs');
  if (!pay || !runs) return;
  var done = (ix.tickets || []).filter(function(x){ return x.status === 'settled' && x.after_cost != null; })
    .sort(function(a, c){ return (a.due || '').localeCompare(c.due || ''); });
  if (!done.length) {
    var open = (ix.tickets || []).map(function(x){ return x.due; }).filter(Boolean).sort();
    pay.style.display = 'none';
    document.getElementById('demo-empty-pay').textContent = open.length ?
      'No ticket has settled yet. The first is due ' + when(open[0]) + ', and this chart fills in from then.' :
      'No tickets yet. Run a model to add the first.';
  } else {
    pay.style.display = ''; document.getElementById('demo-empty-pay').textContent = '';
    var traces = [['BUY', 'Picked (BUY)', BLUE], ['PASS', 'Passed on (PASS)', ORANGE]].map(function(s){
      var sum = 0, xs = [], ys = [], tip = [];
      done.filter(function(x){ return x.call === s[0]; }).forEach(function(x){
        sum += x.after_cost * 100; xs.push(pt(x.due)); ys.push(sum);
        tip.push(esc(x.symbol) + ', ' + esc(x.name || 'no name') + ', ' + pct(x.after_cost) + ' after cost');
      });
      return {x: xs, y: ys, name: s[1], mode: 'lines+markers', line: {color: s[2], width: 2, shape: 'hv'},
              marker: {size: 8, color: s[2], line: {color: '#ffffff', width: 2}}, text: tip,
              hovertemplate: '%{text}<br>Running total %{y:.2f}%<extra>' + s[1] + '</extra>'};
    });
    var lp = plotBase('Running total, % after cost');
    lp.shapes = [{type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 0, y1: 0, line: {color: MUTED, width: 1}}];
    Plotly.react(pay, traces, lp, PCONF);
  }
  LAST = [ix, mine];
  drawScores(ix, mine);
  drawCarry(ix);
}
// Model scores, revision task 11 of 26 September 2026: one bar a learner,
// the median of the research fits on the chosen metric, best at the top,
// coloured by the kind of model. Each run by a new user is a dot on its
// learner's bar, orange for the visitor's own.
var METRICS = window.__METRICS__ || [], RESEARCH = window.__RESEARCH__ || [];
var FIELD = {rmse: 'blind_rmse', mae: 'blind_mae', u2: 'blind_u2', ratio: 'ratio'};
var COL = {rmse: 2, mae: 3, u2: 4, ratio: 5};
var REF = {u2: [1, 'Constant guess'], ratio: [1.1, 'Overfit limit']};
var METRIC = 'u2', LAST = null;
var KIND = {'LogReg.glm': 'Logistic', 'LogReg.enet': 'Logistic', 'RF': 'Forest', 'rf': 'Forest',
            'LightGBM': 'Boosted trees', 'HistGBM': 'Boosted trees', 'GBM.classic': 'Boosted trees'};
var KINDCOL = {'Logistic': BLUE, 'Forest': '#2f7d62', 'Boosted trees': '#7a4fa0', 'Other': MUTED};
var NAME = {'LogReg.glm': 'Logistic regression', 'LogReg.enet': 'Elastic-net logistic', 'RF': 'Random forest',
            'rf': 'Random forest', 'LightGBM': 'LightGBM', 'HistGBM': 'Histogram boosting', 'GBM.classic': 'Gradient boosting'};
function kindOf(m){ return KIND[m] || 'Other'; }
function nameOf(m){ return NAME[m] || m || 'unknown'; }
function median(a){ a = a.slice().sort(function(x, y){ return x - y; }); var n = a.length;
  return n ? (n % 2 ? a[(n - 1) / 2] : (a[n / 2 - 1] + a[n / 2]) / 2) : null; }
function fmt(k, v){ return k === 'rmse' || k === 'mae' ? (v * 100).toFixed(1) : v.toFixed(k === 'ratio' ? 2 : 3); }
// Horizontal bars share one layout: the page's type, grid and hover, the
// categories in the order given, first at the bottom.
function barBase(xtitle, cats){
  var l = plotBase(xtitle);
  l.height = Math.max(170, 96 + 38 * cats.length); l.margin = {l: 8, r: 16, t: 22, b: 40};
  l.barmode = 'overlay'; l.bargap = 0.35;
  // Under the axis title: 56 px below the plot, as a share of the plot's height.
  l.legend = {orientation: 'h', x: 0, y: -56 / (l.height - 62), yanchor: 'top', font: {size: 11}};
  l.xaxis = {fixedrange: true, gridcolor: GRID, zerolinecolor: MUTED, tickfont: {color: MUTED},
             title: {text: xtitle, font: {size: 11, color: MUTED}}};
  l.yaxis = {fixedrange: true, automargin: true, type: 'category', categoryorder: 'array', categoryarray: cats,
             tickfont: {color: INK, size: 12}};
  return l;
}
function drawScores(ix, mine){
  var runs = document.getElementById('demo-chart-runs'); if (!runs || !window.Plotly) return;
  var k = METRIC, meta = METRICS.filter(function(m){ return m[0] === k; })[0] || [k, k, ''];
  document.getElementById('demo-metric-note').textContent = meta[2] + ' Each bar is the median of the research fits of one model; the count is in brackets.';
  document.querySelectorAll('.demo-metric').forEach(function(b){ b.classList.toggle('on', b.getAttribute('data-metric') === k); });
  var scale = (k === 'rmse' || k === 'mae') ? 100 : 1, groups = {};
  RESEARCH.forEach(function(r){
    var v = r[COL[k]]; if (v == null) return;
    var n = nameOf(r[1]); (groups[n] = groups[n] || {kind: kindOf(r[1]), vals: []}).vals.push(v * scale);
  });
  var scored = (ix.runs || []).filter(function(r){ return r.status === 'done' && r[FIELD[k]] != null; });
  scored.forEach(function(r){ var n = nameOf(r.chosen); groups[n] = groups[n] || {kind: kindOf(r.chosen), vals: []}; });
  // Worst first, so the best, the lowest on every one of the four, is on top.
  var order = Object.keys(groups).map(function(n){ return [n, median(groups[n].vals)]; })
    .sort(function(a, c){ return (c[1] == null ? -1e9 : c[1]) - (a[1] == null ? -1e9 : a[1]); });
  // The value sits in the label, where a run's dot cannot cover it.
  var label = {}; order.forEach(function(o){
    label[o[0]] = o[0] + ' (' + groups[o[0]].vals.length + ')<br>' + (o[1] == null ? 'no research fit' : fmt(k, o[1] / scale));
  });
  // Theil's U2 and the overfit ratio run either side of their reference line,
  // so a bar to the left beats the constant guess or sits under the limit.
  var base = REF[k] ? REF[k][0] : 0;
  var cats = order.map(function(o){ return label[o[0]]; }), traces = [];
  ['Logistic', 'Forest', 'Boosted trees', 'Other'].forEach(function(kd){
    var rows = order.filter(function(o){ return groups[o[0]].kind === kd && o[1] != null; });
    if (!rows.length) return;
    traces.push({type: 'bar', orientation: 'h', name: kd, marker: {color: KINDCOL[kd]},
                 base: base, x: rows.map(function(o){ return o[1] - base; }), y: rows.map(function(o){ return label[o[0]]; }),
                 customdata: rows.map(function(o){ return fmt(k, o[1] / scale); }),
                 hovertemplate: 'median ' + meta[1] + ' %{customdata}<extra>' + kd + '</extra>'});
  });
  [[false, "New users' runs", INK], [true, 'Your runs', ORANGE]].forEach(function(g){
    var rs = scored.filter(function(r){ return (mine.indexOf(r.run_id) >= 0) === g[0]; });
    if (!rs.length) return;
    traces.push({type: 'scatter', mode: 'markers', name: g[1], x: rs.map(function(r){ return r[FIELD[k]] * scale; }),
                 y: rs.map(function(r){ return label[nameOf(r.chosen)]; }),
                 marker: {size: 11, color: g[2], line: {color: '#ffffff', width: 2}},
                 customdata: rs.map(function(r){ return esc(r.name || 'no name') + ' on ' + esc((r.symbols || '').replace(/USDT/g, '')); }),
                 hovertemplate: '%{customdata}<br>' + meta[1] + ' %{x:.3f}<extra></extra>'});
  });
  document.getElementById('demo-empty-runs').textContent = cats.length ? '' : 'No model has recorded ' + meta[1] + ' yet.';
  var lr = barBase(meta[1] + (scale === 100 ? ', percentage points' : ''), cats);
  if (REF[k]) {
    lr.shapes = [{type: 'line', yref: 'paper', y0: 0, y1: 1, x0: REF[k][0], x1: REF[k][0], line: {color: MUTED, width: 1, dash: 'dash'}}];
    lr.annotations = [{yref: 'paper', y: 1, x: REF[k][0], xanchor: 'left', yanchor: 'bottom', showarrow: false,
                       text: REF[k][1], font: {size: 11, color: MUTED}}];
  }
  Plotly.react(runs, traces, lr, PCONF);
}
// What carries the book, revision task 14: the total after cost of every
// settled BUY ticket, by model or by coin, largest on top, in the Model
// scores colours. A coin takes the colour of the kind of model that bought it
// most often.
var CARRY = 'model';
function drawCarry(ix){
  var el = document.getElementById('demo-chart-carry'), empty = document.getElementById('demo-empty-carry');
  if (!el || !window.Plotly) return;
  document.querySelectorAll('.demo-carry').forEach(function(b){ b.classList.toggle('on', b.getAttribute('data-carry') === CARRY); });
  var done = (ix.tickets || []).filter(function(x){ return x.status === 'settled' && x.after_cost != null && x.call === 'BUY'; });
  if (!done.length) { el.style.display = 'none'; empty.textContent = 'No BUY ticket has settled yet, so nothing has carried or dragged the book so far.'; return; }
  el.style.display = ''; empty.textContent = '';
  var sums = {};
  done.forEach(function(x){
    var key = CARRY === 'model' ? nameOf(x.model) : x.symbol, s = sums[key] = sums[key] || {v: 0, n: 0, kinds: {}};
    s.v += x.after_cost * 100; s.n += 1; s.kinds[kindOf(x.model)] = (s.kinds[kindOf(x.model)] || 0) + 1;
  });
  var order = Object.keys(sums).sort(function(a, c){ return sums[a].v - sums[c].v; });
  var kindTop = function(s){ return Object.keys(s.kinds).sort(function(a, c){ return s.kinds[c] - s.kinds[a]; })[0]; };
  var cats = order.map(function(n){ return n + ' (' + sums[n].n + ')'; });
  var tr = {type: 'bar', orientation: 'h', x: order.map(function(n){ return sums[n].v; }), y: cats, showlegend: false,
            marker: {color: order.map(function(n){ return KINDCOL[kindTop(sums[n])]; })},
            text: order.map(function(n){ return (sums[n].v >= 0 ? '+' : '') + sums[n].v.toFixed(2) + '%'; }),
            textposition: 'outside', cliponaxis: false, textfont: {size: 11, color: INK},
            hovertemplate: '%{y}<br>total %{x:.2f}% after cost<extra></extra>'};
  var l = barBase('Total after cost, per cent', cats);
  l.showlegend = false;
  l.shapes = [{type: 'line', yref: 'paper', y0: 0, y1: 1, x0: 0, x1: 0, line: {color: MUTED, width: 1}}];
  Plotly.react(el, [tr], l, PCONF);
}
document.querySelectorAll('.demo-carry').forEach(function(b){
  b.addEventListener('click', function(){ CARRY = b.getAttribute('data-carry'); if (LAST) drawCarry(LAST[0]); });
});document.querySelectorAll('.demo-metric').forEach(function(b){
  b.addEventListener('click', function(){ METRIC = b.getAttribute('data-metric'); if (LAST) drawScores(LAST[0], LAST[1]); });
});
// A chart inside the folded Performance Log is drawn at no width; it is
// resized when the fold opens, and given the type, grid and hover of the
// charts above so the top and foot of the page read alike (revision task 13).
document.querySelectorAll('details.demo-research').forEach(function(d){
  d.addEventListener('toggle', function(){
    if (d.open && window.Plotly) d.querySelectorAll('.js-plotly-plot').forEach(function(el){
      Plotly.relayout(el, {'font.family': 'Jost, Helvetica Neue, Arial, sans-serif', 'font.color': INK, 'font.size': 12,
        'paper_bgcolor': 'rgba(0,0,0,0)', 'plot_bgcolor': 'rgba(0,0,0,0)', 'xaxis.gridcolor': GRID, 'yaxis.gridcolor': GRID,
        'xaxis.tickfont.color': MUTED, 'yaxis.tickfont.color': MUTED, 'hoverlabel.bgcolor': '#ffffff',
        'hoverlabel.bordercolor': GRID, 'hoverlabel.font.color': INK, 'legend.orientation': 'h'});
      Plotly.Plots.resize(el);
    });
  });
});
// A chart drawn while C2 was hidden has no width; it is resized when C2 opens.
window.addEventListener('hashchange', function(){
  setTimeout(function(){
    if (!window.Plotly) return;
    ['demo-chart-pay', 'demo-chart-runs', 'demo-chart-carry'].forEach(function(id){
      var el = document.getElementById(id);
      if (el && el.offsetParent !== null && el.data) Plotly.Plots.resize(el);
    });
  }, 80);
});

// The newest ten of each table, with Show all for the rest.
var SHOW = {tickets: false, runs: false};
function more(key, n){
  var b = document.querySelector('.demo-more[data-table="' + key + '"]'); if (!b) return;
  b.hidden = n <= 10; b.textContent = SHOW[key] ? 'Show the newest 10' : 'Show all ' + n;
}
document.querySelectorAll('.demo-more').forEach(function(b){
  b.addEventListener('click', function(){ var k = b.getAttribute('data-table'); SHOW[k] = !SHOW[k]; board(); });
});
function board(){
  fetch('data/index.json?t=' + Date.now(), {cache: 'no-store'}).then(function(r){
    if (!r.ok) throw new Error('none yet'); return r.json();
  }).then(function(ix){
    var mine = fetchStore(MINE, []);
    var t = ix.totals || {}, b = t.buy || {}, p = t.passed || {};
    // Three tiles with a line each, revision task 9; the counts behind a tap.
    var tile = function(v, head, line){ return '<div><b>' + v + '</b><span>' + head + '</span><small>' + line + '</small></div>'; };
    document.getElementById('demo-totals').innerHTML =
      tile(pct(b.mean) || 'none yet', 'Picked, average after cost', 'What a BUY ticket made on average, less trading cost.') +
      tile(pct(p.mean) || 'none yet', 'Passed on, average after cost', 'What the model passed on did over the same time. Picks should beat it.') +
      tile((b.n || 0) + ' closed', 'BUY tickets settled', (b.positive || 0) + ' made money. A ticket closes at its target, its stop or its due time.');
    var cn = document.getElementById('demo-counts');
    if (cn) cn.textContent = (t.runs || 0) + ' ' + (t.runs === 1 ? 'run' : 'runs') + ' by new users. ' +
      (t.open || 0) + ' ' + (t.open === 1 ? 'ticket' : 'tickets') + ' still open.';
    var cnt = document.getElementById('demo-count-runs'); if (cnt) cnt.textContent = (ix.runs || []).length;
    var all = (ix.tickets || []).slice().sort(function(a, c){ return (c.issued || '').localeCompare(a.issued || ''); });
    var rows = SHOW.tickets ? all : all.slice(0, 10), runsAll = ix.runs || [], runRows = SHOW.runs ? runsAll : runsAll.slice(0, 10);
    more('tickets', all.length); more('runs', runsAll.length);
    document.getElementById('demo-tables').hidden = !(ix.tickets || []).length && !runsAll.length;
    document.getElementById('demo-tickets').innerHTML = '<div class="demo-scroll"><table><tr><th>Friend</th><th>Issued</th><th>Symbol</th><th>Timeframe</th><th>Call</th><th>Score</th><th>Entry</th><th>Due</th><th>Result</th><th>After cost</th></tr>' +
      rows.map(function(x){
        var res = x.status === 'settled' ? x.how : 'open';
        var cls = x.after_cost > 0 ? 'pos' : (x.after_cost < 0 ? 'neg' : '');
        return '<tr class="' + (mine.indexOf(x.run_id) >= 0 ? 'mine' : '') + '"><td>' + esc(x.name) + '</td><td>' + when(x.issued) + '</td><td>' + esc(x.symbol) +
          '</td><td>' + esc(x.frame) + '</td><td>' + esc(x.call) + '</td><td>' + (x.score == null ? '' : x.score.toFixed(3)) + '</td><td>' + x.entry_price +
          '</td><td>' + when(x.due) + '</td><td>' + esc(res) + '</td><td class="' + cls + '">' + (x.status === 'settled' ? pct(x.after_cost) : '') + '</td></tr>';
      }).join('') + '</table></div>';
    document.getElementById('demo-runs').innerHTML = '<div class="demo-scroll"><table><tr><th>Friend</th><th>When</th><th>Timeframe</th><th>Symbols</th><th>Model</th><th>RMSE</th><th>Theil\'s U2</th></tr>' +
      runRows.map(function(r){
        var bad = r.status !== 'done', three = !bad && r.blind_u2 == null && r.blind_top != null;
        var rm = bad ? 'failed' : (r.blind_rmse != null ? fmt('rmse', r.blind_rmse) : 'n/a');
        var u2 = bad ? esc((r.error || '').slice(0, 60)) : three ? ('three-way, top fifth ' + pct(r.blind_top)) :
          (r.blind_u2 != null ? fmt('u2', r.blind_u2) : 'n/a');
        return '<tr class="' + (mine.indexOf(r.run_id) >= 0 ? 'mine' : '') + '"><td>' + esc(r.name) + '</td><td>' + when(r.started) + '</td><td>' + esc(r.frame) +
          '</td><td>' + esc((r.symbols || '').replace(/USDT/g, '')) + '</td><td>' + esc(r.chosen || '') + '</td><td>' + rm + '</td><td>' + u2 + '</td></tr>';
      }).join('') + '</table></div>';
    labelTables();
    drawCharts(ix, mine);
  }).catch(function(){
    document.getElementById('demo-totals').textContent = 'No tickets yet.';
  });
}
board();

// Every copy of the Run block shows the same status and the same name.
function setStatus(html){ document.querySelectorAll('.demo-status').forEach(function(s){ s.innerHTML = html; }); }
function busy(on){ document.querySelectorAll('.demo-go').forEach(function(b){ b.disabled = on; }); }
var LINK = ' <a href="#panel-C2">See them on C2 Ledger</a>.';
document.querySelectorAll('.demo-name').forEach(function(i){
  i.value = fetchStore(NKEY, '');
  i.addEventListener('input', function(){
    store(NKEY, i.value);
    document.querySelectorAll('.demo-name').forEach(function(j){ if (j !== i) j.value = i.value; });
  });
});
function wait(id, started){
  fetch('data/runs/' + id + '.json?t=' + Date.now(), {cache: 'no-store'}).then(function(r){
    if (!r.ok) throw new Error('not yet'); return r.json();
  }).then(function(rec){
    if (rec.status === 'done') {
      setStatus('Done. ' + (rec.tickets || []).length + ' paper tickets issued with ' + esc(rec.chosen) +
        (rec.held && rec.held.length ? '. Held to the demo limits: ' + esc(rec.held.join('; ')) : '') + '.' + LINK);
    } else {
      setStatus('The run failed: ' + esc(rec.error || 'no reason recorded') + '. Change a setting and run again.');
    }
    busy(false);
    board();
  }).catch(function(){
    var mins = Math.round((Date.now() - started) / 60000);
    if (mins > 40) { setStatus('No result after 40 minutes. The queue may be full; try again later.'); busy(false); return; }
    setStatus('Running, ' + mins + ' minutes so far. You can leave this page; your tickets will be on C2 Ledger.' + LINK);
    setTimeout(function(){ wait(id, started); }, 20000);
  });
}
document.querySelectorAll('.demo-go').forEach(function(go){
  go.addEventListener('click', function(){
    if (!RELAY) { setStatus('Running is not switched on yet.'); return; }
    var cfg = collect(); store(KEY, cfg);
    var box = go.closest('.demo-run'), nm = box && box.querySelector('.demo-name');
    busy(true); setStatus('Sending your settings.');
    fetch(RELAY + '/run', {method: 'POST', headers: {'content-type': 'application/json'},
          body: JSON.stringify({name: nm ? nm.value : '', config: cfg})})
    .then(function(r){ return r.json().then(function(j){ return [r.ok, j]; }); })
    .then(function(res){
      if (!res[0]) { setStatus(esc(res[1].error || 'The run was refused.')); busy(false); return; }
      var mine = fetchStore(MINE, []); mine.push(res[1].run_id); store(MINE, mine);
      wait(res[1].run_id, Date.now());
    }).catch(function(){ setStatus('Could not reach the runner. Try again in a minute.'); busy(false); });
  });
});
})();
</script>
"""


def universe() -> dict:
    """The symbols a demo run accepts, by market, as the page lists them."""
    import demo_run as dr
    return {"crypto": [f"{c[:-4]}/USDT" for c in dr.COINS], "equity": list(dr.STOCKS)}


def demo_choices(doc: str) -> str:
    """The market, timeframe, coin and quick-pick lists, cut to what a demo run does.

    The served page offers every coin in the operator's local panel, 567 of
    them, and the equity frames. demo_run.sanitize would drop anything else, so
    offering it would only let a friend choose settings that are then ignored.
    """
    import demo_run as dr

    def opts(values, chosen, label=lambda v: v):
        return "".join(f'<option value="{v}"{" selected" if v in chosen else ""}>{label(v)}</option>'
                       for v in values)

    names = {"15m": "15 minutes", "30m": "30 minutes", "1h": "1 hour", "2h": "2 hours", "4h": "4 hours",
             "6h": "6 hours", "8h": "8 hours", "12h": "12 hours", "1d": "1 day"}
    frames = {f: names[f] for f in dr.FRAMES}
    coins = [f"{c[:-4]}/USDT" for c in dr.COINS]
    swaps = {
        "market": opts(["crypto", "equity"], {"crypto"}, {"crypto": "crypto", "equity": "US stocks"}.get),
        "frame": opts(list(frames), {"4h"}, frames.get),
        "symbols": opts(coins, {"BTC/USDT", "ETH/USDT", "SOL/USDT"}),
        "bundle": opts(["all", "majors", "btc-eth"], {"all"}),
    }
    for name, inner in swaps.items():
        doc = re.sub(r'(<select[^>]*name="%s"[^>]*>).*?(</select>)' % name,
                     lambda m: m.group(1) + inner + m.group(2), doc, flags=re.S)
    return doc


# Dark themes, operator request, 24 September 2026. Solarized Dark first,
# replacing a plain lightness flip that read as too high in contrast (Ethan
# Schoonover, https://ethanschoonover.com/solarized/). Everforest Dark and
# Zenbones Seoulbones Dark were read from the operator's iTerm2 colour files,
# ~/Downloads/everforest-dark.itermcolors and zenbones-seoulbones-dark.itermcolors;
# where a file has no orange, it is the mean of its red and yellow.
# ramp maps inverted lightness onto the theme's greys, background first.
# lanes keeps the six panels six distinct colours, cool to warm, keyed by
# every hex the stylesheet declares for a lane, including its later overrides.
_LANE_KEYS = {"a1": ("0b4f8a",), "a2": ("1f7ac4", "1a6cb0"), "b1": ("0e7a4f",),
              "b2": ("27a86e", "1c7f52"), "c1": ("c2410c",), "c2": ("ea7a2c", "b35a10")}
THEMES = {
    "solarized": dict(
        ramp=[(0.00, "002b36"), (0.10, "073642"), (0.35, "586e75"),
              (0.60, "839496"), (0.80, "93a1a1"), (1.00, "93a1a1")],
        accent=["b58900", "cb4b16", "dc322f", "d33682", "6c71c4", "268bd2", "2aa198", "859900"],
        lanes=dict(a1="6c71c4", a2="268bd2", b1="2aa198", b2="859900", c1="cb4b16", c2="b58900"),
        bg="002b36", surface="073642", sel="586e75", selfg="fdf6e3", soft="839496", emph="93a1a1",
        td="c9d1c8", label="a8d8b9", head="f2c9a0", link="9cc9e8"),
    "everforest": dict(
        ramp=[(0.00, "2d353b"), (0.10, "343f44"), (0.35, "4f5b58"),
              (0.60, "859289"), (0.80, "d3c6aa"), (1.00, "d3c6aa")],
        accent=["dbbc7f", "e19d80", "e67e80", "d699b6", "7fbbb3", "83c092", "a7c080"],
        lanes=dict(a1="7fbbb3", a2="83c092", b1="a7c080", b2="dbbc7f", c1="e19d80", c2="e67e80"),
        bg="2d353b", surface="343f44", sel="414b51", selfg="d3c6aa", soft="859289", emph="d3c6aa",
        td="d3c6aa", label="a7c080", head="dbbc7f", link="7fbbb3"),
    "seoulbones": dict(
        ramp=[(0.00, "4b4b4b"), (0.10, "555555"), (0.35, "6c6465"),
              (0.60, "a8a8a8"), (0.80, "dddddd"), (1.00, "dddddd")],
        accent=["ffdf9b", "f1b49f", "e388a3", "a5a6c5", "97bdde", "6fbdbe", "98bd99"],
        lanes=dict(a1="a5a6c5", a2="97bdde", b1="6fbdbe", b2="98bd99", c1="ffdf9b", c2="e388a3"),
        bg="4b4b4b", surface="555555", sel="777777", selfg="dddddd", soft="a8a8a8", emph="dddddd",
        td="dddddd", label="98bd99", head="ffdf9b", link="97bdde"),
}
# Kanagawa Dragon, from ~/Downloads/kanagawa-dragon.itermcolors, chosen on
# 24 September 2026 because its dim text still measures 7.3 to 1 against the
# background, where Solarized's measured 4.7 and small type read as faint.
THEMES["kanagawa"] = dict(
    ramp=[(0.00, "181616"), (0.10, "282727"), (0.35, "625e5a"),
          (0.60, "a6a69c"), (0.80, "c5c9c5"), (1.00, "c5c9c5")],
    accent=["e6c384", "c4937c", "c4746e", "a292a3", "938aa9", "7fb4ca", "7aa89f", "87a987"],
    lanes=dict(a1="938aa9", a2="7fb4ca", b1="7aa89f", b2="87a987", c1="c4937c", c2="e6c384"),
    bg="181616", surface="282727", sel="2d4f67", selfg="c5c9c5", soft="a6a69c", emph="c5c9c5",
    td="c5c9c5", label="87a987", head="e6c384", link="7fb4ca")
# Warm light, 24 September 2026, after the operator found every dark theme
# too dark to be a page a new visitor enjoys, and pointed to the investing
# app Wealthsimple as the look wanted: a warm off-white ground, white cards
# with a soft shadow in place of outlines, dark warm grey type, sage green, and
# one amber action. A light theme keeps the page's own colours and the charts
# as drawn; only LIGHT_CSS is laid over them.
THEMES["warm"] = dict(
    light=True, bg="f5f4f1", surface="ffffff", sel="efe3c4", selfg="32302f", soft="6b6660",
    emph="32302f", td="32302f", label="2f6f62", head="8a8378", link="2f6f62",
    lanes=dict(a1="4f6d8f", a2="5f8fa8", b1="2f6f62", b2="6f9a7c", c1="b8732a", c2="c99a2e"))
THEME = "warm"


def _rgb(h: str) -> tuple[int, int, int]:
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _flip(r: int, g: int, b: int) -> tuple[int, int, int]:
    """A light-mode colour carried onto the chosen dark theme.

    Greys follow the theme's ramp by inverted lightness, so white paper becomes
    the background and dark ink the text. A lane keeps its own lane colour. A
    saturated colour takes the nearest accent by hue. A pale tint or a dark
    coloured ink takes its base tone with a little of that accent mixed in.
    """
    import colorsys
    key = "%02x%02x%02x" % (r, g, b)
    h, l, sat = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    th = THEMES[THEME]
    t = 1 - l
    for (t0, c0), (t1, c1) in zip(th["ramp"], th["ramp"][1:]):
        if t <= t1:
            f = 0 if t1 == t0 else (t - t0) / (t1 - t0)
            base = tuple(a + (z - a) * f for a, z in zip(_rgb(c0), _rgb(c1)))
            break
    for lane, keys in _LANE_KEYS.items():
        if key in keys:
            return _rgb(th["lanes"][lane])
    if sat < 0.2:
        return tuple(round(v) for v in base)

    def hue(c):
        return colorsys.rgb_to_hls(*(v / 255 for v in _rgb(c)))[0]
    accent = _rgb(min(th["accent"],
                      key=lambda c: min(abs(hue(c) - h), 1 - abs(hue(c) - h))))
    if 0.25 < l < 0.85:
        return accent
    return tuple(round(a + (z - a) * 0.2) for a, z in zip(base, accent))


def _dark_colours(text: str) -> str:
    def hexsub(m):
        v = m.group(1)
        if len(v) == 3:
            v = "".join(c * 2 for c in v)
        return "#%02x%02x%02x" % _flip(int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16))

    def rgbsub(m):
        parts = [x.strip() for x in m.group(2).split(",")]
        r, g, b = _flip(*(int(float(x)) for x in parts[:3]))
        return f"{m.group(1)}({r},{g},{b}" + (f",{parts[3]}" if len(parts) > 3 else "") + ")"

    text = re.sub(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", hexsub, text)
    text = re.sub(r"\b(rgba?)\(([^)]*)\)", rgbsub, text)
    text = re.sub(r"(:\s*|\s)white\b", lambda m: m.group(1) + "#" + THEMES[THEME]["bg"], text)
    text = re.sub(r"(:\s*|\s)black\b", lambda m: m.group(1) + "#" + THEMES[THEME]["emph"], text)
    return text


DARK_CSS = """
/* The chosen dark theme; the @name@ tokens are filled by theme_css(). The
   page's own colours are mapped in the source by dark(); the charts are
   pictures drawn on white, so the filter below inverts them, turns their hue
   back, and lays the result on the theme, white becoming the background and
   black the text. */
:root { color-scheme: dark; }
body { background:@bg@; }
img, .plotly-graph-div { filter: url(#darktheme); background-color:#ffffff !important; }
::selection { background:@sel@; color:@selfg@; }
* { scrollbar-color:@sel@ @surface@; }
/* Quieter frames, operator request, 24 September 2026. Every frame line is a
   faint base1 at low opacity; a lane's colour stays only on a 2px top edge and
   in the text of its tags, which are tinted rather than filled. */
.card, .card .pair .slot, .thumb, .chart, .block, .panelsec, .flow .chip, .gchip, .loadrec,
.demo-run, .demo-board, input, select, textarea {
  border-color:rgba(@emph_rgb@,0.13) !important; }
.card .pair .slotcap, .cardfoot, .chart figcaption, td, .reclist li {
  border-color:rgba(@emph_rgb@,0.08) !important; }
.card { border-top-width:2px !important; }
.flow .chip, .chart, .demo-run, .demo-board { border-top-width:2px !important; }
.card > h2 .tag, .card > h2 .num, .setchip, .runchip, .readchip { font-weight:600 !important; }
.card p, .note, .slotcap { color:@soft@ !important; }
.thumb, .card .pair .slot { border-radius:3px; }
a.card:hover { box-shadow:0 2px 12px rgba(0,0,0,0.25) !important; }
/* Tables in pastel on dark, operator request, 24 September 2026. The panel
   shade base02 as ground, body in a soft pale grey, row labels in mint,
   headers in peach, links in sky blue.
   Thin pale type on the blue ground haloed at its edges, so the type is also
   larger, with more leading. */
table { background:@surface@ !important; font-size:13.5px !important; line-height:1.5 !important;
        -webkit-font-smoothing:antialiased; border-radius:3px; }
td { color:@td@ !important; border-color:rgba(@emph_rgb@,0.10) !important; padding:7px 9px !important; }
td:first-child, td:first-child b { color:@label@ !important; }
th { background:@bg@ !important; color:@head@ !important; font-size:12px !important;
     padding:7px 9px !important; border-bottom:1px solid rgba(@head_rgb@,0.28) !important; }
td a { color:@link@ !important; text-underline-offset:2px; }
tr:hover td { background:rgba(@emph_rgb@,0.05); }
.cluster, .cluster .field, .fields .field, .hyperblock .field {
  border-color:rgba(@emph_rgb@,0.13) !important; border-left-width:1px !important; }
.cluster { background:@surface@ !important; }
.field label, .cluster > h4 { color:@emph@ !important; }
.card.c-a1, .flow .chip.c-a1 { border-top-color:var(--c-a1) !important; }
.c-a1>h2 .num, .c-a1>h2 .tag, .card.c-a1 .setchip, .card.c-a1 .runchip, .card.c-a1 .readchip, .flow .chip.c-a1 .num { background:color-mix(in srgb, var(--c-a1) 16%, transparent) !important; color:var(--c-a1) !important; }
.card.c-a2, .flow .chip.c-a2 { border-top-color:var(--c-a2) !important; }
.c-a2>h2 .num, .c-a2>h2 .tag, .card.c-a2 .setchip, .card.c-a2 .runchip, .card.c-a2 .readchip, .flow .chip.c-a2 .num { background:color-mix(in srgb, var(--c-a2) 16%, transparent) !important; color:var(--c-a2) !important; }
.card.c-b1, .flow .chip.c-b1 { border-top-color:var(--c-b1) !important; }
.c-b1>h2 .num, .c-b1>h2 .tag, .card.c-b1 .setchip, .card.c-b1 .runchip, .card.c-b1 .readchip, .flow .chip.c-b1 .num { background:color-mix(in srgb, var(--c-b1) 16%, transparent) !important; color:var(--c-b1) !important; }
.card.c-b2, .flow .chip.c-b2 { border-top-color:var(--c-b2) !important; }
.c-b2>h2 .num, .c-b2>h2 .tag, .card.c-b2 .setchip, .card.c-b2 .runchip, .card.c-b2 .readchip, .flow .chip.c-b2 .num { background:color-mix(in srgb, var(--c-b2) 16%, transparent) !important; color:var(--c-b2) !important; }
.card.c-c1, .flow .chip.c-c1 { border-top-color:var(--c-c1) !important; }
.c-c1>h2 .num, .c-c1>h2 .tag, .card.c-c1 .setchip, .card.c-c1 .runchip, .card.c-c1 .readchip, .flow .chip.c-c1 .num { background:color-mix(in srgb, var(--c-c1) 16%, transparent) !important; color:var(--c-c1) !important; }
.card.c-c2, .flow .chip.c-c2 { border-top-color:var(--c-c2) !important; }
.c-c2>h2 .num, .c-c2>h2 .tag, .card.c-c2 .setchip, .card.c-c2 .runchip, .card.c-c2 .readchip, .flow .chip.c-c2 .num { background:color-mix(in srgb, var(--c-c2) 16%, transparent) !important; color:var(--c-c2) !important; }
/* Reading sweep, 24 September 2026. The account line was 9px; the best-so-far
   callout and the ticked model carried a brown fill and a thick left bar;
   keyboard focus had no visible ring. */
.mh-meta { font-size:11px !important; line-height:1.4 !important; max-width:36% !important; }
:focus-visible { outline:2px solid @link@ !important; outline-offset:2px; }
.recommend, .hyperblock, .hyperblock.on {
  border-color:rgba(@emph_rgb@,0.13) !important; border-left-width:1px !important; }
.recommend, .hyperblock.on { background:@surface@ !important; border-top:2px solid @head@ !important; }
/* A phone, operator request, 24 September 2026, after the page was found
   unreadable away from the desk. The page reads, sets and runs on a phone.
   One column, larger type,
   every table row becomes a small card with its column name above each value
   (the labels are added by labelTables in DEMO_SCRIPT), charts at full width,
   and tap targets of at least 44px. */
@media (max-width:760px) {
  html, body { overflow-x:hidden; font-size:15px; }
  /* A grid or flex child defaults to the width of its widest content, so a
     wide table or a long tag held its column open past the screen. */
  .lanes > *, .card, .briefrow > *, .tools, .panelwrap, .panelsheet, .panelsec, .block,
  .mh-title, .mh-strip, .bigtable { min-width:0 !important; max-width:100% !important; }
  .lanes, .briefrow, .charts, .charts.figs, .demo-tables,
  .briefrow .tools .charts.figs { grid-template-columns:1fr !important; }
  .sheet, .sheet.front { height:auto !important; overflow:visible !important; }
  .sheet.front .lanes { height:auto !important; }

  /* Title bar: the name, then the steps, then the account line, stacked. The
     date strip and the second row of steps cannot be read at this width. */
  .topband, .sheet > .flow { display:none !important; }
  .masthead { flex-wrap:wrap !important; height:auto !important; row-gap:8px; padding:8px 0 !important; }
  .mh-mark { border-right:none !important; }
  .mh-title, .mh-meta, .mh-strip { max-width:100% !important; flex:1 1 100% !important; }
  .mh-title h1 { font-size:17px !important; }
  .mh-meta { margin-left:0 !important; text-align:left !important; padding-left:0 !important;
             border-left:none !important; font-size:13px !important; }
  .flowbar, .flow, .mh-strip { flex-wrap:wrap !important; row-gap:6px; gap:6px; }
  .flowbar { flex:1 1 100% !important; margin-left:0 !important; max-width:100% !important; }
  .flowbar .flowarrow { display:none !important; }
  .flowbar .flowstep, .flow .chip { font-size:13px !important; padding:6px 9px !important; }
  .flowbar .flowstep b { font-size:13px !important; }

  /* Front page cards: both chart previews side by side at a readable height. */
  .card { padding:12px !important; }
  .card > h2 { flex-wrap:wrap !important; row-gap:6px; font-size:18px !important; }
  .card .pair { height:170px !important; flex:0 0 auto !important; }
  .card p { font-size:14px !important; }
  .cardfoot { flex-wrap:wrap !important; row-gap:8px; font-size:13px !important; }

  /* Panel pages. Operator request, 25 September 2026: friends set and run a
     model from a phone, so the settings stay, and each row shows its tools
     above its table. One field a line, and type of 16px so a phone does not
     zoom the page when a box is tapped. */
  .briefrow > .tools { order:-1; }
  .fields, .cluster > .fields { grid-template-columns:1fr !important; }
  .field input[type=text], .field input[type=number], .field select, .field textarea {
       font-size:16px !important; min-height:44px; padding:8px 10px !important; }
  .field select[multiple] { min-height:132px; }
  .block { padding:12px !important; }
  .block > h3 { font-size:15px !important; }
  .note, .block p, .howto li { font-size:14px !important; line-height:1.5 !important; }
  .chart img, .charts img, .thumb { max-height:none !important; height:auto !important; object-fit:contain !important; }
  .plotly-graph-div { max-width:100% !important; }

  /* Tables as cards. */
  table, thead, tbody, tr, td { display:block !important; width:auto !important; }
  thead, tr:has(> th) { display:none !important; }
  table { background:transparent !important; }
  tr { background:@surface@; border-radius:4px; margin:0 0 10px 0; padding:8px 12px; }
  td { border:none !important; padding:3px 0 !important; font-size:14px !important;
       white-space:normal !important; }
  td:first-child { font-size:15px !important; font-weight:700; padding-bottom:6px !important; }
  td[data-label]:not(:first-child)::before { content:attr(data-label); display:block;
       font-size:11.5px; font-weight:700; letter-spacing:0.3px; text-transform:uppercase;
       color:@head@; margin-bottom:1px; }
  td:empty { display:none !important; }
  /* A number table puts each label and its value on one line; a prose table
     (the panel's own brief) keeps the label above the text. */
  td[data-label]:not(:first-child) { display:flex !important; justify-content:space-between;
       align-items:baseline; gap:14px; }
  td[data-label]:not(:first-child)::before { margin:0 !important; flex:0 0 auto; }
  .brieftable td[data-label]:not(:first-child) { display:block !important; }
  .brieftable td[data-label]:not(:first-child)::before { margin-bottom:1px !important; }
  .demo-scroll, .bigtable { max-height:none !important; overflow:visible !important; }

  /* Run block. */
  .demo-row { flex-wrap:wrap; }
  .demo-row input { flex:1 1 100% !important; font-size:16px !important; padding:10px !important; }
  .btn, button, .tablefilter { min-height:44px; font-size:15px !important; }
  .demo-go { width:100%; }
  .demo-front { grid-template-columns:1fr !important; }
  .demo-preset { flex:1 1 100%; }
  .loadnote { display:block; margin:8px 0 0 0; }
}
"""



LIGHT_CSS = """
/* Warm light. Jost is a free geometric face close to the investing apps the
   operator pointed to; the system sans stands in if it cannot load. */
:root { @lanes@ }
body, button, input, select, textarea { font-family:'Jost', 'Helvetica Neue', Helvetica, Arial, sans-serif !important; }
body { color:#32302f; }
td, .mh-meta, .demo-totals b { font-variant-numeric:tabular-nums; }
.card, .block, .chart, .panelsec, .demo-run, .demo-board, .cluster {
  background:#ffffff !important; border:none !important; border-radius:12px !important;
  box-shadow:0 1px 2px rgba(50,48,47,0.06), 0 4px 14px rgba(50,48,47,0.05) !important; }
.card { border-top:3px solid transparent !important; }
.card.c-a1 { border-top-color:var(--c-a1) !important; } .card.c-a2 { border-top-color:var(--c-a2) !important; }
.card.c-b1 { border-top-color:var(--c-b1) !important; } .card.c-b2 { border-top-color:var(--c-b2) !important; }
.card.c-c1 { border-top-color:var(--c-c1) !important; } .card.c-c2 { border-top-color:var(--c-c2) !important; }
a.card:hover { box-shadow:0 2px 4px rgba(50,48,47,0.08), 0 10px 28px rgba(50,48,47,0.10) !important; }
.card .pair .slot, .thumb, .chart img { border:none !important; background:#ffffff !important; border-radius:8px !important; }
.cluster { box-shadow:none !important; background:#faf9f7 !important; }
.cluster .field, .fields .field, .hyperblock .field { background:#ffffff; border:1px solid #ebe8e3 !important; border-radius:8px; }
.recommend, .hyperblock.on { background:#fbf6ea !important; border-top-color:#c99a2e !important; }
input, select, textarea { background:#ffffff !important; border:1px solid #dcd8d1 !important; border-radius:8px !important; color:#32302f !important; }
.btn, button.btn { border-radius:999px !important; background:#ecebe7 !important; color:#32302f !important;
  font-weight:600 !important; padding:9px 20px !important; }
.btn:hover { background:#e2e0da !important; }
.demo-go { background:#f0a830 !important; color:#2a2520 !important; }
.demo-go:hover { background:#e59a1c !important; }
.demo-preset.on { background:#fbf6ea !important; box-shadow:inset 0 0 0 2px #c99a2e; }
table { box-shadow:none !important; }
th { background:#faf9f7 !important; color:#8a8378 !important; font-weight:600 !important; letter-spacing:0.2px; }
td:first-child, td:first-child b { font-weight:600; }
.block > h3, .cluster > h4 { color:#32302f !important; letter-spacing:0.2px; }
.masthead, .topband { border-color:#e6e3dd !important; }
.flowbar .flowstep, .flow .chip { border-radius:999px !important; background:#ffffff !important;
  border:1px solid #e6e3dd !important; }
.exported { background:#fbf6ea !important; color:#5c4a1e !important; border-left:none !important; border-radius:12px; }
@media (max-width:760px) { tr { box-shadow:0 1px 2px rgba(50,48,47,0.06); } }
"""


def theme_css() -> str:
    th = THEMES[THEME]
    out = DARK_CSS
    if th.get("light"):
        out = out.replace(":root { color-scheme: dark; }", "")
        out = re.sub(r"img, \.plotly-graph-div \{ filter: url\(#darktheme\);[^}]*\}", "", out)
        lanes = "".join(f"--c-{k}:#{v}; " for k, v in th["lanes"].items())
        out += LIGHT_CSS.replace("@lanes@", lanes)
    for k in ("bg", "surface", "sel", "selfg", "soft", "emph", "td", "label", "head", "link"):
        out = out.replace(f"@{k}@", "#" + th[k])
    for k in ("emph", "head"):
        out = out.replace(f"@{k}_rgb@", ",".join(str(v) for v in _rgb(th[k])))
    return out


def theme_filter() -> str:
    """Invert a chart, turn its hue back, and lay it between the theme's
    background (for white) and its text colour (for black)."""
    th = THEMES[THEME]
    bg, fg = _rgb(th["bg"]), _rgb(th["emph"])
    funcs = "".join(f'<feFunc{c} type="table" tableValues="{f / 255:.3f} {b / 255:.3f}"/>'
                    for c, f, b in zip("RGB", fg, bg))
    return ('<svg width="0" height="0" style="position:absolute" aria-hidden="true">'
            '<filter id="darktheme" color-interpolation-filters="sRGB">'
            '<feColorMatrix type="hueRotate" values="180"/>'
            f'<feComponentTransfer>{funcs}</feComponentTransfer></filter></svg>')


def dark(doc: str) -> str:
    """Every colour in the page's styles and inline drawings, turned dark.

    Scripts are left alone: they hold the chart library and each interactive
    figure's data, which the screen filter in DARK_CSS already turns dark, and
    flipping them here as well would turn them light again.
    """
    parts = re.split(r"(<script\b.*?</script>)", doc, flags=re.S)
    for i in range(0, len(parts), 2):
        seg = parts[i]
        seg = re.sub(r"(<style[^>]*>)(.*?)(</style>)",
                     lambda m: m.group(1) + _dark_colours(m.group(2)) + m.group(3), seg, flags=re.S)
        seg = re.sub(r'(\s(?:style|fill|stroke|color|bgcolor)=")([^"]*)(")',
                     lambda m: m.group(1) + _dark_colours(m.group(2)) + m.group(3), seg)
        parts[i] = seg
    return "".join(parts)


def scrub(doc: str) -> str:
    """Script names and commands left in tooltips, tables and chart hover text.

    The page keeps the prose that explains each column and each milestone; it
    loses only the name of the file that does the work and any command line.
    """
    # A table row that shows the command a run used.
    doc = re.sub(r"<tr>(?:(?!</tr>).)*?(?:\.venv/bin/python|python3? [\w/.-]+\.py)(?:(?!</tr>).)*</tr>",
                 "", doc, flags=re.S)
    # A script's path in plain text or in a tooltip.
    doc = re.sub(r"(?:\.venv/bin/python\s+)?\b0[1-5]-[\w-]+/[\w./-]+\.py\b", "the code", doc)
    # The same inside a figure's JSON, where HTML is escaped, as an italic line.
    doc = re.sub(r"\\u003cbr\\u003e\\u003ci\\u003e0[1-5]-[\w-]+\\u002f[\w.\\-]+?\.py\\u003c\\u002fi\\u003e",
                 "", doc)
    return doc


# Settings a demo run never reads, removed 25 September 2026 at the operator's
# request for fewer settings. The indicator engines and C2's figure choices
# only draw charts, the calibration run is not part of a demo run, and the
# trading mode is always paper.
ON_B2_C1 = ' on <a href="#panel-B2">B2</a> or <a href="#panel-C1">C1</a>'
DEMO_DROP = ("Choose MACD", "Choose Averages", "Choose Fibonacci", "Choose Confluence",
             "Choose Calibration", "Choose Figures")


def trim_settings(chunk: str) -> str:
    """A panel with only the settings a demo run uses."""
    for title in DEMO_DROP:
        m = re.search(r'<div class="block">\s*<h3>%s</h3>' % re.escape(title), chunk)
        if m:
            chunk = drop_blocks(chunk, m.group(0))
    # The trading mode is fixed at paper, so its box and its note go; the
    # market stays, crypto or US stocks, since 26 September 2026.
    chunk = drop_blocks(chunk, '<div class="field modebox"')
    chunk = re.sub(r'<p class="note formnote"><span id="note-market-choice"></span>.*?</p>', "", chunk, flags=re.S)
    chunk = re.sub(r"<li>Set the indicator engines below.*?</li>", "", chunk, flags=re.S)
    # A row whose settings are all gone keeps its table at full width.
    chunk = re.sub(r'<div class="tools">\s*</div>', "", chunk)
    chunk = re.sub(r'(<button[^>]*\bloadrec\b[^>]*>)[^<]*(</button>)',
                   r'\1Load best fit settings as defaults\2<span class="note loadnote">'
                   r'Then skip ahead to B2 or C1 and press Run Model.</span>', chunk)
    return chunk


def build(relay: str, log=print) -> str:
    client = app.test_client()
    css = (reg.SCRIPTS / "control_static" / "control.css").read_text(encoding="utf-8")
    index = client.get("/").get_data(as_text=True)
    body = re.search(r"<body>(.*)</body>", index, re.S)
    # The front page is left exactly as the served board draws it. The board
    # of tickets sat above it until 24 September 2026 and shrank every panel
    # to a thumbnail; it now opens C2 Ledger, beside the rest of the record.
    shell = strip_code(body.group(1) if body else index)
    # Quick start and Run Model open the front page, operator request 25
    # September 2026, so a visitor on a phone can run before reading anything.
    shell = shell.replace('<div class="lanes">',
                          '<div class="demo-front">' + quick_block("") + RUN_BLOCK + "</div>"
                          '<div class="lanes">', 1)
    sections = []
    for card in reg.CARDS:
        page = client.get(f"/card/{card.key}").get_data(as_text=True)
        chunk = trim_settings(strip_code(panel_chunk(page)))
        if card.key in ("B2", "C1"):
            chunk = quick_block(" below") + RUN_BLOCK + chunk
        elif card.key == "C2":
            chunk = c2_page(chunk)
        else:
            chunk = quick_block(ON_B2_C1) + chunk
        sections.append(
            f'<section class="panelsec" id="panel-{card.key}">'
            f'<h3 class="pk" title="{_html.escape(card.lead, quote=True)}">'
            f'{card.key} &middot; {_html.escape(card.title)}</h3>'
            f'<div class="panelsheet">{chunk}</div></section>')
    log(f"  {len(sections)} panels rendered")
    doc = ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
           "<meta name='viewport' content='width=device-width, initial-scale=1'>"
           "<title>Swing Trader &middot; Control Centre</title>"
           f"<style>{css}{ce.EXTRA_CSS}{DEMO_CSS}</style><style>__DARK_CSS__</style>"
           "<script>__PLOTLY__</script></head><body>"
           + shell
           + '<div id="panels" hidden>' + "".join(sections) + '</div>'
           + '<div class="exported"><b>Paper trading demo</b> &nbsp;Built '
             f'{datetime.now():%d %B %Y %H:%M}. The charts show the operator\'s own '
             'research record as of that date; the paper tickets update as friends run.</div>'
           + "<script>window.__PRESETS__ = " + json.dumps(presets()) + ";window.__METRICS__ = " + json.dumps(METRICS)
           + ";window.__RESEARCH__ = " + json.dumps(research_fits())
           + ";window.__UNIVERSE__ = " + json.dumps(universe()) + ";</script>" + ce.SCRIPT
           + DEMO_SCRIPT.replace("__RELAY__", repr(relay.rstrip("/")) if relay else "''")
           + "</body></html>")
    light = THEMES[THEME].get("light")
    doc = demo_choices(scrub(doc))
    # The served board runs on a local server; the public page does not.
    doc = doc.replace("A paper account on a local server; nothing here can place an order.",
                      "A paper account; nothing here can place an order.").replace("LOCAL, PAPER ONLY", "PAPER ONLY")
    if not light:
        doc = dark(doc)
    # After the flip, because these rules are written for the dark page.
    doc = doc.replace("__DARK_CSS__", theme_css(), 1)
    if light:
        doc = doc.replace("</head>", "<link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>"
                          "<link rel='stylesheet' href='https://fonts.googleapis.com/css2?"
                          "family=Jost:wght@400;500;600;700&display=swap'></head>", 1)
    else:
        doc = doc.replace("</head><body>", "</head><body>" + theme_filter(), 1)
    doc = ce.inline_charts(doc, log=log)
    # The library goes in last, so the scrub never reads three megabytes of it.
    doc = doc.replace("__PLOTLY__", PLOTLY.read_text(encoding="utf-8"), 1)
    for pat in ("<pre", "<code", "Show all code", "03-inputs/", "05-research/", ".py"):
        n = doc.count(pat)
        if n:
            log(f"  note: {n} occurrence(s) of {pat!r} left in the page")
    return doc


def publish(index_html: Path, log=print) -> None:
    """Commit the page to gh-pages, creating the branch the first time.

    A separate worktree, so the working copy of main is never switched. Only
    index.html is written; data/ belongs to the workflows.
    """
    tmp = Path(tempfile.mkdtemp())
    wt = tmp / "pages"
    have = subprocess.run(["git", "ls-remote", "--heads", "origin", "gh-pages"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()
    if have:
        subprocess.run(["git", "fetch", "origin", "gh-pages"], cwd=REPO, check=True)
        subprocess.run(["git", "worktree", "add", str(wt), "origin/gh-pages"], cwd=REPO, check=True)
        subprocess.run(["git", "checkout", "-B", "gh-pages"], cwd=wt, check=True)
    else:
        subprocess.run(["git", "worktree", "add", "--detach", str(wt)], cwd=REPO, check=True)
        subprocess.run(["git", "checkout", "--orphan", "gh-pages"], cwd=wt, check=True)
        subprocess.run(["git", "rm", "-rf", "-q", "."], cwd=wt, check=True)
        (wt / "data" / "runs").mkdir(parents=True, exist_ok=True)
        (wt / "data" / "runs" / ".keep").write_text("")
        (wt / ".nojekyll").write_text("")
    shutil.copy(index_html, wt / "index.html")
    subprocess.run(["git", "add", "-A"], cwd=wt, check=True)
    subprocess.run(["git", "commit", "-q", "-m", f"The demo page, built {datetime.now():%d %B %Y %H:%M}"], cwd=wt)
    subprocess.run(["git", "push", "origin", "gh-pages"], cwd=wt, check=True)
    subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=REPO, check=True)
    # A push to gh-pages starts nothing, since that branch carries no
    # workflows, so the deployment is started by name.
    subprocess.run(["gh", "workflow", "run", "demo-deploy.yml", "--ref", "main"], cwd=REPO, check=True)
    log(f"published to gh-pages and deployment started; live at {PAGES_URL} in a minute or two")


def main() -> int:
    global THEME
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--relay", default="", help="the relay's address, such as https://swing-relay.<you>.workers.dev")
    ap.add_argument("--publish", action="store_true", help="push the page to gh-pages")
    ap.add_argument("--theme", default=THEME, choices=sorted(THEMES), help="the dark colour theme")
    ap.add_argument("--out", default="index.html", help="file name under site/, for a trial build")
    a = ap.parse_args()
    THEME = a.theme
    print(f"building the demo page, theme {THEME}")
    doc = build(a.relay)
    SITE.mkdir(exist_ok=True)
    out = SITE / a.out
    out.write_text(doc, encoding="utf-8")
    print(f"wrote {out.relative_to(REPO)} ({out.stat().st_size / 2**20:.1f} MB)")
    if a.publish:
        publish(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
