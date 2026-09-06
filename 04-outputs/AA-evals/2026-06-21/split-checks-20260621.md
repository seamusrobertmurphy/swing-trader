# Split checks (2026-06-21) -- data-readiness audit, 1h frame

Proportionality / drift audit between the temporal train and the final-year out-of-sample hold-out. This is a DATA-READINESS gate, SEPARATE from the model GO/NO-GO. Thresholds: base-rate +/-5pp, PSI 0.10/0.25, KS alpha 0.01.

**Data-readiness verdict: FAIL**
- 12 coin(s) present on only one side: ORDI/USDT, JST/USDT, ALICE/USDT, JTO/USDT, BEL/USDT, ACT/USDT
- 2 feature(s) with MAJOR drift (PSI >= 0.25)
- 11 coin(s) with base-rate drift > 5.0pp

Label: +2.0/-1.0 ATR within 48 bars; base rate 0.313.

## Temporal integrity
- train: 2017-12-15 11:00:00 -> 2025-06-16 23:00:00
- test : 2025-06-19 00:00:00 -> 2026-06-18 23:00:00
- gap 2.04d vs embargo 2d -> OK

## Panel and coin composition (leads -- the dimension most specific to this data)
- coins in train: 33, in test: 31, one-sided (cannot be learned-then-tested): 12
- coins with base-rate drift > 5pp train->test: 11

Dominant coins by train row-share (pooled model is implicitly weighted toward these):
| symbol    |   n_train |   n_test |   train_share |   test_share |
|:----------|----------:|---------:|--------------:|-------------:|
| ETH/USDT  |     51895 |     7600 |        0.1361 |       0.099  |
| BTC/USDT  |     48859 |     5254 |        0.1282 |       0.0684 |
| BNB/USDT  |     41460 |     6244 |        0.1088 |       0.0813 |
| LTC/USDT  |     28775 |     3741 |        0.0755 |       0.0487 |
| SOL/USDT  |     27582 |     8062 |        0.0724 |       0.105  |
| DOGE/USDT |     27324 |     8049 |        0.0717 |       0.1048 |
| ADA/USDT  |     27075 |     6215 |        0.071  |       0.0809 |
| LINK/USDT |     25263 |     4676 |        0.0663 |       0.0609 |

One-sided coins (flagged, exclude or handle): ORDI/USDT, JST/USDT, ALICE/USDT, JTO/USDT, BEL/USDT, ACT/USDT, BICO/USDT, ALLO/USDT, ONDO/USDT, ASTER/USDT, PUMP/USDT, BIO/USDT

## Continuous-feature drift (worst by PSI)
| feature            |   ks_stat |         ks_p |       psi | severity   | flag   |
|:-------------------|----------:|-------------:|----------:|:-----------|:-------|
| f_wc_rv_long       |   0.26802 | 0            | 0.499485  | major      | True   |
| f_wc_ema_mid_slow  |   0.20736 | 0            | 0.491792  | major      | True   |
| f_wc_mom_1440      |   0.1434  | 0            | 0.207924  | moderate   | True   |
| f_wc_rv_ratio      |   0.1478  | 0            | 0.207053  | moderate   | True   |
| f_wc_rv_short      |   0.17314 | 0            | 0.199907  | moderate   | True   |
| f_hr_rv_long       |   0.17282 | 0            | 0.199907  | moderate   | True   |
| f_wc_ema_fast_mid  |   0.1419  | 0            | 0.198024  | moderate   | True   |
| f_wc_atr_pct       |   0.16888 | 0            | 0.186408  | moderate   | True   |
| f_wc_mom_480       |   0.12476 | 0            | 0.117727  | moderate   | True   |
| f_flow_imb_168     |   0.13716 | 0            | 0.0972468 | ok         | True   |
| f_wc_rsi           |   0.11754 | 2.18056e-301 | 0.0955716 | ok         | True   |
| f_flow_imb         |   0.08114 | 1.27539e-143 | 0.0955114 | ok         | True   |
| f_flow_taker_ratio |   0.08316 | 7.52611e-151 | 0.0955114 | ok         | True   |
| f_flow_imb_24      |   0.10058 | 1.26999e-220 | 0.0752179 | ok         | True   |
| f_hr_atr_pct       |   0.1122  | 1.37327e-274 | 0.0677774 | ok         | True   |

## Proportionality table (label + binary features, compact)
| check             | item                     |   train_stat |   test_stat |   delta | p_or_psi   | flag   |
|:------------------|:-------------------------|-------------:|------------:|--------:|:-----------|:-------|
| label base-rate   | ALL                      |       0.3155 |      0.3031 | -1.24   | 0.0        | ok     |
| binary feature    | f_tl_cdl_doji            |       0.1499 |      0.1531 |  0.32   | 0.0241     | ok     |
| binary feature    | f_tl_ht_trendmode        |       0.6165 |      0.6194 |  0.29   | 0.1377     | ok     |
| binary feature    | f_tl_cdl_hammer          |       0.0266 |      0.0283 |  0.17   | 0.0068     | ok     |
| binary feature    | f_tl_cdl_three_white     |       0.0006 |      0.0004 | -0.03   | 0.0073     | ok     |
| binary feature    | f_tl_cdl_morningstar     |       0.0026 |      0.0025 | -0.01   | 0.5347     | ok     |
| continuous PSI/KS | f_wc_rv_long             |       0.268  |      0      |  0.4995 | major      | DRIFT  |
| continuous PSI/KS | f_wc_ema_mid_slow        |       0.2074 |      0      |  0.4918 | major      | DRIFT  |
| continuous PSI/KS | f_wc_mom_1440            |       0.1434 |      0      |  0.2079 | moderate   | DRIFT  |
| continuous PSI/KS | f_wc_rv_ratio            |       0.1478 |      0      |  0.2071 | moderate   | DRIFT  |
| continuous PSI/KS | f_wc_rv_short            |       0.1731 |      0      |  0.1999 | moderate   | DRIFT  |
| continuous PSI/KS | f_hr_rv_long             |       0.1728 |      0      |  0.1999 | moderate   | DRIFT  |
| continuous PSI/KS | f_wc_ema_fast_mid        |       0.1419 |      0      |  0.198  | moderate   | DRIFT  |
| continuous PSI/KS | f_wc_atr_pct             |       0.1689 |      0      |  0.1864 | moderate   | DRIFT  |
| continuous PSI/KS | f_wc_mom_480             |       0.1248 |      0      |  0.1177 | moderate   | DRIFT  |
| continuous PSI/KS | f_flow_imb_168           |       0.1372 |      0      |  0.0972 | ok         | DRIFT  |
| continuous PSI/KS | f_wc_rsi                 |       0.1175 |      0      |  0.0956 | ok         | DRIFT  |
| continuous PSI/KS | f_flow_imb               |       0.0811 |      0      |  0.0955 | ok         | DRIFT  |
| continuous PSI/KS | f_flow_taker_ratio       |       0.0832 |      0      |  0.0955 | ok         | DRIFT  |
| continuous PSI/KS | f_flow_imb_24            |       0.1006 |      0      |  0.0752 | ok         | DRIFT  |
| continuous PSI/KS | f_hr_atr_pct             |       0.1122 |      0      |  0.0678 | ok         | DRIFT  |
| continuous PSI/KS | f_wc_mom_240             |       0.0902 |      0      |  0.0648 | ok         | DRIFT  |
| continuous PSI/KS | f_ta_pta_fisher          |       0.0842 |      0      |  0.0559 | ok         | DRIFT  |
| continuous PSI/KS | f_hr_mom_168             |       0.0876 |      0      |  0.0542 | ok         | DRIFT  |
| continuous PSI/KS | f_hr_rv_ratio            |       0.097  |      0      |  0.0526 | ok         | DRIFT  |
| continuous PSI/KS | f_wc_mom_120             |       0.0734 |      0      |  0.0498 | ok         | DRIFT  |
| continuous PSI/KS | f_hr_rv_short            |       0.0916 |      0      |  0.0445 | ok         | DRIFT  |
| continuous PSI/KS | f_wc_bb_pos              |       0.0821 |      0      |  0.0401 | ok         | DRIFT  |
| continuous PSI/KS | f_hr_vol_ratio           |       0.0671 |      0      |  0.0359 | ok         | DRIFT  |
| continuous PSI/KS | f_ta_pta_cksp_long_dist  |       0.0647 |      0      |  0.0291 | ok         | DRIFT  |
| continuous PSI/KS | f_hr_mom_72              |       0.0538 |      0      |  0.0266 | ok         | DRIFT  |
| continuous PSI/KS | f_ta_cmf                 |       0.0532 |      0      |  0.0232 | ok         | DRIFT  |
| continuous PSI/KS | f_ta_pta_trix            |       0.0499 |      0      |  0.0209 | ok         | DRIFT  |
| continuous PSI/KS | f_ta_stochk              |       0.0489 |      0      |  0.0207 | ok         | DRIFT  |
| continuous PSI/KS | f_ta_willr               |       0.0469 |      0      |  0.0207 | ok         | DRIFT  |
| continuous PSI/KS | f_ta_mfi                 |       0.0465 |      0      |  0.0198 | ok         | DRIFT  |
| continuous PSI/KS | f_hr_ema_mid_slow        |       0.0507 |      0      |  0.0187 | ok         | DRIFT  |
| continuous PSI/KS | f_tl_sar_dist            |       0.0432 |      0      |  0.0176 | ok         | DRIFT  |
| continuous PSI/KS | f_wc_vol_ratio           |       0.0456 |      0      |  0.0161 | ok         | DRIFT  |
| continuous PSI/KS | f_ta_pta_vortex_diff     |       0.0411 |      0      |  0.0145 | ok         | DRIFT  |
| continuous PSI/KS | f_ta_adx                 |       0.0424 |      0      |  0.0141 | ok         | DRIFT  |
| continuous PSI/KS | f_tl_ultosc              |       0.0468 |      0      |  0.0128 | ok         | DRIFT  |
| continuous PSI/KS | f_ta_pta_cmo             |       0.0474 |      0      |  0.0126 | ok         | DRIFT  |
| continuous PSI/KS | f_hr_rsi                 |       0.0475 |      0      |  0.0126 | ok         | DRIFT  |
| continuous PSI/KS | f_hr_ema_fast_mid        |       0.0363 |      0      |  0.0113 | ok         | DRIFT  |
| continuous PSI/KS | f_hr_mom_24              |       0.0365 |      0      |  0.0089 | ok         | DRIFT  |
| continuous PSI/KS | f_ta_aroon_osc           |       0.0347 |      0      |  0.0087 | ok         | DRIFT  |
| continuous PSI/KS | f_hr_mom_12              |       0.0266 |      0      |  0.0072 | ok         | DRIFT  |
| continuous PSI/KS | f_tl_mama_dist           |       0.0237 |      0      |  0.0065 | ok         | DRIFT  |
| continuous PSI/KS | f_hr_mom_6               |       0.0254 |      0      |  0.0065 | ok         | DRIFT  |
| continuous PSI/KS | f_ta_pta_cksp_short_dist |       0.0225 |      0      |  0.0043 | ok         | DRIFT  |
| continuous PSI/KS | f_hr_bb_pos              |       0.0314 |      0      |  0.0038 | ok         | DRIFT  |
| continuous PSI/KS | f_ta_cci                 |       0.0208 |      0      |  0.003  | ok         | DRIFT  |
| continuous PSI/KS | f_ta_dmi_diff            |       0.0242 |      0      |  0.003  | ok         | DRIFT  |
| continuous PSI/KS | f_tl_ht_dcphase          |       0.0188 |      0      |  0.0018 | ok         | DRIFT  |
| continuous PSI/KS | f_ta_pta_ppo_hist        |       0.0093 |      0.0258 |  0.001  | ok         | ok     |
| continuous PSI/KS | f_tl_cdl_engulfing       |       0.0107 |      0.0062 |  0.0006 | ok         | DRIFT  |
| continuous PSI/KS | f_tl_cdl_marubozu        |       0.0016 |      1      |  0.0003 | ok         | ok     |
| continuous PSI/KS | f_tl_cdl_harami          |       0.005  |      0.5527 |  0.0001 | ok         | ok     |
| continuous PSI/KS | f_tl_cdl_three_black     |       0.0001 |      1      |  0      | ok         | ok     |
| continuous PSI/KS | f_tl_cdl_eveningstar     |       0.0005 |      1      |  0      | ok         | ok     |
| continuous PSI/KS | f_tl_cdl_shootingstar    |       0.0002 |      1      |  0      | ok         | ok     |

## Imbalance comparison (natural vs class_weight, embargoed TS-CV, no SMOTE)
| treatment | Kappa | minority recall | Brier (cal) | ECE (cal) | OOB | CV acc (mean+/-std) |
| --- | --- | --- | --- | --- | --- | --- |
| natural (chosen) | -0.027 | 0.095 | 0.2405 | 0.1093 | 0.712 | 0.620+/-0.049 |
| balanced | -0.055 | 0.402 | 0.2626 | 0.1694 | 0.753 | 0.493+/-0.047 |

Chosen by best average rank across Kappa, minority recall and Brier (calibration), tie-broken by Brier: **natural**. Brier and ECE grade whether a treatment distorts the probabilities the 0.60 confidence filter trades on; `balanced` is a candidate, not a default. Diagnostic only -- the after-fee Metric 2 still decides GO/NO-GO.

