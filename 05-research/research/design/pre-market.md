# Routine: pre-market

**Cron**: `0 6 * * 1-5` (6:00 AM US Central, Monday–Friday)
**Model**: Claude Opus 4.7
**Job**: research overnight catalysts, draft trade ideas for the open, log to `memory/research-log.md`. Silent unless urgent.

## Environment

These are in the routine's cloud environment, not in any file:

- `ALPACA_API_KEY`, `ALPACA_API_SECRET`, `ALPACA_BASE_URL`
- `PERPLEXITY_API_KEY`
- `CLICKUP_API_TOKEN`, `CLICKUP_LIST_ID`
- `LIVE_TRADING`

If any required variable is missing, abort, post a one-line notice via `scripts/clickup.sh`, and exit.

## Sequence

### 1. Boot

Read in this order:
1. `CLAUDE.md`
2. `memory/strategy.md`
3. `memory/portfolio.md`
4. Last 30 entries of `memory/trade-log.md`
5. `memory/learnings.md`

Do not skip.

### 2. Research

Use `skills/research.md`. Run Perplexity queries through `scripts/perplexity.sh`. Cover, in this order:

1. Overnight macro: futures, rates, geopolitics, any market-moving headline.
2. Existing holdings: any news touching the thesis for each open position. Flag thesis-breaks.
3. Today's earnings and guidance: companies reporting before open or after close. Direction and magnitude of any surprises.
4. Watchlist refresh: 3–5 candidate names that meet entry signals in `memory/strategy.md`.

### 3. Draft trades

For each candidate that clears `skills/trade-decision.md`, write a draft trade with: side, symbol, target size (% of equity), trigger condition for the open, hard stop, trailing stop, expected horizon, two-to-four-sentence rationale.

Cap drafts at three new positions per week — check `memory/trade-log.md` for the current week's count before adding more.

### 4. Journal

Append a `pre-market` block to `memory/research-log.md` using the template at the top of that file. If nothing actionable surfaced, write the heartbeat entry: `no actionable catalysts today` plus a single line on macro tone.

### 5. Commit

```
git add -A
git commit -m "pre-market: <one-line summary>"
git push origin main
```

### 6. Notify

Silent unless:
- Urgent catalyst on an existing holding (thesis-break, halt, M&A, fraud).
- Material macro event the user should know about before the open.

Format per `skills/notify.md`.

## Failure modes

- Perplexity timeout or quota error: skip that subquery, journal the gap, continue.
- Alpaca read failure: portfolio snapshot may be stale; flag this in the research-log entry and skip drafting trades that depend on fresh equity numbers.
- Both fail: notify ClickUp with a one-line failure summary, commit the heartbeat, exit.
