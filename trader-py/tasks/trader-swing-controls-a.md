# trader-swing — Chapter Two Task Request (expanded)
### Working title: Day Trader Governance

This document is the build spec for today's coding session. It carries the manifesto and design
parameters forward unchanged, then adds the quantitative and computational detail needed to write
code: formulae, windows, thresholds-as-parameters, and the screening function. Principles are settled.
This session turns them into math and modules.

---

## 0. Quick-review variable list (read this first)

Every tunable below is a **parameter in one config block**, never hard-coded, and the risk-bounding
ones are **operator-owned and held outside the model's reach** (marked 🔒).

**Selection screen (per-coin, computed before the model sees the coin)**
- `quote_volume_24h_usdt` — 24h quote volume, USDT. Hard gate. 🔒 floor
- `atr_pct` — ATR(14) ÷ current price, as a percent. Band, two edges. 🔒 floor and ceiling
- `spread_pct` — (ask − bid) ÷ mid, as a percent. Hard gate. 🔒 ceiling
- `candle_count` — number of daily candles returned. Sufficiency gate. 🔒 minimum
- `pass` — boolean, true only if all gates clear

**Edge and exit (per-trade economics)**
- `round_trip_fee_pct` — venue round-trip cost (Binance ≈ 0.15–0.20%)
- `expected_slippage_pct` — modelled slippage per round trip
- `edge_floor_pct` — minimum net expected move to allow a trade. 🔒
- `take_profit_pct` — target gain; must exceed `edge_floor_pct`
- `stop_loss_pct` — max loss per trade before forced exit
- `net_expected_move = est_move_pct − round_trip_fee_pct − expected_slippage_pct`

**Position and frequency limits**
- `max_trades_per_day` — hard cap. 🔒
- `max_open_positions` — concurrent positions (3–4 at current account size). 🔒
- `position_size_pct` — capital per trade; volatility-scaled (see §3)
- `hold_window_days` — range, fitted by walk-forward, not fixed (swing band)

**Signal layer (from existing day-metrics notebook)**
- `macd`, `macd_signal`, `macd_hist`, `hist_slope`, `converging`
- `cross_up`, `cross_down`, `guarded_buy`, `guarded_sell`, `epsilon` (noise band)
- `bear_div`, `bull_div` (swing-pivot divergence flags)
- four-vote score: `w_macd*MACD + w_ma*MA + w_fib*Fib + w_candle*Candle`
- `threshold` — vote score to fire (2 standard, 3 when few trades to learn from)

**Evaluation harness (frozen, versioned, operator-owned)** 🔒
- `oos_window`, `train_window`, `regime_set`, `fee_assumption` — all fixed across comparisons
- `experiment_log` — one line per walk-forward run: params, OOS after-fee result, kept/discarded

---

## 1. Manifesto (preserved verbatim)

> The minimum-edge floor is the structural answer to the volume-hiding problem you have been circling all session. A model judged on cumulative return can always make its numbers look busier by taking many small trades, and the fees quietly eat the account while the trade count looks like activity. Three defences stack against that. The trades-per-day cap limits how many trades exist. The minimum-edge floor limits how thin each one is allowed to be. And the walk-forward validation reports only out-of-sample after-fee results, so no amount of in-sample churn can flatter the verdict. Together those three make the volume trick impossible by construction: the model cannot trade often, cannot trade thin, and cannot hide the result. Your buffer-margin idea is the middle pillar of that structure, and naming it that way is what makes it load-bearing rather than decorative.

---

## 2. The four-gate selection screen (NEW — build this first)

A single screening function per coin, run across the execution venue (Binance), **not** across all
205 CCXT exchanges. Scoped to the venue you actually trade. Run weekly; save a dated table each run.

**Inputs:** daily OHLCV, last 90–180 candles, plus current order-book top.

**Gate 1 — liquidity (hard).** `quote_volume_24h_usdt` from the ticker. Reject below floor before
computing anything else.

**Gate 2 — volatility band.** ATR(14) as a percent of price.
- True range per day: `TR = max(high−low, |high−prev_close|, |low−prev_close|)`
- `ATR = 14-period moving average of TR` (Wilder's smoothing standard; SMA acceptable for v1)
- `atr_pct = ATR / current_price × 100`
- Pass if `atr_floor_pct ≤ atr_pct ≤ atr_ceiling_pct`. Both edges are parameters, fitted later.

**Gate 3 — spread (hard).** `spread_pct = (ask − bid) / mid × 100` from order book. Reject above a
tight ceiling (well under the fee).

**Gate 4 — history sufficiency.** Reject if `candle_count < min_history`. Mirrors the existing
notebook's skip-too-new logic (no Ichimoku cloud on young tokens).

**Output:** per coin → `{symbol, quote_volume_24h_usdt, atr_pct, spread_pct, candle_count, pass}`.
Collect into a dated table. Survivors = candidate universe (target 15–25 to scan, hold 3–4 at once).

---

## 3. Edge floor, exit, and position sizing (the quantitative core)

**Net edge test (entry gate).** A trade is refused unless:
`net_expected_move = est_move_pct − round_trip_fee_pct − expected_slippage_pct ≥ edge_floor_pct`
Measured on **net**, not gross. This is the fence, not an alarm — it refuses, it does not warn.

**Exit coupling.** Required ordering, enforce in code:
`edge_floor_pct < take_profit_pct` and `atr_floor_pct` large enough that a normal multi-day range
reaches `take_profit_pct` inside `hold_window_days`. `stop_loss_pct` set against the same ATR.

**Volatility-scaled position sizing (industry standard, ATR-based).** Keep dollar risk roughly
constant across coins: size each position so that `stop_loss_pct × position_value ≈ constant risk
budget`. Higher-ATR coin → smaller position; calmer coin → larger. At ~$500–1000 account, floor
position size at the venue's minimum notional, and prefer 3–4 larger positions over many tiny clips
that waste edge on fees and bump minimums.

---

## 4. Hold period — resolved as a range, not a fixed number

The earlier "1–3 days" was a gut figure. Resolution: **swing is the band** (days to ~2 weeks),
scalping and day-trading ruled out (fees and PDT rule), position-trading ruled out (underuses the
signal stack). Within the swing band, make `hold_window_days` a **walk-forward parameter** (e.g.
search 1–10 days) and let out-of-sample results pick it. Shorter holds demand higher `atr_pct`;
longer holds tolerate lower. Same dial, two ends.

---

## 5. Autoresearch lifts (from karpathy/autoresearch, adapted)

The repo's architecture maps onto this project, but its separation is enforced by **instruction**
("do not modify this file"); a model optimised against the metric needs separation enforced by
**code structure**. Lifts:
- **Narrow editable surface.** Define the one file/module the model may tune; lock everything else
  (evaluation, fee floor, ATR band, guardrails) in files the model cannot write to.
- **Experiment log.** Each walk-forward run writes one line: params tried, OOS after-fee result,
  kept or discarded, why. This is the artefact the operator reviews weekly.
- **Frozen yardstick.** Same OOS windows, fees, regime set across every comparison. Any change to
  the harness is a deliberate, separately-recorded human act, never mid-comparison.
- **program.md pattern.** The human-owned instruction layer (this document / PROJECT-BRIEF.md) is
  iterated by the operator; the model iterates the strategy. Mirrors his program.md vs train.py split.
- **Caution:** trading is adversarial and non-stationary; an OOS metric can rot live in a way his
  fixed-corpus val_bpb never does. The weekly human review is not automatable away.

---

## 6. Design parameters (carried forward, unchanged)

### Three stacked defences against volume-hiding
- **Who sets the floor.** Operator-set or fixed outside the model's reach, never tuned by the model. Reviewed weekly.
- **Defence one — trades-per-day cap.** Hard, in code. Churn becomes mechanically impossible.
- **Defence two — minimum-edge floor.** Refuses trades whose net move does not clear the floor.
- **Defence three — out-of-sample validation.** Walk-forward only; report OOS after-fee multi-regime aggregate.

### Floor is a fence, not an alarm
- Refuses the trade; optional alarm band may sit above the fence, but the fence protects the account.
- Measured on estimated move minus fee minus slippage — the honest waterline, above the raw fee.

### Two venues, two fence sets
- **Binance crypto.** Round trip ≈ 0.15–0.20% (0.075%/side with BNB). Fee is the binding fence. Keep BNB topped up.
- **Alpaca equities.** Per-trade ≈ zero (reg pass-throughs, sells only). Binding fence is the PDT rule: sub-25k cash account capped at 3 day-trades / rolling 5 days. Margin interest 6.25%/yr on leveraged overnight holds — trade cash-only. Confirm account is direct self-directed, not partner-routed (else 0%-3% commission band applies).
- Model must know which fence set governs each order.

### Strategy character
- Selective high-conviction **swing**, not scalper. Patience is the edge that survives fees.
- Both venues push toward the same patient multi-day hold, for different reasons.

### Signal discipline
- Signal-line crossover fires earlier (more false starts); zero-line fires later (more confirmed).
- Conservatism (guarded crossovers, epsilon band, confirmation bars) set once in training, not overridden live.
- Selectivity does not replace validation. Use 3-of-4 threshold when a setup has few trades to learn from.

### Operator cadence (weekly, not intra-trade)
- Model trades inside fixed fences all week; operator reviews and re-sets fences weekly.
- Intra-trade intervention is where humans do damage; weekly cadence guards against it.
- Operator time best spent reading the market broadly, not obsessing over individual trades.

---

## 7. Still open / sequencing
- **First milestone before anything else:** walk-forward must show the existing four-vote model clears fees out-of-sample across regimes, with stop and take-profit added. If it cannot beat buy-and-hold and a coin-flip on the current coins, more coins will not save it.
- Candidate universe by tradability + regime diversity; training universe must intersect executable pairs.
- Whale-detection and event-driven ideas: separate, individually-tested modules on a conventionally trained core, liquid coins only. Prove or kill each on its own evidence.
