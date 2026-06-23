"""wf_splitter.py - Stage C: time-aware walk-forward splitting and evaluation.

Replaces any random or stratified split with a chronological, forward-chained walk-forward
design. It is the multi-fold, regime-stability companion to train_model_1h.split() (which
holds out a single final year for the headline GO/NO-GO). Where that answers "does an edge
survive the most recent year", this answers "is the edge stable across regimes, or does it
live in one". See tasks/task-request-data-pipeline-methodology.md (Stage C).

Design (all from the task request):
  C.2  Expanding- or rolling-window walk-forward. Boundaries are CALENDAR dates shared
       across all coins. Train on the earliest block, test on the next, slide forward.
  C.3  Purge / embargo at every cut, sized to max(longest feature lookback, label horizon)
       bars, taken from build_dataset_1h so it can never drift from the features that set it.
       Bars within that distance of the seam share information across the split.
  C.4  Split on TIME, not on coins. A coin appears in both train and test, but only its
       earlier bars train and its later bars test. No whole-coin holdout (that answers a
       different question and is left as a separately-scoped experiment).
  C.5  Per-fold reporting, weighted/annotated by coin count, so a thin early fold is not
       read as equal evidence to a broad later one.
  Universe: each fold draws its eligible coins from the point-in-time per-fold universe
       lists produced by profile_panel (Stage B.7), so membership never depends on the
       future. Falls back to all coins if no universe map is supplied.
  Transforms: fit on TRAIN ONLY and apply forward (scale_fit_apply / a train-fit Pipeline).
       Nothing past the training cutoff may leak backward into features or scaling.

Why NOT stratified sampling (the C.1 rationale, also exposed as METHODOLOGY for the notebook):
  The data-generating process drifts. 2017-18 ICO mania, the 2021 bull, the 2022
  deleveraging, and the current regime are different processes. A split that interleaves
  test bars among training bars borrows the future to predict the past and yields an error
  estimate that will not survive live trading. Stratifying on variance forces similar class
  proportions across splits by drawing regardless of time, destroying the temporal ordering
  that is the whole object of interest. It measures interpolation within a known
  distribution; the question that matters is extrapolation forward into an unknown regime.
  Only a forward-chained split measures that.

Plain ASCII. No orders, read-only. The headline model GO/NO-GO remains the final-year OOS
in train_model_1h; this module is the regime-stability lens on top of it.
"""
from __future__ import annotations

import argparse
import json
import math
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))

TIME_COL = "datetime"
GROUP_COL = "symbol"
LABEL_COL = "label"


# --------------------------------------------------------------------------- #
# Purge / embargo sized from the actual feature + label windows (C.3)
# --------------------------------------------------------------------------- #
def purge_embargo_bars() -> tuple[int, int, int]:
    """Return (purge_bars, longest_feature_bars, label_horizon_bars). The purge is
    max(longest feature lookback, label horizon); reading the windows from build_dataset_1h
    guarantees it tracks the features that actually set it."""
    try:
        import build_dataset_1h as b1
        longest_feat = max([b1.WC["ema_slow"], b1.WC["rsi"], b1.WC["atr"], b1.WC["rv_long"]]
                           + list(b1.WC["mom"]))
        horizon = b1.LABEL["horizon_bars"]
        bpd = b1.BARS_PER_DAY
    except Exception:
        longest_feat, horizon, bpd = 125 * 24, 48, 24
    return max(longest_feat, horizon), longest_feat, horizon


def purge_embargo_days(bars_per_day: int = 24) -> int:
    p, _, _ = purge_embargo_bars()
    return int(math.ceil(p / bars_per_day))


# --------------------------------------------------------------------------- #
# Universe matching (Stage B lists carry both 'BTCUSDT' and 'BTC/USDT' forms)
# --------------------------------------------------------------------------- #
def _universe_for(fold_open: pd.Timestamp, universes: dict | None, dataset_uses_slash: bool):
    """Pick the point-in-time universe whose fold-open date is the latest at/<= this fold's
    open, and return it in the symbol form the dataset uses. None means 'all coins'."""
    if not universes:
        return None
    keys = sorted(universes)
    chosen = None
    for k in keys:
        if pd.Timestamp(k).tz_localize("UTC") <= fold_open:
            chosen = k
    chosen = chosen or keys[0]
    entry = universes[chosen]
    if isinstance(entry, dict):                       # {"raw":[...], "slash":[...]}
        return set(entry["slash"] if dataset_uses_slash else entry["raw"])
    # plain list: infer form from the first element
    has_slash = bool(entry) and "/" in entry[0]
    if has_slash == dataset_uses_slash:
        return set(entry)
    if dataset_uses_slash:
        return {f"{s[:-4]}/USDT" if s.endswith("USDT") else s for s in entry}
    return {s.replace("/", "") for s in entry}


# --------------------------------------------------------------------------- #
# The splitter (C.2 / C.3 / C.4)
# --------------------------------------------------------------------------- #
class WalkForwardSplitter:
    """Forward-chained walk-forward splitter on shared calendar boundaries.

    Parameters
    ----------
    n_folds        number of out-of-sample test windows
    test_days      length of each test window in calendar days
    scheme         'expanding' (train = all history before the cut) or
                   'rolling'   (train = the trailing `train_days` before the cut)
    train_days     trailing train length for the rolling scheme (ignored if expanding)
    embargo_days   purge/embargo band; defaults to purge_embargo_days() = max(feature
                   lookback, label horizon) in days
    usable_start   drop all bars before this date (the thin-panel cutoff from B.9)
    universes      Stage B.7 per-fold universe map {iso_date: [...] or {"raw","slash"}}
    embargo_test_side  also drop the leading `embargo` of each test window. Off by default:
                   in a pure forward chain training is always BEFORE test, so the operative
                   leak is train labels reaching forward across the cut, which the train-side
                   purge removes; dropping OOS from the test side only discards evidence.
    """

    def __init__(self, n_folds=5, test_days=120, scheme="expanding", train_days=540,
                 embargo_days=None, usable_start=None, universes=None,
                 time_col=TIME_COL, group_col=GROUP_COL, embargo_test_side=False):
        self.n_folds = n_folds
        self.test_days = test_days
        self.scheme = scheme
        self.train_days = train_days
        self.embargo_days = embargo_days if embargo_days is not None else purge_embargo_days()
        self.usable_start = pd.Timestamp(usable_start).tz_localize("UTC") if usable_start else None
        self.universes = universes
        self.time_col = time_col
        self.group_col = group_col
        self.embargo_test_side = embargo_test_side

    def _boundaries(self, t0, tN):
        """The n_folds test windows are the last n_folds blocks of `test_days`, ending at tN.
        Returns a list of (test_start, test_end) calendar pairs, earliest first."""
        td = pd.Timedelta(days=self.test_days)
        bounds = []
        end = tN
        for _ in range(self.n_folds):
            start = end - td
            bounds.append((start, end))
            end = start
        return list(reversed(bounds))

    def split(self, df: pd.DataFrame):
        """Yield one dict per fold with positional train/test indices into `df` (sorted by
        time), the calendar windows, the fold universe, and the coin count (for C.5)."""
        d = df.sort_values(self.time_col).reset_index(drop=True)
        t = pd.to_datetime(d[self.time_col])
        if t.dt.tz is None:
            t = t.dt.tz_localize("UTC")
        t0 = t.min() if self.usable_start is None else max(t.min(), self.usable_start)
        tN = t.max()
        emb = pd.Timedelta(days=self.embargo_days)
        dataset_uses_slash = bool(len(d)) and "/" in str(d[self.group_col].iloc[0])
        pos = np.arange(len(d))

        for i, (ts, te) in enumerate(self._boundaries(t0, tN)):
            uni = _universe_for(ts, self.universes, dataset_uses_slash)
            in_uni = d[self.group_col].isin(uni).values if uni is not None else np.ones(len(d), bool)

            test_lo = ts + emb if self.embargo_test_side else ts
            test_mask = (t >= test_lo).values & (t < te).values & in_uni
            train_hi = ts - emb                                   # purge the band before the cut
            if self.scheme == "rolling":
                train_lo = ts - pd.Timedelta(days=self.train_days) - emb
                train_mask = (t >= max(t0, train_lo)).values & (t <= train_hi).values & in_uni
            else:                                                 # expanding
                train_mask = (t >= t0).values & (t <= train_hi).values & in_uni

            tr, teidx = pos[train_mask], pos[test_mask]
            if len(tr) == 0 or len(teidx) == 0:
                continue
            n_coins = int(d.loc[teidx, self.group_col].nunique())
            yield dict(fold=i, train_idx=tr, test_idx=teidx,
                       train_span=(t.iloc[tr].min(), t.iloc[tr].max()),
                       test_span=(ts, te), embargo_days=self.embargo_days,
                       n_train=len(tr), n_test=len(teidx), n_coins=n_coins,
                       scheme=self.scheme)

    def fold_table(self, df: pd.DataFrame) -> pd.DataFrame:
        """Composition audit: one row per fold (spans, sizes, coin count). The C.5 evidence
        that thin folds are not equal to broad ones."""
        rows = []
        for f in self.split(df):
            rows.append(dict(fold=f["fold"],
                             train_start=f["train_span"][0].date(), train_end=f["train_span"][1].date(),
                             test_start=f["test_span"][0].date(), test_end=f["test_span"][1].date(),
                             n_train=f["n_train"], n_test=f["n_test"], n_coins=f["n_coins"],
                             embargo_days=f["embargo_days"]))
        return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Train-only transform (nothing past the cut leaks into scaling)
# --------------------------------------------------------------------------- #
def scale_fit_apply(train_X: pd.DataFrame, test_X: pd.DataFrame):
    """Standardise with statistics fit on TRAIN ONLY, applied forward to test. The minimal
    form of 'fit all transforms on train only'; any sklearn transformer must follow the same
    rule (fit on train rows, transform test)."""
    mu = train_X.mean()
    sd = train_X.std().replace(0, 1.0)
    return (train_X - mu) / sd, (test_X - mu) / sd, dict(mean=mu, std=sd)


# --------------------------------------------------------------------------- #
# Per-fold evaluation and coin-count-weighted summary (C.5)
# --------------------------------------------------------------------------- #
def evaluate_walkforward(df, feat_cols, splitter: WalkForwardSplitter,
                         label_col=LABEL_COL, model=None, verbose=True) -> pd.DataFrame:
    """Fit `model` (default LightGBM, else logistic) on each fold's train and score AUC +
    buy-precision on its test. Reports per fold AND a coin-count-weighted aggregate, so
    regime dependence is visible rather than hidden in a single pooled number."""
    from sklearn.metrics import roc_auc_score
    if model is None:
        try:
            from lightgbm import LGBMClassifier
            mk = lambda: LGBMClassifier(n_estimators=200, num_leaves=31, learning_rate=0.05,
                                        subsample=0.8, colsample_bytree=0.8, n_jobs=-1, verbose=-1)
        except Exception:
            from sklearn.linear_model import LogisticRegression
            mk = lambda: LogisticRegression(max_iter=1000)
    else:
        mk = lambda: model

    d = df.sort_values(splitter.time_col).reset_index(drop=True)
    rows = []
    for f in splitter.split(d):
        tr, te = f["train_idx"], f["test_idx"]
        Xtr, ytr = d.loc[tr, feat_cols], d.loc[tr, label_col]
        Xte, yte = d.loc[te, feat_cols], d.loc[te, label_col]
        if yte.nunique() < 2 or ytr.nunique() < 2:
            continue
        Xtr_s, Xte_s, _ = scale_fit_apply(Xtr, Xte)
        clf = mk().fit(Xtr_s, ytr)
        p = clf.predict_proba(Xte_s)[:, 1]
        auc = roc_auc_score(yte, p)
        thr = np.quantile(p, 0.90)                       # top-decile confidence as a buy proxy
        sel = p >= thr
        prec = float(yte[sel].mean()) if sel.any() else float("nan")
        rows.append(dict(fold=f["fold"], test_start=f["test_span"][0].date(),
                         test_end=f["test_span"][1].date(), n_coins=f["n_coins"],
                         n_test=f["n_test"], base_rate=round(float(yte.mean()), 3),
                         auc=round(auc, 3), buy_precision=round(prec, 3),
                         lift=round(prec - float(yte.mean()), 3)))
        if verbose:
            print(f"  fold {f['fold']}: {rows[-1]['test_start']}..{rows[-1]['test_end']} "
                  f"coins={f['n_coins']:3d} AUC={auc:.3f} prec={prec:.3f}")
    tab = pd.DataFrame(rows)
    if not tab.empty:
        w = tab["n_coins"]
        wmean = lambda c: float(np.average(tab[c], weights=w))
        if verbose:
            print(f"  coin-weighted: AUC={wmean('auc'):.3f} buy_precision={wmean('buy_precision'):.3f} "
                  f"lift={wmean('lift'):+.3f}  (unweighted AUC={tab['auc'].mean():.3f})")
        tab.attrs["weighted_auc"] = wmean("auc")
        tab.attrs["weighted_precision"] = wmean("buy_precision")
    return tab


# --------------------------------------------------------------------------- #
# Stage B artefact loading
# --------------------------------------------------------------------------- #
def _profile_root() -> str:
    """Profile location, read from profile_panel so writer and reader never diverge.
    Falls back to the same main-outputs path if that import is unavailable."""
    try:
        import profile_panel as _pp
        return _pp.PROFILE_ROOT
    except Exception:
        return os.path.join(os.path.dirname(HERE), "outputs", "3A-training-test-data", "panel-profile")


def load_universes(profile_dir: str | None = None) -> dict | None:
    """Load per_fold_universe.json from a Stage B run (or the latest via profile/latest.txt)."""
    if profile_dir is None:
        latest = os.path.join(_profile_root(), "latest.txt")
        if not os.path.exists(latest):
            return None
        profile_dir = open(latest).read().strip()
    path = os.path.join(profile_dir, "per_fold_universe.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def load_usable_start(profile_dir: str | None = None):
    """Read the usable_start_date the profiler chose (B.9), if a run exists."""
    if profile_dir is None:
        latest = os.path.join(_profile_root(), "latest.txt")
        if not os.path.exists(latest):
            return None
        profile_dir = open(latest).read().strip()
    path = os.path.join(profile_dir, "decision_summary.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f).get("usable_start_date")


# The C.1 methodology cell, kept here so the notebook can render it verbatim.
METHODOLOGY = """\
## Splitting methodology: forward-chained, not stratified

Objective: estimate out-of-sample performance under REGIME DRIFT, not interpolation within a
known distribution. The data-generating process drifts across time -- the 2017-18 ICO mania,
the 2021 bull run, the 2022 deleveraging, and the current regime are different processes. A
split that interleaves test bars among training bars borrows the future to predict the past
and yields an error estimate that will not survive live trading.

Stratified sampling is rejected. Stratifying on variance forces similar class proportions
across splits by drawing observations regardless of position in time, which destroys the
temporal ordering that is the whole object of interest. It answers "can the model interpolate
within a known distribution"; the question that matters is "can it extrapolate forward into an
unknown regime." Only a forward-chained split measures that.

Design: expanding/rolling walk-forward on shared calendar boundaries; purge/embargo =
max(feature lookback, label horizon) at every cut; split on time not on coins; per-fold
universe drawn point-in-time from the Stage B profile; transforms fit on train only;
per-fold metrics weighted by coin count.
"""


def main():
    p = argparse.ArgumentParser(description="Stage C: walk-forward split audit on the 1h dataset")
    p.add_argument("--dataset", default=None, help="dataset path (default: build_dataset_1h.DATASET_PATH)")
    p.add_argument("--folds", type=int, default=5)
    p.add_argument("--test-days", type=int, default=120)
    p.add_argument("--scheme", choices=["expanding", "rolling"], default="expanding")
    p.add_argument("--train-days", type=int, default=540)
    p.add_argument("--profile-dir", default=None, help="Stage B run dir (default: latest)")
    p.add_argument("--demo-model", action="store_true", help="also fit a model per fold for AUC/precision")
    a = p.parse_args()

    import build_dataset_1h as b1
    path = a.dataset or b1.DATASET_PATH
    df = b1.read_frame(path)
    if df is None:
        raise SystemExit(f"no dataset at {path}")
    if "in_sample" in df.columns:
        df = df[df["in_sample"]].copy()
    feat = b1.feature_columns(df)

    universes = load_universes(a.profile_dir)
    usable_start = load_usable_start(a.profile_dir)
    pb, lf, lh = purge_embargo_bars()
    print(METHODOLOGY)
    print(f"purge/embargo: {pb} bars (feature lookback {lf}, label horizon {lh}) "
          f"= {purge_embargo_days()} days")
    print(f"usable_start: {usable_start} | universes: "
          f"{'loaded' if universes else 'none (all coins)'}\n")

    sp = WalkForwardSplitter(n_folds=a.folds, test_days=a.test_days, scheme=a.scheme,
                             train_days=a.train_days, usable_start=usable_start,
                             universes=universes)
    print(sp.fold_table(df).to_string(index=False))
    if a.demo_model:
        print("\nper-fold model (regime stability):")
        evaluate_walkforward(df, feat, sp)


if __name__ == "__main__":
    main()
