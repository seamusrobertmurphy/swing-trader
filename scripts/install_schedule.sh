#!/bin/bash
# Install, verify or remove the trading schedule. Works on macOS and Linux.
#
#   ./scripts/install_schedule.sh              install and verify
#   ./scripts/install_schedule.sh verify       check only, change nothing
#   ./scripts/install_schedule.sh remove       uninstall
#   ./scripts/install_schedule.sh install 15   tick every 15 minutes
#
# WHAT GETS SCHEDULED. One job: scripts/tick.sh, every TICK_MINUTES minutes,
# all day. It asks Alpaca's clock what is due and usually does nothing. There
# is no wall-clock time anywhere in the schedule, so moving this repo to
# another machine in another timezone needs no edit. The tick handles the
# catastrophe stop while the market is open, the weekly rebalance when the
# cadence is due and the moment is calm, and the daily report after the close.
#
# WHY NOT CRON ON macOS. Cron runs outside the login session and cannot read
# the login Keychain, where the Alpaca keys live on this Mac: a probe on
# 2026-08-26 returned rc=44 and an empty key. It fails silently, so the
# schedule would look installed and never trade. launchd agents can read it.
# On Linux there is no Keychain, credentials come from the environment or
# <repo>/.env, and systemd (or cron) is fine.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TPL="$REPO/scripts/schedule"
LABEL="com.daytrader.tick"
UNIT="daytrader-tick"
action="${1:-install}"
TICK_MINUTES="${2:-20}"
OS="$(uname -s)"

fill () {   # template -> stdout, with the repo's real paths substituted
  sed -e "s#__REPO__#$REPO#g" \
      -e "s#__LABEL__#$LABEL#g" \
      -e "s#__LOGDIR__#$LOGDIR#g" \
      -e "s#__INTERVAL__#$((TICK_MINUTES * 60))#g" \
      -e "s#__MINUTES__#$TICK_MINUTES#g" "$1"
}

case "$OS" in
  Darwin) LOGDIR="$HOME/Library/Logs/daytrader"; DEST="$HOME/Library/LaunchAgents" ;;
  Linux)  LOGDIR="${XDG_STATE_HOME:-$HOME/.local/state}/daytrader"
          DEST="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user" ;;
  *)      echo "unsupported OS: $OS"; exit 1 ;;
esac
mkdir -p "$LOGDIR"

# ---------------------------------------------------------------- remove ----
if [ "$action" = "remove" ]; then
  if [ "$OS" = "Darwin" ]; then
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null && echo "unloaded $LABEL"
    rm -f "$DEST/$LABEL.plist"
  else
    systemctl --user disable --now "$UNIT.timer" 2>/dev/null && echo "disabled $UNIT.timer"
    rm -f "$DEST/$UNIT.service" "$DEST/$UNIT.timer"
    systemctl --user daemon-reload 2>/dev/null
  fi
  echo "schedule removed."
  exit 0
fi

# --------------------------------------------------------------- install ----
if [ "$action" = "install" ]; then
  mkdir -p "$DEST"
  if [ "$OS" = "Darwin" ]; then
    fill "$TPL/launchd.plist.template" > "$DEST/$LABEL.plist"
    plutil -lint "$DEST/$LABEL.plist" >/dev/null || { echo "bad plist"; exit 1; }
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null
    launchctl bootstrap "gui/$(id -u)" "$DEST/$LABEL.plist" \
      && echo "loaded $LABEL (every $TICK_MINUTES min)"
  else
    fill "$TPL/systemd.service.template" > "$DEST/$UNIT.service"
    fill "$TPL/systemd.timer.template"   > "$DEST/$UNIT.timer"
    systemctl --user daemon-reload
    systemctl --user enable --now "$UNIT.timer" \
      && echo "enabled $UNIT.timer (every $TICK_MINUTES min)"
    # Without lingering, user timers stop when the last session logs out, which
    # is exactly what happens on a headless box you ssh into and leave.
    if ! loginctl show-user "$USER" 2>/dev/null | grep -q "Linger=yes"; then
      echo ""
      echo "NOTE: user services stop when you log out of this machine. To keep"
      echo "      the schedule running headless, once:"
      echo "          sudo loginctl enable-linger $USER"
    fi
  fi
fi

# ---------------------------------------------------------------- verify ----
echo ""
echo "===== verify ====="
fail=0
echo "repo:        $REPO"
echo "logs:        $LOGDIR"
echo "tick every:  $TICK_MINUTES minutes"

if [ "$OS" = "Darwin" ]; then
  launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1 \
    && echo "registered:  $LABEL" || { echo "NOT REGISTERED: $LABEL"; fail=1; }
else
  systemctl --user is-enabled "$UNIT.timer" >/dev/null 2>&1 \
    && echo "registered:  $UNIT.timer" || { echo "NOT ENABLED: $UNIT.timer"; fail=1; }
fi

# 1. Credentials resolve at all.
echo ""
if "$REPO/.venv/bin/python" "$REPO/inputs/config.py" 2>/dev/null | grep -q "ALPACA_API_KEY .*set"; then
  echo "credentials: found"
else
  echo "credentials: MISSING. Put them in the environment or $REPO/.env (mode 600)."
  fail=1
fi

# 2. The scheduler can actually READ this repo. On macOS a repo on a removable
#    volume is blocked by privacy control until /bin/bash is granted Full Disk
#    Access, and the job then dies before running a line. The probe must attempt
#    a real read: an earlier version used `ls`, which is a stat, and stat is
#    permitted while read is not, so it passed while the agents were failing.
echo ""
echo "checking that a background job can read this repo..."
probe="$LOGDIR/permission-probe.log"; : > "$probe"
if [ "$OS" = "Darwin" ]; then
  cat > "$DEST/$LABEL.probe.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>$LABEL.probe</string>
<key>ProgramArguments</key><array><string>/bin/bash</string><string>-c</string>
<string>head -c 1 "$REPO/inputs/config.py" &gt;/dev/null 2&gt;&amp;1 &amp;&amp; echo READ_OK || echo READ_BLOCKED</string>
</array>
<key>StandardOutPath</key><string>$probe</string>
<key>StandardErrorPath</key><string>$probe</string>
<key>RunAtLoad</key><false/></dict></plist>
PLIST
  launchctl bootout "gui/$(id -u)/$LABEL.probe" 2>/dev/null
  launchctl bootstrap "gui/$(id -u)" "$DEST/$LABEL.probe.plist" 2>/dev/null
  launchctl kickstart -k "gui/$(id -u)/$LABEL.probe" 2>/dev/null
  for _ in $(seq 1 15); do grep -q "READ_" "$probe" 2>/dev/null && break; sleep 1; done
  launchctl bootout "gui/$(id -u)/$LABEL.probe" 2>/dev/null
  rm -f "$DEST/$LABEL.probe.plist"
else
  head -c 1 "$REPO/inputs/config.py" >/dev/null 2>&1 && echo READ_OK > "$probe" \
                                                     || echo READ_BLOCKED > "$probe"
fi

if grep -q READ_OK "$probe" 2>/dev/null; then
  echo "PASS: the scheduler can read this repo."
else
  fail=1
  echo "FAIL: a background job cannot read this repo."
  if [ "$OS" = "Darwin" ]; then
    cat <<'MSG'

    macOS privacy control refuses background jobs read access to a removable
    volume, and the refusal happens before any of our code runs.

    Fix, once:
      1. System Settings > Privacy & Security > Full Disk Access
      2. "+", then Shift-Cmd-G, enter:  /bin/bash
      3. Add it, switch it on
      4. Re-run: ./scripts/install_schedule.sh verify

    Or move the repo to the internal disk, which removes this whole class of
    problem (and the exFAT litter noted in CLAUDE.md) at once.
MSG
  fi
fi

# 3. The tick itself runs end to end.
echo ""
echo "dry-running one tick..."
if "$REPO/scripts/tick.sh" --dry-run 2>&1 | tail -2 | sed 's/^/    /'; then :; else fail=1; fi

echo ""
[ "$fail" -eq 0 ] && echo "SCHEDULE ACTIVE." \
                  || echo "SCHEDULE INSTALLED BUT WILL NOT RUN until the above is fixed."
exit "$fail"
