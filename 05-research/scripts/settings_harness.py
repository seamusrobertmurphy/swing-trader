"""Settings harness: post values through the served page, run the model test,
and check the record used them. Usage: settings-harness.py GROUP [GROUP...]"""
import sys, json, glob, os, time, subprocess, shutil, urllib.request, urllib.parse, pathlib
REPO = pathlib.Path(__file__).resolve().parents[2]; os.chdir(REPO)
sys.path.insert(0, "03-inputs"); import bench_config as bc
BASE = "http://127.0.0.1:8787"
GROUPS = {
  "data": {"market": "crypto", "frame": "slice_4h_40k", "bundle": "all",
           # Eight coins, not two: the cross-sectional ranking keeps a third of
           # the assets at each bar and leaves a bar whole below a five-asset
           # floor, so a two-coin run can never show that setting doing anything.
           # The eight coins with the densest in-sample coverage in this slice,
           # because the point-in-time screen leaves most of the 137 with a few
           # dozen rows and a bar carrying one asset cannot be ranked.
           "symbols": ["XRP/USDT", "SOL/USDT", "LTC/USDT", "TRX/USDT",
                       "LINK/USDT", "MATIC/USDT", "SHIB/USDT", "SUI/USDT"],
           "rows": "20000"},
  "split": {"holdout_days": "150", "purge_bars": "6", "embargo_bars": "12", "folds": "2",
            "scheme": "expanding", "repeats": "2", "boot_samples": "3"},
  "model": {"estimators": ["LogReg.glm", "RF"], "tune": "", "class_weight": "none",
            "reject_ratio": "1.3", "RF.n_estimators": "37", "RF.max_depth": "3",
            "LogReg.glm.C": "0.5"},
  "calibration": {"run_calibration": "1", "methods": ["Platt"], "cal_fraction": "0.25", "bins": "7"},
  "features": {"families": ["f_wc_", "f_hr_", "f_btc_"], "include": "f_st_agree",
               "exclude": "f_hr_rv_long", "max_features": "20"},
  "selection": {"run_selection": "1", "l1_ratio": "0.7", "rule": "min", "sel_sample": "2000",
                "sel_folds": "2", "feed_model": "1", "draw_intervals": "1"},
  "label": {"target_atr": "2.0", "stop_atr": "1.0", "kind": "barrier", "flat_band": "0.003", "horizon_bars": "12"},
  "screen": {"min_quote_volume": "25000000", "atr_low": "0.012", "atr_high": "0.08",
             "min_history_days": "120", "rank_signal": "f_btc_mom_168", "rank_tercile": "top", "fold_bar": "0.55"},
  "signals": {"macd_fast": "10", "macd_slow": "24", "macd_signal": "8", "macd_noise_k": "0.3",
              "macd_confirm_bars": "2", "ma_fast": "15", "ma_slow": "45", "fib_lookback": "90",
              "fib_min_swing_frac": "0.04", "confluence_threshold": "1.5", "candle_decay": "5"},
  "viz": {"panels": ["candles", "macd", "confluence", "fibonacci", "reliability",
                     "importance", "selectivity", "equity"],
          "viz_symbol": "LTC/USDT", "viz_bars": "300",
          "overlays": ["ema200", "supertrend", "swings", "entries", "exits", "volume"],
          "theme": "dark"},
}
# Every group is measured on the rows the run reads, so the data group is posted
# first whatever was asked for. Without it a screen or a viz test ran against
# whatever basket the last session left in the active configuration.
ALWAYS_FIRST = "data"
def post(section, form):
    data = urllib.parse.urlencode([(k, v) for k, vs in form.items() for v in (vs if isinstance(vs, list) else [vs])]).encode()
    with urllib.request.urlopen(urllib.request.Request(f"{BASE}/config/{section}", data=data)) as r:
        return json.loads(r.read())
groups = sys.argv[1:] or list(GROUPS)
if ALWAYS_FIRST not in groups:
    groups = [ALWAYS_FIRST] + groups
backup = REPO / "04-outputs/AA-evals/bench/config.harness-backup.json"
shutil.copy(bc.ACTIVE, backup)
problems = []
try:
    for g in groups:
        res = post(g, GROUPS[g])
        if "error" in res: problems.append(f"{g}: save refused: {res['error']}"); continue
    cfg = bc.load()
    # 1. the saved file holds what was posted
    for g in groups:
        for k, v in GROUPS[g].items():
            if "." in k:
                m = max((n for n in bc.MODEL_PARAMS if k.startswith(n + ".")), key=len); s = k[len(m) + 1:]
                got = (cfg["model"].get("params") or {}).get(m, {}).get(s)
                want = float(v) if "." in v else int(v)
                if got != want: problems.append(f"model params {k}: saved {got!r}, posted {v!r}")
                continue
            got = cfg[g].get(k)
            if isinstance(v, list): ok = (sorted(got) == sorted(v)) if isinstance(got, list) else (set(got.split()) == set(v))
            elif v in ("0", "1") and isinstance(got, bool): ok = got == (v == "1")
            else:
                try: ok = float(got) == float(v)
                except (TypeError, ValueError): ok = str(got) == str(v)
            if not ok: problems.append(f"{g}.{k}: saved {got!r}, posted {v!r}")
    # 2. run the model test on the saved configuration
    before = set(glob.glob("04-outputs/AA-evals/*/bench-*.json"))
    t0 = time.time()
    run = subprocess.run([".venv/bin/python", "03-inputs/bench_run.py", "--label", "settings harness"], capture_output=True, text=True, timeout=1500)
    print(f"run: exit {run.returncode} in {time.time()-t0:.0f}s"); print(run.stdout[-1500:]); print(run.stderr[-800:])
    new = set(glob.glob("04-outputs/AA-evals/*/bench-*.json")) - before
    if not new: problems.append("no record written"); rec = None
    else:
        rec = json.load(open(sorted(new)[-1])); print("record:", sorted(new)[-1])
        emb = rec["config"]
        for g in groups:
            for k in GROUPS[g]:
                if "." in k: continue
                if emb.get(g, {}).get(k) != cfg[g].get(k): problems.append(f"record {g}.{k}: embeds {emb.get(g,{}).get(k)!r}, config {cfg[g].get(k)!r}")
        # 3. the record shows the setting was CONSUMED, not merely embedded.
        # A value that round-trips into the file and into the record's config
        # block proves the form works and proves nothing about the run: every
        # setting listed here changed something the run reported.
        f_ = rec.get("filter") or {}
        figs = rec.get("figures") or []
        consumed = {
          "screen": [
            ("volatility band applied", (f_.get("volatility") or {}).get("applied")),
            ("volatility band matches the posted band",
             (f_.get("volatility") or {}).get("low") == cfg["screen"]["atr_low"]
             and (f_.get("volatility") or {}).get("high") == cfg["screen"]["atr_high"]),
            ("volume floor applied at the posted floor",
             (f_.get("liquidity") or {}).get("applied")
             and (f_.get("liquidity") or {}).get("floor") == cfg["screen"]["min_quote_volume"]),
            ("history floor applied at the posted days",
             (f_.get("history") or {}).get("applied")
             and (f_.get("history") or {}).get("days") == cfg["screen"]["min_history_days"]),
            ("ranking applied on the posted signal and third",
             (f_.get("ranking") or {}).get("applied")
             and (f_.get("ranking") or {}).get("signal") == cfg["screen"]["rank_signal"]
             and (f_.get("ranking") or {}).get("tercile") == cfg["screen"]["rank_tercile"]),
            ("fold pass rate scored against the posted bar",
             all(r.get("fold_bar") == cfg["screen"]["fold_bar"] and r.get("folds_scored")
                 for r in rec["scores"])),
          ],
          "label": [("the record names the outcome it scored",
                     rec.get("kind") == cfg["label"]["kind"])],
          "viz": [("every ticked figure was drawn",
                   sorted(f["panel"] for f in figs) == sorted(cfg["viz"]["panels"])),
                  ("no figure is an empty box",
                   bool(figs) and all(f["bytes"] > 12_000 for f in figs))],
          "signals": [("the figures that read the engine settings were drawn",
                       {"macd", "confluence", "fibonacci"} <= {f["panel"] for f in figs})],
        }
        for g in groups:
            for what, ok in consumed.get(g, []):
                if not ok: problems.append(f"{g}: NOT CONSUMED, {what}")
        print("filter:", json.dumps({k: (v.get("applied") if isinstance(v, dict) else v)
                                     for k, v in f_.items()}))
        print("figures:", [(f["panel"], f["bytes"]) for f in figs])
        print("scores rows:", len(rec["scores"]), "| keys:", list(rec["scores"][0])[:20] if rec["scores"] else None)
        print("screen:", {k: (v if not isinstance(v, (list, dict)) else len(v)) for k, v in (rec.get("screen") or {}).items()} )
        print("calibration:", {k: (v if not isinstance(v, (list, dict)) else len(v)) for k, v in (rec.get("calibration") or {}).items()})
    # 4. Choose Label, Outcome: the run must ROUTE on it. The barrier path was
    # checked above; flip the setting and the same command must score the
    # three-way outcome and say so in its own record.
    if "label" in groups:
        post("label", dict(GROUPS["label"], kind="three-way"))
        before3 = set(glob.glob("04-outputs/AA-evals/*/bench-3way-*.json"))
        r3 = subprocess.run([".venv/bin/python", "03-inputs/bench_run.py",
                             "--label", "settings harness, three-way"],
                            capture_output=True, text=True, timeout=1500)
        print(f"three-way run: exit {r3.returncode}"); print(r3.stdout[-900:]); print(r3.stderr[-500:])
        new3 = set(glob.glob("04-outputs/AA-evals/*/bench-3way-*.json")) - before3
        if not new3:
            problems.append("label.kind: three-way wrote no three-way record")
        else:
            d3 = json.load(open(sorted(new3)[-1]))
            print("three-way record:", sorted(new3)[-1])
            if d3.get("kind") != "three-way":
                problems.append(f"label.kind: the record says {d3.get('kind')!r}")
            if d3.get("band") != float(GROUPS["label"]["flat_band"]):
                problems.append(f"label.flat_band: the run used {d3.get('band')!r}, "
                                f"posted {GROUPS['label']['flat_band']}")
            if not (d3.get("filter") or {}).get("volatility", {}).get("applied"):
                problems.append("label.kind: the three-way path skipped the filter")
finally:
    shutil.copy(backup, bc.ACTIVE)
print("PROBLEMS:" if problems else "all posted settings saved and embedded", *problems, sep="\n  ")
