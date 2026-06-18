# Task addendum: quant principles layered onto the original brief

This file extends `TASK_trading-routine-setup-task.md`. The original brief stands. Where this addendum and the original disagree, this addendum governs. The agent identity in `CLAUDE.md` carries the operative version of everything below.

## Why this exists

The original brief specified a working agent and a routine schedule. It did not specify how to size positions inside the 5% cap, how to respond to drawdowns short of the 3% daily circuit, how to read or ignore daily news, how to bound correlation across positions, or how to handle the rare dislocation that justifies stretching the rules. Those gaps got filled by the synthesis in `research/synthesis-quant-methods.md`, which distils the Thorp, Derman-Taleb, and supporting canon (see `research/authoritative-references.md`) into twelve operating principles. This task records the principles, what they touch, and what work remains for the routine agent to absorb them.

## What changes in CLAUDE.md

Sections added or refined:

1. A **Principles** section between the identity preamble and the hard rules. Twelve numbered principles, each a short paragraph, in the order set by the synthesis document. The principles are read by every routine on boot and govern everything not covered by an explicit hard rule.
2. **Hard rules refined**:
   - Position sizing: the 5% notional cap remains the ceiling. Default size is half-Kelly inside the cap, computed from the entry write-up's explicit win-probability and reward-to-risk estimates. Kelly inputs go in the trade-log entry so the weekly review can grade them.
   - Drawdown response: the binary 3% daily circuit remains. Layered on top, a rolling weekly drawdown ramp begins shrinking new-position size below −5% on the rolling 5-day P&L and reduces 1:1 with each further 1% of drawdown. Recovery reverses the ramp.
   - Gap-risk sizing: new positions are sized so that a 15% adverse overnight gap on any one name does not by itself trip the 3% daily circuit.
   - Anchoring prohibition: hold/sell logic does not reference cost basis. Cost basis is used only to compute the 7% hard stop, P&L for the journal, and (when live) tax accounting.
   - Correlation budget: aggregate weight of any cluster of holdings with pairwise 60-day correlation above 0.7 is capped at 20% of equity. This sits alongside the existing 30% GICS-sector cap.
   - VIX noise filter: SPY-level moves smaller than VIX / √252 are not thesis-relevant. Single-name moves are evaluated against the name's own implied volatility where available, otherwise an assumed 1.5× SPY beta.
   - Fat-pitch regime: one position may be stretched to 10% of equity in a documented dislocation. Entry requires asymmetric R:R ≥ 3:1, a named structural cause, and a written exit condition, all in the trade-log entry. Without all three, the cap stays at 5%.

## What changes in the routines

No routine prompt file is rewritten by this addendum. Each routine will absorb the principles by reading `CLAUDE.md` on boot. The Friday weekly review is the only routine that may edit `memory/strategy.md`. The first Friday review after this addendum lands will be responsible for translating the principles into the operational rule text in `strategy.md`. The proposed translation is sketched below for that review to either adopt, refine, or reject.

### Proposed strategy.md edits, for the weekly review to consider

- **Sizing** section: replace the flat 5%-on-entry rule with "size at half-Kelly inside a 5% notional cap; record Kelly inputs (p, b) in the entry log; quarter-Kelly when only the minimum count of entry signals fire."
- **Risk** section: add the drawdown ramp, the gap-risk sizing rule, the correlation cluster cap, and the VIX noise filter.
- **Entry signals** section: add the requirement that every entry log contain a one-paragraph affirmative case and a one-paragraph devil's advocate that the agent attempted and failed to make stick.
- **Exit signals** section: add an explicit anchoring-prohibition reminder above the existing list.
- **New section: Fat-pitch regime**: codify the 10%-cap exception with its three required conditions.
- **New section: Circle of competence**: maintain a named whitelist of sectors and themes. Outside-the-list names go in `learnings.md`, not the book. The list expands only after one full earnings cycle of watching but not trading an outside-the-list name.
- **Benchmarks** section: add the requirement to compute geometric and arithmetic mean returns separately and to report variance drag σ²/2.
- **New section: Factor monitoring**: each Friday, compute coarse value, momentum, quality, and size tilts for the book against SPY. Flag absolute tilts above 0.3 and resolve them in the next two weeks of new entries.

The weekly-review routine is free to depart from this sketch where the operational reality of the past week's data argues for a different translation. The principles in CLAUDE.md are the constraint; the strategy.md wording is the routine's craft.

## What changes in the skills

`skills/trade-decision.md`, when next touched by the working agent (not the routine agent), will get a section on Kelly-sizing arithmetic with worked examples at p = 0.55 and b = 1.5, half-Kelly and quarter-Kelly, against a portfolio of US$100,000 paper equity. Until then the routines compute Kelly inline using the formula in CLAUDE.md.

`skills/journal.md` will get a template addendum for the entry log specifying the required fields: affirmative case, devil's advocate attempt, Kelly inputs (p, b, f), correlation cluster the new name joins, factor exposures it adds, and the planned exit. The midday and close routines append to the same entry as the position evolves.

## What does not change

- The Alpaca contract, the Perplexity research wrapper, the ClickUp notification format.
- The five-routine cadence and its cron table.
- The seven environment variables and their exact spellings.
- The paper-only mandate until `LIVE_TRADING=true`.
- The hard prohibitions: shorts, options, margin, leveraged ETFs, inverse ETFs, crypto, averaging down.

## Acceptance for this addendum

This addendum is accepted when:

1. `CLAUDE.md` carries the Principles section and the refined hard rules described above.
2. `research/synthesis-quant-methods.md` and `research/authoritative-references.md` exist and are linked from `INDEX.md`.
3. The next Friday weekly-review run produces a `strategy.md` rewrite that visibly references at least the Kelly-sizing rule, the drawdown ramp, the anchoring prohibition, the correlation budget, and the fat-pitch regime, with reasoned departures from the sketch above where the routine judges they apply.
4. `memory/learnings.md` carries an entry, posted by the next available routine, acknowledging that the principles are live and any open questions that arose from reading them.

## Open questions the addendum leaves to the routine

- Whether the Kelly inputs are estimated nominally (the agent's own subjective p, b) or empirically (rolling realised win rate and reward-to-risk). The synthesis assumes nominal until enough trade history exists to compute empirical; the routine decides the crossover.
- Whether the correlation matrix is computed weekly in the Friday review or daily in the close routine. Weekly is cheaper and probably sufficient.
- Whether factor tilts are computed via off-the-shelf style classifications (e.g., GICS quality dummies, P/B value buckets) or against a coarse internal scoring rubric. The latter is more honest; the former is faster.

None of these block the principles from going live. They are the next layer of refinement, to be raised in the first weekly review.
