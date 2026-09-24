"""Random search across markets, symbols, features, models, settings and regimes.

    .venv/bin/python 03-inputs/bench_random_suite.py cache            # cut the pools once
    .venv/bin/python 03-inputs/bench_random_suite.py run --draws 40 --per-draw 5
    .venv/bin/python 03-inputs/bench_random_suite.py report <run.jsonl>

Operator request, 23 September 2026: a full suite of randomised settings comparing
training regimes, models, hyperparameters, coins, stocks and feature sets. It
exists because the three-way outcome's +1.0 to +1.2 per cent per trade on 16
September came from one draw of three coins, and every later run changed several
things at once, so nothing on record says which of them the result depended on.

A draw has two levels. The data draw picks a panel (crypto at 1h, 4h or 1d, US
equities at 1h or 1d), a random handful of that panel's symbols, a horizon, a
break-even band and a random set of feature families; the panel is read and
split once. Several model draws then share those rows, each picking an estimator,
random hyperparameters, a class weight and one of the seven resampling regimes
in bench_run.folds_of. Every model draw is scored on the blind period, which is
the same for every model draw on a data draw.

Scoring is the three-way outcome of bench_three_way, with three additions that
the single runs lack.

1. Non-overlapping trades. The top fifth of blind rows by P(bullish) minus
   P(bearish) holds consecutive bars of one symbol, whose forward windows share
   most of their bars, so one move is counted up to `horizon` times. Here the
   selected rows are thinned per symbol so no two held windows overlap, and the
   mean after cost and its t statistic are reported on what is left. This is the
   kill harness the 22 September handover named as open.
2. A shuffle null. The same number of blind rows drawn at random, 2,000 times;
   the share of draws whose mean is at least the model's is its p-value. A top
   fifth that beats every row by chance is common when the market drifts.
3. The overfit ratio as the house defines it: the root multiclass Brier score of
   the cross-validation test folds over that of the training folds, rejected
   above 1.1 (model_metrics.RMSE_RATIO_REJECT).

The forward return is rebuilt from f_hr_mom_<h> read h bars later, as
bench_three_way does, but only where the row h places later is exactly h bars
later on the market's own calendar. The per-bar screen removes rows, and on a
gap the row shift reads a window that starts after the entry bar; on the slice
the 16 September runs read, that was true of most training rows. The anchor draw also scores the old
row shift so the 16 September record can be reproduced.

Everything is appended to a JSONL file one model draw at a time, so a run killed
by memory pressure keeps what it finished and the report reads whatever is there.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench_config as bc          # noqa: E402
import bench_run as br             # noqa: E402
import model_metrics as mm         # noqa: E402

REPO = bc.REPO
OUT = REPO / "04-outputs" / "AA-evals" / "random-suite"
CACHE = OUT / "cache"


# One entry per panel. `holdout` is the blind period in days, `before` and
# `blind` the rows a symbol needs on each side of the cut to join the pool,
# `cost` the round-trip cost charged per trade as a share of price. Crypto pays
# train_model.COST_PCT, 0.20 per cent. Equities pay 0.10 per cent, twice the
# 3.8 basis points a side measured on the paper book on 18 August 2026.
PANELS = {
    # Binance spot klines, data.binance.vision, https://data.binance.vision/
    # (acquire_vision.BASE_URL), built by build_dataset_1h.py.
    "crypto-4h": dict(path="03-inputs/binance-data/dataset_4h_allmarket.parquet", bar="4h",
                      holdout=365, before=2000, blind=400, cost=0.002, horizons=(6, 12, 24)),
    "crypto-1d": dict(path="03-inputs/binance-data/dataset_1d_allmarket.parquet", bar="1d",
                      holdout=365, before=400, blind=80, cost=0.002, horizons=(6, 12, 24)),
    "crypto-1h": dict(path="03-inputs/binance-data/dataset_1h_allmarket.parquet", bar="1h",
                      holdout=180, before=5000, blind=800, cost=0.002, horizons=(12, 24, 72)),
    # The 8 September 40,000-row cut of the 4h panel, which the 16 September
    # three-way runs read. Kept so the anchor reproduces them on the same rows.
    "crypto-4h-slice": dict(path="03-inputs/binance-data/slice_4h_40k.parquet", bar="4h",
                            holdout=365, before=1000, blind=300, cost=0.002, horizons=(6, 12, 24)),
    # Alpaca US equities, SIP feed, adjustment=all. The download manifest
    # 03-inputs/alpaca-data/download_manifest.json records no retrieval link.
    "equity-1d": dict(path="03-inputs/alpaca-data/dataset_eq1d_allmarket.parquet", bar="1d",
                      holdout=365, before=750, blind=150, cost=0.001, horizons=(6, 12, 24),
                      pool_size=40),
    # Same source; manifest 03-inputs/alpaca-data/download_manifest_1h.json, no link.
    "equity-1h": dict(path="03-inputs/alpaca-data/dataset_eq1h_allmarket.parquet", bar="1h",
                      holdout=90, before=1000, blind=300, cost=0.001, horizons=(6, 12, 24)),
}

MODELS = ("LogReg.glm", "LogReg.enet", "RF", "HistGBM", "LightGBM", "GBM.classic")
REGIMES = ("expanding", "rolling", "kfold", "repeated-kfold", "leave-one-out",
           "monte-carlo", "bootstrap")
TRAIN_CAP = 20000          # most recent training rows kept, for time on this machine
NULL_DRAWS = 2000


# ---------------------------------------------------------------------------
# Pools and caches
# ---------------------------------------------------------------------------

def _pool(path: str, spec: dict) -> list[str]:
    """Symbols with enough in-sample rows before the blind cut and inside it."""
    import pyarrow.parquet as pq
    t = pq.read_table(str(REPO / path), columns=["symbol", "datetime", "in_sample"]).to_pandas()
    t = t[t["in_sample"]]
    cut = t["datetime"].max() - pd.Timedelta(days=spec["holdout"])
    before = t[t["datetime"] < cut].groupby("symbol").size()
    blind = t[t["datetime"] >= cut].groupby("symbol").size()
    d = pd.concat([before.rename("b"), blind.rename("t")], axis=1).fillna(0)
    ok = sorted(d[(d["b"] >= spec["before"]) & (d["t"] >= spec["blind"])].index)
    if spec.get("pool_size") and len(ok) > spec["pool_size"]:
        ok = sorted(np.random.RandomState(0).choice(ok, spec["pool_size"], replace=False))
    return list(ok)


def build_cache(log=print) -> dict:
    """One small Parquet per panel, holding every bar of the pool as float32.

    The four-hour panel is four row groups of about a million rows each, so
    reading one symbol through bench_run.read_capped decompresses a quarter of
    the file. Streaming it once in batches and keeping the pool is a single pass
    that never holds more than one batch.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq
    CACHE.mkdir(parents=True, exist_ok=True)
    pools = {}
    for name, spec in PANELS.items():
        src = REPO / spec["path"]
        if not src.exists():
            log(f"{name}: no panel at {spec['path']}, skipped"); continue
        pool = _pool(spec["path"], spec)
        pools[name] = pool
        pf = pq.ParquetFile(str(src))
        keep = [c for c in pf.schema.names
                if c in ("symbol", "datetime", "in_sample") or c.startswith("f_")]
        want = set(pool)
        writer, n = None, 0
        for batch in pf.iter_batches(batch_size=100_000, columns=keep):
            df = batch.to_pandas()
            # Every bar of the pool, screened or not. The screen says which bars
            # may be entered; the exit price of a trade exists either way, and
            # dropping screened bars here left most daily stock windows without
            # an exit (24 September 2026).
            df = df[df["symbol"].isin(want)]
            if df.empty:
                continue
            f = [c for c in df.columns if c.startswith("f_")]
            df[f] = df[f].astype("float32")
            tbl = pa.Table.from_pandas(df, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(str(CACHE / f"{name}.parquet"), tbl.schema)
            writer.write_table(tbl.cast(writer.schema))
            n += len(df)
        if writer:
            writer.close()
        log(f"{name}: {len(pool)} symbols, {n:,} rows -> {(CACHE / f'{name}.parquet').relative_to(REPO)}")
    (CACHE / "pools.json").write_text(json.dumps(pools, indent=2))
    return pools


def load_panel(name: str, symbols: list[str]) -> pd.DataFrame:
    # The slice is 25 MB and read whole, because the anchor's MATIC has too few
    # blind rows to enter the slice's pool and so is not in its cache.
    if name == "crypto-4h-slice":
        df = pd.read_parquet(REPO / PANELS[name]["path"], filters=[("symbol", "in", list(symbols))])
    else:
        df = pd.read_parquet(CACHE / f"{name}.parquet", filters=[("symbol", "in", list(symbols))])
    return df.sort_values(["datetime", "symbol"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Target
# ---------------------------------------------------------------------------

def calendar(name: str) -> pd.Index:
    """Every bar time the panel's market traded, from all of its pool symbols.

    Stocks skip nights, weekends and holidays, so "h bars later" cannot be read
    off the clock; it is h places later on this calendar. For crypto the
    calendar is every hour and the two agree.
    """
    src = REPO / PANELS[name]["path"] if name == "crypto-4h-slice" else CACHE / f"{name}.parquet"
    return pd.Index(sorted(pd.read_parquet(src, columns=["datetime"])["datetime"].unique()))


def forward_return(df: pd.DataFrame, horizon: int, exact: bool = True) -> pd.Series:
    """Close-to-close return over the next `horizon` bars, per symbol.

    f_hr_mom_<h> at bar t is close[t] over close[t-h] minus one, so the same
    column h rows later is the forward return from t, provided those h rows are
    h consecutive bars. With `exact` a row whose h-th successor is not exactly
    h places later on the market calendar (column `pos`) gets no return.
    """
    col = f"f_hr_mom_{horizon}"
    d = df[["symbol", "pos", col]].sort_values(["symbol", "pos"])
    g = d.groupby("symbol")
    fwd = g[col].shift(-horizon)
    if exact:
        fwd = fwd.where((g["pos"].shift(-horizon) - d["pos"]) == horizon)
    return fwd.reindex(df.index)


def three_way(ret: np.ndarray, band: float) -> np.ndarray:
    out = np.ones(len(ret), dtype=int)
    out[ret > band] = 2
    out[ret < -band] = 0
    return out


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _brier_rmse(y: np.ndarray, p: np.ndarray) -> float:
    onehot = np.eye(3)[y]
    return float(np.sqrt(((p - onehot) ** 2).sum(axis=1).mean()))


def _proba(est, X) -> np.ndarray:
    p = est.predict_proba(X)
    full = np.zeros((len(X), 3))
    full[:, list(est.classes_)] = p
    return full


def non_overlapping(frame: pd.DataFrame, picked: np.ndarray, horizon: int) -> np.ndarray:
    """Thin picked rows so no symbol holds two windows at once.

    Walks each symbol's picked rows in calendar order and keeps a row only if
    it starts at or after the end of the last kept window.
    """
    sub = frame.loc[picked, ["symbol", "pos"]].sort_values(["symbol", "pos"])
    keep = []
    for _, g in sub.groupby("symbol"):
        free = -1
        for idx, t in zip(g.index, g["pos"]):
            if t >= free:
                keep.append(idx)
                free = t + horizon
    return np.array(sorted(keep), dtype=int)


def money(frame: pd.DataFrame, proba: np.ndarray, cost: float, horizon: int, bar: str,
          rng: np.random.RandomState, null: bool = False) -> dict:
    """What the top fifth by P(bullish) minus P(bearish) made, three ways."""
    ret = frame["ret"].to_numpy(float)
    edge = proba[:, 2] - proba[:, 0]
    top = np.flatnonzero(edge >= np.quantile(edge, 0.8))
    out = dict(n_rows=len(ret), all_rows=float(ret.mean() - cost),
               n_top=len(top), top=float(ret[top].mean() - cost))
    out["lift"] = out["top"] - out["all_rows"]
    thin = non_overlapping(frame.reset_index(drop=True), top, horizon)
    r = ret[thin] - cost
    out["n_thin"] = len(thin)
    out["thin"] = float(r.mean()) if len(r) else float("nan")
    out["thin_t"] = (float(r.mean() / (r.std(ddof=1) / math.sqrt(len(r))))
                     if len(r) > 2 and r.std(ddof=1) > 0 else float("nan"))
    # The same windows, every row: the non-overlapping version of "all rows".
    every = non_overlapping(frame.reset_index(drop=True), np.arange(len(ret)), horizon)
    out["thin_all_rows"] = float(ret[every].mean() - cost)
    if null:
        draws = np.array([ret[rng.choice(len(ret), len(top), replace=False)].mean()
                          for _ in range(NULL_DRAWS)]) - cost
        out["p_null"] = float((draws >= out["top"]).mean())
    return out


def _classes(y: np.ndarray) -> np.ndarray:
    return np.bincount(y, minlength=3) / len(y)


def score(model: str, params: dict, cw: str, regime: str, k: int, seed: int,
          train: pd.DataFrame, test: pd.DataFrame, feats: list[str],
          cost: float, horizon: int, bar: str) -> dict | None:
    from sklearn.metrics import log_loss
    est = br.make_estimator(model, cw, dict(params, random_state=seed))
    if est is None:
        return None
    X, y = train[feats], train["y"].to_numpy()
    limit = {"leave-one-out": 30}.get(regime)
    folds = br.folds_of(len(train), k, regime, repeats=3, boot=5, seed=seed, limit=limit)
    rng = np.random.RandomState(seed)
    cv_p, cv_y, cv_i, tr_rmse = [], [], [], []
    for tr, te in folds:
        e = br.make_estimator(model, cw, dict(params, random_state=seed))
        e.fit(X.iloc[tr], y[tr])
        cv_p.append(_proba(e, X.iloc[te])); cv_y.append(y[te]); cv_i.append(te)
        # Training error on at most 5,000 of the fold's own rows, for the ratio.
        s = tr if len(tr) <= 5000 else rng.choice(tr, 5000, replace=False)
        tr_rmse.append(_brier_rmse(y[s], _proba(e, X.iloc[s])))
    cvp, cvy, cvi = np.vstack(cv_p), np.concatenate(cv_y), np.concatenate(cv_i)
    cv_rmse = _brier_rmse(cvy, cvp)
    cv_money = money(train.iloc[cvi].reset_index(drop=True), cvp, cost, horizon, bar, rng)

    est.fit(X, y)
    bp = _proba(est, test[feats])
    by = test["y"].to_numpy()
    prior = np.tile(_classes(y), (len(by), 1))
    blind = money(test.reset_index(drop=True), bp, cost, horizon, bar, rng, null=True)
    blind.update(log_loss=float(log_loss(by, np.clip(bp, 1e-6, 1), labels=[0, 1, 2])),
                 log_loss_prior=float(log_loss(by, prior, labels=[0, 1, 2])),
                 rmse=_brier_rmse(by, bp))
    return dict(n_folds=len(folds), cv_rmse=cv_rmse, train_rmse=float(np.mean(tr_rmse)),
                ratio=cv_rmse / float(np.mean(tr_rmse)),
                cv_top=cv_money["top"], cv_all_rows=cv_money["all_rows"], blind=blind)


# ---------------------------------------------------------------------------
# Random draws
# ---------------------------------------------------------------------------

def _loguniform(rng, lo, hi):
    return float(math.exp(rng.uniform(math.log(lo), math.log(hi))))


def draw_params(model: str, rng) -> dict:
    c = lambda xs: xs[rng.randint(len(xs))]
    if model == "LogReg.glm":
        return dict(C=_loguniform(rng, 1e-3, 10))
    if model == "LogReg.enet":
        return dict(C=_loguniform(rng, 1e-3, 1), l1_ratio=round(float(rng.uniform(0, 1)), 2))
    if model == "RF":
        return dict(n_estimators=int(rng.randint(100, 301)), max_depth=c([3, 4, 6, 8, 12, 0]),
                    min_samples_leaf=c([1, 10, 50, 200, 500]), max_features=c(["sqrt", "0.3", "0.6"]))
    if model == "HistGBM":
        return dict(learning_rate=_loguniform(rng, 0.01, 0.2), max_leaf_nodes=c([7, 15, 31, 63]),
                    max_iter=int(rng.randint(100, 401)), l2_regularization=c([0.0, 1.0, 10.0]),
                    min_samples_leaf=c([20, 100, 400]))
    if model == "LightGBM":
        return dict(learning_rate=_loguniform(rng, 0.01, 0.2), num_leaves=c([7, 15, 31, 63]),
                    n_estimators=int(rng.randint(100, 401)), min_child_samples=c([20, 100, 400]),
                    subsample=round(float(rng.uniform(0.5, 1)), 2), subsample_freq=1,
                    colsample_bytree=round(float(rng.uniform(0.5, 1)), 2), reg_lambda=c([0.0, 1.0, 10.0]))
    if model == "GBM.classic":
        return dict(learning_rate=_loguniform(rng, 0.02, 0.2), n_estimators=int(rng.randint(50, 201)),
                    max_depth=int(rng.randint(2, 5)), subsample=round(float(rng.uniform(0.5, 1)), 2))
    raise ValueError(model)


def draw_data(rng, pools: dict, families_of: dict) -> dict:
    panels = [p for p in PANELS if p in pools and len(pools[p]) >= 2 and p != "crypto-4h-slice"]
    panel = panels[rng.randint(len(panels))]
    spec, pool = PANELS[panel], pools[panel]
    n = int(rng.randint(2, min(8, len(pool)) + 1))
    symbols = sorted(rng.choice(pool, n, replace=False).tolist())
    fams = families_of[panel]
    pick = [f for f in fams if rng.rand() < 0.5]
    while len(pick) < 2:
        f = fams[rng.randint(len(fams))]
        pick = sorted(set(pick) | {f})
    cost = spec["cost"]
    band = float([cost / 2, cost, 1.5 * cost, 2.5 * cost, 5 * cost][rng.randint(5)])
    horizon = int(spec["horizons"][rng.randint(len(spec["horizons"]))])
    return dict(panel=panel, symbols=symbols, families=sorted(pick), horizon=horizon,
                band=round(band, 5), exact=True)


def draw_model(rng) -> dict:
    model = MODELS[rng.randint(len(MODELS))]
    return dict(model=model, params=draw_params(model, rng),
                class_weight=("balanced" if rng.rand() < 0.3 and model != "GBM.classic" else "none"),
                regime=REGIMES[rng.randint(len(REGIMES))], k=int(rng.randint(3, 6)))


# The 16 September three-way record, bench-3way-20260916-140347 and -140850:
# the slice, LINK LTC MATIC, the last 12,000 in-sample rows, a 12-bar forward
# return by row shift, three families, the depth-4 forest under three
# expanding folds, no class weight, a 365-day blind period and the default
# two-day embargo.
ANCHORS = [
    dict(name="anchor-16sep-band0.002",
         data=dict(panel="crypto-4h-slice", symbols=["LINK/USDT", "LTC/USDT", "MATIC/USDT"],
                   families=["f_hr_", "f_st_", "f_wc_"], horizon=12, band=0.002, exact=False,
                   rows=12000, embargo_days=2),
         model=dict(model="RF", params=dict(n_estimators=150, max_depth=4, min_samples_leaf=200),
                    class_weight="none", regime="expanding", k=3)),
]
ANCHORS.append(dict(ANCHORS[0], name="anchor-16sep-band0.01",
                    data=dict(ANCHORS[0]["data"], band=0.01)))
ANCHORS.append(dict(ANCHORS[0], name="anchor-16sep-exact-time",
                    data=dict(ANCHORS[0]["data"], exact=True)))


def prepare(data: dict, log=print):
    spec = PANELS[data["panel"]]
    df = load_panel(data["panel"], data["symbols"])
    cal = calendar(data["panel"])
    df["pos"] = cal.get_indexer(df["datetime"])
    if data.get("exact", True):
        # The return is read on every bar, then the screen picks the entries.
        df["ret"] = forward_return(df, data["horizon"], exact=True)
        df = df[df["in_sample"]]
    else:
        # The 16 September runs: screened rows only, return by row shift.
        df = df[df["in_sample"]].reset_index(drop=True)
        df["ret"] = forward_return(df, data["horizon"], exact=False)
    if data.get("rows"):
        # The last `rows` screened rows, as bench_run.read_capped took them.
        df = df.tail(int(data["rows"]))
    df = df[df["ret"].notna()].reset_index(drop=True)
    feats = [c for c in df.columns if c.startswith("f_") and any(c.startswith(f) for f in data["families"])]
    # The blind period in days; the holdout study moves it, every other caller
    # takes the panel's own.
    cut = df["datetime"].max() - pd.Timedelta(days=int(data.get("holdout") or spec["holdout"]))
    if data.get("embargo_days"):
        # The anchor keeps the 16 September embargo in days, to reproduce it.
        train = df[df["datetime"] <= cut - pd.Timedelta(days=data["embargo_days"])]
    else:
        # A training row is kept only if its whole forward window closes before
        # the first blind bar, counted on the market calendar.
        first_blind = int(cal.searchsorted(cut, side="right"))
        train = df[df["pos"] + data["horizon"] < first_blind]
    test = df[df["datetime"] > cut].reset_index(drop=True)
    train = train.tail(TRAIN_CAP).reset_index(drop=True)
    # A column that is empty on every training row carries nothing and some
    # learners refuse it.
    feats = [c for c in feats if train[c].notna().any()]
    for d in (train, test):
        d["y"] = three_way(d["ret"].to_numpy(float), data["band"])
    return train, test, feats, cut, spec


def run_one(tag: str, data: dict, mdl: dict, train, test, feats, cut, spec, seed: int, sink, log=print):
    t0 = time.time()
    try:
        got = score(mdl["model"], mdl["params"], mdl["class_weight"], mdl["regime"], mdl["k"], seed,
                    train, test, feats, spec["cost"], data["horizon"], spec["bar"])
    except Exception as exc:          # a draw that fails is recorded, not fatal
        got, err = None, f"{type(exc).__name__}: {exc}"
    else:
        err = None if got else "model unavailable"
    row = dict(tag=tag, seed=seed, data=data, model=mdl, cut=str(cut.date()),
               n_train=len(train), n_test=len(test), n_feats=len(feats), cost=spec["cost"],
               mix_train=_classes(train["y"].to_numpy()).round(4).tolist(),
               mix_blind=_classes(test["y"].to_numpy()).round(4).tolist(),
               seconds=round(time.time() - t0, 1), error=err, **(got or {}))
    sink.write(json.dumps(row, default=str) + "\n"); sink.flush()
    if got:
        b = got["blind"]
        log(f"  {tag:10s} {mdl['model']:11s} {mdl['regime']:14s} cv {got['cv_top']*100:+.3f}% "
            f"blind top {b['top']*100:+.3f}% (all {b['all_rows']*100:+.3f}%, p {b['p_null']:.3f}) "
            f"thin {b['thin']*100:+.3f}% n {b['n_thin']} t {b['thin_t']:.2f} ratio {got['ratio']:.2f} "
            f"[{row['seconds']:.0f}s]")
    else:
        log(f"  {tag:10s} {mdl['model']:11s} failed: {err}")
    return row


def run(draws: int, per_draw: int, seed: int, replicate: int, log=print) -> Path:
    pools = json.loads((CACHE / "pools.json").read_text())
    import pyarrow.parquet as pq
    families_of = {p: sorted({"_".join(c.split("_")[:2]) + "_"
                              for c in pq.ParquetFile(str(CACHE / f"{p}.parquet")).schema.names
                              if c.startswith("f_")}) for p in pools}
    stamp = datetime.now()
    day = REPO / "04-outputs" / "AA-evals" / stamp.strftime("%Y-%m-%d")
    day.mkdir(parents=True, exist_ok=True)
    path = mm.unclobbered(day / f"random-suite-{stamp:%Y%m%d-%H%M%S}.jsonl")
    rng = np.random.RandomState(seed)
    rows = []
    with path.open("w") as sink:
        for a in ANCHORS:
            log(f"{a['name']}: {a['data']['panel']} {' '.join(a['data']['symbols'])}")
            tr, te, feats, cut, spec = prepare(a["data"])
            log(f"  {len(tr):,} training rows, {len(te):,} blind, {len(feats)} features, cut {cut.date()}")
            rows.append(run_one(a["name"], a["data"], a["model"], tr, te, feats, cut, spec, 0, sink, log))
        for i in range(draws):
            data = draw_data(rng, pools, families_of)
            log(f"draw {i+1}/{draws}: {data['panel']} {' '.join(data['symbols'])} h{data['horizon']} "
                f"band {data['band']} {'+'.join(data['families'])}")
            try:
                tr, te, feats, cut, spec = prepare(data)
            except Exception as exc:
                log(f"  prepare failed: {exc}"); continue
            if len(tr) < 1000 or len(te) < 200 or not feats:
                log(f"  too few rows ({len(tr)} train, {len(te)} blind) or no features, skipped"); continue
            log(f"  {len(tr):,} training rows, {len(te):,} blind, {len(feats)} features, cut {cut.date()}")
            for j in range(per_draw):
                rows.append(run_one(f"d{i+1:02d}m{j+1}", data, draw_model(rng), tr, te, feats, cut,
                                    spec, int(rng.randint(1_000_000)), sink, log))
            del tr, te

        # Replication: the best model draws by blind top fifth, refitted on
        # symbols of the same panel that the original draw did not use.
        ok = [r for r in rows if not r["error"] and not r["tag"].startswith("anchor")]
        ok.sort(key=lambda r: -r["blind"]["top"])
        for r in ok[:replicate]:
            pool = [s for s in pools[r["data"]["panel"]] if s not in r["data"]["symbols"]]
            if len(pool) < 2:
                log(f"replicate {r['tag']}: no unused symbols in {r['data']['panel']}"); continue
            n = min(len(r["data"]["symbols"]), len(pool))
            data = dict(r["data"], symbols=sorted(rng.choice(pool, n, replace=False).tolist()))
            log(f"replicate {r['tag']} on {' '.join(data['symbols'])}")
            tr, te, feats, cut, spec = prepare(data)
            if len(tr) < 1000 or len(te) < 200:
                log("  too few rows, skipped"); continue
            run_one(f"rep-{r['tag']}", data, r["model"], tr, te, feats, cut, spec, r["seed"], sink, log)
    log(f"record: {path.relative_to(REPO)}")
    return path


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def report(path: Path, log=print) -> Path:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    good = [r for r in rows if not r.get("error")]
    flat = pd.DataFrame([dict(tag=r["tag"], panel=r["data"]["panel"],
                              symbols=" ".join(s.replace("/USDT", "") for s in r["data"]["symbols"]),
                              horizon=r["data"]["horizon"], band=r["data"]["band"],
                              families="+".join(f.strip("_")[2:] for f in r["data"]["families"]),
                              model=r["model"]["model"], regime=r["model"]["regime"],
                              class_weight=r["model"]["class_weight"],
                              params=json.dumps(r["model"]["params"]),
                              n_train=r["n_train"], n_test=r["n_test"], ratio=r["ratio"],
                              cv_top=r["cv_top"], top=r["blind"]["top"], all_rows=r["blind"]["all_rows"],
                              lift=r["blind"]["lift"], p_null=r["blind"]["p_null"],
                              thin=r["blind"]["thin"], n_thin=r["blind"]["n_thin"],
                              thin_t=r["blind"]["thin_t"], thin_all=r["blind"]["thin_all_rows"],
                              ll=r["blind"]["log_loss"], ll_prior=r["blind"]["log_loss_prior"])
                         for r in good])
    flat.to_csv(path.with_suffix(".csv"), index=False)
    main = flat[~flat["tag"].str.startswith(("anchor", "rep-"))]
    pct = lambda v: "n/a" if v != v else f"{v*100:+.3f}"
    L = [f"# Random settings suite, {datetime.now():%d %B %Y %H:%M}", "",
         f"{len(main)} random model draws scored, {len(rows) - len(good)} failed, from `{path.name}`. "
         "Money columns are per cent per trade after cost on the blind period; top is the fifth of "
         "rows with the largest P(bullish) minus P(bearish), thin is the same trades with overlapping "
         "windows removed, p is the share of 2,000 random picks of the same size that did as well.", ""]

    def table(d, cols):
        out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
        for _, r in d.iterrows():
            out.append("| " + " | ".join(
                pct(r[c]) if c in ("cv_top", "top", "all_rows", "lift", "thin", "thin_all") else
                (f"{r[c]:.3f}" if isinstance(r[c], float) else str(r[c])) for c in cols) + " |")
        return out

    if len(main):
        L += ["## Overall", "",
              f"Top fifth positive after cost in {int((main['top'] > 0).sum())} of {len(main)} draws; "
              f"beat taking every row in {int((main['lift'] > 0).sum())}; shuffle p at or below 0.05 in "
              f"{int((main['p_null'] <= 0.05).sum())}, where chance alone gives about {0.05*len(main):.0f}. "
              f"Non-overlapping trades positive in {int((main['thin'] > 0).sum())}, with t at or above 2 in "
              f"{int((main['thin_t'] >= 2).sum())}. Overfit ratio above 1.1 in "
              f"{int((main['ratio'] > 1.1).sum())}. Blind log loss beat the class-mix constant in "
              f"{int((main['ll'] < main['ll_prior']).sum())}.", ""]
        for key in ("panel", "model", "regime", "class_weight", "horizon"):
            g = main.groupby(key).agg(n=("top", "size"), top=("top", "median"), lift=("lift", "median"),
                                      thin=("thin", "median"), share_positive=("thin", lambda s: float((s > 0).mean())),
                                      ratio=("ratio", "median"), cv_minus_blind=("cv_top", "median"))
            g["cv_minus_blind"] = g["cv_minus_blind"] - g["top"]
            L += [f"## By {key.replace('_', ' ')}", "", "Medians across draws.", ""]
            L += table(g.reset_index(), [key, "n", "top", "lift", "thin", "share_positive", "ratio", "cv_minus_blind"])
            L += [""]
        best = main.sort_values("thin", ascending=False).head(15)
        L += ["## Best fifteen", "", "Ranked by non-overlapping after-cost return. Chosen after the "
              "fact from many draws, so the top of this list is expected to look good by chance.", ""]
        L += table(best, ["tag", "panel", "symbols", "horizon", "band", "families", "model", "regime",
                          "top", "all_rows", "p_null", "thin", "n_thin", "thin_t", "ratio"])
        L += [""]
    anc = flat[flat["tag"].str.startswith("anchor")]
    if len(anc):
        L += ["## Anchor runs", "", "The 16 September setup, rebuilt.", ""]
        L += table(anc, ["tag", "n_train", "n_test", "top", "all_rows", "p_null", "thin", "n_thin", "thin_t", "ratio"])
        L += [""]
    rep = flat[flat["tag"].str.startswith("rep-")]
    if len(rep):
        orig = flat.set_index("tag")
        L += ["## Replication", "", "The best draws refitted on unused symbols of the same panel.", ""]
        L += ["| draw | original symbols | original top | original thin | new symbols | new top | new thin | new t |",
              "|---|---|---|---|---|---|---|---|"]
        for _, r in rep.iterrows():
            o = orig.loc[r["tag"][4:]]
            L.append(f"| {r['tag'][4:]} | {o['symbols']} | {pct(o['top'])} | {pct(o['thin'])} | {r['symbols']} "
                     f"| {pct(r['top'])} | {pct(r['thin'])} | {r['thin_t']:.2f} |")
        L += [""]
    md = path.with_suffix(".md")
    md.write_text("\n".join(L) + "\n", encoding="utf-8")
    log(f"report: {md.relative_to(REPO)}")
    return md


# ---------------------------------------------------------------------------
# Blind length and regime study
# ---------------------------------------------------------------------------
#
# Operator hypotheses, 24 September 2026: that the random forest and LightGBM
# under leave-one-out or Monte Carlo resampling will give the best performance,
# and that the number of days held out as the blind period plays a critical
# part in which model comes out strongest.
#
# The resampling regime never changes the fitted model here: every model is
# refitted on the whole training window before it meets the blind period, and
# the regime only decides how its training-window score is estimated. So the
# first hypothesis is tested in the form in which it can act, as the regime
# used to choose a model. Three parts:
#
#   holdout  the cut moves; eight fixed models are refitted for blind periods
#            of 60 to 540 days and ranked on each.
#   window   one fit at the 365-day cut, and the blind year scored in separate
#            stretches of 30, 60, 90 and 180 days, which isolates the length of
#            the scored window from the training rows a shorter holdout adds.
#   regime   at the 365-day cut, each model's training-window score under all
#            seven regimes, and the blind rank of the model each regime would
#            have chosen.

STUDY_MODELS = [
    ("RF-incumbent", "RF", dict(n_estimators=150, max_depth=4, min_samples_leaf=200)),
    ("RF-mid", "RF", dict(n_estimators=200, max_depth=8, min_samples_leaf=50)),
    ("RF-deep", "RF", dict(n_estimators=200, max_depth=0, min_samples_leaf=10)),
    ("LightGBM-default", "LightGBM", dict(n_estimators=300, learning_rate=0.05, num_leaves=31)),
    ("LightGBM-regularised", "LightGBM", dict(n_estimators=300, learning_rate=0.03, num_leaves=15,
                                              min_child_samples=200, subsample=0.7, subsample_freq=1,
                                              colsample_bytree=0.7, reg_lambda=10.0)),
    ("HistGBM", "HistGBM", dict(max_iter=300, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=100)),
    ("LogReg.glm", "LogReg.glm", dict(C=0.1)),
    ("LogReg.enet", "LogReg.enet", dict(C=0.1, l1_ratio=0.5)),
]
STUDY_HOLDOUTS = (60, 90, 180, 270, 365, 540)
STUDY_WINDOWS = (30, 60, 90, 180)


def study_setups(pools: dict, families_of: dict, seed: int) -> list[dict]:
    """Two fixed data setups per panel, all feature families, band equal to cost."""
    rng = np.random.RandomState(seed)
    out = []
    for panel, n, horizon in (("crypto-4h", 6, 12), ("crypto-1h", 5, 24), ("equity-1d", 8, 12)):
        for rep in range(2):
            syms = sorted(rng.choice(pools[panel], min(n, len(pools[panel])), replace=False).tolist())
            out.append(dict(panel=panel, symbols=syms, families=families_of[panel], horizon=horizon,
                            band=PANELS[panel]["cost"], exact=True, setup=f"{panel}-{rep + 1}"))
    return out


def _blind_proba(model, params, train, test, feats, seed=0):
    est = br.make_estimator(model, "none", dict(params, random_state=seed))
    est.fit(train[feats], train["y"].to_numpy())
    return _proba(est, test[feats])


def _cv_claim(model, params, regime, train, feats, cost, horizon, seed=0, k=3):
    X, y = train[feats], train["y"].to_numpy()
    folds = br.folds_of(len(train), k, regime, repeats=3, boot=5, seed=seed,
                        limit={"leave-one-out": 30}.get(regime))
    ps, idx = [], []
    for tr, te in folds:
        e = br.make_estimator(model, "none", dict(params, random_state=seed))
        e.fit(X.iloc[tr], y[tr])
        ps.append(_proba(e, X.iloc[te])); idx.append(te)
    i = np.concatenate(idx)
    return money(train.iloc[i].reset_index(drop=True), np.vstack(ps), cost, horizon,
                 None, np.random.RandomState(seed))


def study(seed: int, parts: tuple[str, ...], log=print) -> Path:
    pools = json.loads((CACHE / "pools.json").read_text())
    import pyarrow.parquet as pq
    families_of = {p: sorted({"_".join(c.split("_")[:2]) + "_"
                              for c in pq.ParquetFile(str(CACHE / f"{p}.parquet")).schema.names
                              if c.startswith("f_")}) for p in pools}
    stamp = datetime.now()
    day = REPO / "04-outputs" / "AA-evals" / stamp.strftime("%Y-%m-%d")
    day.mkdir(parents=True, exist_ok=True)
    path = mm.unclobbered(day / f"blind-length-study-{stamp:%Y%m%d-%H%M%S}.jsonl")
    rng = np.random.RandomState(seed)
    with path.open("w") as sink:
        put = lambda row: (sink.write(json.dumps(row, default=str) + "\n"), sink.flush())
        for data in study_setups(pools, families_of, seed):
            log(f"{data['setup']}: {' '.join(data['symbols'])} h{data['horizon']}")
            spec = PANELS[data["panel"]]
            if "holdout" in parts:
                for h in STUDY_HOLDOUTS:
                    tr, te, feats, cut, _ = prepare(dict(data, holdout=h))
                    if len(tr) < 1000 or len(te) < 100:
                        log(f"  holdout {h}: {len(tr)} train, {len(te)} blind, skipped"); continue
                    for name, model, params in STUDY_MODELS:
                        m = money(te, _blind_proba(model, params, tr, te, feats), spec["cost"],
                                  data["horizon"], None, rng, null=True)
                        put(dict(kind="holdout", setup=data["setup"], data=data, holdout=h,
                                 cut=str(cut.date()), n_train=len(tr), n_test=len(te), name=name, **m))
                    log(f"  holdout {h}: {len(tr):,} train, {len(te):,} blind, cut {cut.date()}")
            if "window" in parts or "regime" in parts:
                tr, te, feats, cut, _ = prepare(dict(data, holdout=365))
                probas = {}
                for name, model, params in STUDY_MODELS:
                    probas[name] = _blind_proba(model, params, tr, te, feats)
                    full = money(te, probas[name], spec["cost"], data["horizon"], None, rng, null=True)
                    put(dict(kind="window", setup=data["setup"], window=365, start=str(cut.date()),
                             name=name, **full))
                if "window" in parts:
                    for w in STUDY_WINDOWS:
                        edges = pd.date_range(cut, periods=365 // w + 1, freq=f"{w}D")
                        for lo, hi in zip(edges[:-1], edges[1:]):
                            sel = ((te["datetime"] > lo) & (te["datetime"] <= hi)).to_numpy()
                            if sel.sum() < 50:
                                continue
                            sub = te[sel].reset_index(drop=True)
                            for name in probas:
                                m = money(sub, probas[name][sel], spec["cost"], data["horizon"], None, rng)
                                put(dict(kind="window", setup=data["setup"], window=w,
                                         start=str(lo.date()), name=name, **m))
                    log(f"  windows scored at cut {cut.date()}")
                # Regimes on the first setup of each panel only: every regime
                # is about 56 fits a model, and on this machine that is the
                # cost that decides whether the study finishes overnight.
                if "regime" in parts and data["setup"].endswith("-1"):
                    for name, model, params in STUDY_MODELS:
                        for regime in REGIMES:
                            t0 = time.time()
                            m = _cv_claim(model, params, regime, tr, feats, spec["cost"], data["horizon"])
                            put(dict(kind="regime", setup=data["setup"], name=name, regime=regime,
                                     claim_top=m["top"], claim_thin=m["thin"],
                                     seconds=round(time.time() - t0, 1)))
                        log(f"  regimes scored for {name}")
    log(f"record: {path.relative_to(REPO)}")
    return path


def study_report(path: Path, log=print) -> Path:
    from scipy.stats import spearmanr
    rows = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    df = pd.DataFrame(rows)
    pct = lambda v: "n/a" if v != v else f"{v*100:+.3f}"
    L = [f"# Blind length and regime study, {datetime.now():%d %B %Y %H:%M}", "",
         f"From `{path.name}`. Money is per cent per trade after cost on the top fifth of rows by "
         "P(bullish) minus P(bearish); thin is the same trades with overlapping windows removed.", ""]

    ho = df[df["kind"] == "holdout"] if "kind" in df else df.iloc[0:0]
    if len(ho):
        L += ["## Moving the cut", "", "The winning model at each blind length, by top fifth after cost, "
              "and the Spearman rank correlation of the eight models' order against their order at 365 days.", "",
              "| setup | blind days | cut | winner | winner top | runner-up top | all rows | rank corr. with 365 |",
              "|---|---|---|---|---|---|---|---|"]
        for setup, g in ho.groupby("setup", sort=False):
            ref = g[g["holdout"] == 365].set_index("name")["top"]
            for h, gh in g.groupby("holdout"):
                gh = gh.sort_values("top", ascending=False)
                common = gh.set_index("name")["top"].reindex(ref.index)
                rho = spearmanr(common, ref).correlation if len(ref) and common.notna().all() else float("nan")
                L.append(f"| {setup} | {h} | {gh['cut'].iloc[0]} | {gh['name'].iloc[0]} | {pct(gh['top'].iloc[0])} "
                         f"| {pct(gh['top'].iloc[1])} | {pct(gh['all_rows'].iloc[0])} | {rho:+.2f} |")
        wins = ho.loc[ho.groupby(["setup", "holdout"])["top"].idxmax(), "name"].value_counts()
        L += ["", "Wins by model across every setup and blind length: "
              + ", ".join(f"{k} {v}" for k, v in wins.items()) + ".", ""]

    wi = df[df["kind"] == "window"] if "kind" in df else df.iloc[0:0]
    if len(wi):
        L += ["## Same fit, shorter windows", "", "One fit per model at the 365-day cut. Each window length "
              "splits the blind year into separate stretches, and the stretch's winner is recorded.", "",
              "| setup | window days | stretches | distinct winners | year winner wins | median best minus worst |",
              "|---|---|---|---|---|---|"]
        for setup, g in wi.groupby("setup", sort=False):
            year = g[g["window"] == 365]
            yw = year.sort_values("top", ascending=False)["name"].iloc[0]
            for w in STUDY_WINDOWS:
                gw = g[g["window"] == w]
                if gw.empty:
                    continue
                per = gw.groupby("start")
                winners = per.apply(lambda x: x.sort_values("top", ascending=False)["name"].iloc[0])
                spread = per["top"].agg(lambda s: s.max() - s.min())
                L.append(f"| {setup} | {w} | {len(winners)} | {winners.nunique()} | "
                         f"{int((winners == yw).sum())} | {spread.median()*100:.3f} |")
            L.append(f"| {setup} | 365 | 1 | 1 | year winner {yw} at {pct(year['top'].max())} | "
                     f"{(year['top'].max() - year['top'].min())*100:.3f} |")
        L += [""]

    rg = df[df["kind"] == "regime"] if "kind" in df else df.iloc[0:0]
    if len(rg) and len(wi):
        blind = wi[wi["window"] == 365].set_index(["setup", "name"])["top"]
        L += ["## Choosing by regime", "", "For each regime, the model with the best training-window top "
              "fifth, where that model ranked on the blind year out of eight, and the Spearman correlation "
              "between the eight claims and the eight blind results. Rank 1 is the best blind model.", "",
              "| setup | regime | chosen | its blind rank | its blind top | claim | claim vs blind corr. |",
              "|---|---|---|---|---|---|---|"]
        for (setup, regime), g in rg.groupby(["setup", "regime"], sort=False):
            b = blind.loc[setup]
            rank = b.rank(ascending=False)
            pick = g.sort_values("claim_top", ascending=False).iloc[0]
            rho = spearmanr(g.set_index("name")["claim_top"].reindex(b.index), b).correlation
            L.append(f"| {setup} | {regime} | {pick['name']} | {int(rank[pick['name']])} | "
                     f"{pct(b[pick['name']])} | {pct(pick['claim_top'])} | {rho:+.2f} |")
        L += [""]
    md = path.with_suffix(".md")
    md.write_text("\n".join(L) + "\n", encoding="utf-8")
    log(f"report: {md.relative_to(REPO)}")
    return md


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("cache")
    r = sub.add_parser("run")
    r.add_argument("--draws", type=int, default=40)
    r.add_argument("--per-draw", type=int, default=5)
    r.add_argument("--seed", type=int, default=20260923)
    r.add_argument("--replicate", type=int, default=5)
    p = sub.add_parser("report")
    p.add_argument("path")
    st = sub.add_parser("study")
    st.add_argument("--seed", type=int, default=20260924)
    st.add_argument("--parts", nargs="*", default=["holdout", "window", "regime"])
    sr = sub.add_parser("study-report")
    sr.add_argument("path")
    a = ap.parse_args()
    if a.cmd == "cache":
        build_cache()
    elif a.cmd == "run":
        report(run(a.draws, a.per_draw, a.seed, a.replicate))
    elif a.cmd == "study":
        study_report(study(a.seed, tuple(a.parts)))
    elif a.cmd == "study-report":
        study_report(Path(a.path))
    else:
        report(Path(a.path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
