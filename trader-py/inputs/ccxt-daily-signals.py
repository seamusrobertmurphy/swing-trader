import ccxt, warnings, numpy as np, pandas as pd
import pandas_ta_classic as ta
from pykalman import KalmanFilter
warnings.filterwarnings('ignore')

exchange = ccxt.binance()

def calculate_indicator(symbol, timeframe='1d', limit=300):
    bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(bars[:-1], columns=['timestamp','open','high','low','close','volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.set_index('timestamp')

    close = df['close'].iloc[-1]
    low   = df['low'].iloc[-1]

    kf = KalmanFilter(transition_matrices=[1], observation_matrices=[1],
                      initial_state_mean=0, initial_state_covariance=1,
                      observation_covariance=1, transition_covariance=.01)
    state_means,_ = kf.filter(df['close'].values)
    df['kf_mean'] = state_means
    kalman = df['kf_mean'].iloc[-1]
    above_kalman = low > kalman

    df.ta.ema(length=14, append=True)
    ema_14 = df['EMA_14'].iloc[-1]
    ema_cross = ema_14 > kalman

    bb = df.ta.bbands(length=14)
    bbl = bb['BBL_14_2.0'].iloc[-1]; bbu = bb['BBU_14_2.0'].iloc[-1]

    isa_9 = df.ta.ichimoku()[1]['ISA_9'].iloc[-1]
    isb_26 = df.ta.ichimoku()[1]['ISB_26'].iloc[-1]
    amat = bool(df.ta.amat()['AMATe_LR_8_21_2'].iloc[-1] == 1)
    rsi = df.ta.rsi().iloc[-1]
    chop = round(float(df.ta.chop().iloc[-1]), 2)

    buy  =  amat &  ema_cross &  above_kalman
    sell = ~amat & ~ema_cross & ~above_kalman
    return dict(Symbol=symbol, Buy=buy, Sell=sell, Close=round(close,4),
                RSI=round(rsi,2), Chop=chop, AMAT=amat, EMA_gt_Kalman=ema_cross,
                Low_gt_Kalman=above_kalman)

# universe: liquid USDT spot pairs by quote volume
tk = exchange.fetch_tickers()
usdt = [(s,d.get('quoteVolume') or 0) for s,d in tk.items()
        if s.endswith('/USDT') and ':' not in s]
universe = [s for s,_ in sorted(usdt, key=lambda x:-x[1])[:15]]
print("universe:", universe)

rows=[]
for s in universe:
    try: rows.append(calculate_indicator(s))
    except Exception as e: print("skip",s,type(e).__name__,str(e)[:60])
res = pd.DataFrame(rows)
top = res.sort_values(['Buy','RSI'], ascending=[False,True]).head(5)
bot = res.sort_values(['Sell','RSI'], ascending=[False,False]).head(5)
print("\n== TOP (buy candidates) =="); print(top.to_string(index=False))
print("\n== BOTTOM (sell candidates) =="); print(bot.to_string(index=False))
print("\nrows:", len(res), "buys:", int(res.Buy.sum()), "sells:", int(res.Sell.sum()))
