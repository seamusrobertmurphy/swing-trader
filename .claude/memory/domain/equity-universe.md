# Equity universe

- 2026-08-25: Alpaca files every ETF, ETN and leveraged fund under
  `AssetClass.US_EQUITY`, so `inputs/alpaca_data.py universe` returns them
  alongside operating companies. Of the 2,673 names passing the $20M
  dollar-volume screen, 659 are pooled funds and 162 are leveraged or inverse.
  Matters because a momentum rank promotes leveraged funds mechanically: a 3x
  fund carries about three times its sector's trailing twelve-month return.
  The first live book (2026-08-18) consequently held SOXL, KORU and MUU,
  breaking the charter's never-margin rule. Filter is
  `inputs/equity_universe_filter.py`, cached to
  `inputs/alpaca-data/asset_classes.json`; `alpaca_trade.UNIVERSE_EXCLUDE`
  is set to `"funds"`.

- 2026-08-25: Classification is by registered product name because Alpaca's
  `Asset` object carries no ETF flag. Bare "Trust", "Fund" and "Portfolio" are
  NOT sufficient on their own: equity REITs and several banks are legally
  trusts, and an earlier pattern wrongly excluded Vornado Realty Trust, Camden
  Property Trust, Northern Trust Corporation and Digital Realty Trust. The
  rule now requires an issuer or explicit-vehicle marker, or a bare marker with
  no operating-company marker present. Re-verify this list after any pattern
  edit.

- 2026-08-25: Excluding all pooled funds does NOT cost the 12-1 momentum edge.
  Re-running the pre-registered monthly harness across three universes gave
  SURVIVES in all three, and the fund-free version is marginally stronger
  (+1.132%/month, t 2.59, against +1.082%, t 2.53 as deployed). Selection fold
  rate falls 79% to 74%, still over the 60% bar. Record:
  `outputs/AA-evals/2026-08-25/fund-exclusion-momentum-20260825.md`.
