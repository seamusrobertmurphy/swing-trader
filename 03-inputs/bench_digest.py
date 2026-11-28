"""One table over every comparison run on disk, so a long run has a single readable answer.

    .venv/bin/python 03-inputs/bench_digest.py

Reads every bench-comparison run-*.json under 04-outputs/AA-evals/ and writes
04-outputs/AA-evals/bench-digest.md. Rewritten in place each time, because there
is one current answer and a dated pile of them is what this exists to replace.

Three questions, and they are the only three a comparison run of comparison runs can answer.

Does the ranking of the configurations hold across conditions, or did it come
from one slice of one panel? A configuration that wins on one condition and loses
on the next is not better, it is lucky, and the count of wins is what says which.

Does the axis matter more than the configuration? The fold count moved held-out
error more than any hyperparameter did in September. If that is still true across
the whole grid then tuning the forest is the wrong lever and the table should say
so in a number.

Did anything, anywhere, beat always predicting the base rate? Theil's U2 below
one on the blind period is the only result here that would change what gets
traded. Every other column is diagnosis.
"""

from __future__ import annotations

import json
import re
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "04-outputs" / "AA-evals"
OUT = EVALS / "bench-digest.md"


def load_sweeps() -> list[dict]:
    out = []
    for p in sorted(EVALS.glob("*/bench-sweep-*.json")):
        if p.name.startswith("._"):
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        cfg = d.get("config") or {}
        if not d.get("rows"):
            continue
        d["file"] = p
        d["kind"] = d.get("kind") or "forest"
        d["design_name"] = d.get("design_name") or d["kind"]
        d["folds"] = cfg.get("split", {}).get("folds")
        d["holdout"] = cfg.get("split", {}).get("holdout_days")
        d["weight"] = cfg.get("model", {}).get("class_weight")
        d["symbols"] = cfg.get("data", {}).get("symbols", "")
        d["rows_cap"] = cfg.get("data", {}).get("rows")
        fams = cfg.get("features", {}).get("families") or []
        d["families"] = " ".join(fams) if fams else "all"
        d["n_symbols"] = len(str(d["symbols"]).split()) or "all"
        out.append(d)
    return out


def fmt(v, dp=4):
    if v is None or not isinstance(v, (int, float)):
        return "n/a"
    try:
        if v != v:                                  # NaN
            return "n/a"
    except TypeError:
        return "n/a"
    return f"{v:.{dp}f}"


def main() -> int:
    sweeps = load_sweeps()
    if not sweeps:
        OUT.write_text("# Comparison run digest\n\nNo comparison run records on disk yet.\n",
                       encoding="utf-8")
        print(f"no comparison runs found; wrote an empty {OUT.relative_to(REPO)}")
        return 0

    every = sweeps
    regime_sweeps = [s for s in every if s["kind"] == "regime"]
    estimator_sweeps = [s for s in every if s["kind"] == "estimator"]
    # The three sections below compare the six forest configurations, so a
    # regime or estimator sweep, whose rows are named after regimes and
    # learners, would put "kfold" and "LightGBM" into the configuration ranking.
    sweeps = [s for s in every if s["kind"] == "forest"]

    L = [f"# Comparison run digest, {datetime.now():%d %B %Y %H:%M}", "",
         f"Every configuration comparison run on disk: **{len(every)} comparison runs**, "
         f"{sum(len(s['rows']) for s in every)} configuration fits in total: "
         f"{len(sweeps)} over the forest's settings, {len(regime_sweeps)} over the "
         f"resampling regime and {len(estimator_sweeps)} over the model. "
         f"Rewritten in place on each update.", ""]

    axes = defaultdict(set)
    for s in every:
        for k in ("folds", "holdout", "weight", "families", "n_symbols"):
            axes[k].add(s[k])
        for r in s["rows"]:
            axes["regime"].add(r.get("scheme") or "expanding")
            axes["estimator"].add(r.get("model") or "RF")
    L += ["Axes covered so far: "
          + ", ".join(f"{k} {sorted(map(str, v))}" for k, v in sorted(axes.items())), ""]

    # --- 0. which regime tells the truth, one table per design -------------
    for design_name in sorted({s["design_name"] for s in regime_sweeps}):
        these = [s for s in regime_sweeps if s["design_name"] == design_name]
        claimed, blind, ratio, passed, n = (defaultdict(list), defaultdict(list),
                                            defaultdict(list), defaultdict(int),
                                            defaultdict(int))
        for s in these:
            for r in s["rows"]:
                k = r.get("scheme") or r["name"]
                claimed[k].append(r["cv"]["rmse"])
                blind[k].append(r["blind"]["rmse"])
                ratio[k].append(r["rmse_ratio"])
                passed[k] += 0 if r["rejected"] else 1
                n[k] += 1
        params = " ".join(f"{k}={v}" for k, v in (these[0]["rows"][0].get("params") or {}).items())
        L += [f"## Which resampling regime tells the truth, {design_name}", "",
              f"{len(these)} comparison run{'s' if len(these) > 1 else ''} held one model at one "
              f"setting ({params}) and "
              "scored it under every regime against the same blind period. Claimed "
              "is what the regime said the held-out error would be; blind is what "
              "the blind period found; optimism is claimed minus blind, so a "
              "negative number is a regime promising less error than it delivered. "
              "On a price series a row an hour after another is nearly the same "
              "observation, so a regime that puts later rows in training and "
              "earlier ones in test has seen the answer.", "",
              "| regime | keeps time in order | claimed RMSE | blind RMSE | optimism "
              "| overfit ratio | passed the bar | fits |",
              "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
        opt = {k: statistics.mean(claimed[k]) - statistics.mean(blind[k]) for k in n}
        for k in sorted(n, key=lambda k: opt[k]):
            ordered = k in ("expanding", "rolling")
            L.append(f"| {k} | {'yes' if ordered else 'no'} | {fmt(statistics.mean(claimed[k]))} "
                     f"| {fmt(statistics.mean(blind[k]))} | {opt[k]:+.4f} "
                     f"| {statistics.mean(ratio[k]):.3f} | {passed[k]} of {n[k]} | {n[k]} |")
        ordered = [opt[k] for k in n if k in ("expanding", "rolling")]
        random_ = [opt[k] for k in n if k not in ("expanding", "rolling")]
        if ordered and random_:
            worst = min(opt, key=opt.get)
            L += ["", f"The two time-ordered regimes are optimistic by {statistics.mean(ordered):+.4f} "
                      f"on average and the five that ignore time by {statistics.mean(random_):+.4f}. "
                      f"The most optimistic is **{worst}** at {opt[worst]:+.4f}, and "
                      + ("it passed the overfit bar on its own claimed error, which is the "
                         "leak passing the check that exists to catch it."
                         if passed[worst] == n[worst] and n[worst] else
                         "it did not pass the overfit bar."), ""]

    # --- 0a. the purge ------------------------------------------------------
    purge_sweeps = [s for s in every if s["kind"] == "purge"]
    if purge_sweeps:
        agg = defaultdict(list)
        for s in purge_sweeps:
            for r in s["rows"]:
                k = int((r.get("params") or {}).get("purge_bars", 0)) if False else int(r["name"].split("-")[-1])
                agg[k].append((r["cv"]["rmse"], r["blind"]["rmse"], r["rmse_ratio"]))
        L += ["## Does a purge between folds change the claimed error", "",
              f"{len(purge_sweeps)} comparison run{'s' if len(purge_sweeps) > 1 else ''} dropped rows from the end "
              "of each walk-forward training block before scoring the next. The label looks "
              "twelve bars ahead, so without a purge the last twelve training rows of every "
              "fold carry the scored block's outcomes.", "",
              "| rows purged | claimed RMSE | blind RMSE | optimism | overfit ratio |",
              "| ---: | ---: | ---: | ---: | ---: |"]
        for k in sorted(agg):
            cv = statistics.mean(a for a, _, _ in agg[k]); bl = statistics.mean(b for _, b, _ in agg[k])
            L.append(f"| {k} | {cv:.4f} | {bl:.4f} | {cv - bl:+.4f} | {statistics.mean(c for _, _, c in agg[k]):.3f} |")
        L.append("")

    # --- 0b. which estimator ------------------------------------------------
    if estimator_sweeps:
        agg = defaultdict(lambda: defaultdict(list))
        for s in estimator_sweeps:
            for r in s["rows"]:
                k = r.get("model") or r["name"]
                agg[k]["ratio"].append(r["rmse_ratio"])
                agg[k]["cv"].append(r["cv"]["rmse"])
                agg[k]["blind"].append(r["blind"]["rmse"])
                agg[k]["u2"].append(r["blind"]["theil_u2"])
                agg[k]["auc"].append(r.get("blind_auc") or float("nan"))
                agg[k]["pass"].append(0 if r["rejected"] else 1)
        L += ["## Which model", "",
              f"{len(estimator_sweeps)} comparison run{'s' if len(estimator_sweeps) > 1 else ''} scored "
              "every model the bench builds on "
              "the same rows, the same walk-forward folds and the same blind period. "
              "The ratio is cross-validated over training error and the bar rejects "
              "above 1.1; blind U2 below one is the only column that says the model "
              "beat always predicting the base rate.", "",
              "| model | CV RMSE | blind RMSE | overfit ratio | passed the bar "
              "| blind U2 | blind AUC | fits |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for k in sorted(agg, key=lambda k: statistics.mean(agg[k]["blind"])):
            a = agg[k]
            L.append(f"| {k} | {fmt(statistics.mean(a['cv']))} | {fmt(statistics.mean(a['blind']))} "
                     f"| {statistics.mean(a['ratio']):.3f} | {sum(a['pass'])} of {len(a['pass'])} "
                     f"| {fmt(statistics.mean(a['u2']), 3)} | {fmt(statistics.mean(a['auc']), 3)} "
                     f"| {len(a['cv'])} |")
        L.append("")

    if not sweeps:
        OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
        print(f"{len(every)} comparison runs digested to {OUT.relative_to(REPO)}")
        return 0

    # --- 1. does the ranking hold -----------------------------------------
    wins = defaultdict(int)
    places = defaultdict(list)
    for s in sweeps:
        ordered = sorted(s["rows"], key=lambda r: r["cv"]["rmse"])
        for rank, r in enumerate(ordered, start=1):
            places[r["name"]].append(rank)
        wins[ordered[0]["name"]] += 1

    L += ["## Does the ranking hold across conditions", "",
          "Each comparison run ranks the six configurations on held-out RMSE. A "
          "configuration that wins on one condition and loses on the next is not "
          "better, it is lucky.", "",
          "| configuration | times first | mean place | best | worst |",
          "| --- | ---: | ---: | ---: | ---: |"]
    for name in sorted(places, key=lambda n: statistics.mean(places[n])):
        pl = places[name]
        L.append(f"| {name} | {wins[name]} of {len(sweeps)} "
                 f"| {statistics.mean(pl):.2f} | {min(pl)} | {max(pl)} |")
    stable = len({p for name in places for p in [tuple(places[name])]}) and all(
        min(places[n]) == max(places[n]) for n in places)
    L += ["", "The ranking is identical in every comparison run." if stable else
          "The ranking moves between comparison runs, so it is a property of the condition "
          "as much as of the configuration.", ""]

    # --- 2. axis against configuration ------------------------------------
    span_within = [max(r["cv"]["rmse"] for r in s["rows"])
                   - min(r["cv"]["rmse"] for r in s["rows"]) for s in sweeps]
    by_axis = {}
    for axis in ("folds", "holdout", "weight", "families", "n_symbols"):
        groups = defaultdict(list)
        for s in sweeps:
            best = min(s["rows"], key=lambda r: r["cv"]["rmse"])
            groups[str(s[axis])].append(best["cv"]["rmse"])
        if len(groups) < 2:
            continue
        means = {k: statistics.mean(v) for k, v in groups.items()}
        by_axis[axis] = (max(means.values()) - min(means.values()), means)

    L += ["## Does the axis matter more than the configuration", "",
          "The configuration span is how far apart the six configurations sit "
          "within one comparison run. Each axis span is how far the winning configuration's "
          "held-out error moves when only that axis changes. An axis that moves it "
          "further than the configurations do is the bigger lever, and tuning the "
          "forest is then the wrong question.", "",
          f"Configuration span within a comparison run: mean "
          f"**{statistics.mean(span_within):.4f}**, "
          f"largest {max(span_within):.4f}.", "",
          "| axis | span of the winner's held-out RMSE | values |",
          "| --- | ---: | --- |"]
    for axis, (span, means) in sorted(by_axis.items(), key=lambda kv: -kv[1][0]):
        vals = ", ".join(f"{k} {v:.4f}" for k, v in sorted(means.items()))
        L.append(f"| {axis} | {span:.4f} | {vals} |")
    if by_axis:
        biggest, (bspan, _) = max(by_axis.items(), key=lambda kv: kv[1][0])
        cspan = statistics.mean(span_within)
        L += ["", f"The largest axis is **{biggest}** at {bspan:.4f}, against a mean "
                  f"configuration span of {cspan:.4f}, "
                  + (f"a factor of {bspan / cspan:.1f}. The axis is the bigger lever."
                     if bspan > cspan else
                     "so the configurations still separate further than the axis does."),
              ""]

    # --- 3. did anything beat the base rate --------------------------------
    beat = []
    for s in sweeps:
        for r in s["rows"]:
            u2 = (r.get("blind") or {}).get("theil_u2")
            if u2 is not None and u2 < 1.0 and not r["rejected"]:
                beat.append((s, r, u2))
    L += ["## Did anything beat always predicting the base rate", "",
          "Theil's U2 below one on the blind period, from a configuration that also "
          "passed the overfit bar. This is the only column here that would change "
          "what gets traded.", ""]
    if not beat:
        # key=, not a bare tuple. Ties on the first element sent min on to
        # compare the dicts behind it, which raises.
        cands = [((r.get("blind") or {}).get("theil_u2"), s, r)
                 for s in sweeps for r in s["rows"]
                 if (r.get("blind") or {}).get("theil_u2") is not None]
        best = min(cands, key=lambda t: t[0])
        L += [f"**No.** Across {len(sweeps)} comparison runs and "
              f"{sum(len(s['rows']) for s in sweeps)} fits, nothing reached a blind "
              f"U2 below one. The closest was {best[2]['name']} at {best[0]:.4f} "
              f"on {best[1]['n_symbols']} symbols, {best[1]['folds']} folds, "
              f"{best[1]['holdout']}-day holdout, class weight {best[1]['weight']}, "
              f"and a U2 of {best[0]:.4f} still means it did worse than a constant.", ""]
    else:
        L += [f"**{len(beat)} of {sum(len(s['rows']) for s in sweeps)} fits.**", "",
              "| configuration | symbols | folds | holdout | weight | families | blind U2 | ratio |",
              "| --- | ---: | ---: | ---: | --- | --- | ---: | ---: |"]
        for s, r, u2 in sorted(beat, key=lambda t: t[2])[:25]:
            L.append(f"| {r['name']} | {s['n_symbols']} | {s['folds']} | {s['holdout']} "
                     f"| {s['weight']} | {s['families']} | {u2:.4f} "
                     f"| {r['rmse_ratio']:.3f} |")
        L += ["", "Each of these is a candidate, not a result. A single blind period "
                  "is one regime, and the walk-forward kill harness is what decides "
                  "whether an edge survives being asked the same question in "
                  "different years.", ""]

    # --- the full grid -----------------------------------------------------
    L += ["## Every comparison run", "",
          "| when | symbols | rows | families | folds | holdout | weight | winner "
          "| CV RMSE | blind U2 | passed |",
          "| --- | ---: | ---: | --- | ---: | ---: | --- | --- | ---: | ---: | ---: |"]
    for s in sorted(sweeps, key=lambda s: s.get("stamped", "")):
        best = min(s["rows"], key=lambda r: r["cv"]["rmse"])
        npass = sum(1 for r in s["rows"] if not r["rejected"])
        when = re.sub(r"T", " ", str(s.get("stamped", ""))[:16])
        L.append(f"| {when} | {s['n_symbols']} | {s['rows_cap']} | {s['families']} "
                 f"| {s['folds']} | {s['holdout']} | {s['weight']} | {best['name']} "
                 f"| {fmt(best['cv']['rmse'])} "
                 f"| {fmt((best.get('blind') or {}).get('theil_u2'), 3)} "
                 f"| {npass} of {len(s['rows'])} |")

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"{len(every)} comparison runs digested to {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
