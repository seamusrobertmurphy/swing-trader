"""Kernel density estimates for a probabilistic classifier. PROPOSAL PROTOTYPE.

Drafted 8 September 2026 for review. Nothing in this repository calls it yet and
no verdict rests on it; it exists so the proposal in
05-research/tasks/proposal-kde-metrics.md carries real numbers instead of
formulas. Read that document first.

The case for kernels here is that everything the model emits is a probability
and every measure of it so far has been a histogram. The reliability curve is
ten bins, the calibration error is a weighted sum over those bins, and MISE as
implemented is the same sum again. A histogram answers differently depending on
where its edges fall, and with 1,286 blind rows spread over ten bins the tails
hold a few dozen observations each, which is where the largest calibration gaps
have been reported from. A kernel estimate replaces the edges with a bandwidth,
which is one stated number that can be varied to show the answer does not depend
on it.

Five estimators are prototyped. Each says what it answers and what it cannot.
"""

from __future__ import annotations

import numpy as np

# A probability lives on nought to one and a Gaussian kernel does not, so mass
# leaks past both ends and the density is biased downward there. Reflecting the
# sample at both boundaries before smoothing puts that mass back. This matters
# precisely where it is least convenient: the confident tail, where a threshold
# actually trades.
REFLECT = True


def silverman(x: np.ndarray) -> float:
    """Silverman's rule of thumb. Fast, and too wide when the density is not normal."""
    x = np.asarray(x, float)
    n = x.size
    if n < 2:
        return 0.05
    sd = np.std(x, ddof=1)
    iqr = float(np.subtract(*np.percentile(x, [75, 25])))
    a = min(sd, iqr / 1.349) if iqr > 0 else sd
    return float(0.9 * a * n ** (-0.2)) or 0.01


def scott(x: np.ndarray) -> float:
    x = np.asarray(x, float)
    n = max(x.size, 2)
    return float(np.std(x, ddof=1) * n ** (-0.2)) or 0.01


def kde(x: np.ndarray, grid: np.ndarray, bw: float | None = None,
        reflect: bool = REFLECT) -> np.ndarray:
    """Gaussian kernel density on a grid, reflected at nought and one."""
    x = np.asarray(x, float)
    if x.size == 0:
        return np.zeros_like(grid)
    h = bw or silverman(x)
    sample = np.concatenate([x, -x, 2.0 - x]) if reflect else x
    z = (grid[:, None] - sample[None, :]) / h
    dens = np.exp(-0.5 * z ** 2).sum(axis=1) / (sample.size * h * np.sqrt(2 * np.pi))
    return dens * (3.0 if reflect else 1.0)


def _norm(d: np.ndarray, grid: np.ndarray) -> np.ndarray:
    area = float(np.trapezoid(d, grid))
    return d / area if area > 0 else d


# ---------------------------------------------------------------------------
# 1. The smoothed reliability curve, and MISE as a real integral
# ---------------------------------------------------------------------------

def smooth_reliability(y, p, bw: float | None = None, points: int = 200):
    """Observed frequency as a continuous function of predicted probability.

    A Nadaraya-Watson kernel regression of the outcome on the prediction. This is
    the reliability curve without bins: at every point on the predicted range it
    is the weighted mean outcome of the observations near that point, weighted by
    a Gaussian in the prediction.

    What it answers: where, on the predicted range, does the stated probability
    depart from what happened, and by how much, without the answer depending on
    where ten bin edges happened to fall.

    What it cannot: it says nothing about ranking. A model can sit on the
    diagonal everywhere and still be a coin flip, which is exactly what a flat
    forecast at the base rate does.
    """
    y, p = np.asarray(y, float), np.asarray(p, float)
    h = bw or silverman(p)
    grid = np.linspace(float(p.min()), float(p.max()), points)
    w = np.exp(-0.5 * ((grid[:, None] - p[None, :]) / h) ** 2)
    denom = w.sum(axis=1)
    obs = np.where(denom > 0, (w * y[None, :]).sum(axis=1) / np.maximum(denom, 1e-12),
                   np.nan)
    dens = _norm(kde(p, grid, h), grid)
    return dict(grid=grid, observed=obs, density=dens, bandwidth=h)


def kde_mise(y, p, bw: float | None = None, points: int = 200) -> float:
    """Integrated squared calibration error, integrated rather than summed.

    The squared distance between the smoothed reliability curve and the diagonal,
    integrated over the predicted range against the estimated density of the
    predictions. This is the same quantity model_metrics.mise estimates by
    binning, computed without bins.
    """
    r = smooth_reliability(y, p, bw, points)
    g, obs, dens = r["grid"], r["observed"], r["density"]
    ok = np.isfinite(obs)
    if ok.sum() < 3:
        return float("nan")
    return float(np.trapezoid(((obs[ok] - g[ok]) ** 2) * dens[ok], g[ok]))


# ---------------------------------------------------------------------------
# 2. Class-conditional separation
# ---------------------------------------------------------------------------

def class_separation(y, p, bw: float | None = None, points: int = 400) -> dict:
    """How far apart the two outcome classes sit on the predicted range.

    Estimate the density of the predictions given the outcome was one, and given
    it was nought, then measure the distance between the two curves. This is the
    question AUC answers, asked without ranking and without a threshold, and it
    is reported three ways because the three fail differently:

    overlap    the integral of the smaller of the two densities. One means the
               classes are indistinguishable; nought means perfectly separated.
               The most directly readable of the three.
    l2         the integrated squared difference between the densities. Punishes
               a large gap in a dense region far more than a small one in a tail.
    hellinger  bounded on nought to one, and unlike the L2 distance it is a
               proper metric, so a value can be compared across samples of
               different sizes.

    What it cannot: it is blind to calibration. Shift every prediction by the
    same amount and all three are unchanged, which is exactly the case Theil's
    bias share catches and this does not. Read them together.
    """
    y, p = np.asarray(y, float), np.asarray(p, float)
    p1, p0 = p[y == 1], p[y == 0]
    if p1.size < 5 or p0.size < 5:
        return dict(overlap=None, l2=None, hellinger=None, bandwidth=None)
    h = bw or max(silverman(p), 1e-3)
    grid = np.linspace(0.0, 1.0, points)
    f1 = _norm(kde(p1, grid, h), grid)
    f0 = _norm(kde(p0, grid, h), grid)
    overlap = float(np.trapezoid(np.minimum(f1, f0), grid))
    l2 = float(np.trapezoid((f1 - f0) ** 2, grid))
    hell = float(np.sqrt(max(0.0, 1.0 - np.trapezoid(np.sqrt(f1 * f0), grid))))
    return dict(overlap=overlap, l2=l2, hellinger=hell, bandwidth=h,
                n_pos=int(p1.size), n_neg=int(p0.size))


# ---------------------------------------------------------------------------
# 3. Is the model attempting to discriminate at all
# ---------------------------------------------------------------------------

def spread_of_predictions(p, base: float, bw: float | None = None,
                          points: int = 400) -> dict:
    """The density of the predictions themselves, against the base rate.

    A model with nothing to say returns the base rate for every row, and its
    predictions pile into a spike there. This measures the pile: the share of the
    predicted mass within a tenth of the base rate, and the effective range the
    predictions actually occupy.

    Why it earns a place: every accuracy measure in this repository can be
    satisfied by a model that never departs from the base rate, and several
    nearly are. This says so directly and in one number.
    """
    p = np.asarray(p, float)
    h = bw or max(silverman(p), 1e-3)
    grid = np.linspace(0.0, 1.0, points)
    dens = _norm(kde(p, grid, h), grid)
    near = (grid > base - 0.05) & (grid < base + 0.05)
    mass = float(np.trapezoid(dens[near], grid[near])) if near.sum() > 2 else float("nan")
    q = np.percentile(p, [5, 50, 95])
    return dict(mass_near_base=mass, p05=float(q[0]), p50=float(q[1]),
                p95=float(q[2]), span_90=float(q[2] - q[0]), bandwidth=h)


# ---------------------------------------------------------------------------
# 4. A null band, so a wobble is judged against noise
# ---------------------------------------------------------------------------

def null_band(y, p, draws: int = 200, bw: float | None = None,
              points: int = 200, seed: int = 0) -> dict:
    """What the smoothed reliability curve looks like when there is no signal.

    The outcomes are shuffled against the predictions and the curve recomputed,
    many times. The band is the middle 90 per cent of those curves. A real curve
    inside the band at a point says the departure there is what this many
    observations produce by chance.

    This is the piece the binned reliability table has never had. The largest
    calibration errors reported in this repository come from bins holding a few
    dozen rows, and nothing has said whether a gap of 0.4 in such a bin is a
    finding or a sample size.
    """
    y, p = np.asarray(y, float), np.asarray(p, float)
    h = bw or silverman(p)
    real = smooth_reliability(y, p, h, points)
    rng = np.random.RandomState(seed)
    curves = np.empty((draws, points))
    for i in range(draws):
        curves[i] = smooth_reliability(rng.permutation(y), p, h, points)["observed"]
    lo = np.nanpercentile(curves, 5, axis=0)
    hi = np.nanpercentile(curves, 95, axis=0)
    obs = real["observed"]
    outside = np.isfinite(obs) & ((obs < lo) | (obs > hi))
    return dict(grid=real["grid"], observed=obs, lo=lo, hi=hi,
                share_outside=float(np.mean(outside[np.isfinite(obs)])),
                bandwidth=h, draws=draws)


# ---------------------------------------------------------------------------
# 5. Does any of it depend on the bandwidth
# ---------------------------------------------------------------------------

def bandwidth_sensitivity(y, p, factors=(0.5, 0.75, 1.0, 1.5, 2.0)) -> list[dict]:
    """Every measure above, recomputed at several bandwidths.

    A kernel estimate replaces the arbitrariness of bin edges with the
    arbitrariness of a bandwidth, and that is only an improvement if the answer
    is shown not to turn on it. This table is what makes the rest reportable: a
    measure whose value moves materially across this range is not reported.
    """
    base = silverman(np.asarray(p, float))
    out = []
    for f in factors:
        h = base * f
        sep = class_separation(y, p, bw=h)
        out.append(dict(factor=f, bandwidth=h, mise=kde_mise(y, p, bw=h),
                        overlap=sep["overlap"], hellinger=sep["hellinger"]))
    return out


def report(y, p, base: float | None = None, draws: int = 200) -> dict:
    """Every proposed measure on one set of predictions."""
    y, p = np.asarray(y, float), np.asarray(p, float)
    b = float(np.mean(y)) if base is None else base
    return dict(
        n=int(y.size), base_rate=b,
        kde_mise=kde_mise(y, p),
        separation=class_separation(y, p),
        spread=spread_of_predictions(p, b),
        null=null_band(y, p, draws=draws),
        sensitivity=bandwidth_sensitivity(y, p),
    )
