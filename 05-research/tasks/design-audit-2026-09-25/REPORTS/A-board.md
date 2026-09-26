# A-board design review

Assessment A, the design review of the served control-centre board on a desktop, written on 25 September 2026 without sight of any detector output. It rests on the captures in `board/`, on the templates, stylesheet, registry and table builders in `03-inputs/`, and on one read-only measurement I ran myself (`A-board/rows.mjs`, results in `A-board/rows-1440.json` and `A-board/rows-1280.json`). That script only navigated with GET and scrolled. It skipped B1, because B1's page script sends a POST to `/varselect/fit` as soon as it loads (finding A-12). No button was pressed and no file in the repository was changed.

## Heuristic scores

| # | Heuristic | Score | Key issue |
|---|-----------|-------|-----------|
| 1 | Visibility of system status | 3 | Save, unsaved and run states are clear. Charts show an empty box for 4.5 to 10.2 s while drawing, and the front-page dot measures file age, not whether the result is current |
| 2 | Match with the real world | 2 | Labels promise behaviour the code does not deliver (the known label defects), "NOT YET" for a run that failed, and two different quantities both called "Rows" on B1 |
| 3 | User control and freedom | 2 | Reset, Reset defaults and Load best reload the page with no confirm and no undo, and drop unsaved edits |
| 4 | Consistency and standards | 2 | 574, 504 and 460 fits. 119 and 66 beat a constant guess. The overfit cap is 1.1 and 1.3 on one page. The Save button changes colour on every panel |
| 5 | Error prevention | 1 | A run can start on settings the form does not show. A leaking resampling scheme and a cap above the house bar can be saved with nothing to flag them |
| 6 | Recognition rather than recall | 2 | The front page does not show the standing of the record. Selections in multi-selects are pale grey. Numbers are printed without saying what they measure |
| 7 | Flexibility and efficiency | 2 | Zoom, sort, filter and Show all code exist. C1's Run button sits 2,673 px down, and there are no keyboard shortcuts for Save or Run |
| 8 | Aesthetic and minimalist design | 2 | Density is intended, but every panel carries the same trailing blocks, an empty 220 px console, and 100 to 687 px of blank white beside its tables |
| 9 | Error recovery | 2 | A failed run reports only "exit code N after N seconds". Save errors do name the section that failed |
| 10 | Help and documentation | 3 | Tooltips on every field, a What to do list on each panel, and a glossary in the run report. Three of those lists are out of date |
| **Total** | | **21/40** | **Acceptable** |

## Specificity verdict

The board is authored, but the inside of each panel has grown from a template. The front page belongs to this product and no other. It has the cheat sheet's lane gradient, the numbered badges, the reading-order chips, the hand-stepped reel and the timeline band, and a reader who knows the printed sheet recognises it at once. Inside, every panel stacks the same trailing sequence whatever the panel is for, namely What to do, Best so far, Output, Evidence Log, Figures, then Explore. The Best so far box repeats word for word on B1, B2 and C1. C2 has nothing to run, yet it carries the same shape, and the idle console is the largest dark mass on B1, B2 and C1. Any admin tool could use that scaffolding unchanged. The largest missed opportunity is the scoreboard. PRODUCT.md calls it the product, yet it is a generic sortable table 3,000 px down C1, sorted by date, with no treatment of its own.

## Cognitive load

Four of the eight checks fail, which is high load. The density itself is intended, so the fix is hierarchy rather than removal.

1. Single focus fails. C1 stacks The record, This run, The last run, Models, Choose Model, Choose Settings, Scores, Calibration, Grid Search, Run the test, What to do, Best so far, Output, Scoreboard, Three-way, Evidence Log, 15 figures and three Explore charts.
2. Visual hierarchy fails. The verdict line is 12 px while the lines under it are 13.5 px, and the front page carries no answer at all.
3. Minimal choices fails. The decision points with more than four options are Choose Model (6 models), Choose Settings (9 forest settings), Choose Features (15 families, 8 to include, 8 to leave out), the B1 picker (33 checkboxes), Choose Figures (8 figures and 6 overlays), and six Save all settings buttons on A1.
4. Working memory fails. A run's settings are spread over five panels ("Change them on the tool that owns each one"), explanations sit only in tooltips, and the front page does not carry the current standing of the record.

Chunking, grouping, one thing at a time and progressive disclosure pass. The other runs fold away, the settings blocks of unticked models are hidden, and code is folded.

## Emotional journey

C1 has the best opening on the board. "The last run did not improve on the best so far, 1.1480 against 0.9800" is the answer, first, in plain words. Every panel then ends in a long tail. First come empty figure boxes that fill in several seconds later, then Explore charts in default colours, then blank white beside short tables. The front page is the weakest point, because it greets the operator with green dots and a green dollar gain while the record says nothing has cleared its fees. PRODUCT.md calls that reading better than the evidence.

## Findings

### A-01 Make every count come from one source

- **Surface and place.** Board, C1 and C2. `control_tables.py:287` (the standing reads bench-sweep and bench-2 records, 574 fits), `control_interactive.py:440-468` (the scoreboard histogram reads bench-sweep only, 504 fits), `control_tables.py:958` (hard-coded "460 and counting").
- **Severity.** P1
- **Evidence.** C1-top-01.png says "574 fits from 126 comparison runs ... 119 beat a constant guess". C1-top-08.png says "66 of 504 fits beat always predicting the base rate". C2-top-01.png, Ledger table, says "Every scored fit on disk, 460 and counting". C2-overview.png, Assessment, shows "125 rows". C2-top-04.png says "146 runs and 18 milestones".
- **Why it matters.** The scoreboard is the product, and a page that gives 119 and 66 as the answer to the same question makes both numbers impossible to check.
- **Proposed change.** Write one function that returns fits, runs, passed and beat, and have the standing, the histogram title, the Ledger row and the live-book title all read it. Replace "460 and counting" with the live count. Where a figure covers a subset on purpose, its title says so, for example "504 comparison-run fits; single runs excluded".
- **Effort.** M
- **Command.** harden

### A-02 Judge every fit against one overfit bar

- **Surface and place.** Board, C1. `control_tables.py:299-313` (each row is graded against the cap of its own run), gloss `control_tables.py:110`, Choose Model cap field.
- **Severity.** P1
- **Evidence.** C1-top-03.png, Scores table, reads "Overfit ratio ... Rejected above 1.1, whatever its error". C1-top-02.png shows the Choose Model "Overfit ratio cap" set to 1.3. C1-top-01.png, This run, reads "overfit ratio 1.010 against a cap of 1.30, so it passes". C1-top-04.png, Best so far, reads "under the 1.1 cap". The scoreboard CAP column reads 1.30 (C1-top-05.png). The comment at `control_tables.py:302-307` itself says rows judged at 1.1 and rows judged at 1.3 are both shown as "passes", and both are added into "323 passed the overfit bar".
- **Why it matters.** The pass count and the best-on-record ranking mix two bars, so the record reads better than the house rule of 1.1 allows.
- **Proposed change.** Compute "passed" for every row from its stored ratio against `model_metrics.RMSE_RATIO_REJECT` (1.1). Keep the run's own cap as a plain column. When a saved cap is above 1.1, give Choose Model a warn edge and the words "above the house bar of 1.1".
- **Effort.** S
- **Command.** harden

### A-03 Let the decisive bar decide the verdict

- **Surface and place.** Board, C1, The last run. `control_tables.py:1801-1806`.
- **Severity.** P1
- **Evidence.** The verdict is "NOT YET" whenever one or two of the three bars pass. C1-top-02.png reads "NOT YET. RF passed the overfit bar and did not beat a constant guess, missed the fold bar" beside blind U2 1.148 and AUC 0.488. The Scores table (C1-top-03.png) calls U2 "the only score that would change what gets traded". None of the three bars is the after-cost return, yet PRODUCT.md frames the question as whether a rule clears its fees.
- **Why it matters.** A run that did worse than a constant guess and worse than a coin flip is labelled as almost there.
- **Proposed change.** Return "NO" whenever blind U2 is 1 or above. Replace NOT YET with "NO, passed 1 of 3". Add the after-cost return per trade on the blind period as a fourth bar that must pass before WORTH KEEPING can show. Put the failing number in the sentence, "blind U2 1.148, worse than a constant guess".
- **Effort.** M
- **Command.** clarify

### A-04 Colour the failing numbers

- **Surface and place.** Board, C1 The last run and Scoreboard, and C2 Assessment. `card.html:284` and `card.html:661`.
- **Severity.** P1
- **Evidence.** Only cells that read "passes" or "rejected" are coloured. C1-top-02.png shows a green "passes" beside U2 1.148 and AUC 0.488, both in plain black. C1-top-04.png and C1-top-05.png show green "passes" on rows whose blind U2 is 1.14, among 574 rows. C2-overview.png shows the same in Assessment.
- **Why it matters.** The only colour on a failed row is the pass green.
- **Proposed change.** Rename the column "Overfit bar". Colour BLIND U2 with `--bad` at 1 or above and `--ok` below 1. Colour AUC red below 0.5. A row shows green only when every bar passes.
- **Effort.** S
- **Command.** colorize

### A-05 Fix the stability axis on A2

- **Surface and place.** Board, A2, Explore, "90 features: how good alone, and how steady". `control_interactive.py:222-227`.
- **Severity.** P1
- **Evidence.** A2-top-04.png shows every point at y = 0 on an axis that runs from -1 to 1, and every marker the same size. The code looks for columns named stability, sign_stability or steady, and permutation, perm_importance or importance, with a default of 0.0. `04-outputs/AA-evals/2026-09-08/feature-report-4h-20260908.csv` names them "stable" and "in_company", and f_btc_mom_168 has stable 0.8. Family colours are assigned in the order the families first appear, not from the fixed family map.
- **Why it matters.** The chart says no feature holds its sign across folds, which the record contradicts, and it cannot fail, which is the fault this repository has logged most often.
- **Proposed change.** Read "stable" and "in_company". Fix the y range at 0 to 1, since a share cannot be negative. When a column is missing, return `_missing()` naming it rather than plotting zeros. Take family colours from the family map in `control_charts.py`.
- **Effort.** S
- **Command.** harden

### A-06 Put the answer on the front page

- **Surface and place.** Board, front page. `index.html:82-89` (lead and foot), `control_centre.py:207-208` (dot state), `base.html:74-84` (money).
- **Severity.** P1
- **Evidence.** In front-top-01.png the six card leads are lists of nouns ("Market, timeframe, symbols, screen.") and no text states what the record found. The most prominent figures on the page are the equity paper book, "$102,206 $2,206" with the gain in green, which is a different track from the crypto research. Four of the six cards carry a green dot, and `control_centre.py:208` sets that dot when the newest record file is under seven days old, not when a result passes. DESIGN.md reserves green for a pass.
- **Why it matters.** At a glance the front page reads as healthy and green while the record says no crypto rule has cleared its fees, which PRODUCT.md principle 5 calls worse than no board.
- **Proposed change.** Replace each card lead with its panel's one-line standing from the same source as C1's record. For C1 that is "Best blind U2 0.980; last run 1.148; none cleared fees". Draw the age dot in neutral ink shades, with a title such as "record written 3 days ago". Label the masthead money "Equity paper book".
- **Effort.** M
- **Command.** clarify

### A-07 Fill the short side of each row

- **Surface and place.** Board, A1 A2 B2 C1 C2. `control.css:804-813` stretches the table block but not the table inside it, and never stretches the `.tools` column. Group definitions are in `control_registry.py`.
- **Severity.** P1
- **Evidence.** From `rows-1440.json`, the blank white inside the table block below its table measures 100 px on A1 Datasets, 344 px on A1 Screening, 359 px on A2 Indicator engines, 171 px on B2 Resampling regimes, 314 px on C1 Models, 144 px on C1 Scores and 203 px on C2 Ledger. On A1 Hard Rules the right column ends 687 px above the end of the row (Trade geometry runs from 1606 to 2721, the row to 3408). On B2, Compare regimes sits alone in a 246 px row. On C1 the column beside Run the test holds only a 51 px fold. See A1-top-02, A1-top-04, B2-top-01, C1-top-03 and C2-top-01.
- **Why it matters.** The operator set this layout rule on 20 September, and every panel measured breaks it.
- **Proposed change.** In the registry, give each brief group the figures that fill its gap. A1 Screening takes "What the filter and ranking leave" and "The barrier's base rate against its breakeven". C1 Models takes "Every model on overfit ratio and blind U2". Make `.tools` a flex column whose last block grows. Add a `control_eval` check that fails when the two sides of a row differ by more than 40 px.
- **Effort.** M
- **Command.** layout

### A-08 Clear AA contrast on tags and names

- **Surface and place.** Board, front cards and panel mastheads. `control.css:217-221` (tag at opacity 0.85), `control.css:538` (panel name), `control.css:328` (console empty text).
- **Severity.** P1
- **Evidence.** The 9.5 px bold tags sit at opacity 0.85, which blends each lane fill toward white. White on the blended fill measures 4.11 on A2, 4.03 on B1, 3.80 on B2, 4.05 on C1 and 3.69 on C2, against the 4.5 required. The panel name in the masthead measures 4.40 on B2 and 4.22 on C2 against the board ground (B2-measure.json, C2-measure.json). The console empty-state text, #5b6b7d on #0b2038, measures 3.01. The opacity undoes the 22 September darkening at `control.css:910-917`.
- **Why it matters.** These fail WCAG AA on the label that names each panel's scope.
- **Proposed change.** Remove the opacity from `.tag`. Darken `--c-b2` to #17704a and `--c-c2` to #9c4d0c so the masthead names clear 4.5 on #eef1f4. Set the console empty text to #8fa1b3.
- **Effort.** S
- **Command.** colorize

### A-09 Warn before a reset throws away edits

- **Surface and place.** Board, B1 B2 C1 job blocks and every settings block. `card.html:535` (job Reset), `card.html:1223-1230` (Reset defaults), `card.html:1217` (Load best).
- **Severity.** P1
- **Evidence.** The job button "Reset" is `onclick="location.reload()"`, placed beside "Run it" (B1-top-01, B2-top-01, C1-top-03). It reloads the page and silently drops every unsaved edit in every settings block. "Reset defaults" sends its POST and reloads with no confirmation and no undo. Load best reloads the same way.
- **Why it matters.** The configuration is the session's work, and one slip beside Run erases it.
- **Proposed change.** Rename the job button "Clear this form" and have it reset only that form's fields in place. Before Reset defaults or Load best, confirm when any form is dirty, for example "3 unsaved edits in Choose Basket and Choose Label will be lost". Keep the previous values and offer "Undo reset" in the save-state line for 30 seconds.
- **Effort.** M
- **Command.** harden

### A-10 Block runs on unsaved settings

- **Surface and place.** Board, B1 B2 C1. `card.html:863-880` (run submit).
- **Severity.** P1
- **Evidence.** The run handler sends its POST without checking `.cfgform.dirty`. The unsaved state (`card.html:793-797`, `control.css:963`) only draws an edge on the block and writes "not saved yet" in the masthead. On C1 that line is 2,600 px above the Run button.
- **Why it matters.** The record would carry settings that differ from what the operator last typed, which breaks principle 1 at the one moment it counts.
- **Proposed change.** While any form is dirty, the Run button reads "Save and run" and calls `saveAll()` before it posts. The alternative is an inline warning above the button that names the unsaved blocks.
- **Effort.** S
- **Command.** harden

### A-11 Show that a chart is drawing

- **Surface and place.** Board, every Figures block and trade-geometry block. `card.html:720-730`, `control_centre.py:527-547`.
- **Severity.** P2
- **Evidence.** After scrolling Figures into view (`rows-1440.json`), the images took 4.5 s to finish on A1 (9 images), 10.2 s on A2 (9), 6.1 s on C1 (15) and 5.6 s on C2 (20). Until then each card is an empty white box with a caption (A1-top-05, A2-top-04, C1-top-06, C2-top-04).
- **Why it matters.** An empty box looks the same as a chart with nothing to draw or a draw that failed.
- **Proposed change.** Give `.chart` a reserved `aspect-ratio: 12/7` with a "drawing" line that is removed on load, and show "draw failed" on error.
- **Effort.** S
- **Command.** harden

### A-12 Stop drawing and fitting on load

- **Surface and place.** Board, front, B1 and every panel. `control_centre.py:527-547`, `card.html:849`, `control_varselect.py:682`.
- **Severity.** P2
- **Evidence.** Charts are drawn fresh on every request with `no-store`. The front page, with 13 eager images, took 4.3 s to load (front-measure.json), and 7.4 s and 36.5 s in my two runs. Save all settings re-requests every chart and thumbnail on the page. B1 calls `refit()` on load, which POSTs `/varselect/fit`, loads the panel and fits statsmodels each time the page opens. The chart route's own docstring says "a page that refits on every reload is a page nobody can leave open".
- **Why it matters.** On an 8 GB machine that swaps, opening or saving a panel costs from seconds to half a minute.
- **Proposed change.** Cache each PNG keyed on the chart name, a hash of the configuration and the newest record time, and serve an ETag. After a save, redraw only the charts whose inputs changed. On B1, render the last fit's table from disk and refit only when a box is ticked.
- **Effort.** M
- **Command.** optimize

### A-13 Decide whether This run prints paths

- **Surface and place.** Board, C1 This run and the running state. `card.html:215-240`, `card.html:877`.
- **Severity.** P2
- **Evidence.** C1-top-01.png shows ".venv/bin/python 03-inputs/bench_run.py --label loop-record", "04-outputs/AA-evals/bench/config.json" and "04-outputs/AA-evals/2026-09-22/bench-20260922-220829.md". While a job runs, the state line prints "running: " followed by the full command. PRODUCT.md says no script or data path appears in readable text.
- **Why it matters.** Two instructions from the operator conflict, and the page follows the later one without saying so.
- **Proposed change.** Ask Seamus which instruction wins. If the no-path rule holds, show "bench_run, label loop-record", "the shared configuration", and the record as a link titled by its date, with the full path in the tooltip. The running state then reads "running Run the test".
- **Effort.** S
- **Command.** clarify

### A-14 Tie table results to a record

- **Surface and place.** Board, B2 Resampling regimes, A1 Datasets, C1 Scores. `control_tables.py:887-901`, `control_tables.py:598`.
- **Severity.** P2
- **Evidence.** The Result column on B2 is prose typed in from one September run, such as "0.10 below." and "Within 0.01 of the blind period." (B2-top-01). The C1 Benchmarks column reads "0.03 after Platt scaling; 0.23 raw" with no record named. Running Compare regimes cannot change either text.
- **Why it matters.** A result with no record or date cannot be checked, which is principle 1.
- **Proposed change.** Fill the Result column from the newest regime record, with its date and a link. Where no record exists, say "not run under these settings".
- **Effort.** M
- **Command.** harden

### A-15 Rank the scoreboard by blind score

- **Surface and place.** Board, C1 Scoreboard and Three-way. `control_tables.py` scoreboard builder, `control.css:547-556`.
- **Severity.** P2
- **Evidence.** The table has 575 rows, 16,342 px tall inside a 520 px box, and it also scrolls sideways (`rows-1440.json`). The page has 14,105 DOM nodes (C1-measure.json). The rows are sorted newest first. Identical reruns stack up, with purge-0 to purge-48 all scoring 0.9892, and Three-way has 42 rows of which 12 are distinct (C1-top-05, C1-top-06). The RECORD column is cut at the right edge. Numbers are left-aligned and set without tabular figures.
- **Why it matters.** The first screen of the product shows the latest reruns, not the best fits or how much they vary.
- **Proposed change.** Sort by blind U2 ascending among fits under 1.1 by default. Add a "distinct settings" toggle that folds reruns into one row with their count and spread. Right-align numeric columns with `font-variant-numeric: tabular-nums`. Pin WHEN and MODEL to the left edge. Render the first 100 rows and the rest on scroll.
- **Effort.** M
- **Command.** layout

### A-16 Cut the type scale to four steps

- **Surface and place.** Board, all views. `control.css` throughout, `control.css:886` and `control.css:989`.
- **Severity.** P2
- **Evidence.** The measure files count 14 sizes between 8 and 14.5 px (8, 9, 9.2, 9.5, 10, 10.5, 11, 11.5, 12, 12.5, 13, 13.5, 14, 14.5). The C1 verdict line is 12 px while the standing lines under it are 13.5 px (measured). The masthead money is 9 px.
- **Why it matters.** Sizes half a pixel apart cannot show rank, and the one sentence that is the answer is the smallest on its block.
- **Proposed change.** Use 10.5, 12, 13.5 and 16 px, with mono at 11.5. Set the verdict line at 16 px, weight 700. Set the masthead money at 12 px.
- **Effort.** M
- **Command.** typeset

### A-17 Keep warm lanes off verdict colours

- **Surface and place.** Board, C1 and C2, every Save and Run button. `control.css:737-741`, `control.css:997-1001`, `control.css:314-318`.
- **Severity.** P2
- **Evidence.** The C1 lane, #c2410c, and the C2 lane, #b35a10, drive every heading rule, section edge and Save button on those panels (C1-top-01 to C1-top-03). They sit beside Stop and "rejected" in #a01c1c and Best so far in ochre. Save takes the panel colour, so the primary action is navy on A1, orange on C1, and on B2 a green #1c7f52 beside the Run green #0e7a5f (B2-top-01). Run uses the pass green.
- **Why it matters.** On the results panels, where a failure must stand out, most of the page is already red-orange.
- **Proposed change.** Move C1 and C2 to a hue that no state uses, such as the sheet purple #6b3fa0 and #8a5cc2. The other option is to keep lane colour on edges only. Give Save and Run one fixed action colour, navy #14304d, keep Stop red, and never use the pass green for a button.
- **Effort.** M
- **Command.** colorize

### A-18 Make steps and labels match controls

- **Surface and place.** Board, B1 C1 C2. `control_registry.py:698-700`, `control_registry.py:833-845`, `card.html:534`.
- **Severity.** P2
- **Evidence.** C1 What to do (C1-top-04) says "press Save on each tool you change", but one Save now saves everything. It says "the line under the button is the command", but that line is hidden (`control.css:862`). It says "Read Results, directly below", but the block is titled "The last run" and sits above. B1 says "Press Screen variables", but that job is folded under Other runs, and every job button reads "Run it" (B1-top-01). B1 shows "Rows 2000" in Choose Screen beside "From your settings: Rows 6,000", which is a different quantity under the same name. C2 says "Nothing is configured here" beside Choose Figures and its Save button (C2-top-01).
- **Why it matters.** The operator follows the step list, and three panels send him to controls that are not there.
- **Proposed change.** Rewrite the four step lists against the current layout. Label each job button with the job's own title, such as "Run the test" and "Screen variables". Put the elastic-net job first on B1, since Choose Screen configures it. Rename the two Rows fields "Candles to load" and "Rows for the screen".
- **Effort.** S
- **Command.** clarify

### A-19 Flag a leaking scheme at the control

- **Surface and place.** Board, B2 Choose Resampling, C1 This run.
- **Severity.** P2
- **Evidence.** In B2-top-01 the saved regime is monte-carlo, and the table beside it says Monte Carlo claims an error "0.10 below" the blind period. C1 This run lists "2 monte-carlo folds". The only warning is the note's closing words "Ignores time."
- **Why it matters.** The saved configuration uses the regime the panel itself says flatters a fit, and nothing marks the run.
- **Proposed change.** Add "(ignores time)" to those options in the select. Give the block a warn edge when one is chosen. Put "time ignored" into C1's verdict sentence, since `control_tables.py:1790` already builds that phrase.
- **Effort.** S
- **Command.** harden

### A-20 Shrink the idle console

- **Surface and place.** Board, B1 B2 C1 Output. `control.css:698`, `card.html:1305-1310`.
- **Severity.** P2
- **Evidence.** B1-top-02, B2-overview and C1-top-04 each show a 220 px navy box reading "Nothing has run yet in this session." at a contrast of 3.01. A failed run reports only "exit code N after N seconds."
- **Why it matters.** The idle state spends a third of a screen on nothing, and the failed state names no cause.
- **Proposed change.** Hold the idle console at 40 px and grow it to 220 px when a job starts. On failure, show the last non-empty line of the traceback beside the pill and scroll the console to it.
- **Effort.** S
- **Command.** quieter

### A-21 Date evidence by the run

- **Surface and place.** Board, every Evidence Log and the front-page dots. `control_centre.py:190-198`, `control_centre.py:207`.
- **Severity.** P2
- **Evidence.** `record_summary` dates each record by the file's modification time. B2-overview and C1-top-06 list bench-sweep-20260916-* as "22 Sep 2026, 15:30".
- **Why it matters.** A copy or a checkout makes an old record look new, and the front-page dot follows the same wrong date.
- **Proposed change.** Read the record's own `stamped` field, as the scoreboard already does (`control_tables.py:290`). Fall back to the date in the file name, and only then to the modification time.
- **Effort.** S
- **Command.** harden

### A-22 Hold notes to one line

- **Surface and place.** Board, every settings block. `card.html:122-135`, `bench_config.py` notes.
- **Severity.** P2
- **Evidence.** The Choose Label note runs six lines (A1-top-02), including a paragraph typed into the template at `card.html:133` ("A trade that has not worked by then usually will not"). Choose Filter runs five lines (A1-top-01) and Choose MACD five (A2-top-01). Notes also use colons in prose, as in "Fold pass rate: the history...", "Best of 574 fits so far: rf." and "min: Keep the model".
- **Why it matters.** DESIGN.md's Tooltip Rule and the 20 September audit set one note line under each tool, and the long notes push Save below the fold.
- **Proposed change.** Keep one line that names the current choice, such as "12 bars of 4 hours, 2 days; barrier", and move the rest into the title attribute. Remove the colons and the aphorism.
- **Effort.** M
- **Command.** distill

### A-23 Use the house palette in Explore

- **Surface and place.** Board, Explore charts on A1 B1 B2 C1 C2. `control_interactive.py:37-46`, `control_varselect.py:161-169`.
- **Severity.** P2
- **Evidence.** The layout sets no colorway, so A1's "Coverage by month and symbol" uses plotly's default ten colours (A1-top-05). B1's coefficient path draws 33 lines in the same defaults, puts its legend under the range slider, and prints λ.1se over λ.min (B1-top-03). When WebGL is missing, the Scattergl charts show plotly's raw 24 px message.
- **Why it matters.** DESIGN.md's One Meaning Rule says a colour means the same thing in every figure.
- **Proposed change.** Set `layout.colorway` to the sheet order (blue, green, ochre, purple, navy, red, ink-soft) and take family colours from the family map. Move the legend above the plot. Offset the two λ labels. Fall back to `go.Scatter` when WebGL fails.
- **Effort.** S
- **Command.** colorize

### A-24 Fit panel pages in 1280 px

- **Surface and place.** Board, all panel mastheads and front card tags at 1280 by 800. `control.css:144-148`, `base.html:63-86`.
- **Severity.** P2
- **Evidence.** In `rows-1280.json`, the C1 document is 1,329 px wide in a 1,280 px viewport, and the masthead money ends at 1,329. C1-1280-top-01 shows "LOCAL, PAP" and the money cut off. On front1280-top-01 the A2 tag is cut at "CONFLUEN" (measured as clipped).
- **Why it matters.** On the laptop the page scrolls sideways and the money line is lost.
- **Proposed change.** Below 1,360 px, hide `.repo` and let `.mh-meta` wrap under the flow bar (`flex-wrap` on `.masthead`), or shorten the flow-bar chips to their keys. Shorten the tags to three words, with the full list in the title.
- **Effort.** S
- **Command.** adapt

### A-25 Bring Run up to the record

- **Surface and place.** Board, C1. `card.html` job placement.
- **Severity.** P2
- **Evidence.** In `rows-1440.json`, C1's Run button starts at 2,673 px, on the third screen. Above it sit The record, This run, The last run, Models, Choose Model, Choose Settings, Scores, Calibration and Grid Search (C1-top-03).
- **Why it matters.** The panel exists to run a model and read the answer, and the answer is at the top while the button is three screens down.
- **Proposed change.** Add a compact run strip directly under The record, holding Name this run, Save and run, and the state pill. Keep the full block where it is for its note.
- **Effort.** S
- **Command.** layout

### A-26 Make the small controls look like controls

- **Surface and place.** Board, the panel masthead and the front reels. `control.css:317`, `control.css:793`, `index.html:63-77`.
- **Severity.** P3
- **Evidence.** The masthead buttons "Load best as defaults", "Show run code" and "Show all code" are filled #eef2f6 on a #eef1f4 ground at 10 px with no border, so they read as bold text (A1-top-01). The reel arrows measure 10 by 13 px (front-measure.json) and are buttons inside the card's link. No template has a `main` landmark.
- **Proposed change.** Give ghost buttons a 1 px rule border. Make the reel arrows 24 by 24 px and move the reel bar outside the anchor. Wrap the body block in `main`.
- **Effort.** S
- **Command.** polish

### A-27 Take What to do's edge from the panel

- **Surface and place.** Board, every panel. `control.css:876`, `control.css:737` and `control.css:910`, DESIGN.md.
- **Severity.** P3
- **Evidence.** `.howto` uses `var(--c-c1)` on every panel, so A1 blue (A1-top-04) and B1 green (B1-top-01) both show an orange rule. The stylesheet declares the lane palette twice, and the second block wins. DESIGN.md still lists the older hexes (#1f7ac4, #27a86e, #ea7a2c), a console height of 220 px against 330 px in `control.css:325`, and "no focus-visible rule", which is no longer true.
- **Proposed change.** Use `var(--panel)`. Fold the second `:root` block into the first. Bring DESIGN.md in line with the file.
- **Effort.** S
- **Command.** colorize

### A-28 Cut repeats on the front page

- **Surface and place.** Board, front. `index.html:52-89`.
- **Severity.** P3
- **Evidence.** In front-top-01, each tag repeats its card lead ("MARKET, BASKET, FILTER, RANKING, LABEL" above "Market, timeframe, symbols, screen."). The reading-order chips repeat the six cards in the same order. "9 CHARTS · SETTINGS" counts charts, which no decision uses. The slot captions are cut off, as in "Training window against blind p…".
- **Proposed change.** Keep either the tag or the lead, not both. Replace the chart count with the record count. Let the slot captions wrap to two lines.
- **Effort.** S
- **Command.** distill

### A-29 Name the quantity beside each number

- **Surface and place.** Board, C1 The record, the Best so far box on B1 B2 C1, C1 table heads, A2 Columns.
- **Severity.** P3
- **Evidence.** C1-top-01 reads "Best on record 0.9800 (rf, ...). Last run 1.1480 (RF, ...)", which names neither U2 nor the blind period and spells the model two ways. Best so far reads "Best of 574 fits so far: rf.". The table heads read MAX_DEPTH and N_ESTIMATORS (C1-top-02). The A2 Columns table repeats its family's description on all 90 rows and scrolls sideways (A2-overview).
- **Proposed change.** Write "Best blind U2 0.9800 (random forest, ...)", with one display name per model. Use plain head names, with the library name in the title. In A2 Columns, replace the third column with each column's AUC alone, stability and importance from the feature report.
- **Effort.** S
- **Command.** clarify

### A-30 Widen the grid field

- **Surface and place.** Board, C1 Choose Grid Search.
- **Severity.** P3
- **Evidence.** C1-top-03 shows "learning_rate=0.(" cut off inside a quarter-width box.
- **Proposed change.** Make Grid a full-width two-row textarea in mono type.
- **Effort.** S
- **Command.** layout

By severity there are no P0, 10 P1, 15 P2 and 5 P3 findings.

## Known defects on screen

These were found before this review. This section says only where each one appears on the board.

1. Take-profit and Stop never change the label. They appear in A1 Choose Label (A1-top-02), where the note explains the win as reaching the take-profit before the stop, and in C1 This run as "Label 2 ATR take-profit against 1 ATR stop" (C1-top-01).
2. The eleven A2 engine settings only draw charts. They appear in Choose MACD (5 fields), Choose Averages (2), Choose Fibonacci (2) and Choose Confluence (2), each with its own Save. A2 What to do, step 2, says they change the columns (A2-overview).
3. With no model ticked, three models are fitted, not six. This shows in C1 Choose Model, and `card.html:891` shows all six settings blocks when none is ticked, which supports the wrong reading.
4. Fold pass rate counts folds with U2 under 1, not money. The wrong description appears in the A1 Choose Ranking note, "where the strategy must have made money" (A1-top-02), and in the C1 Scores table, "Pass rate, share of half-year folds where the strategy made money" (C1-top-03).
5. Embargo 0 means 2 days, not the horizon. This shows in the B2 Choose Blind Period note, "0 uses the label horizon" (B2-top-01).
6. Class weight defaults to balanced although it scored worse. This shows in C1 Choose Model, where the note itself says it "lifted blind U2 to 1.15" (C1-top-02), and in C1 This run.
7. The 0.313 base rate is quoted on the 4-hour frame. It appears only as a tooltip, on the A1 take-profit field (`bench_config.py:516`), and cannot be seen in the captures.

## Keep these

1. The record block that opens C1. It gives the verdict first, then the best and last U2, then the counts, and This run states the spread of reruns, "an improvement smaller than that is not an improvement". It is the most honest element on the board.
2. The save machinery, with one Save for the whole panel, an edge on the block with unsaved edits, and a confirmation that names the sections and the time.
3. "From your settings: Rows 6,000. Change them on the tool that owns each one", which puts the one-owner rule on screen.
4. The A1 Datasets Result row, "No crypto strategy has beaten its costs on unseen data", which states a failure as plainly as a success.
5. The lane gradient, the flow bar on every page with the current panel marked, and the breadcrumb.
6. A chart that raises returns a box that names the failure instead of a broken image, and the lightbox asks for a larger draw and says it is waiting.
7. Other runs folded away behind one lead job, and the settings of unticked models hidden.

## Detector false positives

I saw no detector output. These signals in the capture measure files are not findings for this surface, for the reasons given.

1. Controls under 44 px (55 of 56 on A1). The board is a desktop instrument used with a mouse, so the only real target problem is the 10 by 13 px reel arrow, which is in A-26.
2. Text under 12 px (763 of 800 elements on A1). The small scale is intended by DESIGN.md. The fault is the fourteen near-identical steps, which is A-16.
3. Empty figure boxes in the slices. The capture waited 350 ms per slice, and the images do arrive after 4.5 to 10.2 s. The real fault is the missing loading state, which is A-11.
4. "WebGL is not supported" in B2, C1 and C2. Headless Chrome ran with `--disable-gpu`. Only the missing fallback is a finding, which is in A-23.
5. A dark-mode media rule was detected. `control.css` has none, and on panel pages one comes from `plotly.min.js`. The board has no dark theme by design.
