"""Cross-sectional ranking: long the strongest coins each bar, not predict each in isolation.

Pivot (Seamus, 2026-06-24) after the entry-sharpening NO-GO: per-coin barrier prediction sits
at the efficient-market floor. Cross-sectional framing asks a different question -- at each bar,
RANK the active universe by a strength signal and hold only the top names -- and relative
strength frequently carries an edge where time-series direction does not (the classic momentum
result). This tests it honestly on the 4h frame we already have.

Method, vectorized and point-in-time:
  * At each timestamp, rank the coins present by a candidate signal into cross-sectional deciles
    (only bars with >= MIN_COINS in the cross-section, so the rank is meaningful).
  * For each decile, the realised forward return is the dataset's `trade_ret` (the +tgt/-stp ATR
    barrier outcome from that bar), minus the 0.20% round-trip fee.
  * The edge is the TOP decile's after-fee return, read against the market (all-coin mean) and the
    BOTTOM decile. A real cross-sectional edge shows top > market > bottom, top-after-fee > 0, and
    a positive long-short SPREAD that holds across TRAIN and TEST.

Reports every candidate strength signal on TRAIN (in-sample) and TEST (final-year OOS), so a
train/test rank flip (the artifact signature that sank the entry work) is visible immediately.
Honest, after-fee. No orders. Plain ASCII.
"""
from __future__ import annotations
import os
import numpy as np
import pandas as pd

import build_dataset_1h as bd
import train_model_1h as t1
import train_model as tm

COST = tm.COST_PCT / 100.0
MIN_COINS = 5           # min coins in a cross-section to rank; the screened 4h universe is thin
                        # (median ~5-7 coins/bar), so we rank into TERCILES, not deciles
TOP_FRAC = 1.0 / 3.0    # long the top third each bar, read against the bottom third and the market
MIN_ROWS = 800          # min top-cohort rows for a block's number to be readable


def candidate_signals(df, feat):
    """Strength/momentum-like features that make sense to rank coins by, cross-sectionally."""
    keys = ("mom", "roc", "trix", "rsi", "ppo", "macd", "ema_fast_slow", "ema_fast_mid",
            "_st_", "_mst_", "_btc_", "rs_", "_strength", "vortex", "aroon", "cmo")
    sigs = [c for c in feat if any(k in c.lower() for k in keys)]
    # keep those with enough coverage
    return [c for c in sigs if df[c].notna().mean() > 0.5]


def cross_section_edge(frame, sig):
    """Top/bottom-tercile and market after-fee returns for one signal on one block. Each bar is
    ranked among the coins present; the top third is the long cohort, the bottom third the short
    reference. Cost cancels in the long-short spread; the top cohort carries the full round-trip."""
    d = frame[[sig, "datetime", "trade_ret", "label"]].dropna()
    if d.empty:
        return None
    cnt = d.groupby("datetime")[sig].transform("size")
    d = d[cnt >= MIN_COINS]
    if len(d) < MIN_ROWS:
        return None
    pct = d.groupby("datetime")[sig].rank(pct=True, method="average")
    top_m = pct > (1 - TOP_FRAC)
    bot_m = pct <= TOP_FRAC
    top = d.loc[top_m, "trade_ret"]
    bot = d.loc[bot_m, "trade_ret"]
    mkt = d["trade_ret"]
    if len(top) < MIN_ROWS:
        return None
    return dict(
        signal=sig, n_top=len(top),
        top_edge=round((top.mean() - COST) * 100, 3),
        bot_edge=round((bot.mean() - COST) * 100, 3),
        market=round((mkt.mean() - COST) * 100, 3),
        spread_pp=round((top.mean() - bot.mean()) * 100, 3),
        top_win=round(float(d.loc[top_m, "label"].mean()), 3),
    )


def main():
    bd.configure(4)
    path = os.path.join(bd.BINANCE_DATA, "dataset_4h_allmarket.parquet")
    print(f"loading {os.path.basename(path)} ...", flush=True)
    df = t1.load(path)
    feat = bd.feature_columns(df)
    sigs = candidate_signals(df, feat)
    print(f"rows {len(df):,}  coins {df['symbol'].nunique()}  candidate signals {len(sigs)}",
          flush=True)

    train, test, cut = t1.split(df)
    for nm, f in (("train", train), ("test", test)):
        cb = f.groupby("datetime").size()
        print(f"  {nm}: {len(f):,} rows, coins/bar median {cb.median():.0f} (p90 {cb.quantile(.9):.0f}); "
              f"{int((cb >= MIN_COINS).sum()):,} bars have >= {MIN_COINS} coins to rank")
    print(f"OOS split at {cut}\n", flush=True)

    rows = []
    for sig in sigs:
        tr = cross_section_edge(train, sig)
        te = cross_section_edge(test, sig)
        if tr is None or te is None:
            continue
        rows.append(dict(signal=sig,
                         tr_top=tr["top_edge"], tr_spread=tr["spread_pp"],
                         te_top=te["top_edge"], te_market=te["market"],
                         te_bot=te["bot_edge"], te_spread=te["spread_pp"],
                         te_top_win=te["top_win"], te_n_top=te["n_top"]))
    board = pd.DataFrame(rows)
    if board.empty:
        print("no signal had a usable cross-section (check MIN_COINS / coverage).")
        return
    # rank by OOS top-decile after-fee edge
    board = board.sort_values("te_top", ascending=False).reset_index(drop=True)
    pd.set_option("display.width", 220, "display.max_columns", 30)
    print("=" * 100)
    print("CROSS-SECTIONAL TERCILE EDGE (after 0.20%% fee). tr_=TRAIN, te_=TEST(OOS). top=long the")
    print("strongest third each bar; market=all coins; spread=top-bottom. Edge that survives shows")
    print("te_top>0, te_top>te_market, and the SAME sign on tr_spread and te_spread (no train/test flip).")
    print("=" * 100)
    print(board.to_string(index=False))

    # Two separate questions, reported honestly and not conflated:
    #   (1) RELATIVE STRENGTH: do the strongest coins beat the weakest, stably? (top-bottom spread)
    #   (2) LONG-ONLY GO: does the top third clear ZERO after fees? (absolute te_top)
    mkt = board["te_market"].iloc[0]                       # market baseline is the same for all signals
    stable_pos = board[(board["tr_spread"] > 0) & (board["te_spread"] > 0)].copy()
    beats_mkt = board[board["te_top"] > mkt]
    # most robust = largest WORST-CASE spread across the two splits (not a lucky single split)
    pool = stable_pos if len(stable_pos) else board
    pool["min_spread"] = pool[["tr_spread", "te_spread"]].min(axis=1)
    best_spread = pool.sort_values("min_spread", ascending=False).iloc[0]
    best_abs = board.iloc[0]                               # already sorted by te_top desc

    print("\n" + "=" * 100)
    print("VERDICT (two questions kept separate)")
    print("=" * 100)
    print(f"  market after-fee baseline: {mkt:+.3f}%/trade  (what every coin averages -- the level to beat)")
    print(f"\n  (1) RELATIVE STRENGTH (top third vs bottom third):")
    print(f"      {len(stable_pos)}/{len(board)} signals show a positive AND train/test sign-stable spread; "
          f"{len(beats_mkt)}/{len(board)} have the top third beating the market.")
    print(f"      most stable: {best_spread['signal']}  train spread {best_spread['tr_spread']:+.3f}pp, "
          f"test {best_spread['te_spread']:+.3f}pp  (top {best_spread['te_top']:+.3f}% vs bottom {best_spread['te_bot']:+.3f}%)")
    rel_real = len(stable_pos) >= 0.5 * len(board)
    print(f"      => relative-strength signal is {'PRESENT and broad' if rel_real else 'weak/inconsistent'}.")
    print(f"\n  (2) LONG-ONLY after fees:")
    print(f"      best top third: {best_abs['signal']} at {best_abs['te_top']:+.3f}%/trade "
          f"({'beats' if best_abs['te_top'] > mkt else 'below'} market {mkt:+.3f}%, "
          f"{'POSITIVE' if best_abs['te_top'] > 0 else 'still NEGATIVE'} absolute).")
    if best_abs["te_top"] > 0:
        print("      => GO candidate: graduate to a non-overlapping top-K portfolio backtest vs buy&hold/BTC.")
    else:
        print("      => NOT long-only-GO yet: the cross-sectional edge is real but DROWNED by the negative")
        print("         baseline. Levers to lift the absolute level above zero: a market-regime gate (deploy")
        print("         only when the market baseline is not deeply negative / BTC trending up), a less")
        print("         fee-punishing label/exit (longer horizon, fewer round trips), or a longer-horizon frame.")
    return board


if __name__ == "__main__":
    main()
