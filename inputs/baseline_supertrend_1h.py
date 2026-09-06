"""Triple-Supertrend rules baseline, scored on the after-fee out-of-sample scoreboard.

This is the rules-based benchmark the model must beat. It trades the SAME signal the
live bot traded: long-only spot, enter when all three Supertrend
bands agree on an uptrend AND price is above the EMA-200 gate, exit when the agreement
breaks. No look-ahead: every decision at bar t uses bars up to t only.

It deliberately reuses two layers:
  - the Supertrend math from build_dataset_1h.py (_supertrend_band, ST_BANDS, ST_EMA),
    so the baseline and the f_st_ model features are the SAME indicator, not two drifting
    copies;
  - ClaudeTrader's risk/performance modules (utils.risk, utils.performance), installed
    editable into this .venv, for the ATR trailing stop and the Sharpe/Sortino/Calmar/
    max-drawdown/profit-factor report -- the exact after-fee metric set the workflow needs.

Scope: a benchmark, not an executor. It never imports keys, never places orders, and is
unaffected by LIVE_TRADING. Run it to answer one question: does the ML model earn its
complexity over a simple, tradeable trend rule, after fees, on the final-year holdout?

Usage:
    .venv/bin/python inputs/baseline_supertrend_1h.py                 # all dataset coins
    .venv/bin/python inputs/baseline_supertrend_1h.py -s BTCUSDT ETHUSDT --trail
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_dataset_1h as B   # Supertrend math + offline kline loader (single source of truth)

# ClaudeTrader (editable install in this .venv). Generic top-level names, so alias on import.
try:
    from utils import performance as ct_perf
    from utils import risk as ct_risk
except Exception as exc:  # noqa: BLE001
    raise SystemExit(
        "ClaudeTrader not importable. Install it into this venv:\n"
        "  .venv/bin/pip install -e /Volumes/PortableSSD/Github/SuperTrendTradingBot/ClaudeTrader\n"
        f"(import error: {exc})"
    )

OOS_BARS = 365 * 24            # final ~1 year holdout, matching the model's OOS design
FEE_PCT = 0.001                # 10 bps taker per side (Binance spot); round-trip = 20 bps
PERIODS_PER_YEAR = ct_perf.periods_per_year_for("1h")   # 8760


def supertrend_signals(df: pd.DataFrame):
    """Causal long-only signal from the triple-Supertrend + EMA-200 gate (the bot's
    rule, core path). Returns aligned arrays: uptrend(all-three-agree), enter, ema_ok, atr%."""
    ups = [B._supertrend_band(df, p, m)[0] for p, m in B.ST_BANDS]
    uptrend = np.all(ups, axis=0)
    ema200 = df["close"].ewm(span=B.ST_EMA, adjust=True).mean().to_numpy()
    close = df["close"].to_numpy(float)
    ema_ok = close > ema200
    enter = np.zeros(len(df), dtype=bool)
    enter[1:] = uptrend[1:] & ~uptrend[:-1] & ema_ok[1:]    # reversal into full agreement, above EMA
    atr_pct = (B._atr_pct(df, B.LABEL["atr_len"]) / 100.0).to_numpy()
    return uptrend, enter, ema_ok, atr_pct


def simulate_coin(df: pd.DataFrame, trail: bool):
    """Long-only, single-position fee-aware sim over one coin. Builds a per-bar equity curve
    (mark-to-market) and a per-trade return list, then scores both via ClaudeTrader."""
    uptrend, enter, _ema_ok, atr_pct = supertrend_signals(df)
    close = df["close"].to_numpy(float)
    low = df["low"].to_numpy(float)
    n = len(df)

    equity = 1.0
    curve = np.empty(n)
    trades: list[float] = []
    in_pos = False
    entry_px = stop = 0.0
    prev_close = close[0]

    for i in range(n):
        if in_pos:
            equity *= close[i] / prev_close            # mark-to-market on the bar's move
            if trail and atr_pct[i] > 0:               # ClaudeTrader ratcheting ATR stop
                stop = ct_risk.update_trailing_stop("long", close[i], stop, 2.0 * atr_pct[i] * close[i])
            hit_stop = trail and low[i] <= stop
            if hit_stop or not uptrend[i]:             # exit: stop or agreement broke
                exit_px = stop if hit_stop else close[i]
                gross = exit_px / entry_px
                net = gross * (1 - FEE_PCT) / (1 + FEE_PCT)   # fee both sides
                trades.append(net - 1.0)
                equity *= exit_px / close[i] if close[i] else 1.0
                equity *= (1 - FEE_PCT)                # exit fee on the book
                in_pos = False
        elif enter[i]:
            in_pos = True
            entry_px = close[i]
            equity *= (1 - FEE_PCT)                    # entry fee
            stop = close[i] - 2.0 * atr_pct[i] * close[i] if atr_pct[i] > 0 else 0.0
        curve[i] = equity
        prev_close = close[i]

    report = ct_perf.compute_metrics(curve.tolist(), trades, periods_per_year=PERIODS_PER_YEAR)
    buy_hold = close[-1] / close[0] - 1.0
    return report, buy_hold, len(trades)


def main():
    ap = argparse.ArgumentParser(description="Triple-Supertrend rules baseline (after-fee OOS scoreboard)")
    ap.add_argument("-s", "--symbols", nargs="+", default=None, help="default: every coin in the built dataset")
    ap.add_argument("--oos-bars", type=int, default=OOS_BARS)
    ap.add_argument("--trail", action="store_true", help="add a ClaudeTrader 2xATR trailing stop")
    args = ap.parse_args()

    symbols = args.symbols
    if symbols is None:   # default to whatever the current dataset actually covers
        ds = pd.read_parquet(B.DATASET_PATH, columns=["symbol"])
        symbols = sorted(s.replace("/", "") for s in ds["symbol"].unique())
    print(f"baseline: triple-Supertrend, long-only, fee={FEE_PCT*1e4:.0f}bps/side, "
          f"OOS={args.oos_bars} bars, trail={args.trail}, coins={len(symbols)}\n")

    rows = []
    for sym in symbols:
        df = B.load_coin(B.DEFAULT_KLINES_ROOT, sym)
        if len(df) < args.oos_bars + B.ST_EMA:
            print(f"  skip {sym}: only {len(df)} bars")
            continue
        oos = df.iloc[-args.oos_bars:].reset_index(drop=True)
        rep, bh, ntr = simulate_coin(oos, args.trail)
        rows.append(dict(symbol=sym, trades=ntr, ret=rep.total_return, bh=bh,
                         edge=rep.total_return - bh, sharpe=rep.sharpe_ratio,
                         sortino=rep.sortino_ratio, calmar=rep.calmar_ratio,
                         maxdd=rep.max_drawdown, winrate=rep.win_rate, pf=rep.profit_factor))
        print(f"  {sym:14s} trades={ntr:4d} ret={rep.total_return:+7.2%} "
              f"b&h={bh:+7.2%} edge={rep.total_return-bh:+7.2%} sharpe={rep.sharpe_ratio:+5.2f}")

    if not rows:
        raise SystemExit("no coins scored")
    r = pd.DataFrame(rows)
    print("\n=== AFTER-FEE OOS SCOREBOARD (equal-weight across coins) ===")
    print(f"  coins scored        : {len(r)}")
    print(f"  beat buy-and-hold   : {(r.edge>0).sum()}/{len(r)}  ({(r.edge>0).mean():.0%})")
    print(f"  mean strategy ret   : {r.ret.mean():+.2%}   mean buy-and-hold : {r.bh.mean():+.2%}")
    print(f"  mean / median edge  : {r.edge.mean():+.2%} / {r.edge.median():+.2%}")
    print(f"  mean / median sharpe: {r.sharpe.mean():+.2f} / {r.sharpe.median():+.2f}")
    print(f"  mean max drawdown   : {r.maxdd.mean():.2%}")
    print(f"  pooled win rate     : {r.winrate.mean():.1%}   total trades : {int(r.trades.sum())}")
    verdict = "GO" if (r.edge > 0).mean() > 0.5 and r.sharpe.median() > 0 else "NO-GO"
    print(f"\n  VERDICT vs buy-and-hold: {verdict}")
    out = os.path.join(B.BINANCE_DATA, "baseline_supertrend_oos.csv")
    r.to_csv(out, index=False)
    print(f"  wrote {out}")


if __name__ == "__main__":
    main()
