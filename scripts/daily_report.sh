#!/bin/bash
# Daily results report for the Alpaca paper momentum book.
#
# Runs the catastrophe stop, marks the book to market, and writes the report
# that opens with the "Where the money actually is" block. Every figure is
# recomputed at the moment of writing.
#
# Install (weekdays 13:20 PT = 16:20 ET, twenty minutes after the close, so the
# closing marks have settled):
#     20 13 * * 1-5 /Volumes/PortableSSD/Github/day-trader/scripts/daily_report.sh
#
# On a market holiday the account simply reports an unchanged book, which is the
# correct answer, so no holiday calendar is needed here.
set -uo pipefail

REPO="/Volumes/PortableSSD/Github/day-trader"
PY="$REPO/.venv/bin/python"
STAMP="$(date -u +%Y%m%d-%H%M)"
DAY="$(date -u +%Y-%m-%d)"
LOGDIR="$REPO/outputs/AA-evals/$DAY"
cd "$REPO" || { echo "ABORT: $REPO unreachable (portable SSD not mounted?)" >&2; exit 1; }
[ -x "$PY" ] || { echo "ABORT: $PY missing" >&2; exit 1; }
mkdir -p "$LOGDIR"
LOG="$LOGDIR/daily-$STAMP.log"

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

echo "daily report $STAMP UTC" | tee -a "$LOG"
step "1/3 catastrophe stop" "$PY" inputs/alpaca_trade.py check
step "2/3 mark to market"   "$PY" inputs/alpaca_trade.py status
step "3/3 write report"     "$PY" inputs/alpaca_daily_report.py

if [ "$status" -eq 0 ]; then
  echo "" | tee -a "$LOG"
  echo "daily report complete. log: $LOG" | tee -a "$LOG"
else
  echo "" | tee -a "$LOG"
  echo "daily report finished WITH FAILURES. read: $LOG" | tee -a "$LOG"
fi
exit "$status"
