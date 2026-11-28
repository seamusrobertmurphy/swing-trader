# Glossary

The terms the swing-trader app uses, for trading and for the statistics behind its models. Begun 26 September 2026 for round-three revision task 1, from the glossaries in `README.md` and `02-runtime/trader-workflow.qmd`, and extended with every term the app's pages now use. A commit that puts a new term on a page adds its entry here.

## Contents

- [After-cost return](#after-cost-return)
- [Amihud ratio](#amihud-ratio)
- [ATR](#atr)
- [AUC](#auc)
- [Base rate](#base-rate)
- [Block bootstrapping](#block-bootstrapping)
- [Break-even band](#break-even-band)
- [Break-even chance](#break-even-chance)
- [Calibration](#calibration)
- [Candle](#candle)
- [Confidence group](#confidence-group)
- [Confidence interval](#confidence-interval)
- [Confirmed best](#confirmed-best)
- [Corwin-Schultz spread](#corwin-schultz-spread)
- [Cost floor](#cost-floor)
- [Edge](#edge)
- [Edge floor](#edge-floor)
- [Elastic net](#elastic-net)
- [EMA](#ema)
- [Embargo](#embargo)
- [Evaluation metric](#evaluation-metric)
- [Feature family](#feature-family)
- [Fold pass rate](#fold-pass-rate)
- [Gradient boosting](#gradient-boosting)
- [Grid search](#grid-search)
- [Horizon](#horizon)
- [Hyperparameter](#hyperparameter)
- [k-fold cross-validation](#k-fold-cross-validation)
- [Logistic regression](#logistic-regression)
- [MACD](#macd)
- [MAE](#mae)
- [Money Flow Index](#money-flow-index)
- [Multiple comparisons](#multiple-comparisons)
- [Nested cross-validation](#nested-cross-validation)
- [Overfit ratio](#overfit-ratio)
- [Paper trade](#paper-trade)
- [Preset](#preset)
- [Purge](#purge)
- [Random forest](#random-forest)
- [Random search](#random-search)
- [Relative volume](#relative-volume)
- [Response variable](#response-variable)
- [Resubstitution](#resubstitution)
- [Retraining frequency](#retraining-frequency)
- [RMSE](#rmse)
- [Settled](#settled)
- [SIP](#sip)
- [Slippage](#slippage)
- [Spread](#spread)
- [Supertrend](#supertrend)
- [Survivorship bias](#survivorship-bias)
- [Taken and skipped](#taken-and-skipped)
- [Technical indicators](#technical-indicators)
- [Test set](#test-set)
- [Test slot](#test-slot)
- [Theil's U2](#theils-u2)
- [Three-way outcome](#three-way-outcome)
- [Timeframe](#timeframe)
- [Training set](#training-set)
- [Triple barrier](#triple-barrier)
- [Tuning grid](#tuning-grid)
- [Validation set](#validation-set)
- [Volatility](#volatility)
- [Volume](#volume)
- [Walk-forward validation](#walk-forward-validation)
- [Why this call](#why-this-call)

## After-cost return

What a trade made once the cost of buying and selling is taken off. A trade that rose 0.50 per cent and paid 0.20 per cent to enter and leave returned 0.30 per cent after cost.

*In the app.* Every figure of money is after cost, 0.20 per cent a round trip for crypto on Binance and 0.10 per cent for US stocks on Alpaca, the second measured on the operator's own paper fills.

## Amihud ratio

How far a price moves for each unit of money traded, the size of a candle's price change divided by the money that changed hands. A high ratio means a small amount of trading moves the price, so buying and selling cost more.

*In the app.* One of the two measures behind the cost floor, as the price move per million USDT or dollars traded, averaged over a day of candles.

*Read more.* Amihud, Y. (2002). Illiquidity and stock returns: cross-section and time-series effects. Journal of Financial Markets 5, 31 to 56. https://doi.org/10.1016/s1386-4181(01)00024-6

## ATR

Average true range, the typical size of a candle's move from low to high, averaged over the last 14 candles and written as a share of price. An ATR of 0.015 means the price usually moves 1.5 per cent.

*In the app.* Take-profit and stop are set in ATR, so they widen on wild coins and narrow on calm ones, and the volatility band on A1 is measured in it.

*Read more.* https://en.wikipedia.org/wiki/Average_true_range

## AUC

Area under the receiver operating characteristic curve, the chance that a randomly chosen win is rated above a randomly chosen loss. 0.5 is a coin flip and 1 is perfect ordering.

*In the app.* Reported for each model on the test year on C1.

*Read more.* https://en.wikipedia.org/wiki/Receiver_operating_characteristic

## Base rate

The share of candles whose outcome was a win, before any model is applied. A model has to beat always guessing the base rate before it has shown anything.

*In the app.* With a take-profit of 2 ATR and a stop of 1 ATR the base rate on four-hour candles was about 0.26, below the one in three a trade needs to break even.

## Block bootstrapping

Resampling a series in whole blocks of consecutive candles, with replacement, to estimate how much a score would vary on a different sample. Drawing single candles would break the time order that makes neighbouring candles alike.

*In the app.* The bootstrap design on B2 draws blocks as long as the purge or the cube root of the candles, whichever is longer, and scores the candles left out.

*Read more.* Künsch, H. R. (1989). The jackknife and the bootstrap for general stationary observations. The Annals of Statistics 17. https://doi.org/10.1214/aos/1176347265

## Break-even band

The range of returns, either side of zero, that counts as flat in a three-way outcome. A return inside it would pay no more than the trading cost.

*In the app.* Set on A1's Choose Label. 0.002 matches the 0.20 per cent crypto round trip; the three-way preset uses 0.01.

## Break-even chance

The chance of reaching the take-profit before the stop at which a trade neither makes nor loses money on average, the stop's distance divided by the stop's and the take-profit's distances together. With a take-profit of 2 ATR and a stop of 1 ATR it is 1 in 3.

*In the app.* A win-or-loss model's rating must beat it for a trade to be taken; the Why this call line gives both numbers.

## Calibration

Whether a model's stated chances match what happens. A well calibrated model that says 30 per cent is right about 30 per cent of the time.

*In the app.* The Performance Log on C2 sets each preset's expected move after cost against what its paper trades made, by confidence fifth; points on the dashed line mean the forecasts were right on average.

*Read more.* Niculescu-Mizil, A. and Caruana, R. (2005). Predicting good probabilities with supervised learning. Proceedings of the 22nd International Conference on Machine Learning, 625 to 632. https://doi.org/10.1145/1102351.1102430

## Candle

One period of price history, its open, high, low and close and the volume traded, over one timeframe. A 4-hour candle is four hours of trading.

*In the app.* Every setting counted in time, the horizon, the history to load, the purge and the embargo, is counted in candles.

## Confidence group

Which fifth of the test year's ratings a new rating falls in, from 1, the least confident, to 5, the most. What that fifth earned after cost in the test year is the trade's expected move.

*In the app.* Shown on each paper trade and in its Why this call line.

## Confidence interval

A range that would contain the true value in a stated share of repeated samples, most often 95 per cent. A narrow interval that stays above zero is evidence; a wide one crossing zero is not.

*In the app.* The confirmed-best rule asks for a 95 per cent interval of a configuration's mean after-cost return that lies wholly above zero.

## Confirmed best

The configuration the app may call the best, by a rule fixed on 26 September 2026 before any result arrived. It needs at least 30 independent trades, a 95 per cent confidence interval above zero widened for multiple comparisons, and taken trades beating skipped ones; among those that qualify, the highest lower bound wins.

*In the app.* The status column of the calibration table on C2. The rule is `05-research/research/confirmed-best-rule.md`.

## Corwin-Schultz spread

An estimate of the gap between buy and sell prices from the highs and lows of two consecutive candles, for data that carries no order book. A candle's high is usually a buy and its low a sell, so part of the range is the spread.

*In the app.* The second measure behind the cost floor, in per cent of price.

*Read more.* Corwin, S. A. and Schultz, P. (2012). A simple way to estimate bid-ask spreads from daily high and low prices. The Journal of Finance 67, 719 to 760. https://doi.org/10.1111/j.1540-6261.2012.01729.x. Brauneis, A., Mestel, R., Riordan, R. and Theissen, E. (2021). How to measure the liquidity of cryptocurrency markets? Journal of Banking and Finance 124, 106041. https://doi.org/10.1016/j.jbankfin.2020.106041

## Cost floor

A filter that drops the candles most expensive to trade, those whose Corwin-Schultz spread or Amihud ratio is above a percentile of the run's own training candles. It replaced a fixed floor of 30 million USDT a day on 26 September 2026.

*In the app.* A1's Choose Filter, at the 80th percentile by default, which drops the costliest fifth.

## Edge

How much better the trades a model takes do than the ones it skips, the average after-cost return of taken trades minus that of skipped trades. Positive means the model's choices beat its rejections.

*In the app.* The Edge tile on C2.

## Edge floor

The smallest expected move after cost a trade must have to be taken. A trade whose expected move is below it is skipped, however high its rating.

*In the app.* A1's Choose Filter, 0 per cent by default, which skips any trade expected to lose money.

## Elastic net

A logistic or linear regression whose coefficients are shrunk towards zero by a mix of two penalties, lasso, which can set weak ones to exactly zero, and ridge, which shrinks them all. The mixing value sets the blend and the strength sets how hard.

*In the app.* The model of the Quick and simple preset, and the variable screen on B1.

*Read more.* Zou, H. and Hastie, T. (2005). Regularization and variable selection via the elastic net. Journal of the Royal Statistical Society Series B 67, 301 to 320. https://doi.org/10.1111/j.1467-9868.2005.00503.x

## EMA

Exponential moving average, an average of recent closes in which newer candles count more than older ones.

*In the app.* Several of the indicator families compare a fast, a middle and a slow EMA, and the Supertrend lines use a 200-candle EMA.

*Read more.* https://en.wikipedia.org/wiki/Moving_average

## Embargo

A gap of candles left out between the last training candle and the test set, so effects running on past the training window cannot leak into the test. López de Prado places it after each validation block; in this app the test set comes last, so the gap sits before it.

*In the app.* B2's Choose Train-Test Split; 0 uses the horizon.

*Read more.* López de Prado, M. (2018). Advances in Financial Machine Learning. Wiley. ISBN 978-1-119-48208-6.

## Evaluation metric

How predictions are scored against outcomes, kept apart from the response variable, which is what is predicted.

*In the app.* A win-or-loss run is scored by the RMSE of its predicted chance of a win, a three-way run by log loss, and every run also reports the after-cost return of its most confident fifth.

## Feature family

A group of input columns built the same way and named by a shared prefix, such as f_wc_ for windows measured in days, f_hr_ for the shorter intraday windows, f_ta_ for the in-house oscillators, f_st_ for the Supertrend lines, f_btc_ for strength against bitcoin, f_rv_ for relative volume and f_cost_ for trading cost.

*In the app.* Chosen on C1's Choose Features; nothing ticked offers every family.

## Fold pass rate

The share of cross-validation folds in which a model beats always guessing the base rate, a Theil's U2 under 1 on that fold. It measures how stable a model is across time periods, not how accurate it is.

*In the app.* A1's Choose Ranking. It is reported against its bar and does not reject a model.

## Gradient boosting

A model built from many small decision trees added one at a time, each fitted to the errors the trees before it left. LightGBM and histogram gradient boosting are fast versions that bin the inputs first.

*In the app.* LightGBM, histogram boosting and gradient boosting are three of the six learners on C1; LightGBM runs the three-way preset.

## Grid search

Trying every combination of a model's settings from a list of values, and keeping the one that scores best on validation.

*In the app.* The Light and Standard tuning levels on C1.

## Horizon

How many candles ahead a trade's outcome is judged. A trade still open at the horizon closes there.

*In the app.* A1's Choose Label, 12 candles by default; the three-way preset uses 24 daily candles.

## Hyperparameter

A setting of a model chosen before it is fitted, not learned from the data, such as the number of trees in a random forest or the strength of an elastic net's penalty.

*In the app.* Set one by one under Advanced model building on C1, or searched with a tuning level.

## k-fold cross-validation

Splitting data into k blocks and scoring each block with a model fitted on the others. On candles the blocks must be walk-forward, never random, or the model learns from the future.

*In the app.* B2 offers k-fold and its repeated form beside walk-forward, to show how much a random split flatters a score.

*Read more.* Bergmeir, C. and Benítez, J. M. (2012). On the use of cross-validation for time series predictor evaluation. Information Sciences 191, 192 to 213. https://doi.org/10.1016/j.ins.2011.12.028

## Logistic regression

A model that turns a weighted sum of its inputs into a chance between 0 and 1 of an outcome. Simple, fast and hard to overfit.

*In the app.* The steadiest learner on the test year in the three-way search of 26 September 2026, beating taking every candle in 25 of 32 combinations.

## MACD

Moving average convergence divergence, the gap between a fast and a slow EMA of the close, with a signal line that is an EMA of that gap. The gap crossing its signal line is read as a change in momentum.

*In the app.* A2's Choose MACD sets its spans, a noise band and how many candles confirm a crossing.

*Read more.* https://en.wikipedia.org/wiki/MACD

## MAE

Mean absolute error, the average size of a miss with every miss counted once.

*In the app.* One of the Model scores metrics on C2, in percentage points of the predicted chance of a win.

*Read more.* Hyndman, R. J. and Koehler, A. B. (2006). Another look at measures of forecast accuracy. International Journal of Forecasting 22, 679 to 688. https://doi.org/10.1016/j.ijforecast.2006.03.001

## Money Flow Index

An oscillator that weighs price by volume over the last 14 candles, from 0 when all the money went into falling candles to 1 when all went into rising ones. Near 1 is overbought and near 0 oversold.

*In the app.* The money flow gate on A1's Choose Filter, off by default. On all 20 demo stocks a gate at 0.5 raised what every kept candle earned; on crypto it did not.

*Read more.* https://en.wikipedia.org/wiki/Money_flow_index

## Multiple comparisons

The more configurations are tested, the more likely one looks good by chance. Correcting for it widens each confidence interval; the Bonferroni correction tests each of k configurations at 5 per cent divided by k.

*In the app.* The confirmed-best rule applies a Bonferroni correction across every configuration with 30 independent trades.

*Read more.* https://en.wikipedia.org/wiki/Bonferroni_correction

## Nested cross-validation

Choosing a model's settings inside an inner cross-validation and scoring the chosen settings on an outer set the inner loop never saw, so the reported score is not flattered by the search.

*In the app.* Tuning chooses settings on the validation folds inside the training years and scores the winner once on the test year, which is the outer set.

*Read more.* Varma, S. and Simon, R. (2006). Bias in error estimation when using cross-validation for model selection. BMC Bioinformatics 7. https://doi.org/10.1186/1471-2105-7-91

## Overfit ratio

Cross-validated RMSE divided by training RMSE. Near 1 the model does as well on candles it has not seen as on those it learned from; above 1.1 it has learned noise and is rejected.

*In the app.* The overfit bar on C1, and the Overfit ratio tab of Model scores on C2.

## Paper trade

A trade recorded but never placed with a broker. It records a decision at the moment it was made and is checked against real prices when its horizon ends.

*In the app.* Every run issues one paper trade per symbol, taken or skipped, listed on C2.

## Preset

A saved set of every setting, filled in with one tap. The app has three, Best on record, Three-way outcome and Quick and simple, each in a crypto and a stock version. Editing any setting by hand ends the preset.

*In the app.* Quick start on the home page and A1.

## Purge

Candles removed from the training set because their outcome window overlaps the validation period. A candle's label looks ahead by the horizon, so without purging, training data would contain information about validation outcomes.

*In the app.* B2's Choose Training Regime; the horizon is the safe value.

*Read more.* López de Prado, M. (2018). Advances in Financial Machine Learning. Wiley. ISBN 978-1-119-48208-6.

## Random forest

Many decision trees, each grown on a random sample of the candles and of the inputs, whose votes are averaged. Averaging many noisy trees gives a steadier answer than any one tree.

*In the app.* The model of the Best on record preset.

*Read more.* Breiman, L. (2001). Random forests. Machine Learning 45, 5 to 32. https://doi.org/10.1023/a:1010933404324

## Random search

Trying a random sample of the combinations in a grid rather than all of them. Over the same ranges it usually matches a full grid in far fewer fits.

*In the app.* The Thorough tuning level on the slower models.

*Read more.* Bergstra, J. and Bengio, Y. (2012). Random search for hyper-parameter optimization. Journal of Machine Learning Research 13, 281 to 305. https://jmlr.org/papers/v13/bergstra12a.html

## Relative volume

A candle's volume divided by its normal volume, the average for the same time slot over the past 20 days, so 2 is twice normal. It compares like with like, because volume rises and falls through every day.

*In the app.* A model input whenever its feature family is offered, which is every run that leaves the families on C1 unticked, and a rule on A1's Choose Filter, off until tested.

*Read more.* `05-research/research/volume/volume-selection-research-2026-09-26.md`

## Response variable

What the model predicts, kept apart from the evaluation metric, which is how the prediction is scored.

*In the app.* A1's Choose Label. Barrier is win or loss; three-way is up, down or flat over the horizon.

## Resubstitution

Scoring a model on the same data it was fitted on, which overstates how well it will do on new data.

*In the app.* The Full RMSE on C1 is the resubstitution error; the overfit ratio compares it with the validation error.

## Retraining frequency

How often a model is fitted again on fresh data.

*In the app.* A model is fitted anew every time a run starts, and every four hours by the scheduled scan; nothing is carried over between runs.

## RMSE

Root mean squared error, the average size of a miss with big misses counted harder, because each is squared first. When RMSE is much bigger than MAE the model is sometimes very wrong rather than steadily slightly wrong.

*In the app.* The evaluation metric of a win-or-loss run and a Model scores tab on C2.

## Settled

A paper trade whose horizon has ended, or whose target or stop was hit first, with its result after cost recorded.

*In the app.* Settled hourly by a scheduled job; C2's Settled tile counts them.

## SIP

The securities information processor, the consolidated feed that carries trades from every US exchange. Alpaca's free plan shows only the IEX exchange in real time, which understates a stock's volume; its paid plan carries the SIP feed.

*In the app.* Stock prices come from the SIP feed where the account has it.

*Read more.* https://docs.alpaca.markets/docs/about-market-data-api

## Slippage

The difference between the price expected when an order is sent and the price it fills at.

*In the app.* Measured at 5.0 basis points a fill on the operator's own Alpaca paper orders, part of the 0.10 per cent stock cost.

## Spread

The gap between the best price to buy and the best price to sell at one moment. Buying and selling at once loses the spread.

*In the app.* Estimated from candle ranges by the Corwin-Schultz method and judged by the cost floor.

*Read more.* https://en.wikipedia.org/wiki/Bid%E2%80%93ask_spread

## Supertrend

A trailing line set a multiple of ATR below or above the price that flips side when the price crosses it, used to read the direction of a trend.

*In the app.* Three Supertrend lines are among the indicator families on A2.

## Survivorship bias

The flattering error of testing only on coins or stocks that still exist today, which leaves out those that failed. The crypto history here includes delisted coins.

*In the app.* The A1 Screening table.

*Read more.* https://en.wikipedia.org/wiki/Survivorship_bias

## Taken and skipped

The two decisions a run makes for each symbol. Taken means the model ranked it among its best and its expected move after cost cleared the edge floor; skipped means it did not.

*In the app.* The Call column and the Taken against skipped chart on C2.

## Technical indicators

Formulas that turn a candle's price and volume history into a reading of trend or momentum. The app's feature families carry, among others, the average directional index, ADX, with its directional movement lines, DMI, for trend strength; the commodity channel index, CCI; the Chaikin money flow, CMF; the Chande momentum oscillator, CMO; the MESA adaptive moving average, MAMA; the percentage price oscillator, PPO, a MACD in per cent; the parabolic SAR, a trailing stop and reverse; TRIX, the rate of change of a triple-smoothed EMA; the ultimate oscillator, ULTOSC; Williams %R; the stochastic oscillator; and Aroon.

*In the app.* The f_ta_, f_ta_pta_ and f_tl_ families on C1, and the indicator settings on A2.

*Read more.* https://en.wikipedia.org/wiki/Technical_indicator

## Test set

Candles set aside before any validation and scored once, at the end. Nothing that chooses a model may look at them.

*In the app.* The final year, 365 days by default, on B2's Choose Train-Test Split.

## Test slot

A configuration drawn from a grid of learner, response variable, timeframe and horizon, run by the scheduled scan so the whole grid is forward-tested, not only the presets. Each scan picks the one with the fewest paper trades so far.

*In the app.* The calibration table on C2.

## Theil's U2

A model's error divided by the error of a simple benchmark, here always predicting the average outcome. Below 1 the model beats that constant guess. Theil's U1 is a related measure bounded between 0 and 1.

*In the app.* A Model scores tab on C2 and the test of each fold in the fold pass rate.

## Three-way outcome

A response variable with three classes, whether the price ends the horizon up, down or flat, where flat is inside the break-even band.

*In the app.* The Three-way outcome preset.

## Timeframe

The length of one candle. The app offers 15 minutes to 1 day for crypto and 1 day for stocks.

*In the app.* A1's Choose Market.

## Training set

The candles a model is fitted on.

*In the app.* Every candle before the test set, less the embargo.

## Triple barrier

A win-or-loss label with three barriers, a take-profit above, a stop below and a time limit, the horizon. The trade is a win if the take-profit is reached before the stop within the horizon.

*In the app.* The barrier response variable, with the take-profit and stop set in ATR on A1's Choose Label.

*Read more.* López de Prado, M. (2018). Advances in Financial Machine Learning. Wiley. ISBN 978-1-119-48208-6.

## Tuning grid

The list of hyperparameter values a search tries. A bigger grid finds better settings on validation and flatters the validation score more, which is why the test set is kept out of tuning.

*In the app.* Light, Standard, Thorough or Custom on C1's Choose Grid Search, with the number of fits and a rough time shown.

## Validation set

Data held out while choosing among models or settings, to compare candidates and guard against overfitting. It is not the test set.

*In the app.* The walk-forward folds inside the training years.

## Volatility

How far a price typically moves, measured here by ATR as a share of price.

*In the app.* A1's volatility band. Below it moves are too small to cover trading costs; above it ordinary swings hit the stop.

## Volume

How much of a coin or stock changed hands, in USDT for crypto and dollars for stocks.

*In the app.* Behind relative volume, the Amihud ratio and the money flow gate.

## Walk-forward validation

Training on earlier candles and validating on the next block, then moving forward through time. It is the standard design for time series, because random folds would let the model learn from the future.

*In the app.* The expanding and rolling designs on B2's Choose Training Regime; repeats shift where the folds start.

## Why this call

The reason a paper trade was taken or skipped, from the checks the model's rating had to pass. A user's run applies four: the win chance beats the break-even chance (or, for three-way, a rise is likelier than a fall), the candle passes the cost, volume and money-flow filters, the expected move clears the edge floor, and the coin ranks in the run's top third. The scheduled scans apply the first three. A skipped trade names the checks it failed.

*In the app.* The last column of C2's Paper trades table and the hover text on the Forecast card. Trades made before 30 September 2026 did not save the filter or ranking checks, so their line works out the rest from what they stored.
