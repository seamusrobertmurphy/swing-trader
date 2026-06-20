#!/usr/bin/env bash
# scripts/alert.sh — surface an operational alert to the human, loudly.
#
#     scripts/alert.sh "<short-title>" "<body>"
#
# Three channels, best-effort, never fatal to the caller:
#   1. Durable: appends a dated block to memory/research-log.md (the routine
#      commits it, so it is seen on the next read even if the popup is missed).
#   2. Terminal: prints to stderr.
#   3. Desktop: macOS `osascript` notification, or Linux `notify-send` if present.
#
# Exits 0 always; the caller decides whether the underlying condition is fatal.

title="${1:-alert}"
body="${2:-}"
ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
log="$repo_root/memory/research-log.md"

{ printf '\n## %s ALERT — %s\n%s\n' "$ts" "$title" "$body" >> "$log"; } 2>/dev/null || true

echo "ALERT [$title] $body" >&2

if command -v osascript >/dev/null 2>&1; then
  osascript -e "display notification \"${body//\"/\\\"}\" with title \"trader-swing: ${title//\"/\\\"}\"" >/dev/null 2>&1 || true
elif command -v notify-send >/dev/null 2>&1; then
  notify-send "trader-swing: $title" "$body" >/dev/null 2>&1 || true
fi

exit 0
