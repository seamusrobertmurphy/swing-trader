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
# opening auction: on 2026-08-26 that cost +42.6bp per fill against +3.8bp for
# the mid-session batch of 2026-08-18. alpaca_trade.py refuses to submit
# outside the session, and this script inherits that guard.
#
# Install (Mondays, 10:30 ET = 07:30 PT, an hour after the open):
#     crontab -e
#     30 7 * * 1 /Volumes/PortableSSD/Github/day-trader/scripts/weekly_rebalance.sh
#
# Every run appends to outputs/AA-evals/<date>/runbook-<stamp>.log and exits
# non-zero if any step fails, so a silent failure cannot look like a success.
set -uo pipefail

REPO="/Volumes/PortableSSD/Github/day-trader"
PY="$REPO/.venv/bin/python"
STAMP="$(date -u +%Y%m%d-%H%M)"
DAY="$(date -u +%Y-%m-%d)"
LOGDIR="$REPO/outputs/AA-evals/$DAY"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/runbook-$STAMP.log"
cd "$REPO" || exit 1

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
