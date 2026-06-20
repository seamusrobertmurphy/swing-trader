# Report of previous work — buy-signal pipeline

Earlier in this project, against real Binance daily data, a complete buy-signal
pipeline was built and run end-to-end. It produced an honest, and unfavourable,
result.

## Dataset
27,699 labeled rows, one per (coin, day), across ten USDT pairs — BTC, ETH, SOL,
BNB, XRP, ADA, AVAX, LINK, LTC, DOGE — spanning 2017 to 2026. Seventeen features,
all scale-invariant (ratios, slopes, distances, flags), computed causally so no
bar sees the future. A leakage test confirmed this exactly: features at a given
bar were identical whether or not later bars existed. The label is the agreed
rule — 1 if price gains +10% before falling −5% within 20 days, else 0 — giving a
base rate of about 0.325 (a coin-flip-beating model must clear that).

## Split
Time-ordered, never shuffled: oldest 70% train, newest 30% test, with a 20-day
embargo straddling the cut so no training label could peek into the test period.
Tuning happened only on train via TimeSeriesSplit cross-validation; the test set
was scored exactly once.

## Result — NO-GO
Two models were fit; RandomForest won. On the untouched test slice: buy-class
precision 0.320 against a 0.304 base rate — a lift of only +0.017, ROC-AUC 0.514.
That is barely distinguishable from guessing, and it matches the earlier ~48%
out-of-sample finding. No demonstrable edge yet. A live trade script with the
`LIVE_TRADING` safety gate was written but never armed and never placed an order.

## The catch at handoff time
All of that lived in the old `trader-swing` folder, which had since been emptied
(work was moved to the new repo). The handoff session was mounted on that empty
folder and could not see the real repo, so it could not rebuild or save anything
where it belonged. The next session needed to be pointed at the correct repo
first.

## Status update (this session)
This session IS mounted on the correct repo (`day-trader/trader-py`). The work
was never lost — the three scripts (`inputs/build_dataset.py`,
`inputs/train_model.py`, `inputs/trade_binance.py`), the dataset
(`outputs/dataset.csv`, 27,699 rows), the trained model (`outputs/model.joblib`),
and the metrics (`outputs/model_metrics.txt`) are all present. The metrics file
confirms the standing NO-GO result. The rebuild described in `HANDOFF_TASK.md` is
therefore largely already done; what remains is the operator's go/no-go decision.
