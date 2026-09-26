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
    model         D2   which models and the grid compared over them
    calibration   E1   the mapping, the held-out fraction, the class weight
    viz           C3   what the charts draw, so a trend can be read differently

Every record the runner writes embeds the configuration that produced it. That
is not decoration. On 8 September 2026 a committed comparison run could not be replayed
because its fold count and its grid lived only in the session that ran it, and a
committed calibration was cited at 120,000 rows when it had been run at 60,000.
A result that does not carry its settings is a result nobody can check.

Nothing here loads data or fits anything; it only says what should be done.
bench_run.py does it.
"""

from __future__ import annotations

import functools
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
            "eq1d":  "03-inputs/alpaca-data/dataset_eq1d_allmarket.parquet",
            "eq1h":  "03-inputs/alpaca-data/dataset_eq1h_allmarket.parquet",
            "eq30m": "03-inputs/alpaca-data/dataset_eq30m_allmarket.parquet",
            "eq15m": "03-inputs/alpaca-data/dataset_eq15m_allmarket.parquet",
            "eq5m":  "03-inputs/alpaca-data/dataset_eq5m_allmarket.parquet",
        },
        "benchmark": "SPY",
    },
}

# Named bundles, so a day's work can say "the majors" rather than retyping six
# tickers. A bundle is a starting point: the symbols field is free text and wins
# when it is filled in.
# One plain line for each option in the two selection lists. Shown under the
# box as the choice changes. Operator instruction, 16 September 2026: every
# data object offered gets a description a newcomer can read.
FRAME_NOTES = {
    "5m": "One candle every 5 minutes. Scalping; a trade lasts about two hours.",
    "15m": "One candle every 15 minutes. Scalping; history is read straight from Binance.",
    "30m": "One candle every 30 minutes. Short day trades; read straight from Binance.",
    "1h": "One candle every hour. Day trading; a trade lasts a day or two.",
    "2h": "One candle every 2 hours. Day to swing trading; read straight from Binance.",
    "4h": "One candle every 4 hours. Swing trading; the frame most work here used. Whole file is 2 GB.",
    "6h": "One candle every 6 hours. Swing trading; read straight from Binance.",
    "8h": "One candle every 8 hours. Swing trading; read straight from Binance.",
    "12h": "One candle every 12 hours. Swing to position trading; read straight from Binance.",
    "1d": "One candle a day. Position trading, held for weeks; fewest fees.",
    "slice_4h_40k": "A test sample, not a real choice of coins: the last 40,000 rows of the "
                    "4-hour file, cut on 8 September so this 8 GB laptop can load it in "
                    "seconds instead of being killed on the 2 GB file. By accident of "
                    "alphabetical order it holds the 137 coins from LINK onward and no "
                    "bitcoin. Use it to try settings; use the full 4-hour file to judge a coin.",
    "eq1d": "US stocks, one candle a day, from Alpaca. The only market with a strategy that "
            "beat its costs.",
    "eq1h": "US stocks, one candle an hour. Seven candles a session, 09:30 to 16:00 New York.",
    "eq30m": "US stocks, one candle every 30 minutes. Thirteen a session.",
    "eq15m": "US stocks, one candle every 15 minutes. Twenty-six a session.",
    "eq5m": "US stocks, one candle every 5 minutes. Seventy-eight a session; the first fifteen "
            "minutes cost 42.6 basis points a trade against 7.6 after, so they are not traded.",
}
BUNDLE_NOTES = {
    "all": "Every coin or stock in the file.",
    "majors": "Six big coins: BTC, ETH, SOL, BNB, XRP, ADA.",
    "scalp-eight": "Eight liquid coins picked for scalping: BTC, ETH, SOL, SUI, TON, DOGE, NEAR, PEPE.",
    "btc-eth": "Bitcoin and Ethereum only.",
    "large-caps": "Eight large US stocks: AAPL, MSFT, NVDA, AMZN, GOOGL, META, JPM, XOM.",
    "sector-funds": "The eleven US sector funds, XLK to XLC.",
}

FRAME_LABELS = {"5m": "5 minutes", "1h": "1 hour", "4h": "4 hours", "1d": "1 day",
                "slice_4h_40k": "4 hours, test sample", "eq1d": "1 day, US stocks",
                "eq1h": "1 hour, US stocks", "eq30m": "30 minutes, US stocks",
                "eq15m": "15 minutes, US stocks", "eq5m": "5 minutes, US stocks"}
LABEL_NOTE = ('A candle is one period of price history, its open, high, low and close over one '
              'timeframe. The label marks each candle a win or a loss, a win if price reaches '
              'the take-profit before the stop within the horizon. Both are set in ATR, the '
              'coin\'s typical daily move, so they widen on wild coins and narrow on calm ones.')
ROWS_NOTE = ("Each candle covers one period of the timeframe you picked, so a 4-hour candle is "
             "four hours of trading. Crypto trades around the clock, so candles add up fast. "
             "Stocks trade only market hours, so the same count reaches further back.")


def file_symbols(frame: str) -> list[str]:
    """Every coin or stock in one data file, read from the file's own column stats."""
    import pyarrow.parquet as pq
    path = None
    for m in MARKETS.values():
        if isinstance(m, dict) and frame in m.get("frames", {}):
            path = REPO / m["frames"][frame]
    if path is None or not path.exists():
        return []
    if frame in _SYMBOL_CACHE:
        return _SYMBOL_CACHE[frame]
    pf = pq.ParquetFile(path)
    if "symbol" not in pf.schema.names:
        return []
    out: set[str] = set()
    for i in range(pf.num_row_groups):
        out.update(pf.read_row_group(i, columns=["symbol"]).column(0).unique().to_pylist())
    _SYMBOL_CACHE[frame] = sorted(x for x in out if x)
    return _SYMBOL_CACHE[frame]


_SYMBOL_CACHE: dict[str, list[str]] = {}

# One note under each tool that has no live line of its own. Plain words, a
# link where a term has a good definition elsewhere.
W = 'https://en.wikipedia.org/wiki/'
FORM_NOTES = {
    "Choose Features": "Families are groups of columns built the same way; tick the ones the model "
        "may see. Also include or leave out names single columns. At most caps the count, 0 for "
        "no cap. Relative strength against bitcoin is the strongest family measured so far.",
    "Choose MACD": f'<a href="{W}MACD" target="_blank">MACD</a> is the fast average of price minus '
        "the slow one, so it is positive while price is rising faster than its longer trend. The "
        "signal span is an average of MACD itself, and MACD crossing above that line is a buy, "
        "below it a sell. All three spans are counted in candles, 12, 26 and 9 being the standard "
        "set. The histogram is MACD minus its signal line, and the noise band is a multiple of "
        "that histogram's own standard deviation, so 0.5 ignores any cross where the two lines "
        "are closer together than half a typical gap. Confirm candles is how many candles the "
        "cross has to hold before it counts.",
    "Choose Averages": "Two plain averages of the closing price, counted in candles. Price above "
        "the slow one is an uptrend and below it a downtrend; the fast one crossing the slow one "
        "is the signal. 20 and 50 are the usual pair on a swing chart. These two feed the "
        "moving-average vote in the confluence score below.",
    "Choose Fibonacci": f'<a href="{W}Fibonacci_retracement" target="_blank">Fibonacci levels</a> '
        "are fractions of the last swing where price often pauses. Lookback is how many candles "
        "back to find that swing; swings smaller than the fraction are ignored.",
    "Choose Confluence": "Confluence counts how many engines agree. The score to fire is how "
        "many; a candle pattern counts for that many candles after it forms.",
    "Choose Screen": f'A first pass with an <a href="{W}Elastic_net_regularization" target="_blank">'
        "elastic net</a>, a regression that shrinks weak columns to zero. L1 mix 1 is lasso, 0 is "
        "ridge. The 1se rule keeps the simplest model within one standard error of the best. Fit "
        "on survivors passes only the kept columns to the model.",
    "Choose Blind Period": "The last N days are held back and scored once at the very end; nothing "
        "above may look at them. The embargo is a gap of candles at the cut so a label that looks "
        "ahead cannot straddle it; 0 uses the label horizon.",
    "Choose Resampling": "How the training window is cut into folds to estimate error before the "
        "blind period. Expanding and rolling keep time in order and are the only honest choices on "
        "prices; the rest are offered to show how much a random split flatters a fit. Purge drops "
        "rows before each scored block so a look-ahead label cannot leak.",
    "Choose Model": "Tick the models to score. Class weight balanced upweights the rarer "
        "outcome; on 8 September it caused two thirds of the calibration error. Overfit cap: a "
        "model whose held-out error is more than this multiple of its training error is rejected.",
    "Choose Grid Search": "Naming a model turns the run into a grid search: every combination of the grid: key=value,value "
        "pairs is fitted in turn. Leave it empty to score the ticked models once.",
    "Choose Settings": "Every setting each model accepts, with the library's name in brackets. A "
        "value left at its default is not passed. Only the ticked models are used.",
    "Choose Calibration": f'<a href="{W}Calibration_(statistics)" target="_blank">Calibration</a> '
        "checks whether a stated 70 per cent happens 70 per cent of the time, then fits a mapping "
        "to fix it on a held-out slice of the training window. Platt is a smooth curve, isotonic a "
        "step curve.",
    "Choose Figures": "Which figures the run draws, which symbol and how many candles they show, "
        "and which overlays go on the price chart.",
}

REGIME_NOTES = {
    "expanding": "The training window grows and each fold is scored on what follows. Keeps time in order; the house regime.",
    "rolling": "The training window slides along, so old history drops out. Keeps time in order.",
    "kfold": "Random equal blocks, each scored once. Ignores time: later candles sit in training while earlier ones are scored, which flatters the fit.",
    "repeated-kfold": "K-fold reshuffled and repeated. Same leak, several times over.",
    "leave-one-out": "Each scored candle is fitted on all the others, its neighbours included. The most flattering regime on a price series.",
    "monte-carlo": "Repeated random splits at 75 per cent training. Ignores time.",
    "bootstrap": "Draw candles with replacement and score the third left out. Ignores time.",
}
LEARNER_NOTES = {
    "LogReg.glm": "Logistic regression: a weighted sum of the columns turned into a probability. Stable, passes the overfit bar.",
    "LogReg.enet": "Logistic regression with an elastic-net penalty that shrinks weak columns. Best on the blind period so far.",
    "RF": "Random forest: hundreds of decision trees on random slices, averaged. Passes the bar at the incumbent settings.",
    "LightGBM": "A fast gradient booster. Memorises the training rows here: overfit ratio 5.5.",
    "HistGBM": "scikit-learn's gradient booster. Memorises here: overfit ratio 4.4.",
    "GBM.classic": "The older scikit-learn booster, no class weight. Rejected at 1.18.",
}
OPTION_NOTES = {
    "frame": FRAME_NOTES, "bundle": BUNDLE_NOTES, "rank_signal": None, "scheme": REGIME_NOTES,
    "estimators": LEARNER_NOTES,
    "families": {
        "f_wc_": "Trend, momentum and volatility over windows of days.",
        "f_hr_": "The same over a few candles.",
        "f_ta_": "Classic oscillators: Williams %R, Stochastic, CCI, CMF, MFI, ADX, Aroon.",
        "f_ta_pta_": "More oscillators: PPO, TRIX, Vortex, CMO, Fisher, Chande Kroll.",
        "f_tl_": "TA-Lib extras and candle patterns; most of the useless columns live here.",
        "f_st_": "Three Supertrend lines and their agreement.",
        "f_mst_": "The adaptive Supertrend.",
        "f_btc_": "The coin against bitcoin, and bitcoin's own move. The strongest family, by three times.",
    },
    "class_weight": {
        "balanced": "Upweights the rarer outcome. Cost two thirds of the calibration error and lifted blind U2 to 1.15 on every model on 16 September.",
        "none": "No reweighting. The probabilities mean what they say.",
    },
    "tune": {
        "": "No comparison run; the ticked models are scored once.",
        "histgbm": "Comparison run the histogram booster over the grid.",
        "lightgbm": "Comparison run LightGBM over the grid.",
        "rf": "Comparison run the random forest over the grid.",
        "gbm": "Comparison run the classic booster over the grid.",
    },
    "rule": {
        "1se": "Keep the simplest model within one standard error of the best. Fewer columns, generalises better.",
        "min": "Keep the model with the lowest cross-validated error. More columns.",
    },
    "methods": {
        "Platt": "A smooth S-curve fitted to the probabilities.",
        "isotonic": "A step curve that can bend anywhere; needs more rows.",
    },
    "panels": {
        "candles": "Price candles with volume.", "macd": "The MACD lines and histogram.",
        "confluence": "The confluence score over time.", "fibonacci": "Fibonacci levels on price.",
        "reliability": "Stated probability against observed frequency.", "importance": "Which columns the model leaned on.",
        "selectivity": "After-fee return against how choosy the model is.", "equity": "The account curve.",
    },
    "overlays": {
        "ema200": "The 200-candle average, the long trend.", "supertrend": "The Supertrend lines.",
        "swings": "The swing highs and lows Fibonacci uses.", "entries": "Where trades were entered.",
        "exits": "Where trades were exited.", "volume": "Volume under the price.",
    },
    "rank_tercile": {
        "all": "Keep every coin.", "top": "Keep the strongest third.", "middle": "Keep the middle third.",
        "bottom": "Keep the weakest third.",
    },
    "kind": {
        "barrier": "Win or loss: did price reach the take-profit before the stop?",
        "three-way": "Bullish, bearish or break-even, where break-even is a move inside the fee band.",
    },
    "theme": {"light": "Light background.", "dark": "Dark background."},
    "market": {"crypto": "Binance spot crypto, priced in USDT.", "equity": "US stocks through Alpaca, daily candles."},
}
OPTION_NOTES["rank_signal"] = None   # filled below, after RANK_NOTES is defined


def file_columns(frame: str) -> list[str]:
    """The feature columns in one data file, from its schema."""
    import pyarrow.parquet as pq
    path = None
    for m in MARKETS.values():
        if isinstance(m, dict) and frame in m.get("frames", {}):
            path = REPO / m["frames"][frame]
    if path is None or not path.exists():
        return []
    return [c for c in pq.ParquetFile(path).schema.names if c.startswith("f_")]


RANK_NOTES = {
    "none": "No ranking. Every coin that passes the filter is tested.",
    "f_mst_dir": "Adaptive Supertrend direction: +1 when its line says the trend is up, -1 "
                 "when down. The most stable ranking signal found in June.",
    "f_d1_st_up": "The daily chart's Supertrend: 1 when it says up, 0 when down, read from "
                  "the daily candles even when trading a shorter timeframe.",
    "f_btc_mom_168": "How far bitcoin itself moved over the last 168 candles, a week on hourly "
                     "candles. Ranks coins by the whole market's momentum.",
    "f_st_agree": "How many of three Supertrend lines, fast, medium and slow, agree the trend "
                  "is up: -1 when none do, +1 when all three do.",
}
OPTION_NOTES["rank_signal"] = RANK_NOTES

# Revision task 20 of 26 September 2026, the operator's wording.
BAND_NOTE = ('Volatility is how far a coin typically moves in a day, as a share of its price: '
             '0.015 means 1.5 per cent. It is measured by '
             '<a href="https://en.wikipedia.org/wiki/Average_true_range" target="_blank">ATR</a>, '
             'the average daily trading range over the last 14 days.<br><br>'
             'Below the lower band, moves are too small to cover trading costs. Above the upper '
             'band, ordinary swings hit your stop before the trade has a chance to work.<br><br>'
             'Volume is how much of the coin changed hands in the last 24 hours, in USDT. It '
             'answers two questions volatility cannot. Is the move real? Price can jump on a '
             'handful of trades and fall straight back. Can you trade it at the price you see? '
             'When few people are trading, the gap between buy and sell prices widens and your '
             'order fills worse, once going in and again coming out.<br><br>'
             'Volatility tells you there is a move worth catching. Volume tells you it is '
             'genuine and that you can afford to catch it.')
# Revision task 21 of 26 September 2026. The rule is bench_run.score_estimator's:
# a fold passes when its Theil's U2 is under 1, and the rate is reported
# against the bar without rejecting a model.
FOLD_NOTE = ("Fold pass rate is the share of cross-validation folds in which a model beats always "
             "guessing the average outcome, a Theil's U2 under 1 on that fold; 0.6 is 6 folds "
             "of 10. Under the default walk-forward split, each fold is validated only on candles "
             "later than everything it was trained on. The rate measures how stable a model is "
             "across time periods, not how accurate it is, because one lucky period can carry a "
             "pooled score. It is reported against this bar and does not reject a model.")

# Which archive folder holds the raw bars for each frame the bench offers, and
# how many bars a day each frame has. The daily archive is the unsuffixed one
# because that is what acquire_vision wrote before the interval suffix existed;
# slice_4h_40k is a cut of the four-hour panel and shares its bars. eq1d is
# absent on purpose: the equity frame comes from Alpaca and has no Binance
# archive behind it.
#
# These lived in control_charts until 20 September 2026, when the runner needed
# them too: the volume floor and the history floor are measured on the raw bars,
# because the built panel carries ratios and flags and no quote volume at all.
KLINE_ROOTS = {"5m": "klines_5m", "1h": "klines_1h", "4h": "klines_4h",
               "1d": "klines", "slice_4h_40k": "klines_4h",
               "15m": "klines_15m", "30m": "klines_30m", "2h": "klines_2h", "6h": "klines_6h",
               "8h": "klines_8h", "12h": "klines_12h"}

# Crypto trades round the clock, so a day is 24 hours of bars. A US session is
# 09:30 to 16:00 New York, six and a half hours, so a day is seven hourly bars
# and seventy-eight five-minute ones.
# Which folder under alpaca-data holds each equity frame's raw bars, the
# equity twin of KLINE_ROOTS.
EQUITY_STORES = {"eq1d": "daily", "eq1h": "hourly", "eq30m": "min30",
                 "eq15m": "min15", "eq5m": "min5"}

BARS_PER_DAY = {"5m": 288, "15m": 96, "30m": 48, "1h": 24, "2h": 12, "4h": 6, "6h": 4,
                "8h": 3, "12h": 2, "1d": 1,
                "slice_4h_40k": 6, "eq1d": 1, "eq1h": 7, "eq30m": 13,
                "eq15m": 26, "eq5m": 78}


def bars_per_day(frame: str) -> int:
    """Bars in a day on one frame, for a window written in days."""
    return int(BARS_PER_DAY.get(frame, 1))


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
              "GBM.classic"]

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
        ("max_features", "choice", "sqrt", "Columns tried at each split: the square root of "
                                           "the count, its log, a share of them, or all. sqrt "
                                           "is what makes a forest a forest rather than a bag "
                                           "of identical trees.",
         ("sqrt", "log2", "0.5", "0.25", "all")),
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
        ("max_features", "choice", "all", "Columns tried at each split.",
         ("all", "sqrt", "log2", "0.5")),
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
        panel="B1", title="Choose Market",
        # split: each cluster renders as its own form and saves on its own.
        # Operator instruction, 16 September 2026: Choose Market and Choose
        # Basket are two tools on the panel, not one form with two headings.
        split=True,
        blurb="",
        fields=(
            Field_("market", "Market", "choice", "crypto", tuple(MARKETS),
                   note="Crypto reads the Binance archives; equity reads the adjusted Alpaca bars."),
            Field_("frame", "Timeframe", "choice", "slice_4h_40k",
                   ("5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "slice_4h_40k",
                    "eq5m", "eq15m", "eq30m", "eq1h", "eq1d"),
                   note="slice_4h_40k is a 25 MB cut of the four-hour panel and it is an "
                        "alphabetical band, 137 symbols from LINK onward with no bitcoin "
                        "in it, so use it for mechanics and the full 4h panel for anything "
                        "about a named coin. The full panel is two gigabytes and this "
                        "machine swaps, so cap the rows."),
            Field_("bundle", "Quick pick", "choice", "all", tuple(BUNDLES),
                   note="A named starting point. Anything typed below wins over it."),
            Field_("symbols", "Coins or stocks", "symbols", "",
                   note="Space or comma separated, e.g. BTCUSDT ETHUSDT. Empty uses the bundle."),
            Field_("rows", "History to load", "int", 40000, heavy_above=200_000,
                   note="Candles counted across every picked coin, after the house screen, "
                        "newest first. 0 reads everything."),
        )),

    "label": dict(
        panel="A2", title="Choose Label",
        blurb="",
        fields=(
            Field_("target_atr", "Take-profit, ATR", "float", 2.0,
                   note="The inherited +2 has a base rate of 0.313 against a breakeven of 0.333, "
                        "so it loses money by construction before any model is fitted."),
            Field_("stop_atr", "Stop, ATR", "float", 1.0),
            Field_("kind", "Outcome", "choice", "barrier", ("barrier", "three-way"),
                   note="barrier: win or loss. three-way: bullish, bearish or break-even, "
                        "where break-even is a trade that ends inside the fee band."),
            Field_("flat_band", "Break-even band", "float", 0.002,
                   note="Half-width of the break-even class as a share of price; 0.002 is "
                        "the 0.20 per cent round-trip cost."),
            Field_("horizon_bars", "Horizon, candles", "int", 12,
                   note="12 bars is two days on the four-hour frame, which is what the "
                        "built panels hold. The daily frame is built at 2 and the label "
                        "is degenerate there at a 0.068 base rate."),
        )),

    "screen": dict(
        panel="A3", title="Choose Filter",
        split=True,
        blurb="",
        fields=(
            Field_("min_quote_volume", "Volume floor, USDT a day", "float",
                   30_000_000.0,
                   note="Below this an asset cannot be entered at the modelled cost. "
                        "The live screen uses the real spread; the built panel "
                        "approximates it with a Corwin-Schultz high-low model, "
                        "because klines carry no top of book."),
            Field_("atr_low", "Volatility band, lower", "float", 0.015,
                   note="As a fraction of price. Below the band there is no move to "
                        "trade; above it the stop is hit by noise."),
            Field_("atr_high", "Volatility band, upper", "float", 0.071),
            Field_("min_history_days", "Minimum history, days", "int", 157,
                   note="The longest feature lookback plus the label horizon plus a "
                        "buffer, so no row is computed from a window that does not exist."),
            Field_("rank_signal", "Rank by", "choice", "none",
                   ("none", "f_mst_dir", "f_d1_st_up", "f_btc_mom_168", "f_st_agree"),
                   note="Which column the assets are ordered by at each bar, strongest "
                        "to weakest. f_mst_dir, the adaptive Supertrend's direction, was "
                        "the steadiest of the 42 tried in June: its top third beat its "
                        "bottom third by 0.111 percentage points in training and 0.139 "
                        "in test, the same sign both times. It was still killed as a way "
                        "to trade, passing 27 per cent of half-year folds against a 60 "
                        "per cent bar, so it is offered here to be measured, not "
                        "believed."),
            Field_("rank_tercile", "Keep third", "choice", "all",
                   ("all", "top", "bottom"),
                   note="Top keeps the strongest third of the assets at each bar and is "
                        "the third a long-only book would buy. Bottom keeps the weakest "
                        "and is the control: the finding is the gap between the two, so "
                        "the bottom third has to be measurable. There is no middle, "
                        "because nothing is traded on the middle of a ranking. The "
                        "universe is thin, five to seven assets a bar, so a bar carrying "
                        "fewer than five is left whole rather than cut into thirds."),
            Field_("fold_bar", "Fold pass rate", "float", 0.60,
                   note="The share of cross-validation folds on which a model must beat "
                        "always guessing the average outcome. Reported, never used to reject."),
        )),

    "features": dict(
        panel="C1", title="Choose Features",
        blurb="",
        fields=(
            Field_("families", "Families", "multi", None, tuple(FAMILIES),
                   note="Nothing ticked offers every family the frame carries."),
            Field_("include", "Also include", "symbols", "",
                   note="Exact column names, space separated. Added even if their family is off."),
            Field_("exclude", "Leave out", "symbols", "",
                   note="Exact column names, removed last, so this beats everything above."),
            Field_("max_features", "At most", "int", 0,
                   note="0 keeps all. Above 0, keeps the highest by univariate AUC on the "
                        "training window only."),
        )),

    "selection": dict(
        panel="D3", title="Choose Screen",
        blurb="",
        fields=(
            Field_("run_selection", "Screen first", "flag", False,
                   note="Off offers the model every column the Features section chose."),
            Field_("l1_ratio", "L1 mix", "float", 1.0,
                   note="Between the two is the elastic net proper. Lasso zeroes "
                        "coefficients outright; ridge only shrinks them."),
            Field_("rule", "Penalty rule", "choice", "1se", ("1se", "min"),
                   note="1se is the most regularised penalty within one standard error of "
                        "the best, which keeps fewer variables and is the usual choice. "
                        "min keeps whatever scored best."),
            Field_("sel_sample", "Rows", "int", 25000, heavy_above=100_000,
                   note="The saga path is slow. 25,000 screens fine; 3,000 makes the "
                        "unpenalized interval refit singular."),
            # Both this and the split section's folds were labelled "Folds"
            # and they are different quantities: this cuts the elastic net's
            # own cross-validation, that cuts the model's. Renamed 21 September
            # 2026 after a label comparison found the collision.
            Field_("sel_folds", "Folds for this screen", "int", 10,
                   note="How many ways the training rows are cut to choose the "
                        "penalty. Separate from the model's own folds on Choose "
                        "Resampling, which this does not touch."),
            Field_("feed_model", "Fit on survivors", "flag", True,
                   note="On, the screen replaces the model's feature list with what "
                        "survived. Off, the screen is reported and the model still sees "
                        "everything, which is the honest way to measure what the screen cost."),
            Field_("draw_intervals", "Draw intervals", "flag", True,
                   note="An unpenalized refit for 95 per cent confidence intervals. It can "
                        "be singular at small samples, in which case it is skipped and said so."),
        )),

    "signals": dict(
        panel="C3", title="Signal engines",
        split=True,
        blurb="",
        fields=(
            Field_("macd_fast", "MACD fast span", "int", 12),
            Field_("macd_slow", "MACD slow span", "int", 26),
            Field_("macd_signal", "MACD signal span", "int", 9),
            Field_("macd_noise_k", "MACD noise band", "float", 0.5,
                   note="A crossover counts only when the histogram clears this band. "
                        "Larger means fewer, higher-conviction signals; 0 disables it."),
            Field_("macd_confirm_bars", "Confirm bars", "int", 1),
            Field_("ma_fast", "Moving average, fast", "int", 20),
            Field_("ma_slow", "Moving average, slow", "int", 50),
            Field_("fib_lookback", "Fibonacci lookback", "int", 240),
            Field_("fib_min_swing_frac", "Ignore small swings", "float", 0.0,
                   note="As a fraction of price. 0.03 filters noise on quiet ranges."),
            Field_("confluence_threshold", "Score to fire", "float", 2.0,
                   note="How many of the four methods must agree. 2 is at least two."),
            Field_("candle_decay", "Candle signal lasts", "int", 3),
        )),

    "split": dict(
        panel="D1", title="Train and test split",
        split=True,
        blurb="",
        fields=(
            Field_("holdout_days", "Blind days", "int", 365,
                   note="Scored once, at the end. Nothing above may look at it."),
            Field_("purge_bars", "Purge bars", "int", 0,
                   note="Rows dropped from the end of each walk-forward training block, so a "
                        "label that looks ahead cannot straddle the fold edge. 0 is none; "
                        "the honest value is the label horizon."),
            Field_("embargo_bars", "Embargo bars", "int", 0,
                   note="0 uses the label horizon, which is the minimum that stops a "
                        "label straddling the cut."),
            Field_("folds", "Folds", "int", 3, heavy_above=8,
                   note="The fold count moved held-out error more than any setting "
                        "in the September grid: three folds 0.4840, five folds 0.4894, "
                        "against a grid spanning 0.033."),
            Field_("scheme", "Regime", "choice", "expanding",
                   ("expanding", "rolling", "kfold", "repeated-kfold",
                    "leave-one-out", "monte-carlo", "bootstrap"),
                   note="caret models these two as one method, timeslice, with "
                        "fixedWindow deciding between them: \u201cif FALSE, all training "
                        "samples start at 1\u201d, which is expanding. Its window "
                        "geometry is set directly there, initialWindow for the first "
                        "training block, horizon for how many rows each fold scores and "
                        "skip for thinning; here all three are derived from the fold "
                        "count instead, which is fewer settings and less control. "
                        "(05-research/research/caret-package.pdf, createTimeSlices, "
                        "pages 30 to 31.) "
                        "Expanding grows the training window each fold and rolling slides "
                        "it; both keep time in order and are the only two that can be "
                        "trusted on a price series. The rest ignore time: k-fold and its "
                        "repeated form, leave-one-out, Monte Carlo random splits, and the "
                        "bootstrap. They are offered because they are the standard "
                        "comparisons and because seeing what they claim beside what "
                        "walk-forward finds is the clearest demonstration of why a random "
                        "split leaks on autocorrelated returns."),
            Field_("repeats", "Repeats", "int", 10,
                   note="Ten by ten is the usual k-fold repetition. Ignored by the "
                        "schemes that do not repeat. caret calls this repeats and "
                        "says the same: \u201cfor repeated k-fold cross-validation "
                        "only\u201d."),
            # caret exposes the training percentage as trainControl(p = 0.75),
            # \u201cfor leave-group out cross-validation: the training
            # percentage\u201d (05-research/research/caret-package.pdf, page 169).
            # This board had 0.75 written into folds_of as a constant, so the
            # one number that decides how much a random split trains on could
            # not be seen or moved. Named p after caret, labelled in words.
            Field_("train_fraction", "Training share", "float", 0.75,
                   note="How much of the window a random split trains on, the rest "
                        "being scored. Used by Monte Carlo, which is repeated random "
                        "splits; the walk-forward regimes take their share from the "
                        "fold count instead. caret calls this p."),
            # caret's trainControl(selectionFunction = "best") is \u201cthe
            # function used to select the optimal tuning parameter\u201d and
            # offers best, oneSE and tolerance (page 169). The board already
            # applies the one-standard-error idea to the elastic net on the
            # Choose Screen tool and nowhere else: the model was always chosen
            # on the lowest held-out error, with no way to ask for the simplest
            # model within a standard error of it.
            Field_("selection", "Choose the winner by", "choice", "best",
                   ("best", "oneSE"),
                   note="best takes the lowest held-out error among the models that "
                        "pass the overfit bar. oneSE takes the simplest model whose "
                        "error is within one standard error of the best, which "
                        "generalises better and is the same rule the elastic-net "
                        "screen already uses. caret calls this selectionFunction."),
            Field_("boot_samples", "Bootstrap samples", "int", 25,
                   heavy_above=100,
                   note="Each draws a training set of the same size with replacement, so "
                        "about a third of the rows are out of bag and are scored on."),
        )),

    "model": dict(
        panel="D2", title="Model",
        split=True,
        blurb="",
        fields=(
            Field_("estimators", "Models", "multi", None, tuple(ESTIMATORS),
                   note="Nothing ticked scores every model."),
            Field_("tune", "Grid search over", "choice", "", ("",) + tuple(TUNABLE),
                   note="Empty scores every model once. Naming one model tries each of its settings in turn."),
            # caret: "An integer denoting the amount of granularity in the
            # tuning parameter grid. By default, this argument is the number of
            # levels for each tuning parameters that should be generated by
            # train." (05-research/research/caret-package.pdf, page 165.) This
            # is the setting that lets a reader tune without composing a grid
            # by hand, which is what the Grid field below asks for.
            Field_("tune_length", "How hard to tune", "int", 0,
                   note="Values to try for each setting of the model being tuned, "
                        "chosen for you from its own sensible range. 3 is a quick "
                        "look, 10 is thorough. 0 uses the grid written below "
                        "instead. caret calls this tuneLength."),
            Field_("grid", "Grid", "grid",
                   "learning_rate=0.03,0.06,0.12 max_leaf_nodes=15,31 max_iter=200",
                   note="key=v1,v2 separated by spaces. Empty comparison runs the model's own "
                        "entry in TUNE_GRIDS, which for histgbm is eighteen combinations."),
            Field_("class_weight", "Class weight", "choice", "balanced", ("balanced", "none"),
                   note="Balanced cost two thirds of the calibration error on 8 September, "
                        "on the metric these models are ranked by. It is not free."),
            Field_("params", "Hyperparameters", "params", None,
                   note="One block per model chosen above, every setting the library "
                        "accepts. See MODEL_PARAMS for the full surface: 9 for the random "
                        "forest, 12 for LightGBM, 9 for HistGBM. Anything left at its "
                        "default is not passed."),
            Field_("reject_ratio", "Overfit ratio cap", "float", 1.1,
                   note="Cross-validated RMSE over training RMSE. The house bar is 1.1 and "
                        "moving it is a decision, so the run records the value it used."),
        )),

    "calibration": dict(
        panel="E1", title="Choose Calibration",
        blurb="",
        fields=(
            Field_("run_calibration", "Calibrate", "flag", True),
            Field_("methods", "Mappings", "multi", None, ("Platt", "isotonic"),
                   note="Nothing ticked fits both. Both are monotone, so neither changes "
                        "AUC or the order trades are ranked in."),
            Field_("cal_fraction", "Held-out fraction", "float", 0.2,
                   note="Taken from the end of the training window, never from the blind year."),
            Field_("bins", "Reliability bins", "int", 10),
        )),

    "viz": dict(
        panel="C3", title="Choose Figures",
        blurb="",
        fields=(
            Field_("panels", "Figures", "multi", None,
                   ("candles", "macd", "confluence", "fibonacci", "reliability",
                    "importance", "selectivity", "equity"),
                   note="Nothing ticked draws the reliability curve and the importance chart."),
            Field_("viz_symbol", "Symbol", "text", "",
                   note="Empty charts the first symbol in the run."),
            Field_("viz_bars", "Bars", "int", 400),
            Field_("overlays", "Overlays", "multi", None,
                   ("ema200", "supertrend", "swings", "entries", "exits", "volume"),
                   note="Drawn on the candle panel."),
            Field_("theme", "Theme", "choice", "light", ("light", "dark")),
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
        ("Choose Market", "", ("market", "frame")),
        ("Choose Basket", "", ("bundle", "symbols", "rows")),
    ),
    "label": (
        ("", "", ("target_atr", "stop_atr", "horizon_bars", "kind", "flat_band")),
    ),
    "screen": (
        ("Choose Filter", "", ("atr_low", "atr_high", "min_quote_volume", "min_history_days")),
        ("Choose Ranking", "", ("rank_signal", "rank_tercile", "fold_bar")),
    ),
    "features": (
        ("", "", ('families', 'include', 'exclude', 'max_features')),
    ),
    "selection": (
        ("", "", ('run_selection', 'feed_model', 'l1_ratio', 'rule', 'sel_sample', 'sel_folds', 'draw_intervals')),
    ),
    "signals": (
        ("Choose MACD", "", ('macd_fast', 'macd_slow', 'macd_signal', 'macd_noise_k', 'macd_confirm_bars')),
        ("Choose Averages", "", ('ma_fast', 'ma_slow')),
        ("Choose Fibonacci", "", ('fib_lookback', 'fib_min_swing_frac')),
        ("Choose Confluence", "", ('confluence_threshold', 'candle_decay')),
    ),
    "split": (
        ("Choose Blind Period", "", ('holdout_days', 'embargo_bars')),
        ("Choose Resampling", "", ('scheme', 'folds', 'purge_bars', 'repeats',
                                   'train_fraction', 'boot_samples', 'selection')),
    ),
    "model": (
        ("Choose Model", "", ('estimators', 'class_weight', 'reject_ratio')),
        ("Choose Grid Search", "", ('tune', 'grid')),
        ("Choose Settings", "", ('params',)),
    ),
    "calibration": (
        ("", "", ('run_calibration', 'methods', 'cal_fraction', 'bins')),
    ),
    "viz": (
        ("", "", ('panels', 'overlays', 'viz_symbol', 'viz_bars', 'theme')),
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
    "max_depth":          "Tree depth limit",
    "max_leaf_nodes":     "Branches per tree",
    "min_samples_leaf":   "Fewest rows in a leaf",
    "min_samples_split":  "Fewest rows before a split",
    "max_features":       "Columns tried at each split",
    "criterion":          "How a split is judged",
    "bootstrap":          "Resample rows per tree",
    "max_samples":        "Rows per tree when resampling",
    "ccp_alpha":          "Pruning strength",
    "learning_rate":      "Share kept each round",
    "max_iter":           "Rounds",
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
    "validation_fraction": "Held-out share",
    "C":                  "Inverse penalty strength",
    "l1_ratio":           "Lasso to ridge mix",
    "solver":             "Optimiser",
}


def param_fields(model: str) -> tuple:
    """One model's hyperparameters as renderable fields.

    Restored 9 September 2026. A version of this was written, never wired to a
    template, and correctly removed as dead code the same evening; the operator
    then reported the hyperparameter panel as dead, with no options showing,
    because all 42 settings across the models were rendered as a note and
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
    """The grid each model is compared over when none is typed, and what may be typed.

    The Comparison run panel takes a grid as one line of text and the operator could not
    see which names it accepts. This is the reference: every hyperparameter the
    model takes, with its library default, and the grid used when the field
    is left blank. Read from model_assessment_1h.TUNE_GRIDS rather than copied,
    so the panel cannot drift from what the comparison run actually runs.
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
        raw = p.read_bytes()
        # A file that exists and cannot be read is refused, never replaced by
        # the defaults. On 16 September 2026 the drive dropped mid-session and
        # came back with this file the same size and every byte null; the
        # loader returned the defaults, and a sweep meant for three symbols,
        # three families and no class weight ran on the whole slice, every
        # family and the balanced weight, with nothing in the log to say so.
        if raw and raw.count(b"\x00") == len(raw):
            raise SystemExit(f"{p} is {len(raw)} null bytes: the file was zeroed, "
                             "most likely by an unmount mid-write. Restore it from "
                             "the configuration embedded in the last record, or "
                             "press Load best as defaults, before running anything.")
        try:
            saved = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise SystemExit(f"{p} is not readable JSON ({e}); refusing to fall "
                             "back to the defaults silently.")
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
        dotted = False
        for key, raw in form.items():
            # Model names carry dots of their own (LogReg.glm, GBM.classic), so
            # the model is the longest known name the key starts with, not the
            # text before the first dot; that split silently dropped every
            # setting of the three dotted models until 20 September 2026.
            model = max((m for m in MODEL_PARAMS if key.startswith(m + ".")), key=len, default=None)
            if model is None:
                continue
            dotted = True
            setting = key[len(model) + 1:]
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
        # The settings form posts dotted keys; when it does, what it posts is
        # the whole truth, so a setting put back to its default is cleared
        # rather than left at the value saved before.
        if dotted:
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
            vals = raw if isinstance(raw, (list, tuple)) else re.split(r"[,\s]+", str(raw).strip())
            # Coin names are upper case; column names are not, and upper-casing
            # them made every include and exclude an unknown column.
            up = (lambda v: v.strip().upper()) if section == "data" else (lambda v: v.strip())
            out[f.key] = " ".join(up(v) for v in vals if v and v.strip()).strip()
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


@functools.lru_cache(maxsize=8192)
def canonical(sym: str) -> str:
    """A symbol reduced to its letters and digits.

    The built panels carry both BTCUSDT and BTC/USDT depending on which builder
    wrote them, and the equity panels carry a bare ticker. Matching on this form
    means typing the slash, or not typing it, never decides whether a run finds
    its data.

    A capped read of the four-hour panel asks this 1.8 million times, once per
    row, and the answers repeat a few hundred times each, so the result is kept;
    it was 2.45 seconds of a 23-second page, measured 22 September 2026.
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
                f"{market['label']}. Change the market or the timeframe.")
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
        f"Models {', '.join(m['estimators']) or 'every model'}"
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
    """One plain sentence a reader can act on, or decline to."""
    if not prov.get("found"):
        return prov.get("why", "")
    # Rewritten 16 September 2026 at the operator's instruction: plain words,
    # every number glossed in the same breath.
    verdict = ("under 1, so it beat a constant guess, just" if prov["beat_constant"]
               else "1 or more, so it did not beat a constant guess")
    return (
        f"Best of {prov['n_fits']:,} fits so far: {prov['fit']}. "
        f"Error on the unseen year {prov['theil_u2']} times a constant guess, {verdict}. "
        f"Overfit ratio {prov['rmse_ratio']}, under the 1.1 cap. "
        f"Record {Path(str(prov['record'])).name}.")

# Option descriptions for the dropdowns on the job forms and the model
# settings, shown in one line under the tool when a choice is made.
OPTION_NOTES["families"].update({
    "f_4h_": "Four-hour context joined to a shorter timeframe.",
    "f_h1_": "Hourly context joined to a scalp timeframe.",
    "f_d1_": "Daily context: trend, Supertrend and averages on daily candles.",
    "f_w1_": "Weekly context on weekly candles.",
    "f_flow_": "Taker buy share of volume: who is hitting the ask.",
    "f_rg_": "Regime: volatility rank, trend efficiency, bitcoin above or below its average.",
    "f_ms_": "Hourly microstructure summarised per day.",
})
OPTION_NOTES.update({
    "design": {
        "forest": "Nine settings on the random forest, one row each.",
        "regime": "One model under seven resampling regimes against one blind period.",
        "regime-memoriser": "The seven regimes on a forest allowed to memorise.",
        "purge": "The forest with 0 to 48 rows purged from the end of each training block.",
        "models": "Six models at their defaults on the same rows and folds.",
        "models-balanced": "The six models with the balanced class weight.",
    },
    "dataset": dict(FRAME_NOTES, **{"": "The script's own default file."}),
    "interval": dict(FRAME_NOTES, **{"15m": "Fifteen-minute candles, the second scalp timeframe."}),
    "frame": dict(FRAME_NOTES),
    "target": {"forward": "The close-to-close move over the horizon.",
               "barrier": "The trade's return under the take-profit and stop."},
    "models": dict(LEARNER_NOTES),
    "RF.max_features": {
        "sqrt": "Square root of the column count per split, the forest default.",
        "log2": "Log of the column count per split.",
        "0.5": "Half the columns per split.", "0.25": "A quarter of the columns per split.",
        "all": "Every column per split, so the trees grow alike."},
    "GBM.classic.max_features": {
        "all": "Every column per split, the library default.",
        "sqrt": "Square root of the column count per split.",
        "log2": "Log of the column count per split.", "0.5": "Half the columns per split."},
    "RF.criterion": {"gini": "Gini impurity, the default.", "entropy": "Information gain.",
                     "log_loss": "The same as entropy."},
    "RF.bootstrap": {"1": "Each tree sees a resample of the rows.", "0": "Each tree sees every row."},
    "LightGBM.boosting_type": {"gbdt": "Standard gradient boosting.",
                               "dart": "Drops trees at random each round; slower.",
                               "goss": "Keeps the rows with the largest errors; faster."},
    "HistGBM.early_stopping": {"1": "Stops when a held-out slice stops improving.",
                               "0": "Runs every round."},
    "LogReg.glm.solver": {"lbfgs": "The plain fit.", "saga": "Needed when a penalty is set.",
                          "liblinear": "Small-data solver.", "newton-cg": "Newton steps."},
})
