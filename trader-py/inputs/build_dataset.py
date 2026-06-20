"""Build the labeled, scale-invariant training dataset (Task A).

Generalizes backtest.py from "breakout events" to "one row per coin per day".
For each of the 10 universe coins we pull full daily history, compute a set of
features that are all *scale-invariant* (ratios, slopes, distances, flags) so a
single model works across BTC at $60k and DOGE at $0.20, and we attach the
agreed success label: 1 if within HORIZON trading days the close gains +TARGET
before falling -STOP below that day's close, else 0.

Every feature uses ONLY data up to and including its own bar. There is no
forward leakage in the features. The label, by construction, looks forward —
which is exactly why the last HORIZON rows of each coin are dropped (they cannot
be resolved yet) and why train_model.py embargoes the split.

Output: python/outputs/dataset.csv  (symbol, date, <features...>, label)

This module is also imported by trade_binance.py, which reuses fetch_history()
and compute_features() so the live model sees exactly the features it trained on.
"""
from __future__ import annotations

import os
import time
import warnings

import ccxt
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ---- universe: the coins we train AND trade (USDT spot) ----
COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "AVAX", "LINK", "LTC", "DOGE"]
SYMBOLS = [f"{c}/USDT" for c in COINS]

# ---- label rule (the success definition already greenlit) ----
TARGET = 0.10   # +10% gain from this day's close
STOP = 0.05     # -5% below this day's close
HORIZON = 20    # trading (here: calendar, crypto is 24/7) days to resolve

# ---- indicator windows ----
EMA_FAST, EMA_MID, EMA_SLOW = 14, 91, 125
RSI_LEN = 14
CHOP_LEN = 14
BB_LEN = 14
BB_STD = 2.0
VOL_LEN = 20
PIVOT_K = 5     # swing high = local max over +/- this many bars

# The feature columns the model is trained on. trade_binance.py imports this so
# the live feature vector and the training feature vector can never drift apart.
FEATURES = [
    "f_close_kalman",       # (close - kalman) / kalman
    "f_ema_fast_mid",       # (ema14 - ema91) / close
    "f_ema_mid_slow",       # (ema91 - ema125) / close
    "f_rsi",                # RSI / 100
    "f_chop",               # Choppiness / 100
    "f_macd_hist",          # MACD histogram / close
    "f_macd_below_zero",    # 1 if MACD line < 0
    "f_bb_pos",             # (close - bbl) / (bbu - bbl)
    "f_vol_ratio",          # volume / 20-day avg volume
    "f_dist_resistance",    # (nearest resistance - close) / close
    "f_ema_cross",          # 1 if ema14 > ema91 (state)
    "f_golden_cross",       # 1 if ema14 crossed above ema91 this bar (event)
    "f_death_cross",        # 1 if ema14 crossed below ema91 this bar (event)
    "f_doji",               # 1 if doji candle
    "f_dragonfly",          # 1 if dragonfly doji
    "f_gravestone",         # 1 if gravestone doji
    "f_breakout",           # 1 if close broke above nearest resistance this bar
    # --- Keller feature families (added 2026-06-20): daily, causal, scale-invariant ---
    "f_mom_5", "f_mom_10", "f_mom_20", "f_mom_60", "f_mom_120",  # multi-lookback momentum
    "f_mom_accel_10", "f_mom_accel_20",                          # momentum of momentum
    "f_rv_7", "f_rv_30", "f_rv_ratio",                          # realized vol + regime ratio
    "f_parkinson_14", "f_garman_klass_14",                      # range-based volatility
    "f_riskadj_ret", "f_sortino_ret",                          # volatility-adjusted returns
    "f_illiq",                                                  # Amihud-style relative illiquidity
]


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
def fetch_history(symbol: str, exchange: ccxt.Exchange | None = None,
                  timeframe: str = "1d", page: int = 1000) -> pd.DataFrame:
    """Full daily OHLCV history for `symbol`, paginated past the 1000-bar cap.

    ccxt returns at most `page` bars per call, so we walk forward from the
    earliest available bar using `since`, stitching pages until the exchange
    stops returning new data. The final (still-forming) bar is dropped so every
    row is a closed candle.
    """
    ex = exchange or ccxt.binance({"enableRateLimit": True})
    since = ex.parse8601("2017-01-01T00:00:00Z")
    ms_per_bar = ex.parse_timeframe(timeframe) * 1000
    all_bars: list[list] = []
    while True:
        bars = ex.fetch_ohlcv(symbol, timeframe, since=since, limit=page)
        if not bars:
            break
        # Drop overlap with what we already have.
        if all_bars and bars[0][0] <= all_bars[-1][0]:
            bars = [b for b in bars if b[0] > all_bars[-1][0]]
        if not bars:
            break
        all_bars += bars
        since = bars[-1][0] + ms_per_bar
        if len(bars) < page:
            break
        time.sleep((ex.rateLimit or 50) / 1000.0)
    if not all_bars:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    df = pd.DataFrame(all_bars[:-1], columns=["t", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["t"], unit="ms")
    return df.drop(columns="t").reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Indicators (all causal)
# --------------------------------------------------------------------------- #
def _kalman(close: np.ndarray, q: float = 0.01, r: float = 1.0) -> np.ndarray:
    """Scalar random-walk Kalman filter (forward pass only, so it is causal).

    Mirrors the notebook's KalmanFilter(transition=1, observation=1,
    observation_covariance=1, transition_covariance=.01) but is initialised at
    the first close (not 0) to avoid a long warmup ramp. The forward filter at
    bar t uses only observations up to t, so there is no lookahead.
    """
    n = len(close)
    out = np.empty(n)
    x = close[0]
    p = 1.0
    for i in range(n):
        # predict
        p_pred = p + q
        # update
        k = p_pred / (p_pred + r)
        x = x + k * (close[i] - x)
        p = (1 - k) * p_pred
        out[i] = x
    return out


def _rsi(close: pd.Series, length: int = RSI_LEN) -> pd.Series:
    """Wilder's RSI (causal exponential smoothing of gains/losses)."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return 100 - 100 / (1 + rs)


def _choppiness(df: pd.DataFrame, length: int = CHOP_LEN) -> pd.Series:
    """Choppiness Index over a rolling window (causal)."""
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr_sum = tr.rolling(length).sum()
    rng = df["high"].rolling(length).max() - df["low"].rolling(length).min()
    return 100 * np.log10(atr_sum / rng.replace(0.0, np.nan)) / np.log10(length)


def _swing_resistance(df: pd.DataFrame, k: int = PIVOT_K) -> pd.Series:
    """Most recent *confirmed* swing-high level as of each bar (causal).

    A bar i is a swing high if its high is the max over [i-k, i+k]; that fact is
    only known k bars later, so the level becomes usable from bar i+k onward.
    Returns the running latest confirmed swing-high level per bar (NaN until the
    first one is confirmed).
    """
    high = df["high"].values
    n = len(high)
    level = np.full(n, np.nan)
    current = np.nan
    confirmed: dict[int, float] = {}
    for i in range(k, n - k):
        if high[i] == max(high[i - k:i + k + 1]):
            confirmed[i + k] = high[i]   # usable from bar i+k
    for t in range(n):
        if t in confirmed:
            current = confirmed[t]
        level[t] = current
    return pd.Series(level, index=df.index)


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Attach all model features to a daily OHLCV frame. Causal throughout.

    Input must have columns: date, open, high, low, close, volume (ascending date).
    Returns the same frame with the FEATURES columns added.
    """
    df = df.copy().reset_index(drop=True)
    close = df["close"]

    kalman = _kalman(close.values)
    ema_f = close.ewm(span=EMA_FAST, adjust=False).mean()
    ema_m = close.ewm(span=EMA_MID, adjust=False).mean()
    ema_s = close.ewm(span=EMA_SLOW, adjust=False).mean()

    # MACD 12/26/9
    macd_line = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    signal = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = macd_line - signal

    # Bollinger (length 14, 2 std)
    bb_mid = close.rolling(BB_LEN).mean()
    bb_sd = close.rolling(BB_LEN).std(ddof=0)
    bbu = bb_mid + BB_STD * bb_sd
    bbl = bb_mid - BB_STD * bb_sd

    vol_avg = df["volume"].rolling(VOL_LEN).mean()
    resistance = _swing_resistance(df)

    # EMA cross state + events
    ema_cross = ema_f > ema_m
    prev_cross = ema_cross.shift(1)
    golden = ema_cross & (~prev_cross.fillna(ema_cross))
    death = (~ema_cross) & prev_cross.fillna(~ema_cross)

    # Candle shapes (single bar)
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    rng = h - l
    body = (c - o).abs()
    upper = h - np.maximum(o, c)
    lower = np.minimum(o, c) - l
    doji = (rng > 0) & (body <= 0.10 * rng)
    dragonfly = doji & (lower >= 0.6 * rng) & (upper <= 0.10 * rng)
    gravestone = doji & (upper >= 0.6 * rng) & (lower <= 0.10 * rng)

    # Breakout: close crossed above the nearest confirmed resistance this bar
    breakout = (close > resistance) & (close.shift(1) <= resistance)

    df["f_close_kalman"] = (close - kalman) / kalman
    df["f_ema_fast_mid"] = (ema_f - ema_m) / close
    df["f_ema_mid_slow"] = (ema_m - ema_s) / close
    df["f_rsi"] = _rsi(close) / 100.0
    df["f_chop"] = _choppiness(df) / 100.0
    df["f_macd_hist"] = macd_hist / close
    df["f_macd_below_zero"] = (macd_line < 0).astype(int)
    df["f_bb_pos"] = (close - bbl) / (bbu - bbl)
    df["f_vol_ratio"] = df["volume"] / vol_avg
    df["f_dist_resistance"] = (resistance - close) / close
    df["f_ema_cross"] = ema_cross.astype(int)
    df["f_golden_cross"] = golden.astype(int)
    df["f_death_cross"] = death.astype(int)
    df["f_doji"] = doji.astype(int)
    df["f_dragonfly"] = dragonfly.astype(int)
    df["f_gravestone"] = gravestone.astype(int)
    df["f_breakout"] = breakout.astype(int)

    # --- Keller feature families (daily, causal, scale-invariant) -------------
    # Adapted from Keller 2025; lookbacks in days (this is a daily swing model),
    # every column a ratio or log-ratio so one model spans BTC at $60k and DOGE
    # at $0.20. All use only past bars. See tasks/keller-integration.md.
    eps = 1e-8
    ret = close.pct_change()
    # Multi-lookback momentum and its acceleration (momentum of momentum).
    for k in (5, 10, 20, 60, 120):
        df[f"f_mom_{k}"] = close / close.shift(k) - 1.0
    df["f_mom_accel_10"] = df["f_mom_10"].diff()
    df["f_mom_accel_20"] = df["f_mom_20"].diff()
    # Realized volatility (close-to-close) plus a short/long regime ratio.
    df["f_rv_7"] = ret.rolling(7).std()
    df["f_rv_30"] = ret.rolling(30).std()
    df["f_rv_ratio"] = df["f_rv_7"] / (df["f_rv_30"] + eps)
    # Range-based volatility estimators (more efficient than close-to-close).
    log_hl = np.log(h / l)
    log_co = np.log(c / o)
    df["f_parkinson_14"] = np.sqrt(
        (1.0 / (4.0 * np.log(2.0))) * (log_hl ** 2).rolling(14).mean())
    gk = (0.5 * (log_hl ** 2).rolling(14).mean()
          - (2.0 * np.log(2.0) - 1.0) * (log_co ** 2).rolling(14).mean())
    df["f_garman_klass_14"] = np.sqrt(gk.clip(lower=0.0))
    # Volatility-adjusted returns: recent drift per unit of risk (Sharpe- and
    # Sortino-like, the latter using downside deviation).
    vol20 = ret.rolling(20).std()
    df["f_riskadj_ret"] = ret.rolling(5).mean() / (vol20 + eps)
    downside_dev = np.sqrt((ret.clip(upper=0.0) ** 2).rolling(20).mean())
    df["f_sortino_ret"] = ret.rolling(5).mean() / (downside_dev + eps)
    # Amihud-style illiquidity, made scale-invariant: absolute return per unit of
    # the coin's own relative volume (not raw dollar volume, which is not
    # comparable across coins).
    rel_vol = df["volume"] / (df["volume"].rolling(20).mean() + eps)
    df["f_illiq"] = (ret.abs() / (rel_vol + eps)).rolling(14).mean()
    return df


# --------------------------------------------------------------------------- #
# Label
# --------------------------------------------------------------------------- #
def compute_label(df: pd.DataFrame, target: float = TARGET, stop: float = STOP,
                  horizon: int = HORIZON) -> pd.Series:
    """Forward label: 1 if close gains +target before falling -stop, within
    horizon bars; else 0. The stop is checked before the target on any single
    bar (the conservative convention used by backtest.py), so labels never lean
    optimistic. The last `horizon` rows are returned as NaN (unresolvable)."""
    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    n = len(df)
    out = np.full(n, np.nan)
    for t in range(n - horizon):
        c = close[t]
        tgt = c * (1 + target)
        stp = c * (1 - stop)
        label = 0
        for f in range(t + 1, t + 1 + horizon):
            if low[f] <= stp:
                label = 0
                break
            if high[f] >= tgt:
                label = 1
                break
        out[t] = label
    return pd.Series(out, index=df.index)


def build() -> pd.DataFrame:
    ex = ccxt.binance({"enableRateLimit": True})
    frames = []
    for sym in SYMBOLS:
        try:
            raw = fetch_history(sym, ex)
        except Exception as e:  # noqa: BLE001
            print(f"  skip {sym}: {type(e).__name__} {str(e)[:80]}")
            continue
        if len(raw) < EMA_SLOW + CHOP_LEN + HORIZON:
            print(f"  skip {sym}: only {len(raw)} bars")
            continue
        feat = compute_features(raw)
        feat["label"] = compute_label(feat)
        feat.insert(0, "symbol", sym)
        cols = ["symbol", "date", *FEATURES, "label"]
        feat = feat[cols]
        before = len(feat)
        feat = feat.dropna(subset=[*FEATURES, "label"])
        print(f"  {sym}: {len(feat):5d} labeled rows "
              f"({raw['date'].min().date()} -> {raw['date'].max().date()}, "
              f"dropped {before - len(feat)} warmup/unresolved)")
        frames.append(feat)
    data = pd.concat(frames, ignore_index=True)
    data["label"] = data["label"].astype(int)
    return data


if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(__file__), "..", "outputs")
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    data = build()
    path = os.path.join(out_dir, "dataset.csv")
    data.to_csv(path, index=False)
    base = data["label"].mean()
    print(f"\nwrote {path}")
    print(f"rows={len(data)}  coins={data['symbol'].nunique()}  "
          f"date range {data['date'].min().date()} -> {data['date'].max().date()}")
    print(f"base rate (label=1) = {base:.3f}")
