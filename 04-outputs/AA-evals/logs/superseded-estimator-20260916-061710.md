# Estimator sweep, 16 September 2026 06:17

Six estimators at their bench defaults on the same rows, the same walk-forward folds and the same blind period, so a difference between rows is the learner and nothing else.

Binance spot crypto, slice_4h_40k bars, 3 symbols (LINK/USDT, LTC/USDT, MATIC/USDT), 12,000 most recent in-sample rows. Label 2 ATR take-profit against 1 ATR stop within 12 bars. Split holds out the final 365 days with a label-horizon embargo, 3 expanding folds. No variable screen. Estimators RF, class weight none, rejecting above a 1.1 overfit ratio.

One panel read once, split at 2025-06-04 into 6,735 training rows and 1,286 blind. Every configuration is scored against those same rows, so a difference between two rows is the configuration and nothing else. Each was refitted 3 times on different seeds and the spread is reported.

## What each configuration changes

**LogReg.glm** &mdash; Logistic regression, unpenalised, after median imputation and standardisation.

**LogReg.enet** &mdash; Logistic regression with an elastic-net penalty, half lasso and half ridge, C 0.1.

**RF** &mdash; The random forest at the bench defaults: 400 trees, depth 8, 50 rows a leaf.

**HistGBM** &mdash; scikit-learn's histogram gradient booster, 600 iterations at a learning rate of 0.05.

**LightGBM** &mdash; LightGBM, 600 trees of 31 leaves at 0.05.

**GBM.classic** &mdash; scikit-learn's classic booster, 150 trees of depth 3 on half the rows. Takes no class weight, so it is always unweighted.

## Scores

Full is fitted and scored in sample on the training window; CV is walk-forward out-of-fold on that same window. The ratio is CV RMSE over Full RMSE and the bar rejects above 1.1. Theil's U2 is the model's error over the error of always predicting the base rate, so anything at or above one is not beating a constant.

| configuration | RMSE Full | RMSE CV | MAE CV | MISE CV | U2 CV | ratio | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| LogReg.enet | 0.4305 | 0.4349 | 0.3701 | 0.00369 | 1.008 | 1.010 | passes |
| RF | 0.4074 | 0.4371 | 0.3834 | 0.00551 | 1.013 | 1.073 | passes |
| LogReg.glm | 0.4301 | 0.4391 | 0.3666 | 0.00659 | 1.017 | 1.021 | passes |
| GBM.classic | 0.3918 | 0.4624 | 0.4014 | 0.02767 | 1.071 | 1.180 | rejected |
| HistGBM | 0.1133 | 0.4960 | 0.3529 | 0.05967 | 1.149 | 4.379 | rejected |
| LightGBM | 0.0926 | 0.5079 | 0.3511 | 0.07195 | 1.177 | 5.487 | rejected |

## On the blind period

Scored once, at the end.

| configuration | RMSE | MAE | MISE | Theil U1 | Theil U2 | bias share | AUC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| LogReg.enet | 0.4254 | 0.3653 | 0.00181 | 0.568 | 0.995 | 0.001 | 0.563 |
| RF | 0.4284 | 0.3744 | 0.00283 | 0.567 | 1.002 | 0.002 | 0.512 |
| LogReg.glm | 0.4268 | 0.3654 | 0.00302 | 0.567 | 0.998 | 0.001 | 0.558 |
| GBM.classic | 0.4303 | 0.3723 | 0.00310 | 0.566 | 1.006 | 0.002 | 0.531 |
| HistGBM | 0.4670 | 0.3642 | 0.03506 | 0.595 | 1.092 | 0.000 | 0.487 |
| LightGBM | 0.4674 | 0.3574 | 0.03542 | 0.604 | 1.093 | 0.002 | 0.485 |

## Is the difference bigger than the noise

Each configuration refitted 3 times on different seeds. The spread column is the standard deviation of held-out RMSE across those refits. A gap between two configurations smaller than their own spread is not a result.

| configuration | CV RMSE mean | spread across seeds |
| --- | ---: | ---: |
| LogReg.enet | 0.4349 | 0.00000 |
| RF | 0.4371 | 0.00000 |
| LogReg.glm | 0.4391 | 0.00000 |
| GBM.classic | 0.4624 | 0.00000 |
| HistGBM | 0.4960 | 0.00000 |
| LightGBM | 0.5079 | 0.00000 |

The design spans 0.0730 on held-out RMSE. The largest spread within a single configuration is 0.00000. The design is separating configurations rather than noise.


## Reading

3 of 6 configurations passed the overfit bar. The best of those on held-out error is **LogReg.enet** at 0.4349, ratio 1.010, blind Theil U2 0.995.

Swept in 700 seconds.

## The configuration that produced this

```json
{
  "calibration": {
    "bins": 10,
    "cal_fraction": 0.2,
    "methods": [],
    "run_calibration": false
  },
  "data": {
    "bundle": "all",
    "frame": "slice_4h_40k",
    "market": "crypto",
    "rows": 12000,
    "symbols": "LINK/USDT LTC/USDT MATIC/USDT"
  },
  "features": {
    "exclude": "",
    "families": [
      "f_st_",
      "f_wc_",
      "f_hr_"
    ],
    "include": "",
    "max_features": 0
  },
  "label": {
    "horizon_bars": 12,
    "stop_atr": 1.0,
    "target_atr": 2.0
  },
  "model": {
    "class_weight": "none",
    "estimators": [
      "RF"
    ],
    "grid": "learning_rate=0.03,0.06,0.12 max_leaf_nodes=15,31 max_iter=200",
    "params": {
      "RF": {
        "max_depth": 4,
        "min_samples_leaf": 200,
        "n_estimators": 150
      }
    },
    "reject_ratio": 1.1,
    "tune": ""
  },
  "screen": {
    "atr_high": 0.071,
    "atr_low": 0.015,
    "fold_bar": 0.6,
    "min_history_days": 157,
    "min_quote_volume": 30000000.0,
    "rank_signal": "none",
    "rank_tercile": "all"
  },
  "selection": {
    "draw_intervals": true,
    "feed_model": true,
    "l1_ratio": 1.0,
    "rule": "1se",
    "run_selection": false,
    "sel_folds": 10,
    "sel_sample": 25000
  },
  "signals": {
    "candle_decay": 3,
    "confluence_threshold": 2.0,
    "fib_lookback": 240,
    "fib_min_swing_frac": 0.0,
    "ma_fast": 20,
    "ma_slow": 50,
    "macd_confirm_bars": 1,
    "macd_fast": 12,
    "macd_noise_k": 0.5,
    "macd_signal": 9,
    "macd_slow": 26
  },
  "split": {
    "boot_samples": 25,
    "embargo_bars": 0,
    "folds": 3,
    "holdout_days": 365,
    "repeats": 10,
    "scheme": "expanding"
  },
  "viz": {
    "overlays": [],
    "panels": [],
    "theme": "light",
    "viz_bars": 400,
    "viz_symbol": ""
  }
}
```

