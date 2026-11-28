# Confirmed best rule

Version 1, written 26 September 2026, before any forward ticket had settled, for round-two revision task 13. It fixes in advance when the public app may call a configuration the confirmed best, so the winner is not chosen by eye and the best of many configurations is not believed because it looked good by chance. The rule is applied by code, `03-inputs/demo_mark.py`, every hour, and its result is shown on C2. Any change is a new dated version below this one; the old version stays.

A configuration is one preset or one rotated test slot, meaning a market, a candle size, an outcome, a horizon and a learner. Its forward record is the paper tickets the scheduled Scan issues for it, settled on real prices after the trading cost, 0.20 per cent for crypto and 0.10 per cent for stocks.

## Independent trades

Tickets of one configuration overlap in time, because a new scan rates the same symbols while earlier tickets are still open, and overlapping trades are not independent evidence. The record is therefore reduced before any test.

1. The settled BUY tickets entered at the same time are averaged into one basket trade.
2. Basket trades are taken in time order, and one is kept only if it starts after the previous kept one closed.

## The rule

A configuration is confirmed when all four conditions hold at the hourly check.

1. At least 30 independent basket trades, as defined above.
2. The 95 per cent confidence interval of their mean return after cost lies wholly above zero. It is Student's t interval, widened by a Bonferroni correction for every configuration that has reached 30 basket trades at the time of the check, so with k such configurations each interval is at the 1 − 0.05/k level.
3. Its BUY tickets beat its passes. Over the same scans, the mean after-cost return of its settled BUY tickets is above that of its settled NO TRADE tickets.
4. When more than one configuration meets conditions 1 to 3, the confirmed best is the one with the highest lower bound of that interval, not the highest mean.

A configuration that later fails any condition loses the status at the next check.
