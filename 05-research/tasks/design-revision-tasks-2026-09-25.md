# Design revision tasks

On 25 September 2026 the control centre was audited on three surfaces. The first was
the board served at `127.0.0.1:8787`, on a desktop 1440 and 1280 pixels wide. The second
was its offline export, `01-dashboard/control-centre.html`. The third was the public
friends page at `seamusrobertmurphy.github.io/swing-trader`, on a phone 390 and 360
pixels wide and on a desktop 1440 wide. Five auditors worked from one set of
screenshots and in-page measurements, a design review and a technical review of each
surface and one review of every visible word, and the two design reviews were written
before either saw the detector's output. They returned 148 findings, merged here into
110 tasks. Nothing has been changed; the list is for Seamus and Claude to apply
together.

The list opens with the five scores, then ten decisions that need Seamus before the
work they govern starts, then twelve workstreams in the order they are best applied.
It closes with what must be kept, what the auditors judged not to be faults, and what
was fixed on the public page while the audit ran. Each task names the findings it came
from, and each finding, with its screenshots, measurements, source lines and exact
proposed change, is in the reports under `design-audit-2026-09-25/REPORTS/`. The
prefixes are A for the board design review, BB for the board technical review, AD for
the public page design review, BD for the public page technical review, and PUB, BRD
and EXP for the wording review. P1 is a major fault or a failure of the WCAG AA
standard, P2 a minor fault and P3 polish; no auditor found a fault that blocks a task
outright. S is a small edit, M a few hours and L a day or more.

## Scores

| Surface | Review | Score | Band |
|---|---|---|---|
| Board | Design, Nielsen's ten heuristics | 21 of 40 | Acceptable |
| Board and export | Technical, five dimensions | 10 of 20 | Acceptable |
| Public page | Design, Nielsen's ten heuristics | 17 of 40 | Poor |
| Public page | Technical, five dimensions | 8 of 20 | Poor |
| All three | Wording | 105 colons in prose on the board and 91 on the public page, 38 house terms, 24 terms a friend meets undefined, the 7 known label defects and 21 more labels that promise what the code does not do | |

The board is authored for this product on its front page, but every panel ends in the
same trailing blocks, and several of its numbers contradict each other. The public page
is the board cut down by regular expressions, and each cut left something behind that
still claims to work, so its design and technical integrity both failed.

## Decisions first

1. **Known label defects.** Take-profit and Stop never change the label, the eleven
   A2 engine settings only draw charts, no model ticked fits three models, Fold pass
   rate counts folds with U2 under 1 rather than money, Embargo 0 means two days, and
   class weight ships as balanced. Fix the code, or first relabel them with the
   interim text in BRD-05. These were put on hold on 25 September.
2. **Board labels.** Change the board's own labels to the plain words in Appendix A of
   the wording report, or keep them and add plain glosses on the public page only.
3. **Overfit limit.** Count a fit as passed against the house limit of 1.1 always
   (A-02), or against each run's own limit with the limit printed beside it (BRD-02).
   The saved settings use 1.3, and 58 of the 323 fits counted as passed were run at 1.3.
4. **Verdict.** Add the after-cost return per trade on the test period as a bar a run
   must pass before it can read WORTH KEEPING (A-03).
5. **Results colours.** Move the C1 and C2 lanes off red-orange, which sits beside the
   failure red, for example to the cheat sheet's purple, and give Save and Run one fixed
   action colour on every panel (A-17).
6. **Public page build.** Keep one 15 MB file cut down from the board, or build the
   public page as its own page that loads each panel and its images when opened (BD-4).
   The second is a day or more of work and removes most of the speed and orphan faults.
7. **Public starting settings.** Build the public page from a fixed demo configuration
   (expanding folds, no class weight, overfit limit 1.1) rather than the operator's
   saved file, which today starts a friend on Monte Carlo folds and a 1.3 limit.
8. **Friends' names.** Warn that names are published in the public repository history,
   or stop publishing them and show initials only.
9. **Paths on C1.** The This run block prints the command and file paths, which the
   20 September rule forbids on a panel. Keep them, or show a short name with the path
   in the tooltip (A-13).
10. **Front page answer.** Put each panel's standing on its front card, for C1 "Best
    test U2 0.980; last run 1.148; none cleared fees" (A-06).

## Truth on screen

These come first because the product's fifth principle says a board that reads better
than the evidence is worse than no board.

| # | Task | Severity | Where | Effort | From |
|---|---|---|---|---|---|
| 1.1 | Read fits, runs, passed and beat from one function everywhere; C1 says 574 fits and 119 beat a constant guess, its histogram says 66 of 504, C2 says "460 and counting" | P1 | board, public, export | M | A-01, BRD-13 |
| 1.2 | Count passed against one overfit limit, or print each run's limit (decision 3); warn when a saved limit is above 1.1 | P1 | board, public | M | A-02, BRD-02 |
| 1.3 | Make the verdict read NO when test U2 is 1 or more, replace NOT YET with "NO, passed 1 of 3", and put the failing number in the sentence (decision 4 for the money bar) | P1 | board, public | M | A-03 |
| 1.4 | Colour failing numbers, test U2 of 1 or more and AUC under 0.5 in red, and show green only when every bar passes; today a row with U2 1.148 shows only a green "passes" | P1 | board, public cards | S | A-04, AD-17 |
| 1.5 | Fix the A2 stability chart, which plots every feature at zero because it looks for column names the feature report does not use (`stable`, `in_company`) | P1 | board, public | S | A-05 |
| 1.6 | Give each front card its panel's standing, draw the age dot in neutral ink with its rule in words, and label the masthead money as the equity paper book (decision 10) | P1 | board, export | M | A-06, BB-21 |
| 1.7 | Say that the best fit missed the fold bar, and build its day count, fold count and limit from the record; "unseen year" was 150 days | P1 | board, public | S | BRD-01 |
| 1.8 | Make A1's crypto verdict agree with C1, where 9 three-way fits made money after cost | P1 | board, public, export | S | BRD-03 |
| 1.9 | Rewrite the three preset blurbs with what failed; the three-way +1.23 per cent came from LINK, LTC and MATIC with overlapping trades, and the best fit passed 0 of 2 folds | P1 | public | S | PUB-02, AD-9 |
| 1.10 | Show what the known label defects actually do until the code changes (decision 1) | P1 | board, public, export | M | BRD-05 |
| 1.11 | Update the ten stale numbers in help text, among them the 0.313 base rate, the 6.1 basis point execution cost and "0.5 is guessing" | P2 | board, public, export | S | BRD-13 |
| 1.12 | Fill the B2 and C1 Result and Benchmark columns from the newest record with its date | P2 | board | M | A-14 |
| 1.13 | Mark a resampling method that ignores time at the control and in C1's verdict | P2 | board | S | A-19 |
| 1.14 | Date evidence by the record's own stamp, not the file's modification time | P2 | board | S | A-21 |

## Friends first visit

| # | Task | Severity | Where | Effort | From |
|---|---|---|---|---|---|
| 2.1 | Make Run Model amber; `button.btn` outranks `.demo-go`, so write `button.btn.demo-go`, and add a disabled style | P1 | public | S | AD-1, BD-11 |
| 2.2 | Open the front page with three sentences on what this is and who built it, and label or hide the operator's $102,206 account line | P1 | public | S | AD-2, PUB-06 |
| 2.3 | Warn that names are public and kept in the repository history, change the placeholder to "A first name or nickname", add `autocomplete="nickname"` (decision 8) | P1 | public | S | AD-3, BD-18 |
| 2.4 | Start a friend from the Quick and simple preset when nothing is stored (decision 7) | P1 | public | S | AD-6, PUB-10 |
| 2.5 | Replace every What to do list with public steps that name only buttons on the page | P1 | public | S | AD-7, BD-12 |
| 2.6 | Print the demo's limits beside the fields, at most 6 coins, 30,000 candles, 5 folds, 3 repeats, 3 models, 60 to 365 test days | P1 | public | S | PUB-03 |
| 2.7 | Say Run Model sends the settings on screen, define a paper ticket, and save on change instead of eight Save buttons | P1 | public | S | PUB-04, AD-14 |
| 2.8 | Write run messages in words, model names not codes, known failures explained, and a load failure distinct from an empty board | P1 | public | M | PUB-05, AD-12 |
| 2.9 | Announce the run status with `role="status"`, style a failure apart from progress, and show three steps while the run goes | P1 | public | S | BD-10, AD-12 |
| 2.10 | Define the 24 terms a friend meets before any definition, at first use | P1 | public | M | PUB-07 |
| 2.11 | Resume waiting after a reload and keep Run disabled while a run is in flight; parse a relay error that is not JSON | P2 | public | M | BD-18, AD-11 |
| 2.12 | Print the settle time before Run, and after Done offer a calendar reminder and a link to the friend's run on C2 | P2 | public | M | AD-11 |
| 2.13 | Show each preset's blurb before the tap, mark Quick and simple "Start here", and print a one-line summary of what will run | P2 | public | S | AD-13 |
| 2.14 | Name options in words with the code in brackets, and remove Also include, Leave out and Grid from the public page | P2 | public | M | AD-15, PUB-09 |
| 2.15 | Remove the operator's records from the public page, the Evidence Log, Other runs, Hard Rules, the Alpaca columns and the A2 column internals | P2 | public | M | AD-16, PUB-08 |
| 2.16 | Add a link preview, a description, an icon and `color-scheme: only light` | P2 | public | S | AD-23, BD-27 |
| 2.17 | Fold Quick start to one line on the panels once a preset is chosen | P3 | public phone | S | AD-24 |
| 2.18 | Review the new C2 text in the working copy before it publishes | P3 | public | S | PUB-11 |

## Friends page speed

At 1.6 Mbps with a phone-speed processor the first paint came at 13.7 seconds, and the
Run and preset buttons were visible but did nothing until 78.9 seconds (BD-1).

| # | Task | Severity | Where | Effort | From |
|---|---|---|---|---|---|
| 3.1 | Drop the 207 front-card reel images nobody can reach, 9.9 MB of the 25.8 MB file | P1 | public | S | BD-2, AD-5 |
| 3.2 | Bind Run and the presets, and pick the view from the address, in a script near the top of the page | P1 | public | M | BD-1 |
| 3.3 | Ship Plotly's 1.4 MB cartesian bundle instead of the 4.8 MB full one, deferred, drawn when a panel opens, with `scatter` in place of `scattergl` | P1 | public | M | BD-3, BD-20 |
| 3.4 | Publish images as files and panels as separate fetches, with a budget of 1.5 MB for the first view (decision 6) | P1 | public | L | BD-4, AD-5 |

## Friends on phones

| # | Task | Severity | Where | Effort | From |
|---|---|---|---|---|---|
| 4.1 | Put the panel in the address when a chip is tapped, so Back works, and resize figures when a panel opens | P1 | public | S | AD-4 |
| 4.2 | Fit interactive figures to the phone; today they draw 700 pixels wide in a 334 pixel box | P1 | public phone | S | BD-5 |
| 4.3 | Stop the C2 charts widening after "See results" with `minmax(0,1fr)` grid tracks | P1 | public phone | S | BD-6 |
| 4.4 | Show the first ten rows of any long table on a phone with a Show all button; C1 is 343,870 pixels tall today | P1 | public phone | S | AD-8, BD-7 |
| 4.5 | Show each field's explanation on a phone; 229 exist only as hover text | P1 | public phone | M | PUB-01, AD-21, BD-16 |
| 4.6 | Restore the table filter, sort and "Beat a constant guess" scripts, or remove the controls | P2 | public | S | BD-14 |
| 4.7 | Give number fields a number keyboard, the demo limits as `min` and `max`, and 30,000,000 written with separators | P2 | public | M | BD-15, BRD-22 |
| 4.8 | Use tick boxes for Coins, Families and Models; a plain click on a desktop list drops the other choices | P2 | public | M | AD-22, BD-25 |
| 4.9 | Make the panel chips 44 pixels tall, mark the current one, and end each panel with next-panel and back-to-top links | P2 | public phone | S | AD-18 |
| 4.10 | Let a tap open a chart full size, lock chart zoom on phones, and draw phone versions of the front-card charts | P2 | public phone | M | AD-19, BD-21, BD-23 |
| 4.11 | Hide empty labelled cells, show one ticket card per run, and say "passes the overfit bar" in full | P2 | public phone | S | AD-17 |
| 4.12 | Stop the desktop C2 Runs table pushing the page sideways | P2 | public desktop | S | BD-13 |
| 4.13 | Raise the phone front-card tags, counts and captions to 12 pixels and let captions wrap | P2 | public phone | S | BD-22, AD-25 |
| 4.14 | Hide the timeline band and the second reading-order row on the public desktop | P3 | public desktop | S | AD-27 |
| 4.15 | Lay the C2 totals tiles out two to a row on phones | P3 | public phone | S | AD-28 |
| 4.16 | Drop the boxes inside boxes on the public forms, keeping the white block only | P3 | public | S | BD-26 |

## Friends page colour

| # | Task | Severity | Where | Effort | From |
|---|---|---|---|---|---|
| 5.1 | Keep the muted lane colours for card edges and add darker lane text colours; panel names measure 2.58 to 3.80 to 1 against the 4.5 required | P1 | public | S | AD-10, BD-8 |
| 5.2 | Darken the table header and card label grey from `#8a8378` to `#6b6660` | P1 | public | S | BD-9, AD-10 |
| 5.3 | Raise the input border and the chosen-preset ring to 3 to 1, and expose the chosen preset with `aria-pressed` | P2 | public | S | BD-17 |
| 5.4 | Write the warm theme as tokens and remove the dark-theme path it is built from; the page carries 166 `!important` flags | P2 | public | M | BD-24 |
| 5.5 | Warm the leftover cool rules and navy title, and take the page's description out of warning red | P3 | public | S | AD-26 |

## Board safety

| # | Task | Severity | Where | Effort | From |
|---|---|---|---|---|---|
| 6.1 | Ask before Reset, Reset defaults or Load best discards unsaved edits, guard the page against leaving with unsaved edits, and make the job Reset clear only its form | P1 | board | M | A-09, BB-12 |
| 6.2 | Save before a run, or refuse to run while a form is unsaved | P1 | board | S | A-10 |
| 6.3 | Handle a server that is down in Save, Run and the status poll | P2 | board | S | BB-10 |
| 6.4 | Disable Stop when nothing runs and show "stopping" when pressed | P2 | board | S | BB-11 |
| 6.5 | Stop B1 fitting a model every time its page opens; it posts `/varselect/fit` on load, and the audit's own captures triggered it, in memory, writing no file | P2 | board | M | A-12 |

## Board accessibility

| # | Task | Severity | Where | Effort | From |
|---|---|---|---|---|---|
| 7.1 | Uncover the front-card chart arrows, which the caption bar paints over, and move them out of the card link | P1 | board, export | M | BB-01, A-26 |
| 7.2 | Make the 99 field notes reachable by keyboard and screen reader, with `aria-describedby` and a note that opens on hover and on focus | P1 | board | M | BB-05 |
| 7.3 | Let the keyboard sort the tables, with `aria-sort` | P1 | board | S | BB-06 |
| 7.4 | Make the chart lightbox a real dialog and name each Expand button | P1 | board | S | BB-07 |
| 7.5 | Announce save, run and stop state | P1 | board | S | BB-08 |
| 7.6 | Give the charts readable alt text instead of their file keys | P1 | board, export | S | BB-09 |
| 7.7 | Remove the 0.85 opacity from the front-card tags and darken the B2 and C2 panel names and the console placeholder to clear 4.5 to 1 | P1 | board, export | S | A-08, BB-03 |
| 7.8 | Add a main landmark, a skip link and an h1, h2, h3 outline | P2 | board, export | S | BB-20 |
| 7.9 | Write stale or fresh beside each front-card dot | P2 | board, export | S | BB-21 |
| 7.10 | Honour the reduced-motion setting | P3 | board | S | BB-25 |
| 7.11 | Give the masthead ghost buttons a border so they read as buttons | P3 | board | S | A-26 |

## Board layout

| # | Task | Severity | Where | Effort | From |
|---|---|---|---|---|---|
| 8.1 | Fill the short side of each row as the 20 September rule requires, 100 to 687 pixels are blank today, and add a check that fails past 40 pixels | P1 | board | M | A-07 |
| 8.2 | Keep the masthead and front tags on screen at 1280 pixels by letting them wrap | P1 | board | S | BB-02, A-24, BB-23 |
| 8.3 | Let the front page scroll under zoom or in a short window, where C1 and C2 are lost today | P1 | board, export | S | BB-04 |
| 8.4 | Cut the type scale from 14 sizes to four, set the verdict at 16 pixels, and raise the masthead money to 11 or 12 | P2 | board | M | A-16, BB-19 |
| 8.5 | Show "drawing" in a chart box until its image arrives, and "draw failed" on error | P2 | board | S | A-11 |
| 8.6 | Sort the scoreboard by test U2 among passing fits, fold identical reruns into one row, right-align numbers, render 100 rows first | P2 | board | M | A-15 |
| 8.7 | Add a compact run strip under C1's record; Run sits 2,673 pixels down today | P2 | board | S | A-25 |
| 8.8 | Hold the idle console at 40 pixels and show the last error line when a run fails | P2 | board | S | A-20 |
| 8.9 | Hold each tool's note to one line | P2 | board | M | A-22 |
| 8.10 | Make the What to do steps and button labels match the controls on the page | P2 | board | S | A-18, BRD-04, BRD-19 |
| 8.11 | Keep either the tag or the lead on each front card, not both | P3 | board | S | A-28 |
| 8.12 | Name the quantity beside each number, "Best test U2 0.9800 (random forest)" | P3 | board | S | A-29 |
| 8.13 | Make the grid field full width | P3 | board | S | A-30 |
| 8.14 | Stop stretching the timeline image | P3 | board, export | S | BB-27 |

## Board speed

| # | Task | Severity | Where | Effort | From |
|---|---|---|---|---|---|
| 9.1 | Cache each chart drawing with an ETag and redraw only the charts a save affects; the front page takes 4.3 seconds to finish | P2 | board | M | BB-13, A-12 |
| 9.2 | Defer Plotly, use the cartesian bundle and `scatter` | P2 | board | M | BB-14 |
| 9.3 | Lighten C1, 1.3 MB and 14,105 nodes, and find why A1 takes 2 to 3.4 seconds to its first byte | P2 | board | M | BB-15 |
| 9.4 | Drop the 810 per-cell tooltips on A2's Columns table, 43 per cent of that page | P2 | board, export | S | BB-16 |

## Colour system

| # | Task | Severity | Where | Effort | From |
|---|---|---|---|---|---|
| 10.1 | Draw the charts and the Explore figures in the lane and house colours, so a colour means one thing everywhere | P2 | board, public, export | M | BB-17, A-23 |
| 10.2 | Merge the two lane colour blocks in the stylesheet, bring DESIGN.md to the current shades, and define the missing `--soft` token | P2 | board | S | BB-17, A-27, BB-24 |
| 10.3 | Move C1 and C2 off red-orange and give Save and Run one action colour (decision 5) | P2 | board | M | A-17 |
| 10.4 | Draw the What to do edge in the panel's own colour | P3 | board | S | A-27 |

## Wording sweep

| # | Task | Severity | Where | Effort | From |
|---|---|---|---|---|---|
| 11.1 | Replace the 38 house terms and use one name for one thing (decision 2) | P2 | board, public, export | M | BRD-11, BRD-12 |
| 11.2 | Take the colons out of prose at the 45 source sites and six script-built lines | P2 | board, public, export | M | BRD-15 |
| 11.3 | Remove the em dashes, one in the filter label and twelve in chart axis titles, and the middle dots | P2 | board, public, export | S | BB-22, BD-28, BRD-16 |
| 11.4 | Replace the 37 figurative lines and aphorisms | P2 | board, public, export | S | BRD-14 |
| 11.5 | Name what each button does, "Run the test" rather than "Run it" | P2 | board, public | S | BRD-19 |
| 11.6 | Take paths and file names out of readable text (decision 9) | P2 | board, public | M | BRD-20, A-13 |
| 11.7 | Give every results heading a gloss and define MISE | P2 | board, public | S | BRD-17 |
| 11.8 | Repair the sentences broken by the "comparison run" replacement | P2 | board, public, export | S | BRD-10 |
| 11.9 | Count Embargo in the timeframe's own bars, fix the horizon example on stock frames, and name the model settings correctly | P2 | board, public | S | BRD-06, BRD-09, BRD-07 |
| 11.10 | Describe C2 as it is | P2 | board, public | S | BRD-08 |
| 11.11 | Hold headings to three words and use sentence case throughout | P3 | board, public, export | S | BRD-18, BRD-23 |
| 11.12 | Describe only the chosen models' settings under Choose Settings | P3 | board, public | S | BRD-21 |

## Export

| # | Task | Severity | Where | Effort | From |
|---|---|---|---|---|---|
| 12.1 | Remove the controls the file cannot run, four filters, a checkbox, sort headings, six empty figure boxes and two empty disclosures | P2 | export | S | BB-18 |
| 12.2 | Shrink the 19.7 MB file by quantising the charts and dropping reel copies | P3 | export | S | BB-26 |
| 12.3 | Word the footer without a folder path | P3 | export | S | EXP-01 |

## Keep these

1. C1's record block, which gives the verdict first, then the best and last scores,
   and the spread of reruns with "an improvement smaller than that is not an
   improvement".
2. One Save for the whole panel, the edge on a block with unsaved edits, and a save
   line that names the sections and the time.
3. "From your settings", which shows each value once and names the tool that owns it.
4. A1's plain statement that no crypto strategy has beaten its costs, once it agrees
   with C1.
5. The lane gradient, the flow bar with the current panel marked, and the focus ring
   in the panel's colour, with no `outline:none` anywhere.
6. A chart that fails to draw returns a box naming the failure instead of a broken
   image.
7. On the public page, Quick start and Run Model inside the first phone screen, 16
   pixel inputs 44 pixels tall, no sideways scroll on a phone, the relay's plain limit
   messages, C2's "About this page", the C2 ticket charts with zoom and toolbar off, and
   the warm light theme Seamus approved on 24 September.

## Not faults

The auditors judged these detector and measurement signals not to be faults. The
board's small type and density are intended by DESIGN.md, so only the fourteen near
sizes and the 8 to 9 pixel money line are tasks. Controls under 44 pixels on the
desktop board are mouse targets, apart from the 10 by 13 pixel reel arrows. The coloured
left rule on sections is the documented lane device. "WebGL is not supported" came from
headless Chrome run with the GPU off. The dark-mode rule found on panel pages is
Plotly's, and no page has a dark theme. The detector could not load the public page at
its full 78.9 MB rendered size and was run on a copy with each image replaced by a grey
block of the same size.

## Fixed meanwhile

The public page was republished at 00:27 GMT on 26 September by the demo work running
in another session, and three faults seen in the captures were already fixed in it. The
badge "LOCAL, PAPER ONLY" became "PAPER ONLY", the blank BUY and PASS boxes on C2 read
"none yet", and the tickets column "Bars" became "Timeframe". Every task above was
checked against that build.

## Evidence

The reports, the brief the auditors worked to, the capture tool and every screenshot
and measure file are in `design-audit-2026-09-25/` beside this list. Only the five
reports and this list are committed; the 147 screenshots and the measure files stay on
this machine, because `tasks/` is ignored by git.
