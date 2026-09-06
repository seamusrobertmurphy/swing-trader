"""Track A: survivorship stress for the surviving 12-1 momentum result.

The Alpaca panel holds live names only, and delisted momentum-crash victims
would flatter the winner decile, so the SURVIVES verdict cannot stand on this
panel alone. Three attacks, fixed before the run:

  A  liquidity tiers   rerun the identical test on only the top-500 (and
                       top-1000) names by trailing dollar volume at each
                       formation date. Large liquid names rarely delist, so if
                       the spread lives there, missing delistings are not the
                       driver. Same 60% fold bars.
  B  adversarial injection   poison the top decile: each month a fixed share of
                       its names is forcibly assigned a delisting return, -30%
                       (Shumway's exchange estimate) and -55% (his OTC
                       estimate), at monthly rates 0.25%, 0.5%, 1% of positions
                       (about 3%, 6%, 12% annualized, brackets the real US
                       delisting rate). The edge must keep a positive spread
                       and t >= 2 under the plausible cells.
  C  literature anchor  the published CRSP (delisting-complete) 12-1 top-decile
                       premium over the market is roughly 0.5-0.8%/month long-
                       only. Our +1.08 should sit near or above that range, not
                       far above it; a large excess would itself be a bias flag.

    .venv/bin/python inputs/equity_survivorship_stress.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from equity_momentum_monthly import (COST, MIN_DOLLAR_VOL, MIN_HISTORY, MIN_NAMES,
                                     MIN_PRICE, SIGNALS, TOP_FRAC,
                                     fold_verdict, monthly_panel)

INJECT_RATES = (0.0025, 0.005, 0.01)
DELIST_RETURNS = (-0.30, -0.55)
SEED = 20260818


def run(px, dv_med, month_ends, top_liq=None, inject_rate=0.0, delist_ret=-0.30, rng=None):
    sig = SIGNALS["mom_12_1"](px)
    hist_ok = px.notna().rolling(MIN_HISTORY, min_periods=MIN_HISTORY).count() >= MIN_HISTORY
    rows = []
    for i in range(len(month_ends) - 1):
        t0, t1 = month_ends[i], month_ends[i + 1]
        elig = (hist_ok.loc[t0] & (px.loc[t0] >= MIN_PRICE)
                & (dv_med.loc[t0] >= MIN_DOLLAR_VOL) & sig.loc[t0].notna())
        names = elig[elig].index
        if top_liq is not None and len(names) > top_liq:
            names = dv_med.loc[t0, names].nlargest(top_liq).index
        if len(names) < MIN_NAMES:
            continue
        s = sig.loc[t0, names]
        top = s[s.rank(pct=True) > (1 - TOP_FRAC)].index
        fwd = px.loc[t1, names] / px.loc[t0, names] - 1.0
        top_fwd = fwd.loc[top].copy()
        if inject_rate > 0 and len(top_fwd):
            k = int(np.ceil(inject_rate * len(top_fwd)))
            victims = rng.choice(top_fwd.index, size=min(k, len(top_fwd)), replace=False)
            top_fwd.loc[victims] = delist_ret
        rows.append(dict(month=t1, n=len(names), n_top=len(top),
                         top=float(top_fwd.mean()) - COST,
                         mkt=float(fwd.mean()) - COST))
    m = pd.DataFrame(rows).set_index("month")
    m["spread"] = m["top"] - m["mkt"]
    return m


def main():
    px, dv, dv_med = monthly_panel()
    month_ends = px.groupby(px.index.to_period("M")).apply(lambda g: g.index.max()).to_list()

    print("\nPANEL A  liquidity tiers (same 60% fold bars)")
    rows = []
    for tier, label in ((None, "full panel"), (1000, "top-1000 liq"), (500, "top-500 liq")):
        m = run(px, dv_med, month_ends, top_liq=tier)
        v = fold_verdict(m)
        rows.append(dict(universe=label, months=len(m),
                         top=round(float(m["top"].mean()) * 100, 3),
                         mkt=round(float(m["mkt"].mean()) * 100, 3),
                         spread=round(v["mean_spread"] * 100, 3),
                         tstat=round(v["tstat"], 2),
                         abs_rate=f"{v['abs_rate']:.0%}", sel_rate=f"{v['sel_rate']:.0%}",
                         verdict="SURVIVES" if v["survives"] else "KILLED"))
    pd.set_option("display.width", 200)
    print(pd.DataFrame(rows).to_string(index=False))

    print("\nPANEL B  adversarial delisting injection into the TOP decile (full panel)")
    rows = []
    for dr in DELIST_RETURNS:
        for rate in INJECT_RATES:
            rng = np.random.default_rng(SEED)
            m = run(px, dv_med, month_ends, inject_rate=rate, delist_ret=dr, rng=rng)
            v = fold_verdict(m)
            rows.append(dict(delist_ret=f"{dr:.0%}", monthly_rate=f"{rate:.2%}",
                             annualized=f"{rate * 12:.0%}",
                             spread=round(v["mean_spread"] * 100, 3),
                             tstat=round(v["tstat"], 2),
                             sel_rate=f"{v['sel_rate']:.0%}",
                             holds="YES" if (v["mean_spread"] > 0 and v["tstat"] >= 2) else "no"))
    print(pd.DataFrame(rows).to_string(index=False))

    print("\nPANEL C  literature anchor: CRSP delisting-complete 12-1 long-only premium is "
          "roughly +0.5 to +0.8%/month over the market;")
    print("compare the full-panel spread above. Far above that range would itself flag bias.")


if __name__ == "__main__":
    main()
