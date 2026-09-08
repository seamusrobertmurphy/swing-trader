# Hyperparameter tuning, histgbm (2026-09-08)

Grid search over expanding TimeSeriesSplit folds on the training window. Full = fitted and scored in-sample; CV = time-series out-of-fold on the same window. RMSE is on the predicted probabilities, so it is sqrt(Brier); MAE is the mean absolute probability error. RMSEratio = CV RMSE / Full RMSE, and a value above 1.1 is rejected as overfit regardless of its CV error. The blind final year is untouched. 15,000r / 90f. Ranked by CV RMSE.

Grid swept, replayable with `--grid`: `learning_rate=0.03,0.06,0.12 max_leaf_nodes=15,31 max_iter=200`, at `--cv-splits 3`

| hyperparameters | Full MAE | Full RMSE | CV MAE | CV RMSE | RMSEratio | verdict |
| --- | --- | --- | --- | --- | --- | --- |
| learning_rate=0.03 max_leaf_nodes=15 max_iter=200 | 0.3277 | 0.3541 | 0.3944 | 0.4840 | 1.367 | rejected |
| learning_rate=0.06 max_leaf_nodes=15 max_iter=200 | 0.2483 | 0.2842 | 0.3670 | 0.4891 | 1.721 | rejected |
| learning_rate=0.03 max_leaf_nodes=31 max_iter=200 | 0.2347 | 0.2682 | 0.3716 | 0.4915 | 1.832 | rejected |
| learning_rate=0.12 max_leaf_nodes=15 max_iter=200 | 0.1522 | 0.1935 | 0.3401 | 0.5026 | 2.598 | rejected |
| learning_rate=0.06 max_leaf_nodes=31 max_iter=200 | 0.1408 | 0.1765 | 0.3488 | 0.5049 | 2.860 | rejected |
| learning_rate=0.12 max_leaf_nodes=31 max_iter=200 | 0.0516 | 0.0739 | 0.3230 | 0.5173 | 7.003 | rejected |

No setting passed the overfit bar. Every combination scored an RMSEratio above 1.1. The lowest CV RMSE in the grid is learning_rate=0.03 max_leaf_nodes=15 max_iter=200 at 0.4840 with a ratio of 1.367, reported for diagnosis and not for use.

Grid span, best configuration to worst, 0.033 on CV RMSE across 6 settings; 0 pass the overfit bar.

