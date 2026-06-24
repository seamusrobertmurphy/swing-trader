# Autonomous overnight run — progress + plan (started 2026-06-23, ~01:30 PDT)

Operator mandate (Seamus, before sleep): train and tune the model integrating ALL Supertrend
features and per-coin trailing-stop exit protocols, tuned across volatility-regime strata; deliver
honest, deployable OOS results; scan the repo for outstanding jobs; keep working until he returns.
Commitment: report whatever the after-fee OOS scoreboard honestly shows — never a fabricated GO.

## The gating reality
Training "with all the Supertrend features" needs the rebuilt FULL-MARKET dataset (the `f_st_`
block + the dropped duplicate only exist after a rebuild, and survivorship needs the delisted
coins). That rebuild is gated on the survivorship download. So the sequence is download -> audit ->
rebuild -> reprofile -> [train + tune]. The first four are automated; the last is the deliverable.

## Background jobs (do not double-run rebuilds)
- **Download** `acquire_vision.py download --interval 1h` (PID 24958) — pulling the 612-pair
  historical universe incl. ~188 delisted; resumable, checksum-verified. Log:
  `inputs/binance-data/_acquire_vision_download.log`. ~400 klines folders as of last check.
- **Auto-rebuild monitor** (bg task bi3gbtoiy) — waits on PID 24958, then runs: clear exFAT litter
  -> `acquire_vision.py audit` -> `build_dataset_1h.py` (full rebuild, picks up `f_st_` + dup drop)
  -> `profile_panel.py`. Log: `inputs/binance-data/_auto_rebuild.log`. THIS notification is the
  trigger for the training pipeline.

## Done this session (verified)
- ClaudeTrader installed editable into `.venv` (`from utils import risk, performance`).
- `f_st_` Supertrend feature block added to `build_dataset_1h.py` (7 causal features); smoke-tested.
- Dropped the duplicate feature `f_wc_rv_short` (== `f_hr_rv_long`, corr 1.0; EDA-caught).
- `baseline_supertrend_1h.py` — triple-Supertrend rules benchmark, after-fee via ClaudeTrader. NO-GO.
- `exit_geometry_1h.py` — NEW: 1h exit sweep with per-coin trailing stops + time-decaying TP +
  lo/mid/hi regime breakdown, scored after-fee vs buy-hold. Validated on BTC/ETH (NO-GO, bleeds
  worst in high-vol regime — honest). This is the "per-coin trailing stop exit protocol" deliverable.
- **Fixed `model_assessment_1h.py` crash**: the stacking ensemble used `cv=TimeSeriesSplit(3)`, which
  sklearn rejects ("cross_val_predict only works for partitions"). Changed to `cv=3`. THIS was why the
  terminal assessment printed scores then never wrote a record (crashed before `write_record`) — the
  root cause of "assessment not appearing in notebook 3".
- Notebook 3: EDA cell, glmnet variable-selection wiring, hardened+inlined Model Assessment cell,
  header cleanup (all `###`, <=2 words), prose aligned to current methods, Supertrend Integration cell.
- Notebooks 1 & 2: Supertrend Integration cells; headings shortened to <=3 words.
- Docs: `tasks/integration-2026-06-23-claudetrader-supertrend.md`; CLAUDE.md notebook-integration directive.

## Pipeline to run WHEN THE REBUILD LANDS (ordered; from TASK_next-model-build + handover-pm)
1. **Split audit (gate)** `split_checks.py` on the full-market temporal split — representativeness +
   drift + imbalance, BEFORE reading GO/NO-GO. Large drift + NO-GO = regime change, not no-edge.
2. **Variable selection** glmnet path on TRAIN -> `SELECTED_FEATURES` (includes the new `f_st_`).
3. **Train head-to-head** `train_model_1h.py` (or notebook cells) — LogReg/RF/LightGBM, Metric 1/2/3.
4. **Label sweep** `sweep_label_1h.py` — settle the ATR triple-barrier (tgt/stop/horizon) on after-fee.
5. **Exit-geometry sweep** `exit_geometry_1h.py --signal model` — per-coin trailing + time-decay TP,
   regime breakdown. Pick the exit config that maximizes after-fee expectancy and is regime-stable.
6. **Model assessment** `model_assessment_1h.py` (now fixed) — caret Full/CV RMSE + classification view.
7. **Honest GO/NO-GO** on the full-market final-year OOS, vs buy-hold AND coin-flip, after fees.
   Reconcile the exit config back into the live bot's stop/trail and CLAUDE.md's provisional -7%/10%.

## DIAGNOSIS (2026-06-23) — why NO-GO persists, and the reprioritization
Root cause is NOT model capacity; it is the LABEL. Measured on the current data:
base rate 0.313 vs breakeven 0.333 for the +2/-1 ATR geometry, so the target has
NEGATIVE unconditional expectancy (a perfect predictor still starts -2pp down).
Mean trade_ret = -0.069% GROSS, -0.269% after 20bps. LightGBM RMSEratio 0.61 = pure
overfit (no stable cross-time signal); linear models sit at AUC 0.50 = random. This is
the efficient-market floor for public, price-derived TA at 1h on liquid USDT pairs.
Survivorship correction will LOWER measured performance (dead coins are losers), so the
rebuild makes the NO-GO more trustworthy, not better.

Reprioritized pipeline (edge comes from changing the PROBLEM, not tuning the model):
  1. LABEL-GEOMETRY SWEEP FIRST (sweep_label_1h.py) — find a barrier where base rate
     clears breakeven (symmetric +1/-1, or longer horizon resolving on drift). Was step 4;
     now the gating experiment.
  2. Longer-horizon test (daily/swing) — trend/factor structure persists, fee drag drops.
  3. Cross-sectional framing — rank coins, long the top decile (relative momentum) instead
     of predicting each coin's barrier. Cross-sectional edge often survives where TS dies.
  4. Only then: variable selection / train / exit-geometry / assessment on the best label.
  5. Honest GO/NO-GO. Do NOT torture the OOS year to force a GO.
Future information-set work (the real alpha lever, beyond this run): order-book depth/
imbalance, funding, open interest, liquidations, BTC->alt lead-lag, on-chain flow.

## Profit push (2026-06-23, later) — actions taken
- Model zoo expanded: LightGBM is no longer the only booster. `model_assessment_1h.model_zoo` now
  runs THREE gradient-boosting implementations (LightGBM, HistGBM = scalable histogram GBM, and
  GBM.classic = textbook sklearn GBM) alongside LogReg.glm/enet, RF, and the stacking ensemble.
- Caret-style hyperparameter tuning added: `model_assessment_1h.tune(df, feat, model_key)` grids over
  TimeSeriesSplit CV -> CV RMSE per setting; `write_tuning_record` persists to
  outputs/AA-evals/<date>/model-tuning-<model>-<date>.md. CLI: `--tune histgbm|lightgbm|rf|gbm`.
- Fixed a pre-existing `sweep_label_1h.py` bug (feat_cols taken from coin[0]; coins lacking flow
  crashed dropna with KeyError). Now uses the UNION feature set + dropna on present columns. This
  also hardens it for the full-market rebuild (delisted coins lack flow). Relaunched the LABEL SWEEP
  (the #1 profit lever) on 15 liquid coins, widened grid (targets 1.0/1.5/2.0/3.0 x stops 1.0/2.0 x
  horizons 48/96 = symmetric .. forgiving geometries). Log: inputs/binance-data/_label_sweep.log ->
  result to outputs/AA-evals/<date>/label-sweep-<date>.md. Looking for a geometry whose win rate
  clears breakeven stp/(stp+tgt) after fees.
- Chapter-3 EDA cell rewritten: dimensions+characteristics table, label-by-year, per-coin
  composition, feature redundancy, class separation, correlation+distribution visuals.
- TODO next: wire a tuning cell into ch3 Model Tuning (after the zoo/tune validation confirms); add
  BTC lead-lag + relative-strength features to build_dataset_1h (real new information lever); read
  the label-sweep result and reconcile the winning geometry into bd.LABEL.

## New feature families added (populate on rebuild) — 2026-06-23
All in build_dataset_1h.py, wired into build_coin(), causal + scale-invariant, validated:
- `f_btc_` — BTC lead-lag / relative strength (BTC momentum, coin momentum vs BTC, rolling beta/corr).
  First family NOT a self-transform of the coin's own price. `load_btc_series` loaded once in build().
- `f_4h_` / `f_d1_` — MULTI-TIMEFRAME (4h + daily RSI/EMA-spread/momentum/ATR%/Supertrend), resampled
  and merged onto the 1h frame with merge_asof(backward) on the higher-tf CLOSE time. Validated
  no-lookahead (piecewise-constant within each period, value = last higher-tf bar closed by t to 9dp).
  Multi-resolution TRAINING (context), not trading — decision cadence + fee count stay 1h.
- Documented in ch3 Feature Variables -> "### Feature Integration" (markdown + live-source code cell).
The rebuild will jump from 61 features to ~61 + 7(f_st_) + 7(f_btc_) + 10(f_4h_/f_d1_) - 1(dup) ~= 84.

## YouTube workflow finding + Modern Supertrend + Monte Carlo (2026-06-23)
- Read research/GBBC 2026 SuperTrend... .md (TradingView indicator + transcript). KEY: the author
  himself states Supertrend is "right about 48% of the time, basically a coin flip", "bleeds out on
  the 1 hour and below", "only holds up at the 4-hour and above", and is "not a trading system, one
  layer of confluence." This INDEPENDENTLY CONFIRMS our AUC~0.5 / 1h-NO-GO / go-to-4h+ findings.
  These YouTubers are NOT running multi-coin ML models; they trade one chart discretionarily at 4h+
  with 3-layer confluence and tight 2R risk. Headline profit numbers are indicator backtests/marketing.
- Integrated `f_mst_` (Modern Adaptive Supertrend, GBB): Kaufman Efficiency Ratio (KER regime/trend
  efficiency), L2 convex regime-scaled band multiplier, L3 hysteresis/commit filter. Validated: 83%
  fewer false flips than plain Supertrend on BTC 1h; KER in [0,1]; uptrend share 0.48 (matches author).
  KER is a principled chop-vs-trend regime GATE -> trade only when KER high (efficient trend).
- Implication for profit path: decision frame -> 4h+, gate entries on high KER (efficient-trend
  regime), confluence of features, tight risk. This is the systematic version of what the bots do.
- Monte Carlo training regime: inputs/monte_carlo_1h.py (bootstrap + permutation significance on
  after-fee per-trade returns -> CI on total return / max drawdown / Sharpe, p(loss), p-value).
  Wired into ch3 Stability. Writes outputs/AA-evals/<date>/monte-carlo-<date>.md.

## Caveats to carry
- The on-disk dataset is the STALE 47-coin June-21 build (no `f_st_`); any number off it is an upper
  bound twice over. Do NOT report it as the result. Wait for the rebuild.
- Guardrails: no live trading (LIVE_TRADING off), spot only, don't touch config.py/requirements.txt.
  Seamus owns CLAUDE.md/INDEX.md (append only).
