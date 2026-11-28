# Which inputs carry signal (08 September 2026)

Computed on the training window of each frame. The blind final year was not opened.

Three columns, and none of them is trustworthy alone. **alone** is how far a feature's own AUC sits from 0.500, a coin flip, so 0.020 means it ranks winners above losers 52 per cent of the time by itself. **stable** is the share of walk-forward folds in which it pointed the same way as it did over the whole window, so 0.40 means it changed sides in three folds out of five and is a regime rather than a feature. **in company** is how much worse the model's Brier score gets when that one column is shuffled, which catches a feature that is useless alone and useful beside others, and equally a feature that duplicates something the model already has.


## The 4h frame

40,000 training rows to 2025-06-21, 90 features, base rate 0.262.

### By family

| family | what it is | inputs | alone | stable | in company | missing % |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `f_btc_` | strength relative to the market (bitcoin, or SPY on shares) | 7 | 0.0188 | 0.83 | +0.00692 | 0.0 |
| `f_ta_pta_` | pandas-ta indicators | 7 | 0.0486 | 1.00 | +0.00226 | 0.0 |
| `f_w1_` | the weekly picture | 5 | 0.0170 | 0.72 | +0.00213 | 0.0 |
| `f_wc_` | the coin's own price over day-length windows | 12 | 0.0143 | 0.67 | +0.00172 | 0.0 |
| `f_ta_` | in-house indicators (Williams %R, stochastic, CCI, money flow, ADX, Aroon) | 8 | 0.0444 | 0.90 | +0.00160 | 0.0 |
| `f_hr_` | the coin's own price over intraday windows | 14 | 0.0256 | 0.74 | +0.00151 | 0.0 |
| `f_d1_` | the daily picture | 5 | 0.0077 | 0.72 | +0.00115 | 0.0 |
| `f_flow_` | buy and sell order flow | 4 | 0.0085 | 0.75 | +0.00088 | 0.0 |
| `f_st_` | triple Supertrend | 7 | 0.0313 | 0.89 | +0.00055 | 0.0 |
| `f_mst_` | adaptive Supertrend with the efficiency gate | 6 | 0.0077 | 0.60 | +0.00041 | 0.0 |
| `f_tl_` | TA-Lib extras (parabolic SAR, MESA, Hilbert cycle, candle patterns) | 15 | 0.0116 | 0.75 | +0.00029 | 0.0 |

### The ten the model leans on hardest

| feature | family | alone | stable | in company |
| --- | --- | ---: | ---: | ---: |
| `f_btc_mom_168` | `f_btc_` | 0.0017 | 0.80 | +0.01810 |
| `f_btc_mom_24` | `f_btc_` | 0.0367 | 0.80 | +0.01228 |
| `f_btc_mom_6` | `f_btc_` | 0.0358 | 1.00 | +0.00725 |
| `f_ta_aroon_osc` | `f_ta_` | 0.0190 | 0.80 | +0.00544 |
| `f_ta_pta_cksp_long_dist` | `f_ta_pta_` | 0.0616 | 1.00 | +0.00539 |
| `f_ta_pta_ppo_hist` | `f_ta_pta_` | 0.0567 | 1.00 | +0.00497 |
| `f_hr_atr_pct` | `f_hr_` | 0.0203 | 0.60 | +0.00484 |
| `f_btc_corr_168` | `f_btc_` | 0.0112 | 0.60 | +0.00422 |
| `f_btc_beta_168` | `f_btc_` | 0.0161 | 1.00 | +0.00407 |
| `f_ta_pta_trix` | `f_ta_pta_` | 0.0308 | 1.00 | +0.00371 |

### The ten the model does not use

Shuffling any of these changed the model's score by less than one part in a hundred thousand, so the model is not reading them at all. 16 of 90 features sit in that band.

| feature | family | alone | stable | in company |
| --- | --- | ---: | ---: | ---: |
| `f_d1_st_up` | `f_d1_` | 0.0083 | 1.00 | -0.00000 |
| `f_mst_flip` | `f_mst_` | 0.0035 | 1.00 | +0.00000 |
| `f_tl_cdl_three_black` | `f_tl_` | 0.0000 | 0.33 | +0.00000 |
| `f_flow_taker_ratio` | `f_flow_` | 0.0118 | 1.00 | +0.00000 |
| `f_tl_cdl_three_white` | `f_tl_` | 0.0001 | 0.75 | +0.00000 |
| `f_tl_cdl_eveningstar` | `f_tl_` | 0.0004 | 0.60 | +0.00000 |
| `f_tl_cdl_morningstar` | `f_tl_` | 0.0004 | 0.60 | +0.00000 |
| `f_tl_cdl_doji` | `f_tl_` | 0.0054 | 1.00 | +0.00000 |
| `f_tl_cdl_shootingstar` | `f_tl_` | 0.0008 | 0.80 | +0.00000 |
| `f_tl_cdl_hammer` | `f_tl_` | 0.0045 | 1.00 | +0.00000 |

**14 of 90 features held their direction in fewer than three folds out of five.** Those are the ones that describe a period rather than a market.

Full table: `04-outputs/AA-evals/2026-09-08/feature-report-4h-20260908.csv`

