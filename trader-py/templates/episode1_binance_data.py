"""Episode 1 — Binance data pipeline, applied from the CCXT blog.
Four steps: connect, pull, clean, indicators. Each step is small and readable.
"""
import ccxt, pandas as pd, numpy as np, time

PAIR, TIMEFRAME, MONTHS = "BTC/USDT", "1h", 6

# 1. Connect. Swap exchanges by changing this one line: ccxt.binance() -> ccxt.kraken().
ex = ccxt.binance()

# 2. Pull ~6 months of hourly candles, paginating 1000 at a time.
since = ex.parse8601((pd.Timestamp.utcnow() - pd.DateOffset(months=MONTHS)).strftime("%Y-%m-%dT%H:%M:%SZ"))
rows, ms_hour = [], 3600_000
while True:
    batch = ex.fetch_ohlcv(PAIR, TIMEFRAME, since=since, limit=1000)
    if not batch:
        break
    rows += batch
    since = batch[-1][0] + ms_hour
    if len(batch) < 1000:
        break
    time.sleep(ex.rateLimit / 1000)

df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"])
df["time"] = pd.to_datetime(df["time"], unit="ms")
df = df.drop_duplicates("time").set_index("time").sort_index()
print(f"[pull]  {len(df)} rows  {df.index.min()} -> {df.index.max()}")
df.to_csv("data/BTCUSDT_1h_raw.csv")

# 3. Clean. Full hourly grid, forward-fill gaps, no zero volume.
full = pd.date_range(df.index.min(), df.index.max(), freq="h")
gaps = len(full) - len(df)
df = df.reindex(full).ffill()
zeros = int((df["volume"] == 0).sum())
df.loc[df["volume"] == 0, "volume"] = 1e-10
df.index.name = "time"
print(f"[clean] filled {gaps} missing hours, fixed {zeros} zero-volume bars")

# 4. Indicators on close: RSI(14), MACD(12,26,9), Bollinger(20,2).
c = df["close"]
delta = c.diff()
gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
df["rsi14"] = 100 - 100 / (1 + gain / loss)
ema12, ema26 = c.ewm(span=12, adjust=False).mean(), c.ewm(span=26, adjust=False).mean()
df["macd"] = ema12 - ema26
df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
mid, sd = c.rolling(20).mean(), c.rolling(20).std()
df["bb_mid"], df["bb_up"], df["bb_low"] = mid, mid + 2*sd, mid - 2*sd

df.to_csv("data/BTCUSDT_1h.csv")
print("[indic] saved data/BTCUSDT_1h.csv")
print(df[["close","volume","rsi14","macd","macd_signal","bb_up","bb_low"]].tail(5).round(2).to_string())
