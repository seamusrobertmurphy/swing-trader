# TASK: train a model on the metrics, then trade live on Binance

Written 2026-06-18. Picks up after the indicator metrics and the breakout backtest.
Goal: build a best-practice train/test dataset from the indicators, train and honestly
score a model, then turn confirmed signals into real spot orders on Binance.

## Coin subset (the universe we train AND trade)

Liquid, long-history, large-cap USDT spot pairs only — no micro-caps or new listings:

    BTC, ETH, SOL, BNB, XRP, ADA, AVAX, LINK, LTC, DOGE   (all /USDT)

Same list for training and for live trading, so the model is used only on what it learned.

## Task A — build the labeled dataset  (new file: python/inputs/build_dataset.py)

Generalize `backtest.py` from "breakout events" to "one row per coin per day".

Rows: one per (symbol, date) across the 10 coins, full daily history (ccxt, paginate
past 1000 bars if needed).

Features (all **scale-invariant** so one model works across price levels):
- (close - kalman)/kalman, (ema14 - ema91)/close, (ema91 - ema125)/close
- RSI/100, Choppiness/100
- MACD histogram / close, MACD_below_zero (0/1)
- Bollinger position: (close - bbl)/(bbu - bbl)
- volume / 20-day avg volume
- distance to nearest resistance: (resistance - close)/close
- boolean flags: ema_cross, golden/death cross event, doji, dragonfly, gravestone, breakout
Every feature uses ONLY data up to that day. No future leakage.

Label: the success rule already agreed — 1 if, within 20 trading days, price gains
+10% before falling -5% below that day's close; else 0. (Tunable.)

Output: `python/outputs/dataset.csv` (symbol, date, features..., label).

## Task B — train/test split to best practice  (the part to get right)

1. **Time-ordered split, never random.** Sort by date. Train = older ~70%, test = newer ~30%.
2. **Embargo gap = label horizon (20 days)** between train and test: drop rows whose
   20-day label window crosses the split date. Stops the last train labels peeking into test.
3. **Representative span:** the training window must include bull, bear, and sideways
   regimes, not one regime. Check the date range covers all three.
4. **Report the base rate** (share of label=1) on train and test; the model must beat it.
5. **Class imbalance:** if label=1 is rare, use `class_weight="balanced"`.
6. **Final test set is touched once.** Tune only on train (with time-series CV:
   `sklearn.model_selection.TimeSeriesSplit`), then score test a single time.

## Task C — train and score the model

- Model: start simple and legible — `sklearn` logistic regression or
  `RandomForestClassifier` (scikit-learn already installed). No deep learning yet.
- Fit on train features -> label. Evaluate on the held-out test slice.
- Report: accuracy, precision, recall, ROC-AUC, and the confusion matrix, all on test,
  next to the base rate. Precision on the "buy" class matters most (false buys cost money).
- Save the fitted model (`joblib`) to `python/outputs/model.joblib` and a one-line
  metrics summary to `python/outputs/model_metrics.txt`.
- Honesty gate: do NOT proceed to live trading unless test precision clearly beats the
  base rate AND the earlier backtest expectancy survives fees.

## Task D — live trading on Binance  (new file: python/inputs/trade_binance.py)

This is the only part that spends real money. Keep it separate from all the read code.

1. Keys: `BINANCE_API_KEY` / `BINANCE_API_SECRET` from the environment (store via
   `../scripts/store-secrets.sh`). Never in the notebook or repo.
2. Connect with ccxt: `ccxt.binance({"apiKey":..., "secret":...})`.
   **Start on testnet:** `exchange.set_sandbox_mode(True)` until proven.
3. The single safety switch: place orders only if `LIVE_TRADING == "true"` in the env
   (mirror the existing `scripts/binance.sh` rule). Any other value = refuse.
4. Flow each run: read balance (`fetch_balance`) -> for each coin the model flags buy
   today, size the order (cash / number of buys, respecting a max position cap) ->
   place a spot order (`create_order`) -> log it. Act on exits before entries.
5. Operator confirms before going live; the agent does not flip `LIVE_TRADING` itself.

## Files / context

- Notebook: `python/ccxt-daily-signals.ipynb` (engine + config knobs)
- Backtest: `python/inputs/backtest.py` -> `python/outputs/breakout_events.csv`
- Earlier metrics tasks: `tasks/TASK_crossover-and-ml-pipeline.md` (crossover event,
  doji/dragonfly/gravestone, MACD — fold these features into build_dataset.py)

## Honest standing result (why we validate before trading)

Breakout + crossover + volume scored ~57% in-sample but ~48% out-of-sample on a small
test set; positive per-trade return came from the 2:1 target/stop, not prediction, and
no fees were modeled. The model + clean train/test is the test of whether a real edge
exists. If it doesn't survive out-of-sample with fees, don't trade.
