"""Confluence engine: one signal that fires only when methods agree.

Combines four independent reads of the same candles, each reduced to a single
causal stance at every bar (+1 bullish, -1 bearish, 0 neutral):

  1. MACD      guarded crossover, carried forward as a regime   (macd_lab/macd.py)
  2. MA cross  fast MA above/below slow MA                       (the MA notebook)
  3. Fibonacci price reacting at a retracement level             (fib_lab/fib.py)
  4. Candles   bullish / bearish engulfing                       (the candle notebook)

The composite is a weighted sum of the four stances. A BUY fires when the score
rises to +threshold (enough methods agree up and none strongly opposing); a SELL
when it falls to -threshold. One method alone never trades; agreement does. This
is the guardrail idea taken across indicators instead of within one.

Everything is causal: each stance at bar i uses only bars <= i, so the backtest is
honest about what was knowable in real time. The notebooks that seeded this
(kridtapon's Simple-Candle-Strategy and MA-Crossover-Optimize) are folded in here
with the candle column-swap bug fixed and the MA logic kept causal.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))


def _add_lab(module_file: str) -> str:
    """Find the folder holding `module_file` (e.g. 'macd.py') near this file and
    put it on sys.path. Searches this dir, its ancestors, and their immediate
    sub-folders, so the *_lab folders only need to stay roughly together; they can
    be moved as a group anywhere without breaking the import.
    """
    d = HERE
    roots = []
    for _ in range(5):
        roots.append(d)
        d = os.path.dirname(d)
    for r in roots:
        subdirs = [os.path.join(r, s) for s in os.listdir(r)] if os.path.isdir(r) else []
        for cand in [r] + subdirs:
            if os.path.isfile(os.path.join(cand, module_file)):
                if cand not in sys.path:
                    sys.path.insert(0, cand)
                return cand
    raise ImportError(
        f"confluence.py could not locate {module_file}. Keep macd_lab, fib_lab and "
        f"confluence_lab together (siblings under the same parent).")


_add_lab("macd.py")
_add_lab("fib.py")
from macd import compute_signals, MACDConfig          # noqa: E402
from fib import detect_swing, retracement_levels, golden_pocket, FibConfig  # noqa: E402


@dataclass(frozen=True)
class ConfluenceConfig:
    ma_fast: int = 20
    ma_slow: int = 50
    macd: MACDConfig = field(default_factory=MACDConfig)
    fib: FibConfig = field(default_factory=FibConfig)
    candle_decay: int = 3          # bars a candle signal stays "live"
    weights: dict = field(default_factory=lambda: {
        "macd": 1.0, "ma": 1.0, "fib": 1.0, "candle": 1.0})
    threshold: float = 2.0         # score needed to fire; 2 = at least two methods


# --------------------------------------------------------------------------- #
# The four stances, each causal, each a Series of {-1, 0, +1}
# --------------------------------------------------------------------------- #
def macd_stance(close: pd.Series, cfg: ConfluenceConfig) -> pd.Series:
    """Carry the last guarded MACD signal forward as the prevailing regime."""
    s = compute_signals(close, cfg.macd)
    v = pd.Series(0, index=s.index)
    v[s["guarded_buy"]] = 1
    v[s["guarded_sell"]] = -1
    v = v.replace(0, np.nan).ffill().fillna(0)
    return v.astype(int)


def ma_stance(close: pd.Series, cfg: ConfluenceConfig) -> pd.Series:
    """Fast SMA above slow SMA is +1, below is -1. The MA-crossover notebook."""
    fast = close.rolling(cfg.ma_fast).mean()
    slow = close.rolling(cfg.ma_slow).mean()
    v = np.sign(fast - slow).fillna(0)
    return v.astype(int)


def candle_stance(df: pd.DataFrame, cfg: ConfluenceConfig) -> pd.Series:
    """Bullish / bearish engulfing, held live for a few bars (decay).

    Bullish engulfing: previous candle down, this candle up, and this body fully
    engulfs the previous body. Bearish is the mirror. This is the corrected,
    standard definition; the source notebook's column rename had swapped O/C.
    """
    o, c = df["open"], df["close"]
    po, pc = o.shift(1), c.shift(1)
    prev_down = pc < po
    prev_up = pc > po
    up = c > o
    down = c < o
    bull = prev_down & up & (c >= po) & (o <= pc) & ((c - o) > (po - pc))
    bear = prev_up & down & (c <= po) & (o >= pc) & ((o - c) > (pc - po))

    raw = pd.Series(0, index=df.index)
    raw[bull] = 1
    raw[bear] = -1
    # hold the last signal live for candle_decay bars, then let it lapse
    v = raw.replace(0, np.nan).ffill(limit=cfg.candle_decay).fillna(0)
    return v.astype(int)


def fib_stance(df: pd.DataFrame, cfg: ConfluenceConfig) -> pd.Series:
    """Contextual stance from where price sits on a rolling Fibonacci swing.

    Up-leg and price pulled back into the 0.5-0.618 support pocket -> buy the dip
    (+1). Down-leg and price bounced up into that pocket as resistance -> sell the
    rip (-1). Otherwise neutral. Swing recomputed in a trailing window (causal).
    """
    high, low, close = df["high"], df["low"], df["close"]
    n = len(df)
    out = np.zeros(n)
    lb = cfg.fib.lookback
    for i in range(n):
        a = max(0, i - lb + 1)
        sw = detect_swing(high.iloc[a:i + 1].reset_index(drop=True),
                          low.iloc[a:i + 1].reset_index(drop=True), cfg.fib)
        if sw is None or sw.rng <= 0:
            continue
        gp_lo, gp_hi = golden_pocket(sw)
        price = float(close.iloc[i])
        in_pocket = gp_lo <= price <= gp_hi
        if in_pocket:
            out[i] = 1 if sw.up else -1
    return pd.Series(out, index=df.index).astype(int)


# --------------------------------------------------------------------------- #
# Composite
# --------------------------------------------------------------------------- #
def compute_confluence(df: pd.DataFrame, cfg: ConfluenceConfig = ConfluenceConfig()
                       ) -> pd.DataFrame:
    """Return a frame of the four stances, the weighted score, and buy/sell fires.

    Columns: st_macd, st_ma, st_fib, st_candle, score, buy, sell.
    `buy`/`sell` are edge-triggered: True only on the bar the score first reaches
    the threshold, so we trade the transition into agreement, not every bar of it.
    """
    df = df.reset_index(drop=True)
    w = cfg.weights
    st_macd = macd_stance(df["close"], cfg)
    st_ma = ma_stance(df["close"], cfg)
    st_fib = fib_stance(df, cfg)
    st_candle = candle_stance(df, cfg)

    score = (w["macd"] * st_macd + w["ma"] * st_ma
             + w["fib"] * st_fib + w["candle"] * st_candle)

    bull = score >= cfg.threshold
    bear = score <= -cfg.threshold
    buy = bull & ~bull.shift(1, fill_value=False)
    sell = bear & ~bear.shift(1, fill_value=False)

    return pd.DataFrame({
        "st_macd": st_macd, "st_ma": st_ma, "st_fib": st_fib, "st_candle": st_candle,
        "score": score, "buy": buy, "sell": sell,
    })


# --------------------------------------------------------------------------- #
# Simple long-flat backtest (in-sample; honest about fees, not about overfitting)
# --------------------------------------------------------------------------- #
def backtest(df: pd.DataFrame, conf: pd.DataFrame, fee: float = 0.001,
             init_cash: float = 100.0) -> dict:
    """Go long on a buy, flat on a sell. Next-bar fills, fee per side.

    Returns a dict of headline stats plus the equity curve. This is in-sample over
    the whole window: it tells you whether the rule did anything, not whether it
    will keep working. Walk-forward is the next step if the numbers justify it.
    """
    close = df["close"].reset_index(drop=True).values
    buy = conf["buy"].reset_index(drop=True).values
    sell = conf["sell"].reset_index(drop=True).values
    n = len(close)

    cash, units, in_pos = init_cash, 0.0, False
    equity = np.empty(n)
    trades, wins, entry_px = 0, 0, 0.0
    for i in range(n):
        # act on the prior bar's signal at this bar's open-ish (use close, next bar)
        if i > 0 and buy[i - 1] and not in_pos:
            units = (cash * (1 - fee)) / close[i]
            cash = 0.0
            in_pos = True
            entry_px = close[i]
            trades += 1
        elif i > 0 and sell[i - 1] and in_pos:
            cash = units * close[i] * (1 - fee)
            units = 0.0
            in_pos = False
            if close[i] > entry_px:
                wins += 1
        equity[i] = cash + units * close[i]

    if in_pos:                                   # mark-to-market open position
        if close[-1] > entry_px:
            wins += 1
    final = equity[-1]
    bh = init_cash * close[-1] / close[0]
    peak = np.maximum.accumulate(equity)
    mdd = float(((equity - peak) / peak).min()) if n else 0.0
    return {
        "return_pct": (final / init_cash - 1) * 100,
        "buyhold_pct": (bh / init_cash - 1) * 100,
        "trades": trades,
        "win_rate": (wins / trades * 100) if trades else float("nan"),
        "max_drawdown_pct": mdd * 100,
        "equity": equity,
    }
