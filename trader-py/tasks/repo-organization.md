# Repo organization plan (living document)

Started 2026-06-20. A deliberate, iterative reorganization of trader-py around the
three-chapter architecture. Do this as passes across sessions, not one sweep.
Discuss before creating new folders. The structure only becomes clear over time.

## Sequencing

Organize Chapter Two first, the scripts and outputs of its computational modules,
then Chapter Three. Chapter One is already organized (`1A-macd`, `1B-confluence`,
`1C-fibonacci`, `AA-journal`). This task is about the technical-computation modules
and where their scripts and outputs live; the descriptive and design material in
each chapter stays in that chapter's document, not in the output folders.

## The three-chapter spine

- Chapter One, metrics: measure the market. Already organized.
- Chapter Two, controls: decide what is tradable and bound the bet.
- Chapter Three, execution: prove the strategy, then run it.

## Working model: notebooks and module copies

Each chapter has one operational notebook that runs the full workflow click-and-go:
Chapter One `01-trader-metrics.ipynb`, Chapter Two `02-trader-controls.ipynb`, Chapter Three a
notebook still to come that will be named `03-trader-execution`. The notebook is canonical and keeps every function; nothing
is extracted out of it. Each computational module ALSO lives as a standalone copy in
its own output subfolder, a small runnable script you can develop and edit in
isolation without running the whole notebook. Refinements made there are integrated
back into the notebook, so the subfolder scripts are a workbench, not an import the
notebook depends on. Chapter One already works this way: `1A-macd` pairs a standalone
`macd.py` with the integrated notebook.

## Priority 1: organize Chapter Two

Chapter Two's computation currently all lives inside `02-trader-controls.ipynb`. The goal
is to give each computational module a clear home (mirroring Chapter One's lab
folders) and to route its outputs into the format folders with module-prefixed
names, so each metric's scripts and artifacts are easy to find.

### The computational modules (organize these)

2A Universe selection, the four-gate screen.
- Computes: liquidity (24h quote volume), the ATR band, spread, history sufficiency;
  pass or fail per coin.
- Functions today: `screen_coin`, `run_screen`.
- Outputs: the dated candidate table (`Candidates_YYYYMMDD.csv`) and the screen
  scatter chart (the four-gate / screen PNG).

2B ATR volatility band.
- Computes: ATR(14) as a percent of price; the floor and ceiling band; the live-
  guardrail view over time.
- Functions today: `compute_atr_pct`, `atr_band_figure`.
- Outputs: the ATR band chart per coin. Also feeds 2A (the band gate) and 2C (sizing).

2C Position sizing.
- Computes: ATR-scaled, constant-dollar-risk size; the per-position cap; the
  minimum-notional floor.
- Function today: `position_plan`.
- Outputs: the sizing table (CSV) and the sizing chart (PNG) for the passing
  candidates.

2D Net-edge fee fence (this is defence two).
- Computes: net expected move = estimated move minus round-trip fee minus slippage;
  refuse unless it clears the floor; plus the exit-coupling checks.
- Functions today: `net_edge`, `net_edge_ok`, `validate_exit_coupling`.
- Outputs: the fence-check report.

Trades-per-day cap (defence one). A CONFIG control, not a computation; enforced in
code. Small; document it alongside the CONFIG block.

### How the three stacked defences map

The three defences are a principle realized across modules, not a single unit, so do
not build them as one thing: defence one is the trades-per-day cap (a CONFIG
control), defence two is the net-edge floor (module 2D), and defence three is out-of-
sample validation (Chapter Three's walk-forward). Document the framing in the chapter
document; the code lives in 2D plus the cap plus Chapter Three.

### Proposed Chapter Two layout

- The notebook stays canonical: `02-trader-controls.ipynb` keeps every function and the
  full click-and-go workflow. Nothing is extracted out of it.
- Each module also gets a standalone copy in its own subfolder, for example
  `outputs/2A-universe-screen`, `outputs/2B-atr-band`, `outputs/2C-position-sizing`,
  `outputs/2D-edge-fence`, each holding a runnable script and a short NOTES.md. These
  are the development workbench: run and edit one module in isolation, then integrate
  the refinement back into the notebook.
- Outputs: pool into the format folders (`CSV`, `HTML`, `PNG`) with module-prefixed
  filenames, for example `2A-candidates_DATE.csv`, `2A-screen_DATE.png`,
  `2B-atr-band_BTC.png`, `2C-sizing_DATE.csv` and `.png`.

### Chapter Two: descriptive content (leave in the chapter document)

Fences over guardrails, the two-venue fence sets, the operator cadence, the swing
hold-period character, the operator-owned CONFIG principle, and the Karpathy
separation. These are design and governance, not computation, so they belong in
`02-trader-controls.md` and the chapter document, not in an output module.

## Priority 2: organize Chapter Three

Same treatment: name each member of the validation stream, its script, and its
outputs. Chapter Three is a sequence of tests; `experiment_log.csv` is the shared
ledger that records every run, one line each.

3A Walk-forward backtest (name under review).
- The exit simulator plus the rolling, out-of-sample backtest.
- Script: `inputs/walkforward.py`. Outputs: `walkforward_results.md`,
  `walkforward_trades.csv`, `experiment_log.csv`.
- Name candidates to decide between: "Walk-Forward Validation", "Out-of-Sample
  Backtest", "Rolling Validation", "Evidence Harness". (You flagged you may not like
  "walk-forward backtest".)

3B Model pipeline (the original machine-learning model).
- Builds the 17-feature dataset and trains and scores the classifier. It underpins
  the architecture, but its question, does a trained model have edge, is a Chapter
  Three question.
- Scripts: `inputs/build_dataset.py`, `inputs/train_model.py`. Outputs:
  `dataset.csv`, `model.joblib`, `model_metrics.txt`.

3C Entry-threshold sweeps (to build).
- Tune the vote threshold and entry selectivity (2-of-4 versus 3-of-4, trend and
  higher-timeframe confirmation) with fees inside the objective.
- Outputs: `experiment_log` rows plus a comparison table.

3D Exit-geometry sweeps (to build).
- Sweep `stop_atr_mult` and `take_profit_pct` together, the diagnosed leak, to find
  any pair that clears both baselines.
- Built on top of `walkforward.py`. Outputs: `experiment_log` rows plus a results
  table or heatmap.

3E Stability checks (to build).
- Parameter stability, regime-segmented results, randomized-entry (coin-flip) and
  buy-and-hold baselines, and an optional Monte Carlo or bootstrap on trade returns.
- Outputs: a stability report.

Tail of Chapter Three, after the stream clears: paper trading (Alpaca paper, Binance
testnet), then a tiny live allocation. Not a computation module; the execution
endpoint.

### Proposed Chapter Three layout

- Same pattern as the other chapters: one operational notebook holds the full
  click-and-go workflow (a Chapter Three notebook to create, the execution
  counterpart of `01-trader-metrics` and `02-trader-controls`), with each module also copied into
  its own subfolder (`3A`, `3B`, and so on) as a standalone, editable script. The
  current Chapter Three code (`inputs/walkforward.py`, `inputs/build_dataset.py`,
  `inputs/train_model.py`) already serves as those standalone module copies; they
  fold into the notebook as the chapter matures.
- `experiment_log.csv` is the shared results ledger across 3A, 3C, and 3D.
- Outputs: format folders with `3`-prefixed names; group the validation reports
  (the `.md` files) together.

## Pending reorganization actions (reordered: Chapter Two first)

Chapter Two (do first):
- Give 2A through 2D a standalone copy in their module folders (the notebook stays
  canonical and click-and-go); route their outputs into `CSV`/`HTML`/`PNG` with
  module-prefixed names.
- Document the trades-per-day cap with the CONFIG and the three-defences framing.

Chapter Three (do second):
- Settle 3A's name. Group 3A and 3B as the existing validation work; scaffold 3C, 3D,
  and 3E as the tests still to build.
- Relocate the ML pipeline and its artifacts (3B) beside the walk-forward outputs.

Carryover housekeeping (any pass):
- Move the `1B-confluence` stragglers into `HTML/` and `PNG/`.
- Decide whether the journal HTML set stays in `1X-journal/`.
- Remove the duplicate document exports at the root versus the `01/`/`02/` chapter
  folders.
- Fix the README attribution: the AUC ~0.51 result is the ML model (Chapter Three),
  not Chapter One.
- Naming: the strategy is swing, not day. Decide `01-trader-...` or `01-swing-...`.
- Fix broken image paths from the reorg, for example
  `outputs/PNG.divergence_matrix.png` should be `outputs/PNG/divergence_matrix.png`.

## Process

Check before creating any new folder. Place files in existing folders where
possible. Do the reorg as deliberate passes, revisiting periodically as the picture
clears.
