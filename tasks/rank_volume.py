import os, glob, zipfile
import pandas as pd
root = "inputs/binance-data/klines_1h"
COLS = ["open_time","open","high","low","close","volume","close_time",
        "quote_volume","count","taker_buy_volume","taker_buy_quote_volume","ignore"]
rows=[]
for sym in sorted(os.listdir(root)):
    if sym.startswith("._"): continue
    d=os.path.join(root,sym)
    if not os.path.isdir(d): continue
    zips=sorted(z for z in glob.glob(os.path.join(d,"*.zip"))
                if not os.path.basename(z).startswith("._"))
    if not zips: continue
    recent=zips[-2:]            # last ~2 months = current liquidity
    qv=0.0; nbars_total=0
    for zp in recent:
        try:
            with zipfile.ZipFile(zp) as zf:
                nm=zf.namelist()[0]
                with zf.open(nm) as fh:
                    df=pd.read_csv(fh, header=None)
            df=df.iloc[:, :len(COLS)]; df.columns=COLS[:df.shape[1]]
            q=pd.to_numeric(df["quote_volume"], errors="coerce")
            qv+=float(q.sum(skipna=True))
        except Exception:
            pass
    # total bars across ALL months on disk (history gate)
    nbars_total=0
    for zp in zips:
        try:
            with zipfile.ZipFile(zp) as zf:
                nm=zf.namelist()[0]
                with zf.open(nm) as fh:
                    nbars_total+=sum(1 for _ in fh)
        except Exception:
            pass
    rows.append((sym, qv, nbars_total))
res=pd.DataFrame(rows, columns=["symbol","qv_2mo","bars"])
res=res.sort_values("qv_2mo", ascending=False)
res=res[res["bars"]>=1488]     # clear the build's minimum-history gate
top=res.head(50).reset_index(drop=True)
top["symbol"].to_csv("tasks/top50_symbols.txt", index=False, header=False)
pd.options.display.float_format="{:,.0f}".format
print("ranked", len(res), "eligible coins (bars>=1488); top 50 by 2-month quote volume:")
print(top.to_string())
print()
print("SYMS=" + " ".join(top["symbol"].tolist()))
