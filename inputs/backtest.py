"""Breakout-continuation backtest (tier 1).

Hypothesis: after a daily close breaks above a prior swing-high resistance,
price continues. Success = price gains +TARGET before falling STOP below the
broken level, within HORIZON trading days. We measure the hit-rate on history,
split train/test, and break it down by crossover and volume confirmation.
"""
import ccxt, warnings, pandas as pd
warnings.filterwarnings("ignore")

# ---- rules (the success definition you greenlit) ----
PIVOT_K   = 5      # swing-high = local max over +/- this many bars
TARGET    = 0.10   # +10% gain from the breakout close
STOP      = 0.05   # -5% below the broken resistance level
HORIZON   = 20     # trading days to resolve
VOL_LEN   = 20     # volume average window
EMA_FAST, EMA_SLOW = 14, 91

ex = ccxt.binance()
STABLES = {"USDC","FDUSD","USD1","TUSD","DAI","USDP","BUSD"}

def history(symbol, limit=1000):
    bars = ex.fetch_ohlcv(symbol, "1d", limit=limit)
    df = pd.DataFrame(bars[:-1], columns=["t","open","high","low","close","volume"])
    df["t"] = pd.to_datetime(df["t"], unit="ms")
    df["ema_f"] = df["close"].ewm(span=EMA_FAST, adjust=False).mean()
    df["ema_s"] = df["close"].ewm(span=EMA_SLOW, adjust=False).mean()
    df["vol_avg"] = df["volume"].rolling(VOL_LEN).mean()
    return df

def swing_high_levels(df, k):
    """Return list of (confirm_index, level). A bar i is a swing high if its high
    is the max over [i-k, i+k]; it is only *known* k bars later (no lookahead)."""
    h = df["high"].values; n = len(h); out = []
    for i in range(k, n-k):
        if h[i] == max(h[i-k:i+k+1]):
            out.append((i+k, h[i]))   # usable only from bar i+k onward
    return out

def backtest_symbol(symbol):
    df = history(symbol)
    if len(df) < 120: return []
    pivots = swing_high_levels(df, PIVOT_K)
    close = df["close"].values; high = df["high"].values; low = df["low"].values
    events = []; pj = 0; active = None  # active resistance level confirmed so far
    for t in range(1, len(df)):
        while pj < len(pivots) and pivots[pj][0] <= t:
            active = pivots[pj][1]; pj += 1
        if active is None: continue
        # breakout = close crosses above the most recent confirmed resistance
        if close[t] > active and close[t-1] <= active:
            entry = close[t]; level = active
            target = entry*(1+TARGET); stop = level*(1-STOP)
            outcome = "timeout"; ret = None; last = t
            for f in range(t+1, min(t+1+HORIZON, len(df))):
                last = f
                if low[f] <= stop:  outcome="loss"; ret=(stop-entry)/entry; break
                if high[f] >= target: outcome="win"; ret=(target-entry)/entry; break
            if ret is None:  # timeout: mark at last bar in horizon
                ret = (close[last]-entry)/entry
            events.append(dict(
                symbol=symbol, date=df["t"].iloc[t], level=level, entry=entry,
                outcome=outcome, ret=ret,
                crossover=bool(df["ema_f"].iloc[t] > df["ema_s"].iloc[t]),
                volume=bool(df["volume"].iloc[t] > (df["vol_avg"].iloc[t] or 0)),
            ))
            active = None  # wait for a new swing high to form before next breakout
    return events

# universe: liquid, non-stablecoin USDT spot pairs
tk = ex.fetch_tickers()
pairs = [(s, d.get("quoteVolume") or 0) for s,d in tk.items()
         if s.endswith("/USDT") and ":" not in s and s.split("/")[0] not in STABLES]
universe = [s for s,_ in sorted(pairs, key=lambda x:-x[1])[:20]]
print("universe:", len(universe), "pairs")

all_events = []
for s in universe:
    try: all_events += backtest_symbol(s)
    except Exception as e: print("skip", s, type(e).__name__)
ev = pd.DataFrame(all_events)
print("total breakout events:", len(ev))

def hit(df):
    res = df[df.outcome.isin(["win","loss"])]
    n = len(res); w = (res.outcome=="win").sum()
    alln = len(df); wt = (df.outcome=="win").sum()
    return n, (w/n if n else float("nan")), (wt/alln if alln else float("nan"))

def report(df, label):
    n, hr_res, hr_all = hit(df)
    avg = df["ret"].mean()*100 if len(df) else float("nan")
    print(f"  {label:26s} events={len(df):4d}  win%(resolved)={hr_res*100:5.1f}  "
          f"win%(all)={hr_all*100:5.1f}  avg_return/trade={avg:+5.2f}%")

print("\n=== OVERALL ===")
report(ev, "all breakouts")
report(ev[ev.crossover], "+ crossover (EMA14>EMA91)")
report(ev[ev.volume], "+ volume > 20d avg")
report(ev[ev.crossover & ev.volume], "+ crossover & volume")

# train/test split by date (older 70% vs newer 30%)
ev = ev.sort_values("date")
cut = ev["date"].quantile(0.70)
train, test = ev[ev.date<=cut], ev[ev.date>cut]
print(f"\n=== OUT-OF-SAMPLE (split {cut.date()}) — filter: crossover & volume ===")
report(train[train.crossover & train.volume], "train")
report(test[test.crossover & test.volume],  "test")

ev.to_csv("breakout_events.csv", index=False)
print("\nsaved breakout_events.csv")
