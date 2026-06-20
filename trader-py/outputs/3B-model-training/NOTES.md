# 3B - Model training

Chapter Three, Execution. Train and score on the 3A training/test data, under the
walk-forward design. Two models are tested the same way.

## The rule-based strategy

The daily MACD signal-line cross-up, traded with ATR-based exits. `inputs/walkforward.py`
marches the rolling train/test window through history and reports out-of-sample,
after-fees results against buy-and-hold and a coin flip.
Outputs: `outputs/3B-model-training/walkforward_results.md`,
`outputs/CSV/walkforward_trades.csv`, `outputs/CSV/experiment_log.csv` (the shared
results ledger).

## The machine-learning classifier

`inputs/train_model.py` fits a classifier on the training data and scores it once on the
held-out test data, with a time-series cross-validation used only on the training side
for tuning. It currently uses a single hold-out cut rather than the full rolling
walk-forward; aligning it to the 3A design is a planned step.
Outputs: `outputs/3B-model-training/model.joblib`, `model_metrics.txt`.

## Coupling note

`build_dataset.py`, `train_model.py`, and `walkforward.py` stay in `inputs/` this pass.
`train_model.py` imports from `build_dataset`, and `trade_binance.py` does too; the
scripts move into the 3A/3B folders only once a search-based import shim is added so
nothing breaks.

## Current result

NO-GO, from both. The strategy: about 766 out-of-sample trades, +0.03% per trade at a
74% win rate, but the ATR stop-losses average about -8.5% and cancel the +2.8%
take-profits, so it does not beat buy-and-hold or a coin flip. The classifier: test
ROC-AUC about 0.51, no demonstrated skill. The README should attribute the AUC figure to
this model, not to Chapter One.
