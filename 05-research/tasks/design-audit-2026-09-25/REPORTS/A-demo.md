# Design review A

Assessment A of the public friends page, written 25 September 2026 for a friend of Seamus who is new to trading and to models and opens the page on a phone.

## Scope and build

The live page at https://seamusrobertmurphy.github.io/swing-trader/ was gh-pages commit 8489ead8, built 25 September 17:02, while the captures in `demo-phone/` and `demo-desk/` are of the 16:26 build. Two differences between them were checked and are not reported, because the live page already fixed them, the badge now reads PAPER ONLY and the empty totals now read none yet. Every finding below was confirmed on the live build, either in the older captures where nothing changed or in the eleven new captures under `A-demo/`. Line numbers refer to the working copy of `03-inputs/demo_site.py` as read during this review, which another agent was editing at the same time, so each is given with its constant or function name as well. Nothing that posts was pressed. One navigation chip was tapped headlessly to test routing, by `A-demo/navcheck.mjs`, which reads and screenshots only.

## Scores

| # | Heuristic | Score | Key issue |
|---|-----------|-------|-----------|
| 1 | Visibility of system status | 2 | Run status is a grey 14 px note with no progress and no live region, the current panel is never marked, and a run in progress is forgotten on reload |
| 2 | Match with the real world | 1 | Choices are code names (RF, LogReg.glm, f_wc_, monte-carlo, learning_rate=0.03), and the page is titled Control Centre |
| 3 | User control and freedom | 2 | Back leaves the site after a panel tap, there is no reset on the public page, and a started run cannot be followed after leaving |
| 4 | Consistency and standards | 2 | Run Model looks like the presets and the eight Save buttons, the overfit cap reads 1.3 in one place and 1.1 in three, and "passes" sits beside a result worse than guessing |
| 5 | Error prevention | 1 | Unpreset runs use the operator's scratch settings, the name is published without warning, and desktop multi-selects drop choices on a plain click |
| 6 | Recognition rather than recall | 1 | What RF or f_btc_ means is in a table further down the page, field help is in tooltips a phone never shows, and a preset's changes on other panels are invisible |
| 7 | Flexibility and efficiency | 3 | Presets and Run Model sit inside the first phone screen, so a friend can run in two taps, but the phone scoreboard cannot be sorted |
| 8 | Aesthetic and minimalist design | 1 | C1 runs to 343,870 px on a phone and every panel carries the operator's evidence log, file names and stock-market tables |
| 9 | Error recovery | 2 | Relay errors are plain and specific, but a failed run shows the raw Python exception and errors look the same as progress |
| 10 | Help and documentation | 2 | C2's About this page is good, but the front page never says what the page is, and the What to do lists name buttons that were removed |
| **Total** | | **17/40** | **Poor** |

## Specificity verdict

The page is two products stacked. Underneath is the operator's board, specific to this repository down to the lane badges, the three error columns and verdicts that say what failed, and no other product would carry it. On top sits a thin friend layer of Quick start, Run your model, About this page and the ticket board, dressed in generic consumer clothing, white rounded cards, pill buttons, an off-white ground and Jost, and laid over the board by styles in `demo_site.py` that carry 110 `!important` declarations. The seams show in the cool blue-grey rules under every heading, the navy masthead and the washed-out lane colours. The one object that belongs to this reader, the paper ticket, the thing a friend makes and comes back for, is drawn as a generic ten-row key and value card with an empty After cost row. The content is authored for this product, the structure is authored for a different reader, and the friend layer could sit on any light-themed app unchanged.

## Cognitive load

Seven of the eight checklist items fail, which is high cognitive load. Only grouping passes, because the rounded cards group their contents well. Single focus fails because the phone front page opens on the operator's account figures and six panel chips before Quick start. Chunking fails on C1, where each scoreboard card has 19 rows. Visual hierarchy fails because Run Model has the same grey fill as three presets and eight Save buttons. One thing at a time fails because every panel mixes the friend's settings with reference tables and the operator's records. Working memory fails because a model or feature family is chosen by code name and explained in a table below the list. Progressive disclosure fails because all 574 scoreboard rows and all 90 column descriptions are open.

Decision points over four options are the front page with 19 interactive elements, the A2 Families list with 15 options, the A2 Also include and Leave out lists with 90 each, the A1 coin list with 14, the B2 Regime list with 7 and the C1 Models list with 6.

## Emotional journey

The first ten seconds on a phone are uncertain. The title says Swing Trader Control Centre, six chips say Data, Indicators, Variables, Training, Scoreboard and Ledger, and the first number is $102,206 with a green $2,206 beside it, which a friend reads as someone's money, possibly real, before the small PAPER ONLY badge. The Run block does say that nothing is bought or sold, but the line that names the page as a paper trading demo sits at the foot of the front page, 2,700 px down, in red. Quick start then brings relief, three large buttons, though nothing says which one to press. The peak comes three to five minutes after Run Model, when the status reads "Done. 2 paper tickets issued with RF. See them on C2 Ledger", but only for a friend who waited on the page. The end is a valley. C2 shows tickets marked open with a blank After cost, due two days later, a chart on which every run sits above the dashed Guessing the average line, and no way to be reminded. Under the peak-end rule a friend remembers pressing a button, getting nothing yet, and a model worse than guessing, which is not a memory that brings them back. The end needs to be designed, with the settle time, a reminder, and one honest sentence that most runs do not beat guessing and that finding out is the point.

## Findings

### 1. Make Run Model amber

- **Surface.** Public phone and desktop, front, B2 and C1. `03-inputs/demo_site.py` LIGHT_CSS line 1142 `.btn, button.btn { background:#ecebe7 !important }` against line 1145 `.demo-go { background:#f0a830 !important }`.
- **Severity.** P1.
- **Evidence.** `A-demo/front-top-01.png`, `demo-phone/front-top-01.png` and `demo-desk/front-top-01.png` all show Run Model in the same grey as the three presets. Both rules are `!important`, so the more specific `button.btn` (0,1,1) beats `.demo-go` (0,1,0). The grey fill measures 1.19 to 1 against the white card. On desktop the button turns amber only on hover, because `.demo-go:hover` (0,2,0) does win.
- **Why it matters.** The one action the page exists for looks like eleven other buttons, so a friend has to read to find it, against the approved design of one amber Run button.
- **Proposed change.** Change line 1145 to `.btn.demo-go, button.btn.demo-go { background:#f0a830 !important; color:#2a2520 !important; }` and line 1146 to `.btn.demo-go:hover { background:#e59a1c !important; }`, then add `.btn.demo-go:disabled { background:#efe3c4 !important; color:#6b6660 !important; cursor:progress; }` so a running state is visible.
- **Effort.** S.
- **Command.** colorize.

### 2. Say what this is

- **Surface.** Public phone and desktop, front. `demo_site.py` build(), lines 1266 to 1268, inserts Quick start straight above the lanes. The masthead account line comes from `03-inputs/control_templates/base.html` lines 72 to 74. The page's one description of itself is the footer at line 1292.
- **Severity.** P1.
- **Evidence.** `A-demo/front-top-01.png` opens on "Swing Trader · Control Centre", six chips and "$102,206 $2,206 · open 50 $4,481 · closed 58 -$2,265 · cash $10,246". The front heading outline in `demo-phone/front-measure.json` is H1 Swing Trader · Control Centre, then H3 QUICK START. The "Paper trading demo" line is at the foot, `demo-phone/front-top-04.png`.
- **Why it matters.** A friend decides in seconds whether a page about money is safe, and this one shows someone's account before it says it is a pretend-money experiment built by Seamus.
- **Proposed change.** Add a block above Quick start headed "What this is", with three sentences. "Seamus built this page to test whether a computer model can pick crypto trades better than guessing. Pick a preset and press Run Model, and in about five minutes the model rates each coin and turns each rating into a paper ticket, a pretend trade followed on real prices for about two days. No money is involved and nothing is bought or sold." On the public page, hide the masthead account figures or prefix them with "Seamus's paper stock account", and retitle the page "Swing Trader, paper trading test".
- **Effort.** S.
- **Command.** onboard.

### 3. Warn that names are public

- **Surface.** Public phone and desktop, front, B2 and C1. RUN_BLOCK line 138 to 139, placeholder "Your name, shown beside your tickets".
- **Severity.** P1.
- **Evidence.** The name is written to `data/runs/<id>.json` and `data/index.json` on the gh-pages branch of a public repository. The live `data/index.json` lists names such as "anonymous", and commit 16328147 "Remove the setup test run from the demo record" shows that removal leaves the name in the branch history.
- **Why it matters.** A friend who types a full name has published it on GitHub for good without being told, which is the fastest way to lose the trust the warm theme is meant to earn.
- **Proposed change.** Change the placeholder to "A first name or nickname" and add one line under the field, "Shown to everyone who opens this page and kept in the project's public history on GitHub."
- **Effort.** S.
- **Command.** clarify.

### 4. Put the panel in the address

- **Surface.** Public phone and desktop, every panel opened from a chip or a card. `03-inputs/control_export.py` line 258 `ev.preventDefault(); showPanel(key);`, while `demo_site.py` fitFigures (line 483, listener line 491) and the chart resize (line 720) run only on `hashchange`.
- **Severity.** P1.
- **Evidence.** `A-demo/navcheck.mjs` tapped the C2 chip on a 390 px phone. The address stayed without a hash and `history.length` stayed 2, so Back leaves the site. The Runs chart then measured 700 px wide in a 358 px box, and `A-demo/navcheck-C2-runs.png` shows its right side, where the latest run sits, cut off. The four Explore figures on C2 also measured 700 px. `A-demo/B1-panelB1jsplotlyplot-01.png` shows the same clipping on B1, and the phone measure files count 93 to 538 clipped Plotly elements per view.
- **Why it matters.** On a phone Back is the main way home, and the chart a friend comes to C2 to see is cut in half when they arrive by the chip.
- **Proposed change.** In control_export.py line 258, set `location.hash = '#panel-' + key` instead of calling showPanel, and let the existing `fromHash` at line 276 open the panel. Make the back chip set `location.hash = ''`. In demo_site.py, run fitFigures and the chart resize at the end of showPanel as well as on hashchange, and measure the width of the enclosing `.block` rather than the figure's parent.
- **Effort.** S.
- **Command.** harden.

### 5. Cut the page to what shows

- **Surface.** Public phone first, desktop second, all views. build() inlines every chart as base64 through `ce.inline_charts` and puts Plotly in `<head>`. strip_code line 118 removes every button, including the reel's step buttons from `control_templates/index.html` lines 74 and 76.
- **Severity.** P1.
- **Evidence.** `A-demo/C1-measure.json` records 15,042,402 bytes transferred and 25,768,434 decoded, 22,683 DOM nodes and 296 images, 290 of them data URIs totalling 15.5 MB. The front section of `site/index.html` holds 10.4 MB and 219 images to show 12, because each front card reel carries its whole collection while its previous and next buttons were stripped, so 207 images can never be seen. The head holds 4.9 MB of styles and script before the first paint. `loading="lazy"` on 277 images saves nothing, because the bytes are already in the HTML.
- **Why it matters.** A friend on mobile data waits for 15 MB before the first card appears, and many will close the tab before Quick start draws.
- **Proposed change.** Ship one image per front slot instead of the reel. Publish the remaining images as files under `img/` on gh-pages, referenced by path, so lazy loading works. Move Plotly to the end of `<body>` with `defer`. Set a budget of 1.5 MB transferred for the front page.
- **Effort.** M.
- **Command.** optimize.

### 6. Start from a safe preset

- **Surface.** Public phone and desktop, every settings panel. The page's opening values are read from the operator's `04-outputs/AA-evals/bench/config.json`, and DEMO_SCRIPT line 581 `var BASE = flatNow();` treats them as the starting point.
- **Severity.** P1.
- **Evidence.** A friend who presses Run Model without a preset runs scheme monte-carlo (`demo-phone/B2-top-02.png`), class weight balanced and an overfit cap of 1.3 (`demo-phone/C1-top-02.png`). The B2 note on the same screen says expanding and rolling "are the only honest choices on prices", and the C1 Scores table and Best so far box both say the cap is 1.1.
- **Why it matters.** The default path, the one most friends take, runs a configuration the page itself calls dishonest, so their tickets start from a flattered fit.
- **Proposed change.** When no settings are stored, apply the Quick and simple preset on load and mark it on, by calling `applyPreset('quick')` after line 582 when `fetchStore(KEY, null)` is empty. All three presets already set expanding, class weight none, and a cap of 1.1 or 1.3.
- **Effort.** S.
- **Command.** harden.

### 7. Rewrite What to do

- **Surface.** Public phone and desktop, A1, A2, B1, B2, C1 and C2. The lists come from `03-inputs/control_registry.py` lines 700, 746 and 834 and pass through trim_settings (line 1232) untouched apart from one A2 line.
- **Severity.** P1.
- **Evidence.** B1 tells a friend to press Screen variables or Univariate screen (`demo-phone/B1-top-03.png`). C1 says "Press Run the test ... the line under the button is the command it will run" and "Read Results, directly below" (`demo-phone/C1-top-08.png`). C1 also says to pick the market on A1, where the market field was removed. None of these controls exist on the public page, because strip_code removes them.
- **Why it matters.** A friend who follows the page's own instructions looks for buttons that are not there and concludes the page is broken.
- **Proposed change.** Drop the What to do block from every panel in trim_settings, or replace each with one demo sentence, for example on B1 "These settings choose which inputs the model keeps. A preset has already set them, and Run Model on B2 or C1 uses whatever is here."
- **Effort.** S.
- **Command.** clarify.

### 8. Fold the long tables on phones

- **Surface.** Public phone, C1 and A2. The mobile CSS turns every table into cards (DARK_CSS, lines 1088 to 1107), including the 574-row Scoreboard, the Three-way table and the 90-row Columns table.
- **Severity.** P1.
- **Evidence.** C1 is 343,870 px tall on a 390 px phone and A2 is 56,393 px (`demo-phone/C1-measure.json`, `A2-measure.json`). One scoreboard card is about 540 px with 19 rows (`A-demo/C1b-filterscoreboard-01.png`). Table headings are hidden on phones, so the Click a heading to sort feature cannot be used.
- **Why it matters.** The Run block lives on C1, and a friend who scrolls past it meets 400 screens of research fits they cannot sort, with no way back but a long swipe.
- **Proposed change.** Under 760 px, wrap the Scoreboard, Three-way and Columns tables in a `<details>` closed by default, with a one-line summary such as "574 research fits, the best 0.98 times a constant guess. Show them". Inside, show the ten best by blind U2 with a Show all button, the pattern the working copy already uses for tickets. Target a C1 phone height under 20,000 px.
- **Effort.** M.
- **Command.** distill.

### 9. Qualify the Three-way preset

- **Surface.** Public phone and desktop, every Quick start block. presets(), blurb at lines 257 to 260, and C1 The record.
- **Severity.** P1.
- **Evidence.** The live blurb reads "Logistic regression calls each 4-hour bar up, down or flat over the next 12 bars, on LINK and LTC. The one setup that made money after cost, +1.23% a trade on its most confident fifth of unseen data." The record it quotes, `04-outputs/AA-evals/2026-09-16/bench-3way-20260916-140850.json`, was fitted on LINK, LTC and MATIC from the 40,000-row slice, not on the two coins the preset runs. `.claude/memory/general.md` lines 205 to 210 records that the 265 trades overlapped and were not independent, had no stop, covered three coins and one blind year, and that a test on separate trades was still to come.
- **Why it matters.** A friend new to trading reads "made money after cost" as a promise, which breaks the product's own rule to say what failed as plainly as what passed.
- **Proposed change.** Rewrite the blurb as "Logistic regression calls each 4-hour bar up, down or flat over the next 12 bars, on LINK and LTC. On LINK, LTC and MATIC it made +1.23 per cent a trade after cost on its most confident fifth of one unseen year, but those trades overlapped, and it has not yet passed a test on separate trades." Update the last clause if that test has since run.
- **Effort.** S.
- **Command.** clarify.

### 10. Darken lane text and labels

- **Surface.** Public phone and desktop, front cards, panel headings, phone table cards and desktop table heads. THEMES warm, line 912 `lanes=dict(...)`, the card label colour `@head@` at line 1098 and the table head at line 1149, both `#8a8378`.
- **Severity.** P1, fails WCAG AA 1.4.3.
- **Evidence.** `demo-phone/front-measure.json` records the C2 panel name "Ledger" at 2.58 to 1, B2 at 3.19, A2 at 3.51 and C1 at 3.8, all at 18 px or smaller, and the tags and chart counts at 9.5 to 10 px in the same colours. The phone card labels (ISSUED, COIN, DUE) are `#8a8378` on white at 11.5 px, 3.75 to 1, which the measure misses because they are `::before` content. Desktop table heads are `#8a8378` on `#faf9f7`, 3.56 to 1 (`demo-desk/C2-measure.json`).
- **Why it matters.** The panel names and every label a friend reads a ticket by are the faintest text on the page.
- **Proposed change.** Keep the lane colours for the 3 px card edges and use a darker shade for lane text, A2 `#4e7990`, B2 `#577c62`, C1 `#a36625` and C2 `#916f21`, each 4.67 to 4.71 to 1 on white, with one step darker again wherever the text sits on a tinted tag. Change `@head@` and the `th` colour to `#6b6660`, 5.68 to 1 on white and 5.4 on `#faf9f7`.
- **Effort.** S.
- **Command.** colorize.

### 11. Close the return loop

- **Surface.** Public phone and desktop, the Run block and C2. DEMO_SCRIPT wait() at line 792 and board() at line 739.
- **Severity.** P2.
- **Evidence.** Tickets from a default run are due two days after issue, "Sep 27, 13:00 PDT" for runs on 25 September (`A-demo/C2-demoboard-02.png`), and demo_run's LIMITS allow a horizon of up to 72 bars, which is 72 days on daily candles. Nothing before Run says when tickets settle. A friend's own runs are marked only in the browser that ran them, and a blank name becomes "anonymous". A run in progress is forgotten on reload, because wait() is started only by the click.
- **Why it matters.** Seamus's success measure is friends coming back, and the page gives them no date, no reminder and no way to find their tickets on another device.
- **Proposed change.** Under Run Model, print the settle time from timeframe times horizon, "Tickets settle in about 2 days, on Sep 27 at 13:00 Pacific." After Done, offer an Add to calendar link, a `data:text/calendar` file at the due time carrying the page address, and a personal link `#panel-C2` plus the run id that highlights that run on any device. On load, resume wait() for any stored run id younger than 40 minutes that has no record yet.
- **Effort.** M.
- **Command.** onboard.

### 12. Make run states distinct

- **Surface.** Public phone and desktop, the Run block. RUN_BLOCK line 142 `<p class="note demo-status">`, setStatus line 782, and `03-inputs/demo_run.py` line 483.
- **Severity.** P2.
- **Evidence.** Sending, Running, Done, refused and failed all render in the same grey note style, with no `aria-live` anywhere in the build. A failed run shows `f"{type(e).__name__}: {e}"`, a Python exception name, in the status and in the Runs table. The button text never changes while a run is going.
- **Why it matters.** A friend waiting five minutes cannot tell at a glance whether anything is happening or whether it failed, and a screen reader hears nothing.
- **Proposed change.** Add `role="status" aria-live="polite"` to `.demo-status`. Style failures with a `demo-err` class, `#5c1414` on `#fbeeee`. Show three steps, Sent, Training, Tickets issued, filling as each is reached, and set the button text to Running while it is disabled. In demo_run.py, pass through only the plain sanitize messages and replace any other exception with "The run stopped on an error in the model code. Try another preset."
- **Effort.** S.
- **Command.** harden.

### 13. Describe presets before the tap

- **Surface.** Public phone and desktop, every Quick start block. QUICK_BLOCK line 150 and markPreset.
- **Severity.** P2.
- **Evidence.** The three buttons show only "Best on record", "Three-way outcome" and "Quick and simple" (`A-demo/front-top-01.png`). Each blurb appears only after a tap, none is marked as the place to start, and the changes a preset makes on the other five panels are invisible. Nothing beside Run Model says what will run.
- **Why it matters.** A friend cannot choose between three names they do not understand, and presses Run without knowing what they sent.
- **Proposed change.** Print each blurb in small type under its button from the start. Mark Quick and simple "Start here" and pre-select it (finding 6). Rename "Three-way outcome" to "Up, down or flat". Above Run Model, print a one-line summary built from the form, for example "Elastic-net logistic regression on BTC, ETH and SOL, 4-hour candles, tickets due in about 2 days."
- **Effort.** S.
- **Command.** clarify.

### 14. Save on change

- **Surface.** Public phone and desktop, every settings block. RUN_BLOCK line 135 "Sends your saved settings", and the Save all settings buttons kept by strip_code line 118.
- **Severity.** P2.
- **Evidence.** A1 alone shows five Save all settings buttons (`demo-phone/A1-top-01.png` to `-06.png`). Run Model calls `collect()` on every form and sends what is on screen whether or not it was saved, so the note's "saved" is wrong.
- **Why it matters.** Eight Save buttons and the word "saved" tell a friend there is a step to remember, and there is not.
- **Proposed change.** On the public page, remove the Save all settings buttons and store the settings on every `change` event. Change the note to "Sends the settings on these pages, trains your model on fresh prices and issues a paper ticket per coin, in about five minutes."
- **Effort.** S.
- **Command.** distill.

### 15. Name choices in plain words

- **Surface.** Public phone and desktop, A2 Choose Features, C1 Choose Model and C1 Choose Grid Search. demo_choices at line 832 rewrites only the market, frame, symbol and bundle lists.
- **Severity.** P2.
- **Evidence.** The C1 Models list reads LogReg.glm, LogReg.enet, RF, LightGBM, HistGBM and GBM.classic (`demo-phone/C1-top-02.png`), while the plain descriptions sit in a table after the settings. A2 Families reads f_wc_, f_hr_, f_ta_ and so on, and Also include and Leave out list 90 raw column names (`demo-phone/A2-top-01.png`, `-02.png`). The C1 Grid field holds `learning_rate=0.03,0.06,0.12 max_leaf_...` (`demo-phone/C1-top-06.png`).
- **Why it matters.** A friend has to scroll away, decode and scroll back to make one choice.
- **Proposed change.** Extend demo_choices so option labels are plain with the code in brackets, "Random forest (RF)", "Logistic regression (LogReg.glm)", "Relative to bitcoin (f_btc_)" and so on. Remove Also include, Leave out and the Grid field from the public page, since each needs code syntax.
- **Effort.** M.
- **Command.** clarify.

### 16. Drop the operator's records

- **Surface.** Public phone and desktop, every panel. trim_settings (line 1232) keeps the Evidence Log, Other runs on this panel, and the Alpaca columns.
- **Severity.** P2.
- **Evidence.** Every panel ends in an Evidence Log of file names such as `bench-sweep-20260916-060148.md` whose links were removed (`demo-phone/B2-top-06.png`, `B1-top-04.png`). A1's Datasets and Screening tables carry an Alpaca, US equities column although the market is fixed to crypto (`demo-phone/A1-top-03.png`). Copy includes "keep it under 40,000 on this laptop", "Coins or stocks", "Record bench-20260921-201704.json", "Computed in indicator_block" and "WC['rsi'] = 84 bars" (`demo-phone/A2-top-08.png`).
- **Why it matters.** Each of these costs a friend attention and says nothing they can act on, and the file names read as code on a page promised to show none.
- **Proposed change.** On the public page, remove the Evidence Log and Other runs blocks, remove the Alpaca column from A1's tables, rename "Coins or stocks" to "Coins", cut "on this laptop", and drop the Computed in and Window or parameter rows from A2's Columns cards.
- **Effort.** M.
- **Command.** distill.

### 17. Fix the card pattern

- **Surface.** Public phone, C2 tickets and C1 scoreboard. DARK_CSS line 1099 `td:empty { display:none !important; }` against line 1102 `td[data-label]:not(:first-child) { display:flex !important; }`.
- **Severity.** P2.
- **Evidence.** Empty cells still show their label, AFTER COST with nothing beside it on every open ticket (`A-demo/C2-demoboard-02.png`) and CONFIGURATION on every scoreboard card (`A-demo/C1b-filterscoreboard-01.png`), because the later rule is more specific, (0,2,1) against (0,1,1). Tickets are one card per coin, so a two-coin run takes two 600 px cards that repeat the name, issue time, timeframe and due time. A scoreboard card reads VERDICT passes beside BLIND U2 1.1480, a result worse than guessing.
- **Why it matters.** A blank labelled row looks like missing data, and "passes" next to a losing score tells a friend the opposite of the truth.
- **Proposed change.** Change line 1099 to `td[data-label]:empty, td:empty { display:none !important; }`. On phones, group tickets into one card per run, with the shared fields once and one line per coin, for example "LTC, BUY at 71.05, open". Rename the scoreboard's passes and rejected to "passes the overfit bar" and "rejected, overfit".
- **Effort.** S.
- **Command.** layout.

### 18. Make panel navigation thumb-sized

- **Surface.** Public phone, every panel. DARK_CSS line 1063 sets the chips to `padding:6px 9px`.
- **Severity.** P2.
- **Evidence.** The six chips are 30 px tall (`demo-phone/front-measure.json`), sit only at the top, and do not mark the current panel (`demo-phone/A1-top-01.png`). No panel ends with a link to the next, and there is no way back to the top of a 343,870 px page.
- **Why it matters.** A friend working from A1 to C2 must scroll back to the top of each panel to move on, with targets under the 44 px minimum.
- **Proposed change.** Raise the chips to 44 px with `padding:12px 12px`, add `aria-current="page"` and a filled lane background to the current chip, and end each panel with a full-width "Next, B2 Training" link and a "Back to top" link. Better still, on phones fix a bottom bar holding Run Model and the next-panel link.
- **Effort.** S.
- **Command.** adapt.

### 19. Make charts readable on phones

- **Surface.** Public phone, every panel's Figures and front cards. strip_code line 118 removes the enlarge control with the other buttons, and fitFigures only resizes Plotly.
- **Severity.** P2.
- **Evidence.** The static figures are drawn about 1,200 px wide and shown at about 330 px, so axis text is about 4 px (`demo-phone/A1-top-08.png`, Trade geometry). There is no way to open one full size. The Explore Plotly figures keep zoom, pan and a modebar whose buttons are 23 px wide (`demo-phone/B2-measure.json`), so a thumb scrolling past can zoom a chart instead.
- **Why it matters.** Charts are most of the page's weight and give a friend on a phone almost nothing.
- **Proposed change.** Keep the lightbox control on the public page by adding its class to the allow list at line 118, and make a tap on a figure open it at 100vw. Apply the demo's own PCONF (line 636) and `fixedrange:true` to every Plotly figure under 760 px.
- **Effort.** M.
- **Command.** adapt.

### 20. Restore the plain chart note

- **Surface.** Public phone and desktop, C2 Runs against guessing. BOARD in the live build, and the working copy's METRICS text.
- **Severity.** P2.
- **Evidence.** The live note reads "Each dot is one run, scored on unseen data by Theil's U2, the RMSE of its predicted probabilities divided by the RMSE of always predicting the average outcome" (`A-demo/C2-demoboard-01.png`). The 16:26 build read "Each dot is one run's error on unseen data. Below the line beats always guessing the average."
- **Why it matters.** It defines one unknown term with two more, which the writing rules forbid, for the reader least able to decode it.
- **Proposed change.** Lead with the plain sentence and put the technical name second, "Each dot is one run. Below the dashed line, its forecasts beat always guessing the average; above it, they did worse. The score is Theil's U2."
- **Effort.** S.
- **Command.** clarify.

### 21. Show field help on touch

- **Surface.** Public phone, every settings field. The board's `.hint` is hidden (`control_static/control.css` line 785) and the explanation lives in each field's `title`.
- **Severity.** P2.
- **Evidence.** Fields such as Embargo bars, Purge bars, Repeats, Bootstrap samples and Take-profit carry their own explanation only as a tooltip, which a touch screen never shows. The block notes cover some but not all of them (`demo-phone/B2-top-02.png`, `-03.png`).
- **Why it matters.** On a phone a friend sees a label such as "Purge bars" and a number, with no way to find out what it does.
- **Proposed change.** Under 760 px on the public page, show each field's hint below its input at 13 px in `#6b6660`, or add a small "What is this" toggle that reveals it.
- **Effort.** M.
- **Command.** adapt.

### 22. Replace desktop multi-selects

- **Surface.** Public desktop, A1 Coins, A2 Families and C1 Models.
- **Severity.** P2.
- **Evidence.** These are native `<select multiple>` lists (`demo-desk/A1-top-01.png`, `demo-desk/C1-top-01.png`). On a desktop a plain click selects one option and drops the rest, and adding one needs Cmd or Ctrl. A phone shows a native picker with ticks, which works.
- **Why it matters.** A friend on a laptop who clicks SOL to add it silently removes BTC and ETH.
- **Proposed change.** Render each as a row of checkbox chips, 44 px tall, with the current count, "3 of 6 coins chosen".
- **Effort.** S.
- **Command.** harden.

### 23. Add a link preview

- **Surface.** Every place the link is shared. The `<head>` written by build() at line 1255 onward.
- **Severity.** P2.
- **Evidence.** The build has a title and a viewport tag but no `meta name="description"`, no `og:title`, `og:description` or `og:image`, and no icon link.
- **Why it matters.** Friends meet the page as a link in a message, and a bare address titled Control Centre is easy to ignore.
- **Proposed change.** Add a description and Open Graph tags, "Run a paper-trading model in two taps. No money involved.", an `og:image` of the front page at 1200 by 630, and an icon link.
- **Effort.** S.
- **Command.** onboard.

### 24. Collapse repeated Quick start

- **Surface.** Public phone, A1, A2, B1, B2 and C1. build(), panel loop at line 1275 onward.
- **Severity.** P3.
- **Evidence.** Quick start opens every panel at about 550 px on a phone (`demo-phone/A2-top-01.png`), and on B2 and C1 the Run block follows it, so a panel's own settings start a screen and a half down.
- **Why it matters.** The repetition was asked for, but once a preset is chosen it pushes each panel's own content off the first screen.
- **Proposed change.** Once a preset is stored, render Quick start on the panels as one 44 px line, "Preset, Quick and simple. Change", that expands on tap.
- **Effort.** S.
- **Command.** distill.

### 25. Tidy the front cards

- **Surface.** Public phone, front. DARK_CSS line 1069 `.card .pair { height:170px }`.
- **Severity.** P3.
- **Evidence.** Wide charts fill only the top half of the 170 px slot and leave a blank band under each (`demo-phone/small-top-02.png`, A1 and A2 cards). Captions are cut to "Training window agai…", and 44 of the 90 text elements on the phone front are under 12 px, the tags at 9.5 px and the chart counts at 10 px (`demo-phone/front-measure.json`).
- **Why it matters.** The cards are the second thing a friend sees, and they read as cramped thumbnails of a desktop tool.
- **Proposed change.** Under 760 px, show one chart per card at full width with `aspect-ratio` taken from the image, let captions wrap to two lines, and set tags and counts to 12 px.
- **Effort.** S.
- **Command.** typeset.

### 26. Warm the leftover cool tones

- **Surface.** Public phone and desktop, every block heading and brief table, and the footer.
- **Severity.** P3.
- **Evidence.** Block headings keep the board's cool `#c3cedb` rule and the brief tables its cool border, next to warm grey type on `#f5f4f1` (`demo-phone/A1-top-02.png`). The masthead title stays navy. The only description of the page, "Paper trading demo", is set in warning red at the foot (`demo-phone/front-top-04.png`).
- **Why it matters.** The approved theme is warm throughout, and a red disclaimer at the foot reads as a warning rather than a welcome.
- **Proposed change.** Map `#c3cedb` to `#e6e3dd` and the navy title to `#32302f` in LIGHT_CSS, and set the footer label in `#6b6660` once finding 2 puts the description at the top.
- **Effort.** S.
- **Command.** polish.

### 27. Trim desktop chrome

- **Surface.** Public desktop, every panel page.
- **Severity.** P3.
- **Evidence.** A panel page opens with the operator's timeline band, the masthead chips and a second reading-order row repeating the same six links, about 130 px in all (`demo-desk/B2-top-01.png`). C2 scrolls 2 px sideways, 1,442 px wide in a 1,440 px window (`demo-desk/C2-measure.json`). The front cards run down the columns, A1 above A2, while the chips run A1, A2, B1 across.
- **Why it matters.** Three bands of navigation push a friend's settings down the screen and repeat themselves.
- **Proposed change.** Hide `.topband` and `.sheet > .flow` on the public page at every width, as the phone CSS already does, and add `overflow-x:auto` to `.demo-tables > div`.
- **Effort.** S.
- **Command.** quieter.

### 28. Even out the totals tiles

- **Surface.** Public phone, C2 Paper tickets. DEMO_CSS line 412 `.demo-totals div { min-width:120px }`.
- **Severity.** P3.
- **Evidence.** The five tiles wrap as two, one, one, one at uneven widths (`A-demo/C2-demoboard-01.png`).
- **Why it matters.** The first numbers a friend sees on their results page look unfinished.
- **Proposed change.** Under 760 px, set `.demo-totals { display:grid; grid-template-columns:1fr 1fr; }` and let the last tile span both columns.
- **Effort.** S.
- **Command.** layout.

## Known defects

These were found earlier and are not counted above. This is where each shows on the public page.

1. Take-profit and Stop never change the label. A1 Choose Label, fields Take-profit, ATR 2.0 and Stop, ATR 1.0, `demo-phone/A1-top-05.png` and `-06.png`.
2. The eleven A2 engine settings only draw charts. Their forms are removed on the public page (DEMO_DROP, line 1228), but A2's Indicator engines table still gives each engine a SETTINGS row, `demo-phone/A2-top-06.png`.
3. No model ticked fits three models, not six. C1 Choose Model, the Models list and the note "Tick the models to score", `demo-phone/C1-top-02.png` and `-03.png`.
4. Fold pass rate counts folds with U2 under 1, not money. A1 Choose Ranking note, "the share of them where the strategy must have made money", `demo-phone/A1-top-05.png`, and C1 Scores, "Share of half-year folds where the strategy made money", `demo-phone/C1-top-08.png`.
5. Embargo 0 means 2 days, not the horizon. B2 Choose Blind Period note, "0 uses the label horizon", `demo-phone/B2-top-02.png`.
6. Class weight defaults to balanced. C1 Choose Model, `demo-phone/C1-top-02.png`, and the WEIGHT row of every scoreboard card, `A-demo/C1b-filterscoreboard-01.png`. On the public page it is also what an unpreset run sends (finding 6).
7. The 1-hour base rate 0.313 is quoted on the 4-hour frame. The tooltip on A1 Take-profit, ATR, invisible on a phone and shown on hover on a desktop.

## Working copy

The working copy of `demo_site.py` is reworking C2 while this review ran. It folds the operator's research into a closed Research record, caps the ticket and run tables at ten rows with Show all, and adds a column dictionary, which would answer part of findings 8, 16 and 17 for C2 only. It also adds a Model scores chart with four metric buttons, RMSE, MAE, Theil's U2 and Overfit ratio, and a link whose text is the path 04-outputs/AA-evals. For this reader one plain measure against guessing is enough, and the path is the kind of text finding 16 removes.

## Keep these

1. Quick start and Run Model sit inside the first phone screen, with Run Model about 708 px down an 844 px screen, so a friend can run in two taps without reading anything.
2. The settings notes are plain English and shown as text on the public page, for example A1 Choose Filter, which defines ATR as the average over 14 days of each day's range and says "0.015 is 1.5 per cent a day".
3. The relay's limits speak plainly, "That is N runs from you this hour, the most allowed. Try again next hour." and "Today's runs are all used. Try again tomorrow." (`05-research/demo/relay/worker.js` lines 47 and 50).
4. C2's About this page separates a friend's tickets from the operator's account and says "It is not your run."
5. The verdicts are honest, "beat a constant guess, just", the dashed Guessing the average line, and A1's "No crypto strategy has beaten its costs on unseen data."
6. The demo's own ticket charts have zoom, pan and the modebar off, 12 px type, and an empty state that names the next settle time in Pacific time, "No ticket has settled yet. The first is due Sep 27, 13:00 PDT, and this chart fills in from then."
7. Nothing scrolls sideways at 390 or 360 px, inputs are 16 px so a phone does not zoom on tap, and `:focus-visible` draws a 2 px ring.
8. The warm ground with white rounded cards reads calm and light, as approved, and should stay.

## False positives

1. "WebGL is not supported by your browser", flagged as low-contrast text on B2, C1 and C2, comes from headless Chrome started with `--disable-gpu`, and a phone with WebGL draws the figure instead.
2. The phone overflow counts of 93 to 538 elements per view are the internals of the same clipped Plotly figures, one cause, reported once in finding 4.
3. The measure's `dark_mode_rule: true` is a `prefers-color-scheme` rule somewhere in the inlined styles, and every capture renders light, as approved.
4. The measure's zero low-contrast count on the phone ticket and scoreboard cards is a false negative, because the labels are `::before` content and are not text nodes. They fail at 3.75 to 1 (finding 10).
