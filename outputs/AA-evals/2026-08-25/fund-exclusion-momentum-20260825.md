# Leveraged funds in the momentum universe

Run 2026-08-25. Harness `inputs/equity_momentum_monthly.py` (pre-registered,
unchanged except for the new `--exclude` switch). Raw console output alongside
this file as `fund-exclusion-momentum-20260825.txt`.

## What prompted it

The live paper book opened 2026-08-18 held `SOXL` (Direxion Daily Semiconductor
Bull 3X ETF), `KORU` (Direxion Daily MSCI South Korea Bull 3X ETF) and `MUU`
(Direxion Daily MU Bull 2X ETF), verified against the venue's own asset records
on 2026-08-25. Two separate problems:

1. Charter conflict. The hard rules forbid margin and leveraged vehicles. A 3x
   daily ETF is embedded leverage.
2. Selection artifact. A 3x fund carries roughly three times its sector's
   trailing twelve-month return, so a momentum rank promotes leveraged funds
   mechanically. The question this test answers is whether the first SURVIVES
   verdict was partly bought with that leverage.

Cause: `inputs/alpaca_data.py` enumerates `AssetClass.US_EQUITY`, under which
Alpaca files every ETF and ETN, and nothing downstream filtered them.

## Classification

`inputs/equity_universe_filter.py`, cached to
`inputs/alpaca-data/asset_classes.json`. Alpaca's `Asset` carries no ETF flag,
so classification is by registered product name, with issuer markers and
explicit vehicle markers taken as decisive, and bare "Trust"/"Fund"/"Portfolio"
taken as a fund marker only when no operating-company marker is present. That
last rule exists because equity REITs and several banks are legally trusts;
before it, `Vornado Realty Trust`, `Camden Property Trust`, `Northern Trust
Corporation`, `Digital Realty Trust` and eight others were wrongly excluded.
Verified clean after the fix.

Of 14,265 active US-equity assets: 5,908 funds, 905 leveraged or inverse.
Of the 2,673 names passing the $20M dollar-volume screen: 659 funds, 162
leveraged, 2,014 operating companies.

## Result

12-1 momentum, non-overlapping monthly holds, 115 months, 0.05%/month
full-turnover cost, top decile at a 50-name floor. Bars: absolute and selection
positive in at least 60% of half-year folds.

| Universe | spread %/mo | t | abs folds | sel folds | Verdict |
| --- | --- | --- | --- | --- | --- |
| `none`, as deployed | +1.082 | 2.53 | 89% | 79% | SURVIVES |
| `levered`, 162 dropped | +1.045 | 2.59 | 89% | 74% | SURVIVES |
| `funds`, 659 dropped | +1.132 | 2.59 | 84% | 74% | SURVIVES |

Controls behave: `mom_6_1` and `low_vol` are KILLED under all three universes,
as they were on 2026-08-18, so the harness has not been loosened.

## Verdict

The edge is not a leverage artifact. Removing every pooled fund leaves it
marginally stronger on the spread and the t-statistic. The honest caveat is
that the selection fold rate falls from 79% to 74%, still clear of the 60% bar
but five of nineteen folds now have the picks losing to the market.

Acted on: `UNIVERSE_EXCLUDE = "funds"` in `inputs/alpaca_trade.py`, so the
target list at the next rebalance contains operating companies only.

Survivorship caveat unchanged: live names only, every number an upper bound.
