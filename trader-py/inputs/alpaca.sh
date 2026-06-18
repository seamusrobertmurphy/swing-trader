#!/usr/bin/env bash
# scripts/alpaca.sh — thin curl wrapper for the Alpaca REST API.
#
# Reads from the environment:
#   ALPACA_API_KEY      — required
#   ALPACA_API_SECRET   — required
#   ALPACA_BASE_URL     — required for trading calls (paper: https://paper-api.alpaca.markets)
#   ALPACA_DATA_URL     — optional, default https://data.alpaca.markets (market data host)
#
# The trading API (orders, positions, account) and the market data API (bars,
# quotes, trades) live on different hosts. Trading verbs use ALPACA_BASE_URL;
# the `data` verb routes to ALPACA_DATA_URL. Both share the same key headers.
#
# Usage:
#   scripts/alpaca.sh get   /v2/account
#   scripts/alpaca.sh get   /v2/positions
#   scripts/alpaca.sh get   /v2/orders?status=open
#   scripts/alpaca.sh post  /v2/orders                '{"symbol":"NVDA","qty":12,"side":"buy","type":"limit","limit_price":"876.40","time_in_force":"day","client_order_id":"open-20260512-NVDA"}'
#   scripts/alpaca.sh delete /v2/orders/<order_id>
#   scripts/alpaca.sh clock                          # convenience: GET /v2/clock (trading host)
#   scripts/alpaca.sh data  '/v2/stocks/bars?symbols=AAPL&timeframe=1Day&limit=5'
#   scripts/alpaca.sh data  '/v1beta3/crypto/us/bars?symbols=BTC/USD&timeframe=1Day&limit=5'
#
# Output: response body on stdout. HTTP status on stderr if non-2xx.
#
# Every response's X-Request-ID is appended to logs/alpaca-request-ids.log
# (gitignored) and echoed to stderr on errors. Alpaca support asks for this ID
# to trace a failed call, and it cannot be queried later, so it is persisted now.

set -euo pipefail

: "${ALPACA_API_KEY:?ALPACA_API_KEY not set}"
: "${ALPACA_API_SECRET:?ALPACA_API_SECRET not set}"

method="${1:-}"
path="${2:-}"
body="${3:-}"

if [[ -z "$method" ]]; then
  echo "usage: $0 <get|post|put|patch|delete|clock|data> [path] [json_body]" >&2
  exit 64
fi

# Default to the trading host; the `data` verb switches to the market-data host.
base_url="${ALPACA_BASE_URL:-}"

# Convenience for the clock endpoint (trading host).
if [[ "$method" == "clock" ]]; then
  method="get"
  path="/v2/clock"
fi

# Market-data convenience: `data <path>` issues a GET against the data host.
if [[ "$method" == "data" ]]; then
  method="get"
  base_url="${ALPACA_DATA_URL:-https://data.alpaca.markets}"
fi

if [[ -z "$base_url" ]]; then
  echo "alpaca.sh: ALPACA_BASE_URL not set (required for trading calls; the 'data' verb does not need it)" >&2
  exit 78
fi

method_upper="$(echo "$method" | tr '[:lower:]' '[:upper:]')"
url="${base_url%/}${path}"

hdr_file="$(mktemp)"
trap 'rm -f "$hdr_file"' EXIT

curl_args=(
  -sS
  --fail-with-body
  -D "$hdr_file"
  -w "\n%{http_code}"
  -X "$method_upper"
  -H "APCA-API-KEY-ID: ${ALPACA_API_KEY}"
  -H "APCA-API-SECRET-KEY: ${ALPACA_API_SECRET}"
  -H "Accept: application/json"
)

if [[ -n "$body" ]]; then
  curl_args+=(-H "Content-Type: application/json" --data "$body")
fi

# --fail-with-body exits non-zero on HTTP >= 400; do not let set -e abort before
# we have parsed the body, status, and the X-Request-ID for diagnostics.
set +e
response="$(curl "${curl_args[@]}" "$url")"
curl_rc=$?
set -e

http_code="$(printf '%s' "$response" | tail -n1)"
http_body="$(printf '%s' "$response" | sed '$d')"

# Persist the X-Request-ID. It is in the response header, is not queryable
# later, and is what Alpaca support needs to trace a failed call.
req_id="$(grep -i '^x-request-id:' "$hdr_file" | tail -n1 | tr -d '\r' | awk '{print $2}')"
if [[ -n "${req_id:-}" ]]; then
  log_dir="$(cd "$(dirname "$0")/.." && pwd)/logs"
  mkdir -p "$log_dir"
  printf '%s\t%s\t%s\t%s\t%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$method_upper" "$path" "$http_code" "$req_id" \
    >> "$log_dir/alpaca-request-ids.log"
fi

if ! [[ "$http_code" =~ ^[0-9]+$ ]]; then
  echo "alpaca.sh: no HTTP status (curl exit $curl_rc) — likely a network or DNS error" >&2
  exit 1
fi

echo "$http_body"

if [[ "$http_code" -lt 200 || "$http_code" -ge 300 ]]; then
  echo "alpaca.sh: HTTP $http_code (X-Request-ID: ${req_id:-unknown})" >&2
  exit 1
fi
