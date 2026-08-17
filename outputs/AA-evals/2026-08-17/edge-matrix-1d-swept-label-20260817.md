=== REBUILD 1d on swept label +3/-1 ATR 20b Mon 17 Aug 2026 21:41:49 UTC
label: {'tgt_atr': 3.0, 'stp_atr': 1.0, 'horizon_bars': 20, 'atr_len': 14}
  skip AAOIBUSDT: only 33 bars (<80)
  skip AAPLBUSDT: only 19 bars (<80)
  skip AEROUSDT: only 31 bars (<80)
  skip AMATBUSDT: only 19 bars (<80)
  skip AMDBUSDT: only 55 bars (<80)
  skip AMZNBUSDT: only 19 bars (<80)
  skip ARMBUSDT: only 33 bars (<80)
  skip AVGOBUSDT: only 33 bars (<80)
  skip AXTIBUSDT: only 26 bars (<80)
  skip BABABUSDT: only 33 bars (<80)
  skip BCCUSDT: data quality (gap_ratio 0.011, max gap 120h)
  skip BEBUSDT: only 19 bars (<80)
  skip BKRWUSDT: only 33 bars (<80)
  skip BNXUSDT: data quality (gap_ratio 0.004, max gap 144h)
  skip BTCSTUSDT: data quality (gap_ratio 0.004, max gap 96h)
  skip CBRSBUSDT: only 41 bars (<80)
  skip COCOSUSDT: data quality (gap_ratio 0.002, max gap 96h)
  skip COINBUSDT: only 41 bars (<80)
  skip CRCLBUSDT: only 67 bars (<80)
  skip CRWVBUSDT: only 26 bars (<80)
  skip CVCUSDT: data quality (gap_ratio 0.060, max gap 3696h)
  skip DAIUSDT: only 21 bars (<80)
  skip DELLBUSDT: only 19 bars (<80)
  skip DRAMBUSDT: only 41 bars (<80)
  skip DREPUSDT: data quality (gap_ratio 0.002, max gap 96h)
  skip EWYBUSDT: only 55 bars (<80)
  skip FLNCBUSDT: only 19 bars (<80)
  skip FTTUSDT: data quality (gap_ratio 0.127, max gap 7464h)
  skip GLWBUSDT: only 41 bars (<80)
  skip GOOGLBUSDT: only 41 bars (<80)
  skip GRAMUSDT: only 46 bars (<80)
  skip GSBUSDT: only 19 bars (<80)
  skip HOODBUSDT: only 33 bars (<80)
  skip IBMBUSDT: only 33 bars (<80)
  skip INTCBUSDT: only 55 bars (<80)
  skip INTWBUSDT: only 26 bars (<80)
  skip KEYUSDT: data quality (gap_ratio 0.014, max gap 672h)
  skip KORUBUSDT: only 26 bars (<80)
  skip LITEBUSDT: only 48 bars (<80)
  skip LUNAUSDT: data quality (gap_ratio 0.008, max gap 432h)
  skip METABUSDT: only 48 bars (<80)
  skip MRVLBUSDT: only 33 bars (<80)
  skip MSFTBUSDT: only 48 bars (<80)
  skip MSTRBUSDT: only 55 bars (<80)
  skip MUBUSDT: only 67 bars (<80)
  skip MUUBUSDT: only 26 bars (<80)
  skip MVLLBUSDT: only 26 bars (<80)
  skip NBISBUSDT: only 41 bars (<80)
  skip NBTUSDT: data quality (gap_ratio 0.054, max gap 480h)
  skip NOKBUSDT: only 33 bars (<80)
  skip NVDABUSDT: only 67 bars (<80)
  skip ORCLBUSDT: only 26 bars (<80)
  skip PLTRBUSDT: only 48 bars (<80)
  skip PYPLBUSDT: only 19 bars (<80)
  skip QCOMBUSDT: only 41 bars (<80)
  skip QNTBUSDT: only 26 bars (<80)
  skip QQQBUSDT: only 48 bars (<80)
  skip QUICKUSDT: data quality (gap_ratio 0.002, max gap 96h)
  skip REUSDT: only 60 bars (<80)
  skip RKLBBUSDT: only 33 bars (<80)
  skip SKHYBUSDT: only 35 bars (<80)
  skip SMHBUSDT: only 19 bars (<80)
  skip SNDKBUSDT: only 67 bars (<80)
  skip SNXXBUSDT: only 26 bars (<80)
  skip SOXLBUSDT: only 41 bars (<80)
  skip SOXSBUSDT: only 19 bars (<80)
  skip SPCXBUSDT: only 66 bars (<80)
  skip SPYBUSDT: only 41 bars (<80)
  skip STRAXUSDT: data quality (gap_ratio 0.003, max gap 192h)
  skip SUNUSDT: data quality (gap_ratio 0.001, max gap 96h)
  skip TQQQBUSDT: only 26 bars (<80)
  skip TSLABUSDT: only 67 bars (<80)
  skip TSMBUSDT: only 33 bars (<80)
  skip TUSDUSDT: data quality (gap_ratio 0.055, max gap 3984h)
  skip USDCUSDT: data quality (gap_ratio 0.059, max gap 3984h)
  skip USDPUSDT: data quality (gap_ratio 0.092, max gap 3984h)
  skip USDSUSDT: data quality (gap_ratio 0.771, max gap 50760h)
  skip VENUSDT: only 33 bars (<80)
  skip VIDTUSDT: data quality (gap_ratio 0.006, max gap 216h)
  skip WDCBUSDT: only 41 bars (<80)
wrote /Volumes/PortableSSD/Github/day-trader/inputs/binance-data/dataset_1d_allmarket.parquet: rows=533624 coins=551 features=96 base=0.216
=== EDGE MATRIX 1d (swept label) Mon 17 Aug 2026 21:44:00 UTC
## Gate btc+breadth, cost 0.20
loading dataset_1d_allmarket.parquet ...
frame=1d (24h bars)  OOS cut=2025-07-26 00:00:00  gate=btc+breadth (btc col f_btc_mom_24)  cost=0.2%  min_rows=150  candidates=49

============================================================================================================
REGIME-GATED CROSS-SECTIONAL EDGE, 1d frame, gate=btc+breadth, after 0.20% cost. Deciding cell: te_on_top.
============================================================================================================
              signal  gate_open  tr_on_top  tr_on_mkt  te_on_top  te_on_mkt  te_on_n  te_off_top  te_off_mkt
           f_mst_dir       0.07     -2.688     -0.995      1.321     -3.583       13      -3.131      -1.707
           f_st_flip       0.07     -0.468     -0.995     -1.171     -3.583       26      -2.928      -1.707
            f_mo_rsi       0.06     -0.792     -0.972     -1.387     -3.241       43      -1.022      -1.427
         f_wc_mom_20       0.07     -0.819     -0.995     -1.449     -3.583       56      -1.602      -1.707
            f_wc_rsi       0.07     -0.955     -0.995     -1.727     -3.583       56      -1.853      -1.707
        f_ta_pta_cmo       0.07     -0.955     -0.995     -1.727     -3.583       56      -1.853      -1.707
            f_hr_rsi       0.07     -0.955     -0.995     -1.727     -3.583       56      -1.853      -1.707
          f_hr_mom_6       0.07     -1.196     -0.995     -1.970     -3.583       56      -1.595      -1.707
    f_btc_rel_mom_24       0.07     -0.967     -0.995     -1.982     -3.583       56      -1.957      -1.707
         f_hr_mom_24       0.07     -0.967     -0.995     -1.982     -3.583       56      -1.957      -1.707
         f_wc_mom_10       0.07     -1.006     -0.995     -2.052     -3.583       56      -2.018      -1.707
          f_wc_mom_5       0.07     -1.311     -0.995     -2.061     -3.583       56      -1.540      -1.707
          f_st_agree       0.07     -0.788     -0.995     -2.203     -3.583       57      -2.279      -1.707
           f_mst_ker       0.07     -1.026     -0.995     -2.226     -3.583       56      -1.708      -1.707
         f_mo_mom_10       0.06     -0.851     -0.972     -2.239     -3.241       43      -1.198      -1.427
         f_hr_mom_12       0.07     -0.897     -0.995     -2.436     -3.583       56      -1.887      -1.707
      f_mst_ker_rank       0.07     -1.134     -0.995     -2.447     -3.583       56      -1.694      -1.707
          f_mst_flip       0.07     -3.339     -0.995     -2.479     -3.583        5      -3.258      -1.707
        f_st_uptrend       0.07     -0.354     -0.995     -2.514     -3.583       55      -3.340      -1.707
f_ta_pta_vortex_diff       0.07     -0.686     -0.995     -2.586     -3.583       56      -1.615      -1.707

============================================================================================================
BEST: f_mst_dir  gate open 7% of bars
  TEST  gate-on : top-third +1.321%/trade  (gated market -3.583%)
  TEST  gate-off: top-third -3.131%/trade  (market -1.707%)
  TRAIN gate-on : top-third -2.688%/trade
============================================================================================================
  => FRAGILE: clears on TEST only; treat as unproven.
## Gate btc+breadth, cost 0.15
loading dataset_1d_allmarket.parquet ...
frame=1d (24h bars)  OOS cut=2025-07-26 00:00:00  gate=btc+breadth (btc col f_btc_mom_24)  cost=0.15%  min_rows=150  candidates=49

============================================================================================================
REGIME-GATED CROSS-SECTIONAL EDGE, 1d frame, gate=btc+breadth, after 0.15% cost. Deciding cell: te_on_top.
============================================================================================================
              signal  gate_open  tr_on_top  tr_on_mkt  te_on_top  te_on_mkt  te_on_n  te_off_top  te_off_mkt
           f_mst_dir       0.07     -2.638     -0.945      1.371     -3.533       13      -3.081      -1.657
           f_st_flip       0.07     -0.418     -0.945     -1.121     -3.533       26      -2.878      -1.657
            f_mo_rsi       0.06     -0.742     -0.922     -1.337     -3.191       43      -0.972      -1.377
         f_wc_mom_20       0.07     -0.769     -0.945     -1.399     -3.533       56      -1.552      -1.657
            f_wc_rsi       0.07     -0.905     -0.945     -1.677     -3.533       56      -1.803      -1.657
        f_ta_pta_cmo       0.07     -0.905     -0.945     -1.677     -3.533       56      -1.803      -1.657
            f_hr_rsi       0.07     -0.905     -0.945     -1.677     -3.533       56      -1.803      -1.657
          f_hr_mom_6       0.07     -1.146     -0.945     -1.920     -3.533       56      -1.545      -1.657
    f_btc_rel_mom_24       0.07     -0.917     -0.945     -1.932     -3.533       56      -1.907      -1.657
         f_hr_mom_24       0.07     -0.917     -0.945     -1.932     -3.533       56      -1.907      -1.657
         f_wc_mom_10       0.07     -0.956     -0.945     -2.002     -3.533       56      -1.968      -1.657
          f_wc_mom_5       0.07     -1.261     -0.945     -2.011     -3.533       56      -1.490      -1.657
          f_st_agree       0.07     -0.738     -0.945     -2.153     -3.533       57      -2.229      -1.657
           f_mst_ker       0.07     -0.976     -0.945     -2.176     -3.533       56      -1.658      -1.657
         f_mo_mom_10       0.06     -0.801     -0.922     -2.189     -3.191       43      -1.148      -1.377
         f_hr_mom_12       0.07     -0.847     -0.945     -2.386     -3.533       56      -1.837      -1.657
      f_mst_ker_rank       0.07     -1.084     -0.945     -2.397     -3.533       56      -1.644      -1.657
          f_mst_flip       0.07     -3.289     -0.945     -2.429     -3.533        5      -3.208      -1.657
        f_st_uptrend       0.07     -0.304     -0.945     -2.464     -3.533       55      -3.290      -1.657
f_ta_pta_vortex_diff       0.07     -0.636     -0.945     -2.536     -3.533       56      -1.565      -1.657

============================================================================================================
BEST: f_mst_dir  gate open 7% of bars
  TEST  gate-on : top-third +1.371%/trade  (gated market -3.533%)
  TEST  gate-off: top-third -3.081%/trade  (market -1.657%)
  TRAIN gate-on : top-third -2.638%/trade
============================================================================================================
  => FRAGILE: clears on TEST only; treat as unproven.
## Gate btc+funding, cost 0.20
loading dataset_1d_allmarket.parquet ...
frame=1d (24h bars)  OOS cut=2025-07-26 00:00:00  gate=btc+funding (btc col f_btc_mom_24)  cost=0.2%  min_rows=150  candidates=49

============================================================================================================
REGIME-GATED CROSS-SECTIONAL EDGE, 1d frame, gate=btc+funding, after 0.20% cost. Deciding cell: te_on_top.
============================================================================================================
              signal  gate_open  tr_on_top  tr_on_mkt  te_on_top  te_on_mkt  te_on_n  te_off_top  te_off_mkt
          f_mo_st_up       0.38     -0.623     -0.277     -1.260     -2.347       89      -1.378      -1.046
            f_mo_rsi       0.38     -0.359     -0.277     -1.654     -2.347      263      -0.671      -1.046
            f_w1_rsi       0.40     -0.694     -0.295     -1.785     -2.531      320      -1.660      -1.377
       f_x_composite       0.40     -1.213     -0.295     -2.031     -2.531      319      -2.323      -1.377
         f_mo_mom_10       0.38     -0.681     -0.277     -2.034     -2.347      263      -0.790      -1.046
      f_ta_aroon_osc       0.40     -0.997     -0.295     -2.077     -2.531      333      -1.694      -1.377
f_ta_pta_vortex_diff       0.40     -0.875     -0.295     -2.121     -2.531      320      -1.388      -1.377
          f_wc_mom_5       0.40     -1.290     -0.295     -2.156     -2.531      320      -1.186      -1.377
    f_st_ema200_dist       0.40     -1.169     -0.295     -2.165     -2.531      320      -1.823      -1.377
          f_hr_mom_6       0.40     -1.174     -0.295     -2.165     -2.531      320      -1.254      -1.377
         f_st_dist_2       0.40     -1.010     -0.295     -2.210     -2.531      320      -1.231      -1.377
            f_wc_rsi       0.40     -0.969     -0.295     -2.236     -2.531      320      -1.580      -1.377
            f_hr_rsi       0.40     -0.969     -0.295     -2.236     -2.531      320      -1.580      -1.377
        f_ta_pta_cmo       0.40     -0.969     -0.295     -2.236     -2.531      320      -1.580      -1.377
  f_w1_ema_fast_slow       0.40     -0.681     -0.295     -2.237     -2.531      320      -1.473      -1.377
          f_st_agree       0.40     -0.597     -0.295     -2.260     -2.531      330      -2.284      -1.377
        f_hr_mom_168       0.40     -1.139     -0.295     -2.262     -2.531      320      -1.594      -1.377
   f_btc_rel_mom_168       0.40     -1.139     -0.295     -2.262     -2.531      320      -1.594      -1.377
           f_mst_ker       0.40     -1.082     -0.295     -2.358     -2.531      320      -1.330      -1.377
         f_st_dist_3       0.40     -0.625     -0.295     -2.368     -2.531      320      -1.081      -1.377

============================================================================================================
BEST: f_mo_st_up  gate open 38% of bars
  TEST  gate-on : top-third -1.260%/trade  (gated market -2.347%)
  TEST  gate-off: top-third -1.378%/trade  (market -1.046%)
  TRAIN gate-on : top-third -0.623%/trade
============================================================================================================
  => NOT CLEARED with this gate/cost. Try a stricter gate, the achievable-cost
     scenario (--cost), or the coarser frame.
## Gate btc+funding, cost 0.15
loading dataset_1d_allmarket.parquet ...
frame=1d (24h bars)  OOS cut=2025-07-26 00:00:00  gate=btc+funding (btc col f_btc_mom_24)  cost=0.15%  min_rows=150  candidates=49

============================================================================================================
REGIME-GATED CROSS-SECTIONAL EDGE, 1d frame, gate=btc+funding, after 0.15% cost. Deciding cell: te_on_top.
============================================================================================================
              signal  gate_open  tr_on_top  tr_on_mkt  te_on_top  te_on_mkt  te_on_n  te_off_top  te_off_mkt
          f_mo_st_up       0.38     -0.573     -0.227     -1.210     -2.297       89      -1.328      -0.996
            f_mo_rsi       0.38     -0.309     -0.227     -1.604     -2.297      263      -0.621      -0.996
            f_w1_rsi       0.40     -0.644     -0.245     -1.735     -2.481      320      -1.610      -1.327
       f_x_composite       0.40     -1.163     -0.245     -1.981     -2.481      319      -2.273      -1.327
         f_mo_mom_10       0.38     -0.631     -0.227     -1.984     -2.297      263      -0.740      -0.996
      f_ta_aroon_osc       0.40     -0.947     -0.245     -2.027     -2.481      333      -1.644      -1.327
f_ta_pta_vortex_diff       0.40     -0.825     -0.245     -2.071     -2.481      320      -1.338      -1.327
          f_wc_mom_5       0.40     -1.240     -0.245     -2.106     -2.481      320      -1.136      -1.327
    f_st_ema200_dist       0.40     -1.119     -0.245     -2.115     -2.481      320      -1.773      -1.327
          f_hr_mom_6       0.40     -1.124     -0.245     -2.115     -2.481      320      -1.204      -1.327
         f_st_dist_2       0.40     -0.960     -0.245     -2.160     -2.481      320      -1.181      -1.327
            f_wc_rsi       0.40     -0.919     -0.245     -2.186     -2.481      320      -1.530      -1.327
            f_hr_rsi       0.40     -0.919     -0.245     -2.186     -2.481      320      -1.530      -1.327
        f_ta_pta_cmo       0.40     -0.919     -0.245     -2.186     -2.481      320      -1.530      -1.327
  f_w1_ema_fast_slow       0.40     -0.631     -0.245     -2.187     -2.481      320      -1.423      -1.327
          f_st_agree       0.40     -0.547     -0.245     -2.210     -2.481      330      -2.234      -1.327
        f_hr_mom_168       0.40     -1.089     -0.245     -2.212     -2.481      320      -1.544      -1.327
   f_btc_rel_mom_168       0.40     -1.089     -0.245     -2.212     -2.481      320      -1.544      -1.327
           f_mst_ker       0.40     -1.032     -0.245     -2.308     -2.481      320      -1.280      -1.327
         f_st_dist_3       0.40     -0.575     -0.245     -2.318     -2.481      320      -1.031      -1.327

============================================================================================================
BEST: f_mo_st_up  gate open 38% of bars
  TEST  gate-on : top-third -1.210%/trade  (gated market -2.297%)
  TEST  gate-off: top-third -1.328%/trade  (market -0.996%)
  TRAIN gate-on : top-third -0.573%/trade
============================================================================================================
  => NOT CLEARED with this gate/cost. Try a stricter gate, the achievable-cost
     scenario (--cost), or the coarser frame.
=== DONE Mon 17 Aug 2026 21:46:19 UTC
