"""Exit-geometry visualization: exit points, the stop/TP geometry shapes, and the trend lines
preceding them, drawn on real candles.

Read-only mirror of the exit rules simulated in inputs/exit_geometry_1h.py -- an ATR stop that
ratchets up as a trailing stop, a take-profit (optionally decaying toward entry), and a max-hold
time stop -- rendered so the operator can SEE where each trade exits and which barrier closed it.
The three Supertrend trailing bands (the lines the bot itself trails off) and EMA-200 are the
PRECEDING TREND; the entry fires on triple agreement up-cross above EMA-200.

Two views, both saved to outputs/PNG/:
  3-exit-geometry-candles.png   -- one exit config, full geometry on the last N trades.
  3-exit-geometry-compare.png   -- the SAME entries under three different exit geometries, so the
                                   shape difference (fixed TP vs trailing vs decaying TP) is visible.

This file is the validated source for the chapter-3 'Exit Geometry on Candles' notebook cells.
No keys, no orders. Plain ASCII.
"""
from __future__ import annotations
import os
import sys
from collections import Counter

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_dataset_1h as bd

EXIT_REASON_COLOR = {"stop": "#ef5350", "tp": "#1b9e77", "time": "#888888"}
LINE_COLORS = ["#1f77b4", "#2ca02c", "#9467bd"]


def compute_trend(ohlc):
    """The preceding trend: three Supertrend trailing lines + EMA-200, and the entry mask."""
    close = ohlc["close"].to_numpy(float)
    bands = [bd._supertrend_band(ohlc, p, m) for p, m in bd.ST_BANDS]
    ups = np.array([b[0] for b in bands])                 # 3 x n in-uptrend flags
    lines = [b[1] for b in bands]                         # 3 trailing-band lines
    ema = ohlc["close"].ewm(span=bd.ST_EMA, adjust=True).mean().to_numpy()
    uptrend = ups.all(axis=0)
    entries = np.zeros(len(ohlc), bool)
    entries[1:] = uptrend[1:] & ~uptrend[:-1] & (close[1:] > ema[1:])
    return lines, ema, entries


def simulate_with_path(ohlc, entries, cfg, fee, max_hold):
    """Walk each trade forward, RECORDING the stop/TP path per bar and the exit reason.
    Identical mechanics to exit_geometry_1h.simulate(), plus the geometry path for drawing."""
    close = ohlc["close"].to_numpy(float)
    high = ohlc["high"].to_numpy(float)
    low = ohlc["low"].to_numpy(float)
    atrp = (bd._atr_pct(ohlc, bd.LABEL["atr_len"]) / 100.0).to_numpy()
    n = len(ohlc)
    trades = []
    i = 0
    while i < n - 1:
        if not entries[i] or not np.isfinite(atrp[i]) or atrp[i] <= 0:
            i += 1
            continue
        entry = close[i]
        a = atrp[i]
        stop = entry * (1 - cfg["stop_mult"] * a)
        tp0 = entry * (1 + cfg["tp_atr"] * a) if cfg["tp_atr"] else None
        spath, tpath = [], []
        reason, exit_px = "time", None
        j = i + 1
        while j < min(i + 1 + max_hold, n):
            if cfg["trail"]:
                stop = max(stop, close[j] - cfg["trail"] * a * close[j])   # ratchet up only
            tp = tp0
            if tp0 and cfg["tp_decay"]:
                tp = entry * (1 + cfg["tp_atr"] * a * (1 - (j - i) / max_hold))
            spath.append(stop)
            tpath.append(tp if tp else np.nan)
            if low[j] <= stop:
                exit_px, reason = stop, "stop"
                break
            if tp and high[j] >= tp:
                exit_px, reason = tp, "tp"
                break
            j += 1
        if exit_px is None:
            exit_px = close[min(j, n - 1)]
        net = (exit_px / entry) * (1 - fee) / (1 + fee) - 1.0
        trades.append(dict(i=i, j=min(j, n - 1), entry=entry, exit=exit_px, reason=reason,
                           ret=net, spath=np.array(spath), tpath=np.array(tpath)))
        i = j + 1                                                          # one position at a time
    return trades, atrp


def _candles(ax, ohlc, lo, hi):
    close = ohlc["close"].to_numpy(float)
    ax.vlines(np.arange(lo, hi + 1), ohlc["low"].to_numpy()[lo:hi + 1],
              ohlc["high"].to_numpy()[lo:hi + 1], color="#999", lw=0.5, zorder=1)
    for k in range(lo, hi + 1):
        o, c = ohlc["open"].iloc[k], close[k]
        ax.add_patch(plt.Rectangle((k - 0.3, min(o, c)), 0.6, max(abs(c - o), 1e-9),
                     color=("#26a69a" if c >= o else "#ef5350"), zorder=2))


def plot_single(ohlc, lines, ema, trades, atrp, cfg, max_hold, fee, symbol, out_path, n_trades=4):
    if not trades:
        print("no entries to draw")
        return
    shown = trades[-n_trades:]
    start = max(0, shown[0]["i"] - 20)
    end = min(len(ohlc) - 1, shown[-1]["j"] + 20)
    x = np.arange(start, end + 1)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 9), sharex=True,
                                   gridspec_kw={"height_ratios": [3, 1]})
    _candles(ax1, ohlc, start, end)
    for li, ln in enumerate(lines):
        ax1.plot(x, np.asarray(ln)[start:end + 1], lw=0.8, alpha=0.55, color=LINE_COLORS[li],
                 label=f"Supertrend {bd.ST_BANDS[li][0]}/{bd.ST_BANDS[li][1]} (trailing line)")
    ax1.plot(x, ema[start:end + 1], color="#333", lw=1.0, ls="--", label=f"EMA-{bd.ST_EMA} (trend filter)")
    seen_lbl = set()
    for t in shown:
        jx = np.arange(t["i"] + 1, t["i"] + 1 + len(t["spath"]))
        ax1.plot(jx, t["spath"], color="#d95f02", lw=1.5, drawstyle="steps-post", zorder=5,
                 label="trailing stop" if "ts" not in seen_lbl else None)
        if np.isfinite(t["tpath"]).any():
            ax1.plot(jx, t["tpath"], color="#1b9e77", lw=1.0, ls=":", zorder=5,
                     label="take-profit" if "tp" not in seen_lbl else None)
        seen_lbl |= {"ts", "tp"}
        ax1.scatter([t["i"]], [t["entry"]], marker="^", s=95, color="#1f77b4", edgecolor="k", zorder=6)
        ax1.scatter([t["j"]], [t["exit"]], marker="v" if t["reason"] == "stop" else "o",
                    s=95, color=EXIT_REASON_COLOR[t["reason"]], edgecolor="k", zorder=6)
        ax1.annotate(f"{t['reason']} {t['ret'] * 100:+.1f}%", (t["j"], t["exit"]),
                     textcoords="offset points", xytext=(5, 9), fontsize=8,
                     color=EXIT_REASON_COLOR[t["reason"]])
    ax1.set_title(f"{symbol}  exit geometry  .  stop {cfg['stop_mult']}ATR, "
                  f"TP {cfg['tp_atr']}ATR{'-decay' if cfg['tp_decay'] else ''}, "
                  f"trail {cfg['trail']}ATR, max-hold {max_hold}b  .  "
                  f"^ entry, v stop-exit, o tp/time-exit")
    ax1.set_ylabel("price (USDT)")
    ax1.legend(loc="upper left", fontsize=7, ncol=2)
    ax2.fill_between(x, 0, atrp[start:end + 1] * 100, color="#7570b3", alpha=0.4)
    ax2.set_ylabel("ATR %")
    ticks = np.linspace(start, end, 6).astype(int)
    ax2.set_xticks(ticks)
    ax2.set_xticklabels([f"{ohlc['datetime'].iloc[k]:%m-%d %Hh}" for k in ticks])
    ax2.set_xlabel(f"bars {start}-{end}")
    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    rc = Counter(t["reason"] for t in trades)
    print(f"[single] {symbol}: {len(trades)} trades  exits: {rc.get('tp',0)} TP / "
          f"{rc.get('stop',0)} stop / {rc.get('time',0)} time  mean net "
          f"{np.mean([t['ret'] for t in trades])*100:+.2f}%/trade  -> {out_path}")


def plot_compare(ohlc, lines, ema, entries, configs, max_hold, fee, symbol, out_path, anchor_trade=-1):
    """Same entry, three exit geometries side by side -- the shape difference made visible."""
    base, _ = simulate_with_path(ohlc, entries, configs[0][1], fee, max_hold)
    if not base:
        print("no entries to compare")
        return
    anchor = base[anchor_trade]["i"]
    fig, axes = plt.subplots(1, len(configs), figsize=(6 * len(configs), 6), sharey=True)
    for ax, (name, cfg) in zip(np.atleast_1d(axes), configs):
        ent1 = np.zeros(len(ohlc), bool)
        ent1[anchor] = True                                        # isolate the one shared entry
        tr, atrp = simulate_with_path(ohlc, ent1, cfg, fee, max_hold)
        t = tr[0]
        start = max(0, anchor - 15)
        end = min(len(ohlc) - 1, t["j"] + 15)
        _candles(ax, ohlc, start, end)
        for li, ln in enumerate(lines):
            ax.plot(np.arange(start, end + 1), np.asarray(ln)[start:end + 1], lw=0.7, alpha=0.4,
                    color=LINE_COLORS[li])
        jx = np.arange(t["i"] + 1, t["i"] + 1 + len(t["spath"]))
        ax.plot(jx, t["spath"], color="#d95f02", lw=1.6, drawstyle="steps-post", label="trailing/ATR stop")
        if np.isfinite(t["tpath"]).any():
            ax.plot(jx, t["tpath"], color="#1b9e77", lw=1.1, ls=":", label="take-profit")
        ax.scatter([t["i"]], [t["entry"]], marker="^", s=90, color="#1f77b4", edgecolor="k", zorder=6)
        ax.scatter([t["j"]], [t["exit"]], marker="v" if t["reason"] == "stop" else "o", s=90,
                   color=EXIT_REASON_COLOR[t["reason"]], edgecolor="k", zorder=6)
        ax.set_title(f"{name}\n{t['reason']} exit  {t['ret']*100:+.1f}%", fontsize=9)
        ax.set_xticks([])
        ax.legend(loc="upper left", fontsize=7)
    fig.suptitle(f"{symbol}  same entry, three exit geometries  (orange=stop path, dotted=TP)",
                 fontsize=11)
    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"[compare] {symbol}: anchored on entry at bar {anchor}  -> {out_path}")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame", type=int, default=4, help="interval hours (4 or 1)")
    ap.add_argument("-s", "--symbol", default="BTCUSDT")
    args = ap.parse_args()
    bd.configure(args.frame)
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "PNG")
    ohlc = bd.load_coin(bd.DEFAULT_KLINES_ROOT, args.symbol).reset_index(drop=True)
    if ohlc.empty:
        raise SystemExit(f"no klines for {args.symbol} under {bd.DEFAULT_KLINES_ROOT}")
    print(f"{args.symbol}: {len(ohlc)} {bd.INTERVAL} bars")
    lines, ema, entries = compute_trend(ohlc)
    fee = 0.001
    max_hold = bd.LABEL["horizon_bars"] * 4
    cfg = dict(stop_mult=2.0, tp_atr=3.0, trail=2.0, tp_decay=False)
    trades, atrp = simulate_with_path(ohlc, entries, cfg, fee, max_hold)
    plot_single(ohlc, lines, ema, trades, atrp, cfg, max_hold, fee, f"{args.symbol} {bd.INTERVAL}",
                os.path.join(out, "3-exit-geometry-candles.png"))
    configs = [("fixed TP/stop", dict(stop_mult=2.0, tp_atr=3.0, trail=0.0, tp_decay=False)),
               ("trailing stop", dict(stop_mult=2.0, tp_atr=3.0, trail=2.0, tp_decay=False)),
               ("decaying TP", dict(stop_mult=2.0, tp_atr=3.0, trail=2.0, tp_decay=True))]
    plot_compare(ohlc, lines, ema, entries, configs, max_hold, fee, f"{args.symbol} {bd.INTERVAL}",
                 os.path.join(out, "3-exit-geometry-compare.png"))


if __name__ == "__main__":
    main()
