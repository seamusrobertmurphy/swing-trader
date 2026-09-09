"""What the control centre is allowed to show and allowed to run.

Every card on the control centre, and every job behind a Run button, is
declared here and nowhere else. The web app reads this file; it never builds a
command from anything a browser sent. A script that is not in ALLOWED below
cannot be launched however the request is shaped, which is the whole reason the
registry is a separate module from the app.

The knob defaults are not authoritative. Each script already declares its own
default in its argparse call, and control_eval.py reads those defaults straight
out of the source with the ast module and compares them against what is written
here. A default that drifts is a failing check, not a silent disagreement.
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import bench_config as bench

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "03-inputs"
EVALS = REPO / "04-outputs" / "AA-evals"

# The project interpreter. Every job runs under this one, never under whatever
# python happens to be first on the scheduler's PATH, which is how the launchd
# tick spent twelve days failing in August.
PYTHON = str(REPO / ".venv" / "bin" / "python")

# The panels a job may be pointed at. Names, not paths, so a browser cannot
# nominate a file. The 40k slice exists because the full 4h panel is two
# gigabytes and this machine sits nearly five gigabytes into swap; it is the
# setting to reach for first and the reason it is listed first.
PANELS = {
    "slice_4h_40k": "03-inputs/binance-data/slice_4h_40k.parquet",
    "4h": "03-inputs/binance-data/dataset_4h_allmarket.parquet",
    "1h": "03-inputs/binance-data/dataset_1h_allmarket.parquet",
    "1d": "03-inputs/binance-data/dataset_1d_allmarket.parquet",
    "5m": "03-inputs/binance-data/dataset_5m_allmarket.parquet",
}

# The estimator list had been written out twice, here and as
# bench_config.ESTIMATORS, in the same order with the same seven names. Two
# copies of a list the model panel and the sweep panel both offer is two lists
# that disagree the first time one is edited, so this reads the other.
ZOO = bench.ESTIMATORS


@dataclass(frozen=True)
class Knob:
    """One setting, and the command-line flag it becomes."""

    flag: str                       # the long flag, without the leading dashes
    label: str                      # what the form calls it, in plain words
    kind: str                       # int, float, choice, multi, flag, panel
    default: Any = None
    choices: tuple = ()
    note: str = ""                  # one line under the field
    heavy_above: float | None = None  # warn when the value passes this
    # Where the script writes this default itself rather than spelling out a
    # literal, name the symbol so the eval check can say "symbolic, not
    # compared" instead of failing on an expression it cannot evaluate.
    symbolic: str = ""
    # A form default deliberately different from the script's own, with the
    # reason. --tune is the case that made this necessary: the script defaults
    # to None because a plain run is a scorecard, but the sweep panel must
    # arrive already set to a model, or its Run button runs the wrong thing.
    preset: str = ""


@dataclass(frozen=True)
class Job:
    """One runnable script, its knobs, and the evidence it leaves behind."""

    key: str
    script: str                     # file name inside 03-inputs/
    title: str
    blurb: str                      # what pressing Run actually does
    knobs: tuple[Knob, ...]
    records: tuple[str, ...]        # globs under 04-outputs/AA-evals/
    runtime: str                    # honest wall-clock expectation
    # A committed record and the fields a fresh run at the same settings must
    # reproduce. Read by control_eval.py --deep. Empty means no reproduction
    # check is claimed for this job.
    reproduces: dict = field(default_factory=dict)

    @property
    def path(self) -> Path:
        return SCRIPTS / self.script


@dataclass(frozen=True)
class Group:
    """One section inside a panel that absorbed several panels.

    Operator instruction, 9 September 2026. Nine panels became six, and two of
    the six hold everything three or two panels held between them. Fourteen or
    sixteen charts cannot be a flat strip: a reader arriving at a wall of
    drawings has no way to tell which of them answers which question. So a
    merged panel keeps the panels it came from as sections, and each section
    says in one line what it answers.

    The section carries what the panel it replaced carried: its remaining
    charts, its table, its own controls and its own interactive figure. The
    configuration forms and the Run buttons stay at panel level above these,
    because settings that are prominent are settings a reader can find, and the
    operator's instruction of 9 September was that charts sit at the top of a
    panel and the settings directly under them.
    """

    key: str                        # names the interactive figure and the hooks
    title: str                      # the panel this section replaced
    answers: str                    # one line: the question this section answers
    charts: tuple[str, ...] = ()
    table: str = ""                 # built in control_tables.py
    controls: tuple[str, ...] = ()


@dataclass(frozen=True)
class Card:
    """One panel, in the same order and the same colour as the cheat sheet."""

    key: str                        # A1 ... E3
    lane: str                       # A ... E
    colour: str                     # the cheatsheet's own class: c-conf, c-thr
    title: str
    tag: str
    lead: str
    jobs: tuple[Job, ...] = ()
    evidence: tuple[str, ...] = ()  # record globs to list, newest first
    reading: tuple[tuple[str, str], ...] = ()  # (label, repo-relative path)
    # Which section of the bench configuration this panel edits. A panel with a
    # section renders that section's fields as its form, so the panel and the
    # run cannot disagree about what a setting is called or what it accepts.
    section: str = ""
    # Several sections, for a panel that merged. The Data panel owns three: the
    # sources, the label geometry and the screen. Operator instruction,
    # 9 September 2026, merging what were A1, A2 and A3.
    sections: tuple[str, ...] = ()

    @property
    def all_sections(self) -> tuple[str, ...]:
        return self.sections or ((self.section,) if self.section else ())
    # What the panel draws. Every panel that reports a result names at least one
    # chart: the first design drew nothing at all across fifteen panels, which
    # was the largest of the five defects the operator reported.
    charts: tuple[str, ...] = ()
    # Controls a panel offers that are neither a configuration section nor a
    # job: filtering a table, switching a view. Declared so "no panel is read
    # only" can be checked rather than assumed.
    controls: tuple[str, ...] = ()
    # A table the panel itself carries, built in control_tables.py, drawn under
    # the charts. Panels that merged hang their tables off a section instead;
    # this is for a panel that did not merge and still has one thing to list.
    table: str = ""
    # The panels this one absorbed, each keeping its own charts, table and
    # controls under a heading. Empty on a panel that never merged.
    groups: tuple[Group, ...] = ()

    @property
    def all_charts(self) -> tuple[str, ...]:
        """The top row, then each section's own, in reading order.

        The count matters as much as the list. Nine panels named 50 chart slots
        between them and the six name the same 50, so the merge can be shown to
        have lost nothing rather than asserted to have lost nothing.
        """
        out = list(self.charts)
        for g in self.groups:
            out += [n for n in g.charts]
        return tuple(out)

    @property
    def all_tables(self) -> tuple[str, ...]:
        # The panel's own table first, then each section's, so a panel that
        # never merged can still carry one and still be counted.
        return (((self.table,) if self.table else ())
                + tuple(g.table for g in self.groups if g.table))

    @property
    def all_controls(self) -> tuple[str, ...]:
        out = list(self.controls)
        for g in self.groups:
            out += list(g.controls)
        return tuple(out)


# Three columns of two since 9 September 2026, replacing three columns of three.
# The operator merged Performance, Tuning and the Scoreboard into one panel and
# Assessment into the Live book, which leaves six. Column A is what goes in,
# column B is what is chosen and how it is fitted, column C is what came out.
# Two rows rather than three, so a panel is taller and its chart is legible on
# the front page without opening it.
LANES = (
    ("A", "Inputs", "the data, and the columns offered to the model"),
    ("B", "Fitting", "what is selected, and the regime it is fitted under"),
    ("C", "Results", "the current fit against every fit, and the history"),
)

# Spans the frame rather than sitting in a column. Operator instruction,
# 8 September 2026: the chronological progress of the model, its updates and its
# milestones, along the bottom or the top of the screen.
TIMELINE = dict(key="T", title="Timeline",
                sub="every run in order, with its headline result")

# --------------------------------------------------------------------------
# The six jobs. Each one already took these settings as command-line flags
# before the control centre existed; nothing here is a new entry point.
# --------------------------------------------------------------------------

JOB_SPLIT = Job(
    key="split",
    script="split_checks.py",
    title="Audit the split",
    blurb=(
        "Checks that the training window ends before the test window begins, "
        "that the gap between them is at least the label horizon, and that a "
        "random split would have leaked. Writes a dated audit."
    ),
    knobs=(
        Knob("dataset", "Which panel", "panel", default="", symbolic="build_dataset_1h.DATASET_PATH",
             note="Blank leaves the script on its own default panel."),
        Knob("sample", "Rows for the imbalance comparison", "int", default=0,
             note="0 means every row. On this machine a cap of 40,000 is the safe setting.",
             heavy_above=200_000),
        Knob("no-imbalance", "Skip the imbalance comparison", "flag", default=False),
        Knob("no-bracket", "Skip the stratified-random bracket", "flag", default=False),
        Knob("no-perm", "Skip permutation importance", "flag", default=False,
             note="Permutation importance is the slow part."),
    ),
    records=("*/split-checks-*.md", "*/split-audit-*.md"),
    runtime="one to ten minutes, depending on the row cap",
)

JOB_TUNE = Job(
    key="tune",
    script="model_assessment_1h.py",
    title="Sweep the probability model",
    blurb=(
        "Fits one model at every combination in the grid, twice at each point: "
        "once in sample for the training error, once per expanding walk-forward "
        "fold for the cross-validated error. Reports both, and the ratio between "
        "them. The house rule rejects a ratio above 1.1 whatever its error."
    ),
    knobs=(
        Knob("tune", "Which model", "choice", default="histgbm",
             choices=("histgbm", "lightgbm", "rf", "gbm"),
             preset="the script defaults to None, which is a scorecard, not a sweep",
             note="Setting this is what makes the run a sweep rather than a scorecard."),
        Knob("dataset", "Which panel", "panel", default="slice_4h_40k",
             symbolic="build_dataset_1h.DATASET_PATH",
             preset="the 25MB slice, because the 4h panel is two gigabytes"),
        Knob("grid", "The grid to sweep", "text",
             default="learning_rate=0.03,0.06,0.12 max_leaf_nodes=15,31 max_iter=200",
             preset="the six settings of the 8 September sweep, so its record replays",
             note="Blank sweeps the model's own entry in TUNE_GRIDS, which for histgbm "
                  "is eighteen combinations. This is the six that ran on 8 September."),
        Knob("rows", "Row cap, most recent", "int", default=15_000, heavy_above=40_000,
             preset="the script has no cap; this machine needs one",
             note="15,000 finished in 330 seconds. The full panel was killed five times."),
        Knob("cv-splits", "Walk-forward folds", "int", default=3, symbolic="CV_SPLITS",
             preset="the 8 September sweep used three folds while the script defaults to five",
             note="The fold count moves the held-out error more than any setting in the "
                  "grid does: three folds gives 0.4840 and five gives 0.4894 on the same "
                  "configuration, against a grid that spans 0.033 in total."),
    ),
    records=("*/model-tuning-*.md", "*/model-tuning-*.json"),
    runtime="about five minutes at 15,000 rows and six settings",
    reproduces={
        "record": "2026-09-08/model-tuning-histgbm-20260908.md",
        # Three folds, not the shipped five. The committed record did not state
        # its fold count and could not be replayed from the command line at all
        # until --grid existed; at five folds the same configuration returns
        # 0.4894 against the committed 0.4840, while the in-sample column
        # matches to four decimals, which is how the folds were identified.
        "settings": {"tune": "histgbm", "dataset": "slice_4h_40k", "rows": 15_000,
                     "grid": "learning_rate=0.03,0.06,0.12 max_leaf_nodes=15,31 max_iter=200",
                     "cv-splits": 3},
        "column": "CV RMSE",
        "values": [0.4840, 0.4891, 0.4915, 0.5026, 0.5049, 0.5173],
        "tolerance": 0.0005,
    },
)

JOB_TREND_TUNE = Job(
    key="trendtune",
    script="trend_life_tune.py",
    title="Sweep the duration model",
    blurb=(
        "The same sweep against a different target. Not whether the price rose, "
        "which is a binary outcome, but how many bars the current trend had left "
        "before the Supertrend reversed, which is a duration, or time to event. "
        "Held-out error is in bars, so it reads directly. Note a defect in the "
        "target rather than in the sweep: observations whose duration exceeds 120 "
        "bars are DROPPED from the sample rather than treated as right-censored, "
        "so the longest-lived trends are selected out on the value of the outcome "
        "itself and every estimate is biased toward shorter durations."
    ),
    knobs=(
        Knob("frame", "Bar size", "choice", default="4h", choices=("4h", "1d", "eq1d")),
        Knob("coins", "How many assets", "int", default=40, heavy_above=100),
        Knob("folds", "Walk-forward folds", "int", default=3, heavy_above=6,
             note="More folds is a better answer and a longer wait."),
        Knob("rows", "Row cap", "int", default=250_000, heavy_above=40_000,
             note="The fold matters roughly forty times more than the setting here, "
                  "which is the reason the sweep is scored on folds at all."),
    ),
    records=("*/trend-life-tuning-*.md", "*/model-tuning-*.md"),
    runtime="minutes at a small row cap, much longer above 40,000",
)

JOB_VARSELECT = Job(
    key="varselect",
    script="variable_selection.py",
    title="Screen the variables",
    blurb=(
        "Runs an elastic net over the training split only, draws the "
        "cross-validation curve and the coefficient paths, keeps what survives "
        "at one standard error from the best penalty, and refits the survivors "
        "for confidence intervals. The blind year is never touched."
    ),
    knobs=(
        Knob("sample", "Row sample", "int", default=25_000, heavy_above=100_000),
        Knob("l1", "Mixing, 1 is lasso and 0 is ridge", "float", default=1.0,
             note="Between the two is the elastic net proper."),
        # The four figures are written to fixed names, so a run at a different
        # sample size replaces the figures the previous record documents. The
        # knob lets a trial run be sent somewhere else.
        Knob("out", "Where to write", "text", default=None,
             note="Blank writes to 04-outputs/AA-evals/varselect/, replacing the "
                  "figures already there. Give a path to keep those."),
    ),
    records=("varselect/*.md", "varselect/*.png", "varselect/*.html"),
    runtime="under two minutes at 25,000 rows",
)

JOB_ASSESS = Job(
    key="assess",
    script="model_assessment_1h.py",
    title="Resample regime",
    blurb=(
        "Fits every model in the zoo, reports RMSE and MAE on the predicted "
        "probabilities in sample and cross-validated, and the overfit ratio "
        "between them. Selection happens inside the set that passes 1.1."
    ),
    knobs=(
        Knob("dataset", "Which panel", "panel", default="", symbolic="build_dataset_1h.DATASET_PATH"),
        Knob("models", "Which models", "multi", default=None, choices=tuple(ZOO),
             note="Nothing ticked runs the whole zoo."),
        Knob("cv-splits", "Cross-validation folds", "int", default=5, symbolic="CV_SPLITS"),
        Knob("rows", "Row cap, most recent", "int", default=None, heavy_above=200_000,
             note="Blank means the whole panel, which on the 4h frame is two gigabytes."),
    ),
    records=("*/model-assessment-*.md", "*/model-metrics-*.json"),
    runtime="two minutes on the slice, over fifteen on a full panel",
    reproduces={
        "record": "2026-09-06/model-assessment-20260906.md",
        "fields": {"rmse_ratio_reject": 1.1},
    },
)

JOB_CALIBRATE = Job(
    key="calibrate",
    script="calibration.py",
    title="Calibration and reliability",
    blurb=(
        "Assesses calibration: whether a stated probability matches the observed "
        "frequency of the outcome. "
        "Reports reliability by decile, expected and maximum calibration error, "
        "Murphy's decomposition of the Brier score, then fits Platt and "
        "isotonic maps on held-out data and scores them once on the blind year."
    ),
    knobs=(
        Knob("interval", "Bar size", "choice", default="4h", choices=("5m", "15m", "1h", "4h", "1d")),
        Knob("rows", "Row cap", "int", default=120_000, heavy_above=120_000),
        Knob("unbalanced", "Drop the balanced class weight", "flag", default=False,
             note="On 8 September this one argument cut the calibration error from 0.2344 to 0.0736."),
    ),
    records=("*/calibration-*.md", "*/calibration-*.png"),
    runtime="three to six minutes",
    reproduces={
        "record": "2026-09-08/calibration-4h-balanced-20260908.md",
        # 60,000, not the script's default of 120,000. The committed record
        # says it fitted 48,000 observations and calibrated on 12,000, which is
        # a 60,000-row training window split four to one. Written as 120,000
        # here first, the reproduction check failed by 0.246 on ECE and looked
        # like a broken result; it was a wrong citation of the settings.
        "settings": {"interval": "4h", "rows": 60_000, "unbalanced": False},
        "column": "raw row of the summary table",
        "values": [0.2344, 0.7005, 0.2586],
        "tolerance": 0.0005,
    },
)

JOB_EDGE = Job(
    key="edge",
    script="edge_diagnostics.py",
    title="Score the edge",
    blurb=(
        "The money test. Reports expectancy per trade before costs against a "
        "coin flip and a one-bar persistence baseline, the same after costs by "
        "era, and how the return per trade moves as the confidence threshold "
        "rises."
    ),
    knobs=(
        Knob("interval", "Bar size", "choice", default="4h", choices=("5m", "15m", "1h", "4h", "1d")),
        Knob("cv-splits", "Cross-validation folds", "int", default=5),
        Knob("rows", "Row cap, most recent", "int", default=None, heavy_above=200_000),
    ),
    records=("*/edge-diagnostics-*.md", "*/edge-diagnostics-*.png"),
    runtime="five to twenty minutes by frame",
)

JOB_UNIVARIATE = Job(
    key="univariate",
    script="univariate_screen.py",
    title="Screen each predictor alone",
    blurb=(
        "Fits every offered column on its own against an intercept-only model "
        "and tests it by likelihood ratio, chi-squared on one degree of freedom. "
        "Reports the estimate in log-odds with its interval, on standardised "
        "columns so the magnitudes compare, ranked by magnitude."
    ),
    knobs=(
        Knob("rows", "Training rows to fit on", "int", 25_000, heavy_above=60_000,
             note="0 uses every row in the training window. The blind period is "
                  "never opened."),
    ),
    records=("varselect/univariate-*.md", "varselect/univariate-*.json"),
    runtime="under a minute at 25,000 rows",
)

RUNNABLE = (JOB_SPLIT, JOB_TUNE, JOB_TREND_TUNE, JOB_VARSELECT, JOB_UNIVARIATE,
            JOB_ASSESS, JOB_CALIBRATE, JOB_EDGE)

# The allow list the runner enforces. Anything absent cannot be launched.
ALLOWED = {j.script for j in RUNNABLE}

# Named so a reader can see the exclusion was deliberate rather than an
# oversight. These place or amend real orders and are not reachable from a
# browser form, at any setting.
NEVER_RUNNABLE = ("alpaca_trade.py", "trade_binance.py", "paper_trade.py",
                  "schedule_tick.py")


# ---------------------------------------------------------------------------
# Six panels in three columns of two, to the operator's specification of
# 9 September 2026 in 05-research/tasks/eval-control-centre-v2.md.
#
# What was nine is six. Two merges, and neither loses anything:
#
#   C1 Model and scoreboard   = Performance + Tuning + Scoreboard
#   C2 History                = Assessment + Live book
#
# The seam falls where the subjects divide rather than where the old panels
# did. Performance, Tuning and the Scoreboard all concern the current fit and
# where everything stands now; Assessment compares runs across configurations
# and over time, which is the same subject as the history of model testing and
# reads from the same records. The distinction the operator insisted on twice,
# that Performance is one model's error at one configuration computed now while
# Assessment is every run's error compared across configurations, is now carried
# by the layout instead of by discipline inside a single panel.
#
# The three panels of the old column A are gone as panels. Their content did not
# vanish: the cost per round trip is stated on A1 against the bar size it bears
# on, the label geometry against the horizon, and the acceptance criteria
# against the fold bar. Stated where they bear on a choice rather than occupying
# a panel apiece.
#
# `charts` names the top row, four across as on every panel, chosen as the
# headline of each thing the panel came from. `groups` names the rest, under the
# heading of the panel they came from, and every one of them still expands.
# Every panel that reports a result draws at least one chart, which is check 9
# and the answer to a page of fifteen panels that drew nothing at all.
# ---------------------------------------------------------------------------

CARDS = (
    # --- A. Inputs ---------------------------------------------------------
    Card("A1", "A", "c-setup", "Data", "sources, timeline, screening",
         "Which market, which bar size, which archive and which symbols; the "
         "history available and where the training window and the blind period "
         "fall; and which assets are eligible at each bar. The cost of a round "
         "trip is stated against the bar size, the label geometry against the "
         "horizon, and the acceptance criteria against the fold bar, each where "
         "it bears on the choice rather than in a panel of its own.",
         sections=("data", "label", "screen"),
         charts=("data-cube", "cost-by-frame", "timeline-span", "label-base-rate",
                 "candles-barrier", "screen-survivors", "panel-coverage",
                 "cross-sectional-spread"),
         evidence=("*/panel-profile-*.md", "*/candidate-screen-*.md",
                   "*/cross-sectional-*.md", "*/edge-attribution-*.md"),
         reading=(("Archive crawler", "03-inputs/acquire_vision.py"),
                  ("Alpaca daily bars", "03-inputs/alpaca_data.py"),
                  ("Panel profiling", "03-inputs/profile_panel.py"),
                  ("The screen and the label", "03-inputs/build_dataset_1h.py"),
                  ("Cross-sectional ranking", "03-inputs/cross_sectional_4h.py"))),

    Card("A2", "A", "c-comp", "Features and indicators", "what is offered",
         "Which columns are offered to the model, by family and by name, and "
         "the indicator engines behind several of them: MACD, the Supertrend "
         "family, Fibonacci retracements and the confluence score that counts "
         "how many agree. Selection only, not weighting: a tree model ignores a "
         "monotone rescaling of a column. Relative strength against bitcoin is "
         "the strongest family measured so far, by a factor of three, and the "
         "only one not derived from the asset's own price.",
         sections=("features", "signals"),
         charts=("candles-volume", "indicator-overlay", "family-composition",
                 "family-importance", "confluence-agreement", "candles-regimes"),
         table="features",
         controls=("filter the table", "sort any column", "explain on hover"),
         evidence=("*/feature-report-*.md", "*/feature-report-*.csv",
                   "*/analysis-*.md"),
         reading=(("Every feature block", "03-inputs/build_dataset_1h.py"),
                  ("Feature scoring", "03-inputs/feature_report.py"),
                  ("MACD engine", "04-outputs/1A-macd/macd.py"),
                  ("Confluence engine", "04-outputs/1B-confluence/confluence.py"),
                  ("Fibonacci engine", "04-outputs/1C-fibonacci/fib.py"))),

    # --- B. Fitting --------------------------------------------------------
    # Variable selection moved out of Inputs and into Fitting on 9 September
    # 2026. It is not an input: it is the first thing done to the inputs, and it
    # decides what the training regime next door is given.
    Card("B1", "B", "c-thr", "Variable selection", "ranked by magnitude",
         "The last screening stage. Each candidate is fitted alone, tested "
         "against an intercept-only null by likelihood ratio, and ranked by the "
         "magnitude of its estimate. An elastic net then decides which survive "
         "together. Training window only; the blind period is never consulted.",
         section="selection",
         jobs=(JOB_UNIVARIATE, JOB_VARSELECT),
         charts=("univariate-ranking", "coefficient-intervals", "enet-path",
                 "lr-distribution"),
         evidence=("varselect/*.md", "varselect/*.png"),
         reading=(("Elastic-net screen", "03-inputs/variable_selection.py"),
                  ("The univariate screen", "03-inputs/univariate_screen.py"),
                  ("The bench's screen", "03-inputs/bench_run.py"))),

    Card("B2", "B", "c-conf", "Training regime", "split and folds",
         "Chronological, never random: returns are autocorrelated, so a random "
         "partition puts later observations in training and leaks. The blind "
         "period, the embargo at the cut, the fold count and the fold scheme.",
         section="split",
         # regime-advance is the fold advancing through the panel's own dates,
         # one frame per step, and regime-uncertainty fits every one of those
         # folds so the width of the estimate can be read moving with them.
         # Both answer the operator's 9 September instruction that the split be
         # demonstrated the way caret demonstrates it, and that the demonstration
         # show the uncertainty changing over time rather than a static picture.
         charts=("regime-demo", "regime-advance", "split-diagram",
                 "fold-coverage", "regime-uncertainty"),
         evidence=("*/split-checks-*.md",),
         reading=(("The splitter", "03-inputs/train_model_1h.py"),
                  ("The regimes", "03-inputs/bench_run.py"),
                  ("Walk-forward splitter", "03-inputs/wf_splitter.py"))),

    # --- C. Results --------------------------------------------------------
    # The first merge. Fourteen charts, two configuration sections, six jobs and
    # two tables, from three panels. The top row is the headline of each: this
    # model's error, how the hyperparameters moved it, what the 1.1 overfit bar
    # costs, and every fit ever scored against a constant forecast.
    Card("C1", "C", "c-thr", "Model and scoreboard", "fitted, tuned, scored",
         "One model's error at one configuration, computed now; the sweep that "
         "moved it; and every fit ever scored, against a constant forecast. "
         "Five measures are computed twice on the same predictions, in sample "
         "and cross-validated, then once more on the blind period, and Theil's "
         "U2 below one is the only one that says the model beat a constant. The "
         "house rule rejects an overfit ratio above 1.1 whatever its error, and "
         "selection runs inside the set that passes. The history of these fits "
         "over time is next door, because that is a different question.",
         sections=("calibration", "model"),
         jobs=(JOB_ASSESS, JOB_CALIBRATE, JOB_SPLIT, JOB_TUNE, JOB_TREND_TUNE,
               JOB_EDGE),
         charts=("error-full-vs-cv", "hyper-response", "overfit-vs-error",
                 "scoreboard"),
         groups=(
             Group("performance", "Performance",
                   "What did this model score, at this configuration, now? "
                   "Every number here comes from the most recent run and none "
                   "of it is compared against an earlier one.",
                   charts=("reliability-curve", "kde-separation", "kde-spread",
                           "kde-null-band"),
                   table="performance"),
             Group("tuning", "Tuning",
                   "What did the sweep find as the hyperparameters moved, and "
                   "is the winner separable from the runner-up at all?",
                   charts=("sweep-ranking", "tuning-stability",
                           "capacity-vs-error")),
             Group("scoreboard", "Scoreboard",
                   "Where does everything stand? Every configuration ever "
                   "fitted, against always predicting the base rate.",
                   charts=("best-by-estimator", "rmse-by-verdict",
                           "fits-by-config"),
                   table="scoreboard",
                   controls=("filter the table", "sort any column",
                             "explain on hover")),
         ),
         evidence=("*/bench-2*.md", "*/model-assessment-*.md",
                   "*/calibration-*.md", "*/bench-sweep-*.md",
                   "*/model-tuning-*.md", "evaluation-scores.md"),
         reading=(("The runner", "03-inputs/bench_run.py"),
                  ("Metric definitions", "03-inputs/model_metrics.py"),
                  ("Calibration", "03-inputs/calibration.py"),
                  ("Kernel estimates", "03-inputs/kde_metrics.py"),
                  ("The sweep", "03-inputs/bench_sweep.py"),
                  ("Hyperparameter surface", "03-inputs/bench_config.py"),
                  ("The scoreboard", "04-outputs/AA-evals/evaluation-scores.md"))),

    # The second merge. Sixteen charts, the largest panel on the board, so its
    # sections carry more weight than C1's. The project's own movement is put
    # first because it is the part the operator reads, and burying it under five
    # charts of per-run comparison would be the obvious way to lose it.
    Card("C2", "C", "c-out", "History", "over configurations and over time",
         "Every run's error compared across configurations and over time, and "
         "the history of the project that produced them. This is where the "
         "class weight was found to move held-out error nearly as far as the "
         "whole nine-parameter forest space. The calendar counts every record "
         "written under a dated folder and dates each by that folder rather "
         "than by its modification time. The paper trading book keeps its own "
         "history and is not merged in, because merging it would change what "
         "the calendar counts.",
         section="viz",
         # The top row leads on dollars. Operator instruction, 9 September 2026:
         # gains and losses are reported in dollar amounts, on each position and
         # in total, and that is the row a reader sees without opening a panel.
         charts=("money-waterfall", "money-by-position", "best-over-time",
                 "milestone-track"),
         groups=(
             Group("money", "The money",
                   "What the paper account gained and lost, in dollars, on "
                   "each holding and in total. Every other table on this board "
                   "measures model error; this one measures money. A 16 per "
                   "cent fall on a 1.5 per cent holding and a 2 per cent fall "
                   "on a 12 per cent holding are the same dollars, and only "
                   "this section says which.",
                   charts=("money-curve", "money-closed"),
                   table="money",
                   controls=("filter the table", "sort any column")),
             Group("livebook", "Live book",
                   "How the whole project has moved: what has been tried, "
                   "when, and what the best result available on any given day "
                   "was. This section comes first because it is the part that "
                   "gets read.",
                   charts=("run-calendar", "run-ranking", "evidence-growth",
                           "headline-history", "what-has-been-tried",
                           "milestones-by-kind", "record-kinds"),
                   controls=("calendar or ranking", "filter by kind")),
             Group("assessment", "Assessment",
                   "What each run scored, and how the runs compare against "
                   "each other once the "
                   "configuration changes: which axis moved the answer, and "
                   "where each configuration places against the ones it "
                   "replaced.",
                   charts=("config-effect", "overfit-vs-blind", "sweep-grid",
                           "config-rank-spread", "weight-paired",
                           "assessment-compact", "capacity-vs-error"),
                   table="assessment"),
         ),
         evidence=("*/bench-sweep-*.md", "*/bench-2*.md", "*/DAILY-*.md",
                   "*/execution-report-*.md"),
         reading=(("The digest", "03-inputs/bench_digest.py"),
                  ("The sweep runner", "03-inputs/bench_sweep.py"),
                  ("Milestones", "03-inputs/milestones.py"),
                  ("Book state", "05-research/memory/alpaca-book-state.json"),
                  ("The digest on disk", "04-outputs/AA-evals/bench-digest.md"),
                  ("The historic scoreboard",
                   "04-outputs/AA-evals/evaluation-scores.md"))),
)


CARDS_BY_KEY = {c.key: c for c in CARDS}
JOBS_BY_KEY = {j.key: j for j in RUNNABLE}


def lane_cards(lane: str) -> list[Card]:
    return [c for c in CARDS if c.lane == lane]


# --------------------------------------------------------------------------
# Reading a script's own argparse defaults, without importing it.
#
# Importing model_assessment_1h to ask what --rows defaults to would pull in
# pandas, lightgbm and scikit-learn, which on this machine is most of a
# gigabyte inside the web process. The ast module reads the same answer off the
# source text for nothing.
# --------------------------------------------------------------------------

def script_defaults(script: str) -> dict[str, Any]:
    """Flag name to default, for every add_argument in a script.

    A default written as an expression rather than a literal, such as
    bd.DATASET_PATH, comes back as the source text of that expression with a
    leading "=", so the caller can tell "the literal string bd.DATASET_PATH"
    from "a symbol I could not evaluate".
    """
    src = (SCRIPTS / script).read_text(encoding="utf-8")
    tree = ast.parse(src)

    # A default written as a bare name defined in the same file, such as
    # CV_SPLITS = 5, is resolvable and worth resolving: left unresolved the
    # command builder cannot tell that a form showing 5 matches the script and
    # emits --cv-splits 5 on every run. A dotted name from another module, such
    # as bd.DATASET_PATH, stays unresolved and is reported as symbolic.
    consts: dict[str, Any] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            try:
                consts[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, SyntaxError):
                pass

    out: dict[str, Any] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_argument"):
            continue
        names = [a.value for a in node.args
                 if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        longs = [n for n in names if n.startswith("--")]
        if not longs:
            continue
        flag = longs[0].lstrip("-")
        default: Any = None
        action = None
        for kw in node.keywords:
            if kw.arg == "action" and isinstance(kw.value, ast.Constant):
                action = kw.value.value
            if kw.arg != "default":
                continue
            try:
                default = ast.literal_eval(kw.value)
            except (ValueError, SyntaxError):
                if isinstance(kw.value, ast.Name) and kw.value.id in consts:
                    default = consts[kw.value.id]
                else:
                    default = "=" + ast.unparse(kw.value)
        if action == "store_true" and default is None:
            default = False
        out[flag] = default
    return out


_DEFAULT_CACHE: dict[str, dict] = {}


def _script_default(job: "Job", knob: "Knob"):
    """What the script itself would do if the flag were left off.

    This, not the form's default, decides whether a flag is emitted. The form
    may arrive preset to something the script would not have chosen, and on the
    sweep panel it does: --tune shows histgbm while the script defaults to None.
    Comparing against the form's own default would have dropped that flag and
    quietly run the scorecard instead of the sweep. Found by check 5a on
    8 September, before the button was ever pressed.
    """
    if job.script not in _DEFAULT_CACHE:
        _DEFAULT_CACHE[job.script] = script_defaults(job.script)
    got = _DEFAULT_CACHE[job.script].get(knob.flag, None)
    if isinstance(got, str) and got.startswith("="):
        return None                     # an expression: treat as "no literal default"
    return got


def build_command(job: Job, values: dict[str, Any]) -> list[str]:
    """Compose the command line for one run.

    A knob left where the script would have left it contributes nothing, so the
    command reads as the difference from the script's own behaviour. Every value
    is placed as its own argv element, so nothing is ever passed through a
    shell.
    """
    cmd = [PYTHON, str(Path("03-inputs") / job.script)]
    for knob in job.knobs:
        raw = values.get(knob.flag, None)
        base = _script_default(job, knob)
        if knob.kind == "flag":
            if bool(raw) != bool(base):
                cmd.append(f"--{knob.flag}")
            continue
        if raw in (None, "", [], ()):
            continue
        if knob.kind == "panel":
            if raw not in PANELS:
                raise ValueError(f"unknown panel: {raw!r}")
            cmd += [f"--{knob.flag}", PANELS[raw]]
            continue
        if knob.kind == "choice":
            if raw not in knob.choices:
                raise ValueError(f"{knob.flag}: {raw!r} is not one of {knob.choices}")
            if raw == base:
                continue
            cmd += [f"--{knob.flag}", str(raw)]
            continue
        if knob.kind == "multi":
            chosen = [v for v in (raw if isinstance(raw, (list, tuple)) else [raw])
                      if v in knob.choices]
            if not chosen:
                continue
            cmd += [f"--{knob.flag}", *chosen]
            continue
        if knob.kind == "int":
            val: Any = int(raw)
        elif knob.kind == "float":
            val = float(raw)
        else:
            val = str(raw)
        if base is not None and val == base:
            continue
        cmd += [f"--{knob.flag}", str(val)]
    return cmd


def records_for(globs) -> list[Path]:
    """Every record matching these patterns, newest first."""
    hits: list[Path] = []
    for g in globs:
        hits += list(EVALS.glob(g))
    # The repository lives on an exFAT volume, which cannot store extended
    # attributes, so macOS drops a "._" companion beside every file it writes.
    # They are junk, they are git-ignored, and left in they would show up as
    # half the records on a panel.
    hits = [p for p in hits if p.is_file() and not p.name.startswith("._")]
    hits.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return hits


def repo_rel(path) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO))
    except ValueError:
        return str(path)


LOG_DIR = EVALS / "logs"


def env_for_run() -> dict:
    """The environment a job inherits.

    LIVE_TRADING is forced off for anything the control centre launches. None
    of the registered scripts places an order, so this is belt and braces, but
    a belt costs one line.
    """
    env = dict(os.environ)
    env["LIVE_TRADING"] = "false"
    env["MPLBACKEND"] = "Agg"
    env["PYTHONUNBUFFERED"] = "1"
    return env
