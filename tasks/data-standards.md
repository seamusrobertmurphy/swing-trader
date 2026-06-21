# Data standards (hard rules) -- crypto training data

Sourced by Seamus 2026-06-21 ("Phase 2: Data Infrastructure" guidelines) and adopted as
hard rules going forward. Enforced in code where marked.

## Rules

1. **Interval.** OHLCV at 1-hour bars.
   Enforced: `flow_data.py --interval 1h`; `build_dataset_1h.py`.

2. **Historical depth and the split.** Download and use the LONGEST history available per
   coin (BTC back to 2017, ~8.5 years); history is never truncated. The "2 years training,
   1 year out-of-sample" figures are MINIMUMS, not caps. The split holds out the final ~1
   year (or more) as out-of-sample and trains on ALL prior history -- seven-plus years for
   the established coins -- with an embargo straddling the cut so neither side peeks. To be
   included, a coin must clear the floor: at least ~2 years usable before the cut and ~1
   year after. Enforced at the split: `train_model.py` 1h path (task 9). The download
   (`flow_data.py --all-market`, default start 2017-08) already pulls the full depth.

3. **Exchange-grade, low-gap data; not free APIs with gaps.** Primary source is Binance's
   official data.binance.vision archives (exchange-direct, deterministic, and they carry the
   taker-buy flow ccxt drops). ccxt is a fallback/top-up for the still-forming current bar
   only, never the primary feed. Every coin passes a data-quality gate before it enters
   training: at most 2% of expected hourly bars missing and no single gap longer than 72
   hours; coins that fail are excluded (our features assume regularly spaced hourly bars).
   Enforced: `build_dataset_1h.py` -> `DATA_QUALITY`, `gap_stats`, `passes_quality`.

4. **Reproducible and offline.** The dataset builds from the stored archives, not a live
   network call, so any build is repeatable.
   Enforced: `build_dataset_1h.py` reads `inputs/binance-data/klines_1h/`.

## Compliance snapshot (2026-06-21)

- 1h interval: met.
- Depth: full history is downloading now (BTC back to 2017); >= 3 years available for the
  established coins. Newer coins contribute shorter point-in-time histories, which the
  screen and the per-coin history gate handle.
- Exchange-grade: met, and stronger than the guideline asks (see note below). Gap gate is
  now in the build.
- 2-year train / 1-year OOS split: to be enforced in the train_model 1h adaptation (task 9).

## Note on the guideline's code snippet

The snippet fetches via ccxt and states ccxt is "acceptable for learning." We went further:
the primary source is the official binance.vision archives, which are exchange-direct and
gap-checked, so we satisfy rule 3 more fully than the snippet does. ccxt stays wired as the
live top-up/fallback, exactly the role the snippet uses it for.
