# Routine: midday

**Cron**: `0 12 * * 1-5` (12:00 PM US Central, Monday–Friday)
**Model**: Claude Opus 4.7
**Job**: cut losing positions trading below the −7% hard-stop line, tighten trailing stops on winners. Notify only if action is taken.

## Environment

Same as market-open. Abort cleanly if anything required is missing.

## Sequence

### 1. Boot

`CLAUDE.md`, `memory/strategy.md`, `memory/portfolio.md`, last 30 of `memory/trade-log.md`, `memory/learnings.md`. Also re-read today's `memory/research-log.md` entry to remember the morning's theses.

### 2. Refresh positions

Pull live positions and last prices from Alpaca via `scripts/alpaca.sh`. Compute, for each holding:

- Current unrealised P&L vs cost basis.
- Distance from cost basis (% above or below).
- Distance from peak since entry (track peak in `memory/portfolio.md` Notes if not natively available).

### 3. Apply hard stop

For each holding trading at or below −7% from cost basis:

1. Confirm there is no pending order on the symbol.
2. Place a market sell for the full position via `skills/trade-execute.md`.
3. Append a SELL entry to `memory/trade-log.md` referencing the original BUY entry.

Hard stop is non-discretionary at midday. Do not second-guess.

### 4. Tighten trailing stops on winners

For each holding up materially since entry (rule of thumb: ≥ +8%), confirm the 10% trailing stop is in place at the current price level. If a tighter discretionary stop is appropriate (thesis nearly played out, parabolic move), the agent may move the trailing stop up — journal the reason.

Never loosen a stop. Never re-buy a position cut earlier in the same day.

### 5. Daily loss cap check

Recompute realised + unrealised intraday P&L as a percentage of starting-day equity. If beyond −3%, halt new orders for the day (record this state in `memory/portfolio.md` Notes) and notify ClickUp. The market-close routine respects this halt.

### 6. Journal

Append entries for every action taken: stop fires, stop adjustments, halts. If no action was needed, write a single line: `YYYY-MM-DD midday: no action; <one-line tone of book>` to `memory/research-log.md` so there is a heartbeat.

### 7. Commit

```
git add -A
git commit -m "midday: <stops fired | stops tightened | no action>"
git push origin main
```

### 8. Notify

Notify ClickUp if and only if:
- A stop fired (any position cut).
- The daily loss cap halted further orders.
- A material discretionary stop change was made.

Otherwise silent.

## Failure modes

- Stale price feed: defer the action; do not cut on a single tick. Pull a fresh quote.
- Order rejection on a sell: try once more with a marketable limit. If still rejected, escalate to ClickUp immediately — a stuck losing position is a hard-rule concern.
