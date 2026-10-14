# Live account audit

Written 14 October 2026, 20:40 UTC, after the close. It checks what changes when the stock momentum book moves from the Alpaca paper account to a funded live one, against Alpaca's own documentation, the paper account's settings read through the API today, and the code in `03-inputs/`.

## Where the money actually is

| | |
| --- | --- |
| Account value | $97,589.45, from a $100,000 start |
| Change since it went live on 18 August | -2.41% |
| The market, same period | +0.28% (SPY, close of 18 August to 14 October) |
| Was this within expectations? | Yes. The plan expects swings of about 14% over these 40 trading days, and the book trails the market by 2.7 points, about a fifth of that. |
| Worst single holding | CRS, down 23.7% from what we paid. It is sold automatically at -25%, checked every tick the market is open. WDC (-26.7%) was sold that way on 13 October and SITM (-25.4%) today. |
| What it costs us to trade | 4.0 basis points per fill on 13 fills to 13 October, against the 5 to 10 assumed. Today's SITM sale is not yet measured. |
| Rebalances done | 8 of the 6 the trial needed. The week of 28 September was missed and 21 September ran a day late. |

**This is fake money.** It is a paper account. The switch that would let it spend real money is off.

## How to read this

Section two lists Alpaca's rules that apply to a live account and whether the book already meets them. Section three lists faults in our own code that would surface on a live account. Section four lists decisions that only the account holder can make. Each finding names its source.

## Alpaca's rules

1. Every Alpaca account is a margin account. Alpaca's support page answers "No, we do not offer cash accounts" (alpaca.markets/support/alpaca-cash-accounts, written about 2021 and not contradicted by anything newer found today). Below $2,000 of equity the account has 1x buying power, and from $2,000 it may borrow 2x overnight and 4x intraday (docs.alpaca.markets, "Margin and short selling"). The paper account today reports a maximum multiplier of 4 and buying power of $285,553 on $97,589 of equity. The book never borrows only because `build_orders` in `alpaca_trade.py` sizes buys from cash. Nothing at the broker stops a bug from borrowing. Status open, see finding 9 and decision 2.

2. Settlement is one business day. Because the account is a margin account, sale proceeds can be reused before they settle, so the good-faith violations that apply to cash accounts do not apply here. Status fine, nothing to do.

3. The pattern day trader rule, $25,000 of equity and four day trades in five days, is being replaced by FINRA's intraday margin rule. Alpaca's page on it says "a 12-month interim transition period will commence" during which firms "may apply either the legacy PDT rules or the new intraday margin rules", and gives no start date. The paper account no longer reports a day-trader flag or a day-trade count, and its configuration no longer carries `pdt_check`. The book buys and sells the same stock on one day only if a catastrophe stop fires on a stock bought that morning. Status fine under either rule.

4. Buys are always placed in dollars, never in whole shares. Alpaca accepts that only for stocks marked `fractionable`, for "market, limit, stop & stop limit orders with a time in force=Day", from $1 an order (docs.alpaca.markets, "Fractional trading"). All 50 stocks held or targeted today are fractionable and tradable, checked one by one through the API. This matters more on a small account, because 36 of the 48 stocks held cost more than $90 a share, which is 1.8 per cent of a $5,000 account. Status fine today, see finding 8 for the case it does not handle.

5. Paper fills are simulated. Alpaca's paper page says paper trading "does not account for" market impact, latency slippage, queue position, price improvement, regulatory fees or dividends, and that "you can submit and receive a fill for an order that is much larger than the actual available liquidity". The 4.0 basis points measured so far is therefore the quoted spread only. A live fill can be worse through slippage or better through price improvement, and a live account is paid dividends that the paper one never was. Status open until the first live week is measured, as the 10 October status report already planned.

6. Regulatory fees are charged on live trades and not on paper ones. Alpaca's fee page lists FINRA's trading activity fee on sells only and the consolidated audit trail fee on buys and sells, charged at the end of each day and rounded up to the cent. The rates are on alpaca.markets/disclosures and were not checked today, so their size is unknown here. Status open, measure after the first live week.

7. The price feed is the consolidated SIP feed, stamped `"feed": "sip"` in `03-inputs/alpaca-data/download_manifest.json` on 12 October. Alpaca's paper page says paper-only accounts get the IEX feed only, which carries a few per cent of volume. The feed belongs to the account holder's data plan, not to the paper or live account, and `alpaca_data.py` already checks for SIP and stamps the feed it got. Status fine.

## Our code

8. A stock that is not fractionable would stop the rebalance halfway. `submit` in `alpaca_trade.py` sends every buy in dollars and catches no errors, so Alpaca's rejection, "requested asset is not fractionable", would raise after some orders had gone in and before the state file is written. The next tick would see a half-changed book. This has not happened, because every pick so far has been fractionable, and it could happen on paper as well as live. Fix, drop or skip non-fractionable names when the targets are chosen. Must be fixed before real money.

9. Sells and buys go in together, without waiting for the sells to fill. The buy budget counts cash that the sells will free, so for the seconds before they fill the account is spending money it has not yet received. On a 4x margin account that is invisible borrowing. On an account set to 1x, as decision 2 recommends, those buys could be rejected and stop the rebalance halfway, as in finding 8. Fix, submit the sells, wait for them to fill, then submit the buys. Must be fixed before real money, and before the multiplier is set to 1.

10. Every journal line says `ALPACA-PAPER`, in four places in `alpaca_trade.py`, and the daily report counts rebalances by searching the journal for `ALPACA-PAPER REBALANCE` (`alpaca_daily_report.py`, line 134). `cmd_status` prints "Start $100,000.00" and measures the change against $100,000, and `alpaca_daily_report.py` hard-codes `START_EQUITY = 100_000.0`. On a live account every report would label real trades as paper and measure them against the wrong start. Fix, take the label from the endpoint and the start from a setting, and change the search in the same commit. Must be fixed before real money.

11. Three helpers hard-code the paper endpoint, `TradingClient(..., paper=True)` in `alpaca_check.py`, `alpaca_data.py` and `equity_universe_filter.py`. With live keys their account and asset calls would fail to sign in. Price downloads use a separate data client and are unaffected. Fix, read the endpoint the way `alpaca_trade.clients` does. Should be fixed before real money.

12. The code reads one key pair, `ALPACA_API_KEY` and `ALPACA_API_SECRET`, from the environment, then `.env`, then the Keychain. Step 2 of the 10 October status report says to store live keys "under separate names from the paper keys", but no code reads separate names. Exporting the live keys under the standard names for one command, as step 3 says, does work and keeps the scheduled tick on paper. The money switch itself is sound, because `LIVE_TRADING` is read only from the process environment, so a `.env` or Keychain entry cannot arm it.

13. The scheduled catastrophe stop would not watch the live account. Step 4 of the status report keeps the scheduled tick on paper while live rebalances are run by hand, so nothing would sell a live holding that fell 25 per cent between hand runs. Fix, either run the live account's `check` by hand every trading day or give the tick a second, live-only stop check. Must be decided before real money.

14. The journal, the book file and the state file are tracked in a public repository: `05-research/memory/trade-log.md`, `alpaca-portfolio.md` and `alpaca-book-state.json`. A GitHub job running the trader would also print orders and balances in public logs. With real money that publishes the holder's positions and balance. Fix, keep the live journal in a gitignored file. Must be decided before real money.

15. `alpaca-py` 0.43.4 crashes on `get_account_configurations` because the broker no longer sends `pdt_check` and `dtbp_check`. The trader never calls it, so trading is unaffected.

## Holder's decisions

1. How much to put in. The backtest's worst month was -27.8 per cent, in July 2026, and the paper book has fallen 3.4 per cent in one day today. Fractional orders make any size from a few hundred dollars workable. Below $2,000 the broker allows no borrowing at all.
2. The live account's settings `max_margin_multiplier` set to 1 and `no_shorting` set to true, so the broker enforces never-margin and never-short as well as the code. These are account settings for the holder to change, after finding 9 is fixed.
3. Whether the holder can open an Alpaca live account where they live, and the tax treatment. A weekly rebalance of 50 names makes many short sales a year, and in a US taxable account a loss sold and bought back within 30 days can be a wash sale. This is for an accountant, not this audit.
4. Live API keys, created in the Alpaca dashboard and stored by the holder.
5. Setting `ALPACA_BASE_URL=https://api.alpaca.markets` and `LIVE_TRADING=true`, which arms real orders.

## Sources

Alpaca paper trading, https://docs.alpaca.markets/docs/paper-trading. Fractional trading, https://docs.alpaca.markets/docs/fractional-trading. Intraday margin rule and the end of PDT, https://docs.alpaca.markets/us/docs/understanding-finras-new-intraday-margin-rule-and-the-end-of-pdt.md. Margin and short selling, https://docs.alpaca.markets/us/docs/margin-and-short-selling.md. Regulatory fees, https://docs.alpaca.markets/us/docs/regulatory-fees.md. Cash accounts, https://alpaca.markets/support/alpaca-cash-accounts. All read 14 October 2026. Account settings, holdings, fractional flags and orders were read through the paper account's API at 20:30 UTC the same day.

## Fixes since

Findings 8, 9, 10 and 13 were fixed later on 14 October in commit `4a0b6049`, each tested against a fake broker and, for finding 8, against the paper account's asset list. Findings 11 and 14 and the holder's decisions remain open.
