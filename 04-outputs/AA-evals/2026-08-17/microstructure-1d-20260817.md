# Microstructure features on the 1d frame, 2026-08-17

Build: swept label (+3/-1 ATR, 20 daily bars), f_ms_ block from each coin's 1h archive.
wrote /Volumes/PortableSSD/Github/day-trader/inputs/binance-data/dataset_1d_allmarket.parquet: rows=520245 coins=540 features=104 base=0.218
f_ms_ coverage: {'f_ms_flow_imb': 0.964, 'f_ms_vol_updown': 0.964, 'f_ms_hhi': 0.964, 'f_ms_close_pos': 0.964, 'f_ms_rv_range': 0.964, 'f_ms_gap_n': 0.964, 'f_ms_gap_signed': 0.964, 'f_ms_flow_imb_7d': 0.964}

## Gate btc+breadth, cost 0.15, f_ms_ candidates vs f_mst_dir incumbent
frame=1d (24h bars)  OOS cut=2025-07-26 00:00:00  gate=btc+breadth (btc col f_btc_mom_24)  cost=0.15%  min_rows=150  candidates=8

============================================================================================================
REGIME-GATED CROSS-SECTIONAL EDGE, 1d frame, gate=btc+breadth, after 0.15% cost. Deciding cell: te_on_top.
============================================================================================================
          signal  gate_open  tr_on_top  tr_on_mkt  te_on_top  te_on_mkt  te_on_n  te_off_top  te_off_mkt
       f_mst_dir       0.06     -2.583     -0.956      0.040     -3.962       15      -2.834      -1.746
 f_ms_gap_signed       0.06     -1.159     -1.031     -1.867     -4.051       36      -2.683      -1.864
   f_ms_rv_range       0.06     -1.184     -1.031     -2.722     -4.051       40      -1.776      -1.864
  f_ms_close_pos       0.06     -1.043     -1.031     -3.439     -4.051       40      -1.581      -1.864
        f_ms_hhi       0.06     -1.158     -1.031     -3.641     -4.051       40      -2.435      -1.864
f_ms_flow_imb_7d       0.06     -0.820     -1.031     -3.936     -4.051       40      -1.684      -1.864
 f_ms_vol_updown       0.06     -0.878     -1.031     -4.333     -4.051       40      -1.790      -1.864
   f_ms_flow_imb       0.06     -0.462     -1.031     -4.366     -4.051       40      -1.597      -1.864

============================================================================================================
BEST: f_mst_dir  gate open 6% of bars
  TEST  gate-on : top-third +0.040%/trade  (gated market -3.962%)
  TEST  gate-off: top-third -2.834%/trade  (market -1.746%)
  TRAIN gate-on : top-third -2.583%/trade
============================================================================================================
  => FRAGILE: clears on TEST only; treat as unproven.
## Gate btc+funding, cost 0.15, f_ms_ candidates vs f_mst_dir incumbent
frame=1d (24h bars)  OOS cut=2025-07-26 00:00:00  gate=btc+funding (btc col f_btc_mom_24)  cost=0.15%  min_rows=150  candidates=8

============================================================================================================
REGIME-GATED CROSS-SECTIONAL EDGE, 1d frame, gate=btc+funding, after 0.15% cost. Deciding cell: te_on_top.
============================================================================================================
          signal  gate_open  tr_on_top  tr_on_mkt  te_on_top  te_on_mkt  te_on_n  te_off_top  te_off_mkt
   f_ms_rv_range       0.39     -0.043     -0.254     -2.212     -2.968      264      -1.588      -1.370
  f_ms_close_pos       0.39      0.027     -0.254     -2.504     -2.968      264      -1.171      -1.370
       f_mst_dir       0.40     -0.396     -0.252     -2.623     -2.630      173      -2.801      -1.386
 f_ms_vol_updown       0.39     -0.625     -0.254     -2.770     -2.968      264      -1.411      -1.370
f_ms_flow_imb_7d       0.39     -0.256     -0.254     -2.819     -2.968      264      -1.176      -1.370
        f_ms_hhi       0.39     -0.605     -0.254     -2.980     -2.968      264      -2.203      -1.370
 f_ms_gap_signed       0.39     -0.531     -0.254     -3.041     -2.968      199      -2.317      -1.370
   f_ms_flow_imb       0.39     -0.281     -0.254     -3.292     -2.968      264      -0.782      -1.370

============================================================================================================
BEST: f_ms_rv_range  gate open 39% of bars
  TEST  gate-on : top-third -2.212%/trade  (gated market -2.968%)
  TEST  gate-off: top-third -1.588%/trade  (market -1.370%)
  TRAIN gate-on : top-third -0.043%/trade
============================================================================================================
  => NOT CLEARED with this gate/cost. Try a stricter gate, the achievable-cost
     scenario (--cost), or the coarser frame.
## Gate none, cost 0.15, f_ms_ candidates vs f_mst_dir incumbent
frame=1d (24h bars)  OOS cut=2025-07-26 00:00:00  gate=none (btc col f_btc_mom_24)  cost=0.15%  min_rows=150  candidates=8

============================================================================================================
REGIME-GATED CROSS-SECTIONAL EDGE, 1d frame, gate=none, after 0.15% cost. Deciding cell: te_on_top.
============================================================================================================
          signal  gate_open  tr_on_top  tr_on_mkt  te_on_top  te_on_mkt  te_on_n  te_off_top  te_off_mkt
  f_ms_close_pos        1.0     -0.391     -0.536     -1.691     -1.992      677         NaN         NaN
   f_ms_flow_imb        1.0     -0.551     -0.536     -1.761     -1.992      677         NaN         NaN
f_ms_flow_imb_7d        1.0     -0.491     -0.536     -1.817     -1.992      677         NaN         NaN
   f_ms_rv_range        1.0     -0.546     -0.536     -1.832     -1.992      677         NaN         NaN
 f_ms_vol_updown        1.0     -0.555     -0.536     -1.941     -1.992      677         NaN         NaN
        f_ms_hhi        1.0     -0.863     -0.536     -2.506     -1.992      677         NaN         NaN
 f_ms_gap_signed        1.0     -0.475     -0.536     -2.621     -1.992      473         NaN         NaN
       f_mst_dir        1.0     -1.290     -0.546     -2.718     -1.879      371         NaN         NaN

============================================================================================================
BEST: f_ms_close_pos  gate open 100% of bars
  TEST  gate-on : top-third -1.691%/trade  (gated market -1.992%)
  TEST  gate-off: top-third +nan%/trade  (market +nan%)
  TRAIN gate-on : top-third -0.391%/trade
============================================================================================================
  => NOT CLEARED with this gate/cost. Try a stricter gate, the achievable-cost
     scenario (--cost), or the coarser frame.
=== DONE Mon 17 Aug 2026 21:57:32 UTC
