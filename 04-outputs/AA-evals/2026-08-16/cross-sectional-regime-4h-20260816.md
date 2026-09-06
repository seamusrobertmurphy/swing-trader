loading dataset_4h_allmarket.parquet ...
OOS split at 2025-06-21 20:00:00  |  regime = f_btc_mom_168 > 0 (BTC trending up)

========================================================================================================
REGIME-GATED CROSS-SECTIONAL EDGE (after 0.20%% fee). up=BTC-up regime, dn=BTC-down.
top=top-third long cohort, mkt=all coins that regime. Deciding cell: te_up_top (TEST, gate open).
========================================================================================================
        signal  gate_open  tr_up_top  tr_up_mkt  te_up_top  te_up_mkt  te_up_n  te_dn_top  te_dn_mkt
     f_mst_dir       0.47     -0.404     -0.332     -0.203     -0.317     1719     -0.410     -0.438
f_btc_corr_168       0.47     -0.242     -0.332     -0.278     -0.317     2965     -0.379     -0.438
    f_d1_st_up       0.47     -0.274     -0.332     -0.117     -0.317     1820     -0.165     -0.438
   f_hr_mom_72       0.47     -0.350     -0.332     -0.147     -0.317     2965     -0.291     -0.438
   f_st_dist_2       0.47     -0.282     -0.332     -0.358     -0.317     2965     -0.367     -0.438

========================================================================================================
BEST: f_d1_st_up  gate open 47% of bars
  TEST  BTC-up : top-third -0.117%/trade  (regime market -0.317%)
  TEST  BTC-dn : top-third -0.165%/trade  (regime market -0.438%)
  TRAIN BTC-up : top-third -0.274%/trade
  reference    : ungated all-regime market baseline -0.382%/trade
========================================================================================================
  => PARTIAL: the gate lifts the top-third edge well above the ungated baseline and beats the
     regime market, but does not yet clear zero. Stack the next lever (longer-horizon label/
     exit, or a stricter gate e.g. BTC-up AND breadth) before a portfolio backtest.
