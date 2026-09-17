# Panel revision tasks, 16 September 2026

Compiled from the operator's feedback on the A1 Data panel during 16 September
2026, in the order it was given, then generalised into the task list every
panel is revised against. The status table at the end says where each panel
stands at the time of writing.

## The A1 feedback, in order

1. Replace the chart strip at the top left with a concise table of the datasets
   the user can choose between: each timeframe and the trading style it serves
   (scalping, day trading, swing, position), the count of coins and stocks, the
   trading hours, and the cost of a round trip. The fee floor leads the reader
   to the next table.
2. Below it, the hard rules with the workflow's own figures: position cap,
   default size, fat pitch, label geometry, stops.
3. Adopt this structure on every page: tables of the panel's objects on the
   left, the interactive selection tools beside them on the right.
4. Titles of one or two words. "Datasets", not "Two venues, one pipeline". No
   descriptive paragraph under a title, no caption under a table.
5. Cut the "best so far" sentence by 60 per cent and rewrite it, and every
   other sentence on every panel, in clear simplified English. No opaque
   terminology anywhere.
6. Rename "Input data" to "Choose Market". Add a second tool, "Choose Basket".
7. Parse the screening rows out of the hard rules into their own table,
   "Screening", between Datasets and Hard Rules, with "Choose Filter" beside
   it. Remove the subtitles inside the tools ("Tradeable", "History",
   "Ranking", "Barrier", "Horizon").
8. Reduce wording everywhere. The board is a visual and interactive tool, not
   a reading exercise. Labels are one to five words; explanations become
   tooltips; job blurbs are one sentence.
9. A "Show all code" control at the top, as in a Quarto render. Hyperlinks to
   the data sources in the Datasets table.
10. Each tool sits in the same row as the table it acts on, at any zoom, so
    Choose Filter is beside Screening and Choose Label beside Hard Rules.
11. A read-only Trading mode box in Choose Market, to the right of Timeframe,
    with a line beneath explaining it. A line under Choose Basket, under fifteen
    words, restating the selection.
12. Explain horizon in plain words: how long a trade is held before giving up,
    counted in candles, with the bars-to-days line live.
13. "Bar size" is not a trading term; use "Timeframe". Explain every option in
    every list, including what `slice_4h_40k` is and why it exists. Rewrite
    the basket line so a newcomer can read it.
14. Under Choose Filter, define the volatility band and spell out ATR letter by
    letter; explain why volatility pairs with volume, and put the volume floor
    beside the band. Under Choose Ranking, describe each ranking signal as it
    is chosen and explain fold pass rate.
15. In the tables, the left column is one or two words and the explanation
    lives in the venue columns. Define the fee floor as the cost of a buy and
    its sell when the app places orders on Binance or Alpaca through its API
    key. Where space is short, footnote or link to a definition.
16. Move all figures out of the tables into their own block for arranging
    later, right column first, then left.
17. The preset basket must act on the coin list, not compete with it. The coin
    box must be a dropdown read from the file, never typed. Rename "Symbols"
    and "Row cap" to meaningful names ("Coins or stocks", "History to load")
    and explain candles before using the word.
18. A result chart under Choose Ranking, drawn from the selections above it,
    so the user sees the effect of what they chose.

## The general tasks, for every panel

T1  Layout. Rows that pair one plain table with the tools that act on it, in
    reading order. The chart strip, the jobs, the code and the evidence log
    follow the rows. Figures go in a block of their own.

T2  Titles. One or two words for a table. "Choose X" for every tool. No
    subtitle inside a tool, no paragraph under a title, no caption under a
    table.

T3  Tables. Left column one or two words. The explanation sits in the value
    columns, in plain words, every number with its date, every acronym spelled
    out at first use, a link where a term has a good definition elsewhere.

T4  Tools. Every option in every list has a one-line description that appears
    under the tool when it is chosen. Every box that expects a name is a
    dropdown read from the data, never typed. Every numeric box is explained
    in the tool's note: what the number is, its unit, a sensible range, and
    what happens at each end. Where it helps, a live line restates the
    selection in plain words.

T5  Result. A chart under the tools drawn from the current settings, so the
    user sees what the choices do.

T6  Terms. The market's own words, not invented ones: timeframe, candle,
    take-profit, stop. Internal prefixes such as `f_btc_` are explained beside
    their first use.

T7  Links. Data sources and definitions are hyperlinked.

T8  Jobs. A title of two or three words, one sentence of blurb, knob labels of
    one to four words with the explanation as a tooltip.

T9  Checks. One acceptance check per panel asserting the rows, the tools, the
    notes and the result chart, so a regression cannot pass unnoticed.

## Status at the time of writing

| Panel | T1 rows | T2 titles | T3 tables | T4 tools | T5 result | T6 terms | T7 links | T8 jobs | T9 check |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 Data | done | done | done | done | done | done | done | done | done |
| A2 Indicators | done | done | done | done: options and columns described | done | done | done | done | done, check 18 |
| B1 Variables | done | done | done | done: options described | done | done | done | done | done, check 18 |
| B2 Training | done | done | done | done: options described | done | done | none needed | done | done, check 18 |
| C1 Scoreboard | done | done | done | done: options described | done | done | done | done | done, check 18 |
| C2 Ledger | done | done | done | done: options described | done | done | none needed | done | done, check 18 |

Check 18 in `03-inputs/control_eval.py` asserts T1, T4 and T5 on every panel.
Also done on 16 September: table blocks stretch to the height of the tools
beside them (operator instruction from A2), and pages are served with a
no-cache header so a redesign is never hidden by a cached copy. Still to do: a
pass on the front-page cards, whose leads and tags predate this list, and the
placing of the A1 figures into the gaps.
