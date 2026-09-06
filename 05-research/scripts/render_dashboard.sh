#!/bin/bash
# Refresh the dashboard: emit the data, render the Quarto page, optionally open it.
#
#     ./scripts/render_dashboard.sh --open    refresh and show it
#     ./scripts/render_dashboard.sh           refresh only (what the tick calls)
#
# Produces one self-contained 01-dashboard/dashboard.html. There is no server and
# no port: Quarto renders a finished file the way a printer prints a page, and
# "opening" the dashboard means opening that file (or the published link).
#
# Quarto and R are optional. Where they are absent this exits 0 with a note
# rather than failing, so a machine that only trades is not held to be broken
# for lacking a drawing tool.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO" || exit 1
if [ -x "$REPO/.venv/bin/python" ]; then PY="$REPO/.venv/bin/python"
else PY="$(command -v python3)"; fi

"$PY" 03-inputs/dashboard_data.py || { echo "dashboard: data emitter failed" >&2; exit 1; }

# The Analysis and Research pages are fed by their own emitters. Neither is
# allowed to take the page down: the market analysis is worth having, but a
# broken lab engine must not stop the operator seeing where the money is. Each
# failure is reported and the render continues without that page's data.
"$PY" 03-inputs/analysis_charts.py   || echo "dashboard: analysis emitter failed; the Analysis page will be blank" >&2
"$PY" 03-inputs/research_figures.py  || echo "dashboard: figure index failed; the Research page will be blank" >&2

if ! command -v quarto >/dev/null 2>&1; then
  echo "dashboard: quarto not installed; data.json is fresh, page not re-rendered."
  exit 0
fi
if ! command -v R >/dev/null 2>&1 && ! command -v Rscript >/dev/null 2>&1; then
  echo "dashboard: R not installed; data.json is fresh, page not re-rendered."
  exit 0
fi

quarto render 01-dashboard/dashboard.qmd --quiet \
  || { echo "dashboard: quarto render failed" >&2; exit 1; }

PAGE="$REPO/01-dashboard/dashboard.html"
echo "dashboard: $PAGE"

# --open puts it on screen. Not the default: the tick calls this every time
# something happens, and a scheduler must never pop a browser window.
if [ "${1:-}" = "--open" ]; then
  case "$(uname -s)" in
    Darwin) open "$PAGE" ;;
    Linux)  if command -v xdg-open >/dev/null 2>&1; then xdg-open "$PAGE"
            else echo "open it at: file://$PAGE"; fi ;;
  esac
fi
