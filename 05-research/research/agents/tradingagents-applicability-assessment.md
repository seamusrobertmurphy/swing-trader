# TradingAgents Applicability Assessment

Written 2026-08-16 after building and testing TauricResearch/TradingAgents v0.3.1 from the clone at `/Volumes/PortableSSD/Github/TradingAgents` (commit a33fd4c). Companion to `rl-applicability-assessment.md`, which did the same exercise for the RL reference import.

## What It Is

TradingAgents is a LangGraph pipeline that runs one ticker on one date through a staged committee of LLM agents: up to four analysts (market, sentiment, news, fundamentals), a bull and bear researcher who debate, a research manager, a trader, three risk debaters, and a portfolio manager who emits a typed decision. The output is a five-tier rating (Buy, Overweight, Hold, Underweight, Sell) plus an executive summary, an investment thesis, an optional price target, and a time horizon, parsed deterministically from structured output. Paper: arXiv 2412.20138. The README states plainly that it is a research scaffold, that runs are non-deterministic, and that backtest results are not guaranteed to match any published figure.

## Build Record

Built 2026-08-16 on the Mac, natively, no Docker.

- Venv: `/Volumes/PortableSSD/Github/TradingAgents/.venv`, MacPorts python3 3.12.13, `pip install -e ".[dev]"`. Persistent; reuse it, do not recreate.
- exFAT AppleDouble litter cleared post-install (same `._*` hazard as this repo; same `find ... -name '._*' -delete` fix).
- Test suite: `576 passed, 2 skipped, 69 subtests passed in 92.07s`. Both skips expected (optional `langchain_aws` extra not installed; live DeepSeek call needs a real key). Ruff strict lint: clean. Import smoke (`import tradingagents, cli.main`): clean. This reproduces the project's full CI matrix locally.
- Live keyless dataflows all verified on 2026-08-16 against BTC: Yahoo OHLCV (15 daily bars returned), stockstats RSI window, StockTwits crypto stream via the `BTC.X` mapping with a sentiment tally, Reddit RSS with graceful 429 backoff, Polymarket keyless query, date-windowed Yahoo news. Symbol normalisation maps `BTCUSDT` and `SOLUSDT` to `BTC-USD` and `SOL-USD`, so our Binance pair names translate directly.
- Graph construction verified for both asset modes, including an Anthropic-provider crypto graph (19 nodes, no fundamentals analyst) with `claude-fable-5` as the deep model.
- Decision-log round trip verified: store, outcome update with raw and alpha return, reflection injection into the next same-ticker prompt.
- Failure mode verified: a bad LLM key raises a clean `AuthenticationError` on the first agent call. Loud, not silent; compatible with our abort-and-notify rule.

## What Blocks It

No LLM API key exists anywhere on this machine, in the shell environment or any profile file. Every keyless layer is tested; the agentic core has made no live decision run. It needs exactly one provider key (Anthropic, OpenAI, Google, OpenRouter, or any OpenAI-compatible endpoint). A free FRED key would additionally light up the macro tool. Ollama is not a realistic fallback on an 8 GB machine.

## Where It Fits

The June-23 diagnosis concluded that 1h direction prediction sits at the efficient-market floor and that edge requires changing the problem: a coarser frame, new information, or cross-sectional framing. TradingAgents is the "new information" lever. Its inputs (news, StockTwits, Reddit, Polymarket odds, FRED macro) are exactly the channels the price-only pipeline cannot see, and its horizon (its reflection loop grades five-day returns) matches the swing half of the mandate.

Three genuine fits:

1. **Principle 1 automation.** The bull-versus-bear debate is literally the affirmative case plus devil's advocate that every entry must have in `research-log.md`. A pre-market TradingAgents run per candidate produces that document mechanically, with the debate transcript as evidence the thesis was attacked.
2. **A candidate signal to grade.** The five-tier rating is a new feature stream. Journal it per coin per day and score it on the same after-fee, out-of-sample bar as every other candidate. The append-only decision log with realised-return reflection makes the grading nearly free.
3. **Regime-gate input.** The cross-sectional work needs a market-regime gate. The news and macro analysts give a non-price read on regime that `f_rg_` and the BTC-trend features cannot.

## Where It Doesn't

- **No demonstrated edge.** The README disclaims replicable returns, and any LLM backtest carries pretraining look-ahead: the model may already know the period's outcome. Nothing in this framework has passed, or claims to pass, our after-fee out-of-sample scoreboard. Its rating must not touch sizing or execution until it has been graded for several weeks and beaten the bar.
- **Wrong data plane for the model track.** Yahoo daily USD spot, not Binance 1h USDT klines, no order flow. It cannot replace or feed `build_dataset_1h.py`; it sits beside the quant pipeline, not inside it.
- **Crypto mode is the thin path.** The fundamentals analyst is dropped for crypto, so the committee narrows to market, social, and news.
- **Cost and latency.** One run is dozens of LLM calls with a deep model in the debate seats. Daily runs over eight coins is a real API bill; budget and meter before scheduling.
- **Alpha benchmark.** The default alpha baseline for suffix-less tickers is SPY. Set `benchmark_ticker` to `BTC-USD` so altcoin reflections measure alpha against the market that matters.
- **Non-determinism.** Two runs on the same inputs differ. Journal the provider, models, and config with each decision, the same discipline as Kelly inputs.

## Integration Verdict

Keep the repos separate. Do not move day-trader into TradingAgents: that repo is an active upstream (nine releases in eight months) and our value is the control layer it lacks, the hard rules, sizing, journaling, and after-fee scoreboard. Folding our workflow into a fork would cost us clean upstream pulls and bury our discipline inside someone else's release cycle.

Integrate the other direction, as a consumed analysis service:

1. A thin wrapper (`inputs/ta_research.py`, to be written) invokes `/Volumes/PortableSSD/Github/TradingAgents/.venv/bin/python`, calls `TradingAgentsGraph.propagate(symbol, date, asset_type="crypto")` for held coins and screened candidates, and writes the rating, thesis, and debate summary into `research-log.md`. Config: `benchmark_ticker="BTC-USD"`, `max_debate_rounds=1`, memory log pointed into this repo via `TRADINGAGENTS_MEMORY_LOG_PATH` so decisions and reflections are committed with everything else.
2. The pre-market routine treats the output as the Principle 1 write-up plus a candidate signal. The rating never places an order; entries still require the quant screen, the hard rules still cap and stop everything.
3. The Friday review grades accumulated ratings against realised after-fee returns. Only if the signal clears the same bar as any other change does it earn a vote in sizing.

Blocked on one operator decision: which LLM provider key to provision, and the run budget. Everything else is built, tested, and ready to wire.
