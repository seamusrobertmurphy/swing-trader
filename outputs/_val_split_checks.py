import sys, time
sys.path.insert(0, "inputs")
import numpy as np, pandas as pd
import pyarrow.parquet as pq
import split_checks as sc

t0=time.time()
path="inputs/binance-data/dataset_1h_allmarket.parquet"
pf=pq.ParquetFile(path)
print("rows", pf.metadata.num_rows, "row_groups", pf.num_row_groups, flush=True)
batch=next(pf.iter_batches(batch_size=120000))
df=batch.to_pandas()
print("got batch", df.shape, flush=True)
if "in_sample" in df: df=df[df["in_sample"]]
df=df.sort_values("datetime").reset_index(drop=True)
feat=[c for c in df.columns if c.startswith("f_")]
print(f"slice {df.shape} | symbols {df['symbol'].nunique()} | {len(feat)} feats | "
      f"span {df['datetime'].min()} -> {df['datetime'].max()} | {time.time()-t0:.1f}s")

# temporal split inside the slice (mimic t1.split with a 60-day OOS so the slice has both sides)
cut=df["datetime"].max()-pd.Timedelta(days=60)
emb=pd.Timedelta(days=2)
train=df[df["datetime"]<=cut-emb].copy(); test=df[df["datetime"]>cut].copy()
print(f"train {len(train):,} / test {len(test):,}")

table, parts, verdict = sc.audit_split(train, test, feat, embargo_days=2)
print("VERDICT", verdict["status"], "| reasons:", verdict["reasons"][:3])
print("table rows:", len(table), "| cols:", list(table.columns))
print(table.head(6).to_string(index=False))
print("continuous drift top3:\n", parts["continuous"].head(3).to_string(index=False))

# small RF runs
imb, best = sc.imbalance_comparison(train, feat, embargo_bars=48, n_splits=4, sample=30000)
print("imbalance best:", best)
for k,v in imb.items():
    print(f"  {k:9s} kappa {v['kappa']:.3f} minrec {v['minority_recall']:.3f} oob {v['oob']:.3f}")
bk=sc.stratified_holdout_bracket(df, feat, n_repeats=3, sample=30000)
print("bracket kappa %.3f +/- %.3f" % bk["kappa"])
perm=sc.permutation_importance_train(train, feat, sample=20000, top=5)
print("perm top5:", list(perm["feature"]))
rep=sc.write_report(table, parts, verdict, imb, best, bk, perm, out_dir="outputs/AA-evals",
                    label_meta="validation slice")
print("report:", rep, "| total %.1fs" % (time.time()-t0))
