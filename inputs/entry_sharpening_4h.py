"""Entry sharpening on the 4h frame: do EARLY range and trend signals pay after fees?

Directive (Seamus, 2026-06-24): sharpen entry-point design -- respond to high-low RANGE
and BULLISH TRENDS much earlier. The unconditional +tgt/-stp ATR barrier loses after fees
(base rate ~0.25 < breakeven 0.333). Sharpening = entering only when an early range/trend
condition raises the realised win rate above the barrier breakeven AND, the deciding test,
the AFTER-FEE edge above zero -- because the fee, not the hit rate, is what sinks the
unconditional entry.

This extends ch3 'Sharpening Entries' from single-feature deciles on the 1h panel to the
richer 4h frame, and scores each decile by after-fee edge (trade_ret - cost), not just win
rate. Candidate conditions are grouped into families so we can see which KIND of "earlier"
actually pays:

  RANGE  -- where the bar sits in its own high/low range: ATR%, realised-vol, Bollinger,
            Vortex, range-position. (responding to range expansion/contraction)
  TREND  -- early bullish-trend structure: Supertrend distance/flip (f_st_), adaptive
            Supertrend + Kaufman efficiency regime (f_mst_), multi-timeframe daily/weekly
            alignment (f_d1_/f_w1_), and BTC lead-lag (f_btc_, the only cross-asset family).

Honest, after-fee, on the in-sample panel the dataset carries (this is signal DISCOVERY, not
the OOS verdict -- a condition that clears here graduates to an OOS earliness test next).
Plain ASCII, no orders.
"""
from __future__ import annotations
import os
import pandas as pd

import build_dataset_1h as bd
import train_model_1h as t1
import train_model as tm

COST = tm.COST_PCT / 100.0          # 0.20% round-trip as a return fraction


def family(col: str) -> str:
    """Tag a feature column as RANGE, TREND, or OTHER by its name/prefix."""
    c = col.lower()
    range_keys = ("atr", "_rv", "rvol", "bb", "boll", "vortex", "range", "rng",
                  "squeeze", "kc", "_std", "donch")
    trend_keys = ("f_st_", "f_mst_", "ker", "f_d1_", "f_w1_", "f_btc_", "dmi", "adx",
                  "aroon", "mom", "ema_spread", "macd", "supertrend", "sar", "trix")
    if any(k in c for k in trend_keys):
        return "TREND"
    if any(k in c for k in range_keys):
        return "RANGE"
    return "OTHER"


def decile_scoreboard(df, feat, breakeven, n_dec=10, min_n=300):
    """For every feature, find its best decile by AFTER-FEE edge and report win rate too."""
    base = df["label"].mean()
    base_edge = df["trade_ret"].mean() - COST
    rows = []
    for f in feat:
        d = df[[f, "label", "trade_ret"]].dropna()
        if len(d) < min_n * n_dec:
            continue
        try:
            q = pd.qcut(d[f], n_dec, labels=False, duplicates="drop")
        except ValueError:
            continue
        g = d.groupby(q)
        wr = g["label"].mean()
        edge = g["trade_ret"].mean() - COST
        n = g.size()
        ok = n >= min_n
        if not ok.any():
            continue
        wr, edge, n = wr[ok], edge[ok], n[ok]
        k = edge.idxmax()                       # the decile we would actually trade
        rows.append(dict(
            feature=f, family=family(f),
            best_dec_winrate=round(float(wr.loc[k]), 3),
            best_dec_edge_pct=round(float(edge.loc[k]) * 100, 3),
            n=int(n.loc[k]),
            clears_breakeven=bool(wr.loc[k] >= breakeven),
            edge_positive=bool(edge.loc[k] > 0),
            lift_vs_uncond_pp=round((float(edge.loc[k]) - base_edge) * 100, 3),
        ))
    board = pd.DataFrame(rows)
    return board, base, base_edge


def main():
    bd.configure(4)
    path = os.path.join(bd.BINANCE_DATA, "dataset_4h_allmarket.parquet")
    print(f"loading {os.path.basename(path)} ...", flush=True)
    df = t1.load(path)
    feat = bd.feature_columns(df)
    lab = bd.LABEL
    breakeven = lab["stp_atr"] / (lab["stp_atr"] + lab["tgt_atr"])
    print(f"rows {len(df):,}  features {len(feat)}  coins {df['symbol'].nunique()}", flush=True)
    print(f"label {lab['tgt_atr']}/-{lab['stp_atr']} ATR {lab['horizon_bars']}b  "
          f"breakeven win {breakeven:.3f}", flush=True)

    board, base, base_edge = decile_scoreboard(df, feat, breakeven)
    print(f"\nunconditional: base win {base:.3f}  after-fee edge {base_edge*100:+.3f}%/trade "
          f"(this is what 'enter every bar' loses)\n")

    board = board.sort_values("best_dec_edge_pct", ascending=False).reset_index(drop=True)

    # by family: which KIND of 'earlier' pays
    print("=" * 78)
    print("BEST single-condition entry by family (after-fee edge of the decile we'd trade)")
    print("=" * 78)
    for fam in ("TREND", "RANGE", "OTHER"):
        sub = board[board["family"] == fam]
        if not len(sub):
            continue
        print(f"\n--- {fam} ---")
        print(sub.head(8).to_string(index=False))

    winners = board[(board["edge_positive"]) & (board["clears_breakeven"])]
    print("\n" + "=" * 78)
    print(f"CONDITIONS THAT CLEAR BREAKEVEN *AND* PAY AFTER FEES: {len(winners)}")
    print("=" * 78)
    if len(winners):
        print(winners[["feature", "family", "best_dec_winrate", "best_dec_edge_pct",
                       "lift_vs_uncond_pp", "n"]].to_string(index=False))
        print("\n=> these graduate to the OOS earliness test (do they fire earlier than the "
              "Supertrend flip, and does the edge hold out of sample?).")
    else:
        best = board.iloc[0]
        print("NONE. No single condition both clears breakeven and pays after fees in-sample.")
        print(f"closest: {best['feature']} ({best['family']}) edge {best['best_dec_edge_pct']:+.3f}% "
              f"win {best['best_dec_winrate']} -- still {'+' if best['edge_positive'] else ''}"
              f"{'pays' if best['edge_positive'] else 'loses'} after fee.")
        print("Read: single-feature gating is not enough; the earliness/composite-trigger test "
              "is the next lever (enter at the FIRST bar of a confluence, not after the move).")
    return board


if __name__ == "__main__":
    main()
