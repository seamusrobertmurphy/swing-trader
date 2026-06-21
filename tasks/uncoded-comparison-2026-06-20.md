# unCoded comparison and the live-execution / security checklist

Written 2026-06-20. Source: the README of the unCoded bot (ArrowTrade AG), a closed-source
commercial Binance Spot bot. The clone Seamus provided is README-only (the other folders are
CI config and screenshots), so this is a feature and methodology comparison, not a code source.

## Decisions taken from this comparison (2026-06-20)

- ADOPT now: import the `pandas-ta` indicator library to broaden the feature set (Keller's
  note says feature breadth is where the AUC gap likely sits). Add as new feature families in
  `build_dataset.py`, measured out-of-sample, keep only what improves the after-fee result.
- ADOPT into the exit-geometry sweep: per-split trailing stops (each buy split trails with its
  own percentage), and the time-decaying take-profit ("sell time curve"), as variants tested on
  the same after-fee scoreboard as the rest of the sweep.
- DATA: do not limit the coin set. Pull all ~433 USDT spot pairs (full market), point-in-time
  screened. Bar interval is being chosen from the data-options table (Seamus reviewing; he wants
  the hourly tier seriously considered, not defaulted to daily).
- DO NOT adopt: automatic DIP rebuying / DCA accumulation (it is averaging down, forbidden by
  the hard rules). Micro-trading / HFT is a separate large build, only if an intraday sleeve is
  pursued.

## Live-execution and security checklist (revisit later, after this session)

Seamus asked to store these for a later pass. None of this is needed until `LIVE_TRADING` is
armed; it is the hardening `inputs/trade_binance.py` needs before real money moves.

### Binance API key configuration (do on the Binance side)

- Enable Spot trading only.
- Disable withdrawals.
- Disable internal transfers.
- Enable an IP whitelist pointing at the machine that runs the bot.
- Enable 2FA on the Binance account.
- Keys already read from the macOS Keychain via `config.py`; this is about the permissions set
  on Binance's side, which the keychain does not control.

### Execution-engine hardening for inputs/trade_binance.py

- Stops trigger at the stop price, not at the candle close.
- Respect Binance minimum order size (the NOTIONAL filter); warn or skip sub-minimum orders.
  Matters for a small account split across 3-4 positions.
- Rate limiting: stay under Binance's ~50 orders per 10-second window.
- Idempotent order placement, so a retry cannot create a duplicate fill.
- Atomic state transitions to avoid race conditions (unCoded uses explicit statuses such as
  activating, tsl_triggering, stoploss_triggering).
- A reconcile loop that periodically compares bot state against the exchange and corrects drift.
- Per-symbol isolated state and fee/position accounting, so pairs cannot cross-contaminate.
- WebSocket price feed with automatic reconnect; failover and retry policy on API errors.

### Jurisdiction and infra

- Seamus's Binance is registered in Ireland (EU, MiCAR), so Binance.com access is fine. The
  earlier "Canada" note was a misread of a comment on the ALPACA line in `config.py` and does
  not apply to Binance.
- Proxy / VPN support (unCoded's `proxyConfig.js`) only matters if a future host sits in a
  restricted region; not needed for an Ireland-based operator on their own Mac.
- Optional: Telegram as the notification channel (we are dropping ClickUp), plus tax-ready
  transaction exports.

## Backtest-fidelity checks unCoded raises (for our research harness)

- Intracandle fills: unCoded builds higher timeframes from 1-second base candles so a stop hit
  by a wick or a take-profit touched mid-candle is caught. Our walkforward fills at the stop or
  target using the bar's high/low and conservatively assumes the stop hits first when both lie
  inside one bar. Finer bars reduce this ambiguity; document the assumption either way.
- Sharpe annualization: use the correct bars-per-year for the chosen interval; do not carry
  Keller's hourly sqrt(365*24) onto a daily frame. Check `eval_report`.
- Fee accounting: our flat 0.20% COST_PCT is a fine research approximation; unCoded converts the
  exact asset fees to quote at trade price, which only matters at live execution.

## Where unCoded independently confirms our direction

- "Multi-Chart Testing" against every spot pair and the "Chart Shuffling" article (test against
  100 charts, not one) are the wide / point-in-time training move we chose.
- "The 97% Rule: most Binance tokens are dying" is the survivorship point, and it argues asset
  selection matters more than strategy, which supports investing in the screen.
- "Why Your Backtest Lied to You" matches our honest after-fee scoreboard discipline.
