# Head-to-head model comparison (2026-06-21)

**Verdict: NO-GO** - best model **LightGBM**, test AUC 0.513, best-model precision 0.312 vs always-buys 0.303 (precision change +2.9%).

## Dataset and split

| field | value |
| --- | --- |
| rows | 458,539 |
| features | 61 |
| train rows | 381,207 |
| test rows | 76,789 |
| split date | 2025-06-18 |
| embargo (days) | 2 |
| always-buys precision (base rate) | 0.303 |
| confidence band | 0.4 - 0.6 |

## Models, out-of-sample test

Precision is TP/(TP+FP) at the 0.5 threshold; Precision Change (%) is (precision / always-buys - 1) x 100.

| model | CV AUC | test AUC | precision | recall | accuracy | Precision Change (%) |
| --- | --- | --- | --- | --- | --- | --- |
| LogisticRegression | 0.526 | 0.501 | 0.306 | 0.571 | 0.477 | +1.0% |
| RandomForest | 0.524 | 0.513 | 0.309 | 0.609 | 0.468 | +1.9% |
| LightGBM | 0.522 | 0.513 | 0.312 | 0.494 | 0.516 | +2.9% |

## Metric 1: confidence filter (act if p >= hi or p <= lo)

Keller's rule: score only the high-conviction rows we would actually trade. Read precision against always-buys precision (0.303).

| model | coverage | precision | recall | F1 |
| --- | --- | --- | --- | --- |
| LogisticRegression | 2% | 0.280 | 0.668 | 0.395 |
| RandomForest | 1% | 0.000 | 0.000 | 0.000 |
| LightGBM | 18% | 0.304 | 0.432 | 0.357 |

## Metric 3: regime-stratified performance

AUC of the best model within low / mid / high volatility terciles (by 30-day realized volatility). A model that only works in one regime is fragile.

| regime | rows | base rate | test AUC |
| --- | --- | --- | --- |
| low vol | 25,597 | 0.304 | 0.520 |
| mid vol | 25,595 | 0.308 | 0.515 |
| high vol | 25,597 | 0.297 | 0.505 |

## Metric 2: simulated P&L (after costs)

Trades = test days where the model's probability clears 0.60, each held under the +10% / -5% / 20-day triple barrier, minus a 0.20% round-trip cost (Binance.com spot with BNB, plus slippage). Equal-weight, independent trades; position sizing and overlap are the Chapter Two controls' job, not modelled here. The per-trade Sharpe and t-stat say whether the expectancy is signal or noise: |t| above about 2 is the rough bar for significance. The equity curve is the cumulative sum of net trade returns at one unit per trade, not a sized portfolio.

| metric | value |
| --- | --- |
| trades taken (prob >= 0.60) | 5,543 |
| win rate (net > 0) | 30.7% |
| net expectancy / trade | -0.35% |
| per-trade Sharpe | -0.179 |
| t-stat (expectancy vs 0; |t|>2 ~ significant) | -13.30 |

## Charts


**Model comparison**

![Model comparison](eval-head-to-head-20260621-compare.png)


**ROC curves**

![ROC curves](eval-head-to-head-20260621-roc.png)


**LightGBM feature importance**

![LightGBM feature importance](eval-head-to-head-20260621-importance.png)


**Metric 3: AUC by volatility regime**

![Metric 3: AUC by volatility regime](eval-head-to-head-20260621-regime.png)


**Metric 2: equity curve (after costs)**

![Metric 2: equity curve (after costs)](eval-head-to-head-20260621-equity.png)

