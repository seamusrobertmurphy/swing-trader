# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

One operator, Seamus, who built the whole system and knows every term in it. Nobody
else opens the control centre. The repository is public on GitHub and figures from
it appear in a written workflow document, so screens are occasionally seen by
others, but they are not used by others.

The situation is a research session at a desk: a configuration is composed, a model
test is run on historical price data, and the result is judged against the runs that
came before it. The job is deciding whether an idea is worth more of the operator's
time, not learning what the system does.

## Product Purpose

The control centre is the instrument for one question the whole repository exists to
answer: is there a rule a model can trade that clears its fees on data it has never
seen.

It composes a run configuration from ten sections, executes the model test, and
records what every setting did to the result. Success in a session is a judgement:
this configuration is dead, or it is worth another pass. The accumulated record of
those judgements is the asset, not any single run.

It is analysis only. It reads public prices and never places an order.

## Positioning

The scoreboard is the product. Most model dashboards show the current fit; this one
holds every fit ever scored, with the settings that produced it embedded in the
record, so a configuration can be replayed and a claim can be checked rather than
believed. A result that does not carry its settings is treated as a result nobody
can check.

The second commitment is that a setting must do something. Every one of the 64
settings is read by a run and its effect is named in the record, and a check fails
when a setting is saved and consumed by nothing.

## Operating Context

Served locally by Flask at `127.0.0.1:8787`, started by
`05-research/scripts/control_centre.sh`, read full width in a desktop browser.

Also exported to `01-dashboard/control-centre.html`, one self-contained file of
about 20 MB that opens from disk with no server and no network. The export drops
the Run buttons and the console, because a file cannot run a job, and renders the
settings as the values a run used. Both surfaces matter and the offline file must
read on its own.

Six panels in a fixed reading order, A1 Data, A2 Indicators, B1 Variables,
B2 Training, C1 Scoreboard, C2 Ledger. Evidence accumulates as dated records under
`04-outputs/AA-evals/`, currently around 500 scored fits.

The machine is an 8 GB Mac with the repository on an exFAT portable SSD. It swaps
under load, and several past defects were memory pressure rather than logic.

## Capabilities and Constraints

Confirmed functionality: compose a configuration across ten sections and 64
settings; run nine registered scripts, none of which can place an order; fit and
score models with three error columns, in sample, cross-validated and a blind
period scored once; calibrate probabilities; draw figures beside each record; and
list every fit ever scored.

Terminology the board uses and does not gloss: the blind period, the overfit ratio,
Theil's U2, the fold pass rate, the base rate, ATR, the triple barrier.

Constraints that future work must preserve:

- No script that can place or cancel an order is reachable from the board. Four are
  named as permanently excluded.
- A run's record embeds the configuration that produced it.
- Every setting has exactly one owner. Seven were once declared twice and none are
  now.
- Code that fits or scores a model lives in `02-runtime/trader-workflow.qmd`; a
  check compares the document against the runner character for character.
- Headings are at most three words. Explanatory notes are tooltips, not text, with
  one deliberate exception for the result verdict.
- No script or data path appears in readable text on a panel.
- A row's table and its tools occupy the same height; figures fill the shorter side,
  and what does not fit goes to one Figures block at the foot.

Undecided: whether the board should carry more than the four existing equity bar
sizes, and whether the calibration mapping should follow the winning model rather
than the first one ticked.

## Brand Commitments

Plain English throughout, in the operator's own standing instruction: everyday
words, the common word over the colourful one, no em-dashes, no colons in prose, no
aphorisms. Full technical register is required for statistics and methods, where the
metric, the estimate and the test are named precisely.

Numbers are never rounded up into a confident sentence. A verdict says what failed
as plainly as what passed.

Two palettes with different jobs, sharing their neutrals exactly. The ink, the
soft ink and the rule are #16202c, #4a5866 and #c3cedb in both the stylesheet and
the charts, so the page and a figure sit on the same ground. The accents differ on
purpose: six lane colours name a panel, cool to warm from A1 to C2, while the chart
palette names a series or a feature family, and a family keeps its colour across
every chart that draws it.

(Corrected 22 September 2026. The first draft of this file claimed one colour per
lane carried into every chart. The stylesheet declares #0b4f8a through #ea7a2c and
control_charts.py declares #0d5f8a through #a01c1c, so the claim was false, and it
was a claim written from memory rather than read off the files.)

## Evidence on Hand

Around 500 scored fits under `04-outputs/AA-evals/`, each a markdown record with a
JSON sidecar carrying its configuration.

A live paper equity account at Alpaca, about 99,000 dollars from 100,000 deposited,
running the 12-1 momentum basket weekly since 18 August 2026. It is paper money and
the switch that would make it real is off.

One strategy has cleared its costs on unseen data: 12-1 monthly momentum on US
equities. Every crypto candidate has failed, the best reaching 0.992 times a
constant guess on the blind period and still losing 0.086 per cent a trade at its
most confident.

There are no customers, no revenue and no external users. Future work must not
invent any.

## Product Principles

1. A result that does not carry its settings cannot be checked, so every record
   embeds the configuration that produced it.
2. A setting that changes nothing is a defect, not a convenience.
3. One quantity has one owner and one control.
4. The comparison is the finding. A single run is evidence only against the runs
   beside it.
5. Say what failed. A board that reads better than the evidence is worse than no
   board.

## Accessibility & Inclusion

No product-specific requirement has been established. The reading distance is a
desktop browser at full width, and the operator has asked repeatedly for less on
screen rather than more.
