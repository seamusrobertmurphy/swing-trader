# Skill: journal

How to write back to memory files. Used by every routine.

## Append, do not overwrite

These files are append-only:

- `memory/trade-log.md`
- `memory/research-log.md`
- `memory/learnings.md`

Never edit a prior entry. Corrections go in a new entry that references the original by date and one-line title. The historical record is the agent's accountability log.

These files are rewritten in full by exactly one routine:

- `memory/portfolio.md` — only by `routines/market-close.md`.
- `memory/strategy.md` — only by `routines/weekly-review.md`.
- `memory/weekly-review.md` — only by `routines/weekly-review.md` (overwritten weekly; history in git).

## Block templates

Each memory file ends with a `<!-- entries below this line -->` marker. Append new blocks below that line in the format shown at the top of each file. Do not introduce ad-hoc formats; the templates exist so the user can grep.

## Dating

Use `YYYY-MM-DD HH:MM CT` for time-stamped entries (trades, intra-day actions). Use `YYYY-MM-DD` only when the entry covers a whole routine (a pre-market summary, a daily close).

US Central is the operating timezone. If the runtime gives UTC, convert.

## What to journal

A non-exhaustive list, by file:

`memory/trade-log.md`:
- Every order placed, with fill outcome.
- Every order rejected, with the rejection reason.
- Every drafted trade that was skipped at the open, with the gate that failed.
- Every stop fired in midday or close.

`memory/research-log.md`:
- Pre-market block per the template.
- Heartbeat line per routine if nothing else fired ("midday: no action; book stable, +0.4% on day").
- Market-close daily summary block.

`memory/learnings.md`:
- Anything the agent or user wants the weekly-review routine to see when it considers strategy edits. Use sparingly — patterns over incidents.

## What not to journal

- Long verbatim API responses. Summarise.
- Long article text. Summarise with citation.
- Routine debugging chatter. The git log carries that signal already.

## Commit message format

Every routine ends with one commit. Message format:

```
<routine>: <one-line summary>
```

Examples:

```
pre-market: 2 ideas drafted (NVDA, COST), macro tone neutral
market-open: 1 fill NVDA $X at $Y, 1 skip COST trigger missed
midday: no action; book stable
market-close: equity $X, day +0.6%, SPY +0.4%
weekly-review: week of 2026-05-08, alpha +0.8%, grade B
```

Use existing words from the routines' notify formats for consistency.
