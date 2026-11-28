#!/bin/bash
# 30-minute and 3-minute candles, operator request 26 September 2026.
# Binance, all 612 USDT pairs ever listed, into 03-inputs/binance-data/parquet_{30m,3m}.
# Alpaca, the 2,660 screened stocks, regular session, into 03-inputs/alpaca-data/min{3,30}.
# Alpaca builds every bar size from one-minute bars and ends each page at about
# 10,000 of them, so only 3-minute bars are pulled and the 30-minute ones are
# summed from them afterwards; on SPY the two match candle for candle.
# Every part resumes where it stopped, so the script can simply be run again.
#   download_intraday.sh [all|binance|alpaca]
cd "$(dirname "$0")/../.." || exit 1
PY=.venv/bin/python
B=03-inputs/binance-data
A=03-inputs/alpaca-data
part=${1:-all}
if [ "$part" != alpaca ]; then
  (
    $PY 03-inputs/vision_to_parquet.py --interval 30m --workers 10 > $B/download-30m.log 2>&1
    $PY 03-inputs/vision_to_parquet.py --interval 3m --workers 6 > $B/download-3m.log 2>&1
  ) &
fi
if [ "$part" != binance ]; then
  pids=()
  for k in 0 1 2; do
    $PY 03-inputs/alpaca_data.py download --timeframe 3m --shard $k/3 > $A/download-3m-$k.log 2>&1 &
    pids+=($!)
  done
  wait "${pids[@]}"
  $PY 03-inputs/alpaca_data.py resample --timeframe 30m > $A/resample-30m.log 2>&1
fi
wait
find $B $A -name '._*' -delete
printf '\a'; echo "intraday downloads ($part) finished $(date)"
