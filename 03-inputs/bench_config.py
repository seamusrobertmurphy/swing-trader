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
# One plain line for each option in the two selection lists. Shown under the
# box as the choice changes. Operator instruction, 16 September 2026: every
# data object offered gets a description a newcomer can read.
FRAME_NOTES = {
    "5m": "One candle every 5 minutes. Scalping; a trade lasts about two hours.",
    "1h": "One candle every hour. Day trading; a trade lasts a day or two.",
    "4h": "One candle every 4 hours. Swing trading; the frame most work here used. Whole file is 2 GB.",
    "1d": "One candle a day. Position trading, held for weeks; fewest fees.",
    "slice_4h_40k": "A test sample, not a real choice of coins: the last 40,000 rows of the "
                    "4-hour file, cut on 8 September so this 8 GB laptop can load it in "
                    "seconds instead of being killed on the 2 GB file. By accident of "
                    "alphabetical order it holds the 137 coins from LINK onward and no "
                    "bitcoin. Use it to try settings; use the full 4-hour file to judge a coin.",
    "eq1d": "US stocks, one candle a day, from Alpaca. The only market with a strategy that "
            "beat its costs.",
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
                "slice_4h_40k": "4 hours, test sample", "eq1d": "1 day, US stocks"}
LABEL_NOTE = ('A candle is one bar of price history: the open, high, low and close of one '
              'timeframe. The label marks each candle a win or a loss: a win if price reaches '
              'the take-profit before the stop within the horizon. Both are set in ATR, the '
              'coin\'s typical daily move, so they widen on wild coins and narrow on calm ones.')
ROWS_NOTE = ("History to load is how many candles to read, newest first, counted across all "
             "picked coins. A candle is one bar of price history, the open, high, low and "
             "close of one timeframe. 0 reads everything; keep it under 40,000 on this laptop.")


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
    "Choose MACD": f'<a href="{W}MACD" target="_blank">MACD</a> compares a fast and a slow average '
        "of price; a cross of its signal line is a buy or sell. The noise band ignores crosses "
        "smaller than that many histogram deviations, and confirm bars is how long a cross must hold.",
    "Choose Averages": "Two moving averages of price, in candles. Price above the slow one is an "
        "uptrend; the fast one crossing the slow one is a signal.",
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
    "Choose Learner": "Tick the learners to score. Class weight balanced upweights the rarer "
        "outcome; on 8 September it caused two thirds of the calibration error. Overfit cap: a "
        "learner whose held-out error is more than this multiple of its training error is rejected.",
    "Choose Sweep": "Naming a learner turns the run into a sweep over the grid: key=value,value "
        "pairs, one fit per combination. Leave it empty to score the ticked learners once.",
    "Choose Settings": "Every setting each learner accepts, with the library's name in brackets. A "
        "value left at its default is not passed. Only the ticked learners are used.",
    "Choose Calibration": f'<a href="{W}Calibration_(statistics)" target="_blank">Calibration</a> '
        "checks whether a stated 70 per cent happens 70 per cent of the time, then fits a mapping "
        "to fix it on a held-out slice of the training window. Platt is a smooth curve, isotonic a "
        "step curve.",
    "Choose Figures": "Which figures the run draws, which symbol and how many candles they show, "
        "and which overlays go on the price chart.",
}

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
BAND_NOTE = ('Volatility is how far a coin\'s price moves in a typical day, measured by '
             '<a href="https://en.wikipedia.org/wiki/Average_true_range" target="_blank">ATR</a>, '
             'the Average True Range: the average, over the last 14 days, of each day\'s range '
             'from its low to its high. It is written as a share of price, so 0.015 is 1.5 per '
             'cent a day. Below the lower band a coin barely moves and there is nothing to '
             'catch; above the upper band moves are so wild the stop gets hit by noise. '
             'Movement is only useful if you can get in and out, so the volume floor sits '
             'beside it: at least this much, in USDT, traded in the last 24 hours. A volatile '
             'coin with thin volume is a trap.')
FOLD_NOTE = ("Fold pass rate: the history is cut into half-year pieces, called folds, and this "
             "is the share of them where the strategy must have made money; 0.6 is 6 of 10. "
             "One lucky year can make the total look good, and the folds catch that.")

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
                   ("5m", "1h", "4h", "1d", "slice_4h_40k", "eq1d"),
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
                   note="0 reads the whole panel. Rows are counted in-sample and taken "
                        "from the recent end, so a capped run describes the market as it is now."),
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
            Field_("horizon_bars", "Horizon, bars", "int", 12,
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
                        "approximates it with a Corwin-Schultz high-low estimator, "
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
                   note="Cross-sectional ordering. Relative strength was the one "
                        "signal never disproved: 25 of 42 were sign-stable train to "
                        "test, but the way of trading it was killed at 27 per cent of "
                        "half-year folds against a 60 per cent bar."),
            Field_("rank_tercile", "Keep third", "choice", "all",
                   ("all", "top", "middle", "bottom"),
                   note="The point-in-time universe is thin, around five to seven "
                        "assets a bar, so it ranks into thirds at a five-asset floor "
                        "rather than deciles."),
            Field_("fold_bar", "Fold pass rate", "float", 0.60,
                   note="The share of half-year folds that must be positive. A pooled "
                        "total can be carried by one favourable regime, which is why "
                        "the bar is on folds and not on the total."),
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
            Field_("sel_folds", "Folds", "int", 10),
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
                   note="The fold count moved held-out error more than any hyperparameter "
                        "in the September grid: three folds 0.4840, five folds 0.4894, "
                        "against a grid spanning 0.033."),
            Field_("scheme", "Regime", "choice", "expanding",
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
            Field_("repeats", "Repeats", "int", 10,
                   note="Ten by ten is the usual k-fold repetition. Ignored by the "
                        "schemes that do not repeat."),
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
            Field_("estimators", "Estimators", "multi", None, tuple(ESTIMATORS),
                   note="Nothing ticked scores the whole zoo."),
            Field_("tune", "Sweep", "choice", "", ("",) + tuple(TUNABLE),
                   note="Empty scores the zoo without sweeping. Naming one makes the run a sweep."),
            Field_("grid", "Grid", "grid",
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
        ("Choose Resampling", "", ('scheme', 'folds', 'purge_bars', 'repeats', 'boot_samples')),
    ),
    "model": (
        ("Choose Learner", "", ('estimators', 'class_weight', 'reject_ratio')),
        ("Choose Sweep", "", ('tune', 'grid')),
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
            vals = raw if isinstance(raw, (list, tuple)) else re.split(r"[,\s]+", str(raw).strip())
            out[f.key] = " ".join(v.strip().upper() for v in vals if v and v.strip()).strip()
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

