#!/bin/zsh
# Finish the 4h frame once the parallel shard downloads complete: aggregate 4h flow over the
# full on-disk survivorship universe, build dataset_4h_allmarket.parquet, validate. Detached and
# idempotent -- safe to re-run. Logs to _orchestrate_4h.log; writes _4h_DONE on success.
set -u
cd /Volumes/PortableSSD/Github/day-trader
PY=.venv/bin/python
LOG=inputs/binance-data/_orchestrate_4h.log
KL=inputs/binance-data/klines_4h
exec >> "$LOG" 2>&1
echo "=== orchestrate_4h start $(date) ==="

# 1) wait for all shard downloaders to exit, then confirm the zip count is stable (no stragglers)
while pgrep -f 'acquire_vision.py download --interval 4h' >/dev/null; do sleep 60; done
echo "downloaders exited $(date); confirming stability"
prev=0
while true; do
  n=$(find "$KL" -name '*.zip' | wc -l | tr -d ' ')
  if [ "$n" = "$prev" ]; then break; fi
  echo "  zips=$n (was $prev), waiting for stability"; prev=$n; sleep 90
done
echo "download stable: $n zips, $(ls "$KL" | wc -l | tr -d ' ') coins $(date)"

# 2) clear exFAT AppleDouble litter that breaks zip/matplotlib reads
find "$KL" -name '._*' -delete 2>/dev/null
find .venv -name '._*' -delete 2>/dev/null

# 3) aggregate 4h flow over the FULL on-disk universe (survivorship-complete, not exchangeInfo)
SYMS=$($PY -c "import os;print(' '.join(sorted(d for d in os.listdir('$KL') if os.path.isdir('$KL/'+d) and not d.startswith('._'))))")
echo "aggregating 4h flow over $(echo $SYMS | wc -w | tr -d ' ') coins $(date)"
$PY inputs/binance-data/flow_data.py -s ${=SYMS} --interval 4h --skip-download
echo "flow done $(date)"

# 4) build the full 4h dataset (configure(4) via --interval 4)
echo "building 4h dataset $(date)"
$PY inputs/build_dataset_1h.py --interval 4
echo "build done $(date)"

# 5) validate
$PY - <<'PYEOF'
import os, sys
sys.path.insert(0, os.path.abspath("inputs"))
import build_dataset_1h as bd
bd.configure(4)
df = bd.read_frame(bd.DATASET_PATH)
feat = bd.feature_columns(df)
ins = df[df["in_sample"]]
print(f"VALIDATE 4h: rows={len(df):,} in_sample={len(ins):,} coins={df['symbol'].nunique()} "
      f"features={len(feat)} base_all={df['label'].mean():.3f} base_in={ins['label'].mean():.3f} "
      f"span {df['datetime'].min()} -> {df['datetime'].max()}")
PYEOF

touch inputs/binance-data/_4h_DONE
echo "=== orchestrate_4h COMPLETE $(date) ==="
