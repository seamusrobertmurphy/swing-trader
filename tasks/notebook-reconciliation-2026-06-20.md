# Canonical notebook reconciliation: Chapter Three vs the scripts

Written 2026-06-20. The standalone scripts in `inputs/` advanced a lot this session; the
canonical notebook Seamus works from has not kept up. This file lists every drift so the fixes
can be applied in one mechanical pass instead of being reverse-engineered later. It does not edit
the notebook; per the standing convention the canonical notebooks get paste-in cells, not direct
edits.

## Scope

- `03-trader-execution.ipynb` is the one that has drifted, because it is the chapter the scripts
  feed. This is the focus below.
- `02-trader-controls.ipynb` got its CONFIG updated this session (take_profit_pct 10, hold window
  20, fees 0.15 + 0.05) and is otherwise current; its one open item is the exit-geometry stop,
  which is a tuning question, not a drift.
- `01-trader-metrics.ipynb` is prose and Chapter One signals; the script updates do not touch it.

## The core problem

`03-trader-execution.ipynb` carries its own inline copies of `split()`,
`confidence_filtered()`, and `evaluate()`, plus an inline bake-off and honesty gate. Meanwhile
`inputs/train_model.py` is now the source of truth and has grown well past the notebook: it
computes all four Keller metrics, writes the model, and posts a full record to the AA-evals hub
through `inputs/eval_report.py`. The notebook reproduces only the oldest, simplest slice of that
(precision, recall, AUC, the 60/40 filter) and stops there. Every run from the notebook therefore
produces a weaker, unrecorded result than the same run from the script.

The strategic choice is the important part, so decide it first:

- Option A, recommended. Make the notebook a thin driver over the scripts: import `split`,
  `confidence_filtered`, `evaluate`, `CONF_HI`, `CONF_LO`, `COST_PCT` from `train_model`, and call
  `eval_report.write_comparison(...)` for the metrics and bookkeeping. Keep the markdown cells and
  perhaps one or two display cells for teaching, but let the numbers come from the same code the
  script runs. This kills the drift permanently; the notebook and the script can never disagree
  again because they are the same code.
- Option B. Port each missing piece into the notebook inline. Keeps the notebook fully
  self-contained but guarantees this reconciliation has to happen again next time a script changes.

## The drift list (what the notebook is missing or has stale)

1. Stale data path. The load cell uses `ds = CSV / "dataset.csv"` (outputs/CSV). The training set
   moved this session to `inputs/binance-data/dataset_ccxt_10coins_2017-2026.csv` and both scripts
   now resolve it through `bd.DATASET_PATH`. Not breaking (the cell falls back to rebuilding), but
   if left as-is the notebook rebuilds from the network and recreates the file in the old place,
   undoing the move. Paste-in below.

2. No cost constants. The notebook CONFIG has no round-trip fee or slippage. `train_model.py` sets
   `ROUND_TRIP_FEE_PCT 0.15`, `SLIPPAGE_PCT 0.05`, `COST_PCT 0.20`. Without these the notebook
   cannot compute Metric 2.

3. Ignores `trade_ret`. `build_dataset.py` now emits a `trade_ret` column (the realized
   triple-barrier return per row). The notebook never reads it, so it has no raw material for P&L.

4. No Metric 2 (P&L after costs). The notebook stops at precision/recall/AUC. It does not compute
   per-trade expectancy, win rate, per-trade Sharpe, the t-stat, or the additive equity curve that
   `eval_report._pnl` produces. This is the metric that actually decides GO/NO-GO, so its absence
   from the notebook is the biggest gap.

5. No Metric 3 (regime-stratified AUC). The notebook does not split AUC by the `f_rv_30` volatility
   terciles. `eval_report._regime_auc` does (the finding so far: edge concentrates in the
   high-volatility regime).

6. No AA-evals bookkeeping. The notebook never calls `eval_report.write_comparison`, so a run from
   the notebook does not land in `outputs/AA-evals/evaluation-scores.md/.pdf/.docx`, the dated
   per-run record folder, or the chart set. Runs from the notebook are effectively unlogged.

7. No `model_metrics.txt`. `train_model.py` writes a text summary alongside `model.joblib`; the
   notebook writes only the joblib.

8. Minor: the notebook's `evaluate()` returns a smaller dict than the script's (no `conf`, `acc`,
   `rec`, `cv_auc`), which is exactly why it cannot feed `eval_report.write_comparison` as-is.
   Option A resolves this for free by importing the script's `evaluate`.

9. Forward-looking, not yet in either: the daily trade-flow feature from `flow_data.py`
   (`daily_flow.csv`) is not joined in `build_dataset.py` yet, so the notebook is correct to not
   reference it today. When 2.1 in the handoff lands that feature, both `build_dataset.py` and this
   notebook update together.

## Ready-to-paste fixes

Fix 1, the data-load cell (cell currently beginning `ds = CSV / "dataset.csv"`). Replace its body:

```python
ds = bd.DATASET_PATH            # single source of truth: inputs/binance-data/dataset_ccxt_...
if os.path.exists(ds):
    df = pd.read_csv(ds, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    print(f"loaded {ds}  ({len(df):,} rows)")
else:
    print("no training set found - building from live data (needs network)...")
    os.makedirs(bd.DATASET_DIR, exist_ok=True)
    df = bd.build(); df.to_csv(ds, index=False)
```

And the markdown cell above it: change "Loads `outputs/CSV/dataset.csv`..." to "Loads the
training set at `inputs/binance-data/dataset_ccxt_10coins_2017-2026.csv` (via `bd.DATASET_PATH`)
if present, otherwise builds it from live data."

Fix the metrics and bookkeeping (Option A), replacing the inline `split`/`confidence_filtered`/
`evaluate` definitions and the bake-off cell. Sketch:

```python
import train_model as tm, eval_report
train, test, cut = tm.split(df)
feat = [f for f in bd.FEATURES if f in df.columns]
Xtr, ytr, Xte, yte = train[feat], train["label"], test[feat], test["label"]
base_te = yte.mean()

# Same models the script uses (LR, RF, LightGBM); reuse tm.evaluate so notebook == script.
lines = []
scored = []
for name, mdl in tm.build_models(HAVE_LGBM):     # or inline the same 3 estimators
    prec, m = tm.evaluate(name, mdl, Xtr, ytr, Xte, yte, base_te, lines)
    scored.append((prec, name, mdl, m))
print("\n".join(lines))
best = max(scored, key=lambda t: t[0])

# Metrics 2 and 3 + the AA-evals record, identical to the script:
meta = dict(dataset_rows=len(df), n_features=len(feat), train_rows=len(train),
            test_rows=len(test), base_rate=float(base_te),
            cut=str(pd.Timestamp(cut).date()), embargo=tm.EMBARGO_DAYS,
            conf_hi=tm.CONF_HI, conf_lo=tm.CONF_LO, chosen=best[1],
            trade_ret=test["trade_ret"].tolist() if "trade_ret" in test else None,
            regime_vol=test["f_rv_30"].tolist() if "f_rv_30" in test else None,
            cost_pct=tm.COST_PCT)
rec = eval_report.write_comparison(str(OUTPUTS / "AA-evals"),
                                   [m for (_, _, _, m) in scored], yte, meta)
print("evaluation record:", rec["md"])
```

Note: `tm.build_models` does not exist yet; either add a small `build_models(have_lgbm)` helper to
`train_model.py` (cleanest, so notebook and script share the exact estimator list) or paste the
same three estimators inline. Adding the helper is the better move and is a one-function change.

## Recommendation on timing

The analysis is done; this file is the list. The edits themselves are mechanical but land in a
canonical notebook, so they should be applied as paste-ins with Seamus present, or by the next
session working straight from this file. Given the context budget at the end of this session, the
safe path is to hand this file to the next session and have it do Option A as its first task,
before any tuning, so that every tuning run from the notebook is recorded in AA-evals from the
start. If budget allows in this session, Fix 1 (the data path) is the one worth pasting
immediately, because it prevents the notebook from silently undoing the dataset move.
