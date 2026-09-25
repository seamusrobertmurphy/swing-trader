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
    labelTables();
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
  #demo-go { width:100%; }
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
#demo-go { background:#f0a830 !important; color:#2a2520 !important; }
#demo-go:hover { background:#e59a1c !important; }
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
    light = THEMES[THEME].get("light")
    doc = demo_choices(scrub(doc))
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
