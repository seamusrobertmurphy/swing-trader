#!/bin/bash
# Run the tick every TICK_MINUTES, forever, in this session's permission context.
#
# WHY THIS EXISTS. On the Mac the repo sits on a removable volume, and macOS
# refuses background jobs (launchd, cron) read access to it until someone grants
# Full Disk Access by hand. A process started from an already-permitted shell
# inherits that permission, so this runs where a scheduled agent cannot.
#
# The trade-off, stated plainly: this does NOT survive a reboot. launchd or
# systemd does. It is the no-clicks-required option, not the durable one. On
# Linux use ./scripts/install_schedule.sh instead; none of this applies there.
#
#     nohup ./scripts/run_forever.sh > /dev/null 2>&1 &     start, survives logout
#     ./scripts/run_forever.sh stop                         stop it
#     ./scripts/run_forever.sh status                       is it alive
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TICK_MINUTES="${TICK_MINUTES:-20}"
PIDFILE="$REPO/outputs/AA-evals/logs/run_forever.pid"
LOG="$REPO/outputs/AA-evals/logs/run_forever.log"
mkdir -p "$(dirname "$PIDFILE")"

case "${1:-run}" in
  stop)
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      kill "$(cat "$PIDFILE")" && echo "stopped pid $(cat "$PIDFILE")"; rm -f "$PIDFILE"
    else echo "not running"; rm -f "$PIDFILE"; fi
    exit 0 ;;
  status)
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      echo "running, pid $(cat "$PIDFILE"), tick every $TICK_MINUTES min"
      echo "last lines:"; tail -3 "$LOG" 2>/dev/null | sed 's/^/    /'
    else echo "not running"; fi
    exit 0 ;;
esac

# Refuse to start twice.
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "already running, pid $(cat "$PIDFILE")"; exit 0
fi
echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) supervisor start, pid $$, every $TICK_MINUTES min" >> "$LOG"
while true; do
  "$REPO/scripts/tick.sh" >> "$LOG" 2>&1
  sleep $((TICK_MINUTES * 60))
done
