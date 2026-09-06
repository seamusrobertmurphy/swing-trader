# Synthesis: quant methods for a long-only swing book

A distillation of what the source material in this folder (Thorp's AQR interview, the Macro Ops profile, Derman and Taleb on dynamic replication, the two Black-Scholes tutorial transcripts) means for a paper-trading long-only US equity book on a weekly horizon, supplemented with the foundational literature the sources implicitly rest on.

The strategy here does not trade options or leverage. Most of the derivatives apparatus does not apply directly. What carries over is the discipline: how to size, when to act, when to stand down, what to ignore, and how to keep a model from masquerading as a fact.

## 1. Edge must be demonstrable before it is taken

Thorp's repeated insistence is that no trade should be entered unless a rational case can be made that survives the trader's own attempt to break it. The act of failing to break the thesis is itself the evidence of edge. Buffett's "fat pitch" line and the Macro Ops gloss on it carry the same content. The cost of skipping a real edge is small; the cost of trading a phantom edge is unbounded.

Application: every new-position write-up in `research-log.md` carries a one-paragraph affirmative case and a one-paragraph devil's advocate against it. If the rebuttal lands, the entry stands down and the hesitation gets journaled in `learnings.md`.

Reference: Thorp, *A Man for All Markets* (2017), ch. 18. AQR interview, p. 10.

## 2. Size by Kelly, then halve

The Kelly criterion (Kelly 1956; Thorp 1969, 2006) sets the bet fraction that maximises long-run logarithmic wealth growth as f* = (pb − q) / b, where p is win probability, q = 1 − p, and b is the reward-to-risk ratio. For a typical long-only equity setup with an honest p around 0.55 and b around 1.5 (winners run to trailing stop, losers cut at hard stop), full Kelly is roughly 25% per position. Full Kelly is also the precise threshold at which a single estimation error in p or b destroys decades of compounding. Thorp, MacLean and Ziemba (2011) document why professionals run half-Kelly or less: half-Kelly captures roughly three-quarters of the geometric return at half the variance. Quarter-Kelly is appropriate when the edge is freshly hypothesised rather than seasoned.

Application: the 5% notional cap is a ceiling, not a default. Within the cap, position size is half-Kelly when the entry criteria fully fire and quarter-Kelly when only the minimum count fires. Kelly inputs are written down in the entry log so they can be back-graded against realised outcomes in the weekly review.

Reference: Kelly, "A New Interpretation of Information Rate," *Bell System Technical Journal* (1956). MacLean, Thorp, and Ziemba, *The Kelly Capital Growth Investment Criterion* (World Scientific, 2011).

## 3. Tails are fatter than the model assumes

The Black-Scholes derivation assumes geometric Brownian motion and a constant, known volatility. The first BS tutorial in this folder shows the lognormal mean and standard deviation cleanly. Derman and Taleb (2005) lay out why the lognormal assumption fails in practice: implied volatility smiles, transaction costs, discontinuous prices, and fat tails that GBM cannot describe. Mandelbrot's earlier work on stable distributions in cotton prices, and Bouchaud and Potters on power-law tails, are the deeper canon here.

The practical consequence for a long-only book is that the 7% hard stop is not a guarantee of a 7% loss. Earnings gaps, regulatory news, and crash mornings move price discontinuously through stops. Sizing must survive the gap-through-stop case.

Application: position sizing assumes that any single overnight could open down 15% on a name, and that two correlated names could open down simultaneously. The daily 3% circuit is calibrated against that case, not against a Gaussian one-day move.

Reference: Derman and Taleb, "The Illusions of Dynamic Replication," *Quantitative Finance* (2005). Taleb, *Dynamic Hedging* (Wiley, 1997). Mandelbrot, "The Variation of Certain Speculative Prices," *Journal of Business* (1963).

## 4. Drawdowns shrink the book, not just block new orders

Thorp's account of his trend-following operation (in *Hedge Fund Market Wizards*, quoted in the Macro Ops piece) describes a graduated response: at a 5% drawdown the program begins reducing positions, and reduces a further increment with each additional 1% drawdown. The program shuts itself down as the hole deepens, then earns its way back out. This is harder than a binary circuit but produces gentler equity curves and avoids the one-day disaster scenario where the binary halt fires after the damage is already done.

Application: the existing daily 3% circuit stays. Layered on top, a rolling weekly drawdown ramp begins shrinking new-position size below −5% and adds a 1:1 reduction with each further 1%. Recovery reverses the ramp.

Reference: *Hedge Fund Market Wizards* (Schwager, Wiley, 2012), ch. on Thorp. Also relevant: Magdon-Ismail and Atiya, "Maximum Drawdown," *Risk* (2004).

## 5. Anchoring is the cheapest mistake to avoid

Thorp's Electric Autolite anecdote and the broader Tversky-Kahneman literature on anchoring point at the same trap: traders treat their own purchase price as if it were a feature of the security. It is not. The market does not know the cost basis and does not care.

Application: every hold/sell discussion in `trade-log.md` references forward expected value, not entry price. The only legitimate uses of cost basis are mechanical: computing the 7% hard stop, computing realised P&L for the journal, and computing tax lot accounting if the strategy ever goes live.

Reference: Tversky and Kahneman, "Judgment under Uncertainty: Heuristics and Biases," *Science* (1974). Thorp, *A Man for All Markets*, ch. 6.

## 6. Filter the noise with the implied move

Thorp notes that SPY's expected daily move is approximately VIX divided by the square root of 252 (the trading-day count). Daily price changes within that band carry no information that should change a thesis. Most financial-press copy explains moves an order of magnitude smaller than the implied band.

Application: during the pre-market and midday routines, the noise filter is computed as ImpliedDailyMove = VIX / 15.87. SPY-level moves inside ±0.7 of that figure are not thesis-relevant. Single-name moves are evaluated against the name's own implied volatility where available, otherwise against an assumed 1.5× SPY beta.

Reference: Thorp, *A Man for All Markets*, ch. 19. Hull, *Options, Futures, and Other Derivatives* (10th ed.), ch. on volatility.

## 7. Correlation budget, not just sector cap

Markowitz (1952) is the original source: portfolio variance depends on pairwise covariances, not on individual variances alone. Thorp's correlation-matrix discipline (the 60-day window cited in *HFMW*) is a tractable approximation. Two long positions with 0.85 correlation between them are one position dressed for two.

Application: a 60-day pairwise correlation matrix is computed each Friday in the weekly review. Holdings are grouped into clusters at ρ > 0.7. The aggregate weight of any single cluster is capped at 20% of equity. This sits in addition to the existing 30% GICS-sector cap; the latter catches obvious concentration, the former catches the subtle case where two different sectors are moving together.

Reference: Markowitz, "Portfolio Selection," *Journal of Finance* (1952). Sharpe, "Mutual Fund Performance," *Journal of Business* (1966).

## 8. Circle of competence is a written list, not a feeling

Buffett's phrase, Thorp's reformulation, and the Macro Ops gloss all carry the same content. The agent should not trade what it cannot evaluate. Without a written list this becomes elastic and rationalises every interesting name.

Application: `memory/strategy.md` maintains a competence whitelist of sectors and themes. Entries outside the list are journaled in `learnings.md` as observations and not as trades. The list is reviewed on Fridays and expanded only after the agent has watched, but not traded, an outside-the-list name for at least one full earnings cycle.

Reference: Buffett, 1996 Berkshire shareholder letter. Thorp, AQR interview, p. 18.

## 9. Fat pitches override the cap, never the principles

Thorp's 1987 arbitrage, the Kovner oil tanker, the SPAC-discount trade, and the gold-futures calendar spread are all events where Thorp committed capital outside the routine sizing because the dislocation made the asymmetry undeniable. None of them broke his rules on edge, leverage, or worst-case tolerability. They broke the size cap because the underlying R:R justified it.

Application: a fat-pitch entry may stretch one position to 10% of equity, double the normal cap. The entry must document, in the same trade-log entry, three things: an asymmetric R:R of at least 3:1, a structural cause for the dislocation (panic flow, forced selling, capital constraint at intermediaries), and a written exit condition. Without all three, the cap stays at 5%.

Reference: Thorp, *A Man for All Markets*, chs. 21-23. Pedersen, *Efficiently Inefficient* (Princeton, 2015), ch. on event-driven strategies.

## 10. Lognormal arithmetic, not arithmetic arithmetic

The first BS tutorial in this folder works the lognormal explicitly: prices distribute lognormally, mean and standard deviation are computed on log returns, and the arithmetic average of percent returns overstates compound growth by approximately half the variance. This matters when projecting multi-month outcomes from weekly samples.

Application: weekly review computes geometric and arithmetic mean returns separately and reports both. Forward projections of equity paths use the geometric mean. The variance drag (σ²/2) is recorded as a line item alongside the headline return.

Reference: the lognormal foundation traces to Bachelier (1900) and Samuelson (1965). For the arithmetic-vs-geometric gap, see Hughson, Stutzer, and Yung, "The Misuse of Expected Returns," *Financial Analysts Journal* (2006).

## 11. Cross-check beats model worship

Derman and Taleb's central point in the dynamic-replication paper is that practitioners do not in fact lean on the elaborate continuous-hedging derivation; they price by static replication and put-call parity, then use the model as an interpolation device. The general principle for a discretionary book is that two simple consistency checks usually beat one elaborate one.

Application: any new-position write-up triangulates among at least two of: peer-group EV/EBITDA or P/FCF multiple, an owner-earnings yield against the 10-year Treasury, and a replacement-cost or sum-of-the-parts cross-check. Single-method valuations are flagged for additional scrutiny.

Reference: Derman and Taleb (2005), in this folder. Also Damodaran, *Investment Valuation* (Wiley), on triangulation across approaches.

## 12. Factor tilts compound silently

A long-only book sitting on six names is also an implicit factor portfolio. Fama and French (1992, 1993), Jegadeesh and Titman (1993), Carhart (1997), and Asness, Moskowitz, and Pedersen (2013) document that value, size, momentum, quality, and low-volatility tilts compound over multi-year horizons in directions that may or may not be intended. A discretionary book that drifts into a single factor concentration without noticing is taking a large bet it never argued for.

Application: the Friday weekly review computes, for each holding, a coarse factor exposure (value, momentum, quality, size) and aggregates them against SPY. Unintended factor concentrations above an absolute book-vs-SPY tilt of 0.3 are flagged in `weekly-review.md` and resolved in the next two weeks of new entries.

Reference: Fama and French, "The Cross-Section of Expected Stock Returns," *Journal of Finance* (1992). Asness, Moskowitz, and Pedersen, "Value and Momentum Everywhere," *Journal of Finance* (2013). Ilmanen, *Expected Returns* (Wiley, 2011).

## What this changes, concretely

The existing hard rules survive intact. What sits on top of them is the texture: sizing within the cap is now Kelly-informed, drawdowns ramp the book down before they halt it, anchoring is named and prohibited, news is filtered against the implied move, correlation is budgeted alongside sectors, competence is written rather than felt, dislocations have a separate playbook, returns compound in log space, valuations triangulate, and factor tilts get measured. None of this requires touching the broker contract, the routine schedule, or the secrets layer. All of it lives in `CLAUDE.md` as principles and in the next Friday review as proposed strategy edits.
