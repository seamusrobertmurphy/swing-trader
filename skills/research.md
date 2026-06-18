# Skill: research

How to use Perplexity for catalyst and thesis research. Used primarily by `routines/pre-market.md` and ad hoc by the weekly-review.

## Tool

`scripts/perplexity.sh` reads `PERPLEXITY_API_KEY` from the environment and posts a chat-completion-style request. The default model is the Perplexity online model so results include current web context. Do not use the native web search — the brief is explicit.

Invocation:

```
scripts/perplexity.sh "your query here"
```

Output is the response text (plus citations) to stdout. Capture and quote sources in the research-log entry.

## What to look for

### Macro

- Overnight equity-index futures: ES, NQ, YM, RTY direction and magnitude.
- Treasury yields move (especially 10Y), USD index move.
- Geopolitical or policy headlines that move the index (Fed speakers, CPI/PPI prints, sovereign events).

### Catalysts on existing holdings

For every symbol in `memory/portfolio.md`, query Perplexity for news in the last 24 hours. Look specifically for:

- Earnings or guidance revisions.
- M&A or strategic action.
- Regulatory or legal news.
- Customer wins or losses material to the thesis.
- Insider transactions of size.
- Analyst rating changes that move the tape.

Compare against the rationale logged in the BUY entry. If the new news breaks the thesis, flag for action — exit, trim, or hold-with-caution.

### Today's earnings and guidance

Query: "Which S&P 500 or large-cap growth names report earnings before the open today, and what was the headline result?" Then drill into surprises with raised guidance — those are entry candidates by `strategy.md`'s default rules.

### Watchlist refresh

Surface 3–5 candidates that meet entry signals. For each, capture:

- Symbol and current price.
- The catalyst (earnings beat, guide raise, M&A, secular thesis confirmation).
- One-line thesis.
- One-line risk.
- Citation.

## Citations

Every Perplexity-sourced fact in `memory/research-log.md` must include a citation marker — at minimum the publication name and date. Long URLs are fine in the log; they are useful for the user reading transcripts.

## What not to do

- Do not query Perplexity for trade signals. Perplexity surfaces information; the buy/sell decision lives in `skills/trade-decision.md`.
- Do not paste long article bodies into `research-log.md`. Summarise in one to three lines per item.
- Do not retry on rate-limit indefinitely. One retry after 30 seconds, then skip and journal the gap.
