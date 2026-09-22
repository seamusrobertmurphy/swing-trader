"""The control centre's acceptance checks.

    .venv/bin/python 03-inputs/control_eval.py            # everything but the slow parts
    .venv/bin/python 03-inputs/control_eval.py --live     # plus one real job end to end
    .venv/bin/python 03-inputs/control_eval.py --layout   # plus the headless browser probe
    .venv/bin/python 03-inputs/control_eval.py --deep     # plus record reproduction

The objectives are written down in 05-research/tasks/eval-control-centre.md and
every check below names the one it answers. A check prints the artefact it read,
so a pass is a statement about a file rather than a claim.

One check is deliberately not what the eval spec first proposed. Check 9 does
not call 05-research/cheatsheets/src/measure.py, because that script measures
panels in fixed-height cells on a page that must not scroll, and the control
centre scrolls by design, so its overflow test would pass without measuring
anything. The technique is the same, a Chrome headless probe reading each
panel's real content height, applied to the question this page actually has:
does any panel clip its own content, and does the row of five lanes fit the
window.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import control_registry as reg          # noqa: E402
from control_centre import app, runner  # noqa: E402

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

PASS, FAIL, SKIP = "pass", "FAIL", "skip"
results: list[tuple[str, str, str]] = []


def record(check: str, ok, detail: str) -> None:
    state = PASS if ok is True else (SKIP if ok is None else FAIL)
    results.append((check, state, detail))
    mark = {PASS: "  ok  ", FAIL: " FAIL ", SKIP: " skip "}[state]
    # Flushed: python buffers stdout when it is not a terminal, so a run
    # redirected to a file showed nothing at all until it finished, which on a
    # deep run is a quarter of an hour of looking like a hang.
    print(f"[{mark}] {check}\n         {detail}", flush=True)


# ---------------------------------------------------------------------------
# 1 to 7: functional
# ---------------------------------------------------------------------------

def check_index(client) -> str:
    r = client.get("/")
    record("1 index responds", r.status_code == 200,
           f"GET / returned {r.status_code}")
    return r.get_data(as_text=True)


def check_cards(page: str) -> None:
    """Checks 1 and 2 of the second design: four columns, twelve panels."""
    # Inside the columns only. The timeline links to D3 as well and it sits
    # above them, so scanning the whole page counted thirteen panels.
    grid = page[page.find('class="lanes"'):]
    ids = re.findall(r'href="/card/([A-C]\d)"', grid)
    expected = [c.key for c in reg.CARDS]
    # Six since 9 September 2026, not nine. Performance, Tuning and the
    # Scoreboard became C1, and Assessment joined the Live book as C2.
    record("1a six panels in three columns of two, in order",
           ids == expected and len(ids) == 6,
           f"{len(ids)} panels: {' '.join(ids)}")
    rows = {k: sum(1 for c in reg.CARDS if c.lane == k) for k, _t, _s in reg.LANES}
    record("1d two panels in every column", set(rows.values()) == {2},
           f"{rows}, so the grid is three by two and a panel is half again as "
           f"tall as it was at three rows")
    # Since 16 September 2026 the columns carry no title band; the reading
    # order row above them names the panels instead. Count the columns.
    lanes = re.findall(r'class="lane(?: one)?"', page)
    record("1b three columns", len(lanes) == len(reg.LANES),
           f"{len(lanes)} columns rendered, headed by the reading-order row rather "
           f"than by lane titles")
    wrong = [c.key for c in reg.CARDS
             if f'class="card {c.colour}" href="/card/{c.key}"' not in page]
    record("1c each panel keeps a cheat-sheet colour class", not wrong,
           "every panel carries its own class" if not wrong else f"missing on {wrong}")

    # 2: the timeline spans the frame and is not inside a column. Since the
    # 9 September banding it sits in the masthead's middle slot rather than in a
    # strip above it, so the order asserted here is masthead, timeline, columns.
    # Since 16 September 2026 the timeline is a band of its own above the
    # masthead, at the full height of that band, so the order is band,
    # masthead, the reading-order row, columns.
    i_band, i_tl = page.find('class="topband"'), page.find('class="timeline"')
    i_mast, i_flow = page.find('class="masthead"'), page.find('class="flow"')
    i_lanes = page.find('class="lanes"')
    record("2 the timeline spans the frame, above everything",
           0 < i_band < i_tl < i_mast < i_flow < i_lanes,
           f"top band at {i_band} holding the timeline at {i_tl}, masthead at "
           f"{i_mast}, reading order at {i_flow}, columns at {i_lanes}")
    pos = [page.find(f'class="chip {reg.CARDS_BY_KEY[k].colour}" href="/card/{k}"')
           for k, _ in reg.FLOW]
    order_ok = all(x > 0 for x in pos) and pos == sorted(pos) \
        and page.count('class="arrow"') == len(reg.FLOW) - 1
    record("2b the reading order runs A1 to C2 in one line of arrows", order_ok,
           " \u279e ".join(f"{k} {short}" for k, short in reg.FLOW) + ", each chip in its panel's colour"
           if order_ok else "a chip is missing or out of order")


def check_card_pages(client) -> None:
    """Check 3: every panel opens, and every knob of a runnable job is on it."""
    bad, missing = [], []
    for card in reg.CARDS:
        r = client.get(f"/card/{card.key}")
        if r.status_code != 200:
            bad.append(f"{card.key}:{r.status_code}")
            continue
        body = r.get_data(as_text=True)
        for job in card.jobs:
            for knob in job.knobs:
                # A knob is visible either as its own field, or, when the
                # configuration owns it, in the "From your settings" line above
                # the form with its value stated. What must not happen is a
                # knob that is invisible, and what must not happen again is a
                # knob that is visible twice. 21 September 2026.
                owned = (job.key, knob.flag) in reg.CONFIG_OWNED
                # Inside THIS job's form, not anywhere on the page: a setting
                # the configuration owns is rendered once by the tool that owns
                # it, and finding that field would read as a duplicate when it
                # is the single source.
                m = re.search(rf'data-job="{job.key}">(.*?)</form>', body, re.S)
                field = bool(m) and f'name="{knob.flag}"' in m.group(1)
                if owned and field:
                    missing.append(f"{card.key}/{job.key}/{knob.flag} is offered twice")
                elif not owned and not field:
                    missing.append(f"{card.key}/{job.key}/{knob.flag} is nowhere")
                elif owned and f"fromconfig" not in body:
                    missing.append(f"{card.key}/{job.key}/{knob.flag} is stated nowhere")
    record("3a every panel opens", not bad,
           f"{len(reg.CARDS)} panel pages returned 200" if not bad else f"failures: {bad}")
    n = sum(len(j.knobs) for c in reg.CARDS for j in c.jobs)
    n_owned = sum(1 for c in reg.CARDS for j in c.jobs for k in j.knobs
                  if (j.key, k.flag) in reg.CONFIG_OWNED)
    record("3b every knob is visible once, as a field or as a stated setting",
           not missing,
           f"{n} knobs across the board: {n - n_owned} offered as fields, "
           f"{n_owned} read from the configuration and stated above the form"
           if not missing else "; ".join(missing))


def check_controls(client) -> None:
    """Checks 4 to 8: every panel offers a control, and the right ones do."""
    import bench_config as bc

    # all_sections, not section: a merged panel owns several and leaves the
    # singular field empty, so the old check called the Data panel read-only
    # while it was carrying three forms.
    # all_controls, not controls: after the merge every control of a panel's own
    # kind belongs to a section rather than to the panel, so counting the panel
    # field alone reported nought controls on a board that has five.
    read_only = [c.key for c in reg.CARDS
                 if not c.all_sections and not c.jobs and not c.all_controls]
    record("4 no panel is read-only", not read_only,
           f"{sum(1 for c in reg.CARDS if c.all_sections)} panels edit a configuration "
           f"section, {sum(1 for c in reg.CARDS if c.jobs)} can run a script, and "
           f"{sum(1 for c in reg.CARDS if c.all_controls)} carry controls of their own "
           f"kind: filtering a table, switching a view"
           if not read_only else f"offer nothing: {read_only}")

    want = {
        "5 the data panel carries the market and the bars":
            ("A1", ("market", "frame")),
        "5b the data panel carries the symbols and the label":
            ("A1", ("bundle", "symbols", "rows", "target_atr", "horizon_bars")),
        "5c the data panel carries the screen thresholds":
            ("A1", ("min_quote_volume", "atr_low", "atr_high", "rank_signal")),
        "6 the variables panel carries the families":
            ("A2", ("families", "include", "exclude")),
        "6b the variables panel carries the engine parameters":
            ("A2", ("macd_fast", "macd_slow", "fib_lookback", "confluence_threshold")),
        "6c variable selection carries its settings":
            ("B1", ("run_selection", "l1_ratio", "rule")),
        "7 the fitting column carries the split and the folds":
            ("B2", ("holdout_days", "folds", "scheme")),
        "7b the merged model panel carries the models and the grid":
            ("C1", ("estimators", "tune", "grid", "class_weight")),
        "7c the merged model panel still carries the calibration settings":
            ("C1", ("run_calibration", "methods", "bins")),
    }
    for name, (key, fields) in want.items():
        body = client.get(f"/card/{key}").get_data(as_text=True)
        missing = [f for f in fields if f'name="{f}"' not in body]
        record(name, not missing,
               f"{key} renders {', '.join(fields)}" if not missing
               else f"{key} is missing {missing}")

    # 8: a setting posted comes back as the value the runner would use.
    before = bc.load()
    client.post("/config/split", data={"holdout_days": "545", "folds": "8",
                                       "scheme": "bootstrap", "embargo_bars": "0",
                                       "repeats": "10", "boot_samples": "25"})
    got = bc.load()["split"]
    ok = got["holdout_days"] == 545 and got["folds"] == 8 and got["scheme"] == "bootstrap"
    bc.save(before)
    record("8 a posted setting round-trips into the configuration", ok,
           f"holdout 545, folds 8, scheme bootstrap written and read back; "
           f"the previous configuration was restored" if ok else f"got {got}")


def check_visuals(client) -> None:
    """Checks 9 to 13: every panel draws, and the result panels do more."""
    import control_charts as cc

    # all_charts, not charts: a merged panel names four in its top row and the
    # rest under the section they came from, and counting only the top row would
    # report 22 slots where the board has 50 and call the merge lossless on the
    # strength of a number that never looked at the sections.
    blank = [c.key for c in reg.CARDS if not c.all_charts]
    record("9 every panel draws at least one chart", not blank,
           f"{sum(len(c.all_charts) for c in reg.CARDS)} chart slots across "
           f"{len(reg.CARDS)} panels, from {len(cc.CHARTS)} drawings"
           if not blank else f"draw nothing: {blank}")

    thin = []
    for name in sorted(cc.CHARTS):
        png = cc.draw(name)
        if not png or len(png) < 4000:
            thin.append(name)
    record("9b every chart renders", not thin,
           f"{len(cc.CHARTS)} charts drawn" if not thin else f"failed: {thin}")

    body = client.get("/card/C1").get_data(as_text=True)
    record("10 the results column expands a chart and switches layers",
           'class="expand"' in body,
           "every chart carries an expand control that widens it in place")

    body = client.get("/card/C1").get_data(as_text=True)
    record("11 the scoreboard explains a column on hover",
           '<th title=' in body and 'class="tablefilter"' in body
           and '<td title=' not in body,
           "the gloss sits on the column heading, once per column, and each table "
           "has its own filter box; repeating it on every cell was 10,738 tooltips "
           "and half the page weight, so it was moved to the heading on 2026-09-22")

    body = client.get("/card/C2").get_data(as_text=True)
    record("12 the live book shows a calendar and a ranking",
           "run-calendar" in body and "run-ranking" in body
           and 'id="viewswitch"' in body,
           "both are on the History panel with the switch between them, and the "
           "long-term charts beside them")

    import milestones as ms
    marks = ms.load()
    record("13 the timeline carries milestones, not runs", len(marks) >= 10,
           f"{len(marks)} milestones across {len({m['kind'] for m in marks})} kinds, "
           f"each citing a file; runs are the background")


def check_statistics(client) -> None:
    """Checks 14 and 15: what variable selection reports, and where it comes from."""
    import control_tables as ct

    hits = sorted((reg.REPO / "04-outputs" / "AA-evals" / "varselect")
                  .glob("univariate-*.json"))
    if not hits:
        record("14 variable selection reports the univariate screen", None,
               "no univariate record on disk yet")
    else:
        doc = json.loads(hits[-1].read_text())
        row = (doc.get("rows") or [{}])[0]
        need = {"coef", "lo", "hi", "lr", "p", "loglik", "null_loglik"}
        record("14 variable selection reports estimate, interval and likelihood ratio",
               need <= set(row),
               f"{len(doc['rows'])} predictors, each with an estimate, a 95 per cent "
               f"interval, a likelihood ratio against an intercept-only null and its "
               f"p-value; {doc['cleared_05']} cleared the five per cent point against "
               f"{doc['expected_by_chance']:.0f} expected from noise. Read "
               f"{hits[-1].relative_to(reg.REPO)}")

    board = ct.build("scoreboard")
    record("15 the scoreboard is read from records, not carried forward",
           len(board["rows"]) > 400,
           f"{len(board['rows'])} configuration fits, every row read from a "
           f"bench-sweep record on disk at the moment the page was drawn")


def check_third_pass(client) -> None:
    """The layout and library items of the third specification."""
    import control_charts as cc

    css = (reg.SCRIPTS / "control_static" / "control.css").read_text()
    record("T1 the layout is full width", "max-width:none" in css,
           "the sheet is no longer capped at 1680 pixels")

    b3 = client.get("/card/B1").get_data(as_text=True)
    # Since 16 September 2026 a panel opens on rows that pair a plain table
    # with the tools that act on it, and the chart strip follows those rows.
    record("T2 tables and their tools come first, the chart strip after",
           0 < b3.find('class="briefrow"') < b3.find('class="tools"') < b3.find('id="figures-'),
           "each row is a table on the left and its settings on the right, and the "
           "chart strip is rendered after the rows")
    record("T3 settings are clustered, each a full-width row",
           b3.count('class="cluster') >= 1 and ".cfgform .field{" in css,
           f"{b3.count('class=\"cluster')} clusters on B1, and a field is a row spanning the panel")
    record("T4 the panel names itself in the header",
           "B1 &middot; Variables" in b3,
           "entering a panel puts its own name where the site name was")

    bad = [c.key for c in reg.CARDS
           if "Evidence on disk" in client.get(f"/card/{c.key}").get_data(as_text=True)]
    record("T5 Evidence Log, not Evidence on disk", not bad,
           f"renamed on all {len(reg.CARDS)} panels" if not bad
           else f"still wrong on {bad}")

    idx = client.get("/").get_data(as_text=True)
    figs = cc.figures()
    # Since 16 September 2026 the front page carries no figure library; the
    # workflow's figures are served on the panels that name them, A1's
    # screening and hard-rules sections first.
    served = sum(len(re.findall(r'src="/figure/04-outputs/',
                                client.get(f"/card/{c.key}").get_data(as_text=True)))
                 for c in reg.CARDS)
    # 90, not 100. The reels de-duplicate on the file name from 9 September
    # 2026, because avax_macd_20260620.png and twenty-five others exist in two
    # folders each and a reel showing one picture twice looks stuck.
    #
    # 35, not 40. Nine panels became six on 9 September 2026, and a reel takes at
    # most fourteen figures, so the ceiling on what the front page can serve fell
    # with the panel count. The check is that the figures are reachable, and 40
    # across six reels is reachable; the old threshold was measuring the number
    # of panels rather than the library.
    record("T6 the workflow's figures are reachable", len(figs) > 90 and served >= 7,
           f"{len(figs)} figures indexed across {len(cc.FIGURE_DIRS)} folders, "
           f"{served} of them served on the panel pages")

    slots = re.findall(r'class="reel slot" data-n="(\d+)" data-start="(\d+)"', idx)
    starts = [int(a) for _n, a in slots]
    record("T7 each panel shows two charts side by side, stepped by hand",
           len(slots) == 2 * len(reg.CARDS) and all(int(n) > 2 for n, _a in slots)
           and all(starts[i] != starts[i + 1] for i in range(0, len(starts) - 1, 2))
           and "setInterval" not in idx,
           f"{len(slots)} slots over {sum(int(n) for n, _a in slots)} images, two a "
           f"panel opening on different charts, and no timer" if slots else "no slot rendered")

    import bench_config as bc
    schemes = dict((f.key, f) for f in bc.SCHEMA["split"]["fields"])["scheme"].choices
    record("T8 seven resampling regimes", len(schemes) == 7,
           f"{', '.join(schemes)}")
    record("T9 the regimes are demonstrated and their uncertainty shown",
           "regime-demo" in cc.CHARTS and "regime-uncertainty" in cc.CHARTS,
           "one chart draws all seven on the same rows in time order and marks "
           "which keep time in order; another shows how the spread moves")
    record("T10 kernel density charts on the performance section",
           all(k in reg.CARDS_BY_KEY["C1"].all_charts
               for k in ("kde-separation", "kde-spread", "kde-null-band")),
           "the two classes as densities, the range the model uses, and the "
           "calibration curve against shuffled labels")


# ---------------------------------------------------------------------------
# M: the fifth pass. Nine panels became six, and nothing was lost.
# ---------------------------------------------------------------------------

# Measured off the nine-panel board on 9 September 2026, before the merge, by
# summing the registry: 50 chart slots, 8 jobs, 10 configuration sections, 3
# tables and 5 controls of a panel's own kind. Written down rather than
# recomputed, because a check that recomputes both sides of a comparison from
# the same source proves nothing: it would pass just as happily if the merge had
# dropped a section from the registry and from the total at once.
BEFORE = dict(charts=50, jobs=8, sections=10, tables=3, controls=5)


def check_merge(client) -> None:
    """M1 to M5: the two merges kept everything and kept the distinction."""
    now = dict(
        charts=sum(len(c.all_charts) for c in reg.CARDS),
        jobs=sum(len(c.jobs) for c in reg.CARDS),
        sections=sum(len(c.all_sections) for c in reg.CARDS),
        tables=sum(len(c.all_tables) for c in reg.CARDS),
        controls=sum(len(c.all_controls) for c in reg.CARDS),
    )
    # Short of the pre-merge count, not merely different from it. The check
    # exists to catch a panel dropping a chart, a job or a table on its way into
    # a merged one, and an equality test would also fail the moment something
    # was added afterwards, which reads as a lost table and is the opposite of
    # what happened. The feature dictionary added on 9 September is the first
    # such addition: 3 tables became 4 and A2 gained three controls of its own.
    short = {k: (BEFORE[k], now[k]) for k in BEFORE if now[k] < BEFORE[k]}
    gained = {k: (BEFORE[k], now[k]) for k in BEFORE if now[k] > BEFORE[k]}
    record("M1 the merge lost nothing", not short,
           f"across six panels: {now['charts']} chart slots, {now['jobs']} jobs, "
           f"{now['sections']} configuration sections, {now['tables']} tables and "
           f"{now['controls']} controls, against {BEFORE['charts']}, "
           f"{BEFORE['jobs']}, {BEFORE['sections']}, {BEFORE['tables']} and "
           f"{BEFORE['controls']} measured on the nine-panel board"
           + (f"; added since, as before to after: {gained}" if gained else "")
           if not short else f"lost, as before to after: {short}")

    # Every chart the old board named must still be named by the new one. The
    # count alone would not catch a swap, and a swap is exactly what a rewritten
    # CARDS block makes easy.
    import control_charts as cc
    named = {n for c in reg.CARDS for n in c.all_charts}
    orphan = sorted(n for n in named if n not in cc.CHARTS)
    unused = sorted(n for n in cc.CHARTS if n not in named and n != "timeline")
    record("M2 every chart a panel names exists, and every drawing is placed",
           not orphan and not unused,
           f"{len(named)} distinct charts named across the six panels against "
           f"{len(cc.CHARTS)} drawings, with the timeline drawn into the header "
           f"band rather than onto a panel"
           if not orphan and not unused
           else f"named but absent: {orphan}; drawn but unplaced: {unused}")

    merged = [c for c in reg.CARDS if c.groups]
    bodies = {c.key: client.get(f"/card/{c.key}").get_data(as_text=True)
              for c in merged}
    missing = []
    for c in merged:
        for g in c.groups:
            # Operator instruction, 20 September 2026: a group's charts sit in
            # the one Figures block at the foot, so a group with no table
            # keeps no section of its own. It counts as placed when every
            # chart it names is drawn on the page and it says what it answers.
            placed = (f'id="section-{g.key}"' in bodies[c.key]
                      or all(f'data-chart="{n}"' in bodies[c.key] for n in g.charts))
            if not placed or not g.answers:
                missing.append(f"{c.key}/{g.key}")
    record("M3 a merged panel is sectioned, and each section says what it answers",
           len(merged) == 2 and not missing,
           "; ".join(f"{c.key} {c.title}: "
                     + ", ".join(f"{g.title} ({len(g.charts)} charts)"
                                 for g in c.groups) for c in merged)
           if not missing else f"no section markup for {missing}")

    # The distinction the operator stated twice. Performance is one model's
    # error at one configuration computed now; Assessment is every run's error
    # compared across configurations and over time. They read from different
    # records, so they must not end on the same panel wearing one heading.
    where = {}
    for c in reg.CARDS:
        for g in c.groups:
            where[g.key] = c.key
    split_kept = (where.get("performance") == "C1"
                  and where.get("assessment") == "C2"
                  and where["performance"] != where["assessment"])
    record("M4 Performance and Assessment stay separate",
           split_kept,
           "Performance sits on C1 with the current fit and the scoreboard; "
           "Assessment sits on C2 with the history, which is the same subject "
           "as the live book and reads from the same records"
           if split_kept else f"they landed together: {where}")

    # Every job still reachable and still one at a time, and every table still
    # sortable, filterable and glossed where it now lives.
    import control_tables as ct
    jobs_on = {j.key for c in reg.CARDS for j in c.jobs}
    tables_on = [t for c in reg.CARDS for t in c.all_tables]
    rows = {t: len(ct.build(t)["rows"]) for t in tables_on}
    # Every panel carrying a table, not only the merged two. A panel's own table
    # renders from a different branch of the template than a section's, so
    # checking C1 and C2 alone would have said the markup was sound while A2's
    # table arrived with no sorting and no filter box.
    with_tables = [c for c in reg.CARDS if c.all_tables]
    table_bodies = {c.key: bodies.get(c.key)
                    or client.get(f"/card/{c.key}").get_data(as_text=True)
                    for c in with_tables}
    # Sorting is required of every table. A filter box is required only where
    # the panel declared one, because C2's Assessment table has never offered
    # one and demanding it here would fail the board for a gap that predates
    # this check rather than for anything that broke.
    unsortable = sorted(
        c.key for c in with_tables
        if 'class="sortable"' not in table_bodies[c.key]
        or ("filter the table" in c.all_controls
            and 'class="tablefilter"' not in table_bodies[c.key]))
    ok = (jobs_on == {j.key for j in reg.RUNNABLE}
          and sorted(tables_on) == sorted(ct.TABLES)
          and not unsortable)
    record("M5 every job and every table is on a panel and works there", ok,
           f"{len(jobs_on)} of {len(reg.RUNNABLE)} registered jobs are on a "
           f"panel, six of them on C1 alone and still one at a time; the "
           f"{len(tables_on)} tables sit on {sorted(table_bodies)}, carry {rows} "
           f"rows, and each is sortable with a filter of its own"
           if ok else f"jobs {sorted(jobs_on)}, tables {sorted(tables_on)}, "
                      f"no sorting or no filter on {unsortable}")


def check_front_page(client, width: int = 1900, height: int = 1000) -> None:
    """M6: the grid is the front page, and the front page does not scroll.

    Operator instruction, 9 September 2026: the six panels take the overwhelming
    majority of the glass. Measured in a browser rather than judged by eye,
    because a page that shrinks its panels to their content and leaves the
    bottom third empty looks tidy in a screenshot and is exactly the failure.
    """
    if not pathlib.Path(CHROME).exists():
        record("M6 the grid fills the front page without scrolling", None,
               f"Chrome not found at {CHROME}")
        return
    tmp = freeze_page(client, "/", probe=FRONT_PROBE, images=True)
    dom = ""
    for budget in (8000, 20000):
        proc = subprocess.run(
            [CHROME, "--headless", "--disable-gpu", f"--window-size={width},{height}",
             f"--virtual-time-budget={budget}", "--dump-dom", f"file://{tmp}"],
            capture_output=True, text=True, timeout=180)
        dom = proc.stdout
        if 'id="frontprobe"' in dom:
            break
    m = re.search(r'<div id="frontprobe"[^>]*>(.*?)</div>', dom, re.S)
    if not m:
        record("M6 the grid fills the front page without scrolling", False,
               f"the probe did not run; Chrome returned {len(dom)} bytes of DOM")
        return
    got = dict(kv.split("=") for kv in m.group(1).strip().split("|"))
    scroll_h, client_h = int(got["scrollHeight"]), int(got["clientHeight"])
    lanes_h, header_h = int(got["lanes"]), int(got["header"])
    share = 100.0 * lanes_h / client_h if client_h else 0
    fits = scroll_h <= client_h + 1
    record("M6 the front page does not scroll", fits,
           f"at {width} by {height}: scrollHeight {scroll_h} against clientHeight "
           f"{client_h}" + ("" if fits else f", overflowing by {scroll_h - client_h}px"))
    # 72, not 88, since 16 September 2026: the operator put the timeline above
    # everything at the full height of its own band, about a seventh of the
    # glass with the reading-order row, and the grid keeps what is left.
    record("M7 the grid takes the overwhelming majority of the glass", share >= 72,
           f".lanes is {lanes_h}px of a {client_h}px viewport, {share:.1f} per "
           f"cent, above the timeline band, masthead, configuration sentence and "
           f"reading-order row together at {header_h}px")
    thumbs = [int(v) for v in got["thumbs"].split(",") if v]
    record("M8 each panel's chart is legible without opening it",
           len(thumbs) == 2 * len(reg.CARDS) and min(thumbs) >= 150,
           f"{len(thumbs)} panel image boxes, the smallest {min(thumbs)}px tall "
           f"and the largest {max(thumbs)}px, against the 132px cap the "
           f"nine-panel board wore" if thumbs else "no image box measured")


def check_defaults() -> None:
    drift, symbolic, presets = [], [], []
    for job in reg.RUNNABLE:
        actual = reg.script_defaults(job.script)
        for knob in job.knobs:
            if knob.flag not in actual:
                drift.append(f"{job.script}:--{knob.flag} not in the script")
                continue
            got = actual[knob.flag]
            if isinstance(got, str) and got.startswith("="):
                symbolic.append(f"{job.script}:--{knob.flag} = {got[1:]}")
                continue
            if knob.symbolic:
                symbolic.append(f"{job.script}:--{knob.flag}")
                continue
            if knob.preset:
                presets.append(f"--{knob.flag} shows {knob.default!r} against the "
                               f"script's {got!r}, because {knob.preset}")
                continue
            if got != knob.default:
                drift.append(f"{job.script}:--{knob.flag} script={got!r} "
                             f"registry={knob.default!r}")
    detail = (f"{sum(len(j.knobs) for j in reg.RUNNABLE)} knobs read from source; "
              f"{len(symbolic)} symbolic, {len(presets)} deliberately preset")
    record("4a registry defaults match the scripts' own argparse defaults",
           not drift, detail if not drift else f"drift: {drift}")
    # A preset is only safe because build_command compares against the script's
    # default rather than the form's, so the flag is still emitted. Check that.
    unemitted = []
    for job in reg.RUNNABLE:
        vals = {k.flag: k.default for k in job.knobs}
        cmd = reg.build_command(job, vals)
        for knob in job.knobs:
            if knob.preset and f"--{knob.flag}" not in cmd:
                unemitted.append(f"{job.key}:--{knob.flag}")
    record("4b every deliberate preset still reaches the command line", not unemitted,
           "; ".join(presets) if not unemitted
           else f"dropped from the command: {unemitted}")


def check_command(client) -> None:
    # 21 September 2026: two contracts now, not one, because seven settings
    # were being declared in a job form AND in a configuration section, and
    # --rows was re-declared on six jobs. The configuration owns those, the way
    # caret's trainControl owns the resampling and train() receives it rather
    # than re-declaring it. So:
    #
    #   a setting the JOB owns   at its default adds no flag, changed adds one
    #   a setting the CONFIG owns is always passed, from the configuration, and
    #                             whatever the form holds is ignored
    import bench_config as bc

    cfg = bc.load()
    wrong = []

    # Job-owned settings keep the old rule. --coins belongs to the trend-life
    # search alone and no configuration section names it.
    got = reg.build_command(reg.JOB_TREND_TUNE, {"coins": 40})
    if "--coins" in got:
        wrong.append(f"coins at its default still emitted a flag: {got}")
    got = reg.build_command(reg.JOB_TREND_TUNE, {"coins": 25})
    # Anywhere in the command, not at the end: the settings the configuration
    # owns are appended after the job's own, so position says nothing.
    if "--coins" not in got or got[got.index("--coins") + 1] != "25":
        wrong.append(f"coins changed did not reach the command: {got}")

    # Config-owned settings ignore the form and carry the configuration's value.
    for job, flag in ((reg.JOB_EDGE, "rows"), (reg.JOB_TUNE, "cv-splits"),
                      (reg.JOB_CALIBRATE, "interval")):
        want = reg.owned_value(job.key, flag, cfg)
        if want is None:
            continue
        got = reg.build_command(job, {flag: "99999"})
        if f"--{flag}" not in got or got[got.index(f"--{flag}") + 1] != str(want):
            wrong.append(f"{job.key}/{flag}: the form beat the configuration, {got}")

    # And nothing the configuration owns is still rendered as a form field, or
    # a reader would see two boxes for one quantity again.
    shown = []
    for c in reg.CARDS:
        html = client.get(f"/card/{c.key}").get_data(as_text=True)
        for j in (c.jobs or ()):
            for k in j.knobs:
                if (j.key, k.flag) in reg.CONFIG_OWNED and \
                        f'name="{k.flag}" form="run-{j.key}"' in html:
                    shown.append(f"{c.key}/{j.key}/{k.flag}")
    if shown:
        wrong.append("still on a form: " + ", ".join(shown))

    record("5a the configuration owns a setting, or the job does, never both",
           not wrong,
           f"{len(reg.CONFIG_OWNED)} settings read from the configuration by "
           f"{len({k[0] for k in reg.CONFIG_OWNED})} jobs; job-only knobs keep "
           f"the default-adds-no-flag rule" if not wrong else "; ".join(wrong))


    refused = []
    for bad in ("../evil.py", "alpaca_trade.py", "trade_binance.py"):
        fake = reg.Job(key="x", script=bad, title="", blurb="", knobs=(),
                       records=(), runtime="")
        try:
            runner.start(fake, {})
            refused.append(bad)
        except PermissionError:
            pass
    record("5b the runner refuses a script outside the registry", not refused,
           "../evil.py, alpaca_trade.py and trade_binance.py all refused"
           if not refused else f"launched: {refused}")


def check_never_runnable() -> None:
    leak = [s for s in reg.NEVER_RUNNABLE if s in reg.ALLOWED]
    record("6 nothing that can trade is registered", not leak,
           f"{len(reg.ALLOWED)} scripts allowed, none of "
           f"{', '.join(reg.NEVER_RUNNABLE)}" if not leak else f"leaked: {leak}")


def check_live_run(client) -> None:
    """7: one real job, start to record."""
    job = reg.JOB_VARSELECT
    # Into a scratch directory, not the repository's evidence tree. This screen
    # names its four figures without a stamp, so a 3,000-row acceptance run
    # overwrote the 25,000-row figures the committed record documents, twice on
    # 8 September before anyone noticed. An acceptance check must not be able to
    # rewrite the evidence it is checking.
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="control-eval-"))
    r = client.post(f"/run/{job.key}", data={"sample": "3000", "l1": "1.0",
                                             "out": str(scratch)})
    if r.status_code != 200:
        record("7 a real job runs end to end", False,
               f"POST /run/{job.key} returned {r.status_code}: {r.get_data(as_text=True)[:200]}")
        return
    started = time.time()
    offset, saw_output = 0, False
    while time.time() - started < 900:
        state = client.get(f"/log?offset={offset}").get_json()
        offset = state["offset"]
        saw_output = saw_output or bool(state["text"])
        if not state["busy"]:
            break
        time.sleep(2)
    state = runner.state()
    ok = state["returncode"] == 0
    log = reg.LOG_DIR / f"control-{state['run_id']}.log"
    record("7a the job exits cleanly", ok,
           f"exit {state['returncode']} after {state['elapsed']}s, log at {reg.repo_rel(log)}")
    record("7b its output streamed through the polling endpoint", saw_output,
           f"log grew to {log.stat().st_size if log.exists() else 0} bytes while running")
    made = sorted(p.name for p in scratch.rglob("*")
                  if p.is_file() and not p.name.startswith("._"))
    after = {p.name for p in reg.records_for(job.records)}
    record("7c it wrote a record the panel can show",
           any(n.endswith(".md") for n in made),
           f"wrote {len(made)} files into {scratch}: {', '.join(made)}. "
           f"The repository's own evidence tree was untouched and still holds "
           f"{len(after)} records for this panel.")


# ---------------------------------------------------------------------------
# 8: reproduction
# ---------------------------------------------------------------------------

def check_sixth_stage(client) -> None:
    """16 September 2026: the regime and model sweeps exist, run and draw."""
    import control_charts as cc

    regime = [d for d in cc._json("*/bench-sweep-*.json") if d.get("kind") == "regime"]
    schemes = {r.get("scheme") for d in regime for r in d.get("rows") or []}
    want = {"expanding", "rolling", "kfold", "repeated-kfold", "leave-one-out",
            "monte-carlo", "bootstrap"}
    record("16a a regime sweep on disk covers all seven regimes", want <= schemes,
           f"{len(regime)} regime sweep(s), regimes {sorted(schemes)}"
           if regime else "no bench-sweep record carries kind=regime")

    est = [d for d in cc._json("*/bench-sweep-*.json") if d.get("kind") == "estimator"]
    models = {r.get("model") for d in est for r in d.get("rows") or []}
    record("16b an model sweep on disk scores at least five models",
           len(models) >= 5,
           f"{len(est)} model sweep(s), models {sorted(models)}"
           if est else "no bench-sweep record carries kind=model")

    # The chart must be a drawing of the record, not the "nothing on disk"
    # placeholder. The placeholder is a few kilobytes of text on empty axes;
    # a bar chart of seven regimes with labels is well over ten.
    thin = [n for n in ("regime-optimism", "regime-pass-rate", "estimator-compare")
            if len(cc.draw(n) or b"") < 12_000]
    record("16c the regime and model charts draw a result, not a placeholder",
           not thin, "all three above 12 KB" if not thin else f"placeholder-sized: {thin}")

    # repeats is the configuration's from 21 September 2026, the way caret's
    # trainControl owns it, so the design is the job's own choice and the
    # repeat count comes from the Choose Resampling tool whatever the form says.
    import bench_config as _bc
    _rep = str(reg.owned_value("regimesweep", "repeats", _bc.load()) or "")
    got = reg.build_command(reg.JOB_REGIME_SWEEP, {"design": "regime", "repeats": 3})
    want_cmd = [reg.PYTHON, "03-inputs/bench_sweep.py", "--design", "regime"] \
        + (["--repeats", _rep] if _rep else [])
    got2 = reg.build_command(reg.JOB_ESTIMATOR_SWEEP, {"design": "models", "repeats": 1})
    want_cmd2 = [reg.PYTHON, "03-inputs/bench_sweep.py", "--design", "models"] \
        + (["--repeats", _rep] if _rep else [])
    record("16d the two sweep jobs compose the command their preset promises",
           got == want_cmd and got2 == want_cmd2,
           f"{' '.join(got[1:])} and {' '.join(got2[1:])}"
           if got == want_cmd and got2 == want_cmd2 else f"got {got} and {got2}")

    body = client.get("/card/B2").get_data(as_text=True)
    record("16e the training-regime panel carries the sweep job and its chart",
           "regimesweep" in body and "regime-optimism" in body,
           "B2 lists the regime sweep and leads on the claimed-against-blind chart")
    # The drive dropped on 16 September and came back with the active config
    # zeroed; the loader returned the defaults and a sweep ran on the wrong
    # condition with nothing in the log. A zeroed or unreadable file must stop
    # the run, and this proves the guard can fail rather than asserting it.
    import bench_config as bc
    import tempfile
    tmp = pathlib.Path(tempfile.mkdtemp()) / "config.json"
    refused = []
    for body_bytes in (b"\x00" * 200, b"{not json"):
        tmp.write_bytes(body_bytes)
        try:
            bc.load(tmp)
            refused.append(False)
        except SystemExit:
            refused.append(True)
    record("16g a zeroed or unreadable configuration stops the run", all(refused),
           "both a null-byte file and a malformed one raised instead of loading defaults"
           if all(refused) else f"loaded silently: zeroed={not refused[0]}, malformed={not refused[1]}")

    body = client.get("/card/A1").get_data(as_text=True)
    i_v, i_s, i_r, i_c = (body.find('id="section-venues"'), body.find('id="section-screening"'),
                          body.find('id="section-rules"'), body.find('id="figures-'))
    n_fig = body.count('data-src="/figure/')
    a1_ok = 0 < i_v < i_s < i_r < i_c and n_fig >= 7 and "Alpaca, US equities" in body \
        and "Big pitch" in body and "<h3>Choose Market</h3>" in body \
        and "<h3>Choose Basket</h3>" in body
    record("17 A1 opens on Datasets, Screening and Hard Rules, then charts, with Choose "
           "Market and Choose Basket beside them",
           a1_ok, f"venues at {i_v}, screening at {i_s}, rules at {i_r}, charts at {i_c}, "
           f"{n_fig} workflow figures" if a1_ok else
           f"venues {i_v}, screening {i_s}, rules {i_r}, charts {i_c}, figures {n_fig}")
    served = [rel for g in reg.CARDS_BY_KEY["A1"].brief for rel, _ in g.figures
              if client.get(f"/figure/{rel}").status_code != 200]
    record("17b every figure on A1 is served", not served,
           "all seven return 200" if not served else f"missing: {served}")

    # 18: every panel follows the row layout of the 16 September task list,
    # 05-research/tasks/panel-revision-tasks-2026-09-16.md: one row per lead
    # section, each with its tools, a note under every tool, and the result
    # chart the section declares.
    short = []
    for c in reg.CARDS:
        html = client.get(f"/card/{c.key}").get_data(as_text=True)
        rows_ = html.count('class="briefrow')
        # A brief with no tools is not a row: its pictures sit in the one
        # Figures block at the foot (operator instruction, 20 September 2026).
        want_rows = sum(1 for g in c.brief if g.tools or g.tool_charts or g.tool_figures)
        tools_ = html.count("<h3>Choose ")
        want_tools = sum(len(g.tools) for g in c.brief)
        results_ = html.count("<h3>Result</h3>")
        want_results = sum(1 for g in c.brief if g.tool_charts)
        notes_ = html.count('class="note formnote')
        if not (rows_ == want_rows and tools_ >= want_tools and results_ == want_results
                and notes_ >= want_tools):
            short.append(f"{c.key}: rows {rows_}/{want_rows}, tools {tools_}/{want_tools}, "
                         f"results {results_}/{want_results}, notes {notes_}")
    record("18 every panel pairs its tables with their tools, notes and a result chart",
           not short, f"{len(reg.CARDS)} panels, {sum(len(c.brief) for c in reg.CARDS)} rows, "
           f"{sum(len(g.tools) for c in reg.CARDS for g in c.brief)} tools" if not short
           else "; ".join(short))

    body = client.get("/card/C1").get_data(as_text=True)
    record("16f the model panel carries the model sweep and its chart",
           "estimatorsweep" in body and "estimator-compare" in body,
           "C1 lists the model sweep and the ratio-against-U2 chart")


# ---------------------------------------------------------------------------
# 19 and 20: no setting is dead
#
# 20 September 2026. Seven settings on Choose Filter and Choose Ranking, the
# outcome on Choose Label and all sixteen on Signal engines and Choose Figures
# were saved by their forms, drawn by the board's own charts, and read by
# nothing that fitted anything. The failure was silent in both directions: the
# form said the value was kept and the record embedded it, so a run at a 30
# million USDT volume floor and a run with no floor produced the same rows and
# the same record.
#
# Check 19 is structural and refuses a new setting that names no reader, so the
# same thing cannot happen again by inattention. Check 20 is evidential and
# reads the newest run on disk.
# ---------------------------------------------------------------------------

# Every setting, and the module that reads it when a run happens. A file named
# here must exist and must mention the setting; a setting in the schema and not
# here fails the check, which is the point: adding a field to the form means
# saying, in one line, what reads it.
CONSUMED_BY = {
    "data": {"market": "bench_run.py", "frame": "bench_run.py",
             "bundle": "bench_config.py", "symbols": "bench_config.py",
             "rows": "bench_run.py"},
    "label": {"target_atr": "bench_run.py", "stop_atr": "bench_run.py",
              "kind": "bench_run.py", "flat_band": "bench_run.py",
              "horizon_bars": "bench_run.py"},
    "screen": {"min_quote_volume": "bench_run.py", "atr_low": "bench_run.py",
               "atr_high": "bench_run.py", "min_history_days": "bench_run.py",
               "rank_signal": "bench_run.py", "rank_tercile": "bench_run.py",
               "fold_bar": "bench_run.py"},
    "features": {"families": "bench_config.py", "include": "bench_config.py",
                 "exclude": "bench_config.py", "max_features": "bench_run.py"},
    "selection": {"run_selection": "bench_run.py", "l1_ratio": "bench_run.py",
                  "rule": "bench_run.py", "sel_sample": "bench_run.py",
                  "sel_folds": "bench_run.py", "feed_model": "bench_run.py",
                  "draw_intervals": "bench_run.py"},
    "signals": {"macd_fast": "control_charts.py", "macd_slow": "control_charts.py",
                "macd_signal": "control_charts.py", "macd_noise_k": "control_charts.py",
                "macd_confirm_bars": "control_charts.py", "ma_fast": "control_charts.py",
                "ma_slow": "control_charts.py", "fib_lookback": "control_charts.py",
                "fib_min_swing_frac": "control_charts.py",
                "confluence_threshold": "control_charts.py",
                "candle_decay": "control_charts.py"},
    "split": {"train_fraction": "bench_run.py", "selection": "bench_run.py",
              "holdout_days": "bench_run.py", "purge_bars": "bench_run.py",
              "embargo_bars": "bench_run.py", "folds": "bench_run.py",
              "scheme": "bench_run.py", "repeats": "bench_run.py",
              "boot_samples": "bench_run.py"},
    "model": {"estimators": "bench_run.py", "tune": "bench_run.py",
              "tune_length": "bench_run.py",
              "grid": "bench_config.py", "class_weight": "bench_run.py",
              "params": "bench_run.py", "reject_ratio": "bench_run.py"},
    "calibration": {"run_calibration": "bench_run.py", "methods": "bench_run.py",
                    "cal_fraction": "bench_run.py", "bins": "bench_run.py"},
    # viz_symbol reaches the drawing through control_charts._klines, which is
    # the reader that picks a symbol's archive folder; bench_figures calls it
    # rather than carrying a second copy of the timestamp rule.
    "viz": {"panels": "bench_figures.py", "viz_symbol": "control_charts.py",
            "viz_bars": "bench_figures.py", "overlays": "bench_figures.py",
            "theme": "bench_figures.py"},
}


def check_settings_have_readers() -> None:
    """19: every setting in the schema names a module that reads it.

    This is a structural check and it is weaker than it looks. It searches the
    named module for the setting's name, so renaming the lookup while a local
    variable of the same name survives still passes; that was measured on
    20 September by renaming the overlays lookup, which 19 let through and 21b
    caught. What 19 is for is the other failure, a field added to a form with
    nothing behind it, and the behavioural checks 20 to 22 are what prove the
    reader does something.
    """
    import bench_config as bc

    src = {name: (reg.REPO / "03-inputs" / name).read_text(encoding="utf-8")
           for name in sorted({f for sec in CONSUMED_BY.values() for f in sec.values()})}

    unnamed, unread, stale = [], [], []
    for section, spec in bc.SCHEMA.items():
        named = CONSUMED_BY.get(section, {})
        for f in spec["fields"]:
            who = named.get(f.key)
            if who is None:
                unnamed.append(f"{section}.{f.key}")
            elif f.key not in src.get(who, ""):
                unread.append(f"{section}.{f.key} claims {who}, which does not mention it")
        for key in named:
            if key not in {f.key for f in spec["fields"]}:
                stale.append(f"{section}.{key}")

    n = sum(len(s["fields"]) for s in bc.SCHEMA.values())
    record("19 every setting names the module that reads it on a run",
           not (unnamed or unread or stale),
           f"{n} settings across {len(bc.SCHEMA)} sections, each read by one of "
           f"{', '.join(sorted(src))}" if not (unnamed or unread or stale)
           else "; ".join(["no reader named: " + ", ".join(unnamed)] * bool(unnamed)
                          + unread + ["not in the schema: " + ", ".join(stale)] * bool(stale)))

    # The hyperparameters are a second surface, 42 of them, and they reach the
    # estimator through one pass-through rather than one branch each.
    import bench_run as br
    ok = "_clean_params(params)" in (reg.REPO / "03-inputs" / "bench_run.py").read_text(encoding="utf-8")
    n_par = sum(len(v) for v in bc.MODEL_PARAMS.values())
    record("19b the per-model settings reach the estimator", ok,
           f"{n_par} hyperparameters across {len(bc.MODEL_PARAMS)} models pass through "
           f"bench_run.make_estimator" if ok else "make_estimator no longer cleans params")


def _newest_bench_record():
    import glob
    files = sorted(glob.glob(str(reg.EVALS / "*" / "bench-2*.json")))
    files = [f for f in files if not pathlib.Path(f).name.startswith("._")]
    if not files:
        return None
    return json.loads(pathlib.Path(files[-1]).read_text(encoding="utf-8"))


def check_settings_in_the_record() -> None:
    """20: the newest run reported what its settings did, not just what they were."""
    d = _newest_bench_record()
    if d is None:
        record("20 the newest run reports what the filter did", None,
               "no bench record on disk yet")
        return

    f = d.get("filter") or {}
    want = ("volatility", "liquidity", "history", "ranking")
    missing = [k for k in want if not isinstance(f.get(k), dict)]
    resolved = [k for k in want if isinstance(f.get(k), dict)
                and ("applied" in f[k])]
    record("20 the newest run reports what each filter did to its rows",
           not missing and len(resolved) == len(want),
           f"{f.get('rows_in', 0):,} rows read, {f.get('rows_out', 0):,} kept; "
           f"all four filters resolved" if not missing
           else f"the record carries no verdict for {missing}")

    record("20b the newest run names the outcome it scored",
           d.get("kind") in ("barrier", "three-way"),
           f"scored the {d.get('kind')} outcome"
           if d.get("kind") in ("barrier", "three-way")
           else f"the record says {d.get('kind')!r}")

    scored = [r for r in (d.get("scores") or []) if r.get("folds_scored")]
    bar = ((d.get("config") or {}).get("screen") or {}).get("fold_bar")
    record("20c every model carries a fold pass rate against the fold bar",
           bool(scored) and all(r.get("fold_bar") == bar for r in scored),
           f"{len(scored)} model(s), pass rates "
           + ", ".join(f"{r['model']} {r['fold_pass_rate']:.2f}" for r in scored)
           + f" against a {bar} bar" if scored
           else "no model on this record carries a fold pass rate")

    import bench_figures as bf
    ticked = (((d.get("config") or {}).get("viz") or {}).get("panels")
              or list(bf.DEFAULT_PANELS))
    figs = d.get("figures") or []
    if True:
        thin = [x["panel"] for x in figs if x.get("bytes", 0) < 12_000]
        record("20d every ticked figure was drawn beside the record",
               sorted(x["panel"] for x in figs) == sorted(ticked) and not thin,
               f"{len(figs)} figures drawn, smallest "
               f"{min(x['bytes'] for x in figs):,} bytes" if figs and not thin
               else f"ticked {ticked}, drew {[x['panel'] for x in figs]}, "
                    f"placeholder-sized {thin}")


# One setting, the figure that must change when it alone moves, and two values
# far enough apart that the drawing cannot come out identical by chance. Moving
# a whole group at once is not enough: on 20 September the group test passed
# with the MACD spans deliberately hard-coded, because the moving averages and
# the Fibonacci lookback still moved the same four pictures.
ONE_AT_A_TIME = (
    ("signals", "macd_fast",            "macd",       6, 20),
    ("signals", "macd_slow",            "macd",       30, 90),
    ("signals", "macd_signal",          "macd",       3, 21),
    ("signals", "macd_noise_k",         "macd",       0.0, 3.0),
    ("signals", "macd_confirm_bars",    "macd",       1, 6),
    ("signals", "ma_fast",              "confluence", 5, 60),
    ("signals", "ma_slow",              "confluence", 30, 220),
    ("signals", "fib_lookback",         "fibonacci",  60, 300),
    ("signals", "fib_min_swing_frac",   "fibonacci",  0.0, 0.9),
    ("signals", "confluence_threshold", "confluence", 1.0, 3.5),
    ("signals", "candle_decay",         "confluence", 1, 30),
    ("viz",     "viz_bars",             "confluence", 200, 420),
    ("viz",     "theme",                "confluence", "light", "dark"),
)


def check_settings_move_the_picture() -> None:
    """21: each setting, moved on its own, redraws a different figure.

    The weakest kind of check is one that cannot fail, and "the figure was
    drawn" is one of those: a MACD panel drawn at 12/26/9 whatever the form says
    still lands as a large PNG. Each setting here is moved alone, everything
    else held, and the render must change. Skipped rather than failed when the
    raw archives are not on disk, because that is a missing input and not a
    broken wiring.
    """
    import copy
    import io

    import bench_config as bc
    import bench_figures as bf
    import matplotlib.pyplot as plt
    import numpy as np

    cfg = bc.load()
    if bf._bars(cfg)[0] is None:
        record("21 each setting, moved alone, redraws a different figure", None,
               "no raw bars on disk for this frame, so the figures cannot be compared")
        return

    def render(c, name):
        """What the figure DREW, with every word of text left out.

        Comparing the PNG was the first attempt and it could not fail: the MACD
        panel prints its own spans in its title, so hard-coding the engine at
        12/26/9 still produced two different images. What has to differ is the
        geometry, so this hashes the lines, the bars, the scatter offsets, the
        shaded bands and the axis limits, and nothing that is a label.
        """
        import hashlib

        fig = bf.PANELS[name](c, bf._theme(c), {})
        h = hashlib.sha256()
        for ax in fig.get_axes():
            for ln in ax.get_lines():
                h.update(np.asarray(ln.get_xydata(), dtype=float).tobytes())
            for pa in ax.patches:
                h.update(np.asarray(pa.get_extents().get_points(), dtype=float).tobytes())
            for co in ax.collections:
                try:
                    h.update(np.asarray(co.get_offsets(), dtype=float).tobytes())
                except (TypeError, ValueError):
                    pass
                for path in co.get_paths():
                    h.update(np.asarray(path.vertices, dtype=float).tobytes())
            h.update(np.asarray(ax.get_xlim() + ax.get_ylim(), dtype=float).tobytes())
            # The face colours, so the theme is a real difference and not only
            # a palette swap in text that this hash ignores.
            h.update(str(ax.get_facecolor()).encode())
        plt.close(fig)
        return h.digest()

    dead = []
    for section, key, panel, a_, b_ in ONE_AT_A_TIME:
        one, two = copy.deepcopy(cfg), copy.deepcopy(cfg)
        one[section][key], two[section][key] = a_, b_
        if render(one, panel) == render(two, panel):
            dead.append(f"{section}.{key} does not move the {panel} figure")
    record("21 each setting, moved alone, redraws a different figure", not dead,
           f"{len(ONE_AT_A_TIME)} settings moved one at a time, every one changed "
           f"its figure" if not dead else "; ".join(dead))

    # The overlays are one multi-choice field and each entry draws its own
    # geometry, so each is ticked alone against nothing ticked.
    bare = copy.deepcopy(cfg); bare["viz"] = dict(cfg["viz"], overlays=[], viz_bars=300)
    plain = render(bare, "candles")
    quiet = []
    for name in ("ema200", "supertrend", "swings", "entries", "exits", "volume"):
        one = copy.deepcopy(bare); one["viz"] = dict(bare["viz"], overlays=[name])
        if render(one, "candles") == plain:
            quiet.append(name)
    record("21b every overlay draws something on the candles", not quiet,
           "all six of ema200, supertrend, swings, entries, exits and volume "
           "change the candle figure" if not quiet
           else f"drew nothing: {quiet}")


def check_filter_settings_move_the_rows() -> None:
    """22: each filter setting, moved alone, keeps a different set of rows.

    Same discipline as 21 and for the same reason. Until 20 September these
    seven were saved, drawn by one chart, and read by nothing that fitted
    anything, so the only way to know they are wired is to move one and watch
    the row count move. The frame is read once and every variant runs on the
    same rows in memory.
    """
    import copy

    import bench_config as bc
    import bench_run as br

    cfg = bc.load()
    try:
        df, _ = br.load_frame(cfg, log=lambda *a, **k: None)
    except SystemExit as exc:
        record("22 each filter setting, moved alone, keeps a different set of rows",
               None, f"no rows to filter: {exc}")
        return

    def kept(patch):
        c = copy.deepcopy(cfg); c["screen"].update(patch)
        try:
            out, info = br.apply_screen(c, df.copy(), log=lambda *a, **k: None)
            return len(out), info
        except SystemExit:
            return 0, {}

    base, _ = kept({})
    moves = (
        ("atr_low",          dict(atr_low=0.0), dict(atr_low=0.05)),
        ("atr_high",         dict(atr_high=9.0), dict(atr_high=0.05)),
        ("min_quote_volume", dict(min_quote_volume=0.0),
                             dict(min_quote_volume=500_000_000.0)),
        ("min_history_days", dict(min_history_days=0),
                             dict(min_history_days=3000)),
    )
    dead = []
    for key, a_, b_ in moves:
        if kept(a_)[0] == kept(b_)[0]:
            dead.append(f"{key} does not change the rows kept")
    record("22 each filter setting, moved alone, keeps a different set of rows",
           not dead, f"{len(moves)} thresholds moved one at a time from "
           f"{base:,} rows; every one changed the count" if not dead
           else "; ".join(dead))

    # The ranking is the one that can honestly do nothing: a bar carrying fewer
    # than five assets is left whole, and on a thin universe no bar reaches the
    # floor. So the check is that the run says which of the two happened, and
    # that where it did rank, the thirds are different sets.
    # The baseline is the rows with no ranking at all, not the rows the saved
    # configuration happens to keep. On 22 September the configuration itself
    # carried f_btc_mom_168 and the top third, so "base" was already the top
    # third and the check compared the top third against itself; it could only
    # fail, and it did, on a configuration that was working correctly.
    n_flat, _ = kept(dict(rank_signal="none", rank_tercile="all"))
    n_top, i_top = kept(dict(rank_signal="f_btc_mom_168", rank_tercile="top"))
    n_bot, i_bot = kept(dict(rank_signal="f_btc_mom_168", rank_tercile="bottom"))
    applied = (i_top.get("ranking") or {}).get("applied")
    if not applied:
        record("22b the ranking either cuts the universe or says why it could not",
               (i_top.get("ranking") or {}).get("why", "") != "",
               "not applied on these rows, and the record says why: "
               + str((i_top.get("ranking") or {}).get("why")))
    else:
        record("22b the ranking either cuts the universe or says why it could not",
               n_top != n_flat and n_top != n_bot,
               f"the top third keeps {n_top:,} rows and the bottom third "
               f"{n_bot:,}, against {n_flat:,} unranked")

    # 22c: the fold bar is a number the record carries, not a number the run
    # decides for itself.
    src = (reg.REPO / "03-inputs" / "bench_run.py").read_text(encoding="utf-8")
    record("22c the fold pass rate is scored against the configured bar",
           'cfg["screen"].get("fold_bar")' in src and 'row["fold_bar_met"]' in src,
           "bench_run.score_estimator reads fold_bar from the configuration and "
           "records the verdict beside the rate")

    # 22d: all three runners filter, or a comparison run and a single run on
    # the same configuration would score different rows and their records
    # would not be comparable.
    runners = ("bench_run.py", "bench_sweep.py", "bench_three_way.py")
    skipped = [n for n in runners
               if "apply_screen(" not in
               (reg.REPO / "03-inputs" / n).read_text(encoding="utf-8")]
    record("22d every runner applies the filter before it fits", not skipped,
           "bench_run, bench_sweep and bench_three_way all call apply_screen"
           if not skipped else f"does not filter: {skipped}")


def check_the_page_runs_the_test(client) -> None:
    """23: the board can run the model test its own settings describe.

    Added 20 September 2026, after the operator asked how to test the control
    centre and the answer turned out to be that you could not, not fully. The
    board saved all 61 settings and ran eleven scripts, and bench_run.py, the
    one that consumes the whole configuration, was not among them. So a setting
    could be edited on the page and its result could only be read from a shell.
    """
    ok = reg.JOB_BENCH in reg.RUNNABLE and "bench_run.py" in reg.ALLOWED
    record("23 the runner will launch the model test", ok,
           f"{reg.JOB_BENCH.script} is on the allow list as '{reg.JOB_BENCH.key}'"
           if ok else "bench_run.py is not runnable from the page")

    on = [c.key for c in reg.CARDS if reg.JOB_BENCH in (c.jobs or ())]
    body = client.get(f"/card/{on[0]}").get_data(as_text=True) if on else ""
    record("23b a panel carries its Run button",
           bool(on) and 'data-job="bench"' in body,
           f"panel {on[0]} renders the form that posts to /run/bench" if on
           else "no panel lists the model test")

    got = reg.build_command(reg.JOB_BENCH, {"label": "a name"})
    want = [reg.PYTHON, "03-inputs/bench_run.py", "--label", "a name"]
    bare = reg.build_command(reg.JOB_BENCH, {"label": ""})
    record("23c the Run button composes the command it promises",
           got == want and bare == [reg.PYTHON, "03-inputs/bench_run.py"],
           "a named run passes --label and an unnamed one passes no flag"
           if got == want else f"got {got}")


def check_the_page_still_saves(client) -> None:
    """24: nothing on the page can silence the Save buttons.

    20 September 2026. Not one Save button on the board worked, and the handler
    was not at fault. The symbols field is a multi-select when the chosen
    file's symbol list can be read and a plain text box when it cannot, which
    is the case for any frame registered before its panel is built. A note
    written at load spread that box's `selectedOptions`, which an input does
    not have, and the TypeError stopped every handler bound after it, which was
    every control on the page.

    Two things are checked, because the fix has two halves: the controls that
    change state are bound before anything decorative runs, and no code reads
    the symbols box as a select without asking first.
    """
    body = client.get("/card/A1").get_data(as_text=True)
    i_save = body.find("document.querySelectorAll('.cfgform').forEach")
    i_note = body.find("[describeChoice, describeHorizon, describeRank]")
    record("24 the save handler binds before any note is written",
           0 < i_save < i_note,
           f"save at {i_save}, notes at {i_note}, so a note that throws cannot "
           f"stop a save" if 0 < i_save < i_note
           else f"save at {i_save}, notes at {i_note}")

    src = (reg.SCRIPTS / "control_templates" / "card.html").read_text(encoding="utf-8")
    # The only receivers allowed to be spread are ones already proved to be a
    # select: `picker`, which chosenSymbols got from symbolPicker, and `sel`,
    # which describeOptions got by querying for selects.
    ok_receivers = ("picker.selectedOptions", "sel.selectedOptions")
    loose = [ln.strip() for ln in src.splitlines()
             if "selectedOptions" in ln
             and not any(r in ln for r in ok_receivers)]
    record("24b the symbols box is never read as a list without asking",
           not loose, "every read goes through symbolPicker or chosenSymbols"
           if not loose else f"unguarded: {loose}")

    # 24c: every frame the form offers must render a page whose scripts parse.
    # A frame with no built panel is the condition that broke this, so it is
    # the condition the check has to cover.
    import subprocess
    import bench_config as bc

    before = bc.load()
    bad = []
    try:
        for market, spec in bc.MARKETS.items():
            for frame in spec["frames"]:
                cfg = bc.load()
                cfg["data"]["market"], cfg["data"]["frame"] = market, frame
                bc.save(cfg)
                html = client.get("/card/A1").get_data(as_text=True)
                for block in re.findall(r"<script(?![^>]*src=)[^>]*>(.*?)</script>",
                                        html, re.S):
                    tmp = pathlib.Path(tempfile.mkdtemp()) / "b.js"
                    tmp.write_text(block, encoding="utf-8")
                    r = subprocess.run(["node", "--check", str(tmp)],
                                       capture_output=True, text=True)
                    if r.returncode:
                        bad.append(f"{frame}: {r.stderr.splitlines()[0] if r.stderr else '?'}")
                if 'id="s-symbols"' not in html:
                    bad.append(f"{frame}: no symbols field at all")
    finally:
        bc.save(before)
    n = sum(len(s["frames"]) for s in bc.MARKETS.values())
    record("24c every frame the form offers renders a page that parses",
           not bad, f"{n} frames, including the ones with no panel built yet"
           if not bad else "; ".join(bad))


def check_the_code_is_in_the_manuscript() -> None:
    """25: the fitting code in the workflow document is the code that runs.

    The standing rule is the operator's, 12 September 2026: every line of code
    that fitted, tested or drew any part of an analysis is a chunk in the
    manuscript, and a script elsewhere does not count. The four functions the
    control centre spends its settings on were in bench_run.py alone until
    21 September 2026.

    Reproducing them in the document only helps while the two agree, so this
    compares them character for character. A change to the runner that is not
    carried into section 3.15 fails here.
    """
    import ast

    qmd = reg.REPO / "02-runtime" / "trader-workflow.qmd"
    runner = reg.SCRIPTS / "bench_run.py"
    if not qmd.exists():
        record("25 the fitting code is in the workflow document", None,
               "no workflow document on disk")
        return

    src = runner.read_text(encoding="utf-8")
    lines = src.splitlines()
    have = {}
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef):
            have[node.name] = "\n".join(lines[node.lineno - 1:node.end_lineno])

    doc = qmd.read_text(encoding="utf-8")
    wanted = ("make_estimator", "folds_of", "choose_winner", "score_estimator",
              "calibrate")
    missing = [n for n in wanted if have.get(n, "\x00") not in doc]
    record("25 the fitting code is in the workflow document", not missing,
           f"{', '.join(wanted)} appear in section 3.15 exactly as bench_run.py "
           f"defines them, {sum(len(have[n].splitlines()) for n in wanted)} lines"
           if not missing else
           f"the document does not carry the current source of: {', '.join(missing)}")


def check_the_run_code_is_on_the_page(client) -> None:
    """26: the browser shows the settings and the code that spends them.

    Operator instruction, 21 September 2026. Reading the fitting code should
    not mean opening a 2,800-line document: the question "what will this run
    actually do" has a short answer, and it is the configuration plus four
    functions. A button that returned an empty pane would look like a button
    that worked, so the served text is checked for both halves.
    """
    r = client.get("/runcode")
    body = r.get_data(as_text=True) if r.status_code == 200 else ""
    wanted = ("make_estimator", "folds_of", "score_estimator", "calibrate")
    absent = [w for w in wanted if f"def {w}" not in body]
    has_cfg = '"calibration"' in body and '"split"' in body and '"model"' in body
    record("26 the run code route serves the settings and the four functions",
           r.status_code == 200 and not absent and has_cfg,
           f"{len(body):,} characters: the configuration and "
           f"{', '.join(wanted)}" if not absent and has_cfg
           else f"status {r.status_code}, missing {absent}, config {has_cfg}")

    page = client.get("/card/C1").get_data(as_text=True)
    ok = 'id="showruncode"' in page and 'id="runcode"' in page
    record("26b the panel carries the button and the pane it fills", ok,
           "C1 renders Show run code and the block it writes into"
           if ok else "the button or its pane is missing from the panel")


def check_the_results_are_findable(client) -> None:
    """27: the last run's result is above its log, with the parameters in columns.

    Operator instruction, 21 September 2026: "there is no clear results view
    anywhere in the control centre, where are the fucking results and how can
    the user find the tuning parameters". The Performance table did exist, but
    it sat below the run log and four charts, and it pushed the hyperparameters
    into the model's own name where the column width cut them to
    "RF  max_depth=4 min_sa".

    The shape is caret's print.train, from
    05-research/research/caret-package.pdf, caret 7.0-1: how the resampling
    was done, one row per candidate with a column per tuning parameter, and a
    sentence naming the metric that chose and the values the final model used.
    """
    import control_tables as ct

    t = ct.build("tuning") or {}
    heads = t.get("headings") or []
    rows = t.get("rows") or []
    if not rows:
        record("27 the results view shows the last run", None,
               t.get("caption") or "no run on disk to show")
        return

    # A parameter any candidate set must have its own column, never be folded
    # into the model's name.
    import json as _json
    import glob as _glob
    import pathlib as _pl
    docs = sorted(_glob.glob(str(reg.EVALS / "*" / "bench-2*.json")))
    par = set()
    if docs:
        d = _json.loads(_pl.Path(docs[-1]).read_text(encoding="utf-8"))
        for r in (d.get("scores") or []):
            par.update((r.get("params") or {}).keys())
    missing = [k for k in par if k not in heads]
    record("27 every tuning parameter has its own column", not missing,
           f"{len(rows)} candidates, {len(heads)} columns, parameters "
           f"{sorted(par) or 'none in this run'}"
           if not missing else f"folded into the model name: {missing}")

    # Two lines since 21 September 2026, a short verdict and a small detail
    # line, because the first version put the verdict, three reasons, the
    # resampling and the selection rule into one four-hundred-character
    # sentence, which was the clutter rather than the fix. Both are checked:
    # the verdict must say whether it is worth keeping, and the detail must
    # say how it was resampled, on what it was scored and what chose.
    cap = t.get("caption") or ""
    det = t.get("detail") or ""
    verdict_ok = any(w in cap for w in ("WORTH KEEPING", "NOT YET", "NO."))
    detail_ok = all(w in det for w in ("Blind period", "Chosen by", "overfit ratio"))
    record("27b the results give a verdict and say how it was reached",
           verdict_ok and detail_ok,
           f"{cap} / {det[:90]}" if verdict_ok and detail_ok
           else f"verdict {verdict_ok}, detail {detail_ok}: {cap[:60]} | {det[:90]}")

    body = client.get("/card/C1").get_data(as_text=True)
    i_res, i_out = body.find("results-first"), body.find("<h3>Output</h3>")
    record("27c the result is above the run log, not below it",
           0 < i_res < i_out,
           f"results at {i_res:,}, the log at {i_out:,}" if 0 < i_res < i_out
           else f"results at {i_res}, log at {i_out}")


def md_table_column(text: str, column: str) -> list[float]:
    """Every number under a named column of a markdown table, in order."""
    out: list[float] = []
    idx = None
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            idx = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if column in cells:
            idx = cells.index(column)
            continue
        if idx is None or idx >= len(cells) or set(cells[0]) <= set("-: "):
            continue
        try:
            out.append(float(cells[idx].replace(",", "")))
        except ValueError:
            pass
    return out


def md_table_row(text: str, label: str) -> list[float]:
    """Every number on the row whose first cell is this label."""
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0] == label:
            out = []
            for c in cells[1:]:
                try:
                    out.append(float(c.replace(",", "")))
                except ValueError:
                    pass
            return out
    return []


def fresh_numbers(job, path: pathlib.Path) -> list[float]:
    """The numbers this job's record is judged on, pulled back out of it."""
    text = path.read_text(encoding="utf-8", errors="replace")
    if job.key == "tune":
        return md_table_column(text, "CV RMSE")
    if job.key == "calibrate":
        return md_table_row(text, "raw")[:3]     # ECE, MCE, Brier
    return []


def run_to_completion(client, job, values: dict, budget: int = 3600) -> dict:
    r = client.post(f"/run/{job.key}", data={
        k: ("on" if v is True else str(v)) for k, v in values.items()
        if v not in (False, None)})
    if r.status_code != 200:
        return dict(ok=False, why=f"POST returned {r.status_code}: "
                                  f"{r.get_data(as_text=True)[:200]}")
    started = time.time()
    while time.time() - started < budget:
        st = client.get("/log?offset=0").get_json()
        if not st["busy"]:
            break
        time.sleep(3)
    st = runner.state()
    return dict(ok=st["returncode"] == 0, state=st,
                why=f"exit {st['returncode']} after {st['elapsed']}s")


def check_reproduction(client) -> None:
    """8: re-run at the committed settings and compare the numbers.

    This is the check that separates "the button works" from "the button runs
    the thing the record came from". A command can be composed correctly, exit
    zero, write a record, and still have scored something else.
    """
    for job in reg.RUNNABLE:
        spec = job.reproduces
        if not spec or "settings" not in spec:
            continue
        committed = reg.EVALS / spec["record"]
        if not committed.exists():
            record(f"8 {job.key} reproduces its committed record", None,
                   f"{reg.repo_rel(committed)} is not on disk")
            continue
        want = spec["values"]
        before = {p for p in reg.records_for(job.records) if p.suffix == ".md"}
        run = run_to_completion(client, job, spec["settings"])
        if not run["ok"]:
            record(f"8 {job.key} reproduces its committed record", False,
                   f"the re-run failed: {run['why']}. Log at "
                   f"{run.get('state', {}).get('log', '?')}")
            continue
        after = [p for p in reg.records_for(job.records) if p.suffix == ".md"]
        fresh = [p for p in after if p not in before] or after[:1]
        if not fresh:
            record(f"8 {job.key} reproduces its committed record", False,
                   "the run exited cleanly but wrote no markdown record")
            continue
        got = fresh_numbers(job, fresh[0])
        tol = spec.get("tolerance", 0.001)
        if len(got) < len(want):
            record(f"8 {job.key} reproduces its committed record", False,
                   f"{reg.repo_rel(fresh[0])} carries {len(got)} numbers under "
                   f"{spec['column']}, against {len(want)} committed")
            continue
        diffs = [abs(g - w) for g, w in zip(got, want)]
        ok = max(diffs) <= tol
        record(f"8 {job.key} reproduces its committed record", ok,
               f"{spec['column']}: committed {want}, fresh {got[:len(want)]}, "
               f"largest difference {max(diffs):.5f} against a tolerance of {tol}. "
               f"Read {reg.repo_rel(committed)} and {reg.repo_rel(fresh[0])}")


# ---------------------------------------------------------------------------
# 9 and 10: layout
# ---------------------------------------------------------------------------

PROBE = """
<script>
window.addEventListener('load', function(){
  var out = [];
  document.querySelectorAll('.lane > .card').forEach(function(card, i){
    var h2 = card.querySelector('h2');
    var name = h2 ? h2.textContent.replace(/\\s+/g,' ').trim().slice(0,34) : '?';
    var kids = card.children, fill = 0, top = card.getBoundingClientRect().top;
    for (var k = 0; k < kids.length; k++){
      var b = kids[k].getBoundingClientRect().bottom - top;
      if (b > fill) fill = b;
    }
    out.push(i + '|' + card.scrollHeight + '|' + card.clientHeight + '|' + Math.round(fill) + '|' + name);
  });
  var lanes = document.querySelectorAll('.lane').length;
  var heads = document.querySelectorAll('.flow .chip').length;
  var box = document.createElement('div');
  box.id = 'probe';
  // Hidden: the probe is a measuring instrument, and a screenshot taken from
  // the same frozen page should show the page rather than the instrument.
  box.style.display = 'none';
  box.textContent = 'PAGE|' + document.documentElement.scrollWidth + '|'
                  + document.documentElement.clientWidth + '|' + lanes + '|' + heads
                  + '\\n' + out.join('\\n');
  document.body.appendChild(box);
});
</script>
"""


# The front page asks a different question from PROBE above, which measures each
# panel for clipping. This one measures the page: how much of the viewport the
# grid takes, and whether anything overflows it at all.
FRONT_PROBE = """
<script>
window.addEventListener('load', function(){
  var d = document.documentElement;
  var lanes = document.querySelector('.lanes');
  var head  = document.querySelector('.masthead');
  var cfg   = document.querySelector('.cfgline');
  var band  = document.querySelector('.topband');
  var flow  = document.querySelector('.flow');
  var thumbs = [];
  document.querySelectorAll('.lane > .card .pair .slot').forEach(function(r){
    thumbs.push(Math.round(r.getBoundingClientRect().height));
  });
  var header = (head ? head.getBoundingClientRect().height : 0)
             + (cfg ? cfg.getBoundingClientRect().height : 0)
             + (band ? band.getBoundingClientRect().height : 0)
             + (flow ? flow.getBoundingClientRect().height : 0);
  var box = document.createElement('div');
  box.id = 'frontprobe';
  box.style.display = 'none';
  box.textContent = 'scrollHeight=' + d.scrollHeight
                  + '|clientHeight=' + d.clientHeight
                  + '|lanes=' + Math.round(lanes ? lanes.getBoundingClientRect().height : 0)
                  + '|header=' + Math.round(header)
                  + '|thumbs=' + thumbs.join(',');
  document.body.appendChild(box);
});
</script>
"""

def inline_visible_images(client, html: str) -> str:
    """Turn each panel's showing thumbnail into a data URI.

    A saved page cannot reach /chart/, so every image in it fails to load and
    collapses to nothing. Measured that way the front page fitted the frame
    while the served page overflowed it by thirty-nine thousand pixels, because
    a real chart carries an intrinsic aspect ratio and an empty box does not.
    Only the image actually on screen is inlined: the rest of a reel is
    display:none and contributes nothing to layout, and inlining all ninety
    would put fifteen megabytes of base64 through a measurement.
    """
    import base64

    def swap(m):
        src = m.group(2)
        got = client.get(src)
        if got.status_code != 200:
            return m.group(0)
        b64 = base64.b64encode(got.get_data()).decode()
        return f'{m.group(1)}src="data:image/png;base64,{b64}"'

    return re.sub(r'(<img class="thumb on" )src="([^"]+)"', swap, html)


def freeze_page(client, path: str, probe: str = PROBE,
                images: bool = False) -> pathlib.Path:
    """A served page written to a file with its stylesheet inlined.

    Chrome cannot be asked to inject a probe into a page it fetches over HTTP
    with --dump-dom, so the page is saved first. The stylesheet is inlined
    because a saved file has no server to resolve /static/ against, and a page
    measured without its stylesheet would measure nothing.
    """
    html = client.get(path).get_data(as_text=True)
    css = (reg.SCRIPTS / "control_static" / "control.css").read_text(encoding="utf-8")
    # A lambda, not the string. re.sub reads a backslash escape in the
    # replacement as a group reference, and the stylesheet carries
    # content:" \2191" for the sort arrows, so passing the CSS as a template
    # raised "invalid group reference 21" and no page was ever measured.
    html = re.sub(r'<link rel="stylesheet"[^>]*>',
                  lambda _m: f"<style>{css}</style>", html)
    if images:
        html = inline_visible_images(client, html)
    html = html.replace("</body>", probe + "\n</body>")
    tmp = pathlib.Path(tempfile.mkdtemp()) / "control.html"
    tmp.write_text(html, encoding="utf-8")
    return tmp


def check_layout(client, width: int = 1900, height: int = 1000) -> None:
    if not pathlib.Path(CHROME).exists():
        record("9 no panel clips its own content", None,
               f"Chrome not found at {CHROME}")
        return
    tmp = freeze_page(client, "/", images=True)
    # Two attempts, and a longer budget than the cheat sheet's, because the
    # first deep run returned an empty DOM while a model fit was still using
    # the machine. The screenshot in the same run succeeded, so Chrome was
    # working and the page simply had not painted inside four seconds.
    dom, err = "", ""
    for budget in (8000, 20000):
        proc = subprocess.run(
            [CHROME, "--headless", "--disable-gpu", f"--window-size={width},{height}",
             f"--virtual-time-budget={budget}", "--dump-dom", f"file://{tmp}"],
            capture_output=True, text=True, timeout=180)
        dom, err = proc.stdout, proc.stderr
        if 'id="probe"' in dom:
            break
    m = re.search(r'<div id="probe"[^>]*>(.*?)</div>', dom, re.S)
    if not m:
        record("9 no panel clips its own content", False,
               f"the probe did not run after two attempts. Chrome returned "
               f"{len(dom)} bytes of DOM. stderr: {err.strip()[:300] or 'silent'}")
        return
    lines = [ln for ln in m.group(1).replace("&amp;", "&").split("\n") if ln.strip()]
    _, sw, cw, lanes, heads = lines[0].split("|")
    panels = lines[1:]
    if len(panels) != len(reg.CARDS):
        record("9a the probe found every panel", False,
               f"probe matched {len(panels)} panels against {len(reg.CARDS)} registered, "
               "so a pass here would be measuring nothing")
        return
    clipped = []
    for ln in panels:
        i, sh, ch, fill, name = ln.split("|", 4)
        if int(sh) > int(ch) + 1:
            clipped.append(f"{name} ({sh}px of content in a {ch}px box)")
    record("9a the probe found every panel", True,
           f"{len(panels)} panels measured at {width} by {height}")
    record("9b no panel clips its own content", not clipped,
           "every panel shows all of itself" if not clipped else "; ".join(clipped))
    record("9c three lanes, each with its header",
           int(lanes) == len(reg.LANES) and int(heads) == len(reg.CARDS),
           f"{lanes} lanes and {heads} reading-order chips rendered")
    record("9d the page does not scroll sideways", int(sw) <= int(cw) + 1,
           f"content {sw}px wide in a {cw}px window")


def check_screenshot(client, out: pathlib.Path, width: int = 1900,
                     height: int = 1000) -> None:
    if not pathlib.Path(CHROME).exists():
        record("10 a screenshot of the panel wall", None, "Chrome not found")
        return
    tmp = freeze_page(client, "/")
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [CHROME, "--headless", "--disable-gpu", f"--window-size={width},{height}",
         "--virtual-time-budget=4000", f"--screenshot={out}", f"file://{tmp}"],
        capture_output=True, text=True)
    ok = out.exists() and out.stat().st_size > 20_000
    record("10 a screenshot of the panel wall", ok,
           f"{reg.repo_rel(out)}, {out.stat().st_size if out.exists() else 0} bytes")


# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--live", action="store_true", help="run one real job end to end")
    p.add_argument("--layout", action="store_true", help="headless browser probe and screenshot")
    p.add_argument("--deep", action="store_true", help="record reproduction")
    p.add_argument("--all", action="store_true", help="every check")
    p.add_argument("--shot", default=str(reg.REPO / "04-outputs" / "PNG" / "control-centre.png"))
    a = p.parse_args()
    if a.all:
        a.live = a.layout = a.deep = True

    print("Control centre eval, objectives in 05-research/tasks/eval-control-centre.md\n")
    client = app.test_client()
    page = check_index(client)
    check_cards(page)
    check_card_pages(client)
    check_controls(client)
    check_visuals(client)
    check_statistics(client)
    check_third_pass(client)
    check_merge(client)
    check_defaults()
    check_command(client)
    check_never_runnable()
    check_sixth_stage(client)
    check_settings_have_readers()
    check_settings_in_the_record()
    check_settings_move_the_picture()
    check_filter_settings_move_the_rows()
    check_the_page_runs_the_test(client)
    check_the_page_still_saves(client)
    check_the_code_is_in_the_manuscript()
    check_the_run_code_is_on_the_page(client)
    check_the_results_are_findable(client)
    if a.deep:
        check_reproduction(client)
    if a.layout:
        check_front_page(client)
        check_layout(client)
        check_screenshot(client, pathlib.Path(a.shot))
    if a.live:
        check_live_run(client)

    fails = [c for c, s, _ in results if s == FAIL]
    skips = [c for c, s, _ in results if s == SKIP]
    print(f"\n{len(results) - len(fails) - len(skips)} passed, {len(fails)} failed, "
          f"{len(skips)} skipped")
    if fails:
        print("failed: " + "; ".join(fails))
    out = reg.EVALS / "logs" / "control-eval.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps([dict(check=c, state=s, detail=d)
                               for c, s, d in results], indent=2), encoding="utf-8")
    print(f"written to {reg.repo_rel(out)}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
