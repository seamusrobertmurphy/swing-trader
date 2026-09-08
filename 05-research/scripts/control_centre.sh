#!/bin/bash
# Start the control centre and open it.
#
#   05-research/scripts/control_centre.sh            # start, then open a browser
#   05-research/scripts/control_centre.sh --check    # run the acceptance checks and exit
#   05-research/scripts/control_centre.sh --port 9000
#
# The checks are in 03-inputs/control_eval.py and their objectives in
# 05-research/tasks/eval-control-centre.md.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="$REPO/.venv/bin/python"
PORT=8787
CHECK=0

while [ $# -gt 0 ]; do
  case "$1" in
    --check) CHECK=1; shift ;;
    --port)  PORT="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [ ! -x "$PY" ]; then
  echo "no interpreter at $PY. The control centre runs every job under the" >&2
  echo "project venv, never under whatever python is first on PATH." >&2
  exit 1
fi

# The repo lives on an exFAT volume, which cannot hold extended attributes, so
# macOS scatters "._" companion files. Matplotlib reads "._*.mplstyle" and dies
# with a UnicodeDecodeError on byte 0xb0, which would take down a job rather
# than the page. Cheap to clear, so clear it before starting.
find "$REPO/.venv" -name '._*' -delete 2>/dev/null || true

if [ "$CHECK" = "1" ]; then
  exec "$PY" "$REPO/03-inputs/control_eval.py" --layout
fi

"$PY" "$REPO/03-inputs/control_centre.py" --port "$PORT" &
SERVER=$!
trap 'kill $SERVER 2>/dev/null || true' EXIT INT TERM

# Wait for it to answer rather than guessing at a sleep.
for _ in $(seq 1 40); do
  if curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
    open "http://127.0.0.1:$PORT/" 2>/dev/null || true
    break
  fi
  sleep 0.25
done

wait $SERVER
