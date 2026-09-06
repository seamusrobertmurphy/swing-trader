"""Build the labeled, scale-invariant 1-HOUR training dataset (all-market frame).

This is the 1h sibling of build_dataset.py. It is a NEW module so the daily ccxt
path stays untouched and revertible. Differences from the daily build, all decided
2026-06-21 (see tasks/build-decisions-2026-06-21.md):

  - Source: OFFLINE 1h kline archives under inputs/binance-data/klines_1h/<SYMBOL>/
    (downloaded by flow_data.py --interval 1h --all-market), not a live ccxt fetch.
    Reproducible and offline. Joins inputs/binance-data/flow_1h.csv for trade flow.
  - Universe: the full active USDT spot market, point-in-time screened per bar, not a
    fixed ten coins. Membership is written as an `in_sample` flag (see SCREEN).
  - Features: TWO window families on every coin -- a wall-clock family (the daily
    windows multiplied by 24, so a "14-day" EMA stays ~14 days = 336 hours) and a
    shorter intraday-native family -- plus an always-on in-house extra-indicator block
    (Williams %R, Stochastic, CCI, CMF, MFI, ADX/DMI, Aroon), an OPTIONAL pandas-ta breadth
    layer on top (PPO, TRIX, Vortex, CMO, Fisher, Chande Kroll Stop) used when pandas-ta is
    importable from the project .venv, and the trade-flow imbalance. The in-house baseline
    always computes, so the pipeline never hard-depends on pandas-ta. Every feature is
    scale-invariant and causal (uses only bars up to and including its own bar). The
    after-fee scoreboard decides which earn a place.
  - Label: a configurable, ATR-scaled, shorter-day-trade triple barrier. Default is
    +2 ATR before -1 ATR within 48 bars (2 days). Calibrated, not inherited; swept in
    Priority 1b. The last `horizon` bars of each coin are unresolvable and dropped.

Output columns: symbol, datetime, <f_* features...>, in_sample, label, trade_ret.
train_model.py (1h path) selects features by the `f_` prefix, filters to in_sample,
and reads label / trade_ret. The in-house baseline always computes; pandas-ta adds
breadth when present (run the 1h pipeline from the project .venv on the Mac).

Plain ASCII. No API key, no orders, read-only. Causal throughout.
"""
from __future__ import annotations

import argparse
import io
import os
import zipfile

import numpy as np
import pandas as pd

# ----------------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
BINANCE_DATA = os.path.join(HERE, "binance-data")
DEFAULT_KLINES_ROOT = os.path.join(BINANCE_DATA, "klines_1h")
DEFAULT_FLOW = os.path.join(BINANCE_DATA, "flow_1h.parquet")
DEFAULT_FLOW_CSV = DEFAULT_FLOW          # back-compat alias; read_frame() picks .parquet or .csv
DATASET_FILE = "dataset_1h_allmarket.parquet"
DATASET_PATH = os.path.join(BINANCE_DATA, DATASET_FILE)


def read_frame(path):
    """Read a table, preferring Parquet. Given any path, read the .parquet sibling if present,
    else the .csv (datetime parsed as mixed precision). Returns a DataFrame, or None if neither
    exists. Parquet stores real dtypes, so datetimes come back as datetime64 with no reparse -- it
    also loads far faster and is ~5x smaller than the CSV."""
    base = os.path.splitext(path)[0]
    pq, csv = base + ".parquet", base + ".csv"
    if os.path.exists(pq):
        return pd.read_parquet(pq)
    if os.path.exists(csv):
        d = pd.read_csv(csv)
        if "datetime" in d.columns:
            d["datetime"] = pd.to_datetime(d["datetime"], format="mixed")
        return d
    return None


def write_frame(df, path, also_csv=False):
    """Write a table as Parquet (the .parquet sibling of `path`); optionally also dump a CSV copy
    for human spot-checking. Returns the parquet path."""
    base = os.path.splitext(path)[0]
    df.to_parquet(base + ".parquet", index=False)
    if also_csv:
        df.to_csv(base + ".csv", index=False)
    return base + ".parquet"

INTERVAL_HOURS = 1                 # decision-frame bar size in hours; configure() switches it
INTERVAL = "1h"
BARS_PER_DAY = 24                  # = round(24 / INTERVAL_HOURS); configure() keeps it in sync

# Binance spot kline CSV layout (no reliable header in the archives).
KLINE_COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
              "quote_volume", "num_trades", "taker_buy_base", "taker_buy_quote", "ignore"]

# ----------------------------------------------------------------------------
# Feature-window families. Wall-clock = daily windows x24 (preserve real-time
# lookback). Intraday = shorter, hourly-native windows. Momentum lookbacks are in BARS.
# ----------------------------------------------------------------------------
WC = dict(ema_fast=14 * 24, ema_mid=91 * 24, ema_slow=125 * 24, rsi=14 * 24,
          bb=14 * 24, bb_std=2.0, atr=14 * 24, rv_short=7 * 24, rv_long=30 * 24,
          vol=20 * 24, mom=[5 * 24, 10 * 24, 20 * 24, 60 * 24])      # 120,240,480,1440
HR = dict(ema_fast=12, ema_mid=26, ema_slow=50, rsi=14,
          bb=20, bb_std=2.0, atr=14, rv_short=24, rv_long=168,
          vol=24, mom=[6, 12, 24, 72, 168])

# ----------------------------------------------------------------------------
# Label: configurable, ATR-scaled, shorter-day-trade triple barrier.
# ----------------------------------------------------------------------------
LABEL = dict(tgt_atr=2.0, stp_atr=1.0, horizon_bars=48, atr_len=14)

# ----------------------------------------------------------------------------
# Point-in-time screen (1h-recalibrated from the daily four-gate screen). The daily
# ATR band 2.5-12% scales by ~1/sqrt(24) to a 1h band; spread is APPROXIMATED by a
# Corwin-Schultz high-low estimator (klines carry no top-of-book spread), gated on a
# proxy ceiling to be calibrated, not the live 0.05% top-of-book number.
# ----------------------------------------------------------------------------
SCREEN = dict(min_quote_volume_usdt=30_000_000, qv_window=BARS_PER_DAY,
              atr_floor_pct=0.5, atr_ceiling_pct=2.5, atr_len=14,
              min_history_bars=120 * BARS_PER_DAY,        # ~120 days lived through
              spread_proxy_ceiling_pct=0.5, spread_window=BARS_PER_DAY)

# Data-quality gates (hard rule, per tasks/data-standards.md). Exchange-grade means
# low-gap: the offline binance.vision archives are exchange-direct, but coins still
# halt or delist, leaving holes. Our features assume regularly-spaced hourly bars, so
# a coin with too many missing bars (or one very long hole) is excluded from training.
DATA_QUALITY = dict(max_gap_ratio=0.02,        # <=2% of expected hourly bars missing
                    max_single_gap_hours=72)   # no single hole longer than 3 days

EPS = 1e-8


# --------------------------------------------------------------------------- #
# Offline kline loading
# --------------------------------------------------------------------------- #
def _to_datetime(series: pd.Series) -> pd.Series:
    """ms vs microsecond timestamps (Binance switched mid-2025), possibly MIXED within one
    coin. Classify per value (us > 1e14 > ms), normalise ms up to us, then parse once."""
    v = pd.to_numeric(series, errors="coerce")
    v_us = v.where(v > 1e14, v * 1000)
    return pd.to_datetime(v_us, unit="us")


def _read_kline_zip(path: str) -> pd.DataFrame:
    with zipfile.ZipFile(path) as z:
        raw = z.read(z.namelist()[0])
    first = raw[:64].decode("utf-8", "ignore").split(",")[0].strip()
    header = 0 if first and not first.replace(".", "").isdigit() else None
    return pd.read_csv(io.BytesIO(raw), header=header, names=KLINE_COLS)


def load_coin(klines_root: str, symbol: str) -> pd.DataFrame:
    """Load all 1h kline zips for one symbol into a clean OHLCV+ frame, ascending."""
    sym_dir = os.path.join(klines_root, symbol)
    if not os.path.isdir(sym_dir):
        return pd.DataFrame()
    frames = []
    for fn in sorted(os.listdir(sym_dir)):
        if fn.endswith(".zip") and not fn.startswith("._"):   # skip macOS AppleDouble files
            try:
                frames.append(_read_kline_zip(os.path.join(sym_dir, fn)))
            except Exception as e:  # noqa: BLE001
                print(f"  skip {fn}: {e}")
    if not frames:
        return pd.DataFrame()
    d = pd.concat(frames, ignore_index=True)
    d["datetime"] = _to_datetime(d["open_time"])
    for c in ["open", "high", "low", "close", "volume", "quote_volume",
              "num_trades", "taker_buy_base"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = (d.dropna(subset=["close", "volume"]).drop_duplicates("datetime")
         .sort_values("datetime").reset_index(drop=True))
    return d[["datetime", "open", "high", "low", "close", "volume",
              "quote_volume", "num_trades", "taker_buy_base"]]


def load_btc_series(klines_root: str, symbol: str = "BTCUSDT"):
    """BTC close as a datetime-indexed Series (the crypto market beta), loaded once for the BTC
    lead-lag / relative-strength block. Returns None if BTC is absent."""
    d = load_coin(klines_root, symbol)
    if d.empty:
        return None
    idx = pd.to_datetime(d["datetime"]).astype("datetime64[ns]")
    return pd.Series(d["close"].to_numpy(float), index=idx)


# --------------------------------------------------------------------------- #
# Causal indicators
# --------------------------------------------------------------------------- #
def _rsi(close: pd.Series, length: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    ag = gain.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    al = loss.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    rs = ag / al.replace(0.0, np.nan)
    return 100 - 100 / (1 + rs)


def _atr_pct(df: pd.DataFrame, length: int) -> pd.Series:
    """ATR as a percent of close (causal, simple rolling mean of true range)."""
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([(h - l).abs(), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return (tr.rolling(length).mean() / c) * 100.0


def indicator_block(df: pd.DataFrame, prefix: str, w: dict, emit_rv_short: bool = True) -> dict:
    """One window family of scale-invariant, causal features under f_<prefix>_*.
    emit_rv_short=False suppresses the rv_short column (still used for rv_ratio); the WC
    family passes False because its rv_short (7d=168 bars) is identical to f_hr_rv_long
    (168 bars), a redundancy the EDA flagged at corr 1.0. rv_long and rv_ratio still emit."""
    close = df["close"]
    out = {}
    ema_f = close.ewm(span=w["ema_fast"], adjust=False).mean()
    ema_m = close.ewm(span=w["ema_mid"], adjust=False).mean()
    ema_s = close.ewm(span=w["ema_slow"], adjust=False).mean()
    out[f"f_{prefix}_ema_fast_mid"] = (ema_f - ema_m) / close
    out[f"f_{prefix}_ema_mid_slow"] = (ema_m - ema_s) / close
    out[f"f_{prefix}_rsi"] = _rsi(close, w["rsi"]) / 100.0
    bb_mid = close.rolling(w["bb"]).mean()
    bb_sd = close.rolling(w["bb"]).std(ddof=0)
    bbu, bbl = bb_mid + w["bb_std"] * bb_sd, bb_mid - w["bb_std"] * bb_sd
    out[f"f_{prefix}_bb_pos"] = (close - bbl) / (bbu - bbl).replace(0.0, np.nan)
    out[f"f_{prefix}_atr_pct"] = _atr_pct(df, w["atr"]) / 100.0
    ret = close.pct_change()
    rv_s, rv_l = ret.rolling(w["rv_short"]).std(), ret.rolling(w["rv_long"]).std()
    if emit_rv_short:
        out[f"f_{prefix}_rv_short"] = rv_s
    out[f"f_{prefix}_rv_long"] = rv_l
    out[f"f_{prefix}_rv_ratio"] = rv_s / (rv_l + EPS)
    out[f"f_{prefix}_vol_ratio"] = df["volume"] / (df["volume"].rolling(w["vol"]).mean() + EPS)
    for k in w["mom"]:
        out[f"f_{prefix}_mom_{k}"] = close / close.shift(k) - 1.0
    return out


def extra_ta_block(df: pd.DataFrame, length: int = 14) -> dict:
    """Always-on, hand-rolled extra indicators (no pandas-ta needed), all causal and
    scaled to roughly [-1,1] or [0,1] so one model spans all coins."""
    h, l, c, v = df["high"], df["low"], df["close"], df["volume"]
    out = {}
    hh, ll = h.rolling(length).max(), l.rolling(length).min()
    rng = (hh - ll).replace(0.0, np.nan)
    out["f_ta_willr"] = ((hh - c) / rng) * -1.0                       # ~[-1,0]
    out["f_ta_stochk"] = (c - ll) / rng                              # [0,1]
    tp = (h + l + c) / 3.0
    ma = tp.rolling(length).mean()
    md = (tp - ma).abs().rolling(length).mean()
    out["f_ta_cci"] = ((tp - ma) / (0.015 * md.replace(0.0, np.nan))) / 100.0
    mfm = (((c - l) - (h - c)) / (h - l).replace(0.0, np.nan)) * v
    out["f_ta_cmf"] = mfm.rolling(length).sum() / (v.rolling(length).sum() + EPS)
    rmf = tp * v
    pos = rmf.where(tp > tp.shift(1), 0.0)
    neg = rmf.where(tp < tp.shift(1), 0.0)
    mr = pos.rolling(length).sum() / (neg.rolling(length).sum() + EPS)
    out["f_ta_mfi"] = (100 - 100 / (1 + mr)) / 100.0
    # ADX / DMI (Wilder smoothing via RMA), trend strength + directional balance.
    up_move = h.diff()
    dn_move = -l.diff()
    plus_dm = up_move.where((up_move > dn_move) & (up_move > 0), 0.0)
    minus_dm = dn_move.where((dn_move > up_move) & (dn_move > 0), 0.0)
    pc = c.shift(1)
    tr = pd.concat([(h - l).abs(), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    rma_tr = tr.ewm(alpha=1 / length, adjust=False).mean()
    pdi = 100 * plus_dm.ewm(alpha=1 / length, adjust=False).mean() / (rma_tr + EPS)
    mdi = 100 * minus_dm.ewm(alpha=1 / length, adjust=False).mean() / (rma_tr + EPS)
    dx = ((pdi - mdi).abs() / (pdi + mdi).replace(0.0, np.nan)) * 100
    out["f_ta_adx"] = dx.ewm(alpha=1 / length, adjust=False).mean() / 100.0      # [0,1]
    out["f_ta_dmi_diff"] = (pdi - mdi) / 100.0                                   # ~[-1,1]
    # Aroon oscillator: how recently the window's extreme high vs low occurred.
    aroon_len = 25
    idx_hi = h.rolling(aroon_len + 1).apply(lambda x: float(np.argmax(x)), raw=True)
    idx_lo = l.rolling(aroon_len + 1).apply(lambda x: float(np.argmin(x)), raw=True)
    out["f_ta_aroon_osc"] = (idx_hi - idx_lo) / aroon_len                        # [-1,1]
    return out


def _ta_col(res, want=None):
    """Pull one Series from a pandas-ta result, tolerating its DataFrame/column quirks."""
    if res is None:
        return None
    if isinstance(res, pd.DataFrame):
        if want is not None:
            for cc in res.columns:
                if want.lower() in str(cc).lower():
                    return res[cc]
        return res.iloc[:, 0]
    return res


def pandas_ta_block(df: pd.DataFrame) -> dict:
    """OPTIONAL breadth from pandas-ta, under f_ta_pta_*, ON TOP of the always-on in-house
    indicators above. Used only where pandas-ta imports -- the project .venv on the Mac
    (pandas-ta 0.4.x, numpy-2 native). Skipped with a one-line note elsewhere (e.g. the
    sandbox), so the pipeline never hard-depends on it. All outputs are causal and made
    scale-invariant. Indicators chosen to ADD to, not duplicate, the in-house set; includes
    the Chande Kroll Stop. The numpy.NaN shim covers an older classic install if present."""
    try:
        if not hasattr(np, "NaN"):
            np.NaN = np.nan  # noqa: N816  (shim for a classic pandas_ta on numpy 2.x)
        import pandas_ta as ta
    except Exception:  # noqa: BLE001
        print("  (pandas-ta not importable; in-house indicators only this run)")
        return {}
    h, l, c = df["high"], df["low"], df["close"]
    out = {}
    try:                                                  # PPO histogram (scale-free MACD)
        s = _ta_col(ta.ppo(c), "PPOh")
        if s is not None:
            out["f_ta_pta_ppo_hist"] = s / 100.0
    except Exception:  # noqa: BLE001
        pass
    try:                                                  # TRIX (triple-EMA momentum)
        s = _ta_col(ta.trix(c), "TRIX_")
        if s is not None:
            out["f_ta_pta_trix"] = s
    except Exception:  # noqa: BLE001
        pass
    try:                                                  # Vortex: VI+ minus VI-
        vtx = ta.vortex(h, l, c, length=14)
        vip, vim = _ta_col(vtx, "VTXP"), _ta_col(vtx, "VTXM")
        if vip is not None and vim is not None:
            out["f_ta_pta_vortex_diff"] = vip - vim
    except Exception:  # noqa: BLE001
        pass
    try:                                                  # Chande Momentum Oscillator
        s = _ta_col(ta.cmo(c, length=14))
        if s is not None:
            out["f_ta_pta_cmo"] = s / 100.0
    except Exception:  # noqa: BLE001
        pass
    try:                                                  # Fisher Transform
        s = _ta_col(ta.fisher(h, l), "FISHERT_")
        if s is not None:
            out["f_ta_pta_fisher"] = s
    except Exception:  # noqa: BLE001
        pass
    try:                                                  # Chande Kroll Stop, both bands.
        # tvmode=False -> original Chande-Kroll (10,3,20), not TradingView's (10,1,9);
        # this matches research/templates/Chande_Kroll_Stop.ipynb.
        cksp = ta.cksp(h, l, c, tvmode=False)
        longs, shorts = _ta_col(cksp, "CKSPl"), _ta_col(cksp, "CKSPs")
        if longs is not None:
            out["f_ta_pta_cksp_long_dist"] = (c - longs) / c      # >0 when above the long stop
        if shorts is not None:
            out["f_ta_pta_cksp_short_dist"] = (shorts - c) / c    # >0 when below the short stop
    except Exception:  # noqa: BLE001
        pass
    return out


def talib_block(df: pd.DataFrame) -> dict:
    """OPTIONAL canonical/fast breadth from TA-Lib (the C library wheel), under f_tl_*, on
    top of the in-house and pandas-ta layers. Used only where talib imports (the project
    .venv). Deliberately NOT all 158 functions -- most duplicate what we already have. This
    is a curated set of what TA-Lib uniquely ADDS: a candlestick-pattern family, Hilbert-
    transform cycle features, Parabolic SAR and MESA adaptive-MA distances, the Ultimate
    Oscillator. All scale-invariant and causal. Skipped with a note if talib is absent."""
    try:
        import talib
    except Exception:  # noqa: BLE001
        print("  (TA-Lib not importable; skipping f_tl_* breadth this run)")
        return {}
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    out = {}
    for key, fn in (("sar_dist", lambda: (c - talib.SAR(h, l)) / c),
                    ("ultosc", lambda: talib.ULTOSC(h, l, c) / 100.0),
                    ("ht_trendmode", lambda: talib.HT_TRENDMODE(c).astype(float)),
                    ("ht_dcphase", lambda: talib.HT_DCPHASE(c) / 180.0),
                    ("mama_dist", lambda: (c - talib.MAMA(c)[0]) / c)):
        try:
            out[f"f_tl_{key}"] = fn()
        except Exception:  # noqa: BLE001
            pass
    # Curated candlestick patterns, each -100/0/100 -> -1/0/1 (naturally scale-invariant).
    patterns = {"engulfing": "CDLENGULFING", "hammer": "CDLHAMMER",
                "shootingstar": "CDLSHOOTINGSTAR", "doji": "CDLDOJI",
                "morningstar": "CDLMORNINGSTAR", "eveningstar": "CDLEVENINGSTAR",
                "three_white": "CDL3WHITESOLDIERS", "three_black": "CDL3BLACKCROWS",
                "harami": "CDLHARAMI", "marubozu": "CDLMARUBOZU"}
    for name, fn in patterns.items():
        try:
            out[f"f_tl_cdl_{name}"] = getattr(talib, fn)(o, h, l, c) / 100.0
        except Exception:  # noqa: BLE001
            pass
    return out


def flow_block(df: pd.DataFrame, flow: pd.DataFrame, symbol_slash: str) -> dict:
    """Join trade-flow imbalance from flow_1h.csv on (symbol, datetime); add causal
    rolling means. flow_imbalance is the bar's realized aggressive-buy share, known at
    bar close, the same timing as the close-based features, so no lookahead."""
    out = {}
    if flow is None:
        return out
    sub = flow[flow["symbol"] == symbol_slash][["datetime", "flow_imbalance", "taker_buy_ratio"]].copy()
    if sub.empty:
        return out
    # Coerce both merge keys to the same datetime resolution; flow_1h.csv may load 'datetime'
    # as a string and the kline datetime is datetime64[us], which pandas 3 refuses to merge.
    left = df[["datetime"]].copy()
    left["datetime"] = pd.to_datetime(left["datetime"]).astype("datetime64[ns]")
    # flow_1h.csv serialises timestamps with inconsistent sub-second precision, so parse mixed.
    sub["datetime"] = pd.to_datetime(sub["datetime"], format="mixed").astype("datetime64[ns]")
    merged = left.merge(sub, on="datetime", how="left")
    fi = merged["flow_imbalance"]
    out["f_flow_imb"] = fi.values
    out["f_flow_imb_24"] = fi.rolling(24).mean().values
    out["f_flow_imb_168"] = fi.rolling(168).mean().values
    out["f_flow_taker_ratio"] = merged["taker_buy_ratio"].values
    return out


# --------------------------------------------------------------------------- #
# BTC lead-lag and relative-strength block. Alts largely track BTC, so BTC's recent move (the
# market beta of crypto) and the coin's strength RELATIVE to BTC carry information that is NOT in
# the coin's own price history -- the first feature family here that is not a self-transform of the
# coin's price. Causal (bars up to t) and scale-invariant (returns, return differences, beta/corr).
# --------------------------------------------------------------------------- #
def btc_block(df: pd.DataFrame, btc) -> dict:
    """f_btc_* : BTC momentum (market state), the coin's momentum relative to BTC, and the coin's
    rolling beta and correlation to BTC. Empty dict if BTC is unavailable (e.g. building BTC itself
    against a missing series). For BTC vs itself the relatives are ~0 and beta/corr ~1, which is
    correct and harmless."""
    out = {}
    if btc is None:
        return out
    idx = pd.to_datetime(df["datetime"]).astype("datetime64[ns]").to_numpy()
    bc = btc.reindex(idx)
    if bc.isna().all():
        return out
    bc = pd.Series(bc.to_numpy(float), index=df.index)
    close = df["close"]
    bret, cret = bc.pct_change(), close.pct_change()
    for k in (6, 24, 168):                                     # BTC market-state momentum
        out[f"f_btc_mom_{k}"] = bc / bc.shift(k) - 1.0
    for k in (24, 168):                                        # relative strength vs BTC
        out[f"f_btc_rel_mom_{k}"] = (close / close.shift(k) - 1.0) - (bc / bc.shift(k) - 1.0)
    win = 168                                                  # rolling beta + correlation to BTC
    out["f_btc_beta_168"] = cret.rolling(win).cov(bret) / (bret.rolling(win).var() + EPS)
    out["f_btc_corr_168"] = cret.rolling(win).corr(bret)
    return out


# --------------------------------------------------------------------------- #
# Supertrend block, ported from the triple-Supertrend crypto bot this repo used
# to run. That bot was removed on 2026-09-06 with the crypto track; the maths it
# carried lives on here and in baseline_supertrend_1h.py.
# Three ATR-channel trend filters voting, plus an EMA-200 trend gate. Each band is
# the same recursive Supertrend as the live bot; the model consumes only causal,
# scale-invariant projections of it (signed distances / close, an agreement score,
# a reversal flip), never the raw price-level bands. Distinct from the existing
# f_ta_ trend set (ADX/DMI/Aroon) and f_tl_ SAR -- this is the ATR-channel flip the
# model otherwise lacks. The after-fee scoreboard decides if it earns a place.
# --------------------------------------------------------------------------- #
ST_BANDS = ((12, 3.0), (10, 1.0), (11, 2.0))   # (atr_period, atr_mult); the bot's own three bands
ST_EMA = 200


def _wilder_atr(df: pd.DataFrame, period: int) -> pd.Series:
    """ATR with Wilder smoothing (EMA, alpha=1/period), as the live bot uses."""
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([(h - l).abs(), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False).mean()


def _supertrend_band(df: pd.DataFrame, period: int, mult: float):
    """One Supertrend band. Returns (in_uptrend bool array, active-line array).
    Direct port of the bot's _apply_supertrend_band(); causal (bar i
    decides from bars up to i only). The active line is the lower band in an uptrend,
    the upper band in a downtrend -- the trailing stop the bot itself trades off."""
    hl2 = (df["high"].to_numpy(float) + df["low"].to_numpy(float)) / 2.0
    atr = _wilder_atr(df, period).to_numpy()
    upper = hl2 + mult * atr
    lower = hl2 - mult * atr
    close = df["close"].to_numpy(float)
    n = len(df)
    up = np.ones(n, dtype=bool)
    for i in range(1, n):
        if close[i] > upper[i - 1]:
            up[i] = True
        elif close[i] < lower[i - 1]:
            up[i] = False
        else:
            up[i] = up[i - 1]
            if up[i] and lower[i] < lower[i - 1]:
                lower[i] = lower[i - 1]
            if not up[i] and upper[i] > upper[i - 1]:
                upper[i] = upper[i - 1]
    line = np.where(up, lower, upper)
    return up, line


def supertrend_block(df: pd.DataFrame) -> dict:
    """f_st_* : three Supertrend bands voting, signed distance to each active line,
    a signed agreement score, the all-three-agree flag, the reversal flip, and the
    EMA-200 distance. All causal and scale-invariant, so one model spans every coin."""
    out = {}
    close = df["close"].to_numpy(float)
    ups = []
    for k, (period, mult) in enumerate(ST_BANDS, start=1):
        up, line = _supertrend_band(df, period, mult)
        ups.append(up)
        out[f"f_st_dist_{k}"] = (close - line) / close            # >0 when above the active line
    agree = np.sum(ups, axis=0)                                   # 0..3 bands in uptrend
    uptrend = agree == 3
    out["f_st_agree"] = (agree - 1.5) / 1.5                       # signed, ~[-1,1]
    out["f_st_uptrend"] = uptrend.astype(float)                  # 1.0 when all three agree
    flip = np.zeros(len(df))
    flip[1:] = uptrend[1:].astype(int) - uptrend[:-1].astype(int)  # +1 turns up, -1 turns down
    out["f_st_flip"] = flip
    ema200 = df["close"].ewm(span=ST_EMA, adjust=True).mean().to_numpy()
    out["f_st_ema200_dist"] = (close - ema200) / close            # the bot's trend gate
    return out


# --------------------------------------------------------------------------- #
# Multi-timeframe block: higher-resolution CONTEXT (4h + daily) merged causally onto the 1h frame.
# The decision cadence stays 1h -- this is multi-resolution TRAINING (the trend/structure the 1h bar
# sits inside), not multi-resolution TRADING, so there is no extra fee drag and only a small column
# cost, never 4-60x more rows. Each 1h bar sees only higher-tf bars CLOSED at or before it: the
# higher-tf candle is timestamped at its close (right edge) and merge_asof(direction="backward")
# picks the last one closed by the 1h bar. So within a day every 1h bar carries the PREVIOUS
# completed daily bar's features (piecewise-constant, lagged) -- no lookahead.
# --------------------------------------------------------------------------- #
MTF_RULES = (("4h", "f_4h"), ("1D", "f_d1"))


def _resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    g = df.set_index("datetime").resample(rule, label="right", closed="right")
    r = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(),
                      "close": g["close"].last(), "volume": g["volume"].sum()}).dropna()
    return r.reset_index()            # 'datetime' is the bar's CLOSE time (right edge)


def multitf_block(df: pd.DataFrame, rules=None) -> dict:
    """Higher-timeframe CONTEXT (e.g. f_4h_*, f_d1_*): a compact causal, scale-invariant set on
    resampled higher-timeframe candles (RSI, fast-slow EMA spread, momentum, ATR%, Supertrend
    direction), aligned onto the decision frame so bar t only sees higher-tf bars closed by t.
    `rules` defaults to the module MTF_RULES, which configure() retunes per interval."""
    if rules is None:
        rules = MTF_RULES
    out = {}
    base = df[["datetime"]].copy()
    base["datetime"] = pd.to_datetime(base["datetime"]).astype("datetime64[ns]")
    for rule, pre in rules:
        r = _resample_ohlcv(df, rule)
        if len(r) < 30:
            continue
        c = r["close"]
        feat = pd.DataFrame({"datetime": r["datetime"].astype("datetime64[ns]")})
        feat[f"{pre}_rsi"] = (_rsi(c, 14) / 100.0).values
        ef, es = c.ewm(span=12, adjust=False).mean(), c.ewm(span=26, adjust=False).mean()
        feat[f"{pre}_ema_fast_slow"] = ((ef - es) / c).values
        feat[f"{pre}_mom_10"] = (c / c.shift(10) - 1.0).values
        feat[f"{pre}_atr_pct"] = (_atr_pct(r, 14) / 100.0).values
        up, _ = _supertrend_band(r, 10, 3.0)
        feat[f"{pre}_st_up"] = up.astype(float)
        m = pd.merge_asof(base, feat.sort_values("datetime"), on="datetime", direction="backward")
        for col in feat.columns:
            if col != "datetime":
                out[col] = m[col].values
    return out


# --------------------------------------------------------------------------- #
# Modern Adaptive Supertrend (GBB) block. Ports the open-source Pine indicator's two layers that
# earned their place out-of-sample (L1 adaptive-period dropped: the author found no OOS value):
#   L2 - convex regime multiplier on the Kaufman Efficiency Ratio (KER): the band widens in a clean
#        trend AND in chop, tightening only at the transition, so it stops getting whipsawed.
#   L3 - hysteresis / commit filter: close must clear the opposing band by ~0.5 ATR (for >=1 bar) to
#        flip, which the author measured cuts false flips ~60%.
# KER (trend efficiency) and the commit-filtered direction are the genuinely new information here.
# Causal and scale-invariant. Source: research/GBBC 2026 SuperTrend ... .md.
# --------------------------------------------------------------------------- #
MST = dict(atr_period=10, mult=3.0, ker_len=20, ker_win=500, pivot=0.5,
           trend_gain=0.8, chop_gain=0.5, mult_min=1.0, mult_max=6.0, hyst_atr=0.5, hyst_bars=1)


def kaufman_efficiency_ratio(close: pd.Series, length: int) -> pd.Series:
    """KER = |net move over length| / sum of |per-bar moves|. 1 = clean trend, 0 = pure chop."""
    net = (close - close.shift(length)).abs()
    path = close.diff().abs().rolling(length).sum()
    return (net / path.replace(0.0, np.nan)).fillna(0.0)


def modern_supertrend_block(df: pd.DataFrame, cfg: dict = MST) -> dict:
    """f_mst_* : KER regime efficiency, the convex regime-scaled band multiplier (L2), and the
    hysteresis/commit-filtered Supertrend direction + distance (L3). Causal, scale-invariant."""
    out = {}
    hl2 = ((df["high"] + df["low"]) / 2.0).to_numpy(float)
    close = df["close"].to_numpy(float)
    atr = _wilder_atr(df, cfg["atr_period"]).to_numpy()
    ker_s = kaufman_efficiency_ratio(df["close"], cfg["ker_len"])
    ker_rank = ker_s.rolling(cfg["ker_win"], min_periods=cfg["ker_len"]).rank(pct=True).fillna(0.5).to_numpy()
    ker = ker_s.to_numpy()
    pivot = cfg["pivot"]                                       # L2 convex hinge on KER percentile
    f_trend = np.maximum(0.0, (ker_rank - pivot) / (1.0 - pivot))
    f_chop = np.maximum(0.0, (pivot - ker_rank) / pivot)
    mult = np.clip(cfg["mult"] * (1.0 + cfg["trend_gain"] * f_trend + cfg["chop_gain"] * f_chop),
                   cfg["mult_min"], cfg["mult_max"])
    upper_basic = hl2 + mult * atr
    lower_basic = hl2 - mult * atr
    n = len(df)
    upper, lower = upper_basic.copy(), lower_basic.copy()
    direction = np.ones(n, dtype=int)
    cand_dir = cand_count = 0
    for i in range(1, n):                                      # L0 bands + L3 hysteresis flip
        ub_prev, lb_prev = upper[i - 1], lower[i - 1]
        upper[i] = upper_basic[i] if (upper_basic[i] < ub_prev or close[i - 1] > ub_prev) else ub_prev
        lower[i] = lower_basic[i] if (lower_basic[i] > lb_prev or close[i - 1] < lb_prev) else lb_prev
        prev_dir = direction[i - 1]
        new_dir = prev_dir
        buf = cfg["hyst_atr"] * atr[i]
        if prev_dir == 1:
            if close[i] < lb_prev - buf:
                cand_count = cand_count + 1 if cand_dir == -1 else 1
                cand_dir = -1
                if cand_count >= cfg["hyst_bars"]:
                    new_dir, cand_dir, cand_count = -1, 0, 0
            else:
                cand_dir = cand_count = 0
        else:
            if close[i] > ub_prev + buf:
                cand_count = cand_count + 1 if cand_dir == 1 else 1
                cand_dir = 1
                if cand_count >= cfg["hyst_bars"]:
                    new_dir, cand_dir, cand_count = 1, 0, 0
            else:
                cand_dir = cand_count = 0
        direction[i] = new_dir
    line = np.where(direction == 1, lower, upper)
    out["f_mst_ker"] = ker                                     # trend efficiency [0,1]
    out["f_mst_ker_rank"] = ker_rank                          # regime percentile [0,1]
    out["f_mst_mult"] = (mult - cfg["mult_min"]) / (cfg["mult_max"] - cfg["mult_min"])  # band width [0,1]
    out["f_mst_dir"] = direction.astype(float)               # +1 up / -1 down (commit-filtered)
    out["f_mst_dist"] = (close - line) / close               # signed distance to the adaptive line
    flip = np.zeros(n)
    flip[1:] = (direction[1:] != direction[:-1]) * direction[1:]
    out["f_mst_flip"] = flip                                  # +1 flip up, -1 flip down
    return out


# --------------------------------------------------------------------------- #
# Label (ATR-scaled triple barrier) + realized return
# --------------------------------------------------------------------------- #
def compute_label_return(df: pd.DataFrame, cfg: dict = LABEL):
    """1 if +tgt_atr*ATR is reached before -stp_atr*ATR within horizon bars, else 0.
    Stop checked before target on a bar (conservative). trade_ret = realized gross
    return under the barrier (or close-to-close at horizon if neither is touched).
    The ATR fraction is each entry bar's own ATR%, so barriers scale with volatility.
    Last `horizon` bars are NaN."""
    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    atr_frac = (_atr_pct(df, cfg["atr_len"]) / 100.0).values
    n = len(df)
    h_bars = cfg["horizon_bars"]
    lab = np.full(n, np.nan)
    ret = np.full(n, np.nan)
    for t in range(n - h_bars):
        a = atr_frac[t]
        if not np.isfinite(a) or a <= 0:
            continue
        c = close[t]
        tgt = c * (1 + cfg["tgt_atr"] * a)
        stp = c * (1 - cfg["stp_atr"] * a)
        label, r = 0, None
        for f in range(t + 1, t + 1 + h_bars):
            if low[f] <= stp:
                label, r = 0, -cfg["stp_atr"] * a
                break
            if high[f] >= tgt:
                label, r = 1, cfg["tgt_atr"] * a
                break
        if r is None:
            r = close[t + h_bars] / c - 1.0
        lab[t] = label
        ret[t] = r
    return pd.Series(lab, index=df.index), pd.Series(ret, index=df.index)


# --------------------------------------------------------------------------- #
# Point-in-time screen (approximate spread via Corwin-Schultz)
# --------------------------------------------------------------------------- #
def corwin_schultz_spread_pct(df: pd.DataFrame, window: int) -> pd.Series:
    """Effective proportional spread estimated from consecutive high-low ranges
    (Corwin & Schultz 2012), as a PROXY for the unobserved top-of-book spread. Rolling
    median over `window` to tame noise. Returns percent. Causal (bar t uses t-1, t)."""
    hi, lo = np.log(df["high"]), np.log(df["low"])
    hl2 = (hi - lo) ** 2
    beta = hl2 + hl2.shift(1)
    h2 = np.maximum(df["high"], df["high"].shift(1))
    l2 = np.minimum(df["low"], df["low"].shift(1))
    gamma = (np.log(h2 / l2)) ** 2
    den = 3 - 2 * np.sqrt(2)
    alpha = (np.sqrt(2 * beta) - np.sqrt(beta)) / den - np.sqrt(gamma / den)
    s = 2 * (np.exp(alpha) - 1) / (1 + np.exp(alpha))
    s = s.clip(lower=0.0)
    return s.rolling(window).median() * 100.0


def screen_membership(df: pd.DataFrame, cfg: dict = SCREEN) -> pd.Series:
    """Point-in-time membership: True where this bar would have passed the (spread-
    approximated) four-gate screen. liquidity = trailing 24h quote volume; atr_band =
    1h-recalibrated ATR% band; history = enough bars lived; spread = CS proxy ceiling."""
    qv_roll = df["quote_volume"].rolling(cfg["qv_window"]).sum()
    g_liq = qv_roll >= cfg["min_quote_volume_usdt"]
    atr_pct = _atr_pct(df, cfg["atr_len"])
    g_atr = (atr_pct >= cfg["atr_floor_pct"]) & (atr_pct <= cfg["atr_ceiling_pct"])
    g_hist = pd.Series(np.arange(len(df)) >= cfg["min_history_bars"], index=df.index)
    g_spread = corwin_schultz_spread_pct(df, cfg["spread_window"]) <= cfg["spread_proxy_ceiling_pct"]
    return (g_liq & g_atr & g_hist & g_spread).fillna(False)


# --------------------------------------------------------------------------- #
# Data quality (exchange-grade, low-gap; hard rule)
# --------------------------------------------------------------------------- #
def gap_stats(df: pd.DataFrame) -> dict:
    """Interval-bar completeness over the coin's own span. Our features assume regularly
    spaced bars, so holes (halts, delistings, missing archive months) must be small. Bar
    width is INTERVAL_HOURS; max_gap stays in wall-clock hours (the gate is wall-clock)."""
    dt = pd.to_datetime(df["datetime"]).sort_values().reset_index(drop=True)
    span_bars = int((dt.iloc[-1] - dt.iloc[0]).total_seconds() // (INTERVAL_HOURS * 3600)) + 1
    actual = len(dt)
    missing = max(span_bars - actual, 0)
    diffs_h = dt.diff().dropna().dt.total_seconds() / 3600.0
    max_gap = float(diffs_h.max()) if len(diffs_h) else 1.0
    return dict(span_bars=span_bars, actual=actual, missing=missing,
                gap_ratio=(missing / span_bars if span_bars else 1.0),
                max_gap_hours=max_gap)


def passes_quality(q: dict, cfg: dict = DATA_QUALITY) -> bool:
    return (q["gap_ratio"] <= cfg["max_gap_ratio"]
            and q["max_gap_hours"] <= cfg["max_single_gap_hours"])


# --------------------------------------------------------------------------- #
# Assemble one coin and the whole set
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# Regime-state block (handoff Part 2). Rather than a regime switchboard, give ONE model the observable
# regime as input features so it can condition its behaviour on it ("when vol looks like this and trend
# like that, the right behaviour is this"). All causal (past data only, computable live today) and
# scale-invariant: a trailing realized-vol level and its OWN-history percentile (the volatility regime),
# trend drift over a short and a long window, a Kaufman trend-efficiency (trend-to-noise), an up/down
# bar-breadth ratio, the trailing total return, and the BTC MARKET regime (its trend state). The
# diagnostics found the edge is strongest when BTC trends up, so the market regime is first-class here.
# --------------------------------------------------------------------------- #
RG_SHORT, RG_LONG, RG_VOLWIN = 14, 60, 250            # frame-native bar windows (like the HR family)


def regime_block(df: pd.DataFrame, btc=None) -> dict:
    """f_rg_* : volatility regime + trend state + BTC market regime. Causal and scale-invariant."""
    close = df["close"]
    lr = np.log(close).diff()
    rv_s = lr.rolling(RG_SHORT).std()
    net = (np.log(close) - np.log(close).shift(RG_LONG)).abs()         # |net log move| over the long window
    path = lr.abs().rolling(RG_LONG).sum()                            # total log path travelled
    out = {
        "f_rg_rv_short": rv_s,                                         # trailing realized vol (short)
        "f_rg_rv_long": lr.rolling(RG_LONG).std(),                     # trailing realized vol (long)
        "f_rg_vol_regime": rv_s.rolling(RG_VOLWIN).rank(pct=True),     # current vol's percentile in its own history
        "f_rg_drift_short": lr.rolling(RG_SHORT).mean(),              # per-bar trend drift (short)
        "f_rg_drift_long": lr.rolling(RG_LONG).mean(),                # per-bar trend drift (long)
        "f_rg_efficiency": net / (path + EPS),                        # Kaufman trend-to-noise (0..1)
        "f_rg_updown": np.sign(lr).rolling(RG_LONG).mean(),          # net up/down bar breadth (-1..1)
        "f_rg_ret_long": close / close.shift(RG_LONG) - 1.0,         # trailing total return (sign + magnitude)
    }
    if btc is not None:
        idx = pd.to_datetime(df["datetime"]).astype("datetime64[ns]").to_numpy()
        bc = btc.reindex(idx)
        if not bc.isna().all():
            bc = pd.Series(bc.to_numpy(float), index=df.index)
            out["f_rg_btc_ret_long"] = bc / bc.shift(RG_LONG) - 1.0                       # BTC market trend
            out["f_rg_btc_regime"] = (bc > bc.ewm(span=RG_LONG, adjust=True).mean()).astype(float)  # BTC above its trend
    return out


# Microstructure features for the 1d frame, computed from the coin's 1h archive
# (tasks/microstructure-daily-features.md): what a daily bar alone cannot see.
# OPT-IN via --microstructure / MS_BLOCK=1 so the baseline 1d build stays
# untouched until its edge matrix is read; the in-house baseline never depends
# on it. Coins without a 1h archive contribute no f_ms_ columns (same pattern
# as the flow block: the cross-coin concat unions them to NaN).
MS_ENABLED = os.environ.get("MS_BLOCK", "0") == "1"
MS_MIN_HOURS = 18       # a day represented by fewer hourly bars is not summarised
MS_GAP_SIGMA = 3.0      # an hour beyond 3 trailing sigmas is a jump
MS_SIGMA_WIN = 168      # trailing week of hourly returns defines sigma


def microstructure_block(df: pd.DataFrame, hourly: pd.DataFrame | None) -> dict:
    """f_ms_* : daily aggregates of hourly behaviour. Causal (a day's row uses only
    that day's hours, known at the daily close) and scale-invariant throughout."""
    if hourly is None or hourly.empty:
        return {}
    h = hourly.copy()
    h["date"] = pd.to_datetime(h["datetime"]).dt.floor("D")
    h["r"] = np.log(h["close"]).diff()
    h["r2"] = h["r"] ** 2
    sigma = h["r"].rolling(MS_SIGMA_WIN, min_periods=72).std().shift(1)
    exceed = (h["r"].abs() > MS_GAP_SIGMA * sigma).astype(float)
    h["gap_n"] = exceed
    h["gap_signed"] = np.sign(h["r"]).fillna(0.0) * exceed
    h["v2"] = h["volume"] ** 2
    h["upvol"] = h["volume"].where(h["close"] > h["open"], 0.0)

    g = h.groupby("date").agg(
        n=("r", "size"), hi=("high", "max"), lo=("low", "min"), c=("close", "last"),
        v=("volume", "sum"), v2=("v2", "sum"), upv=("upvol", "sum"),
        tb=("taker_buy_base", "sum"), r2=("r2", "sum"),
        gap_n=("gap_n", "sum"), gap_signed=("gap_signed", "sum"))

    v = g["v"].replace(0, np.nan)
    rng = (g["hi"] - g["lo"]).replace(0, np.nan)
    park = (np.log(g["hi"] / g["lo"].replace(0, np.nan)) ** 2) / (4 * np.log(2))
    ms = pd.DataFrame({
        "f_ms_flow_imb": g["tb"] / v - 0.5,                     # taker-buy share, centred
        "f_ms_vol_updown": 2 * g["upv"] / v - 1.0,              # up-hour vs down-hour volume
        "f_ms_hhi": (g["v2"] / v**2 - 1 / g["n"]) / (1 - 1 / g["n"]),  # volume concentration, 0=even
        "f_ms_close_pos": (g["c"] - g["lo"]) / rng,             # close's position in the day's range
        "f_ms_rv_range": np.log((g["r2"] + EPS) / (park + EPS)),  # realized vs Parkinson range vol
        "f_ms_gap_n": g["gap_n"],                               # count of >3-sigma hourly jumps
        "f_ms_gap_signed": g["gap_signed"],                     # their signed sum
    }).where(g["n"] >= MS_MIN_HOURS)
    ms["f_ms_flow_imb_7d"] = ms["f_ms_flow_imb"].rolling(7, min_periods=3).mean()

    key = pd.to_datetime(df["datetime"]).dt.floor("D")
    aligned = ms.reindex(pd.DatetimeIndex(key))
    return {c: pd.Series(aligned[c].to_numpy(), index=df.index) for c in ms.columns}


def build_coin(df: pd.DataFrame, symbol_slash: str, flow: pd.DataFrame, btc=None,
               hourly: pd.DataFrame | None = None) -> pd.DataFrame:
    feats = {}
    feats.update(indicator_block(df, "wc", WC, emit_rv_short=False))  # drop dup of f_hr_rv_long
    feats.update(indicator_block(df, "hr", HR))
    feats.update(extra_ta_block(df))
    feats.update(supertrend_block(df))
    feats.update(pandas_ta_block(df))
    feats.update(talib_block(df))
    feats.update(flow_block(df, flow, symbol_slash))
    feats.update(btc_block(df, btc))
    feats.update(multitf_block(df))
    feats.update(modern_supertrend_block(df))
    feats.update(regime_block(df, btc))            # f_rg_ : volatility + trend regime state (handoff Part 2)
    if MS_ENABLED and INTERVAL == "1d":
        feats.update(microstructure_block(df, hourly))  # f_ms_ : hourly eyes for the daily bar (opt-in)
    out = pd.DataFrame(feats, index=df.index)
    out.insert(0, "datetime", df["datetime"].values)
    out.insert(0, "symbol", symbol_slash)
    lab, tret = compute_label_return(df)
    out["in_sample"] = screen_membership(df).values
    out["label"] = lab.values
    out["trade_ret"] = tret.values
    return out


def feature_columns(df: pd.DataFrame) -> list:
    return [c for c in df.columns if c.startswith("f_")]


def list_symbols(klines_root: str) -> list:
    if not os.path.isdir(klines_root):
        return []
    return sorted(d for d in os.listdir(klines_root)
                  if os.path.isdir(os.path.join(klines_root, d)))


# --------------------------------------------------------------------------- #
# Interval switch. The 1h frame is the default and stays byte-identical; configure(4) /
# configure(24) retune the interval-sensitive knobs so every wall-clock window, the label
# horizon, the screen and the higher-tf context scale to the new bar size. Conventional
# bar-count periods (the 12/26/50 EMA + 14 RSI intraday HR family, ATR/Supertrend bands,
# the extra-TA and candlestick blocks) are deliberately held CONSTANT: they are frame-native
# oscillator periods, not wall-clock lookbacks, so the same period at a coarser bar simply
# spans more real time -- exactly the "shorter family relative to this frame" intent.
# --------------------------------------------------------------------------- #
_WC_DAYS = dict(ema_fast=14, ema_mid=91, ema_slow=125, rsi=14, bb=14, atr=14,
                rv_short=7, rv_long=30, vol=20, mom=[5, 10, 20, 60])   # wall-clock family, in DAYS
_LABEL_HORIZON_DAYS = 2                                                # hour+ frames: +2/-1 ATR 2-day horizon
# Supported decision frames, keyed by interval label; everything else derives from minutes-per-bar.
# 5m and 15m are the sub-hour SCALP frames (added 2026-06-24); 1h/4h/1d are the original swing/day-trade
# frames and stay byte-identical to before.
_FRAME_MIN = {"5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}     # minutes per bar
_MIN_FRAME = {v: k for k, v in _FRAME_MIN.items()}
_INTERVAL_LABEL = {1: "1h", 4: "4h", 24: "1d"}                         # back-compat: int hours -> label
# ATR band per frame = daily 2.5-12% scaled by 1/sqrt(bars-per-day). The hour+ rows are the original
# literals (unchanged); 5m/15m are that same formula precomputed (sqrt(288)=17.0, sqrt(96)=9.8).
_SCREEN_ATR_BAND = {"5m": (0.15, 0.71), "15m": (0.26, 1.22),
                    "1h": (0.5, 2.5), "4h": (1.0, 4.9), "1d": (2.5, 12.0)}
# Higher-timeframe context per frame; the sub-hour frames look up to 1h + 4h.
_MTF_RULES = {"5m": (("1h", "f_h1"), ("4h", "f_4h")),                  # 5m sees 1h + 4h
              "15m": (("1h", "f_h1"), ("4h", "f_4h")),                 # 15m sees 1h + 4h
              "1h": (("4h", "f_4h"), ("1D", "f_d1")),                  # 1h sees 4h + daily
              "4h": (("1D", "f_d1"), ("1W", "f_w1")),                  # 4h sees daily + weekly
              "1d": (("1W", "f_w1"), ("1ME", "f_mo"))}                 # daily sees weekly + monthly
# Sub-hour SCALP label: a short, ATR-scaled triple barrier (fewer bars, tighter target) in place of the
# day-scaled 2-day horizon. 5m: 24 bars (~2h); 15m: 16 bars (~4h). Starting values, swept later like the
# hour+ label.
_SUBHOUR_LABEL = {"5m": dict(tgt_atr=1.5, stp_atr=1.0, horizon_bars=24, atr_len=14),
                  "15m": dict(tgt_atr=1.5, stp_atr=1.0, horizon_bars=16, atr_len=14)}


def configure(frame) -> None:
    """Retune every interval-sensitive global for the given decision frame, IN PLACE so the configs
    bound as function defaults (LABEL, SCREEN) update too. `frame` is an interval LABEL ('5m', '15m',
    '1h', '4h', '1d') or, for back-compat, a number of HOURS (1, 4, 24, or the float INTERVAL_HOURS).
    configure(1) and configure('1h') are identical and reproduce the shipped 1h frame exactly (the
    hour+ frames are byte-identical to before; 5m/15m are the sub-hour scalp frames). Call once before
    build()."""
    global INTERVAL_HOURS, INTERVAL, BARS_PER_DAY, MTF_RULES
    global DEFAULT_KLINES_ROOT, DEFAULT_FLOW, DEFAULT_FLOW_CSV, DATASET_FILE, DATASET_PATH
    if isinstance(frame, str) and frame.strip().lower() in _FRAME_MIN:
        label = frame.strip().lower()                      # '5m', '1h', ...
    else:                                                  # numeric hours (int/float) or numeric string
        try:
            label = _MIN_FRAME[round(float(frame) * 60)]
        except (ValueError, TypeError, KeyError):
            raise ValueError(f"unsupported frame={frame!r}; pick a label in {sorted(_FRAME_MIN)} "
                             f"or hours in {sorted(_INTERVAL_LABEL)}")
    minutes = _FRAME_MIN[label]
    INTERVAL = label
    INTERVAL_HOURS = minutes // 60 if minutes % 60 == 0 else minutes / 60.0   # int for hour+ frames
    BARS_PER_DAY = round(1440 / minutes)                   # 5m->288, 15m->96, 1h->24, 4h->6, 1d->1
    # wall-clock family: day-defined windows -> bars (HR untouched: native oscillator periods)
    for k, d in _WC_DAYS.items():
        WC[k] = [v * BARS_PER_DAY for v in d] if isinstance(d, list) else d * BARS_PER_DAY
    # label: sub-hour frames take the short scalp barrier; hour+ frames keep the day-scaled 2-day horizon
    if label in _SUBHOUR_LABEL:
        LABEL.update(_SUBHOUR_LABEL[label])
    else:
        LABEL["horizon_bars"] = _LABEL_HORIZON_DAYS * BARS_PER_DAY
    # screen windows are wall-clock; the ATR band is the daily band / sqrt(bars-per-day)
    floor, ceiling = _SCREEN_ATR_BAND[label]
    SCREEN["qv_window"] = BARS_PER_DAY
    SCREEN["spread_window"] = BARS_PER_DAY
    SCREEN["min_history_bars"] = 120 * BARS_PER_DAY
    SCREEN["atr_floor_pct"] = floor
    SCREEN["atr_ceiling_pct"] = ceiling
    MTF_RULES = _MTF_RULES[label]
    # storage: each frame gets its own klines folder, flow table and dataset file
    sub = "klines" if INTERVAL == "1d" else f"klines_{INTERVAL}"
    DEFAULT_KLINES_ROOT = os.path.join(BINANCE_DATA, sub)
    DEFAULT_FLOW = os.path.join(BINANCE_DATA, f"flow_{INTERVAL}.parquet")
    DEFAULT_FLOW_CSV = DEFAULT_FLOW
    DATASET_FILE = f"dataset_{INTERVAL}_allmarket.parquet"
    DATASET_PATH = os.path.join(BINANCE_DATA, DATASET_FILE)


def build(klines_root: str | None = None, flow_csv: str | None = None,
          symbols: list | None = None) -> pd.DataFrame:
    klines_root = klines_root or DEFAULT_KLINES_ROOT       # resolve against the configured interval
    flow_csv = flow_csv if flow_csv is not None else DEFAULT_FLOW
    flow = read_frame(flow_csv) if flow_csv else None      # Parquet-preferred (dtypes preserved)
    btc = load_btc_series(klines_root)                     # market beta, loaded once for f_btc_*
    symbols = symbols or list_symbols(klines_root)
    # 1d + --microstructure: each coin's 1h archive feeds the f_ms_ block.
    hourly_root = (os.path.join(BINANCE_DATA, "klines_1h")
                   if MS_ENABLED and INTERVAL == "1d" else None)
    frames = []
    for sym in symbols:
        d = load_coin(klines_root, sym)
        hourly = load_coin(hourly_root, sym) if hourly_root else None
        slash = f"{sym[:-4]}/USDT" if sym.endswith("USDT") else sym
        min_needed = max(max(WC["mom"]), WC["rv_long"], WC["bb"]) + LABEL["horizon_bars"]
        if len(d) < min_needed:
            print(f"  skip {sym}: only {len(d)} bars (<{min_needed})")
            continue
        q = gap_stats(d)
        if not passes_quality(q):
            print(f"  skip {sym}: data quality (gap_ratio {q['gap_ratio']:.3f}, "
                  f"max gap {q['max_gap_hours']:.0f}h)")
            continue
        coin = build_coin(d, slash, flow, btc, hourly)
        feat_cols = feature_columns(coin)
        before = len(coin)
        coin = coin.dropna(subset=[*feat_cols, "label", "trade_ret"])
        in_n = int(coin["in_sample"].sum())
        print(f"  {sym}: {len(coin):6d} rows kept ({in_n} in-sample), "
              f"dropped {before - len(coin)} warmup/unresolved")
        frames.append(coin)
    if not frames:
        raise SystemExit("no coins built; check klines_root")
    data = pd.concat(frames, ignore_index=True)
    data["label"] = data["label"].astype(int)
    data["in_sample"] = data["in_sample"].astype(bool)
    return data


def main():
    p = argparse.ArgumentParser(description="Build an all-market training dataset for a decision frame")
    p.add_argument("--interval", default="1h",
                   help="decision frame: 5m, 15m, 1h (default), 4h, 1d (or hours: 1, 4, 24)")
    p.add_argument("--klines-root", default=None, help="defaults to the configured interval's folder")
    p.add_argument("--flow", default=None, help="defaults to flow_<interval>.parquet")
    p.add_argument("--out", default=None, help="defaults to dataset_<interval>_allmarket.parquet")
    p.add_argument("-s", "--symbols", nargs="+", default=None)
    p.add_argument("--csv", action="store_true",
                   help="also write a .csv beside the .parquet (for human spot-checks)")
    p.add_argument("--microstructure", action="store_true",
                   help="1d frame only: add the f_ms_ block from each coin's 1h archive; "
                        "write to a separate --out so the baseline dataset is preserved")
    args = p.parse_args()

    if args.microstructure:
        global MS_ENABLED
        MS_ENABLED = True
    configure(args.interval)                              # retune the interval-sensitive globals
    out = args.out or DATASET_PATH
    print(f"building {INTERVAL} frame  .  klines={args.klines_root or DEFAULT_KLINES_ROOT}  "
          f"flow={args.flow or DEFAULT_FLOW}  ->  {out}")
    data = build(args.klines_root, args.flow, args.symbols)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    out_path = write_frame(data, out, also_csv=args.csv)
    feat_cols = feature_columns(data)
    base_all = data["label"].mean()
    insamp = data[data["in_sample"]]
    base_in = insamp["label"].mean() if len(insamp) else float("nan")
    print(f"\nwrote {out_path}")
    print(f"rows={len(data)}  in_sample={len(insamp)}  coins={data['symbol'].nunique()}  "
          f"features={len(feat_cols)}")
    print(f"date range {data['datetime'].min()} -> {data['datetime'].max()}")
    print(f"base rate all={base_all:.3f}  base rate in_sample={base_in:.3f}")


if __name__ == "__main__":
    main()
