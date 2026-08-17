# Edge matrix, 4h frame, 2026-08-16

## Gate btc+breadth, standard cost, composite on
loading dataset_4h_allmarket.parquet ...
frame=4h (4h bars)  OOS cut=2025-06-21 20:00:00  gate=btc+breadth (btc col f_btc_mom_168)  cost=0.2%  min_rows=800  candidates=4

============================================================================================================
REGIME-GATED CROSS-SECTIONAL EDGE, 4h frame, gate=btc+breadth, after 0.20% cost. Deciding cell: te_on_top.
============================================================================================================
       signal  gate_open  tr_on_top  tr_on_mkt  te_on_top  te_on_mkt  te_on_n  te_off_top  te_off_mkt
   f_d1_st_up       0.24     -0.289      -0.34     -0.097       -0.5      795      -0.155      -0.345
    f_mst_dir       0.24     -0.492      -0.34     -0.301       -0.5      729      -0.327      -0.345
f_x_composite       0.24     -0.368      -0.34     -0.397       -0.5     1520      -0.287      -0.345
  f_st_dist_2       0.24     -0.288      -0.34     -0.494       -0.5     1504      -0.322      -0.345

============================================================================================================
BEST: f_d1_st_up  gate open 24% of bars
  TEST  gate-on : top-third -0.097%/trade  (gated market -0.500%)
  TEST  gate-off: top-third -0.155%/trade  (market -0.345%)
  TRAIN gate-on : top-third -0.289%/trade
============================================================================================================
  => NOT CLEARED with this gate/cost. Try a stricter gate, the achievable-cost
     scenario (--cost), or the coarser frame.

## Gate btc+funding, standard cost
    p = load_payments(base)
        ^^^^^^^^^^^^^^^^^^^
  File "/Volumes/PortableSSD/Github/day-trader/inputs/funding_features.py", line 52, in load_payments
    raw = pd.concat(frames, ignore_index=True)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Volumes/PortableSSD/Github/day-trader/.venv/lib/python3.12/site-packages/pandas/core/reshape/concat.py", line 382, in concat
    op = _Concatenator(
         ^^^^^^^^^^^^^^
  File "/Volumes/PortableSSD/Github/day-trader/.venv/lib/python3.12/site-packages/pandas/core/reshape/concat.py", line 445, in __init__
    objs, keys = self._clean_keys_and_objs(objs, keys)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Volumes/PortableSSD/Github/day-trader/.venv/lib/python3.12/site-packages/pandas/core/reshape/concat.py", line 507, in _clean_keys_and_objs
    raise ValueError("No objects to concatenate")
ValueError: No objects to concatenate

## Gate btc+breadth, achievable cost 0.15%
============================================================================================================
REGIME-GATED CROSS-SECTIONAL EDGE, 4h frame, gate=btc+breadth, after 0.15% cost. Deciding cell: te_on_top.
============================================================================================================
    signal  gate_open  tr_on_top  tr_on_mkt  te_on_top  te_on_mkt  te_on_n  te_off_top  te_off_mkt
f_d1_st_up       0.24     -0.239      -0.29     -0.047      -0.45      795      -0.105      -0.295

============================================================================================================
BEST: f_d1_st_up  gate open 24% of bars
  TEST  gate-on : top-third -0.047%/trade  (gated market -0.450%)
  TEST  gate-off: top-third -0.105%/trade  (market -0.295%)
  TRAIN gate-on : top-third -0.239%/trade
============================================================================================================
  => NOT CLEARED with this gate/cost. Try a stricter gate, the achievable-cost
     scenario (--cost), or the coarser frame.

## Portfolio backtest, gate btc+breadth, composite, standard cost
loading dataset_4h_allmarket.parquet ...
frame=4h  signal=f_x_composite  gate=btc+breadth  cost=0.2%  horizon=12 bars  OOS cut=2025-06-21 20:00:00

TRAIN every=1: blocks=646 deployed=288 return=-45.4% (ann -9.1%) maxDD=-58.8% | BTC buy&hold +2592.9% maxDD -76.6%
TRAIN every=2: blocks=323 deployed=143 return=-21.6% (ann -3.8%) maxDD=-45.2% | BTC buy&hold +2641.8% maxDD -75.3%
TRAIN every=3: blocks=216 deployed=97 return=+10.7% (ann +1.6%) maxDD=-34.7% | BTC buy&hold +2592.9% maxDD -75.0%

TEST every=1: blocks=142 deployed=34 return=+3.9% (ann +4.0%) maxDD=-15.7% | BTC buy&hold -38.3% maxDD -51.5%
TEST every=2: blocks=71 deployed=15 return=+3.9% (ann +4.0%) maxDD=-6.6% | BTC buy&hold -35.8% maxDD -50.1%
TEST every=3: blocks=48 deployed=11 return=+1.1% (ann +1.1%) maxDD=-4.9% | BTC buy&hold -38.3% maxDD -49.9%

