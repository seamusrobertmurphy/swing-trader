#!/usr/bin/env bash
# scripts/binance.sh — thin, signed curl wrapper for the Binance Spot REST API.
#
# Reads from the environment:
#   BINANCE_API_KEY     — required (signed and key-only calls)
#   BINANCE_API_SECRET  — required for signed calls
#   BINANCE_BASE_URL    — optional, default https://api.binance.com (LIVE exchange,
#                         real funds). Testnet: https://testnet.binance.vision
#   BINANCE_RECV_WINDOW — optional, default 5000 (ms)
#   LIVE_TRADING        — must be exactly "true" to place or cancel a real order.
#                         Any other value (including unset) blocks order endpoints.
#                         Read-only signed calls (e.g. /api/v3/account) are unaffected.
#
# Usage:
#   scripts/binance.sh public GET    /api/v3/ticker/price "symbol=BTCUSDT"
#   scripts/binance.sh signed GET    /api/v3/account      ""
#   scripts/binance.sh signed POST   /api/v3/order        "symbol=BTCUSDT&side=BUY&type=MARKET&quoteOrderQty=50"
#   scripts/binance.sh signed DELETE /api/v3/order        "symbol=BTCUSDT&orderId=12345"
#
# Output: response body on stdout. On API error the body is printed and the
# script exits non-zero. Error -2015 (invalid key / IP / permission) additionally
# fires scripts/alert.sh, because the usual cause is a changed home IP that no
# longer matches the key's trusted-IP whitelist.

set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"

mode="${1:-}"; method="${2:-}"; path="${3:-}"; query="${4:-}"

if [[ -z "$mode" || -z "$method" || -z "$path" ]]; then
  echo "usage: $0 <public|signed> <GET|POST|DELETE|PUT> <path> [query]" >&2
  exit 64
fi

: "${BINANCE_API_KEY:?BINANCE_API_KEY not set}"
base="${BINANCE_BASE_URL:-https://api.binance.com}"
recv="${BINANCE_RECV_WINDOW:-5000}"
method_upper="$(echo "$method" | tr '[:lower:]' '[:upper:]')"

# Live-trading gate. Placing, replacing, or cancelling a real order on the live
# exchange requires the deliberate switch LIVE_TRADING=true. This is the single
# safety switch the brief mandates: it makes an accidental or mis-scripted order
# impossible to fire by default. Read-only signed calls (account, balances,
# open orders via GET) are never gated.
if [[ "$method_upper" =~ ^(POST|PUT|DELETE)$ && "$path" == *"/order"* ]]; then
  if [[ "${LIVE_TRADING:-false}" != "true" ]]; then
    echo "binance.sh: refusing to $method_upper $path — LIVE_TRADING is not 'true' (got '${LIVE_TRADING:-unset}')." >&2
    echo "binance.sh: this is the safety switch. To place a real order, run: export LIVE_TRADING=true" >&2
    exit 77
  fi
fi

if [[ "$mode" == "signed" ]]; then
  : "${BINANCE_API_SECRET:?BINANCE_API_SECRET not set}"
  ts="$(( $(date +%s) * 1000 ))"
  q="$query"
  [[ -n "$q" ]] && q="${q}&"
  q="${q}recvWindow=${recv}&timestamp=${ts}"
  sig="$(printf '%s' "$q" | openssl dgst -sha256 -hmac "$BINANCE_API_SECRET" | sed -E 's/^.*= *//')"
  url="${base%/}${path}?${q}&signature=${sig}"
elif [[ "$mode" == "public" ]]; then
  url="${base%/}${path}"
  [[ -n "$query" ]] && url="${url}?${query}"
else
  echo "binance.sh: mode must be 'public' or 'signed', got '$mode'" >&2
  exit 64
fi

response="$(curl -sS -w $'\n%{http_code}' -X "$method_upper" -H "X-MBX-APIKEY: ${BINANCE_API_KEY}" "$url")"
http_code="$(printf '%s' "$response" | tail -n1)"
http_body="$(printf '%s' "$response" | sed '$d')"

printf '%s\n' "$http_body"

# Binance reports API errors as JSON {"code":-XXXX,"msg":"..."} even on HTTP 200.
if printf '%s' "$http_body" | grep -Eq '"code":[[:space:]]*-2015'; then
  "$here/alert.sh" "binance -2015" \
    "Binance rejected the request: invalid API key, IP, or permissions (-2015). The usual cause is your home IP changing so it no longer matches the key's trusted-IP whitelist. Run 'curl ifconfig.me' and update the Binance API key's IP list, then retry."
  exit 75
fi

if printf '%s' "$http_body" | grep -Eq '"code":[[:space:]]*-[0-9]+'; then
  echo "binance.sh: API error in response (see body above)" >&2
  exit 1
fi

if [[ "$http_code" -lt 200 || "$http_code" -ge 300 ]]; then
  echo "binance.sh: HTTP $http_code" >&2
  exit 1
fi
