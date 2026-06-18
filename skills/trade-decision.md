# Skill: trade-decision

The buy/sell/hold checklist. Every trade must pass this gate before reaching `skills/trade-execute.md`.

`memory/strategy.md` is the source of truth for entry and exit criteria. This skill is the **procedure** for applying them.

## Buy checklist

A new buy fires only when **all** of the following are true:

1. **Universe**: the symbol sits in the universe defined by `memory/strategy.md`.
2. **Entry signal**: at least one entry signal listed in `memory/strategy.md` is present and documented in today's `memory/research-log.md` with a citation.
3. **Thesis**: a written thesis exists in the research-log draft for this symbol, in two to four sentences, naming the catalyst and the expected horizon.
4. **No conflict**: the symbol is not already a position. No averaging up on an existing position is permitted in the starter strategy.
5. **Sizing fits**:
   - Position size at entry ≤ 5% of current portfolio equity.
   - New-positions-this-week count is < 3 (count from `memory/trade-log.md` Monday onward).
   - Resulting cash after the buy ≥ 10% of equity, unless the research entry documents an "exceptional conviction" override.
6. **Risk room**: no daily-loss-cap halt is in effect for today.
7. **`LIVE_TRADING`**: confirmed value (paper or live) and the corresponding `ALPACA_BASE_URL`.

If any check fails, do not place the trade. Journal the reason — "trade-decision gate failed: <which check>" — in `memory/trade-log.md` under today's date.

## Position sizing math

Notional dollars to deploy:

```
notional = floor( min(target_pct, 0.05) * current_equity )
```

where `target_pct` comes from the research-log draft (typically 0.03 to 0.05) and `current_equity` from a fresh Alpaca account read.

Quantity:

```
qty = floor( notional / last_price )
```

If `qty < 1`, do not place the order. Journal "too small to size" and move on. Fractional shares are not enabled in the starter strategy.

## Sell checklist

A sell fires when **any** of the following is true:

1. **Hard stop**: last price ≤ cost_basis × 0.93 (i.e. −7% or worse). Non-discretionary at midday and close.
2. **Trailing stop**: last price ≤ peak_since_entry × 0.90 (i.e. 10% off peak), where peak is tracked in `memory/portfolio.md` Notes.
3. **Thesis break**: the catalyst that drove the buy has reversed, demonstrably, in research. Document in `memory/learnings.md`.
4. **Strategy violation discovered**: the position never should have been opened (e.g. universe slipped in error). Cut, journal, escalate to weekly review.

Trim (partial sell) is a discretionary action only when a winner has run to a target documented in the buy entry. The starter strategy treats trims as full exits if the thesis is exhausted; if conviction remains, hold.

## Hold

The default. Hold beats trade in noise. If neither a buy nor a sell condition is met, do nothing and journal nothing — silence at the position level is fine; routine-level heartbeat journaling is handled elsewhere.

## Edge cases

- **Halted symbol**: skip. Wait for next routine.
- **Gap up on a draft**: if the open price is materially above the trigger (e.g., >3% above), re-evaluate. Do not chase. Often the entry no longer satisfies the entry signal at the new price.
- **Earnings the day of a planned buy**: do not initiate a position right before that name reports. Wait one trading day past the print.
- **Stale `memory/portfolio.md`**: if a fresh Alpaca read disagrees materially with the file, trust Alpaca, log the discrepancy in `memory/learnings.md`, and only the market-close routine rewrites `portfolio.md`.
