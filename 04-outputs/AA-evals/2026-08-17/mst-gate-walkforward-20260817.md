=== 1d run Mon 17 Aug 2026 22:40:16 UTC
frame=1d  signal=f_mst_dir  cost=0.15%  btc col=f_btc_mom_24  breadth col=f_w1_st_up  OOS cut=2025-07-26 00:00:00

PANEL A  half-year walk-forward, gate = btc-up AND breadth>0.5
  fold  open_rate  n_top    net    mkt
2019H2       0.00      0    NaN    NaN
2020H1       0.19      0    NaN -6.870
2020H2       0.75     14  0.170  2.119
2021H1       0.74     12  1.322  5.329
2021H2       0.05     28 -2.469 -2.010
2022H1       0.04     18 -4.707 -5.674
2022H2       0.00      0    NaN    NaN
2023H1       0.39    129 -1.580 -3.117
2023H2       0.74     34  2.602  1.135
2024H1       0.65    116 -5.540 -2.260
2024H2       0.29     42 -3.539 -2.694
2025H1       0.21      3  6.509 -7.458
2025H2       0.07      8 -4.996 -4.280
2026H1       0.01      7  5.795  2.014
eligible folds (n_top>=8): 9  positive: 3  pass rate: 33%  (K1 kills below 60%)

PANEL B  gate width vs edge (all-history and OOS-year gate-on top-third net %/trade)
btc  breadth_min  open_rate  n_top  net_all  n_oos  net_oos
 on          0.3       0.41    872   -1.824     30   -1.828
 on          0.4       0.34    614   -2.194     21    0.706
 on          0.5       0.29    411   -2.487     15    0.040
 on          0.6       0.26    272   -2.446      4   -2.802
off          0.3       0.66   2003   -3.035     95   -3.294
off          0.4       0.55   1578   -3.376     80   -2.684
off          0.5       0.43   1053   -3.336     56   -3.843
off          0.6       0.37    758   -3.443     32   -4.984
tradeable widths (open>=10%): 8  with positive all-history edge: 0  (K2 kills at zero)

PANEL C  attribution, incumbent gate, all history: 119 coins, 26 positive; top-5 carry +283.8pp of -1022.1pp
              n  mean_net  total_net
symbol                              
ADA/USDT     13     6.805     88.463
SOL/USDT      9     5.816     52.345
ATOM/USDT     7     7.178     50.249
LINK/USDT    10     4.746     47.463
PEOPLE/USDT   4    11.319     45.276
ENS/USDT      2    20.024     40.047
OGN/USDT      1    35.308     35.308
SXP/USDT      4     7.500     30.001

==========================================================================================
VERDICT: KILLED on 1d (K1: fold pass rate 33% < 60%; K2: no tradeable gate width with positive all-history edge). Journal as a closed artifact.
==========================================================================================

=== 4h run Mon 17 Aug 2026 22:40:40 UTC
frame=4h  signal=f_mst_dir  cost=0.15%  btc col=f_btc_mom_168  breadth col=f_d1_st_up  OOS cut=2025-06-21 20:00:00

PANEL A  half-year walk-forward, gate = btc-up AND breadth>0.5
  fold  open_rate  n_top    net    mkt
2019H1       1.00     58  0.084  0.256
2019H2       0.35     13 -0.023 -0.821
2020H1       0.58     89 -0.176 -0.163
2020H2       0.72    304 -0.101  0.226
2021H1       0.53    489  0.064  0.267
2021H2       0.48    669  0.007 -0.067
2022H1       0.18    269 -2.468 -1.268
2022H2       0.28    195 -2.124 -0.253
2023H1       0.57    638 -0.465 -0.296
2023H2       0.77    821  0.513  0.065
2024H1       0.44   1345 -0.622 -0.686
2024H2       0.57   1351 -0.613 -0.486
2025H1       0.23    235 -1.019 -0.239
2025H2       0.21    282 -0.339 -0.423
2026H1       0.30    447 -0.196 -0.492
eligible folds (n_top>=8): 15  positive: 4  pass rate: 27%  (K1 kills below 60%)

PANEL B  gate width vs edge (all-history and OOS-year gate-on top-third net %/trade)
btc  breadth_min  open_rate  n_top  net_all  n_oos  net_oos
 on          0.3       0.49   9049   -0.376   1074   -0.352
 on          0.4       0.45   8214   -0.361    919   -0.161
 on          0.5       0.41   7205   -0.423    729   -0.251
 on          0.6       0.37   6008   -0.519    639   -0.391
off          0.3       0.61  12894   -0.420   2173   -0.143
off          0.4       0.53  10844   -0.413   1899   -0.020
off          0.5       0.47   9006   -0.433   1539   -0.133
off          0.6       0.41   7243   -0.507   1189   -0.215
tradeable widths (open>=10%): 8  with positive all-history edge: 0  (K2 kills at zero)

PANEL C  attribution, incumbent gate, all history: 197 coins, 54 positive; top-5 carry +356.6pp of -3047.8pp
              n  mean_net  total_net
symbol                              
DOGE/USDT   301     0.562    169.076
NEAR/USDT    88     0.785     69.065
EOS/USDT     84     0.501     42.077
THETA/USDT   27     1.415     38.214
ONDO/USDT     7     5.446     38.122
COMP/USDT     7     4.817     33.721
GRT/USDT     25     1.286     32.158
SXP/USDT     14     2.265     31.704

==========================================================================================
VERDICT: KILLED on 4h (K1: fold pass rate 27% < 60%; K2: no tradeable gate width with positive all-history edge). Journal as a closed artifact.
==========================================================================================
=== DONE Mon 17 Aug 2026 22:43:07 UTC
