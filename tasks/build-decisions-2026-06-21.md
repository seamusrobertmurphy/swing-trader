# Build decisions, 2026-06-21 (1h all-market foundation)

Recorded mid-session after Seamus confirmed the June-21 handover supersedes June-20 for
all task directives. The repo moves to a full-market, 1-hour frame; do not fall back to
the fixed-ten daily frame. pandas-ta features and per-coin trailing-stop exit geometry
are confirmed directives, not open questions.

## Settled this session

1. **Coin universe.** Full ~433 active USDT spot pairs (live from Binance exchangeInfo),
   point-in-time screened, not the fixed ten. Confirmed and validated (exchangeInfo
   returns 433).

2. **Bar interval.** 1 hour. Downloader extended and validated (BTC/ETH/SOL, 2024-01..02,
   4320 hourly rows, 24/day, flow_imbalance in range). 1d path kept revertible.

3. **Spread gate in the point-in-time screen: APPROXIMATE it.** Kline archives carry no
   top-of-book spread. Model a proxy spread from data we do have (inverse of quote volume
   and/or intrabar range) and apply the live 0.05% ceiling to the proxy. Honest caveat in
   the code: it is a model of spread, not the real book. (Live screen still uses the real
   spread.)

4. **1h feature windows: BOTH families.** Keep the existing windows scaled x24 to preserve
   wall-clock lookback (a 14-day EMA stays ~14 days = 336h) AND add shorter intraday-native
   windows. Join flow_imbalance. The after-fee out-of-sample scoreboard decides which
   features earn their place. Recalibrate the ATR-band thresholds (currently 2.5-12% on
   daily ATR) to the 1h frame empirically.

   REVISED 2026-06-21 (Seamus): NO pandas-ta dependency. He did not agree to a pandas-ta
   block. The extra-indicator breadth (Williams %R, Stochastic, CCI, CMF, MFI, ADX/DMI,
   Aroon) is computed in-house in build_dataset_1h.py, all causal and scale-invariant.

   REVISED AGAIN 2026-06-21 (Seamus): pandas-ta IS wanted after all. The in-house indicators
   stay as the always-on baseline; pandas-ta is added back as an OPTIONAL breadth layer
   (f_ta_pta_*: PPO, TRIX, Vortex, CMO, Fisher, Chande Kroll Stop), used when importable. The
   system install had failed only because pip could not downgrade the MacPorts root-owned
   numpy; the fix is the operator-sanctioned project .venv, where pandas-ta 0.4.71b0 installs
   and computes cleanly (numpy 2.2.6, pandas 3.0.3). Run the 1h pipeline from .venv.

   ADDED 2026-06-21 (Seamus): TA-Lib (the C library via its prebuilt python wheel, talib
   0.6.8) is also installed in the .venv and wired as a THIRD optional layer (f_tl_*),
   curated to what it uniquely adds over pandas-ta/in-house: Parabolic SAR and MESA-MA
   distances, Ultimate Oscillator, Hilbert-transform cycle features, and a candlestick-pattern
   family. NOT all 158 functions -- most duplicate existing features, and the full 60-pattern
   set is mostly sparse noise. The feature set is now ~60 across five sources; breadth is
   candidate-only and the after-fee out-of-sample scoreboard, LightGBM regularization, and the
   score-once test are what prune. Watch for overfitting given the model shows no edge yet.

5. **1h label geometry: SHORTER DAY-TRADE HORIZON.** Horizon ~24-120 bars (1-5 days),
   smaller target/stop scaled to 1h ATR rather than the inherited +10/-5. Make (target,
   stop, horizon-in-bars) configurable and sweep in Priority 1b. Leans into the day-trader
   half of the mandate while keeping cost small relative to a still-meaningful target.

## Engineering approach (chosen, revertible)

- New module `inputs/build_dataset_1h.py`; leave the daily `build_dataset.py` untouched so
  the 1d path stays revertible.
- It reads the offline `klines_1h/` archives (reproducible, offline) and joins `flow_1h.csv`.
- Exposes FEATURES, HORIZON_BARS, DATASET_PATH for train_model to consume; train_model gets
  a minimal time-column-aware tweak (datetime vs date) without breaking the 1d path.
- The full build over all 433 coins runs on the Mac (alongside the download); the sandbox
  builds and validates the pipeline on a small multi-coin dev slice.

## Standing constraints (unchanged)

No live trading; LIVE_TRADING off; spot only; never short/options/margin/futures/leveraged;
never average down. Measure on the out-of-sample, after-fee scoreboard; keep only what beats
buy-and-hold and a coin-flip. Plain ASCII. Do not touch config.py, requirements.txt, or
day-metrics.ipynb unless asked. Seamus owns CLAUDE.md.
