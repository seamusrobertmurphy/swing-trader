"""Does TimesFM's forecast help the presets' models as an extra input?

    .venv/bin/python 03-inputs/timesfm_feature_test.py --count     # forecasts needed, and the time
    .venv/bin/python 03-inputs/timesfm_feature_test.py             # the test

Operator request, 30 September 2026, upgrade 3: "Test TimesFM as an extra input
to the model. Its forecast becomes one more thing the model weighs, and the
scoreboard shows whether it helps."

Each preset, on crypto and on stocks, is run as a user's run is, through
demo_run.build_frame, the screen, the cost floor and the preset's own model, as
mfi_gate_test.py does. Three columns are added to every candle, each made from
the 512 closes up to and including that candle only, at the preset's horizon:
f_tfm_ret, the median forecast's move from the close; f_tfm_band, the width of
the 10th to 90th percentile band over the close; and f_tfm_z, the move over the
width. The model is fitted twice on the same training rows, without and with the
three columns, and both are scored once on the same test year.

The rule, fixed before any result: TimesFM helps a preset if with it the test
year's Theil's U2 falls and the overfit ratio stays at or under 1.1 (win-or-loss
presets), and the most confident fifth earns more after cost (every preset).

TimesFM 2.5, https://huggingface.co/google/timesfm-2.5-200m-pytorch, Apache 2.0.
Forecasts are cached in 03-inputs/timesfm-features/, so a rerun computes only
new candles. The record is written in the bench-sweep shape, so its rows reach
the C1 scoreboard and the app's Model scores unchanged.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
# Two stages, 30 September 2026. The first loads PyTorch, before the other
# libraries as timesfm_forecast.py must, and only makes the forecasts. The second,
# run as a fresh process with --fit, never loads PyTorch and fits the models: the
# first run died without a word on the Three-way preset, whose LightGBM and
# PyTorch each carry their own OpenMP, a known crash when both are loaded.
if "--fit" not in sys.argv:
    import torch  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench_config as bc          # noqa: E402
import bench_run as br             # noqa: E402
import demo_run as dr              # noqa: E402
import demo_scan as ds             # noqa: E402
import train_model_1h as t1        # noqa: E402

CONTEXT = 512
CACHE = Path(__file__).resolve().parent / "timesfm-features"
TFM = ["f_tfm_ret", "f_tfm_band", "f_tfm_z"]
LABELS = {"best": "Best on record", "threeway": "Three-way outcome", "quick": "Quick and simple"}


def cases() -> list[tuple[str, str, dict]]:
    p = json.loads(ds.PRESET_FILE.read_text(encoding="utf-8"))
    out = []
    for market in ("crypto", "equity"):
        for key in ("best", "threeway", "quick"):
            cfg, _ = dr.sanitize(ds.as_form(p[key][market]))
            out.append((key, market, cfg))
    return out


def rows_of(cfg: dict):
    """The case's rows exactly as a user's run makes them (mfi_gate_test.one)."""
    df, _, feats = dr.build_frame(cfg, log=lambda *_: None)
    d, _ = br.apply_screen(cfg, df.copy(), log=lambda *_: None)
    f = br.choose_features(cfg, feats, log=lambda *_: None)
    lb = cfg["label"]
    if lb["kind"] == "three-way":
        d["label"] = dr._three_way(d["ret3"].to_numpy(float), float(lb["flat_band"]))
    gap = max(1, int(np.ceil(int(lb["horizon_bars"]) / bc.bars_per_day(cfg["data"]["frame"]))))
    train, test, cut = t1.split(d, oos_days=int(cfg["split"]["holdout_days"]), embargo_days=gap)
    train, test, _ = dr.floors(cfg, train, test, log=lambda *_: None)
    return train, test, f, cut


def key_of(ts, market: str = "crypto") -> np.ndarray:
    """Candle open times as UTC nanoseconds, or for stocks the trading date.

    A stock row is stamped as a plain date at midnight and the price file as
    midnight New York, 04:00 or 05:00 UTC, so stocks are matched by the date in
    New York; crypto keeps the exact time, since its day starts at midnight UTC.
    """
    t = pd.to_datetime(pd.Series(ts))
    if market == "equity":
        t = t.dt.tz_convert("America/New_York").dt.tz_localize(None) if t.dt.tz is not None else t
        return t.dt.normalize().astype("int64").to_numpy()
    t = t.dt.tz_convert("UTC").dt.tz_localize(None) if t.dt.tz is not None else t
    return t.astype("int64").to_numpy()


def cache_path(market, frame, h, sym) -> Path:
    return CACHE / f"{market}-{frame}-h{h}-{sym}.parquet"


def needed(market, frame, h, sym, keys) -> tuple[pd.DataFrame, list[int]]:
    p = cache_path(market, frame, h, sym)
    have = pd.read_parquet(p) if p.exists() else pd.DataFrame(columns=["key", *TFM])
    return have, sorted(set(int(k) for k in keys) - set(have["key"].astype("int64")))


def model(horizon: int):
    import timesfm
    import torch
    torch.set_float32_matmul_precision("high")
    m = timesfm.TimesFM_2p5_200M_torch.from_pretrained("google/timesfm-2.5-200m-pytorch")
    m.compile(timesfm.ForecastConfig(max_context=CONTEXT, max_horizon=horizon, normalize_inputs=True,
                                     use_continuous_quantile_head=True, fix_quantile_crossing=True,
                                     per_core_batch_size=32))
    return m


def compute(m, market, frame, h, sym, keys, log=print) -> pd.DataFrame:
    """TimesFM columns for these candles, from the cache or fitted now."""
    have, todo = needed(market, frame, h, sym, keys)
    if todo and m is None:
        # Candles that closed after the forecasting stage; their rows are left out
        # of both fits below, so with and without still see the same rows.
        log(f"    {sym}: {len(todo)} newest candles have no forecast yet, left out")
        return have
    if todo:
        # Loaded here only: timesfm_forecast imports PyTorch, which the fitting stage must not.
        import timesfm_forecast as tf
        d = tf.load(market, frame, sym)
        if d is None:
            raise SystemExit(f"no prices for {sym} on {frame}")
        opens, close = key_of(d["datetime"], market), d["close"].to_numpy()
        pos = {int(k): i for i, k in enumerate(opens)}
        idx = [pos[k] for k in todo if k in pos and pos[k] >= 64]
        new = []
        t0 = time.time()
        for b in range(0, len(idx), 64):
            part = idx[b:b + 64]
            # Only the closes up to and including the candle itself.
            p, q = m.forecast(horizon=h, inputs=[close[max(0, i + 1 - CONTEXT): i + 1].astype("float32") for i in part])
            c = close[part]
            ret = p[:, h - 1] / c - 1
            band = (q[:, h - 1, 9] - q[:, h - 1, 1]) / c
            new.append(pd.DataFrame(dict(key=opens[part], f_tfm_ret=ret, f_tfm_band=band,
                                         f_tfm_z=ret / np.where(band > 0, band, np.nan))))
            if b and b % 1280 == 0:
                log(f"    {sym}: {b:,} of {len(idx):,} forecasts, {time.time() - t0:.0f}s")
        if new:
            have = pd.concat([have, *new], ignore_index=True).drop_duplicates("key")
            CACHE.mkdir(parents=True, exist_ok=True)
            have.to_parquet(cache_path(market, frame, h, sym), index=False)
    return have


def join(rows: pd.DataFrame, feats: pd.DataFrame, sym: str, market: str) -> pd.DataFrame:
    col = "symbol" if "symbol" in rows.columns else "coin"
    mine = rows[rows[col].astype(str).str.replace("/", "") == sym].copy()
    mine["key"] = key_of(mine["datetime"], market)
    return mine.merge(feats.astype({"key": "int64"}), on="key", how="left").drop(columns="key")


def with_tfm(m, market, cfg, rows, log=print) -> pd.DataFrame:
    frame, h = cfg["data"]["frame"], int(cfg["label"]["horizon_bars"])
    col = "symbol" if "symbol" in rows.columns else "coin"
    parts = []
    for sym in sorted(rows[col].astype(str).str.replace("/", "").unique()):
        keys = key_of(rows.loc[rows[col].astype(str).str.replace("/", "") == sym, "datetime"], market)
        parts.append(join(rows, compute(m, market, frame, h, sym, keys, log=log), sym, market))
    out = pd.concat(parts).sort_values("_row").reset_index(drop=True)      # the rows' own order
    hit = float(out["f_tfm_ret"].notna().mean())
    if hit < 0.99:
        raise SystemExit(f"only {hit:.1%} of rows found their TimesFM forecast; the join is wrong")
    return out


def score(cfg, train, test, feats, label):
    name = cfg["model"]["estimators"][0]
    params = (cfg["model"].get("params") or {}).get(name)
    row = {}
    if cfg["label"]["kind"] == "barrier":
        got = br.score_estimator(name, params, cfg, train.dropna(subset=feats), test.dropna(subset=feats), feats,
                                 log=lambda *_: None)
        row = dict(got[0]) if got else {}
    est = br.make_estimator(name, cfg["model"]["class_weight"], params)
    tr = train.dropna(subset=feats)
    est.fit(tr[feats], tr["label"])
    _, earned, rec = dr.fifths(cfg, est, test.dropna(subset=feats), feats)
    row.update(model=name, name=label, fifths=earned, top_fifth=rec["top_fifth"], every=rec["every"],
               test_candles=rec["test_candles"], train_candles=len(tr), features=len(feats))
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--count", action="store_true", help="count the forecasts needed and stop")
    ap.add_argument("--only", default=None, help="one case, such as quick:crypto, for a trial")
    ap.add_argument("--rows", type=int, default=0, help="keep only the newest rows of each split, for a trial")
    ap.add_argument("--fit", action="store_true", help="the second stage: fit from the cached forecasts")
    a = ap.parse_args()
    todo = [c for c in cases() if not a.only or f"{c[0]}:{c[1]}" == a.only]
    built = []
    for key, market, cfg in todo:
        train, test, f, cut = rows_of(cfg)
        if a.rows:
            train, test = train.tail(a.rows), test.tail(a.rows // 3)
        # Each row keeps its year and its place, since joining on the forecasts
        # renumbers the rows.
        train = train.assign(_part="train")
        test = test.assign(_part="test")
        rows = pd.concat([train, test], ignore_index=True)
        frame, h = cfg["data"]["frame"], int(cfg["label"]["horizon_bars"])
        col = "symbol" if "symbol" in rows.columns else "coin"
        n = 0
        for sym in rows[col].astype(str).str.replace("/", "").unique():
            n += len(needed(market, frame, h, sym, key_of(rows.loc[rows[col].astype(str).str.replace("/", "") == sym,
                                                                    "datetime"], market))[1])
        print(f"{LABELS[key]}, {market}: {frame}, horizon {h}, {len(train):,} training and {len(test):,} test "
              f"candles, {n:,} forecasts to compute", flush=True)
        built.append((key, market, cfg, train, test, f, cut, n))
    total = sum(b[-1] for b in built)
    print(f"{total:,} forecasts in all, about {total / 64 * 7 / 60:.0f} minutes at 7 seconds a batch of 64", flush=True)
    if a.count:
        return 0
    if not a.fit:
        # Stage one: every forecast into the cache, then the fitting stage as a
        # process of its own.
        m = model(max(int(b[2]["label"]["horizon_bars"]) for b in built))
        for key, market, cfg, train, test, f, cut, _ in built:
            print(f"forecasts for {LABELS[key]}, {market}", flush=True)
            with_tfm(m, market, cfg, pd.concat([train, test], ignore_index=True).assign(
                _row=lambda x: np.arange(len(x))), log=print)
        del m
        return subprocess.run([sys.executable, __file__, "--fit"] + sys.argv[1:]).returncode
    m = None
    now = datetime.now(timezone.utc)
    folder = bc.REPO / "04-outputs" / "AA-evals" / now.strftime("%Y-%m-%d")
    folder.mkdir(parents=True, exist_ok=True)
    stem = folder / f"bench-sweep-timesfm-{now:%Y%m%d-%H%M%S}"
    out, cases_out = [], []
    for key, market, cfg, train, test, f, cut, _ in built:
        print(f"== {LABELS[key]}, {market}", flush=True)
        rows = pd.concat([train, test], ignore_index=True)
        rows["_row"] = np.arange(len(rows))
        allrows = with_tfm(m, market, cfg, rows, log=print)
        if len(allrows) != len(rows):
            raise SystemExit("rows were lost in the join")
        # Both fits use only rows that have a forecast, so they score the same rows.
        allrows = allrows.dropna(subset=["f_tfm_ret"])
        tr, te = allrows[allrows["_part"] == "train"], allrows[allrows["_part"] == "test"]
        base = f"{LABELS[key]}, {market}"
        without = score(cfg, tr.dropna(subset=f + TFM), te.dropna(subset=f + TFM), f, f"{base}, without TimesFM")
        withit = score(cfg, tr.dropna(subset=f + TFM), te.dropna(subset=f + TFM), f + TFM, f"{base}, with TimesFM")
        for r in (without, withit):
            r.update(case=key, market=market, frame=cfg["data"]["frame"], kind=cfg["label"]["kind"], cut=str(cut.date()))
        out += [without, withit]
        cases_out.append((base, cfg["label"]["kind"], without, withit))
        print(f"   top fifth {without['top_fifth']} -> {withit['top_fifth']}", flush=True)
        stem.with_suffix(".json").write_text(json.dumps(dict(
            stamped=now.isoformat(timespec="seconds"), design="TimesFM", kind="timesfm",
            design_name="TimesFM as an input", repeats=1, rows=out), default=float, indent=1))
    write_md(stem, cases_out, now)
    print(stem.with_suffix(".md"))
    return 0


def write_md(stem, cases_out, now) -> None:
    pc = lambda v: "" if v is None else f"{100 * v:+.2f}"               # noqa: E731
    num = lambda v, k: "" if v is None else f"{v:.{k}f}"                 # noqa: E731
    L = [f"# TimesFM as an input, {now:%Y-%m-%d}", "",
         f"Record `{stem.name}.json`, written by `03-inputs/timesfm_feature_test.py`. Each preset was run as a "
         "user's run is and fitted twice on the same training rows, without and with three TimesFM columns (the "
         "median forecast's move, the band width and their ratio, each from the 512 closes up to its own candle), "
         "then scored once on the same test year. TimesFM helps a preset if, with it, the test year's Theil's U2 "
         "falls and the overfit ratio stays at or under 1.1 (win-or-loss presets), and the most confident fifth "
         "earns more after cost (every preset). Money is per cent per candle after cost, over overlapping holds.", "",
         "| Preset | Outcome | Test Theil's U2 | Test AUC | Overfit ratio | Top fifth % | Every candle % | Helps |",
         "|---|---|---|---|---|---|---|---|"]
    for base, kind, a, b in cases_out:
        def cell(k, fmt):
            x, y = a.get(k), b.get(k)
            return "" if x is None or y is None else f"{fmt(x)} to {fmt(y)}"
        u2 = cell("blind", lambda v: num(v.get("theil_u2"), 3)) if kind == "barrier" else "n/a"
        auc = cell("blind_auc", lambda v: num(v, 3)) if kind == "barrier" else "n/a"
        ratio = cell("rmse_ratio", lambda v: num(v, 3)) if kind == "barrier" else "n/a"
        top_up = (b.get("top_fifth") or -9) > (a.get("top_fifth") or -9)
        if kind == "barrier":
            helps = (b["blind"]["theil_u2"] < a["blind"]["theil_u2"] and b["rmse_ratio"] <= 1.1 and top_up)
        else:
            helps = top_up
        L.append(f"| {base} | {kind} | {u2} | {auc} | {ratio} | {pc(a.get('top_fifth'))} to {pc(b.get('top_fifth'))} | "
                 f"{pc(a.get('every'))} to {pc(b.get('every'))} | {'yes' if helps else 'no'} |")
    L += ["", "Each cell reads without TimesFM, then with it."]
    stem.with_suffix(".md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
