---
name: Swing Trader Control Centre
description: A dense research instrument that reads like a printed cheat sheet, one colour per panel lane, carried unchanged into every figure.
colors:
  brand-navy: "#14304d"
  navy-deep: "#0b2038"
  navy-tint: "#e8eef4"
  ink: "#16202c"
  ink-soft: "#4a5866"
  rule: "#c3cedb"
  paper: "#ffffff"
  board-bg: "#eef1f4"
  lane-a1-data: "#0b4f8a"
  lane-a2-indicators: "#1f7ac4"
  lane-b1-variables: "#0e7a4f"
  lane-b2-training: "#27a86e"
  lane-c1-scoreboard: "#c2410c"
  lane-c2-ledger: "#ea7a2c"
  sheet-blue: "#0d5f8a"
  sheet-purple: "#6b3fa0"
  sheet-green: "#0e7a5f"
  sheet-ochre: "#a8560c"
  sheet-navy: "#1c4f8f"
  sheet-red: "#a01c1c"
  sheet-slate: "#4a5568"
  state-idle: "#8f9aa6"
typography:
  display:
    fontFamily: "Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "12.5px"
    fontWeight: 800
    lineHeight: 1.05
    letterSpacing: "-0.3px"
  headline:
    fontFamily: "Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "14.5px"
    fontWeight: 800
    lineHeight: 1.1
    letterSpacing: "-0.15px"
  title:
    fontFamily: "Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "12px"
    fontWeight: 800
    lineHeight: 1.45
    letterSpacing: "0.5px"
  section-title:
    fontFamily: "Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "13px"
    fontWeight: 800
    lineHeight: 1.45
    letterSpacing: "normal"
  body:
    fontFamily: "Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "12.5px"
    fontWeight: 400
    lineHeight: 1.35
    letterSpacing: "normal"
  label:
    fontFamily: "Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "11.5px"
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: "normal"
  table-head:
    fontFamily: "Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "11.5px"
    fontWeight: 800
    lineHeight: 1.45
    letterSpacing: "0.3px"
  caption:
    fontFamily: "Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.3
    letterSpacing: "normal"
  result:
    fontFamily: "Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 700
    lineHeight: 1.4
    letterSpacing: "normal"
  mono:
    fontFamily: "SF Mono, Menlo, Consolas, monospace"
    fontSize: "11.5px"
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: "normal"
rounded:
  chip: "2px"
  surface: "3px"
  pill: "10px"
  dot: "50%"
spacing:
  hair: "3px"
  xs: "5px"
  sm: "8px"
  md: "12px"
  lg: "18px"
  card: "8px 10px 9px 10px"
  block: "14px 16px"
  field: "6px 8px 7px 8px"
components:
  panel-card:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.surface}"
    padding: "{spacing.card}"
  panel-badge:
    backgroundColor: "{colors.lane-a1-data}"
    textColor: "{colors.paper}"
    rounded: "{rounded.pill}"
    padding: "0 9px"
    height: "20px"
    width: "30px"
  panel-tag:
    backgroundColor: "{colors.lane-a1-data}"
    textColor: "{colors.paper}"
    rounded: "{rounded.chip}"
    padding: "2px 5px"
  flow-chip:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.surface}"
    padding: "2px 9px 3px 6px"
  block:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.surface}"
    padding: "{spacing.block}"
  cluster:
    backgroundColor: "#fbfcfd"
    textColor: "{colors.ink}"
    rounded: "{rounded.surface}"
    padding: "8px 10px 4px 10px"
  button-primary:
    backgroundColor: "{colors.sheet-green}"
    textColor: "{colors.paper}"
    rounded: "{rounded.surface}"
    padding: "8px 16px"
  button-ghost:
    backgroundColor: "#eef2f6"
    textColor: "{colors.navy-deep}"
    rounded: "{rounded.surface}"
    padding: "8px 16px"
  button-stop:
    backgroundColor: "{colors.sheet-red}"
    textColor: "{colors.paper}"
    rounded: "{rounded.surface}"
    padding: "8px 16px"
  button-disabled:
    backgroundColor: "{colors.state-idle}"
    textColor: "{colors.paper}"
    rounded: "{rounded.surface}"
    padding: "8px 16px"
  field-input:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.mono}"
    rounded: "{rounded.surface}"
    padding: "4px 6px"
  field-input-disabled:
    backgroundColor: "#f7f9fb"
    textColor: "{colors.ink}"
    typography: "{typography.mono}"
    rounded: "{rounded.surface}"
    padding: "4px 6px"
  table-head-cell:
    backgroundColor: "{colors.navy-tint}"
    textColor: "{colors.navy-deep}"
    typography: "{typography.table-head}"
    padding: "5px 7px"
  console:
    backgroundColor: "{colors.navy-deep}"
    textColor: "#d7e2ec"
    typography: "{typography.mono}"
    rounded: "{rounded.surface}"
    padding: "10px 12px"
    height: "220px"
  callout-info:
    backgroundColor: "{colors.navy-tint}"
    textColor: "#12314a"
    rounded: "{rounded.surface}"
    padding: "9px 12px"
  callout-ok:
    backgroundColor: "#ecf6f2"
    textColor: "#123f33"
    rounded: "{rounded.surface}"
    padding: "9px 12px"
  callout-warn:
    backgroundColor: "#fbeeee"
    textColor: "#5c1414"
    rounded: "{rounded.surface}"
    padding: "9px 12px"
  recommend:
    backgroundColor: "#fffaf4"
    textColor: "{colors.ink}"
    rounded: "0 3px 3px 0"
    padding: "9px 12px"
  chart-figure:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink-soft}"
    rounded: "{rounded.surface}"
    padding: "7px 9px 8px 9px"
---

# Design System: Swing Trader Control Centre

## Overview

**Creative North Star: "The Operable Cheat Sheet"**

The board is a printed one-page reference that was made to run. It wears the
clothes of `05-research/cheatsheets/swing-trader-cheatsheet.html`, the colour
tokens, the lane grid, the coloured top border, the round number badge and the
uppercase tag, all lifted unchanged so a panel here and a panel there are
recognisably the same panel. What changed is the measure: the sheet is typeset
in points for an 11 by 8.5 inch page, and every size on screen is in pixels for
a monitor.

Density is the governing value. One operator reads this at full width on a
desktop and knows every term on it, so the board spends its space on evidence
rather than on explanation. Settings sit four across in quarter-width boxes so a
whole configuration is visible at once. Charts sit four across in boxes the size
of the front-page panels. The reason a setting exists is a tooltip, not a
paragraph, which is the single strongest rule in the system and the one that
makes the density possible.

Colour carries meaning and nothing else. Six panels run across one cool-to-warm
gradient, two shades to a lane, blue for the inputs, green for the fitting,
orange for the results, and the panel's hue follows it inside through one custom
property so every element on an open panel is one colour. The same palette is
declared again in `03-inputs/control_charts.py` so a colour on a figure means
what it means on the board. Depth is flat: a one-pixel rule, a four or five
pixel coloured border, and two soft hover shadows are the whole vocabulary.

**Key Characteristics:**
- Print-derived grid, screen-sized type, scrolling panel pages
- One hue per panel lane, carried into the figures
- Notes as tooltips, with one deliberate exception for the result verdict
- Flat surfaces, coloured edges, no ambient shadow at rest
- Four-across rhythm for settings, charts and hyperparameter boxes
- Two surfaces from one stylesheet, a served page and a self-contained file

## Colors

A navy-and-paper ground carrying one saturated hue per panel lane, with three of
the cheat sheet's six accents doing double duty as the pass, warn and fail
states.

### Primary
- **Instrument Navy** (`{colors.brand-navy}`): the masthead rule, the lane
  header underline, the lane key pill, the reading-order arrows, the left rule
  on a command block and on the results block. It is the frame the work sits in
  and it never carries a verdict.
- **Navy Deep** (`{colors.navy-deep}`): the masthead title, every block heading,
  every field label, and the console ground. The darkest ink in the system.
- **Navy Tint** (`{colors.navy-tint}`): table head fill, the informational
  callout, the hovered row of a large table, the hovered expand control.

### Secondary
The six lane colours, two shades of one hue per lane, run in the order the
panels are used. Each shade is dark enough to carry white type on a badge.
- **Deep Harbour Blue** (`{colors.lane-a1-data}`) and **Open Blue**
  (`{colors.lane-a2-indicators}`): A1 Data and A2 Indicators, the inputs.
- **Forest** (`{colors.lane-b1-variables}`) and **Spring Green**
  (`{colors.lane-b2-training}`): B1 Variables and B2 Training, the fitting.
- **Burnt Orange** (`{colors.lane-c1-scoreboard}`) and **Amber**
  (`{colors.lane-c2-ledger}`): C1 Scoreboard and C2 Ledger, the results.

### Tertiary
The cheat sheet's original six, kept for the records, the export and every
figure. They are the palette `control_charts.py` declares and the per-family
colour map interpolates from.
- **Sheet Blue** (`{colors.sheet-blue}`), **Sheet Purple**
  (`{colors.sheet-purple}`), **Sheet Green** (`{colors.sheet-green}`),
  **Sheet Ochre** (`{colors.sheet-ochre}`), **Sheet Navy**
  (`{colors.sheet-navy}`), **Sheet Red** (`{colors.sheet-red}`): the first
  series order on a multi-line chart is blue, green, ochre, purple, navy, red,
  then ink-soft. **Sheet Slate** (`{colors.sheet-slate}`) rules the left edge of
  an interactive figure's note.
- Feature families take fixed tints of these six, so a family keeps its colour
  from the composition chart through to the importance chart. The tints avoid
  resting on the red and green pair alone.

### Neutral
- **Ink** (`{colors.ink}`): body text, table cells, the verdict line.
- **Ink Soft** (`{colors.ink-soft}`): notes, captions, axis labels and ticks,
  the card foot, the timestamp on an evidence row.
- **Rule** (`{colors.rule}`): every one-pixel border, every chart spine, the
  grid lines at 35 per cent alpha.
- **Paper** (`{colors.paper}`): every card, block, field and chart ground.
- **Board** (`{colors.board-bg}`): the page behind the cards.
- **Idle** (`{colors.state-idle}`): a disabled button and a status dot with no
  record behind it.

### Named Rules
**The One Meaning Rule.** A colour means the same thing on the board and in a
figure. The chart module declares the same hexadecimals the stylesheet does, on
purpose, so a family or a lane can be followed from a panel into a drawing
without a legend.

**The Lane Inheritance Rule.** A panel's colour is set once. The class the card
wears on the front page goes on `.sheet` when that panel opens and sets
`--panel`; every coloured element downstream reads that property with a
fallback. A new coloured element is one declaration, never one rule per element
per lane.

**The Verdict Colours Rule.** Green, ochre and red are reserved for pass, warn
and fail, on the status dot, the run pill, and the `v-ok` and `v-bad` table
cells. They are never used to decorate a surface.

## Typography

**Display Font:** Helvetica Neue (with Helvetica and Arial)
**Body Font:** Helvetica Neue (with Helvetica and Arial)
**Label/Mono Font:** SF Mono (with Menlo and Consolas), for every input, every
command, the console, the code folds, and the symbol picker

**Character:** One neutral grotesque doing all the work, weighted hard at 700
and 800 for structure and left plain at 400 for prose, with monospace reserved
strictly for values a machine reads or writes. Small sizes and tight leading
throughout, because the reader is one metre from the glass and wants more
evidence on screen rather than larger words.

### Hierarchy
- **Display** (800, 12.5px, 1.05, -0.3px): the masthead title. Reduced to 12px
  on the front page, where the strap line and the repository line are removed
  outright.
- **Headline** (800, 14.5px, 1.1, -0.15px): a panel card's name, set in the
  lane colour, with the badge at its left and the tag pushed to its right.
- **Title** (800, 12px, 1.45, 0.5px, uppercase): every block heading, underlined
  in the panel colour.
- **Section Title** (800, 13px, sentence case, no tracking): a merged panel's
  section heading, in the panel colour over a two-pixel rule. Deliberately not
  uppercase, so a section reads as a division rather than as another block.
- **Body** (400, 12.5px, 1.35): lead paragraphs, section answers, table cells.
- **Label** (700, 11.5px, 1.25): a field's name inside the settings grid. Full
  width labels outside the grid run at 12.5px.
- **Table Head** (800, 11.5px, 0.3px, uppercase): column headings, pinned when
  the table scrolls.
- **Caption** (400, 11px, 1.3): a chart's figure caption, over a hairline rule.
- **Result** (700, 14px, 1.4): the verdict line on C1, the largest prose on any
  panel.
- **Mono** (400, 11.5px, 1.4): inputs, console, code folds. Drops to 10.5px in a
  code fold and 11px in the symbol picker.
- **Micro** (400, 9px to 9.5px): the reel caption, the slot caption, the slide
  counter, the front-page masthead meta.

### Named Rules
**The Three Word Rule.** No heading exceeds three words. Qualify, date or
attribute in the first sentence beneath it, never in the heading.

**The Tooltip Rule.** An explanatory note is a tooltip, not body text. Every
`.hint` is hidden outright and the configuration sentence with it; one to five
words appear on the page and the explanation arrives on hover, with `cursor:help`
on anything carrying one. The one deliberate exception is the result verdict on
C1, `.resultline` at 14px and `.resultdetail` at 11px, which is text because it
is the answer and not a caption.

**The Fixed Headline Rule.** Headline type in the masthead is fixed, not scaled
to its box. The dollar figure rides at 1.02em of the meta line and the band
keeps the height it was cut to.

**The No Path Rule.** No script path or data path appears in readable text on a
panel. The command block is rendered and hidden; the exact command survives as
the Run button's tooltip and runs unchanged.

## Layout

The board is a three-column grid of six panels, `.lanes` at
`repeat(3, minmax(0, 1fr))` with an 18px gutter and no row gap, each lane an
inner grid of one header and two equal rows at a 9px gap. `minmax(0, 1fr)` is
load-bearing: it makes the two rows share the column rather than size to
whichever panel has the longest lead, and it keeps row two of column A level
with row two of column C. A lane holding one panel takes `.one` and gives it the
whole height.

The front page alone is pinned to the glass. `.sheet.front` is the viewport
height, a flex column with `overflow:hidden`, so everything the top band does
not use goes to the lanes. Panel pages scroll as far as their sections go, and
that is deliberate: a control centre gains nothing from fitting one frame, and
the sibling Quarto dashboard's no-scroll rule does not apply here.

Above the lanes sit three fixed bands. The timeline occupies its own band at
6.75vh, floored at 54px and capped at 77px, so it scales with the glass and
never eats the panels. The masthead beneath it is one thin line carrying the
mark, the title, the tools, the middle strip and the money headline. Then the
reading order, one line of coloured chips and arrows from A1 to C2 over a
two-pixel navy rule.

Inside a panel the unit is the brief row. `.briefrow` is two equal columns at an
18px gutter with `align-items:stretch`, the left column a flex column whose
table block stretches to the tools beside it, so the two sides of a row end
level. Figures fill whichever side is shorter, two across in a brief table, one
across under the tools at a 300px cap, two across when they are trade-geometry
figures. What is left over goes to one Figures block at the foot, four across,
after every table and every tool, with the interactive figures beneath the grid.
Below the rows the page runs full width: job tools two per row, then the run
output, the result tables and the Evidence Log, never a half-empty second
column.

Settings are a dense grid, not full-width rows. A cluster's `.fields` is four
across at an 8px by 12px gap, dropping to three below 1400px and two below
1000px. Chart grids are four across, dropping to two below 1200px. The panel
wrapper's first child pairs off into two columns and collapses to one below
1200px; the lanes go to two columns below 1100px and a brief row goes to one.
Large tables scroll inside a 520px box with their headings pinned.

Page zoom is a first-class control. `?zoom=0.7` sets a document zoom, the
browser remembers it, and the front page's height is recomputed in zoomed pixels
on load and resize rather than trusting `100vh` under a zoom.

Two surfaces share this layout. The Flask page at `127.0.0.1:8787` is the
operable one. The export at `01-dashboard/control-centre.html` is one
self-contained file of about 21 MB that opens from disk with no server: the job
forms, the Run buttons, the run output block and the console are removed,
because a file cannot run a job, and every settings field is kept and
`disabled` so a reader sees what the run used. Three layout differences follow
from that. The 118px chart cap is lifted, because the control that opened a
chart full page went with the other buttons and a small picture with no way to
enlarge it would be the dead control in another form. The panels become stacked
`.panelsec` sections with a back chip rather than separate pages. A panel whose
whole content was a Run button and a console says so in a note instead of
rendering empty.

## Elevation & Depth

The system is flat. Depth is carried by a one-pixel rule border, a coloured
top or left border, and tonal separation between the board ground and the paper
card. Nothing is lifted at rest.

### Shadow Vocabulary
- **Card lift** (`box-shadow: 0 2px 10px rgba(20,48,77,0.16)`): a panel card on
  hover, paired with `transform: translateY(-1px)` over 120 milliseconds. The
  only shadow that moves anything.
- **Chip lift** (`box-shadow: 0 1px 4px rgba(20,48,77,0.25)`): a reading-order
  chip on hover.
- **Scrim** (`background: rgba(11,32,56,0.88)`): the full-page chart overlay,
  the only true layer in the system, at `z-index: 200`.

### Named Rules
**The Edge Not Shadow Rule.** Importance is shown by an edge, never by a
shadow. A card carries a five-pixel coloured top border, a section a five-pixel
left border, a cluster and a callout a three or four pixel left border. A
surface that needs to stand out gets a thicker rule in the panel's colour, not
a drop shadow.

**The Flat At Rest Rule.** Shadows respond to a pointer and to nothing else.
Every shadow in the stylesheet sits behind `:hover`.

## Shapes

Small, consistent radii and straight edges. Three pixels is the house corner on
every card, block, field, button, callout and chart box. Two pixels is the chip
corner, used on a tag, a run chip, a set chip, a pill and a thumbnail. The panel
badge is the only genuinely round form, a ten-pixel pill at least 30px wide and
20px tall, sized by its label rather than fixed so a two-character key cannot be
clipped. The status dot is a full circle at eight pixels.

A left-ruled callout squares its left corners and rounds its right,
`border-radius: 0 3px 3px 0`, so the coloured rule reads as an edge of the page
rather than as a stripe inside a rounded box. That form recurs on the command
block, the configuration line, the recommendation box, the section answers line
and the interactive figure's note.

Images are contained, never cropped. Every thumbnail, reel frame, chart and
lightbox image uses `object-fit: contain` with `object-position: top center`,
because several of these drawings are very wide and showing one small is better
than cutting it.

## Components

### Buttons
- **Shape:** house corner (3px), no border.
- **Primary:** green (`{colors.sheet-green}`) on white, 700 at 13px, 8px by 16px
  padding. Used for Save these settings and Run it.
- **Ghost:** pale blue-grey fill (`#eef2f6`) with navy-deep type, same metrics.
  Used for Reset defaults, Load best as defaults, Show all code, and the export's
  one surviving control.
- **Stop:** the warning red (`{colors.sheet-red}`), same metrics.
- **Disabled:** idle grey with `cursor: not-allowed`.
- **Hover / Focus:** no hover treatment on a button. There is no focus-visible
  treatment anywhere in the stylesheet.

### Panel Cards
The front-page panel, and the component the whole system is named for.
- **Corner Style:** 3px, with a five-pixel top border in the lane colour.
- **Background:** paper. The warning lane alone tints its ground (`#fdf6f6`).
- **Header:** a pill badge carrying the panel key, the panel name in the lane
  colour at 14.5px/800, and an uppercase tag pushed right at 9.5px with 0.85
  opacity.
- **Body:** a two-slot image pair, each slot stepping by hand through the whole
  collection with a previous and next control and a slide counter, then a lead
  paragraph clamped to three lines.
- **Foot:** a hairline rule, a status dot (fresh, stale, old or none), when it
  last ran, and a chip pushed right, run or read or charts-and-settings, in the
  panel's own colour.
- **Shadow Strategy:** flat at rest, card lift on hover.

### Blocks and Sections
- **Block:** paper, 1px rule, 3px corner, 14px by 16px padding, 16px below. Its
  heading is uppercase 12px/800 in navy-deep over a rule in the panel colour.
- **Section:** a block with a five-pixel left border in the panel colour and a
  sentence-case heading. Below the heading sits the answers line, the question
  the section answers, set apart on a tinted ground with its own three-pixel
  left rule. That line is text and not a tooltip because it is how a reader
  finds which of sixteen charts they came for.
- **Brief block:** a section whose table is fixed-layout, wrapping, with a bold
  first column at 15 per cent width.

### Inputs and Fields
- **Style:** white ground, 1px rule, 3px corner, monospace at 12px inside the
  settings grid, each field in its own bordered box so the grid reads as boxes
  rather than as rows.
- **Label:** above the control, 11.5px/700 in navy-deep.
- **Note:** hidden. The reason a setting exists is the field's `title`.
- **Focus:** no treatment.
- **Disabled:** used only in the exported file, where the text stays at full
  contrast on a `#f7f9fb` ground with a lighter border and a default cursor,
  because the number is the content and a greyed number cannot be read.
- **Multi-select:** at least 92px tall; the symbol picker 118px in Menlo at 11px.

### Tables
- **Head:** navy-tint fill, navy-deep uppercase 11.5px/800, two-pixel navy
  bottom rule, pinned to the top when the table scrolls.
- **Body:** 12.5px, hairline row rules, top-aligned, no wrapping in a large
  table and wrapping in a brief table.
- **Sorting:** the active column appends an up or down arrow glyph.
- **Verdicts:** a cell reading `passes` goes green and bold, `rejected` red and
  bold.
- **Scroll box:** 520px maximum with a 3px corner; rows tint navy on hover.

### Callouts
- **Warn (default):** four-pixel red left rule, `#fbeeee` ground, dark red text,
  with its lead word uppercase at 11.5px.
- **Info:** navy rule on navy-tint.
- **Ok:** green rule on `#ecf6f2`.
- **Recommend:** ochre rule on `#fffaf4`, carrying where the panel's opening
  settings came from, what that record scored, and its Load best control.

### Run Console
- **Style:** navy-deep ground, pale blue text, monospace 11.5px, 220px tall,
  scrolling, 3px corner.
- **Empty state:** the console says so in its own words rather than sitting
  blank.
- **State line:** an uppercase pill above it, grey when idle, green when
  running, navy when done, red when it failed.
- **Placement:** beside the form that fills it. It once sat at the foot of a
  two-megabyte page, which made the Run button read as dead.

### Chart Figure
- **Style:** a paper box with a four-pixel top border in the panel colour, the
  image capped at 118px and contained, and a caption over a hairline rule.
- **Expand:** a small control at the top right, revealed on hover at 120
  milliseconds and always visible where there is no pointer, because a control
  that only appears on hover does not exist on a touch screen.
- **Lightbox:** a fixed navy scrim, the image at 88vh maximum on a white pad, a
  caption at 70ch, and a waiting line while the full-size draw arrives. The
  hidden attribute is restated with `!important`, because an author `display`
  rule beats the browser's own `[hidden]` rule at any specificity.

### Reading Order
Six coloured chips separated by arrows, each chip a white box with a four-pixel
top border and a coloured key badge in the panel's own hue, over a two-pixel
navy rule. It replaced three lane titles and is the only navigation on the front
page besides the cards themselves.

### The Reel
The signature component. A panel card's image area holds the panel's whole
collection stacked in one box and shows one at a time, stepped by hand and never
on its own. The frames are absolutely positioned inside a `min-height: 0` flex
item, which is the whole trick: left in flow, a 1200 by 700 chart resolves its
height against a parent with no definite height, claims space it was never
given, and pushes the card's lead and foot out of its row. Out of flow the image
contributes nothing to the card's height and the row decides how big it is.

### Hyperparameter Block
One block per ticked estimator, hidden when not chosen, its settings in the same
four-across grid as everything else, with an ochre left rule and an uppercase
ochre heading. Beside a sweep's grid field sits a reference table naming what
that one line of text accepts.

## Do's and Don'ts

### Do:
- **Do** set a panel's colour once through the `--panel` custom property and let
  every coloured element read it with a fallback.
- **Do** declare a new chart colour in `control_charts.py` from the same
  hexadecimals the stylesheet uses, so the board and the figure agree.
- **Do** keep every heading to three words or fewer and put the qualification in
  the first sentence beneath it.
- **Do** put an explanation in a `title` attribute and one to five words on the
  page, with `cursor:help` on the element that carries it.
- **Do** make a brief row's table and its tools the same height, fill the
  shorter side with that row's figures, and send everything left over to one
  Figures block at the foot, four across, with the interactive figures beneath
  the grid.
- **Do** let a panel page scroll. The front page alone is pinned to the viewport.
- **Do** use `minmax(0, 1fr)` and `min-height: 0` on any grid or flex child that
  holds a drawing, or the drawing sets the height of the row.
- **Do** contain an image rather than cropping it, at `object-position: top
  center`.
- **Do** cap a large table at 520px and pin its headings.
- **Do** say what is absent on the axes when a chart has nothing to draw, rather
  than drawing an empty box.
- **Do** keep the exported file's disabled fields at full text contrast, with
  only the frame and the cursor saying they cannot be edited.

### Don't:
- **Don't** print a script path or a data path in readable text on a panel. The
  command lives in the Run button's tooltip.
- **Don't** write a note as body text. The result verdict on C1 is the one
  exception, and it is the answer rather than a caption.
- **Don't** scale headline type to its box. The masthead figures are fixed.
- **Don't** put a shadow on a resting surface. Use a thicker coloured edge.
- **Don't** colour a surface green, ochre or red for decoration; those three are
  the pass, warn and fail states.
- **Don't** rely on the red and green pair alone to separate two series. The
  feature-family tints were chosen for that reason.
- **Don't** lay settings out as full-width rows. Four across, quarter width, so
  a whole configuration is visible at once.
- **Don't** put a form far from the output it produces.
- **Don't** apply the sibling Quarto dashboard's no-scroll rule to this board.

## Not Yet Defined

Recorded as absent rather than invented, so a later pass does not mistake a gap
for a decision.

- There is no documented type scale. The sizes above are the ones the stylesheet
  states, and they do not follow a ratio.
- There is no motion language. The only transitions in the build are 120
  millisecond opacity fades on hover controls and the card's hover lift; there
  is no easing token, no duration scale and no named motion role.
- There is no `:focus-visible` treatment anywhere. Keyboard focus falls back to
  the browser default.
- There is no dark mode. The console ground and the lightbox scrim are dark
  surfaces inside a light board, not a theme.
- Accessibility has no established requirement beyond the colour-blind
  consideration recorded in the feature-family map.
