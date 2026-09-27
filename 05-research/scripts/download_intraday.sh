#!/bin/bash
# 30-minute and 3-minute candles, operator request 26 September 2026.
# Binance, all 612 USDT pairs ever listed, into 03-inputs/binance-data/parquet_{30m,3m}.
# Alpaca, the 2,660 screened stocks, regular session, into 03-inputs/alpaca-data/min{30,3}.
# Both parts resume where they stopped, so the script can simply be run again.
cd "$(dirname "$0")/../.." || exit 1
PY=.venv/bin/python
B=03-inputs/binance-data
A=03-inputs/alpaca-data
(
  $PY 03-inputs/vision_to_parquet.py --interval 30m --workers 10 > $B/download-30m.log 2>&1
  $PY 03-inputs/vision_to_parquet.py --interval 3m --workers 6 > $B/download-3m.log 2>&1
) &
for tf in 30m 3m; do
  pids=()
  for k in 0 1 2 3; do
    $PY 03-inputs/alpaca_data.py download --timeframe $tf --shard $k/4 > $A/download-$tf-$k.log 2>&1 &
    pids+=($!)
  done
  wait "${pids[@]}"
done
wait
find 03-inputs/binance-data 03-inputs/alpaca-data -name '._*' -delete
printf '\a'; echo "intraday downloads finished $(date)"
