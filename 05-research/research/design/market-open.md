# Routine: market-open

**Cron**: `30 8 * * 1-5` (8:30 AM US Central, Monday–Friday)
**Model**: Claude Opus 4.7
**Job**: execute the trades drafted at pre-market, set stops, append to `memory/trade-log.md`. Notify only if a trade fires.

## Environment

These are in the routine's cloud environment, not in any file:

- `ALPACA_API_KEY`, `ALPACA_API_SECRET`, `ALPACA_BASE_URL`
- `PERPLEXITY_API_KEY` (rarely needed here, but loaded for ad hoc lookups)
- `CLICKUP_API_TOKEN`, `CLICKUP_LIST_ID`
- `LIVE_TRADING`

Abort if any required variable is missing. Notify ClickUp.

## Sequence

### 1. Boot

Same as pre-market: `CLAUDE.md`, `memory/strategy.md`, `memory/portfolio.md`, last 30 of `memory/trade-log.md`, `memory/learnings.md`. Also read **today's** `memory/research-log.md` entry — the drafted trades live there.

### 2. Pre-flight checks

- Confirm market is open via Alpaca clock endpoint. If closed (early close, holiday, halt), journal the skip and exit clean.
- Confirm `LIVE_TRADING` value. If unset or not exactly the string `true`, treat as paper. Use `ALPACA_BASE_URL` as-is.
- Confirm portfolio equity from Alpaca matches `memory/portfolio.md` last-known equity to within reasonable drift. If wildly off, halt new orders and notify.
- Confirm daily loss cap not already breached.

### 3. Execute drafts

For each drafted trade in today's research-log entry:

1. Re-check the trigger. If the trigger condition is not met at the open, skip and journal "trigger missed".
2. Re-check position-sizing math via `skills/trade-decision.md`. If the trade would push past 5% per position, 3 new positions per week, or below the 10% cash floor, skip and journal the reason.
3. Place the order via `scripts/alpaca.sh` per `skills/trade-execute.md` — market or marketable-limit, IOC unless otherwise specified.
4. Poll the order until filled, partially filled, or canceled. Record fill price.
5. Set the 10% trailing stop server-side. The −7% hard stop is enforced by the agent at midday and close; document it in the trade-log entry but do not place a hard stop order (the brief uses agent-managed stops, not bracket orders, so the agent can adjust on thesis).

### 4. Journal

Append one block per filled trade to `memory/trade-log.md` per the template at the top of that file. If a draft was skipped, journal it with the reason in the same dated section.

### 5. Update portfolio snapshot

Light update only — refresh the open-positions table in `memory/portfolio.md` with the new fills. Full mark-to-market is a market-close job.

### 6. Commit

```
git add -A
git commit -m "market-open: <N trades placed | no fills | skipped — reason>"
git push origin main
```

### 7. Notify

Notify ClickUp only if at least one trade was placed. Format per `skills/notify.md` — symbol, side, size, fill price, stop levels, one-line rationale.

## Failure modes

- Alpaca order rejected: journal the rejection reason; do not retry blindly. If the rejection is a sizing or pattern violation, surface it in the notification.
- Partial fill: record the actual fill. Do not chase the unfilled balance unless the original trigger still holds and a fresh order is justified by `skills/trade-decision.md`.
- Halted symbol: skip and journal.
