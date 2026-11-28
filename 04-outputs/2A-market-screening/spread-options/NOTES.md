# Spread visualisation options

Four ways to see the screen's spread gate, all built from the same screen run
(`2A-sample_20260620.csv`, 28 coins). Pick one (or two) to fold into the controls
notebook. Regenerate with `python build_spread_options.py`.

The gate itself: a coin is rejected if its top-of-book spread is above 0.05%, because
the spread is a hidden cost paid every time you trade, and we want it well under the
fee.

## Option 1 - Sorted bars vs the ceiling
`option-1-sorted-bars.png`

Each coin's spread as a bar, sorted, green if it clears the 0.05% ceiling, red if not.
- Strength: dead simple, the familiar view, tells you at a glance who passes.
- Weakness: the very tight spreads (BTC, ETH) are almost invisible near zero, and it
  says nothing about *why* a coin's spread is wide.

## Option 2 - Spread vs liquidity (scatter)
`option-2-spread-vs-liquidity.png`

Spread against 24-hour volume, both on log axes, coloured by whether the spread clears.
- Strength: the most insight. It shows the relationship that justifies the gate at all:
  spreads tighten as volume rises, so the wide-spread rejects (top-left) are the same
  thin coins the liquidity floor is already wary of. The spread ceiling and the
  liquidity floor are two views of one idea.
- Weakness: a scatter takes a moment longer to read, and needs the log axes to work.

## Option 3 - Spread as a cost on top of the fee
`option-3-cost-stack.png`

Each coin's total cost to round-trip, stacked: the fixed 0.20% fee-plus-slippage base in
navy, then the spread added on top (green if within the gate, red if it pushes the total
past the budget line at 0.25%).
- Strength: the most decision-relevant. It makes the spread concrete as money, shows the
  full cost of trading each coin, and ties directly to the net-edge fence (a trade has
  to clear all of this before it earns anything).
- Weakness: the constant fee base takes up most of the height, so the spread differences
  read as a thin band on top.

## Option 4 - Spread (cost) vs ATR (opportunity)
`option-4-cost-vs-atr.png`

Spread (the cost to enter, log axis) against daily ATR% (the typical move, the
opportunity), with the ATR band and the spread ceiling drawn in.
- Strength: connects two gates in one picture - it asks whether a coin moves enough to
  be worth its spread, which is the whole logic of the screen in a single chart.
- Weakness: showing two gates at once is busier; better once you already understand each
  gate on its own.

## Suggestion

For *understanding* the gate, Option 2 is the clearest. For *deciding*, Option 3 makes
the cost real and lines up with the net-edge fence. If you want one in the notebook, I'd
lean Option 3 as the main spread view with Option 2 as a companion, but they're laid out
here so you can judge for yourself.
