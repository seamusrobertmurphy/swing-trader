"""The control centre: the cheat sheet, with the panels made operable.

Run it:

    .venv/bin/python 03-inputs/control_centre.py          # http://127.0.0.1:8787
    05-research/scripts/control_centre.sh                 # same, with the checks

Fifteen panels in five lanes, laid out and coloured exactly as
05-research/cheatsheets/swing-trader-cheatsheet.html. Every panel opens its
evidence. Five of them carry a settings form: change a number, press Run, watch
the script's own output arrive line by line, and read the dated record it wrote
when it finishes.

Three deliberate limits.

Nothing runs inside this process. Every job is a subprocess under the project
interpreter, so a job the machine kills takes the job down and leaves the page
up, which matters on a machine already four and a half gigabytes into swap.

One job at a time. A second Run while one is going is refused with the name of
what is running, because two panels of the 4h frame at once is how the render
died in September.

Nothing here can trade. The runner will only launch a script named in
control_registry.ALLOWED, LIVE_TRADING is forced to false for every child, and
the four scripts that can move money are listed in NEVER_RUNNABLE so their
absence reads as a decision.
"""

from __future__ import annotations

import html
import json
import re
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file

import control_registry as reg

APP_DIR = Path(__file__).resolve().parent
app = Flask(
    __name__,
    template_folder=str(APP_DIR / "control_templates"),
    static_folder=str(APP_DIR / "control_static"),
)

try:                                    # nicer records where the library exists
    import markdown as _md
except ImportError:                     # and a readable fallback where it does not
    _md = None


# ---------------------------------------------------------------------------
# The runner
# ---------------------------------------------------------------------------

class Runner:
    """One job at a time, its output on disk, its state readable while it runs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.proc: subprocess.Popen | None = None
        self.run_id: str = ""
        self.job_key: str = ""
        self.command: list[str] = []
        self.log_path: Path | None = None
        self.started: float = 0.0
        self.finished: float = 0.0
        self.returncode: int | None = None

    @property
    def busy(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self, job: reg.Job, values: dict) -> dict:
        if job.script not in reg.ALLOWED:
            raise PermissionError(f"{job.script} is not a registered job")
        command = reg.build_command(job, values)
        with self._lock:
            if self.busy:
                raise RuntimeError(f"{self.job_key} is already running")
            reg.LOG_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            self.run_id = f"{job.key}-{stamp}"
            self.job_key = job.key
            self.command = command
            self.log_path = reg.LOG_DIR / f"control-{self.run_id}.log"
            self.returncode = None
            self.finished = 0.0
            self.started = time.time()
            header = (f"$ {' '.join(command)}\n"
                      f"# started {datetime.now():%Y-%m-%d %H:%M:%S}\n"
                      f"# working directory {reg.REPO}\n\n")
            self.log_path.write_text(header, encoding="utf-8")
            handle = self.log_path.open("a", encoding="utf-8", buffering=1)
            self.proc = subprocess.Popen(
                command, cwd=str(reg.REPO), env=reg.env_for_run(),
                stdout=handle, stderr=subprocess.STDOUT, text=True,
            )
            threading.Thread(target=self._reap, args=(self.proc, handle),
                             daemon=True).start()
        return self.state()

    def _reap(self, proc: subprocess.Popen, handle) -> None:
        code = proc.wait()
        elapsed = time.time() - self.started
        handle.write(f"\n# finished with exit code {code} after "
                     f"{elapsed:.0f} seconds\n")
        handle.close()
        self.returncode = code
        self.finished = time.time()

    def stop(self) -> None:
        if self.busy and self.proc is not None:
            self.proc.terminate()

    def state(self) -> dict:
        return dict(
            run_id=self.run_id, job=self.job_key, busy=self.busy,
            command=" ".join(self.command),
            returncode=self.returncode,
            elapsed=int((self.finished or time.time()) - self.started) if self.started else 0,
            log=reg.repo_rel(self.log_path) if self.log_path else "",
        )

    def tail(self, offset: int) -> dict:
        text = ""
        if self.log_path and self.log_path.exists():
            with self.log_path.open("r", encoding="utf-8", errors="replace") as fh:
                fh.seek(offset)
                text = fh.read()
                offset = fh.tell()
        st = self.state()
        st.update(text=text, offset=offset)
        return st


runner = Runner()


# ---------------------------------------------------------------------------
# Reading records back
# ---------------------------------------------------------------------------

def render_record(path: Path) -> str:
    """One saved record as HTML, whatever shape it was written in."""
    suffix = path.suffix.lower()
    if suffix == ".png":
        return f'<img src="/file/{reg.repo_rel(path)}" alt="{html.escape(path.name)}">'
    if suffix == ".json":
        body = json.dumps(json.loads(path.read_text(encoding="utf-8")), indent=2)
        return f"<pre class='rec'>{html.escape(body[:20000])}</pre>"
    text = path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".csv":
        return csv_table(text)
    if _md is not None:
        return _md.markdown(text, extensions=["tables", "fenced_code"])
    return f"<pre class='rec'>{html.escape(text)}</pre>"


def csv_table(text: str, max_rows: int = 40) -> str:
    """A comma-separated record as a table, truncated with the true count."""
    import csv
    import io

    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return "<p class='note'>Empty file.</p>"
    head, body = rows[0], rows[1:]
    cells = "".join(f"<th>{html.escape(c)}</th>" for c in head)
    out = [f"<table><thead><tr>{cells}</tr></thead><tbody>"]
    for r in body[:max_rows]:
        out.append("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in r) + "</tr>")
    out.append("</tbody></table>")
    if len(body) > max_rows:
        out.append(f"<p class='note'>First {max_rows} of {len(body)} rows.</p>")
    return "".join(out)


STAMP_RE = re.compile(r"(\d{4})-?(\d{2})-?(\d{2})")


def record_summary(path: Path) -> dict:
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    return dict(
        name=path.name,
        rel=reg.repo_rel(path),
        when=mtime.strftime("%d %b %Y, %H:%M"),
        age_days=(datetime.now() - mtime).days,
        size=path.stat().st_size,
    )


def card_status(card: reg.Card) -> dict:
    """What the panel shows on the index: when it last ran, and what it said."""
    hits = reg.records_for(card.evidence) if card.evidence else []
    if not hits:
        return dict(state="none", when="never run", detail="")
    latest = hits[0]
    age = (datetime.now() - datetime.fromtimestamp(latest.stat().st_mtime)).days
    state = "fresh" if age <= 7 else ("stale" if age <= 60 else "old")
    return dict(state=state,
                when=datetime.fromtimestamp(latest.stat().st_mtime).strftime("%d %b %Y"),
                detail=latest.name, count=len(hits))


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    lanes = []
    for key, title, sub in reg.LANES:
        cards = []
        for card in reg.lane_cards(key):
            cards.append(dict(card=card, status=card_status(card),
                              runnable=bool(card.jobs)))
        lanes.append(dict(key=key, title=title, sub=sub, cards=cards))
    return render_template("index.html", lanes=lanes, runner=runner.state(),
                           n_jobs=len(reg.RUNNABLE))


@app.route("/card/<key>")
def card_page(key: str):
    card = reg.CARDS_BY_KEY.get(key.upper())
    if card is None:
        abort(404)
    jobs = []
    for job in card.jobs:
        jobs.append(dict(job=job, defaults=reg.script_defaults(job.script),
                         preview=" ".join(reg.build_command(job, {
                             k.flag: k.default for k in job.knobs}))))
    evidence = [record_summary(p) for p in reg.records_for(card.evidence)[:12]]
    return render_template("card.html", card=card, jobs=jobs, evidence=evidence,
                           panels=reg.PANELS, runner=runner.state())


@app.route("/run/<job_key>", methods=["POST"])
def run_job(job_key: str):
    job = reg.JOBS_BY_KEY.get(job_key)
    if job is None:
        return jsonify(error=f"no job called {job_key}"), 404
    values: dict = {}
    for knob in job.knobs:
        if knob.kind == "flag":
            values[knob.flag] = request.form.get(knob.flag) is not None
        elif knob.kind == "multi":
            values[knob.flag] = request.form.getlist(knob.flag)
        else:
            values[knob.flag] = request.form.get(knob.flag, "")
    try:
        state = runner.start(job, values)
    except RuntimeError as exc:
        return jsonify(error=str(exc)), 409
    except (ValueError, PermissionError) as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(state)


@app.route("/log")
def log_tail():
    return jsonify(runner.tail(int(request.args.get("offset", 0))))


@app.route("/stop", methods=["POST"])
def stop_job():
    runner.stop()
    return jsonify(runner.state())


@app.route("/record/<path:rel>")
def record_page(rel: str):
    path = (reg.REPO / rel).resolve()
    if reg.EVALS not in path.parents or not path.is_file():
        abort(404)
    return render_template("record.html", rel=rel, name=path.name,
                           body=render_record(path),
                           summary=record_summary(path), runner=runner.state())


@app.route("/file/<path:rel>")
def raw_file(rel: str):
    """Images inside a record. Confined to the evidence tree."""
    path = (reg.REPO / rel).resolve()
    if reg.EVALS not in path.parents or not path.is_file():
        abort(404)
    return send_file(path)


@app.route("/health")
def health():
    return jsonify(ok=True, cards=len(reg.CARDS), jobs=len(reg.RUNNABLE),
                   runner=runner.state())


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", type=int, default=8787)
    p.add_argument("--host", default="127.0.0.1",
                   help="loopback by default: this launches jobs, it is not for a network")
    a = p.parse_args()
    print(f"Control centre on http://{a.host}:{a.port}")
    print(f"{len(reg.CARDS)} panels, {len(reg.RUNNABLE)} of them runnable, "
          f"under {reg.PYTHON}")
    app.run(host=a.host, port=a.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
