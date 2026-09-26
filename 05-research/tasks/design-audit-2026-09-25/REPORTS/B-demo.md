# B-demo audit

Assessment B, the detector and technical audit of the public friends page, `https://seamusrobertmurphy.github.io/swing-trader/`, on phone (390 by 844) and desktop (1440 by 900), run on 25 September 2026 against the page served with Last-Modified 25 Sep 2026 23:28 GMT. The page was republished at 00:27 GMT on 26 September while the audit ran; that build (24,440,822 bytes decoded, `B-demo/live-now.html`) was checked again and every finding below still held on it, with the same 218 reel images, 10 `data-src` copies, Plotly in the head, grid rules, button rules, table greys and "What to do" text. Nothing in the repository was changed and no button that posts was pressed. New evidence sits in `audit/B-demo/`.

## Audit health

Scores follow the impeccable audit playbook, 0 to 4 per dimension.

| # | Dimension | Score | Key finding |
|---|-----------|-------|-------------|
| 1 | Accessibility | 2 | Warm lane colours and table greys fail contrast (16 texts on the front page, 47 on desktop C1), and the run status is never announced |
| 2 | Performance | 1 | 15.0 MB transferred, 25.8 MB decoded; at 1.6 Mbps the Run button is visible but dead for 65 s |
| 3 | Responsive design | 2 | One column and 44 px inputs work, but every interactive figure is clipped at 334 of 700 px and C1 is 343,870 px tall |
| 4 | Theming | 2 | The warm theme undoes the board's contrast fix, and the one amber Run button renders grey |
| 5 | Implementation integrity | 1 | The page is the board with parts cut out by regular expressions, and the cuts leave dead controls and instructions |
| **Total** | | **8/20** | **Poor** |

## Integrity verdict

Fail. The public page does not express its own system. It is the operator's board rendered by Flask and then reduced by `strip_code`, `drop_blocks` and `trim_settings` in `03-inputs/demo_site.py`, with a dark-theme layer (`DARK_CSS`) repurposed for a light theme and a light layer (`LIGHT_CSS`) laid over both with 166 `!important` flags. Each subtraction left something behind that still claims to work. The reel step buttons were removed (0 `reelbtn` in the page) while 218 reel images, 10.3 MB, stayed. The table sort, filter and "Beat a constant guess" script was cut by `panel_chunk` (line 63) while 4 filter boxes, 1 checkbox and a pointer cursor on 15 sortable tables stayed. The "What to do" steps still send friends to "Run the test", "Screen variables" and "Compare regimes", which the page no longer has. The approved amber Run button lost to a more specific grey rule. The detector's own findings (undersized text, nested cards, skipped headings, uppercase tags) were all confirmed in screenshots and source, and are minor beside these.

## Executive summary

The page scored 8 of 20, in the Poor band, with 28 verified findings, 0 at P0, 12 at P1, 13 at P2 and 3 at P3. The most severe were these five.

1. The page was usable only after the whole 25.8 MB file had parsed. At 1.6 Mbps with a phone-speed CPU the first paint came at 13.7 s, and the Run and preset buttons were visible but inert until 78.9 s.
2. Of the 25.8 MB, 9.9 MB were front-page images no visitor can ever see, 2.8 MB were second copies of figures, and 4.8 MB was the full Plotly library parsed in the head before anything drew.
3. Every interactive figure on a phone was drawn 700 px wide and clipped to 334 px, and after the "See results" link the C2 charts and their notes were cut off mid-sentence.
4. The warm theme's lane colours (2.58 to 3.80 to 1) and header grey (3.56 to 1) failed WCAG 1.4.3 across every view.
5. The Run status line had no live region, so a screen-reader user heard nothing between pressing Run Model and the result.

The recommended order is to stop the dead weight first (hidden images, figure copies, Plotly bundle), then bind the buttons early and fix the three overflow bugs, then the contrast tokens and the stale instructions.

## Measured evidence

Table 1 summarises the capture measure files, `demo-phone/*-measure.json` and `demo-desk/*-measure.json`, section `top`. Sideways counts in parentheses are elements clipped inside the page rather than page scroll. An asterisk marks contrast failures that are all the "WebGL is not supported" notice, an artefact of the capture flag `--disable-gpu`.

| View | Width | Page height px | Page scrolls sideways | Text under 12 px | Contrast failures | Controls under 44 px |
|---|---|---|---|---|---|---|
| front | 390 | 2,761 | no | 44 of 90 | 16 | 8 of 19 |
| A1 | 390 | 14,753 | no (161) | 37 of 226 | 0 | 24 of 49 |
| A2 | 390 | 56,393 | no (93) | 18 of 1,109 | 0 | 19 of 29 |
| B1 | 390 | 6,228 | no (538) | 32 of 140 | 0 | 62 of 72 |
| B2 | 390 | 6,690 | no (57) | 32 of 124 | 2* | 15 of 33 |
| C1 | 390 | 343,870 | no (258) | 51 of 10,603 | 4* | 41 of 68 |
| C2 | 390 | 79,158 | no (355) | 37 of 2,097 | 4* | 30 of 33 |
| front | 1440 | 964 | no | 67 of 90 | 16 | 13 of 19 |
| A1 | 1440 | 5,208 | no | 195 of 247 | 13 | 54 of 55 |
| A2 | 1440 | 3,578 | no (731) | 266 of 1,135 | 18 | 32 of 35 |
| B1 | 1440 | 3,025 | no | 76 of 155 | 7 | 78 of 78 |
| B2 | 1440 | 2,957 | no | 88 of 140 | 8 | 39 of 39 |
| C1 | 1440 | 6,815 | no (1,242) | 122 of 10,658 | 47 | 73 of 74 |
| C2 | 1440 | 5,961 | yes, 1,442 px | 70 of 2,146 | 41 | 39 of 39 |

The phone contrast counts undercount, because the measure walks text nodes and the phone table labels are `::before` text. Every view shared the same outline and rules. Headings ran H1 then H3 with no H2, and C1 had H3 then H5 "RF". There was no `main` landmark and no footer, one `nav` and one `header`. There were 12 focus rules and a visible 2 px ring, no reduced-motion rule, and a dark-mode rule that came only from Plotly's bundled map CSS. All 296 images carried `alt` (6 empty), and 277 were marked `loading="lazy"`, which saved nothing because 290 of them were data URIs already inside the HTML. The DOM held 22,683 nodes in every view, since all seven views are one document.

The desktop C2 sideways scroll came from the Runs table. `layout.json` and `shot-desk-C2-runs.png` located it as `#demo-runs > .demo-scroll > table`, 608 px wide, pushing the page to 1,500 px on the 17:10 probe (1,442 px in the capture), with the Blind score column cut at "U2 1.041, AU".

Table 2 breaks down the 25,767,208 decoded bytes of `B-demo/live.html`.

| Part | Bytes | Share | Seen by a visitor |
|---|---|---|---|
| Front-page reel images, 218 | 10,326,452 | 40.1% | 12 images, 412,280 bytes |
| Panel images, 77 | 5,125,454 | 19.9% | yes, 62 of them (2,470,704 bytes) repeat reel images |
| `figure data-src` copies, 10 | 2,818,632 | 10.9% | never |
| Plotly 3.6.0, full bundle, in `<head>` | 4,844,144 | 18.8% | needed for 13 figures |
| Interactive figure data | about 1,240,000 | 4.8% | yes |
| 17 tables | 1,096,438 | 4.3% | yes; scoreboard 669,193 bytes |

Only 99 of the 304 embedded images were distinct. The images made up 13.3 MB of the 15.0 MB gzip transfer, because base64 compresses poorly. The file's order decided what a visitor saw first. The head ended at 19.1 per cent of the file, the front page started at 19.2 per cent, panel A1 at 59.5 per cent, C1 at 87.4 per cent, C2 at 94.5 per cent, and the scripts that bind the buttons and choose the view at 99.9 per cent.

Table 3 gives load times measured by `B-demo/probe.mjs` in headless Chrome at 390 by 844, cache off, four times CPU slowdown, opening `#panel-C2`, the address the Run block links to.

| Network assumed | First paint | Buttons visible but inert | C2 shown | Load event |
|---|---|---|---|---|
| 1.6 Mbps, 150 ms round trip | 13.7 s | 13.7 to 78.9 s | 79.9 s | 79.7 s |
| 9 Mbps, 60 ms round trip | 8.1 s | 8.1 to 22.4 s | 22.9 s | 22.8 s |

At 0.4 Mbps, a weak 3G signal, the 15.0 MB transfer alone would take about 300 s. Records are `B-demo/slow-1600.json` and `B-demo/slow-9000.json`.

## Findings

### P1 findings

**1. Bind the Run and preset buttons before the file finishes**

- **Surface and place**: public phone and desktop, every view. `demo_site.py` build lines 1133 to 1145 put `ce.SCRIPT` and `DEMO_SCRIPT` after `#panels`, at 99.9 per cent of the file, and the view is chosen by `fromHash()` in `control_export.py` SCRIPT (line 277 onward).
- **Severity**: P1
- **Evidence**: `slow-1600.json`, Run Model visible from 13.7 s with no handler until 78.9 s; a link to `#panel-C2` showed the front grid for 65 s and then jumped. At 9 Mbps the dead window was 14.3 s (`slow-9000.json`).
- **Why it matters**: a friend who taps Run Model or a preset during that window gets no response and no sign the page is still loading, and reasonably concludes it is broken.
- **Proposed change**: put a small inline script in `<head>` that reads `location.hash` and sets `data-view` on `<html>`, with CSS that shows only that view from first paint; bind `.demo-go`, `.demo-preset` and `.demo-name` by event delegation on `document` in a script placed straight after the front-page shell, not after `#panels`; render the Run button `disabled` with the label "Loading" and enable it from that script.
- **Effort**: M
- **Command**: harden

**2. Drop the reel images nobody can open**

- **Surface and place**: public phone and desktop, front page. `strip_code` (`demo_site.py` line 118) removes every button including the reel's previous and next (`index.html` lines 74 and 76), but the template still emits every image of each panel's reel (`index.html` lines 69 to 71).
- **Severity**: P1
- **Evidence**: 218 reel images, 10,326,452 bytes, of which 12 (412,280 bytes) are the `.on` images shown; 0 `reelbtn` in the page. The detector's text-occlusion finding ("3/10" covered by `div.slotcap`, 12 times) is the orphaned reel counter.
- **Why it matters**: 9.9 MB, 38 per cent of the file, is downloaded by every friend and can never be seen.
- **Proposed change**: in `build()`, after `strip_code(shell)`, delete every `img.thumb` without the `on` class and the `.reelbar` inside `.card .pair .slot`, leaving one image per slot.
- **Effort**: S
- **Command**: optimize

**3. Ship a smaller Plotly, deferred, outside the head**

- **Surface and place**: public phone and desktop, every view. `demo_site.py` line 1137 (`<script>__PLOTLY__</script></head>`) and line 1163 inline `03-inputs/control_static/plotly.min.js`.
- **Severity**: P1
- **Evidence**: plotly.js v3.6.0 full bundle, 4,844,144 bytes (1,463,373 gzip), parsed before first paint. At 9 Mbps the head's 1.5 MB of compressed bytes arrives in under 2 s, yet first paint came at 8.1 s, so most of the wait was parsing the library at phone CPU speed. The page uses only `scatter` (87 traces), `scattergl` (59), `bar` (2) and `histogram` (1). The cartesian bundle, `plotly.js-cartesian-dist-min@3.6.0/plotly-cartesian.min.js`, is 1,420,800 bytes (471,516 gzip), fetched from jsDelivr on 25 September.
- **Why it matters**: a phone cannot draw a single word until 4.8 MB of chart code has been parsed, and most views open with no interactive figure on screen.
- **Proposed change**: replace `scattergl` with `scatter` (finding 20), publish `plotly-cartesian.min.js` beside `index.html` on gh-pages or load it from `cdn.jsdelivr.net/npm/plotly.js-cartesian-dist-min@3.6.0`, with `defer`, and call each figure's `newPlot` from a function run when its panel opens.
- **Effort**: M
- **Command**: optimize

**4. Serve images as files and panels on demand**

- **Surface and place**: public phone and desktop, every view. `ce.inline_charts` (`control_export.py` line 187) called at `demo_site.py` line 1161; `figure class="chart" data-src` from `card.html` lines 347, 366 and 727.
- **Severity**: P1
- **Evidence**: Table 2. 304 data URIs, 99 distinct; 10 `figure data-src` attributes repeat 2,818,632 bytes of images whose expand script is not on the page; 62 panel images repeat reel images. Transfer 15,041,874 bytes (`demo-phone/front-measure.json`).
- **Why it matters**: a friend on mobile data pays 15 MB for a front page that shows 12 small charts, and `loading="lazy"` cannot help while the bytes sit inside the HTML.
- **Proposed change**: in `build()`, write each distinct PNG once to gh-pages as `img/<sha1>.png`, point `src` at it with `loading="lazy"`, `width` and `height`, and strip `data-src` from `figure.chart`. Then move each panel's HTML, its figure data and its large tables into `panels/<key>.html` and `panels/<key>.json`, fetched on `hashchange`, as `data/index.json` already is. From the byte counts, a first front-page view would then transfer roughly 0.7 MB instead of 15.0 MB; this is an estimate, not a measurement.
- **Effort**: L
- **Command**: optimize

**5. Fit the interactive figures to the phone**

- **Surface and place**: public phone, A1, A2, B1, B2, C1 and C2. `fitFigures` in `DEMO_SCRIPT`, `demo_site.py` lines 375 to 383.
- **Severity**: P1
- **Evidence**: `B-demo/shot-phone-C1-figure.png`, the calibration and tuning figures cut at the right with the x-axis title "stated" and "RMSE" half off screen; `layout.json` phone views, `svg-container` 700 px wide inside a 334 px box; measure overflow counts 57 to 538 per view. The check `Math.abs(el.clientWidth - w) > 4` compares two widths that CSS has already clamped to 334 px (`.plotly-graph-div{max-width:100%}`, line 934), so `Plotly.relayout` never runs.
- **Why it matters**: the right half of every chart, with its axis title and its highest values, is unreachable because `overflow-x:hidden` stops sideways scroll; WCAG 1.4.10 Reflow.
- **Proposed change**: compare `el._fullLayout.width` with the parent's width, relayout with `{autosize: true, width: null}`, pass `{responsive: true}` in each figure's config, and rerun on `resize` and `orientationchange` as well as `load` and `hashchange`.
- **Effort**: S
- **Command**: adapt

**6. Stop the C2 charts widening after "See results"**

- **Surface and place**: public phone, C2 reached by a link from C1, B2 or the front page. `DEMO_CSS` lines 345 and 349 (`.demo-charts` grid, `1fr 1fr`, then `1fr` under 900 px).
- **Severity**: P1
- **Evidence**: `B-demo/shot-phone-C2-after-hashchange.png`, the "Runs against guessing" chart 700 px wide and its note cut at "the RMSE of always predicting the average outcome. Below 1 bea"; `shots.json` `c2_chart_w` 700. The chart is drawn while C2 is hidden, at Plotly's default 700 px, and a `1fr` track grows to that minimum content width, so the resize at line 586 measures the widened track and keeps 700.
- **Why it matters**: this is the path every friend takes after pressing Run Model, and the page loses the end of the sentence that explains their score; WCAG 1.4.10.
- **Proposed change**: `grid-template-columns: minmax(0,1fr) minmax(0,1fr)` at line 345 and `minmax(0,1fr)` at line 349, so the resize handler at lines 581 to 589 then sizes the charts to the card.
- **Effort**: S
- **Command**: layout

**7. Cap the phone tables instead of 575 cards**

- **Surface and place**: public phone, C1 Scoreboard and Three-way, A2 Columns, C2 Assessment and Money. `DARK_CSS` phone rules, `demo_site.py` line 955, `.demo-scroll, .bigtable { max-height:none !important; overflow:visible !important; }`.
- **Severity**: P1
- **Evidence**: `layout.json`, C1 page 343,870 px of which the Scoreboard block is 311,977 px (575 rows as cards, about 370 phone screens); Three-way 21,939 px; A2 Columns 49,914 of 56,393 px; C2 Assessment 43,674 px and Money 26,634 px. The filter box that would narrow them does nothing (finding 14).
- **Why it matters**: the Figures block and Evidence log at the foot of C1 are effectively unreachable on a phone, and scrolling past a table takes minutes.
- **Proposed change**: under 760 px, show the first 10 rows of any table over 20 rows and a "Show all 575 rows" button that reveals the rest, or keep `.bigtable` at `max-height:70vh; overflow:auto` as on desktop.
- **Effort**: S
- **Command**: adapt

**8. Darken the lane colours used as text**

- **Surface and place**: public phone and desktop, front cards, flow chips and panel headings. `THEMES["warm"]["lanes"]`, `demo_site.py` line 760, set as `--c-a1` to `--c-c2` by `LIGHT_CSS` line 973 and used as text colour by `DARK_CSS` lines 862 to 873. It overrides the board's fix of 22 September at `control.css` lines 910 to 915.
- **Severity**: P1
- **Evidence**: `demo-phone/front-measure.json` and `demo-desk/front-measure.json`, 16 failures each, `#c99a2e` 2.58, `#6f9a7c` 3.19, `#5f8fa8` 3.51, `#b8732a` 3.80 to 1 on white, on card titles at 18 px, tags at 9.5 px and chips at 10 px; detector low-contrast findings at both widths. On their own 16 per cent tinted chip fill the ratios drop to 2.25 to 3.18.
- **Why it matters**: the panel names, the one way a new visitor finds their way around, fail WCAG 1.4.3.
- **Proposed change**: keep the muted lanes for the 3 px top borders and add text tokens that clear 4.5 to 1 on white, on the chip tint and on `#fbf6ea`, computed for this audit: a1 `#4c698a`, a2 `#476e83`, b1 `#2f6f62` (unchanged), b2 `#50725a`, c1 `#935c21`, c2 `#85661e`; use them in lines 862 to 873 in place of `var(--c-xx)` for `color`.
- **Effort**: S
- **Command**: colorize

**9. Darken the table header and card label grey**

- **Surface and place**: public desktop table headers, `LIGHT_CSS` line 997 (`th { color:#8a8378 }` on `#faf9f7`); public phone card labels, `DARK_CSS` lines 944 to 946 (`color:@head@`, `head="8a8378"` at line 759).
- **Severity**: P1
- **Evidence**: 3.56 to 1 on `#faf9f7` at 12 px (47 failures on desktop C1, 41 on C2, 18 on A2, 13 on A1); 3.75 to 1 on white for the phone's 11.5 px uppercase labels ISSUED, COIN, DESCRIPTION (`demo-phone/C2-top-02.png`, `C1-top-05.png`).
- **Why it matters**: these words name every value in every table, and they fail WCAG 1.4.3 at their size.
- **Proposed change**: set `head` to `#6b6660`, the theme's own `soft` grey (5.68 to 1 on white, 5.17 on `#f5f4f1`), or to `#767066` (4.91 on white), and use the token in line 997 instead of the literal.
- **Effort**: S
- **Command**: colorize

**10. Announce the run status**

- **Surface and place**: public phone and desktop, front, B2 and C1 Run blocks. `RUN_BLOCK`, `demo_site.py` line 142, `<p class="note demo-status"></p>`, written by `setStatus` at line 630.
- **Severity**: P1
- **Evidence**: 0 `aria-live` and 0 `role="status"` in the page; `layout.json` `status_live` null on all three copies.
- **Why it matters**: "Sending your settings", "Running, 3 minutes so far" and "The run failed" are the only feedback on the page's main task, and a screen-reader user hears none of them; WCAG 4.1.3 Status Messages.
- **Proposed change**: `<p class="note demo-status" role="status" aria-live="polite">`; the hidden copies are `display:none` and stay silent.
- **Effort**: S
- **Command**: harden

**11. Make Run Model the amber button**

- **Surface and place**: public phone and desktop, front, B2 and C1. `LIGHT_CSS`, `demo_site.py` lines 990 and 993: `.btn, button.btn { background:#ecebe7 !important }` has specificity 0,1,1 and beats `.demo-go { background:#f0a830 !important }` at 0,1,0.
- **Severity**: P1
- **Evidence**: `layout.json`, computed background `rgb(236, 235, 231)` on every Run button at both widths, the same as the three presets; `demo-phone/front-top-01.png`. Only `.demo-go:hover` wins, so the button turns amber under a desktop mouse and never on a phone. The same rule also hides the disabled state, since `.btn:disabled` at `control.css` line 316 carries no `!important` (derived from the cascade; Run was not pressed).
- **Why it matters**: the one action the page exists for looks the same as the five grey buttons around it, against the approved design of 24 September.
- **Proposed change**: `button.btn.demo-go { background:#f0a830 !important; color:#2a2520 !important; }` (7.48 to 1), a matching `:hover`, and `button.btn:disabled { background:#e6e3dd !important; color:#8a8378 !important; }`.
- **Effort**: S
- **Command**: polish

**12. Rewrite the steps that name removed buttons**

- **Surface and place**: public phone and desktop, "What to do" blocks. Text from the panel registry; `trim_settings`, `demo_site.py` line 1094, removes only the line about indicator engines.
- **Severity**: P1
- **Evidence**: live page, C1 "Press Run the test. It spends every setting saved above, and the line under the button is the command it will run" and "Read Results, directly below" (neither exists; the button is Run Model and the results block is dropped by `OWN_RUN_BLOCKS`, line 92); C1 "Pick the market" (the market field is removed, line 1086); B1 "Press Screen variables ... or Univariate screen"; B2 "Press Compare regimes"; A1 "Pick the coins or stocks" (only 14 coins are offered). Seen in `demo-phone/B1-top-03.png`.
- **Why it matters**: a friend following the page's own instructions hits a button that is not there, which costs trust faster than any styling fault.
- **Proposed change**: give the public page its own "What to do" text per panel in `demo_site.py`, keyed by panel, for C1 "Press Run Model. Your tickets appear on C2 in about five minutes.", and drop the steps for B1 and B2 buttons.
- **Effort**: S
- **Command**: clarify

### P2 findings

**13. Stop the C2 Runs table widening the desktop page**

- **Surface and place**: public desktop, C2 Paper tickets. `DEMO_CSS` line 317, `.demo-tables { grid-template-columns:3fr 2fr }`, with `white-space:nowrap` at line 320.
- **Severity**: P2
- **Evidence**: `demo-desk/C2-measure.json` page width 1,442 px; `layout.json` 1,500 px with `#demo-runs` table 608 px wide ending at 1,499.8 px; `B-demo/shot-desk-C2-runs.png`, "Blind score" cut at "U2 1.041, AU".
- **Why it matters**: the results view scrolls sideways and hides each run's score, the number a friend came to see.
- **Proposed change**: `grid-template-columns: minmax(0,3fr) minmax(0,2fr)`, so `.demo-scroll` (overflow auto, line 323) scrolls inside its column.
- **Effort**: S
- **Command**: layout

**14. Restore or remove the dead table controls**

- **Surface and place**: public phone and desktop, A2, C1 and C2. The handlers live in `card.html` lines 1125 to 1200 and are cut by `panel_chunk` (`demo_site.py` line 63, `page.rfind("<script>")`).
- **Severity**: P2
- **Evidence**: 4 `.tablefilter` boxes ("Filter these results", `demo-desk/C2`, `shot-desk-C2-runs.png`), 1 `.beatonly` checkbox "Beat a constant guess" on C1, and `cursor:pointer` on the headers of 15 `table.sortable` (`control.css` line 902); no script in the page contains `sortable`, `tablefilter` or `beatonly`.
- **Why it matters**: typing in a filter box or clicking a header does nothing, and on a phone the filter is the only way through 575 scoreboard cards.
- **Proposed change**: copy the sort, filter and beat-only handlers from `card.html` into `DEMO_SCRIPT` (about 60 lines, no server calls), and give each sortable `th` `tabindex="0"`, `aria-sort` and an Enter key handler.
- **Effort**: S
- **Command**: harden

**15. Give number fields a number keyboard and limits**

- **Surface and place**: public phone and desktop, every settings form. Board field markup in `card.html`; limits in `03-inputs/demo_run.py` line 75 (`LIMITS`).
- **Severity**: P2
- **Evidence**: 66 `type="text"` inputs, 0 `inputmode`, 0 `min`, `max` or `pattern`; values such as `30000000.0` for Volume floor (`demo-desk/A1-top-02.png`). Out-of-range values are clamped by `sanitize` only after the run, reported as "Held to the demo limits" about five minutes later. The 6-coin limit is not shown beside the Coins list.
- **Why it matters**: on a phone every numeric box opens the full letter keyboard, and a friend learns a value was ignored only after the run.
- **Proposed change**: add `inputmode="numeric"` for integers and `inputmode="decimal"` otherwise; add `min` and `max` from `LIMITS` (rows up to 30,000, folds 2 to 5, repeats 1 to 3, blind days 60 to 365, horizon 2 to 72, ATR 0.25 to 10, break-even band 0 to 0.05, at most 6 coins) and print the range in the label; on `input`, set `aria-invalid` and a one-line message tied by `aria-describedby`; show 30,000,000 with separators.
- **Effort**: M
- **Command**: harden

**16. Show field help on touch screens**

- **Surface and place**: public phone, every settings field. `.hint` hidden at `control.css` line 785; help carried only in `title` on 85 `.field` elements.
- **Severity**: P2
- **Evidence**: 84 `.hint` blocks set to `display:none`; phones do not show `title` tooltips. Two tooltips carry the operator's own notes, the A1 timeframe note ("slice_4h_40k is a 25 MB cut ... this machine swaps") and about 90 A2 column range cells ("read from the Parquet footer").
- **Why it matters**: friends new to "L1 mix", "Purge bars" or "Embargo bars" have no way to learn what a setting does on the device they use; WCAG 3.3.2 Labels or Instructions.
- **Proposed change**: under 760 px, show `.hint` as one 13 px line under its field, or add a 44 px "What is this" disclosure per field; remove the two operator notes in `scrub()`.
- **Effort**: M
- **Command**: clarify

**17. Raise non-text contrast and expose the chosen preset**

- **Surface and place**: public phone and desktop. Input borders `LIGHT_CSS` line 989 (`#dcd8d1`); field cards line 987 (`#ebe8e3`); chosen preset line 995 (`inset 0 0 0 2px #c99a2e` on `#fbf6ea`); `markPreset`, `demo_site.py` line 462.
- **Severity**: P2
- **Evidence**: input border 1.42 to 1 on white, field card border 1.22 to 1, preset ring 2.39 to 1, all under the 3 to 1 of WCAG 1.4.11; `.demo-preset` toggles a class with no `aria-pressed` (WCAG 4.1.2).
- **Why it matters**: a friend cannot see where a text box starts, and a screen-reader user cannot tell which preset is filled in.
- **Proposed change**: input border `#9d927e` (3.07 to 1), preset ring `#ae8528` (3.15 on `#fbf6ea`), and `b.setAttribute('aria-pressed', on)` in `markPreset`.
- **Effort**: S
- **Command**: harden

**18. Harden the run path after reload**

- **Surface and place**: public phone and desktop, Run blocks. `DEMO_SCRIPT` lines 640 to 674; name field at lines 138 and 139.
- **Severity**: P2
- **Evidence**: run ids are stored in `swingtrader.demo.runs`, but no code restarts `wait()` on load, so after a reload the status is blank and Run Model is enabled again while the first job still runs; a relay error page that is not JSON makes `r.json()` throw and shows "Could not reach the runner"; the name is published to the public `data/index.json`, while the field says only "shown beside your tickets"; the field has no `autocomplete`.
- **Why it matters**: a friend who reloads mid-run is invited to start a second GitHub Actions job, and may put a full name on a public page without knowing it.
- **Proposed change**: on load, call `wait()` for any id in `swingtrader.demo.runs` without a record and keep Run disabled meanwhile; read `r.text()` and parse it in a `try`, showing the HTTP status on failure; change the placeholder to "A first name or nickname, shown publicly with your tickets"; add `autocomplete="nickname"` (WCAG 1.3.5).
- **Effort**: M
- **Command**: harden

**19. Announce view changes and fix the outline**

- **Surface and place**: public phone and desktop, every view. `showPanel` in `control_export.py` lines 240 to 246; section headings built at `demo_site.py` lines 1127 to 1131.
- **Severity**: P2
- **Evidence**: `layout.json`, `document.title` "Swing Trader · Control Centre" in every view and focus left on `BODY` after a route change; no `main` landmark; headings H1 then H3 (detector skipped-heading, confirmed) and H3 then H5 "RF" on C1.
- **Why it matters**: a keyboard or screen-reader user who follows a panel link is not told the view changed and starts again from the top of the document; WCAG 2.4.2 and 1.3.1.
- **Proposed change**: set `document.title = key + ' ' + title + ' · Swing Trader'` in `showPanel`; make the section's `.pk` an `h2` with `tabindex="-1"` and focus it; wrap the views in `<main>`; demote the RF `h5` to `h4`.
- **Effort**: S
- **Command**: harden

**20. Replace WebGL scatter traces with SVG**

- **Surface and place**: public phone and desktop, B1, B2, C1 and C2 figures. `control_interactive.py` lines 134, 320 and 423; `control_merged.py` lines 190, 195 and 286.
- **Severity**: P2
- **Evidence**: 6 figures carry 59 `scattergl` traces, the largest 7,300 numbers (B2); `layout.json` counts 15 WebGL canvases created at load, hidden panels included; the capture with GPU off showed "WebGL is not supported by your browser" in place of the figure (`demo-phone/C1-measure.json`).
- **Why it matters**: browsers cap live WebGL contexts per page (desktop Chrome warns past 16), so a phone can drop the oldest figures, and a browser with WebGL blocked shows a notice instead of the chart; SVG handles a few thousand points without either risk.
- **Proposed change**: `go.Scatter` in place of `go.Scattergl` at those six lines, which also lets finding 3 use the cartesian bundle.
- **Effort**: S
- **Command**: optimize

**21. Stop board figures catching a scrolling thumb**

- **Surface and place**: public phone, the 11 board figures on A1 to C2. The C2 demo charts already fixed this at `DEMO_SCRIPT` lines 520 to 528.
- **Severity**: P2
- **Evidence**: board figures keep the Plotly toolbar (buttons 23 by 44 px in every phone measure file) and the default drag-to-zoom, which on touch zooms the chart instead of scrolling the page.
- **Why it matters**: on pages 14,753 to 343,870 px tall, a thumb that lands on a chart zooms into it and the friend loses their place; the 23 px buttons also sit under the 24 px of WCAG 2.5.8.
- **Proposed change**: in `fitFigures`, under 760 px, call `Plotly.relayout(el, {dragmode: false, 'xaxis.fixedrange': true, 'yaxis.fixedrange': true})`, and hide the toolbar with `.js-plotly-plot .modebar-container { display:none }` in the phone rules, matching what the C2 charts already do.
- **Effort**: S
- **Command**: adapt

**22. Raise the small text**

- **Surface and place**: public phone front cards, `control.css` line 85 (badge 8 px), line 592 (`.reelnum` 9 px), line 778 (`.slotcap` 9.5 px), card `.tag` and `.num`; public desktop labels at 11.5 px and the 12 px `h1`.
- **Severity**: P2
- **Evidence**: Table 1, 44 of 90 text elements under 12 px on the phone front page (8, 9, 9.5 and 10 px); 195 of 247 on desktop A1; detector undersized-ui-text 45 to 57 findings and flat-type-hierarchy (desktop `h1` 12 px, `h3` 12 px, body 12.5 px); slot captions truncated to about 20 characters on a phone ("Training window agai...", `demo-phone/front-top-02.png`).
- **Why it matters**: the page names and chart titles a friend reads first are the smallest text on it.
- **Proposed change**: under 760 px set `.tag, .num, .setchip, .slotcap, .mh-meta .badge` to 12 px and let `.slotcap` wrap to two lines; on desktop raise field labels and notes from 11.5 to 13 px and the `h1` to 18 px, since the public page is not the one-operator board.
- **Effort**: S
- **Command**: typeset

**23. Redraw the charts for the public page**

- **Surface and place**: public phone and desktop, front cards and every Figures block. PNGs from `control_charts.py`, inlined by `ce.inline_charts`.
- **Severity**: P2
- **Evidence**: `demo-phone/front-top-02.png` and `small-top-02.png`, desktop-sized charts shrunk into a 170 px box so axis text is a few pixels high, drawn in the board palette (saturated red `#a01c1c` bars, navy, purple) beside the muted warm lanes; `demo-phone/A1-top-08.png`; `alt` names each chart ("Training window against blind period") but not what it shows.
- **Why it matters**: on a phone the charts are decoration, and in colour they belong to a different page than the warm theme Seamus approved.
- **Proposed change**: render a phone variant of each front-card chart at 700 by 440 px with 14 px text and the warm lane colours, and write `alt` as the finding, such as "2,979 days train the model and the last 150 are held back".
- **Effort**: L
- **Command**: colorize

**24. Build the warm theme from tokens**

- **Surface and place**: public phone and desktop. `DARK_CSS` (119 `!important`), `LIGHT_CSS` (47 `!important`, 15 literal colours), `DEMO_CSS` (10 literal colours), `DEMO_SCRIPT` chart colours, `demo_site.py` lines 305 to 1020.
- **Severity**: P2
- **Evidence**: the warm tokens in `THEMES["warm"]` cover 10 roles, while `LIGHT_CSS` hard-codes `#faf9f7`, `#ebe8e3`, `#dcd8d1`, `#ecebe7`, `#f0a830` and others; `DEMO_CSS` keeps the board's blue-grey stat boxes (`#e8eef4`) and navy numbers (`#0b2038`) on C2 (`demo-desk/C2-top-01.png`); the masthead title and "PAPER ONLY" badge stay in board navy `--tuv`; `theme_css()` builds the light theme by deleting parts of the dark one. Finding 11 is one result.
- **Why it matters**: every change to the look has to win a specificity contest, and the colours on C2 and the masthead do not match the approved warm theme.
- **Proposed change**: declare `--bg`, `--surface`, `--ink`, `--ink-soft`, `--line`, `--field-line`, `--accent`, `--accent-ink` and the `--lane-*` pairs on `:root` for the warm theme, map the board's `--tuv`, `--ink`, `--rule` and `--idle` onto them, write `LIGHT_CSS` and `DEMO_CSS` in `var()` only, and remove the dark path from `theme_css()`.
- **Effort**: M
- **Command**: colorize

**25. Use tick boxes for Models, Coins and Families**

- **Surface and place**: public phone and desktop, C1 Choose Model (`estimators`), A1 Choose Basket (`symbols`), A2 Choose Features (`families`, `include`, `exclude`).
- **Severity**: P2
- **Evidence**: all are `<select multiple>` list boxes (`demo-phone/C1-top-02.png`), while the note under Models says "Tick the models to score"; on a desktop a plain click drops every other choice unless Ctrl or Command is held; the Coins box does not say that at most 6 run.
- **Why it matters**: a friend who clicks a second model on a desktop silently loses the first.
- **Proposed change**: render each as a `fieldset` with a `legend` and one 44 px checkbox row per option, keeping the same `name` so `collect()` and `fill()` need only the checkbox branch.
- **Effort**: M
- **Command**: clarify

### P3 findings

**26. Flatten the boxes inside boxes**

- **Surface and place**: public phone and desktop, settings forms. `LIGHT_CSS` lines 977, 986 and 987.
- **Severity**: P3
- **Evidence**: detector nested-cards, 27 on A1 and 28 on C1; `demo-phone/C1-top-02.png` and `C1-top-03.png` show three rounded boxes deep (block, cluster, field) and a fourth for the RF settings with a 2 px amber top edge (detector border-accent-on-rounded).
- **Why it matters**: three frames around each input read as clutter on a 390 px screen, and each frame's padding narrows the input.
- **Proposed change**: drop the `.cluster` fill and the `.field` border and radius on the public page, keeping the white block card only.
- **Effort**: S
- **Command**: quieter

**27. Add link preview, icon and colour scheme**

- **Surface and place**: public page `<head>`, `demo_site.py` lines 1133 to 1137.
- **Severity**: P3
- **Evidence**: the head has only `charset`, `viewport` and the Jost stylesheet; no `description`, no Open Graph tags, no icon, no `color-scheme`.
- **Why it matters**: friends receive the link in a chat app, where it shows as a bare address, and a browser's forced dark mode can repaint the approved light theme.
- **Proposed change**: add `<meta name="description">`, `og:title`, `og:description`, an `og:image` of the front page at 1200 by 630 px, a favicon, and `<meta name="color-scheme" content="only light">`.
- **Effort**: S
- **Command**: onboard

**28. Remove the em dashes from axis titles**

- **Surface and place**: public desktop and phone, C1 and C2 interactive figures. `control_merged.py` lines 215, 224, 225, 333 and 343 join a measure and its note with an em dash.
- **Severity**: P3
- **Evidence**: 12 em dashes in the page, all in axis titles and their menu labels, such as the Theil U2 title on C1, where "Theil U2 on the blind period" and "below one beats always predicting the base rate" are joined by the dash.
- **Why it matters**: the writing rules forbid the em dash in any visible text.
- **Proposed change**: join with a comma, "Theil U2 on the blind period, below 1 beats always predicting the base rate".
- **Effort**: S
- **Command**: clarify

## Patterns

Four faults recur. First, the page is made by subtracting from the board with regular expressions, and each subtraction left an orphan (findings 2, 4, 12 and 14). Second, the theme is a stack of overrides, so colour decisions are settled by specificity rather than tokens (findings 8, 9, 11 and 24). Third, everything is inlined into one document, so a friend opening one view pays for all seven and waits for the last byte before anything responds (findings 1 to 4). Fourth, grid tracks were written as `1fr` rather than `minmax(0,1fr)`, which let wide content push its column past the screen (findings 5, 6 and 13).

## What works

These parts should be kept as they are.

1. All 85 settings fields have a `label for` tied to their `id`, no view has an unnamed control, and all 17 tables have header cells.
2. The 2 px `:focus-visible` ring (`DARK_CSS` line 878) shows on every control, and a keyboard reaches Run Model in 11 tab stops on the front page and 12 on C1 at phone width.
3. The phone layout rules (`demo_site.py` lines 888 to 965) give one column, 16 px inputs 44 px tall so iOS does not zoom, 44 px buttons, a full-width Run button and tables as labelled cards; no phone view scrolls the page sideways.
4. The viewport allows pinch zoom and the document declares `lang="en"`.
5. The two C2 demo charts are the model for every other figure, with no toolbar, no drag zoom, fixed ranges and a colour pair checked for colour blindness (lines 515 to 528).
6. Browser storage is wrapped in `try`, and a preset refills from the built defaults before applying, so a preset also works as a reset.
7. The run states are written in plain words, including the failure reason and a 40-minute stop, and the tickets load from `data/index.json` with `no-store`, separate from the page.

## False positives

These detector or capture results were judged not to be defects, or not the defect they appear to be.

1. The detector could not scan the live address; it stopped with "snapshot is 78925714 bytes (limit 50331648)" (`B-demo/detect-live-failure.txt`). The four `B-demo/detect-*.json` files were run on `live-lite.html`, the same page with each image replaced by a grey placeholder of the same pixel size, so no finding about image content could come from the detector.
2. The detector scanned the whole document in every run, so `#panel-C1` and `#panel-A1` repeated front-page findings (115, 139 and 137 findings at 390 px, 314 at 1440 px); counts per view are from the capture measure files instead.
3. The low-contrast "WebGL is not supported by your browser" text (4.16 to 1) on phone B2, C1 and C2 came from `cap.mjs` launching Chrome with `--disable-gpu`; with the GPU on, WebGL was available and the notice count was 0 (`layout.json`).
4. `dark_mode_rule: true` in every measure file came from Plotly's bundled map CSS, not from the page, which has no dark mode by design.
5. The absent reduced-motion rule is not a finding, because the page's only motion is a 0.12 s hover fade.
6. Detector low-contrast `#6b7885` on `#f5f4f1` at 4.1 to 1 on desktop was the five decorative arrows between the flow steps (`control.css` line 940), which carry no information.
7. Detector tight-leading (56 to 57) was mostly single-line text, field labels at 11.5 px with 1.25 line height and the card titles, where leading has no effect; only the account line wraps on a phone, and it reads acceptably.
8. The coloured 3 px top border on the rounded cards is the approved lane marker from DESIGN.md; only the RF settings box's amber edge (finding 26) is incidental.

## Known defects

The brief listed seven label defects already found. They show on the public page as follows.

1. Take-profit and Stop never change the label, shown on A1, Choose Label, fields "Take-profit, ATR" (2.0) and "Stop, ATR" (1.0), `demo-desk/A1-top-02.png`.
2. The eleven A2 engine settings that only draw charts are not on the public page; `DEMO_DROP` (`demo_site.py` lines 1076 and 1077) removes them, and only the A2 "Indicator engines" table still describes the engines.
3. No model ticked fits three models on the board; on the public page `demo_run.sanitize` falls back to two, RF and LogReg.glm (`demo_run.py` line 145). It shows on C1, Choose Model, the Models list and its note "Tick the models to score".
4. Fold pass rate is described as money on A1, Choose Ranking, in the visible note "the share of them where the strategy must have made money", `demo-desk/A1-top-02.png`.
5. Embargo 0 meaning 2 days sits on B2, Choose Blind Period, field "Embargo bars" (12).
6. Class weight defaulting to balanced shows on C1, Choose Model, "Class weight" set to balanced beside a note that balanced caused two thirds of the calibration error, `demo-phone/C1-top-02.png` and `C1-top-03.png`.
7. The 1-hour base rate 0.313 is quoted in the tooltip of A1 "Take-profit, ATR"; on a phone it cannot be seen at all (finding 16).

## Fixed meanwhile

Three defects seen in the captures were fixed in `demo_site.py` and were live in the 00:27 GMT build, so they are not reported. The badge "LOCAL, PAPER ONLY" became "PAPER ONLY" (lines 1149 and 1150). The C2 boxes "BUY, mean a trade after cost" and "PASS, mean a trade after cost", blank in `demo-phone/C2-top-02.png`, now read "none yet" (lines 601 and 602). The tickets column "Bars" became "Timeframe" (lines 605 and 613).

## Recommended actions

1. **[P1] `/impeccable optimize`**, findings 2, 3 and 4, in that order, since dropping the hidden reel images is one short change worth 9.9 MB.
2. **[P1] `/impeccable harden`**, findings 1 and 10, so the buttons respond from first paint and the run status is announced.
3. **[P1] `/impeccable adapt`** and **`/impeccable layout`**, findings 5, 6, 7 and 13, the figure fit, the C2 grid, the phone tables and the desktop Runs column.
4. **[P1] `/impeccable colorize`**, findings 8 and 9, the lane text tokens and the header grey.
5. **[P1] `/impeccable polish`** and **`/impeccable clarify`**, findings 11 and 12, the amber Run button and the public "What to do" text.
6. **[P2] `/impeccable harden`**, findings 14, 15, 17, 18 and 19.
7. **[P2] `/impeccable clarify`**, findings 16 and 25.
8. **[P2] `/impeccable optimize`** and **`/impeccable adapt`**, findings 20 and 21.
9. **[P2] `/impeccable typeset`** and **`/impeccable colorize`**, findings 22, 23 and 24.
10. **[P3] `/impeccable quieter`**, **`/impeccable onboard`** and **`/impeccable clarify`**, findings 26, 27 and 28, then `/impeccable polish` as the last pass.
