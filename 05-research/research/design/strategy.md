# strategy.md — current rule set

Rewritten only by the Friday weekly-review routine. Mid-week routines read but never edit.

## Mandate

- Long-only US equities.
- Swing horizon: days to months. No intraday round trips.
- North star: outperform SPY total return over rolling three- and twelve-month windows.

## Universe

- S&P 500 constituents.
- Plus US-listed large-cap growth names (market cap ≥ $10B) with positive trailing-twelve-month operating cash flow.
- No ADRs of companies headquartered in sanctioned or capital-controlled jurisdictions.
- No biotechs pre-revenue, no SPACs, no recent IPOs (< 6 months public).

## Entry signals

A buy requires **at least two** of the following confirmed in today's `research-log.md` with citations:

1. Positive earnings surprise (reported EPS or revenue at least 3% above consensus) in the most recent quarterly print, **with raised forward guidance**.
2. Durable secular thesis confirmed in research (AI infrastructure, GLP-1, on-shoring, energy transition, defence spend, cloud migration) where the name is a clear beneficiary, not a tangential play.
3. High-level technical breakout: closing above the prior 50-day high on volume at least 1.2x the 20-day average. No candle-pattern intraday signals.
4. Analyst upgrades from at least two major sell-side firms within the past five trading days, where the upgrade explicitly cites a fundamental catalyst, not a valuation re-rating.

Negative override: skip the trade if any of these is present, regardless of how many positives fire:

- Earnings within the next five trading days.
- Recent insider selling of size by C-suite (CEO, CFO).
- Active SEC investigation or material accounting restatement.
- Stock down more than 15% in the trailing month (catching a falling knife).

## Exit signals

A sell fires on **any** of:

1. **Hard stop**: last price ≤ cost_basis × 0.93 (−7% from entry). Non-discretionary. Enforced at midday and close.
2. **Trailing stop**: last price ≤ peak_since_entry × 0.90 (10% off peak). Server-side trailing-stop order on Alpaca.
3. **Thesis break**: the catalyst that drove the buy has reversed in research — earnings miss, guide cut, regulatory action, key-person departure, fraud allegation. Document the break in `learnings.md`.
4. **Time stop**: position held 120 calendar days without making a new closing high. Cut and redeploy.
5. **Strategy violation discovered**: the position should never have been opened. Cut, journal, escalate to Friday review.

Trims are not used in this strategy. Exits are full exits.

## Position sizing

- Per new position: 5% of current equity, hard cap. Smaller is fine when conviction is moderate.
- Max 3 new positions per week (Monday open through Friday close).
- Cash floor: 10% of equity minimum. Override allowed only when at least three of the four entry signals fire on a single name; document the override in the trade-log entry.
- Max 12 concurrent positions. If the book is full, the lowest-conviction holding must be exited before a new entry.
- No averaging down. No averaging up either; size is set at entry and held.

## Risk

- Daily drawdown circuit breaker: realised + unrealised intraday P&L at or beyond −3% of starting-day equity halts all new orders for the day. Existing stops continue to operate.
- Sector concentration: no more than 30% of equity in any single GICS sector.
- Single-name concentration: enforced by the 5% sizing rule; no top-up after a winner runs.

Hard rules in `CLAUDE.md` take precedence over anything written here.

## Disallowed

- Shorting.
- Options of any kind.
- Margin and leveraged ETFs (TQQQ, SOXL, etc.).
- Inverse ETFs.
- Crypto and crypto-proxy equities (do not buy MSTR as a BTC proxy).
- Averaging down on a losing position.
- Day trading (no entry and exit on the same session unless a hard stop fires).

## Benchmarks

- Primary: SPY total return.
- Secondary tracking: QQQ and IWM for growth and small-cap tone, not as performance benchmarks.

## Open questions

<!-- The weekly-review routine resolves these or leaves them for the user. -->

## Change log

- 2026-05-11: Initial rule set seeded from the task brief defaults. Reason: agent needs rules to apply before first paper run.
