# Evaluation scores

One row per evaluation run, newest first. Each row links to its full record.

## What the columns mean

- **date** - the day the evaluation was run.
- **evaluation type** - which kind of evaluation. *Head-to-head*: several models trained on the same train/test split and compared. Later types: walk-forward backtest, tuning sweep, stability check.
- **dataset** - rows and feature count used (e.g. 26,762r / 32f).
- **best model** - the model kept, chosen by the highest buy-class precision on the test set.
- **test AUC** - area under the ROC curve on the out-of-sample test set: the chance the model scores a real buy above a non-buy. 0.50 = no skill (a coin flip), 1.00 = perfect ranking; it does not depend on a threshold.
- **precision** - of the days the model called a buy (probability >= 0.5), the share that were genuine buys: TP / (TP + FP). "When it says buy, how often is it right."
- **base rate** - the share of all test days that were genuine buys, P(label=1). The precision you would get by blindly calling everything a buy: the baseline to beat.
- **lift (x)** - precision divided by base rate. How many times better than the blind baseline. 1.0x = no better than guessing; above 1 = adding value. Verify it yourself: precision / base rate.
- **verdict** - GO only if precision clearly beats the base rate and AUC clears 0.55; otherwise NO-GO.
- **record** - links to the full per-run report (markdown for the numbers, HTML for the charts).

A day is labelled a "buy" (label = 1) if its close gains +10% before falling -5% within the next 20 days; otherwise 0. Each per-run record also reports Keller Metric 1 (precision and recall at the 60/40 trading threshold) and Metric 3 (AUC split by volatility regime).

## Runs

| date | evaluation type | dataset | best model | test AUC | precision | base rate | lift (x) | verdict | record |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-06-20 | head-to-head | 26,762r / 32f | LightGBM | 0.520 | 0.325 | 0.305 | 1.07x | NO-GO | [md](2026-06-20/eval-head-to-head-20260620.md) / [html](2026-06-20/eval-head-to-head-20260620.html) |
