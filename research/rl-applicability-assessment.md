# RL applicability assessment

A memo on `research/rl_reference/`. The source, `~/repos/ReinforcementTrading_Part_1`, is a PPO-on-Gymnasium reinforcement learner trained against EURUSD hourly bars with discrete OPEN-CLOSE-HOLD actions across an SL/TP grid. The question is whether any of it belongs in the trader-swing runtime, and which parts.

The short answer is that the trained agent itself does not belong. The method patterns underneath it do, with translation.

## Where the source breaks the brief

The conflicts are not stylistic. They are structural and they sit on the hard rules.

The action space encodes shorts. `trading_env.py` builds actions over `for direction in [0, 1]` where `0=short` and `1=long`, on every cross of SL and TP. Half of every learned policy is short-direction probability mass. The brief is unambiguous: never short. The action space would have to be rewritten before any policy could be deployed without violating that.

The accounting assumes leverage. The default `lot_size=100000` against an `initial_equity_usd=10000` is roughly thirty-to-one notional leverage in EURUSD terms. The brief forbids margin, leveraged ETFs, and inverse ETFs. Even setting `lot_size` to something small would not fix the conceptual gap: forex pip mechanics are not equity share mechanics.

The horizon is wrong. `min_episode_steps=300` to `episode_max_steps=2000` on hourly bars is a few weeks to a few months of forex hours. Reward shaping pays `hold_reward_weight * unrealized_pips` per bar on winners and charges `time_penalty_pips` per bar in trade. That is the gradient of a day-trader, not a swing-trader on a multi-month SPY-beat horizon. The brief explicitly is not day-trading.

The reward references entry price continuously. Lines 425-435 of `trading_env.py` compute `unrealized_pips` against `entry_price` and shape reward off that path. The brief's Principle 5 prohibits using cost basis in hold or sell logic. The SL is fine — that is one of the three permitted uses of cost basis. The reward shaping is not fine — it teaches the policy to anchor on entry.

There is no edge gate. PPO learns a mapping from feature windows to actions. There is no place in the loop where an affirmative thesis is written, no place where a devil's advocate rebuts it, no place where the trade stands down if the rebuttal lands. The brief's Principle 1 makes that gate the entry requirement. A learned policy that fires on pattern recognition alone is the opposite shape.

There is no Kelly sizing. The env trades fixed lots. There is no half-Kelly default, no quarter-Kelly fallback, no 5% notional cap, no fat-pitch override with the three required conditions, no drawdown ramp, no gap-risk margin, no correlation budget. All of that would have to be added externally; none of it is in the model.

The asset class is wrong. EURUSD on hourly bars is not the universe the trader-swing brief operates in. The benchmark is SPY total return on a long-only US equity book.

## What does survive translation

Three method patterns transfer cleanly. They are documented in `research/equity-feature-adaptation.md` (features) and tagged below for the Friday-review process to pick up if the user wants them.

**Relative-feature design.** `indicators.py` deliberately hides raw price and raw MA values from the agent and feeds it only scale-invariant features: RSI, ATR, slopes, distances of close from MAs, MA spread, MA spread slope. This is the right shape for any cross-sectional equity feature pipeline. A momentum quintile rank, an EV/EBITDA z-score against peer group, an owner-earnings yield versus the 10-year Treasury — all are relative features in the same sense. The list of features needs to change; the design principle does not.

**OOS evaluation harness.** `train_agent.py` lines 144-173 implement a pattern worth adopting: hold out the last 20% of the time series, evaluate every checkpoint deterministically on that slice, and pick the checkpoint with the best out-of-sample terminal equity rather than the lowest in-sample loss. The same pattern, applied to a backtested rule set rather than a learned policy, is the operational form of Principle 1 — prefer the configuration that survived data it did not see. This is a candidate skill for the Friday-review process to add.

**Friction model.** `trading_env.py` charges spread plus commission as a round-trip cost on close, and adds bounded random slippage on entry and exit. The structure is sound. For US equities the numbers are different: no forex-style spread, but bid-ask, exchange and SEC fees, and the slippage characteristic of mid-cap names at the open. The structure transfers; the constants do not.

A fourth pattern is worth noting but not yet a recommendation: **position-persistent semantics.** Once open, the env's position remains until exited by agent action or SL/TP. That is the right shape for the brief's "hold or exit, never average down" stance. The existing trade-execute skill already enforces that implicitly; the env code makes it explicit, which has documentary value.

## What does not survive translation

The PPO model itself. The discrete action space with short directions. The pip-and-lot accounting. The hold-time reward shaping. The fixed-lot sizing. The hourly bar cadence. The lack of fundamentals input. The lack of an explicit thesis layer.

A separate effort that wanted to use RL in this book would need to construct a different env: long-only action space, position-size action as a continuous Kelly fraction within the 5% cap, multi-asset universe, daily bars at the finest, fundamental features stitched into the observation, a thesis-text input encoded somehow, and reward that compounds over months rather than rewarding hour-by-hour drift. That is a full research project, not an import.

## Recommendations

For now, no runtime change. The code stays at `research/rl_reference/` as a study object. The two notes in this folder — this assessment and `equity-feature-adaptation.md` — capture the parts of the source that map to the brief and the parts that do not, so that future sessions inherit the conclusion rather than re-deriving it.

Two Friday-review candidates if the user wants to pursue them:

A backtest harness, modelled on the train/test split pattern in `train_agent.py`, that runs the strategy.md rule set over historical bars on the current universe, checkpoints the parameter grid at regular intervals, and selects parameters by OOS terminal equity. This would be a new skill, not a new routine. The output feeds the Friday review.

A relative-feature library for the research skill, modelled on the design in `indicators.py`, that computes the cross-sectional features the brief already requires (momentum, value, quality, size tilts; owner-earnings yield versus 10Y; EV/EBITDA peer z-score). The implementation lives outside the runtime; the routines call it as a helper, not as a model.

Both candidates are append-only to the existing structure. They do not modify any of the five routines, the boot order, or the hard rules.

## Trail

This assessment was produced on 2026-05-11. It supersedes any prior implicit reading of the source repo. If the source upstream changes, this memo should be re-derived rather than patched.
