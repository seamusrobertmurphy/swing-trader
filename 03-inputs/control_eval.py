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
    ids = re.findall(r'href="/card/([A-E]\d)"', page)
    expected = [c.key for c in reg.CARDS]
    record("2a every panel present, in cheat-sheet order", ids == expected,
           f"{len(ids)} panels rendered: {' '.join(ids)}")
    lanes = re.findall(r'class="lane-k">([A-E])<', page)
    record("2b five lanes", lanes == [k for k, _, _ in reg.LANES],
           f"lane headers rendered: {' '.join(lanes)}")
    wrong = [c.key for c in reg.CARDS
             if f'class="card {c.colour}" href="/card/{c.key}"' not in page]
    record("2c each panel keeps the cheat sheet's colour class", not wrong,
           "every panel carries its own class" if not wrong
           else f"colour class missing on {wrong}")


def check_card_pages(client) -> None:
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
    record("3a every panel page opens", not bad,
           "15 panel pages returned 200" if not bad else f"failures: {bad}")
    record("3b every knob has a field on the form", not missing,
           f"{sum(len(j.knobs) for j in reg.RUNNABLE)} fields rendered across "
           f"{len(reg.RUNNABLE)} jobs" if not missing else f"absent: {missing}")


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
    before = {p.name for p in reg.records_for(job.records)}
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


def freeze_page(client, path: str) -> pathlib.Path:
    """A served page written to a file with its stylesheet inlined.

    Chrome cannot be asked to inject a probe into a page it fetches over HTTP
    with --dump-dom, so the page is saved first. The stylesheet is inlined
    because a saved file has no server to resolve /static/ against, and a page
    measured without its stylesheet would measure nothing.
    """
    html = client.get(path).get_data(as_text=True)
    css = (reg.SCRIPTS / "control_static" / "control.css").read_text(encoding="utf-8")
    html = re.sub(r'<link rel="stylesheet"[^>]*>', f"<style>{css}</style>", html)
    html = html.replace("</body>", PROBE + "\n</body>")
    tmp = pathlib.Path(tempfile.mkdtemp()) / "control.html"
    tmp.write_text(html, encoding="utf-8")
    return tmp


def check_layout(client, width: int = 1600, height: int = 1000) -> None:
    if not pathlib.Path(CHROME).exists():
        record("9 no panel clips its own content", None,
               f"Chrome not found at {CHROME}")
        return
    tmp = freeze_page(client, "/")
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
    record("9c five lanes, each with its header", int(lanes) == 5 and int(heads) == 5,
           f"{lanes} lanes and {heads} lane headers rendered")
    record("9d the page does not scroll sideways", int(sw) <= int(cw) + 1,
           f"content {sw}px wide in a {cw}px window")


def check_screenshot(client, out: pathlib.Path, width: int = 1600,
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
    check_defaults()
    check_command()
    check_never_runnable()
    if a.deep:
        check_reproduction(client)
    if a.layout:
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
