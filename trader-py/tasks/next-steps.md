# Task request: remaining work

Chapter Three, updated 2026-06-20. Priority 0 is done. This is the single consolidated list of what remains. Hand it to a fresh session and say "start at Priority 1."

## Status as of this update

Priority 0 (the scoreboard) is built and run. The trade-exit simulator and the walk-forward backtest live in `inputs/walkforward.py`. Run `python inputs/walkforward.py` from the repo root; it fetches full daily history live via ccxt in about 16 seconds and is deterministic on rerun. It writes `outputs/experiment_log.csv` (one row per run), `outputs/walkforward_trades.csv` (every out-of-sample trade), and `outputs/walkforward_results.md` (the write-up).

Current verdict: NO-GO. Across 766 out-of-sample trades on the ten coins, expectancy is about plus 0.03 percent per trade with a 74 percent win rate, but the ATR stop-losses average minus 8.5 percent and cancel the frequent plus 2.8 percent take-profits. The signal beats a coin-flip by a hair and does not beat buy-and-hold. This matches the standing Chapter One result. The point is that the scoreboard now exists, so every change below can be measured honestly and logged one row at a time.

Baseline configuration the scoreboard used: entry is the MACD signal-line cross-up gated to the ATR band 2.5 to 12 percent; exits are an ATR stop at 1.5 times daily ATR, a 3 percent take-profit, and a 10-day time stop, with the stop checked before the target. Train 365 days, test 90 days, 20-day embargo, signal and exits frozen so the test window is scored once.

## The one rule still holds

Measure everything against the walk-forward scoreboard, out-of-sample and after fees. Keep only changes that improve the out-of-sample after-fee result versus both buy-and-hold and a coin-flip. No paper or live trading until something clears that bar.

## Priority 1: make the existing strategy profitable (each item is one measurable experiment)

### 1.1 Fix the exit geometry (do this first, it is the diagnosed problem)

The wide ATR stop is what kills the edge: rare minus 8.5 percent losers cancel the frequent plus 2.8 percent winners. Sweep `stop_atr_mult` and `take_profit_pct` together, with fees inside the objective, through `walkforward.py`. Try tighter stops, wider or trailing take-profits, and a reward-to-risk shape that fits the 74 percent win rate. Done when each variant is logged to `experiment_log.csv` and we know whether any stop and take-profit pair clears both baselines.

### 1.2 Tighten entry selectivity to cut whipsaws

Require more confirmation before entering: trend agreement (only buy when a higher-timeframe or long moving-average trend is up), histogram confirmation, or the stricter 3-of-4 vote threshold instead of the loose entry. Done when it is measured out-of-sample, with fewer trades and better expectancy.

### 1.3 Fix the target and label (high leverage, cheap)

The current backtest uses a fixed 3 percent take-profit over a 10-day window. Test a volatility-scaled target such as plus 2 ATR before minus 1 ATR, and match the label to the real hold window and the actual exits. The model can only be as good as the question it is set. Done when alternative targets are compared out-of-sample.

## Priority 2: sharpen the variables

Add features one at a time and keep only those that improve the after-fee out-of-sample result. Quality and predictiveness beat quantity. In order of expected impact:

1. Regime and market context. The biggest gap is that the model does not know what kind of market it is in. Add the ATR band as a feature, trend strength (ADX or the slope of a long moving average), distance from a long moving average, whether volatility is rising or falling, and market-wide context: Bitcoin's trend and Bitcoin's volatility, because crypto moves together.
2. Multiple timeframes. Everything is daily now. Add the same indicators on the weekly chart for the bigger trend and optionally a 4-hour view for timing. "Daily up while weekly up" beats daily alone and cuts whipsaws.
3. Graded momentum. Turn binary "it crossed" into "how convincing": MACD histogram slope and acceleration, bars since the last cross, and the size of the divergence.
4. Volume and participation. Volume relative to its own average, on-balance-volume direction, and volume confirming a breakout.
5. Data hygiene. Keep every feature strictly causal, drop near-duplicates such as overlapping moving-average distances, and scale features so no single one dominates.

## Priority 3: only after the core clears the bar

- Per-coin models instead of one model for all.
- Whale-detection submodule on liquid coins, tested on its own evidence.
- Event-driven news and social track, separate infrastructure and latency, tested on its own.
- Paper trading wiring (Alpaca paper and Binance testnet) once a configuration passes walk-forward.
- A tiny live allocation last, using the single safety switch, reviewed weekly.

## Harness refinements (tighten the scoreboard itself when convenient)

These are honest limitations of the current backtest, flagged by the build:

- Fills are assumed at the exact stop or target level; intrabar gaps could fill worse. Model gap slippage.
- There is no portfolio concurrency cap in the backtest, though the live controls cap holdings at three or four positions. Add the cap if it changes results.
- Daily bars only; intraday exits are not modelled.
- Add an apples-to-apples baseline that compares to buy-and-hold only over the periods the signal is actually in the market, alongside the existing full-window comparison.

## Still-open questions to settle

- The Alpaca crypto commission, the one missing fee number.
- Confirm the Alpaca account is direct self-directed and cash-only, with no margin.
- Finalize the training and trading coin universe so it intersects with the execution venue. Alpaca's crypto list is much narrower than Binance.
- The exact hold length and the ATR floor and ceiling are walk-forward outputs. The current values (10 days, 2.5 to 12 percent) are starting points, not settled.

## Standing constraints (do not violate)

- Isolation: work in new files, keep existing work revertible, do not break what runs.
- Do not touch `inputs/config.py` (keys only, read from the macOS Keychain), `inputs/requirements.txt`, or `day-metrics.ipynb` unless asked.
- No live trading. Place no orders. Leave `LIVE_TRADING` off.
- No emojis or decorative icons anywhere. Plain words and ASCII.
- Be honest about edge. Never present a NO-GO result as tradeable. Guard against lookahead with the embargo and the score-once discipline.
