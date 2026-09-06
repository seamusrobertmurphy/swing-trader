"""One error-metric layer for every model in this repo, and the record the dashboard reads.

WHY THIS EXISTS. Until now each script computed its own errors its own way, so a
number on one page could not be set beside a number on another. Worse, the
overfit ratio was computed upside down (see RMSE_RATIO below). This module is
the single definition, written once, so the seven-model sklearn zoo and the
sequence models that come next produce rows that can sit in the same table.

THE FOUR NUMBERS.

  RMSE  root mean squared error. Average miss, in the target's own units, with
        big misses counted much harder than small ones because the error is
        squared before averaging. Lower is better. Nothing else here punishes a
        rare disaster the way this does.

  MAE   mean absolute error. Average miss, in the target's own units, every miss
        counted once. Lower is better. Read it beside RMSE: when RMSE is much
        the larger of the two, the model is occasionally very wrong rather than
        steadily slightly wrong.

  MAPE  mean absolute percentage error. The same average miss written as a share
        of the true value, so "off by 28 per cent" rather than "off by 11 bars".
        It divides by the observed value, so it exists only for a target that is
        never zero. Counting bars until a trend flips is never zero and MAPE is
        defined; a nought-or-one label is zero for most rows and it is not. The
        functions below return None in that case rather than a silent infinity.

  RMSE ratio  the cross-validated RMSE divided by the training RMSE. One means
        the model errs as much on data it has not seen as on data it fitted,
        which is what an honest model does. Above 1.1 it is rejected: it has
        memorised the training window. This direction is the house standard in
        CLAUDE.md and it is the opposite of what model_assessment_1h.py computed
        until 2026-09-05, where an overfit model scored 0.91 and a reader
        applying the "reject above 1.1" rule would have passed it.

WHAT CROSS-VALIDATION MEANS HERE. Not random k-fold. Market bars are
autocorrelated, so a random split puts next Tuesday in the training set and
scores the model on last Monday, which leaks the future into the past and
flatters everything. Folds here walk forward: fit on a block, score the block
after it, extend, repeat. Each fold's held-out score is kept separately so the
dashboard can show the spread rather than one average that hides it.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "outputs" / "AA-evals"
ET = ZoneInfo("America/New_York")

# Above this, the model is rejected as overfit. CLAUDE.md, statistical
# reporting rule 8, following Murphy et al. (2026) Table 5.
RMSE_RATIO_REJECT = 1.1

# A target whose values are all at least this far from zero is safe to divide
# by. Below it MAPE explodes on a handful of rows and reports a number in the
# thousands that describes those rows and nothing else.
MAPE_FLOOR = 1e-6


def rmse(y, p) -> float:
    """Root mean squared error, in the target's units. Big misses count harder."""
    y, p = np.asarray(y, float), np.asarray(p, float)
    return float(np.sqrt(np.mean((p - y) ** 2)))


def mae(y, p) -> float:
    """Mean absolute error, in the target's units. Every miss counts once."""
    y, p = np.asarray(y, float), np.asarray(p, float)
    return float(np.mean(np.abs(p - y)))


def mape(y, p):
    """Mean absolute percentage error, or None when the target reaches zero.

    Returns None rather than infinity or a silently dropped subset, because a
    MAPE computed on only the non-zero rows is a different quantity from the one
    the name promises and nothing downstream would know.
    """
    y, p = np.asarray(y, float), np.asarray(p, float)
    if y.size == 0 or np.any(np.abs(y) < MAPE_FLOOR):
        return None
    return float(np.mean(np.abs((p - y) / y)) * 100.0)


def is_mape_defined(y) -> bool:
    """Whether this target can carry a percentage error at all."""
    y = np.asarray(y, float)
    return bool(y.size) and not bool(np.any(np.abs(y) < MAPE_FLOOR))


def errors(y, p) -> dict:
    """All three errors on one set of predictions."""
    return dict(rmse=rmse(y, p), mae=mae(y, p), mape=mape(y, p))


def walk_forward_folds(n: int, splits: int = 5):
    """Expanding forward-chained fold boundaries over n rows already in time order.

    Yields (train_end, test_start, test_end). The first fold trains on the first
    block and scores the second; each later fold keeps everything before it. No
    row is ever scored by a model that saw a later row, which is the whole point.
    """
    if splits < 2 or n < splits + 1:
        return
    edge = n // (splits + 1)
    for k in range(1, splits + 1):
        tr_end = edge * k
        te_end = edge * (k + 1) if k < splits else n
        if te_end > tr_end:
            yield tr_end, tr_end, te_end


def score_run(y_train, p_train, folds: list) -> dict:
    """Assemble one model's row from its in-sample fit and its walk-forward folds.

    y_train / p_train  the training window and the model's predictions on it,
                       the optimistic fit that shows what it can memorise.
    folds              one (y, p) pair per held-out fold, in time order.

    The returned dict is the record format. Every producer in this repo writes
    it and the dashboard reads only this.
    """
    train = errors(y_train, p_train)
    per_fold = []
    for i, (yf, pf) in enumerate(folds, start=1):
        e = errors(yf, pf)
        per_fold.append(dict(fold=i, n=int(np.asarray(yf).size), **e))

    if per_fold:
        cv = dict(
            rmse=float(np.mean([f["rmse"] for f in per_fold])),
            mae=float(np.mean([f["mae"] for f in per_fold])),
            mape=(float(np.mean([f["mape"] for f in per_fold]))
                  if all(f["mape"] is not None for f in per_fold) else None),
        )
        ratio = cv["rmse"] / train["rmse"] if train["rmse"] else float("nan")
    else:
        cv, ratio = dict(rmse=None, mae=None, mape=None), float("nan")

    return dict(
        train=train, cv=cv, folds=per_fold,
        rmse_ratio=ratio,
        overfit=bool(np.isfinite(ratio) and ratio > RMSE_RATIO_REJECT),
        reject_above=RMSE_RATIO_REJECT,
    )


def write_record(rows: list, *, frame: str, target: str, target_kind: str,
                 panel: str = "", note: str = "") -> Path:
    """Persist a set of scored models to outputs/AA-evals/<exchange date>/.

    rows        one dict per model: {"model": name, "params": {...}, **score_run(...)}
    frame       the bar size the model was trained on, e.g. "4h" or "1d"
    target      what it predicted, e.g. "bars_to_flip"
    target_kind "regression" or "probability". The dashboard uses this to decide
                whether a percentage error can exist at all.
    panel       which dataset, e.g. "crypto 4h, 567 coins"
    """
    stamp = datetime.now(ET)
    day = EVALS / f"{stamp:%Y-%m-%d}"
    day.mkdir(parents=True, exist_ok=True)
    path = day / f"model-metrics-{stamp:%Y%m%d-%H%M}.json"
    path.write_text(json.dumps(dict(
        stamped=stamp.isoformat(timespec="seconds"),
        frame=frame, target=target, target_kind=target_kind,
        panel=panel, note=note, models=rows,
    ), indent=2), encoding="utf-8")
    return path


def read_records(limit: int = 40) -> list:
    """Every metrics record on disk, newest first. Used by the dashboard emitter."""
    out = []
    for p in sorted(EVALS.glob("*/model-metrics-*.json"), reverse=True)[:limit]:
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        d["file"] = str(p.relative_to(REPO))
        out.append(d)
    return out
