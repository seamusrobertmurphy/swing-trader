"""Run several named configurations against one panel and compare them.

    .venv/bin/python 03-inputs/bench_sweep.py                 # the built-in forest design
    .venv/bin/python 03-inputs/bench_sweep.py --design forest --repeats 3
    .venv/bin/python 03-inputs/bench_sweep.py --list

One panel is read once and every configuration is scored against those same
rows, so a difference between two rows of the output is the configuration and
nothing else. Running each configuration separately would reread the panel, and
on a capped read that is not guaranteed to return the same rows.

The design is a comparison, not a grid. Each configuration moves one axis away
from the incumbent and the two extremes bracket them, so a row that wins can be
attributed to the thing that changed. A full nine-parameter grid over the same
ranges is tens of thousands of fits and would answer a question nobody asked:
the September sweep already showed the whole grid spanning 0.033 on held-out
error while a change of fold moved it by more.

Three designs, and they vary different things. `forest` holds the estimator
and the split fixed and moves the forest's own settings. `regime` holds the
estimator and its settings fixed and moves the resampling regime through all
seven bench_run.folds_of implements, so the same model is scored under
walk-forward, k-fold, leave-one-out, Monte Carlo and the bootstrap against one
blind period that is the same for every row; the gap between what a regime
claimed and what the blind period found is that regime's optimism, and on an
autocorrelated series the regimes that ignore time should claim the most.
`estimator` holds the split fixed and moves the estimator through the zoo.

`--repeats` refits every configuration that many times with a different random
seed, and for the random regimes redraws the partition, and reports the spread. That matters more than it sounds: on 8 September a
grid of nine settings moved held-out error by 0.094 bars while changing the fold
moved it by 3.83, so a difference between two configurations means nothing until
it is bigger than the noise in either of them.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench_config as bc          # noqa: E402
import bench_run as br             # noqa: E402
import model_metrics as mm         # noqa: E402
import train_model_1h as t1        # noqa: E402


# ---------------------------------------------------------------------------
# The designs. Each entry is a name, a one-line reason, and the parameters that
# differ from the estimator's library defaults.
# ---------------------------------------------------------------------------

# What ran on 8 September and won 16 of 76 sweeps: 150 trees, depth 4, 200 rows
# a leaf. The regime design holds this fixed so the only thing moving is the
# regime.
_INCUMBENT = dict(n_estimators=150, max_depth=4, min_samples_leaf=200)
# A forest that can memorise: unconstrained depth, one row a leaf, 100 trees so
# leave-one-out's 200 fits finish. On 8 September this shape had a walk-forward
# overfit ratio of 3.68. A model that cannot learn a single row cannot leak one
# either, which is why the incumbent's regime sweep found the leak inside the
# seed noise; this is the shape that shows how far a random partition flatters
# a model that does memorise.
_MEMORISER = dict(n_estimators=100, max_depth=0, min_samples_leaf=1)


def _unpack(entry):
    """A configuration is (name, why, params) or (name, why, params, overrides)."""
    name, why, params = entry[:3]
    overrides = entry[3] if len(entry) > 3 else {}
    return name, why, params, overrides


DESIGNS: dict[str, dict] = {
    "forest": dict(
        model="RF",
        note="Nine settings on the random forest, one axis per configuration.",
        configs=[
            ("library-defaults",
             "Every setting as scikit-learn ships it. Unconstrained depth and a "
             "single row per leaf, so this is the most a forest can memorise and "
             "the upper bound on the overfit ratio.",
             dict(n_estimators=400, max_depth=0, min_samples_leaf=1)),

            ("incumbent",
             "What ran on 8 September: 150 trees, depth 4, 200 rows a leaf. The "
             "row every other configuration is compared against.",
             dict(n_estimators=150, max_depth=4, min_samples_leaf=200)),

            ("more-trees",
             "The incumbent with 400 trees instead of 150. Tree count is the one "
             "axis that cannot overfit by growing, so this isolates whether the "
             "incumbent is simply under-sampled.",
             dict(n_estimators=400, max_depth=4, min_samples_leaf=200)),

            ("deeper-narrower",
             "Depth 12 and 50 rows a leaf, the library's leaf size. Buys capacity "
             "back and should push the overfit ratio up; the question is what it "
             "buys on held-out error in exchange.",
             dict(n_estimators=400, max_depth=12, min_samples_leaf=50)),

            ("pruned-subsampled",
             "Cost-complexity pruning at 0.0005, 60 per cent of rows per tree, and "
             "entropy rather than gini. Three different brakes from leaf size, to "
             "see whether the same restraint can be bought without flattening the "
             "model.",
             dict(n_estimators=400, max_depth=12, min_samples_leaf=50,
                  ccp_alpha=0.0005, max_samples=0.6, criterion="entropy")),

            ("all-features",
             "Every column considered at every split instead of the square root, "
             "with 20 rows needed to split. Removes the feature sampling that makes "
             "a forest a forest, so the trees correlate and the ensemble should "
             "lose most of its variance reduction.",
             dict(n_estimators=400, max_depth=12, min_samples_leaf=50,
                  max_features="", min_samples_split=20)),
        ]),

    # The incumbent forest under every resampling regime the bench offers. The
    # fourth element of each configuration overrides a section of the bench
    # configuration for that row alone. Everything else, the rows, the split at
    # the blind cut, the features and the estimator, is identical across rows.
    "regime": dict(
        model="RF",
        kind="regime",
        note="One estimator at one setting, scored under seven resampling "
             "regimes against a single blind period. Two regimes keep time in "
             "order and five ignore it; the difference between a regime's "
             "claimed error and the blind error is what that regime leaks.",
        configs=[
            ("expanding", "The training window grows and each fold is scored on "
             "what follows. The house regime.", _INCUMBENT,
             {"split": {"scheme": "expanding"}}),
            ("rolling", "The training window slides, so old regimes drop out of "
             "the fit. Time stays in order.", _INCUMBENT,
             {"split": {"scheme": "rolling"}}),
            ("kfold", "Equal random blocks, each scored once. A row an hour "
             "after a training row is nearly the same observation.", _INCUMBENT,
             {"split": {"scheme": "kfold"}}),
            ("repeated-kfold", "The same, reshuffled and repeated ten times.",
             _INCUMBENT, {"split": {"scheme": "repeated-kfold"}}),
            ("leave-one-out", "Every scored row is fitted on all the others, so "
             "its neighbours on both sides are in training. Capped at 200 rows "
             "drawn at random, as bench_run.folds_of says.", _INCUMBENT,
             {"split": {"scheme": "leave-one-out"}}),
            ("monte-carlo", "Repeated random splits at 75 per cent training.",
             _INCUMBENT, {"split": {"scheme": "monte-carlo"}}),
            ("bootstrap", "Resample with replacement and score the third of "
             "rows left out of bag.", _INCUMBENT,
             {"split": {"scheme": "bootstrap"}}),
        ]),

    "regime-memoriser": dict(
        model="RF",
        kind="regime",
        note="The seven resampling regimes on a forest with unconstrained depth "
             "and one row a leaf, the most a forest can memorise, against the "
             "same blind period. The regime sweep on the incumbent measures the "
             "leak on a model too blunt to exploit it; this one measures it on a "
             "model that can.",
        configs=None,       # filled from the regime design below
        ),

    # The purge between walk-forward folds, workplan stage 2 of 16 September
    # 2026. The label looks twelve bars ahead, so the last twelve training rows
    # of every fold carry the scored block's outcomes unless they are dropped.
    "purge": dict(
        model="RF",
        kind="purge",
        note="The incumbent forest under expanding walk-forward with 0, 6, 12, 24 and "
             "48 rows purged from the end of each training block. The blind period "
             "is the same for every row; what moves is the claimed error.",
        configs=[(f"purge-{k}", f"{k} rows dropped before each scored block.", _INCUMBENT,
                  {"split": {"scheme": "expanding", "purge_bars": k}})
                 for k in (0, 6, 12, 24, 48)],
        ),

    # Every estimator the bench can build, each at bench_run.make_estimator's
    # own defaults, under the house regime. Ensemble.stack is in the zoo the
    # assessment script offers and make_estimator does not build it, so it is
    # not listed here rather than listed and skipped.
    "estimator": dict(
        model="RF",
        kind="estimator",
        note="Six estimators at their bench defaults on the same rows, the same "
             "walk-forward folds and the same blind period, so a difference "
             "between rows is the learner and nothing else.",
        configs=[
            ("LogReg.glm", "Logistic regression, unpenalised, after median "
             "imputation and standardisation.", None,
             {"model": {"estimator": "LogReg.glm"}}),
            ("LogReg.enet", "Logistic regression with an elastic-net penalty, "
             "half lasso and half ridge, C 0.1.", None,
             {"model": {"estimator": "LogReg.enet"}}),
            ("RF", "The random forest at the bench defaults: 400 trees, depth "
             "8, 50 rows a leaf.", None, {"model": {"estimator": "RF"}}),
            ("HistGBM", "scikit-learn's histogram gradient booster, 600 "
             "iterations at a learning rate of 0.05.", None,
             {"model": {"estimator": "HistGBM"}}),
            ("LightGBM", "LightGBM, 600 trees of 31 leaves at 0.05.", None,
             {"model": {"estimator": "LightGBM"}}),
            ("GBM.classic", "scikit-learn's classic booster, 150 trees of depth "
             "3 on half the rows. Takes no class weight, so it is always "
             "unweighted.", None, {"model": {"estimator": "GBM.classic"}}),
        ]),
}


# The estimator sweep again under the balanced class weight, workplan stage 4.
DESIGNS["estimator-balanced"] = dict(
    DESIGNS["estimator"], kind="estimator",
    note=DESIGNS["estimator"]["note"] + " This run fits every learner with the balanced "
         "class weight, the setting the 8 September calibration record blamed for two "
         "thirds of the calibration error.",
    configs=[(name, why, params, {"model": dict(ov.get("model", {}), class_weight="balanced")})
             for name, why, params, ov in (_unpack(e) for e in DESIGNS["estimator"]["configs"])])

DESIGNS["regime-memoriser"]["configs"] = [
    (name, why, _MEMORISER, ov) for name, why, _p, ov in
    (_unpack(e) for e in DESIGNS["regime"]["configs"])]


# ---------------------------------------------------------------------------

def prepare(cfg: dict, log=print):
    """Read the panel once and split it once, for every configuration to share."""
    df, available = br.load_frame(cfg, log=log)
    feats = br.choose_features(cfg, available, log=log)
    holdout = int(cfg["split"]["holdout_days"])
    embargo = int(cfg["split"]["embargo_bars"] or 0)
    train, test, cut = t1.split(
        df, oos_days=holdout,
        embargo_days=max(1, embargo // 6) if embargo else t1.EMBARGO_DAYS)
    if len(train) < 500 or len(test) < 100:
        raise SystemExit(f"the split leaves {len(train):,} training rows and "
                         f"{len(test):,} blind rows, too little to compare on.")
    log(f"split at {cut.date()}: {len(train):,} training rows, {len(test):,} blind")
    feats, screen = br.screen_variables(cfg, train, feats, log=log)
    return train, test, feats, screen, cut


def run_design(cfg: dict, design: dict, repeats: int = 1, log=print) -> list[dict]:
    train, test, feats, screen, cut = prepare(cfg, log=log)
    out = []
    for entry in design["configs"]:
        name, why, params, overrides = _unpack(entry)
        seeds = []
        for r in range(repeats):
            # Copy every section the row touches, so one row's override cannot
            # leak into the next row through a shared dict.
            local = {k: (dict(v) if isinstance(v, dict) else v) for k, v in cfg.items()}
            for section, fields in overrides.items():
                local[section] = dict(local.get(section) or {})
                local[section].update({k: v for k, v in fields.items() if k != "estimator"})
            model = (overrides.get("model") or {}).get("estimator") or design["model"]
            # A different seed each repeat, so the spread below is the model's own
            # randomness rather than a rerun of the identical fit. The regime is
            # reseeded too, so a repeated k-fold repeats a different partition.
            local["split"]["seed"] = r
            # A row with no explicit parameters still needs the seed, or every
            # repeat is the identical fit and the spread reads exactly zero,
            # which the 16 September estimator record did before this line.
            seeded = dict(params or {}, random_state=r) if r else params
            got = br.score_estimator(model, seeded,
                                     local, train, test, feats,
                                     log=(log if r == 0 else lambda *a, **k: None))
            if got:
                seeds.append(got[0])
        if not seeds:
            log(f"  {name}: estimator unavailable, skipped")
            continue
        row = dict(seeds[0])
        row.update(name=name, why=why, params=params or {}, repeats=len(seeds))
        if len(seeds) > 1:
            row["cv_rmse_sd"] = float(np.std([s["cv"]["rmse"] for s in seeds], ddof=1))
            row["ratio_sd"] = float(np.std([s["rmse_ratio"] for s in seeds], ddof=1))
            row["cv_rmse_mean"] = float(np.mean([s["cv"]["rmse"] for s in seeds]))
        out.append(row)
    return out, screen, cut, len(train), len(test)


def write_record(cfg, design, rows, screen, cut, n_train, n_test,
                 repeats, seconds, log=print) -> Path:
    stamp = datetime.now()
    day = br.RUNS / stamp.strftime("%Y-%m-%d")
    day.mkdir(parents=True, exist_ok=True)
    md = mm.unclobbered(day / f"bench-sweep-{stamp:%Y%m%d-%H%M%S}.md")

    def _n(v, dp=4):
        return "n/a" if v is None or (isinstance(v, float) and not np.isfinite(v)) \
            else f"{v:.{dp}f}"

    kind = design.get("kind", "forest")
    heading = {"forest": f"Configuration sweep, {design['model']}",
               "regime": f"Resampling regime sweep, {design.get('name', 'regime')}",
               "estimator": f"Estimator sweep, {design.get('name', 'estimator')}",
               "purge": "Purge sweep, rows dropped before each scored block"}.get(
                   kind, f"Sweep, {design.get('name', kind)}")
    L = [f"# {heading}, {stamp:%d %B %Y %H:%M}", "",
         design["note"], "",
         bc.describe(cfg), "",
         f"One panel read once, split at {cut.date()} into {n_train:,} training rows "
         f"and {n_test:,} blind. Every configuration is scored against those same "
         f"rows, so a difference between two rows is the configuration and nothing "
         f"else." + (f" Each was refitted {repeats} times on different seeds and the "
                     f"spread is reported." if repeats > 1 else ""), "",
         "## What each configuration changes", ""]
    for r in rows:
        L.append(f"**{r['name']}** &mdash; " + r["why"])
        L.append("")
        if r["params"]:
            L.append("`" + " ".join(f"{k}={v}" for k, v in r["params"].items()) + "`")
            L.append("")

    cv_means = ("walk-forward out-of-fold on that same window" if kind != "regime"
                else "out-of-fold under the row's own regime on that same window")
    L += ["## Scores", "",
          "Full is fitted and scored in sample on the training window; CV is "
          f"{cv_means}. The ratio is CV RMSE over "
          "Full RMSE and the bar rejects above "
          f"{cfg['model']['reject_ratio']}. Theil's U2 is the model's error over the "
          "error of always predicting the base rate, so anything at or above one is "
          "not beating a constant.", "",
          "| configuration | RMSE Full | RMSE CV | MAE CV | MISE CV | U2 CV | ratio | verdict |",
          "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for r in sorted(rows, key=lambda r: r["cv"]["rmse"]):
        L.append(f"| {r['name']} | {_n(r['full']['rmse'])} | {_n(r['cv']['rmse'])} "
                 f"| {_n(r['cv']['mae'])} | {_n(r['cv']['mise'], 5)} "
                 f"| {_n(r['cv']['theil_u2'], 3)} | {r['rmse_ratio']:.3f} "
                 f"| {'rejected' if r['rejected'] else 'passes'} |")

    if kind == "regime":
        # The blind period is the same rows for every regime, so the blind
        # column is nearly constant and the claimed column is the finding.
        L += ["", "## What each regime claimed against what the blind period found", "",
              "Every row is the same estimator at the same setting scored on the "
              "same blind rows, so the blind column barely moves. The claimed "
              "column is what each regime said the held-out error would be. "
              "Optimism is claimed minus blind: a negative number is a regime "
              "that promised less error than the blind period delivered, and on "
              "a series where neighbouring rows are nearly the same observation "
              "that is the leak, measured.", "",
              "| regime | keeps time in order | claimed RMSE | blind RMSE | optimism "
              "| claimed U2 | blind U2 | ratio | verdict |",
              "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
        for r in sorted(rows, key=lambda r: r["cv"]["rmse"] - r["blind"]["rmse"]):
            ordered = r["scheme"] in ("expanding", "rolling")
            L.append(f"| {r['name']} | {'yes' if ordered else 'no'} "
                     f"| {_n(r['cv']['rmse'])} | {_n(r['blind']['rmse'])} "
                     f"| {r['cv']['rmse'] - r['blind']['rmse']:+.4f} "
                     f"| {_n(r['cv']['theil_u2'], 3)} | {_n(r['blind']['theil_u2'], 3)} "
                     f"| {r['rmse_ratio']:.3f} | {'rejected' if r['rejected'] else 'passes'} |")
        ordered = [r for r in rows if r["scheme"] in ("expanding", "rolling")]
        random_ = [r for r in rows if r["scheme"] not in ("expanding", "rolling")]
        if ordered and random_:
            o = np.mean([r["cv"]["rmse"] - r["blind"]["rmse"] for r in ordered])
            q = np.mean([r["cv"]["rmse"] - r["blind"]["rmse"] for r in random_])
            po = sum(1 for r in ordered if not r["rejected"])
            pq = sum(1 for r in random_ if not r["rejected"])
            L += ["", f"Mean optimism of the two time-ordered regimes {o:+.4f}, of the "
                      f"five that ignore time {q:+.4f}. {po} of {len(ordered)} ordered "
                      f"regimes and {pq} of {len(random_)} random regimes passed the "
                      f"overfit bar on their own claimed error.", ""]

    L += ["", "## On the blind period", "",
          "Scored once, at the end.", "",
          "| configuration | RMSE | MAE | MISE | Theil U1 | Theil U2 | bias share | AUC |",
          "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for r in sorted(rows, key=lambda r: r["cv"]["rmse"]):
        b = r["blind"]
        L.append(f"| {r['name']} | {_n(b['rmse'])} | {_n(b['mae'])} | {_n(b['mise'], 5)} "
                 f"| {_n(b['theil_u1'], 3)} | {_n(b['theil_u2'], 3)} "
                 f"| {_n(b['theil_bias'], 3)} | {r['blind_auc']:.3f} |")

    if repeats > 1 and any("cv_rmse_sd" in r for r in rows):
        L += ["", "## Is the difference bigger than the noise", "",
              f"Each configuration refitted {repeats} times on different seeds. The "
              "spread column is the standard deviation of held-out RMSE across those "
              "refits. A gap between two configurations smaller than their own spread "
              "is not a result.", "",
              "| configuration | CV RMSE mean | spread across seeds |",
              "| --- | ---: | ---: |"]
        for r in sorted(rows, key=lambda r: r.get("cv_rmse_mean", r["cv"]["rmse"])):
            L.append(f"| {r['name']} | {_n(r.get('cv_rmse_mean', r['cv']['rmse']))} "
                     f"| {_n(r.get('cv_rmse_sd'), 5)} |")
        spreads = [r["cv_rmse_sd"] for r in rows if r.get("cv_rmse_sd") is not None]
        span = max(r["cv"]["rmse"] for r in rows) - min(r["cv"]["rmse"] for r in rows)
        if spreads:
            L += ["", f"The design spans {span:.4f} on held-out RMSE. The largest "
                      f"spread within a single configuration is {max(spreads):.5f}. "
                      + ("The design is separating configurations rather than noise."
                         if span > 3 * max(spreads) else
                         "**The design does not clear its own noise**, so no row here "
                         "is distinguishable from any other and the comparison should "
                         "be run on more rows or more repeats before it is believed."), ""]

    passing = [r for r in rows if not r["rejected"]]
    best = min(passing, key=lambda r: r["cv"]["rmse"]) if passing else None
    L += ["", "## Reading", "",
          f"{len(passing)} of {len(rows)} configurations passed the overfit bar."
          + (f" The best of those on held-out error is **{best['name']}** at "
             f"{best['cv']['rmse']:.4f}, ratio {best['rmse_ratio']:.3f}, "
             f"blind Theil U2 {best['blind']['theil_u2']:.3f}." if best else
             " Nothing passed, so the design has no usable configuration in it."), ""]
    if best and best["blind"]["theil_u2"] is not None and best["blind"]["theil_u2"] >= 1.0:
        L += [f"The winner's blind U2 of {best['blind']['theil_u2']:.3f} is at or above "
              "one, so it does not beat always predicting the base rate. That is a "
              "statement about the columns and the barrier, not about the settings: no "
              "configuration of a forest creates signal that is not in its inputs.", ""]

    if screen:
        L += [f"A variable screen ran first and kept {len(screen['survivors'])} "
              f"columns at lambda.{screen['rule']}.", ""]
    L += [f"Swept in {seconds:.0f} seconds.", "",
          "## The configuration that produced this", "", "```json",
          json.dumps(cfg, indent=2, sort_keys=True), "```", ""]

    md.write_text("\n".join(L) + "\n", encoding="utf-8")
    md.with_suffix(".json").write_text(json.dumps(
        dict(stamped=stamp.isoformat(timespec="seconds"), design=design["model"],
             kind=kind, design_name=design.get("name", ""), repeats=repeats,
             config=cfg, rows=rows), indent=2, default=str),
        encoding="utf-8")
    log(f"record: {md.relative_to(bc.REPO)}")
    return md


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--design", default="forest", choices=sorted(DESIGNS))
    ap.add_argument("--config", default=None, help="a saved bench config; default is the active one")
    ap.add_argument("--repeats", type=int, default=1,
                    help="refits per configuration, on different seeds, to measure the noise")
    ap.add_argument("--list", action="store_true", help="show the design and exit")
    a = ap.parse_args()

    design = dict(DESIGNS[a.design], name=a.design)
    if a.list:
        print(f"{a.design}: {design['note']}\n")
        for entry in design["configs"]:
            name, why, params, overrides = _unpack(entry)
            print(f"  {name}")
            print(f"    {why}")
            if params:
                print("    " + " ".join(f"{k}={v}" for k, v in params.items()))
            if overrides:
                print("    overrides " + json.dumps(overrides))
        return 0

    t0 = time.time()
    cfg = bc.load(Path(a.config) if a.config else None)
    print(bc.describe(cfg))
    print()
    rows, screen, cut, n_tr, n_te = run_design(cfg, design, a.repeats)
    if not rows:
        raise SystemExit("no configuration produced a score.")
    write_record(cfg, design, rows, screen, cut, n_tr, n_te, a.repeats,
                 time.time() - t0)
    print(f"done in {time.time() - t0:.0f} seconds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
