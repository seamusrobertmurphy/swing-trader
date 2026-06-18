#!/usr/bin/env bash
# scripts/load-secrets.sh — load API secrets into the environment for a local run.
#
# Source it, do not execute it:
#     source scripts/load-secrets.sh
#
# macOS: reads each secret from the login Keychain (service = var name,
#        account = "trader-swing"). Store them once with scripts/store-secrets.sh.
# Linux: reads them from a gitignored env file, default ~/.config/trader-swing/env
#        (override with TRADER_SWING_ENV). The file is plain NAME=value lines.
#
# Secrets loaded (only those that exist are exported):
#   BINANCE_API_KEY  BINANCE_API_SECRET
#   PERPLEXITY_API_KEY
#   ALPACA_API_KEY   ALPACA_API_SECRET      (optional; paper equities)
#
# Non-secret config defaults are set if unset:
#   BINANCE_BASE_URL   (default https://api.binance.com)
#   ALPACA_BASE_URL    (default https://paper-api.alpaca.markets)
#   LIVE_TRADING       (default false)
#
# Any expected secret that is not stored is reported as a warning; sourcing
# still succeeds, so skipping a key you do not use (e.g. Perplexity) is fine.
# Works whether your shell is bash or zsh.

# Guard: must be sourced, not executed.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "load-secrets.sh must be sourced: 'source scripts/load-secrets.sh'" >&2
  exit 64
fi

_ts_kc_account="trader-swing"
_ts_secret_names=(BINANCE_API_KEY BINANCE_API_SECRET PERPLEXITY_API_KEY ALPACA_API_KEY ALPACA_API_SECRET)

_ts_load_macos() {
  local name val
  for name in "${_ts_secret_names[@]}"; do
    if val="$(security find-generic-password -a "$_ts_kc_account" -s "$name" -w 2>/dev/null)"; then
      export "$name=$val"
    fi
  done
}

_ts_load_linux() {
  local f="${TRADER_SWING_ENV:-$HOME/.config/trader-swing/env}"
  if [[ ! -f "$f" ]]; then
    echo "load-secrets.sh: env file not found at $f" >&2
    return 0
  fi
  local line name val
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" =~ ^[[:space:]]*$ ]] && continue
    name="${line%%=*}"
    val="${line#*=}"
    name="$(echo "$name" | tr -d '[:space:]')"
    [[ -n "$name" ]] && export "$name=$val"
  done < "$f"
}

case "$(uname -s)" in
  Darwin) _ts_load_macos ;;
  *)      _ts_load_linux ;;
esac

# Non-secret defaults.
: "${BINANCE_BASE_URL:=https://api.binance.com}"; export BINANCE_BASE_URL
: "${ALPACA_BASE_URL:=https://paper-api.alpaca.markets}"; export ALPACA_BASE_URL
: "${LIVE_TRADING:=false}"; export LIVE_TRADING

# The Alpaca CLI reads its secret from ALPACA_SECRET_KEY; our scripts use
# ALPACA_API_SECRET. Mirror it so one stored secret serves both.
if [[ -n "${ALPACA_API_SECRET:-}" && -z "${ALPACA_SECRET_KEY:-}" ]]; then
  export ALPACA_SECRET_KEY="$ALPACA_API_SECRET"
fi

# Report any expected secret that is not set (warning only, never fatal).
# eval-based indirect read works in both bash and zsh; ${!name} does not.
_ts_missing=""
for _ts_name in "${_ts_secret_names[@]}"; do
  eval "_ts_val=\"\${$_ts_name:-}\""
  [[ -z "$_ts_val" ]] && _ts_missing="$_ts_missing $_ts_name"
done

if [[ -n "$_ts_missing" ]]; then
  echo "load-secrets.sh: not stored (skipped or missing):$_ts_missing" >&2
fi

echo "load-secrets.sh: secrets loaded (LIVE_TRADING=$LIVE_TRADING)" >&2
unset _ts_kc_account _ts_secret_names _ts_missing _ts_name _ts_val
return 0 2>/dev/null || true
