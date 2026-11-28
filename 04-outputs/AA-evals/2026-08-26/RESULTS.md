# What we found on 26 August 2026

## Where the money actually is

| | |
| --- | --- |
| Account value | $98,583, from a $100,000 start |
| Change since it went live on 18 August | **-1.42%** |
| The market, same period | -0.18% |
| Was this within expectations? | Yes. The plan expected swings of about 5% a week. The book fell 6% last week and won 2.8% back today, which is the same size of swing in both directions |
| Worst single holding | AXTI, down 15.6% from what we paid. It gets sold automatically at -25% |
| What it costs us to trade | 42.6 basis points per trade, against the 5 to 10 we assumed. This is the bad news below |
| Rebalances done | 2 of the 6 we need. Monday 24 August was missed; this one ran a day late |

**This is fake money.** It is a paper account. The switch that would let it
spend real money is off.

---

## The short version

The second rebalance went through. Every one of the 31 orders filled.

Two things went wrong and both are now fixed in the code. Trading cost eleven
times what we assumed, because the orders were sent overnight and all landed in
the first six minutes of trading. And the safety rule we added last week to stop
the book being one big bet was not doing its job: it looked like it was working
and it was not.

Neither breaks the strategy. Both change how it is run.

---

## Bug one: the cap that was not a cap

**What happened.** Last week the book had 37 of its 50 stocks moving up and down
together, worth 66.6% of the money. Your rules cap any such group at 20%. We
wrote the cap and switched it on.

It did almost nothing. After the cap, the book has 35 of 50 stocks in one group,
worth 62.7% of the money. Three points better. The cap is 20%.

**Why it failed.** Think of seating people at a dinner table with a rule that
nobody may sit near more than ten people they already know. The rule was being
checked only as each new guest arrived, against the guests already seated. The
guest who sat down first was never checked again. By the end of the evening she
was surrounded by thirty people she knew, and the rule never noticed, because it
only ever looked backwards.

That is exactly what happened. Measured on the book it produced, one stock, ASX,
finished with 36.0% of the money sitting in things that move with it. Ten of the
fifty holdings were over the 20% cap. The rule reported success the whole time.

**What we tested.** We rewrote the rule to check both directions: a stock is
only bought if buying it leaves *every* affected holding under the cap, not just
the new one. Then we re-ran the entire nine and a half years of history with the
old rule, the new rule, and no rule at all, to find out what the fix costs.

| Version | How much the picks beat the average stock, per month | Biggest group ever held |
| --- | --- | --- |
| No cap at all | 1.443% | 41 stocks |
| Old cap (broken) | 1.444% | 37 stocks |
| **New cap (fixed)** | **1.379%** | **28 stocks** |

That middle row is the proof the old cap did nothing: its result is identical to
having no cap, to within a rounding error.

**What we found.** The fix costs about 4.4% of the edge. The strategy still
passes: it beat the average stock in 84% of half-year chunks, exactly as before
the fix, and the statistical score is 2.19, where above 2 means luck is an
unlikely explanation.

On today's list, the fixed rule holds every holding at or under 19.8% and cuts
the biggest group from 35 stocks to 18. It buys different things: security
software, networking, a biotech instrument maker, a trucking firm, an oil
refiner, a steelmaker. The book stops being a single bet on computer chips.

**Fixed in code, not yet in the book.** The change takes effect at the next
rebalance. Until Monday the book still carries the concentration the broken rule
allowed.

---

## Bug two: we traded at the worst minute of the day

**What happened.** Trading cost 42.6 basis points per fill. A basis point is one
hundredth of one percent. We assumed 5 to 10. Last week's fills measured 3.8.

The cause is timing, not the market. The rebalance was submitted at 1:08 in the
morning New York time, while the exchange was shut. Orders sent to a shut
exchange sit in a queue and all execute the instant it opens. Every one of our
31 orders filled inside the first six minutes of trading.

**Why that is expensive.** The opening bell is the noisiest moment of the day.
The gap between what buyers offer and sellers ask is at its widest, and prices
move fastest. Last week's orders went in during a calm mid-morning and cost 3.8
basis points. Same book, same strategy, eleven times the cost, purely from the
clock.

In money: 42.6 basis points on $52,131 of trading is $222. Against the assumed
cost it is roughly $200 more than it should have been, or 0.2% of the account,
in one rebalance.

**A measurement error we found while checking.** The tool that measures this was
comparing each fill against the price during the minute *before* it, not the
minute it happened. On a calm day that hardly matters. On a fast-moving open it
charges one minute of ordinary price drift as though it were a trading cost. It
turned out not to change the headline much (42.9 against 42.6) but it badly
distorted the typical trade: the middle fill measured 29.9 basis points the wrong
way and 12.5 the right way. Both numbers are now measured correctly.

So the honest reading is: the typical trade cost 12.5 basis points, still above
the 5 to 10 we assumed, and a handful of terrible fills at the open dragged the
average to 42.6. The worst was SMTC at 375 basis points.

**Fixed.** Three changes. The measurement now uses the right minute. The tool
warns loudly when fills cluster in the first fifteen minutes. And the trading
code now refuses to submit orders when the exchange is shut, or within fifteen
minutes of the close, because both queue into an auction. That refusal is
already live and was tested tonight: it blocked a submission and named the
reason.

---

## Bug three: nobody was running it

**What happened.** The rebalance due Monday 24 August did not happen. This one
ran on Tuesday night for Wednesday's open. The five-step weekly sequence existed
only as a comment in a file, and depended on a person remembering.

**Why that is bad.** The whole point of this phase is six clean weekly cycles,
after which we can say whether real trading costs match the model. Two cycles
are done and both were untidy. Every miss pushes the verdict out a week.

**Fixed, but needs your say-so to switch on.** `scripts/weekly_rebalance.sh`
runs all five steps, logs everything, and fails loudly rather than quietly. To
have it run itself every Monday at 10:30 New York time, an hour after the open:

```
crontab -e
30 7 * * 1 /Volumes/PortableSSD/Github/day-trader/scripts/weekly_rebalance.sh
```

I have not installed that. Setting a machine to place orders on a schedule with
nobody watching is your decision, not mine, even with fake money.

---

## The thing that is going right

Today the book gained 2.81% while the market gained 0.02%. Last week it lost
6.25% while the market lost 0.20%.

That is one fact, not two. The book is a concentrated bet on semiconductors, so
it loses much more than the market on bad days and wins much more on good ones.
The strategy is behaving exactly as the concentration diagnosis predicted. It is
also why the cluster cap matters: without it, the account's fate is decided by
one industry.

The safety rails all held. No holding is near the -25% automatic sale. The
account never used borrowed money or bet against anything, because the code
cannot do either.

## One thing to note, not yet a problem

Cash is 9.50% of the account. Your rules want at least 10%. This is drift, not a
breach: the rule is applied when buying, and the holdings then rose in value,
which shrinks cash as a share. The next rebalance resets it. Worth watching in
case it becomes a pattern.

---

## Two things you asked for that do not exist

**Revenue.** There is none. Nothing has been sold at a profit and no real money
is in play.

**Model accuracy.** There is no model. This strategy is a sorting rule: line up
the stocks by last year's return, buy the top fifty. There is nothing to be
accurate or inaccurate about.

---

## One caveat on every historical number above

The stock data only covers companies that still exist today. Companies that went
bankrupt or were bought are missing, which makes every historical result look
better than reality. We tested how much better and the strategy still passed, but
treat the history as a ceiling, not a measurement.

The live account figures are not affected by this. Those are real fills at real
prices in a real market.
