# Routine: market-close

**Cron**: `0 15 * * 1-5` (3:00 PM US Central, Monday–Friday)
**Model**: Claude Opus 4.7
**Job**: mark to market, fully refresh `memory/portfolio.md`, write a daily journal entry, post EOD summary to ClickUp. Always notifies.

## Environment

Same as market-open. Abort cleanly if anything required is missing.

## Sequence

### 1. Boot

`CLAUDE.md`, `memory/strategy.md`, `memory/portfolio.md`, last 30 of `memory/trade-log.md`, `memory/learnings.md`. Also re-read today's `memory/research-log.md` entry for context.

### 2. Pull authoritative state from Alpaca

- Account equity, cash, buying power.
- All open positions with qty, average cost, last price, unrealised P&L.
- All orders placed today, with status.
- Today's realised P&L from filled exits.

### 3. Fetch SPY for benchmark

Pull SPY today's return and inception-to-date return through `scripts/alpaca.sh` market-data endpoint. The agent tracks inception-to-date alpha vs SPY.

### 4. Rewrite portfolio.md

Replace `memory/portfolio.md` in full using the template at the top of that file. Include:

- Timestamp.
- Total equity, cash, buying power, day P&L, inception P&L.
- SPY inception-to-date for comparison.
- Open positions table with the columns listed in the template, peaks updated.
- Pending orders (carryover stops or unfilled entries).
- A short Notes block: anything carrying overnight (planned exits, conviction notes, halted-by-loss-cap state if applicable).

This is the only routine that may rewrite `portfolio.md` in full.

### 5. Journal

Append a daily summary block to `memory/research-log.md` under a `## YYYY-MM-DD market-close` heading:

- Trades filled today (by symbol).
- Stops fired or moved.
- Day P&L vs SPY day.
- One-line tone: what kind of day it was for the book.

### 6. Commit

```
git add -A
git commit -m "market-close: equity $X, day P&L Y%, SPY Z%"
git push origin main
```

### 7. Notify — always

Post EOD summary to ClickUp via `scripts/clickup.sh`, format per `skills/notify.md`:

- Equity, cash, day P&L (% and $), inception P&L.
- SPY day and inception for the same period.
- Trades filled today (brief).
- Stops fired (brief).
- Any flags: loss-cap halt, thesis-break flagged on a holding, anything that needs the user's eyes.

## Failure modes

- Alpaca read failure: do not rewrite `portfolio.md` from incomplete data. Journal the failure in `research-log.md`, leave `portfolio.md` untouched, and notify ClickUp that EOD state is stale.
- Partial data (e.g., positions but no equity): same — flag and stop.
