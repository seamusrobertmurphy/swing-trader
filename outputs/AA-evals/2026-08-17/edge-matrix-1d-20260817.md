# Edge matrix, 1d frame, 2026-08-17

## Gate btc, standard cost (baseline comparison to the 4h -0.117)
            signal  gate_open  tr_on_top  tr_on_mkt  te_on_top  te_on_mkt  te_on_n  te_off_top  te_off_mkt
    f_btc_corr_168       0.38      0.040     -0.490     -0.906     -1.355      276       0.064      -0.361
       f_mo_mom_10       0.36     -0.465     -0.484     -0.947     -1.344      223       0.075      -0.222
         f_st_flip       0.38     -0.576     -0.490     -1.014     -1.355      114      -1.093      -0.361
          f_w1_rsi       0.38     -0.495     -0.490     -1.069     -1.355      276      -0.471      -0.361
    f_ta_aroon_osc       0.38     -0.494     -0.490     -1.100     -1.355      289      -0.634      -0.361
f_w1_ema_fast_slow       0.38     -0.617     -0.490     -1.164     -1.355      276      -0.129      -0.361
          f_mo_rsi       0.36     -0.395     -0.484     -1.189     -1.344      223      -0.087      -0.222
f_mo_ema_fast_slow       0.36     -0.397     -0.484     -1.210     -1.344      223       0.065      -0.222
 f_btc_rel_mom_168       0.38     -0.782     -0.490     -1.335     -1.355      276      -0.280      -0.361
      f_hr_mom_168       0.38     -0.782     -0.490     -1.335     -1.355      276      -0.280      -0.361
          f_hr_rsi       0.38     -0.699     -0.490     -1.343     -1.355      276      -0.771      -0.361
          f_wc_rsi       0.38     -0.699     -0.490     -1.343     -1.355      276      -0.771      -0.361
       f_st_dist_2       0.38     -0.920     -0.490     -1.351     -1.355      276      -0.870      -0.361
       f_st_dist_3       0.38     -0.721     -0.490     -1.376     -1.355      276      -0.690      -0.361
        f_hr_mom_6       0.38     -0.863     -0.490     -1.397     -1.355      276      -0.862      -0.361
       f_hr_mom_24       0.38     -0.691     -0.490     -1.421     -1.355      276      -0.830      -0.361
  f_btc_rel_mom_24       0.38     -0.691     -0.490     -1.421     -1.355      276      -0.830      -0.361
        f_wc_mom_5       0.38     -0.886     -0.490     -1.438     -1.355      276      -0.947      -0.361
 f_hr_ema_fast_mid       0.38     -0.435     -0.490     -1.493     -1.355      276      -0.759      -0.361
       f_w1_mom_10       0.38     -0.605     -0.490     -1.520     -1.355      276      -0.412      -0.361

============================================================================================================
BEST: f_btc_corr_168  gate open 38% of bars
  TEST  gate-on : top-third -0.906%/trade  (gated market -1.355%)
  TEST  gate-off: top-third +0.064%/trade  (market -0.361%)
  TRAIN gate-on : top-third +0.040%/trade
============================================================================================================
  => NOT CLEARED with this gate/cost. Try a stricter gate, the achievable-cost
     scenario (--cost), or the coarser frame.

## Gate btc+breadth, standard cost
     f_st_dist_2       0.06     -1.306     -1.018     -1.132     -1.496       45      -1.049      -0.688
      f_st_agree       0.06     -1.147     -1.018     -1.215     -1.496       56      -1.844      -0.688
      f_mst_dist       0.06     -1.293     -1.018     -1.250     -1.496       45      -1.245      -0.688
       f_mst_ker       0.06     -0.836     -1.018     -1.269     -1.496       45      -0.872      -0.688
     f_st_dist_3       0.06     -1.013     -1.018     -1.323     -1.496       45      -0.929      -0.688
    f_st_uptrend       0.06     -1.098     -1.018     -1.372     -1.496       54      -2.878      -0.688
     f_st_dist_1       0.06     -1.164     -1.018     -1.524     -1.496       45      -1.040      -0.688
f_btc_rel_mom_24       0.06     -0.968     -1.018     -1.592     -1.496       45      -1.022      -0.688

============================================================================================================
BEST: f_st_flip  gate open 6% of bars
  TEST  gate-on : top-third +0.717%/trade  (gated market -1.496%)
  TEST  gate-off: top-third -1.234%/trade  (market -0.688%)
  TRAIN gate-on : top-third -1.257%/trade
============================================================================================================
  => FRAGILE: clears on TEST only; treat as unproven.

## Gate btc+breadth, achievable cost 0.15%
     f_st_dist_2       0.06     -1.256     -0.968     -1.082     -1.446       45      -0.999      -0.638
      f_st_agree       0.06     -1.097     -0.968     -1.165     -1.446       56      -1.794      -0.638
      f_mst_dist       0.06     -1.243     -0.968     -1.200     -1.446       45      -1.195      -0.638
       f_mst_ker       0.06     -0.786     -0.968     -1.219     -1.446       45      -0.822      -0.638
     f_st_dist_3       0.06     -0.963     -0.968     -1.273     -1.446       45      -0.879      -0.638
    f_st_uptrend       0.06     -1.048     -0.968     -1.322     -1.446       54      -2.828      -0.638
     f_st_dist_1       0.06     -1.114     -0.968     -1.474     -1.446       45      -0.990      -0.638
f_btc_rel_mom_24       0.06     -0.918     -0.968     -1.542     -1.446       45      -0.972      -0.638

============================================================================================================
BEST: f_st_flip  gate open 6% of bars
  TEST  gate-on : top-third +0.767%/trade  (gated market -1.446%)
  TEST  gate-off: top-third -1.184%/trade  (market -0.638%)
  TRAIN gate-on : top-third -1.207%/trade
============================================================================================================
  => FRAGILE: clears on TEST only; treat as unproven.

## Gate btc+breadth, ex-top-3 liquidity (structural narrowing)
       f_wc_mom_5       0.04     -1.396     -1.242     -0.846     -1.082       25      -1.252      -0.978
 f_btc_rel_mom_24       0.04     -1.078     -1.242     -1.006     -1.082       25      -1.215      -0.978
      f_hr_mom_24       0.04     -1.078     -1.242     -1.006     -1.082       25      -1.215      -0.978
   f_mst_ker_rank       0.04     -1.174     -1.242     -1.139     -1.082       25      -1.135      -0.978
      f_st_dist_2       0.04     -1.383     -1.242     -1.160     -1.082       25      -1.123      -0.978
        f_mst_ker       0.04     -1.056     -1.242     -1.185     -1.082       25      -1.029      -0.978
 f_st_ema200_dist       0.04     -1.323     -1.242     -1.199     -1.082       25      -1.197      -0.978
   f_btc_corr_168       0.04     -0.621     -1.242     -1.263     -1.082       25      -0.530      -0.978

============================================================================================================
BEST: f_mo_st_up  gate open 4% of bars
  TEST  gate-on : top-third +5.509%/trade  (gated market -1.728%)
  TEST  gate-off: top-third -1.588%/trade  (market -0.832%)
  TRAIN gate-on : top-third -1.268%/trade
============================================================================================================
  => FRAGILE: clears on TEST only; treat as unproven.

## Gate btc+funding, standard cost
       f_st_dist_3       0.38     -0.753     -0.633     -1.376     -1.355      276      -0.690      -0.361
        f_hr_mom_6       0.38     -0.943     -0.633     -1.397     -1.355      276      -0.862      -0.361
       f_hr_mom_24       0.38     -0.878     -0.633     -1.421     -1.355      276      -0.830      -0.361
  f_btc_rel_mom_24       0.38     -0.878     -0.633     -1.421     -1.355      276      -0.830      -0.361
        f_wc_mom_5       0.38     -1.018     -0.633     -1.438     -1.355      276      -0.947      -0.361
 f_hr_ema_fast_mid       0.38     -0.701     -0.633     -1.493     -1.355      276      -0.759      -0.361
       f_w1_mom_10       0.38     -0.790     -0.633     -1.520     -1.355      276      -0.412      -0.361

============================================================================================================
BEST: f_btc_corr_168  gate open 38% of bars
  TEST  gate-on : top-third -0.906%/trade  (gated market -1.355%)
  TEST  gate-off: top-third +0.064%/trade  (market -0.361%)
  TRAIN gate-on : top-third -0.151%/trade
============================================================================================================
  => NOT CLEARED with this gate/cost. Try a stricter gate, the achievable-cost
     scenario (--cost), or the coarser frame.

## Portfolio backtest, best single signal, btc+breadth, both costs
frame=1d  signal=f_w1_st_up  gate=btc+breadth  cost=0.2%  horizon=2 bars  OOS cut=2025-08-13 00:00:00

TRAIN every=1: blocks=585 deployed=46 return=-40.9% (ann -8.6%) maxDD=-58.6% | BTC buy&hold +1297.4% maxDD -76.4%
TRAIN every=2: blocks=293 deployed=24 return=-39.6% (ann -8.2%) maxDD=-47.8% | BTC buy&hold +1297.4% maxDD -75.9%
TRAIN every=3: blocks=195 deployed=14 return=+3.6% (ann +0.6%) maxDD=-25.9% | BTC buy&hold +1283.1% maxDD -75.7%

TEST every=1: blocks=99 deployed=6 return=+1.5% (ann +1.5%) maxDD=-15.6% | BTC buy&hold -46.2% maxDD -50.3%
TEST every=2: blocks=50 deployed=2 return=-10.8% (ann -10.9%) maxDD=-10.8% | BTC buy&hold -46.2% maxDD -49.4%
TEST every=3: blocks=33 deployed=1 return=+5.6% (ann +5.9%) maxDD=+0.0% | BTC buy&hold -46.0% maxDD -49.5%

frame=1d  signal=f_w1_st_up  gate=btc+breadth  cost=0.15%  horizon=2 bars  OOS cut=2025-08-13 00:00:00

TRAIN every=1: blocks=585 deployed=46 return=-39.5% (ann -8.2%) maxDD=-57.9% | BTC buy&hold +1297.4% maxDD -76.4%
TRAIN every=2: blocks=293 deployed=24 return=-38.8% (ann -8.0%) maxDD=-47.3% | BTC buy&hold +1297.4% maxDD -75.9%
TRAIN every=3: blocks=195 deployed=14 return=+4.3% (ann +0.7%) maxDD=-25.7% | BTC buy&hold +1283.1% maxDD -75.7%

TEST every=1: blocks=99 deployed=6 return=+1.8% (ann +1.9%) maxDD=-15.4% | BTC buy&hold -46.2% maxDD -50.3%
TEST every=2: blocks=50 deployed=2 return=-10.7% (ann -10.8%) maxDD=-10.7% | BTC buy&hold -46.2% maxDD -49.4%
TEST every=3: blocks=33 deployed=1 return=+5.7% (ann +6.0%) maxDD=+0.0% | BTC buy&hold -46.0% maxDD -49.5%

