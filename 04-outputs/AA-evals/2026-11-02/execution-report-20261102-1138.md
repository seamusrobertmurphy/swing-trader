# Execution report 2026-11-02 11:38 New York

Per-fill slippage vs the fill-minute VWAP (spread cost only; gaps and drift excluded). Modeled round trip: 5-10bp.

fills=14  mean slippage=+6.4bp  median=+5.5bp  worst=+19.3bp  notional=$21,433  cost=$+14.15

Limit-first test. limit arm all in: 6 fills, mean +4.6bp, median +3.3bp; of which limit fills: 4 fills, mean +1.6bp, median +1.2bp and market fallbacks: 2 fills, mean +10.6bp, median +10.6bp. Market arm: 8 fills, mean +7.8bp, median +7.0bp.


symbol side     fill  ref_vwap  slip_bp  notional fill_et  minutes_from_open      arm
   EAT  buy  216.110  215.6933     19.3   1582.94   11:13                103   market
  TTMI sell   83.130   83.2400     13.2   1586.21   11:13                103 fallback
   FIX sell 1225.010 1226.1763      9.5   1628.22   11:11                101   market
  SNDK  buy 1118.622 1117.6548      8.7   1582.94   11:13                103   market
  NTAP  buy  192.600  192.4388      8.4   1582.94   11:13                103   market
  TRGP  buy  301.890  301.6472      8.0   1582.94   11:15                105 fallback
   ARM sell  204.190  204.3047      5.6   1521.55   11:11                101   market
  LRCX sell  237.020  237.1502      5.5   1645.64   11:11                101   market
  INTC  buy   62.970   62.9415      4.5   1582.94   11:13                103    limit
   TXN  buy  309.240  309.1134      4.1   1582.94   11:13                103   market
  PANW  buy  362.830  362.7529      2.1   1582.94   11:13                103    limit
  MRNA sell  221.870  221.8900      0.9    705.47   11:11                101   market
  AMAT sell  392.990  392.9986      0.2   1682.49   11:11                101    limit
   APA  buy   50.220   50.2221     -0.4   1582.94   11:13                103    limit
