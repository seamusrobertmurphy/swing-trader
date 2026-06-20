# Integrating the confluence layer into day-metrics — a paste-in guide

You are integrating this into `day-metrics.ipynb` yourself, so nothing here edits
the notebook. These are cells to paste and the plain-language explanation to sit
beside them. Everything runs on the candles the notebook already fetches; it adds
no new data source and no new heavy dependency.

---

## 1. Where the data comes from, in plain terms

Every number in the notebook comes from one place: the public **Binance** price
feed, reached through the **ccxt** library's `fetch_ohlcv` call inside
`calculate_indicator`. ccxt is a thin wrapper over the exchange's web API. Nothing
is simulated or read from disk. `SANDBOX = False` means real mainnet prices, but the
connection is read-only: the notebook never places an order.

One unit of data is a **candle**: six numbers for a single time period, being time,
open, high, low, close, volume. The most recent candle is still forming, so the code
drops it (`bars[:-1]`) and keeps only closed candles. A signal that used the forming
candle would shift minute to minute and could not be acted on.

The **universe** is not fixed. `fetch_tickers()` returns 24-hour stats for every
market; the notebook keeps spot `/USDT` pairs and takes the `TOP_N` busiest by
volume, chosen fresh each run.

The global dials, set in the config cell:

| dial | default | plain meaning |
|---|---|---|
| EXCHANGE | binance | which venue's prices |
| SANDBOX | False | real prices, read-only, no orders |
| TIMEFRAME | 1d | one candle is one day |
| LIMIT | 300 | pull 300 candles; 299 remain after dropping the forming one |
| TOP_N | 20 | scan the 20 busiest /USDT pairs |

Everything inherits `TIMEFRAME`. On `1d` this is a **swing** read: signals update
once a day. Change it to `1h` or `4h` and the whole notebook, the confluence layer
included, recomputes on that faster clock. `LIMIT` sets how far back the history
reaches.

A "window" is how many recent candles a metric averages. Short windows react fast
and noisily, long windows are smooth and slow. What the notebook already computes:

| metric | window | reads, in plain terms |
|---|---|---|
| Kalman filter | adaptive | a smoothed fair-value line through the noise |
| EMA-14 | 14 | recent trend direction |
| Bollinger | 14, 2σ | a volatility envelope around price |
| Ichimoku | 9 / 26 / 52 | multi-span trend cloud |
| AMAT | 8 / 21 / 2 | is a fast average leading a slow one |
| RSI | 14 | overbought high, oversold low, scale 0–100 |
| Choppiness | 14 | trending versus chopping sideways |
| MACD | 12 / 26 / 9 | momentum: fast EMA minus slow EMA, plus its signal line |
| candle shapes | 1 candle | doji, dragonfly, gravestone reversal hints |

The notebook's existing **Buy** fires when three agree: AMAT trend on, EMA-14 above
Kalman, day's low above Kalman. **Sell** is the mirror.

---

## 2. What the confluence layer adds

A second, independent opinion built from four classic methods that read the market
differently, combined so a trade only flags when they **agree**. One indicator alone
whipsaws; agreement filters most of that out. Each method casts one **vote** at the
latest candle: `+1` bullish, `-1` bearish, `0` neutral.

- **MACD (12/26/9)** — momentum. Votes `+1` after a *guarded* bullish crossover,
  `-1` after a guarded bearish one. Guarded means tiny crosses inside a noise band
  are ignored, so it does not flip on every wiggle.
- **MA crossover (20/50)** — the oldest trend test. `+1` when the 20-candle average
  is above the 50-candle average, `-1` below.
- **Fibonacci (lookback 240, golden pocket 0.5–0.618)** — location. Finds the most
  recent big swing and asks where price sits. Pulled back into the golden pocket in
  an uptrend votes `+1` (buy the dip); bounced into it in a downtrend votes `-1`.
- **Candles (engulfing, 3-candle memory)** — a reversal pattern. Bullish engulfing
  `+1`, bearish `-1`, held live a few candles.

**Score is the four votes summed**, range `-4` to `+4`. A **BUY** fires when the
score first reaches **+2**, a **SELL** at **-2**. The threshold is the guardrail:
no single method trades alone.

---

## 3. The cells to paste

These assume the notebook's variables already exist: `universe`, `results`,
`calculate_indicator`, `go`, `pd`, `np`, `TIMEFRAME`, `LIMIT`. The import finds the
`confluence_lab` folder wherever it sits, so it keeps working after you move folders.

**Cell A — import the engine (location-independent):**

```python
import os, sys
_cands = ["confluence_lab", "outputs/confluence_lab",
          "../confluence_lab", "../outputs/confluence_lab"]
_lab = next((os.path.abspath(c) for c in _cands
             if os.path.isfile(os.path.join(c, "confluence.py"))), None)
if _lab is None:                              # last resort: shallow search
    for root, _, files in os.walk("."):
        if "confluence.py" in files and root.count(os.sep) <= 4:
            _lab = os.path.abspath(root); break
assert _lab, "confluence.py not found — set _lab to your confluence_lab path"
sys.path.insert(0, _lab)
from confluence import ConfluenceConfig, compute_confluence

CONF_CFG = ConfluenceConfig(ma_fast=20, ma_slow=50)   # MACD 12/26/9 + Fib 240 inherited
print("Confluence ready. Votes look through these windows:")
print(f"  MACD {CONF_CFG.macd.fast}/{CONF_CFG.macd.slow}/{CONF_CFG.macd.signal} guarded"
      f" · MA {CONF_CFG.ma_fast}/{CONF_CFG.ma_slow}"
      f" · Fib lookback {CONF_CFG.fib.lookback}, pocket 0.5–0.618"
      f" · candles {CONF_CFG.candle_decay}-bar memory · fire at |score|>={CONF_CFG.threshold}")
print(f"  Clock inherited from the notebook: TIMEFRAME={TIMEFRAME}, LIMIT={LIMIT}")
```

**Cell B — score every coin and add the columns to a copy of `results`:**

```python
conf_rows = []
for symbol in universe:
    try:
        df_sym, _ = calculate_indicator(symbol)       # the same fetch the notebook uses
        c = compute_confluence(df_sym, CONF_CFG)
        last, recent = c.iloc[-1], c.tail(3)
        conf_rows.append(dict(
            Symbol=symbol,
            St_MACD=int(last.st_macd), St_MA=int(last.st_ma),
            St_Fib=int(last.st_fib),  St_Candle=int(last.st_candle),
            Conf_Score=int(last.score),
            Conf_Buy=bool(recent.buy.any()), Conf_Sell=bool(recent.sell.any())))
    except Exception as e:
        print(f"skip {symbol}: {type(e).__name__}")

conf_df = pd.DataFrame(conf_rows)
results_conf = results.merge(conf_df, on="Symbol", how="left")
print(f"confluence scored {len(conf_df)} pairs | "
      f"{int(conf_df.Conf_Buy.sum())} fresh buys | {int(conf_df.Conf_Sell.sum())} fresh sells")
results_conf.sort_values("Conf_Score", ascending=False)
```

**Cell C — chart the strongest candidate (price, agreement ribbon, score):**

```python
from plotly.subplots import make_subplots
from IPython.display import HTML

pick = results_conf.sort_values("Conf_Score", ascending=False)["Symbol"].iloc[0]
df_p, _ = calculate_indicator(pick)
c = compute_confluence(df_p, CONF_CFG)
t, buy, sell = df_p.index, c["buy"].values, c["sell"].values

fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.04,
                    row_heights=[0.55, 0.22, 0.23],
                    subplot_titles=(f"{pick} — price, MAs, confluence signals",
                                    "Agreement (green up / red down)", "Score"))
fig.add_trace(go.Candlestick(x=t, open=df_p.open, high=df_p.high, low=df_p.low,
              close=df_p.close, name="price", showlegend=False,
              increasing_line_color="#26a69a", decreasing_line_color="#ef5350"), 1, 1)
fig.add_trace(go.Scatter(x=t, y=df_p.close.rolling(CONF_CFG.ma_fast).mean(),
              name=f"MA{CONF_CFG.ma_fast}", line=dict(color="#42a5f5", width=1)), 1, 1)
fig.add_trace(go.Scatter(x=t, y=df_p.close.rolling(CONF_CFG.ma_slow).mean(),
              name=f"MA{CONF_CFG.ma_slow}", line=dict(color="#ab47bc", width=1)), 1, 1)
fig.add_trace(go.Scatter(x=t[buy], y=df_p.low[buy]*0.98, mode="markers", name="BUY",
              marker=dict(symbol="triangle-up", size=12, color="#1b7d6f")), 1, 1)
fig.add_trace(go.Scatter(x=t[sell], y=df_p.high[sell]*1.02, mode="markers", name="SELL",
              marker=dict(symbol="triangle-down", size=12, color="#c62828")), 1, 1)
z = np.vstack([c.st_macd, c.st_ma, c.st_fib, c.st_candle])
fig.add_trace(go.Heatmap(x=t, y=["MACD","MA","Fib","Candle"], z=z, zmin=-1, zmax=1,
              colorscale=[[0,"#ef5350"],[0.5,"#eeeeee"],[1,"#26a69a"]], showscale=False), 2, 1)
fig.add_trace(go.Scatter(x=t, y=c.score, fill="tozeroy",
              line=dict(color="#5e35b1"), showlegend=False), 3, 1)
fig.add_hline(y=CONF_CFG.threshold,  line=dict(color="#1b7d6f", dash="dot"), row=3, col=1)
fig.add_hline(y=-CONF_CFG.threshold, line=dict(color="#c62828", dash="dot"), row=3, col=1)
fig.update_layout(height=820, xaxis_rangeslider_visible=False,
                  legend=dict(orientation="h", y=1.04))
fig.write_html("outputs/confluence_chart.html", include_plotlyjs=True, auto_open=False)
HTML(fig.to_html(include_plotlyjs="cdn", full_html=False))
```

---

## 4. How to read the new columns

`St_MACD, St_MA, St_Fib, St_Candle` are each method's current vote, `+1` up, `-1`
down, `0` neutral. Read across a row to see *who* agrees. `Conf_Score` is the four
summed, `-4` to `+4`, the distance from zero being the strength of agreement.
`Conf_Buy` / `Conf_Sell` are True when a fresh signal fired in the last three
candles: that is the *timing*, while the score is the *strength*.

The strongest long is a high positive `Conf_Score` with `Conf_Buy` True; the
strongest exit a deep negative score with `Conf_Sell` True. When the notebook's own
`Buy` column agrees with a positive confluence, both the trend engine and the four
methods point the same way and conviction is highest.

---

## 5. Where to act — the entry and exit points to watch

Read the chart top down. The **triangles** on price are the calls: green up entry,
red down exit. The **ribbon** shows why: each row is one method, green when it votes
up, red down; the more rows sharing a colour, the stronger the agreement. The
**score panel** is the trigger: each time the purple line crosses the dotted `+2`
line a buy fires, the `-2` line a sell.

Watch for an **entry** when the score climbs through `+2` with a fresh `Conf_Buy`,
best of all when price is sitting in or just above the Fibonacci golden pocket and
the MACD row turns green at the same spot, location and momentum together, and the
notebook's own `Buy` is also True.

Watch for an **exit** when the score drops through `-2` with a fresh `Conf_Sell`, or
when price loses the golden pocket and breaks below the 78.6% retracement, or on a
bearish MACD divergence where price makes a higher high but MACD makes a lower high.

**Honest limit.** In-sample over a falling test window these signals mostly reduced
losses by sitting out the worst of the drop, but showed no proven edge, the same
NO-GO the project already reached. Treat this as a second opinion to weigh, not an
autopilot. Nothing here places an order, and the live switch stays off until a
walk-forward test across rising, falling, and sideways markets earns it.

---

## 6. Folder dependency, so nothing breaks when you move things

Keep `macd_lab`, `fib_lab`, and `confluence_lab` together as siblings under one
parent (they currently live under `outputs/`). `confluence.py` finds its two
siblings by searching nearby folders, and the import cell above finds
`confluence_lab` the same way, so the group can be relocated as long as it stays
together. The dashboards' offline fallback looks for `BTCUSDT_1h_raw.csv` near the
folder; live ccxt data needs no local file at all. If you ever split the three
folders apart, set the path by hand in Cell A.
