"""Earliness test: does entering BEFORE the Supertrend flip, gated on a bullish-trend regime,
turn the after-fee edge positive? (4h frame, final-year OOS.)

Directive (Seamus, 2026-06-24): respond to bullish trends MUCH EARLIER. The sharpening
discovery (entry_sharpening_4h.py) found that on the 4h frame, after fees:
  * RANGE/volatility conditions alone never pay;
  * the only single conditions with positive after-fee edge are trend/momentum, and the
    strongest is f_btc_mom_168 -- Bitcoin's own ~28-day momentum (a market-wide bullish-trend
    gate, the only signal not derived from the coin's own price);
  * flip EVENTS (f_st_flip, f_mst_flip) are too late -- they lose after fees.

So the lever is: gate on a bullish-trend regime, then enter on an EARLY coin-momentum trigger
at the first confluence bar, instead of waiting for the Supertrend flip to confirm. This script
quantifies, head to head on the OOS year:

  LATE     -- enter when the Supertrend flips up (f_st_flip up). The bot's current behaviour.
  EARLY    -- enter at the FIRST bar where BTC trend is up (f_btc_mom_168 > 0) AND the coin's
              own early momentum has turned up (f_ta_pta_trix > 0). A rising-edge trigger.
  EARLY+KER-- EARLY additionally gated to the efficient-trend regime (f_mst_ker high), to skip
              chop where momentum signals whipsaw.

Reported per cohort: coverage, win rate, after-fee edge/trade (the decider), and -- the point
of the exercise -- how many bars EARLIER the EARLY trigger fires than the next Supertrend flip
in the same coin, and the entry-price improvement that buys (joined from raw 4h klines).

Honest, after-fee, OOS. No orders. Plain ASCII.
"""
from __future__ import annotations
import os
import numpy as np
import pandas as pd

import build_dataset_1h as bd
import train_model_1h as t1
import train_model as tm

COST = tm.COST_PCT / 100.0


def cohort_stats(sub, base_edge):
    """Win rate, after-fee edge, coverage for a boolean-selected cohort of bars."""
    d = sub.dropna(subset=["trade_ret", "label"])
    n = len(d)
    if n == 0:
        return dict(n=0, win=float("nan"), edge_pct=float("nan"), lift_pp=float("nan"))
    edge = d["trade_ret"].mean() - COST
    return dict(n=n, win=round(float(d["label"].mean()), 3),
                edge_pct=round(edge * 100, 3),
                lift_pp=round((edge - base_edge) * 100, 3))


def rising_edge(mask: pd.Series) -> pd.Series:
    """True only on the bar a condition first becomes true (first bar of each run)."""
    m = mask.fillna(False).astype(bool)
    return m & ~m.shift(1, fill_value=False)


def up_flip(series: pd.Series) -> pd.Series:
    """Supertrend flip-up: any positive value of the flip column (covers +1 / count forms)."""
    return series.fillna(0) > 0


def build_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Add per-coin signal columns, vectorized (sorted by symbol, datetime). Rising-edge
    computed with a per-coin shift so a run never bleeds across coin boundaries."""
    df = df.sort_values(["symbol", "datetime"]).reset_index(drop=True)
    grp = df["symbol"]
    btc_up = (df["f_btc_mom_168"] if "f_btc_mom_168" in df else df["f_btc_mom_6"]) > 0
    coin_up = (df["f_ta_pta_trix"] if "f_ta_pta_trix" in df else df["f_hr_mom_12"]) > 0
    df["sig_late"] = up_flip(df["f_st_flip"]) if "f_st_flip" in df else False

    def rise(mask):
        m = mask.fillna(False).astype(bool)
        prev = m.groupby(grp).shift(1, fill_value=False)
        return m & ~prev

    df["sig_early"] = rise(btc_up & coin_up)
    if "f_mst_ker" in df:
        ker_hi = df["f_mst_ker"] >= df["f_mst_ker"].median()
        df["sig_early_ker"] = rise(btc_up & coin_up & ker_hi)
    else:
        df["sig_early_ker"] = df["sig_early"]
    return df


def earliness(g: pd.DataFrame, horizon: int) -> list:
    """For each EARLY trigger, bars until the next LATE flip within `horizon` bars."""
    leads = []
    early_idx = np.flatnonzero(g["sig_early"].values)
    late_idx = np.flatnonzero(g["sig_late"].values)
    if not len(late_idx):
        return leads
    for e in early_idx:
        nxt = late_idx[late_idx > e]
        if len(nxt) and (nxt[0] - e) <= horizon:
            leads.append(int(nxt[0] - e))
    return leads


def main():
    bd.configure(4)
    path = os.path.join(bd.BINANCE_DATA, "dataset_4h_allmarket.parquet")
    print(f"loading {os.path.basename(path)} ...", flush=True)
    df = t1.load(path)
    lab = bd.LABEL
    horizon = lab["horizon_bars"]
    print(f"rows {len(df):,}  coins {df['symbol'].nunique()}  horizon {horizon}b", flush=True)

    df = build_signals(df)

    train, test, cut = t1.split(df)
    print(f"OOS split at {cut}: train {len(train):,}  test {len(test):,}", flush=True)

    for name, frame in (("TRAIN (in-sample)", train), ("TEST (OOS)", test)):
        base_edge = frame["trade_ret"].mean() - COST
        uncond = cohort_stats(frame, base_edge)
        print("\n" + "=" * 78)
        print(f"{name}  -- unconditional after-fee edge {uncond['edge_pct']:+.3f}%/trade "
              f"(n={uncond['n']:,})")
        print("=" * 78)
        rows = []
        for key, lbl in (("sig_late", "LATE  (Supertrend flip up)"),
                         ("sig_early", "EARLY (BTC-up & coin-mom-up, 1st bar)"),
                         ("sig_early_ker", "EARLY+KER (+ efficient-trend gate)")):
            s = cohort_stats(frame[frame[key]], base_edge)
            rows.append(dict(cohort=lbl, **s))
        board = pd.DataFrame(rows)
        print(board.to_string(index=False))

    # earliness: how many bars sooner EARLY fires than the next Supertrend flip (OOS coins)
    leads = []
    for _, g in test.groupby("symbol"):
        leads += earliness(g, horizon)
    if leads:
        leads = np.array(leads)
        print("\n" + "=" * 78)
        print(f"EARLINESS (OOS): EARLY trigger leads the next Supertrend flip on "
              f"{len(leads):,} occasions")
        print(f"  bars earlier -- median {np.median(leads):.0f}, mean {leads.mean():.1f}, "
              f"p90 {np.percentile(leads, 90):.0f}  (1 bar = 4h)")
        print("=" * 78)
    else:
        print("\nno EARLY->LATE lead pairs found OOS (check signal prevalence above).")

    print("\nREAD: compare EARLY vs LATE after-fee edge on the TEST block. If EARLY > LATE and "
          "EARLY > 0, entering earlier on the bullish-trend regime is the sharpening that pays; "
          "the earliness count is how much sooner it puts us in.")


if __name__ == "__main__":
    main()
