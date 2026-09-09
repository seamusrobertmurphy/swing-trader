"""Each predictor fitted alone, tested against an intercept-only null.

    .venv/bin/python 03-inputs/univariate_screen.py            # the active bench config
    .venv/bin/python 03-inputs/univariate_screen.py --rows 20000

Asked for by the operator on 8 September 2026 as the first half of variable
selection, and the repository had none of it. What existed was an elastic net,
which answers a different question: the net says which predictors survive
*together* under a penalty, and this says what each one is worth *alone*. A
column can be strong alone and dropped by the net because another column carries
the same information, and a column can be worthless alone and kept because it is
useful beside something else. Both readings are needed and neither substitutes.

Three quantities per predictor.

The estimate is the logistic coefficient, in log-odds, with its 95 per cent
interval from the fitted standard error. It is reported on the standardised
column, so the magnitudes compare across predictors measured on different
scales, which is what "ranked by magnitude" requires.

The likelihood ratio statistic is twice the difference in log-likelihood between
the model with that one predictor and a model with only an intercept. Under the
null that the predictor adds nothing it is chi-squared on one degree of freedom,
so 3.84 is the five per cent point and 6.63 the one per cent point.

The p-value follows from that statistic. It is reported with a floor of
p < 0.001 rather than as zero, and it is not corrected for multiple testing
here: ninety predictors tested at five per cent produce four or five apparent
findings from noise alone, so the count of predictors is printed beside the
count that cleared, and the ranking is what the panel reads rather than the
individual p-values.

Everything is computed on the training window. The blind period is never opened.
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench_config as bc          # noqa: E402
import bench_run as br             # noqa: E402
import model_metrics as mm         # noqa: E402
import train_model_1h as t1        # noqa: E402

warnings.filterwarnings("ignore")

OUT = bc.REPO / "04-outputs" / "AA-evals" / "varselect"

# The chi-squared points on one degree of freedom, so the panel can mark them
# without pulling in a distribution table at draw time.
CHI2_05, CHI2_01 = 3.841459, 6.634897


def _chi2_sf(x: float) -> float:
    """Survival function of chi-squared on one degree of freedom.

    One degree of freedom has a closed form, the complementary error function of
    the root of half the statistic, so this needs no scipy.
    """
    from math import erfc, sqrt
    return float(erfc(sqrt(max(x, 0.0) / 2.0)))


def fit_one(x: np.ndarray, y: np.ndarray, null_ll: float) -> dict | None:
    """One predictor, standardised, against the intercept-only null."""
    from sklearn.linear_model import LogisticRegression

    ok = np.isfinite(x)
    if ok.sum() < 200:
        return None
    xs, ys = x[ok], y[ok]
    sd = xs.std()
    if not np.isfinite(sd) or sd == 0:
        return None                                   # a constant column
    xs = ((xs - xs.mean()) / sd).reshape(-1, 1)

    # No penalty. A penalised coefficient is not the maximum-likelihood estimate
    # and its likelihood ratio against an unpenalised null is not a test.
    est = LogisticRegression(penalty=None, max_iter=2000).fit(xs, ys)
    p = np.clip(est.predict_proba(xs)[:, 1], 1e-12, 1 - 1e-12)
    ll = float(np.sum(ys * np.log(p) + (1 - ys) * np.log(1 - p)))

    # The null is refitted on the same rows, because a predictor with gaps is
    # scored on fewer observations and comparing its likelihood against a null
    # fitted on all of them would credit it for the rows it never saw.
    base = float(ys.mean())
    null_here = float(np.sum(ys * np.log(base) + (1 - ys) * np.log(1 - base)))

    coef = float(est.coef_[0][0])
    lr = 2.0 * (ll - null_here)
    # The standard error of a logistic coefficient is the root of the inverse
    # information; with one standardised predictor it is the root reciprocal of
    # the summed p(1-p) weighted second moment.
    w = p * (1 - p)
    info = float(np.sum(w * xs[:, 0] ** 2) - np.sum(w * xs[:, 0]) ** 2 / np.sum(w))
    se = float(np.sqrt(1.0 / info)) if info > 0 else float("nan")
    return dict(coef=coef, se=se,
                lo=coef - 1.96 * se, hi=coef + 1.96 * se,
                lr=lr, p=_chi2_sf(lr), n=int(ok.sum()),
                loglik=ll, null_loglik=null_here)


def run(cfg: dict, rows_cap: int | None = None, log=print) -> dict:
    df, available = br.load_frame(cfg, log=log)
    feats = br.choose_features(cfg, available, log=log)
    train, _test, cut = t1.split(df, oos_days=int(cfg["split"]["holdout_days"]))
    if rows_cap and len(train) > rows_cap:
        train = train.tail(rows_cap)
    y = train["label"].to_numpy(float)
    base = float(y.mean())
    null_ll = float(np.sum(y * np.log(base) + (1 - y) * np.log(1 - base)))
    log(f"{len(train):,} training rows to {cut.date()}, base rate {base:.3f}, "
        f"{len(feats)} predictors")

    out = []
    for name in feats:
        got = fit_one(train[name].to_numpy(float), y, null_ll)
        if got:
            out.append(dict(feature=name, **got))
    out.sort(key=lambda r: -abs(r["coef"]))

    cleared_05 = sum(1 for r in out if r["lr"] > CHI2_05)
    cleared_01 = sum(1 for r in out if r["lr"] > CHI2_01)
    expected = 0.05 * len(out)
    log(f"{cleared_05} of {len(out)} cleared the five per cent point, against "
        f"{expected:.0f} expected from noise alone; {cleared_01} cleared one per cent")
    return dict(rows=out, n_train=len(train), base_rate=base, cut=str(cut.date()),
                null_loglik=null_ll, cleared_05=cleared_05, cleared_01=cleared_01,
                expected_by_chance=expected, config=cfg)


def write_record(res: dict, log=print) -> Path:
    stamp = datetime.now()
    OUT.mkdir(parents=True, exist_ok=True)
    js = mm.unclobbered(OUT / f"univariate-{stamp:%Y%m%d-%H%M%S}.json")
    js.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")

    md = js.with_suffix(".md")
    rows = res["rows"]
    L = [f"# Univariate screen, {stamp:%d %B %Y %H:%M}", "",
         bc.describe(res["config"]), "",
         f"Each predictor fitted alone on {res['n_train']:,} training rows to "
         f"{res['cut']}, base rate {res['base_rate']:.3f}, and tested against an "
         f"intercept-only model by likelihood ratio. The statistic is chi-squared "
         f"on one degree of freedom, so 3.84 is the five per cent point and 6.63 "
         f"the one per cent point. Estimates are on standardised columns so their "
         f"magnitudes compare, and the table is ranked by magnitude.", "",
         f"**{res['cleared_05']} of {len(rows)} predictors cleared the five per cent "
         f"point, against {res['expected_by_chance']:.0f} expected from noise alone "
         f"at that many tests.** {res['cleared_01']} cleared one per cent. No "
         f"multiple-testing correction is applied, so the ranking is the reading "
         f"and an individual p-value near the threshold is not a finding.", "",
         "| predictor | estimate | 95% interval | likelihood ratio | p | rows |",
         "| --- | ---: | :---: | ---: | ---: | ---: |"]
    for r in rows[:40]:
        pv = "< 0.001" if r["p"] < 0.001 else f"{r['p']:.3f}"
        L.append(f"| {r['feature']} | {r['coef']:+.4f} "
                 f"| {r['lo']:+.4f} to {r['hi']:+.4f} | {r['lr']:.2f} | {pv} "
                 f"| {r['n']:,} |")
    if len(rows) > 40:
        L.append(f"\nFirst 40 of {len(rows)}.")
    L += ["", "An elastic net answers the other half of the question: which of "
              "these survive together under a penalty. A predictor strong alone "
              "can be dropped there because another carries the same information, "
              "and one worthless alone can be kept because it is useful beside "
              "something else. Both readings are needed and neither substitutes.", ""]
    md.write_text("\n".join(L) + "\n", encoding="utf-8")
    log(f"record: {md.relative_to(bc.REPO)}")
    return md


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=None)
    ap.add_argument("--rows", type=int, default=25000,
                    help="training rows to fit on; 0 uses every row in the window")
    a = ap.parse_args()
    cfg = bc.load(Path(a.config) if a.config else None)
    res = run(cfg, a.rows or None)
    write_record(res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
