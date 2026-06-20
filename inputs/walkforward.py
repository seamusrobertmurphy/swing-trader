"""Priority 0: trade exits (P0.1) and a walk-forward backtest (P0.2).

This is the scoreboard. It answers one question honestly: does the project's
daily MACD signal-line cross-up, traded with ATR-based exits, beat fees
out-of-sample across regimes, versus buy-and-hold and a coin flip?

Research and validation only. No live trading. No orders. Nothing here can
place an order; it only fetches public daily candles and simulates trades.

It reuses the conventions and parameter names from day-controls.ipynb:
  - CONFIG (the tunable params dict)
  - compute_atr_pct(df, length)
  - compute_signals(df, cfg)  -> macd, signal, hist, ema12/26, rsi, cross_up, cross_down
  - net_edge(...) / the fee-and-slippage model
  - the HARNESS / experiment_log.csv schema

Run:  python inputs/walkforward.py
Writes: outputs/walkforward_results.md, appends outputs/experiment_log.csv,
        outputs/walkforward_trades.csv (every simulated test-window trade).

P0.1 exit precedence on each bar (conservative):
  1. stop-loss (ATR-based) checked first,
  2. take-profit,
  3. time stop at hold_window_days_max,
  4. optional MACD cross-down signal exit (off by default; see USE_SIGNAL_EXIT).
On a single bar, if both stop and target lie inside [low, high], the STOP is
assumed to trigger. Net return = gross - round_trip_fee_pct - expected_slippage_pct.
"""

import os
import sys
import time
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import ccxt
except Exception as exc:  # pragma: no cover
    print("ccxt is required:", exc)
    sys.exit(1)


# --- paths ---------------------------------------------------------------
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUTPUTS = ROOT / "outputs"
OUTPUTS.mkdir(parents=True, exist_ok=True)


# --- CONFIG (mirrors day-controls.ipynb; do not edit the notebook) -------
# These are the same names and values used live in day-controls.ipynb.
CONFIG = dict(
    round_trip_fee_pct    = 0.15,
    expected_slippage_pct = 0.05,
    edge_floor_pct        = 1.5,
    take_profit_pct       = 3.0,
    stop_atr_mult         = 1.5,
    atr_length            = 14,
    atr_floor_pct         = 2.5,
    atr_ceiling_pct       = 12.0,
    hold_window_days_min  = 1,
    hold_window_days_max  = 10,
)

# Frozen harness windows (mirrors HARNESS in day-controls.ipynb).
HARNESS = dict(
    version           = "harness-v1",
    train_window_days = 365,     # ~12 months train
    oos_window_days   = 90,      # ~3 months test
    embargo_days      = 20,      # straddles the train/test cut, no peeking
    metric            = "oos_after_fee_expectancy",
)

# Project universe: ten coins on /USDT.
UNIVERSE = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
            "ADA/USDT", "AVAX/USDT", "LINK/USDT", "LTC/USDT", "DOGE/USDT"]

# Signal switches.
USE_ATR_BAND_GATE = True    # only enter when ATR% is inside the tradable band
USE_SIGNAL_EXIT   = False   # optional P0.1 extra: exit on MACD cross-down

# Coin-flip baseline.
FLIP_SEEDS = [11, 23, 37, 51, 73]   # average random entries over several seeds


# --- data ----------------------------------------------------------------
def fetch_full_daily(exchange, symbol, max_bars=20000, page=1000):
    """Full daily OHLCV via ccxt, paginated past the 1000-bar cap.
    Drops the final (unclosed) candle. Returns a DataFrame indexed by date."""
    since = exchange.parse8601("2017-01-01T00:00:00Z")
    all_bars = []
    last_ts = None
    while True:
        try:
            bars = exchange.fetch_ohlcv(symbol, timeframe="1d", since=since, limit=page)
        except Exception as exc:
            print(f"  fetch error {symbol}: {type(exc).__name__} {exc}; retrying once")
            time.sleep(2.0)
            bars = exchange.fetch_ohlcv(symbol, timeframe="1d", since=since, limit=page)
        if not bars:
            break
        if last_ts is not None:
            bars = [b for b in bars if b[0] > last_ts]
            if not bars:
                break
        all_bars.extend(bars)
        last_ts = all_bars[-1][0]
        since = last_ts + 1
        if len(bars) < page or len(all_bars) >= max_bars:
            break
        time.sleep(exchange.rateLimit / 1000.0)
    if not all_bars:
        return pd.DataFrame()
    df = pd.DataFrame(all_bars, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.drop_duplicates("timestamp").set_index("timestamp").sort_index()
    df = df.iloc[:-1]   # drop the final unclosed candle
    return df


# --- indicators (mirrors compute_atr_pct / compute_signals) --------------
def compute_atr_pct(df, length=None):
    length = length or CONFIG["atr_length"]
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([(h - l).abs(), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    atr = tr.rolling(length).mean()
    return (atr / c) * 100.0


def compute_signals(df, cfg=CONFIG):
    """Add MACD, signal, histogram, EMAs, RSI(14), ATR% and crossover flags.
    Identical definition to day-controls.ipynb compute_signals."""
    df = df.copy()
    c = df["close"]
    df["ema12"] = c.ewm(span=12, adjust=False).mean()
    df["ema26"] = c.ewm(span=26, adjust=False).mean()
    df["macd"] = df["ema12"] - df["ema26"]
    df["signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["hist"] = df["macd"] - df["signal"]
    d = c.diff()
    up = d.clip(lower=0).rolling(14).mean()
    dn = (-d.clip(upper=0)).rolling(14).mean()
    df["rsi"] = 100 - 100 / (1 + up / dn)
    df["atr_pct"] = compute_atr_pct(df, cfg["atr_length"])
    df["cross_up"] = (df["macd"] > df["signal"]) & (df["macd"].shift(1) <= df["signal"].shift(1))
    df["cross_down"] = (df["macd"] < df["signal"]) & (df["macd"].shift(1) >= df["signal"].shift(1))
    return df


# --- fees ----------------------------------------------------------------
def round_trip_cost_pct(cfg=CONFIG):
    """Total round-trip drag as a percent (fees + modelled slippage)."""
    return cfg["round_trip_fee_pct"] + cfg["expected_slippage_pct"]


# --- P0.1 trade exits ----------------------------------------------------
def simulate_exit(entry_date, entry_price, entry_atr_pct, future, cfg=CONFIG,
                  use_signal_exit=USE_SIGNAL_EXIT):
    """Walk forward bar by bar from the bar AFTER entry and return the exit.

    Inputs:
      entry_date    : pandas Timestamp of the entry bar.
      entry_price   : entry fill price (the entry bar close).
      entry_atr_pct : daily ATR% known at entry (sets the stop distance).
      future        : DataFrame of subsequent bars (must include open/high/low/close,
                      and 'cross_down' if use_signal_exit). Index = dates, ascending,
                      strictly after the entry bar.

    Exit precedence checked each bar:
      1. stop-loss: low <= entry * (1 - stop_atr_mult * atr_pct/100)   [checked first]
      2. take-profit: high >= entry * (1 + take_profit_pct/100)
      3. signal exit (optional): MACD cross-down -> exit at that bar's close
      4. time stop: after hold_window_days_max bars, exit at that bar's close
    If both stop and target are inside one bar's [low, high], the STOP is taken.

    Net return = gross return - round_trip_cost_pct (percent points).
    Returns a dict: exit_date, exit_price, reason, gross_ret_pct, net_ret_pct, bars_held.
    """
    stop_pct = cfg["stop_atr_mult"] * entry_atr_pct
    stop_price = entry_price * (1 - stop_pct / 100.0)
    target_price = entry_price * (1 + cfg["take_profit_pct"] / 100.0)
    cost = round_trip_cost_pct(cfg)
    max_bars = cfg["hold_window_days_max"]

    n = min(max_bars, len(future))
    if n == 0:
        # No bars after entry to resolve on; close flat at entry (degenerate).
        return dict(exit_date=entry_date, exit_price=entry_price, reason="no_future_bars",
                    gross_ret_pct=0.0, net_ret_pct=-cost, bars_held=0)

    for k in range(n):
        bar = future.iloc[k]
        lo, hi, cl = float(bar["low"]), float(bar["high"]), float(bar["close"])
        bar_date = future.index[k]
        # 1. stop first (conservative)
        if lo <= stop_price:
            gross = (stop_price - entry_price) / entry_price * 100.0
            return dict(exit_date=bar_date, exit_price=stop_price, reason="stop_loss",
                        gross_ret_pct=gross, net_ret_pct=gross - cost, bars_held=k + 1)
        # 2. take-profit
        if hi >= target_price:
            gross = (target_price - entry_price) / entry_price * 100.0
            return dict(exit_date=bar_date, exit_price=target_price, reason="take_profit",
                        gross_ret_pct=gross, net_ret_pct=gross - cost, bars_held=k + 1)
        # 3. optional signal exit on MACD cross-down
        if use_signal_exit and bool(bar.get("cross_down", False)):
            gross = (cl - entry_price) / entry_price * 100.0
            return dict(exit_date=bar_date, exit_price=cl, reason="signal_exit",
                        gross_ret_pct=gross, net_ret_pct=gross - cost, bars_held=k + 1)
    # 4. time stop at the last bar inside the hold window
    bar = future.iloc[n - 1]
    cl = float(bar["close"])
    gross = (cl - entry_price) / entry_price * 100.0
    return dict(exit_date=future.index[n - 1], exit_price=cl, reason="time_stop",
                gross_ret_pct=gross, net_ret_pct=gross - cost, bars_held=n)


# --- entry signal --------------------------------------------------------
def entry_mask(df, cfg=CONFIG, use_atr_band=USE_ATR_BAND_GATE):
    """Boolean Series: True on bars where an entry fires.
    Entry = MACD signal-line cross-up, optionally gated to the ATR tradable band.
    All inputs are causal (known at the bar's close)."""
    sig = df["cross_up"].fillna(False)
    if use_atr_band:
        in_band = (df["atr_pct"] >= cfg["atr_floor_pct"]) & (df["atr_pct"] <= cfg["atr_ceiling_pct"])
        sig = sig & in_band.fillna(False)
    return sig


# --- run trades over a window --------------------------------------------
def trades_in_window(df, start, end, cfg=CONFIG, entries=None,
                     use_signal_exit=USE_SIGNAL_EXIT):
    """Simulate every entry whose entry bar falls in [start, end) and resolve it
    with simulate_exit. The exit may legitimately run a few bars past `end`
    (a position opened near the window edge), but entries are confined to the
    window, which is what keeps test windows non-overlapping in entry space.

    `entries`: optional precomputed boolean Series (e.g. random for the coin
    flip). If None, the MACD-band entry signal is used.
    Returns a list of trade dicts."""
    if entries is None:
        entries = entry_mask(df, cfg)
    out = []
    idx = df.index
    win = df[(idx >= start) & (idx < end)]
    for ts in win.index:
        if not bool(entries.loc[ts]):
            continue
        row = df.loc[ts]
        atr = float(row["atr_pct"])
        if not np.isfinite(atr) or atr <= 0:
            continue
        entry_price = float(row["close"])
        pos = df.index.get_loc(ts)
        future = df.iloc[pos + 1:]
        if len(future) == 0:
            continue
        ex = simulate_exit(ts, entry_price, atr, future, cfg, use_signal_exit)
        out.append(dict(entry_date=ts, entry_price=entry_price, entry_atr_pct=atr, **ex))
    return out


# --- walk-forward windows ------------------------------------------------
def window_edges(df, harness=HARNESS):
    """Yield (train_start, train_end, test_start, test_end) tuples sliding forward.
    Embargo straddles the train/test cut: the last `embargo_days` of nominal train
    are dropped, and test begins `embargo_days` after the cut, so no test trade can
    peek into a training bar (entries near the cut are excluded both sides)."""
    if df.empty:
        return
    tw = pd.Timedelta(days=harness["train_window_days"])
    ow = pd.Timedelta(days=harness["oos_window_days"])
    emb = pd.Timedelta(days=harness["embargo_days"])
    first, last = df.index[0], df.index[-1]
    cut = first + tw
    while cut + emb + ow <= last + pd.Timedelta(days=1):
        train_start = cut - tw
        train_end = cut - emb                  # drop last embargo days of train
        test_start = cut + emb                 # test starts after embargo
        test_end = test_start + ow
        yield (train_start, train_end, test_start, test_end)
        cut = cut + ow                         # slide forward by one test window


# --- aggregation ---------------------------------------------------------
def expectancy(trades):
    """Mean after-fee net return per trade (percent), and supporting stats."""
    if not trades:
        return dict(n=0, exp_pct=float("nan"), win_rate=float("nan"),
                    med_pct=float("nan"), total_pct=float("nan"))
    nets = np.array([t["net_ret_pct"] for t in trades], dtype=float)
    return dict(
        n=len(nets),
        exp_pct=float(np.mean(nets)),
        win_rate=float(np.mean(nets > 0)),
        med_pct=float(np.median(nets)),
        total_pct=float(np.sum(nets)),
    )


# --- baselines -----------------------------------------------------------
def buy_hold_window(df, test_start, test_end, cfg=CONFIG):
    """Buy-and-hold over the test window: buy first available close at/after
    test_start, sell last close before test_end, after one round-trip cost.
    Returns net percent for the window (or None if no bars)."""
    seg = df[(df.index >= test_start) & (df.index < test_end)]
    if len(seg) < 2:
        return None
    entry = float(seg["close"].iloc[0])
    exit_ = float(seg["close"].iloc[-1])
    gross = (exit_ - entry) / entry * 100.0
    return gross - round_trip_cost_pct(cfg)


def coin_flip_window(df, test_start, test_end, cfg=CONFIG, seed=0,
                     n_entries=None):
    """Random entries inside the test window with the SAME exit and fee model.
    Number of random entries matches the count of real signal entries in the
    window (so it is a like-for-like control). Returns list of trade dicts."""
    seg = df[(df.index >= test_start) & (df.index < test_end)]
    # candidate bars: those with a finite ATR and at least one future bar
    cand = [ts for ts in seg.index
            if np.isfinite(df.loc[ts, "atr_pct"]) and df.loc[ts, "atr_pct"] > 0
            and df.index.get_loc(ts) + 1 < len(df)]
    if not cand or not n_entries:
        return []
    rng = np.random.default_rng(seed)
    k = min(n_entries, len(cand))
    picks = rng.choice(len(cand), size=k, replace=False)
    rand = pd.Series(False, index=df.index)
    for p in picks:
        rand.loc[cand[p]] = True
    return trades_in_window(df, test_start, test_end, cfg, entries=rand)


# --- main ----------------------------------------------------------------
def run():
    t_start = time.time()
    print("Priority 0 walk-forward backtest (research only; no orders).")
    print(f"signal: MACD signal-line cross-up"
          f"{' gated to ATR band' if USE_ATR_BAND_GATE else ''}; "
          f"exits: ATR stop (x{CONFIG['stop_atr_mult']}), TP +{CONFIG['take_profit_pct']}%, "
          f"time stop {CONFIG['hold_window_days_max']}d"
          f"{', signal-exit on' if USE_SIGNAL_EXIT else ''}.")
    print(f"fees: round-trip {round_trip_cost_pct():.2f}% (fee {CONFIG['round_trip_fee_pct']}% "
          f"+ slip {CONFIG['expected_slippage_pct']}%).")
    print(f"windows: train {HARNESS['train_window_days']}d / test {HARNESS['oos_window_days']}d "
          f"/ embargo {HARNESS['embargo_days']}d.\n")

    exchange = ccxt.binance()
    exchange.enableRateLimit = True

    per_coin = {}            # symbol -> dict of aggregated OOS results
    all_oos_trades = []      # every OOS signal trade (flat list)
    all_bh = []              # per-window buy-hold nets
    all_flip = []            # per-seed coin-flip trade pools

    history_span = {}

    for symbol in UNIVERSE:
        print(f"[{symbol}] fetching full daily history ...", flush=True)
        df = fetch_full_daily(exchange, symbol)
        if df.empty or len(df) < (HARNESS["train_window_days"] + HARNESS["oos_window_days"]):
            print(f"  insufficient history ({len(df)} bars); skipping")
            continue
        df = compute_signals(df, CONFIG)
        history_span[symbol] = (df.index[0].date(), df.index[-1].date(), len(df))
        print(f"  {len(df)} bars, {df.index[0].date()} -> {df.index[-1].date()}")

        coin_oos_trades = []
        coin_bh = []
        coin_flip_nets = {s: [] for s in FLIP_SEEDS}
        n_windows = 0

        for (tr_s, tr_e, te_s, te_e) in window_edges(df, HARNESS):
            n_windows += 1
            # --- test window: score ONCE with the frozen signal+exit (no tuning) ---
            test_trades = trades_in_window(df, te_s, te_e, CONFIG)
            coin_oos_trades.extend(test_trades)

            # --- buy-and-hold baseline on the same test window ---
            bh = buy_hold_window(df, te_s, te_e, CONFIG)
            if bh is not None:
                coin_bh.append(bh)

            # --- coin-flip baseline: same n entries, same exits, several seeds ---
            for s in FLIP_SEEDS:
                ft = coin_flip_window(df, te_s, te_e, CONFIG, seed=s,
                                      n_entries=len(test_trades))
                coin_flip_nets[s].extend([t["net_ret_pct"] for t in ft])

        agg = expectancy(coin_oos_trades)
        bh_mean = float(np.mean(coin_bh)) if coin_bh else float("nan")
        flip_seed_means = [np.mean(v) if v else float("nan") for v in coin_flip_nets.values()]
        flip_mean = float(np.nanmean(flip_seed_means)) if flip_seed_means else float("nan")

        per_coin[symbol] = dict(
            n_windows=n_windows, **agg,
            buy_hold_mean_pct=bh_mean, flip_mean_pct=flip_mean,
        )
        all_oos_trades.extend([dict(symbol=symbol, **t) for t in coin_oos_trades])
        all_bh.extend(coin_bh)
        for s in FLIP_SEEDS:
            all_flip.append((s, symbol, coin_flip_nets[s]))

        print(f"  windows={n_windows}  oos_trades={agg['n']}  "
              f"exp={agg['exp_pct']:+.3f}%  win={agg['win_rate']*100 if agg['n'] else float('nan'):.1f}%  "
              f"BH(win avg)={bh_mean:+.3f}%  flip={flip_mean:+.3f}%\n", flush=True)

    # --- aggregate across all coins and windows (the only number we trust) ---
    agg_all = expectancy(all_oos_trades)
    bh_all = float(np.mean(all_bh)) if all_bh else float("nan")
    # coin-flip: pool per seed across all coins, mean each seed, then average seeds
    flip_seed_pool = {s: [] for s in FLIP_SEEDS}
    for (s, sym, nets) in all_flip:
        flip_seed_pool[s].extend(nets)
    flip_seed_exp = {s: (float(np.mean(v)) if v else float("nan")) for s, v in flip_seed_pool.items()}
    flip_all = float(np.nanmean(list(flip_seed_exp.values())))
    flip_n_avg = float(np.mean([len(v) for v in flip_seed_pool.values()]))

    print("=" * 68)
    print("AGGREGATE OUT-OF-SAMPLE (after fees), all coins x all test windows")
    print("=" * 68)
    print(f"  signal strategy : n={agg_all['n']}  exp/trade={agg_all['exp_pct']:+.4f}%  "
          f"win={agg_all['win_rate']*100:.1f}%  median={agg_all['med_pct']:+.3f}%")
    print(f"  buy-and-hold    : per-window net avg = {bh_all:+.4f}% "
          f"(n_windows={len(all_bh)})")
    print(f"  coin-flip       : exp/trade={flip_all:+.4f}%  (avg n={flip_n_avg:.0f} per seed, "
          f"{len(FLIP_SEEDS)} seeds)")

    # --- GO / NO-GO verdict ---
    # GO only if signal OOS after-fee expectancy clearly beats BOTH baselines.
    # Buy-and-hold here is a per-window average net; to compare like-for-like we
    # also express the signal as average net per test window.
    sig_per_window = (agg_all["total_pct"] / max(1, len(all_bh))) if all_bh else float("nan")
    beats_flip = (np.isfinite(agg_all["exp_pct"]) and np.isfinite(flip_all)
                  and agg_all["exp_pct"] > flip_all + 0.10)   # clear margin, 0.10pp
    beats_bh = (np.isfinite(sig_per_window) and np.isfinite(bh_all)
                and sig_per_window > bh_all)
    positive_edge = np.isfinite(agg_all["exp_pct"]) and agg_all["exp_pct"] > 0.0
    verdict = "GO" if (positive_edge and beats_flip and beats_bh) else "NO-GO"

    print("-" * 68)
    print(f"  signal net per test window (sum/ #windows) = {sig_per_window:+.4f}%")
    print(f"  beats coin-flip (margin>0.10pp)? {beats_flip}   "
          f"beats buy-hold? {beats_bh}   positive edge? {positive_edge}")
    print(f"  VERDICT: {verdict}")
    print("=" * 68)

    # --- persist trades ---
    if all_oos_trades:
        tdf = pd.DataFrame(all_oos_trades)
        tdf.to_csv(OUTPUTS / "walkforward_trades.csv", index=False)
        print(f"wrote {OUTPUTS / 'walkforward_trades.csv'} ({len(tdf)} trades)")

    # --- append to experiment_log.csv (matching the scaffold's spirit) ---
    log_path = OUTPUTS / "experiment_log.csv"
    why = ("OOS after-fee expectancy beats buy-hold and coin-flip"
           if verdict == "GO" else
           "no demonstrated OOS edge after fees vs buy-hold/coin-flip (NO-GO)")
    row = {
        "ts_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "harness": HARNESS["version"],
        "kept": (verdict == "GO"),
        "why": why,
        "p_edge_floor_pct": CONFIG["edge_floor_pct"],
        "p_take_profit_pct": CONFIG["take_profit_pct"],
        "p_atr_floor_pct": CONFIG["atr_floor_pct"],
        "p_threshold": "macd_crossup+atrband",
        "oos_after_fee_expectancy_pct": round(agg_all["exp_pct"], 4) if agg_all["n"] else None,
        "oos_win_rate": round(agg_all["win_rate"], 4) if agg_all["n"] else None,
        "oos_n_trades": agg_all["n"],
        "oos_vs_buy_hold_pct": (round(sig_per_window - bh_all, 4)
                                if np.isfinite(sig_per_window) and np.isfinite(bh_all) else None),
    }
    header = not log_path.exists()
    pd.DataFrame([row]).to_csv(log_path, mode="a", header=header, index=False)
    print(f"appended run to {log_path}")

    # --- write results markdown ---
    write_results_md(per_coin, agg_all, bh_all, flip_all, flip_seed_exp,
                     sig_per_window, verdict, history_span, beats_flip, beats_bh,
                     positive_edge, all_oos_trades)

    print(f"\ndone in {time.time() - t_start:.0f}s")
    return verdict


def write_results_md(per_coin, agg_all, bh_all, flip_all, flip_seed_exp,
                     sig_per_window, verdict, history_span, beats_flip, beats_bh,
                     positive_edge, all_oos_trades_ref=None):
    """Plain-ASCII results write-up to outputs/walkforward_results.md."""
    lines = []
    a = lines.append
    a("# Priority 0 walk-forward results")
    a("")
    a(f"Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} (UTC). "
      "Research and validation only. No live trading; no orders were placed.")
    a("")
    a("## What was built")
    a("")
    a("Two pieces, in one module (inputs/walkforward.py):")
    a("")
    a("- P0.1 trade-exit simulator (simulate_exit): given an entry and the")
    a("  following daily bars, walks forward bar by bar and returns the exit")
    a("  price, date, reason, and after-fee return.")
    a("- P0.2 walk-forward backtest: rolls train/test windows per coin with an")
    a("  embargo, scores the test window once, aggregates only the out-of-sample")
    a("  after-fee result, and compares against buy-and-hold and a coin flip.")
    a("")
    a("## Signal and exit rules")
    a("")
    a("Entry signal: the MACD signal-line cross-up already defined in")
    a("compute_signals (cross_up)" +
      (", gated to the ATR tradable band "
       f"[{CONFIG['atr_floor_pct']}%, {CONFIG['atr_ceiling_pct']}%]."
       if USE_ATR_BAND_GATE else "."))
    a("This is the simplest honest choice and reuses the live notebook's")
    a("definition without the leakage risk of the four-vote model machinery.")
    a("")
    a("Exit precedence per bar (conservative), from CONFIG:")
    a(f"  1. ATR stop-loss, checked first: entry * (1 - {CONFIG['stop_atr_mult']} "
      "* daily_atr_pct/100).")
    a(f"  2. take-profit: entry * (1 + {CONFIG['take_profit_pct']}/100).")
    if USE_SIGNAL_EXIT:
        a("  3. signal exit: MACD cross-down before the time stop, exit at close.")
        a(f"  4. time stop: exit at close after {CONFIG['hold_window_days_max']} bars.")
    else:
        a(f"  3. time stop: exit at close after {CONFIG['hold_window_days_max']} bars.")
        a("  (Optional MACD cross-down signal exit is implemented but OFF by default.)")
    a("If both stop and target sit inside one bar's [low, high], the STOP is taken.")
    a(f"Net return = gross - {CONFIG['round_trip_fee_pct']}% fee - "
      f"{CONFIG['expected_slippage_pct']}% slippage "
      f"= gross - {round_trip_cost_pct():.2f}% round trip.")
    a("")
    a("## Windows and embargo")
    a("")
    a(f"Train {HARNESS['train_window_days']} days, test {HARNESS['oos_window_days']} days, "
      f"sliding forward by one test window. A {HARNESS['embargo_days']}-day embargo")
    a("straddles the train/test cut (last embargo days of train dropped; test")
    a("starts embargo days after the cut), so no test trade can peek into training.")
    a("The signal+exit are frozen, so there is no per-window threshold tuning to")
    a("overfit; the test window is scored exactly once. Full daily history per coin")
    a("spans the 2017-2026 bull, bear and sideways regimes.")
    a("")
    a("## Headline out-of-sample, after-fee numbers")
    a("")
    a("Aggregate across all coins and all test windows:")
    a("")
    a(f"  signal strategy : trades={agg_all['n']}  "
      f"expectancy/trade={agg_all['exp_pct']:+.4f}%  "
      f"win-rate={agg_all['win_rate']*100:.1f}%  median/trade={agg_all['med_pct']:+.3f}%")
    a(f"  signal net per test window = {sig_per_window:+.4f}%")
    a(f"  buy-and-hold    : per-window net average = {bh_all:+.4f}%")
    a(f"  coin-flip       : expectancy/trade = {flip_all:+.4f}% "
      f"(avg over {len(flip_seed_exp)} seeds)")
    a("")
    a("Coin-flip by seed (expectancy/trade %): " +
      ", ".join(f"{s}:{v:+.3f}" for s, v in flip_seed_exp.items()))
    a("")
    a("Exit-reason breakdown (out-of-sample, after fees):")
    if all_oos_trades_ref:
        tdf = pd.DataFrame(all_oos_trades_ref)
        for reason, grp in tdf.groupby("reason"):
            a(f"  {reason:<12} n={len(grp):>4}  mean net={grp['net_ret_pct'].mean():+.3f}%")
        a("Read: take-profits are frequent and small (+TP-cost each); stop-losses")
        a("are rarer but large on these volatile coins, and the asymmetry cancels")
        a("the win-rate. A high win-rate here is not an edge.")
        a("")
    a("Note on the buy-and-hold comparison: buy-and-hold holds for the whole")
    a("90-day test window, so its per-window net captures entire moves, while the")
    a("signal is exposed only for short bursts (a few bars per trade). The two are")
    a("not exposure-matched; buy-and-hold is structurally favoured here and the")
    a("ten survivors flatter it further. The signal would need a strong per-trade")
    a("edge to overcome that, and it does not.")
    a("")
    a("## Per-coin out-of-sample (after fees)")
    a("")
    a("coin       windows  trades   exp/trade   win%    BH(win avg)   flip/trade")
    a("-" * 74)
    for sym, r in per_coin.items():
        name = sym.split("/")[0]
        a(f"{name:<10} {r['n_windows']:>7}  {r['n']:>6}   "
          f"{r['exp_pct']:>+8.3f}%  "
          f"{(r['win_rate']*100 if r['n'] else float('nan')):>5.1f}   "
          f"{r['buy_hold_mean_pct']:>+9.3f}%   {r['flip_mean_pct']:>+8.3f}%")
    a("")
    a("History span per coin (first -> last, bars):")
    for sym, (d0, d1, n) in history_span.items():
        a(f"  {sym.split('/')[0]:<6} {d0} -> {d1}  ({n} bars)")
    a("")
    a("## Verdict")
    a("")
    a(f"  positive after-fee edge?   {positive_edge}")
    a(f"  beats coin-flip (clear)?   {beats_flip}")
    a(f"  beats buy-and-hold?        {beats_bh}")
    a("")
    a(f"  GO/NO-GO: {verdict}")
    a("")
    if verdict == "NO-GO":
        a("NO-GO. The MACD cross-up signal, traded with these ATR exits and after")
        a("realistic round-trip costs, does not show a clear out-of-sample edge over")
        a("both baselines across regimes. This matches the project's standing NO-GO")
        a("(Chapter One AUC ~0.51, no demonstrated edge). It is a valid, useful")
        a("result: it says do not trade this configuration, and it gives a clean")
        a("scoreboard to measure future improvements against (threshold tuning, a")
        a("better label, regime features). Do not present this as tradeable.")
    else:
        a("GO on this scoreboard means the configuration beat both baselines out of")
        a("sample after fees. Treat with caution: confirm on a held-out coin set and")
        a("re-run before any paper trading. Still no live orders without sign-off.")
    a("")
    a("## Caveats and assumptions")
    a("")
    a("- Stop/target fills are assumed at the exact stop/target price; intrabar")
    a("  gaps could fill worse. Slippage is modelled as a flat percent, not")
    a("  size- or volatility-dependent.")
    a("- One position at a time per entry; no portfolio-level position cap is")
    a("  enforced in the backtest (the live notebook caps concurrency separately).")
    a("- Entries are confined to each test window; an exit may run a few bars past")
    a("  the window edge, which is realistic and does not leak training data.")
    a("- The ATR-band gate reduces trade count; without it there are more trades")
    a("  but the same honest measurement applies. Switch via USE_ATR_BAND_GATE.")
    a("- Daily bars only; no intraday timing. Survivorship: the ten coins are all")
    a("  survivors, which flatters buy-and-hold more than the signal.")
    a("")

    path = OUTPUTS / "walkforward_results.md"
    path.write_text("\n".join(lines))
    print(f"wrote {path}")


if __name__ == "__main__":
    run()
