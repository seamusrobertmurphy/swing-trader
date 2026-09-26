"""Write the Swing Trader app as one file to send to people.

    .venv/bin/python 03-inputs/share_app.py      # writes 01-dashboard/swing-trader.html
    05-research/scripts/control_centre.sh --export

The page is the public app exactly as demo_site builds it, with every chart,
style and script inside the file. Two things change so it still works when it
is opened from an email or a download rather than from the website.

1. Its live data, the scan, the tickets and each run's results and pictures,
   is read from the website by full address. GitHub Pages lets any page read
   it, so the file shows the same live numbers the website does.
2. Run sends people to the website, because the relay that starts a run only
   answers the website and never a file.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import demo_site as ds             # noqa: E402

OUT = ds.REPO / "01-dashboard" / "swing-trader.html"
DATA = ds.PAGES_URL + "data/"

# Each short address the page uses for live data, and how many times the
# built page carries it; a count that changes means demo_site changed and the
# file would quietly read nothing, so the build stops instead.
SHORT = {"fetch('data/": 5, 'src="data/': 1}
NO_RUN = "Running is not switched on yet."
LIVE = f"Running works on the live app, {ds.PAGES_URL}"


def main() -> None:
    doc = ds.build("")
    for short, want in SHORT.items():
        got = doc.count(short)
        if got != want:
            sys.exit(f"expected {want} of {short!r} in the page, found {got}; "
                     "update SHORT in share_app.py")
        doc = doc.replace(short, short.replace("data/", DATA))
    if doc.count(NO_RUN) != 1:
        sys.exit(f"the Run message {NO_RUN!r} was not found; update share_app.py")
    doc = doc.replace(NO_RUN, LIVE)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ds.REPO)} ({OUT.stat().st_size / 2**20:.1f} MB)")


if __name__ == "__main__":
    main()
