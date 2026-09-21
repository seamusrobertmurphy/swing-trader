"""Execute one bench configuration: data, features, screen, split, fit, calibrate.

    .venv/bin/python 03-inputs/bench_run.py                    # the active config
    .venv/bin/python 03-inputs/bench_run.py --config path.json
    .venv/bin/python 03-inputs/bench_run.py --label "btc majors, no TA-Lib"

Every stage reads bench_config, so the panels that edit a section and the run
that consumes it cannot disagree. The record written at the end embeds the whole
configuration, which is the point: a result that does not carry its settings is
a result nobody can check, and this repository has two committed records that
could not be replayed because their fold count and their row cap lived only in
the session that produced them.

The metric definitions are model_metrics', not this module's, so a number here
and a number on the dashboard mean the same thing. The estimators are built here
rather than taken from model_assessment_1h.model_zoo, because that function
hard-codes class_weight="balanced" and the whole reason this exists is that the
operator wants that argument under their own hand: on 8 September it was costing
two thirds of the calibration error on the metric these models are ranked by.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from datetime import datetime
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench_config as bc          # noqa: E402
import model_metrics as mm         # noqa: E402
import train_model_1h as t1        # noqa: E402

warnings.filterwarnings("ignore")

REPO = bc.REPO
RUNS = REPO / "04-outputs" / "AA-evals"


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def read_capped(path: Path, symbols: list[str], cap: int, log=print) -> pd.DataFrame:
    """The most recent `cap` in-sample rows OF THE REQUESTED SYMBOLS.

    Order matters here and getting it wrong is silent. train_model_1h.load caps
    by reading Parquet row groups from the end of the file, which is the right
    thing for memory on this machine. Filtering to a few symbols afterwards
    leaves whatever share of those rows happened to belong to them, and on the
    four-hour slice a 12,000-row cap returned 64 symbols starting at L, so a run
    asking for bitcoin and ether found neither and aborted saying they were not
    in the panel. They were; they were just not in the tail.

    So the filter goes inside the read. Row groups are still taken from the end
    and the process still never holds the whole panel, but the count that decides
    when to stop is the count of rows the run actually wants.
    """
    if not cap:
        df = t1.load(str(path))
        return df if not symbols else df

    if not symbols or not str(path).endswith(".parquet"):
        return t1.load(str(path), tail_rows=cap)

    import pyarrow.parquet as pq

    wanted = {bc.canonical(s) for s in symbols}
    pf = pq.ParquetFile(str(path))
    chunks, kept, groups = [], 0, 0
    for g in range(pf.num_row_groups - 1, -1, -1):
        c = pf.read_row_group(g).to_pandas()
        groups += 1
        c = c[c["symbol"].map(lambda v: bc.canonical(v) in wanted)]
        if len(c):
            chunks.append(c)
            kept += int(c["in_sample"].sum()) if "in_sample" in c.columns else len(c)
        if kept >= cap:
            break
    if not chunks:
        return pd.DataFrame(columns=pf.schema.names)
    df = pd.concat(chunks[::-1], ignore_index=True).sort_values("datetime")
    if "in_sample" in df.columns:
        df = df[df["in_sample"]]
    df = df.reset_index(drop=True).tail(cap).reset_index(drop=True)
    log(f"  read {groups} of {pf.num_row_groups} row groups to find "
        f"{len(df):,} rows of the requested symbols")
    return df


def load_frame(cfg: dict, log=print):
    """The rows this run covers, and every feature column the frame carries."""
    rel = bc.dataset_path(cfg)
    path = REPO / rel
    if not path.exists():
        raise SystemExit(
            f"no panel at {rel}. Build it first, or choose another bar size on the "
            f"Input data panel.")

    cap = int(cfg["data"].get("rows") or 0)
    syms = bc.symbols_for(cfg)
    log(f"reading {rel}" + (f", capped at {cap:,} in-sample rows" if cap else ", whole panel"))
    df = read_capped(path, syms, cap, log=log)

    if syms:
        # The panels carry both forms, BTCUSDT and BTC/USDT, depending on which
        # builder wrote them, so match on the letters and digits alone. Typing
        # the slash or leaving it out must not decide whether a run finds its
        # data.
        canon = {bc.canonical(s): s for s in df["symbol"].unique()}
        keep, missing = [], []
        for want in syms:
            hit = canon.get(bc.canonical(want))
            (keep.append(hit) if hit else missing.append(want))
        if missing:
            log(f"  not in this panel, ignored: {', '.join(missing)}")
        if not keep:
            raise SystemExit(
                f"none of the requested symbols are in {rel}. It carries "
                f"{len(canon)} symbols, for example "
                f"{', '.join(sorted(canon.values())[:6])}.")
        df = df[df["symbol"].isin(keep)].reset_index(drop=True)
        log(f"  matched {len(keep)}: {', '.join(keep[:8])}")

    feats = [c for c in df.columns if c.startswith("f_")]
    log(f"  {len(df):,} rows, {df['symbol'].nunique()} symbols, "
        f"{len(feats)} feature columns, base rate {df['label'].mean():.3f}")
    log(f"  span {df['datetime'].min().date()} to {df['datetime'].max().date()}")
    return df, feats


def check_label(cfg: dict, log=print) -> None:
    """Say plainly when the requested barrier is not the one in the frame.

    The label column is computed when the panel is built, from the raw kline
    highs and lows, and the built panel does not carry the price paths needed to
    recompute it. So a barrier different from the one on disk is a rebuild, not
    a setting, and pretending otherwise would score one geometry while reporting
    another.
    """
    import build_dataset_1h as bd

    frame = cfg["data"]["frame"]
    label_frame = "4h" if frame == "slice_4h_40k" else frame
    try:
        bd.configure(label_frame)
        # The keys are tgt_atr and stp_atr, not target_atr and stop_atr. Read
        # under the wrong names they came back None, the comparison below could
        # not fail, and the note fired on every run including the ones where the
        # barrier matched exactly.
        built = dict(target=bd.LABEL.get("tgt_atr"), stop=bd.LABEL.get("stp_atr"),
                     horizon=bd.LABEL.get("horizon_bars"))
    except Exception:                                   # noqa: BLE001
        return
    want = dict(target=cfg["label"]["target_atr"], stop=cfg["label"]["stop_atr"],
                horizon=cfg["label"]["horizon_bars"])
    if any(built[k] is not None and float(built[k]) != float(want[k]) for k in want):
        log("")
        log("NOTE: the barrier on this panel is not the one requested.")
        log(f"  panel was built at  {built['target']} / -{built['stop']} ATR "
            f"within {built['horizon']} bars")
        log(f"  this run asks for   {want['target']} / -{want['stop']} ATR "
            f"within {want['horizon']} bars")
        log("  The label is computed from the raw kline paths at build time and the")
        log("  built panel does not carry them, so a different barrier is a rebuild:")
        log(f"    .venv/bin/python 03-inputs/build_dataset_1h.py --interval {label_frame}")
        log("  To explore geometry instead, sweep it on the Label geometry panel.")
        log("  This run continues on the barrier the panel actually holds.")
        log("")


# ---------------------------------------------------------------------------
# Choose Filter and Choose Ranking
#
# Wired 20 September 2026. Until that day all seven settings on the A3 panel
# were saved by the form, drawn by the ranking-preview chart, and read by
# nothing that fitted anything, so a run with a 30 million USDT volume floor and
# a run with no floor at all scored exactly the same rows.
#
# Two of the four are measured on the raw kline archives rather than on the
# built panel, because the panel carries ratios and flags and no quote volume
# and no listing date at all. That is slower and it is the only honest way: the
# alternative is to report a floor that was never applied.
# ---------------------------------------------------------------------------

_ATR_COLUMNS = ("f_d1_atr_pct", "f_wc_atr_pct", "f_hr_atr_pct")


def _atr_column(df: pd.DataFrame) -> str | None:
    """The column holding a bar's volatility as a share of price.

    The band is written as a share of price, 0.015 being 1.5 per cent a day, and
    the daily column is preferred because that is the quantity the band was
    calibrated on and the quantity the ranking-preview chart draws.
    """
    for c in _ATR_COLUMNS:
        if c in df.columns:
            return c
    return next((c for c in df.columns if c.endswith("atr_pct")), None)


def _archive_root(cfg: dict) -> Path | None:
    """The folder of raw bars behind this frame, or None when there is none."""
    if cfg["data"].get("market") != "crypto":
        return None
    name = bc.KLINE_ROOTS.get(cfg["data"].get("frame", ""), "")
    root = REPO / "03-inputs" / "binance-data" / name
    return root if name and root.is_dir() else None


def _archive_folder(root: Path, symbol: str) -> Path | None:
    """One symbol's archive folder, matched on letters and digits alone."""
    want = bc.canonical(symbol)
    for d in root.iterdir():
        if d.is_dir() and bc.canonical(d.name) == want:
            return d
    return None


def _raw_bars(folder: Path, first, last, log=print) -> pd.DataFrame:
    """The raw bars of one symbol covering a span, from its own archives.

    Only the archives whose own period touches the span are opened. A symbol's
    four-hour history is 111 files and a two-year span needs about 25 of them,
    so reading the lot would cost the run a minute for nothing.
    """
    import build_dataset_1h as bd

    keep = []
    for p in sorted(folder.glob("*.zip")):
        if p.name.startswith("._"):
            continue
        stamp = p.stem.split("-", 2)[-1]            # YYYY-MM or YYYY-MM-DD
        try:
            start = pd.Timestamp(stamp)
        except ValueError:
            continue
        end = start + (pd.offsets.MonthEnd(1) if len(stamp) == 7 else pd.Timedelta(days=1))
        if end >= first and start <= last:
            keep.append(p)
    frames = []
    for p in keep:
        try:
            frames.append(bd._read_kline_zip(str(p)))
        except Exception:                           # noqa: BLE001
            continue                                # a truncated month, not a failure
    if not frames:
        return pd.DataFrame()
    d = pd.concat(frames, ignore_index=True)
    d["datetime"] = bd._to_datetime(d["open_time"])
    for c in ("close", "quote_volume"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    return (d.dropna(subset=["quote_volume"]).drop_duplicates("datetime")
            .sort_values("datetime").reset_index(drop=True))


def _listing_date(folder: Path):
    """When a symbol first traded, from the first timestamp of its first archive."""
    import build_dataset_1h as bd

    for p in sorted(folder.glob("*.zip")):
        if p.name.startswith("._"):
            continue
        try:
            d = bd._read_kline_zip(str(p))
        except Exception:                           # noqa: BLE001
            continue
        stamps = bd._to_datetime(d["open_time"]).dropna()
        if len(stamps):
            return stamps.min()
    return None


def quote_volume_24h(cfg: dict, df: pd.DataFrame, log=print):
    """Trailing 24-hour quote volume in USDT for every row, from the archives.

    Returns (Series aligned to df.index, note). The Series is None when the
    archives are not on disk, and the note says so rather than leaving the
    reader to assume a floor was applied.
    """
    root = _archive_root(cfg)
    if root is None:
        return None, (f"no Binance archive behind the "
                      f"{cfg['data'].get('frame')} frame, so the volume floor "
                      f"could not be measured on these rows")
    window = bc.bars_per_day(cfg["data"]["frame"])
    out = pd.Series(np.nan, index=df.index, dtype=float)
    missing = []
    for sym, part in df.groupby("symbol"):
        folder = _archive_folder(root, str(sym))
        if folder is None:
            missing.append(str(sym))
            continue
        first = part["datetime"].min() - pd.Timedelta(days=2)
        raw = _raw_bars(folder, first, part["datetime"].max(), log=log)
        if raw.empty:
            missing.append(str(sym))
            continue
        qv = raw["quote_volume"].rolling(window, min_periods=max(1, window // 2)).sum()
        lookup = pd.Series(qv.to_numpy(), index=raw["datetime"].to_numpy())
        out.loc[part.index] = part["datetime"].map(lookup).to_numpy()
    note = ("" if not missing else
            f"no archive for {', '.join(missing[:6])}"
            f"{' and others' if len(missing) > 6 else ''}, kept unfiltered")
    return out, note


def rank_tercile(df: pd.DataFrame, signal: str, keep: str, floor: int = 5):
    """Keep one third of the assets at each bar, ranked by one column.

    The point-in-time universe is thin, around five to seven assets a bar, so
    June's cross-sectional work ranked into thirds at a five-asset floor rather
    than into deciles. A bar carrying fewer than the floor is left whole: a
    third of four assets is one asset, which is not a cross-section.

    Returns (rows to keep, how many bars were actually ranked), because a run on
    three coins never reaches the floor and a record that called that "applied,
    0 rows dropped" would read as a ranking that found nothing to cut.
    """
    order = df[signal].astype(float)
    rank = order.groupby(df["datetime"]).rank(method="first", pct=True)
    n = df.groupby("datetime")["symbol"].transform("size")
    band = {"bottom": (0.0, 1 / 3), "middle": (1 / 3, 2 / 3), "top": (2 / 3, 1.0)}[keep]
    inside = (rank > band[0]) & (rank <= band[1])
    thin = n < floor
    return thin | inside, int(df.loc[~thin, "datetime"].nunique())


def apply_screen(cfg: dict, df: pd.DataFrame, log=print):
    """Every setting on Choose Filter and Choose Ranking, applied to the rows.

    Returns (rows kept, a record of what each filter did). A filter that cannot
    be measured on this frame is reported as not applied, with the reason, so a
    record never implies a threshold that never touched a row.
    """
    sc = cfg["screen"]
    info: dict = {"rows_in": len(df), "symbols_in": int(df["symbol"].nunique())}
    log("filter")

    # --- volatility band, from the frame's own ATR column
    col = _atr_column(df)
    lo, hi = float(sc["atr_low"]), float(sc["atr_high"])
    if col is None:
        info["volatility"] = dict(applied=False,
                                  why="this frame carries no ATR column")
        log("  volatility band: no ATR column in this frame, not applied")
    else:
        v = df[col].astype(float)
        keep = v.isna() | ((v >= lo) & (v <= hi))
        info["volatility"] = dict(applied=True, column=col, low=lo, high=hi,
                                  dropped=int((~keep).sum()))
        log(f"  volatility band {lo:g} to {hi:g} of price on {col}: "
            f"dropped {int((~keep).sum()):,} of {len(df):,} rows")
        df = df[keep]

    # --- liquidity floor, measured on the raw bars
    floor = float(sc["min_quote_volume"])
    if df.empty:
        info["liquidity"] = dict(applied=False, why="no rows left to measure")
    else:
        qv, note = quote_volume_24h(cfg, df, log=log)
        if qv is None:
            info["liquidity"] = dict(applied=False, floor=floor, why=note)
            log(f"  volume floor: {note}")
        else:
            qv = qv.reindex(df.index)
            keep = qv.isna() | (qv >= floor)
            info["liquidity"] = dict(applied=True, floor=floor,
                                     dropped=int((~keep).sum()),
                                     measured=int(qv.notna().sum()), note=note)
            log(f"  volume floor {floor:,.0f} USDT a day: dropped "
                f"{int((~keep).sum()):,} of {len(df):,} rows, measured on "
                f"{int(qv.notna().sum()):,}" + (f"; {note}" if note else ""))
            df = df[keep]

    # --- history floor, from each symbol's listing date
    days = int(sc["min_history_days"])
    root = _archive_root(cfg)
    if root is None or df.empty:
        info["history"] = dict(applied=False, days=days,
                               why="no archive to read a listing date from")
        log(f"  history floor: no archive behind this frame, not applied")
    else:
        keep = pd.Series(True, index=df.index)
        listed = {}
        for sym, part in df.groupby("symbol"):
            folder = _archive_folder(root, str(sym))
            first = _listing_date(folder) if folder is not None else None
            if first is None:
                continue
            listed[str(sym)] = str(pd.Timestamp(first).date())
            keep.loc[part.index] = part["datetime"] >= first + pd.Timedelta(days=days)
        info["history"] = dict(applied=True, days=days, listed=listed,
                               dropped=int((~keep).sum()))
        log(f"  history floor {days} days after listing: dropped "
            f"{int((~keep).sum()):,} of {len(df):,} rows")
        df = df[keep]

    # --- the cross-sectional ranking
    sig, keep_third = sc.get("rank_signal", "none"), sc.get("rank_tercile", "all")
    if sig == "none" or keep_third == "all":
        info["ranking"] = dict(applied=False, signal=sig, tercile=keep_third,
                               why="no ranking chosen" if sig == "none"
                                   else "every third kept")
        log(f"  ranking: {info['ranking']['why']}")
    elif sig not in df.columns:
        info["ranking"] = dict(applied=False, signal=sig, tercile=keep_third,
                               why=f"{sig} is not a column of this frame")
        log(f"  ranking: {sig} is not in this frame, not applied")
    elif df.empty:
        info["ranking"] = dict(applied=False, signal=sig, tercile=keep_third,
                               why="no rows left to rank")
    else:
        keep, ranked = rank_tercile(df, sig, keep_third)
        bars = int(df["datetime"].nunique())
        if not ranked:
            info["ranking"] = dict(
                applied=False, signal=sig, tercile=keep_third, floor=5,
                why=f"no bar carries the five assets a third needs; this run "
                    f"averages {len(df) / max(bars, 1):.1f} assets a bar")
            log(f"  ranking by {sig}: not applied, {info['ranking']['why']}")
        else:
            info["ranking"] = dict(applied=True, signal=sig, tercile=keep_third,
                                   floor=5, bars_ranked=ranked, bars=bars,
                                   dropped=int((~keep).sum()))
            log(f"  ranking by {sig}, keeping the {keep_third} third at a five-asset "
                f"floor: {ranked:,} of {bars:,} bars ranked, dropped "
                f"{int((~keep).sum()):,} of {len(df):,} rows")
            df = df[keep]

    df = df.reset_index(drop=True)
    info["rows_out"] = len(df)
    info["symbols_out"] = int(df["symbol"].nunique()) if len(df) else 0
    if not len(df):
        raise SystemExit(
            "the filter left no rows. " + "; ".join(
                f"{k} dropped {v['dropped']:,}" for k, v in info.items()
                if isinstance(v, dict) and v.get("dropped")) +
            ". Widen the volatility band, lower the volume floor, or shorten "
            "the history floor on the Choose Filter tool.")
    log(f"  {len(df):,} rows of {info['rows_in']:,} kept, "
        f"{info['symbols_out']} of {info['symbols_in']} symbols, "
        f"base rate {df['label'].mean():.3f}")
    return df, info


# ---------------------------------------------------------------------------
# Features and the screen
# ---------------------------------------------------------------------------

def choose_features(cfg: dict, available: list[str], log=print) -> list[str]:
    feats = bc.resolve_features(cfg, available)
    named = [n for n in str(cfg["features"].get("include", "")).split()]
    unknown = [n for n in named if n not in available]
    if unknown:
        log(f"  named but not in this frame, ignored: {', '.join(unknown)}")
    if not feats:
        raise SystemExit("the feature selection left no columns. Tick a family, or "
                         "clear the exclusions.")
    fams = sorted({"_".join(c.split("_")[:2]) + "_" for c in feats})
    log(f"  {len(feats)} of {len(available)} columns offered, "
        f"families {', '.join(fams)}")
    return feats


def cap_features(cfg: dict, train: pd.DataFrame, feats: list[str], log=print) -> list[str]:
    """Choose Features, At most: keep the N columns with the largest univariate
    AUC against the label on the training window only. 0 keeps all. Until
    20 September 2026 the setting was saved and never read."""
    cap = int(cfg["features"].get("max_features") or 0)
    if cap <= 0 or len(feats) <= cap:
        return feats
    from sklearn.metrics import roc_auc_score
    y = train["label"].to_numpy()
    score = {}
    for f in feats:
        x = train[f].to_numpy(dtype=float)
        ok = np.isfinite(x)
        if ok.sum() < 50 or len(np.unique(y[ok])) < 2:
            score[f] = 0.0
            continue
        score[f] = abs(roc_auc_score(y[ok], x[ok]) - 0.5)
    kept = sorted(feats, key=lambda f: -score[f])[:cap]
    log(f"  at most {cap}: kept the {len(kept)} columns with the largest univariate AUC, "
        f"dropped {len(feats) - len(kept)}")
    return [f for f in feats if f in set(kept)]


def coefficient_intervals(samp: pd.DataFrame, survivors: list[str], log=print):
    """Choose Screen, Draw intervals: an unpenalised logistic refit on the
    survivors for 95 per cent confidence intervals. Singular at small samples,
    in which case it is skipped and said so. Wired 20 September 2026."""
    import warnings
    import statsmodels.api as sm
    X = sm.add_constant(samp[survivors].astype(float))
    y = samp["label"].astype(float)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            res = sm.Logit(y, X).fit(disp=0)
        except (np.linalg.LinAlgError, ValueError):
            try:
                res = sm.Logit(y, X).fit(disp=0, method="bfgs", maxiter=500)
            except (np.linalg.LinAlgError, ValueError) as exc:
                log(f"  coefficient intervals: skipped, the refit is singular ({exc})")
                return f"skipped, singular: {exc}"
    ci = res.conf_int()
    out = [(n, float(res.params[n]), float(ci.loc[n, 0]), float(ci.loc[n, 1]))
           for n in res.params.index if n != "const"]
    log(f"  coefficient intervals drawn for {len(out)} survivors")
    return out


def screen_variables(cfg: dict, train: pd.DataFrame, feats: list[str], log=print):
    """The elastic-net screen, on the training window only."""
    sel = cfg["selection"]
    if not sel.get("run_selection"):
        return feats, {}
    import variable_selection as vs

    n = int(sel.get("sel_sample") or 25000)
    keep_idx = train.index[train[[*feats, "label"]].notna().all(axis=1).to_numpy()]
    if len(keep_idx) > n:
        keep_idx = keep_idx[np.random.RandomState(0).choice(len(keep_idx), n, replace=False)]
    samp = train.loc[keep_idx]
    log(f"  elastic net on {len(samp):,} training rows, l1_ratio "
        f"{sel['l1_ratio']:g}, {sel['sel_folds']} folds")
    X, y, _ = vs.build_matrix(samp, y_col="label", x_cols=feats, standardize=True)
    res = vs.enet_cv(X, y, family="binomial", l1_ratio=float(sel["l1_ratio"]),
                     n_folds=int(sel["sel_folds"]), verbose=False)
    kept = vs.screen(res, sel.get("rule", "1se"))
    survivors = [n_ for n_, _ in kept]
    info = dict(
        rule=sel.get("rule", "1se"),
        l1_ratio=float(sel["l1_ratio"]),
        rows=len(samp),
        lambda_min=float(res["lambda_min"]), lambda_1se=float(res["lambda_1se"]),
        nonzero_min=int(res["nonzero"][res["i_min"]]),
        nonzero_1se=int(res["nonzero"][res["i_1se"]]),
        survivors=[(n_, float(v)) for n_, v in kept],
    )
    log(f"  lambda.{info['rule']} keeps {len(survivors)} of {len(feats)}")
    if survivors and sel.get("draw_intervals"):
        info["intervals"] = coefficient_intervals(samp, survivors, log=log)
    if not survivors:
        log("  nothing survived the screen; the model keeps every offered column")
        return feats, info
    if sel.get("feed_model"):
        log("  the model is fitted on the survivors")
        return survivors, info
    log("  the screen is reported only; the model still sees every offered column")
    return feats, info


# ---------------------------------------------------------------------------
# Estimators
# ---------------------------------------------------------------------------

# Conventions for values a web form cannot express. A form field holds a number
# or a word, never None, so these stand in for it: 0 means "no cap" where the
# library wants None, and an empty string means "all of them".
_NONE_IF_ZERO = {"max_depth", "max_samples", "ccp_alpha_none"}
_NONE_IF_EMPTY = {"max_features"}


def _clean_params(params: dict | None) -> dict:
    out = {}
    for k, v in (params or {}).items():
        if k in _NONE_IF_ZERO and (v in (0, 0.0, "0", "")):
            out[k] = None
        elif k in _NONE_IF_EMPTY and str(v).strip() in ("", "all"):
            out[k] = None
        elif k == "max_features" and str(v).replace(".", "", 1).isdigit():
            out[k] = float(v) if "." in str(v) else int(v)
        else:
            out[k] = v
    return out


def make_estimator(name: str, class_weight: str, params: dict | None = None):
    """One estimator, honouring the configured class weight and every setting.

    model_assessment_1h hard-codes class_weight="balanced" throughout and fixes
    every other hyperparameter in the function body. That argument moves
    predicted probabilities away from the base rate by construction and on the
    four-hour frame accounted for two thirds of the calibration error, so it
    belongs to the operator, and so does the rest of the surface: whatever
    bench_config.MODEL_PARAMS names for a model is passed straight through to
    it, and an unknown name raises here rather than being silently dropped.
    """
    from sklearn.ensemble import (GradientBoostingClassifier,
                                  HistGradientBoostingClassifier,
                                  RandomForestClassifier)
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    cw = "balanced" if class_weight == "balanced" else None
    p = _clean_params(params)
    key = name.lower()
    # The seed is a setting like any other, so a caller measuring the spread
    # across refits can move it. Fixed as a keyword below it collided with a
    # caller passing the same name and raised.
    p.setdefault("random_state", 0)

    if key.startswith("logreg"):
        if key.endswith("enet"):
            p.setdefault("penalty", "elasticnet")
            p.setdefault("solver", "saga")
            p.setdefault("l1_ratio", 0.5)
            p.setdefault("C", 0.1)
        p.setdefault("max_iter", 5000)
        # lbfgs is deterministic and rejects a seed; saga accepts one.
        if p.get("solver", "lbfgs") == "lbfgs":
            p.pop("random_state", None)
        return Pipeline([("impute", SimpleImputer(strategy="median")),
                         ("scale", StandardScaler()),
                         ("clf", LogisticRegression(class_weight=cw, **p))])
    if key == "rf":
        p.setdefault("n_estimators", 400)
        p.setdefault("max_depth", 8)
        p.setdefault("min_samples_leaf", 50)
        est = RandomForestClassifier(class_weight=cw, n_jobs=-1, **p)
    elif key == "histgbm":
        p.setdefault("learning_rate", 0.05)
        p.setdefault("max_leaf_nodes", 31)
        p.setdefault("max_iter", 600)
        p.setdefault("l2_regularization", 1.0)
        est = HistGradientBoostingClassifier(class_weight=cw, **p)
    elif key == "lightgbm":
        try:
            from lightgbm import LGBMClassifier
        except ImportError:
            return None
        p.setdefault("learning_rate", 0.05)
        p.setdefault("num_leaves", 31)
        p.setdefault("n_estimators", 600)
        est = LGBMClassifier(class_weight=cw, n_jobs=-1,
                             verbose=-1, **p)
    elif key in ("gbm", "gbm.classic"):
        # scikit-learn's classic booster takes no class_weight. Sample weights
        # would be the equivalent and are not wired, so it is always unweighted
        # and the record says so rather than implying the setting applied.
        p.setdefault("learning_rate", 0.05)
        p.setdefault("n_estimators", 150)
        p.setdefault("max_depth", 3)
        p.setdefault("subsample", 0.5)
        est = GradientBoostingClassifier(**p)
    else:
        return None
    return Pipeline([("impute", SimpleImputer(strategy="median")), ("clf", est)])


def folds_of(n: int, k: int, scheme: str, repeats: int = 10,
             boot: int = 25, seed: int = 0, limit: int | None = None,
             purge: int = 0):
    """Which rows train and which are scored, for each resampling regime.

    Two of these keep time in order and the rest do not, which is the whole
    point of offering them together. Returns are autocorrelated: a row an hour
    after another is nearly the same observation, so any regime that puts a
    later row in training and an earlier one in test is scoring the model on
    something it has effectively already seen. Walk-forward is the honest
    answer; the others are here because they are the standard comparisons and
    because the gap between what they claim and what walk-forward finds is the
    most direct demonstration of the leak.

    expanding       the training window grows, each fold scored on what follows
    rolling         the training window slides, so old regimes drop out
    kfold           k equal blocks, each scored once, time ignored
    repeated-kfold  the same, reshuffled and repeated
    leave-one-out   every row scored by a model fitted on all the others
    monte-carlo     repeated random splits at a fixed train fraction
    bootstrap       resample with replacement, score the rows left out of bag
    """
    rng = np.random.RandomState(seed)
    out = []

    if scheme in ("expanding", "rolling"):
        # `purge` drops the last rows of each training block, so a label that
        # looks `horizon` bars ahead from the block's end cannot carry the
        # scored block's outcome into training. Added 16 September 2026; the
        # blind cut was embargoed from the start, the folds were not.
        edges = np.linspace(0, n, k + 2, dtype=int)
        for i in range(1, k + 1):
            lo = 0 if scheme == "expanding" else edges[i - 1]
            hi = max(lo + 1, edges[i] - max(0, int(purge)))
            out.append((np.arange(lo, hi), np.arange(edges[i], edges[i + 1])))

    elif scheme in ("kfold", "repeated-kfold"):
        reps = repeats if scheme == "repeated-kfold" else 1
        for r in range(reps):
            order = rng.permutation(n)
            for blk in np.array_split(order, k):
                out.append((np.setdiff1d(order, blk, assume_unique=False), blk))

    elif scheme == "leave-one-out":
        # `limit` exists for the drawing, which shows eight bands: generating two
        # hundred index arrays so eight could be plotted was most of the 29
        # seconds that froze the training-regime panel on open.
        # Every row in turn is n fits, which on 6,735 rows is 6,735 fits of a
        # 400-tree forest. Capped at 200 rows drawn at random, and the cap is
        # said out loud rather than left as a surprise in the timing.
        picks = rng.choice(n, size=min(n, limit or 200), replace=False)
        for i in picks:
            out.append((np.setdiff1d(np.arange(n), [i]), np.array([i])))

    elif scheme == "monte-carlo":
        for _ in range(max(repeats, 2)):
            order = rng.permutation(n)
            cut = int(n * 0.75)
            out.append((order[:cut], order[cut:]))

    elif scheme == "bootstrap":
        for _ in range(max(boot, 2)):
            tr = rng.randint(0, n, n)
            oob = np.setdiff1d(np.arange(n), np.unique(tr))
            if len(oob) > 20:
                out.append((tr, oob))

    else:
        raise ValueError(f"unknown resampling regime: {scheme!r}")

    out = [(tr, te) for tr, te in out if len(tr) > 50 and len(te) >= 1]
    return out[:limit] if limit else out


def score_estimator(name, params, cfg, train, test, feats, log=print):
    """Full errors in sample, cross-validated errors per fold, and the blind year.

    Both columns carry the same five measures, so Full and CV are read against
    each other rather than against different quantities. MAPE is None on a
    nought-or-one label because it divides by the outcome, and it is reported as
    not applicable rather than computed on the rows where the outcome is one.
    """
    cw = cfg["model"]["class_weight"]
    bins = int(cfg["calibration"].get("bins") or 10)
    est = make_estimator(name, cw, params)
    if est is None:
        log(f"  {name}: not available in this environment, skipped")
        return None
    Xtr, ytr = train[feats], train["label"].to_numpy()
    base = float(ytr.mean())            # the naive forecast Theil's U2 is against

    est.fit(Xtr, ytr)
    p_full = est.predict_proba(Xtr)[:, 1]
    full = mm.errors(ytr, p_full, bins=bins, naive=base)

    cv_p, cv_y, fold_u2 = [], [], []
    for tr, te in folds_of(len(train), int(cfg["split"]["folds"]),
                           cfg["split"]["scheme"],
                           repeats=int(cfg["split"].get("repeats") or 10),
                           boot=int(cfg["split"].get("boot_samples") or 25),
                           # The seed is a setting so a caller measuring the
                           # spread across refits can redraw the random regimes
                           # as well as reseed the model; before this every
                           # repeat of a k-fold scored the same partition.
                           seed=int(cfg["split"].get("seed") or 0),
                           purge=int(cfg["split"].get("purge_bars") or 0)):
        e = make_estimator(name, cw, params)
        e.fit(train.iloc[tr][feats], train.iloc[tr]["label"])
        p_fold = e.predict_proba(train.iloc[te][feats])[:, 1]
        y_fold = train.iloc[te]["label"].to_numpy()
        cv_p.append(p_fold)
        cv_y.append(y_fold)
        # Choose Ranking, Fold pass rate: a fold counts as passed when the
        # model's error on it is below the error of always predicting the
        # training base rate, which is Theil's U2 under one. A fold scoring
        # fewer than 20 rows, which is every fold of leave-one-out, has no
        # meaningful U2 and is left out of the rate rather than counted.
        if len(y_fold) >= 20 and len(np.unique(y_fold)) > 1:
            fold_u2.append(float(mm.errors(y_fold, p_fold, bins=bins,
                                           naive=base)["theil_u2"]))
    if cv_p:
        cv = mm.errors(np.concatenate(cv_y), np.concatenate(cv_p), bins=bins, naive=base)
    else:
        cv = dict(full)

    p_te = est.predict_proba(test[feats])[:, 1]
    yte = test["label"].to_numpy()
    blind = mm.errors(yte, p_te, bins=bins, naive=float(yte.mean()))

    row = dict(model=name, params=params or {},
               scheme=cfg["split"]["scheme"],
               full=full, cv=cv, blind=blind)
    row["rmse_ratio"] = cv["rmse"] / full["rmse"] if full["rmse"] else float("nan")
    row["rejected"] = row["rmse_ratio"] > float(cfg["model"]["reject_ratio"])
    bar = float(cfg["screen"].get("fold_bar") or 0.0)
    row["fold_u2"] = fold_u2
    row["fold_bar"] = bar
    row["folds_scored"] = len(fold_u2)
    row["fold_pass_rate"] = (float(np.mean([u < 1.0 for u in fold_u2]))
                             if fold_u2 else float("nan"))
    row["fold_bar_met"] = bool(fold_u2) and row["fold_pass_rate"] >= bar
    try:
        from sklearn.metrics import roc_auc_score
        row["blind_auc"] = float(roc_auc_score(yte, p_te))
    except Exception:                                   # noqa: BLE001
        row["blind_auc"] = float("nan")
    log(f"  {name:14s} full RMSE {full['rmse']:.4f}  cv RMSE {cv['rmse']:.4f}  "
        f"ratio {row['rmse_ratio']:.3f}  {'REJECTED' if row['rejected'] else 'passes'}"
        f"  U2 {cv['theil_u2']:.3f}  blind AUC {row['blind_auc']:.3f}"
        + ("" if not fold_u2 else
           f"  folds beating a constant {row['fold_pass_rate']:.2f} of "
           f"{len(fold_u2)} against a {bar:g} bar, "
           f"{'met' if row['fold_bar_met'] else 'NOT MET'}"))
    return row, est, p_te


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------

def calibrate(cfg, est, train, test, feats, log=print):
    """Reliability on the blind year, before and after the fitted mappings."""
    import calibration as cal

    cc = cfg["calibration"]
    frac = float(cc.get("cal_fraction") or 0.2)
    cut = int(len(train) * (1 - frac))
    fit_part, cal_part = train.iloc[:cut], train.iloc[cut:]
    if len(cal_part) < 200:
        log("  too few rows held out for a mapping; calibration skipped")
        return {}

    e = make_estimator(cfg["model"]["estimators"][0] if cfg["model"]["estimators"]
                       else "HistGBM", cfg["model"]["class_weight"])
    e.fit(fit_part[feats], fit_part["label"])
    p_cal = e.predict_proba(cal_part[feats])[:, 1]
    y_cal = cal_part["label"].to_numpy()
    p_te = e.predict_proba(test[feats])[:, 1]
    y_te = test["label"].to_numpy()

    want = cc.get("methods") or ["Platt", "isotonic"]
    maps = {"raw": lambda p: p}
    if "Platt" in want:
        maps["Platt"] = cal.fit_platt(p_cal, y_cal)
    if "isotonic" in want:
        maps["isotonic"] = cal.fit_isotonic(p_cal, y_cal)

    bins = int(cc.get("bins") or 10)
    out = {}
    for name, f in maps.items():
        p = np.clip(f(p_te), 0.0, 1.0)
        out[name] = dict(**cal.calibration_errors(y_te, p, bins),
                         **cal.brier_decomposition(y_te, p, bins))
        out[name]["table"] = cal.reliability(y_te, p, bins).to_dict("records")
        log(f"  {name:9s} ECE {out[name]['ece']:.4f}  MCE {out[name]['mce']:.4f}  "
            f"Brier {out[name]['brier']:.4f}")
    out["_n_fit"] = len(fit_part)
    out["_n_cal"] = len(cal_part)
    out["_n_test"] = len(test)
    out["_base"] = float(y_te.mean())
    return out


# ---------------------------------------------------------------------------
# The record
# ---------------------------------------------------------------------------

def screen_section(cfg: dict, info: dict) -> list[str]:
    """What each filter did to the rows, as a table a reader can check.

    A filter that could not be measured on this frame says so and says why,
    because a record that lists a 30 million USDT floor without saying the
    frame carries no volume column implies a threshold that never touched a
    row.
    """
    L = ["## The filter", "",
         f"{info['rows_in']:,} rows of {info['symbols_in']} symbols were read; "
         f"{info['rows_out']:,} rows of {info['symbols_out']} symbols survived "
         "Choose Filter and Choose Ranking.", "",
         "| filter | setting | applied | rows dropped |",
         "| --- | --- | --- | ---: |"]
    v = info.get("volatility") or {}
    L.append(f"| volatility band | {cfg['screen']['atr_low']:g} to "
             f"{cfg['screen']['atr_high']:g} of price"
             + (f", on {v['column']}" if v.get("column") else "") + " | "
             + ("yes" if v.get("applied") else f"no, {v.get('why', '')}") + " | "
             + (f"{v.get('dropped', 0):,}" if v.get("applied") else "n/a") + " |")
    q = info.get("liquidity") or {}
    L.append(f"| volume floor | {cfg['screen']['min_quote_volume']:,.0f} USDT a day | "
             + ("yes, from the raw archives" if q.get("applied")
                else f"no, {q.get('why', '')}") + " | "
             + (f"{q.get('dropped', 0):,}" if q.get("applied") else "n/a") + " |")
    h = info.get("history") or {}
    L.append(f"| history floor | {cfg['screen']['min_history_days']} days after listing | "
             + ("yes" if h.get("applied") else f"no, {h.get('why', '')}") + " | "
             + (f"{h.get('dropped', 0):,}" if h.get("applied") else "n/a") + " |")
    r = info.get("ranking") or {}
    tercile = r.get("tercile", "all")
    L.append(f"| ranking | {r.get('signal', 'none')}, "
             + ("every third kept" if tercile == "all"
                else f"keeping the {tercile} third") + " | "
             + (f"yes, on {r.get('bars_ranked', 0):,} of {r.get('bars', 0):,} bars "
                f"that carry five assets" if r.get("applied")
                else f"no, {r.get('why', '')}") + " | "
             + (f"{r.get('dropped', 0):,}" if r.get("applied") else "n/a") + " |")
    L.append("")
    if h.get("listed"):
        L += ["Listing dates read from each symbol's first archive: "
              + ", ".join(f"{k} {vv}" for k, vv in sorted(h["listed"].items())) + ".", ""]
    if q.get("note"):
        L += [q["note"].capitalize() + ".", ""]
    return L


def bench_figures_for(cfg, rows, est, train, test, feats, log=print, stamp=None):
    """Draw the figures this run asked for, and never let a drawing stop a run.

    A record is evidence and a picture is not, so a matplotlib failure is
    reported and the scores are still written. Before 20 September 2026 the
    Choose Figures and Signal engines settings were read by the panel's own
    charts and by nothing the run did, so a record never carried a picture of
    the rows it scored.
    """
    if not (cfg["viz"].get("panels") or []):
        return []
    try:
        import bench_figures as bf
        return bf.draw_all(cfg, rows=rows, est=est, train=train, test=test,
                           feats=feats, log=log, stamp=stamp)
    except Exception as exc:                            # noqa: BLE001
        log(f"figures: not drawn ({type(exc).__name__}: {exc})")
        return []


def write_record(cfg, rows, screen, cal, label, log=print,
                 screen_info=None, figures=None, stamp=None) -> Path:
    stamp = stamp or datetime.now()
    day = RUNS / stamp.strftime("%Y-%m-%d")
    day.mkdir(parents=True, exist_ok=True)
    # Seconds, not minutes. The unclobbered guard appends the time when a name
    # is taken, so a minute-stamped bench name collided with itself and produced
    # bench-20260908-1709-1709.md.
    stem = f"bench-{stamp:%Y%m%d-%H%M%S}"
    md = mm.unclobbered(day / f"{stem}.md")

    L = [f"# Bench run, {stamp:%d %B %Y %H:%M}", ""]
    if label:
        L += [f"**{label}**", ""]
    L += [bc.describe(cfg), ""]
    L += [f"The outcome scored was the {cfg['label'].get('kind', 'barrier')} "
          + ("label on the panel, a win when price reached the take-profit before "
             "the stop within the horizon."
             if cfg["label"].get("kind", "barrier") == "barrier"
             else "label; see the three-way record."), ""]

    if screen_info:
        L += screen_section(cfg, screen_info)

    if rows:
        L += ["## Scores", "",
              "Five measures, each computed twice on the same predictions, so Full and "
              "CV are read against each other rather than against different quantities. "
              "**Full** is fitted and scored in sample on the training window, the "
              "optimistic number showing what the model can memorise. **CV** is "
              "walk-forward out-of-fold on that same window. The blind period is scored "
              "once, at the end, and appears in the second table.", "",
              "| model | RMSE Full | RMSE CV | MAE Full | MAE CV | MAPE Full | MAPE CV "
              "| MISE Full | MISE CV | U2 Full | U2 CV | ratio | verdict |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]

        def _n(v, dp=4):
            return "n/a" if v is None or (isinstance(v, float) and not np.isfinite(v)) \
                else f"{v:.{dp}f}"

        for r in sorted(rows, key=lambda r: r["cv"]["rmse"]):
            name = r["model"] + (" " + " ".join(f"{k}={v}" for k, v in r["params"].items())
                                 if r["params"] else "")
            f_, c_ = r["full"], r["cv"]
            L.append(
                f"| {name} | {_n(f_['rmse'])} | {_n(c_['rmse'])} "
                f"| {_n(f_['mae'])} | {_n(c_['mae'])} "
                f"| {_n(f_['mape'], 1)} | {_n(c_['mape'], 1)} "
                f"| {_n(f_['mise'], 5)} | {_n(c_['mise'], 5)} "
                f"| {_n(f_['theil_u2'], 3)} | {_n(c_['theil_u2'], 3)} "
                f"| {r['rmse_ratio']:.3f} "
                f"| {'rejected' if r['rejected'] else 'passes'} |")

        L += ["", "### On the blind period", "",
              "Scored once. Theil's U1 is bounded on nought to one and nought is a perfect "
              "forecast. U2 is the model's error over the error of always predicting the "
              "base rate, so below one beats it and above one is worse than doing nothing. "
              "The bias share is how much of the squared error comes from the forecast's "
              "mean sitting away from the outcome's, which catches a model that is "
              "systematically high or low rather than merely noisy.", "",
              "| model | RMSE | MAE | MISE | Theil U1 | Theil U2 | bias share | AUC |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for r in sorted(rows, key=lambda r: r["cv"]["rmse"]):
            b = r["blind"]
            L.append(f"| {r['model']} | {_n(b['rmse'])} | {_n(b['mae'])} "
                     f"| {_n(b['mise'], 5)} | {_n(b['theil_u1'], 3)} "
                     f"| {_n(b['theil_u2'], 3)} | {_n(b['theil_bias'], 3)} "
                     f"| {r['blind_auc']:.3f} |")

        passing = [r for r in rows if not r["rejected"]]
        L += ["", f"{len(passing)} of {len(rows)} passed the "
                  f"{cfg['model']['reject_ratio']} overfit bar, which is cross-validated "
                  f"RMSE over training RMSE."
                  + ("" if not passing else
                     f" The best of those on held-out error is "
                     f"{min(passing, key=lambda r: r['cv']['rmse'])['model']}."), ""]
        scored = [r for r in rows if r.get("folds_scored")]
        if scored:
            bar = float(cfg["screen"].get("fold_bar") or 0.0)
            L += ["", "### Fold pass rate", "",
                  "The share of cross-validated folds on which the model's error was "
                  "below the error of always predicting the training base rate, which "
                  "is Theil's U2 under one. A pooled total can be carried by one "
                  f"favourable stretch, which is why the bar sits on folds. The bar is "
                  f"{bar:g}, set on the Choose Ranking tool.", "",
                  "| model | folds scored | folds beating a constant | rate | bar | verdict |",
                  "| --- | ---: | ---: | ---: | ---: | --- |"]
            for r in scored:
                beat = sum(1 for u in r["fold_u2"] if u < 1.0)
                L.append(f"| {r['model']} | {r['folds_scored']} | {beat} "
                         f"| {r['fold_pass_rate']:.2f} | {bar:g} "
                         f"| {'met' if r['fold_bar_met'] else 'not met'} |")
            L.append("")

        if figures:
            L += ["## Figures", "",
                  "Drawn from the Choose Figures and Signal engines settings on this "
                  "run's own rows, and written beside this record.", ""]
            for f in figures:
                L.append(f"- `{f['file']}`, {f['what']}")
            L.append("")
            for f in figures:
                L += ["", f"![{f['what']}]({f['file']})"]
            L.append("")

        if all(r["full"]["mape"] is None for r in rows):
            L += ["MAPE is not applicable here. It divides by the outcome and the outcome "
                  "is nought for the majority class, so the quantity does not exist rather "
                  "than being large. It is computed and reported on continuous targets "
                  "such as bars until the trend reverses.", ""]

    if screen:
        L += ["## Variable selection", "",
              f"An elastic net at l1_ratio {screen['l1_ratio']:g} over "
              f"{screen['rows']:,} training rows. lambda.min {screen['lambda_min']:.5g} "
              f"keeps {screen['nonzero_min']}; lambda.1se {screen['lambda_1se']:.5g} "
              f"keeps {screen['nonzero_1se']}. Screened at lambda.{screen['rule']}.", ""]
        if screen["survivors"]:
            L += ["| feature | coefficient |", "| --- | ---: |"]
            L += [f"| {n} | {v:+.4f} |" for n, v in screen["survivors"][:30]]
            if len(screen["survivors"]) > 30:
                L.append(f"\nFirst 30 of {len(screen['survivors'])}.")
        else:
            L.append("Nothing survived at that penalty.")
        L.append("")

    if cal:
        L += ["## Calibration", "",
              f"Fitted on {cal['_n_fit']:,} rows, mapping fitted on a held-out "
              f"{cal['_n_cal']:,}, scored once on the {cal['_n_test']:,}-row blind "
              f"period. Base rate {cal['_base']:.3f}.", "",
              "| mapping | ECE | MCE | Brier | reliability | resolution | uncertainty |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for name in ("raw", "Platt", "isotonic"):
            if name not in cal:
                continue
            c = cal[name]
            L.append(f"| {name} | {c['ece']:.4f} | {c['mce']:.4f} | {c['brier']:.4f} "
                     f"| {c['reliability']:.5f} | {c['resolution']:.5f} "
                     f"| {c['uncertainty']:.4f} |")
        L.append("")

    L += ["## The configuration that produced this", "",
          "Every setting, so the run replays from its own record.", "",
          "```json", json.dumps(cfg, indent=2, sort_keys=True), "```", ""]
    md.write_text("\n".join(L) + "\n", encoding="utf-8")
    (md.with_suffix(".json")).write_text(
        json.dumps(dict(stamped=stamp.isoformat(timespec="seconds"), label=label,
                        config=cfg, scores=rows, screen=screen,
                        kind=cfg["label"].get("kind", "barrier"),
                        filter=screen_info, figures=figures,
                        calibration={k: v for k, v in (cal or {}).items()
                                     if not k.endswith("table")}),
                   indent=2, default=str), encoding="utf-8")
    log(f"record: {md.relative_to(REPO)}")
    return md


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=None, help="a saved config; default is the active one")
    ap.add_argument("--label", default="", help="a name for this run, printed in the record")
    a = ap.parse_args()

    t0 = time.time()
    cfg = bc.load(Path(a.config) if a.config else None)
    print(bc.describe(cfg))
    print()

    # Choose Label, Outcome. The barrier is a win-or-loss column on the panel;
    # the three-way outcome is read off the return a trade would make and is
    # scored on money rather than on error, so it is a different run and not a
    # different argument. Until 20 September 2026 this setting was saved and the
    # runner ignored it, so a record said three-way and scored the barrier.
    if str(cfg["label"].get("kind", "barrier")) == "three-way":
        import bench_three_way as b3
        import train_model as tm
        band = float(cfg["label"].get("flat_band") or 0.002)
        ests = cfg["model"]["estimators"] or ["LogReg.glm", "RF", "HistGBM"]
        print(f"the outcome is three-way, so this run is scored on money: "
              f"bullish, bearish or break-even inside a band of "
              f"{band * 100:.2f} per cent of price")
        res = b3.run(cfg, ests, band, tm.COST_PCT / 100.0, target="forward")
        b3.write_record(cfg, res, time.time() - t0)
        print(f"done in {time.time() - t0:.0f} seconds")
        return 0

    df, available = load_frame(cfg)
    check_label(cfg)
    df, screen_info = apply_screen(cfg, df)
    feats = choose_features(cfg, available)

    holdout = int(cfg["split"]["holdout_days"])
    embargo = int(cfg["split"]["embargo_bars"] or 0)
    train, test, cut = t1.split(df, oos_days=holdout,
                                embargo_days=max(1, embargo // 6) if embargo else t1.EMBARGO_DAYS)
    if len(train) < 500 or len(test) < 100:
        raise SystemExit(f"the split leaves too little: {len(train):,} training rows and "
                         f"{len(test):,} blind rows. Widen the row cap or shorten the "
                         f"held-out period.")
    print(f"split at {cut.date()}: {len(train):,} training rows, {len(test):,} blind")

    feats = cap_features(cfg, train, feats)
    feats, screen = screen_variables(cfg, train, feats)

    rows = []
    tune = cfg["model"].get("tune", "")
    if tune:
        grid = bc.grid_of(cfg)
        if not grid:
            import model_assessment_1h as ma
            grid = ma.TUNE_GRIDS[tune]
        combos = [dict(zip(grid, v)) for v in product(*grid.values())]
        print(f"sweeping {tune} over {len(combos)} settings")
        for params in combos:
            got = score_estimator(tune, params, cfg, train, test, feats)
            if got:
                rows.append(got[0])
        best_est = None
    else:
        chosen = cfg["model"]["estimators"] or ["LogReg.glm", "RF", "HistGBM"]
        print(f"scoring {len(chosen)} estimators")
        best_est = None
        per_model = cfg["model"].get("params") or {}
        for name in chosen:
            got = score_estimator(name, per_model.get(name), cfg, train, test, feats)
            if got:
                rows.append(got[0])
                if best_est is None:
                    best_est = got[1]

    cal = {}
    if cfg["calibration"].get("run_calibration"):
        print("calibrating")
        cal = calibrate(cfg, best_est, train, test, feats)

    stamp = datetime.now()
    figures = bench_figures_for(cfg, rows, best_est, train, test, feats, stamp=stamp)
    write_record(cfg, rows, screen, cal, a.label, screen_info=screen_info,
                 figures=figures, stamp=stamp)
    print(f"done in {time.time() - t0:.0f} seconds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
