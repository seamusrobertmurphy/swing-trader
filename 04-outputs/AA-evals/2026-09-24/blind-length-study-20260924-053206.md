# Blind length and regime study, 24 September 2026 09:20

From `blind-length-study-20260924-053206.jsonl`. Money is per cent per trade after cost on the top fifth of rows by P(bullish) minus P(bearish); thin is the same trades with overlapping windows removed.

## Moving the cut

The winning model at each blind length, by top fifth after cost, and the Spearman rank correlation of the eight models' order against their order at 365 days.

| setup | blind days | cut | winner | winner top | runner-up top | all rows | rank corr. with 365 |
|---|---|---|---|---|---|---|---|
| crypto-4h-1 | 60.0 | 2026-04-19 | LogReg.enet | +0.410 | +0.351 | -0.692 | +0.76 |
| crypto-4h-1 | 90.0 | 2026-03-20 | LogReg.enet | -0.219 | -0.401 | -0.433 | +0.43 |
| crypto-4h-1 | 180.0 | 2025-12-20 | RF-incumbent | -0.351 | -0.444 | -0.520 | +0.83 |
| crypto-4h-1 | 270.0 | 2025-09-21 | RF-incumbent | +0.158 | +0.007 | -0.593 | +0.07 |
| crypto-4h-1 | 365.0 | 2025-06-18 | RF-incumbent | -0.088 | -0.404 | -0.268 | +1.00 |
| crypto-4h-1 | 540.0 | 2024-12-25 | LightGBM-default | +0.080 | +0.021 | -0.234 | -0.79 |
| crypto-4h-2 | 60.0 | 2026-04-20 | LogReg.enet | +0.650 | +0.416 | -1.085 | -0.45 |
| crypto-4h-2 | 90.0 | 2026-03-21 | LogReg.glm | -0.030 | -0.271 | -0.703 | -0.50 |
| crypto-4h-2 | 180.0 | 2025-12-21 | RF-deep | -0.343 | -0.492 | -0.689 | -0.48 |
| crypto-4h-2 | 270.0 | 2025-09-22 | RF-deep | -0.441 | -0.510 | -0.854 | +0.29 |
| crypto-4h-2 | 365.0 | 2025-06-19 | RF-incumbent | -0.256 | -0.300 | -0.564 | +1.00 |
| crypto-4h-2 | 540.0 | 2024-12-26 | RF-incumbent | +0.166 | +0.068 | -0.352 | -0.17 |
| crypto-1h-1 | 60.0 | 2026-04-18 | LogReg.enet | -0.028 | -0.031 | -0.726 | -0.38 |
| crypto-1h-1 | 90.0 | 2026-03-19 | LogReg.glm | -0.298 | -0.301 | -0.582 | -0.71 |
| crypto-1h-1 | 180.0 | 2025-12-19 | LogReg.glm | -0.394 | -0.395 | -0.730 | -0.57 |
| crypto-1h-1 | 270.0 | 2025-09-20 | RF-incumbent | -0.197 | -0.257 | -0.811 | -0.14 |
| crypto-1h-1 | 365.0 | 2025-06-17 | RF-incumbent | -0.656 | -0.685 | -0.487 | +1.00 |
| crypto-1h-1 | 540.0 | 2024-12-24 | LightGBM-default | -0.493 | -0.542 | -0.462 | +0.50 |
| crypto-1h-2 | 60.0 | 2026-04-18 | LightGBM-default | +0.012 | -0.180 | -0.903 | +0.48 |
| crypto-1h-2 | 90.0 | 2026-03-19 | RF-mid | -0.088 | -0.103 | -0.654 | +0.45 |
| crypto-1h-2 | 180.0 | 2025-12-19 | LogReg.enet | -0.490 | -0.560 | -0.778 | -0.07 |
| crypto-1h-2 | 270.0 | 2025-09-20 | LogReg.glm | -0.586 | -0.588 | -0.803 | -0.55 |
| crypto-1h-2 | 365.0 | 2025-06-17 | RF-incumbent | -0.776 | -0.789 | -0.457 | +1.00 |
| crypto-1h-2 | 540.0 | 2024-12-24 | RF-deep | -0.394 | -0.491 | -0.425 | +0.57 |
| equity-1d-1 | 60.0 | 2026-05-02 | LogReg.enet | +3.876 | +3.652 | -0.673 | +0.29 |
| equity-1d-1 | 90.0 | 2026-04-02 | LightGBM-regularised | +1.649 | +1.623 | -0.427 | -0.05 |
| equity-1d-1 | 180.0 | 2026-01-02 | HistGBM | +2.321 | +1.959 | +1.661 | +0.50 |
| equity-1d-1 | 270.0 | 2025-10-04 | LightGBM-regularised | +1.158 | +1.137 | +1.078 | +0.29 |
| equity-1d-1 | 365.0 | 2025-07-01 | LogReg.glm | +1.199 | +1.084 | +0.704 | +1.00 |
| equity-1d-1 | 540.0 | 2025-01-07 | LogReg.glm | +1.462 | +1.239 | +0.792 | +0.95 |
| equity-1d-2 | 60.0 | 2026-05-02 | LightGBM-default | +2.986 | +2.867 | +1.429 | +0.69 |
| equity-1d-2 | 90.0 | 2026-04-02 | HistGBM | +2.737 | +2.672 | +0.719 | +0.62 |
| equity-1d-2 | 180.0 | 2026-01-02 | RF-incumbent | +3.687 | +3.598 | +1.100 | +0.69 |
| equity-1d-2 | 270.0 | 2025-10-04 | LightGBM-default | +2.842 | +2.604 | +1.020 | +0.81 |
| equity-1d-2 | 365.0 | 2025-07-01 | LightGBM-default | +2.547 | +2.388 | +0.934 | +1.00 |
| equity-1d-2 | 540.0 | 2025-01-07 | HistGBM | +1.677 | +1.507 | +0.969 | +0.62 |

Wins by model across every setup and blind length: RF-incumbent 9, LogReg.enet 6, LogReg.glm 6, LightGBM-default 6, RF-deep 3, HistGBM 3, LightGBM-regularised 2, RF-mid 1.

## Same fit, shorter windows

One fit per model at the 365-day cut. Each window length splits the blind year into separate stretches, and the stretch's winner is recorded.

| setup | window days | stretches | distinct winners | year winner wins | median best minus worst |
|---|---|---|---|---|---|
| crypto-4h-1 | 30 | 12 | 3 | 10 | 1.712 |
| crypto-4h-1 | 60 | 6 | 5 | 1 | 1.341 |
| crypto-4h-1 | 90 | 4 | 3 | 1 | 1.055 |
| crypto-4h-1 | 180 | 2 | 2 | 1 | 0.989 |
| crypto-4h-1 | 365 | 1 | 1 | year winner RF-incumbent at -0.088 | 0.597 |
| crypto-4h-2 | 30 | 12 | 7 | 2 | 1.423 |
| crypto-4h-2 | 60 | 6 | 5 | 1 | 1.225 |
| crypto-4h-2 | 90 | 4 | 4 | 1 | 0.943 |
| crypto-4h-2 | 180 | 2 | 2 | 1 | 0.683 |
| crypto-4h-2 | 365 | 1 | 1 | year winner RF-incumbent at -0.256 | 0.301 |
| crypto-1h-1 | 30 | 12 | 6 | 3 | 1.172 |
| crypto-1h-1 | 60 | 6 | 4 | 0 | 0.979 |
| crypto-1h-1 | 90 | 4 | 4 | 1 | 0.751 |
| crypto-1h-1 | 180 | 2 | 2 | 1 | 0.593 |
| crypto-1h-1 | 365 | 1 | 1 | year winner RF-incumbent at -0.656 | 0.343 |
| crypto-1h-2 | 30 | 12 | 7 | 3 | 1.007 |
| crypto-1h-2 | 60 | 6 | 4 | 2 | 0.834 |
| crypto-1h-2 | 90 | 4 | 3 | 2 | 0.769 |
| crypto-1h-2 | 180 | 2 | 1 | 0 | 0.650 |
| crypto-1h-2 | 365 | 1 | 1 | year winner RF-incumbent at -0.776 | 0.263 |
| equity-1d-1 | 30 | 12 | 6 | 2 | 2.429 |
| equity-1d-1 | 60 | 6 | 5 | 1 | 2.638 |
| equity-1d-1 | 90 | 4 | 4 | 1 | 2.489 |
| equity-1d-1 | 180 | 2 | 2 | 1 | 1.320 |
| equity-1d-1 | 365 | 1 | 1 | year winner LogReg.glm at +1.199 | 0.872 |
| equity-1d-2 | 30 | 12 | 6 | 0 | 1.987 |
| equity-1d-2 | 60 | 6 | 2 | 4 | 1.455 |
| equity-1d-2 | 90 | 4 | 2 | 0 | 1.232 |
| equity-1d-2 | 180 | 2 | 2 | 1 | 1.298 |
| equity-1d-2 | 365 | 1 | 1 | year winner LightGBM-default at +2.547 | 0.827 |

## Choosing by regime

For each regime, the model with the best training-window top fifth, where that model ranked on the blind year out of eight, and the Spearman correlation between the eight claims and the eight blind results. Rank 1 is the best blind model.

| setup | regime | chosen | its blind rank | its blind top | claim | claim vs blind corr. |
|---|---|---|---|---|---|---|
| crypto-4h-1 | expanding | HistGBM | 8 | -0.685 | +0.491 | -0.93 |
| crypto-4h-1 | rolling | LogReg.glm | 3 | -0.407 | +0.453 | +0.67 |
| crypto-4h-1 | kfold | LightGBM-default | 7 | -0.586 | +4.428 | -0.86 |
| crypto-4h-1 | repeated-kfold | LightGBM-default | 7 | -0.586 | +4.415 | -0.83 |
| crypto-4h-1 | leave-one-out | LogReg.glm | 3 | -0.407 | +6.918 | +0.27 |
| crypto-4h-1 | monte-carlo | LightGBM-default | 7 | -0.586 | +4.664 | -0.83 |
| crypto-4h-1 | bootstrap | LightGBM-default | 7 | -0.586 | +4.127 | -0.86 |
| crypto-1h-1 | expanding | RF-deep | 5 | -0.817 | +0.184 | +0.26 |
| crypto-1h-1 | rolling | LogReg.glm | 7 | -0.992 | -0.016 | -0.52 |
| crypto-1h-1 | kfold | LightGBM-default | 2 | -0.685 | +5.044 | +0.60 |
| crypto-1h-1 | repeated-kfold | LightGBM-default | 2 | -0.685 | +5.098 | +0.60 |
| crypto-1h-1 | leave-one-out | RF-deep | 5 | -0.817 | +3.690 | +0.22 |
| crypto-1h-1 | monte-carlo | HistGBM | 3 | -0.744 | +5.101 | +0.57 |
| crypto-1h-1 | bootstrap | LightGBM-default | 2 | -0.685 | +4.947 | +0.62 |
| equity-1d-1 | expanding | LightGBM-regularised | 4 | +0.816 | +0.569 | +0.33 |
| equity-1d-1 | rolling | LogReg.enet | 2 | +1.084 | +0.651 | +0.69 |
| equity-1d-1 | kfold | LightGBM-default | 3 | +0.857 | +6.609 | +0.05 |
| equity-1d-1 | repeated-kfold | LightGBM-default | 3 | +0.857 | +6.625 | +0.05 |
| equity-1d-1 | leave-one-out | RF-deep | 7 | +0.468 | +8.104 | -0.03 |
| equity-1d-1 | monte-carlo | LightGBM-default | 3 | +0.857 | +6.750 | +0.02 |
| equity-1d-1 | bootstrap | LightGBM-default | 3 | +0.857 | +6.387 | +0.05 |

