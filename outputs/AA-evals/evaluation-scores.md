# Evaluation scores

One row per evaluation run, newest first. Each row links to its full record.

## What counts as a "buy" (the label)

The model predicts one yes/no event, not a price or a return size.

- A "buy" is set by a **triple-barrier** test (Lopez de Prado). From each day's close, draw three lines: an upper barrier at **+10%**, a lower barrier at **-5%**, and a time barrier **20 days** out.
- Walk forward day by day. If price reaches **+10% before** it falls to -5%, that day is a buy (**label = 1**).
- If it hits **-5% first**, or 20 days pass without reaching +10%, it is a **0**.
- On a day where both could have happened, we assume the **stop (-5%) hit first**, so the label never flatters itself.
- So the question the model answers is: will a +10% move arrive before a -5% drawdown within 20 days?

## How precision is scored

Every test day has two facts: what the model said (buy or not, at the 0.5 cut) and what actually happened. That gives four outcomes:

- **True positive** - said buy, and it was a buy. A good call.
- **False positive** - said buy, but it was not. A bad trade that spends real money.
- **False negative** - said no, but it was a buy. A missed chance.
- **True negative** - said no, and it was not. Correctly stood aside.

- **Precision = true positives / (true positives + false positives).** In plain words: every time the model shouts "buy", how often is it right?
- Precision only punishes bad trades (false positives) and ignores missed chances (false negatives). That is deliberate: a bad trade loses money now, a missed chance only costs an opportunity that comes around again.
- Recall is the mirror (of all the real buys, how many we caught). We rank models by precision, not recall, because being right when we act matters more than acting often.

## What the columns mean

- **date** - the day the evaluation was run.
- **evaluation type** - which kind of evaluation. *Head-to-head*: several models trained on the same train/test split and compared. Later types: walk-forward backtest, tuning sweep, stability check.
- **dataset** - rows and feature count used (e.g. 26,762r / 32f).
- **best model** - the model kept, chosen by the highest Best Model Precision.
- **test AUC** - area under the ROC curve on the out-of-sample test set: the chance the model scores a real buy above a non-buy. 0.50 = no skill (a coin flip), 1.00 = perfect ranking; it does not depend on a threshold.
- **Best Model Precision** - the precision of the chosen model: of the days it called a buy, the share that were genuine buys.
- **Always Buys Precision** - the precision a mindless model that calls every day a buy would score, i.e. the share of all test days that were buys. The baseline to beat.
- **Precision Change (%)** - how much better the best model is than always-buying: (Best Model Precision / Always Buys Precision - 1) x 100. +0% = no better than mindless; above 0 = adding value. Verify it from the two columns to its left.
- **Net P&L/trade** - Keller Metric 2 in one number: the average return of a trade the model takes (probability >= 0.60), after the 0.20% round-trip cost (Binance.com spot with BNB, plus slippage). Above 0 = a model-picked trade makes money after fees. This is the number to maximise when tuning.
- **trades** - how many trades the model would have taken in the test window (probability >= 0.60). Too few trades and the P&L is noise.
- **verdict** - GO only if Best Model Precision clearly beats Always Buys Precision and AUC clears 0.55; otherwise NO-GO.
- **record** - links to the full per-run report (markdown for the numbers, HTML for the charts).

Each per-run record also reports Keller Metric 1 (precision and recall at the 60/40 trading threshold) and Metric 3 (AUC split by volatility regime).

## Runs

| date | evaluation type | dataset | best model | test AUC | Best Model Precision | Always Buys Precision | Precision Change (%) | Net P&L/trade | trades | verdict | record |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-06-24 | head-to-head (1h) | 458,539r / 61f (1h all-market) | LightGBM | 0.510 | 0.311 | 0.303 | +2.5% | -0.38% | 7,348 | NO-GO | [md](2026-06-24/eval-head-to-head-20260624.md) / [html](2026-06-24/eval-head-to-head-20260624.html) |
| 2026-06-24 | head-to-head (1h) | 458,539r / 61f (1h all-market) | LightGBM | 0.510 | 0.311 | 0.303 | +2.5% | -0.38% | 7,348 | NO-GO | [md](2026-06-24/eval-head-to-head-20260624.md) / [html](2026-06-24/eval-head-to-head-20260624.html) |
| 2026-06-23 | head-to-head (1h) | 458,539r / 61f (1h all-market) | LightGBM | 0.510 | 0.311 | 0.303 | +2.5% | -0.38% | 7,348 | NO-GO | [md](2026-06-23/eval-head-to-head-20260623.md) / [html](2026-06-23/eval-head-to-head-20260623.html) |
| 2026-06-23 | label sweep | 33,533r / 61f | best +3.0/-1.5ATR 480b | LightGBM | 0.516 | 0.324 | 0.315 | +2.9% | -0.25% | 5,273 | NO-GO | [md](2026-06-23/label-sweep-20260623.md) |
| 2026-06-23 | label sweep | 33,356r / 61f | best +3.0/-2.0ATR 48b | LightGBM | 0.527 | 0.363 | 0.331 | +9.5% | -0.25% | 4,290 | NO-GO | [md](2026-06-23/label-sweep-20260623.md) |
| 2026-06-23 | head-to-head (1h) | 458,539r / 61f (1h all-market) | LightGBM | 0.510 | 0.311 | 0.303 | +2.5% | -0.38% | 7,348 | NO-GO | [md](2026-06-23/eval-head-to-head-20260623.md) / [html](2026-06-23/eval-head-to-head-20260623.html) |
| 2026-06-21 | head-to-head (1h) | 458,539r / 61f (1h all-market) | LightGBM | 0.510 | 0.311 | 0.303 | +2.5% | -0.38% | 7,348 | NO-GO | [md](2026-06-21/eval-head-to-head-20260621.md) / [html](2026-06-21/eval-head-to-head-20260621.html) |
| 2026-06-21 | head-to-head (1h) | 458,539r / 61f (1h all-market) | LightGBM | 0.510 | 0.311 | 0.303 | +2.5% | -0.38% | 7,348 | NO-GO | [md](2026-06-21/eval-head-to-head-20260621.md) / [html](2026-06-21/eval-head-to-head-20260621.html) |
| 2026-06-21 | head-to-head (1h) | 458,539r / 61f (1h all-market) | LightGBM | 0.513 | 0.312 | 0.303 | +2.9% | -0.35% | 5,543 | NO-GO | [md](2026-06-21/eval-head-to-head-20260621.md) / [html](2026-06-21/eval-head-to-head-20260621.html) |
| 2026-06-21 | head-to-head | 26,772r / 32f | LightGBM | 0.528 | 0.326 | 0.305 | +7.0% | +0.20% | 1,398 | NO-GO | [md](2026-06-21/eval-head-to-head-20260621.md) / [html](2026-06-21/eval-head-to-head-20260621.html) |
