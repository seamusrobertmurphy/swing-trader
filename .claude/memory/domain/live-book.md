# Live paper book

- 2026-08-25: The weekly cadence is manual and it already slipped. The
  rebalance due Monday 2026-08-24 did not run, and price bars went a week
  stale, because nothing schedules the runbook in
  `inputs/alpaca_trade.py`'s docstring. Matters because the execution verdict
  needs roughly six clean cycles; every missed one pushes it out a week.

- 2026-08-25: First week of the live book: equity $93,748, down 6.25% over
  five sessions against SPY's -0.20%. Inside the modelled distribution (35%
  annual vol is ~4.9%/week, so this is about -1.3 sigma) but the six-point
  tracking gap traces to concentration: roughly 32 of the 50 names were
  semiconductors, memory or optics, about 64% of equity in one correlated
  cluster against a charter cap of 30% per sector and 20% per cluster.

- 2026-08-25: Two charter rules are still unimplemented in
  `inputs/alpaca_trade.py`: the Principle 7 correlation-cluster cap and the
  Principle 4 drawdown sizing ramp. The ramp would be triggering now (rolling
  five-session P&L -6.25%, below the -5% threshold), and its "1:1 with each
  further 1%" wording is ambiguous enough that it needs an operator ruling
  before it is coded.

- 2026-08-26: The correlation-cluster cap deployed on 2026-08-25 was not
  enforcing itself. `equity_cluster_cap.admit` tested only a candidate's links
  back to already-admitted names and never re-tested the earlier names as later
  correlates arrived, so a name admitted early accumulated an unbounded
  neighbourhood. On the book it produced, ASX finished with 36.0% of equity
  correlating above 0.7 with it and ten of fifty holdings breached the 20% cap;
  the largest chained group was 35 names at 62.7% of equity against 37 at 66.6%
  with no cap at all. Its 115-month spread (1.444%/month) is identical to the
  uncapped run (1.443%), which is the proof it did nothing. Fixed symmetrically
  (`admit(symmetric=True)`, default): every neighbourhood now bounded, worst
  19.8%, largest chained group 18 names / 32.4% on the 2026-08-25 formation.
  Costs 4.4% of the edge (1.379%/month), fold rates unchanged 84%/79%, verdict
  still SURVIVES. Record
  `outputs/AA-evals/2026-08-26/cluster-cap-symmetric-liveshape-20260826.txt`.
  Takes effect at the next rebalance; the live book still carries the old
  concentration.

- 2026-08-26: Submitting a rebalance while the market is shut queues every DAY
  order into the opening auction, and that is where the cost is. All 31 fills of
  the 2026-08-26 rebalance landed inside the first six minutes at +42.6bp mean
  (+12.5bp median), against +3.8bp for the mid-session batch of 2026-08-18:
  same book, eleven times the cost, from the clock alone. `alpaca_trade.py`
  now refuses to submit outside the session or within 15 minutes of the close
  (`session_gate`, `--anytime` overrides), tested live.

- 2026-08-26: `alpaca_execution_report.py` was measuring each fill against the
  minute bar BEFORE the fill, not the one containing it (`bars[0]` off a start
  of t-1min), so it charged a minute of price drift as spread cost. On a fast
  open it moved the median from +12.5bp to +29.9bp. Fixed. Matters because this
  tool is the sole evidence for the execution verdict the paper phase exists to
  produce.

- 2026-08-26: `scripts/weekly_rebalance.sh` runs the five-step weekly runbook
  with logging and a non-zero exit on any step failure. NOT installed in cron;
  scheduling unattended order submission is an operator decision. Suggested
  line is in the script header (Mondays 07:30 PT, an hour after the open).

- 2026-08-26 (correction): the first cycle's execution cost was 7.3bp per fill,
  not the 3.8bp reported on the day and repeated since. 3.8 came from the
  reference-minute bug in `alpaca_execution_report.py` (it compared each fill
  against the minute BEFORE it), which was fixed the same day. The corrected
  figure is still inside the 5-10bp model band, so no verdict changes, but the
  number was quoted in several places and is now corrected in the live code.
  Dated records under `outputs/AA-evals/` keep the original figure: they record
  what was believed on the day and are not rewritten.

- 2026-08-26: the dashboard's charts were verified by rendering and LOOKING at
  them, which caught two faults no error message would have. The equity chart
  drew the account's whole 3-month history when the book only went live on
  18 August, so nine tenths of the panel was a flat line at the starting stake
  and every real move was crushed into a sliver. And every single-stock
  correlation group carried the identical label "1 stock", so ggplot silently
  SUMMED them into one bar: the page showed a 13% bar labelled "1 stock" when a
  single holding is 1.8% of the book. Both fixed. The lesson is that a chart
  can render perfectly, exit zero, and still be wrong; rendering is not
  checking.


- 2026-09-05: the rebalance due 1 September never ran, and the cause is the
  scheduler, not the model. `scripts/run_forever.sh` was carrying the tick from
  a permitted shell; its recorded process 1389 is gone and the tick log stops at
  2026-08-29T17:09Z, so the loop died that afternoon (its own header says it
  does not survive a reboot). The launchd agent that would survive one still
  cannot read the removable volume, confirmed again by
  `./scripts/install_schedule.sh verify`. Both scheduling layers were down at
  once and nothing reported it. Matters because the execution verdict needs six
  clean weekly cycles and only three are done; nine days passed with the book
  unrebalanced. A liveness check on the tick log is the missing guard.

- 2026-09-05: book at $96,916.57, -3.08% since 18 August against SPY +0.36%,
  49 positions, cash 11.38% against the 10% floor. Worst holding AAOI -20.4%,
  inside the -25% catastrophe stop. Measured execution over 21 days: 102 fills,
  mean +18.2bp, median +6.2bp, dragged up by the 31 opening-auction fills of
  26 August at +42.6bp. The two intraday cycles are 7.3bp (18 August, corrected)
  and 9.2bp (27 August), both inside the 5-10bp model band.

- 2026-09-05: the 12-1 momentum edge re-tested on bars through 4 September
  still SURVIVES on both cadences, with a small erosion and one alarming fold.
  Monthly: spread +1.006%/month over 116 months, t 2.41, abs 85% / sel 80%
  (was +1.082, t 2.53, 89%/79% on 18 August). Weekly: +0.245%/week, t 2.33,
  85%/85% (was +0.259, t 2.47). But the 2026H2 fold is the worst selection
  half-year in the 9.5-year record, top decile -4.704%/month against the market
  +0.942%, a -5.646 point gap, landing directly after 2026H1's best-ever
  +5.319. That is the momentum-crash shape after a hot run, and it is what the
  live book is sitting in. Records
  `outputs/AA-evals/2026-09-05/monthly-factors-20260905.md` and
  `weekly-factors-20260905.md`. Secondary: rev_21d now clears both fold bars
  (70%/85%) but at t 1.44, so it is not evidence, only a thing to watch.

- 2026-09-05: first baseline on the sequence-model target, before any network
  exists. A HistGradientBoosting regressor on 250,000 rows of the crypto 4h
  panel (40 coins, 90 features) predicting bars until the Supertrend flips:
  training RMSE 17.876, cross-validated RMSE 24.857, ratio 1.391, REJECTED as
  overfit on the 1.1 bar. Against always guessing the average, which scores
  26.477, the model is better by 6.1 per cent, and its first fold at 26.98 is
  worse than the flat guess. The target's median is 16 bars. Record
  `outputs/AA-evals/2026-09-06/model-metrics-20260906-0056.json`. This is the
  number an LSTM or GRU has to beat, and beating a rejected baseline is a low
  bar, so the honest comparison is against 26.477.
