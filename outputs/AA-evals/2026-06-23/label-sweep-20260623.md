# Priority 1b: label-geometry sweep (2026-06-23)

ATR-scaled triple-barrier label swept over (target, stop, horizon). The model and split are fixed; only the label changes per row. Net P&L/trade is after the 0.20% round-trip cost on the model's confident trades (prob >= 0.60). 'breakeven win' is stop/(stop+target) in ATR units -- a geometry is lopsided when its actual win rate sits at or below breakeven. Ranked by net P&L/trade, best first.

| geometry | horizon | base rate | test AUC | trades | precision | precision change | net P&L/trade | win rate | breakeven win | t-stat |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| +3.0/-1.5 ATR | 480b (20d) | 0.315 | 0.516 | 5,273 | 0.324 | +2.9% | -0.247% | 32.4% | 33.3% | -7.70 |
| +4.0/-1.0 ATR | 240b (10d) | 0.188 | 0.519 | 3,461 | 0.198 | +5.7% | -0.258% | 19.8% | 20.0% | -7.22 |
| +3.0/-1.0 ATR | 480b (20d) | 0.234 | 0.510 | 4,023 | 0.236 | +0.7% | -0.279% | 23.6% | 25.0% | -9.46 |
| +4.0/-1.0 ATR | 480b (20d) | 0.190 | 0.522 | 3,683 | 0.192 | +1.3% | -0.281% | 19.2% | 20.0% | -8.30 |
| +2.0/-1.0 ATR | 480b (20d) | 0.309 | 0.512 | 3,933 | 0.311 | +0.9% | -0.283% | 31.1% | 33.3% | -10.98 |
| +2.0/-1.0 ATR | 240b (10d) | 0.306 | 0.513 | 3,876 | 0.312 | +2.0% | -0.284% | 31.2% | 33.3% | -10.81 |
| +3.0/-1.5 ATR | 240b (10d) | 0.314 | 0.513 | 5,484 | 0.318 | +1.3% | -0.287% | 31.8% | 33.3% | -9.15 |
| +4.0/-1.5 ATR | 240b (10d) | 0.259 | 0.520 | 5,256 | 0.263 | +1.4% | -0.295% | 26.3% | 27.3% | -8.47 |
| +3.0/-1.0 ATR | 240b (10d) | 0.232 | 0.509 | 3,864 | 0.231 | -0.4% | -0.314% | 23.1% | 25.0% | -10.37 |
| +4.0/-1.5 ATR | 480b (20d) | 0.259 | 0.513 | 5,262 | 0.259 | -0.2% | -0.319% | 25.9% | 27.3% | -9.14 |
| +2.0/-1.5 ATR | 240b (10d) | 0.402 | 0.507 | 5,546 | 0.402 | +0.0% | -0.324% | 40.2% | 42.9% | -12.26 |
| +2.0/-1.5 ATR | 480b (20d) | 0.404 | 0.506 | 5,954 | 0.396 | -1.8% | -0.339% | 39.6% | 42.9% | -13.49 |

**Best by net P&L/trade:** +3.0/-1.5 ATR over 480 bars -> net -0.247%/trade, win 32.4% vs breakeven 33.3%, t-stat -7.70, AUC 0.516. Verdict: NO-GO.

