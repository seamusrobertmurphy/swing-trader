# Split checks (2026-06-21) -- data-readiness audit, 1h frame

Proportionality / drift audit between the temporal train and the final-year out-of-sample hold-out. This is a DATA-READINESS gate, SEPARATE from the model GO/NO-GO. Thresholds: base-rate +/-5pp, PSI 0.10/0.25, KS alpha 0.01.

**Data-readiness verdict: REVIEW**
- 1/2 features with moderate drift (PSI >= 0.1)

synthetic validation

## Temporal integrity
- train: 2023-01-01 00:00:00 -> 2023-06-16 15:00:00
- test : 2024-06-01 00:00:00 -> 2024-07-04 07:00:00
- gap 350.38d vs embargo 2d -> OK

## Proportionality table (compact)
| check             | item          |   train_stat |   test_stat |   delta | p_or_psi   | flag   |
|:------------------|:--------------|-------------:|------------:|--------:|:-----------|:-------|
| label base-rate   | ALL           |       0.3142 |      0.3    | -1.42   | 0.4518     | ok     |
| binary feature    | f_tl_cdl_doji |       0.1462 |      0.1575 |  1.13   | 0.4453     | ok     |
| continuous PSI/KS | f_wc_mom      |       0.13   |      0      |  0.1155 | moderate   | DRIFT  |
| continuous PSI/KS | f_hr_rv       |       0.0333 |      0.4462 |  0.0092 | ok         | ok     |

## Continuous-feature drift (worst by PSI)
| feature   |   ks_stat |        ks_p |      psi | severity   | flag   |
|:----------|----------:|------------:|---------:|:-----------|:-------|
| f_wc_mom  |      0.13 | 2.89306e-10 | 0.115526 | moderate   | True   |

## Panel representation
- coins in train: 2, in test: 2, one-sided: 0

## Imbalance comparison (natural vs class_weight, embargoed TS-CV, no SMOTE)
| treatment | Kappa | minority recall | OOB | CV acc (mean+/-std) |
| --- | --- | --- | --- | --- |
| natural | 0.010 | 0.030 | 0.710 | 0.690+/-0.010 |
| balanced (chosen) | 0.040 | 0.440 | 0.670 | 0.560+/-0.030 |

Chosen by Kappa + minority recall: **balanced**. Diagnostic only -- the after-fee Metric 2 still decides GO/NO-GO.

## Permutation importance (chosen model, AUC drop)
| feature   |   importance |   std |
|:----------|-------------:|------:|
| f_wc_mom  |        0.012 | 0.001 |
| f_hr_rv   |        0.004 | 0.001 |

## Stratified-random holdout bracket (Parente idiom -- OPTIMISTIC, not the headline)
- 10 stratified 70/30 draws
- Kappa 0.070 +/- 0.005; accuracy 0.550 +/- 0.010; minority recall 0.420 +/- 0.020
- Time-agnostic, so it leaks adjacent bars and overstates the edge; it brackets the temporal number from above and is never the basis for GO/NO-GO.

