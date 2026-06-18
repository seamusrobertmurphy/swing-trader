# Authoritative references

A curated reading list. The four sources already in this folder (Thorp AQR interview, Macro Ops profile, Derman and Taleb on dynamic replication, the BS tutorials) anchor the synthesis. The works below are the canon they implicitly rest on. Citations are written so they can be found in Google Scholar or a library catalogue without further work.

## Sizing and growth-optimal betting

- Kelly, J. L. (1956). "A New Interpretation of Information Rate." *Bell System Technical Journal* 35(4), 917-926. The original. Derived from information theory, not utility theory.
- Thorp, E. O. (1969). "Optimal Gambling Systems for Favorable Games." *Review of the International Statistical Institute* 37(3), 273-293. Thorp's first formal treatment for casino games.
- Thorp, E. O. (2006). "The Kelly Criterion in Blackjack, Sports Betting, and the Stock Market." In *Handbook of Asset and Liability Management*, vol. 1, North-Holland. The extension to equities, including the variance-drag argument for fractional Kelly.
- MacLean, L. C., Thorp, E. O., and Ziemba, W. T., eds. (2011). *The Kelly Capital Growth Investment Criterion: Theory and Practice*. World Scientific. The reference textbook.

## Portfolio theory and factor models

- Markowitz, H. M. (1952). "Portfolio Selection." *Journal of Finance* 7(1), 77-91. Covariance, not variance, drives portfolio risk.
- Sharpe, W. F. (1964). "Capital Asset Prices." *Journal of Finance* 19(3), 425-442. CAPM, single-factor.
- Fama, E. F. and French, K. R. (1992). "The Cross-Section of Expected Stock Returns." *Journal of Finance* 47(2), 427-465. Value and size premia.
- Fama, E. F. and French, K. R. (1993). "Common Risk Factors in the Returns on Stocks and Bonds." *Journal of Financial Economics* 33(1), 3-56. The three-factor model.
- Jegadeesh, N. and Titman, S. (1993). "Returns to Buying Winners and Selling Losers." *Journal of Finance* 48(1), 65-91. The momentum effect.
- Carhart, M. M. (1997). "On Persistence in Mutual Fund Performance." *Journal of Finance* 52(1), 57-82. Four-factor model with momentum.
- Asness, C. S., Moskowitz, T. J., and Pedersen, L. H. (2013). "Value and Momentum Everywhere." *Journal of Finance* 68(3), 929-985. The two largest factor premia, cross-asset.
- Ilmanen, A. (2011). *Expected Returns: An Investor's Guide to Harvesting Market Rewards*. Wiley. The practitioner reference for the empirical premia.
- Pedersen, L. H. (2015). *Efficiently Inefficient*. Princeton University Press. Strategy-by-strategy walk through what works and why.

## Market efficiency, behaviour, and the limits of EMH

- Fama, E. F. (1970). "Efficient Capital Markets: A Review of Theory and Empirical Work." *Journal of Finance* 25(2), 383-417. The strongest statement of EMH.
- Lo, A. W. (2004). "The Adaptive Markets Hypothesis." *Journal of Portfolio Management* 30(5), 15-29. EMH as a moving target.
- Lo, A. W. (2017). *Adaptive Markets: Financial Evolution at the Speed of Thought*. Princeton. Book-length treatment.
- Tversky, A. and Kahneman, D. (1974). "Judgment Under Uncertainty: Heuristics and Biases." *Science* 185(4157), 1124-1131. Anchoring, availability, representativeness.
- Kahneman, D. (2011). *Thinking, Fast and Slow*. Farrar, Straus and Giroux. The synthesis.

## Options, derivatives, and the limits of GBM

- Bachelier, L. (1900). "Théorie de la Spéculation." *Annales Scientifiques de l'École Normale Supérieure*. Brownian motion applied to prices.
- Black, F. and Scholes, M. (1973). "The Pricing of Options and Corporate Liabilities." *Journal of Political Economy* 81(3), 637-654.
- Merton, R. C. (1973). "Theory of Rational Option Pricing." *Bell Journal of Economics and Management Science* 4(1), 141-183.
- Heston, S. L. (1993). "A Closed-Form Solution for Options with Stochastic Volatility." *Review of Financial Studies* 6(2), 327-343. Volatility itself is a process.
- Dupire, B. (1994). "Pricing with a Smile." *Risk* 7(1), 18-20. Local volatility.
- Taleb, N. N. (1997). *Dynamic Hedging: Managing Vanilla and Exotic Options*. Wiley. The practitioner's account.
- Derman, E. and Taleb, N. N. (2005). "The Illusions of Dynamic Replication." *Quantitative Finance* 5(4), 323-326. In this folder.
- Mandelbrot, B. B. (1963). "The Variation of Certain Speculative Prices." *Journal of Business* 36(4), 394-419. The original fat-tail observation.
- Bouchaud, J.-P. and Potters, M. (2003). *Theory of Financial Risk and Derivative Pricing*. Cambridge. Power-law tails, non-Gaussian risk.

## Risk and drawdown

- Sortino, F. A. and Price, L. N. (1994). "Performance Measurement in a Downside Risk Framework." *Journal of Investing* 3(3), 59-64. Downside deviation as the risk metric.
- Magdon-Ismail, M. and Atiya, A. F. (2004). "Maximum Drawdown." *Risk* 17(10), 99-102. The statistical properties of the worst-loss path.
- Lopez de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley. Modern, machine-learning aware treatment of backtest pathologies and risk.

## Practitioner accounts the synthesis leans on

- Thorp, E. O. (2017). *A Man for All Markets*. Random House. The autobiography. Chapters on Princeton-Newport, the 1987 trade, SPAC-discount, and gold-futures arbitrage are the source for much of what Macro Ops summarises.
- Schwager, J. D. (2012). *Hedge Fund Market Wizards*. Wiley. The Thorp chapter is the source for the drawdown-ramp and correlation-budget anecdotes.
- Buffett, W. E. (annual). Berkshire Hathaway shareholder letters. The "circle of competence" and "fat pitch" framing.
- Damodaran, A. (2012). *Investment Valuation*, 3rd ed. Wiley. The triangulation discipline.

## Where to look for current data and method

- AQR Capital Management research library (aqr.com/Insights/Research). Open-access factor and macro research; the Ilmanen and Asness papers are usually here in working-paper form first.
- SSRN's Financial Economics Network. Most of the canonical papers above are on SSRN with full text.
- Renaissance Technologies and other quant shops do not publish. Their effective canon lives in Lopez de Prado, Cont, and the *Quantitative Finance* journal.

## How to add to this list

When a routine encounters a method, claim, or anecdote that cannot be traced to one of the references above, log it in `memory/learnings.md` with the source and a question mark, then chase the primary citation in the next session. Secondary summaries (Macro Ops, Investopedia, Substack) are starting points, not endpoints.
