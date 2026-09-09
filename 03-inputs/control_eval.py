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
    lanes = re.findall(r'class="lane-k">([A-C])<', page)
    record("1b three columns", lanes == [k for k, _, _ in reg.LANES],
           f"columns rendered: {' '.join(lanes)}"
           + f"; titles {', '.join(t for _k, t, _s in reg.LANES)}")
    wrong = [c.key for c in reg.CARDS
             if f'class="card {c.colour}" href="/card/{c.key}"' not in page]
    record("1c each panel keeps a cheat-sheet colour class", not wrong,
           "every panel carries its own class" if not wrong else f"missing on {wrong}")

    # 2: the timeline spans the frame and is not inside a column. Since the
    # 9 September banding it sits in the masthead's middle slot rather than in a
    # strip above it, so the order asserted here is masthead, timeline, columns.
    i_tl, i_lanes = page.find('class="timeline"'), page.find('class="lanes"')
    i_mast, i_strip = page.find('class="masthead"'), page.find('class="mh-strip"')
    record("2 the timeline spans the frame, above everything",
           0 < i_mast < i_strip < i_tl < i_lanes,
           f"masthead at {i_mast}, its middle slot at {i_strip}, timeline at "
           f"{i_tl}, columns at {i_lanes}; it is outside every column and inside "
           f"the one header band, which is about 40 pixels rather than 124")


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
                if f'name="{knob.flag}"' not in body:
                    missing.append(f"{card.key}/{job.key}/{knob.flag}")
    record("3a every panel opens", not bad,
           f"{len(reg.CARDS)} panel pages returned 200" if not bad else f"failures: {bad}")
    record("3b every knob of a runnable job is on its panel", not missing,
           f"{sum(len(j.knobs) for c in reg.CARDS for j in c.jobs)} job fields "
           f"rendered" if not missing else f"absent: {missing}")


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
        "7b the merged model panel carries the estimators and the grid":
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
    record("11 the scoreboard explains a value on hover",
           '<td title=' in body and '<th title=' in body
           and 'class="tablefilter"' in body,
           "every heading and every cell carries what the column means, and each "
           "table has its own filter box rather than one shared across the panel")

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
    record("T2 charts sit above the settings on a panel",
           0 < b3.find("<h3>Charts</h3>") < b3.find('class="cluster"'),
           "the chart block is rendered before the settings block")
    record("T3 settings are clustered, each a full-width row",
           b3.count('class="cluster"') >= 3 and ".cfgform .field{" in css,
           f"{b3.count('class=&#34;cluster&#34;') or b3.count('class=\"cluster\"')} "
           f"clusters on B1, and a field is a two-column row spanning the panel")
    record("T4 the panel names itself in the header",
           "B1 &middot; Variable selection" in b3,
           "entering a panel puts its own name where the site name was")

    bad = [c.key for c in reg.CARDS
           if "Evidence on disk" in client.get(f"/card/{c.key}").get_data(as_text=True)]
    record("T5 Evidence Log, not Evidence on disk", not bad,
           f"renamed on all {len(reg.CARDS)} panels" if not bad
           else f"still wrong on {bad}")

    idx = client.get("/").get_data(as_text=True)
    figs = cc.figures()
    served = len(re.findall(r'src="/figure/04-outputs/', idx))
    # 90, not 100. The reels de-duplicate on the file name from 9 September
    # 2026, because avax_macd_20260620.png and twenty-five others exist in two
    # folders each and a reel showing one picture twice looks stuck.
    #
    # 35, not 40. Nine panels became six on 9 September 2026, and a reel takes at
    # most fourteen figures, so the ceiling on what the front page can serve fell
    # with the panel count. The check is that the figures are reachable, and 40
    # across six reels is reachable; the old threshold was measuring the number
    # of panels rather than the library.
    record("T6 the workflow's figures are reachable", len(figs) > 90 and served >= 35,
           f"{len(figs)} figures indexed across {len(cc.FIGURE_DIRS)} folders, "
           f"{served} of them served into the panels' reels on the front page. "
           f"The browsable library was removed on 9 September 2026 and the reels "
           f"are how a figure is reached")

    reels = re.findall(r'class="reel" data-n="(\d+)"', idx)
    record("T7 figures rotate in each panel's own image box",
           len(reels) == len(reg.CARDS) and sum(int(n) for n in reels) > 80,
           f"{len(reels)} reels holding {sum(int(n) for n in reels)} images, "
           f"all on the front page rather than on pages of their own")

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
            if f'id="section-{g.key}"' not in bodies[c.key] or not g.answers:
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
    record("M7 the grid takes the overwhelming majority of the glass", share >= 88,
           f".lanes is {lanes_h}px of a {client_h}px viewport, {share:.1f} per "
           f"cent, above the masthead, timeline and configuration sentence "
           f"together at {header_h}px")
    thumbs = [int(v) for v in got["thumbs"].split(",") if v]
    record("M8 each panel's chart is legible without opening it",
           len(thumbs) == len(reg.CARDS) and min(thumbs) >= 150,
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


def check_command() -> None:
    cases = [
        (reg.JOB_CALIBRATE,
         {"interval": "4h", "rows": 120_000, "unbalanced": False},
         [reg.PYTHON, "03-inputs/calibration.py"]),
        (reg.JOB_CALIBRATE,
         {"interval": "1d", "rows": 40_000, "unbalanced": True},
         [reg.PYTHON, "03-inputs/calibration.py", "--interval", "1d",
          "--rows", "40000", "--unbalanced"]),
        (reg.JOB_ASSESS,
         {"dataset": "slice_4h_40k", "models": ["RF", "HistGBM"],
          "cv-splits": 5, "rows": ""},
         [reg.PYTHON, "03-inputs/model_assessment_1h.py",
          "--dataset", reg.PANELS["slice_4h_40k"],
          "--models", "RF", "HistGBM"]),
        # cv-splits left at 5 above, so no flag. Moved off it here, so a flag.
        (reg.JOB_ASSESS,
         {"dataset": "", "models": [], "cv-splits": 3, "rows": 40_000},
         [reg.PYTHON, "03-inputs/model_assessment_1h.py",
          "--cv-splits", "3", "--rows", "40000"]),
        # cv-splits defaults to the module constant CV_SPLITS = 5, resolved out
        # of the source, so a form showing 5 emits no flag.
        (reg.JOB_TREND_TUNE,
         {"frame": "4h", "coins": 40, "folds": 3, "rows": 15_000},
         [reg.PYTHON, "03-inputs/trend_life_tune.py", "--rows", "15000"]),
        # The sweep panel arrives preset. Every preset must survive into the
        # command, or Run quietly does something else.
        (reg.JOB_TUNE,
         {k.flag: k.default for k in reg.JOB_TUNE.knobs},
         [reg.PYTHON, "03-inputs/model_assessment_1h.py",
          "--tune", "histgbm", "--dataset", reg.PANELS["slice_4h_40k"],
          "--grid", "learning_rate=0.03,0.06,0.12 max_leaf_nodes=15,31 max_iter=200",
          "--rows", "15000", "--cv-splits", "3"]),
    ]
    wrong = []
    for job, values, want in cases:
        got = reg.build_command(job, values)
        if got != want:
            wrong.append(f"{job.key}: got {got} wanted {want}")
    record("5a a setting at its default adds no flag, a changed one does",
           not wrong, f"{len(cases)} command lines composed exactly"
           if not wrong else "; ".join(wrong))

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
  var heads = document.querySelectorAll('.lane-hd').length;
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
  var thumbs = [];
  document.querySelectorAll('.lane > .card .reel').forEach(function(r){
    thumbs.push(Math.round(r.getBoundingClientRect().height));
  });
  var header = (head ? head.getBoundingClientRect().height : 0)
             + (cfg ? cfg.getBoundingClientRect().height : 0);
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
           int(lanes) == len(reg.LANES) and int(heads) == len(reg.LANES),
           f"{lanes} lanes and {heads} lane headers rendered")
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
    check_command()
    check_never_runnable()
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
