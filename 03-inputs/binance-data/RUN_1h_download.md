# Full-market 1h kline pull (run on the Mac, not the sandbox)

The full ~433-coin pull is thousands of small HTTP requests and roughly 0.7 GB
zipped. That exceeds the sandbox's 45-second-per-command cap, so run it on the Mac.
The extended `flow_data.py` was validated in-session on BTC/ETH/SOL for 2024-01..02
(4320 hourly rows, 24 per day, flow_imbalance in range), so the script itself is known
good; this is just the scale-up.

## Status

Started 2026-06-21 on the Mac (MacPorts python 3.12.13, pandas 3.0.3), running detached.
It is resumable, so if it stops just re-run the same command and it resumes.

Monitor:    `tail -f /Volumes/PortableSSD/Github/day-trader/tasks/download_1h.log`
Count zips: `find /Volumes/PortableSSD/Github/day-trader/inputs/binance-data/klines_1h -name '*.zip' ! -name '._*' | wc -l`
Stop:       find the python PID with `pgrep -f flow_data.py` then `kill <PID>`

## Command

Logs go in tasks/ (per operator preference). The download output dir is anchored to the
script's own folder, so klines still land in inputs/binance-data/klines_1h regardless of cwd.

```bash
cd /Volumes/PortableSSD/Github/day-trader
nohup /opt/local/bin/python3 -u inputs/binance-data/flow_data.py --interval 1h --all-market > tasks/download_1h.log 2>&1 &
```

What it does:

- Resolves the universe live from Binance `exchangeInfo`: every active USDT spot pair
  with `status=TRADING` and spot trading allowed (433 as of 2026-06).
- Downloads monthly 1h kline archives from `data.binance.vision` into
  `klines_1h/<SYMBOL>/`, falling back to daily files for the current open month.
- Aggregates every bar into `flow_1h.csv` (symbol, datetime, close, volume,
  quote_volume, num_trades, taker_buy_base, taker_buy_ratio, flow_imbalance), one row
  per hour.

## Notes

- Resumable. Files already on disk are skipped, so you can interrupt with Ctrl-C and
  re-run; it picks up where it stopped.
- No API key, no orders, read-only public data. Only dependency is `pandas`.
- Wall-clock: expect on the order of one to a few hours, dominated by the many small
  requests, not by bandwidth. Most of the time is the script probing months that
  predate each coin's listing (those 404 and skip cleanly).
- To cut that probing at the cost of early BTC/ETH history, scope the start:
  `--start 2020-01` (Binance Vision's archives are densest from 2020 on). The default
  start is 2017-08 for full history.
- Do NOT add `--aggtrades` to a full-market run; that pulls the multi-gigabyte
  trade-level archives for every coin and is only needed for finer-than-bar flow later.
- Validate-first option, if you want to watch it work before the full run:
  `python3 flow_data.py --interval 1h -s BTCUSDT ETHUSDT --start 2025-01 --end 2025-02`

## After it finishes

`flow_1h.csv` and `klines_1h/` are the inputs the `build_dataset.py` 1h refactor will
read (offline, reproducible). The refactor also needs the three modeling decisions
settled (point-in-time spread gate, 1h feature windows, 1h label geometry).
