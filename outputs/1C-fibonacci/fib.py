"""Fibonacci retracements and extensions, written to be read.

This file is deliberately verbose and self-contained so it can be lifted into
another repo and understood without the rest of the project. It mirrors the
structure of macd_lab/macd.py: one config dataclass, pure functions, and a causal
feature builder at the end.

THE WHOLE IDEA IN THREE SENTENCES
After a strong move, price tends to pull back part of the way before continuing.
The amounts it tends to pull back to cluster around a few ratios derived from the
Fibonacci sequence (0.236, 0.382, 0.5, 0.618, 0.786). Those ratios, laid as
horizontal lines between a recent swing low and swing high, give you a grid of
likely support/resistance; the same ratios projected *past* the swing give you
target levels (1.272, 1.618, ...).

WHERE THE NUMBERS COME FROM
The Fibonacci sequence is 1,1,2,3,5,8,13,21,34,55,...  Divide a term by the next
and the ratio settles at 0.618 (the inverse of the golden ratio phi = 1.618).
Divide by the term two along and you get 0.382; the square root of 0.618 is 0.786;
0.5 is not a Fibonacci ratio at all but is kept by convention because markets
respect the halfway point. Extensions are the same ratios above 1: 1.272 is
sqrt(1.618), 1.618 is phi, 2.618 is phi squared.

ALL MATH IN ONE PLACE
Let lo and hi be the two extremes of the chosen swing and rng = hi - lo.
  retracement(r) = hi - r * rng        # r in 0..1  -> a line between lo and hi
  up_extension(E)   = lo + E * rng      # E > 1      -> a target ABOVE hi
  down_extension(E) = hi - E * rng      # E > 1      -> a target BELOW lo
Retracement lines are identical horizontal levels regardless of trend; what flips
with trend is only how you read them (support in an uptrend, resistance in a
downtrend). Extensions are drawn in the direction the latest leg is travelling.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field

import numpy as np
import pandas as pd


# The canonical ratios. Edit these in one place to retune the whole tool.
RETRACEMENTS = [0.236, 0.382, 0.5, 0.618, 0.786]
EXTENSIONS = [1.272, 1.618, 2.0, 2.618]
GOLDEN_POCKET = (0.5, 0.618)   # the band traders watch most for entries


@dataclass(frozen=True)
class FibConfig:
    """Knobs. Defaults give the standard retracement + extension set."""

    lookback: int = 240          # bars used to find the swing (auto-anchor).
                                 #   ~10 days on an hourly chart. Larger = bigger,
                                 #   slower-moving swing; smaller = more reactive.
    retracements: list = field(default_factory=lambda: list(RETRACEMENTS))
    extensions: list = field(default_factory=lambda: list(EXTENSIONS))
    min_swing_frac: float = 0.0  # ignore swings smaller than this fraction of
                                 #   price (0 = accept any). Filters noise on
                                 #   quiet ranges if you raise it, e.g. 0.03.

    def as_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Swing detection: the auto-anchor
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Swing:
    lo: float          # swing low price
    hi: float          # swing high price
    lo_idx: int        # bar index of the low
    hi_idx: int        # bar index of the high
    up: bool           # True if the latest leg is low -> high (an up-move)

    @property
    def rng(self) -> float:
        return self.hi - self.lo


def detect_swing(high: pd.Series, low: pd.Series, cfg: FibConfig = FibConfig()
                 ) -> Swing | None:
    """Anchor to the highest high and lowest low of the last `lookback` bars.

    This is what charting tools call "auto fib". Direction is decided by recency:
    if the high printed after the low, the most recent leg is up, so we read the
    retracements as support and project extensions upward; if the low printed
    last, the leg is down and we mirror it.

    Returns None if the window is too short or the swing is below min_swing_frac.
    """
    n = len(high)
    if n < 5:
        return None
    w = min(cfg.lookback, n)
    h = high.iloc[-w:]
    l = low.iloc[-w:]
    hi_idx = int(h.idxmax())
    lo_idx = int(l.idxmin())
    hi = float(high.iloc[hi_idx])
    lo = float(low.iloc[lo_idx])
    if hi <= lo:
        return None
    if cfg.min_swing_frac > 0 and (hi - lo) / hi < cfg.min_swing_frac:
        return None
    up = hi_idx > lo_idx          # high more recent -> latest leg is up
    return Swing(lo=lo, hi=hi, lo_idx=lo_idx, hi_idx=hi_idx, up=up)


# --------------------------------------------------------------------------- #
# Levels
# --------------------------------------------------------------------------- #
def retracement_levels(sw: Swing, cfg: FibConfig = FibConfig()) -> dict[float, float]:
    """{ratio: price} for 0, the retracements, and 1.0. Lines between lo and hi."""
    ratios = [0.0] + list(cfg.retracements) + [1.0]
    return {r: sw.hi - r * sw.rng for r in ratios}


def extension_levels(sw: Swing, cfg: FibConfig = FibConfig()) -> dict[float, float]:
    """{ratio: price} for the projection targets, drawn in the leg's direction."""
    if sw.up:
        return {E: sw.lo + E * sw.rng for E in cfg.extensions}     # above hi
    return {E: sw.hi - E * sw.rng for E in cfg.extensions}         # below lo


def golden_pocket(sw: Swing) -> tuple[float, float]:
    """The 0.5-0.618 price band, returned low-to-high."""
    a = sw.hi - GOLDEN_POCKET[0] * sw.rng
    b = sw.hi - GOLDEN_POCKET[1] * sw.rng
    return (min(a, b), max(a, b))


def nearest_level(price: float, sw: Swing, cfg: FibConfig = FibConfig()
                  ) -> tuple[float, float]:
    """(ratio, price) of the retracement line closest to `price`."""
    levels = retracement_levels(sw, cfg)
    r = min(levels, key=lambda k: abs(levels[k] - price))
    return r, levels[r]


# --------------------------------------------------------------------------- #
# Model features: scale-invariant and causal
# --------------------------------------------------------------------------- #
def fib_features(df: pd.DataFrame, cfg: FibConfig = FibConfig()) -> pd.DataFrame:
    """Causal, scale-invariant Fibonacci features indexed like `df`.

    `df` needs 'high','low','close'. At every bar the swing is recomputed using
    only the trailing `lookback` window, so nothing peeks ahead. Drop-in for
    inputs/build_dataset.py:compute_features the same way macd_features is:

        from fib_lab.fib import fib_features, FibConfig
        df = df.join(fib_features(df, FibConfig()))

    Columns (all ratios/flags, no raw price):
      f_fib_pos          where close sits in the swing, (close-lo)/rng, 0..1
      f_fib_dist_near    signed distance to nearest retracement line / close
      f_fib_in_golden    1 if close is inside the 0.5-0.618 pocket
      f_fib_leg_up       1 if the latest leg is an up-move
      f_fib_swing_size   swing height / close (how big the active structure is)
    """
    high, low, close = df["high"], df["low"], df["close"]
    n = len(df)
    pos = np.full(n, np.nan)
    dist = np.full(n, np.nan)
    golden = np.zeros(n)
    legup = np.zeros(n)
    size = np.full(n, np.nan)

    for i in range(n):
        lo_i = max(0, i - cfg.lookback + 1)
        sw = detect_swing(high.iloc[lo_i:i + 1].reset_index(drop=True),
                          low.iloc[lo_i:i + 1].reset_index(drop=True), cfg)
        if sw is None or sw.rng <= 0:
            continue
        c = float(close.iloc[i])
        pos[i] = np.clip((c - sw.lo) / sw.rng, -0.5, 1.5)
        _, lvl_price = nearest_level(c, sw, cfg)
        dist[i] = (c - lvl_price) / c
        gp_lo, gp_hi = golden_pocket(sw)
        golden[i] = 1.0 if gp_lo <= c <= gp_hi else 0.0
        legup[i] = 1.0 if sw.up else 0.0
        size[i] = sw.rng / c

    feat = pd.DataFrame(index=df.index)
    feat["f_fib_pos"] = pos
    feat["f_fib_dist_near"] = dist
    feat["f_fib_in_golden"] = golden
    feat["f_fib_leg_up"] = legup
    feat["f_fib_swing_size"] = size
    return feat
