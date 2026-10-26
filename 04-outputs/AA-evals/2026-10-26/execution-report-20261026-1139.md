# Execution report 2026-10-26 11:39 New York

Per-fill slippage vs the fill-minute VWAP (spread cost only; gaps and drift excluded). Modeled round trip: 5-10bp.

fills=25  mean slippage=+5.8bp  median=+6.1bp  worst=+20.2bp  notional=$43,380  cost=$+25.74

Limit-first test. limit arm all in: 6 fills, mean +5.6bp, median +2.7bp; of which limit fills: 4 fills, mean +0.9bp, median +0.4bp and market fallbacks: 2 fills, mean +14.8bp, median +14.8bp. Market arm: 19 fills, mean +5.9bp, median +7.1bp.


symbol side        fill  ref_vwap  slip_bp  notional fill_et  minutes_from_open      arm
   MRK sell  141.240000  141.5257     20.2   1661.39   11:13                103   market
   CNC sell   68.370000   68.5018     19.2   1880.87   11:13                103   market
  DOCN  buy  100.480000  100.3118     16.8   1661.05   11:15                105 fallback
   NUE sell  258.120000  258.4972     14.6   1829.43   11:13                103   market
   ATI  buy  164.160000  163.9337     13.8   1661.05   11:13                103   market
   ARM  buy  222.910000  222.6248     12.8   1661.05   11:15                105 fallback
   TGT sell  150.340000  150.5174     11.8   1741.56   11:13                103   market
  TRGP sell  304.110000  304.4550     11.3   1912.23   11:13                103   market
  KEYS sell  325.690000  326.0373     10.7   1876.57   11:13                103   market
    SN  buy  199.160000  198.9725      9.4   1661.05   11:13                103   market
  AAOI  buy   71.310000   71.2558      7.6   1661.05   11:13                103   market
  TTMI  buy   87.052139   86.9900      7.1   1661.05   11:13                103   market
   UMC sell   19.150000   19.1617      6.1   1852.95   11:13                103   market
  SMTC  buy  137.990000  137.9176      5.2   1661.05   11:13                103   market
   APA sell   51.440000   51.4615      4.2   1898.98   11:13                103    limit
   FIX  buy 1249.712000 1249.4343      2.2   1661.05   11:13                103   market
    SU sell   79.180000   79.1886      1.1   1843.88   11:13                103    limit
  AMAT  buy  387.982701  387.9787      0.1   1661.05   11:13                103   market
  LRCX  buy  239.240000  239.2506     -0.4   1661.05   11:13                103    limit
   TXG  buy   74.230000   74.2377     -1.0   1661.05   11:13                103   market
  TSEM  buy  178.850000  178.8715     -1.2   1661.05   11:13                103    limit
  PANW sell  388.204078  388.1451     -1.5   1966.79   11:13                103   market
  NBIS  buy  162.500000  162.5545     -3.4   1661.05   11:13                103   market
  ROIV  buy   36.340000   36.3605     -5.6   1661.05   11:13                103   market
   PBF  buy   81.140000   81.2622    -15.0   1661.05   11:13                103   market
