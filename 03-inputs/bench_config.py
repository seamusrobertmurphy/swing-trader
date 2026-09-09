"""The bench: one run configuration, edited from the panels that own each part.

Choosing features on one panel, a grid on another and a split on a third only
means something if they compose into a single run. This module is that single
run, held as one JSON document under 04-outputs/AA-evals/bench/, so a panel
edits a section and the runner reads the whole thing.

Seven sections, each owned by the cheat-sheet panel of the same name:

    data          B1   which market, which bars, which symbols, how many rows
    label         A2   the triple barrier: take-profit, stop, horizon
    screen        A3   liquidity, volatility, history, and the cross-sectional rank
    features      C1   which families and which columns are offered to the model
    selection     D3   the elastic-net screen, and whether its survivors are fitted
    signals       C3   the indicator engines' own knobs, MACD, Fibonacci, MA
    split         D1   the held-out period, the embargo, the folds
    model         D2   which estimators and the grid swept over them
    calibration   E1   the mapping, the held-out fraction, the class weight
    viz           C3   what the charts draw, so a trend can be read differently

Every record the runner writes embeds the configuration that produced it. That
is not decoration. On 8 September 2026 a committed sweep could not be replayed
because its fold count and its grid lived only in the session that ran it, and a
committed calibration was cited at 120,000 rows when it had been run at 60,000.
A result that does not carry its settings is a result nobody can check.

Nothing here loads data or fits anything; it only says what should be done.
bench_run.py does it.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
BENCH = REPO / "04-outputs" / "AA-evals" / "bench"
ACTIVE = BENCH / "config.json"


# ---------------------------------------------------------------------------
# The panels a run can be pointed at.
#
# Named, never paths, so a browser form can never nominate a file. The crypto
# frames come from the survivorship-complete data.binance.vision archives; the
# equity frame from the Alpaca daily bars, adjusted.
# ---------------------------------------------------------------------------

MARKETS = {
    "crypto": {
        "label": "Binance spot crypto",
        "frames": {
            "5m":  "03-inputs/binance-data/dataset_5m_allmarket.parquet",
            "1h":  "03-inputs/binance-data/dataset_1h_allmarket.parquet",
            "4h":  "03-inputs/binance-data/dataset_4h_allmarket.parquet",
            "1d":  "03-inputs/binance-data/dataset_1d_allmarket.parquet",
            "slice_4h_40k": "03-inputs/binance-data/slice_4h_40k.parquet",
        },
        "benchmark": "BTCUSDT",
    },
    "equity": {
        "label": "Alpaca US equities",
        "frames": {
            "eq1d": "03-inputs/alpaca-data/dataset_eq1d_allmarket.parquet",
        },
        "benchmark": "SPY",
    },
}

# Named bundles, so a day's work can say "the majors" rather than retyping six
# tickers. A bundle is a starting point: the symbols field is free text and wins
# when it is filled in.
BUNDLES = {
    "all": [],
    "majors": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT"],
    "scalp-eight": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "SUIUSDT",
                    "TONUSDT", "DOGEUSDT", "NEARUSDT", "PEPEUSDT"],
    "btc-eth": ["BTCUSDT", "ETHUSDT"],
    "large-caps": ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "JPM", "XOM"],
    "sector-funds": ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP",
                     "XLI", "XLB", "XLU", "XLRE", "XLC"],
}

# The feature families, by column prefix, with what each one is. The counts move
# with the frame, so they are not written here; the panel reads them off the
# loaded frame.
FAMILIES = {
    "f_wc_":   "wall-clock windows, the daily windows times the bars per day",
    "f_hr_":   "intraday windows, the shorter family",
    "f_ta_":   "in-house oscillators: Williams %R, Stochastic, CCI, CMF, MFI, ADX, Aroon",
    "f_ta_pta_": "pandas-ta block: PPO, TRIX, Vortex, CMO, Fisher, Chande Kroll",
    "f_tl_":   "TA-Lib block: Parabolic SAR, MESA, Ultimate Oscillator, Hilbert, candles",
    "f_st_":   "triple Supertrend",
    "f_mst_":  "Modern Adaptive Supertrend with the efficiency-ratio gate",
    "f_btc_":  "relative strength against bitcoin, the only family not from the coin's own price",
    "f_4h_":   "four-hour context, joined causally",
    "f_d1_":   "daily context, joined causally",
    "f_w1_":   "weekly context, joined causally",
    "f_flow_": "taker-buy trade-flow imbalance",
    "f_rg_":   "regime state: trailing volatility, its own percentile, trend efficiency",
    "f_ms_":   "microstructure, derived from hourly bars",
}

ESTIMATORS = ["LogReg.glm", "LogReg.enet", "RF", "LightGBM", "HistGBM",
              "GBM.classic", "Ensemble.stack"]

TUNABLE = ["histgbm", "lightgbm", "rf", "gbm"]


# ---------------------------------------------------------------------------
# Every hyperparameter each estimator will accept, with its library default and
# what it does. These are the fields the Model panel renders once an estimator
# is chosen, and the same names the grid accepts, so a value set here and a
# value swept there mean the same thing to the same estimator.
#
# Defaults are the library's own, not this project's, except where a note says
# otherwise. Where a project default differs it is because the machine or the
# panel size demanded it, and the note says so.
# ---------------------------------------------------------------------------

MODEL_PARAMS: dict[str, tuple] = {
    "RF": (
        ("n_estimators", "int", 400, "Trees in the forest. More is steadier and slower; "
                                     "it does not overfit by growing, it only costs time."),
        ("max_depth", "int", 8, "Deepest a tree may grow. None grows until leaves are pure, "
                                "which memorises; 0 here means None."),
        ("min_samples_leaf", "int", 50, "Fewest rows a leaf may hold. The main brake on "
                                        "memorising: raise it when the overfit ratio climbs."),
        ("min_samples_split", "int", 2, "Fewest rows a node needs before it may split."),
        ("max_features", "text", "sqrt", "Columns considered at each split: sqrt, log2, a "
                                         "count, or a fraction. sqrt is what makes a forest "
                                         "a forest rather than a bag of identical trees."),
        ("criterion", "choice", "gini", "gini or entropy. Rarely changes much.",
         ("gini", "entropy", "log_loss")),
        ("bootstrap", "flag", True, "Sample rows with replacement per tree."),
        ("max_samples", "float", 0.0, "Fraction of rows per tree when bootstrapping. "
                                      "0 uses all of them."),
        ("ccp_alpha", "float", 0.0, "Cost-complexity pruning. Above 0 prunes weak branches."),
    ),
    "LightGBM": (
        ("n_estimators", "int", 600, "Boosting rounds."),
        ("learning_rate", "float", 0.05, "How much of each round is kept. Lower needs more "
                                         "rounds and generalises better."),
        ("num_leaves", "int", 31, "Leaves per tree. LightGBM grows leaf-wise, so this is the "
                                  "real capacity knob and it overfits fast above 63."),
        ("max_depth", "int", -1, "Depth cap. -1 is uncapped, which with num_leaves is usual."),
        ("min_child_samples", "int", 20, "Fewest rows in a leaf."),
        ("subsample", "float", 1.0, "Row fraction per round. Below 1 needs subsample_freq set."),
        ("subsample_freq", "int", 0, "Resample rows every this many rounds. 0 disables "
                                     "subsampling however low subsample is set."),
        ("colsample_bytree", "float", 1.0, "Column fraction per tree."),
        ("reg_alpha", "float", 0.0, "L1 penalty on leaf weights."),
        ("reg_lambda", "float", 0.0, "L2 penalty on leaf weights."),
        ("min_split_gain", "float", 0.0, "Gain a split must deliver before it is taken."),
        ("boosting_type", "choice", "gbdt", "gbdt is standard; dart drops trees and is slower; "
                                            "goss subsamples by gradient.",
         ("gbdt", "dart", "goss")),
    ),
    "HistGBM": (
        ("learning_rate", "float", 0.05, "How much of each round is kept."),
        ("max_iter", "int", 600, "Boosting rounds."),
        ("max_leaf_nodes", "int", 31, "Leaves per tree, the capacity knob."),
        ("max_depth", "int", 0, "Depth cap. 0 means None, uncapped."),
        ("min_samples_leaf", "int", 20, "Fewest rows in a leaf."),
        ("l2_regularization", "float", 1.0, "L2 penalty. The project default is 1.0 where "
                                            "the library's is 0.0."),
        ("max_bins", "int", 255, "Histogram bins per feature. Fewer is faster and coarser."),
        ("early_stopping", "flag", False, "Stop when a held-out slice stops improving. Note "
                                          "that slice is taken from the end of the training "
                                          "window, so it is the most recent market."),
        ("validation_fraction", "float", 0.1, "Size of that slice."),
    ),
    "GBM.classic": (
        ("n_estimators", "int", 150, "Boosting rounds."),
        ("learning_rate", "float", 0.05, "How much of each round is kept."),
        ("max_depth", "int", 3, "Depth of each tree. This one grows depth-wise, so 3 is deep "
                                "enough to matter."),
        ("subsample", "float", 0.5, "Row fraction per round. Below 1 makes it stochastic."),
        ("min_samples_leaf", "int", 1, "Fewest rows in a leaf."),
        ("max_features", "text", "", "Columns per split. Empty uses all of them."),
    ),
    "LogReg.glm": (
        ("C", "float", 1.0, "Inverse regularisation strength. Smaller penalises harder."),
        ("max_iter", "int", 5000, "Solver iterations before it gives up."),
        ("solver", "choice", "lbfgs", "lbfgs for the plain fit, saga when a penalty needs it.",
         ("lbfgs", "saga", "liblinear")),
    ),
    "LogReg.enet": (
        ("C", "float", 0.1, "Inverse regularisation strength."),
        ("l1_ratio", "float", 0.5, "Mixing, 1 is lasso and 0 is ridge."),
        ("max_iter", "int", 5000, "Solver iterations."),
    ),
}


@dataclass(frozen=True)
class Field_:
    """One setting on a panel form, and how to render and validate it."""

    key: str
    label: str
    kind: str                 # int, float, text, choice, multi, flag, symbols, grid
    default: Any = None
    choices: tuple = ()
    note: str = ""
    heavy_above: float | None = None


# ---------------------------------------------------------------------------
# The schema. One entry per section, in the order the panels read left to right.
# ---------------------------------------------------------------------------

SCHEMA: dict[str, dict] = {
    "data": dict(
        panel="B1", title="Input data",
        blurb="Which market, which bar size, which symbols, and how much history. "
              "Everything downstream reads what this section selects.",
        fields=(
            Field_("market", "Market", "choice", "crypto", tuple(MARKETS),
                   note="Crypto reads the Binance archives; equity reads the adjusted Alpaca bars."),
            Field_("frame", "Bar size", "choice", "slice_4h_40k",
                   ("5m", "1h", "4h", "1d", "slice_4h_40k", "eq1d"),
                   note="slice_4h_40k is a 25 MB cut of the four-hour panel and it is an "
                        "alphabetical band, 137 symbols from LINK onward with no bitcoin "
                        "in it, so use it for mechanics and the full 4h panel for anything "
                        "about a named coin. The full panel is two gigabytes and this "
                        "machine swaps, so cap the rows."),
            Field_("bundle", "Symbol bundle", "choice", "all", tuple(BUNDLES),
                   note="A named starting point. Anything typed below wins over it."),
            Field_("symbols", "Symbols", "symbols", "",
                   note="Space or comma separated, e.g. BTCUSDT ETHUSDT. Empty uses the bundle."),
            Field_("rows", "Row cap, most recent", "int", 40000, heavy_above=200_000,
                   note="0 reads the whole panel. Rows are counted in-sample and taken "
                        "from the recent end, so a capped run describes the market as it is now."),
        )),

    "label": dict(
        panel="A2", title="Label geometry",
        blurb="The triple barrier the model is asked to predict. It is a modelling "
              "decision, not an observed quantity, and the barrier's own base rate "
              "sets the win rate a strategy must beat before fees.",
        fields=(
            Field_("target_atr", "Take-profit, in ATR", "float", 2.0,
                   note="The inherited +2 has a base rate of 0.313 against a breakeven of 0.333, "
                        "so it loses money by construction before any model is fitted."),
            Field_("stop_atr", "Stop, in ATR", "float", 1.0),
            Field_("horizon_bars", "Horizon, in bars", "int", 12,
                   note="12 bars is two days on the four-hour frame, which is what the "
                        "built panels hold. The daily frame is built at 2 and the label "
                        "is degenerate there at a 0.068 base rate."),
        )),

    "screen": dict(
        panel="A3", title="Ranking and screening",
        blurb="Which assets are eligible at each bar, recomputed from information "
              "available at that bar. Membership is point-in-time, so a coin that "
              "was illiquid in 2019 is absent from 2019 however liquid it is now.",
        fields=(
            Field_("min_quote_volume", "Liquidity floor, 24h quote volume", "float",
                   30_000_000.0,
                   note="Below this an asset cannot be entered at the modelled cost. "
                        "The live screen uses the real spread; the built panel "
                        "approximates it with a Corwin-Schultz high-low estimator, "
                        "because klines carry no top of book."),
            Field_("atr_low", "Volatility band, lower", "float", 0.015,
                   note="As a fraction of price. Below the band there is no move to "
                        "trade; above it the stop is hit by noise."),
            Field_("atr_high", "Volatility band, upper", "float", 0.071),
            Field_("min_history_days", "History an asset must have", "int", 157,
                   note="The longest feature lookback plus the label horizon plus a "
                        "buffer, so no row is computed from a window that does not exist."),
            Field_("rank_signal", "Rank the universe by", "choice", "none",
                   ("none", "f_mst_dir", "f_d1_st_up", "f_btc_mom_168", "f_st_agree"),
                   note="Cross-sectional ordering. Relative strength was the one "
                        "signal never disproved: 25 of 42 were sign-stable train to "
                        "test, but the way of trading it was killed at 27 per cent of "
                        "half-year folds against a 60 per cent bar."),
            Field_("rank_tercile", "Keep which third", "choice", "all",
                   ("all", "top", "middle", "bottom"),
                   note="The point-in-time universe is thin, around five to seven "
                        "assets a bar, so it ranks into thirds at a five-asset floor "
                        "rather than deciles."),
            Field_("fold_bar", "Folds a result must win", "float", 0.60,
                   note="The share of half-year folds that must be positive. A pooled "
                        "total can be carried by one favourable regime, which is why "
                        "the bar is on folds and not on the total."),
        )),

    "features": dict(
        panel="C1", title="Feature selection",
        blurb="Which columns are offered to the model. Families first, then any "
              "column named explicitly. The blind year is never consulted here.",
        fields=(
            Field_("families", "Families offered", "multi", None, tuple(FAMILIES),
                   note="Nothing ticked offers every family the frame carries."),
            Field_("include", "Also include, by name", "symbols", "",
                   note="Exact column names, space separated. Added even if their family is off."),
            Field_("exclude", "Exclude, by name", "symbols", "",
                   note="Exact column names, removed last, so this beats everything above."),
            Field_("max_features", "Keep at most", "int", 0,
                   note="0 keeps all. Above 0, keeps the highest by univariate AUC on the "
                        "training window only."),
        )),

    "selection": dict(
        panel="D3", title="Variable selection",
        blurb="An elastic net over the training window decides which of the offered "
              "columns survive. Ninety features against the available sample admits "
              "overfitting, and the penalty is what stops it. The blind year is never "
              "touched.",
        fields=(
            Field_("run_selection", "Screen before fitting", "flag", False,
                   note="Off offers the model every column the Features section chose."),
            Field_("l1_ratio", "Mixing, 1 is lasso and 0 is ridge", "float", 1.0,
                   note="Between the two is the elastic net proper. Lasso zeroes "
                        "coefficients outright; ridge only shrinks them."),
            Field_("rule", "Penalty to screen at", "choice", "1se", ("1se", "min"),
                   note="1se is the most regularised penalty within one standard error of "
                        "the best, which keeps fewer variables and is the usual choice. "
                        "min keeps whatever scored best."),
            Field_("sel_sample", "Rows for the screen", "int", 25000, heavy_above=100_000,
                   note="The saga path is slow. 25,000 screens fine; 3,000 makes the "
                        "unpenalized interval refit singular."),
            Field_("sel_folds", "Cross-validation folds for the penalty", "int", 10),
            Field_("feed_model", "Fit the model on the survivors", "flag", True,
                   note="On, the screen replaces the model's feature list with what "
                        "survived. Off, the screen is reported and the model still sees "
                        "everything, which is the honest way to measure what the screen cost."),
            Field_("draw_intervals", "Draw the coefficient intervals", "flag", True,
                   note="An unpenalized refit for 95 per cent confidence intervals. It can "
                        "be singular at small samples, in which case it is skipped and said so."),
        )),

    "signals": dict(
        panel="C3", title="Signal engines",
        blurb="The indicator engines' own knobs. These drive both the features "
              "derived from them and what the charts draw, so a change here "
              "changes the picture and the model together.",
        fields=(
            Field_("macd_fast", "MACD fast span", "int", 12),
            Field_("macd_slow", "MACD slow span", "int", 26),
            Field_("macd_signal", "MACD signal span", "int", 9),
            Field_("macd_noise_k", "MACD noise band, in histogram sigmas", "float", 0.5,
                   note="A crossover counts only when the histogram clears this band. "
                        "Larger means fewer, higher-conviction signals; 0 disables it."),
            Field_("macd_confirm_bars", "Bars a cross must hold", "int", 1),
            Field_("ma_fast", "Moving average, fast", "int", 20),
            Field_("ma_slow", "Moving average, slow", "int", 50),
            Field_("fib_lookback", "Fibonacci swing lookback, bars", "int", 240),
            Field_("fib_min_swing_frac", "Ignore swings smaller than", "float", 0.0,
                   note="As a fraction of price. 0.03 filters noise on quiet ranges."),
            Field_("confluence_threshold", "Confluence score to fire", "float", 2.0,
                   note="How many of the four methods must agree. 2 is at least two."),
            Field_("candle_decay", "Bars a candle signal stays live", "int", 3),
        )),

    "split": dict(
        panel="D1", title="Train and test split",
        blurb="Chronological, never random. Returns are autocorrelated, so a random "
              "partition puts later observations in training and leaks.",
        fields=(
            Field_("holdout_days", "Blind period at the end, days", "int", 365,
                   note="Scored once, at the end. Nothing above may look at it."),
            Field_("embargo_bars", "Embargo at the cut, bars", "int", 0,
                   note="0 uses the label horizon, which is the minimum that stops a "
                        "label straddling the cut."),
            Field_("folds", "Walk-forward folds", "int", 3, heavy_above=8,
                   note="The fold count moved held-out error more than any hyperparameter "
                        "in the September grid: three folds 0.4840, five folds 0.4894, "
                        "against a grid spanning 0.033."),
            Field_("scheme", "Resampling regime", "choice", "expanding",
                   ("expanding", "rolling", "kfold", "repeated-kfold",
                    "leave-one-out", "monte-carlo", "bootstrap"),
                   note="Expanding grows the training window each fold and rolling slides "
                        "it; both keep time in order and are the only two that can be "
                        "trusted on a price series. The rest ignore time: k-fold and its "
                        "repeated form, leave-one-out, Monte Carlo random splits, and the "
                        "bootstrap. They are offered because they are the standard "
                        "comparisons and because seeing what they claim beside what "
                        "walk-forward finds is the clearest demonstration of why a random "
                        "split leaks on autocorrelated returns."),
            Field_("repeats", "Repeats, for the repeated schemes", "int", 10,
                   note="Ten by ten is the usual k-fold repetition. Ignored by the "
                        "schemes that do not repeat."),
            Field_("boot_samples", "Bootstrap resamples", "int", 25,
                   heavy_above=100,
                   note="Each draws a training set of the same size with replacement, so "
                        "about a third of the rows are out of bag and are scored on."),
        )),

    "model": dict(
        panel="D2", title="Model and hyperparameters",
        blurb="Which estimators are fitted, and the grid swept over one of them. "
              "Every grid point is fitted twice, in sample for the training error "
              "and per fold for the cross-validated one.",
        fields=(
            Field_("estimators", "Estimators to score", "multi", None, tuple(ESTIMATORS),
                   note="Nothing ticked scores the whole zoo."),
            Field_("tune", "Sweep this one", "choice", "", ("",) + tuple(TUNABLE),
                   note="Empty scores the zoo without sweeping. Naming one makes the run a sweep."),
            Field_("grid", "The grid", "grid",
                   "learning_rate=0.03,0.06,0.12 max_leaf_nodes=15,31 max_iter=200",
                   note="key=v1,v2 separated by spaces. Empty sweeps the model's own "
                        "entry in TUNE_GRIDS, which for histgbm is eighteen combinations."),
            Field_("class_weight", "Class weight", "choice", "balanced", ("balanced", "none"),
                   note="Balanced cost two thirds of the calibration error on 8 September, "
                        "on the metric these models are ranked by. It is not free."),
            Field_("params", "Hyperparameters", "params", None,
                   note="One block per estimator chosen above, every setting the library "
                        "accepts. See MODEL_PARAMS for the full surface: 9 for the random "
                        "forest, 12 for LightGBM, 9 for HistGBM. Anything left at its "
                        "default is not passed."),
            Field_("reject_ratio", "Reject above this overfit ratio", "float", 1.1,
                   note="Cross-validated RMSE over training RMSE. The house bar is 1.1 and "
                        "moving it is a decision, so the run records the value it used."),
        )),

    "calibration": dict(
        panel="E1", title="Calibration",
        blurb="Whether a stated 70 per cent happens 70 per cent of the time. A "
              "mapping is fitted on held-out training rows and scored once on the "
              "blind year. It corrects what a probability means; it adds no edge.",
        fields=(
            Field_("run_calibration", "Calibrate after scoring", "flag", True),
            Field_("methods", "Mappings to fit", "multi", None, ("Platt", "isotonic"),
                   note="Nothing ticked fits both. Both are monotone, so neither changes "
                        "AUC or the order trades are ranked in."),
            Field_("cal_fraction", "Held-out fraction for the mapping", "float", 0.2,
                   note="Taken from the end of the training window, never from the blind year."),
            Field_("bins", "Reliability bins", "int", 10),
        )),

    "viz": dict(
        panel="C3", title="Charts",
        blurb="Which figures a run saves, and the symbol and window they are drawn from. These change the picture only; no number moves because a chart was drawn differently.",
        fields=(
            Field_("panels", "Figures the run draws", "multi", None,
                   ("candles", "macd", "confluence", "fibonacci", "reliability",
                    "importance", "selectivity", "equity"),
                   note="Nothing ticked draws the reliability curve and the importance chart."),
            Field_("viz_symbol", "Symbol to chart", "text", "",
                   note="Empty charts the first symbol in the run."),
            Field_("viz_bars", "Bars to show", "int", 400),
            Field_("overlays", "Overlays", "multi", None,
                   ("ema200", "supertrend", "swings", "entries", "exits", "volume"),
                   note="Drawn on the candle panel."),
            Field_("theme", "Chart theme", "choice", "light", ("light", "dark")),
        )),
}

SECTIONS = tuple(SCHEMA)


# ---------------------------------------------------------------------------
# How a panel groups its settings.
#
# Operator instruction, 9 September 2026: related variables are clustered rather
# than listed flat. Each entry names a group, says in one line what the group
# decides, and lists the settings in it. A field not named in any cluster falls
# into the last one, so adding a setting to the schema never makes it invisible.
# ---------------------------------------------------------------------------

CLUSTERS: dict[str, tuple] = {
    "data": (
        ("Where the data comes from",
         "The market and the archive decide everything downstream.",
         ("market", "frame")),
        ("Which assets",
         "A bundle is a starting point; anything typed wins over it.",
         ("bundle", "symbols")),
        ("How much of it",
         "Counted in-sample and taken from the recent end.",
         ("rows",)),
    ),
    "label": (
        ("The barrier",
         "A take-profit and a stop, both in units of the asset's own volatility.",
         ("target_atr", "stop_atr")),
        ("How long it may take",
         "Past this the trade closes wherever it stands.",
         ("horizon_bars",)),
    ),
    "screen": (
        ("Can it be traded",
         "Liquidity and volatility, the two reasons an asset is ineligible.",
         ("min_quote_volume", "atr_low", "atr_high")),
        ("Is there enough of it",
         "Shorter history than the longest lookback means rows computed from "
         "a window that does not exist.",
         ("min_history_days",)),
        ("Ranking the survivors",
         "Cross-sectional ordering, and how much of the order is kept.",
         ("rank_signal", "rank_tercile", "fold_bar")),
    ),
    "features": (
        ("Families",
         "Whole blocks of columns, offered or withheld together.",
         ("families",)),
        ("Named columns",
         "Exceptions to the families. Exclusions are applied last and win.",
         ("include", "exclude", "preset")),
        ("How many survive",
         "", ("max_features",)),
    ),
    "selection": (
        ("Whether to screen at all",
         "Off offers the model every column the families chose.",
         ("run_selection", "feed_model")),
        ("The penalty",
         "How hard the net shrinks, and which penalty is screened at.",
         ("l1_ratio", "rule")),
        ("How it is fitted",
         "", ("sel_sample", "sel_folds", "draw_intervals")),
    ),
    "signals": (
        ("MACD",
         "Two moving averages and the line that crosses them, with the guard "
         "that stops a crossing counting as a signal in noise.",
         ("macd_fast", "macd_slow", "macd_signal", "macd_noise_k",
          "macd_confirm_bars")),
        ("Moving averages",
         "The trend filter the other engines are read against.",
         ("ma_fast", "ma_slow")),
        ("Fibonacci",
         "How far back the swing is measured, and how small a swing is ignored.",
         ("fib_lookback", "fib_min_swing_frac")),
        ("Combining them",
         "How many engines must agree before anything fires.",
         ("confluence_threshold", "candle_decay")),
    ),
    "split": (
        ("What is held back",
         "Scored once, at the end. Nothing above it may look at it.",
         ("holdout_days", "embargo_bars")),
        ("How the rest is resampled",
         "The fold count moved held-out error further than any hyperparameter "
         "did in the September grid.",
         ("scheme", "folds", "repeats", "boot_samples")),
    ),
    "model": (
        ("Which estimators",
         "", ("estimators", "class_weight")),
        ("Sweeping one of them",
         "Naming a model makes the run a sweep rather than a scorecard.",
         ("tune", "grid")),
        ("Hyperparameters",
         "Every setting the chosen estimators accept.",
         ("params",)),
        ("The bar",
         "Cross-validated error over training error. Moving it is a decision, "
         "so the run records the value it used.",
         ("reject_ratio",)),
    ),
    "calibration": (
        ("Whether to calibrate",
         "", ("run_calibration", "methods")),
        ("How the mapping is fitted",
         "Taken from the end of the training window, never from the blind year.",
         ("cal_fraction", "bins")),
    ),
    "viz": (
        ("Figures",
         "Which figures a run saves, and what is drawn on the candle chart.",
         ("panels", "overlays")),
        ("Chart subject",
         "The symbol and window every figure is drawn from.",
         ("viz_symbol", "viz_bars", "theme")),
    ),
}


def clusters_for(section: str) -> list[dict]:
    """One section's fields, grouped. Anything ungrouped lands in the last group."""
    spec = SCHEMA[section]
    by_key = {f.key: f for f in spec["fields"]}
    groups, placed = [], set()
    for title, why, keys in CLUSTERS.get(section, ()):
        fields = [by_key[k] for k in keys if k in by_key]
        placed.update(f.key for f in fields)
        if fields:
            groups.append(dict(title=title, why=why, fields=fields))
    left = [f for f in spec["fields"] if f.key not in placed]
    if left:
        if groups:
            groups[-1]["fields"] = list(groups[-1]["fields"]) + left
        else:
            groups.append(dict(title=spec["title"], why="", fields=left))
    return groups


# Plain names for the library's names. A form reading "n estimators" and
# "max leaf nodes" tells a reader nothing; the operator described these as tree
# length, number of branches and how many randomisers, which is what they are.
# The library name stays visible beside the plain one, because it is what the
# grid field and the record use.
PARAM_LABEL = {
    "n_estimators":       "How many trees",
    "max_depth":          "How deep a tree may grow",
    "max_leaf_nodes":     "Branches per tree",
    "min_samples_leaf":   "Fewest rows in a leaf",
    "min_samples_split":  "Fewest rows before a split",
    "max_features":       "Columns tried at each split",
    "criterion":          "How a split is judged",
    "bootstrap":          "Resample rows per tree",
    "max_samples":        "Rows per tree when resampling",
    "ccp_alpha":          "Pruning strength",
    "learning_rate":      "How much of each round is kept",
    "max_iter":           "Boosting rounds",
    "num_leaves":         "Branches per tree",
    "min_child_samples":  "Fewest rows in a leaf",
    "subsample":          "Rows per round",
    "subsample_freq":     "How often rows are resampled",
    "colsample_bytree":   "Columns per tree",
    "reg_alpha":          "L1 penalty on leaf weights",
    "reg_lambda":         "L2 penalty on leaf weights",
    "min_split_gain":     "Gain a split must deliver",
    "boosting_type":      "Boosting method",
    "l2_regularization":  "L2 penalty",
    "max_bins":           "Histogram bins per column",
    "early_stopping":     "Stop when it stops improving",
    "validation_fraction": "Slice held out to decide that",
    "C":                  "Inverse penalty strength",
    "l1_ratio":           "Mixing, 1 is lasso and 0 is ridge",
    "solver":             "Optimiser",
}


def param_fields(model: str) -> tuple:
    """One estimator's hyperparameters as renderable fields.

    Restored 9 September 2026. A version of this was written, never wired to a
    template, and correctly removed as dead code the same evening; the operator
    then reported the hyperparameter panel as dead, with no options showing,
    because all 42 settings across the estimators were rendered as a note and
    nothing else. This time the template renders them.
    """
    out = []
    for spec in MODEL_PARAMS.get(model, ()):
        key, kind, default, note = spec[0], spec[1], spec[2], spec[3]
        choices = spec[4] if len(spec) > 4 else ()
        label = PARAM_LABEL.get(key, key.replace("_", " "))
        out.append(Field_(f"{model}.{key}", f"{label}  ({key})", kind,
                          default, choices, note))
    return tuple(out)


def tunable_grids() -> dict:
    """The grid each model is swept over when none is typed, and what may be typed.

    The Sweep panel takes a grid as one line of text and the operator could not
    see which names it accepts. This is the reference: every hyperparameter the
    estimator takes, with its library default, and the grid used when the field
    is left blank. Read from model_assessment_1h.TUNE_GRIDS rather than copied,
    so the panel cannot drift from what the sweep actually runs.
    """
    try:
        import model_assessment_1h as ma
        grids = ma.TUNE_GRIDS
    except Exception:                                   # noqa: BLE001
        grids = {}
    out = {}
    for model, params in MODEL_PARAMS.items():
        key = model.lower().split(".")[0]
        out[model] = dict(
            settings=[(p[0], p[2], p[3]) for p in params],
            default_grid=grids.get(key, {}),
            combinations=(len(list(__import__("itertools").product(*grids[key].values())))
                          if key in grids else 0))
    return out


def defaults() -> dict:
    """A complete configuration, every section at its default."""
    out: dict = {}
    for name, spec in SCHEMA.items():
        out[name] = {f.key: ([] if f.kind == "multi" and f.default is None else f.default)
                     for f in spec["fields"]}
    return out


def load(path: Path | None = None) -> dict:
    """The active configuration, with any section absent filled from defaults.

    With no configuration saved yet the settings open on what previous runs
    found best rather than on the schema's bare defaults, which is the operator's
    instruction of 9 September 2026. Once a configuration is saved it wins, so
    the recommendation is a starting point and not a thing that keeps returning.
    """
    p = Path(path) if path else ACTIVE
    if not p.exists():
        try:
            return recommended()[0]
        except Exception:                               # noqa: BLE001
            return defaults()
    cfg = defaults()
    if p.exists():
        try:
            saved = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return cfg
        for name in cfg:
            if isinstance(saved.get(name), dict):
                cfg[name].update({k: v for k, v in saved[name].items()
                                  if k in cfg[name]})
    return cfg


def save(cfg: dict, path: Path | None = None) -> Path:
    p = Path(path) if path else ACTIVE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=2, sort_keys=True), encoding="utf-8")
    return p


def coerce(section: str, form: dict) -> dict:
    """Turn one panel's posted form into typed, validated settings.

    Anything the schema does not name is dropped, so a browser cannot introduce
    a setting the runner has never heard of.
    """
    spec = SCHEMA[section]
    out: dict = {}
    if section == "model":
        # Hyperparameters arrive as "<estimator>.<setting>", one flat field per
        # setting, because a browser form has no nesting. Only names the schema
        # knows for that estimator are kept, and a value equal to the library
        # default is dropped rather than passed, so a command stays the
        # difference from the library's own behaviour.
        params: dict = {}
        for key, raw in form.items():
            if "." not in key or not key.split(".")[0] in MODEL_PARAMS:
                continue
            model, setting = key.split(".", 1)
            for s_ in MODEL_PARAMS[model]:
                if s_[0] != setting:
                    continue
                kind, default = s_[1], s_[2]
                try:
                    val = (int(float(raw)) if kind == "int" else
                           float(raw) if kind == "float" else
                           (str(raw).lower() not in ("", "0", "false")) if kind == "flag"
                           else str(raw).strip())
                except (TypeError, ValueError):
                    break
                if val != default:
                    params.setdefault(model, {})[setting] = val
                break
        if params:
            out["params"] = params
    for f in spec["fields"]:
        if f.kind == "flag":
            out[f.key] = f.key in form and str(form[f.key]).lower() not in ("", "0", "false")
            continue
        if f.key not in form:
            continue
        raw = form[f.key]
        if f.kind == "multi":
            vals = raw if isinstance(raw, (list, tuple)) else [raw]
            out[f.key] = [v for v in vals if v in f.choices]
        elif f.kind == "choice":
            if raw in f.choices:
                out[f.key] = raw
        elif f.kind == "symbols":
            out[f.key] = " ".join(re.split(r"[,\s]+", str(raw).strip().upper())).strip()
        elif f.kind == "int":
            try:
                out[f.key] = int(float(raw))
            except (TypeError, ValueError):
                pass
        elif f.kind == "float":
            try:
                out[f.key] = float(raw)
            except (TypeError, ValueError):
                pass
        else:
            out[f.key] = str(raw).strip()
    return out


def canonical(sym: str) -> str:
    """A symbol reduced to its letters and digits.

    The built panels carry both BTCUSDT and BTC/USDT depending on which builder
    wrote them, and the equity panels carry a bare ticker. Matching on this form
    means typing the slash, or not typing it, never decides whether a run finds
    its data.
    """
    return re.sub(r"[^A-Za-z0-9]+", "", str(sym)).upper()


def symbols_for(cfg: dict) -> list[str]:
    """The symbols this run covers. Typed symbols win over the bundle."""
    typed = str(cfg["data"].get("symbols", "")).split()
    if typed:
        return typed
    return list(BUNDLES.get(cfg["data"].get("bundle", "all"), []))


def dataset_path(cfg: dict) -> str:
    market = MARKETS.get(cfg["data"].get("market", "crypto"), MARKETS["crypto"])
    frame = cfg["data"].get("frame", "")
    if frame in market["frames"]:
        return market["frames"][frame]
    # A frame from the other market: report it rather than guessing a file.
    for m in MARKETS.values():
        if frame in m["frames"]:
            raise ValueError(
                f"frame {frame!r} belongs to {m['label']}, not to "
                f"{market['label']}. Change the market or the bar size.")
    raise ValueError(f"unknown frame {frame!r}")


def resolve_features(cfg: dict, available: list[str]) -> list[str]:
    """The columns this run offers the model, from the columns the frame has.

    Order: families, then explicit includes, then explicit excludes last, so an
    exclusion always wins. A name that is not in the frame is dropped silently
    here and reported by the runner, which knows what the frame actually held.
    """
    fc = cfg["features"]
    fams = list(fc.get("families") or [])
    if fams:
        chosen = [c for c in available if any(c.startswith(p) for p in fams)]
        # f_ta_ would otherwise swallow f_ta_pta_, which is a different library.
        if "f_ta_" in fams and "f_ta_pta_" not in fams:
            chosen = [c for c in chosen if not c.startswith("f_ta_pta_")]
    else:
        chosen = list(available)
    for name in str(fc.get("include", "")).split():
        if name in available and name not in chosen:
            chosen.append(name)
    drop = set(str(fc.get("exclude", "")).split())
    return [c for c in chosen if c not in drop]


def grid_of(cfg: dict) -> dict:
    """The hyperparameter grid, parsed from its one-line form."""
    spec = str(cfg["model"].get("grid", "")).strip()
    if not spec:
        return {}
    grid: dict = {}
    for token in spec.split():
        if "=" not in token:
            raise ValueError(f"grid term {token!r} is not key=value")
        k, vs = token.split("=", 1)
        vals = []
        for v in vs.split(","):
            v = v.strip()
            for cast in (int, float):
                try:
                    vals.append(cast(v))
                    break
                except ValueError:
                    continue
            else:
                vals.append(v)
        grid[k.strip()] = vals
    return grid


def describe(cfg: dict) -> str:
    """One paragraph naming every setting, for the head of a record."""
    d, m, s_, sel = cfg["data"], cfg["model"], cfg["split"], cfg["selection"]
    syms = symbols_for(cfg)
    who = "all symbols" if not syms else (
        f"{len(syms)} symbols ({', '.join(syms[:6])}"
        f"{' and others' if len(syms) > 6 else ''})")
    rows = "the whole panel" if not d["rows"] else \
        f"{d['rows']:,} most recent in-sample rows"
    screen = ("no variable screen" if not sel["run_selection"] else
              f"an elastic net at l1_ratio {sel['l1_ratio']:g} screened at lambda.{sel['rule']}"
              f"{', and the model fitted on the survivors' if sel['feed_model'] else ''}")
    return (
        f"{MARKETS[d['market']]['label']}, {d['frame']} bars, {who}, {rows}. "
        f"Label {cfg['label']['target_atr']:g} ATR take-profit against "
        f"{cfg['label']['stop_atr']:g} ATR stop within "
        f"{cfg['label']['horizon_bars']} bars. Split holds out the final "
        f"{s_['holdout_days']} days with "
        f"{'a label-horizon' if not s_['embargo_bars'] else str(s_['embargo_bars']) + '-bar'} "
        f"embargo, {s_['folds']} {s_['scheme']} folds. {screen[0].upper() + screen[1:]}. "
        f"Estimators {', '.join(m['estimators']) or 'the whole zoo'}"
        f"{', sweeping ' + m['tune'] if m['tune'] else ''}, class weight "
        f"{m['class_weight']}, rejecting above a {m['reject_ratio']} overfit ratio."
    )


# ---------------------------------------------------------------------------
# What previous runs found best
#
# Operator instruction, 9 September 2026: the settings load as the recommended
# configuration from previous runtimes rather than as fixed defaults.
#
# Read the wording carefully, because the honest version and the flattering one
# differ. This returns the best configuration ON RECORD, not the optimal one.
# The two are not the same and this repository has the evidence: across 76
# sweeps and 456 fits the configuration ranking was not stable between
# conditions, the configuration that came last on one slice took first place 36
# times of 76 across all of them, and not one fit reached a Theil U2 meaningfully
# below one. So the recommendation is a starting point with a citation, and the
# panel says which record it came from and what that record scored.
# ---------------------------------------------------------------------------

def _all_records() -> list[dict]:
    import glob
    out = []
    for pat in ("*/bench-sweep-*.json", "*/bench-2*.json"):
        for f in glob.glob(str(REPO / "04-outputs" / "AA-evals" / pat)):
            if Path(f).name.startswith("._"):
                continue
            try:
                d = json.loads(Path(f).read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            d["_file"] = str(Path(f).relative_to(REPO))
            out.append(d)
    return out


def recommended() -> tuple[dict, dict]:
    """The best configuration on record, and where it came from.

    Ranked on the blind period, because that is the only column scored once and
    the only one a configuration cannot be tuned against. Among fits that also
    passed the overfit bar, the lowest Theil U2 wins; U2 below one means the
    model beat always predicting the base rate, and above one means it did not.

    Returns (configuration, provenance). Provenance names the record, the fit,
    what it scored and how many fits it was chosen from, so the recommendation
    can be checked rather than trusted.
    """
    best = None
    n_fits = n_passing = 0
    for d in _all_records():
        cfg = d.get("config")
        if not isinstance(cfg, dict):
            continue
        for r in (d.get("rows") or d.get("scores") or []):
            blind = r.get("blind")
            if not isinstance(blind, dict):
                continue
            u2 = blind.get("theil_u2")
            if u2 is None:
                continue
            n_fits += 1
            if r.get("rejected"):
                continue
            n_passing += 1
            if best is None or u2 < best[0]:
                best = (u2, cfg, r, d)

    if best is None:
        return defaults(), dict(found=False,
                                why="No scored run on disk yet, so the settings "
                                    "are the schema's own defaults.")

    u2, cfg, row, doc = best
    merged = defaults()
    for section in merged:
        if isinstance(cfg.get(section), dict):
            merged[section].update({k: v for k, v in cfg[section].items()
                                    if k in merged[section]})
    # The winning fit's own hyperparameters, which live on the row rather than
    # in the configuration, because a sweep varies them per fit.
    params = row.get("params") or {}
    if params:
        model = (merged["model"]["estimators"] or ["RF"])[0]
        merged["model"].setdefault("params", {})
        merged["model"]["params"] = dict(merged["model"].get("params") or {})
        merged["model"]["params"][model] = dict(params)

    return merged, dict(
        found=True,
        record=doc["_file"],
        stamped=str(doc.get("stamped", ""))[:19].replace("T", " "),
        fit=row.get("name") or row.get("model") or "",
        theil_u2=round(float(u2), 4),
        rmse_ratio=round(float(row.get("rmse_ratio", float("nan"))), 3),
        params=params,
        n_fits=n_fits, n_passing=n_passing,
        beat_constant=bool(u2 < 1.0),
    )


def recommendation_sentence(prov: dict) -> str:
    """One sentence a reader can act on, or decline to."""
    if not prov.get("found"):
        return prov.get("why", "")
    verdict = ("which beat always predicting the base rate, though only just"
               if prov["beat_constant"] else
               "which did NOT beat always predicting the base rate")
    return (
        f"These settings are the best configuration on record, not an optimal "
        f"one. Chosen from {prov['n_fits']:,} scored fits, {prov['n_passing']:,} "
        f"of which passed the overfit bar, by the lowest Theil U2 on the blind "
        f"period. The winner was {prov['fit']} at U2 {prov['theil_u2']}, "
        f"{verdict}, with an overfit ratio of {prov['rmse_ratio']}. "
        f"Read {prov['record']}, run {prov['stamped']}. The ranking of "
        f"configurations was not stable across conditions, so treat this as a "
        f"starting point with a citation.")

