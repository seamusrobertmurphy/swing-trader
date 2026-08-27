#!/bin/bash
# Weekly runbook for the Alpaca paper momentum book, in one command.
#
# WHY THIS EXISTS. The rebalance due Monday 2026-08-24 never ran, because the
# sequence lived only in a docstring and a person had to remember it. The book
# then went a week without a rebalance and its price bars went stale. The
# execution verdict needs about six clean weekly cycles, so every missed cycle
# costs a week.
#
# RUN IT INTRADAY. Orders submitted while the market is shut queue into the
# opening auction: on 2026-08-26 that cost +42.6bp per fill against +7.3bp for
# the mid-session batch of 2026-08-18. alpaca_trade.py refuses to submit
# outside the session, and this script inherits that guard.
#
# Install (Mon/Tue/Wed 07:30 PT = 10:30 ET, an hour after the open):
#   Superseded by scripts/tick.sh, which decides for itself what is due.
#   Kept for running a cycle by hand.
#
# It is scheduled three days because Monday can be a market holiday. The script
# exits quietly when a rebalance already happened inside the cadence window, so
# on a normal week Tuesday and Wednesday do nothing; after a holiday Monday,
# Tuesday picks the cycle up. alpaca_trade.py's own 5-day cadence guard is the
# backstop, so a double rebalance is impossible even if this check is wrong.
#
# Every run appends to outputs/AA-evals/<date>/runbook-<stamp>.log and exits
# non-zero if any step fails, so a silent failure cannot look like a success.
set -uo pipefail

# Repo is wherever this script lives, one level up, so the tree can be
# cloned or moved to another machine without editing anything.
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -x "$REPO/.venv/bin/python" ]; then PY="$REPO/.venv/bin/python"
else PY="$(command -v python3)"; fi
STAMP="$(date -u +%Y%m%d-%H%M)"
DAY="$(date -u +%Y-%m-%d)"
LOGDIR="$REPO/outputs/AA-evals/$DAY"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/runbook-$STAMP.log"
cd "$REPO" || { echo "ABORT: $REPO unreachable" >&2; exit 1; }
[ -x "$PY" ] || { echo "ABORT: $PY missing" >&2; exit 1; }

# Already rebalanced inside the cadence window? Do nothing and say so. This is
# what makes the Tue/Wed retries silent on a normal week.
if [ -f "$REPO/memory/alpaca-book-state.json" ]; then
  if ! "$PY" - "$REPO/memory/alpaca-book-state.json" <<'EOF'
import json, sys
from datetime import datetime, timezone
last = datetime.fromisoformat(json.load(open(sys.argv[1]))["last_rebalance"])
days = (datetime.now(timezone.utc) - last).days
print(f"last rebalance {days} day(s) ago")
sys.exit(1 if days < 5 else 0)
EOF
  then
    echo "$(date -u +%Y-%m-%dT%H:%MZ) already rebalanced inside the weekly window; nothing to do."
    exit 0
  fi
fi

status=0
step () {
  local title="$1"; shift
  echo "" | tee -a "$LOG"
  echo "===== $title =====" | tee -a "$LOG"
  if ! "$@" 2>&1 | tee -a "$LOG"; then
    echo "STEP FAILED: $*" | tee -a "$LOG"
    status=1
  fi
}

echo "weekly runbook $STAMP UTC" | tee -a "$LOG"
step "1/5 refresh bars"      "$PY" inputs/alpaca_data.py download
step "2/5 rebalance"         "$PY" inputs/alpaca_trade.py rebalance --execute
step "3/5 catastrophe stop"  "$PY" inputs/alpaca_trade.py check
step "4/5 mark to market"    "$PY" inputs/alpaca_trade.py status
step "5/5 execution report"  "$PY" inputs/alpaca_execution_report.py

echo "" | tee -a "$LOG"
if [ "$status" -eq 0 ]; then
  echo "runbook complete, all five steps clean. log: $LOG" | tee -a "$LOG"
else
  echo "runbook finished WITH FAILURES. read: $LOG" | tee -a "$LOG"
fi
exit "$status"
