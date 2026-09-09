"""Render the whole control centre to one self-contained HTML file.

    .venv/bin/python 03-inputs/control_export.py
    .venv/bin/python 03-inputs/control_export.py --out somewhere.html --open

Writes 01-dashboard/control-centre.html: every panel, every chart and every
figure the workflow has produced, inlined as data URIs, in one file that opens
from disk with no server, no network and no dependencies.

What it is and is not. The served page runs jobs and saves settings; a file
cannot. So the export keeps every panel, every chart and every reading, drops
the Run buttons and the settings forms, and says so at the top rather than
showing controls that would do nothing. It is the view, for reading and for
sending to somebody, not the control centre.

Everything is embedded, so the file is large and it is meant to be: the point is
that it still shows the same charts in a year, on a machine that has none of
this repository on it.
"""

from __future__ import annotations

import argparse
import base64
import html as _html
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench_config as bench       # noqa: E402
import control_charts as charts    # noqa: E402
import control_registry as reg     # noqa: E402
from control_centre import app     # noqa: E402

OUT = reg.REPO / "01-dashboard" / "control-centre.html"

# The folders the workflow writes figures into. Every PNG in them is collected
# into the gallery, because 124 of them existed and not one was reachable from
# the page.
FIGURE_DIRS = [
    "04-outputs/PNG", "04-outputs/AA-evals", "04-outputs/dashboard",
    "04-outputs/2A-market-screening", "04-outputs/1A-macd",
    "04-outputs/1B-confluence", "04-outputs/1C-fibonacci",
    "04-outputs/2B-atr-band", "04-outputs/2C-position-sizing",
    "04-outputs/2D-edge-fence", "04-outputs/3A-training-test-data",
    "04-outputs/3B-model-training", "04-outputs/3C-model-tuning",
    "04-outputs/3D-stability", "04-outputs/AA-journal", "04-outputs/journal",
]

# Above this a figure is left out with its size named. A dozen four-megabyte
# renders would make a file nobody can open, which defeats the purpose.
MAX_FIGURE_BYTES = 1_800_000


def data_uri(path: Path) -> str:
    return ("data:image/png;base64,"
            + base64.b64encode(path.read_bytes()).decode())


def collect_figures(log=print) -> list[dict]:
    """Every PNG the workflow has produced, newest first, with where it came from."""
    seen, out, skipped = set(), [], 0
    for rel in FIGURE_DIRS:
        root = reg.REPO / rel
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*.png")):
            if p.name.startswith("._") or p.resolve() in seen:
                continue
            seen.add(p.resolve())
            if p.stat().st_size > MAX_FIGURE_BYTES:
                skipped += 1
                continue
            out.append(dict(
                path=p, name=p.name, folder=rel.split("/")[-1],
                when=datetime.fromtimestamp(p.stat().st_mtime),
                kb=p.stat().st_size // 1024))
    out.sort(key=lambda d: d["when"], reverse=True)
    log(f"  {len(out)} figures collected from {len(FIGURE_DIRS)} folders"
        + (f", {skipped} left out as larger than "
           f"{MAX_FIGURE_BYTES // 1024:,} KB" if skipped else ""))
    return out


def strip_controls(body: str) -> str:
    """Remove what cannot work in a file, rather than leaving it inert.

    A Run button that does nothing is worse than no Run button: it says the file
    can do something it cannot. The forms go, and the panel keeps its charts,
    its readings and its evidence.
    """
    body = re.sub(r'<form class="(?:runform|cfgform)".*?</form>', "", body,
                  flags=re.S)
    body = re.sub(r'<div class="console".*?</div>', "", body, flags=re.S)
    body = re.sub(r'<button[^>]*>.*?</button>', "", body, flags=re.S)
    return body


def inline_charts(doc: str, log=print) -> str:
    """Replace every /chart/name.png with the drawing itself."""
    names = sorted(set(re.findall(r'/chart/([a-z0-9-]+)\.png', doc)))
    for name in names:
        png = charts.draw(name)
        if not png:
            continue
        uri = "data:image/png;base64," + base64.b64encode(png).decode()
        doc = re.sub(rf'/chart/{re.escape(name)}\.png(\?[^"\']*)?', uri, doc)
    log(f"  {len(names)} charts drawn and inlined")
    return doc


def gallery_html(figs: list[dict]) -> str:
    """The workflow's own figures, filterable by folder and searchable by name."""
    folders = sorted({f["folder"] for f in figs})
    chips = "".join(
        f'<button class="gchip" data-folder="{_html.escape(f)}">{_html.escape(f)}'
        f' <i>{sum(1 for g in figs if g["folder"] == f)}</i></button>'
        for f in folders)
    items = []
    for f in figs:
        items.append(
            f'<figure class="gfig" data-folder="{_html.escape(f["folder"])}" '
            f'data-name="{_html.escape(f["name"].lower())}">'
            f'<img loading="lazy" src="{data_uri(f["path"])}" alt="{_html.escape(f["name"])}">'
            f'<figcaption><b>{_html.escape(f["name"])}</b>'
            f'<span>{f["folder"]} &middot; {f["when"]:%d %b %Y} &middot; {f["kb"]} KB</span>'
            f'</figcaption></figure>')
    return (
        '<section id="gallery"><h2 class="secthead">Figure library</h2>'
        f'<p class="note">Every figure this workflow has produced, {len(figs)} of '
        'them, from the folders the notebooks and the evaluation scripts write '
        'into. Filter by folder or type to search by name. None of these was '
        'reachable from the page before.</p>'
        f'<div class="gbar"><button class="gchip on" data-folder="">all '
        f'<i>{len(figs)}</i></button>{chips}'
        '<input id="gsearch" type="text" placeholder="search by file name"></div>'
        f'<div class="ggrid">{"".join(items)}</div></section>')


SCRIPT = """
<script>
// The gallery filters in the page, because the file has no server behind it.
const chips = document.querySelectorAll('.gchip');
const figs  = document.querySelectorAll('.gfig');
const search = document.getElementById('gsearch');
let folder = '';
function apply() {
  const q = (search.value || '').toLowerCase();
  figs.forEach(f => {
    const okF = !folder || f.dataset.folder === folder;
    const okQ = !q || f.dataset.name.includes(q);
    f.style.display = (okF && okQ) ? '' : 'none';
  });
}
chips.forEach(c => c.addEventListener('click', () => {
  chips.forEach(x => x.classList.remove('on'));
  c.classList.add('on');
  folder = c.dataset.folder;
  apply();
}));
if (search) search.addEventListener('input', apply);

// Panels are sections in one document rather than separate pages, so every
// link that pointed at a page now points at an anchor.
document.querySelectorAll('a[href^="/card/"]').forEach(a => {
  a.setAttribute('href', '#panel-' + a.getAttribute('href').split('/').pop());
});
document.querySelectorAll('a[href^="/record/"], a[href^="/file/"]').forEach(a => {
  a.replaceWith(...a.childNodes);
});
</script>
"""

EXTRA_CSS = """
.exported{ background:#fdf6f6; border-left:4px solid #a01c1c; color:#5c1414;
  padding:9px 12px; font-size:12.5px; border-radius:0 3px 3px 0; margin:0 0 16px 0; }
.exported b{ color:#a01c1c; text-transform:uppercase; letter-spacing:.3px;
  font-size:11.5px; }
.secthead{ font-size:17px; color:#0b2038; border-bottom:2px solid #14304d;
  padding-bottom:6px; margin:34px 0 10px 0; }
.panelsec{ background:#fff; border:1px solid #c3cedb; border-radius:3px;
  padding:14px 16px; margin:0 0 18px 0; }
.panelsec > h3.pk{ margin:0 0 10px 0; font-size:15px; font-weight:800;
  color:#0b2038; }
.gbar{ display:flex; flex-wrap:wrap; gap:6px; align-items:center; margin:0 0 14px 0; }
.gchip{ font-size:11.5px; border:1px solid #c3cedb; background:#fff; color:#16202c;
  border-radius:3px; padding:4px 9px; cursor:pointer; }
.gchip.on{ background:#14304d; color:#fff; border-color:#14304d; }
.gchip i{ font-style:normal; opacity:.65; margin-left:3px; }
#gsearch{ margin-left:auto; padding:5px 9px; font-size:12.5px; border:1px solid #c3cedb;
  border-radius:3px; min-width:220px; }
.ggrid{ display:grid; grid-template-columns:repeat(auto-fill, minmax(300px, 1fr));
  gap:14px; }
.gfig{ margin:0; background:#fff; border:1px solid #c3cedb; border-radius:3px;
  padding:8px; }
.gfig img{ width:100%; height:auto; display:block; }
.gfig figcaption{ font-size:11px; color:#4a5866; margin-top:5px; line-height:1.35; }
.gfig figcaption b{ display:block; color:#16202c; word-break:break-all; }
"""


def build(log=print) -> str:
    client = app.test_client()
    css = (reg.SCRIPTS / "control_static" / "control.css").read_text(encoding="utf-8")

    index = client.get("/").get_data(as_text=True)
    body = re.search(r"<body>(.*)</body>", index, re.S)
    shell = body.group(1) if body else index
    # Everything inside .sheet, so the masthead and the lanes are kept as they are.
    log("  index rendered")

    sections = []
    for card in reg.CARDS:
        page = client.get(f"/card/{card.key}").get_data(as_text=True)
        inner = re.search(r'<div class="panelwrap">(.*?)\n</div>\s*\n?\{?%?', page, re.S)
        if inner is None:
            inner = re.search(r'<div class="panelwrap">(.*)</div>\s*</div>', page, re.S)
        chunk = strip_controls(inner.group(1)) if inner else ""
        sections.append(
            f'<section class="panelsec" id="panel-{card.key}">'
            f'<h3 class="pk">{card.key} &middot; {_html.escape(card.title)}</h3>'
            f'<p class="note">{_html.escape(card.lead)}</p>'
            f'<div class="panelwrap">{chunk}</div></section>')
    log(f"  {len(sections)} panels rendered")

    figs = collect_figures(log=log)
    doc = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<title>Swing Trader &middot; Control Centre</title>"
        f"<style>{css}{EXTRA_CSS}</style></head><body>"
        + shell.replace(
            '<div class="cfgline">',
            '<div class="exported"><b>Exported view</b> &nbsp;This is one file, '
            f'saved {datetime.now():%d %B %Y %H:%M}, with every chart and figure '
            'inside it. It opens with no server and no network. The settings and '
            'the Run buttons are not here, because a file cannot run a script: '
            'for those, serve the page with '
            '<code>05-research/scripts/control_centre.sh</code>.</div>'
            '<div class="cfgline">', 1)
        + '<h2 class="secthead">The panels</h2>'
        + "".join(sections)
        + gallery_html(figs)
        + SCRIPT + "</body></html>")

    doc = inline_charts(doc, log=log)
    return doc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--open", action="store_true", help="open it when done")
    a = ap.parse_args()

    print("building the consolidated view")
    doc = build()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    mb = out.stat().st_size / 2 ** 20
    print(f"wrote {out.relative_to(reg.REPO)}  ({mb:,.1f} MB, self-contained)")
    if a.open:
        subprocess.run(["open", str(out)], capture_output=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
