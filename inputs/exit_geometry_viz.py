"""Exit-geometry visualization: exit points, the stop/TP geometry shapes, AND the trend data
leading into each entry, drawn on real candles.

Read-only mirror of the exit rules simulated in inputs/exit_geometry_1h.py -- an ATR stop that
ratchets up as a trailing stop, a take-profit (optionally decaying toward entry), and a max-hold
time stop -- rendered so the operator can SEE where each trade exits, which barrier closed it, and
crucially what the TREND looked like around the entry that opened it.

The trend context around each entry is shown three ways:
  * the price panel shades the lookback window before every entry and draws the three Supertrend
    trailing lines (the bot's own bands) plus EMA-200;
  * a Supertrend-agreement panel counts how many of the three bands are in an uptrend (0-3), so the
    trend BUILDING into the 3/3 entry is visible, with EMA-200 slope shaded behind it;
  * a momentum panel (RSI-14) and the ATR% the barriers are scaled by.
Each entry is annotated with its trend snapshot (Supertrend agreement, side of EMA-200, RSI).

Callable from notebooks via render(); run as a CLI it writes outputs/PNG/3-exit-geometry-*.png.
This file is the single source for the chapter-1/2/3 exit-geometry notebook cells. Plain ASCII.
"""
from __future__ import annotations
import os
import sys
from collections import Counter

import numpy as np
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_dataset_1h as bd

REASON_COL = {"stop": "#ef5350", "tp": "#1b9e77", "time": "#888888"}
LINE_COL = ["#1f77b4", "#2ca02c", "#9467bd"]
PRE_ENTRY = 24          # bars of trend context to highlight before each entry


def _rsi(close, n=14):
    """Wilder RSI on a close array (causal)."""
    d = np.diff(close, prepend=close[0])
    up = np.where(d > 0, d, 0.0)
    dn = np.where(d < 0, -d, 0.0)
    ru = np.zeros_like(close)
    rd = np.zeros_like(close)
    ru[:n] = up[:n].mean() if n <= len(up) else up.mean()
    rd[:n] = dn[:n].mean() if n <= len(dn) else dn.mean()
    for i in range(n, len(close)):
        ru[i] = (ru[i - 1] * (n - 1) + up[i]) / n
        rd[i] = (rd[i - 1] * (n - 1) + dn[i]) / n
    rs = ru / np.where(rd == 0, np.nan, rd)
    return 100 - 100 / (1 + rs)


def compute_trend(ohlc):
    """Preceding trend: 3 Supertrend trailing lines + EMA-200, the per-band uptrend flags, and the
    triple-agreement entry mask. Returns (lines, ema, entries, ups)."""
    close = ohlc["close"].to_numpy(float)
    bands = [bd._supertrend_band(ohlc, p, m) for p, m in bd.ST_BANDS]
    ups = np.array([b[0] for b in bands])                  # 3 x n in-uptrend flags
    lines = [b[1] for b in bands]                          # 3 trailing-band lines
    ema = ohlc["close"].ewm(span=bd.ST_EMA, adjust=True).mean().to_numpy()
    uptrend = ups.all(axis=0)
    entries = np.zeros(len(ohlc), bool)
    entries[1:] = uptrend[1:] & ~uptrend[:-1] & (close[1:] > ema[1:])
    return lines, ema, entries, ups


def trend_context(ohlc, ups, ema):
    """Signals that describe the trend around an entry: Supertrend agreement (0-3), EMA-200 up
    slope, and RSI-14."""
    close = ohlc["close"].to_numpy(float)
    agree = ups.sum(axis=0)                                # 0..3 bands in uptrend
    ema_up = np.concatenate([[False], np.diff(ema) > 0])   # EMA-200 rising
    rsi = _rsi(close)
    return dict(agree=agree, ema_up=ema_up, rsi=rsi)


def simulate_with_path(ohlc, entries, cfg, fee, max_hold):
    """Walk each trade forward, recording the stop/TP path per bar and the exit reason. No
    look-ahead; identical mechanics to exit_geometry_1h.simulate(), plus the geometry path."""
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
                stop = max(stop, close[j] - cfg["trail"] * a * close[j])
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
        i = j + 1
    return trades, atrp


def _candles(ax, ohlc, lo, hi):
    close = ohlc["close"].to_numpy(float)
    ax.vlines(np.arange(lo, hi + 1), ohlc["low"].to_numpy()[lo:hi + 1],
              ohlc["high"].to_numpy()[lo:hi + 1], color="#999", lw=0.5, zorder=1)
    for k in range(lo, hi + 1):
        o, c = ohlc["open"].iloc[k], close[k]
        ax.add_patch(plt.Rectangle((k - 0.3, min(o, c)), 0.6, max(abs(c - o), 1e-9),
                     color=("#26a69a" if c >= o else "#ef5350"), zorder=2))


def plot_single(ohlc, lines, ema, ups, trades, atrp, cfg, max_hold, fee, symbol,
                out_path=None, n_trades=4, show=False):
    """Price + exit geometry, a Supertrend-agreement trend panel, and an RSI/ATR panel, with the
    trend context around each entry shaded and annotated."""
    if not trades:
        print("no entries to draw")
        return None
    ctx = trend_context(ohlc, ups, ema)
    shown = trades[-n_trades:]
    start = max(0, shown[0]["i"] - PRE_ENTRY - 8)
    end = min(len(ohlc) - 1, shown[-1]["j"] + 20)
    x = np.arange(start, end + 1)
    fig, (ax1, axv, ax2, ax3) = plt.subplots(4, 1, figsize=(16, 13), sharex=True,
                                             gridspec_kw={"height_ratios": [3, 1, 1, 1]})
    _candles(ax1, ohlc, start, end)
    # volume histogram directly beneath the candles, coloured by candle direction
    _vup = ohlc["close"].to_numpy(float) >= ohlc["open"].to_numpy(float)
    axv.bar(x, ohlc["volume"].to_numpy(float)[start:end + 1], width=0.7, alpha=0.85,
            color=np.where(_vup[start:end + 1], "#26a69a", "#ef5350"))
    axv.set_ylabel("volume")
    for li, ln in enumerate(lines):
        ax1.plot(x, np.asarray(ln)[start:end + 1], lw=0.8, alpha=0.55, color=LINE_COL[li],
                 label=f"Supertrend {bd.ST_BANDS[li][0]}/{bd.ST_BANDS[li][1]} (trailing line)")
    ax1.plot(x, ema[start:end + 1], color="#333", lw=1.0, ls="--", label=f"EMA-{bd.ST_EMA} (trend filter)")
    seen = set()
    for t in shown:
        # shade the trend-context window leading into the entry
        ax1.axvspan(max(start, t["i"] - PRE_ENTRY), t["i"], color="#1f77b4", alpha=0.06, zorder=0)
        jx = np.arange(t["i"] + 1, t["i"] + 1 + len(t["spath"]))
        ax1.plot(jx, t["spath"], color="#d95f02", lw=1.5, drawstyle="steps-post", zorder=5,
                 label=None if "s" in seen else "trailing stop")
        if np.isfinite(t["tpath"]).any():
            ax1.plot(jx, t["tpath"], color="#1b9e77", lw=1.0, ls=":", zorder=5,
                     label=None if "t" in seen else "take-profit")
        seen |= {"s", "t"}
        ax1.scatter([t["i"]], [t["entry"]], marker="^", s=95, color="#1f77b4", edgecolor="k", zorder=6)
        ax1.scatter([t["j"]], [t["exit"]], marker="v" if t["reason"] == "stop" else "o", s=95,
                    color=REASON_COL[t["reason"]], edgecolor="k", zorder=6)
        snap = f"ST {ctx['agree'][t['i']]}/3 {'^' if ctx['ema_up'][t['i']] else 'v'}EMA  RSI {ctx['rsi'][t['i']]:.0f}"
        ax1.annotate(snap, (t["i"], t["entry"]), textcoords="offset points", xytext=(-8, -22),
                     fontsize=7, color="#1f77b4", ha="right")
        ax1.annotate(f"{t['reason']} {t['ret'] * 100:+.1f}%", (t["j"], t["exit"]),
                     textcoords="offset points", xytext=(5, 9), fontsize=8, color=REASON_COL[t["reason"]])
    ax1.set_title(f"{symbol}  exit geometry + entry trend context  .  stop {cfg['stop_mult']}ATR, "
                  f"TP {cfg['tp_atr']}ATR{'-decay' if cfg['tp_decay'] else ''}, trail {cfg['trail']}ATR, "
                  f"max-hold {max_hold}b  .  shaded = {PRE_ENTRY}-bar pre-entry trend window")
    ax1.set_ylabel("price (USDT)")
    ax1.legend(loc="upper left", fontsize=7, ncol=2)

    # trend panel: Supertrend agreement 0-3, EMA-200 up-slope shaded behind
    ax2.fill_between(x, 0, 3, where=ctx["ema_up"][start:end + 1], color="#2ca02c", alpha=0.08,
                     step="post", label="EMA-200 rising")
    ax2.step(x, ctx["agree"][start:end + 1], where="post", color="#1f77b4", lw=1.3,
             label="Supertrend agreement (0-3)")
    for t in shown:
        if start <= t["i"] <= end:
            ax2.axvline(t["i"], color="#1f77b4", lw=0.8, ls=":", alpha=0.7)
    ax2.set_ylim(-0.2, 3.2)
    ax2.set_yticks([0, 1, 2, 3])
    ax2.set_ylabel("ST bands up")
    ax2.legend(loc="upper left", fontsize=7, ncol=2)

    # momentum + volatility panel: RSI-14 (left) and ATR% (right)
    ax3.plot(x, ctx["rsi"][start:end + 1], color="#9467bd", lw=1.1, label="RSI-14")
    ax3.axhline(50, color="#bbb", lw=0.7, ls="--")
    ax3.set_ylabel("RSI-14")
    ax3.set_ylim(0, 100)
    axr = ax3.twinx()
    axr.fill_between(x, 0, atrp[start:end + 1] * 100, color="#7570b3", alpha=0.25)
    axr.set_ylabel("ATR %")
    for t in shown:
        if start <= t["i"] <= end:
            ax3.axvline(t["i"], color="#1f77b4", lw=0.8, ls=":", alpha=0.7)
    ax3.legend(loc="upper left", fontsize=7)
    ticks = np.linspace(start, end, 6).astype(int)
    ax3.set_xticks(ticks)
    ax3.set_xticklabels([f"{ohlc['datetime'].iloc[k]:%m-%d %Hh}" for k in ticks])
    ax3.set_xlabel(f"bars {start}-{end}")
    fig.tight_layout()
    if out_path:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        fig.savefig(out_path, dpi=150)
    rc = Counter(t["reason"] for t in trades)
    print(f"[single] {symbol}: {len(trades)} trades  exits: {rc.get('tp',0)} TP / "
          f"{rc.get('stop',0)} stop / {rc.get('time',0)} time  mean net "
          f"{np.mean([t['ret'] for t in trades])*100:+.2f}%/trade"
          + (f"  -> {out_path}" if out_path else ""))
    if show:
        plt.show()
    else:
        plt.close(fig)
    return fig


def plot_compare(ohlc, lines, ema, ups, entries, configs, max_hold, fee, symbol,
                 out_path=None, anchor_trade=-1, show=False):
    """Same entry, several exit geometries side by side -- the shape difference made visible, each
    panel labelled with the trend snapshot at the shared entry."""
    base, _ = simulate_with_path(ohlc, entries, configs[0][1], fee, max_hold)
    if not base:
        print("no entries to compare")
        return None
    ctx = trend_context(ohlc, ups, ema)
    anchor = base[anchor_trade]["i"]
    snap = f"entry trend: ST {ctx['agree'][anchor]}/3, {'EMA up' if ctx['ema_up'][anchor] else 'EMA down'}, RSI {ctx['rsi'][anchor]:.0f}"
    n = len(configs)
    fig, axes = plt.subplots(2, n, figsize=(6 * n, 7), squeeze=False, sharex="col", sharey="row",
                             gridspec_kw={"height_ratios": [3, 1]})
    for c, (name, cfg) in enumerate(configs):
        ax = axes[0, c]
        axvol = axes[1, c]
        ent1 = np.zeros(len(ohlc), bool)
        ent1[anchor] = True
        tr, _ = simulate_with_path(ohlc, ent1, cfg, fee, max_hold)
        t = tr[0]
        s = max(0, anchor - PRE_ENTRY - 4)
        e = min(len(ohlc) - 1, t["j"] + 15)
        _candles(ax, ohlc, s, e)
        ax.axvspan(max(s, anchor - PRE_ENTRY), anchor, color="#1f77b4", alpha=0.06, zorder=0)
        for li, ln in enumerate(lines):
            ax.plot(np.arange(s, e + 1), np.asarray(ln)[s:e + 1], lw=0.7, alpha=0.4, color=LINE_COL[li])
        jx = np.arange(t["i"] + 1, t["i"] + 1 + len(t["spath"]))
        ax.plot(jx, t["spath"], color="#d95f02", lw=1.6, drawstyle="steps-post", label="stop path")
        if np.isfinite(t["tpath"]).any():
            ax.plot(jx, t["tpath"], color="#1b9e77", lw=1.1, ls=":", label="take-profit")
        ax.scatter([t["i"]], [t["entry"]], marker="^", s=90, color="#1f77b4", edgecolor="k", zorder=6)
        ax.scatter([t["j"]], [t["exit"]], marker="v" if t["reason"] == "stop" else "o", s=90,
                   color=REASON_COL[t["reason"]], edgecolor="k", zorder=6)
        ax.set_title(f"{name}\n{t['reason']} exit  {t['ret']*100:+.1f}%", fontsize=9)
        ax.set_xticks([])
        ax.legend(loc="upper left", fontsize=7)
        # volume histogram beneath each geometry, coloured by candle direction
        _vup = ohlc["close"].to_numpy(float) >= ohlc["open"].to_numpy(float)
        axvol.bar(np.arange(s, e + 1), ohlc["volume"].to_numpy(float)[s:e + 1], width=0.7,
                  alpha=0.85, color=np.where(_vup[s:e + 1], "#26a69a", "#ef5350"))
        axvol.set_xticks([])
        if c == 0:
            axvol.set_ylabel("volume")
    fig.suptitle(f"{symbol}  same entry, exit geometries  .  {snap}  (shaded = pre-entry trend window)",
                 fontsize=11)
    fig.tight_layout()
    if out_path:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        fig.savefig(out_path, dpi=150)
    print(f"[compare] {symbol}: anchored on entry at bar {anchor}"
          + (f"  -> {out_path}" if out_path else ""))
    if show:
        plt.show()
    else:
        plt.close(fig)
    return fig


def render(symbol="BTCUSDT", frame=4, show=False, save=True, out_dir=None,
           cfg=None, compare_cfgs=None):
    """One call: load a coin, compute the trend + entries, and draw both the single-config exit
    geometry (with entry trend context) and the geometry comparison. Usable from any notebook."""
    bd.configure(frame)
    if out_dir is None:
        out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "outputs", "PNG")
    folder = symbol.replace("/", "")
    ohlc = bd.load_coin(bd.DEFAULT_KLINES_ROOT, folder).reset_index(drop=True)
    if ohlc.empty:
        print(f"no klines for {folder} under {bd.DEFAULT_KLINES_ROOT}")
        return
    lines, ema, entries, ups = compute_trend(ohlc)
    fee = 0.001
    max_hold = bd.LABEL["horizon_bars"] * 4
    cfg = cfg or dict(stop_mult=2.0, tp_atr=3.0, trail=2.0, tp_decay=False)
    compare_cfgs = compare_cfgs or [
        ("fixed TP/stop", dict(stop_mult=2.0, tp_atr=3.0, trail=0.0, tp_decay=False)),
        ("trailing stop", dict(stop_mult=2.0, tp_atr=3.0, trail=2.0, tp_decay=False)),
        ("decaying TP", dict(stop_mult=2.0, tp_atr=3.0, trail=2.0, tp_decay=True))]
    trades, atrp = simulate_with_path(ohlc, entries, cfg, fee, max_hold)
    sp = os.path.join(out_dir, "3-exit-geometry-candles.png") if save else None
    cp = os.path.join(out_dir, "3-exit-geometry-compare.png") if save else None
    label = f"{symbol} {bd.INTERVAL}"
    plot_single(ohlc, lines, ema, ups, trades, atrp, cfg, max_hold, fee, label, sp, show=show)
    plot_compare(ohlc, lines, ema, ups, entries, compare_cfgs, max_hold, fee, label, cp, show=show)


def main():
    import argparse
    import matplotlib
    matplotlib.use("Agg")
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame", type=int, default=4, help="interval hours (4 or 1)")
    ap.add_argument("-s", "--symbol", default="BTCUSDT")
    args = ap.parse_args()
    render(symbol=args.symbol, frame=args.frame, show=False, save=True)


if __name__ == "__main__":
    main()
