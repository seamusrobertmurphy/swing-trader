# Sweep digest, 08 September 2026 21:11

Every configuration sweep on disk: **76 sweeps**, 456 configuration fits in total. Rewritten in place on each update.

Axes covered so far: families ['all', 'f_btc_', 'f_btc_ f_st_ f_wc_', 'f_st_ f_wc_ f_hr_'], folds ['3', '5', '8'], holdout ['365', '545'], n_symbols ['1', '2', '3', '8'], weight ['balanced', 'none']

## Does the ranking hold across conditions

Each sweep ranks the six configurations on held-out RMSE. A configuration that wins on one condition and loses on the next is not better, it is lucky.

| configuration | times first | mean place | best | worst |
| --- | ---: | ---: | ---: | ---: |
| deeper-narrower | 0 of 76 | 3.08 | 2 | 4 |
| pruned-subsampled | 0 of 76 | 3.17 | 3 | 5 |
| more-trees | 24 of 76 | 3.20 | 1 | 6 |
| incumbent | 16 of 76 | 3.22 | 1 | 6 |
| library-defaults | 36 of 76 | 3.63 | 1 | 6 |
| all-features | 0 of 76 | 4.70 | 2 | 6 |

The ranking moves between sweeps, so it is a property of the condition as much as of the configuration.

## Does the axis matter more than the configuration

The configuration span is how far apart the six configurations sit within one sweep. Each axis span is how far the winning configuration's held-out error moves when only that axis changes. An axis that moves it further than the configurations do is the bigger lever, and tuning the forest is then the wrong question.

Configuration span within a sweep: mean **0.0298**, largest 0.0481.

| axis | span of the winner's held-out RMSE | values |
| --- | ---: | --- |
| weight | 0.0258 | balanced 0.4622, none 0.4365 |
| n_symbols | 0.0232 | 1 0.4578, 2 0.4346, 3 0.4474, 8 0.4473 |
| families | 0.0055 | all 0.4445, f_btc_ 0.4483, f_btc_ f_st_ f_wc_ 0.4501, f_st_ f_wc_ f_hr_ 0.4488 |
| folds | 0.0040 | 3 0.4462, 5 0.4499, 8 0.4503 |
| holdout | 0.0025 | 365 0.4475, 545 0.4500 |

The largest axis is **weight** at 0.0258, against a mean configuration span of 0.0298, so the configurations still separate further than the axis does.

## Did anything beat always predicting the base rate

Theil's U2 below one on the blind period, from a configuration that also passed the overfit bar. This is the only column here that would change what gets traded.

**41 of 456 fits.**

| configuration | symbols | folds | holdout | weight | families | blind U2 | ratio |
| --- | ---: | ---: | ---: | --- | --- | ---: | ---: |
| incumbent | 3 | 3 | 365 | none | f_st_ f_wc_ f_hr_ | 0.9961 | 1.014 |
| incumbent | 3 | 5 | 365 | none | f_st_ f_wc_ f_hr_ | 0.9961 | 1.018 |
| incumbent | 3 | 8 | 365 | none | f_st_ f_wc_ f_hr_ | 0.9961 | 1.022 |
| more-trees | 3 | 3 | 365 | none | f_st_ f_wc_ f_hr_ | 0.9964 | 1.013 |
| more-trees | 3 | 5 | 365 | none | f_st_ f_wc_ f_hr_ | 0.9964 | 1.018 |
| more-trees | 3 | 8 | 365 | none | f_st_ f_wc_ f_hr_ | 0.9964 | 1.022 |
| incumbent | 3 | 3 | 545 | none | f_st_ f_wc_ f_hr_ | 0.9973 | 1.017 |
| incumbent | 3 | 5 | 545 | none | f_st_ f_wc_ f_hr_ | 0.9973 | 1.021 |
| incumbent | 3 | 8 | 545 | none | f_st_ f_wc_ f_hr_ | 0.9973 | 1.027 |
| incumbent | 1 | 5 | 545 | none | f_btc_ f_st_ f_wc_ | 0.9974 | 1.034 |
| incumbent | 1 | 8 | 545 | none | f_btc_ f_st_ f_wc_ | 0.9974 | 1.038 |
| incumbent | 1 | 3 | 545 | none | f_btc_ f_st_ f_wc_ | 0.9974 | 1.035 |
| more-trees | 3 | 3 | 545 | none | f_st_ f_wc_ f_hr_ | 0.9976 | 1.016 |
| more-trees | 3 | 5 | 545 | none | f_st_ f_wc_ f_hr_ | 0.9976 | 1.021 |
| more-trees | 3 | 8 | 545 | none | f_st_ f_wc_ f_hr_ | 0.9976 | 1.026 |
| more-trees | 1 | 3 | 545 | none | f_btc_ f_st_ f_wc_ | 0.9977 | 1.035 |
| more-trees | 1 | 5 | 545 | none | f_btc_ f_st_ f_wc_ | 0.9977 | 1.034 |
| more-trees | 1 | 8 | 545 | none | f_btc_ f_st_ f_wc_ | 0.9977 | 1.038 |
| incumbent | 3 | 3 | 545 | none | all | 0.9986 | 1.019 |
| incumbent | 3 | 5 | 545 | none | all | 0.9986 | 1.023 |
| incumbent | 3 | 8 | 545 | none | all | 0.9986 | 1.027 |
| more-trees | 3 | 3 | 545 | none | all | 0.9986 | 1.018 |
| more-trees | 3 | 5 | 545 | none | all | 0.9986 | 1.022 |
| more-trees | 3 | 8 | 545 | none | all | 0.9986 | 1.027 |
| pruned-subsampled | 1 | 3 | 545 | none | f_btc_ f_st_ f_wc_ | 0.9990 | 1.093 |

Each of these is a candidate, not a result. A single blind period is one regime, and the walk-forward kill harness is what decides whether an edge survives being asked the same question in different years.

## Every sweep

| when | symbols | rows | families | folds | holdout | weight | winner | CV RMSE | blind U2 | passed |
| --- | ---: | ---: | --- | ---: | ---: | --- | --- | ---: | ---: | ---: |
| 2026-09-08 17:38 | 3 | 12000 | f_btc_ f_st_ f_wc_ | 3 | 365 | none | more-trees | 0.4331 | 1.002 | 3 of 6 |
| 2026-09-08 17:43 | 2 | 6000 | f_btc_ | 3 | 365 | none | incumbent | 0.4346 | 1.003 | 4 of 6 |
| 2026-09-08 17:43 | 2 | 6000 | f_btc_ | 3 | 365 | none | incumbent | 0.4346 | 1.003 | 4 of 6 |
| 2026-09-08 17:45 | 3 | 12000 | f_btc_ f_st_ f_wc_ | 3 | 365 | none | more-trees | 0.4331 | 1.002 | 3 of 6 |
| 2026-09-08 17:52 | 3 | 12000 | f_btc_ f_st_ f_wc_ | 3 | 365 | none | more-trees | 0.4331 | 1.002 | 3 of 6 |
| 2026-09-08 17:58 | 3 | 12000 | all | 3 | 365 | none | more-trees | 0.4330 | 1.001 | 3 of 6 |
| 2026-09-08 18:00 | 1 | 6000 | f_btc_ f_st_ f_wc_ | 3 | 365 | none | more-trees | 0.4472 | 1.000 | 2 of 6 |
| 2026-09-08 18:02 | 8 | 30000 | f_btc_ f_st_ f_wc_ | 3 | 365 | none | more-trees | 0.4330 | 1.002 | 3 of 6 |
| 2026-09-08 18:04 | 3 | 12000 | f_btc_ | 3 | 365 | none | incumbent | 0.4321 | 1.004 | 4 of 6 |
| 2026-09-08 18:06 | 3 | 12000 | f_st_ f_wc_ f_hr_ | 3 | 365 | none | more-trees | 0.4338 | 0.996 | 3 of 6 |
| 2026-09-08 18:09 | 3 | 12000 | f_btc_ f_st_ f_wc_ | 3 | 365 | balanced | library-defaults | 0.4609 | 1.086 | 3 of 6 |
| 2026-09-08 18:13 | 3 | 12000 | all | 3 | 365 | balanced | library-defaults | 0.4522 | 1.055 | 3 of 6 |
| 2026-09-08 18:14 | 1 | 6000 | f_btc_ f_st_ f_wc_ | 3 | 365 | balanced | library-defaults | 0.4687 | 1.079 | 4 of 6 |
| 2026-09-08 18:16 | 8 | 30000 | f_btc_ f_st_ f_wc_ | 3 | 365 | balanced | library-defaults | 0.4584 | 1.082 | 3 of 6 |
| 2026-09-08 18:18 | 3 | 12000 | f_btc_ | 3 | 365 | balanced | library-defaults | 0.4638 | 1.098 | 4 of 6 |
| 2026-09-08 18:20 | 3 | 12000 | f_st_ f_wc_ f_hr_ | 3 | 365 | balanced | library-defaults | 0.4609 | 1.076 | 3 of 6 |
| 2026-09-08 18:22 | 3 | 12000 | f_btc_ f_st_ f_wc_ | 3 | 545 | none | more-trees | 0.4333 | 1.002 | 3 of 6 |
| 2026-09-08 18:26 | 3 | 12000 | all | 3 | 545 | none | more-trees | 0.4326 | 0.999 | 3 of 6 |
| 2026-09-08 18:27 | 1 | 6000 | f_btc_ f_st_ f_wc_ | 3 | 545 | none | incumbent | 0.4480 | 0.997 | 3 of 6 |
| 2026-09-08 18:29 | 8 | 30000 | f_btc_ f_st_ f_wc_ | 3 | 545 | none | more-trees | 0.4310 | 1.001 | 3 of 6 |
| 2026-09-08 18:30 | 3 | 12000 | f_btc_ | 3 | 545 | none | incumbent | 0.4338 | 1.000 | 3 of 6 |
| 2026-09-08 18:32 | 3 | 12000 | f_st_ f_wc_ f_hr_ | 3 | 545 | none | more-trees | 0.4329 | 0.998 | 3 of 6 |
| 2026-09-08 18:34 | 3 | 12000 | f_btc_ f_st_ f_wc_ | 3 | 545 | balanced | library-defaults | 0.4601 | 1.059 | 2 of 6 |
| 2026-09-08 18:37 | 3 | 12000 | all | 3 | 545 | balanced | library-defaults | 0.4520 | 1.040 | 3 of 6 |
| 2026-09-08 18:38 | 1 | 6000 | f_btc_ f_st_ f_wc_ | 3 | 545 | balanced | library-defaults | 0.4743 | 1.063 | 4 of 6 |
| 2026-09-08 18:40 | 8 | 30000 | f_btc_ f_st_ f_wc_ | 3 | 545 | balanced | library-defaults | 0.4569 | 1.056 | 3 of 6 |
| 2026-09-08 18:41 | 3 | 12000 | f_btc_ | 3 | 545 | balanced | library-defaults | 0.4689 | 1.069 | 3 of 6 |
| 2026-09-08 18:43 | 3 | 12000 | f_st_ f_wc_ f_hr_ | 3 | 545 | balanced | library-defaults | 0.4582 | 1.058 | 3 of 6 |
| 2026-09-08 18:47 | 3 | 12000 | f_btc_ f_st_ f_wc_ | 5 | 365 | none | more-trees | 0.4349 | 1.002 | 3 of 6 |
| 2026-09-08 18:53 | 3 | 12000 | all | 5 | 365 | none | more-trees | 0.4347 | 1.001 | 3 of 6 |
| 2026-09-08 18:55 | 1 | 6000 | f_btc_ f_st_ f_wc_ | 5 | 365 | none | incumbent | 0.4452 | 1.000 | 3 of 6 |
| 2026-09-08 18:58 | 8 | 30000 | f_btc_ f_st_ f_wc_ | 5 | 365 | none | incumbent | 0.4348 | 1.002 | 3 of 6 |
| 2026-09-08 19:00 | 3 | 12000 | f_btc_ | 5 | 365 | none | more-trees | 0.4342 | 1.003 | 4 of 6 |
| 2026-09-08 19:03 | 3 | 12000 | f_st_ f_wc_ f_hr_ | 5 | 365 | none | incumbent | 0.4355 | 0.996 | 3 of 6 |
| 2026-09-08 19:05 | 3 | 12000 | f_btc_ f_st_ f_wc_ | 5 | 365 | balanced | library-defaults | 0.4599 | 1.086 | 2 of 6 |
| 2026-09-08 19:10 | 3 | 12000 | all | 5 | 365 | balanced | library-defaults | 0.4529 | 1.055 | 2 of 6 |
| 2026-09-08 19:11 | 1 | 6000 | f_btc_ f_st_ f_wc_ | 5 | 365 | balanced | library-defaults | 0.4663 | 1.079 | 3 of 6 |
| 2026-09-08 19:13 | 8 | 30000 | f_btc_ f_st_ f_wc_ | 5 | 365 | balanced | library-defaults | 0.4609 | 1.082 | 3 of 6 |
| 2026-09-08 19:15 | 3 | 12000 | f_btc_ | 5 | 365 | balanced | library-defaults | 0.4665 | 1.098 | 3 of 6 |
| 2026-09-08 19:19 | 3 | 12000 | f_st_ f_wc_ f_hr_ | 5 | 365 | balanced | library-defaults | 0.4618 | 1.076 | 3 of 6 |
| 2026-09-08 19:22 | 3 | 12000 | f_btc_ f_st_ f_wc_ | 5 | 545 | none | incumbent | 0.4349 | 1.002 | 3 of 6 |
| 2026-09-08 19:27 | 3 | 12000 | all | 5 | 545 | none | more-trees | 0.4343 | 0.999 | 3 of 6 |
| 2026-09-08 19:28 | 1 | 6000 | f_btc_ f_st_ f_wc_ | 5 | 545 | none | more-trees | 0.4474 | 0.998 | 3 of 6 |
| 2026-09-08 19:31 | 8 | 30000 | f_btc_ f_st_ f_wc_ | 5 | 545 | none | more-trees | 0.4348 | 1.001 | 2 of 6 |
| 2026-09-08 19:32 | 3 | 12000 | f_btc_ | 5 | 545 | none | more-trees | 0.4336 | 0.999 | 4 of 6 |
| 2026-09-08 19:35 | 3 | 12000 | f_st_ f_wc_ f_hr_ | 5 | 545 | none | incumbent | 0.4347 | 0.997 | 3 of 6 |
| 2026-09-08 19:37 | 3 | 12000 | f_btc_ f_st_ f_wc_ | 5 | 545 | balanced | library-defaults | 0.4638 | 1.059 | 2 of 6 |
| 2026-09-08 19:41 | 3 | 12000 | all | 5 | 545 | balanced | library-defaults | 0.4575 | 1.040 | 2 of 6 |
| 2026-09-08 19:41 | 1 | 6000 | f_btc_ f_st_ f_wc_ | 5 | 545 | balanced | library-defaults | 0.4704 | 1.063 | 4 of 6 |
| 2026-09-08 19:44 | 8 | 30000 | f_btc_ f_st_ f_wc_ | 5 | 545 | balanced | library-defaults | 0.4660 | 1.056 | 2 of 6 |
| 2026-09-08 19:45 | 3 | 12000 | f_btc_ | 5 | 545 | balanced | library-defaults | 0.4658 | 1.069 | 3 of 6 |
| 2026-09-08 19:48 | 3 | 12000 | f_st_ f_wc_ f_hr_ | 5 | 545 | balanced | library-defaults | 0.4667 | 1.058 | 3 of 6 |
| 2026-09-08 19:52 | 3 | 12000 | f_btc_ f_st_ f_wc_ | 8 | 365 | none | more-trees | 0.4371 | 1.002 | 3 of 6 |
| 2026-09-08 19:59 | 3 | 12000 | all | 8 | 365 | none | more-trees | 0.4363 | 1.001 | 3 of 6 |
| 2026-09-08 20:00 | 1 | 6000 | f_btc_ f_st_ f_wc_ | 8 | 365 | none | incumbent | 0.4446 | 1.000 | 3 of 6 |
| 2026-09-08 20:04 | 8 | 30000 | f_btc_ f_st_ f_wc_ | 8 | 365 | none | incumbent | 0.4365 | 1.002 | 3 of 6 |
| 2026-09-08 20:06 | 3 | 12000 | f_btc_ | 8 | 365 | none | more-trees | 0.4360 | 1.003 | 4 of 6 |
| 2026-09-08 20:10 | 3 | 12000 | f_st_ f_wc_ f_hr_ | 8 | 365 | none | more-trees | 0.4373 | 0.996 | 3 of 6 |
| 2026-09-08 20:13 | 3 | 12000 | f_btc_ f_st_ f_wc_ | 8 | 365 | balanced | library-defaults | 0.4608 | 1.086 | 2 of 6 |
| 2026-09-08 20:20 | 3 | 12000 | all | 8 | 365 | balanced | library-defaults | 0.4562 | 1.055 | 2 of 6 |
| 2026-09-08 20:21 | 1 | 6000 | f_btc_ f_st_ f_wc_ | 8 | 365 | balanced | library-defaults | 0.4658 | 1.079 | 3 of 6 |
| 2026-09-08 20:25 | 8 | 30000 | f_btc_ f_st_ f_wc_ | 8 | 365 | balanced | library-defaults | 0.4563 | 1.082 | 3 of 6 |
| 2026-09-08 20:27 | 3 | 12000 | f_btc_ | 8 | 365 | balanced | library-defaults | 0.4692 | 1.098 | 3 of 6 |
| 2026-09-08 20:31 | 3 | 12000 | f_st_ f_wc_ f_hr_ | 8 | 365 | balanced | library-defaults | 0.4635 | 1.076 | 3 of 6 |
| 2026-09-08 20:34 | 3 | 12000 | f_btc_ f_st_ f_wc_ | 8 | 545 | none | more-trees | 0.4370 | 1.002 | 2 of 6 |
| 2026-09-08 20:42 | 3 | 12000 | all | 8 | 545 | none | incumbent | 0.4361 | 0.999 | 2 of 6 |
| 2026-09-08 20:43 | 1 | 6000 | f_btc_ f_st_ f_wc_ | 8 | 545 | none | incumbent | 0.4492 | 0.997 | 3 of 6 |
| 2026-09-08 20:46 | 8 | 30000 | f_btc_ f_st_ f_wc_ | 8 | 545 | none | incumbent | 0.4375 | 1.000 | 2 of 6 |
| 2026-09-08 20:48 | 3 | 12000 | f_btc_ | 8 | 545 | none | incumbent | 0.4356 | 1.000 | 4 of 6 |
| 2026-09-08 20:52 | 3 | 12000 | f_st_ f_wc_ f_hr_ | 8 | 545 | none | more-trees | 0.4370 | 0.998 | 3 of 6 |
| 2026-09-08 20:55 | 3 | 12000 | f_btc_ f_st_ f_wc_ | 8 | 545 | balanced | library-defaults | 0.4596 | 1.059 | 2 of 6 |
| 2026-09-08 21:00 | 3 | 12000 | all | 8 | 545 | balanced | library-defaults | 0.4568 | 1.040 | 2 of 6 |
| 2026-09-08 21:02 | 1 | 6000 | f_btc_ f_st_ f_wc_ | 8 | 545 | balanced | library-defaults | 0.4666 | 1.063 | 3 of 6 |
| 2026-09-08 21:05 | 8 | 30000 | f_btc_ f_st_ f_wc_ | 8 | 545 | balanced | library-defaults | 0.4612 | 1.056 | 2 of 6 |
| 2026-09-08 21:07 | 3 | 12000 | f_btc_ | 8 | 545 | balanced | library-defaults | 0.4668 | 1.069 | 3 of 6 |
| 2026-09-08 21:11 | 3 | 12000 | f_st_ f_wc_ f_hr_ | 8 | 545 | balanced | library-defaults | 0.4631 | 1.058 | 3 of 6 |
