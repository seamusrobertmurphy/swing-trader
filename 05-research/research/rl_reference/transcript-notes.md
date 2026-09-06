# Transcript notes — author's walkthrough of the RL repo

Companion notes to the imported source at `research/rl_reference/`. Distilled from the author's video walkthrough at https://www.youtube.com/watch?v=oW4hgB1vIoY. The transcript was provided in full by the user; this is the working summary.

The video walks the four files of `~/repos/ReinforcementTrading_Part_1` end to end. The author trains a PPO agent on EURUSD hourly bars and runs it on held-out 2023–2025 data. Below: the conceptual frame, the file-by-file walkthrough, and the limitations the author himself surfaces.

## The five concepts the author opens with

The standard reinforcement-learning vocabulary, applied to trading:

The **agent** is the trained model. It places long or short positions and sets stop-loss and take-profit distances at entry.

The **environment** is the historical price series wrapped in a Gym interface. The agent reads it, the env replies with the next observation and a reward.

The **actions** are discrete: no-trade, or open in one of two directions with one of a small grid of SL and TP distances.

The **reward** is the trade's realised profit and loss when a position closes, scaled to a usable range. Positive on wins, negative on losses, magnitude proportional to PnL.

The **policy** is the mapping the agent learns from observed state to action. PPO updates that mapping.

The author frames the loop as "training a dog": the agent has no intrinsic motivation, so the code maximises the reward signal directly. Actions that earned more reward in training receive higher probability in deployment.

The training run is model-free: the agent learns from interaction with the env rather than from a written model of how price moves.

## File walkthrough

### `indicators.py`

The author opens with the indicator pipeline. RSI(14), ATR(14), SMA(20), SMA(50). He computes a "slope" as the first difference of each MA — he notes explicitly that this is not a regression slope, just `ma_t − ma_{t-1}`. He drops NaN rows at the head of the series after the indicators are computed.

He calls this file the natural place to extend the feature set. The relative-feature philosophy is implicit in his choice to feed the agent slopes and distances rather than raw levels, but he does not spell it out in the video.

### `trading_env.py`

The class `ForexTradingEnv` inherits from `gym.Env`. The default `window_size` is 30; the agent observes the last 30 bars at each step.

In the spoken walkthrough the author says the SL options are `[60, 90, 120]` pips and the TP options are also `[60, 90, 120]`. The current code in the repo has been widened since: `SL_OPTS = [5, 10, 15, 25, 30, 60, 90, 120]` and `TP_OPTS` matches. Either version conveys the same point — the SL/TP grid is a small set of pip distances baked into the action space, expanded only at the cost of training compute.

The action structure in the video is described as: action zero is no-trade, otherwise the agent chooses long or short. The current code separates this further into HOLD, CLOSE, and OPEN(direction, sl, tp), with position persistence — once open, the position lasts until the agent issues CLOSE or until SL/TP triggers intrabar. The video's framing is the older two-action version; the imported file is the position-persistent rewrite.

The reward function:

The agent receives `pnl × 10000` on a winning close, where the 10,000 multiplier converts EURUSD price moves to pips. Negative on a losing close. The author notes the edge case where a single hourly candle's range spans both SL and TP — without tick data, the order of events inside the bar is unknown. The code treats this case as a loss, "to be on the safe side". The current `_check_sl_tp_intrabar_and_maybe_close` carries the same convention: when both are hit, exit at SL.

The `step` function combines the action, the SL/TP check, and the reward computation, returning the standard Gym tuple. `reset` zeros the equity to $10,000 and clears state. `render` plots the equity curve.

### `train_agent.py`

The author imports PPO from `stable_baselines3`. He describes PPO as well-suited to trading: noisy, continuous data flowing live, where the agent needs to update incrementally as new bars arrive.

Wrapping the env in `DummyVecEnv` is required by stable-baselines3 even with a single environment. The author notes this is for parallelisation support and waves past the technical detail.

He trains for **50,000 timesteps** in the spoken walkthrough. The current code in the repo trains for **600,000**. He acknowledges this as a tunable: more timesteps deepen learning but risk overfitting and cost compute. The trained model is saved as `model_eurusd_<...>.zip`.

The author runs `python train_agent.py` live, watches the rolling logs (elapsed time, learning rate, loss), and notes the in-sample equity curve trends up — the agent is finding positive reward and shaping its policy toward it.

### `test_agent.py`

Loads the saved model and runs it on out-of-sample data (in the video, EURUSD hourly 2023–2025). No further training. Same SL/TP grid and window size as training.

The OOS equity is "not what we expected" — the curve looks fine early, fades later, and ends short of the in-sample trajectory. The author does not call this a failure; he calls it the correct sign that the in-sample fit was partly memorisation, and the cure is more features, more careful SL/TP grids, and fewer training timesteps.

## Limitations the author himself raises

The author closes the video with an honest list of weaknesses. Worth recording, because they form the constraint set any reuse of this code has to acknowledge.

He used "barely few classic technical indicators" — RSI, ATR, two MAs, and a difference-based slope. The slope is not a real regression; he says so. Better features would compound through better policies.

The SL and TP options are too coarse. A grid of three pip distances on a single direction does not give the agent enough flexibility on hourly EURUSD. He suggests 5-pip increments from 30 to 100 pips as a fuller grid.

The training step count risks overfitting. He demonstrates this directly: re-training from 50,000 down to 10,000 timesteps gives a different equity profile — sometimes worse in-sample, sometimes more stable out-of-sample. The point being: 50,000 was not load-bearing, and "more training" is not monotonic improvement.

He notes that the market is noisy and the model is trying to extract a real signal from a high noise floor. He does not claim the agent has solved the problem; he claims the framework is enjoyable, instructive, and ready for the viewer to extend.

## How this maps onto the trader-swing brief

These notes describe the source repo as-is. They do not endorse a port. The applicability assessment at `../rl-applicability-assessment.md` is the argument for what survives translation to the trader-swing book and what does not.

The video confirms what the assessment infers from the code: the action space is symmetric long/short, the horizon is hourly, the reward is PnL-of-closed-trade, and the only validation is a single train/test split with a small grid of hyperparameters tuned by hand. None of those choices are compatible with the trader-swing brief without rewriting the env. The relative-feature design and the OOS-equity-as-selection-metric pattern are the parts the assessment identifies as portable.

## Citation

Source video: "[Reinforcement Learning Trading — Part 1](https://www.youtube.com/watch?v=oW4hgB1vIoY)". Transcript provided by user, 2026-05-11.

Sources:

- [YouTube — Reinforcement Learning Trading Part 1](https://www.youtube.com/watch?v=oW4hgB1vIoY)
- `research/rl_reference/indicators.py`
- `research/rl_reference/trading_env.py`
- `research/rl_reference/train_agent.py`
- `research/rl_reference/test_agent.py`
