"""Tunable MACD with guarded crossover signals and divergence detection.

Moving Average Convergence Divergence (Appel, 1970s). This module rebuilds the
metric the project already uses in inputs/build_dataset.py (close.ewm with
adjust=False, 12/26/9) and extends it three ways the operator asked for:

  1. Tunable windows          - fast / slow / signal are configurable.
  2. Guarded crossover signal - the raw "MACD crosses its signal line" event is
                                noisy near the zero line. We suppress crosses that
                                fall inside an error margin (an epsilon band scaled
                                to the histogram's own recent volatility) and
                                require N bars of confirmation. This is the sell
                                guardrail the operator flagged.
  3. Divergence detection     - price makes a higher high while MACD makes a lower
                                high (bearish), or the mirror (bullish). Computed
                                on CONFIRMED swing pivots so it never peeks ahead.

Everything here is causal: a value at bar i uses only bars <= i (divergence is
stamped at the bar the later pivot is confirmed, not at the pivot itself).

Vocabulary, per the standard reading of the indicator:
  MACD line   = EMA(fast) - EMA(slow)
  Signal line = EMA(signal) of the MACD line
  Histogram   = MACD line - Signal line
  Convergence = histogram shrinking toward zero  (momentum fading)
  Divergence  = histogram growing away from zero (momentum building)
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class MACDConfig:
    """All knobs in one place. Defaults are the classic 12/26/9."""

    fast: int = 12          # fast EMA span
    slow: int = 26          # slow EMA span
    signal: int = 9         # signal-line EMA span (the "EMA line" crosses watch)

    # --- guardrails on the crossover signal ---------------------------------
    noise_k: float = 0.5    # epsilon band = noise_k * rolling std of histogram.
                            #   A cross only counts if the histogram clears this
                            #   band; bigger noise_k = fewer, higher-conviction
                            #   signals. 0 disables the band entirely.
    noise_window: int = 50  # lookback (bars) for the histogram volatility used
                            #   to size the epsilon band.
    confirm_bars: int = 1   # histogram must hold its new sign this many bars
                            #   before the cross is accepted (1 = accept on the
                            #   bar of the cross; 2 = wait one more bar; ...).

    # --- divergence detection -----------------------------------------------
    pivot_window: int = 6   # a swing high/low must be the extreme of +/- this
                            #   many bars. Confirmed pivot_window bars late.
    div_lookback: int = 60  # only compare a new pivot to prior pivots within
                            #   this many bars.

    def as_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Core metric
# --------------------------------------------------------------------------- #
def compute_macd(close: pd.Series, cfg: MACDConfig = MACDConfig()) -> pd.DataFrame:
    """Return a frame with the three MACD components for a close-price series.

    Matches inputs/build_dataset.py exactly when cfg is left at 12/26/9:
    EMAs use adjust=False so the recursion is the textbook one.
    """
    close = pd.Series(close).astype(float).reset_index(drop=True)
    ema_fast = close.ewm(span=cfg.fast, adjust=False).mean()
    ema_slow = close.ewm(span=cfg.slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=cfg.signal, adjust=False).mean()
    hist = macd - signal
    return pd.DataFrame({"macd": macd, "signal": signal, "hist": hist})


# --------------------------------------------------------------------------- #
# Swing pivots (causal: confirmed `pivot_window` bars after the fact)
# --------------------------------------------------------------------------- #
def _confirmed_pivots(series: pd.Series, window: int, kind: str) -> pd.Series:
    """Boolean series, True at the *pivot bar* for confirmed swing highs/lows.

    A bar i is a swing high if series[i] is the max over [i-window, i+window].
    It can only be known at bar i+window, so for causal use the caller must read
    the flag no earlier than that. `confirm_index` returns where it becomes known.
    """
    v = series.values
    n = len(v)
    flag = np.zeros(n, dtype=bool)
    for i in range(window, n - window):
        seg = v[i - window : i + window + 1]
        if kind == "high" and v[i] == seg.max() and np.argmax(seg) == window:
            flag[i] = True
        elif kind == "low" and v[i] == seg.min() and np.argmin(seg) == window:
            flag[i] = True
    return pd.Series(flag, index=series.index)


def _detect_divergence(close: pd.Series, macd: pd.Series, cfg: MACDConfig
                       ) -> tuple[pd.Series, pd.Series]:
    """Return (bearish, bullish) boolean series, stamped at the CONFIRM bar.

    Bearish: price higher high, MACD lower high  -> uptrend losing strength.
    Bullish: price lower low,   MACD higher low   -> downtrend losing strength.
    Each signal is placed at pivot_index + pivot_window, i.e. the first bar at
    which the pivot is actually known, so the series stays causal/tradeable.
    """
    n = len(close)
    bear = np.zeros(n, dtype=bool)
    bull = np.zeros(n, dtype=bool)
    w = cfg.pivot_window

    highs = _confirmed_pivots(close, w, "high")
    lows = _confirmed_pivots(close, w, "low")
    high_idx = list(np.where(highs.values)[0])
    low_idx = list(np.where(lows.values)[0])

    for a, b in zip(high_idx, high_idx[1:]):
        if b - a > cfg.div_lookback:
            continue
        if close.iloc[b] > close.iloc[a] and macd.iloc[b] < macd.iloc[a]:
            conf = min(b + w, n - 1)
            bear[conf] = True

    for a, b in zip(low_idx, low_idx[1:]):
        if b - a > cfg.div_lookback:
            continue
        if close.iloc[b] < close.iloc[a] and macd.iloc[b] > macd.iloc[a]:
            conf = min(b + w, n - 1)
            bull[conf] = True

    return pd.Series(bear, index=close.index), pd.Series(bull, index=close.index)


# --------------------------------------------------------------------------- #
# Signals (raw + guarded) and a strength score
# --------------------------------------------------------------------------- #
def compute_signals(close: pd.Series, cfg: MACDConfig = MACDConfig()) -> pd.DataFrame:
    """Full MACD frame: components, raw events, guarded signals, divergences.

    Columns added on top of macd/signal/hist:
      cross_up / cross_down       raw signal-line crossovers (this bar)
      zero_up / zero_down         MACD line crossing the zero line
      hist_slope                  hist[i] - hist[i-1]  (momentum of the histogram)
      converging                  histogram shrinking toward zero (early warning)
      eps                         the error-margin band at each bar
      guarded_buy / guarded_sell  crossovers that clear the band AND confirm
      bear_div / bull_div         confirmed divergences (causal)
      strength                    -100..+100 conviction score (sign = direction)
    """
    close = pd.Series(close).astype(float).reset_index(drop=True)
    out = compute_macd(close, cfg)
    macd, signal, hist = out["macd"], out["signal"], out["hist"]

    # Raw crossovers of the MACD line and its signal ("EMA") line.
    above = macd > signal
    cross_up = above & ~above.shift(1, fill_value=False)
    cross_down = ~above & above.shift(1, fill_value=True)

    # Zero-line crossings of the MACD line itself.
    pos = macd > 0
    zero_up = pos & ~pos.shift(1, fill_value=False)
    zero_down = ~pos & pos.shift(1, fill_value=True)

    # Histogram momentum and the "converging toward zero" early warning.
    hist_slope = hist.diff().fillna(0.0)
    converging = (hist.abs() < hist.abs().shift(1)).fillna(False)

    # Error-margin band: scale to the histogram's own recent volatility so the
    # threshold travels with the market instead of being a fixed price amount.
    eps = cfg.noise_k * hist.abs().rolling(cfg.noise_window, min_periods=5).std()
    eps = eps.fillna(0.0)
    cleared = hist.abs() >= eps

    # Confirmation: histogram must hold its sign for `confirm_bars` bars.
    if cfg.confirm_bars <= 1:
        held_pos = pd.Series(True, index=hist.index)
        held_neg = pd.Series(True, index=hist.index)
    else:
        k = cfg.confirm_bars
        held_pos = (hist > 0).rolling(k).sum().fillna(0) >= k
        held_neg = (hist < 0).rolling(k).sum().fillna(0) >= k

    guarded_buy = cross_up & cleared & held_pos
    guarded_sell = cross_down & cleared & held_neg

    bear_div, bull_div = _detect_divergence(close, macd, cfg)

    # Conviction score. Sign follows direction (buy +, sell -). Magnitude blends:
    #   how far the histogram cleared the band, histogram slope, zero-line context
    #   (a sell below zero / buy above zero is the stronger continuation case),
    #   and a bonus when divergence corroborates the cross.
    band = eps.replace(0, np.nan)
    clearance = (hist.abs() / band).clip(upper=3).fillna(0) / 3.0   # 0..1
    slope_norm = (hist_slope.abs() / hist.abs().rolling(cfg.noise_window,
                  min_periods=5).mean().abs().replace(0, np.nan)).clip(upper=2).fillna(0) / 2.0
    base = (0.6 * clearance + 0.4 * slope_norm)

    strength = pd.Series(0.0, index=hist.index)
    sell_mask = guarded_sell.copy()
    buy_mask = guarded_buy.copy()
    strength[sell_mask] = -base[sell_mask] * 100
    strength[buy_mask] = base[buy_mask] * 100
    # zero-line context and divergence corroboration nudge magnitude up to 100.
    strength[sell_mask & (macd < 0)] *= 1.15
    strength[buy_mask & (macd > 0)] *= 1.15
    strength[sell_mask & bear_div] *= 1.25
    strength[buy_mask & bull_div] *= 1.25
    strength = strength.clip(-100, 100).round(1)

    out["cross_up"] = cross_up
    out["cross_down"] = cross_down
    out["zero_up"] = zero_up
    out["zero_down"] = zero_down
    out["hist_slope"] = hist_slope
    out["converging"] = converging
    out["eps"] = eps
    out["guarded_buy"] = guarded_buy
    out["guarded_sell"] = guarded_sell
    out["bear_div"] = bear_div
    out["bull_div"] = bull_div
    out["strength"] = strength
    return out


# --------------------------------------------------------------------------- #
# Model features (scale-invariant, causal) - drop-in for build_dataset.py
# --------------------------------------------------------------------------- #
def macd_features(df: pd.DataFrame, cfg: MACDConfig = MACDConfig()) -> pd.DataFrame:
    """Return scale-invariant, causal MACD features indexed like `df`.

    `df` needs a 'close' column. To enrich the model, the operator can paste the
    returned columns into inputs/build_dataset.py:compute_features(), e.g.

        from macd_lab.macd import macd_features, MACDConfig
        df = df.join(macd_features(df, MACDConfig()))

    All columns are ratios/flags/normalised counts, matching the project's
    "no raw price in a feature" rule, and use only data up to each bar.
    """
    close = df["close"].astype(float).reset_index(drop=True)
    s = compute_signals(close, cfg)

    # bars since the last signal-line crossover, normalised by the slow span.
    cross = (s["cross_up"] | s["cross_down"]).values
    bars_since = np.zeros(len(cross))
    last = -1
    for i, c in enumerate(cross):
        if c:
            last = i
        bars_since[i] = (i - last) if last >= 0 else cfg.slow
    bars_since = np.minimum(bars_since, cfg.slow) / cfg.slow

    feat = pd.DataFrame(index=close.index)
    feat["f_macd_hist"] = s["hist"] / close              # matches existing feature
    feat["f_macd_line"] = s["macd"] / close
    feat["f_macd_signal"] = s["signal"] / close
    feat["f_macd_below_zero"] = (s["macd"] < 0).astype(int)
    feat["f_macd_cross_state"] = (s["macd"] > s["signal"]).astype(int)
    feat["f_macd_bars_since_cross"] = bars_since
    feat["f_macd_hist_slope"] = s["hist_slope"] / close
    feat["f_macd_guarded_buy"] = s["guarded_buy"].astype(int)
    feat["f_macd_guarded_sell"] = s["guarded_sell"].astype(int)
    feat["f_macd_bear_div"] = s["bear_div"].astype(int)
    feat["f_macd_bull_div"] = s["bull_div"].astype(int)
    feat["f_macd_strength"] = s["strength"] / 100.0
    feat.index = df.index
    return feat
