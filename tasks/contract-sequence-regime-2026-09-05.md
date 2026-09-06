# Contract, sequence regime models

Agreed 5 September 2026 with Seamus, before any code. Written under the
`assumptions-test` protocol. Nothing is built until this is confirmed.

## Problem

Supertrend loses money in sideways markets, because a market that saws across
its line keeps firing entries and every entry pays a fee. Monte Carlo on the
4-hour Supertrend baseline returned a 99.7 per cent chance of loss over ten
thousand simulations, and the indicator's own author says it bleeds below the
4-hour frame and holds up above it. Seven models have already tried to predict
direction on this panel and all seven landed between 0.50 and 0.55 area under
the curve, where 0.50 is a coin flip.

The open question is therefore not whether a bigger model predicts direction.
It is whether a sequence model can predict how long a trend will last, well
enough to tell Supertrend when to stand down.

## User

Seamus, sole operator, reading the result cold. Outcome first, then the number,
then what it costs. The result that matters is money after fees, not a metrics
table.

## Success

Supertrend with the network's gate beats Supertrend without it, out of sample,
after fees, on at least 60 per cent of half-year folds, on both panels. The
test is the existing kill harness in `inputs/mst_gate_walkforward.py`, the one
that already falsified four candidates. Fees are 15 basis points on crypto,
the achievable rate in `ACHIEVABLE_COST_PCT`, and the measured 7 to 9 basis
points on equities.

A model that predicts regime beautifully and does not move that number has
failed.

## In scope

1. A sequence training rig in PyTorch on the M1 graphics chip through Metal,
   covering LSTM, GRU and a temporal convolution, with the architecture a
   parameter rather than three separate scripts.
2. A sliding-window dataset built as a strided view over the flat panel, never
   a materialised three-dimensional tensor, because the obvious construction
   is 94 GB on a machine with 8.
3. Two swappable labels, scored side by side rather than chosen in advance.
   The first is bars until the Supertrend flips, a regression target countable
   from history with no judgement call. The second is whether that Supertrend
   trade paid after fees, the meta-label of Lopez de Prado.
4. Walk-forward splits with purge and embargo, reusing `inputs/wf_splitter.py`
   rather than writing new splitting code.
5. Hyperparameter tuning scored on the training window only, with the blind
   final year never touched, following the pattern already in
   `model_assessment_1h.tune`.
6. An after-fee scoreboard that ends in the gated Supertrend economics, not in
   accuracy.
7. Both panels. Crypto 4-hour, 3.9 million rows across 567 coins, and equity
   daily, 5.0 million rows across 2,547 names. Both already carry the
   Supertrend and regime feature families, so no new indicator work is needed
   to start.

## Out of scope

Transformers, attention models, pretrained or foundation models, and
fine-tuning anything downloaded. Ruled out by the operator. Eight gigabytes of
shared memory cannot train them, and size is not what is missing here.

## Constraints

- Apple M1, 8 cores, 8 GB shared between processor and graphics chip, roughly
  2 GB free in practice. Every design choice follows from this.
- PyTorch is not installed. MacPorts carries `py312-pytorch @2.12.0`, but the
  project virtual environment was built with `include-system-site-packages =
  false`, so a MacPorts install would be invisible to it. Resolve before build.
- The crypto 4-hour panel stops at 21 June 2026 and the equity panel at
  20 July 2026, so both are stale. A refresh took most of a day last time.
- The repository sits on an exFAT volume, which scatters AppleDouble files that
  break matplotlib on import. Sweep before any figure is drawn.
- The baseline to beat is not zero. It is ungated Supertrend, and separately
  the hand-built regime features already in `build_dataset_1h.regime_block`
  and the Kaufman efficiency gate in the adaptive Supertrend.
- Runs natively. No Docker, no per-task environment, per CLAUDE.md.

## Smallest version

One architecture, one label, one panel, one coin family, run end to end into
the economic scoreboard. The point is to prove the pipe carries water before
anything is swept across it. If the smallest version cannot produce an
after-fee number, the sweep would only produce many wrong ones faster.

## Assumptions

Every one of these is mine and needs confirming or correcting.

1. The model never places an order. This build writes predictions and
   scoreboard records only, and wiring it to money is a separate step that
   gets its own approval. The operator did not exclude this, so I am assuming
   it rather than inferring agreement.
2. The model never outputs direction and never picks what to buy. Direction
   stays with the 12-1 momentum rule that survived. Also not excluded by the
   operator, also an assumption.
3. Training uses the feature columns already in the panels, which passed a
   leakage audit, rather than new indicator families.
4. Sequence length starts at 64 bars and is a swept parameter.
5. Existing split, embargo and scoreboard code is reused rather than rewritten.
6. Stale panels are acceptable while proving the pipe, and get refreshed before
   any number is reported as a verdict.
7. Training runs on this machine, not in the cloud.

## Open questions

1. Refresh the panels first, or prove the pipe on stale data and refresh before
   the verdict? The second is faster to a first result.
2. In the equity arm, does the gate sit on Supertrend, or on the momentum book
   that actually trades? Supertrend on equities is computed but has never been
   traded, so gating it answers a question about an untraded strategy.
3. How large a tuning budget, in hours, before a result is called?
