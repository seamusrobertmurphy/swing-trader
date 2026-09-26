"""The figures one bench run draws, from Choose Figures and Signal engines.

    from bench_figures import draw_all
    draw_all(cfg, rows=rows, est=est, train=train, test=test, feats=feats)

Written 20 September 2026. Sixteen settings, the eleven on Signal engines and
the five on Choose Figures, were saved by the forms and drawn by the control
centre's own charts, and nothing the runner did read one of them, so a record
carried scores and never a picture of the rows those scores came from.

Four of the eight figures are drawn on the raw bars, because the built panel
carries ratios and flags and no price at all; the MACD, moving-average,
Fibonacci and confluence settings drive them through the same lab engines the
workflow document uses, imported by file path, never a second copy of their
arithmetic. The other four are drawn on the run's own blind period: the
reliability curve, what the model leaned on, what choosiness buys, and the
account curve of the trades it would have taken.

Nothing here decides anything. A figure is a picture of evidence, not evidence,
so bench_run catches every failure in this module and still writes its scores.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt            # noqa: E402
import numpy as np                         # noqa: E402
import pandas as pd                        # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench_config as bc                  # noqa: E402

REPO = bc.REPO

# Two palettes, one per theme. The light one is the cheat sheet's, so a colour
# here means what it means on the board.
THEMES = {
    "light": dict(bg="#ffffff", ink="#16202c", soft="#4a5866", rule="#c3cedb",
                  up="#0e7a5f", down="#a01c1c", blue="#0d5f8a", orange="#a8560c",
                  purple="#6b3fa0"),
    "dark":  dict(bg="#12181f", ink="#e6edf5", soft="#9aa8b8", rule="#2d3a48",
                  up="#3fbf92", down="#e0604f", blue="#5aa9dc", orange="#e0a45a",
                  purple="#b18ce0"),
}

WHAT = {
    "candles": "price candles over the charted span, with the chosen overlays",
    "macd": "the MACD lines, the histogram and the noise band a crossing must clear",
    "confluence": "how many of the four engines agreed, candle by candle",
    "fibonacci": "the Fibonacci levels of the swing the engine found",
    "reliability": "stated probability against what happened, on the test period",
    "importance": "how much each column mattered, by permutation on the test period",
    "selectivity": "return per trade after cost against how choosy the model is",
    "equity": "the account curve of the trades taken on the test period",
}


def _theme(cfg: dict) -> dict:
    return THEMES.get(str(cfg["viz"].get("theme") or "light"), THEMES["light"])


def _fig(t: dict, w=7.0, h=3.6, rows=1, ratios=None):
    fig, axes = plt.subplots(rows, 1, figsize=(w, h), dpi=130, sharex=(rows > 1),
                             height_ratios=ratios)
    axes = np.atleast_1d(axes)
    fig.patch.set_facecolor(t["bg"])
    for ax in axes:
        ax.set_facecolor(t["bg"])
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(t["rule"])
        ax.tick_params(colors=t["soft"], labelsize=7)
        ax.grid(True, color=t["rule"], linewidth=0.5, alpha=0.5)
        ax.set_axisbelow(True)
        ax.title.set_color(t["ink"])
        ax.xaxis.label.set_color(t["soft"])
        ax.yaxis.label.set_color(t["soft"])
    return fig, (axes[0] if rows == 1 else axes)


def _nothing(ax, t, why: str) -> None:
    ax.text(0.5, 0.5, why, ha="center", va="center", fontsize=8, color=t["soft"],
            wrap=True, transform=ax.transAxes)
    ax.set_xticks([]); ax.set_yticks([])
    ax.grid(False)


def _bars(cfg: dict):
    """The raw bars this run charts, reusing the control centre's own reader.

    The reader lives in control_charts because it handles the millisecond and
    microsecond timestamps Binance mixes inside one symbol's folder, and a
    second copy of that rule here is a second place for it to be wrong.
    """
    import control_charts as cc
    n = max(120, int(cfg["viz"].get("viz_bars") or 400))
    who, d = cc._klines(cfg, n)
    if who is None:
        return None, None, d
    sym, frame = who
    return sym, frame, d


# ---------------------------------------------------------------------------
# On the raw bars: every Signal engines setting drives one of these
# ---------------------------------------------------------------------------

def draw_candles(cfg, t, ctx):
    """Candles with whatever Choose Figures ticked under Overlays.

    Entries and exits are the confluence engine's own edge-triggered fires, so
    the moving averages, the MACD spans, the Fibonacci lookback and the score to
    fire all move the markers on this picture.
    """
    import control_charts as cc
    n = max(120, int(cfg["viz"].get("viz_bars") or 400))
    sym, frame, d = _bars(cfg)
    overlays = set(cfg["viz"].get("overlays") or [])
    want_vol = "volume" in overlays
    fig, axes = _fig(t, rows=2 if want_vol else 1,
                     ratios=[3.0, 1.0] if want_vol else None,
                     h=4.0 if want_vol else 3.4)
    ax = axes[0] if want_vol else axes
    if sym is None:
        _nothing(ax, t, str(d)); return fig
    show = d.tail(n).reset_index(drop=True)
    x = np.arange(len(show))

    up = show["close"] >= show["open"]
    ax.vlines(x, show["low"], show["high"], color=np.where(up, t["up"], t["down"]),
              linewidth=0.6)
    ax.bar(x, (show["close"] - show["open"]).abs(),
           bottom=show[["open", "close"]].min(axis=1), width=0.7,
           color=np.where(up, t["up"], t["down"]), linewidth=0)

    drawn = []
    if "ema200" in overlays:
        ema = show["close"].ewm(span=200, adjust=False).mean()
        ax.plot(x, ema, color=t["blue"], linewidth=1.0)
        drawn.append("200-candle average")
    if "supertrend" in overlays:
        import build_dataset_1h as bd
        for period, mult in bd.ST_BANDS:
            _u, line = bd._supertrend_band(d, period, mult)
            ax.plot(x, np.asarray(line)[-len(show):], color=t["orange"],
                    linewidth=0.7, alpha=0.85)
        drawn.append("Supertrend " + ", ".join(f"{p}/{m:g}" for p, m in bd.ST_BANDS))
    if "swings" in overlays:
        fib = cc._engine("fib")
        sw = fib.detect_swing(show["high"], show["low"], cc._conf_cfg(cfg).fib)
        if sw is not None and sw.rng > 0:
            ax.scatter([sw.lo_idx, sw.hi_idx], [sw.lo, sw.hi], s=26,
                       color=t["purple"], zorder=6)
            ax.plot([sw.lo_idx, sw.hi_idx], [sw.lo, sw.hi], color=t["purple"],
                    linewidth=0.9, linestyle="--")
            drawn.append(f"swing over {cfg['signals']['fib_lookback']} candles")
    if overlays & {"entries", "exits"}:
        conf = cc._engine("confluence").compute_confluence(show, cc._conf_cfg(cfg))
        if "entries" in overlays:
            i = np.flatnonzero(conf["buy"].to_numpy())
            ax.scatter(i, show["low"].to_numpy()[i] * 0.99, marker="^", s=30,
                       color=t["up"], zorder=6)
            drawn.append(f"{len(i)} entries")
        if "exits" in overlays:
            i = np.flatnonzero(conf["sell"].to_numpy())
            ax.scatter(i, show["high"].to_numpy()[i] * 1.01, marker="v", s=30,
                       color=t["down"], zorder=6)
            drawn.append(f"{len(i)} exits")
    if want_vol:
        axes[1].bar(x, show["volume"], width=0.8, color=t["soft"], alpha=0.6,
                    linewidth=0)
        axes[1].set_ylabel("volume")
        drawn.append("volume")

    ax.set_ylabel("price")
    ax.set_title(f"{sym}, {cc._interval(frame)} candles, the last {len(show)}"
                 + (f"; overlays: {', '.join(drawn)}" if drawn else
                    "; no overlays ticked"), fontsize=8)
    _date_axis(axes[-1] if want_vol else ax, show, t)
    fig.tight_layout()
    return fig


def _date_axis(ax, show, t) -> None:
    step = max(1, len(show) // 6)
    at = list(range(0, len(show), step))
    ax.set_xticks(at)
    ax.set_xticklabels([str(pd.Timestamp(show["datetime"].iloc[i]).date()) for i in at],
                       fontsize=6, color=t["soft"])


def draw_macd(cfg, t, ctx):
    """The MACD the Signal engines settings actually describe, not 12/26/9."""
    import control_charts as cc
    n = max(120, int(cfg["viz"].get("viz_bars") or 400))
    sym, frame, d = _bars(cfg)
    fig, axes = _fig(t, rows=2, ratios=[1.6, 1.0], h=3.8)
    if sym is None:
        _nothing(axes[0], t, str(d)); _nothing(axes[1], t, ""); return fig
    show = d.tail(n).reset_index(drop=True)
    x = np.arange(len(show))
    s = cfg["signals"]
    sig = cc._engine("macd").compute_signals(d["close"], cc._macd_cfg(cfg)).tail(len(show))
    sig.index = show.index

    axes[0].plot(x, show["close"], color=t["ink"], linewidth=1.0)
    buy, sell = sig["guarded_buy"].to_numpy(), sig["guarded_sell"].to_numpy()
    axes[0].scatter(x[buy], show["close"].to_numpy()[buy], marker="^", s=26, color=t["up"])
    axes[0].scatter(x[sell], show["close"].to_numpy()[sell], marker="v", s=26, color=t["down"])
    axes[0].set_ylabel("price")
    axes[0].set_title(f"{sym}: MACD {s['macd_fast']}/{s['macd_slow']}/{s['macd_signal']}, "
                      f"noise band {s['macd_noise_k']:g} sigma, confirmed over "
                      f"{s['macd_confirm_bars']} candle(s): {int(buy.sum())} buys, "
                      f"{int(sell.sum())} sells", fontsize=8)

    hist, eps = sig["hist"].to_numpy(), sig["eps"].to_numpy()
    axes[1].bar(x, hist, width=0.8, linewidth=0,
                color=np.where(hist >= 0, t["up"], t["down"]), alpha=0.6)
    axes[1].fill_between(x, -eps, eps, color=t["soft"], alpha=0.25, linewidth=0)
    axes[1].plot(x, sig["macd"], color=t["blue"], linewidth=0.9)
    axes[1].plot(x, sig["signal"], color=t["orange"], linewidth=0.9)
    axes[1].axhline(0, color=t["rule"], linewidth=0.8)
    axes[1].set_ylabel("MACD")
    _date_axis(axes[1], show, t)
    fig.tight_layout()
    return fig


def draw_confluence(cfg, t, ctx):
    """The four stances and their weighted score against the score to fire."""
    import control_charts as cc
    n = max(120, int(cfg["viz"].get("viz_bars") or 400))
    sym, frame, d = _bars(cfg)
    fig, ax = _fig(t)
    if sym is None:
        _nothing(ax, t, str(d)); return fig
    show = d.tail(n).reset_index(drop=True)
    conf = cc._engine("confluence").compute_confluence(show, cc._conf_cfg(cfg))
    x = np.arange(len(show))
    score = conf["score"].to_numpy(float)
    thr = float(cfg["signals"]["confluence_threshold"])
    ax.bar(x, score, width=0.9, linewidth=0,
           color=np.where(score >= 0, t["up"], t["down"]), alpha=0.65)
    ax.axhline(thr, color=t["ink"], linestyle="--", linewidth=0.9)
    ax.axhline(-thr, color=t["ink"], linestyle="--", linewidth=0.9)
    ax.axhline(0, color=t["rule"], linewidth=0.8)
    s = cfg["signals"]
    ax.set_ylabel("engines agreeing, minus one to plus one each")
    ax.set_title(f"{sym}: score to fire {thr:g}, averages {s['ma_fast']}/{s['ma_slow']}, "
                 f"a candle signal lasting {s['candle_decay']} candles; "
                 f"{int(conf['buy'].sum())} buys, {int(conf['sell'].sum())} sells",
                 fontsize=8)
    _date_axis(ax, show, t)
    fig.tight_layout()
    return fig


def draw_fibonacci(cfg, t, ctx):
    """The swing the lookback found, and the levels drawn off it."""
    import control_charts as cc
    n = max(120, int(cfg["viz"].get("viz_bars") or 400))
    sym, frame, d = _bars(cfg)
    fig, ax = _fig(t)
    if sym is None:
        _nothing(ax, t, str(d)); return fig
    show = d.tail(n).reset_index(drop=True)
    fib = cc._engine("fib")
    fcfg = cc._conf_cfg(cfg).fib
    sw = fib.detect_swing(show["high"], show["low"], fcfg)
    x = np.arange(len(show))
    ax.plot(x, show["close"], color=t["ink"], linewidth=1.0, zorder=4)
    s = cfg["signals"]
    if sw is None or sw.rng <= 0:
        ax.set_title(f"{sym}: no swing cleared "
                     f"{s['fib_min_swing_frac']:g} of price over "
                     f"{s['fib_lookback']} candles", fontsize=8)
    else:
        for ratio, price in fib.retracement_levels(sw, fcfg).items():
            ax.axhline(price, color=t["purple"], linewidth=0.7, alpha=0.7)
            ax.text(len(show) * 1.005, price, f"{ratio:g}", fontsize=6,
                    color=t["purple"], va="center")
        lo, hi = fib.golden_pocket(sw)
        ax.axhspan(lo, hi, color=t["purple"], alpha=0.14, zorder=0)
        ax.scatter([sw.lo_idx, sw.hi_idx], [sw.lo, sw.hi], s=26, color=t["orange"],
                   zorder=6)
        ax.set_title(f"{sym}: swing over {s['fib_lookback']} candles, "
                     f"{'up' if sw.up else 'down'}, a range of "
                     f"{sw.rng / max(sw.hi, 1e-9) * 100:.1f} per cent of price; "
                     f"the shaded band is the 0.5 to 0.618 pocket", fontsize=8)
    ax.set_ylabel("price")
    _date_axis(ax, show, t)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# On the run's own blind period
# ---------------------------------------------------------------------------

def draw_reliability(cfg, t, ctx):
    p, y = ctx.get("p_blind"), ctx.get("y_blind")
    fig, ax = _fig(t, h=3.4, w=5.2)
    if p is None:
        _nothing(ax, t, "no fitted model on this run to score the test period with")
        return fig
    bins = int(cfg["calibration"].get("bins") or 10)
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges) - 1, 0, bins - 1)
    xs, ys, ns = [], [], []
    for b in range(bins):
        m = idx == b
        if m.sum() < 5:
            continue
        xs.append(float(p[m].mean())); ys.append(float(y[m].mean())); ns.append(int(m.sum()))
    ax.plot([0, 1], [0, 1], color=t["rule"], linestyle="--", linewidth=0.9)
    ax.axhline(float(y.mean()), color=t["soft"], linewidth=0.8)
    ax.scatter(xs, ys, s=np.clip(np.array(ns) / max(ns) * 120, 12, 120),
               color=t["blue"], zorder=5)
    ax.plot(xs, ys, color=t["blue"], linewidth=1.0)
    ax.set_xlabel("stated probability"); ax.set_ylabel("how often it happened")
    ax.set_title(f"{ctx['model']} on {len(p):,} test rows, {bins} bins; the flat line "
                 f"is the base rate {y.mean():.3f}", fontsize=8)
    fig.tight_layout()
    return fig


def draw_importance(cfg, t, ctx):
    fig, ax = _fig(t, h=3.8, w=5.6)
    est, test, feats = ctx.get("est"), ctx.get("test"), ctx.get("feats")
    if est is None or test is None:
        _nothing(ax, t, "no fitted model on this run")
        return fig
    from sklearn.inspection import permutation_importance
    n = min(len(test), 4000)
    part = test.iloc[-n:]
    try:
        r = permutation_importance(est, part[feats], part["label"], n_repeats=3,
                                   random_state=0, scoring="neg_brier_score")
    except Exception as exc:                            # noqa: BLE001
        _nothing(ax, t, f"permutation importance could not be measured: {exc}")
        return fig
    order = np.argsort(r.importances_mean)[-18:]
    ax.barh([feats[i] for i in order], r.importances_mean[order],
            xerr=r.importances_std[order], color=t["blue"], height=0.7,
            error_kw=dict(ecolor=t["soft"], elinewidth=0.6))
    ax.tick_params(axis="y", labelsize=6)
    ax.set_xlabel("rise in Brier score when the column is shuffled")
    ax.set_title(f"{ctx['model']}: the {len(order)} columns of {len(feats)} that mattered most, "
                 f"on {n:,} test rows", fontsize=8)
    fig.tight_layout()
    return fig


def draw_selectivity(cfg, t, ctx):
    fig, ax = _fig(t, h=3.4, w=5.4)
    p, test = ctx.get("p_blind"), ctx.get("test")
    if p is None or test is None or "trade_ret" not in test.columns:
        _nothing(ax, t, "no fitted model, or this frame carries no trade return")
        return fig
    import train_model as tm
    # A user's stock run pays 0.10 per cent, not the crypto 0.20; demo_run passes it.
    cost = ctx.get("cost", tm.COST_PCT / 100.0)
    ret = test["trade_ret"].to_numpy(float)
    ok = np.isfinite(ret)
    qs = np.arange(0.0, 0.96, 0.05)
    xs, ys, ns = [], [], []
    for q in qs:
        thr = np.quantile(p[ok], q)
        m = ok & (p >= thr)
        if m.sum() < 30:
            continue
        xs.append(float(q)); ys.append(float(ret[m].mean() - cost)); ns.append(int(m.sum()))
    if not xs:
        _nothing(ax, t, "too few test rows to draw a selectivity curve")
        return fig
    ax.plot(xs, np.array(ys) * 100, color=t["blue"], linewidth=1.2, marker="o",
            markersize=3)
    ax.axhline(0, color=t["ink"], linewidth=0.9)
    ax.axhline((ret[ok].mean() - cost) * 100, color=t["soft"], linestyle="--",
               linewidth=0.9)
    ax.set_xlabel("share of test rows skipped, least confident first")
    ax.set_ylabel("return per trade after cost, per cent")
    ax.set_title(f"{ctx['model']}: charging {cost * 100:.2f} per cent a trade; the dashed "
                 f"line is taking every row, {(ret[ok].mean() - cost) * 100:+.3f} per cent",
                 fontsize=8)
    fig.tight_layout()
    return fig


def draw_equity(cfg, t, ctx):
    fig, ax = _fig(t, h=3.4, w=5.6)
    p, test = ctx.get("p_blind"), ctx.get("test")
    if p is None or test is None or "trade_ret" not in test.columns:
        _nothing(ax, t, "no fitted model, or this frame carries no trade return")
        return fig
    import train_model as tm
    cost = ctx.get("cost", tm.COST_PCT / 100.0)
    d = test.assign(p=p).sort_values("datetime")
    ret = d["trade_ret"].to_numpy(float)
    thr = np.nanquantile(d["p"].to_numpy(float), 0.8)
    taken = np.isfinite(ret) & (d["p"].to_numpy(float) >= thr)
    if taken.sum() < 5:
        _nothing(ax, t, "fewer than five trades taken on the test period")
        return fig
    curve = np.cumprod(1.0 + ret[taken] - cost)
    market = np.cumprod(1.0 + ret[np.isfinite(ret)] - cost)
    when = pd.to_datetime(d["datetime"].to_numpy()[taken])
    ax.plot(when, (curve - 1) * 100, color=t["blue"], linewidth=1.2)
    ax.plot(pd.to_datetime(d["datetime"].to_numpy()[np.isfinite(ret)]),
            (market - 1) * 100, color=t["soft"], linewidth=1.0, linestyle="--")
    ax.axhline(0, color=t["ink"], linewidth=0.9)
    ax.set_ylabel("cumulative return, per cent")
    ax.set_title(f"{ctx['model']}: the top fifth by stated probability, "
                 f"{int(taken.sum()):,} trades at {cost * 100:.2f} per cent each, against "
                 f"the dashed line of taking every row", fontsize=8)
    ax.tick_params(axis="x", labelsize=6)
    fig.tight_layout()
    return fig


PANELS = {
    "candles": draw_candles, "macd": draw_macd, "confluence": draw_confluence,
    "fibonacci": draw_fibonacci, "reliability": draw_reliability,
    "importance": draw_importance, "selectivity": draw_selectivity,
    "equity": draw_equity,
}


# What Choose Figures draws when nothing is ticked. The panel's note has
# promised these two since the form was written; until 20 September 2026 the run
# drew neither, because it drew nothing at all.
DEFAULT_PANELS = ("reliability", "importance")


def draw_all(cfg: dict, rows=None, est=None, train=None, test=None, feats=None,
             log=print, stamp=None) -> list[dict]:
    """Every figure Choose Figures ticked, written beside the record."""
    want = [p for p in (cfg["viz"].get("panels") or DEFAULT_PANELS) if p in PANELS]
    if not want:
        return []
    stamp = stamp or datetime.now()
    day = REPO / "04-outputs" / "AA-evals" / stamp.strftime("%Y-%m-%d")
    out_dir = day / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    t = _theme(cfg)

    ctx: dict = dict(est=est, train=train, test=test, feats=feats,
                     model=(rows[0]["model"] if rows else "the model"))
    if est is not None and test is not None and feats:
        try:
            ctx["p_blind"] = est.predict_proba(test[feats])[:, 1]
            ctx["y_blind"] = test["label"].to_numpy()
        except Exception as exc:                        # noqa: BLE001
            log(f"  test probabilities unavailable for the figures: {exc}")

    drawn = []
    log(f"figures: {', '.join(want)}, {cfg['viz'].get('theme', 'light')} theme")
    for name in want:
        rel = f"figures/bench-{stamp:%Y%m%d-%H%M%S}-{name}.png"
        path = day / rel
        try:
            fig = PANELS[name](cfg, t, ctx)
        except Exception as exc:                        # noqa: BLE001
            fig, ax = _fig(t)
            _nothing(ax, t, f"{name} could not be drawn:\n{type(exc).__name__}: {exc}")
            log(f"  {name}: {type(exc).__name__}: {exc}")
        fig.savefig(path, facecolor=t["bg"], bbox_inches="tight")
        plt.close(fig)
        drawn.append(dict(panel=name, file=rel, what=WHAT[name],
                          bytes=path.stat().st_size))
        log(f"  {name} -> {rel} ({path.stat().st_size:,} bytes)")
    return drawn
