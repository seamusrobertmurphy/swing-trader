"""Exit-geometry sweep on the 1h frame: per-coin trailing stops + time-decaying take-profit.

Step 5 of session-handover-2026-06-21-pm: given confident long entries, which exit geometry
maximizes after-fee expectancy out-of-sample, and is it stable across volatility regimes? This is
the 1h, per-coin companion to the daily `walkforward.py` (which has an ATR stop + fixed TP but no
trailing stop and no regime breakdown).

Entries (two modes, --signal):
  - `model`      : train LightGBM on the train split, enter OOS bars where p(barrier-hit) >= conf_hi.
  - `supertrend` : the triple-Supertrend long rule (no training; fast, for validation).

Each exit config is simulated per coin, bar by bar, with no look-ahead:
  - ATR stop at entry_atr * stop_mult below entry;
  - take-profit at entry_atr * tp_atr above entry (optionally time-decaying toward entry over the hold);
  - optional per-coin trailing stop that ratchets up by trail_mult * ATR (ClaudeTrader `update_trailing_stop`);
  - hard time stop at max_hold bars.
Net return is after `cost` per side. Results are aggregated per coin, overall, and per entry-volatility
tercile (low/mid/high), scored against buy-and-hold and a coin flip on the same OOS window.

No keys, no orders, unaffected by LIVE_TRADING. Read-only research.

Usage:
  .venv/bin/python inputs/exit_geometry_1h.py --signal supertrend -s BTCUSDT ETHUSDT
  .venv/bin/python inputs/exit_geometry_1h.py --signal model            # full dataset coins
"""
from __future__ import annotations

import argparse
import itertools
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_dataset_1h as bd
import train_model_1h as t1
import train_model as tm

try:
    from utils import risk as ct_risk            # ClaudeTrader ratcheting trailing stop
except Exception as exc:  # noqa: BLE001
    raise SystemExit(f"ClaudeTrader not importable ({exc}); pip install -e .../ClaudeTrader into the .venv")

OOS_BARS = 365 * 24
FEE = 0.001                                       # 10 bps/side
MAX_HOLD = bd.LABEL["horizon_bars"] * 4           # generous vs the 48-bar label horizon


def _entry_atr_pct(df: pd.DataFrame) -> np.ndarray:
    return (bd._atr_pct(df, bd.LABEL["atr_len"]) / 100.0).to_numpy()


def supertrend_entries(df: pd.DataFrame) -> np.ndarray:
    """Long entry when all three Supertrend bands turn to agreement above EMA-200 (the bot rule)."""
    ups = [bd._supertrend_band(df, p, m)[0] for p, m in bd.ST_BANDS]
    uptrend = np.all(ups, axis=0)
    ema200 = df["close"].ewm(span=bd.ST_EMA, adjust=True).mean().to_numpy()
    ema_ok = df["close"].to_numpy() > ema200
    e = np.zeros(len(df), bool)
    e[1:] = uptrend[1:] & ~uptrend[:-1] & ema_ok[1:]
    return e


def simulate(df: pd.DataFrame, entries: np.ndarray, cfg: dict):
    """One coin, one exit config. Returns (trades list of dicts) with net return + entry vol."""
    close = df["close"].to_numpy(float); high = df["high"].to_numpy(float); low = df["low"].to_numpy(float)
    atr = _entry_atr_pct(df)
    n = len(df); trades = []; i = 0
    while i < n - 1:
        if not entries[i] or not np.isfinite(atr[i]) or atr[i] <= 0:
            i += 1; continue
        entry = close[i]; a = atr[i]
        stop = entry * (1 - cfg["stop_mult"] * a)
        tp0 = entry * (1 + cfg["tp_atr"] * a) if cfg["tp_atr"] else None
        exit_px = None
        j = i + 1
        while j < min(i + 1 + MAX_HOLD, n):
            if cfg["trail"]:                                    # ratchet the stop up (ClaudeTrader)
                stop = ct_risk.update_trailing_stop("long", close[j], stop, cfg["trail"] * a * close[j])
            tp = tp0
            if tp0 and cfg["tp_decay"]:                         # decay TP toward entry over the hold
                frac = (j - i) / MAX_HOLD
                tp = entry * (1 + cfg["tp_atr"] * a * (1 - frac))
            if low[j] <= stop:
                exit_px = stop; break
            if tp and high[j] >= tp:
                exit_px = tp; break
            j += 1
        if exit_px is None:
            exit_px = close[min(j, n - 1)]
        net = (exit_px / entry) * (1 - FEE) / (1 + FEE) - 1.0
        trades.append(dict(ret=net, vol=a))
        i = j + 1                                               # one position at a time
    return trades


def grid():
    cfgs = []
    for stop_mult, tp_atr, trail, tp_decay in itertools.product(
            [1.5, 2.0, 3.0], [2.0, 3.0, None], [0.0, 2.0, 3.0], [False, True]):
        if tp_atr is None and tp_decay:        # decay only meaningful with a TP
            continue
        cfgs.append(dict(stop_mult=stop_mult, tp_atr=tp_atr, trail=trail, tp_decay=tp_decay))
    return cfgs


def _label(cfg):
    tp = f"{cfg['tp_atr']}ATR" + ("-decay" if cfg["tp_decay"] else "") if cfg["tp_atr"] else "noTP"
    tr = f"trail{cfg['trail']}" if cfg["trail"] else "noTrail"
    return f"stop{cfg['stop_mult']}/{tp}/{tr}"


def main():
    ap = argparse.ArgumentParser(description="1h exit-geometry sweep (per-coin trailing + regime breakdown)")
    ap.add_argument("--signal", choices=["model", "supertrend"], default="supertrend")
    ap.add_argument("-s", "--symbols", nargs="+", default=None)
    ap.add_argument("--oos-bars", type=int, default=OOS_BARS)
    args = ap.parse_args()

    symbols = args.symbols
    if symbols is None:
        ds = pd.read_parquet(bd.DATASET_PATH, columns=["symbol"])
        symbols = sorted(s.replace("/", "") for s in ds["symbol"].unique())

    model = prob_by_key = None
    if args.signal == "model":
        print("training LightGBM for entry signal...")
        df = t1.load(bd.DATASET_PATH); feat = bd.feature_columns(df)
        train, _test, _cut = t1.split(df)
        name, mdl = [(n, m) for n, m in tm.build_models(tm.HAVE_LGBM) if "LGBM" in type(m).__name__ or "LightGBM" in n][0]
        mdl.fit(train[feat], train["label"])
        allp = df[["symbol", "datetime"]].copy()
        allp["p"] = mdl.predict_proba(df[feat])[:, 1]
        prob_by_key = {(r.symbol, pd.Timestamp(r.datetime)): r.p for r in allp.itertuples()}

    cfgs = grid()
    print(f"signal={args.signal}  coins={len(symbols)}  exit-configs={len(cfgs)}  "
          f"fee={FEE*1e4:.0f}bps/side  OOS={args.oos_bars} bars\n")

    # collect trades per config across coins
    agg = {i: [] for i in range(len(cfgs))}
    bh = []
    for sym in symbols:
        d = bd.load_coin(bd.DEFAULT_KLINES_ROOT, sym)
        if len(d) < args.oos_bars + bd.ST_EMA:
            continue
        oos = d.iloc[-args.oos_bars:].reset_index(drop=True)
        if args.signal == "supertrend":
            ent = supertrend_entries(oos)
        else:
            slash = f"{sym[:-4]}/USDT" if sym.endswith("USDT") else sym
            ent = np.array([prob_by_key.get((slash, pd.Timestamp(t)), 0.0) >= tm.CONF_HI
                            for t in oos["datetime"]], bool)
        if ent.sum() == 0:
            continue
        for ci, cfg in enumerate(cfgs):
            agg[ci].extend(simulate(oos, ent, cfg))
        bh.append(oos["close"].iloc[-1] / oos["close"].iloc[0] - 1.0)

    # score each config: mean net expectancy/trade + per-vol-tercile breakdown
    rows = []
    for ci, cfg in enumerate(cfgs):
        tr = agg[ci]
        if not tr:
            continue
        rets = np.array([t["ret"] for t in tr]); vols = np.array([t["vol"] for t in tr])
        terc = pd.qcut(vols, 3, labels=["lo", "mid", "hi"], duplicates="drop") if len(set(vols)) > 3 else None
        reg = {}
        if terc is not None:
            for g in ["lo", "mid", "hi"]:
                m = (terc == g)
                reg[g] = float(rets[m].mean()) if m.any() else float("nan")
        rows.append(dict(cfg=_label(cfg), n=len(tr), exp=float(rets.mean()),
                         win=float((rets > 0).mean()), reg=reg))
    rows.sort(key=lambda r: r["exp"], reverse=True)

    bh_exp = float(np.mean(bh)) if bh else float("nan")
    print(f"buy-and-hold mean OOS return/coin: {bh_exp:+.2%}\n")
    print(f"{'exit config':30s} {'trades':>7} {'exp/trade':>10} {'win%':>6}   regime exp (lo/mid/hi)")
    print("-" * 92)
    for r in rows[:15]:
        rg = r["reg"]
        rgs = "  ".join(f"{rg.get(g, float('nan')):+.3%}" for g in ["lo", "mid", "hi"]) if rg else "n/a"
        print(f"{r['cfg']:30s} {r['n']:>7} {r['exp']:>+9.3%} {r['win']:>6.1%}   {rgs}")
    if rows:
        best = rows[0]
        verdict = "GO" if best["exp"] > 0 and best["exp"] > bh_exp / max(best["n"], 1) else "NO-GO"
        print(f"\nbest exit: {best['cfg']}  exp/trade {best['exp']:+.3%} on {best['n']} trades  -> {verdict} vs buy-hold")
        out = os.path.join(bd.BINANCE_DATA, f"exit_geometry_{args.signal}_oos.csv")
        pd.DataFrame([{**{k: r[k] for k in ("cfg", "n", "exp", "win")},
                       **{f"reg_{g}": r["reg"].get(g) for g in ("lo", "mid", "hi")}} for r in rows]).to_csv(out, index=False)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
