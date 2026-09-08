# Probability calibration, 4h frame (08 September 2026)

Fitted on 48,000 training observations to 2025-06-21, calibrated on a held-out 12,000-row slice of the same training window, and scored once on the 18,872-row blind year. Base rate 0.254. The estimator carries `class_weight=None`.

A calibrated probability means what it says: of the observations the model called 30 per cent, 30 per cent should have gone on to hit the barrier. Expected calibration error is the average gap between predicted and observed frequency weighted by bin population; maximum calibration error is the widest gap in any bin, which matters because a confidence threshold trades inside one bin rather than across the average.

## Summary

| mapping | ECE | MCE | Brier | reliability | resolution | uncertainty |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| raw | 0.0736 | 0.6542 | 0.2060 | 0.01728 | 0.00090 | 0.1893 |
| Platt | 0.0301 | 0.3367 | 0.1926 | 0.00381 | 0.00046 | 0.1893 |
| isotonic | 0.0304 | 0.6718 | 0.1919 | 0.00356 | 0.00073 | 0.1893 |

Brier decomposes as reliability minus resolution plus uncertainty. Reliability is the calibration penalty and falls toward zero as a mapping does its job. Resolution rewards departure from the base rate and is a property of the ranking, so a monotone mapping leaves it close to unchanged. Uncertainty is the base rate's own variance and belongs to the data.


## Reliability, raw

| predicted band | n | mean predicted | observed frequency | gap |
| --- | ---: | ---: | ---: | ---: |
| 0.0-0.1 | 273 | 0.081 | 0.117 | +0.036 |
| 0.1-0.2 | 4,272 | 0.162 | 0.217 | +0.055 |
| 0.2-0.3 | 8,020 | 0.249 | 0.268 | +0.020 |
| 0.3-0.4 | 4,017 | 0.340 | 0.277 | -0.062 |
| 0.4-0.5 | 1,039 | 0.442 | 0.250 | -0.192 |
| 0.5-0.6 | 466 | 0.545 | 0.255 | -0.289 |
| 0.6-0.7 | 286 | 0.649 | 0.283 | -0.366 |
| 0.7-0.8 | 248 | 0.748 | 0.198 | -0.550 |
| 0.8-0.9 | 214 | 0.846 | 0.192 | -0.654 |
| 0.9-1.0 | 37 | 0.919 | 0.351 | -0.568 |

## Reliability, Platt

| predicted band | n | mean predicted | observed frequency | gap |
| --- | ---: | ---: | ---: | ---: |
| 0.1-0.2 | 501 | 0.184 | 0.136 | -0.048 |
| 0.2-0.3 | 13,239 | 0.260 | 0.255 | -0.005 |
| 0.3-0.4 | 4,238 | 0.328 | 0.265 | -0.063 |
| 0.4-0.5 | 588 | 0.442 | 0.257 | -0.186 |
| 0.5-0.6 | 270 | 0.540 | 0.204 | -0.337 |
| 0.6-0.7 | 36 | 0.623 | 0.361 | -0.262 |

## Reliability, isotonic

| predicted band | n | mean predicted | observed frequency | gap |
| --- | ---: | ---: | ---: | ---: |
| 0.0-0.1 | 58 | 0.058 | 0.103 | +0.045 |
| 0.1-0.2 | 1,026 | 0.165 | 0.168 | +0.003 |
| 0.2-0.3 | 11,037 | 0.268 | 0.255 | -0.013 |
| 0.3-0.4 | 6,298 | 0.315 | 0.270 | -0.045 |
| 0.4-0.5 | 200 | 0.406 | 0.190 | -0.216 |
| 0.5-0.6 | 197 | 0.545 | 0.203 | -0.342 |
| 0.6-0.7 | 20 | 0.668 | 0.050 | -0.618 |
| 0.7-0.8 | 2 | 0.797 | 0.500 | -0.297 |
| 0.8-0.9 | 11 | 0.854 | 0.182 | -0.672 |
| 0.9-1.0 | 23 | 1.000 | 0.435 | -0.565 |

## Verdict

The raw probabilities carry an expected calibration error of 0.0736 and a maximum of 0.6542. The lowest error after mapping is Platt at 0.0301. Calibration reduces the error by 0.0435 in probability units.

Calibration is monotone, so it does not change AUC or the order in which trades are ranked. It changes the number a confidence threshold and a Kelly fraction read, which is where a miscalibrated probability does its damage.

Full reliability tables: `04-outputs/AA-evals/2026-09-08/calibration-4h-unweighted-20260908.csv`

