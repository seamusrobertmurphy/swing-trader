# 3C - Model tuning (to build)

Chapter Three, Execution. Scaffold only. Search for settings that clear both baselines
(buy-and-hold and a coin flip), with every candidate scored on the 3A walk-forward test
windows, out-of-sample and after fees.

## Entry-threshold tuning

Tune the vote threshold and entry selectivity with fees inside the objective: 2-of-4
versus 3-of-4 vote agreement, plus trend and higher-timeframe confirmation.

## Exit-geometry tuning

Sweep `stop_atr_mult` and `take_profit_pct` together, the diagnosed leak where the wide
ATR stop cancels the take-profits, to find any pair that clears the baselines. Built on
`inputs/walkforward.py`.

## Outputs

- rows appended to `outputs/CSV/experiment_log.csv` (the shared ledger)
- comparison tables and a stop-by-target heatmap
