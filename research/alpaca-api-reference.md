# Alpaca API reference (trader-swing slice)

Curated from the Alpaca docs index at https://docs.alpaca.markets/llms.txt. That
index spans 350+ pages, most of it the **Broker API** (custodial account
creation, KYC, withdrawals, whitelisted addresses) for partners running accounts
on behalf of others. None of that applies to a self-directed trading account.
This file captures only the two surfaces trader-swing uses: the **Trading API**
and the **Market Data API**. Fetch the full index when an endpoint here is
insufficient.

## Two hosts, one set of keys

The trading API and the market data API are different hosts. Both authenticate
with the same headers, `APCA-API-KEY-ID` and `APCA-API-SECRET-KEY`.

| Surface       | Host                                | Env var           | Notes                              |
|---------------|-------------------------------------|-------------------|------------------------------------|
| Trading paper | `https://paper-api.alpaca.markets`  | `ALPACA_BASE_URL` | Default in `load-secrets.sh`.      |
| Trading live  | `https://api.alpaca.markets`        | `ALPACA_BASE_URL` | Only when `LIVE_TRADING=true`.     |
| Market data   | `https://data.alpaca.markets`       | `ALPACA_DATA_URL` | Default; no paper/live split.      |

`scripts/alpaca.sh` routes trading verbs to `ALPACA_BASE_URL` and the `data`
verb to `ALPACA_DATA_URL`. Every response's `X-Request-ID` is persisted to
`logs/alpaca-request-ids.log`; Alpaca support needs that ID to trace a failed
call and it cannot be queried later.

## Tooling

Three ways to reach Alpaca, in increasing abstraction:

- **`scripts/alpaca.sh`** — thin curl wrapper. Best for routines and quick checks.
- **Alpaca CLI** (`alpaca`, installed via `go install`) — interactive account/order ops.
- **`alpaca-py` SDK** (in `requirements.txt`) — the path the official guides use;
  best for the backtest harness and any bar/feature work in Python.

## Trading API (v2, trading host)

| Verb / path                          | Purpose                                  |
|--------------------------------------|------------------------------------------|
| `GET /v2/account`                    | Equity, cash, buying power, status.       |
| `GET /v2/positions`                  | Open positions.                           |
| `GET /v2/orders?status=open`         | Working orders.                           |
| `POST /v2/orders`                    | Place an order (market/limit/stop/trailing). |
| `DELETE /v2/orders/{id}`             | Cancel an order.                          |
| `GET /v2/clock`                      | Market open/closed, next open/close.      |
| `GET /v2/calendar`                   | Trading calendar.                         |
| `GET /v2/assets`                     | Tradable asset list.                      |

Trailing-stop orders (Principle: 10% trail on winners) are placed here with
`type":"trailing_stop"` and `trail_percent`.

## Market Data API (data host)

Stocks use `v2`, crypto uses `v1beta3`. **Crypto market data needs no API keys.**

| Verb / path                                              | Purpose                |
|----------------------------------------------------------|------------------------|
| `GET /v2/stocks/bars?symbols=AAPL&timeframe=1Day`        | Historical stock bars. |
| `GET /v2/stocks/quotes/latest?symbols=AAPL`              | Latest stock quote.    |
| `GET /v1beta3/crypto/us/bars?symbols=BTC/USD&timeframe=1Day` | Historical crypto bars. |
| `GET /v1beta3/crypto/us/latest/quotes?symbols=BTC/USD`  | Latest crypto quote.   |

`timeframe` values: `1Min`, `5Min`, `15Min`, `1Hour`, `1Day`, `1Week`, `1Month`.

### Examples via the wrapper

```bash
source scripts/load-secrets.sh
scripts/alpaca.sh data '/v2/stocks/bars?symbols=AAPL&timeframe=1Day&limit=5'
scripts/alpaca.sh data '/v1beta3/crypto/us/bars?symbols=BTC/USD&timeframe=1Day&limit=5'
```

### Examples via the SDK (from the official guide)

```python
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime

client = CryptoHistoricalDataClient()  # no keys required for crypto data
req = CryptoBarsRequest(
    symbol_or_symbols=["BTC/USD"],
    timeframe=TimeFrame.Day,
    start=datetime(2022, 9, 1),
    end=datetime(2022, 9, 7),
)
client.get_crypto_bars(req).df
```

## Note on crypto venue

trader-swing executes crypto on **Binance**, not Alpaca. Alpaca crypto data is
still useful as a free, key-less reference feed for bars and quotes, and for
cross-checking Binance prices. Order execution for crypto goes through
`scripts/binance.sh`.
