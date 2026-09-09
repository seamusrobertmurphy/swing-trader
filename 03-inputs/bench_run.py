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
        elif k in _NONE_IF_EMPTY and str(v).strip() == "":
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


def folds_of(n: int, k: int, scheme: str):
    """Walk-forward fold boundaries over n rows already sorted by time."""
    edges = np.linspace(0, n, k + 2, dtype=int)
    out = []
    for i in range(1, k + 1):
        lo = 0 if scheme == "expanding" else edges[i - 1]
        out.append((np.arange(lo, edges[i]), np.arange(edges[i], edges[i + 1])))
    return [(tr, te) for tr, te in out if len(tr) > 50 and len(te) > 20]


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

    cv_p, cv_y = [], []
    for tr, te in folds_of(len(train), int(cfg["split"]["folds"]),
                           cfg["split"]["scheme"]):
        e = make_estimator(name, cw, params)
        e.fit(train.iloc[tr][feats], train.iloc[tr]["label"])
        cv_p.append(e.predict_proba(train.iloc[te][feats])[:, 1])
        cv_y.append(train.iloc[te]["label"].to_numpy())
    if cv_p:
        cv = mm.errors(np.concatenate(cv_y), np.concatenate(cv_p), bins=bins, naive=base)
    else:
        cv = dict(full)

    p_te = est.predict_proba(test[feats])[:, 1]
    yte = test["label"].to_numpy()
    blind = mm.errors(yte, p_te, bins=bins, naive=float(yte.mean()))

    row = dict(model=name, params=params or {},
               full=full, cv=cv, blind=blind)
    row["rmse_ratio"] = cv["rmse"] / full["rmse"] if full["rmse"] else float("nan")
    row["rejected"] = row["rmse_ratio"] > float(cfg["model"]["reject_ratio"])
    try:
        from sklearn.metrics import roc_auc_score
        row["blind_auc"] = float(roc_auc_score(yte, p_te))
    except Exception:                                   # noqa: BLE001
        row["blind_auc"] = float("nan")
    log(f"  {name:14s} full RMSE {full['rmse']:.4f}  cv RMSE {cv['rmse']:.4f}  "
        f"ratio {row['rmse_ratio']:.3f}  {'REJECTED' if row['rejected'] else 'passes'}"
        f"  U2 {cv['theil_u2']:.3f}  blind AUC {row['blind_auc']:.3f}")
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

def write_record(cfg, rows, screen, cal, label, log=print) -> Path:
    stamp = datetime.now()
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

    df, available = load_frame(cfg)
    check_label(cfg)
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

    write_record(cfg, rows, screen, cal, a.label)
    print(f"done in {time.time() - t0:.0f} seconds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
