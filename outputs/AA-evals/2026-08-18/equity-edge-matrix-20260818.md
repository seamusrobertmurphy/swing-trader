=== FULL EQUITY BUILD take 2 Tue 18 Aug 2026 05:09:23 UTC
built 2547 equities (46 skipped), 4996861 rows, 96 features, base rate 0.253
wrote /Volumes/PortableSSD/Github/day-trader/inputs/alpaca-data/dataset_eq1d_allmarket.parquet
=== EDGE MATRIX spy+breadth cost 0.05 Tue 18 Aug 2026 05:13:13 UTC
equities 1d  OOS cut=2025-07-20 00:00:00  gate=spy+breadth (SPY col f_btc_mom_24)  cost=0.05%  top 10% at 50-name floor  candidates=48

============================================================================================================
EQUITY CROSS-SECTIONAL EDGE, 1d, gate=spy+breadth, after 0.05% cost. Deciding cell: te_on_top.
============================================================================================================
            signal  gate_open  tr_on_top  tr_on_mkt  te_on_top  te_on_mkt  te_on_n  te_off_top
 f_hr_ema_fast_mid       0.68      0.033      0.177      0.837      0.322    19864       0.679
  f_st_ema200_dist       0.68      0.112      0.177      0.824      0.322    19864       0.668
  f_btc_rel_mom_24       0.68      0.045      0.177      0.812      0.322    19864       0.724
       f_hr_mom_24       0.68      0.045      0.177      0.812      0.322    19864       0.724
       f_wc_mom_20       0.68      0.080      0.177      0.798      0.322    19864       0.709
 f_wc_ema_fast_mid       0.68      0.073      0.177      0.780      0.322    19864       0.417
f_w1_ema_fast_slow       0.68      0.181      0.177      0.753      0.322    19864       0.614
     f_ta_pta_trix       0.68      0.073      0.177      0.752      0.322    19864       0.407
        f_mst_dist       0.68      0.067      0.177      0.744      0.322    19864       1.092
       f_hr_mom_72       0.68      0.177      0.177      0.738      0.322    19864       0.554
 f_btc_rel_mom_168       0.68      0.169      0.177      0.737      0.322    19864       0.591
      f_hr_mom_168       0.68      0.169      0.177      0.737      0.322    19864       0.591
       f_w1_mom_10       0.68      0.040      0.177      0.726      0.322    19864       0.536
       f_st_dist_1       0.68      0.094      0.177      0.717      0.322    19864       0.808
       f_mo_mom_10       0.68      0.217      0.177      0.655      0.333    19540       0.688
       f_wc_mom_60       0.68      0.056      0.177      0.647      0.322    19864       0.341
       f_hr_mom_12       0.68      0.078      0.177      0.644      0.322    19864       0.691
       f_wc_mom_10       0.68      0.092      0.177      0.609      0.322    19864       0.714
 f_ta_pta_ppo_hist       0.68      0.123      0.177      0.591      0.322    19864       0.345
          f_w1_rsi       0.68      0.131      0.177      0.573      0.322    19864       0.454

============================================================================================================
BEST: f_hr_ema_fast_mid  gate open 68%
  TEST  gate-on : top-decile +0.837%/trade  (gated market +0.322%)
  TRAIN gate-on : top-decile +0.033%/trade
============================================================================================================
  => CANDIDATE: clears after cost, train/test consistent. Next: the walk-forward
     kill harness (60% fold pass, tradeable width, attribution breadth).
=== EDGE MATRIX spy+breadth cost 0.10 (stress)
equities 1d  OOS cut=2025-07-20 00:00:00  gate=spy+breadth (SPY col f_btc_mom_24)  cost=0.1%  top 10% at 50-name floor  candidates=48

============================================================================================================
EQUITY CROSS-SECTIONAL EDGE, 1d, gate=spy+breadth, after 0.10% cost. Deciding cell: te_on_top.
============================================================================================================
            signal  gate_open  tr_on_top  tr_on_mkt  te_on_top  te_on_mkt  te_on_n  te_off_top
 f_hr_ema_fast_mid       0.68     -0.017      0.127      0.787      0.272    19864       0.629
  f_st_ema200_dist       0.68      0.062      0.127      0.774      0.272    19864       0.618
  f_btc_rel_mom_24       0.68     -0.005      0.127      0.762      0.272    19864       0.674
       f_hr_mom_24       0.68     -0.005      0.127      0.762      0.272    19864       0.674
       f_wc_mom_20       0.68      0.030      0.127      0.748      0.272    19864       0.659
 f_wc_ema_fast_mid       0.68      0.023      0.127      0.730      0.272    19864       0.367
f_w1_ema_fast_slow       0.68      0.131      0.127      0.703      0.272    19864       0.564
     f_ta_pta_trix       0.68      0.023      0.127      0.702      0.272    19864       0.357
        f_mst_dist       0.68      0.017      0.127      0.694      0.272    19864       1.042
       f_hr_mom_72       0.68      0.127      0.127      0.688      0.272    19864       0.504
 f_btc_rel_mom_168       0.68      0.119      0.127      0.687      0.272    19864       0.541
      f_hr_mom_168       0.68      0.119      0.127      0.687      0.272    19864       0.541
       f_w1_mom_10       0.68     -0.010      0.127      0.676      0.272    19864       0.486
       f_st_dist_1       0.68      0.044      0.127      0.667      0.272    19864       0.758
       f_mo_mom_10       0.68      0.167      0.127      0.605      0.283    19540       0.638
       f_wc_mom_60       0.68      0.006      0.127      0.597      0.272    19864       0.291
       f_hr_mom_12       0.68      0.028      0.127      0.594      0.272    19864       0.641
       f_wc_mom_10       0.68      0.042      0.127      0.559      0.272    19864       0.664
 f_ta_pta_ppo_hist       0.68      0.073      0.127      0.541      0.272    19864       0.295
          f_w1_rsi       0.68      0.081      0.127      0.523      0.272    19864       0.404

============================================================================================================
BEST: f_hr_ema_fast_mid  gate open 68%
  TEST  gate-on : top-decile +0.787%/trade  (gated market +0.272%)
  TRAIN gate-on : top-decile -0.017%/trade
============================================================================================================
  => FRAGILE: clears on TEST only; treat as unproven.
=== EDGE MATRIX ungated cost 0.05 (reference)
equities 1d  OOS cut=2025-07-20 00:00:00  gate=none (SPY col f_btc_mom_24)  cost=0.05%  top 10% at 50-name floor  candidates=48

============================================================================================================
EQUITY CROSS-SECTIONAL EDGE, 1d, gate=none, after 0.05% cost. Deciding cell: te_on_top.
============================================================================================================
            signal  gate_open  tr_on_top  tr_on_mkt  te_on_top  te_on_mkt  te_on_n  te_off_top
        f_mst_dist        1.0      0.272      0.372      0.854      0.461    29040         NaN
 f_hr_ema_fast_mid        1.0      0.245      0.372      0.787      0.461    29040         NaN
  f_btc_rel_mom_24        1.0      0.241      0.372      0.784      0.461    29040         NaN
       f_hr_mom_24        1.0      0.241      0.372      0.784      0.461    29040         NaN
  f_st_ema200_dist        1.0      0.247      0.372      0.775      0.461    29040         NaN
       f_wc_mom_20        1.0      0.264      0.372      0.770      0.461    29040         NaN
       f_st_dist_1        1.0      0.334      0.372      0.746      0.461    29040         NaN
        f_mst_mult        1.0      0.321      0.372      0.723      0.461    29055         NaN
    f_mst_ker_rank        1.0      0.327      0.372      0.720      0.461    29050         NaN
f_w1_ema_fast_slow        1.0      0.253      0.372      0.709      0.461    29040         NaN
    f_btc_beta_168        1.0      0.521      0.372      0.707      0.461    29040         NaN
      f_hr_mom_168        1.0      0.343      0.372      0.691      0.461    29040         NaN
 f_btc_rel_mom_168        1.0      0.343      0.372      0.691      0.461    29040         NaN
         f_mst_ker        1.0      0.328      0.372      0.690      0.461    29040         NaN
       f_hr_mom_72        1.0      0.232      0.372      0.680      0.461    29040         NaN
       f_w1_mom_10        1.0      0.203      0.372      0.666      0.461    29040         NaN
       f_mo_mom_10        1.0      0.382      0.372      0.666      0.468    28538         NaN
 f_wc_ema_fast_mid        1.0      0.197      0.372      0.665      0.461    29040         NaN
       f_hr_mom_12        1.0      0.282      0.372      0.659      0.461    29040         NaN
     f_ta_pta_trix        1.0      0.166      0.372      0.643      0.461    29040         NaN

============================================================================================================
BEST: f_mst_dist  gate open 100%
  TEST  gate-on : top-decile +0.854%/trade  (gated market +0.461%)
  TRAIN gate-on : top-decile +0.272%/trade
============================================================================================================
  => CANDIDATE: clears after cost, train/test consistent. Next: the walk-forward
     kill harness (60% fold pass, tradeable width, attribution breadth).
=== DONE Tue 18 Aug 2026 05:17:40 UTC
