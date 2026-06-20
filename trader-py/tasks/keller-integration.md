# Keller 2025 review and integration plan

Source: `research/Keller 2025 Machine Learning Models That Actually Work in Crypto Trading`.
This maps the paper's guidance onto trader-py as it stands, grounded in the actual
code (`inputs/build_dataset.py`, `inputs/train_model.py`, `inputs/walkforward.py`),
and proposes changes ordered by feasibility and payoff.

Headline: we are strong where the paper says most people are weak (transaction costs,
and most forms of look-ahead bias), and weak where the paper says the real edge comes
from (feature depth, regime-awareness, and confidence-filtered evaluation). The single
biggest lever is feature engineering, where our model currently scores test AUC 0.514
on 17 daily features. The paper's production model reaches 0.58 with richer features.

## What we already do well (do not redo)

- Transaction costs (Failure Mode 4). `walkforward.py` nets every trade as
  gross minus round-trip fee (0.15%) minus slippage (0.05%), and the GO gate requires
  beating buy-and-hold and a coin flip after fees. The 2D net-edge fence enforces the
  same idea at entry. This is our strongest area.
- Causal features and a clean split (most of Failure Mode 3). Every feature in
  `build_dataset.py` uses only data up to its own bar (forward-only Kalman, swing highs
  confirmed k bars late, label drops the last HORIZON rows). The scaler is inside a
  Pipeline, so it is fit on train only and applied to test, which is exactly the RIGHT
  pattern the paper contrasts against the WRONG fit-on-everything one. The split is
  time-ordered with a 20-day embargo on both sides.
- Simple, legible models (Failure Mode 1). Logistic regression and a regularized
  random forest, no deep learning. Train CV AUC 0.547 versus test AUC 0.514 is a small
  gap, so we are not badly overfit; the problem is weak signal, not memorization.
- Honest baselines. `walkforward.py` already compares against buy-and-hold and a
  multi-seed coin flip.

## The five failure modes against our code

| Mode | Status | Where it lives |
|---|---|---|
| 1 Overfitting to noise | Mostly handled | `train_model.py` (regularized RF, CV on train, test scored once) |
| 2 Non-stationarity | Overlooked on the model side | `train_model.py` does one fixed split, no rolling retrain, no regime features |
| 3 Look-ahead bias | Handled except survivorship | `build_dataset.py` causal; `train_model.py` train-only scaling + embargo; but a fixed list of 10 surviving coins |
| 4 Transaction costs | Handled | `walkforward.py` fee + slippage; 2D fence |
| 5 Insufficient features | Partial; biggest gap | `build_dataset.py` has 17 daily features, 8 of them binary, no multi-timeframe / volatility / order-flow families |

Detail on the three we have not closed:

Mode 2, non-stationarity. The rule-based strategy in `walkforward.py` rolls its
train/test window forward, which gives it some regime adaptation. The machine-learning
model does not: `train_model.py` cuts one 70/30 split (train 2017-09 to 2024-01, test
2024-03 to 2026-05) and never retrains. `regime_note()` cannot even compute a regime;
it only reports date spans. There are no regime features and no stationarity test. This
is the clearest unaddressed gap.

Mode 3, the remaining piece is survivorship bias. `COINS` is a fixed list of ten coins
that survived to today, and the 2A screen also selects from coins with current top
volume. We never see the coins that died. The paper calls this out explicitly. It does
not invalidate the work, but it means results are optimistic and should be labelled as
such until delisted coins are added.

Mode 5, features. We do engineer features rather than feeding raw prices, which is the
right instinct, but the set is shallow relative to the paper: everything is on the daily
timeframe, eight of seventeen columns are binary flags (sparse), and we are missing the
families the paper found most predictive. This is where most of the AUC gap likely sits.

## Models: Tier 1 and Tier 2

Tier 1, gradient boosting. We have logistic regression and random forest but no
gradient boosting. Recommendation: add LightGBM (or XGBoost) as a third entry in the
`train_model.py` bake-off, with the paper's conservative settings (num_leaves 31,
learning_rate 0.05, max_depth 6, min_data_in_leaf 100, feature and bagging fraction 0.8,
early stopping on a validation slice). Feasibility: high. It drops into the existing
evaluate() harness next to LR and RF; it needs `pip install lightgbm` and does not need
the StandardScaler. Our 19k training rows clear the paper's "10k+ is enough" bar. Feed
it the new features below, or the gain will be small.

Tier 2, ensemble (stacking). Today we pick the single better of LR and RF, which is a
selection, not an ensemble. Recommendation, after GBM is in: stack LR, RF, and GBM with
a logistic-regression meta-model trained on out-of-fold predictions, so the meta-model
never sees in-sample base predictions. Feasibility: medium, because the out-of-fold
stacking has to respect the time order. The paper's richer stack (separate direction,
volatility, and regime models) is a larger build; start with the same-target stack.

Tiers 3 (online learning) and 4 (reinforcement learning) are explicitly later. The
paper itself uses RL only for position sizing, which our rule-based 2C sizing already
covers adequately.

## Features to add (the 70% lever)

The paper's feature code is hourly; we are a daily swing system, so adapt the lookbacks
to days. All of these are causal and scale-invariant and belong in
`build_dataset.py:compute_features` and the `FEATURES` list (which `trade_binance.py`
imports, so train and live stay in sync).

| Family | What to add | Feasibility |
|---|---|---|
| Multi-lookback momentum | `close/close.shift(k)-1` for k in roughly 5, 10, 20, 60, 120 days, plus the diff (acceleration) | High, OHLCV only |
| Realized volatility | rolling std of returns (7d, 30d), Parkinson (high/low), Garman-Klass (OHLC), and a vol-of-vol ratio | High, OHLCV only; doubles as Mode 2 regime input |
| Volatility-adjusted returns | mean return over short window divided by volatility (Sharpe-like and Sortino-like) | High, cheap, stabilizing |
| Illiquidity proxy | Amihud: rolling mean of abs(return) / dollar volume | High, OHLCV only |
| Order-flow imbalance, microstructure spread | bid/ask and trade-flow imbalance | Low; needs order-book and trade data we do not store yet |

Two notes. ATR percent already exists in the controls layer (2B) but is not a model
feature; fold a volatility feature into the model too. And consider trimming or
complementing the eight binary flags, which carry little information next to the
continuous families above. True order-flow features should be a separate
data-collection sub-project, not a blocker for the rest.

## The three evaluation metrics

Metric 1, precision and recall at the decision threshold. Not done. `train_model.py`
scores at probability 0.5. Recommendation: add an evaluation that keeps only rows where
the probability is above 0.60 or below 0.40, then reports precision, recall, F1, and the
share of rows kept. Feasibility: high; the paper provides the function and it is a few
lines. This is the measurement twin of the trading filter below.

Metric 2, simulated profit and loss with costs. Partial. `walkforward.py` reports
after-fee expectancy per trade and beats baselines, but for the rule strategy, not the
model, and it does not report a Sharpe ratio or a maximum drawdown for an equity curve.
Recommendation: when the model probability drives entries, route those entries through
the same exit-and-cost engine in `walkforward.py` and report cumulative return, Sharpe,
and max drawdown. Feasibility: medium; reuse the existing engine, change only what
generates entries.

Metric 3, regime-stratified performance. Not done. `walkforward.py` asserts that its
windows span rising, falling, and sideways markets but never splits results by regime.
Recommendation: define a simple regime label (for example BTC above or below its 200-day
trend, or volatility terciles) and report AUC and expectancy per regime. Feasibility:
high to medium; the only real work is choosing the regime definition, which is reused for
the Mode 2 regime features.

## The 60/40 confidence filter

Strong fit, high feasibility. Trade only when the model probability is above 0.60 or
below 0.40 and ignore the middle band; the paper reports this filters about 70% of
signals, cuts cost, and raises conviction. We do not have it yet because the model does
not drive trades; the rule strategy does. Recommendation: expose the cutoff as a CONFIG
knob, apply it in the model evaluation now (this is Metric 1), and apply it to
model-driven entries later, and sweep the cutoff in 3C model tuning.

One caveat specific to us: our label is positive only about 30% of the time (target +10%
before stop -5% within 20 days), so the classes are not balanced around 0.5. A raw
symmetric 0.60/0.40 cut assumes a 50% base rate. Calibrate the probabilities first (or
set the cut relative to the base rate) so "high conviction" means what we think it means.

## Recommended order of work

1. High, now. Add the OHLCV-computable feature families (multi-lookback momentum and
   acceleration, realized-volatility estimators, volatility-adjusted returns, Amihud
   illiquidity) to `build_dataset.py`. Lands in 3A.
2. High, now. Add LightGBM to the `train_model.py` bake-off with conservative settings.
   Lands in 3B.
3. High, now. Add the confidence-filtered evaluation (Metric 1) and expose the 0.60/0.40
   cutoff as a CONFIG knob. Lands in 3B, swept in 3C.
4. Medium. Run the model under the 3A walk-forward (rolling retrain) to attack
   non-stationarity, and add regime-stratified reporting (Metric 3).
5. Medium. Route model-driven entries through the `walkforward.py` cost-and-exit engine
   for full profit and loss, Sharpe, and drawdown (Metric 2).
6. Medium. Stack LR, RF, and GBM with a meta-model (Tier 2) once the above is stable.
7. Lower or later. Order-flow and order-book features (needs new data capture), online
   learning (Tier 3), reinforcement learning for sizing (Tier 4), and survivorship-bias
   mitigation (add delisted coins to training).

All of steps 1 to 3 touch only editable scripts (`build_dataset.py`, `train_model.py`),
not the canonical notebooks, and new tunable values should follow the operator-owned
CONFIG convention.
