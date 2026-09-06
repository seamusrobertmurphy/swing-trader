# Repository map, before the reorganisation

Taken 6 September 2026, immediately before Seamus reorganised the folders. Its
purpose is to say what will break when things move, so the same map can be taken
again afterwards and the two compared. 472 tracked files, 137 MB.

## What each folder is for

| Folder | Files | Size | What it holds |
| --- | ---: | ---: | --- |
| `inputs/` | 61 | 0.7 MB | Every script. The trading path, the data builders, the model code, the dashboard emitter. This is the codebase |
| `inputs/binance-data/` | 16 | 13.6 MB | Crypto data store. Universe snapshots and one legacy CSV are tracked; the 33 GB of bars and the Parquet panels are ignored |
| `inputs/alpaca-data/` | 8 | 2.4 MB | Equity data store. Universe snapshots and manifests tracked; the 5 GB of daily bars ignored |
| `inputs/binance-scripts/` | 3 | 0.0 MB | Vendored Binance sample downloaders. Third-party, untouched |
| `outputs/AA-evals/` | 136 | 6.1 MB | The evidence trail. Every dated report, factor test, execution report and metrics record. The most important folder in the repo |
| `outputs/1A` to `3D` | 35 | 3.9 MB | The lab engines, one folder per chapter step. MACD, confluence, Fibonacci, screening, ATR band, sizing, edge fence, training, tuning, stability |
| `outputs/PNG/`, `CSV/`, `HTML/`, `journal/` | 53 | 20.0 MB | Generated figures and tables. Committed because the notebooks cite them |
| `00-` to `03-` notebooks | 14 | 50.7 MB | The four workflow chapters. `00-trader-workflow.ipynb` alone is 44 MB |
| `dashboard/` | 2 | 0.1 MB | The Quarto source and its stylesheet. The rendered page is ignored |
| `memory/` | 7 | 0.1 MB | Runtime journal the agent writes. Book state, portfolio, trade log, research log |
| `.claude/memory/` | 4 | 0.0 MB | Project memory that travels with the repo |
| `tasks/` | 35 | 0.3 MB | Working notes, handovers, contracts. No build depends on it |
| `research/` | 57 | 38.2 MB | Reading library. 20 third-party PDFs, design notes, the RL reference import, notebook templates |
| `scripts/` | 10 | 0.0 MB | Shell entry points and the schedule templates |
| `skills/` | 5 | 0.0 MB | Agent instruction files for the routine cadence |
| repo root | 8 | 0.1 MB | CLAUDE.md, INDEX.md, README.md, MIGRATE.md, the three requirements files |

## What imports what

Moving a module in the left column breaks every file in the right column,
because `inputs/` modules import each other by bare name and that only works
while they share a directory.

| Module | Broken by moving it |
| --- | --- |
| `build_dataset_1h.py` | 24 files: analysis_charts, baseline_supertrend_1h, build_dataset_equity, cross_sectional_4h, cross_sectional_regime, cross_sectional_regime_4h, edge_attribution, edge_diagnostics and more |
| `train_model.py` | 18 files: cross_sectional_4h, cross_sectional_regime, cross_sectional_regime_4h, edge_attribution, edge_diagnostics, entry_earliness_4h, entry_sharpening_4h, entry_walkforward_4h and more |
| `train_model_1h.py` | 17 files: cross_sectional_4h, cross_sectional_regime, cross_sectional_regime_4h, edge_attribution, edge_diagnostics, entry_earliness_4h, entry_sharpening_4h, entry_walkforward_4h and more |
| `config.py` | 9 files: alpaca_check, alpaca_daily_report, alpaca_data, alpaca_execution_report, alpaca_trade, dashboard_data, equity_universe_filter, schedule_tick and more |
| `equity_momentum_monthly.py` | 6 files: alpaca_trade, dashboard_data, equity_cluster_cap, equity_portfolio_sim, equity_survivorship_stress, equity_weekly_factors |
| `cross_sectional_4h.py` | 6 files: cross_sectional_regime, cross_sectional_regime_4h, edge_attribution, equity_edge_matrix, mst_gate_walkforward, portfolio_backtest |
| `alpaca_trade.py` | 5 files: alpaca_daily_report, alpaca_execution_report, analysis_charts, dashboard_data, schedule_tick |
| `eval_report.py` | 4 files: model_assessment_1h, sweep_label_1h, train_model, train_model_1h |
| `model_metrics.py` | 3 files: dashboard_data, trend_life_baseline, trend_life_tune |
| `cross_sectional_regime.py` | 3 files: edge_attribution, mst_gate_walkforward, portfolio_backtest |
| `build_dataset_equity.py` | 3 files: equity_edge_matrix, equity_momentum_monthly, equity_walkforward |
| `equity_cluster_cap.py` | 2 files: alpaca_trade, dashboard_data |
| `build_dataset.py` | 2 files: trade_binance, train_model |
| `macd.py` | 2 files: build_macd_charts, confluence |
| `fib.py` | 2 files: build_fib_charts, confluence |
| `indicators.py` | 2 files: test_agent, train_agent |
| `trading_env.py` | 2 files: test_agent, train_agent |

## Modules nothing else imports

These are run by hand from the command line. Safe to move on their own,
but check `scripts/*.sh` and the notebooks for the paths that call them.

- `alpaca_check`, `alpaca_data`, `analysis_charts`, `atr_band`
- `baseline_supertrend_1h`, `build_confluence`, `build_fib_charts`, `build_macd_charts`
- `build_screen_charts`, `build_spread_options`, `cross_sectional_regime_4h`, `download-aggTrade`
- `download-trade`, `edge_fence`, `entry_sharpening_4h`, `entry_walkforward_4h`
- `episode1_binance_data`, `equity_portfolio_sim`, `equity_survivorship_stress`, `equity_walkforward`
- `equity_weekly_factors`, `exit_geometry_1h`, `exit_geometry_viz`, `fetch_funding`
- `flow_data`, `model_assessment_1h`, `mst_gate_walkforward`, `multiframe_eval`
- `paper_trade`, `portfolio_backtest`, `regime_conditioning`, `render_workflow_docx`
- `research_figures`, `schedule_tick`, `screen`, `sizing`
- `split_checks`, `sweep_label_1h`, `ta_research`, `test_agent`
- `trade_binance`, `train_agent`, `trend_life_tune`, `variable_selection`
- `walkforward`, `wf_splitter`

## Paths written into files, which a move breaks silently

Absolute paths to `/Volumes/PortableSSD`, which break if the repo is moved or
cloned. `MIGRATE.md` records that these were removed from every script in
August; what remains is in notebooks and two shell scripts.

| File | What it points at |
| --- | --- |
| `00-trader-workflow.ipynb` | the `.venv` interpreter, and the TradingAgents repo beside this one |
| `02-trader-controls.ipynb` | three CSVs under `outputs/` |
| `03-trader-execution.ipynb` | the repo root, the `.venv`, and a Binance snapshot |
| `inputs/baseline_supertrend_1h.py` | the ClaudeTrader checkout under `Github/SuperTrendTradingBot` |
| `inputs/ta_research.py` | the TradingAgents repo and its own `.venv` |
| `inputs/binance-data/orchestrate_4h.sh` | the repo root |
| `tasks/run_auto_eval.sh` | the repo root |

Relative paths that break if a folder is renamed. Every script finds the repo
root by walking up until it sees `inputs/`, so **renaming `inputs/` breaks
everything**. The dashboard reads `outputs/dashboard/data.json` and
`outputs/AA-evals/*/`. The daily report writes into `outputs/AA-evals/<date>/`.

## The three things most likely to break

1. **Renaming `inputs/`.** Every script locates the repo root by looking for it,
   and every module imports its neighbours by bare name, which only works while
   they share one directory. Splitting `inputs/` into subfolders needs either a
   package with `__init__.py` and dotted imports, or a `sys.path` entry.
2. **Moving `outputs/AA-evals/`.** The dashboard emitter, the daily report and
   the metrics layer all write and read it by that path.
3. **Moving `memory/alpaca-book-state.json`.** The five-day cadence guard reads
   it, and without it the next run believes no rebalance has ever happened.

## Suggested order for the move

Move the folders nothing imports first, confirm, then the code. `tasks/`,
`research/`, `skills/` and the notebook chapters are safe to move today; nothing
executable depends on them. `outputs/` subfolders other than `AA-evals` are next.
Leave `inputs/` and `outputs/AA-evals/` until last, and when `inputs/` moves,
run `.venv/bin/python inputs/alpaca_check.py` and one dashboard render as the
proof that nothing broke.
