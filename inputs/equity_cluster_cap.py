"""Track A: the correlation-cluster cap, and the test of what it costs the edge.

Principle 7 of the charter: compute a 60-day pairwise correlation matrix over
holdings, and cap the aggregate weight of any cluster with rho > 0.7 at 20% of
equity. The live momentum book has never enforced this. The 2026-08-18 book put
roughly 64% of equity into one semiconductor / memory / optics cluster, which
is how a -0.20% week for SPY became a -6.25% week for the book.

The cap cannot simply be switched on, because momentum concentrates BY
CONSTRUCTION: last year's winners are last year's winning theme. Capping the
cluster may be removing the factor rather than de-risking it. So this module
does two things: it provides the admission rule the live book will use, and it
re-runs the pre-registered monthly test with that rule applied, so the cost to
the edge is measured before anything is deployed.

Admission rule (deliberately local, not transitive). Walk the ranked names best
first; admit a candidate only if the weight already admitted that correlates
above RHO with it, plus the candidate's own weight, stays within CAP. Single-
linkage connected components would chain across the whole market in a
risk-on tape and cap everything; this cannot.

    .venv/bin/python inputs/equity_cluster_cap.py --exclude funds
    .venv/bin/python inputs/equity_cluster_cap.py --exclude funds --cap 0.30
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from equity_momentum_monthly import (COST, MIN_DOLLAR_VOL, MIN_HISTORY,
                                     MIN_NAMES, MIN_PRICE, SIGNALS,
                                     TOP_FRAC, fold_verdict, monthly_panel)

RHO = 0.70          # charter: clusters are pairs correlating above this
CAP = 0.20          # charter: aggregate cluster weight ceiling, share of equity
CORR_WINDOW = 60    # charter: 60-day pairwise correlation
INVESTED = 0.90     # book is 90% invested behind the 10% cash floor


def admit(ranked: list, corr: pd.DataFrame, n_target: int,
          cap: float = CAP, rho: float = RHO,
          invested: float = INVESTED, symmetric: bool = True) -> list:
    """Best-first admission under the local cluster cap. Returns held names.

    Each admitted name carries weight INVESTED / n_target, so the cap is
    expressed in names: a cluster may hold at most floor(cap / weight) of them.

    SYMMETRY (fixed 2026-08-26). The original rule tested only the candidate's
    links back to names already admitted, and never re-tested those earlier
    names as later correlates arrived. A name admitted early therefore
    accumulated an unbounded neighbourhood: measured on the live book of
    2026-08-26, ASX finished with 36.0% of equity correlating above rho with
    it, and ten of the fifty holdings sat over a cap of 20%. The cap was not
    being enforced, only the appearance of it. `symmetric=True` admits a
    candidate only when neither the candidate NOR any name it links to exceeds
    the cap afterwards, which bounds every holding's neighbourhood by
    construction. `symmetric=False` preserves the original behaviour for
    comparison.
    """
    weight = invested / n_target
    held: list = []
    neigh: dict = {}           # held name -> count of held names correlating > rho
    for sym in ranked:
        if len(held) >= n_target:
            break
        if sym not in corr.index:
            continue
        linked = [h for h in held if h in corr.index
                  and corr.at[sym, h] > rho]
        if (len(linked) + 1) * weight > cap + 1e-12:
            continue
        if symmetric and any((neigh[h] + 2) * weight > cap + 1e-12 for h in linked):
            continue
        held.append(sym)
        neigh[sym] = len(linked)
        for h in linked:
            neigh[h] += 1
    return held


def largest_cluster(held: list, corr: pd.DataFrame, rho: float = RHO) -> int:
    """Diagnostic: biggest connected component among the held names."""
    idx = [h for h in held if h in corr.index]
    if not idx:
        return 0
    adj = (corr.loc[idx, idx] > rho)
    seen, best = set(), 0
    for s in idx:
        if s in seen:
            continue
        stack, comp = [s], set()
        while stack:
            x = stack.pop()
            if x in comp:
                continue
            comp.add(x)
            stack += [y for y in idx if adj.at[x, y] and y not in comp]
        seen |= comp
        best = max(best, len(comp))
    return best


def run(px, dv_med, month_ends, capped: bool, cap: float, rho: float,
        top_liq: int = 0, n_names: int = 0, invested: float = INVESTED,
        symmetric: bool = True):
    """top_liq / n_names mirror the LIVE book when set (500-name liquidity tier,
    50 holdings at 1.8% each) rather than the decile construction of the
    pre-registered test. The distinction matters: at 120 names and 0.75% each a
    20% cap permits 26 per cluster and barely binds; at 50 names and 1.8% each
    it permits 11 and binds hard."""
    sig = SIGNALS["mom_12_1"](px)
    ret = np.log(px).diff()
    hist_ok = px.notna().rolling(MIN_HISTORY, min_periods=MIN_HISTORY).count() >= MIN_HISTORY
    rows = []
    for i in range(len(month_ends) - 1):
        t0, t1 = month_ends[i], month_ends[i + 1]
        elig = (hist_ok.loc[t0] & (px.loc[t0] >= MIN_PRICE)
                & (dv_med.loc[t0] >= MIN_DOLLAR_VOL) & sig.loc[t0].notna())
        names = elig[elig].index
        if top_liq and len(names) > top_liq:
            names = dv_med.loc[t0, names].nlargest(top_liq).index
        if len(names) < MIN_NAMES:
            continue
        s = sig.loc[t0, names].sort_values(ascending=False)
        n_target = n_names or max(1, int(round(len(names) * TOP_FRAC)))
        fwd = px.loc[t1, names] / px.loc[t0, names] - 1.0
        if capped:
            # Correlations from the CORR_WINDOW sessions ending at formation,
            # so nothing after t0 is used. Restrict to a workable candidate
            # pool: the cap only ever needs replacements from further down.
            pool = s.index[:min(len(s), n_target * 6)]
            w = ret.loc[:t0, pool].tail(CORR_WINDOW)
            corr = w.corr()
            held = admit(list(s.index), corr, n_target, cap, rho, invested,
                         symmetric=symmetric)
            big = largest_cluster(held, corr, rho)
        else:
            held = list(s.index[:n_target])
            w = ret.loc[:t0, held].tail(CORR_WINDOW)
            big = largest_cluster(held, w.corr(), rho)
        rows.append(dict(month=t1, n=len(names), n_top=len(held),
                         top=float(fwd.reindex(held).mean()) - COST,
                         mkt=float(fwd.mean()) - COST, big=big))
    m = pd.DataFrame(rows).set_index("month")
    m["spread"] = m["top"] - m["mkt"]
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exclude", choices=("none", "levered", "funds"), default="funds")
    ap.add_argument("--cap", type=float, default=CAP)
    ap.add_argument("--rho", type=float, default=RHO)
    ap.add_argument("--live-shape", action="store_true",
                    help="mirror the live book: top-500 liquidity tier, 50 names at 1.8%%")
    a = ap.parse_args()
    top_liq, n_names = (500, 50) if a.live_shape else (0, 0)

    px, dv, dv_med = monthly_panel(a.exclude)
    month_ends = px.groupby(px.index.to_period("M")).apply(
        lambda g: g.index.max()).to_list()

    out = []
    settings = ((False, True, "uncapped"),
                (True, False, f"cap {a.cap:.0%} OLD asymmetric"),
                (True, True, f"cap {a.cap:.0%} NEW symmetric"))
    for capped, sym, label in settings:
        m = run(px, dv_med, month_ends, capped, a.cap, a.rho, top_liq, n_names,
                symmetric=sym)
        v = fold_verdict(m)
        out.append(dict(book=label, months=len(m),
                        names=round(float(m["n_top"].mean()), 1),
                        max_cluster=round(float(m["big"].mean()), 1),
                        worst_cluster=int(m["big"].max()),
                        mean_top=round(float(m["top"].mean()) * 100, 3),
                        spread=round(v["mean_spread"] * 100, 3),
                        tstat=round(v["tstat"], 2),
                        abs_rate=f"{v['abs_rate']:.0%}",
                        sel_rate=f"{v['sel_rate']:.0%}",
                        verdict="SURVIVES" if v["survives"] else "KILLED"))
    board = pd.DataFrame(out)
    pd.set_option("display.width", 200)
    print("=" * 104)
    shape = "LIVE shape: top-500 tier, 50 names at 1.8%" if a.live_shape \
        else "pre-registered shape: full decile"
    print(f"CLUSTER-CAP COST TEST, 12-1 momentum, universe exclude={a.exclude}, "
          f"after {COST:.2%}/month. %%/month. {shape}.")
    print(f"max_cluster = mean size of the largest correlated group actually held.")
    print("=" * 104)
    print(board.to_string(index=False))
    print("\nsurvivorship caveat: live names only; every number an upper bound.")


if __name__ == "__main__":
    main()
