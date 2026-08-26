#!/bin/bash
# Install, reload and VERIFY the two scheduled jobs for the paper book.
#
#   weekly   Mon/Tue/Wed 07:30 local (10:30 New York)  -> rebalance runbook
#   daily    Mon-Fri     13:20 local (16:20 New York)  -> results report
#
# launchd, not cron. Cron on macOS runs outside the login session and cannot
# read the login Keychain, where this repo's Alpaca keys live: a cron probe on
# 2026-08-26 returned rc=44 from `security find-generic-password` and an empty
# key, so a cron schedule would have failed silently every Monday. launchd user
# agents run in the GUI session and can read it.
#
#   ./scripts/install_schedule.sh            install, reload and verify
#   ./scripts/install_schedule.sh verify     verify only, change nothing
#   ./scripts/install_schedule.sh remove     unload and delete both agents
set -uo pipefail

REPO="/Volumes/PortableSSD/Github/day-trader"
SRC="$REPO/scripts/launchd"
DEST="$HOME/Library/LaunchAgents"
LOGS="$HOME/Library/Logs/daytrader"
AGENTS=(com.seamus.daytrader.weekly com.seamus.daytrader.daily)
GUI="gui/$(id -u)"
action="${1:-install}"

if [ "$action" = "remove" ]; then
  for a in "${AGENTS[@]}"; do
    launchctl bootout "$GUI/$a" 2>/dev/null && echo "unloaded $a"
    rm -f "$DEST/$a.plist"
  done
  echo "both agents removed."
  exit 0
fi

if [ "$action" = "install" ]; then
  mkdir -p "$DEST" "$LOGS"
  for a in "${AGENTS[@]}"; do
    cp "$SRC/$a.plist" "$DEST/$a.plist" || exit 1
    launchctl bootout "$GUI/$a" 2>/dev/null
    launchctl bootstrap "$GUI" "$DEST/$a.plist" && echo "loaded $a"
  done
fi

echo ""
echo "===== verify ====="
fail=0

for a in "${AGENTS[@]}"; do
  if launchctl print "$GUI/$a" >/dev/null 2>&1; then
    echo "registered: $a"
  else
    echo "NOT REGISTERED: $a"; fail=1
  fi
done

# The one that actually bites. macOS privacy control (TCC) blocks background
# jobs from READING a removable volume until the user grants Full Disk Access.
# Until then the agent dies with "Operation not permitted" before running a
# single line, which looks identical to nothing being scheduled at all.
#
# The probe must attempt a real READ. An earlier version used `ls`, which is a
# stat, and stat is permitted while read is not: it passed while the agents
# were failing, which is a guard that cannot fail. Measured under launchd on
# 2026-08-26: stat OK, list dir BLOCKED, read file BLOCKED, exec a binary OK,
# Keychain OK.
echo ""
echo "checking whether a background job can reach the repo on the portable SSD..."
probe="$LOGS/permission-probe.log"
: > "$probe"
cat > "$DEST/com.seamus.daytrader.probe.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.seamus.daytrader.probe</string>
<key>ProgramArguments</key><array>
<string>/bin/bash</string><string>-c</string>
<string>head -c 1 "$REPO/inputs/alpaca_trade.py" &gt;/dev/null 2&gt;&amp;1 || { echo "REPO_UNREADABLE"; exit 1; }; security find-generic-password -a trader -s ALPACA_API_KEY -w &gt;/dev/null 2&gt;&amp;1 || { echo "KEYCHAIN_UNREADABLE"; exit 1; }; echo BOTH_OK</string>
</array>
<key>StandardOutPath</key><string>$probe</string>
<key>StandardErrorPath</key><string>$probe</string>
<key>RunAtLoad</key><false/>
</dict></plist>
PLIST
launchctl bootout "$GUI/com.seamus.daytrader.probe" 2>/dev/null
launchctl bootstrap "$GUI" "$DEST/com.seamus.daytrader.probe.plist" 2>/dev/null
launchctl kickstart -k "$GUI/com.seamus.daytrader.probe" 2>/dev/null
for _ in $(seq 1 15); do grep -q "BOTH_OK\|not permitted\|error" "$probe" 2>/dev/null && break; sleep 1; done
launchctl bootout "$GUI/com.seamus.daytrader.probe" 2>/dev/null
rm -f "$DEST/com.seamus.daytrader.probe.plist"

if grep -q "BOTH_OK" "$probe" 2>/dev/null; then
  echo "PASS: a background job can read the repo AND the Keychain. The schedule will run."
else
  fail=1
  echo "FAIL: a background job cannot run this repo. It reported:"
  sed 's/^/    /' "$probe"
  cat <<'MSG'

    This is macOS privacy control, not a bug in the schedule. Background jobs
    are refused access to a removable volume until you allow it by hand, and
    the refusal happens before any of our code runs.

    To fix, once:
      1. System Settings > Privacy & Security > Full Disk Access
      2. Press "+", then Shift-Cmd-G, and enter:  /bin/bash
      3. Add it and make sure its switch is on
      4. Re-run:  ./scripts/install_schedule.sh verify

    The durable alternative is to move the repo off the portable SSD onto the
    internal disk, which removes this whole class of problem (and the exFAT
    AppleDouble litter noted in CLAUDE.md) at the same time.
MSG
fi

echo ""
if [ "$fail" -eq 0 ]; then
  echo "SCHEDULE ACTIVE."
else
  echo "SCHEDULE INSTALLED BUT WILL NOT RUN until the above is fixed."
fi
echo "next weekly: Mon/Tue/Wed 07:30 local   next daily: weekdays 13:20 local"
echo "logs: $LOGS"
exit "$fail"
