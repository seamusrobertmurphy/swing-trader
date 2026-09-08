#!/bin/bash
# Render the runtime document, 02-runtime/trader-workflow.qmd, to HTML and Word.
#
#     ./05-research/scripts/render_workflow.sh          both formats
#     ./05-research/scripts/render_workflow.sh html     HTML only, quick
#
# WHY THIS SCRIPT EXISTS. Three things must happen in order and each has been
# forgotten at least once.
#
#  1. QUARTO_PYTHON must point at the project venv. Quarto looks for the
#     jupyter-cache package in whatever Python IT resolves, not in the kernel's,
#     so without this the render aborts on a missing package while the kernel
#     itself is fine.
#  2. Quarto renders the docx through pandoc, which sizes every table to its own
#     content. Thirty-five tables end up at thirty-five widths and the document
#     reads as a pile of fragments. format_docx_tables.py is the post-pass that
#     gives them one shape, set by the operator on 2026-09-07. It is not
#     optional and Quarto cannot do it.
#  3. The first render after any source edit re-executes every cell, about
#     fifteen minutes. It is near-instant afterwards because the cache holds.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO" || exit 1
DOC="02-runtime/trader-workflow.qmd"
what="${1:-all}"

if [ -x "$REPO/.venv/bin/python" ]; then PY="$REPO/.venv/bin/python"
else PY="$(command -v python3)"; fi
export QUARTO_PYTHON="$PY"

command -v quarto >/dev/null 2>&1 || { echo "quarto not installed; nothing rendered." >&2; exit 0; }

render () {
  echo "rendering $1 ..."
  quarto render "$DOC" --to "$1" || { echo "render to $1 FAILED" >&2; return 1; }
}

rc=0
case "$what" in
  html) render html || rc=1 ;;
  docx) render docx || rc=1 ;;
  *)    render html || rc=1; render docx || rc=1 ;;
esac

# Step 2. Only if a docx was actually produced by this run.
if [ "$what" != "html" ] && [ -f "02-runtime/trader-workflow.docx" ]; then
  "$PY" 03-inputs/format_docx_tables.py 02-runtime/trader-workflow.docx \
    || { echo "table formatting pass FAILED; the docx tables are unshaped" >&2; rc=1; }
fi

for f in 02-runtime/trader-workflow.html 02-runtime/trader-workflow.docx; do
  [ -f "$f" ] && echo "  $f  ($(date -r "$f" '+%Y-%m-%d %H:%M'), $(du -h "$f" | cut -f1))"
done
exit "$rc"
