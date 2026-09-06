"""Pre-market committee run: TradingAgents ratings for the crypto book.

Runs each symbol through the TradingAgents bull/bear committee (crypto mode:
market, social and news analysts; fundamentals is dropped for crypto) and
appends the rating, executive summary and model provenance to
memory/research-log.md. The framework's own decision log, with realised-return
reflections, is redirected into memory/ta-decisions.md so it is committed with
the repo and gradeable at the Friday review.

The rating is a CANDIDATE signal only (research/tradingagents-applicability-
assessment.md): it never places orders and never overrides the hard rules.

The Anthropic key lives in the TradingAgents repo's gitignored .env, never in
this repo. Run under the TradingAgents venv:

    /Volumes/PortableSSD/Github/TradingAgents/.venv/bin/python \
        inputs/ta_research.py BTC ETH SOL [--date YYYY-MM-DD] [--dry-run]
"""

import argparse
import os
import sys
from datetime import date as _date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TA_REPO = Path("/Volumes/PortableSSD/Github/TradingAgents")

from dotenv import load_dotenv  # noqa: E402  (venv-provided)

load_dotenv(TA_REPO / ".env")

# Keep the framework's decision/reflection log inside this repo, set before
# tradingagents reads its config.
os.environ.setdefault(
    "TRADINGAGENTS_MEMORY_LOG_PATH", str(REPO / "05-research" / "memory" / "ta-decisions.md")
)

from tradingagents.dataflows.symbol_utils import normalize_symbol  # noqa: E402
from tradingagents.default_config import DEFAULT_CONFIG  # noqa: E402
from tradingagents.graph.trading_graph import TradingAgentsGraph  # noqa: E402

# Crypto price data now comes from the Binance public-data vendor (local
# `binance-vendor` branch of the TradingAgents clone), so the plain -USD forms
# work at full precision and the old Yahoo collision overrides are gone.
# TON stays excluded while TONUSDT is status BREAK (halted) on Binance.
YAHOO_OVERRIDES: dict[str, str] = {}


def build_config(args) -> dict:
    cfg = DEFAULT_CONFIG.copy()
    cfg["llm_provider"] = "anthropic"
    cfg["deep_think_llm"] = args.deep
    cfg["quick_think_llm"] = args.quick
    cfg["max_debate_rounds"] = args.debate_rounds
    # Altcoin alpha is measured against the crypto market, not SPY.
    cfg["benchmark_ticker"] = "BTC-USD"
    cfg["results_dir"] = str(REPO / "04-outputs" / "ta-reports")
    # Crypto OHLCV from Binance (full precision, no dead listings); anything
    # the Binance vendor cannot serve falls through to Yahoo.
    cfg["data_vendors"] = {**cfg["data_vendors"], "core_stock_apis": "binance,yfinance"}
    return cfg


def summary_line(final_decision: str) -> str:
    """Pull the one-line executive summary out of the rendered PM decision."""
    for line in final_decision.splitlines():
        if line.startswith("**Executive Summary**:"):
            return line.removeprefix("**Executive Summary**:").strip()
    return final_decision.replace("\n", " ")[:300]


def append_research_log(entries: list[str], run_date: str, cfg: dict) -> Path:
    log = REPO / "05-research" / "memory" / "research-log.md"
    log.parent.mkdir(parents=True, exist_ok=True)
    header_line = f"## {run_date} TradingAgents pre-market"
    header = (
        f"\n{header_line}\n\n"
        f"Committee: market+social+news analysts, bull/bear debate "
        f"({cfg['max_debate_rounds']} round), risk panel, PM. "
        f"Models: deep={cfg['deep_think_llm']}, quick={cfg['quick_think_llm']} "
        f"(anthropic). Candidate signal only; grades accrue in ta-decisions.md.\n\n"
    )
    prefix = "" if log.exists() and header_line in log.read_text() else header
    with open(log, "a", encoding="utf-8") as f:
        f.write(prefix + "\n".join(entries) + "\n")
    return log


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("symbols", nargs="+", help="BTC, BTCUSDT or BTC-USD forms all work")
    ap.add_argument("--date", default=_date.today().isoformat())
    ap.add_argument("--deep", default="claude-sonnet-5")
    ap.add_argument("--quick", default="claude-haiku-4-5")
    ap.add_argument("--debate-rounds", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true",
                    help="verify key, config and graph compile; no LLM calls")
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ABORT: ANTHROPIC_API_KEY is not set. Put it in "
              f"{TA_REPO / '.env'} (gitignored there) or the environment.",
              file=sys.stderr)
        return 1
    if len(args.symbols) > 8:
        print("ABORT: more than 8 symbols in one run; split it (API cost guard).",
              file=sys.stderr)
        return 1

    # Bare bases like BTC need the -USD suffix before normalisation.
    pairs = []
    for s in args.symbols:
        s = s.strip().upper()
        p = normalize_symbol(s if "-" in s or s.endswith(("USDT", "USDC", "USD")) else f"{s}-USD")
        pairs.append(YAHOO_OVERRIDES.get(p, p))

    cfg = build_config(args)
    ta = TradingAgentsGraph(selected_analysts=("market", "social", "news"), config=cfg)

    if args.dry_run:
        print(f"dry-run OK: graph compiled ({len(ta.graph.get_graph().nodes)} nodes); "
              f"would run {pairs} for {args.date}; "
              f"decisions -> {os.environ['TRADINGAGENTS_MEMORY_LOG_PATH']}")
        return 0

    # One entry appended per symbol as it completes, so a crash on one coin
    # loses nothing already finished; failures are journaled, not fatal.
    done = failed = 0
    for pair in pairs:
        print(f"--- {pair} {args.date} ---", flush=True)
        try:
            final_state, rating = ta.propagate(pair, args.date, asset_type="crypto")
            report_dir = ta.save_reports(final_state, pair)
            entry = (f"- **{pair}: {rating}.** "
                     f"{summary_line(final_state['final_trade_decision'])} "
                     f"Full report: {Path(report_dir).relative_to(REPO)}")
            done += 1
        except Exception as e:
            entry = f"- **{pair}: FAILED.** {type(e).__name__}: {str(e)[:200]}"
            failed += 1
        log = append_research_log([entry], args.date, cfg)
        print(entry.splitlines()[0], flush=True)

    print(f"\nLogged {done} rating(s), {failed} failure(s) to {log.relative_to(REPO)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
