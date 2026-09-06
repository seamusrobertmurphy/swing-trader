#!/bin/bash
# Put the Alpaca keys where every scheduler on this machine will find them.
#
#     ./scripts/set_credentials.sh KEY SECRET
#     ./scripts/set_credentials.sh            (prompts, nothing echoed)
#
# Writes ~/.config/daytrader/env, mode 600, outside the repo so it can never be
# committed and so it sits on a filesystem that actually enforces permissions
# (the Mac's exFAT SSD does not). The systemd unit reads it; config.py reads the
# environment first, so exporting these by hand works too.
set -uo pipefail

DIR="$HOME/.config/daytrader"
F="$DIR/env"
K="${1:-}"; S="${2:-}"
if [ -z "$K" ]; then read -rp "ALPACA_API_KEY: " K; fi
if [ -z "$S" ]; then read -rsp "ALPACA_API_SECRET (not echoed): " S; echo; fi
[ -z "$K" ] || [ -z "$S" ] && { echo "ABORT: both values are required." >&2; exit 1; }

mkdir -p "$DIR"; chmod 700 "$DIR"
umask 077
cat > "$F" <<EOF
ALPACA_API_KEY=$K
ALPACA_API_SECRET=$S
ALPACA_BASE_URL=https://paper-api.alpaca.markets
LIVE_TRADING=false
EOF
chmod 600 "$F"
echo "wrote $F (mode $(stat -f %Lp "$F" 2>/dev/null || stat -c %a "$F"))"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="$REPO/.venv/bin/python"; [ -x "$PY" ] || PY="$(command -v python3)"
echo "verifying against the live paper account..."
env ALPACA_API_KEY="$K" ALPACA_API_SECRET="$S" "$PY" "$REPO/inputs/alpaca_check.py" 2>&1 | head -3
