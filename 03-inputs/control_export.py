"""Render the whole control centre to one self-contained HTML file.

    .venv/bin/python 03-inputs/control_export.py
    .venv/bin/python 03-inputs/control_export.py --out somewhere.html --open

Writes 01-dashboard/control-centre.html: every panel, every chart and every
figure the workflow has produced, inlined as data URIs, in one file that opens
from disk with no server, no network and no dependencies.

What it is and is not. The served page runs jobs and saves settings; a file
cannot. So the export keeps every panel, every chart, every reading and every
settings form, drops the Run buttons and the console, and renders the settings
as disabled fields carrying the values the run used. It is the view, for reading
and for sending to somebody, not the control centre.

The settings were stripped out entirely until 9 September 2026, on the reasoning
that a control which cannot act is a control that lies. The operator opened the
file and found no configuration on any panel, which is most of what the page is,
so they are kept and disabled instead: a reader needs to see what the run was
configured with even though they cannot change it.

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

import control_charts as charts    # noqa: E402
import control_registry as reg     # noqa: E402
from control_centre import app     # noqa: E402

OUT = reg.REPO / "01-dashboard" / "control-centre.html"

# Above this a figure is left out with its size named. A dozen four-megabyte
# renders would make a file nobody can open, which defeats the purpose.
MAX_FIGURE_BYTES = 1_800_000


def data_uri(path: Path) -> str:
    return ("data:image/png;base64,"
            + base64.b64encode(path.read_bytes()).decode())


def strip_controls(body: str) -> str:
    """Remove what cannot work in a file, and disable what is worth showing.

    The job forms and the console go: they exist to launch a subprocess and a
    file has nothing to show for them. The settings forms stay, because the
    settings are most of what a panel is, but every input and select in them is
    given `disabled` so the browser draws them as values rather than as controls
    that silently do nothing. Their Save and Reset buttons are replaced with a
    line naming the script that serves the editable page.
    """
    body = re.sub(r'<form class="runform".*?</form>', "", body, flags=re.S)
    body = re.sub(r'<div class="console".*?</div>', "", body, flags=re.S)

    def freeze(m: re.Match) -> str:
        form = m.group(0)
        # `disabled` on each field, not `readonly`: readonly leaves a select
        # editable and a checkbox tickable, which is the appearance of a working
        # control and the thing this is avoiding.
        form = re.sub(r"<(input|select|textarea)\b", r"<\1 disabled", form)
        form = re.sub(r'<div class="formfoot">.*?</div>', FROZEN_FOOT, form,
                      flags=re.S)
        return form

    body = re.sub(r'<form class="cfgform".*?</form>', freeze, body, flags=re.S)
    body = re.sub(r'<button[^>]*>.*?</button>', "", body, flags=re.S)
    return body


FROZEN_FOOT = ('<p class="note frozen">These are the settings the run used. '
               'Changing them needs the served page: '
               '<code>05-research/scripts/control_centre.sh</code>.</p>')


def panel_body(page: str) -> str:
    """The contents of a panel's <div class="panelwrap">, matched by depth.

    This had been a non-greedy regex up to the first newline followed by
    </div>, which is the close of the Charts block, so every exported panel
    stopped after its four pictures and carried none of its settings, its
    tables or its evidence. The operator reported the missing configuration on
    9 September 2026 and the stripping of the forms was blamed; the forms were
    never in the file to strip.
    """
    open_tag = '<div class="panelwrap">'
    start = page.find(open_tag)
    if start < 0:
        return ""
    i = start + len(open_tag)
    depth, out = 1, []
    while i < len(page) and depth:
        nxt_open = page.find("<div", i)
        nxt_close = page.find("</div>", i)
        if nxt_close < 0:
            break
        if 0 <= nxt_open < nxt_close:
            depth += 1
            out.append(page[i:nxt_open + 4]); i = nxt_open + 4
        else:
            depth -= 1
            if depth == 0:
                out.append(page[i:nxt_close])
                break
            out.append(page[i:nxt_close + 6]); i = nxt_close + 6
    return "".join(out)


def inline_charts(doc: str, log=print) -> str:
    """Replace every /chart/ and /figure/ reference with the image itself.

    Both, not just the charts. The panels each cycle a reel of the workflow's
    own figures now, and those arrive as /figure/ paths; left alone they would
    be broken images in a file that is supposed to need nothing.
    """
    names = sorted(set(re.findall(r'/chart/([a-z0-9-]+)\.png', doc)))
    for name in names:
        png = charts.draw(name)
        if not png:
            continue
        uri = "data:image/png;base64," + base64.b64encode(png).decode()
        doc = doc.replace(f"/chart/{name}.png", uri)
    log(f"  {len(names)} charts drawn and inlined")

    figs = sorted(set(re.findall(r'/figure/(04-outputs/[^"\']+\.png)', doc)))
    kept = skipped = 0
    for rel in figs:
        path = reg.REPO / rel
        if not path.is_file():
            continue
        if path.stat().st_size > MAX_FIGURE_BYTES:
            skipped += 1
            continue
        doc = doc.replace(f"/figure/{rel}", data_uri(path))
        kept += 1
    log(f"  {kept} panel figures inlined"
        + (f", {skipped} too large" if skipped else ""))

    # Anything still pointing at the server would be a broken image in a file
    # that is meant to need nothing, so say how many rather than shipping them.
    left = len(re.findall(r'src="/(?:chart|figure)/', doc))
    if left:
        log(f"  WARNING: {left} image references still point at the server")
    return doc


SCRIPT = """
<script>
// Panels are sections in one document rather than separate pages, so every
// link that pointed at a page now points at an anchor.
// Entering a panel hides the grid and shows that panel alone, with a way back.
// One file, so this is the whole of its navigation.
const grid   = document.querySelector('.lanes');
const panels = document.getElementById('panels');
// The front page's sheet is height:100vh with overflow hidden, which is what
// makes the six-panel grid fit one screen without scrolling. The panel sections
// are siblings of that sheet, so with the class left on, opening a panel hid
// the grid and left the panel sitting under a full screen of locked, empty
// sheet: the operator clicked a panel and landed in an empty room. The lock
// comes off while a panel is open and goes back on at the grid.
const sheet  = document.querySelector('.sheet');
function showPanel(key) {
  panels.hidden = false;
  panels.querySelectorAll('.panelsec').forEach(s => {
    s.style.display = (s.id === 'panel-' + key) ? '' : 'none';
  });
  grid.style.display = 'none';
  if (sheet) sheet.classList.remove('front');
  window.scrollTo(0, 0);
}
function showGrid() {
  panels.hidden = true;
  grid.style.display = '';
  if (sheet) sheet.classList.add('front');
  window.scrollTo(0, 0);
}
document.querySelectorAll('a[href^="/card/"]').forEach(a => {
  const key = a.getAttribute('href').split('/').pop();
  a.setAttribute('href', '#panel-' + key);
  a.addEventListener('click', ev => { ev.preventDefault(); showPanel(key); });
});
// The back control is created here, after strip_controls has already run over
// the section HTML on the Python side, so it survives the regex that removes
// every <button> from a panel. The operator clicked the timeline and landed on
// what looked like an empty page, which is what this ordering is for.
document.querySelectorAll('.panelsec').forEach(sec => {
  const back = document.createElement('button');
  back.className = 'gchip back';
  back.textContent = '\u2190 all panels';
  back.addEventListener('click', showGrid);
  sec.insertBefore(back, sec.firstChild);
});
document.querySelectorAll('a[href^="/record/"], a[href^="/file/"]').forEach(a => {
  a.replaceWith(...a.childNodes);
});
// Opening the file at #panel-C2 lands on that panel, so a link to one panel can
// be sent on its own and so the layout can be checked without a click.
function fromHash() {
  const m = /^#panel-([A-Z]\d)$/.exec(window.location.hash || '');
  if (m) showPanel(m[1]); else showGrid();
}
window.addEventListener('hashchange', fromHash);
fromHash();
// The browser scrolls to the anchor itself, and it does so after this script
// and after the next frame, so a deep link opened with the masthead above the
// top of the window and a blank band where it should have been. The scroll is
// put back on load and once more when the images have settled the layout.
window.addEventListener('load', () => {
  window.scrollTo(0, 0);
  setTimeout(() => window.scrollTo(0, 0), 60);
});
</script>
"""

EXTRA_CSS = """
.exported{ background:#fdf6f6; border-left:4px solid #a01c1c; color:#5c1414;
  padding:9px 12px; font-size:12.5px; border-radius:0 3px 3px 0; margin:28px 0 0 0; }
.exported b{ color:#a01c1c; text-transform:uppercase; letter-spacing:.3px;
  font-size:11.5px; }
.secthead{ font-size:17px; color:#0b2038; border-bottom:2px solid #14304d;
  padding-bottom:6px; margin:34px 0 10px 0; }
.panelsec{ background:#fff; border:1px solid #c3cedb; border-radius:3px;
  padding:14px 16px; margin:0 0 18px 0; }
.panelsec > h3.pk{ margin:0 0 10px 0; font-size:15px; font-weight:800;
  color:#0b2038; }
/* The only chip left is the back button the script inserts on each panel. It
   is inserted after strip_controls has run, so it is not caught by the regex
   that removes every button from a section. */
.gchip{ font-size:11.5px; border:1px solid #c3cedb; background:#fff; color:#16202c;
  border-radius:3px; padding:4px 9px; cursor:pointer; }
.gchip.back{ display:block; margin:0 0 12px 0; font-weight:700; color:#14304d;
  border-color:#14304d; }
/* A disabled field here is a displayed value, so the text stays at full
   contrast and only the frame and the cursor say it cannot be edited. The
   browser default greys the text, which makes the number unreadable and the
   number is the content. */
.cfgform input:disabled, .cfgform select:disabled, .cfgform textarea:disabled{
  color:#16202c; -webkit-text-fill-color:#16202c; opacity:1;
  background:#f7f9fb; border-color:#d7dfe8; cursor:default; }
.note.frozen{ margin:6px 0 0 0; color:#4a5866; }
/* The served page caps a chart at 118 pixels and offers a control that opens it
   full page. That control is stripped here with every other button, so the cap
   is lifted instead and the file shows each chart at its own size; a small
   picture with no way to enlarge it would be the dead control in another form. */
.chart img{ max-height:none; }
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
        chunk = strip_controls(panel_body(page))
        # A panel whose whole content was a job form and a console has nothing
        # left after stripping, and an empty section reads as a broken page.
        # Say what is missing and where it is, rather than opening a blank one.
        if len(re.sub(r"<[^>]+>|\s+", "", chunk)) < 40:
            chunk = ('<p class="note">This panel is a Run button and its output, '
                     'and neither is in a file: the settings it takes and the log '
                     'it writes need the served page, '
                     '<code>05-research/scripts/control_centre.sh</code>. Its charts '
                     'and its evidence are on the front page.</p>')
        sections.append(
            f'<section class="panelsec" id="panel-{card.key}">'
            f'<h3 class="pk">{card.key} &middot; {_html.escape(card.title)}</h3>'
            f'<p class="note">{_html.escape(card.lead)}</p>'
            f'<div class="panelwrap">{chunk}</div></section>')
    log(f"  {len(sections)} panels rendered")

    doc = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<title>Swing Trader &middot; Control Centre</title>"
        f"<style>{css}{EXTRA_CSS}</style></head><body>"
        # The notice sits at the foot, not the head. Operator instruction,
        # 9 September 2026: the top of the page is for the timeline and the
        # headline summary, and a reader who wants to know what kind of file
        # this is can find it at the end.
        + shell
        + '<div id="panels" hidden>' + "".join(sections) + '</div>'
        + '<div class="exported"><b>Exported view</b> &nbsp;This is one file, '
          f'saved {datetime.now():%d %B %Y %H:%M}, with every chart and every '
          'figure inside it. It opens with no server and no network. The '
          'settings and the Run buttons are not in it, because a file cannot '
          'run a script: for those, serve the page with '
          '<code>05-research/scripts/control_centre.sh</code>.</div>'
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
