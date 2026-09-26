# B-board audit

Assessment B, the technical audit of the served control-centre board at `http://127.0.0.1:8787` and its offline export `01-dashboard/control-centre.html`, run on 25 September 2026 against the five dimensions of the impeccable audit playbook. Nothing was pressed or posted and no repository file was changed. Evidence written by this assessment is in `audit/B-board/`, beside the captures already in `audit/board/` and `audit/export/`.

The order below is the health table, the integrity verdict, a summary of the measure files and timings, the findings from most to least severe, what works and must be kept, the detector findings judged false, and where the known label defects appear on screen.

## Audit health

| # | Dimension | Score | Key finding |
|---|-----------|-------|-------------|
| 1 | Accessibility | 2 | Every explanatory note is a `title` on a non-focusable div with its text removed by `display:none !important`, so no keyboard or screen-reader user can reach any of the 99 field notes; sorting, the lightbox and run status are mouse-only or silent |
| 2 | Performance | 2 | Every chart is redrawn by matplotlib behind one global lock and served `no-store`, so the front page's load event lands at 4.27 s against DOMContentLoaded at 0.79 s; a 4.8 MB plotly bundle blocks rendering on every panel page |
| 3 | Responsive design | 2 | Desktop-only by design and sound at 1440 by 900; at 1280 by 800 every panel masthead runs 72 px off screen and cuts the LOCAL, PAPER ONLY badge; at 200 per cent zoom the front page hides C1 and C2 and cannot scroll |
| 4 | Theming | 2 | Tokens exist and 268 `var()` uses carry most colour, but the charts use a different palette from the lanes, DESIGN.md lists the pre-22 September lane shades, lane tokens are declared twice, one token (`--soft`) is undefined, and there is no reduced-motion rule |
| 5 | Implementation integrity | 2 | Several verified defects of one shape, a fix or a claim that did not reach every copy: the front-page chart arrows exist but are painted over, the keyboard sort a comment promises was never wired, the per-cell titles a comment records as removed survive on A2, and the export keeps controls it has no script for |
| **Total** | | **10/20** | **Acceptable, significant work needed** |

The generic rubric scores a desktop-only page 0 on responsive design. The brief asks for a judgement against the board's stated intent, one expert on a desktop, and against that intent the board earns 2, because it works at 1440 by 900 and breaks at 1280 by 800 and under zoom.

## Integrity verdict

Pass, narrowly. The board is a product-specific system and not an interchangeable template. It has one stylesheet with named tokens, a lane-colour inheritance through `--panel` (control.css lines 234 to 239 and 748 to 750), a single `:focus-visible` rule in the lane colour (lines 894 to 900), labels bound to every settings input, and templates whose comments record each operator decision with its date. The detector's volume, 85 to 269 warnings a page, is mostly the intended density and the documented coloured left rule, and those are listed as false positives at the end.

What keeps the verdict narrow is a repeated pattern. A fix or a promise is written once and does not reach the other copies of the same thing. The front-page reel arrows were built and are then covered by the caption bar (BB-01). The stylesheet says sortable headings answer the keyboard (control.css lines 901 to 902) and the script binds only `click` (card.html line 1127). The template comment at card.html lines 319 to 325 records removing per-cell titles because they were 48.3 per cent of C1, and the second table template at line 425 still emits 810 of them on A2. DESIGN.md's One Meaning Rule says the chart module declares the stylesheet's hexadecimals, and it declares none of the six lane colours. The export's own rule is that a control it cannot run is removed or disabled, and it keeps four filter boxes, a checkbox, nine sortable headings and six 330 px figure boxes with no script behind any of them.

## Measure summary

The measure files are `board/<view>-measure.json` and `export/e-measure.json`, all at 1440 by 900. Contrast counts come from the capture tool, which does not composite `opacity`; the front-page tag failures in BB-03 were computed from the stylesheet instead.

| View | Page height px | DOM nodes | Text under 12 px | Contrast fails measured | Controls under 44 px | Unnamed controls | Images, lazy | Headings | `main` |
|---|---|---|---|---|---|---|---|---|---|
| front | 900, locked | 432 | 60 of 79 | 0 | 31 of 38 | 1, the timeline link | 219, 206 | h1, 6 h2 | no |
| A1 | 4,332 | 1,570 | 763 of 800 | 0 | 55 of 56 | 0 | 17, 16 | h1 then h3, 14 | no |
| A2 | 3,610 | 1,706 | 295 of 1,152 | 0 | 49 of 52 | 0 | 10, 9 | h1 then h3, 13 | no |
| B1 | 2,986 | 1,865 | 80 of 162 | 0 | 92 of 92 | 1, not real | 5, 4 | h1 then h3, 10 | no |
| B2 | 2,746 | 486 | 90 of 137 | 1, panel name 4.40 | 48 of 48 | 0 | 8, 7 | h1 then h3, 10 | no |
| C1 | 7,246 | 14,105 | 261 of 10,822 | 0 | 105 of 107 | 5, not real | 16, 15 | h1 then h3, 27 | no |
| C2 | 4,087 | 3,815 | 95 of 2,027 | 1, panel name 4.22 | 52 of 54 | 0 | 21, 20 | h1 then h3, 11 | no |
| export, front view | 964 | 18,835 | 61 of 81 | 0 | 31 of 38 | 1 | 296, 277, 290 as data URIs | h1, 6 h2 | no |

Every page has `lang="en"` and a title, every table has `th`, and no page scrolls sideways at 1440. The board has two `:focus` rules of its own; the other nine counted on panel pages come from plotly. No page carries a `prefers-reduced-motion` rule. The `prefers-color-scheme` rule the measure found on panel pages is plotly's injected `prefers-color-scheme:light` CSS, not the board's, so the board has no dark mode, which matches its design. Most controls sit under 44 px, which is the AAA target (WCAG 2.5.5); the AA minimum (2.5.8, 24 px or spaced) is met by the masthead and flow controls through spacing, so target size is not reported as a failure except where a control is also hidden (BB-01). The unnamed ghost buttons on B1 and C1 and the empty h3 headings on those panels are the job forms folded inside the closed "Other runs" disclosure, whose text a closed `details` does not render; they are not real.

Page timings, curl GET from this machine, three or four samples each, time to first byte: front 0.75 to 1.11 s, A1 1.94 to 3.44 s, A2 0.26 s, B1 0.32 s, B2 0.41 s, C1 1.35 to 2.02 s, C2 0.73 s. Document transfer from the measure files: front 63 KB (load event 4,268 ms), A1 187 KB (3,600 ms), A2 304 KB (1,109 ms), B1 205 KB (1,517 ms), B2 197 KB (2,072 ms), C1 1,304 KB (3,595 ms), C2 659 KB (4,267 ms). Each panel page also loads `plotly.min.js` at 4,844,191 bytes uncompressed. Chart PNGs measured 15,331 to 41,409 bytes and took 0.12 to 0.53 s each, redrawn on every request. The export is 19,685,805 bytes and opened in 581 ms from disk.

## Findings

**BB-01. Uncover the front-page chart arrows**

- **Surface and place**: board and export, front page, all six cards. `03-inputs/control_templates/index.html` lines 63 to 90; `03-inputs/control_static/control.css` lines 776 to 781.
- **Severity**: P1. WCAG 2.4.11 Focus Not Obscured (Minimum), AA, and 4.1.2 Name, Role, Value for the buttons nested in a link.
- **Evidence**: the detector reports `span.reelnum "3/10" is 100% covered by an opaque element (div.slotcap)` twelve times, two per card (`B-board/detect-front.json`). The crop `B-board/front-slot-foot-crop.png` from `board/front-top-01.png` shows the caption bar and no arrows. Cause: `.slotcap` is absolutely placed at the bottom with `background:#fff` and 60 px of right padding, and it follows `.reelbar` in the markup with no `z-index` on either, so it paints over the arrows. The caption is also cut with an ellipsis while those 60 px stay blank. The 24 arrow buttons still take focus, invisibly, and they sit inside `<a class="card">`, so a click on the covered arrow opens the panel instead of stepping.
- **Why it matters**: the operator's 16 September design, two charts per card stepped by hand, does not work, and a keyboard user tabs through 24 stops that cannot be seen.
- **Proposed change**: give `.card .pair .slot .reelbar` `z-index:2; background:#fff; border-left:1px solid var(--rule)` and change `.slotcap` padding to `1px 5px 2px 5px` with `right:62px`. Move the buttons out of the link, making the card an `<article class="card">` whose `h2` holds `<a href="/card/A1">` with `a::after{content:"";position:absolute;inset:0}` so the whole card stays clickable and the reel buttons, at `position:relative; z-index:3`, sit above it. Give each button a name that says which panel, `aria-label="Next A1 chart"`.
- **Effort**: M
- **Command**: harden

**BB-02. Keep the panel masthead on screen at 1280**

- **Surface and place**: board, all six panel pages at 1280 by 800. `03-inputs/control_templates/base.html` lines 45 to 87; `control.css` lines 125 to 146, 792 to 793 and 926 to 927.
- **Severity**: P1. WCAG 1.4.10 Reflow, AA, within the board's own desktop target.
- **Evidence**: `B-board/A1-1280-measure.json` gives a document 1,352 px wide in a 1,280 px window, with `.mh-meta`, the badge and the cash line ending at 1,352 px. `B-board/A1-1280-top-01.png` and `board/C1-1280-top-01.png` show the badge cut to "LOCAL," and the account line cut after "$4,481". The title, four tool buttons and the six-step flow bar are all `flex:0 0 auto` and nothing in the band wraps or shrinks.
- **Why it matters**: the paper-only badge is the board's safety signal and the dollar line is the first figure the repository's reporting rule asks for, and both leave the screen on the smaller of the two desktop sizes the brief names.
- **Proposed change**: `.masthead{flex-wrap:wrap; row-gap:4px}`; `.flowbar{flex:1 1 auto; min-width:0; flex-wrap:wrap}`; `.mh-meta{flex:0 1 auto; min-width:0; max-width:none}`; and below 1400 px hide `.flowbar .flowstep span` so the steps show "A1" to "C2" with the full name kept in their existing `title`.
- **Effort**: S
- **Command**: adapt

**BB-03. Fix the text colours that fail AA**

- **Surface and place**: board and export. Front-page card tags, `control.css` lines 217 to 221; the panel name in the masthead, line 538 with the lane tokens at lines 910 to 915; the empty console line, line 328.
- **Severity**: P1. WCAG 1.4.3 Contrast (Minimum), AA.
- **Evidence**: `.card > h2 .tag` carries `opacity:0.85`, so its white 9.5 px bold text sits on a paler lane colour. Computed from the stylesheet, A2 4.11, B1 4.03, B2 3.80, C1 4.05 and C2 3.69 to 1; only A1 passes at 5.79. The measure files record the panel name on the board ground `#eef1f4` at 4.40 on B2 (`board/B2-measure.json`) and 4.22 on C2 (`board/C2-measure.json`); the 22 September darkening at lines 910 to 915 was checked against white, not against the ground the masthead sits on. The console's "Nothing has run yet in this session." is `#5b6b7d` on `#0b2038`, 3.01 to 1, and the measure tool cannot see it because it is a pseudo-element.
- **Why it matters**: these are the labels that say what each panel holds and which panel is open.
- **Proposed change**: delete `opacity:0.85` from `.card > h2 .tag` (every lane then passes, the lowest C2 at 4.79). Set `--c-b2:#1b7b4f` (4.64 on the ground, 5.26 under white type) and `--c-c2:#aa550f` (4.61 and 5.23), and consider `--c-c1:#c0400c` since the current 4.57 passes by 0.07. Set the console placeholder colour to `#788a9d` (4.63).
- **Effort**: S
- **Command**: colorize

**BB-04. Let the front page scroll when it cannot fit**

- **Surface and place**: board and export, front page under browser zoom or a short window. `control.css` lines 61 to 65 and 293; `base.html` lines 24 to 29.
- **Severity**: P1. WCAG 1.4.4 Resize Text, AA, and 1.4.10 Reflow, AA.
- **Evidence**: `B-board/front-zoom200-top-01.png` at 720 by 450 CSS pixels, which is 1440 by 900 at 200 per cent zoom. Every chart slot collapses to a line, the C1 card is cut mid-sentence, C2 is off the page, and `B-board/front-zoom200-measure.json` gives a document exactly 450 px tall, so nothing scrolls. The cause is `.sheet.front{height:100vh; overflow:hidden}`, which the script re-applies on every resize.
- **Why it matters**: the one operator who zooms in, which the board itself invites with `?zoom=`, loses two of the six panels and every chart on the front page.
- **Proposed change**: add `@media (max-height:760px), (max-width:1100px){ .sheet.front{height:auto !important; overflow:visible} .sheet.front .lane{grid-template-rows:auto} .card .pair{min-height:200px} }`, and in `fit()` skip setting the height when `matchMedia('(max-height:760px), (max-width:1100px)').matches`. The no-scroll rule then still holds at the desktop sizes it was written for.
- **Effort**: S
- **Command**: adapt

**BB-05. Make the notes reachable without a mouse**

- **Surface and place**: board, every panel page. `card.html` lines 35 to 110, 466 to 509 and 1115 to 1118; `control.css` line 785.
- **Severity**: P1. WCAG 1.3.1 Info and Relationships, A; 2.1.1 Keyboard, A; 3.3.2 Labels or Instructions, A.
- **Evidence**: `.hint{display:none !important}` removes each note from the accessibility tree, and the script copies it into a `title` on the wrapping `div.field`, which never takes focus. Counted in the served HTML, 99 `div.field[title]` notes across the six panels (55 on C1), 15 headings, 94 column headings and 17 glossed terms carry text reachable only by hovering, and `aria-describedby` appears zero times on any page. Focusing an input shows and announces nothing of its note.
- **Why it matters**: the notes are where every setting is defined, and the operator's rule that every term is defined where first used holds only for a mouse.
- **Proposed change**: keep the Tooltip Rule and make the tooltip reachable. Replace the `display:none` on `.hint` with a visually hidden class (`position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0)`), give each `.hint` an id and each input `aria-describedby` pointing at it, and show the hint as a small positioned panel on `.field:hover` and `.field:focus-within`, closed by Escape, instead of relying on the native `title`. Drop the duplicated `title` once the panel exists.
- **Effort**: M
- **Command**: harden

**BB-06. Let the keyboard sort the tables**

- **Surface and place**: board, every sortable table (Datasets, Screening, Columns, Scores, Scoreboard, Three-way and others). `card.html` lines 1125 to 1158; `control.css` lines 901 to 902.
- **Severity**: P1. WCAG 2.1.1 Keyboard, A; 4.1.2 Name, Role, Value, A.
- **Evidence**: the script binds only `click` on `table.sortable th`; `tabindex` and `aria-sort` appear zero times in every served page. The stylesheet comment says "A sortable heading is a control, so it takes focus and answers the keyboard", which the code does not do.
- **Why it matters**: sorting the 574-row scoreboard is how runs are compared, which PRODUCT.md names as the point of a session.
- **Proposed change**: render each sortable heading as `<th aria-sort="none"><button type="button" class="sortbtn">{{ h }}</button></th>`, bind the sort to the button, and set `aria-sort` to `ascending` or `descending` on the sorted `th` and `none` on the rest.
- **Effort**: S
- **Command**: harden

**BB-07. Give the chart lightbox dialog behaviour**

- **Surface and place**: board, every panel page. `card.html` lines 687 to 692 and 1238 to 1282.
- **Severity**: P1. WCAG 2.4.3 Focus Order, A; 2.4.11 Focus Not Obscured (Minimum), AA; 4.1.2 Name, Role, Value, A.
- **Evidence**: the overlay is a `div` with no `role="dialog"` or `aria-modal`, focus stays on the Expand button behind it, Tab moves through the page underneath the overlay, and closing does not return focus. Every one of the 15 to 21 Expand buttons on a panel has the same name, "Expand". Escape does close it (line 1281).
- **Why it matters**: a keyboard user opens a chart and then tabs through controls hidden under an 88 per cent navy veil.
- **Proposed change**: make the overlay a `<dialog id="lightbox">`, open it with `showModal()` and close it with `close()`, which gives a focus trap, an inert page and Escape for free, and call `opener.focus()` on close. Name each button `aria-label="Expand {{ caption }}"`.
- **Effort**: S
- **Command**: harden

**BB-08. Announce save, run and stop state**

- **Surface and place**: board, masthead save state and every panel's Output block. `card.html` lines 10, 596 to 599, 786 to 790 and 1287 to 1292.
- **Severity**: P1. WCAG 4.1.3 Status Messages, AA.
- **Evidence**: `#savestate`, `#runstate` and `#console` have no `role="status"` or `aria-live`; `aria-live` appears zero times on every served page. "saved", "running for N seconds", "finished" and "exit code" change silently.
- **Why it matters**: a run takes seconds to minutes and its outcome is the thing the panel exists to report.
- **Proposed change**: `role="status"` on `#savestate` and `#runinfo`, and `aria-live="polite"` with `aria-atomic="false"` on `#console` only while a run is in progress, so its lines are not read back on load.
- **Effort**: S
- **Command**: harden

**BB-09. Give the charts real alt text**

- **Surface and place**: board and export, every panel page and the lightbox. `card.html` lines 338, 382, 722 and 1262; front-page timeline link at `index.html` lines 40 to 42.
- **Severity**: P1. WCAG 1.1.1 Non-text Content, A.
- **Evidence**: panel charts use `alt="{{ name }}"`, so C1's 15 charts read "reliability-curve", "kde-spread", "scoreboard" and so on (`B-board/C1.html`), and the lightbox copies that slug. The front-page reel already uses the readable label. The timeline link's only name is its image alt "timeline", the one unnamed link in `board/front-measure.json`.
- **Why it matters**: the charts carry the results, and a file key is not a description of any of them.
- **Proposed change**: use `alt="{{ chart_titles.get(name, ('', name))[1] }}"` now, and later let each chart function return the headline it draws inside the image (for example "1 of 61 features survive at one standard error") for use as the alt. Give the timeline link `aria-label="Timeline of changes, 15 June to 24 September"`.
- **Effort**: S
- **Command**: clarify

**BB-10. Handle a dropped server in Save and Run**

- **Surface and place**: board, every panel page. `card.html` lines 806 to 851, 863 to 880 and 1294 to 1318.
- **Severity**: P2
- **Evidence**: `saveOne`, the run submit and `poll()` call `await res.json()` with no `try` and no check of `res.ok`. The project CLAUDE.md says the server has no reloader and is killed and restarted after any code change. If it is down, Save stays disabled with "saving 5..." for good, Run stays disabled, and a poll that fails mid-run leaves "running for N seconds" on screen with no failure state.
- **Why it matters**: the page then says a job is running or saving when nothing is, which is the kind of false state the board was rebuilt to stop.
- **Proposed change**: wrap each in `try`/`catch`, check `res.ok` before `res.json()`, re-enable the button in `finally`, and set the pill to "failed" with "the control centre is not answering; restart it with 05-research/scripts/control_centre.sh" as the message.
- **Effort**: S
- **Command**: harden

**BB-11. Give Stop a state and an answer**

- **Surface and place**: board, Output block on A1, B1, B2, C1 and C2. `card.html` line 599 and line 1336.
- **Severity**: P2
- **Evidence**: Stop is always enabled, idle or not, is styled inline at 11.5 px with 4 px padding (about 21 px tall, `board/B1-top-02.png`), and its handler posts `/stop` and ignores the reply, so pressing it changes nothing on screen.
- **Why it matters**: the one control that halts a running job gives no sign that it worked.
- **Proposed change**: move the inline style to `.btn.stop{font-size:12px; padding:6px 14px}`, disable Stop while the pill is idle, and on click set the pill to "stopping" and let the next poll report the exit.
- **Effort**: S
- **Command**: harden

**BB-12. Warn before a reload discards edits**

- **Surface and place**: board, every panel with settings. `card.html` line 535 (the job form's Reset calls `location.reload()`), lines 1210 to 1231 (Reset defaults and Load best reload after posting).
- **Severity**: P2
- **Evidence**: the page tracks unsaved blocks (`markDirty`, line 795) but has no `beforeunload` guard, and three buttons reload the whole panel. Reset on a job form reloads the page to clear one job's boxes. Reset defaults posts at once with no confirmation.
- **Why it matters**: unsaved edits in any of A1's five settings blocks vanish without a word when one of these is pressed.
- **Proposed change**: add `window.addEventListener('beforeunload', e => { if (document.querySelector('.cfgform.dirty')) e.preventDefault(); })`; make the job-form Reset call `form.reset()` instead of reloading; ask "Put the defaults back for this block?" before Reset defaults posts.
- **Effort**: S
- **Command**: harden

**BB-13. Cache the chart drawings**

- **Surface and place**: board, every page. `03-inputs/control_centre.py` lines 527 to 546; `03-inputs/control_charts.py` lines 4009 to 4050; `card.html` lines 848 to 850.
- **Severity**: P2
- **Evidence**: each `/chart/<name>.png` is redrawn by matplotlib on every request, one at a time under `_DRAW_LOCK`, and sent with `Cache-Control: no-store`; five charts measured 0.12 to 0.53 s each on repeat requests with identical bytes. The front page's 13 eager images therefore queue: `board/front-measure.json` shows DOMContentLoaded at 788 ms and the load event at 4,268 ms. After Save, the script resets `src` on every `.chart img`, which queues 15 to 21 redraws on C1 and C2.
- **Why it matters**: the front page takes four seconds to finish, and a Save stalls every chart on the panel on an 8 GB machine already in swap.
- **Proposed change**: memoise the PNG bytes in `draw()` on the key (name, scale, modification times of the records and `bench/config.json` it reads), send an `ETag` from that key with `Cache-Control: no-cache` so the browser gets a 304, and after Save refresh only the charts registered as reading the saved section.
- **Effort**: M
- **Command**: optimize

**BB-14. Stop the plotly bundle blocking every panel**

- **Surface and place**: board, all six panel pages. `base.html` line 9; `03-inputs/control_interactive.py` lines 134, 320 and 423; `03-inputs/control_merged.py` lines 190, 195 and 286.
- **Severity**: P2
- **Evidence**: `plotly.min.js` is 4,844,191 bytes, loaded as a blocking script in `<head>`, served uncompressed with `Cache-Control: no-cache`, and parsed on every panel load for four to six scatter figures. The figures use `Scattergl`, which rendered "WebGL is not supported by your browser" in the headless capture `board/C1-overview.png`; that message is a headless artefact on this Mac, but it shows the figures depend on a WebGL context for a few hundred points.
- **Why it matters**: the panel cannot paint until five megabytes of script are parsed, for figures near the foot of the page.
- **Proposed change**: load the library with `defer` and emit each figure's `Plotly.newPlot` inside a `DOMContentLoaded` handler (which removes the reason the comment gives for loading it in the head), switch to the `plotly-cartesian` partial bundle, and use `go.Scatter` wherever a trace has fewer than 5,000 points.
- **Effort**: M
- **Command**: optimize

**BB-15. Lighten the C1 page**

- **Surface and place**: board, C1. `card.html` lines 616 to 672 and 1320 to 1333; A1's server render.
- **Severity**: P2
- **Evidence**: C1 is 1,303,989 bytes and 14,105 DOM nodes, with first byte after 1.35 to 2.02 s and DOMContentLoaded at 3,569 ms. The Scoreboard section alone is 670,677 bytes for 575 rows, and the inline figure data about 460 KB. After each run `refreshReport()` fetches the whole 1.3 MB page to replace three blocks. Each keystroke in a filter box reads `textContent` of every row with no debounce. A1 has the slowest first byte of all, 1.94 to 3.44 s over four samples.
- **Why it matters**: the panel the operator returns to after every run is the slowest to open and to refresh.
- **Proposed change**: render the first 100 scoreboard rows and a "show all 574" control, or send the rows as JSON and build them on demand; add `content-visibility:auto` to `.bigtable tbody`; debounce the filter by 150 ms; give the report blocks their own route, `/card/C1/report`, for `refreshReport()`; profile A1's render to find what reads 2 seconds of disk.
- **Effort**: M
- **Command**: optimize

**BB-16. Drop the per-cell titles on the panel table**

- **Surface and place**: board and export, A2 Columns table. `card.html` line 425.
- **Severity**: P2
- **Evidence**: `B-board/A2.html` carries 810 `<td title="...">` attributes holding 9 distinct strings, 130,680 bytes, 43 per cent of the 303,820-byte page. The comment at card.html lines 319 to 325 records removing exactly this from the other table templates on 22 September, because it "fought the table it explained".
- **Why it matters**: a tooltip pops under every cell the pointer crosses on the panel's main table, and the fix recorded for it did not reach this copy.
- **Proposed change**: change line 425 to `<td>{{ cell }}</td>`; the heading already carries the gloss at line 419.
- **Effort**: S
- **Command**: distill

**BB-17. Put the charts on the lane palette**

- **Surface and place**: board and export, all charts and the token layer. `control_charts.py` lines 41 to 44; `control.css` lines 13 to 34, 737 to 741, 707 to 710, 910 to 915, 960 and 963; `DESIGN.md` front matter lines 12 to 18 and the One Meaning Rule.
- **Severity**: P2
- **Evidence**: the chart module declares the cheat-sheet colours (`#0d5f8a`, `#6b3fa0`, `#0e7a5f`, `#a8560c`, `#1c4f8f`, `#a01c1c`) and none of the six lane colours, zero occurrences of each, while DESIGN.md says "The chart module declares the same hexadecimals the stylesheet does". DESIGN.md still lists the lane shades `#1f7ac4`, `#27a86e` and `#ea7a2c` that the stylesheet replaced on 22 September for contrast, and the detector flags the live `#1a6cb0` and `#1c7f52` as outside DESIGN.md. The lane tokens are declared in two `:root` blocks with different values. 78 hex literals sit outside `:root` (25 distinct); `.mh-meta .cash` hard-codes `#14304d`, `#0e7a5f` and `#a01c1c` where `--tuv`, `--ok` and `--bad` exist; `var(--warn, #9a6100)` names a fallback that differs from `--warn` itself.
- **Why it matters**: a lane cannot be followed from a panel into its drawings, and the design document now describes colours that fail AA.
- **Proposed change**: give `control_charts.py` a `LANE = {"A1": "#0b4f8a", ...}` table copied from the stylesheet's final values and use it wherever a chart stands for a panel; update DESIGN.md's front matter to the 22 September shades (or the ones in BB-03); merge the two `:root` lane blocks into one; replace the hard-coded cash colours with `var(--tuv)`, `var(--ok)` and `var(--bad)`; drop the `#9a6100` fallbacks.
- **Effort**: M
- **Command**: colorize

**BB-18. Remove the export's dead controls**

- **Surface and place**: export, A2, C1 and C2 panels, the "Other runs" disclosures, and every Explore block. `03-inputs/control_export.py` lines 57 to 104.
- **Severity**: P2
- **Evidence**: the export carries three scripts totalling about 6 KB and none binds a filter or a sort, yet it keeps four "Filter these rows" boxes, the "Beat a constant guess" checkbox, and sortable headings with `cursor:pointer` and a tooltip saying "Combine with a heading click to sort". It keeps six `plotly-graph-div` boxes 330 px tall with no library and no `newPlot`, shown as a blank block under Explore in `B-board/e-B1-overview.png`. Both "Other runs on this panel" disclosures (counts 1 and 5) open on nothing, and the lead job block survives as a title and a sentence with no tool (B1's "Univariate screen" in the same capture), which the builder's own comment calls a stub. Six hidden lightboxes with `<img src="">` remain although every Expand button was removed.
- **Why it matters**: the file is the board for anyone without the server, and each of these reads as a broken page.
- **Proposed change**: in `strip_controls`, remove `.seccontrols`, the `details.otherruns` block, `class="block leadjob"` job blocks (the first regex matches only `class="block"`), the `#lightbox` div and every `.interactive-block`, or keep the interactive blocks and inline the partial plotly bundle; drop `sortable` from table classes, or ship the sort and filter script, which needs no server.
- **Effort**: S
- **Command**: harden

**BB-19. Raise the masthead money line**

- **Surface and place**: board and export, every page. `control.css` lines 85, 94 and 144 to 149.
- **Severity**: P2
- **Evidence**: the account line is 9 px (`.mh-meta`, lines 94 and 144) and the paper badge 9.5 px on panels and 8 px on the front page (line 85), below DESIGN.md's own Micro floor of 9 px; the detector flags 8 px as off the type ramp. The front page has 60 of 79 text elements under 12 px.
- **Why it matters**: the dollar figure and the paper-only badge are the two things the repository says a reader must see first, and they are the smallest type on the board.
- **Proposed change**: `.mh-meta{font-size:11px}`, `.mh-meta .badge{font-size:10.5px}`, and on the front page `.sheet.front .mh-meta{font-size:10.5px}` and `.sheet.front .mh-meta .badge{font-size:10px}`. The rest of the dense type is intended and should stay.
- **Effort**: S
- **Command**: typeset

**BB-20. Give panel pages landmarks and an outline**

- **Surface and place**: board and export, every page. `base.html` lines 33 and 89; `card.html` lines 25, 31, 72 and 114; `index.html` line 52.
- **Severity**: P2. WCAG 1.3.1 Info and Relationships and 2.4.1 Bypass Blocks, as best practice.
- **Evidence**: no page has `<main>` or a skip link. Every panel runs h1 then h3 with no h2 (detector `skipped-heading` on all six), and C1 runs h3 to h5 for the "RF" settings block. The front page's visible chip row is a `div` with an `aria-label` and no role, which assistive technology ignores, while its `<nav class="flowbar">` is hidden. "Trading mode" is a `<label>` bound to no control (card.html line 114).
- **Why it matters**: a screen-reader user moves by headings and landmarks, and on a 7,246-pixel page there are neither in usable form.
- **Proposed change**: wrap the body block in `<main id="main">` with a skip link to it; make block titles h2, cluster titles h3 and model blocks h4; make the front row `<nav aria-label="The six panels, in order">`; change the Trading mode label to a `<span class="lab">`.
- **Effort**: S
- **Command**: harden

**BB-21. Say stale in words beside the dot**

- **Surface and place**: board and export, front page card feet. `index.html` line 84; `control.css` lines 248 to 250.
- **Severity**: P2. WCAG 1.4.1 Use of Color, A, arguable because the date is printed beside the dot.
- **Evidence**: `board/front-top-01.png` shows orange dots on A1 (16 Aug) and A2 (08 Sep) and green on the rest; the dot has no text, title or label, so "fresh", "stale" and "old" exist only as colour.
- **Why it matters**: the judgement that a panel's record is out of date is carried by hue alone.
- **Proposed change**: add the word after the date, "16 Aug 2026, stale", or `title` and `aria-label` on the dot with the rule that set it, for example "stale, older than 14 days".
- **Effort**: S
- **Command**: clarify

**BB-22. Remove the em dash the filter writes**

- **Surface and place**: board, C1 Scoreboard, when "Beat a constant guess" is ticked. `card.html` line 1186.
- **Severity**: P2, because the operator's writing rules are standing product rules.
- **Evidence**: the label is rewritten to the template string `` `Beat a constant guess \u2014 ${kept} of ${total}` ``. The served pages have no em dash in text or tooltips; this is the one place the board writes one.
- **Why it matters**: it breaks a hard rule the operator applies to every visible word.
- **Proposed change**: `` `Beat a constant guess, ${kept} of ${total} kept` ``.
- **Effort**: S
- **Command**: clarify

**BB-23. Keep the front-page tags whole at 1280**

- **Surface and place**: board and export, front page at 1280 by 800. `control.css` lines 217 to 221.
- **Severity**: P3
- **Evidence**: `board/front1280-top-01.png` shows A2's tag cut to "FEATURES, MACD, AVERAGES, FIBONACCI, CONFLUEN" and C1's pressed against its title, because the tag is `white-space:nowrap` inside a card with `overflow:hidden`.
- **Why it matters**: the tag lists what the panel sets, and its last word is lost.
- **Proposed change**: `.card > h2 .tag{white-space:normal; text-align:right; line-height:1.2}`, or shorten the registry tags to three items.
- **Effort**: S
- **Command**: layout

**BB-24. Define the soft text token**

- **Surface and place**: board, C1 "The last run" detail line. `control.css` line 872.
- **Severity**: P3
- **Evidence**: `.resultdetail{color:var(--soft)}` names a token that is never declared, so the declaration is invalid and the line inherits body ink rather than the soft grey DESIGN.md gives the verdict detail.
- **Why it matters**: the verdict and its detail are meant to read at two weights and read at one.
- **Proposed change**: `color:var(--ink-soft)`.
- **Effort**: S
- **Command**: polish

**BB-25. Honour reduced motion**

- **Surface and place**: board, front cards and every panel. `control.css` lines 201 to 202 and the `transition` rules at 412, 587 and 596; `card.html` lines 1095, 1110 and 1331.
- **Severity**: P3. WCAG 2.3.3 Animation from Interactions, AAA.
- **Evidence**: no `prefers-reduced-motion` rule exists; cards lift on hover and three `scrollIntoView({behavior:'smooth'})` calls ignore the setting.
- **Why it matters**: the motion is small, but a reader who has asked the system for none still gets it.
- **Proposed change**: `@media (prefers-reduced-motion: reduce){ a.card:hover{transform:none} *{transition:none !important} }` and pass `behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'`.
- **Effort**: S
- **Command**: animate

**BB-26. Shrink the export file**

- **Surface and place**: export. `control_export.py` lines 52 to 55 and 187 onward.
- **Severity**: P3
- **Evidence**: 19,685,805 bytes, of which 290 inline PNG data URIs are 15,472,720; 277 images carry `loading="lazy"`, which does nothing for data already in the document; 18,835 DOM nodes (`export/e-measure.json`).
- **Why it matters**: a file near 20 MB is at or over many mail attachment limits, and it is sent as the board for people without the server.
- **Proposed change**: quantise the chart PNGs to 256 colours before encoding (flat-colour charts usually lose over half their size), drop `loading="lazy"` from inlined images, and remove the duplicate reel copies the front grid carries.
- **Effort**: S
- **Command**: optimize

**BB-27. Stop stretching the timeline image**

- **Surface and place**: board and export, front page top band. `control.css` lines 78 to 79.
- **Severity**: P3
- **Evidence**: `.topband .timeline img{object-fit:fill}` stretches the drawing to the band; at 720 px wide (`B-board/front-zoom200-top-01.png`) the milestone labels are visibly condensed.
- **Why it matters**: the band exists so the milestone labels can be read.
- **Proposed change**: `object-fit:contain; object-position:left center`, and draw the chart at the band's aspect in `control_charts.timeline()`.
- **Effort**: S
- **Command**: polish

## Phone visitor

A phone visitor to the board gets the desktop page shrunk to fit, because no template sets a viewport meta tag. At 390 px wide the browser lays the front page out at 980 px and scales it to 40 per cent (`B-board/phone-front-top-01.png`, `phone-front-measure.json`), so 9 px text arrives at about 3.6 px, the lanes fall to two columns with C1 and C2 stacked on the left, and every control is a pinch-zoom target. That matches the board's desktop-only intent; the public friends page is the phone surface.

## What works

These should be kept through any fix.

1. One `:focus-visible` rule for every focusable element, in the open panel's lane colour with a 2 px offset (control.css lines 894 to 900), and no `outline:none` anywhere.
2. Every settings input and select has a `<label for>`, and `lang`, `title` and table headings are present on every page.
3. The lane inheritance through `--panel`, set once on `.sheet` and read by 268 `var()` uses, so a panel is one hue from its masthead to its focus ring.
4. The script binds Save and Run first and wraps each decorative note in its own `try`, so a failing note can no longer silence the controls (card.html lines 766 to 776 and 1057 to 1061).
5. Lazy loading on 206 of 219 front-page images and on every foot chart, and in-page sort and filter with no round trip.
6. The unsaved-block marker (`.block:has(.cfgform.dirty)`) and the save state that stays on screen with the sections and time it wrote.
7. The export's `disabled` settings fields drawn at full contrast (`control_export.py` EXTRA_CSS), so a frozen value is still readable.
8. The board's density itself, which PRODUCT.md and DESIGN.md intend and which the detector's volume should not be read as arguing against.

## False positives

1. `side-tab` (6 to 15 a page) and `border-accent-on-rounded` (5 to 20 a page). The coloured left rule on `.section`, `.cluster`, `.standing`, `.howto` and `.runreport` is the documented lane device (control.css lines 631 to 639, DESIGN.md Elevation), carried from the printed cheat sheet, and not an ornament.
2. `line-length` (175 on A2, 36 on C1). The long lines are cells of wide reference tables read along a row, not prose.
3. `tiny-text` and `undersized-ui-text`, most instances. Table cells at 11 to 12 px and field labels at 11.5 px are the intended instrument density on the DESIGN.md type ramp; only the 8 to 9.5 px masthead money line and badge are reported, in BB-19.
4. `low-contrast` of `#6b7885` on `#eef1f4` at 4.0 to 1, five on each panel page. These are the five flow-bar arrows, marked `aria-hidden` and decorative, which WCAG 1.4.3 exempts. The detector missed the real failures in BB-03.
5. `all-caps-body` on 38 to 47 characters. These are short uppercase table headings and card tags, labels rather than body text.
6. `cramped-padding` on `.bigtable`. The table meets its own scroll border by design; the 3 px row padding in the run report is dense but legible.
7. `flat-type-hierarchy`. Accurate as a measurement, since the h1 is 12.5 px against 12 px body, but the one-line masthead is an operator instruction of 16 September and DESIGN.md's Display role.
8. `gray-on-color` of `#e8eef4` on `#283b50`, six in the export. That is the hidden lightbox caption on the navy veil at 9.81 to 1.
9. `dark-glow`, one in the export. The page is light; the navy shadow is the chip hover shadow at 25 per cent.
10. `broken-image` `<img src="">`, six in the export and one in the templates. It is the hidden lightbox image waiting for a source; in the export it is dead markup, covered in BB-18.
11. `design-system-color` on the templates folder. The templates were scanned without their stylesheet, whose path is a Jinja expression the detector could not resolve, so every colour read as black.
12. `aphoristic-cadence`, one in the export. The flagged cell is A1's Screening table, "Too little and there is nothing to catch; too much and the stop is hit by noise", which is a balanced construction the operator's rules discourage; it is a copy matter for the copy audit, not a technical defect.
13. The measure files' unnamed ghost buttons (1 on B1, 5 on C1) and empty h3 headings. They are the job forms inside the closed "Other runs" disclosure, whose text a closed `details` does not render; the markup names them.
14. The C1 detector scan failed twice, once on a 30 s navigation timeout and once on a dropped browser connection, and succeeded on the third attempt. With free memory near 140 MB and 2.9 GB of swap in use at the time, this is read as machine pressure rather than a page defect.

## Known defects shown

The brief's known label defects were not re-tested; this is where each appears on the board.

1. Take-profit and Stop never change the label. A1, the Choose Label block beside the Screening table, fields "Take-profit, ATR" and "Stop, ATR", and the worked example sentence written into the block's note (card.html line 133).
2. The eleven A2 engine settings only draw charts. A2, the four blocks beside Indicator engines, Choose MACD, Choose Averages, Choose Fibonacci and Choose Confluence.
3. No model ticked fits three models, not six. C1, Choose Model, the "Models" list; with nothing ticked the script shows all six settings blocks under Choose Settings (card.html line 891), which reinforces the wrong count.
4. Fold pass rate counts folds with U2 under 1, not money. C1, the Scores table row "Pass rate, Share of half-year folds where the strategy made money, At least 0.6", and the This Run row "How it scored".
5. Embargo 0 means 2 days, not the horizon. B2, Choose Blind Period, field "Embargo bars".
6. Class weight defaults to balanced though it scored worse. C1, Choose Model, field "Class weight", and the This Run settings line "Models RF, class weight balanced".
7. Tooltips quote the 1-hour base rate 0.313 on the 4-hour frame. A1, Choose Label, the hover note on "Take-profit, ATR".

## Counts

27 findings, 9 at P1, 13 at P2, 5 at P3, none at P0. Detector output for every target is saved as `B-board/detect-<view>.json`.
