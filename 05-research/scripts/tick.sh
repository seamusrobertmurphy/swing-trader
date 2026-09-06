#!/bin/bash
# One wake-up of the trading schedule. Portable: finds its own repo, picks the
# interpreter, logs, and never assumes a timezone or an operating system.
#
# Called by the scheduler (launchd on macOS, systemd on Linux, cron anywhere).
# Safe to run by hand at any moment: it decides what is due and usually does
# nothing.
set -uo pipefail

# Repo is wherever this script lives, one level up. Never hard-coded, so the
# whole tree can be moved or cloned to another machine and still work.
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO" || { echo "ABORT: cannot enter $REPO" >&2; exit 1; }

# Prefer the project venv, fall back to whatever python3 is on PATH.
if [ -x "$REPO/.venv/bin/python" ]; then PY="$REPO/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then PY="$(command -v python3)"
else echo "ABORT: no python found" >&2; exit 1; fi

LOGDIR="${DAYTRADER_LOG_DIR:-$REPO/outputs/AA-evals/logs}"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/tick-$(date -u +%Y-%m).log"     # one file per month, appended

{
  "$PY" 03-inputs/schedule_tick.py "$@"
  rc=$?
  [ "$rc" -ne 0 ] && echo "TICK EXITED $rc"
  exit "$rc"
} 2>&1 | tee -a "$LOG"
exit "${PIPESTATUS[0]}"
