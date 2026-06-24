# Task Request: Cross-Sectional Relative-Strength Edge (4h)

**Status:** open, iterative. Append to the Iteration Log at the bottom each session; keep the
Backlog ordered and check items off as they land. Started 2026-06-24.

**Scope:** Turn the first stable signal this project has found — cross-sectional relative strength
on the 4h frame — into a deployable, honestly-backtested long-only strategy, or prove it cannot
clear the fee line. No shorting, no leverage, spot only (the brief is non-negotiable).

---

## The finding that opened this (2026-06-24)

Cross-sectional ranking was fixed and, more importantly, it found something. The bug was a 20-coin
threshold and deciles against a universe that only carries ~5-7 coins per bar after the point-in-time
liquidity screen — so every signal returned "no usable cross-section." Now it ranks into **terciles**
at a 5-coin floor.

The result (`inputs/cross_sectional_4h.py`, 4h frame, final-year OOS, after 0.20% round-trip fee),
read as two separate questions:

1. **Relative strength is REAL and broad.** 25 of 42 momentum/trend signals show a positive AND
   train/test sign-stable top-third-minus-bottom-third spread; 33 of 42 have the top third beating
   the market average. Most robust by worst-case spread: `f_mst_dir` (adaptive-Supertrend direction)
   +0.111pp train / +0.139pp test; also `f_btc_corr_168` (+0.191/+0.109), `f_d1_st_up`
   (+0.131/+0.019). The strongest coins reliably beat the weakest.
2. **Not long-only-GO yet.** The universe's after-fee baseline is **-0.382%/trade** (the +2/-1 ATR
   label has negative unconditional expectancy and the fee compounds it), so the best top third
   (`f_d1_st_up`, -0.143%) beats the market but stays negative in absolute terms. The edge is real
   but **drowned by the negative baseline**, not absent.

This is categorically different from the time-series entry work (`entry_sharpening/earliness/
walkforward_4h.py`), which found no stable signal at all. Here there is stable structure to build on.

**The whole game now:** lift the absolute level of the top-third cohort above zero after fees,
long-only. Three levers, stackable: (a) a market-regime gate (deploy only when the market baseline
is not deeply negative / BTC trending up); (b) a less fee-punishing label/exit (longer horizon,
fewer round trips); (c) a longer-horizon (daily) frame.

---

## Backlog (ordered; edge comes from lifting the baseline, not re-ranking)

- [ ] **1. Market-regime gate.** `inputs/cross_sectional_regime_4h.py` — rank the top third only on
  bars where BTC is trending up (`f_btc_mom_168 > 0`), cash otherwise. Does the BTC-up top third
  clear zero after fees, OOS, train/test stable? Report per regime + gate-open share. (RUNNING / first
  result in the Iteration Log.)
- [ ] **2. Less fee-punishing label/exit.** Re-score the top-third cohort under a longer-horizon /
  wider-target label (e.g. +3/-1.5 ATR over 96-192 bars) and the per-coin trailing exit from
  `exit_geometry_1h.py`, so fewer round trips per unit of trend captured. Fewer trades, less fee drag.
- [ ] **3. Daily frame.** Build/score the same tercile ranking on a 1-day frame (per
  `tasks/multi-resolution-build-plan.md`). Trend/factor structure persists at lower frequency and the
  fee-per-unit-return drops sharply. Cross-sectional momentum is classically a daily/weekly effect.
- [ ] **4. Stricter / composite gate.** If (1) helps but does not clear zero, stack gates: BTC-up
  AND market breadth (share of universe in uptrend) AND/or KER efficient-trend regime (`f_mst_ker`).
- [ ] **5. Non-overlapping top-K portfolio backtest.** Once a cohort clears zero per-trade, build the
  actual tradeable portfolio: top-K coins, rebalanced on a non-overlapping schedule, equal-weight,
  cash when the gate is closed, the 5%/Kelly sizing and 10% cash floor from Chapter 2. Score total
  return / max drawdown / Sharpe vs buy-and-hold and BTC, after fees.
- [ ] **6. Per-fold walk-forward stability.** Run the winning portfolio through `wf_splitter.py` /
  half-year folds (the test that killed the early-entry idea). Only a cohort positive across most
  folds and both BTC regimes graduates.
- [ ] **7. Monte Carlo robustness.** `monte_carlo_1h.py` bootstrap + reorder + sign-flip null on the
  portfolio's per-trade returns. ROBUST requires P5 > 0, p(loss) < 5%, p-value < 0.05.
- [ ] **8. Reconcile to live + notebooks.** If it survives, wire the ranking + gate into the
  execution path and document in the notebooks (ch3 selection/training, ch2 controls); reconcile the
  exit config back into the live bot's stop/trail and CLAUDE.md's provisional -7%/10%.

## Guardrails

- After-fee, OOS, honest GO/NO-GO every step. Do NOT torture the OOS year to force a GO; the
  walk-forward + Monte Carlo gates exist to catch a lucky single window.
- The point-in-time universe is thin (~5-7 coins/bar); terciles, not deciles. Liquidity screen stays
  (we can only trade liquid coins) — the thinness is real, not a bug.
- No live trading (LIVE_TRADING off), spot only. Seamus owns CLAUDE.md/INDEX.md (append only).
- Memory: [[cross-sectional-relative-strength-real-but-drowned]], [[multi-timeline-4h-beats-1h-still-nogo]],
  [[entry-sharpening-4h-no-durable-edge]].

---

## Iteration Log

### 2026-06-24 — opening + task 1 launched
- Cross-sectional tercile fix landed (`cross_sectional_4h.py`); finding above.
- Task 1 (regime gate) built as `cross_sectional_regime_4h.py` and run.

### 2026-06-24 — task 1 result: regime gate is PARTIAL (does not clear zero)
Gate = `f_btc_mom_168 > 0` (BTC trending up), open 47% of bars. Best signal `f_d1_st_up`:
- TEST BTC-up top third **-0.117%/trade** vs that regime's market -0.317% (beats by +0.20pp) and vs
  the ungated all-regime baseline -0.382%; TEST BTC-down top third -0.165% (regime market -0.438%);
  TRAIN BTC-up -0.274% (same sign, top beats market in both regimes — directionally consistent).
- The gate does two real things: the top third beats the market in every regime, and gating lifts
  the top third from -0.143% (ungated) to -0.117% (BTC-up). But it does NOT clear zero.
- **Diagnosis:** even in the BTC-up regime the average alt trade loses -0.317% after fees. The
  binding constraint is the FEE + LABEL baseline, not the regime — a market that loses 0.32%/trade
  when the +2/-1 ATR barrier round-trips every ~2 days at 20bps cannot be gated into profit.
- **Therefore the next lever is the baseline, not the ranking.** Promote tasks 2 (longer-horizon /
  wider-target label + per-coin trailing exit = fewer round trips, less fee drag) and 3 (daily frame =
  lower fee-per-unit-return) ahead of stricter gating. Keep the BTC-up gate as a stackable filter once
  the baseline is less negative.
