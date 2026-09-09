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
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

from flask import (Flask, Response, abort, jsonify, render_template,
                   request, send_file)

import bench_config as bench
import control_charts as charts
import control_interactive as interactive
import control_tables as tables
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


# The dollar headline, on every page. A context processor rather than an
# argument to each render_template call, because there are six of those and the
# seventh would have been the one that forgot. Operator instruction,
# 9 September 2026: report gains and losses in dollars, visibly.
@app.context_processor
def _money_strip():
    try:
        return dict(money=tables.money_strip())
    except Exception:                                   # noqa: BLE001
        return dict(money={})


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    lanes = []
    for key, title, sub in reg.LANES:
        cards = []
        for card in reg.lane_cards(key):
            # The reel: this panel's own charts first, then the figures the
            # workflow has already produced on the same subject. They rotate in
            # the card's own image box rather than opening a page, so the whole
            # thing stays on one screen.
            reel = [dict(src=f"/chart/{n}.png",
                         label=charts.CHARTS.get(n, ("", n))[1], kind="chart")
                    for n in card.all_charts]
            # A panel may pin named figures to the very front, ahead of its own
            # charts. A2 pins avax_macd_20260620.png: the reel holds 23 figures
            # newest first, that one is from 20 June, and the operator could not
            # find it. The names are data in control_charts.PINNED.
            pinned = charts.PINNED.get(card.key, ())
            # getattr, not a plain call. The figure library is being withdrawn
            # from the served page in a separate sweep, and an index route that
            # raises AttributeError the moment the function goes takes the whole
            # control centre down rather than one image box.
            gallery = getattr(charts, "figures", None)
            if gallery is not None:
                shots = [dict(src=f"/figure/{f['rel']}", label=f["name"],
                              kind="figure", name=f["name"])
                         for f in gallery(card.key, limit=14)]
                front = [s for s in shots if s["name"] in pinned]
                reel = front + reel + [s for s in shots if s not in front]
            cards.append(dict(card=card, status=card_status(card),
                              runnable=bool(card.jobs), reel=reel))
        lanes.append(dict(key=key, title=title, sub=sub, cards=cards))
    cfg = bench.load()
    # Whichever panel carries the history charts, resolved rather than named.
    # The link had been hard-coded to C3, and the panels are being merged and
    # renumbered, so a fixed key is a dead link waiting to happen. No match
    # means no link at all, which is better than one that goes nowhere.
    timeline_key = next((c.key for c in reg.CARDS
                         if {"run-calendar", "best-over-time"} & set(c.all_charts)), "")
    return render_template("index.html", lanes=lanes, runner=runner.state(),
                           n_jobs=len(reg.RUNNABLE), timeline=reg.TIMELINE,
                           timeline_key=timeline_key,
                           describes=bench.describe(cfg))


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
    cfg = bench.load()
    # A panel may own several sections since the Data panel merged three, so
    # each is rendered as its own form and saves on its own.
    # "vals", not "values": a dict has a values() method and Jinja resolves the
    # attribute to that method rather than to the key, so form.values.get raised
    # on every panel with a form.
    # The hyperparameters and the grid reference. The model section renders a
    # `params` field that was a note with no controls, so all 42 settings across
    # the estimators were invisible and the operator reported the panel dead.
    # Every estimator, not only the chosen ones. Showing blocks for the current
    # selection alone rendered one block of nine fields and the panel still read
    # as empty; the question a reader has here is what CAN be set, and which of
    # those are in play is answered by marking them.
    chosen = set(cfg.get("model", {}).get("estimators") or [])
    hyper = [dict(model=m, fields=bench.param_fields(m), chosen=(m in chosen),
                  vals=(cfg.get("model", {}).get("params") or {}).get(m, {}))
             for m in bench.MODEL_PARAMS]
    forms = [dict(name=n, spec=bench.SCHEMA[n], vals=cfg.get(n, {}),
                  clusters=bench.clusters_for(n))
             for n in card.all_sections if n in bench.SCHEMA]
    # A merged panel keeps the panels it absorbed as sections, each with its own
    # charts, its own table and its own interactive figure. The table is built
    # here rather than in the template because control_tables.build catches its
    # own failures and returns a caption saying what went wrong, and a template
    # cannot do that: a table that raised inside Jinja would blank the panel.
    groups = [dict(g=g,
                   table=(tables.build(g.table) if g.table else None),
                   figure=interactive.build(g.key))
              for g in card.groups]
    # A panel that never merged can still carry a table of its own, built here
    # for the same reason as the section tables above.
    table = tables.build(card.table) if card.table else None
    return render_template("card.html", card=card, jobs=jobs, evidence=evidence,
                           panels=reg.PANELS, runner=runner.state(),
                           forms=forms, hyper=hyper, table=table,
                           grids=bench.tunable_grids(), groups=groups,
                           chart_titles=charts.CHARTS,
                           interactive=interactive.build(card.key),
                           plotly=True,
                           recommendation=bench.recommendation_sentence(
                               bench.recommended()[1]),
                           describes=bench.describe(cfg))


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


@app.route("/chart/<name>.png")
def chart(name: str):
    """One chart as PNG. Drawn on request from records already on disk.

    Nothing here fits a model or rebuilds a frame: a page that refits on every
    reload is a page nobody can leave open, and this machine is already deep in
    swap. A chart that raises returns a box naming the failure rather than a
    broken image, because a broken image says nothing about what went wrong.

    ?size=large redraws the same chart at 2.4 times the dots per inch, for the
    full-page view. It is requested only when that view opens, never with the
    page: nine panels preloading large renders would be slow for a view most of
    them never open.
    """
    scale = charts.LARGE_SCALE if request.args.get("size") == "large" else 1.0
    png = charts.draw(name, scale)
    if png is None:
        abort(404)
    return Response(png, mimetype="image/png",
                    headers={"Cache-Control": "no-store"})


@app.route("/config/<section>", methods=["POST"])
def save_section(section: str):
    """Write one panel's settings into the shared bench configuration.

    The panel edits its own section and nothing else, and bench_config.coerce
    decides what a posted value becomes, so a browser cannot introduce a setting
    the runner has never heard of or a type it cannot use.
    """
    if section not in bench.SCHEMA:
        return jsonify(error=f"no section called {section}"), 404
    cfg = bench.load()
    form = request.form.to_dict(flat=False)
    flat = {k: (v if len(v) > 1 else v[0]) for k, v in form.items()}
    try:
        cfg[section].update(bench.coerce(section, flat))
    except (ValueError, TypeError) as exc:
        return jsonify(error=str(exc)), 400
    bench.save(cfg)
    return jsonify(saved=section, settings=cfg[section],
                   describes=bench.describe(cfg))


@app.route("/config/recommend", methods=["POST"])
def load_recommended():
    """Replace the active configuration with the best one on record."""
    cfg, prov = bench.recommended()
    bench.save(cfg)
    return jsonify(loaded=True, provenance=prov,
                   sentence=bench.recommendation_sentence(prov),
                   describes=bench.describe(cfg))


@app.route("/config/<section>/reset", methods=["POST"])
def reset_section(section: str):
    """Put one section back to the schema's own defaults, and nothing else."""
    if section not in bench.SCHEMA:
        return jsonify(error=f"no section called {section}"), 404
    cfg = bench.load()
    cfg[section] = bench.defaults()[section]
    bench.save(cfg)
    return jsonify(reset=section, settings=cfg[section],
                   describes=bench.describe(cfg))


@app.route("/figure/<path:rel>")
def figure(rel: str):
    """One figure the workflow produced, from the output tree only."""
    path = (reg.REPO / rel).resolve()
    outputs = (reg.REPO / "04-outputs").resolve()
    if outputs not in path.parents or path.suffix.lower() != ".png" \
            or not path.is_file():
        abort(404)
    return send_file(path)


@app.route("/health")
def health():
    return jsonify(ok=True, cards=len(reg.CARDS), jobs=len(reg.RUNNABLE),
                   runner=runner.state())


# The variable-selection panel refits on demand, so it needs an endpoint rather
# than a picture. Registered here and defined in control_varselect, because it
# is the one thing on the page that answers a question the reader asks with a
# tick box. It reads the configured training window and fits it; it launches
# nothing, so it does not go through the runner and the allow list is untouched.
# Registered above main() and not at the foot of the file: app.run blocks, so a
# blueprint registered after it would attach only once the server had stopped.
import control_varselect as varselect            # noqa: E402

app.register_blueprint(varselect.bp)


def _warm() -> None:
    """Import the heavy modelling stack in the background at startup.

    Several charts import bench_run lazily, which pulls train_model_1h and with
    it scikit-learn, lightgbm and the rest. The first panel to need it paid
    between eight and eleven seconds for that import alone, which reads as the
    page freezing on open; the operator reported exactly that on the training
    regime. Doing it here means the wait falls where nobody is looking at the
    screen. A failure is silent on purpose: a warm-up that cannot import is a
    slow page, not a broken one, and the real import will raise where it matters.
    """
    try:
        import bench_run  # noqa: F401
        import kde_metrics  # noqa: F401
    except Exception:                                   # noqa: BLE001
        pass


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", type=int, default=8787)
    p.add_argument("--host", default="127.0.0.1",
                   help="loopback by default: this launches jobs, it is not for a network")
    a = p.parse_args()
    threading.Thread(target=_warm, daemon=True).start()
    print(f"Control centre on http://{a.host}:{a.port}")
    print(f"{len(reg.CARDS)} panels, {len(reg.RUNNABLE)} of them runnable, "
          f"under {reg.PYTHON}")
    app.run(host=a.host, port=a.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
