#!/bin/bash
# Refresh the dashboard: emit the data, render the Quarto page.
#
# Produces one self-contained dashboard/dashboard.html. There is no server and
# no port: Quarto renders a finished file the way a printer prints a page, and
# "opening" the dashboard means opening that file (or the published link).
#
# Quarto and R are optional. Where they are absent this exits 0 with a note
# rather than failing, so a machine that only trades is not held to be broken
# for lacking a drawing tool.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || exit 1
if [ -x "$REPO/.venv/bin/python" ]; then PY="$REPO/.venv/bin/python"
else PY="$(command -v python3)"; fi

"$PY" inputs/dashboard_data.py || { echo "dashboard: data emitter failed" >&2; exit 1; }

if ! command -v quarto >/dev/null 2>&1; then
  echo "dashboard: quarto not installed; data.json is fresh, page not re-rendered."
  exit 0
fi
if ! command -v R >/dev/null 2>&1 && ! command -v Rscript >/dev/null 2>&1; then
  echo "dashboard: R not installed; data.json is fresh, page not re-rendered."
  exit 0
fi

quarto render dashboard/dashboard.qmd --quiet \
  && echo "dashboard: $REPO/dashboard/dashboard.html" \
  || { echo "dashboard: quarto render failed" >&2; exit 1; }
