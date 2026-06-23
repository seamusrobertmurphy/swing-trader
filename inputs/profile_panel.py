"""profile_panel.py - Stage B: profile the panel to choose split parameters from evidence.

Stage C (the walk-forward splitter) names parameters it cannot responsibly set without
first looking at the data: the usable start date, the minimum-history threshold, the
continuity/liquidity cut-offs, and the per-fold universe. This module measures the panel's
properties so each of those is justified by a diagnostic rather than assumed. See
tasks/task-request-data-pipeline-methodology.md (Stage B).

It reads the RAW 1h kline zips under inputs/binance-data/klines_1h/<SYMBOL>/ (the
survivorship-complete set produced by acquire_vision.py), one symbol at a time, so the full
panel never has to fit in memory and zero-volume / zero-range bars are counted faithfully
(the aggregated flow table drops them, which would hide exactly the quality signal B.6
wants). Timestamps are treated as tz-aware UTC throughout and the ms->us unit change at
2025-01 is normalised at load.

Diagnostics (one streaming pass per symbol builds the metadata row that combines B.1/B.2/B.6):
  B.1 coverage & lifespan      first/last bar, bar count, span, realised/expected ratio
  B.2 gap & continuity         missing-bar run-lengths, gap count, largest gap, halt flag
  B.3 listing/delisting        monthly entry, exit, cumulative-active series
  B.4 breadth-over-time        count of alive-and-eligible symbols per month
  B.5 survivorship audit       active vs delisted vs the dated snapshot; delisted share
  B.6 liquidity & quality      volume distribution, zero-volume/zero-range/stale-run counts
  B.7 point-in-time universe   per fold-open date, the eligible set using only past info
  B.8 threshold sensitivity    survivor counts as min-history / coverage cut-offs sweep
  B.9 parameter decisions      usable start, min-history, point-of-entry rule, justified
  B.10 persist artefacts       metadata table, entry/exit log, breadth curve, monthly QV,
                               per-fold universe lists, decision summary (run-timestamped)

Symbol convention: Stage B works in the on-disk 'BTCUSDT' form (matches klines_1h folders
and the crawl). build_dataset_1h writes the dataset symbol as 'BTC/USDT', so the persisted
per-fold universe lists carry BOTH forms and Stage C matches on whichever the dataset uses.

Plain ASCII. No orders, read-only. Causal: every per-fold filter uses only data at/before
the fold-open date.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import zipfile
from datetime import datetime, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
BINANCE_DATA = os.path.join(HERE, "binance-data")
DEFAULT_KLINES_ROOT = os.path.join(BINANCE_DATA, "klines_1h")
PROFILE_ROOT = os.path.join(os.path.dirname(HERE), "outputs", "3A-training-test-data",
                            "panel-profile")             # run-stamped subdirs -> main outputs tree

KLINE_COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
              "quote_volume", "num_trades", "taker_buy_base", "taker_buy_quote", "ignore"]

# Defaults; every one is a named parameter so the sweep (B.8) and decision summary (B.9)
# can record exactly what was used. They can be overridden from the CLI / driver.
DEFAULTS = dict(
    interval="1h",
    coverage_cut=0.90,          # realised/expected bar ratio a coin must clear (B.1/B.4)
    max_single_gap_hours=72,    # a hole longer than this flags a halt/delist (B.2)
    breadth_floor=30,           # min alive-and-eligible coins for a "usable" month (B.9)
    pit_min_history_days=125,   # placeholder; B.9 derives the real value from feature windows
    pit_trailing_qv_months=1,   # trailing window for the point-in-time liquidity screen (B.7)
    pit_min_quote_volume=30_000_000,   # trailing quote-volume floor, USDT (mirrors SCREEN)
    stale_run_flag=24,          # >= this many identical consecutive closes flags a stale run
)


# --------------------------------------------------------------------------- #
# Loading (one symbol at a time)
# --------------------------------------------------------------------------- #
def _to_datetime(series: pd.Series) -> pd.Series:
    """ms vs microsecond open_time (Binance switched mid-2025), possibly MIXED within one
    coin's archives. Classify per value (us > 1e14 > ms), normalise ms up to us, parse as
    tz-aware UTC. Mixing naive and aware timestamps corrupts the gap arithmetic silently."""
    v = pd.to_numeric(series, errors="coerce")
    v_us = v.where(v > 1e14, v * 1000)
    return pd.to_datetime(v_us, unit="us", utc=True)


def _read_zip(path: str) -> pd.DataFrame:
    with zipfile.ZipFile(path) as z:
        name = z.namelist()[0]
        raw = z.read(name)
    first = raw[:64].decode("utf-8", "ignore").split(",")[0].strip()
    header = 0 if first and not first.replace(".", "").isdigit() else None
    return pd.read_csv(io.BytesIO(raw), header=header, names=KLINE_COLS)


def list_symbols(root: str = DEFAULT_KLINES_ROOT) -> list:
    """Every symbol folder on disk that holds at least one (non-AppleDouble) zip."""
    if not os.path.isdir(root):
        return []
    out = []
    for s in sorted(os.listdir(root)):
        d = os.path.join(root, s)
        if os.path.isdir(d) and any(f.endswith(".zip") and not f.startswith("._")
                                    for f in os.listdir(d)):
            out.append(s)
    return out


def load_symbol_bars(symbol: str, root: str = DEFAULT_KLINES_ROOT) -> pd.DataFrame | None:
    """Read every zip for one symbol into a tz-aware-UTC-indexed OHLCV frame, deduped and
    sorted on bar-open time. Returns None if nothing readable. Does NOT drop zero-volume
    bars -- B.6 needs to count them."""
    sym_dir = os.path.join(root, symbol)
    if not os.path.isdir(sym_dir):
        return None
    frames = []
    for fn in sorted(os.listdir(sym_dir)):
        if not fn.endswith(".zip") or fn.startswith("._"):
            continue
        try:
            frames.append(_read_zip(os.path.join(sym_dir, fn)))
        except Exception as e:
            print(f"  skip {symbol}/{fn}: {e}")
    if not frames:
        return None
    d = pd.concat(frames, ignore_index=True)
    d["dt"] = _to_datetime(d["open_time"])
    for c in ["open", "high", "low", "close", "volume", "quote_volume", "num_trades",
              "taker_buy_base"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = (d.dropna(subset=["dt"]).drop_duplicates("dt").sort_values("dt")
         .set_index("dt"))
    return d[["open", "high", "low", "close", "volume", "quote_volume", "num_trades",
              "taker_buy_base"]]


# --------------------------------------------------------------------------- #
# B.1 + B.2 + B.6 in one per-symbol pass -> a metadata row
# --------------------------------------------------------------------------- #
def _gap_stats(index: pd.DatetimeIndex, freq="1h"):
    """Reindex onto the complete hourly index over the symbol's OWN span (not the global
    span, or every coin shows huge leading/trailing gaps), find the missing positions, and
    run-length them. Returns (n_gaps, max_gap_hours, total_missing, expected_bars)."""
    full = pd.date_range(index.min(), index.max(), freq=freq)
    expected = len(full)
    present = index.isin(set(index))   # trivially true; we compare against `full` instead
    missing_mask = ~full.isin(set(index))
    total_missing = int(missing_mask.sum())
    if total_missing == 0:
        return 0, 0, 0, expected
    # run-length: positions of missing bars; a break in consecutive integer positions ends a gap
    pos = np.flatnonzero(missing_mask)
    splits = np.split(pos, np.flatnonzero(np.diff(pos) > 1) + 1)
    gap_lens = [len(s) for s in splits]
    return len(gap_lens), int(max(gap_lens)), total_missing, expected


def profile_symbol(symbol: str, root: str = DEFAULT_KLINES_ROOT, cfg: dict = DEFAULTS) -> dict | None:
    """One streaming pass over a symbol's bars -> the metadata row combining B.1, B.2, B.6."""
    bars = load_symbol_bars(symbol, root)
    if bars is None or len(bars) == 0:
        return None
    idx = bars.index
    first, last = idx.min(), idx.max()
    n_bars = len(bars)
    span_hours = int((last - first) / pd.Timedelta(hours=1)) + 1
    n_gaps, max_gap_h, total_missing, expected = _gap_stats(idx)
    coverage = n_bars / expected if expected else 0.0

    vol = bars["volume"].fillna(0)
    qv = bars["quote_volume"].fillna(0)
    n_zero_vol = int((vol <= 0).sum())
    rng = (bars[["open", "high", "low", "close"]].nunique(axis=1) == 1)   # o==h==l==c
    n_zero_range = int(rng.sum())
    # longest run of identical consecutive closes (stale price)
    close = bars["close"].values
    if len(close) > 1:
        change = np.r_[True, close[1:] != close[:-1]]
        run_ids = np.cumsum(change)
        stale_run = int(pd.Series(run_ids).value_counts().max())
    else:
        stale_run = 1

    return dict(
        symbol=symbol,
        first_bar=first, last_bar=last, n_bars=n_bars,
        span_hours=span_hours, expected_bars=expected, coverage=round(coverage, 4),
        n_gaps=n_gaps, max_gap_hours=max_gap_h, total_missing=total_missing,
        gap_ratio=round(total_missing / expected, 4) if expected else 0.0,
        halt_flag=bool(max_gap_h > cfg["max_single_gap_hours"]),
        quote_volume_median=float(qv.median()), quote_volume_total=float(qv.sum()),
        n_zero_volume=n_zero_vol, n_zero_range=n_zero_range,
        stale_run_max=stale_run,
        illiquid_flag=bool((n_zero_vol / n_bars) > 0.05 or stale_run >= cfg["stale_run_flag"]),
    )


def build_metadata(symbols: list, root: str = DEFAULT_KLINES_ROOT, cfg: dict = DEFAULTS,
                   verbose=True) -> pd.DataFrame:
    """B.1/B.2/B.6 over the whole panel -> the master eligibility table, one row per symbol."""
    rows = []
    for i, s in enumerate(symbols, 1):
        r = profile_symbol(s, root, cfg)
        if r:
            rows.append(r)
        if verbose and i % 50 == 0:
            print(f"  profiled {i}/{len(symbols)} symbols...")
    md = pd.DataFrame(rows)
    if not md.empty:
        md = md.sort_values("first_bar").reset_index(drop=True)
    return md


# --------------------------------------------------------------------------- #
# Per-symbol monthly quote-volume (feeds the point-in-time liquidity screen, B.7)
# --------------------------------------------------------------------------- #
def build_monthly_qv(symbols: list, root: str = DEFAULT_KLINES_ROOT, verbose=True) -> pd.DataFrame:
    """Per symbol per calendar month: summed quote volume and bar count. Cheap, and it is
    what makes the B.7 liquidity screen point-in-time (trailing volume as-of the fold open,
    never lifetime volume, which would leak the future into universe membership)."""
    rows = []
    for i, s in enumerate(symbols, 1):
        bars = load_symbol_bars(s, root)
        if bars is None:
            continue
        months = bars.index.tz_localize(None).to_period("M")   # UTC wall-time; tz stripped to quiet the period warning
        m = bars["quote_volume"].fillna(0).groupby(months).agg(["sum", "count"])
        for period, (qsum, cnt) in m.iterrows():
            rows.append(dict(symbol=s, month=period.to_timestamp().tz_localize("UTC"),
                             quote_volume=float(qsum), n_bars=int(cnt)))
        if verbose and i % 50 == 0:
            print(f"  monthly QV {i}/{len(symbols)}...")
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# B.3 listing/delisting timeline + B.4 breadth-over-time
# --------------------------------------------------------------------------- #
def listing_timeline(md: pd.DataFrame) -> pd.DataFrame:
    """Monthly entries (first bar), exits (last bar), net, and cumulative-active."""
    first_m = md["first_bar"].dt.tz_localize(None).dt.to_period("M")
    last_m = md["last_bar"].dt.tz_localize(None).dt.to_period("M")
    entries = first_m.value_counts().sort_index()
    exits = last_m.value_counts().sort_index()
    idx = pd.period_range(min(first_m.min(), last_m.min()), max(first_m.max(), last_m.max()), freq="M")
    tl = pd.DataFrame({"entries": entries.reindex(idx, fill_value=0),
                       "exits": exits.reindex(idx, fill_value=0)})
    tl["net"] = tl["entries"] - tl["exits"]
    tl["cumulative_active"] = tl["net"].cumsum()
    tl.index = idx.to_timestamp().tz_localize("UTC")
    tl.index.name = "month"
    return tl.reset_index()


def breadth_curve(md: pd.DataFrame, cfg: dict = DEFAULTS) -> pd.DataFrame:
    """B.4: per month, how many symbols are alive (first<=month<=last) and, separately, how
    many are alive AND clear the coverage cut. The usable window should start where the
    eligible count first supports a cross-sectional model (B.9)."""
    months = (pd.period_range(md["first_bar"].min().tz_localize(None).to_period("M"),
                              md["last_bar"].max().tz_localize(None).to_period("M"), freq="M")
              .to_timestamp().tz_localize("UTC"))
    fb = md["first_bar"].values
    lb = md["last_bar"].values
    cov_ok = (md["coverage"] >= cfg["coverage_cut"]).values
    rows = []
    for m in months:
        m64 = np.datetime64(m.tz_convert("UTC").tz_localize(None))
        alive = (fb <= m64) & (lb >= m64)
        rows.append(dict(month=m, n_alive=int(alive.sum()),
                         n_eligible=int((alive & cov_ok).sum())))
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# B.5 survivorship audit
# --------------------------------------------------------------------------- #
def survivorship_audit(md: pd.DataFrame, active_symbols: list) -> dict:
    """Partition the profiled panel against the dated active snapshot and quantify the
    delisted share and the bar volume the dead coins contribute. A near-zero delisted
    share means the panel is survivor-contaminated and Stage A must be revisited."""
    act = set(active_symbols)
    md = md.copy()
    md["active"] = md["symbol"].isin(act)
    n = len(md)
    dead = md[~md["active"]]
    return dict(n_symbols=n, n_active=int(md["active"].sum()), n_delisted=int((~md["active"]).sum()),
                delisted_share=float((~md["active"]).mean()) if n else 0.0,
                dead_bar_share=float(dead["n_bars"].sum() / md["n_bars"].sum()) if md["n_bars"].sum() else 0.0,
                active_flag=md[["symbol", "active"]])


# --------------------------------------------------------------------------- #
# B.7 point-in-time universe construction
# --------------------------------------------------------------------------- #
def pit_universe(fold_open: pd.Timestamp, md: pd.DataFrame, monthly_qv: pd.DataFrame | None,
                 cfg: dict = DEFAULTS) -> list:
    """The eligible symbol set for one fold-open date, using ONLY information available at
    that date: listed at least `pit_min_history_days` before the open, still trading at the
    open (last_bar >= open), clearing the coverage cut, and -- if monthly_qv is given --
    passing a TRAILING quote-volume floor computed over the months before the open. Lifetime
    volume is never used; that would leak the future into membership (B.7)."""
    fold_open = pd.Timestamp(fold_open)
    if fold_open.tzinfo is None:
        fold_open = fold_open.tz_localize("UTC")
    min_hist = pd.Timedelta(days=cfg["pit_min_history_days"])
    listed = md["first_bar"] <= (fold_open - min_hist)
    alive = md["last_bar"] >= fold_open
    cov_ok = md["coverage"] >= cfg["coverage_cut"]
    cand = md[listed & alive & cov_ok]
    if monthly_qv is None or monthly_qv.empty:
        return sorted(cand["symbol"].tolist())
    # trailing liquidity: sum quote volume over the months strictly before the open
    lo = fold_open - pd.DateOffset(months=cfg["pit_trailing_qv_months"])
    win = monthly_qv[(monthly_qv["month"] >= lo) & (monthly_qv["month"] < fold_open)]
    qv = win.groupby("symbol")["quote_volume"].sum()
    liquid = set(qv[qv >= cfg["pit_min_quote_volume"]].index)
    return sorted(s for s in cand["symbol"] if s in liquid)


def per_fold_universes(fold_opens: list, md: pd.DataFrame, monthly_qv: pd.DataFrame | None,
                       cfg: dict = DEFAULTS) -> dict:
    """Recompute the point-in-time universe forward for each fold-open date. Proves
    membership never depends on the future. Returns {iso_date: [symbols...]}."""
    return {pd.Timestamp(d).strftime("%Y-%m-%d"): pit_universe(d, md, monthly_qv, cfg)
            for d in fold_opens}


# --------------------------------------------------------------------------- #
# B.8 threshold sensitivity
# --------------------------------------------------------------------------- #
def threshold_sweep(md: pd.DataFrame, monthly_qv: pd.DataFrame | None, fold_opens: list,
                    hist_days_grid=(60, 90, 125, 180, 270), cov_grid=(0.80, 0.90, 0.95),
                    cfg: dict = DEFAULTS) -> pd.DataFrame:
    """Sweep min-history and coverage cut-offs across a small grid and report how many
    symbols survive and the median per-fold universe size. A choice that loses or gains a
    third of the universe under a small change must be made consciously, not by default."""
    rows = []
    for h in hist_days_grid:
        for c in cov_grid:
            cc = dict(cfg); cc["pit_min_history_days"] = h; cc["coverage_cut"] = c
            n_survive = int((md["coverage"] >= c).sum())
            sizes = [len(pit_universe(d, md, monthly_qv, cc)) for d in fold_opens]
            rows.append(dict(min_history_days=h, coverage_cut=c,
                             n_symbols_pass_coverage=n_survive,
                             fold_universe_median=int(np.median(sizes)) if sizes else 0,
                             fold_universe_min=int(np.min(sizes)) if sizes else 0,
                             fold_universe_max=int(np.max(sizes)) if sizes else 0))
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# B.9 parameter decisions
# --------------------------------------------------------------------------- #
def _feature_windows():
    """Longest feature lookback (bars) and label horizon (bars) from build_dataset_1h, so
    the minimum-history floor is tied to what the pipeline actually needs to produce one
    clean labelled observation. Falls back to literals if the import is unavailable."""
    try:
        import build_dataset_1h as b1
        longest_feat = max([b1.WC["ema_slow"], b1.WC["rsi"], b1.WC["atr"], b1.WC["rv_long"]]
                           + list(b1.WC["mom"]))
        horizon = b1.LABEL["horizon_bars"]
        bars_per_day = b1.BARS_PER_DAY
    except Exception:
        longest_feat, horizon, bars_per_day = 125 * 24, 48, 24
    return longest_feat, horizon, bars_per_day


def decide_parameters(md: pd.DataFrame, breadth: pd.DataFrame, cfg: dict = DEFAULTS,
                      buffer_days=30) -> dict:
    """Translate the diagnostics into the parameters the splitter consumes, each stated with
    the diagnostic that justified it (B.9)."""
    longest_feat, horizon, bpd = _feature_windows()
    min_history_bars = longest_feat + horizon + buffer_days * bpd
    min_history_days = int(np.ceil(min_history_bars / bpd))

    usable = breadth[breadth["n_eligible"] >= cfg["breadth_floor"]]
    usable_start = usable["month"].min() if not usable.empty else None

    return {
        "usable_start_date": (usable_start.strftime("%Y-%m-%d") if usable_start is not None else None),
        "usable_start_justification":
            f"first month with >= {cfg['breadth_floor']} alive-and-eligible coins "
            f"(breadth curve B.4); before this the panel is too thin for a cross-sectional model",
        "min_history_bars": int(min_history_bars),
        "min_history_days": min_history_days,
        "min_history_justification":
            f"longest feature lookback ({longest_feat} bars) + label horizon ({horizon} bars) "
            f"+ {buffer_days}d buffer; the floor exceeds what the pipeline needs for one clean "
            f"labelled observation, with margin",
        "coverage_cut": cfg["coverage_cut"],
        "max_single_gap_hours": cfg["max_single_gap_hours"],
        "trailing_qv_months": cfg["pit_trailing_qv_months"],
        "min_quote_volume_usdt": cfg["pit_min_quote_volume"],
        "point_of_entry_rule":
            "coin enters at its first valid bar (realistic; mirrors when trading would "
            "actually begin) rather than requiring it to span the full fold; the per-fold "
            "universe (B.7) records membership so coins cannot drift in and out invisibly",
        "purge_embargo_bars": int(max(longest_feat, horizon)),
        "purge_embargo_days": int(np.ceil(max(longest_feat, horizon) / bpd)),
        "purge_embargo_justification":
            "max(longest feature lookback, label horizon); bars within this distance of a "
            "fold cut share information across the seam (Lopez de Prado purge/embargo)",
    }


# --------------------------------------------------------------------------- #
# Symbol-form helpers (Stage C matches on the dataset's symbol convention)
# --------------------------------------------------------------------------- #
def to_slash(sym: str, quote="USDT") -> str:
    """'BTCUSDT' -> 'BTC/USDT' (the form build_dataset_1h writes into the dataset)."""
    return f"{sym[:-len(quote)]}/{quote}" if sym.endswith(quote) else sym


# --------------------------------------------------------------------------- #
# Plots (plain, static diagnostics)
# --------------------------------------------------------------------------- #
def make_plots(timeline: pd.DataFrame, breadth: pd.DataFrame, md: pd.DataFrame, out_dir: str):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"  (matplotlib unavailable, skipping plots: {e})")
        return []
    paths = []

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(timeline["month"], timeline["entries"], width=20, label="entries")
    ax.bar(timeline["month"], -timeline["exits"], width=20, label="exits")
    ax2 = ax.twinx()
    ax2.plot(timeline["month"], timeline["cumulative_active"], color="black", lw=1.2,
             label="cumulative active")
    ax.set_title("Listing / delisting timeline"); ax.legend(loc="upper left"); ax2.legend(loc="lower right")
    p = os.path.join(out_dir, "timeline.png"); fig.tight_layout(); fig.savefig(p, dpi=110); plt.close(fig)
    paths.append(p)

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(breadth["month"], breadth["n_alive"], label="alive")
    ax.plot(breadth["month"], breadth["n_eligible"], label="alive & eligible")
    ax.set_title("Breadth over time"); ax.set_ylabel("coins"); ax.legend()
    p = os.path.join(out_dir, "breadth.png"); fig.tight_layout(); fig.savefig(p, dpi=110); plt.close(fig)
    paths.append(p)

    fig, ax = plt.subplots(figsize=(9, 4))
    gl = md["max_gap_hours"].clip(upper=500)
    ax.hist(gl, bins=40)
    ax.set_title("Largest-gap distribution (hours, clipped at 500)"); ax.set_xlabel("hours")
    p = os.path.join(out_dir, "gap_distribution.png"); fig.tight_layout(); fig.savefig(p, dpi=110); plt.close(fig)
    paths.append(p)
    return paths


# --------------------------------------------------------------------------- #
# B.10 driver: compute everything and persist run-stamped artefacts
# --------------------------------------------------------------------------- #
def default_fold_opens(md: pd.DataFrame, n=6) -> list:
    """A simple yearly grid of fold-open dates spanning the panel, for B.7/B.8 demos. The
    real splitter (Stage C) sets its own boundaries; these just exercise the builder."""
    lo = md["first_bar"].min().tz_convert("UTC").normalize()
    hi = md["last_bar"].max().tz_convert("UTC").normalize()
    return list(pd.date_range(lo, hi, periods=n + 2)[1:-1])


def profile(root: str = DEFAULT_KLINES_ROOT, out_root: str = PROFILE_ROOT,
            active_symbols: list | None = None, cfg: dict = DEFAULTS,
            symbols: list | None = None, make_plot=True) -> dict:
    """Run B.1-B.10 and persist artefacts under out_root/<UTC-stamp>/. Returns the paths."""
    cfg = dict(DEFAULTS, **(cfg or {}))
    symbols = symbols or list_symbols(root)
    if not symbols:
        raise SystemExit(f"no symbol folders under {root}; run acquire_vision.py download first")
    print(f"profiling {len(symbols)} symbols from {root}")

    md = build_metadata(symbols, root, cfg)
    monthly_qv = build_monthly_qv(symbols, root)
    timeline = listing_timeline(md)
    breadth = breadth_curve(md, cfg)
    folds = default_fold_opens(md)
    decisions = decide_parameters(md, breadth, cfg)

    # use the derived min-history for the persisted per-fold universes
    cfg_pit = dict(cfg); cfg_pit["pit_min_history_days"] = decisions["min_history_days"]
    universes = per_fold_universes(folds, md, monthly_qv, cfg_pit)
    sweep = threshold_sweep(md, monthly_qv, folds, cfg=cfg)

    if active_symbols is None:
        try:
            import acquire_vision as av
            active_symbols, taken, _ = av.load_latest_snapshot(BINANCE_DATA)
            decisions["snapshot_taken_at"] = taken
        except Exception:
            active_symbols = []
    surv = survivorship_audit(md, active_symbols or [])
    md = md.merge(surv["active_flag"], on="symbol", how="left")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    out_dir = os.path.join(out_root, stamp)
    os.makedirs(out_dir, exist_ok=True)

    md.to_parquet(os.path.join(out_dir, "symbol_metadata.parquet"), index=False)
    md[["symbol", "first_bar", "last_bar", "n_bars", "active"]].to_csv(
        os.path.join(out_dir, "entry_exit_log.csv"), index=False)
    breadth.to_parquet(os.path.join(out_dir, "breadth_curve.parquet"), index=False)
    timeline.to_parquet(os.path.join(out_dir, "timeline.parquet"), index=False)
    monthly_qv.to_parquet(os.path.join(out_dir, "monthly_qv.parquet"), index=False)
    sweep.to_csv(os.path.join(out_dir, "threshold_sweep.csv"), index=False)
    # per-fold universes carry both symbol forms for Stage C
    uni_out = {d: {"raw": syms, "slash": [to_slash(s) for s in syms]}
               for d, syms in universes.items()}
    with open(os.path.join(out_dir, "per_fold_universe.json"), "w") as f:
        json.dump(uni_out, f, indent=2)
    decisions_full = dict(decisions, survivorship=surv | {"active_flag": None}, n_symbols=len(md),
                          fold_opens=[str(pd.Timestamp(d).date()) for d in folds],
                          generated_at=stamp, klines_root=root, config=cfg)
    decisions_full["survivorship"].pop("active_flag", None)
    with open(os.path.join(out_dir, "decision_summary.json"), "w") as f:
        json.dump(decisions_full, f, indent=2, default=str)

    plots = make_plots(timeline, breadth, md, out_dir) if make_plot else []

    # stable pointer so the splitter / report can find the latest run
    with open(os.path.join(out_root, "latest.txt"), "w") as f:
        f.write(out_dir)

    print(f"\nsurvivorship: {surv['n_symbols']} symbols, {surv['n_delisted']} delisted "
          f"({surv['delisted_share']:.1%}), dead bars {surv['dead_bar_share']:.1%}")
    print(f"usable start: {decisions['usable_start_date']} | min history: "
          f"{decisions['min_history_days']}d | purge/embargo: {decisions['purge_embargo_days']}d")
    print(f"artefacts -> {out_dir}")
    return dict(out_dir=out_dir, metadata=md, breadth=breadth, timeline=timeline,
                decisions=decisions_full, universes=universes, sweep=sweep, plots=plots)


def main():
    p = argparse.ArgumentParser(description="Stage B: profile the panel to choose split parameters")
    p.add_argument("--root", default=DEFAULT_KLINES_ROOT, help="klines_1h folder")
    p.add_argument("--out", default=PROFILE_ROOT, help="profile artefact root")
    p.add_argument("--coverage-cut", type=float, default=DEFAULTS["coverage_cut"])
    p.add_argument("--breadth-floor", type=int, default=DEFAULTS["breadth_floor"])
    p.add_argument("--limit", type=int, default=None, help="profile only the first N symbols (smoke test)")
    p.add_argument("--no-plots", action="store_true")
    a = p.parse_args()
    cfg = dict(DEFAULTS, coverage_cut=a.coverage_cut, breadth_floor=a.breadth_floor)
    syms = list_symbols(a.root)
    if a.limit:
        syms = syms[:a.limit]
    profile(a.root, a.out, cfg=cfg, symbols=syms, make_plot=not a.no_plots)


if __name__ == "__main__":
    main()
