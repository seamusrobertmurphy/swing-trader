# C-copy, copy and terminology audit

Written 25 September 2026 by the copy and terminology auditor. Read-only. No file in
the repository was changed and nothing was pressed or posted.

## What was read

The board was read by GET at about 17:05 Pacific on 25 September 2026, the front page
and `/card/A1` to `/card/C2`, and every visible string, option, placeholder, `title`,
`alt`, table heading, caption and script-built message was extracted with Python. The
public page is the saved copy `demo-live.html`, built 25 September 2026 16:05 and
published as gh-pages `1608689d`. The export is `01-dashboard/control-centre.html`,
saved 24 September 2026 07:20. Source lines are from HEAD `fcd0e462` (17:02). The file
`03-inputs/demo_site.py` was being edited by another agent while this audit ran (1,224
lines at the start, 1,321 at 17:12), so its line numbers are from a copy taken at 17:12,
`audit/C-copy/demo_site.snapshot.py`. Where the live public page and that copy differ,
the entry says so. The extracted text is kept beside this report in `audit/C-copy/`
(`board_corpus.txt`, `demo_corpus.txt`, `punct_board.txt`, `punct_demo.txt`).

The public page takes almost all of its text from the board, so most board entries
below also show on the public page and in the export. Each entry names every surface it
reaches.

## Counts by class

Counted as unique strings on screen or on hover, after removing repeats across pages. The export column is from the file saved on 24 September, which predates some board text.

| Class | Board | Public page | Export |
| --- | ---: | ---: | ---: |
| Em dash | 1 | 0 | 0 |
| En dash outside a number range | 0 | 0 | 0 |
| Colon in prose | 105 (72 without the 33 identical B1 hovers), from 45 source sites in Appendix D, plus 6 script-built lines | 91, plus 3 run messages | 74 |
| Section sign | 0 | 0 | 0 |
| Slash as shorthand in prose | 0 | 0 | 0 |
| Middle dot as a separator | 24, from 8 template sites | 17 | 18 |
| Headings over three words | 13 headings of 4 kinds | 7, plus 1 pending in source | 7 |
| House terms a reader cannot know | 38 terms (Appendix A) | the same 38 | as board |
| Terms used before or without a definition | not counted, the board's reader is the author | 24 (PUB-07) | as board |
| Labels that promise what the code does not do | 7 known, all located, and 15 new | 7 known and 6 new | as board |
| Stale numbers in help text | 1 known and 9 new | 1 known and 8 new | as board |
| Figurative words and aphorisms | 37 lines (Appendix C) | 37 lines | as board |
| Unclear buttons, errors and empty states | 12 | 11 | not counted, the export has no Run buttons |
| One thing under several names | 13 families of names | 13 | as board |
| Paths or file names in readable or hover text | 14 sites | 6 sites | 4 found, including the footer |

The five fixes that matter most are PUB-01, PUB-02, BRD-01, BRD-02 and BRD-05.

## Public page

The reader is a friend new to trading and to models, often on a phone, where nothing
can be hovered.

### PUB-01 Show the definitions on a phone

- **Surface.** Public phone and public desktop, every panel view. Produced by the
  board's Tooltip Rule, `control_static/control.css:785` (`.hint{display:none
  !important}`) and the `title=` attributes written in `control_templates/card.html:33,
  41, 55, 76, 99, 305, 417, 425`, carried into the public page unchanged by
  `demo_site.py`.
- **Severity.** P1.
- **Evidence.** The public page carries 229 unique explanations that exist only in a
  `title` attribute, 99 field notes, 92 table-heading glosses, 34 per-column labels on
  B1, 21 section headings and 13 others (count from `demo.jsonl`). On a 390 px phone
  none of them can be reached (`demo-phone/A1-top-04.png` shows the four Choose Filter
  fields with no note under any of them). "Fold pass rate", "Keep third", "L1 mix",
  "Embargo bars", "Purge bars", "Class weight" and "Overfit ratio cap" have no
  definition a phone reader can see.
- **Why it matters.** A friend deciding what to change has only the label, and the
  labels are the house terms listed in PUB-07 and BRD-12.
- **Proposed change.** On the public page only, add to `DEMO_CSS` in `demo_site.py`
  the rule `.field .hint{display:block !important; font-size:12px; margin-top:3px}`
  and show each table's heading glosses as a short list under the table. Rewrite the
  notes the public page keeps with the plain replacements in PUB-07 and Appendix B
  before they become visible, or the page will show the board's expert wording.
- **Effort.** M.
- **Command.** adapt.

### PUB-02 Say what each preset really found

- **Surface.** Public phone and desktop, front page and every panel, the Quick start
  block. `demo_site.snapshot.py:253-263` (`presets()` blurbs). The live page shows the
  same three blurbs.
- **Severity.** P1.
- **Evidence.** The "Three-way outcome" blurb reads "Logistic regression calls each
  4-hour bar up, down or flat over the next 12 bars, on LINK and LTC. The one setup that
  made money after cost, +1.23% a trade on its most confident fifth of unseen data." The
  record it is read from, `04-outputs/AA-evals/2026-09-16/bench-3way-20260916-140850.json`,
  ran on LINK, LTC and MATIC on the `slice_4h_40k` test sample, 265 overlapping rows in
  a 365-day blind period. `_for_demo` (`demo_site.snapshot.py:189`) drops MATIC, so the
  preset runs a configuration that was never scored. "The one setup" contradicts C1,
  which says 9 of 42 three-way fits made money after cost. The "Best on record" blurb
  reads "Random forest on 4-hour bars of LINK and LTC. The best fit so far, with an error
  on unseen data 0.98 times that of always guessing the average." Its record,
  `2026-09-21/bench-20260921-201704.json`, row `max_depth 9, min_samples_leaf 63`, ran
  on LINK, LTC and MATIC and has `fold_pass_rate 0.0`, so neither of its two folds beat
  a constant guess and it missed the fold bar.
- **Why it matters.** A friend will read a preset as a result that works, and both
  blurbs leave out the part that failed.
- **Proposed change.** Replace the three blurbs with these.
  - Best on record. "A random forest on 4-hour candles. On LINK, LTC and MATIC it had
    an error 0.98 times that of always guessing the average on prices it had not seen,
    2 per cent better, the best score on record. Neither of its two test folds beat
    that guess, so it is not good enough to trade. This preset runs it on LINK and LTC."
  - Three-way outcome, renamed "Up, down or flat". "Logistic regression sorts each
    4-hour candle into up, down or flat over the next 12 candles. On LINK, LTC and MATIC
    its most confident fifth made 1.23 per cent a trade after cost over a year it had
    not seen, but those trades overlap, so one price move was counted many times, and
    the result has not been confirmed. This preset runs it on LINK and LTC."
  - Quick and simple. "Elastic-net logistic regression, a simple model that ignores
    weak signals, on BTC, ETH and SOL, the latest 8,000 4-hour candles, tested in time
    order. The fastest run."
- **Effort.** S.
- **Command.** clarify.

### PUB-03 State the demo's limits beside the fields

- **Surface.** Public phone and desktop, A1 Choose Basket, and the Run messages.
  `bench_config.py:119-121` (`ROWS_NOTE`), `bench_config.py:506-508` (the History to
  load note), `bench_config.py:103` (BUNDLE_NOTES "all"), `demo_site.snapshot.py:796`
  (bundle options), `demo_run.py:75-78` (`LIMITS`), `demo_run.py:121-123`.
- **Severity.** P1.
- **Evidence.** The visible note says "0 reads everything; keep it under 40,000 on this
  laptop." (`demo-phone/A1-top-02.png`). The demo run caps history at 30,000 candles and
  turns 0 into 30,000 (`demo_run.py:121-123`), and "this laptop" is Seamus's. Quick pick
  offers "all", "Every coin or stock in the file.", while the run keeps at most 6 coins
  (`LIMITS symbols=6`). The run also caps folds at 5, repeats at 3, models at 3 and the
  blind period at 60 to 365 days, and a friend learns this only after the run, from
  "Held to the demo limits: ...".
- **Why it matters.** The page promises settings the run then silently changes.
- **Proposed change.** On the public page, replace the History to load note with "How
  many candles to read, newest first, across all the coins picked. A candle is one bar
  of price history, its open, high, low and close. The demo reads at most 30,000, and 0
  also means 30,000." Remove "all" from Quick pick on the public page. Under Choose Basket
  add the visible line "The demo runs at most 6 of these 14 coins." Under Choose
  Resampling add "The demo allows at most 5 folds and 3 repeats." Under Choose Blind
  Period add "The demo holds back between 60 and 365 days." Under Choose Model add "The
  demo fits at most 3 models." On the board, change "on this laptop" to "on the 8 GB
  Mac".
- **Effort.** S.
- **Command.** clarify.

### PUB-04 Say which settings Run Model sends

- **Surface.** Public phone and desktop, the Run your model block on the front page,
  B2 and C1, and every Save all settings button. `demo_site.snapshot.py:135-136`,
  `demo_site.snapshot.py:591`, `control_templates/card.html:151`.
- **Severity.** P1.
- **Evidence.** The note says "Sends your saved settings, trains your model on fresh
  prices and issues a paper ticket per coin, in about five minutes. Nothing is bought or
  sold." The Run handler calls `collect()` on the forms as they stand and sends that, saved
  or not (live page script, `var cfg = collect(); store(KEY, cfg);`). Save all settings
  only writes to this browser, and says "Saved in this browser." after the press. "Paper
  ticket" is not defined on this page.
- **Why it matters.** A friend will think unsaved changes are ignored, and will not know
  what a paper ticket is until they reach C2.
- **Proposed change.** Note text "Runs the settings shown on these pages, trains a model
  on recent prices, and issues one paper ticket for each coin, a pretend trade followed
  on real prices until it reaches its target, its stop or its due time. It takes about
  five minutes. Nothing is bought or sold." On the public page, relabel Save all settings
  as "Keep in this browser".
- **Effort.** S.
- **Command.** clarify.

### PUB-05 Tell a friend what happened after a run

- **Surface.** Public phone and desktop, the Run status line and the C2 Runs table.
  `demo_site.snapshot.py:742-745` (status), `:710-714` (Runs table), `:637` and `:721`
  (empty states), `demo_run.py:290, 319-320, 377, 481-483` (error text).
- **Severity.** P1.
- **Evidence.** Success reads "Done. 8 paper tickets issued with " and then the chosen
  model's code name, such as RF or LogReg.enet. Limits read "Held to the demo limits: history to load was held to 30,000
  candles". Failure reads "The run failed: " followed by the raw error, which for an
  unexpected fault is Python's own, "ValueError: ...". The Runs table heading "Blind
  score" holds "U2 " and "AUC " with three decimals, or "top fifth " and two
  percentages, or "failed: " and the first 80 characters of the error,
  none of which the page defines. When the ticket file cannot be fetched the totals say
  "No tickets yet.", the same words as a genuinely empty board.
- **Why it matters.** The only feedback a friend gets is written in the operator's
  shorthand, and a network failure is reported as if nothing had happened.
- **Proposed change.**
  - Success. "Done. Your run chose the random forest and issued 8 paper tickets. See
    them on C2 Ledger." Map model codes to names, `rf` and `RF` to "the random forest",
    `LogReg.glm` to "logistic regression", `LogReg.enet` to "elastic-net logistic
    regression", `HistGBM` to "histogram gradient boosting".
  - Limits. "Some settings were above the demo's limits and were lowered, history to
    30,000 candles." One clause per setting, in plain names.
  - Failure. Map the three known reasons. "no coin could be built" becomes "None of the
    chosen coins had enough price history. Pick other coins or read more history." "no
    model could be fitted" becomes "No model could be trained on these settings. Tick a
    different model or read more history." The split message becomes, for example, "After holding back
    the last 150 days for testing, only 420 candles were left to learn from. Read more
    history or hold back fewer days." Anything else becomes "Something went wrong on our
    side (ValueError). Please run it again, and tell Seamus if it happens twice."
  - Runs table. Heading "Against guessing", cell "0.998" with the dictionary line
    "Against guessing, the model's error divided by the error of always guessing the
    average. Below 1 is better." For a three-way run, the cell reads the top-fifth
    return then "a trade, all rows" and the all-row return, "+1.23% a trade, all rows
    +0.07%".
  - Load failure. "The results could not be loaded. Check your connection and reload
    the page."
- **Effort.** M.
- **Command.** clarify.

### PUB-06 Open the front page with plain words

- **Surface.** Public phone and desktop, front page. `control_centre.py:324-325` (card
  tags built from tool names), `control_registry.py:586, 646, 684, 705, 740, 832` (card
  leads), `control_charts.py:3935-4004` (slot captions),
  `control_templates/base.html:73-85` (money line).
- **Severity.** P1.
- **Evidence.** The front page (`demo-phone/front-top-01.png` and the slices below it)
  shows "A1 Data MARKET, BASKET, FILTER, RANKING, LABEL", then leads "Univariate screen, elastic net,
  survivors.", "Blind period, embargo, folds, regime.", "Fit, comparison run, calibrate;
  every fit against a constant forecast.", and captions "Training window against blind
  period", "Every model on overfit ratio and blind U2", "What the overfit bar costs in
  held-out error". The money line "$102,206 $2,206 · open 50 $4,481 · closed 58 -$2,265 ·
  cash $10,246" under a "LOCAL, PAPER ONLY" badge is Seamus's paper stock account, which
  a friend will read as the demo's result.
- **Why it matters.** The first screen decides whether a newcomer trusts the page, and
  none of these words has been explained yet.
- **Proposed change.** On the public page only, replace the card leads with
  A1 "Which coins, how long each candle is, and what counts as a win."
  A2 "The price measures the model can read."
  B1 "Which of those measures to keep."
  B2 "How much recent history is kept back to test the model."
  C1 "Which model to train, and how its score is judged."
  C2 "Your paper tickets and every friend's results."
  Drop the tag line inside each card heading (see BRD-18). Replace the money line with
  "Seamus's practice stock account, not your run. $102,206 from $100,000, up $2,206."
  The source already changes the badge to "PAPER ONLY" (`demo_site.snapshot.py:1246-1247`),
  which is not yet published.
- **Effort.** S.
- **Command.** onboard.

### PUB-07 Define each term where a friend first meets it

- **Surface.** Public phone and desktop, all views. Sources listed per term.
- **Severity.** P1.
- **Evidence.** 24 terms reach a friend before any definition they can see. Front page
  "paper ticket", "model", "preset", "blind period". A1 "USDT" (`control_tables.py:572`),
  "bp" (`control_tables.py:590`, defined a row later at `:595`), "maker orders", "BNB fee
  discount" (`:593`), "Kelly", "catastrophe stop", "charter", "basket", "rebalance"
  (Hard Rules, `:670-790`), "Supertrend" in the Rank by note (`bench_config.py:283-293`,
  defined only on A2), "base rate" (never defined visibly). B1 "lasso" and "ridge", used
  to define "L1 mix" (`bench_config.py:171-174`). C1 "overfit bar", "constant guess",
  "blind top fifth" and "Three-way" in The record block (`card.html:172-205`), which sits
  above the Scores table that defines them. "upweights" (`bench_config.py:182-184`). Live
  C2 "BUY" and "PASS", never defined on the published page.
- **Why it matters.** A friend cannot choose a setting whose name they do not know.
- **Proposed change.** Add these definitions as visible text at first use on the public
  page.
  - paper ticket. "a paper ticket, a pretend trade in one coin, followed on real prices
    until it reaches its target, its stop or its due time"
  - model. "a model, a formula fitted to past prices that rates each coin"
  - blind period. "the blind period, the most recent days of prices kept back and used
    once, at the end, to test the model"
  - base rate. "the base rate, the share of past candles that were wins"
  - constant guess. "a constant guess, a forecast that always says the base rate"
  - USDT. "USDT, a coin that tracks the US dollar, so prices here are in dollars"
  - bp. write "42.6 basis points (hundredths of a per cent)" at the first use in the
    Trading hours row
  - Supertrend. "the Supertrend, a line drawn a set distance below the price in an
    uptrend and above it in a downtrend"
  - L1 mix. "1 drops weak columns entirely; 0 only shrinks them; values between mix the
    two"
  - class weight balanced. "Balanced makes wins, the rarer outcome, count for more when
    the model is fitted."
  - overfit ratio. "the overfit ratio, the error on rows the model did not train on
    divided by the error on rows it did; far above 1 means it memorised its training
    rows"
  - BUY and PASS. "BUY means the model rated the coin among its best; PASS means it did
    not." The working copy adds this at `demo_site.snapshot.py:276-279`, not yet published.
  - Hard Rules, Kelly, charter, basket and rebalance. Remove the Hard Rules table from
    the public page (see PUB-08) rather than define them.
- **Effort.** M.
- **Command.** onboard.

### PUB-08 Leave the operator's own records off the public page

- **Surface.** Public phone and desktop, A1, A2, B1, B2, C1, C2. `control_tables.py:657-795`
  (Hard Rules), `:565-603` (Alpaca column of Datasets), `control_templates/card.html:675-686`
  (Evidence Log), the A2 Columns table, the B1 per-column hovers from
  `control_varselect.py:595-600`.
- **Severity.** P2.
- **Evidence.** The public page shows the 16-row Hard Rules table for Seamus's stock
  basket, the Evidence Log as bare file names ("bench-20260922-220829.md", "coef_ci.png",
  "cv_curve.png"), the A2 Columns table with function names and code ("indicator_block",
  "from WC['mom'] = [30, 60, 120, 360]"), and B1 hovers such as "fitted alone: +0.1310
  log-odds, p < 0.001".
- **Why it matters.** None of it changes a friend's run, and all of it reads as noise.
- **Proposed change.** In `demo_site.py`, drop the Hard Rules block, the Alpaca column,
  every Evidence Log block and the A2 Columns table from the public page, as the working
  copy already does for C2's stock tables.
- **Effort.** S.
- **Command.** distill.

### PUB-09 Name the options in words

- **Surface.** Public phone and desktop, and the board, every select. `card.html:47`
  (`{{ c or 'none' }}` prints the stored value), `card.html:62` and `:85-94` (multi and
  hyperparameter options), `demo_site.snapshot.py:796` (bundle options).
- **Severity.** P2.
- **Evidence.** Option text is the stored code. Quick pick "majors", "btc-eth". Rank by
  "f_mst_dir", "f_d1_st_up", "f_btc_mom_168", "f_st_agree". Families "f_wc_" to "f_ms_".
  Regime "kfold", "repeated-kfold", "monte-carlo". Choose the winner by "best", "oneSE".
  Penalty rule "1se", "min". Models "LogReg.glm", "LogReg.enet", "RF", "HistGBM",
  "GBM.classic". Grid search over "none", "histgbm", "lightgbm", "rf", "gbm". Hyperparameters
  "gini", "log_loss", "gbdt", "dart", "goss", "lbfgs", "saga", "liblinear". The job forms
  already have plain labels for one of these lists (`control_registry.py:886-891`,
  `CHOICE_LABELS["tune"]`), which the Choose Grid Search tool does not use.
- **Why it matters.** A code in a drop-down tells a friend nothing and is the first thing
  Seamus called meaningless.
- **Proposed change.** Keep the stored values and show the words in Appendix A as the
  option text on both surfaces, through one `OPTION_LABELS` map in `bench_config.py` read
  by `card.html:47, 62, 90`.
- **Effort.** M.
- **Command.** clarify.

### PUB-10 Keep friends off the settings the page calls unsound

- **Surface.** Public phone and desktop, B2 and C1, when no preset is chosen. The
  public page is built with the operator's saved configuration as its starting values;
  in `demo-live.html` the Regime select has `monte-carlo` selected, Class weight has
  `balanced` selected and the Overfit ratio cap box holds 1.3.
- **Severity.** P2.
- **Evidence.** B2's own note says "Expanding and rolling keep time in order and are the
  only honest choices on prices; the rest are offered to show how much a random split
  flatters a fit" (`bench_config.py:178-181`), while the starting value is Monte Carlo.
  C1 says balanced "Cost two thirds of the calibration error" (`bench_config.py:744`)
  while the starting value is balanced.
- **Why it matters.** A friend who presses Run Model without a preset runs the choices
  the page tells them not to trust.
- **Proposed change.** Build the public page from a fixed demo configuration, expanding
  folds, class weight none and an overfit cap of 1.1, rather than from the operator's
  saved file. If the defaults stay, add under Choose Resampling "The starting choice,
  Monte Carlo, ignores time order; pick expanding for a fair test."
- **Effort.** S.
- **Command.** harden.

### PUB-11 Review the new C2 text before it goes live

- **Surface.** Public, C2, in the working copy only. `demo_site.snapshot.py:273-285`
  (About this page), `:288-298` (Model scores notes), `:300-315` (dictionary),
  `:345-358` (Research record).
- **Severity.** P3.
- **Evidence.** "What the columns mean" is a four-word heading. "expected it to pay" is
  figurative. "the learner the run chose" uses "learner". The Overfit ratio note says
  "Above 1.1 the model has fitted noise in its training data and is rejected", while a
  friend's run rejects above whatever the cap on C1 says, 1.3 on the saved settings. The
  Research record says the stock account "is reported every trading day by a scheduled
  job, one file a day named DAILY", while the DAILY files on disk are dated 14, 15, 16,
  21 and 22 September and none since. The link text "04-outputs/AA-evals" is a data path.
  "and counting" is filler.
- **Why it matters.** This text will be published on the next build.
- **Proposed change.** Heading "Column meanings". "BUY means the model ranked that coin
  among its best and expected it to rise by more than the trading cost; PASS means it did
  not." "the model the run chose". Overfit ratio note "Cross-validated RMSE divided by
  training RMSE. Above the cap on C1, 1.1 unless changed, the model has memorised its
  training data and is rejected." Research record "The operator's own stock account is
  reported by a scheduled job in a file named DAILY with its date, kept on GitHub in the
  evaluations folder." with the link text "the evaluations folder". Cut "and counting".
- **Effort.** S.
- **Command.** clarify.

## Board

These entries show on the board and, unless stated, on the public page and the export,
which are built from it.

### BRD-01 Say that the best fit missed the fold bar

- **Surface.** Board B1, B2 and C1 (Best so far block and The record), public page
  ("Load best fit settings as defaults"), export. `bench_config.py:1285-1297`
  (`recommendation_sentence`), `control_templates/card.html:180-186` (Best on record).
- **Severity.** P1.
- **Evidence.** B1 shows "Best of 574 fits so far: rf. Error on the unseen year 0.98
  times a constant guess, under 1, so it beat a constant guess, just. Overfit ratio
  1.058, under the 1.1 cap. Record bench-20260921-201704.json." That fit
  (`2026-09-21/bench-20260921-201704.json`, `max_depth 9, min_samples_leaf 63`) has
  `fold_pass_rate 0.0` and `fold_bar_met false`, its blind period was 150 days, not a
  year, and its run capped the overfit ratio at the value it was saved with, not a fixed
  1.1. The Best on record line says "0.9800 (rf, 2026-09-21 20:17)" with no fold result.
- **Why it matters.** The product's fifth principle is to say what failed, and the one
  sentence that recommends a configuration hides the check it failed.
- **Proposed change.** "Best of 574 fits, a random forest on 21 September. On its last
  150 days it scored 0.980 of a constant guess, 2 per cent better, and its overfit ratio
  was 1.058. Neither of its 2 folds beat a constant guess, so it missed the fold bar."
  Build the day count, fold count and cap from the record rather than writing "year" and
  "1.1". Best on record line "Best on record 0.9800 (random forest, 21 September 20:17,
  missed the fold bar)."
- **Effort.** S.
- **Command.** clarify.

### BRD-02 State the overfit cap each run used

- **Surface.** Board C1 and C2, public C1 and C2, export. Statements of 1.1 at
  `control_tables.py:945` ("Rejected above 1.1, whatever its error."), `:66` ("Above 1.1
  is rejected as overfit"), `:110` ("under the 1.1 overfit bar"), `bench_config.py:751`
  ("The house bar is 1.1"), `bench_config.py:1296` ("under the 1.1 cap", hard-coded),
  `control_interactive.py` notes ("the dashed line is the 1.1 overfit bar", "Red failed
  the 1.1 overfit bar"), `demo_site.snapshot.py:296-297`.
- **Severity.** P1.
- **Evidence.** The saved configuration rejects above 1.3 (Overfit ratio cap field value
  1.3; masthead "rejecting above a 1.3 overfit ratio"; C1 detail "overfit ratio 1.010
  against 1.3"). The counts "323 passed the overfit bar" (`control_tables.py:363`) mix
  runs judged at 1.1 and at 1.3.
- **Why it matters.** "Passed" means two different tests on the same page, and the
  board states the stricter one.
- **Proposed change.** Every statement reads the run's own cap. Scores table
  "Rejected above the cap on Choose Model, 1.1 unless changed." Scoreboard gloss "Above
  the run's own cap, shown in the cap column, it is rejected." Count line "323 passed the
  overfit cap each was run with; 58 of them were run with the looser cap of 1.3." A count
  from the records on 25 September found 60 fits run at 1.3, 58 of which passed, and
  516 run at 1.1.
- **Effort.** M.
- **Command.** clarify.

### BRD-03 Make the crypto result agree with C1

- **Surface.** Board A1 Datasets table, public A1, export. `control_tables.py:597-601`.
- **Severity.** P1.
- **Evidence.** A1 says "No crypto strategy has beaten its costs on unseen data. Ranking
  coins by strength works, but the fee eats it." C1 says "Three-way: best blind top
  fifth +1.226% a trade after cost ... 9 made money after cost."
- **Why it matters.** Two panels of one board give opposite answers to the question the
  board exists to answer.
- **Proposed change.** "No crypto strategy has passed every test after costs. Ranking
  coins by strength picks better coins than average, but the 0.20 per cent trading cost
  is larger than the gain. The three-way outcome made money after cost over one year in
  September, on overlapping trades, and has not been confirmed." In the Alpaca cell,
  write "(t-statistic 2.41, to 5 Sep 2026)" for "(t 2.41, to 5 Sep 2026)"; the figure is
  `2026-09-05/monthly-factors-20260905.md` line 81.
- **Effort.** S.
- **Command.** clarify.

### BRD-04 Point the C1 steps at what is on the page

- **Surface.** Board C1, What to do. `control_registry.py:745-749`.
- **Severity.** P1.
- **Evidence.** Step 3 says "It spends every setting saved above, and the line under the
  button is the command it will run." The line is hidden (`control.css:862`,
  `.cmd{display:none}`) and the command is the button's tooltip (`card.html:859`). Step 4
  says "Read Results, directly below." No block is called Results; the block is headed
  "The last run" (`card.html:270`). Step 4 also says "the unseen period" for the blind
  period.
- **Why it matters.** The two steps that tell the operator where to look send him to
  things that are not there.
- **Proposed change.** Step 3 "Press Run the test. It uses every setting saved on the
  six panels; hover the button to see the command." Step 4 "Read The last run, directly
  below. Three checks decide it, a lower error than a constant guess on the blind period,
  an overfit ratio under the cap, and enough folds that beat a constant guess."
- **Effort.** S.
- **Command.** clarify.

### BRD-05 Show where each known label defect appears

- **Surface.** Board, public page and export, as listed.
- **Severity.** P1.
- **Evidence and place.**
  1. Take-profit and Stop never change the label. They show as A1 Choose Label fields
     "Take-profit, ATR" and "Stop, ATR" (`bench_config.py:515-518`), in the label note
     and its live example "Example: with a typical daily move of 2 per cent, take-profit
     2.0 is a target 4.0 per cent above the buy and stop 1.0 is an exit 2.0 per cent
     below it." (`card.html:995-1002`), in the masthead line and the C1 This run row
     "Label 2 ATR take-profit against 1 ATR stop within 12 bars." (`bench_config.py:1174-1176`),
     in the Outcome note "barrier: Win or loss: did price reach the take-profit before
     the stop?" (`bench_config.py:262`), and on public A1.
  2. The eleven A2 engine settings only draw charts. A2 step 2 says "Set the indicator
     engines below if you want their columns to change" (`control_registry.py:675`), the
     Choose Averages note says "These two feed the moving-average vote in the confluence
     score below." (`bench_config.py:162-165`), and the eleven fields sit under Choose
     MACD, Choose Averages, Choose Fibonacci and Choose Confluence
     (`bench_config.py:627-641`). The public page removes step 2 but keeps the fields and
     the note.
  3. No model ticked fits three models, not six. C1 Choose Model note "Nothing ticked
     scores every model." (`bench_config.py:724`), on the board and the public page; the
     runner falls back to `["LogReg.glm", "RF", "HistGBM"]` (`bench_run.py:1404, 1464`).
  4. Fold pass rate counts folds with U2 under 1, not money. A1 field "Fold pass rate"
     with the note "The share of half-year folds that must be positive." (`bench_config.py:568-571`),
     the visible A1 note "the history is cut into half-year pieces, called folds, and
     this is the share of them where the strategy must have made money" (`bench_config.py:305-307`),
     and C1 Scores "Pass rate, Share of half-year folds where the strategy made money."
     (`control_tables.py:950`). The folds are B2's resampling folds (2 Monte Carlo folds
     on the saved settings), not half-years. The A1 Rank by note uses the same "60 per
     cent bar" for a June test that did count money (`bench_config.py:553-557`).
  5. Embargo 0 means 2 days, not the horizon. B2 Embargo bars note "0 uses the label
     horizon" (`bench_config.py:656-657`), Choose Blind Period note "0 uses the label
     horizon" (`bench_config.py:175-177`), masthead "with a label-horizon embargo"
     (`bench_config.py:1180`).
  6. Class weight defaults to balanced though it scored worse. C1 Class weight select,
     first and selected option "balanced" (`bench_config.py:742`), its own note "Cost
     two thirds of the calibration error and lifted blind U2 to 1.15 on every model on 16
     September." (`bench_config.py:228`).
  7. The 1-hour base rate on the 4-hour frame. A1 Take-profit note "The inherited +2 has
     a base rate of 0.313 against a breakeven of 0.333" (`bench_config.py:516-517`),
     while B1's own figure note gives 0.298 for the 1-hour file.
- **Why it matters.** Each is a setting or a sentence that tells the reader something
  the code does not do.
- **Proposed change.** Until the code is fixed, the text says what happens.
  1. Label the two fields "Take-profit, ATR (not yet used)" and "Stop, ATR (not yet
     used)", drop the example sentence, and write the masthead clause as "Label from the
     built file, 12 bars".
  2. Replace A2 step 2 with "The indicator engines below change only the charts on this
     page and C2. The model's columns are built with fixed settings." Replace the Choose
     Averages note's last sentence with "They change the charts, not the model's
     columns."
  3. "Nothing ticked fits three models, logistic regression, the random forest and
     histogram gradient boosting."
  4. Label "Folds that must beat guessing". Note "The share of B2's folds in which the
     model's error must be below that of a constant guess; 0.6 with 5 folds means 3. It
     does not test money." Scores row "Fold pass rate, the share of folds in which the
     model beat a constant guess. At least 0.6."
  5. "0 uses a two-day gap."
  6. Put "none" first and selected, and label the other option "balanced (scored worse
     on 16 September)".
  7. Compute the base rate for the chosen frame and print it, "On this frame the +2
     target has a base rate of 0.298 against a breakeven of 0.333." (0.298 is the
     1-hour file's figure in B1's own note; the 4-hour figure has to be computed).
- **Effort.** M.
- **Command.** harden.

### BRD-06 Make Embargo bars mean bars on every timeframe

- **Surface.** Board B2, public B2, masthead line. `bench_run.py:1419-1421`,
  `bench_config.py:655-657`.
- **Severity.** P2.
- **Evidence.** The field is labelled "Embargo bars", and the runner converts it with
  `embargo // 6`, six bars a day, whatever the timeframe. On 1-hour candles 12 bars
  becomes 2 days, 48 bars.
- **Why it matters.** The label promises a count of candles that is only right on the
  4-hour frame.
- **Proposed change.** Convert with `bench_config.bars_per_day(frame)`, or relabel the
  field "Embargo, 4-hour bars" with the note "Counted in 4-hour bars whatever the
  timeframe."
- **Effort.** S.
- **Command.** harden.

### BRD-07 Name the model settings correctly

- **Surface.** Board C1 Choose Settings and the Models table, public C1. `bench_config.py:868,
  877-878` (`PARAM_LABEL`), `control_tables.py:933` (the Models table's Settings
  column built from those labels).
- **Severity.** P2.
- **Evidence.** `max_iter` is "Rounds" for every model, so logistic regression lists
  "Inverse penalty strength; Rounds; Optimiser." where `max_iter` is solver steps, not
  boosting rounds. `num_leaves` and `max_leaf_nodes` are "Branches per tree", but they
  count leaves.
- **Why it matters.** The label tells the reader to expect a different quantity.
- **Proposed change.** "Most solver steps (max_iter)" for LogReg.glm and LogReg.enet,
  "Rounds (max_iter)" for HistGBM only, and "Leaves per tree (num_leaves)" and "Leaves per
  tree (max_leaf_nodes)".
- **Effort.** S.
- **Command.** clarify.

### BRD-08 Describe C2 as it is

- **Surface.** Board C2 What to do and section headings, public C2 (live). `control_registry.py:833-837,
  857-858`.
- **Severity.** P2.
- **Evidence.** Step 1 says "Nothing is configured here." while C2 carries the Choose
  Figures form with five settings. Step 2 says "Live book for the runs and milestones",
  and the Live book heading holds the run calendar and milestones, not the paper book.
- **Why it matters.** The heading name suggests the stock account and the step denies a
  form that is on screen.
- **Proposed change.** Step 1 "Choose Figures sets which charts a run draws. Everything
  else here records what the book did and what every run found." Rename the Live book
  group "Run history" and write step 2 as "Read Money for the account in dollars, Run
  history for the runs and milestones, and Assessment for every run compared."
- **Effort.** S.
- **Command.** clarify.

### BRD-09 Fix the horizon note on stock and 15-minute frames

- **Surface.** Board A1 Choose Label note. `control_templates/card.html:1049-1056`,
  with `hours_per_bar` from `control_centre.py:432`.
- **Severity.** P2.
- **Evidence.** The note computes hours per bar as 24 divided by bars per day, which
  counts a stock trading day as 24 hours. On "1 hour, US stocks" it prints "Here: 12 bars
  of 3.4285714285714284 hours, so 41.1 hours." On "30 minutes, US stocks" it prints bars
  of 1.8461538461538463 hours. On "15 minutes, US stocks" it prints "bars of 5 minutes",
  and on "5 minutes, US stocks" it prints 3.7 hours for what is one hour of candles.
- **Why it matters.** The only worked example of the horizon is wrong on the four
  intraday stock timeframes.
- **Proposed change.** Use the frame's own minutes, "12 candles of 1 hour, 12 trading
  hours." "12 candles of 15 minutes, 3 hours." and no colon.
- **Effort.** S.
- **Command.** harden.

### BRD-10 Repair the text left by "comparison run"

- **Surface.** Board C1, B2 and C2, public C1 and C2, export.
- **Severity.** P2.
- **Evidence and place.**
  - `bench_config.py:232` "No comparison run; the ticked models are scored once."
  - `bench_config.py:233-236` "Comparison run the histogram booster over the grid." and
    three more like it, shown under Choose Grid Search when a model is picked.
  - `bench_config.py:740` "key=v1,v2 separated by spaces. Empty comparison runs the
    model's own entry in TUNE_GRIDS, which for histgbm is eighteen combinations."
  - `control_registry.py:285-286` the same sentence on the Assess models Grid field.
  - `control_registry.py:318` "The same comparison run on a different target: bars until
    the Supertrend flips."
  - `control_tables.py:118-120` "across this comparison run session the fold count moved
    held-out error by 0.0040."
  - `control_templates/card.html:191` and `control_tables.py:363` "574 fits from 126
    comparison runs", where 126 is every record (`len(docs)`), most of them single runs;
    C2 says "125 runs" for the same records (`control_tables.py:250`).
  - `control_registry.py:740` the C1 lead "Fit, comparison run, calibrate; every fit
    against a constant forecast."
- **Why it matters.** A word replaced everywhere at once left sentences that do not parse
  and a count that names the wrong thing.
- **Proposed change.** "No grid search; the ticked models are fitted once." "Grid-search
  the histogram booster." (and the random forest, LightGBM, classic booster). "Words like
  learning_rate=0.03,0.06 separated by spaces. Left empty, the model's own grid is used,
  18 combinations for the histogram booster." "The same grid search on a different
  target, the number of bars until the Supertrend changes direction." "across these runs
  the fold count moved held-out error by 0.0040." "574 fits from 126 records." with C2
  counting the same records the same way. C1 lead "Fit, tune and calibrate a model, and
  rank it against every fit before it."
- **Effort.** S.
- **Command.** clarify.

### BRD-11 Replace the house coinages

- **Surface.** Board, public page and export.
- **Severity.** P2.
- **Evidence.** The 38 terms in Appendix A, each confirmed on screen with its source line.
- **Why it matters.** Seamus called the last sheet's terminology meaningless; these are
  the words that made it so.
- **Proposed change.** Apply Appendix A. Where it says "change label", change the board
  label as well; where it says "gloss", keep the board label and add the plain gloss on
  the public page.
- **Effort.** M.
- **Command.** clarify.

### BRD-12 Use one name for one thing

- **Surface.** Board, public page and export.
- **Severity.** P2.
- **Evidence and place.**
  - The blind period is also "the unseen year" (`bench_config.py:1295`), "the unseen
    period" (`control_registry.py:748`), "unseen data" (`control_tables.py:598, 601, 949`),
    "the held-out period" (`control_tables.py:69-72`), "the blind year"
    (`bench_config.py:764`) and "the test window" (`control_registry.py:253`).
  - "Held out" also means the cross-validation folds, in the C1 headings "RMSE, held
    out", "MAE, held out", "MISE, held out" (`control_tables.py:1762`).
  - The overfit threshold is "overfit bar", "overfit ratio cap", "Overfit cap", "the
    house bar", "the 1.1 cap" and the column "cap".
  - The benchmark is "constant guess", "constant forecast", "always guessing the
    average", "always guessing the base rate", "always predicting the base rate" and
    "a constant".
  - ATR is "the coin's typical daily move" (`bench_config.py:115-118`, the Supertrend row at
    `control_tables.py:837`, the Hard stop row at `:737`) and "the size of a typical bar's move" (`control_tables.py:1198`).
    The label's ATR is 14 candles of the traded timeframe (`build_dataset_1h.py:102`);
    only the screen band reads the daily ATR (`bench_run.py:249-259`).
  - "Regime" is the resampling scheme (B2 field and table), a market state (A1 Screening
    row "Regime", "one favourable regime"), a feature family (`bench_config.py:1307`
    "Regime: volatility rank...") and, in the A2 figure note, a feature that changes
    sign.
  - "Screen" is the A1 filter ("The screen a name must pass", `control_tables.py:133`)
    and the B1 variable screen; A1 also calls it "gates" and "Choose Filter".
  - "Panel" is a board page, a data file ("the 4h panel", "Panels built and
    available"), a chart pane ("Drawn on the candle panel", `bench_config.py:781`) and
    the Figures select's field name.
  - One model is "rf", "RF", "random forest" and "Random forest" (C1 lines "(rf,
    2026-09-21 20:17)" and "(RF, 2026-09-22 22:08)").
  - The features tool is "Choose Features", "the Features section" (`bench_config.py:594`)
    and "the Feature selection form" (`control_tables.py:153, 164`).
  - C1 has two blocks for one run, "This run" (`card.html:216`) and "The last run"
    (`card.html:270`).
  - The Save step says "then Save" (`control_registry.py:639-640`) and the button says
    "Save all settings".
  - "Load best as defaults" on the board and "Load best fit settings as defaults" on the
    public page (`demo_site.snapshot.py:1195`).
  - The timeline is "Every run, with the milestones marked" (`control_charts.py:4002`)
    and "Timeline: every run in order, with its headline result" (`control_registry.py:241-242`).
- **Why it matters.** A reader who meets two names assumes two things.
- **Proposed change.** Blind period on the board everywhere, with the public gloss from
  PUB-07. "Folds" for the cross-validation columns, "RMSE, folds", "MAE, folds", "MISE,
  folds". "Overfit cap" everywhere, and the column "cap". "Constant guess" everywhere,
  defined once in the C1 Scores table as "a forecast that always says the base rate".
  ATR in the label defined as "the average high-to-low range of the last 14 candles";
  the screen band note keeps "a typical day". "Resampling" for the B2 field and table
  ("Resampling schemes"); "market state" for the A1 row and the `f_rg_` family; "flips
  sign between folds" in the A2 note. "Filters" for A1, "variable screen" for B1. "Page"
  for a board page and "data file" for a panel file; the Figures field note "Drawn on
  the candle chart." "Random forest" in prose, "RF" in tables. "Choose Features" in both
  glosses. Rename "This run" to "Last run" and "The last run" to "Fits compared". "Save
  all settings" in the step. "Load the best run's settings" on both surfaces. One
  timeline caption, "Every run in order, with milestones".
- **Effort.** M.
- **Command.** clarify.

### BRD-13 Update the stale numbers

- **Surface.** Board, public page and export.
- **Severity.** P2.
- **Evidence and place.**
  - `control_tables.py:958` Ledger "Every scored fit on disk, 460 and counting". C1 counts
    574.
  - `control_tables.py:573` Datasets "the current test uses 3". The saved configuration
    has 2 symbols, LINK/USDT and LTC/USDT.
  - `bench_config.py:208` "LogReg.enet ... Best on the blind period so far." and
    `control_tables.py:915-916` "the most reliable model on this board so far". C1's own
    table ranks RF 0.9800, LogReg.glm 0.9859, LogReg.enet 0.9924.
  - `control_tables.py:596-597` "measured 6.1 bp a fill on average, 3.3 typical, over 41
    fills to 14 Sep 2026." The newer `2026-09-22/execution-report-20260922-1032.md`
    reports 21 fills, mean 5.0 bp, median 4.6 bp.
  - `control_tables.py:961` Ledger Reports "one file a day under a dated folder". DAILY
    files exist for 14, 15, 16, 21 and 22 September and none since.
  - `control_tables.py:896` Resampling table "Same leak, ten times." The record
    `2026-09-16/bench-sweep-20260916-060522.md` shows repeated k-fold claiming 0.3600
    against a blind 0.4467, 0.087 below, from 3 seeds.
  - `control_tables.py:252-253` "Performance next door is one run at one configuration";
    the Performance table was removed on 22 September (`control_tables.py:210-217`).
  - `control_tables.py:941` "Lower is better; 0.5 is guessing." A constant guess at the
    base rate scores about 0.46 (square root of 0.30 times 0.70), not 0.5.
  - The known 0.313 (BRD-05 item 7).
- **Why it matters.** Numbers in help text are read as current and these are not.
- **Proposed change.** "Every scored fit on disk, 574 on 25 September, each with the
  settings that produced it." (read the count). "the saved test uses 2" (read it).
  LogReg.enet notes "Best of six models at their defaults on 16 September, 0.995 on the
  blind period." Execution "measured 5.0 bp a fill on average, 4.6 typical, over 21
  fills on 22 Sep 2026." Reports "The daily book report and the execution report, one
  file per report under a dated folder; the last is dated 22 September." Repeated k-fold
  "Claimed error 0.09 below the blind period, as k-fold did." "C1's Scores is one run at
  one configuration; this is all of them." RMSE "Lower is better. A constant guess scores
  about 0.46 at a base rate of 0.30."
- **Effort.** S.
- **Command.** clarify.

### BRD-14 Replace figurative words and aphorisms

- **Surface.** Board, public page and export.
- **Severity.** P2.
- **Evidence.** The lines in Appendix C, each with its source line.
- **Why it matters.** They break Seamus's first writing rule and several state a claim
  with no number behind it.
- **Proposed change.** Apply Appendix C.
- **Effort.** S.
- **Command.** clarify.

### BRD-15 Take the colons out of prose

- **Surface.** Board, public page and export.
- **Severity.** P2.
- **Evidence.** 105 strings on the board, 91 on the public page. The source sites are in
  Appendix D. Two template lines produce 42 of them, `control_varselect.py:595` (the 33
  B1 hovers "fitted alone: -0.0300 log-odds, p 0.330") and `card.html:425` (9 A2 cell
  hovers "column: The column as it is named in the panel."). Six script lines build more
  at run time, `card.html:916` (every option note, "balanced: Upweights the rarer
  outcome"), `:928` ("f_mst_dir: Adaptive Supertrend direction"), `:953` ("2 coins picked:
  LINK, LTC."), `:999` ("Example: with a typical daily move"), `:1055` ("Here: 12 bars"),
  and `demo_site.snapshot.py:743, 745, 712` ("Held to the demo limits:", "The run
  failed:", "failed:").
- **Why it matters.** The colon is banned in prose on the same terms as the em dash.
- **Proposed change.** Apply Appendix D. For the generated lines, "balanced, which
  gives the rarer outcome more weight", "Alone, -0.0300 log-odds (p 0.330)", "2 coins
  picked, LINK and LTC.", "For example, with a typical daily move of 2 per cent ...",
  "12 candles of 4 hours, 2 days."
- **Effort.** M.
- **Command.** clarify.

### BRD-16 Remove the em dash and the middle dots

- **Surface.** The em dash on the board only; the middle dots on the board, the public
  page and the export.
- **Severity.** P2.
- **Evidence.** Em dash, `control_templates/card.html:1186`, the Beat a constant guess
  label after it is ticked, which reads "Beat a constant guess", an em dash (U+2014), then "119 of 574". Middle dots,
  `base.html:56` and `card.html:4` "Swing Trader · Control Centre", `card.html:5` "A1 ·
  Data", `base.html:78, 80, 82` the money line, `base.html:85` "seamusrobertmurphy/swing-trader
  · nothing here can place an order", `index.html:86` "9 charts · settings",
  `card.html:115` "PAPER · testnet", `control_export.py:422`.
- **Why it matters.** Both are banned separators.
- **Proposed change.** "Beat a constant guess, 119 of 574". Title "Control Centre" (see
  BRD-18). Panel name "A1 Data". Money line "$102,206, up $2,206. Open 50, up $4,481.
  Closed 58, down $2,265. Cash $10,246." Repository line "seamusrobertmurphy/swing-trader.
  Nothing here can place an order." Card foot "9 charts and settings". Mode "PAPER, on
  the testnet".
- **Effort.** S.
- **Command.** typeset.

### BRD-17 Put a gloss on every results heading

- **Surface.** Board C1 The last run table, public C1, export. `control_tables.py:1762`
  (headings) against the gloss keys at `control_tables.py:52-127`.
- **Severity.** P2.
- **Evidence.** The eleven headings "RMSE, held out", "RMSE, in sample", "MAE, held out",
  "MISE, held out", "overfit ratio", "folds beating a constant", "RMSE, blind", "U2,
  blind", "AUC, blind", "max_depth" and "n_estimators" carry an empty `title`. The glosses
  exist under other keys ("RMSE CV", "MISE CV", "ratio", "blind U2"). MISE is defined
  nowhere a reader can reach. The C1 This run and model tables' headings "model", "fits",
  "its best", "when", "this run" also carry none (`card.html:248`).
- **Why it matters.** The one table that reports the last run is the one with no
  definitions.
- **Proposed change.** Key the glosses by the headings in use, and add "MISE, folds,
  the integrated squared error of the calibration curve on the folds; lower means the
  stated probabilities match how often wins happen."
- **Effort.** S.
- **Command.** clarify.

### BRD-18 Keep headings to three words

- **Surface.** Board, public page and export.
- **Severity.** P3.
- **Evidence.** `base.html:56` h1 "Swing Trader · Control Centre", four words.
  `card.html:4-5` h1 on every panel "Swing Trader · Control Centre A1 · Data", six words.
  `index.html:66` each front card h2 contains its tag, so the heading reads "A1 Data
  market, basket, filter, ranking, label" (seven words) for A1, A2 and C1 and five for
  B2. `card.html:544` summary "Other runs on this panel", five words. The working copy of
  `demo_site.py:302` adds "What the columns mean", four words.
- **Why it matters.** The heading rule is three words, and a screen reader announces the
  whole tag list as the heading.
- **Proposed change.** h1 "Control Centre", with "Swing Trader" kept in the browser title.
  Panel h1 "A1 Data", with the site name as a link outside the heading. Move the tag out
  of each h2 into `<p class="tag">`. Summary "Other runs". "Column meanings".
- **Effort.** S.
- **Command.** typeset.

### BRD-19 Name what each button does

- **Surface.** Board, all panels with jobs; public for the Save button. `card.html:534-535,
  596-599, 9-16, 152, 1310`, `control_varselect.py:618-624`.
- **Severity.** P2.
- **Evidence.** Every job's button reads "Run it", under nine differently named jobs,
  while the steps say "Press Run the test", "Press Screen variables", "Press Compare
  regimes" and the console says "Press Run and the script's own output arrives here.".
  "Reset" beside Run reloads the page, while "Reset defaults" on a form restores that
  block's defaults. "Load best as defaults" replaces the saved settings with the best
  run's, not with defaults (`control_centre.py:573`, the route's own description). "Show run code" and "Show all code"
  do not say which code. "Stop" does not say what it stops. A failed run reads "exit code
  1 after 24 seconds." (`card.html:1310`). B1's figure buttons read "six largest alone"
  and the loading text "Fitting.". The lightbox failure reads "the full-size draw failed;
  the panel still has the small one" (`card.html:1271`).
- **Why it matters.** A label should say what will happen.
- **Proposed change.** Button text equals the job title, "Run the test", "Screen
  variables", "Rank columns alone", "Compare resampling", "Compare models", "Assess
  models", "Check the split", "Trend length", "Profit by confidence". Console "Nothing
  has run yet. Press a Run button above and its output appears here." "Reset" beside Run
  becomes "Undo changes". "Reset defaults" becomes "Reset this block". "Load best as
  defaults" becomes "Load the best run's settings". "Show the fitting code" and "Show the
  workflow document". "Stop the run". Failure "The run stopped after 24 seconds with exit
  code 1. The last lines of the output above say why." B1 buttons "elastic-net
  survivors" becomes "Kept by the elastic net", "six largest alone" becomes "Six
  strongest alone", loading "Fitting the ticked columns." Lightbox "The large version
  could not be drawn. The small chart on the page is correct."
- **Effort.** S.
- **Command.** clarify.

### BRD-20 Take paths and file names out of readable text

- **Surface.** Board, and the public page where marked.
- **Severity.** P2.
- **Evidence.** Visible text on C1 This run, "04-outputs/AA-evals/bench/config.json. A1
  Data wrote data, screen, label; ..." (`control_tables.py:1460-1462`), ".venv/bin/python
  03-inputs/bench_run.py --label loop-record" (`control_tables.py:1444`), and the record
  link text "04-outputs/AA-evals/2026-09-22/bench-20260922-220829.md" (`card.html:224`).
  The workflow block "02-runtime/trader-workflow.qmd, the one document every analysis has
  to live in." (`card.html:759`) once shown. Hover text "Every fit in every record under
  04-outputs/AA-evals" (`card.html:236`), "The function inside 03-inputs/build_dataset_1h.py"
  (`control_tables.py:155`), "(05-research/research/caret-package.pdf, createTimeSlices,
  pages 30 to 31.)" (`bench_config.py:672-673`, also public), "2,000 rows of
  dataset_1h_allmarket.parquet" (`control_varselect.py:175`, also public), "slice_4h_40k
  is a 25 MB cut" (`bench_config.py:497`, also public), "Record bench-20260921-201704.json."
  (`bench_config.py:1297`, also public). Image alt text is the chart key on every panel,
  "data-cube", "ranking-preview" (`card.html:337, 380, 721`), and the front reel's
  caption is the file name for gallery figures, "2A-screen_20260620.png",
  "bench-20260922-220829-importance.png" (`control_centre.py:311`, also public).
- **Why it matters.** The standing rule of 20 September is no script or data path in
  readable text on a panel.
- **Proposed change.** "The saved settings file. A1 Data wrote data, screen and label;
  ..." "bench_run, named loop-record" or the step "The model test, named loop-record".
  Record link text "Open the record". "The workflow document, where every analysis
  lives." Hovers "Every fit on record that passed the overfit cap", "The function in the
  dataset builder that emits this column", "(caret package manual, createTimeSlices,
  pages 30 and 31)", "2,000 rows of the 1-hour file", "The 4-hour test sample is a 25 MB
  cut". Best so far ends "Recorded 21 September 20:17." Alt text from `CHARTS` captions,
  "What the filter and ranking leave, from the current settings". Reel captions from the
  figure's own title or "Earlier figure, 20 June 2026".
- **Effort.** M.
- **Command.** clarify.

### BRD-21 Describe only the chosen settings under Choose Settings

- **Surface.** Board C1 Choose Settings, public C1, export. `card.html:908-919`
  (`describeOptions`).
- **Severity.** P3.
- **Evidence.** The note line under Choose Settings describes every select in the form,
  including the hidden blocks of unticked models, with only the option word as a prefix.
  The export shows "sqrt: Square root of the column count per split, the forest default.
  gini: Gini impurity, the default. on: Each tree sees a resample of the rows. gbdt:
  Standard gradient boosting. off: Runs every round. all: Every column per split, the
  library default. lbfgs: The plain fit." with only RF ticked.
- **Why it matters.** "on" and "off" mean nothing without the setting's name, and four of
  the seven notes are for models that will not run.
- **Proposed change.** Skip selects inside a hidden `.hyperblock`, and prefix each note
  with the field label, "Resample rows per tree, on, each tree sees a resample of the
  rows."
- **Effort.** S.
- **Command.** clarify.

### BRD-22 Write large numbers the way people read them

- **Surface.** Board A1 and public A1. The input values rendered at `card.html:106`.
- **Severity.** P3.
- **Evidence.** "Volume floor, USDT a day" shows "30000000.0" (`demo-phone/A1-top-04.png`).
- **Why it matters.** Eight digits and a decimal are hard to read as 30 million.
- **Proposed change.** Show "30,000,000" in the box, or relabel "Volume floor, million
  USDT a day" with the value "30".
- **Effort.** S.
- **Command.** typeset.

### BRD-23 Use one case for headings

- **Surface.** Board, public page and export.
- **Severity.** P3.
- **Evidence.** Title case "Hard Rules", "Evidence Log", "Choose Blind Period", "Choose
  Grid Search" beside sentence case "Trade geometry", "Feature families", "Resampling
  regimes", "What to do", "The workflow". A1's "Trade geometry" block (`card.html:363`)
  holds seven figures of which five are about spread and screening.
- **Why it matters.** Small, but mixed case reads as two systems.
- **Proposed change.** Sentence case throughout, "Hard rules", "Evidence log", "Choose
  blind period". Rename "Trade geometry" to "Rule figures".
- **Effort.** S.
- **Command.** polish.

## Export

### EXP-01 Word the export footer without a path

- **Surface.** Export, foot of every page, and the frozen note on each form.
  `control_export.py:430-432`, `control_export.py:111`.
- **Severity.** P3.
- **Evidence.** "Exported file. Saved 24 September 2026 07:20. Opens with no server. To
  run jobs or change settings, start the served page with the control centre script in
  05-research/scripts." and "Settings as saved. Change them on the served page, not
  here."
- **Why it matters.** It prints a folder path and calls the board "the served page".
- **Proposed change.** "Saved 24 September 2026 07:20. This file opens without a server,
  so it cannot run jobs or change settings. Start the control centre on the Mac to do
  either." and "Settings as saved. Change them in the live control centre, not in this
  file."
- **Effort.** S.
- **Command.** clarify.

The export also carries every board entry above, because it is rendered from the same
templates; it was last built on 24 September, so it shows older counts.

## What works

Keep these. The verdict sentences on C1 name what failed in plain words, "RF is not
usable, it did no better than guessing the average", once the colon goes. The What
changed since last time row compares a score change with the bench's own spread, "an
improvement smaller than that is not an improvement", which is the product's fourth
principle stated with its number. The In force column of Hard Rules says "Not in force"
and "Switched off for the basket" rather than implying every rule runs. The money
glosses report dollars and explain why ("A 16 per cent fall on a small holding and a 2
per cent fall on a large one can be the same dollars"). The C1 Scores table gives each
score a definition and its bar in one row. The Resampling table reports each scheme with
its measured gap. The From your settings line names the tool that owns each value
instead of offering it twice. On the public page, "Nothing is bought or sold." is short
and true, and the working copy's column dictionary and C2 guide are the right idea.

## False positives

- The en dash in `control_charts.py:1347` joins two dates, a number range, which is
  allowed.
- The full script path in each Run button's `title` is by design (DESIGN.md, the run
  command is the Run button's tooltip), so it is not listed in BRD-20.
- "seamusrobertmurphy/swing-trader" and pairs such as "LINK/USDT" were caught by the
  slash check and are a repository name and trading notation.
- Times such as "20:17", "p < 0.001", "LIVE_TRADING=true", "key=v1,v2" and the grid
  string are technical notation.
- The colon inside the caret quotation "if FALSE, all training samples start at 1" is
  quoted text; the colon before the quotation is still prose and is in Appendix D.
- The "fitted alone" hovers on B1 read as label and value; they are counted and a
  replacement is offered, but they could stand as notation if Seamus prefers.

## Appendix A, house terms

"Board" says whether the board label should change or keep its label and gain a gloss.
The public page always takes the plain form.

| On screen | Where | Plain replacement | Board |
| --- | --- | --- | --- |
| Quick pick | A1, `bench_config.py:502` | Coin list | change label |
| scalp-eight, btc-eth, large-caps, sector-funds, majors | A1 options, `bench_config.py:340-349` | Eight coins for scalping, Bitcoin and Ether, Eight large US stocks, US sector funds, Six big coins | change option text |
| Keep third (all, top, bottom) | A1, `bench_config.py:559` | Which third to keep (all, strongest third, weakest third) | change label |
| Fold pass rate | A1, `bench_config.py:568` | Folds that must beat guessing | change label |
| Rank by f_mst_dir, f_d1_st_up, f_btc_mom_168, f_st_agree | A1, `bench_config.py:549-550` | Adaptive Supertrend direction, Daily Supertrend up, Bitcoin's move over a week, Supertrend lines agreeing | change option text |
| screen (A1 table "The screen a name must pass") | `control_tables.py:133` | filter | change |
| Regime (A1 Screening row) | `control_tables.py:638` | Market state | change label |
| degenerate | A1 Horizon note, `bench_config.py:528` | useless, since only 6.8 per cent of candles are wins | change |
| klines, top of book | A1 Volume note, `bench_config.py:541` | price files, best bid and ask | change |
| slice_4h_40k | A1 Timeframe note and masthead, `bench_config.py:497`, `:1175` | the 4-hour test sample | change |
| data cube | A1 caption, `control_charts.py:3944` | How the data table is built | change caption |
| Panels built and available | A1 caption, `control_charts.py:3950` | Data files built | change caption |
| charter | A1 Hard Rules, `control_tables.py:738, 746` | the trading rules written in May | change |
| Big pitch, Narrow book | A1, `control_tables.py:702, 640` | One larger position, Coins that passed before | gloss |
| f_wc_ to f_ms_ families | A2, `bench_config.py:354-369` | the family's plain name, "Days-long windows", "Short windows", "Classic oscillators", "More oscillators", "TA-Lib extras", "Three Supertrends", "Adaptive Supertrend", "Against bitcoin", "4-hour context", "Daily context", "Weekly context", "Buying pressure", "Market state", "Hourly detail" | change option text, keep code in a hover |
| survivors, Fit on survivors | B1 lead and field, `control_registry.py:684`, `bench_config.py:613` | kept columns, Fit on kept columns | change label |
| L1 mix | B1, `bench_config.py:595`, `control_registry.py:339` | Lasso share | change label |
| 1se, min | B1, `bench_config.py:598` | simplest within one standard error, lowest error | change option text |
| Regime (B2 field and table) | `bench_config.py:662`, `control_tables.py:889` | Resampling | change label |
| kfold, repeated-kfold, monte-carlo | B2, `bench_config.py:663-664` | k-fold, repeated k-fold, Monte Carlo | change option text |
| best, oneSE | B2, `bench_config.py:705-706` | lowest error, simplest within one standard error | change option text |
| Axis | B2 and C1 jobs, `control_registry.py:453, 477` | What to compare | change label |
| comparison run | many, BRD-10 | grid search, or run, or record | change |
| overfit bar, house bar, cap | many, BRD-12 | overfit cap | change |
| constant guess | many | constant guess, defined once as a forecast that always says the base rate | gloss |
| blind top fifth | C1, `card.html:199` | the most confident fifth, on the blind period | change |
| Three-way | C1 heading and line, `control_registry.py:810`, `card.html:199` | Up, down or flat | change label |
| How hard to tune | C1, `bench_config.py:733` | Values per setting | change label |
| Grid search over / Compare one model over a grid | C1, `bench_config.py:725`, `control_registry.py:370` | Model to tune (both) | change label |
| TUNE_GRIDS | C1 hints, `bench_config.py:740`, `control_registry.py:285` | the model's own grid | change |
| LogReg.glm, LogReg.enet, RF, HistGBM, GBM.classic | C1 options and headings, `bench_config.py:371-372` | Logistic regression, Elastic-net logistic regression, Random forest, Histogram gradient boosting, Classic gradient boosting | change option text, keep code in tables |
| Trend-life search | C1, `control_registry.py:317` | Trend length | change label |
| Score edge | C1, `control_registry.py:417` | Profit by confidence | change label |
| Audit split | C1, `control_registry.py:252` | Check the split | change label |
| Skip imbalance, Skip bracket, Skip permutation | C1, `control_registry.py:260-263` | Skip class balance check, Skip random-split comparison, Skip column importance | change label |
| selectivity | C2 Figures option, `bench_config.py:774` | return by confidence | change option text |
| Which axes have been varied, What moves the answer, by axis | C2 captions, `control_charts.py:3974, 3978` | Which settings have been varied, What each setting does to the score | change caption |
| Live book | C2 heading, `control_registry.py:857` | Run history | change label |

## Appendix B, field notes the public page should show

These are the notes a friend would read once PUB-01 makes them visible, in plain form.

| Field | Plain note |
| --- | --- |
| Timeframe | How long each candle is. 4 hours is the timeframe most tests here used. |
| Volatility band, lower and upper | How far a coin must move in a typical day, as a share of price; 0.015 is 1.5 per cent. Below the band there is nothing to catch; above it the stop is hit by noise. |
| Volume floor | At least this many dollars traded in the last 24 hours, so a coin can be bought and sold without moving its price. |
| Minimum history, days | A coin must have this many days of prices, so every measure the model reads can be computed. |
| Rank by | Orders the coins at each candle, strongest first, by the measure chosen. None keeps every coin. |
| Which third to keep | Strongest third keeps the top third of that order; weakest third is the comparison. |
| Take-profit, Stop | Not yet used by the run (BRD-05). |
| Horizon | How many candles a trade is held before it closes. |
| Outcome | Win or loss, or up, down or flat. |
| Break-even band | A move smaller than this share of price counts as flat; 0.002 is the 0.20 per cent trading cost. |
| Lasso share | 1 drops weak columns entirely; 0 only shrinks them. |
| Blind days | The most recent days kept back and used once, at the end, to test the model. |
| Embargo | A gap of candles between training and testing, so a trade that looks ahead cannot see the test period. |
| Resampling | How the training history is cut into folds to check the model before the blind days. Expanding and rolling keep time in order. |
| Folds | How many pieces the training history is cut into. |
| Class weight | Balanced makes wins count for more when the model is fitted; none leaves them as they are and scored better. |
| Overfit cap | The model is rejected if its error on unseen folds is more than this many times its error on the training rows. |

## Appendix C, figurative words and aphorisms

| Current | Source | Replacement |
| --- | --- | --- |
| "Ranking coins by strength works, but the fee eats it." | `control_tables.py:598-599` | see BRD-03 |
| "A volatile coin with thin volume is a trap." | `bench_config.py:303-304` | "A coin that moves a lot but trades little costs more to buy and sell than its moves pay." |
| "It is not free." | `bench_config.py:744` | cut |
| "sqrt is what makes a forest a forest rather than a bag of identical trees." | `bench_config.py:398-400` | "sqrt makes each tree look at different columns, so the trees differ." |
| "The main brake on memorising: raise it when the overfit ratio climbs." | `bench_config.py:394-395` | "Raising it is the main way to stop the forest memorising its training rows; raise it when the overfit ratio rises." |
| "the real capacity knob", "the capacity knob" | `bench_config.py:414, 431` | "the main control on model size" |
| "Solver iterations before it gives up." | `bench_config.py:454` | "Most solver steps before it stops." |
| "gini or entropy. Rarely changes much." | `bench_config.py:402` | "gini or entropy. Changing it rarely moves the score." |
| "A trade that has not worked by then usually will not, and the money is wanted for the next one. Shorter trades more often with less room; longer ties money up." | `card.html:133` | "A shorter horizon gives more trades with less room to move; a longer one holds money for longer." |
| "offered here to be measured, not believed" | `bench_config.py:557-558` | "offered here for testing only" |
| "the only honest choices on prices", "flatters a fit" | `bench_config.py:179-180` | "the only choices that keep later prices out of training", "claims less error than the blind period finds" |
| "the honest value is the label horizon" | `bench_config.py:653-654` | "set it to the label horizon, 12 candles here" |
| "which is the honest way to measure what the screen cost" | `bench_config.py:615-616` | "so the score shows what the screen cost" |
| "flatters the fit", "The most flattering regime on a price series" | `bench_config.py:200-202` | "claims less error than it should", "Claims the least error of any scheme on prices" |
| "The honest one." | `control_tables.py:59` | "The number the overfit cap and the choice of model use." |
| "The money column." | `control_tables.py:97` | cut |
| "This is the money." | `control_tables.py:47-48` | cut |
| "The column that adds up." | `control_tables.py:52-53` | "These add up to the account's whole change." |
| "The largest single lever measured here" | `control_tables.py:124` | "The setting that moved the error most" |
| "Positive on unseen data, or it does not ship." | `control_tables.py:949` | "Must be positive on the blind period, or it is not traded." |
| "The most flattering: 0.12 below the blind period." | `control_tables.py:898` | "Claimed error 0.12 below the blind period, the largest gap." |
| "Same leak, ten times." | `control_tables.py:896` | see BRD-13 |
| "So the screen cannot peek at the answer." | `control_tables.py:882` | "So the screen never sees the test data." |
| "same appetite for memorising noise as HistGBM" | `control_tables.py:926` | "memorises noise as readily as HistGBM" |
| "One name cannot sink the book." | `control_tables.py:692` | "No single holding can lose more than 5 per cent of the account." |
| "Full Kelly ruins the account on a mis-estimated edge." | `control_tables.py:698` | "Full Kelly sizing loses heavily when the estimated odds are wrong." |
| "Stops a bad day compounding into a decision made badly." | `control_tables.py:727` | "No new orders after a 3 per cent loss, until the 24 hours pass." |
| "amputates the strategy that was tested" | `control_tables.py:732` | "removes most of the trades the tested strategy made" |
| "Cuts a losing trend short before it becomes a hole." | `control_tables.py:739` | "Limits the loss on a falling price." |
| "Lets a winner run and keeps most of what it made." | `control_tables.py:747` | "Keeps most of a gain when a rising price turns down." |
| "which is the difference between a brake and a switch" | `control_tables.py:754` | cut |
| "Forces selectivity on a discretionary book." | `control_tables.py:759` | "Limits how many new names are bought in a week." |
| "A loser is sold or held, never fed." | `control_tables.py:764` | "A falling holding is sold or kept, never bought more of." |
| "Decide on what happens next, not on what was paid." | `control_tables.py:771` | "Hold or sell on the expected return from here, not on the price paid." |
| "The fee is the adversary." | `control_tables.py:777` | cut |
| "A strategy that cannot pay its fee is not a strategy." | `control_tables.py:784` | "A strategy that earns less than its fee loses money." |
| "capped so that reading a large panel cannot take the page down" | `control_varselect.py:607-608` | "capped so the page stays responsive" |

## Appendix D, colons in prose by source

Replace each colon with a comma, a full stop, or "such as", as shown.

| Source | Current, from the colon | Replacement |
| --- | --- | --- |
| `base.html:57` | "Three columns: choose the inputs, ..." | "Three columns, choose the inputs, fit and tune the model, read the result." |
| `control_registry.py:241-242` via `index.html:39` | "Timeline: every run in order, ..." | "Every run in order, with its headline result" |
| `control_registry.py:610, 612, 614` | "Where a trade is closed: hard stop, ...", "The four gates on the live market: volume, ...", "... daily volatility: does the move cover the cost" | "Where a trade is closed, by hard stop, trailing stop or take-profit", "The four live-market gates, volume, volatility, history and spread", "The buy-sell gap against daily volatility, and whether the move covers it" |
| `control_registry.py:641` | "Set the gates on Choose Filter: how much a name must move, ..." | "Set on Choose Filter how much a name must move, how much must trade and how long it must have existed." |
| `control_registry.py:675` | see BRD-05 | |
| `control_registry.py:699` | "Choose Screen: the lasso-to-ridge mix, ..." | "Set the elastic net on Choose Screen, the lasso share, the penalty rule, and how many rows and folds." |
| `control_registry.py:748` | "Three bars decide it: did it ..." | see BRD-04 |
| `control_registry.py:318` | "... on a different target: bars until ..." | see BRD-10 |
| `control_registry.py:451` | "... one blind period: what each regime claimed ..." | "Same model, seven resampling schemes and one blind period, showing what each claimed against what was found." |
| `control_registry.py:456-459` | "forest settings: the random forest's own settings. resampling regime: ..." | "Forest settings varies the random forest's own settings. Resampling varies the fold scheme on the usual forest. ..." |
| `control_registry.py:810`, `card.html:199` | "Three-way: best blind top fifth" | "Up, down or flat, best most-confident fifth" |
| `control_registry.py:519-521` | "... every panel has saved: these coins, ..." | "Fits and scores the model on the settings every panel has saved, such as these coins, ..." |
| `card.html:752-753` | "... the code that spends them: section 3.15 ..." | "The saved settings, then the code that uses them, which is section 3.15 of the workflow document." |
| `card.html:458` | "From your settings:" | "From your settings," |
| `card.html:425` | "{heading}: {gloss}" on 9 A2 cells | "{heading}, {gloss}" |
| `card.html:916, 928, 953, 999, 1055` | option notes, rank note, basket note, example, horizon | see BRD-15 |
| `bench_config.py:115-117` | "A candle is one bar of price history: the open, ..."; "a win or a loss: a win if ..." | "A candle is one bar of price history, its open, high, low and close. The label marks each candle a win if price reaches the take-profit before the stop within the horizon, and a loss otherwise." |
| `bench_config.py:182-184` | "Overfit cap: a model whose ..." | "The overfit cap rejects a model whose ..." |
| `bench_config.py:185-186` | "... a grid search: every combination of the grid: key=value,value pairs ..." | "Naming a model turns the run into a grid search, which fits every combination of the grid in turn." |
| `bench_config.py:220, 222`, `control_tables.py:812-814, 818` | "Classic oscillators: Williams %R, ...", "TA-Lib extras: ...", "More oscillators from the pandas-ta library: ...", "The state of the market: ..." | "Classic oscillators, Williams %R, Stochastic, ...", and the same pattern |
| `bench_config.py:262-263, 519-521` | "barrier: win or loss. three-way: ..." | "Barrier is win or loss. Up, down or flat adds a flat class for moves inside the fee band." |
| `bench_config.py:296-304`, `control_tables.py:618` | "the Average True Range: the average ..." | "the Average True Range, the average ..." |
| `bench_config.py:305-307` | "Fold pass rate: the history ..." | see BRD-05 |
| `bench_config.py:397-398` | "Columns tried at each split: the square root ..." | "Columns tried at each split, the square root of the count, its log, a share of them, or all." |
| `bench_config.py:394` | "The main brake on memorising: raise it ..." | see Appendix C |
| `bench_config.py:553-554` | "... the 42 tried in June: its top third ..." | "... the 42 tried in June; its top third ..." |
| `bench_config.py:561-563` | "Bottom keeps the weakest and is the control: the finding is ..." | "Bottom keeps the weakest and is the comparison, because the finding is the gap between the two." |
| `bench_config.py:660` | "... in the September grid: three folds 0.4840, ..." | "... in the September grid, 0.4840 at three folds and 0.4894 at five, against a grid spanning 0.033." |
| `bench_config.py:666-667, 685` | "... deciding between them: “if FALSE ...”", "says the same: “for repeated ...”" | "... deciding between them, and its manual says “if FALSE, all training samples start at 1”", "and its manual says the same, “for repeated k-fold cross-validation only”" |
| `bench_config.py:751` | "Cross-validated RMSE over training RMSE: how much worse ..." (also `control_tables.py:942`) | "Cross-validated RMSE over training RMSE, which shows how much worse the model does on rows it did not see." |
| `bench_config.py:1294` | "Best of 574 fits so far: rf." | see BRD-01 |
| `control_tables.py:55, 82, 100, 111, 124, 131, 132` | "Which configuration produced the row: ...", "... call was read off: ...", "... for every blind row: ...", "... this fit was: ...", "... lever measured here: ...", "The crypto venue: ...", "The equity venue: ..." | "Which configuration produced the row, its symbols, folds and class weight.", "What the up, down or flat call was read from, the close-to-close return or the barrier trade's return.", "The same mean over every blind row, which is the market's own drift less cost.", "Which of the six forest settings this fit was, the library defaults, ...", "... the setting that moved the error most, 0.0255 on matched conditions.", "The crypto venue, Binance spot, read from the public archives.", "The equity venue, Alpaca's paper account on the SIP feed." |
| `control_tables.py:70-72` | "Theil's U2 on the held-out period: the model's error ..." | "Theil's U2 on the blind period, the model's error over the error of always guessing the base rate." |
| `control_tables.py:646, 650` | "... through its API key: 0.15 per cent ..." | "... through its API key costs 0.15 per cent ..." |
| `control_tables.py:742, 772, 786, 960` | "... is still unsettled: the code carries ...", "... three things only: the catastrophe stop, ...", "... has cleared it: buying last year's ...", "The paper account in dollars: open and closed ..." | full stops or commas, "... is still unsettled. The code carries ...", "... three things only, the catastrophe stop, realised profit and loss, and tax.", "... has cleared it, buying last year's strongest stocks, by 1.0 per cent a month.", "The paper account in dollars, with open and closed positions, cash, and the curve since 18 August 2026." |
| `control_tables.py:871` | "... by likelihood ratio: does it explain the outcome at all?" | "... by likelihood ratio, to see whether it explains the outcome at all." |
| `control_tables.py:1057, 1096` | "... own randomness: an improvement ...", "... the run of 2026-09-22 21:37: every setting is the same." | "... own randomness, so an improvement smaller than that is not an improvement.", "Nothing was changed since the run of 2026-09-22 21:37, and every setting is the same." |
| `control_tables.py:1211` | "... exactly to zero: 1 is all of it, 0 is none." | "... exactly to zero, where 1 is all of it and 0 is none." |
| `control_tables.py:250` | "Every run on disk: 125 runs, ..." | "Every run on disk, 125 runs and 574 fits, ..." |
| `control_tables.py:1501-1506` | "not usable: it did no better ..." | "not usable, because it did no better than guessing the average" |
| `bench_run.py:1203` | "Named but not in this frame, so ignored: F_ST_AGREE." | "F_ST_AGREE was named but is not in this file, so it was ignored." |
| `control_interactive.py:382, 434, 508` | "..., which matters: the largest gaps ...", "The line only ever falls: it is ...", "... the diamonds are milestones: the few points ..." | "..., which matters because the largest gaps ...", "The line only falls, because it is the best result available on that day.", "... the diamonds are milestones, the few points ..." |
| `control_varselect.py:180` | "Read it right to left: at the strongest penalty ..." | "Read it right to left. At the strongest penalty ..." |
| `control_varselect.py:595` | "fitted alone: -0.0300 log-odds, p 0.330" | "Alone, -0.0300 log-odds (p 0.330)" |
| `demo_site.snapshot.py:712, 743, 745` | "failed: ...", "Held to the demo limits: ...", "The run failed: ..." | see PUB-05 |
