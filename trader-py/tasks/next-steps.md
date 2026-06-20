# Task request: exits, walk-forward validation, and feature upgrades

Chapter Three. 2026-06-20. Hand this to a fresh session and say "start at Priority 0."

## Where we are

Chapter 1 (`day-metrics.ipynb`): a buy-signal model on ten coins, 2017 to 2026, about 27,699 labelled days. Label is "price gains 10 percent before it falls 5 percent within 20 days." Standing result is NO-GO: out-of-sample buy-precision about 0.32 against a 0.30 base rate, AUC about 0.51. No demonstrated edge after fees.

Chapter 2 (`day-controls.ipynb`): built and run live. It has the weekly four-gate screen (liquidity, ATR band, spread, history), ATR-scaled position sizing, the net-edge fee fence, a frozen evaluation harness with an experiment-log scaffold, and a signal journal that saves a per-coin study sheet to `outputs/journal/`.

What is missing: trade exits, the walk-forward backtest, and therefore any honest measure of whether the signals make money after fees. No live trading. No orders placed. The trade script exists but is gated off.

## The one sequencing rule

Build exits and walk-forward first, and build them together. Until that scoreboard exists, every other improvement is guesswork, because we cannot measure whether it helps. No feature work, no new coins, no submodules, and no paper or live trading until walk-forward returns an honest after-fee verdict.

## Priority 0: the scoreboard (do this first, one focused session)

### P0.1 Trade exits

What: a function that, given an entry and the following daily bars, walks forward bar by bar and returns the exit as price, date, reason, and profit after fees. Exit reasons: take-profit hit (`take_profit_pct` above entry); stop-loss hit (ATR-based, `stop_atr_mult` times daily ATR, already in CONFIG); time stop (nothing hit within `hold_window_days`); optional signal exit (MACD cross-down). Check the stop before the target on the same bar (conservative).

Why: without exits the strategy has no risk control. A winner can round-trip back to nothing and a loser can run unbounded until the opposite signal arrives. Exits are half the edge.

Effort: a few hours, well bounded.

Done when: every simulated trade closes with a reason and an after-fee return.

### P0.2 Walk-forward backtest harness

What: roll through history. Train the weights and the vote threshold on a training window, score once on an untouched test window after a 20-day embargo, slide forward, repeat across bull, bear, and sideways stretches. Report only the out-of-sample, after-fee, multi-regime aggregate. Write one line per run to `outputs/experiment_log.csv` (the scaffold is already there).

Why: this is the only honest measure of edge and the gate before any real money.

Effort: the same session as exits. The backtest is literally exits applied across the rolling windows.

Done when: there is a single number answering "does the current four-vote model beat fees out-of-sample, across regimes, versus buy-and-hold and a coin flip," produced by the frozen harness.

## Priority 1: make the model honest before making it fancy

### P1.1 Threshold tuning with fees inside the objective

Test 2-of-4 versus 3-of-4 votes, tuned with fees counted inside the score, not added afterward. This is the direct lever against whipsaws (the small flip-flop losses in choppy, trendless stretches).

### P1.2 Fix the target before adding features (high leverage, cheap)

Test alternatives to the current "10 percent before minus 5 within 20 days" label: a volatility-scaled target such as "plus 2 ATR before minus 1 ATR"; a plain forward n-day return; or a label matched to the real hold window and the actual take-profit and stop. The model can only be as good as the question it is set, so this often beats any new feature.

## Priority 2: sharpen the variables

Add features one at a time, and keep only the ones that improve the after-fee out-of-sample result. Quality and predictiveness beat quantity, and a feature is only good relative to the target it predicts. In order of expected impact:

1. Regime and context. The biggest gap is that the model does not know what kind of market it is in. Add the ATR band itself as a feature, trend strength (ADX or the slope of a long moving average), distance from a long moving average, whether volatility is rising or falling, and market-wide context: Bitcoin's trend and Bitcoin's volatility, because crypto moves together and a coin's odds depend on whether Bitcoin is calm or crashing.

2. Multiple timeframes. Everything is daily now. Compute the same indicators on the weekly chart so the model sees the larger trend, and optionally a 4-hour view for timing. "Daily momentum up while the weekly trend is up" is far stronger than daily alone and cuts whipsaws.

3. Graded momentum. Turn binary "it crossed" into "how convincing": MACD histogram slope and acceleration, bars since the last cross, and the size of the divergence.

4. Volume and participation. Volume relative to its own average, on-balance-volume direction, and volume confirming a breakout. A move on rising volume is more trustworthy than the same move on thin volume.

5. Data hygiene. Keep every feature strictly causal (already verified), drop near-duplicates such as overlapping moving-average distances, and scale features so no single one dominates. Pruning redundant inputs often helps as much as adding new ones.

## Priority 3: only after the core proves edge

- Per-coin models instead of one model for all.
- Whale-detection submodule on liquid coins, looking for structural accumulation and distribution, tested on its own evidence.
- Event-driven news and social track, which is a sensing and latency problem, tested as a separate module.
- Paper trading wiring (Alpaca paper and Binance testnet) once a configuration passes walk-forward.
- A tiny live allocation last, using the single safety switch, reviewed weekly.

## Still-open questions to settle

- The Alpaca crypto commission, the one missing fee number.
- Confirm the Alpaca account is direct self-directed and cash-only, with no margin.
- Finalize the training and trading coin universe so it intersects with the execution venue. Alpaca's crypto list is much narrower than Binance.
- The exact hold length within the 1-to-10-day band and the ATR floor and ceiling are walk-forward outputs, not guesses.

## Standing constraints (do not violate)

- Isolation: work in the notebook or new files, keep existing work revertible, do not break what runs.
- Do not touch `inputs/config.py` (keys only, read from the macOS Keychain), `inputs/requirements.txt`, or `day-metrics.ipynb` unless asked.
- No live trading. Place no orders. Leave `LIVE_TRADING` off.
- No emojis or decorative icons anywhere. Plain words and ASCII.
- Be honest about edge. Never present a NO-GO model as tradeable.
