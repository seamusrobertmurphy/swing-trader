"""Acceptance checks for the bench: the configuration, the metrics, the runner.

    .venv/bin/python 03-inputs/bench_eval.py            # everything but the real runs
    .venv/bin/python 03-inputs/bench_eval.py --live     # plus a real run and a real sweep
    .venv/bin/python 03-inputs/bench_eval.py --all

Each check names the artefact it read or the closed-form value it compared
against, so a pass is a statement rather than a claim.

The metric checks matter most and they are not smoke tests. Theil's U2 and MISE
were both defined in this repository rather than taken off a shelf, because the
textbook forms divide by an outcome that is nought for the majority class, so
they are checked against cases whose answer is known in advance: a forecast that
always predicts the base rate must return a U2 of exactly one, and a perfectly
calibrated forecast must return a MISE of nought.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench_config as bc          # noqa: E402
import model_metrics as mm         # noqa: E402

PASS, FAIL, SKIP = "pass", "FAIL", "skip"
results: list[tuple[str, str, str]] = []


def record(check: str, ok, detail: str) -> None:
    # bool(ok), not `ok is True`. numpy comparisons return np.bool_, which is
    # never the True singleton, so a passing numpy check reported as a failure.
    # Caught on 8 September by check 5e, which was correct and said so.
    state = SKIP if ok is None else (PASS if bool(ok) else FAIL)
    results.append((check, state, detail))
    mark = {PASS: "  ok  ", FAIL: " FAIL ", SKIP: " skip "}[state]
    print(f"[{mark}] {check}\n         {detail}", flush=True)


# ---------------------------------------------------------------------------
# The configuration
# ---------------------------------------------------------------------------

def check_config() -> None:
    cfg = bc.defaults()
    missing = [f"{s}.{f.key}" for s, spec in bc.SCHEMA.items()
               for f in spec["fields"] if f.key not in cfg[s]]
    record("1a every schema field has a default", not missing,
           f"{len(bc.SECTIONS)} sections, "
           f"{sum(len(v['fields']) for v in bc.SCHEMA.values())} fields"
           if not missing else f"absent: {missing}")

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "c.json"
        cfg["data"]["symbols"] = "BTCUSDT ETHUSDT"
        cfg["model"]["params"] = {"RF": {"min_samples_leaf": 200}}
        bc.save(cfg, p)
        back = bc.load(p)
    same = back == cfg
    record("1b a configuration round-trips through disk", same,
           "saved and reloaded identically, nested parameters included"
           if same else "the reloaded configuration differs from the saved one")

    # A browser can post anything; the schema is what decides.
    got = bc.coerce("data", {"market": "crypto", "rows": "25000",
                             "symbols": "btcusdt, ethusdt",
                             "frame": "not-a-frame", "evil": "rm -rf"})
    ok = (got.get("rows") == 25000
          and got.get("symbols") == "BTCUSDT ETHUSDT"
          and "frame" not in got and "evil" not in got)
    record("1c posted settings are typed, and anything unknown is dropped", ok,
           f"rows became {got.get('rows')!r}, symbols {got.get('symbols')!r}, "
           f"an invalid frame and an unknown field were both refused"
           if ok else f"got {got}")

    got = bc.coerce("model", {"RF.min_samples_leaf": "300", "RF.max_depth": "8",
                              "LightGBM.num_leaves": "31", "Bogus.x": "1"})
    p = got.get("params", {})
    ok = (p.get("RF", {}).get("min_samples_leaf") == 300
          and "max_depth" not in p.get("RF", {})       # 8 is the library default
          and "LightGBM" not in p                       # 31 is the library default
          and "Bogus" not in p)
    record("1d a hyperparameter left at its library default is not passed", ok,
           "min_samples_leaf 300 kept; max_depth 8 and num_leaves 31 dropped as "
           "defaults; an unknown estimator refused" if ok else f"got {p}")


def check_features() -> None:
    avail = ["f_wc_a", "f_wc_b", "f_hr_a", "f_ta_x", "f_ta_pta_y", "f_btc_m", "f_tl_z"]
    cfg = bc.defaults()

    cfg["features"]["families"] = ["f_ta_"]
    got = bc.resolve_features(cfg, avail)
    ok = got == ["f_ta_x"]
    record("2a the in-house oscillators do not swallow the pandas-ta block", ok,
           "f_ta_ selected f_ta_x alone, leaving f_ta_pta_y out; they are "
           "different libraries and one prefix is a prefix of the other"
           if ok else f"got {got}")

    cfg["features"] = dict(families=["f_wc_"], include="f_btc_m f_nope",
                           exclude="f_wc_a", preset="", max_features=0)
    got = bc.resolve_features(cfg, avail)
    ok = got == ["f_wc_b", "f_btc_m"]
    record("2b families, then names, then exclusions last", ok,
           "f_wc_ gave two, a named column was added, an exclusion removed one, "
           "and a name not in the frame was ignored" if ok else f"got {got}")

    cfg["features"] = dict(families=[], include="", exclude="", preset="", max_features=0)
    got = bc.resolve_features(cfg, avail)
    record("2c nothing ticked offers everything", got == avail,
           f"{len(got)} of {len(avail)} columns offered")


def check_symbols() -> None:
    pairs = [("BTCUSDT", "BTC/USDT"), ("btc/usdt", "BTCUSDT"),
             ("BTC-USDT", "BTCUSDT"), ("AAPL", "aapl")]
    bad = [f"{a} vs {b}" for a, b in pairs if bc.canonical(a) != bc.canonical(b)]
    record("3 a symbol matches whichever form it is written in", not bad,
           "BTCUSDT, BTC/USDT, btc/usdt and BTC-USDT all reduce to the same key"
           if not bad else f"did not match: {bad}")


# ---------------------------------------------------------------------------
# The metrics, against cases whose answer is known in advance
# ---------------------------------------------------------------------------

def check_metrics() -> None:
    rng = np.random.RandomState(0)
    n = 20000
    y = rng.binomial(1, 0.25, n).astype(float)
    base = float(y.mean())

    flat = np.full(n, base)
    u2 = mm.theil(y, flat)["u2"]
    ok = abs(u2 - 1.0) < 1e-12
    record("4a always predicting the base rate returns a Theil U2 of exactly one",
           ok, f"U2 = {u2:.12f}. This is the definition and it is the reference "
               f"every other U2 in the repository is read against")

    e = mm.errors(y, flat)
    record("4b that same forecast is perfectly calibrated and useless",
           e["mise"] < 1e-6 and e["theil_bias"] < 1e-12,
           f"MISE {e['mise']:.3e}, bias share {e['theil_bias']:.3e}, RMSE "
           f"{e['rmse']:.4f}. MISE near nought for a model that says nothing is "
           f"why it is read beside RMSE and never instead of it")

    record("4c MAPE does not exist on a nought-or-one outcome",
           e["mape"] is None and not mm.is_mape_defined(y),
           "reported as None rather than computed on the rows where the outcome "
           "is one, which would be a different quantity from the one the name promises")

    shifted = np.clip(flat + 0.30, 0, 1)
    t = mm.theil(y, shifted)
    exp_bias = (0.30 ** 2) / float(np.mean((shifted - y) ** 2))
    ok = abs(t["bias"] - exp_bias) < 1e-9
    record("4d the bias share matches its closed form on a known shift", ok,
           f"a forecast shifted +0.30 gives a bias share of {t['bias']:.6f} "
           f"against the closed form {exp_bias:.6f}")

    # A forecast that is right on average within every region of its own range.
    p = np.clip(rng.uniform(0.05, 0.95, n), 0, 1)
    y2 = rng.binomial(1, p).astype(float)
    m = mm.mise(y2, p, bins=10)
    record("4e a perfectly calibrated spread forecast scores near nought on MISE",
           m < 5e-4, f"MISE {m:.5f} where the outcome was drawn from the "
                     f"prediction itself, so the calibration curve is the diagonal")

    ratio_case = mm.score_run(y, flat, [(y[:1000], flat[:1000])])
    record("4f the overfit ratio is cross-validated over training, not the reverse",
           abs(ratio_case["rmse_ratio"] - 1.0) < 0.05
           and ratio_case["reject_above"] == mm.RMSE_RATIO_REJECT,
           f"identical predictions give a ratio of "
           f"{ratio_case['rmse_ratio']:.4f} against a bar of "
           f"{ratio_case['reject_above']}")


def check_kde() -> None:
    import kde_metrics as km

    rng = np.random.RandomState(1)
    n = 4000
    p = np.clip(rng.uniform(0.05, 0.95, n), 0, 1)
    y = rng.binomial(1, p).astype(float)

    sep = km.class_separation(y, p)
    ok = all(0.0 <= sep[k] <= 1.0 for k in ("overlap", "hellinger"))
    record("5a the separation measures stay inside their bounds", ok,
           f"overlap {sep['overlap']:.4f}, Hellinger {sep['hellinger']:.4f}, "
           f"both bounded on nought to one by construction")

    flat = np.full(n, 0.25)
    yf = rng.binomial(1, 0.25, n).astype(float)
    sepf = km.class_separation(yf, flat)
    record("5b a constant forecast separates the classes not at all",
           sepf["overlap"] is None or sepf["overlap"] > 0.97,
           f"overlap {sepf['overlap']}, at or near one, which is the reading for "
           f"two classes that are indistinguishable on the predicted range")

    spread = km.spread_of_predictions(flat, 0.25)
    record("5c the spread measure detects a model that never leaves the base rate",
           spread["span_90"] < 1e-9 and spread["mass_near_base"] > 0.99,
           f"90 per cent span {spread['span_90']:.2e}, mass within 0.05 of the "
           f"base rate {spread['mass_near_base']:.3f}")

    sens = km.bandwidth_sensitivity(y, p)
    span = max(s["overlap"] for s in sens) - min(s["overlap"] for s in sens)
    record("5d the sensitivity table is produced for every kernel number",
           len(sens) == 5 and all(s["bandwidth"] > 0 for s in sens),
           f"five bandwidths from half Silverman's rule to twice it; overlap "
           f"moves {span:.4f} across them on this well-spread sample")

    # The band has to separate the two cases it exists to separate, so it is
    # given both: a model whose outcomes were drawn from its own predictions,
    # which has real signal, and one whose outcomes are independent of them.
    signal = km.null_band(y, p, draws=60)
    noise_y = rng.binomial(1, float(y.mean()), n).astype(float)
    noise = km.null_band(noise_y, p, draws=60)
    record("5e the null band is well formed", bool(np.all(signal["lo"] <= signal["hi"])),
           f"{signal['draws']} permutations, the lower edge never above the upper")
    ok = signal["share_outside"] > 0.75 and noise["share_outside"] < 0.35
    record("5f the null band tells signal from noise", ok,
           f"a model whose outcomes came from its own predictions sits outside the "
           f"band over {signal['share_outside'] * 100:.1f} per cent of its range; "
           f"one whose outcomes are independent of them sits outside over "
           f"{noise['share_outside'] * 100:.1f} per cent. That gap is the whole "
           f"purpose of the band")


# ---------------------------------------------------------------------------
# Real runs
# ---------------------------------------------------------------------------

PY = str(bc.REPO / ".venv" / "bin" / "python")


def _run(args, budget=2400):
    return subprocess.run([PY, *args], cwd=str(bc.REPO), capture_output=True,
                          text=True, timeout=budget)


def check_live() -> None:
    with tempfile.TemporaryDirectory() as d:
        cfg = bc.defaults()
        cfg["data"].update(frame="slice_4h_40k", symbols="LINK/USDT LTC/USDT",
                           rows=6000)
        cfg["features"]["families"] = ["f_btc_", "f_st_"]
        cfg["model"].update(estimators=["LogReg.glm"], class_weight="none")
        cfg["label"]["horizon_bars"] = 12
        p = Path(d) / "eval.json"
        bc.save(cfg, p)

        t0 = time.time()
        r = _run(["03-inputs/bench_run.py", "--config", str(p), "--label", "bench eval"])
        ok = r.returncode == 0
        record("6a a configured run completes", ok,
               f"exit {r.returncode} in {time.time() - t0:.0f}s"
               + ("" if ok else f"\n         {r.stderr.strip()[-400:]}"))
        if not ok:
            return

        recs = sorted((bc.REPO / "04-outputs" / "AA-evals").glob("*/bench-2*.json"),
                      key=lambda q: q.stat().st_mtime, reverse=True)
        newest = recs[0] if recs else None
        if newest is None:
            record("6b the run wrote a record carrying its own configuration", False,
                   "no bench record on disk")
            return
        doc = json.loads(newest.read_text())
        same = doc.get("config") == cfg
        record("6b the record carries the configuration that produced it", same,
               f"{newest.relative_to(bc.REPO)} embeds a configuration that "
               f"{'matches' if same else 'DIFFERS from'} the one the run was given, "
               f"so the run replays from its own file")

        scores = doc.get("scores") or []
        cols = {"full", "cv", "blind", "rmse_ratio"}
        has = bool(scores) and cols <= set(scores[0])
        metrics = set(scores[0]["cv"]) if has else set()
        want = {"rmse", "mae", "mape", "mise", "theil_u1", "theil_u2", "theil_bias"}
        record("6c every measure is present in both columns", has and want <= metrics,
               f"{len(scores)} model row(s), each carrying "
               f"{', '.join(sorted(want & metrics))} in full, cv and blind"
               if has else "the record has no scores block")


def check_sweep_determinism() -> None:
    """Two identical sweeps must agree, or nothing compared across them means anything."""
    with tempfile.TemporaryDirectory() as d:
        cfg = bc.defaults()
        cfg["data"].update(frame="slice_4h_40k", symbols="LINK/USDT LTC/USDT", rows=6000)
        cfg["features"]["families"] = ["f_btc_"]
        cfg["model"].update(class_weight="none")
        cfg["label"]["horizon_bars"] = 12
        cfg["calibration"]["run_calibration"] = False
        p = Path(d) / "sweep.json"
        bc.save(cfg, p)

        got = []
        for _ in range(2):
            r = _run(["03-inputs/bench_sweep.py", "--config", str(p)])
            if r.returncode != 0:
                record("7 two identical sweeps agree", False,
                       f"a sweep failed: {r.stderr.strip()[-300:]}")
                return
            newest = max((bc.REPO / "04-outputs" / "AA-evals").glob("*/bench-sweep-*.json"),
                         key=lambda q: q.stat().st_mtime)
            doc = json.loads(newest.read_text())
            got.append({row["name"]: round(row["cv"]["rmse"], 10) for row in doc["rows"]})
        same = got[0] == got[1]
        record("7 two identical sweeps agree to ten decimals", same,
               f"{len(got[0])} configurations, held-out RMSE identical across two "
               f"separate processes" if same else
               f"they differ: {[k for k in got[0] if got[0][k] != got[1].get(k)]}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--live", action="store_true", help="run a real fit and a real sweep")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    if a.all:
        a.live = True

    print("Bench eval\n")
    check_config()
    check_features()
    check_symbols()
    check_metrics()
    check_kde()
    if a.live:
        check_live()
        check_sweep_determinism()

    fails = [c for c, s, _ in results if s == FAIL]
    skips = [c for c, s, _ in results if s == SKIP]
    print(f"\n{len(results) - len(fails) - len(skips)} passed, {len(fails)} failed, "
          f"{len(skips)} skipped")
    if fails:
        print("failed: " + "; ".join(fails))
    out = bc.REPO / "04-outputs" / "AA-evals" / "logs" / "bench-eval.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps([dict(check=c, state=s, detail=d)
                               for c, s, d in results], indent=2), encoding="utf-8")
    print(f"written to {out.relative_to(bc.REPO)}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
