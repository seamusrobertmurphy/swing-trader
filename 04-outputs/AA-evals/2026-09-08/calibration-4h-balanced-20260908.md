# Probability calibration, 4h frame (08 September 2026)

Fitted on 48,000 training observations to 2025-06-21, calibrated on a held-out 12,000-row slice of the same training window, and scored once on the 18,872-row blind year. Base rate 0.254. The estimator carries `class_weight=balanced`.

A calibrated probability means what it says: of the observations the model called 30 per cent, 30 per cent should have gone on to hit the barrier. Expected calibration error is the average gap between predicted and observed frequency weighted by bin population; maximum calibration error is the widest gap in any bin, which matters because a confidence threshold trades inside one bin rather than across the average.

## Summary

| mapping | ECE | MCE | Brier | reliability | resolution | uncertainty |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| raw | 0.2344 | 0.7005 | 0.2586 | 0.06997 | 0.00092 | 0.1893 |
| Platt | 0.0295 | 0.2818 | 0.1913 | 0.00257 | 0.00046 | 0.1893 |
| isotonic | 0.0314 | 0.6461 | 0.1925 | 0.00373 | 0.00048 | 0.1893 |

Brier decomposes as reliability minus resolution plus uncertainty. Reliability is the calibration penalty and falls toward zero as a mapping does its job. Resolution rewards departure from the base rate and is a property of the ranking, so a monotone mapping leaves it close to unchanged. Uncertainty is the base rate's own variance and belongs to the data.


## Reliability, raw

| predicted band | n | mean predicted | observed frequency | gap |
| --- | ---: | ---: | ---: | ---: |
| 0.0-0.1 | 14 | 0.080 | 0.214 | +0.134 |
| 0.1-0.2 | 229 | 0.169 | 0.148 | -0.020 |
| 0.2-0.3 | 1,299 | 0.261 | 0.181 | -0.080 |
| 0.3-0.4 | 3,349 | 0.356 | 0.227 | -0.129 |
| 0.4-0.5 | 5,629 | 0.452 | 0.261 | -0.191 |
| 0.5-0.6 | 5,092 | 0.546 | 0.283 | -0.263 |
| 0.6-0.7 | 1,953 | 0.640 | 0.267 | -0.373 |
| 0.7-0.8 | 614 | 0.746 | 0.262 | -0.484 |
| 0.8-0.9 | 458 | 0.847 | 0.240 | -0.607 |
| 0.9-1.0 | 235 | 0.926 | 0.226 | -0.701 |

## Reliability, Platt

| predicted band | n | mean predicted | observed frequency | gap |
| --- | ---: | ---: | ---: | ---: |
| 0.1-0.2 | 481 | 0.184 | 0.154 | -0.030 |
| 0.2-0.3 | 12,968 | 0.262 | 0.249 | -0.013 |
| 0.3-0.4 | 4,712 | 0.326 | 0.280 | -0.045 |
| 0.4-0.5 | 565 | 0.442 | 0.234 | -0.209 |
| 0.5-0.6 | 146 | 0.528 | 0.247 | -0.282 |

## Reliability, isotonic

| predicted band | n | mean predicted | observed frequency | gap |
| --- | ---: | ---: | ---: | ---: |
| 0.0-0.1 | 43 | 0.019 | 0.140 | +0.121 |
| 0.1-0.2 | 2,163 | 0.191 | 0.200 | +0.009 |
| 0.2-0.3 | 12,000 | 0.279 | 0.258 | -0.022 |
| 0.3-0.4 | 4,428 | 0.318 | 0.272 | -0.046 |
| 0.4-0.5 | 109 | 0.465 | 0.229 | -0.236 |
| 0.5-0.6 | 2 | 0.569 | 0.500 | -0.069 |
| 0.6-0.7 | 6 | 0.644 | 0.333 | -0.311 |
| 0.7-0.8 | 8 | 0.746 | 0.375 | -0.371 |
| 0.8-0.9 | 108 | 0.850 | 0.204 | -0.646 |
| 0.9-1.0 | 5 | 1.000 | 0.400 | -0.600 |

## Verdict

The raw probabilities carry an expected calibration error of 0.2344 and a maximum of 0.7005. The lowest error after mapping is Platt at 0.0295. Calibration reduces the error by 0.2049 in probability units.

Calibration is monotone, so it does not change AUC or the order in which trades are ranked. It changes the number a confidence threshold and a Kelly fraction read, which is where a miscalibrated probability does its damage.

Full reliability tables: `04-outputs/AA-evals/2026-09-08/calibration-4h-balanced-20260908.csv`

