# trader-swing — Chapter Two Manifesto and Design Parameters

## Manifesto (preserved verbatim)

> The minimum-edge floor is the structural answer to the volume-hiding problem you have been circling all session. A model judged on cumulative return can always make its numbers look busier by taking many small trades, and the fees quietly eat the account while the trade count looks like activity. Three defences stack against that. The trades-per-day cap limits how many trades exist. The minimum-edge floor limits how thin each one is allowed to be. And the walk-forward validation reports only out-of-sample after-fee results, so no amount of in-sample churn can flatter the verdict. Together those three make the volume trick impossible by construction: the model cannot trade often, cannot trade thin, and cannot hide the result. Your buffer-margin idea is the middle pillar of that structure, and naming it that way is what makes it load-bearing rather than decorative.

---

## Design parameters (build-out)

### The three stacked defences against volume-hiding

- **Who sets the floor.** The minimum-edge floor is set by the operator or fixed outside the model's reach, never tuned by the model itself. The model is judged on the results the floor produces, so a model that could lower the floor would lower it to book more wins. The floor is reviewed weekly by the operator, not learned.
- **Defence one — trades-per-day cap.** A hard limit on how many trades can exist in a day, set in code. This alone makes the volume trick mechanically impossible: the model cannot churn because it cannot place the orders.
- **Defence two — minimum-edge floor.** A trade is refused unless its expected net move clears the floor. Net means after round-trip fee and after expected slippage, not gross. On Binance crypto the round trip is roughly 0.2 percent, so the floor sits well above that, in the region of one and a half to two percent expected move.
- **Defence three — out-of-sample validation.** Walk-forward only. Tune weights and threshold on a training segment, score once on an untouched test segment, move forward, repeat. Report only the out-of-sample, after-fee, multi-regime aggregate. No in-sample result is ever the verdict.

### The floor is a fence, not an alarm

- The floor **refuses** the trade. It is not a flag the model can ring and then trade anyway. An alarm that lets the trade through does not stop the loss.
- Keep an optional **alarm band** just above the fence as an early warning, but the fence below it is what protects the account.
- The floor is measured on **estimated move minus round-trip fee minus expected slippage**. That is the honest waterline, and it is higher than the raw fee.

### How the floor relates to the exit

- The take-profit target must sit **above** the floor. A take-profit below the floor is incoherent: aiming to exit at a gain the entry rule calls too thin to take.
- Floor and take-profit are **set together**, not independently.
- Set too low, the floor lets churn through. Set too high, the model sits on its hands and never trades, which can look like success right up until you notice no trades cleared in a month. The floor is a tuned parameter, reviewed weekly.

### Two venues, two fence sets

- **Binance crypto.** Round-trip cost roughly 0.15 to 0.2 percent (0.075 percent per side paying fees in BNB, 0.1 percent otherwise). Fee is the binding fence. Keep a BNB balance topped up for the discount.
- **Alpaca equities.** Per-trade cost effectively zero (regulatory pass-throughs on sells only, cents per trade). The binding fence is the pattern-day-trader rule: a sub-25k cash account is capped at three day-trades per rolling five days. Margin interest at 6.25 percent annualized applies to any leveraged overnight hold — trade cash-only to avoid it. Confirm the account is direct self-directed, not partner-routed, or the zero-commission assumption breaks.
- The model must know **which fence set governs the order it is about to place.**

### Strategy character

- Selective, high-conviction **swing** strategy, not a scalper. Patience is the edge that survives fees.
- Waiting twenty-four or forty-eight hours for a clearly attractive setup is the correct economic response to the fee structure, not idleness.
- Both venues, for different reasons (fee on crypto, day-trade cap on equities), push toward the same patient multi-day hold. Constraints and instinct point the same way.

### Signal discipline

- The MACD signal-line crossover fires earlier, offers a longer runway, and produces more false starts. The zero-line crossover fires later and confirms more.
- Conservatism (guarded crossovers, epsilon noise band, confirmation bars) is set **once** in training and **not overridden live**. The danger is the operator reaching in to take the early signal the model correctly skipped.
- Selectivity does not replace validation. Rare high-conviction signals still have to be proven to predict the move they claim. Use the stricter three-of-four threshold when a setup has fewer trades to learn from.

### Operator cadence (weekly, not intra-trade)

- The model trades inside fixed fences all week. The operator reviews and re-sets the fences weekly.
- Weekly review is where a human belongs: adjusting fences, reading whether the regime changed, deciding whether to widen or tighten, and re-running out-of-sample validation.
- Intra-trade intervention is where humans do damage. The weekly cadence is itself a guardrail against operator interference.
- Operator time is best spent reading broadly and exploring the market — learning new areas, finding where the clear opportunities are — not obsessing over individual trades, margins, and graphs.

### Volatility filter — ATR band (NOT YET BUILT; missing from day-metrics.ipynb)

- **Metric:** ATR (average true range), 14-period, read as a **percentage of current price** so coins are comparable. Daily ATR for a 1-3 day hold. Measures typical daily movement *now*, not over the coin's lifespan.
- **It is a band, two edges, both fitted by walk-forward, both held outside the model's reach:**
  - **Floor** — a coin must move enough per day to reach the take-profit inside the hold window. Floor sits *above* the net edge requirement (above ~2-3% daily ATR if the edge floor is ~2%).
  - **Ceiling** — above some ATR the coin gaps through stop and take-profit unpredictably and indicators lose meaning. Ceiling sits *below* where the coin detonates (often the high-ATR meme/micro names).
- **Two jobs, do not conflate them:**
  1. **Selection filter** — the gate that admits or rejects a coin from the universe *before the model sees it*.
  2. **Live guardrail** — keeps the model from trading a coin that has drifted out of the tradable band.
- At the current ~$500-1000 account size the ceiling can be relaxed: orders are too small to move the book, so high-ATR coins become tradable that would not be at $25k+. Re-tighten as the account grows. Make floor and ceiling **parameters, not constants.**
- Couples directly with the edge floor and take-profit: edge floor < take-profit, and ATR floor must exceed the move needed to reach take-profit. One system.

### Still open

- Candidate coin universe: select by **tradability** (liquidity, spread, slippage) and **regime diversity** (bull, bear, sideways, calm, panic in the training window), not by raw count or one day's top volume.
- Training universe must intersect with what each venue can actually execute.
- Whale-detection and event-driven (news/social) ideas: build as **separate, individually tested modules** on top of a conventionally trained core, on liquid coins only. Prove or kill each on its own evidence.
- First milestone before any of the above: walk-forward must show the existing four-vote model clears fees out-of-sample across regimes, with a stop and take-profit added. If it cannot beat buy-and-hold and a coin-flip on the current coins, more coins will not save it.
