# TASK (handoff): finish model training, stage the launch — isolated, non-destructive

The previous session was mounted on the WRONG folder (`trader-swing`, now empty).
The operator's live work — notebook, markdowns, config.py, requirements.txt,
inputs/ — is in the OTHER repo (the `ccxt-bot` project open in Positron). Get
mounted on THAT repo before doing anything.

## Hard constraints (do not violate)
1. Work ONLY inside a brand-new folder you create adjacent to existing work
   (e.g. `<repo>/model-run/`). Everything you write goes there.
2. Do NOT touch the operator's markdowns, notebook, config.py, requirements.txt,
   .venv, environment variables, or git. Current work must stay revertible.
3. Do NOT flip any live switch and do NOT place any order. Staging only. The
   operator arms live trading themselves when back.
4. Be honest about edge. Do not present a NO-GO model as tradeable.

## Environment notes (these cost hours — read them)
- Python is uv-managed (cpython 3.11). The notebook kernel binds to uv's BASE
  interpreter, which is PEP 668 "externally-managed", so plain pip fails.
- In notebooks use %pip (targets the running kernel). %pip does NOT support shell
  redirection — for freeze use `!{sys.executable} -m pip freeze > file`.
- On uv's base Python, add `--break-system-packages` to `%pip install` (never to
  `pip freeze`, which has no such flag).
- To install into a .venv the KERNEL must be `.venv/bin/python` (kernel picker +
  restart); `source activate` in a cell does nothing.
- Packages in use: ccxt, alpaca-py, python-binance, pandas, pandas-ta-classic,
  pykalman, plotly, jinja2, scikit-learn, joblib.

## Build three self-contained scripts in the new folder

### build_dataset.py
- Universe (train AND trade, USDT spot): BTC ETH SOL BNB XRP ADA AVAX LINK LTC DOGE.
- One row per (symbol, date); full daily history via ccxt, paginated past the
  1000-bar cap; drop the final unclosed candle.
- 17 scale-invariant, causal features (use only data up to each bar):
  (close-kalman)/kalman; (ema14-ema91)/close; (ema91-ema125)/close; RSI/100;
  Choppiness/100; MACD-hist/close; MACD-below-zero; Bollinger pos
  (close-bbl)/(bbu-bbl); volume/20d-avg-vol; (nearest-resistance-close)/close;
  flags: ema-cross state, golden/death cross event, doji, dragonfly, gravestone,
  breakout. Use a scalar forward-pass Kalman so pykalman isn't required.
- Label: 1 if +10% before -5% within 20 days, else 0. Stop checked before target
  on a single bar (conservative). Drop last 20 rows/coin and warmup NaNs.
- Output: outputs/dataset.csv. Expose fetch_history() and compute_features().

### train_model.py
- Time-ordered split 70/30, never random. Embargo = 20 days each side of the cut.
- Report base rate on train and test; print both date spans (confirm bull/bear/
  sideways coverage). class_weight="balanced". Tune on train only with
  TimeSeriesSplit; score test ONCE.
- Fit LogisticRegression AND RandomForest; keep higher BUY-class precision.
- Report accuracy/precision/recall/ROC-AUC/confusion vs base rate.
- Honesty gate -> GO only if test buy-precision clearly beats base rate AND AUC>0.55.
- Save model.joblib (model + features + go flag) and model_metrics.txt.

### trade scripts (staged, gated, NO orders)
- ccxt keys are `apiKey` and `secret` (config var names are arbitrary labels).
- Alpaca PAPER: ALPACA_BASE_URL=https://paper-api.alpaca.markets, paper keys.
- Binance LIVE only when LIVE_TRADING == "true" (exact string); else refuse.
  Default ccxt set_sandbox_mode(True) until proven.
- Flow: read balance -> EXITS before ENTRIES -> size by cash/#buys with a
  per-position cap and cash floor -> order -> log. Refuse entry if gate is NO-GO.
- Leave the switch OFF.

## Standing result (prior run, real Binance data)
27,699 rows, 10 coins, 2017–2026, base rate 0.325. Leakage test passed exactly.
Best model RandomForest: test buy-precision 0.320 vs base rate 0.304, lift +0.017,
AUC 0.514. NO-GO — no demonstrable edge. Do not risk real money without first
improving the model (richer/longer-horizon features, higher probability threshold,
per-coin models) and confirming backtest expectancy survives fees.

## Deliverables in the new folder
dataset.csv, model.joblib, model_metrics.txt, the three scripts, plus:
- WALKTHROUGH.md — plain language: the data, each feature/label, the split and
  embargo, the honest result. For the operator to read on return.
- RUNBOOK.md — exact launch commands (Alpaca paper, Binance live), where the single
  safety switch is, the go/no-go decision the operator owns.

## First thing to confirm with the operator
The model is NO-GO. Confirm whether to stage it as-is (ready, switch off) or first
attempt the model improvements above. Do not enable live trading either way.
