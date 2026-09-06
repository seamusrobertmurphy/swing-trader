# Standing rule for every results report

Operator instruction, 2026-08-25. Every results report in this folder opens
with the block below. It goes FIRST, above the findings, above the tables,
above anything else. No preamble before it.

The style of that block is the required style for the whole report: plain
words, one idea per line, every number followed by what it means. A reader who
has never opened this repo must be able to read it cold. Jargon, shorthand
column names and internal verdict words are not acceptable anywhere in the
report, not only in the header.

Recompute every figure at the moment of writing. Never carry a number forward
from the previous report.

---

## Where the money actually is

| | |
| --- | --- |
| Account value | $X, from a $Y start |
| Change since it went live on DATE | -Z% |
| The market, same period | -W% |
| Was this within expectations? | Yes or No, then one sentence saying why |
| Worst single holding | TICKER, down N%. What happens to it and when |
| What it costs us to trade | N basis points per trade, against the N we assumed |
| Rebalances done | N of the N we need. Note any missed |

**This is fake money.** It is a paper account. The switch that would let it
spend real money is off.

(Change that last line the moment it stops being true.)

---

## Where each figure comes from

| Row | Source |
| --- | --- |
| Account value, change | `alpaca_trade.py status` |
| The market | SPY close over the same dates, Alpaca SIP feed |
| Within expectations | modelled weekly swing = annual vol / sqrt(52) |
| Worst holding | `alpaca_trade.py check` |
| Trading cost | `alpaca_execution_report.py` |
| Rebalances | `memory/alpaca-book-state.json` |
| Fake money | `LIVE_TRADING` in the environment |
