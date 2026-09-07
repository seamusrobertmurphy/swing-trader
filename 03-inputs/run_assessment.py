"""Run the caret-style model assessment per frame and persist the record.

WHY THIS EXISTS. The notebook did this inline with RECOMPUTE=True, refitting a
model zoo across three frames from inside a document meant to be read end to
end. On 2026-09-06 that cell was still running after fifteen minutes and took
the whole audit run down with it. The work belongs in a script; the notebook
should display what the script persisted.

Bounded on purpose. This machine has 8 GB shared with its graphics chip and the
4h panel alone is 3.9 million rows, so each frame is sampled rather than loaded
whole, and the sample is the most recent rows so the assessment describes the
market as it is now.

    .venv/bin/python 03-inputs/run_assessment.py --frames 1d 4h --rows 40000
"""
from __future__ import annotations

import argparse
import sys
import time

import build_dataset_1h as bd
import model_assessment_1h as ma
import train_model as tm
import train_model_1h as t1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", nargs="+", default=["1d", "4h"])
    ap.add_argument("--rows", type=int, default=40_000)
    ap.add_argument("--cv-splits", type=int, default=3)
    ap.add_argument("--models", nargs="+",
                    default=["logreg.glm", "RF", "HistGBM", "LightGBM"],
                    help="the bounded zoo; stacking is omitted because it refits every base model")
    a = ap.parse_args()

    for frame in a.frames:
        print(f"\n{'='*78}\nframe {frame}\n{'='*78}", flush=True)
        t0 = time.time()
        try:
            bd.configure(frame)
            df = t1.load(bd.DATASET_PATH)
        except Exception as e:
            print(f"  skipped: {e}")
            continue
        feat = bd.feature_columns(df)
        if len(df) > a.rows:
            df = df.tail(a.rows).reset_index(drop=True)
        print(f"  {len(df):,} rows, {len(feat)} features, models {a.models}", flush=True)

        rows, train, test, cut = ma.assess(df, feat, a.models, a.cv_splits)
        best = min(rows, key=lambda r: r["cv_rmse"])
        blind = ma.blind_metrics(best["est"], train, test, feat,
                                 tm.COST_PCT / 100.0, tm.CONF_HI)
        md, b, verdict = ma.write_record(
            rows, blind, dict(rows=len(df), n_feat=len(feat)),
            f"{ma.REPO if hasattr(ma,'REPO') else tm.OUT}/AA-evals"
            if False else f"{tm.OUT}/AA-evals")
        print(f"\n  best by CV RMSE: {b['model']}  RMSEratio {b['rmse_ratio']:.3f}  "
              f"blind net {blind['net']*100:+.3f}%/trade  verdict {verdict}")
        print(f"  record: {md}   [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    sys.exit(main())
