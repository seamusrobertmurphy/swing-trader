#!/usr/bin/env python3
"""Report whether any panel on a cheat sheet overflows its cell.

The sheet is a fixed grid: every panel gets an identical box and hides whatever
does not fit, silently. This renders the page headless and compares each panel's
content height against its box height, so an over-full panel is a printed number
rather than something you have to spot by eye.

    python3 src/measure.py swing-trader-cheatsheet.html

Ported on 2026-09-07 from the TUV SUD disturbance-check sheets at
/Volumes/PortableSSD/TUVSUD/toolboxes/01 Disturbance Checks/Cheatsheets/src,
where the same script exists for their stacked-column layout. This version
measures fixed cells rather than column totals.
"""
import pathlib, re, subprocess, sys, tempfile

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

PROBE = """
<script>
window.addEventListener('load', function(){
  var out = [];
  document.querySelectorAll('.grid > .card, .strip').forEach(function(card, i){
    var h2 = card.querySelector('h2') || card.querySelector('.sh');
    var name = h2 ? h2.textContent.replace(/\\s+/g,' ').trim().slice(0,38) : 'strip';
    out.push(i + '|' + card.scrollHeight + '|' + card.clientHeight + '|' + name);
  });
  var page = document.querySelector('.sheet');
  var box = document.createElement('div');
  box.id = 'probe';
  box.textContent = 'PAGE|' + page.scrollHeight + '|' + page.clientHeight
                    + '\\n' + out.join('\\n');
  document.body.appendChild(box);
});
</script>
"""

target = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "swing-trader-cheatsheet.html")
html = target.read_text().replace("</body>", PROBE + "\n</body>")
tmp = pathlib.Path(tempfile.mkdtemp()) / target.name
tmp.write_text(html)

dom = subprocess.run(
    [CHROME, "--headless", "--disable-gpu", "--window-size=1056,816",
     "--virtual-time-budget=4000", "--dump-dom", f"file://{tmp}"],
    capture_output=True, text=True).stdout

m = re.search(r'<div id="probe">(.*?)</div>', dom, re.S)
if not m:
    sys.exit("probe not found; the page did not render")

lines = [l for l in m.group(1).replace("&amp;", "&").split("\n") if l.strip()]
_, ps, pc = lines[0].split("|")
over = 0
print(f"page  content {int(ps)/96:.2f} in against a box of {int(pc)/96:.2f} in"
      f"   [{'OVER' if int(ps) > int(pc) + 1 else 'ok'}]\n")
print(f"{'panel':44s} {'content':>8s} {'box':>7s}   verdict")
for ln in lines[1:]:
    i, sh, ch, name = ln.split("|", 3)
    sh, ch = int(sh), int(ch)
    bad = sh > ch + 1
    over += bad
    print(f"{name:44s} {sh/96:7.2f}\" {ch/96:6.2f}\"   "
          f"{'OVER by %.2f in' % ((sh-ch)/96) if bad else 'ok, %.2f in spare' % ((ch-sh)/96)}")
print(f"\n{over} panel(s) over" if over else "\nevery panel fits")
sys.exit(1 if over else 0)
