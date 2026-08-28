"""Collect the research figures so the dashboard can show them.

Three months of analysis produced about two dozen figures. They live as PNGs
under `outputs/`, are referenced by the README and by the workflow notebook,
and until now appeared nowhere in the dashboard, which is why the dashboard
read as a book-keeping page rather than a piece of research.

This does three things and no more. It finds every figure the README shows,
takes the caption and the section it sits under from the README itself rather
than inventing one, and writes a smaller copy the dashboard can carry inline.

The smaller copy matters. The full set is 23 MB, and the dashboard is one
self-contained file refreshed every twenty minutes; inlining 23 MB of PNG would
make a page nobody waits for. The thumbnails come to about a tenth of that, and
each one links to the original at full size.

    .venv/bin/python inputs/research_figures.py
    -> outputs/dashboard/figures/*.png  and  outputs/dashboard/figures.json
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "outputs" / "dashboard" / "figures"
INDEX = REPO / "outputs" / "dashboard" / "figures.json"

THUMB_WIDTH = 1100          # wide enough to read an axis label on a laptop
IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")


def readme_figures() -> list[dict]:
    """Every figure the README shows, with the heading it sits under and the
    sentence that follows it. The words are the README's, not new ones: a
    caption rewritten here would be a second version to fall out of date."""
    txt = (REPO / "README.md").read_text(encoding="utf-8", errors="replace")
    lines = txt.split("\n")
    section, sub = "", ""
    out = []
    for i, line in enumerate(lines):
        if line.startswith("## "):
            section, sub = line[3:].strip(), ""
        elif line.startswith("### "):
            sub = line[4:].strip()
        m = IMG_RE.search(line)
        if not m:
            continue
        caption, rel = m.group(1).strip(), m.group(2).strip()
        src = (REPO / rel)
        if not src.exists():
            continue
        # the first non-empty prose line after the image is its explanation
        blurb = ""
        for nxt in lines[i + 1:i + 6]:
            t = nxt.strip()
            if t and not t.startswith(("#", "!", "|", "```", ">")):
                blurb = t
                break
        out.append(dict(caption=caption, path=rel, section=section, sub=sub,
                        blurb=blurb, source="README"))
    return out


def notebook_figures() -> list[dict]:
    """Figures the workflow notebook draws but the README does not show.

    The notebook renders most of its plots inside the document rather than
    saving them, so this reports which sections carry a drawing and where the
    code for it lives. It does not extract the embedded images: those are
    outputs of a run, and a run is what regenerates them.
    """
    nb_path = REPO / "00-trader-workflow" / "00-trader-workflow.ipynb"
    if not nb_path.exists():
        return []
    nb = json.loads(nb_path.read_text(encoding="utf-8", errors="replace"))
    cells = nb["cells"]
    heading, out = "", []
    for i, c in enumerate(cells):
        src = "".join(c["source"])
        if c["cell_type"] == "markdown":
            for line in src.split("\n"):
                if line.startswith("### "):
                    heading = line[4:].strip()
            continue
        has_image = any("image/png" in o.get("data", {}) for o in c.get("outputs", []))
        if not has_image:
            continue
        first = next((l for l in src.split("\n")
                      if l.strip().startswith("#") and len(l.strip()) > 4), "")
        out.append(dict(section=heading, cell=i,
                        what=first.lstrip("# -").strip()[:160],
                        source="notebook"))
    return out


def thumbnail(src: Path, dst: Path) -> dict:
    """Shrink one figure, and skip the work when the copy is already current.

    This runs on every dashboard refresh, which is every twenty minutes. The
    research figures change perhaps twice a year, so rewriting 23 PNGs to a
    portable SSD each time is pure wear for no gain.
    """
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        im = Image.open(dst)
        return dict(width=im.size[0], height=im.size[1],
                    kb_original=round(src.stat().st_size / 1024),
                    kb_thumb=round(dst.stat().st_size / 1024), cached=True)
    im = Image.open(src)
    w, h = im.size
    if w > THUMB_WIDTH:
        im = im.resize((THUMB_WIDTH, round(h * THUMB_WIDTH / w)), Image.LANCZOS)
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGB")
    im.save(dst, optimize=True)
    return dict(width=im.size[0], height=im.size[1],
                kb_original=round(src.stat().st_size / 1024),
                kb_thumb=round(dst.stat().st_size / 1024), cached=False)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    figs = readme_figures()
    kept = []
    for f in figs:
        src = REPO / f["path"]
        dst = OUT / (src.stem + ".png")
        try:
            info = thumbnail(src, dst)
        except Exception as e:  # noqa: BLE001
            print(f"  ! {src.name}: {type(e).__name__}: {e}")
            continue
        kept.append(f | info | dict(thumb=str(dst.relative_to(REPO)),
                                    file=dst.name))
    nb = notebook_figures()
    INDEX.write_text(json.dumps(dict(figures=kept, notebook=nb), indent=1),
                     encoding="utf-8")
    total_o = sum(k["kb_original"] for k in kept)
    total_t = sum(k["kb_thumb"] for k in kept)
    fresh = sum(1 for k in kept if not k.get("cached"))
    print(f"wrote {INDEX} : {len(kept)} figures ({fresh} redrawn, "
          f"{len(kept) - fresh} already current), {len(nb)} notebook drawings")
    print(f"  {total_o / 1024:.1f} MB of originals -> {total_t / 1024:.1f} MB of thumbnails")


if __name__ == "__main__":
    main()
