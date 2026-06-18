# research/rl_reference

Imported verbatim from `~/repos/ReinforcementTrading_Part_1` on 2026-05-11. This directory is reference material. Nothing inside it is executed by any routine, imported by any skill, or read on the boot order. The trading agent does not see this code at runtime.

## Provenance

A four-file PPO-on-Gymnasium project trained against EURUSD hourly bars.

| File              | Role                                                                          |
|-------------------|-------------------------------------------------------------------------------|
| `indicators.py`   | pandas-ta feature pipeline. RSI, ATR, SMA slopes, close-to-MA distances, MA spread |
| `trading_env.py`  | Gymnasium env, position-persistent. Discrete actions: HOLD, CLOSE, OPEN(direction, SL, TP grid). Friction, slippage, intrabar SL/TP, reward shaping |
| `train_agent.py`  | Stable-Baselines3 PPO, 600k timesteps, checkpointing, best-by-OOS-equity selection, train-vs-test equity plot |
| `test_agent.py`   | Loads the best model, runs deterministic eval, writes a closed-trades CSV |
| `requirements.txt`| Pinned upstream dependencies, re-encoded to UTF-8                              |

The original `data/` directory holds two EURUSD CSVs (1H BID, multi-year). They are not copied here; if a reproduction is wanted, they remain at `~/repos/ReinforcementTrading_Part_1/data/`.

## Why this lives in research/, not in the runtime

The source repo is designed against assumptions that the trader-swing brief forbids. Reading the trader-swing `CLAUDE.md` and the source together, the conflicts are not stylistic: they hit the hard rules.

1. **Shorting.** The discrete action space includes `direction=0` (short) on every SL/TP combination. The trader-swing brief: *Never short.*
2. **Leverage.** Forex pip mechanics assume 100k-unit lots on a $10k notional, which is implicit ~30x leverage. The brief: *Never margin. Never leveraged ETFs.*
3. **Day-trading horizon.** The env operates on hourly bars with random-start episodes of 1000-2000 bars (roughly two to four trading months in forex hours). Reward shaping rewards holding winners by the bar and penalises time-in-trade. The brief: multi-month swing horizon, beat SPY total return, no day-trading.
4. **Anchoring.** SL is set at entry as `entry_price - sl_pips`. The brief permits cost basis only for the 7% hard stop, realised P&L, and tax. The env's SL logic is consistent with that narrow use; its reward shaping that references `unrealized_pips` from entry is not — it ties the live decision to the entry price.
5. **Edge gate.** PPO learns a policy from price-feature windows alone. There is no written affirmative case, no devil's advocate, no Principle 1 evidence-of-edge check. The brief refuses to enter a position without that paragraph pair.
6. **Sizing.** Position size is implicit (one lot, or whatever the env defaults). Half-Kelly with a 5% cap is absent. Drawdown ramp, gap-risk margin, correlation budget — all absent.
7. **Asset class.** EURUSD on hourly bars. The book is US equities benchmarked to SPY.

A wholesale port would break the brief on every axis above. So this code is shelved here as a study object.

## What is reusable, and how

The code carries methods that translate cleanly. The applicability assessment in `../rl-applicability-assessment.md` is the full argument; the short version:

- **Relative-feature design.** `indicators.py` deliberately hides raw price levels and raw MAs from the agent and exposes only scale-invariant quantities (RSI, ATR, slopes, distances, spreads). This is a principled choice and applies equally well to equity research features. The adaptation lives in `../equity-feature-adaptation.md`.
- **OOS evaluation harness.** `train_agent.py`'s pattern — train on the first 80%, evaluate every checkpoint deterministically on the last 20%, keep the checkpoint with the best OOS terminal equity — is the operational form of "prefer the model that survived data it did not see". It is the right shape for a backtest skill the Friday review could call.
- **Friction model.** Spread + commission + bounded random slippage, billed round-trip on close, is a clean cost model. Equities and ETFs have different frictions (no spread in the forex sense, but bid-ask, exchange fees, and Reg NMS slippage). The structure transfers; the constants do not.
- **Position-persistent env semantics.** Once open, the position remains until exited by agent action or by SL/TP. That maps directly onto the brief's "hold or exit, never average down" stance.

What does not survive translation: the discrete action space (it encodes shorts), the reward shaping (it encodes day-trade time pressure), the pip accounting, the lot-size assumption.

## Running the original

The original was built for Windows (`pywin32` in requirements). It expects:

- A `data/` folder with the EURUSD CSVs from the upstream repo
- Python 3.11+ with the pinned `requirements.txt`
- ~6 hours of GPU/CPU for the 600k-timestep PPO run

None of this is set up here. The files are static reference. To reproduce, clone the upstream repo at `~/repos/ReinforcementTrading_Part_1` and follow its own conventions.

## Boundary

Nothing in `routines/`, `skills/`, `scripts/`, or `memory/` imports this code. The agent boot order does not read this directory. Friday-review strategy edits do not reference it. If a future change wants to bring methods from here into the runtime, that change goes through a new task and a Friday-review strategy revision, not through routine append-only journaling.
