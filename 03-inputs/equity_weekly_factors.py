"""Track A: pre-registered WEEKLY-cadence factors, non-overlapping weekly holds.

The operator wants shorter trades. Crypto's answer was unambiguous (shorter
frames die on a 15-20bp fee wall), but equities cost basis points, so the
question is honestly open and this test answers it the same way the monthly one
was answered: signals fixed a priori, non-overlapping holds, the 60% fold bars,
and the full-turnover cost bound now charged EVERY WEEK (0.05%/rebalance, a
~2.6%/year worst-case drag against monthly's ~0.6%).

Pre-registered signals:
  mom_12_1    the surviving formation, rebalanced weekly instead of monthly
  rev_5d      canonical 1-week short-term reversal (buy last week's losers)
  rev_21d     canonical 1-month reversal

A weekly cadence that survives would also quadruple the execution-verdict rate
on the paper book (four cycles by late September instead of one).

    .venv/bin/python inputs/equity_weekly_factors.py
"""
from __future__ import annotations

import pandas as pd

from equity_momentum_monthly import (SIGNALS, fold_verdict, monthly_panel,
                                     run_signal)

WEEKLY_SIGNALS = {
    "mom_12_1_wk": SIGNALS["mom_12_1"],
    "rev_5d": lambda px: -(px / px.shift(5) - 1.0),
    "rev_21d": lambda px: -(px / px.shift(21) - 1.0),
}


def main():
    px, dv, dv_med = monthly_panel()
    week_ends = px.groupby(px.index.to_period("W")).apply(lambda g: g.index.max()).to_list()
    print(f"\nweek-ends: {len(week_ends)}  cost 0.05%/rebalance (full-turnover bound, "
          f"weekly)  top 10% at 50-name floor\n")
    rows = []
    for name, fn in WEEKLY_SIGNALS.items():
        m = run_signal(name, fn, px, dv_med, week_ends)
        v = fold_verdict(m)
        rows.append(dict(signal=name, weeks=len(m),
                         mean_top=round(float(m["top"].mean()) * 100, 3),
                         mean_mkt=round(float(m["mkt"].mean()) * 100, 3),
                         spread=round(v["mean_spread"] * 100, 3),
                         hit=round(v["hit"], 2), tstat=round(v["tstat"], 2),
                         abs_rate=f"{v['abs_rate']:.0%}", sel_rate=f"{v['sel_rate']:.0%}",
                         verdict="SURVIVES" if v["survives"] else "KILLED"))
    pd.set_option("display.width", 200)
    print("=" * 100)
    print("WEEKLY FACTOR TEST, non-overlapping weekly holds, after 0.05%/rebalance. "
          "%/week columns. Bars: abs and sel >= 60% of half-year folds.")
    print("=" * 100)
    print(pd.DataFrame(rows).to_string(index=False))
    print("\nsurvivorship caveat: live names only; upper bounds throughout.")


if __name__ == "__main__":
    main()
