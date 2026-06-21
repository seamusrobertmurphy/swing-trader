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
DEFAULT_FLOW_CSV = os.path.join(BINANCE_DATA, "flow_1h.csv")
DATASET_FILE = "dataset_1h_allmarket.csv"
DATASET_PATH = os.path.join(BINANCE_DATA, DATASET_FILE)

BARS_PER_DAY = 24

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


def indicator_block(df: pd.DataFrame, prefix: str, w: dict) -> dict:
    """One window family of scale-invariant, causal features under f_<prefix>_*."""
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
    sub = flow[flow["symbol"] == symbol_slash][["datetime", "flow_imbalance", "taker_buy_ratio"]]
    if sub.empty:
        return out
    merged = df[["datetime"]].merge(sub, on="datetime", how="left")
    fi = merged["flow_imbalance"]
    out["f_flow_imb"] = fi.values
    out["f_flow_imb_24"] = fi.rolling(24).mean().values
    out["f_flow_imb_168"] = fi.rolling(168).mean().values
    out["f_flow_taker_ratio"] = merged["taker_buy_ratio"].values
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
    """Hourly-bar completeness over the coin's own span. Our features assume regularly
    spaced 1h bars, so holes (halts, delistings, missing archive months) must be small."""
    dt = pd.to_datetime(df["datetime"]).sort_values().reset_index(drop=True)
    span_bars = int((dt.iloc[-1] - dt.iloc[0]).total_seconds() // 3600) + 1
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
def build_coin(df: pd.DataFrame, symbol_slash: str, flow: pd.DataFrame) -> pd.DataFrame:
    feats = {}
    feats.update(indicator_block(df, "wc", WC))
    feats.update(indicator_block(df, "hr", HR))
    feats.update(extra_ta_block(df))
    feats.update(pandas_ta_block(df))
    feats.update(talib_block(df))
    feats.update(flow_block(df, flow, symbol_slash))
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


def build(klines_root: str = DEFAULT_KLINES_ROOT, flow_csv: str = DEFAULT_FLOW_CSV,
          symbols: list | None = None) -> pd.DataFrame:
    flow = None
    if flow_csv and os.path.exists(flow_csv):
        flow = pd.read_csv(flow_csv, parse_dates=["datetime"])
    symbols = symbols or list_symbols(klines_root)
    frames = []
    for sym in symbols:
        d = load_coin(klines_root, sym)
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
        coin = build_coin(d, slash, flow)
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
    p = argparse.ArgumentParser(description="Build the 1h all-market training dataset")
    p.add_argument("--klines-root", default=DEFAULT_KLINES_ROOT)
    p.add_argument("--flow", default=DEFAULT_FLOW_CSV)
    p.add_argument("--out", default=DATASET_PATH)
    p.add_argument("-s", "--symbols", nargs="+", default=None)
    args = p.parse_args()

    data = build(args.klines_root, args.flow, args.symbols)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    data.to_csv(args.out, index=False)
    feat_cols = feature_columns(data)
    base_all = data["label"].mean()
    insamp = data[data["in_sample"]]
    base_in = insamp["label"].mean() if len(insamp) else float("nan")
    print(f"\nwrote {args.out}")
    print(f"rows={len(data)}  in_sample={len(insamp)}  coins={data['symbol'].nunique()}  "
          f"features={len(feat_cols)}")
    print(f"date range {data['datetime'].min()} -> {data['datetime'].max()}")
    print(f"base rate all={base_all:.3f}  base rate in_sample={base_in:.3f}")


if __name__ == "__main__":
    main()
