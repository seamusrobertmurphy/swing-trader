# Probability calibration, 4h frame (09 September 2026)

Fitted on 85,131 training observations to 2025-06-21, calibrated on a held-out 21,283-row slice of the same training window, and scored once on the 18,872-row blind year. Base rate 0.254. The estimator carries `class_weight=balanced`.

A calibrated probability means what it says: of the observations the model called 30 per cent, 30 per cent should have gone on to hit the barrier. Expected calibration error is the average gap between predicted and observed frequency weighted by bin population; maximum calibration error is the widest gap in any bin, which matters because a confidence threshold trades inside one bin rather than across the average.

## Summary

| mapping | ECE | MCE | Brier | reliability | resolution | uncertainty |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| raw | 0.1916 | 0.4547 | 0.2280 | 0.04028 | 0.00179 | 0.1893 |
| Platt | 0.0206 | 0.1680 | 0.1880 | 0.00050 | 0.00115 | 0.1893 |
| isotonic | 0.0208 | 0.2524 | 0.1880 | 0.00052 | 0.00143 | 0.1893 |

Brier decomposes as reliability minus resolution plus uncertainty. Reliability is the calibration penalty and falls toward zero as a mapping does its job. Resolution rewards departure from the base rate and is a property of the ranking, so a monotone mapping leaves it close to unchanged. Uncertainty is the base rate's own variance and belongs to the data.


## Reliability, raw

| predicted band | n | mean predicted | observed frequency | gap |
| --- | ---: | ---: | ---: | ---: |
| 0.0-0.1 | 7 | 0.088 | 0.286 | +0.198 |
| 0.1-0.2 | 180 | 0.168 | 0.094 | -0.074 |
| 0.2-0.3 | 1,470 | 0.263 | 0.169 | -0.094 |
| 0.3-0.4 | 4,581 | 0.356 | 0.224 | -0.132 |
| 0.4-0.5 | 6,658 | 0.450 | 0.254 | -0.196 |
| 0.5-0.6 | 4,824 | 0.542 | 0.297 | -0.245 |
| 0.6-0.7 | 1,058 | 0.634 | 0.326 | -0.308 |
| 0.7-0.8 | 86 | 0.734 | 0.279 | -0.455 |
| 0.8-0.9 | 8 | 0.815 | 0.375 | -0.440 |

## Reliability, Platt

| predicted band | n | mean predicted | observed frequency | gap |
| --- | ---: | ---: | ---: | ---: |
| 0.1-0.2 | 408 | 0.185 | 0.130 | -0.056 |
| 0.2-0.3 | 13,914 | 0.262 | 0.240 | -0.022 |
| 0.3-0.4 | 4,526 | 0.320 | 0.307 | -0.013 |
| 0.4-0.5 | 24 | 0.418 | 0.250 | -0.168 |

## Reliability, isotonic

| predicted band | n | mean predicted | observed frequency | gap |
| --- | ---: | ---: | ---: | ---: |
| 0.0-0.1 | 19 | 0.011 | 0.263 | +0.252 |
| 0.1-0.2 | 916 | 0.152 | 0.148 | -0.003 |
| 0.2-0.3 | 12,169 | 0.263 | 0.238 | -0.025 |
| 0.3-0.4 | 5,768 | 0.318 | 0.303 | -0.015 |

## Verdict

The raw probabilities carry an expected calibration error of 0.1916 and a maximum of 0.4547. The lowest error after mapping is Platt at 0.0206. Calibration reduces the error by 0.1709 in probability units.

Calibration is monotone, so it does not change AUC or the order in which trades are ranked. It changes the number a confidence threshold and a Kelly fraction read, which is where a miscalibrated probability does its damage.

Full reliability tables: `04-outputs/AA-evals/2026-09-09/calibration-4h-balanced-20260909.csv`

