#!/usr/bin/env bash
# scripts/store-secrets.sh — store API secrets once, securely, for local runs.
#
#     bash scripts/store-secrets.sh
#
# macOS: writes each secret into the login Keychain (encrypted, OS-managed),
#        service = var name, account = "trader-swing". Re-running updates them.
# Linux: writes them to a gitignored env file (default ~/.config/trader-swing/env),
#        created with 0600 permissions. Override the path with TRADER_SWING_ENV.
#
# You are prompted for each value; input is hidden and never echoed or written
# to shell history. Leave a prompt blank to skip that key.

set -euo pipefail

kc_account="trader-swing"
names=(BINANCE_API_KEY BINANCE_API_SECRET PERPLEXITY_API_KEY ALPACA_API_KEY ALPACA_API_SECRET)

prompt_secret() {  # $1 = name; prints the entered value (may be empty)
  local name="$1" val=""
  read -r -s -p "  $name (blank to skip): " val </dev/tty
  echo >&2
  printf '%s' "$val"
}

if [[ "$(uname -s)" == "Darwin" ]]; then
  echo "Storing secrets in the macOS login Keychain (account: $kc_account)."
  for name in "${names[@]}"; do
    val="$(prompt_secret "$name")"
    if [[ -z "$val" ]]; then echo "  skipped $name"; continue; fi
    security add-generic-password -U -a "$kc_account" -s "$name" -w "$val"
    echo "  stored $name"
  done
  echo "Done. Load into a shell with: source scripts/load-secrets.sh"
else
  envfile="${TRADER_SWING_ENV:-$HOME/.config/trader-swing/env}"
  mkdir -p "$(dirname "$envfile")"
  touch "$envfile"; chmod 600 "$envfile"
  echo "Writing secrets to $envfile (chmod 600)."
  declare -A newvals=()
  for name in "${names[@]}"; do
    val="$(prompt_secret "$name")"
    [[ -n "$val" ]] && newvals["$name"]="$val"
  done
  tmp="$(mktemp)"; chmod 600 "$tmp"
  # Preserve existing lines whose key we are not overwriting.
  if [[ -s "$envfile" ]]; then
    while IFS= read -r line || [[ -n "$line" ]]; do
      n="${line%%=*}"
      [[ -n "${newvals[$n]+x}" ]] && continue
      printf '%s\n' "$line" >> "$tmp"
    done < "$envfile"
  fi
  for name in "${!newvals[@]}"; do
    printf '%s=%s\n' "$name" "${newvals[$name]}" >> "$tmp"
    echo "  stored $name"
  done
  mv "$tmp" "$envfile"; chmod 600 "$envfile"
  echo "Done. load-secrets.sh reads $envfile on Linux."
fi
