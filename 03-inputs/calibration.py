"""Are the model's probabilities honest, and can they be made honest.

WHY THIS EXISTS. Every model in this repository emits a probability and is scored
on the Brier score, which is the mean squared distance between that probability
and the outcome. Nothing anywhere checked whether the probability means what it
says: whether the bars the model called 30 per cent actually rose 30 per cent of
the time. A model can rank well and still be badly calibrated, and a badly
calibrated probability cannot be used for sizing, because Kelly takes p as an
input and a p that is wrong by ten points sizes the book wrong by more.

There is a specific reason to expect miscalibration here. Every model in the zoo
is fitted with `class_weight="balanced"`, which reweights the minority class and
pushes predicted probabilities away from the base rate by construction. That is
useful for ranking and actively harmful for the metric the models are graded on.

WHAT IT MEASURES.

  reliability   The observed frequency of the outcome within each decile of
                predicted probability. Perfect calibration lies on the diagonal.
                Reported as a table and a chart.
  ECE           Expected calibration error, the average gap between predicted and
                observed frequency, weighted by how many observations fall in each
                bin. One number, in probability units.
  MCE           Maximum calibration error, the widest gap in any bin. ECE can look
                acceptable while one bin is badly wrong, which is the bin a
                confidence threshold would trade on.
  Brier decomp  Murphy's decomposition, Brier = reliability - resolution +
                uncertainty. Reliability is the calibration penalty and falls to
                zero for a perfectly calibrated model. Resolution is how far the
                model's bins depart from the base rate, so it rewards
                discrimination. Uncertainty is the base rate's own variance and is
                a property of the data, not of the model.

WHAT IT FIXES. Two standard post-hoc maps, both fitted on a held-out slice of the
training window and never on the blind year:

  Platt      a one-parameter logistic fit of outcome on the log-odds of the raw
             probability. Cheap, monotone, and it cannot invent structure.
  isotonic   a non-parametric monotone fit. More flexible and more prone to
             overfitting on a small calibration set, so it is reported beside
             Platt rather than instead of it.

Calibration is monotone, so it cannot change AUC or the ordering of trades. It
changes the numbers a threshold and a sizing rule read, which is the point.

    .venv/bin/python 03-inputs/calibration.py --interval 4h --rows 120000
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.calibration import IsotonicRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_dataset_1h as bd          # noqa: E402
import model_metrics as mm             # noqa: E402
import train_model_1h as t1            # noqa: E402

N_BINS = 10


def reliability(y, p, n_bins: int = N_BINS) -> pd.DataFrame:
    """Observed frequency against predicted probability, by equal-width bin.

    Equal-width rather than equal-count, because the question is whether a stated
    30 per cent happens 30 per cent of the time, and that question is asked of a
    probability band, not of a quantile of the model's own output.
    """
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1], right=False), 0, n_bins - 1)
    rows = []
    for b in range(n_bins):
        m = idx == b
        if not m.any():
            continue
        rows.append(dict(bin=f"{edges[b]:.1f}-{edges[b+1]:.1f}", n=int(m.sum()),
                         predicted=float(p[m].mean()), observed=float(y[m].mean())))
    d = pd.DataFrame(rows)
    d["gap"] = d["observed"] - d["predicted"]
    return d


def calibration_errors(y, p, n_bins: int = N_BINS) -> dict:
    d = reliability(y, p, n_bins)
    w = d["n"] / d["n"].sum()
    return dict(ece=float((w * d["gap"].abs()).sum()),
                mce=float(d["gap"].abs().max()),
                bins=len(d))


def brier_decomposition(y, p, n_bins: int = N_BINS) -> dict:
    """Murphy's decomposition: Brier = reliability - resolution + uncertainty."""
    d = reliability(y, p, n_bins)
    n = len(y)
    base = float(np.mean(y))
    rel = float((d["n"] * (d["predicted"] - d["observed"]) ** 2).sum() / n)
    res = float((d["n"] * (d["observed"] - base) ** 2).sum() / n)
    unc = base * (1.0 - base)
    return dict(brier=float(np.mean((p - y) ** 2)), reliability=rel,
                resolution=res, uncertainty=unc, base_rate=base)


def fit_platt(p_cal, y_cal):
    """One-parameter logistic on the log-odds of the raw probability."""
    z = np.log(np.clip(p_cal, 1e-6, 1 - 1e-6) / (1 - np.clip(p_cal, 1e-6, 1 - 1e-6)))
    lr = LogisticRegression(C=1e6, solver="lbfgs").fit(z.reshape(-1, 1), y_cal)
    return lambda p: lr.predict_proba(
        np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6))).reshape(-1, 1))[:, 1]


def fit_isotonic(p_cal, y_cal):
    iso = IsotonicRegression(out_of_bounds="clip").fit(p_cal, y_cal)
    return lambda p: iso.predict(p)


def run(frame: str, rows_cap: int, balanced: bool = True) -> dict:
    bd.configure(frame)
    path = bd.DATASET_PATH
    if not os.path.exists(path):
        raise SystemExit(f"no dataset for {frame} at {path}")
    df = t1.load(path)
    feat = bd.feature_columns(df)
    train, test, cut = t1.split(df)
    del df
    if rows_cap and len(train) > rows_cap:
        train = train.tail(rows_cap)
    train = train.sort_values("datetime")

    # The last fifth of the training window is the calibration set. It is held out
    # of the fit, and it is taken from TRAIN rather than from the blind year, which
    # a calibration fit would otherwise spend.
    cut_i = int(len(train) * 0.8)
    fit_part, cal_part = train.iloc[:cut_i], train.iloc[cut_i:]

    def _pipe():
        kw = dict(class_weight="balanced") if balanced else {}
        return Pipeline([("impute", SimpleImputer(strategy="median")),
                         ("clf", HistGradientBoostingClassifier(
                             max_iter=200, learning_rate=0.06, max_depth=6,
                             min_samples_leaf=100, random_state=0, **kw))])

    est = _pipe().fit(fit_part[feat], fit_part["label"])
    p_cal = est.predict_proba(cal_part[feat])[:, 1]
    y_cal = cal_part["label"].to_numpy()
    p_te = est.predict_proba(test[feat])[:, 1]
    y_te = test["label"].to_numpy()

    maps = {"raw": lambda p: p,
            "Platt": fit_platt(p_cal, y_cal),
            "isotonic": fit_isotonic(p_cal, y_cal)}
    out = {}
    for name, f in maps.items():
        p = np.clip(f(p_te), 0.0, 1.0)
        out[name] = dict(**calibration_errors(y_te, p), **brier_decomposition(y_te, p),
                         table=reliability(y_te, p))
    return dict(frame=frame, cut=str(cut.date()), n_fit=len(fit_part), n_cal=len(cal_part),
                n_test=len(test), base=float(y_te.mean()), balanced=balanced, results=out)


def write_record(r: dict, out_dir) -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    day = os.path.join(str(out_dir), datetime.now().strftime("%Y-%m-%d"))
    os.makedirs(day, exist_ok=True)
    tag = "balanced" if r["balanced"] else "unweighted"
    path = os.path.join(day, f"calibration-{r['frame']}-{tag}-{stamp}.md")

    L = [f"# Probability calibration, {r['frame']} frame ({datetime.now():%d %B %Y})\n",
         f"Fitted on {r['n_fit']:,} training observations to {r['cut']}, calibrated on a held-out "
         f"{r['n_cal']:,}-row slice of the same training window, and scored once on the "
         f"{r['n_test']:,}-row blind year. Base rate {r['base']:.3f}. The estimator carries "
         f"`class_weight={'balanced' if r['balanced'] else 'None'}`.\n",
         "A calibrated probability means what it says: of the observations the model called "
         "30 per cent, 30 per cent should have gone on to hit the barrier. Expected calibration "
         "error is the average gap between predicted and observed frequency weighted by bin "
         "population; maximum calibration error is the widest gap in any bin, which matters "
         "because a confidence threshold trades inside one bin rather than across the average.\n",
         "## Summary\n",
         "| mapping | ECE | MCE | Brier | reliability | resolution | uncertainty |",
         "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for name, d in r["results"].items():
        L.append(f"| {name} | {d['ece']:.4f} | {d['mce']:.4f} | {d['brier']:.4f} | "
                 f"{d['reliability']:.5f} | {d['resolution']:.5f} | {d['uncertainty']:.4f} |")
    L.append("\nBrier decomposes as reliability minus resolution plus uncertainty. Reliability is "
             "the calibration penalty and falls toward zero as a mapping does its job. Resolution "
             "rewards departure from the base rate and is a property of the ranking, so a monotone "
             "mapping leaves it close to unchanged. Uncertainty is the base rate's own variance and "
             "belongs to the data.\n")

    for name, d in r["results"].items():
        L.append(f"\n## Reliability, {name}\n")
        L.append("| predicted band | n | mean predicted | observed frequency | gap |")
        L.append("| --- | ---: | ---: | ---: | ---: |")
        for _, row in d["table"].iterrows():
            L.append(f"| {row['bin']} | {int(row['n']):,} | {row['predicted']:.3f} | "
                     f"{row['observed']:.3f} | {row['gap']:+.3f} |")

    best = min(r["results"], key=lambda k: r["results"][k]["ece"])
    raw_ece = r["results"]["raw"]["ece"]
    L.append("\n## Verdict\n")
    L.append(f"The raw probabilities carry an expected calibration error of {raw_ece:.4f} and a "
             f"maximum of {r['results']['raw']['mce']:.4f}. The lowest error after mapping is "
             f"{best} at {r['results'][best]['ece']:.4f}. "
             + (f"Calibration reduces the error by {raw_ece - r['results'][best]['ece']:.4f} in "
                f"probability units.\n" if best != "raw"
                else "No mapping improved on the raw output.\n"))
    L.append("Calibration is monotone, so it does not change AUC or the order in which trades are "
             "ranked. It changes the number a confidence threshold and a Kelly fraction read, which "
             "is where a miscalibrated probability does its damage.\n")

    csv = os.path.join(day, f"calibration-{r['frame']}-{tag}-{stamp}.csv")
    pd.concat([d["table"].assign(mapping=n) for n, d in r["results"].items()]).to_csv(csv, index=False)
    L.append(f"Full reliability tables: `{os.path.relpath(csv, mm.REPO)}`\n")
    open(path, "w").write("\n".join(L) + "\n")
    return path


def plot(r: dict, out_dir) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    stamp = datetime.now().strftime("%Y%m%d")
    day = os.path.join(str(out_dir), datetime.now().strftime("%Y-%m-%d"))
    os.makedirs(day, exist_ok=True)
    tag = "balanced" if r["balanced"] else "unweighted"
    png = os.path.join(day, f"calibration-{r['frame']}-{tag}-{stamp}.png")
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot([0, 1], [0, 1], color="#8fa3b5", lw=1, ls="--", label="perfect")
    for name, colour in (("raw", "#c8262a"), ("Platt", "#0d5f8a"), ("isotonic", "#0e7a5f")):
        d = r["results"][name]["table"]
        ax.plot(d["predicted"], d["observed"], marker="o", ms=4, lw=1.4, color=colour,
                label=f"{name} (ECE {r['results'][name]['ece']:.3f})")
    ax.axhline(r["base"], color="#5b6b7d", lw=0.8, ls=":", label=f"base rate {r['base']:.3f}")
    ax.set_xlabel("mean predicted probability")
    ax.set_ylabel("observed frequency")
    ax.set_title(f"Reliability, {r['frame']} frame, blind year "
                 f"({'class_weight=balanced' if r['balanced'] else 'unweighted'})")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(png, dpi=150)
    plt.close(fig)
    return png


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--interval", default="4h")
    p.add_argument("--rows", type=int, default=120_000)
    p.add_argument("--unbalanced", action="store_true",
                   help="fit without class_weight='balanced', to isolate its effect")
    p.add_argument("--out", default=str(mm.EVALS))
    a = p.parse_args()
    r = run(a.interval, a.rows, balanced=not a.unbalanced)
    for name, d in r["results"].items():
        print(f"  {name:9s} ECE {d['ece']:.4f}  MCE {d['mce']:.4f}  Brier {d['brier']:.4f}")
    print("\nrecord:", write_record(r, a.out))
    print("chart :", plot(r, a.out))


if __name__ == "__main__":
    main()
