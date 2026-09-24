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


RUN_BLOCK = """
<div class="block demo-run" id="demo-run">
  <h3>Run your model</h3>
  <p class="note">Sends your saved settings from A1 to C2, trains your model on fresh prices and
  issues a paper ticket per coin, in about five minutes. Nothing is bought or sold.</p>
  <div class="demo-row">
    <label for="demo-name">Your name</label>
    <input id="demo-name" type="text" maxlength="40" placeholder="shown beside your tickets">
    <button class="btn" type="button" id="demo-go">Run</button>
  </div>
  <p class="note" id="demo-status"></p>
</div>
"""

BOARD = """
<div class="block demo-board" id="demo-board">
  <h3>Paper tickets</h3>
  <p class="note">Each run leaves one ticket per coin, settled on real prices when due, less 0.20 per cent cost.</p>
  <div id="demo-totals" class="demo-totals">Loading.</div>
  <div class="demo-tables" id="demo-tables" hidden>
    <div><h4>Tickets</h4><div id="demo-tickets"></div></div>
    <div><h4>Runs</h4><div id="demo-runs"></div></div>
  </div>
</div>
"""

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
"""

DEMO_SCRIPT = r"""
<script>
(function(){
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
restore(fetchStore(KEY, {}));
document.querySelectorAll('form.cfgform').forEach(function(f){
  f.addEventListener('submit', function(ev){
    ev.preventDefault();
    store(KEY, collect());
    document.querySelectorAll('.saved').forEach(function(s){ s.textContent = ''; });
    var s = f.querySelector('.saved');
    if (s) { s.textContent = 'Saved in this browser.'; s.classList.add('demo-ok'); }
  });
});

function pct(v){ return (v === null || v === undefined) ? '' : ((v >= 0 ? '+' : '') + (v * 100).toFixed(2) + '%'); }
function esc(s){ return String(s == null ? '' : s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
function when(s){ return s ? s.replace('T', ' ').slice(0, 16) : ''; }

function board(){
  fetch('data/index.json?t=' + Date.now(), {cache: 'no-store'}).then(function(r){
    if (!r.ok) throw new Error('none yet'); return r.json();
  }).then(function(ix){
    var mine = fetchStore(MINE, []);
    var t = ix.totals || {}, b = t.buy || {}, p = t.passed || {};
    document.getElementById('demo-totals').innerHTML =
      '<div><b>' + (t.runs || 0) + '</b>' + (t.runs === 1 ? 'run' : 'runs') + ' by ' + (t.friends || 0) + (t.friends === 1 ? ' friend' : ' friends') + '</div>' +
      '<div><b>' + (t.open || 0) + '</b>tickets still open</div>' +
      '<div><b>' + (b.n || 0) + '</b>BUY tickets settled, ' + (b.positive || 0) + ' made money</div>' +
      '<div><b>' + pct(b.mean) + '</b>BUY, mean a trade after cost</div>' +
      '<div><b>' + pct(p.mean) + '</b>PASS, mean a trade after cost</div>';
    var rows = (ix.tickets || []).slice().sort(function(a, c){ return (c.issued || '').localeCompare(a.issued || ''); }).slice(0, 300);
    document.getElementById('demo-tables').hidden = !(ix.tickets || []).length;
    document.getElementById('demo-tickets').innerHTML = '<div class="demo-scroll"><table><tr><th>Friend</th><th>Issued</th><th>Coin</th><th>Bars</th><th>Call</th><th>Score</th><th>Entry</th><th>Due</th><th>Result</th><th>After cost</th></tr>' +
      rows.map(function(x){
        var res = x.status === 'settled' ? x.how : 'open';
        var cls = x.after_cost > 0 ? 'pos' : (x.after_cost < 0 ? 'neg' : '');
        return '<tr class="' + (mine.indexOf(x.run_id) >= 0 ? 'mine' : '') + '"><td>' + esc(x.name) + '</td><td>' + when(x.issued) + '</td><td>' + esc(x.symbol) +
          '</td><td>' + esc(x.frame) + '</td><td>' + esc(x.call) + '</td><td>' + (x.score == null ? '' : x.score.toFixed(3)) + '</td><td>' + x.entry_price +
          '</td><td>' + when(x.due) + '</td><td>' + esc(res) + '</td><td class="' + cls + '">' + (x.status === 'settled' ? pct(x.after_cost) : '') + '</td></tr>';
      }).join('') + '</table></div>';
    document.getElementById('demo-runs').innerHTML = '<div class="demo-scroll"><table><tr><th>Friend</th><th>When</th><th>Bars</th><th>Coins</th><th>Model</th><th>Blind score</th></tr>' +
      (ix.runs || []).map(function(r){
        var s = r.status !== 'done' ? ('failed: ' + esc((r.error || '').slice(0, 80))) :
          (r.blind_u2 != null ? ('U2 ' + r.blind_u2.toFixed(3) + ', AUC ' + (r.blind_auc || 0).toFixed(3)) :
           ('top fifth ' + pct(r.blind_top) + ' against ' + pct(r.blind_all)));
        return '<tr class="' + (mine.indexOf(r.run_id) >= 0 ? 'mine' : '') + '"><td>' + esc(r.name) + '</td><td>' + when(r.started) + '</td><td>' + esc(r.frame) +
          '</td><td>' + esc((r.symbols || '').replace(/USDT/g, '')) + '</td><td>' + esc(r.chosen || '') + '</td><td>' + s + '</td></tr>';
      }).join('') + '</table></div>';
  }).catch(function(){
    document.getElementById('demo-totals').textContent = 'No tickets yet.';
  });
}
board();

var status = document.getElementById('demo-status');
function wait(id, started){
  fetch('data/runs/' + id + '.json?t=' + Date.now(), {cache: 'no-store'}).then(function(r){
    if (!r.ok) throw new Error('not yet'); return r.json();
  }).then(function(rec){
    if (rec.status === 'done') {
      status.innerHTML = 'Done. ' + (rec.tickets || []).length + ' tickets issued with ' + esc(rec.chosen) +
        (rec.held && rec.held.length ? '. Held to the demo limits: ' + esc(rec.held.join('; ')) : '') +
        '. They are on C2 Ledger under Paper tickets, highlighted.';
    } else {
      status.textContent = 'The run failed: ' + (rec.error || 'no reason recorded') + '. Change a setting and run again.';
    }
    board();
  }).catch(function(){
    var mins = Math.round((Date.now() - started) / 60000);
    if (mins > 40) { status.textContent = 'No result after 40 minutes. The queue may be full; try again later.'; return; }
    status.textContent = 'Running, ' + mins + ' minutes so far. Run ' + id + '. You can leave this page; your tickets will be on C2 Ledger.';
    setTimeout(function(){ wait(id, started); }, 20000);
  });
}
var go = document.getElementById('demo-go');
if (go) go.addEventListener('click', function(){
  if (!RELAY) { status.textContent = 'Running is not switched on yet.'; return; }
  var cfg = collect(); store(KEY, cfg);
  go.disabled = true; status.textContent = 'Sending your settings.';
  fetch(RELAY + '/run', {method: 'POST', headers: {'content-type': 'application/json'},
        body: JSON.stringify({name: document.getElementById('demo-name').value, config: cfg})})
  .then(function(r){ return r.json().then(function(j){ return [r.ok, j]; }); })
  .then(function(res){
    if (!res[0]) { status.textContent = res[1].error || 'The run was refused.'; go.disabled = false; return; }
    var mine = fetchStore(MINE, []); mine.push(res[1].run_id); store(MINE, mine);
    wait(res[1].run_id, Date.now());
  }).catch(function(){ status.textContent = 'Could not reach the runner. Try again in a minute.'; go.disabled = false; });
});
})();
</script>
"""


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

    frames = {"1h": "1 hour", "4h": "4 hours", "1d": "1 day"}
    coins = [f"{c[:-4]}/USDT" for c in dr.COINS]
    swaps = {
        "market": opts(["crypto"], {"crypto"}),
        "frame": opts(list(frames), {"4h"}, frames.get),
        "symbols": opts(coins, {"BTC/USDT", "ETH/USDT", "SOL/USDT"}),
        "bundle": opts(["all", "majors", "btc-eth"], {"all"}),
    }
    for name, inner in swaps.items():
        doc = re.sub(r'(<select[^>]*name="%s"[^>]*>).*?(</select>)' % name,
                     lambda m: m.group(1) + inner + m.group(2), doc, flags=re.S)
    return doc


# Solarized Dark, operator request, 24 September 2026, replacing a plain
# lightness flip that read as too high in contrast. Ethan Schoonover's palette,
# https://ethanschoonover.com/solarized/
SOLAR_RAMP = [(0.00, "002b36"), (0.10, "073642"), (0.35, "586e75"),
              (0.60, "839496"), (0.80, "93a1a1"), (1.00, "93a1a1")]
SOLAR_ACCENT = {"yellow": "b58900", "orange": "cb4b16", "red": "dc322f", "magenta": "d33682",
                "violet": "6c71c4", "blue": "268bd2", "cyan": "2aa198", "green": "859900"}
# The six lanes keep their cool-to-warm order and stay six distinct colours.
SOLAR_LANES = {"0b4f8a": "violet", "1f7ac4": "blue", "0e7a4f": "cyan",
               "27a86e": "green", "c2410c": "orange", "ea7a2c": "yellow"}


def _rgb(h: str) -> tuple[int, int, int]:
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _flip(r: int, g: int, b: int) -> tuple[int, int, int]:
    """A light-mode colour carried onto Solarized Dark.

    Greys follow the Solarized base tones by inverted lightness, so white paper
    becomes the base03 background and dark ink the base1 text. A saturated
    colour takes the nearest Solarized accent by hue. A pale tint or a dark
    coloured ink takes its base tone with a little of that accent mixed in.
    """
    import colorsys
    key = "%02x%02x%02x" % (r, g, b)
    h, l, sat = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    t = 1 - l
    for (t0, c0), (t1, c1) in zip(SOLAR_RAMP, SOLAR_RAMP[1:]):
        if t <= t1:
            f = 0 if t1 == t0 else (t - t0) / (t1 - t0)
            base = tuple(a + (z - a) * f for a, z in zip(_rgb(c0), _rgb(c1)))
            break
    if key in SOLAR_LANES:
        return _rgb(SOLAR_ACCENT[SOLAR_LANES[key]])
    if sat < 0.2:
        return tuple(round(v) for v in base)

    def hue(c):
        return colorsys.rgb_to_hls(*(v / 255 for v in _rgb(c)))[0]
    accent = _rgb(min(SOLAR_ACCENT.values(),
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
    text = re.sub(r"(:\s*|\s)white\b", lambda m: m.group(1) + "#002b36", text)
    text = re.sub(r"(:\s*|\s)black\b", lambda m: m.group(1) + "#93a1a1", text)
    return text


DARK_CSS = """
/* Solarized Dark, operator request, 24 September 2026. The page's own colours
   are mapped in the source by dark(); the charts are pictures drawn on white,
   so the filter below inverts them, turns their hue back, and lays the result
   on the Solarized base, white becoming base03 and black becoming base1. */
:root { color-scheme: dark; }
body { background:#002b36; }
img, .plotly-graph-div { filter: url(#solarized); background-color:#ffffff !important; }
::selection { background:#586e75; color:#fdf6e3; }
* { scrollbar-color:#586e75 #073642; }
"""

SOLAR_FILTER = (
    '<svg width="0" height="0" style="position:absolute" aria-hidden="true">'
    '<filter id="solarized" color-interpolation-filters="sRGB">'
    '<feColorMatrix type="hueRotate" values="180"/>'
    '<feComponentTransfer>'
    '<feFuncR type="table" tableValues="0.576 0"/>'
    '<feFuncG type="table" tableValues="0.631 0.169"/>'
    '<feFuncB type="table" tableValues="0.631 0.212"/>'
    '</feComponentTransfer></filter></svg>')


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


def build(relay: str, log=print) -> str:
    client = app.test_client()
    css = (reg.SCRIPTS / "control_static" / "control.css").read_text(encoding="utf-8")
    index = client.get("/").get_data(as_text=True)
    body = re.search(r"<body>(.*)</body>", index, re.S)
    # The front page is left exactly as the served board draws it. The board
    # of tickets sat above it until 24 September 2026 and shrank every panel
    # to a thumbnail; it now opens C2 Ledger, beside the rest of the record.
    shell = strip_code(body.group(1) if body else index)
    sections = []
    for card in reg.CARDS:
        page = client.get(f"/card/{card.key}").get_data(as_text=True)
        chunk = strip_code(panel_chunk(page))
        if card.key == "C1":
            chunk = RUN_BLOCK + chunk
        if card.key == "C2":
            chunk = BOARD + chunk
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
           + ce.best_script() + ce.SCRIPT
           + DEMO_SCRIPT.replace("__RELAY__", repr(relay.rstrip("/")) if relay else "''")
           + "</body></html>")
    doc = dark(demo_choices(scrub(doc)))
    # After the flip, because these rules are written for the dark page.
    doc = doc.replace("__DARK_CSS__", DARK_CSS, 1)
    doc = doc.replace("</head><body>", "</head><body>" + SOLAR_FILTER, 1)
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
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--relay", default="", help="the relay's address, such as https://swing-relay.<you>.workers.dev")
    ap.add_argument("--publish", action="store_true", help="push the page to gh-pages")
    a = ap.parse_args()
    print("building the demo page")
    doc = build(a.relay)
    SITE.mkdir(exist_ok=True)
    out = SITE / "index.html"
    out.write_text(doc, encoding="utf-8")
    print(f"wrote {out.relative_to(REPO)} ({out.stat().st_size / 2**20:.1f} MB)")
    if a.publish:
        publish(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
