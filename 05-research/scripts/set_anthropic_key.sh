#!/bin/bash
# Put the Anthropic API key into the macOS login Keychain, where config.py
# already looks for every other credential this project uses.
#
#     ./05-research/scripts/set_anthropic_key.sh                 # from ~/Keys/claude.txt
#     ./05-research/scripts/set_anthropic_key.sh path/to/file    # from somewhere else
#     ./05-research/scripts/set_anthropic_key.sh FILE --key 2    # pick, when the file holds several
#     ./05-research/scripts/set_anthropic_key.sh --check         # report only, change nothing
#
# The key is never printed, never passed as a command argument, and never
# written into this repository. It is read from the file, piped straight into
# `security` on standard input, and the only thing echoed is its last four
# characters so you can tell which key is stored.
#
# WHY STDIN AND NOT AN ARGUMENT. `security add-generic-password -w VALUE` puts
# the key in the process argument list, where `ps` can read it, and in the shell
# history file. Given -w with no value the command prompts twice and reads the
# terminal, and it accepts a pipe if the value arrives twice, which is what the
# printf below does. Verified on this machine on 8 September 2026.
set -uo pipefail

SERVICE="ANTHROPIC_API_KEY"
ACCOUNT="trader"                       # the same account the Alpaca keys use
SRC="${1:-$HOME/Keys/claude.txt}"
PICK=""
if [ "${2:-}" = "--key" ]; then PICK="${3:-}"; fi
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [ "$SRC" = "--check" ]; then
  if security find-generic-password -a "$ACCOUNT" -s "$SERVICE" >/dev/null 2>&1; then
    tail4=$(security find-generic-password -a "$ACCOUNT" -s "$SERVICE" -w 2>/dev/null | tail -c 5)
    echo "Keychain holds $SERVICE for account $ACCOUNT, ending $tail4"
  else
    echo "Keychain has no $SERVICE for account $ACCOUNT"
  fi
  "$REPO/.venv/bin/python" -c "
import sys; sys.path.insert(0, '$REPO/03-inputs')
import config
print('config.py resolves it from:', config.source_of('$SERVICE'))"
  exit 0
fi

[ -r "$SRC" ] || { echo "ABORT: cannot read $SRC" >&2; exit 1; }

# A key file that anyone on the machine can read is not a secret. Every file in
# ~/Keys was mode 644 on 8 September 2026, which is world-readable.
mode=$(stat -f %Lp "$SRC")
if [ "$mode" != "600" ]; then
  echo "note: $SRC was mode $mode, which others can read. Tightening to 600."
  chmod 600 "$SRC"
  chmod 700 "$(dirname "$SRC")" 2>/dev/null || true
fi

# Pull the first Anthropic key out of the file, whatever else the file says
# around it. A key file often carries a label line, a date, or several keys.
# A read loop, not mapfile: macOS ships bash 3.2 at /bin/bash and mapfile is a
# bash 4 builtin, so the script died on its own first line of work.
FOUND=()
while IFS= read -r _k; do
  [ -n "$_k" ] && FOUND+=("$_k")
done < <(grep -oE 'sk-ant-[A-Za-z0-9_-]{20,}' "$SRC")
n=${#FOUND[@]}
if [ "$n" -eq 0 ]; then
  echo "ABORT: no string matching sk-ant-... found in $SRC." >&2
  echo "       The file has $(wc -l < "$SRC" | tr -d ' ') lines. Nothing was read out of it." >&2
  exit 1
fi

# NEVER guess which of several keys is wanted. An earlier version took the first
# and said so in a note, and on 8 September 2026 the first was the key expiring
# in October while the second was the replacement, so the wrong one was stored
# and verified green. A file with more than one key now stops and asks.
if [ "$n" -gt 1 ] && [ -z "$PICK" ]; then
  echo "$SRC holds $n keys and this script will not choose between them."
  echo
  i=1
  for k in ${FOUND[@]+"${FOUND[@]}"}; do
    fp=$(printf '%s' "$k" | shasum -a 256 | cut -c1-12)
    line=$(grep -n "${k:0:24}" "$SRC" | head -1 | cut -d: -f1)
    label=$(sed -n "$((line>1 ? line-1 : 1))p;${line}p" "$SRC" \
            | sed -E 's/sk-ant-[A-Za-z0-9_-]+/<key>/g' | tr '\n' ' ' | cut -c1-60)
    echo "  key $i: ends ${k: -4}  fingerprint $fp  line $line"
    echo "         context: $label"
    i=$((i+1))
  done
  echo
  echo "Re-run naming the one you want:  $0 $SRC --key 2"
  exit 2
fi

IDX=${PICK:-1}
if [ "$IDX" -lt 1 ] || [ "$IDX" -gt "$n" ]; then
  echo "ABORT: --key $IDX but the file holds $n." >&2; exit 1
fi
KEY="${FOUND[$((IDX-1))]}"

printf '%s\n%s\n' "$KEY" "$KEY" \
  | security add-generic-password -U -a "$ACCOUNT" -s "$SERVICE" -w >/dev/null 2>&1
if ! security find-generic-password -a "$ACCOUNT" -s "$SERVICE" >/dev/null 2>&1; then
  echo "ABORT: the Keychain did not accept the item." >&2
  exit 1
fi
echo "stored $SERVICE in the login Keychain, account $ACCOUNT, ending ${KEY: -4}"

# Verify against the live API with the smallest call that proves the key works.
echo "verifying against the Anthropic API ..."
code=$(curl -s -o /dev/null -w '%{http_code}' https://api.anthropic.com/v1/messages \
  -H "x-api-key: $KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-haiku-4-5-20251001","max_tokens":1,"messages":[{"role":"user","content":"hi"}]}')
case "$code" in
  200) echo "  HTTP 200. The key works." ;;
  401) echo "  HTTP 401. The key was rejected as invalid or revoked." ;;
  429) echo "  HTTP 429. The key is valid; the account is rate limited right now." ;;
  *)   echo "  HTTP $code. Not a clear pass; check the account at console.anthropic.com." ;;
esac

unset KEY
echo
echo "Nothing was written into the repository. To read it back:"
echo "  .venv/bin/python -c \"import sys; sys.path.insert(0,'03-inputs'); import config; print(config.source_of('$SERVICE'))\""
