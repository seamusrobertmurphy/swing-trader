# Volume in selection

Written 26 September 2026 for the swing-trader app, on how to use trading volume to choose coins and stocks. Every paper below was checked against CrossRef, and every finding is taken from the paper's own abstract. The Binance and Alpaca points were read from their documentation on the same day.

The note runs in six parts. It says what volume is for, what the app does now and why that falls short, what the research says for crypto and then for US stocks, how relative volume should be measured on each timeframe, and what to test.

## Two jobs

Volume answers two different questions, and each needs a different measure.

The first question is whether a trade is safe and cheap. A thinly traded coin or stock has a wide gap between the best buy and sell prices, so an order fills worse on the way in and again on the way out, and a small amount of money can push the price through a stop. This is about size, so an amount measure fits it, but the amount that counts as safe differs by market.

The second question is whether something is happening now. A coin or stock trading far more than usual is being noticed, and that often comes with a real move. This is about change, so it must be measured against the symbol's own normal level, which is relative volume.

## What we do now

The app uses fixed amounts only, and nothing relative.

1. The coins a user can pick must trade at least 10 million USDT a day on their 30-day median and have two years of history. That gives 27 coins.
2. A crypto candle is used only if its coin traded at least 30 million USDT in the 24 hours before it. A stock candle needs 20 million dollars a day.

This falls short for three reasons. A fixed amount ignores how the whole market's volume rises and falls over the years; in 2026 only 3 per cent of Binance pair-days cleared 30 million, against 29 per cent in 2021. It ignores the timeframe, because a 15-minute candle and a daily candle carry very different amounts. And it measures size, not the change in activity that most of the research below is about.

## Crypto

Binance reports, for every candle, the volume in the coin itself, the volume in USDT, the number of trades, and the volume bought by takers, the traders who crossed the spread to buy at once. Candles run from 1 second to 1 month, and they are counted in UTC unless a time zone is asked for (Binance, Kline candlestick data, https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints).

Reported volume can be false. Cong et al. (2023) tested 29 exchanges and found that wash trading, trades a party makes with itself to inflate volume, averaged over 70 per cent of reported volume on the unregulated ones. The number of trades and the taker-buy share are useful cross-checks, because inflated volume shows up as odd trade sizes and counts.

The cost of trading can be measured directly from candles. Brauneis et al. (2021) compared cheap liquidity measures against high-frequency order-book liquidity in crypto. The Corwin and Schultz (2012) and Abdi and Ranaldo spread estimates tracked changes in liquidity best, on every timeframe, venue and coin tested; the Amihud (2002) ratio, a candle's price move divided by the money traded, and the Kyle and Obizhaeva estimate were best for the level of liquidity. So the safety job is better done with a cost measure than with a volume amount.

Crypto volume has a daily shape even though the market never closes. Eross et al. (2019) found that bitcoin volume rises through the day and falls from about 4 pm until midnight GMT, and that liquidity is highest when the major stock markets open. Relative volume on hourly or shorter candles must therefore compare the same hour of the day.

Low activity changes what pays. Bianchi et al. (2022) found that the returns from short-term reversal, buying recent losers, sit mostly in crypto pairs with lower activity, and that past returns combined with volume predict returns. Liu et al. (2022) found that three factors, the crypto market, size and momentum, explain crypto returns across coins.

## US stocks

On Alpaca the free plan shows real-time stock data from the IEX exchange alone, and the paid plan covers all US exchanges, the consolidated feed known as SIP; the free plan's history also excludes the latest 15 minutes (Alpaca, About Market Data API, https://docs.alpaca.markets/docs/about-market-data-api). IEX is one exchange among many, so volume from IEX alone understates a stock's real volume. The app's stock prices come from the consolidated feed where the account has it.

Stock volume has a strong daily shape. Jain and Joh (1988) found that average New York Stock Exchange volume differs by hour of the day and by day of the week, and that volume and returns move together, the relation being steeper for rising prices. Admati and Pfleiderer (1988) explained why trading bunches at certain times.

Unusual volume carries information. Gervais et al. (2001) found that stocks with unusually high volume over a day or a week tend to rise over the following month, and those with unusually low volume tend to fall. Lee and Swaminathan (2000) found that past turnover, shares traded as a share of shares outstanding, predicts how large and how lasting price momentum is. Llorente et al. (2002) found that price moves on trading driven by information tend to continue, while moves on trading driven by hedging tend to reverse.

A practitioner guide makes the same point in plain terms. Mitchell (2026) measures volume against the stock's own average of the last 20 to 30 candles, treats a breakout on rising relative volume as more likely to continue, notes that very low relative volume often comes before a sharp move, and describes volume at 5 to 20 times its average on funds as a sign of a turning point (Trade That Swing, In-Depth Guide to Trading Stocks Based on Volume and Volume Analysis, saved in this folder).

## Relative volume

Relative volume is this candle's volume divided by what is normal for this symbol. What counts as normal depends on the timeframe.

1. Daily and longer candles. Divide today's volume by the average of the last 20 to 30 daily candles.
2. Candles shorter than a day. Divide this candle's volume by the average volume of the same time of day over the last 20 to 30 days, because volume rises and falls through every day, in stocks and in crypto.
3. Stocks during the session. Compare the volume so far today with the average volume by the same time on past days, which is how day traders find unusual activity early.
4. Across symbols. Rank relative volume across the whole market on each candle, so that a busy day for everything does not make every symbol look unusual.

For stocks, turnover is a fairer size measure than share count, because it allows for how many shares exist.

## What to test

The research points to two layers, each measured the right way and each tested on after-cost returns before it is used.

1. A safety floor measured as cost, using the Corwin and Schultz spread estimate and the Amihud ratio, with the cut set as a percentile within each market and timeframe, so crypto and stocks each get their own bar.
2. Relative volume as an input to the model and as a candidate entry rule, measured for the timeframe as above, with the same hour of day compared on intraday candles.

This belongs with the intraday data work in revision task 4, because relative volume by time of day needs candles shorter than a day.

## Search question

A question for further searching, with its context.

Context. A swing and day trading model trades spot crypto on Binance and US stocks through Alpaca, on candles from 15 minutes to 1 day, long only. It needs a volume measure for choosing symbols that works across both markets and every timeframe.

Question. How should relative trading volume be defined and normalised for symbol selection across candle timeframes from intraday to daily, adjusting for time-of-day seasonality in US equities and in 24-hour crypto markets, and what thresholds or percentile ranks do empirical studies find predict continuation or reversal after trading costs?

## References

Admati, A. R. and Pfleiderer, P. (1988). A theory of intraday patterns: volume and price variability. Review of Financial Studies 1, 3 to 40. https://doi.org/10.1093/rfs/1.1.3

Amihud, Y. (2002). Illiquidity and stock returns: cross-section and time-series effects. Journal of Financial Markets 5, 31 to 56. https://doi.org/10.1016/s1386-4181(01)00024-6

Bianchi, D., Babiak, M. and Dickerson, A. (2022). Trading volume and liquidity provision in cryptocurrency markets. Journal of Banking and Finance 142, 106547. https://doi.org/10.1016/j.jbankfin.2022.106547

Brauneis, A., Mestel, R., Riordan, R. and Theissen, E. (2021). How to measure the liquidity of cryptocurrency markets? Journal of Banking and Finance 124, 106041. https://doi.org/10.1016/j.jbankfin.2020.106041

Cong, L. W., Li, X., Tang, K. and Yang, Y. (2023). Crypto wash trading. Management Science 69, 6427 to 6454. https://doi.org/10.1287/mnsc.2021.02709

Corwin, S. A. and Schultz, P. (2012). A simple way to estimate bid-ask spreads from daily high and low prices. The Journal of Finance 67, 719 to 760. https://doi.org/10.1111/j.1540-6261.2012.01729.x

Eross, A., McGroarty, F., Urquhart, A. and Wolfe, S. (2019). The intraday dynamics of bitcoin. Research in International Business and Finance 49, 71 to 81. https://doi.org/10.1016/j.ribaf.2019.01.008

Gervais, S., Kaniel, R. and Mingelgrin, D. H. (2001). The high-volume return premium. The Journal of Finance 56, 877 to 919. https://doi.org/10.1111/0022-1082.00349

Jain, P. C. and Joh, G. (1988). The dependence between hourly prices and trading volume. Journal of Financial and Quantitative Analysis 23, 269. https://doi.org/10.2307/2331067

Lee, C. M. and Swaminathan, B. (2000). Price momentum and trading volume. The Journal of Finance 55, 2017 to 2069. https://doi.org/10.1111/0022-1082.00280

Liu, Y., Tsyvinski, A. and Wu, X. (2022). Common risk factors in cryptocurrency. The Journal of Finance 77, 1133 to 1177. https://doi.org/10.1111/jofi.13119

Llorente, G., Michaely, R., Saar, G. and Wang, J. (2002). Dynamic volume-return relation of individual stocks. Review of Financial Studies 15, 1005 to 1047. https://doi.org/10.1093/rfs/15.4.1005
