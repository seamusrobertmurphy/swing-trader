# What we found on 25 August 2026

## Where the money actually is

| | |
| --- | --- |
| Account value | $93,748, from a $100,000 start |
| Change since it went live on 18 August | **-6.25%** |
| The market, same week | -0.20% |
| Was this within expectations? | Yes. The plan expected swings of about 5% a week, so this is a normal bad week, just an ugly one |
| Worst single holding | AXTI, down 19%. It gets sold automatically at -25% |
| What it costs us to trade | 3.8 basis points per trade, better than the 5 to 10 we assumed |
| Rebalances done | 1 of the 6 we need. Monday's was missed |

**This is fake money.** It is a paper account. The switch that would let it
spend real money is off.

---

## The short version

The strategy still works. We found two bugs in how it was being run. Neither
bug breaks the strategy, and fixing the first one makes it slightly better.

The book is down 6.25% in its first week because it accidentally bought fifty
versions of the same bet.

---

## Bug one: it was buying leveraged funds

**What happened.** The strategy buys the fifty stocks that went up most over
the past year. But the list it picks from was not just stocks. It also
contained funds, including three that multiply their returns by two or three
times. The book bought all three.

**Why that is bad.** Two reasons. Your rules forbid leverage outright. And a
fund that triples its sector's return will always look like the biggest winner
of the year, so the strategy picks it every single time, automatically. It also
falls three times as hard.

**What we tested.** We removed the funds and re-ran the whole history to see
whether the strategy still worked without them. It could have been that the
good results were only coming from the leverage.

**What we found.** The strategy works slightly *better* without the funds.

| Version | How much the picks beat the average stock, per month |
| --- | --- |
| As it was running, funds included | 1.08% |
| Leveraged funds removed | 1.05% |
| All funds removed | **1.13%** |

That number is the gap between what the fifty picks earned and what the average
stock earned, each month, after trading costs. Bigger is better. The gap held
up in every version, so the leverage was not the source of the edge.

Two other checks matter. First, is the gap real or just luck? A statistical
test scores it 2.59, where anything above 2 means luck is an unlikely
explanation. Second, does it work all the time or only in good years? We split
the history into nineteen six-month chunks. The picks beat the average stock in
fourteen of them, or 74%. So it fails roughly one chunk in four. That is normal
for this kind of strategy, but it is not a machine that prints money.

**Fixed.** The funds are now excluded from the list the strategy picks from.

---

## Bug two: fifty stocks, one bet

**What happened.** Thirty-seven of the forty-nine stocks the book holds move up
and down together. They are almost all semiconductors, memory chips and the
optics that go with them. Together they are 66.6% of the money.

Your rules cap any group of stocks that move together at 20% of the money. The
book is at three times that.

**Why that is bad.** The book looks diversified. It is not. It is one bet on
computer chips, sliced fifty ways. That is exactly why the book lost 6.25% last
week while the overall market lost 0.20%.

**Why it happened.** The strategy buys last year's winners, and last year's
winners are last year's winning industry. Concentration is not an accident
here. It is what the strategy does.

**What we tested.** We wrote the cap your rules describe, then re-ran the whole
history with it switched on, to find out what enforcing it costs.

| Version | Monthly gap over the average stock | Biggest group held |
| --- | --- | --- |
| No cap | 1.56% | 13 stocks |
| Cap switched on | 1.51% | 12 stocks |

**What we found.** The cap costs about 3% of the edge. That is cheap. Your
worry, that capping would ruin the strategy, does not show up in nine and a
half years of history.

**Not fixed yet.** Two reasons. First, historically the book's biggest group
averaged thirteen stocks. Right now it is thirty-seven. This month is unusual,
so the cap will bite far harder than the test suggests. Second, your rules
describe the group in a way that can chain: chip stock A moves with B, B moves
with C, so all three count as one group even if A and C have nothing to do with
each other. Chained far enough, that could swallow the entire market and stop
the book buying anything. I wrote a stricter version that cannot chain. You
need to say which one you want.

## Two things you asked for that do not exist

**Revenue.** There is none. Nothing has been sold and no real money is in play.

**Model accuracy.** There is no model. This strategy is a sorting rule: line up
the stocks by last year's return, buy the top fifty. There is nothing to be
accurate or inaccurate about, so there is no accuracy score. The closest
equivalent is how often it beats the average stock, which is 60% of months.

The abandoned crypto work *did* have a model with an accuracy score. It scored
0.50, which is a coin flip. That is why it was abandoned.

---

## One caveat on every number above

The stock data only covers companies that still exist today. Companies that
went bankrupt or were bought are missing. That makes every result here look
better than reality. We tested how much better and the strategy still passed,
but treat these figures as a ceiling, not a measurement.
