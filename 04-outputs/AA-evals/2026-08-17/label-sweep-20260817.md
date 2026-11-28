# Priority 1b: label-geometry sweep (2026-08-17)

ATR-scaled triple-barrier label swept over (target, stop, horizon). The model and split are fixed; only the label changes per row. Net P&L/trade is after the 0.20% round-trip cost on the model's confident trades (prob >= 0.60). 'breakeven win' is stop/(stop+target) in ATR units -- a geometry is lopsided when its actual win rate sits at or below breakeven. Ranked by net P&L/trade, best first.

| geometry | horizon | base rate | test AUC | trades | precision | precision change | net P&L/trade | win rate | breakeven win | t-stat |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| +3.0/-1.0 ATR | 20b (20d) | 0.144 | 0.551 | 383 | 0.191 | +32.6% | -0.126% | 30.8% | 25.0% | -0.28 |
| +2.0/-1.0 ATR | 20b (20d) | 0.273 | 0.543 | 501 | 0.321 | +17.7% | -0.139% | 35.5% | 33.3% | -0.38 |
| +3.0/-1.0 ATR | 10b (10d) | 0.104 | 0.581 | 293 | 0.147 | +41.8% | -0.348% | 31.1% | 25.0% | -0.72 |
| +2.0/-1.0 ATR | 5b (5d) | 0.140 | 0.594 | 289 | 0.180 | +28.6% | -0.388% | 35.6% | 33.3% | -0.97 |
| +2.0/-1.5 ATR | 5b (5d) | 0.156 | 0.617 | 343 | 0.283 | +81.4% | -0.506% | 42.6% | 42.9% | -0.99 |
| +2.0/-1.5 ATR | 20b (20d) | 0.318 | 0.530 | 600 | 0.348 | +9.7% | -0.569% | 41.3% | 42.9% | -1.42 |
| +2.0/-1.5 ATR | 10b (10d) | 0.239 | 0.557 | 522 | 0.295 | +23.5% | -0.617% | 42.5% | 42.9% | -1.56 |
| +3.0/-1.5 ATR | 10b (10d) | 0.119 | 0.598 | 379 | 0.195 | +64.0% | -0.622% | 35.9% | 33.3% | -1.15 |
| +2.0/-1.0 ATR | 10b (10d) | 0.211 | 0.553 | 444 | 0.239 | +13.4% | -0.629% | 33.6% | 33.3% | -1.85 |
| +3.0/-1.0 ATR | 5b (5d) | 0.062 | 0.692 | 173 | 0.139 | +123.9% | -0.713% | 31.2% | 25.0% | -1.13 |
| +3.0/-1.5 ATR | 20b (20d) | 0.169 | 0.561 | 477 | 0.208 | +23.1% | -0.922% | 33.8% | 33.3% | -1.88 |
| +3.0/-1.5 ATR | 5b (5d) | 0.071 | 0.715 | 209 | 0.206 | +189.8% | -1.315% | 34.9% | 33.3% | -1.50 |

**Best by net P&L/trade:** +3.0/-1.0 ATR over 20 bars -> net -0.126%/trade, win 30.8% vs breakeven 25.0%, t-stat -0.28, AUC 0.551. Verdict: NO-GO.

