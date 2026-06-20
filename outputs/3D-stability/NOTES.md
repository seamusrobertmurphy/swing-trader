# 3D - Stability checks (to build)

Chapter Three, Execution. Scaffold only. The validation stage after tuning: confirm any
edge found in 3C is not an artifact.

## Planned work

- parameter stability around the chosen settings
- results split by market type (rising, falling, sideways)
- randomized-entry (coin-flip) and buy-and-hold baselines
- an optional Monte Carlo or bootstrap on trade returns

## Output

- a stability report

## Tail of Chapter Three

After the checks clear: paper trading (Alpaca paper, Binance testnet), then a tiny live
allocation. The execution endpoint, not a computation module. No live trading until a
configuration clearly beats buy-and-hold and a coin flip, out-of-sample and after fees.
