# Skill: notify

ClickUp post format. Used by every routine that surfaces output to the user.

## Tool

`scripts/clickup.sh` reads `CLICKUP_API_TOKEN` and `CLICKUP_LIST_ID` from the environment and creates a task in the configured list. The task title and body define the notification.

Invocation:

```
scripts/clickup.sh "Title" "Body markdown"
```

The body supports markdown. Keep it tight — these are run summaries, not essays.

## Notification rules (by routine)

| Routine        | When to post                                                    |
|----------------|-----------------------------------------------------------------|
| pre-market     | Silent unless urgent catalyst or thesis-break on existing pos.  |
| market-open    | Only if at least one trade is placed.                           |
| midday         | Only if a stop fires, a position is cut, or loss-cap halts day. |
| market-close   | Always.                                                         |
| weekly-review  | Always.                                                         |

## Title format

Stable, scannable, prefixed by routine name:

```
[pre-market] 2026-05-12 — urgent: NVDA halted overnight
[market-open] 2026-05-12 — 1 fill, 1 skip
[midday] 2026-05-12 — stop fired ABC −7%
[market-close] 2026-05-12 — equity $103,400 (+0.6%), SPY +0.4%
[weekly-review] week of 2026-05-08 — alpha +0.8%, grade B
```

Date is the trading day (US Central).

## Body templates

### Pre-market (urgent only)

```
**What**: <one line, e.g., "NVDA halted overnight on M&A speculation">
**Source**: <Perplexity citation>
**Existing exposure**: <position size and basis, if applicable>
**Proposed action at the open**: <trim | cut | hold + monitor>
```

### Market-open (when a trade is placed)

```
**Trades placed**

- BUY NVDA: 12 sh @ $876.40 (notional $10,517, ~5% equity). Hard stop $815, trailing 10%.
  Thesis: <one line>

**Drafted but skipped**

- COST: trigger missed at the open.
```

### Midday (when action fires)

```
**Actions**

- SELL ABC: 80 sh @ $42.10 — hard stop, position −7.2% from cost. Realised $X.
- Trailing stop tightened on NVDA from 10% to 8%, position +12%.

**Day state**: equity $X, P&L −1.4%. Loss cap not yet hit.
```

### Market-close (always)

```
**Equity**: $103,400 (+0.6% day, +3.4% since inception)
**SPY**: +0.4% day, +2.1% since inception
**Alpha (inception)**: +1.3%

**Trades today**
- BUY NVDA 12 sh @ $876.40
- SELL ABC 80 sh @ $42.10 (hard stop, −7.2%)

**Stops moved**
- NVDA: 10% → 8% trailing

**Flags**
- None.
```

### Weekly-review (always, long-form)

```
**Week of 2026-05-08**

**Performance**
- Starting equity: $X
- Ending equity: $X
- Week P&L: $X (Y%)
- SPY same period: Z%
- Alpha: A%

**Trades this week**
- 2026-05-08 BUY NVDA …
- 2026-05-10 SELL ABC …

**What worked**
- …

**What didn't**
- …

**Self-grade**: B
One line: <why>.

**Proposed strategy changes**
- <diff against strategy.md, if any. Otherwise "No changes proposed.">

**Open questions for the user**
- <if any>
```

## Length guidance

- Daily notifications: under 200 words in the body.
- Weekly review: under 600 words.

If the routine wants to say more, link to the commit hash in the body and let git carry the detail.

## Failure modes

- ClickUp API error: retry once after 5 seconds. If still failing, write the same payload to `memory/research-log.md` under a `## YYYY-MM-DD notify-failure` block so the user sees it on the next read, and commit anyway.
