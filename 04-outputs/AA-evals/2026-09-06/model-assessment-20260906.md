# Model assessment (2026-09-06) -- caret-style, 1h frame

RMSE/MAE are on predicted probabilities (RMSE = sqrt(Brier), the caret-style classification RMSE). Full = in-sample on the training window; CV = time-series out-of-fold on the training window; RMSEratio = CV RMSE / Full RMSE (near 1 = stable, above 1.1 = rejected as overfit). The final year is held out as a single blind test (below). Ranked by CV RMSE, best first.

| model | hyperparameters | Full MAE | Full RMSE | CV MAE | CV RMSE | RMSEratio |
| --- | --- | --- | --- | --- | --- | --- |
| HistGBM | leaves=31 lr=0.05 iter=600 | 0.2181 | 0.2619 | 0.3861 | 0.4818 | 1.840 |
| LightGBM | leaves=31 lr=0.05 n=600 | 0.2387 | 0.2806 | 0.4036 | 0.4826 | 1.720 |
| RF | mtry=auto ntree=400 depth=8 | 0.4445 | 0.4526 | 0.4761 | 0.4840 | 1.069 |
| LogReg.glm | C=1.0 | 0.4718 | 0.4855 | 0.4463 | 0.4909 | 1.011 |

**Best by CV RMSE:** HistGBM (CV RMSE 0.4818, RMSEratio 1.840).

**Blind final-year test of the best model** (scored once): AUC 0.509, precision(buy|p>=0.60) 0.249 vs base rate 0.254, net P&L/trade -0.454% on 3,012 trades.

**Classification view** (blind test, 0.5 threshold) -- diagnostics for whether the minority (barrier-hit) class is learned; the after-fee Metric 2 above remains the GO/NO-GO. Cohen's Kappa 0.006; OOB nan (RandomForest only).

| class | precision | recall | F1 |
| --- | --- | --- | --- |
| 0 (no-hit) | 0.748 | 0.706 | 0.726 |
| 1 (barrier-hit) | 0.258 | 0.301 | 0.278 |

Confusion matrix [true x pred]: TN 9,942, FP 4,142, FN 3,348, TP 1,440.

