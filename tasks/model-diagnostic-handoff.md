# Trading Model Diagnostic & Regime Methodology — Task Handoff

**Context:** ML model on Binance spot OHLCV (CCXT + binance.vision), ~600 coins, 2017–2026, bars at 5m / 1h / 4h. Walk-forward evaluation with strict after-cost scoring. Symptom: few profitable entry/exit signals survive transaction costs. This brief defines what to find out and how, in execution order.

---

## Part 1 — Diagnostic sequence

Run these in order. Each answer determines whether the next question matters. Do not jump to architecture changes before questions 1–4 are answered.

### 1. Is there a pre-cost edge at all?
Strip out fees and slippage entirely. Report raw directional accuracy (or AUC, or mean return per predicted trade) on the held-out set. This is the gate.

Baselines that matter:
- A coin-flip at the **actual** class base rate, not 50%. If 53% of bars are up, beating 50% is nothing; beat the real balance.
- Persistence: "next bar equals last bar."

If the model can't beat both before costs, the problem is features or architecture, and nothing downstream matters.

### 2. If there's a pre-cost edge, does it survive costs?
Report the full round-trip cost assumption: maker/taker fee, assumed spread, assumed slippage, and how slippage scales with size. Then show the return distribution before and after that cost is subtracted.

Key number: the gap between mean predicted-trade return and total round-trip cost. If the edge is 8 bps and cost is 12 bps, that is a **horizon problem**, not a model problem, and retraining will not fix it.

### 3. Where on the horizon does the edge live?
Run the same model logic across 5m, 1h, 4h. Report edge-after-cost for each.

Hypothesis to test: the edge strengthens as the bar lengthens, because one fixed cost amortizes over a larger move. If 4h clears costs and 5m doesn't, that settles the scalping question — in the opposite direction from "trade faster." Shorter holds mean more round-trips, more spread paid, worse signal-to-noise. Scalping maximizes the cost drag that is already the dominant term.

### 4. Is the edge real, or is it leakage?
The most common reason a crypto model looks good in backtest and dies live. **If only one thing can be checked first, check this.** Leakage makes a dead model look alive and sends you optimizing a corpse.

Check specifically:
- Are features computed using only information available at decision time, or do any use the close of the bar being predicted?
- Is normalization (scaling, z-scoring) fit on the whole dataset including test, or refit walk-forward inside each training window only?
- Is the label aligned so the model predicts the **next** return, not the current one?

Any single one of these inflates results and then collapses out of sample.

### 5. Is the edge stable across regimes, or an artifact of one?
2017–2026 is not one market. Break walk-forward results into chunks: 2017 run-up, 2018 bear, 2021 bull, 2022 collapse, recent period. Report edge-after-cost per chunk.

If profitability lives almost entirely in one or two regimes, the model is memorizing a period, not generalizing. That decides whether to train regime-conditionally (Part 2) or abandon the global model.

### 6. What's the trade frequency, and is selectivity available?
Report trades per unit time. Then raise the confidence threshold so the model only acts on its strongest signals, and plot after-cost return per trade against threshold.

If the curve rises as the model trades less, the path forward is **selectivity, not a new architecture**. A model that trades twice a week profitably beats one that trades 200 times and bleeds fees. The cost-aware evaluation is already pointing here.

### 7. Trade economics, not just classification metrics.
Accuracy hides ruin. Report on after-cost returns: win rate, average win vs average loss, profit factor, max drawdown, Sharpe. A 55% win rate loses money if wins are smaller than losses.

**Summary of the chain:** Q1 — do you have anything. Q2 — is it tradeable. Q3 — where. Q4 — is it real. Q5 — does it last. Q6–Q7 — how to trade it.

---

## Part 2 — Regime-aware training methodology

### Walk-forward structure (corrects the calendar-year instinct)
Segmenting history and holding out the tail of each segment is correct and strictly better than a single train-then-holdout-last-year split. One holdout gives one estimate, hostage to whatever regime fell in that final year. Many folds give a **distribution** — the thing you actually want, because it shows how much performance varies as conditions change.

But the unit is **not the calendar year.** Markets don't reset on January 1. Holding out December and testing the prior January leaks the future into the past.

Instead, slide a window forward continuously:
- Train Jan 2017 – Jun 2018, test Jul–Sep 2018.
- Roll: train Apr 2017 – Sep 2018, test Oct–Dec 2018.
- Continue to present.

Each test fold is unseen data sitting in the future relative to its training. That is the only honest simulation of deployment.

### Anchored vs rolling
- **Anchored:** training start fixed, window grows, model always has all history.
- **Rolling:** fixed-length window, drops oldest data as it advances, model only knows recent history.

For crypto, rolling is usually the more honest test: 2017 dynamics may actively mislead in 2025, and a model that has forgotten them generalizes the way a deployed model would. **Run both and compare.** Anchored beats rolling → old data helps. Rolling beats anchored → old data is noise or worse.

### The leakage gap
Leave a buffer between end-of-training and start-of-testing, long enough that no feature computed from training-window data overlaps the test window. A 200-period moving average on 4h bars is over a month of lookback; without a gap, the first test predictions are contaminated. This is the time-series form of leakage and it is easy to miss.

### What you can and cannot know about regimes
You **cannot forecast the next regime.** If regime shifts were predictable they'd be arbitraged away. What you can do is **classify the present regime as it reveals itself**, accepting a lag — always a step behind the turn. That is enough to be useful.

### Labelling regimes honestly
Label history with measurable, contemporaneous quantities, never narrative ("the bull year"):
- Realized volatility over a trailing window.
- Trend strength (slope of price, or an ADX-style measure).
- Sign and magnitude of trailing returns, or ratio of up-bars to down-bars.

All computable at every point using **only past data**, which means they can be computed live, today, on the current window. A label that "knows" 2021 was bullish because it saw all of 2021 is leakage. A label that says "trailing 30-day vol is currently low and trend is currently up" is honest — you could have computed it that day.

### Preferred design: condition one model, don't build a switchboard
Rather than training a separate model per regime and hot-swapping, train a **single model that takes current volatility and trend state as inputs** alongside the price features. It learns "when vol looks like this and trend like that, the right behaviour is this." When a 2021-like state recurs, the model recognizes the input pattern and responds — no regime-detection-and-swap layer to build and trust. The regime knowledge lives in the weights, conditioned on observable state.

If explicit per-regime models are still wanted, the walk-forward rule governs everything: assign each historical point to a regime using **only information available at that point.** Never use future data to label the past.

### Bottom line for the regime question
Segment and hold out the tail of each segment — but as a **continuously rolling window with a leakage gap**, not calendar years. Run anchored and rolling both, to learn whether old regimes help or hurt. Identify the current regime with **lagging contemporaneous indicators**, accept the next one is unforecastable, and prefer conditioning one model on observable regime state over a switchboard of regime-specific models. The cross-validation distribution across all folds is the real estimate of how the system behaves when the regime you can't predict arrives.

---

## Part 3 — Keep macro out of the model
Geopolitics, monetary policy, the shift toward DeFi: none of it belongs **inside** a 5m/1h/4h model as a feature. The relationship between a headline and a 5m bar is too noisy and too non-stationary to learn from a handful of episodes; the model will overfit to whatever happened in the training window. Use macro as a **human judgment on top** — whether to deploy capital and at what size — never as a tensor inside the net.
