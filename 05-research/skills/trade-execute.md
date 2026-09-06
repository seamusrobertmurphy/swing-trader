# Skill: trade-execute

Contract for placing orders against Alpaca. Used by `routines/market-open.md` and `routines/midday.md`.

## Endpoint and auth

Base URL: `$ALPACA_BASE_URL` (defaults to `https://paper-api.alpaca.markets` in paper mode).

Headers required on every request:

```
APCA-API-KEY-ID: $ALPACA_API_KEY
APCA-API-SECRET-KEY: $ALPACA_API_SECRET
Content-Type: application/json
```

All low-level HTTP work goes through `scripts/alpaca.sh`. The skill defines what calls to make and how to handle responses, not the curl plumbing.

## Order types in use

### Entry order — buy a new position

- Side: `buy`
- Type: `limit`
- Time-in-force: `day`
- Limit price: last trade × 1.005 (50 bps over) to ensure a marketable fill while avoiding paying through a wide spread.
- Quantity: integer, from `skills/trade-decision.md` sizing math.
- `client_order_id`: deterministic, e.g. `open-YYYYMMDD-SYMBOL`, so retries are idempotent.

Poll the order:

- For up to 60 seconds at 5-second intervals.
- If `status` becomes `filled`, record fill price and break.
- If `status` is `partially_filled` after 60 seconds, cancel the remainder and treat the filled portion as the actual position.
- If `status` is still `new` or `accepted` after 60 seconds, cancel and journal "no fill at limit".

Do not re-place at a higher limit without re-running `skills/trade-decision.md`.

### Exit order — sell an existing position

- Side: `sell`
- Type: `market` for hard-stop sells (speed beats price); `limit` at last × 0.995 for discretionary exits.
- Time-in-force: `day`.
- Quantity: full position (the starter strategy treats trims as full exits — see `skills/trade-decision.md`).

Poll the same way. A hard-stop sell that does not fill in 60 seconds is an escalation event — notify ClickUp immediately and try once with a deeper marketable limit.

### Trailing stop on winners

After a fill, place a trailing-stop sell order:

- Side: `sell`
- Type: `trailing_stop`
- Time-in-force: `gtc`
- `trail_percent`: `10`
- Quantity: position size.

The midday routine may move this stop up by canceling and re-placing at a tighter trail; it never loosens.

## Idempotency and retries

Every order uses a deterministic `client_order_id`. If Alpaca returns a duplicate-id error, fetch the order by that id and treat the response as the result.

For 5xx errors: one retry after 5 seconds. Then journal the failure and notify.

For 4xx errors: do not retry. Journal the rejection reason verbatim and surface in the notification.

## State after fill

For every fill:

1. Append the BUY or SELL block to `memory/trade-log.md` (template at top of that file).
2. For BUYs, set the trailing stop and record the stop order id in the trade-log entry.
3. The next market-close routine reconciles `memory/portfolio.md` against Alpaca; intra-day routines do light touch-ups only.

## What this skill does not do

- It does not decide whether to trade. That is `skills/trade-decision.md`.
- It does not format the ClickUp post. That is `skills/notify.md`.
- It does not handle hard-stop logic. The agent monitors hard stops in the midday and close routines; trailing stops are server-side.
