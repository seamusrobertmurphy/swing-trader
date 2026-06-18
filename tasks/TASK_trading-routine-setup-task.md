# Task: Build a 24/7 AI Trading Agent in Claude Code

## Goal

Stand up a Claude Code project named `trading-routine` that runs on a schedule via Claude Code Routines, places swing/long-horizon equity trades through Alpaca, researches via Perplexity, journals to local memory files, and posts an end-of-day summary to ClickUp. Objective: beat the S&P 500 over a multi-month horizon. Not day trading. Not options. Not crypto.

Start in Alpaca paper trading mode. Live capital is a later toggle.

## Stack

- Model: Claude Opus 4.7.
- Scheduler: Claude Code Routines (remote), running off a GitHub repo so state persists across runs.
- Brokerage: Alpaca REST API (paper first).
- Research: Perplexity API. Do not use native web search.
- Notifications: ClickUp API.
- Hosting: a private GitHub repo named `trading-routine`. Routines clone it, work in a cloud sandbox, and must push commits back to `main` so the next run sees the updated state.

## Repo layout

```
trading-routine/
  CLAUDE.md                 # agent identity, hard rules, boot order
  README.md
  memory/
    strategy.md             # the rules: signals, position sizing, exit criteria
    portfolio.md            # current holdings, cash, last-known equity
    trade-log.md            # every trade taken, with rationale + outcome
    research-log.md         # dated research notes
    learnings.md            # carry-forward insights, mistakes to avoid
    weekly-review.md        # latest Friday review
  routines/
    pre-market.md           # cron + prompt
    market-open.md
    midday.md
    market-close.md
    weekly-review.md
  skills/
    research.md             # how to use Perplexity, what to look for
    trade-decision.md       # buy/sell/hold criteria, position sizing math
    trade-execute.md        # Alpaca order placement contract
    journal.md              # how to write back to memory files
    notify.md               # ClickUp post format
  scripts/
    alpaca.sh               # thin curl wrappers, read env vars
    perplexity.sh
    clickup.sh
```

## Routine schedule (US Central, weekdays only)

| Routine        | Cron              | Job                                                                                          |
|----------------|-------------------|----------------------------------------------------------------------------------------------|
| pre-market     | 6:00 AM Mon–Fri   | Research overnight catalysts. Draft trade ideas. Write to `research-log.md`. Silent unless urgent. |
| market-open    | 8:30 AM Mon–Fri   | Execute the drafted trades. Set 10% trailing stops. Append to `trade-log.md`. Notify only if a trade is placed. |
| midday         | 12:00 PM Mon–Fri  | Cut positions down −7% from cost. Tighten stops on winners. Append to `trade-log.md`.        |
| market-close   | 3:00 PM Mon–Fri   | Mark-to-market, update `portfolio.md`, write daily journal entry, post EOD summary to ClickUp. |
| weekly-review  | 4:00 PM Fri       | Full week review: P&L vs SPY, what worked, what didn't, proposed adjustments to `strategy.md`. Post to ClickUp. Self-grade. |

## Per-routine behaviour (mandatory for all five)

1. **Boot**: read `CLAUDE.md`, then `memory/strategy.md`, `memory/portfolio.md`, `memory/trade-log.md` (last 30 entries), `memory/learnings.md`. Do not skip this step.
2. **Work**: do the routine-specific job using the skills in `skills/`.
3. **Journal**: append findings, trades, and notes to the appropriate memory file. Never overwrite history; only append.
4. **Commit**: `git add -A && git commit -m "<routine>: <one-line summary>" && git push origin main`. Without this, the next run is blind.
5. **Notify**: post a short summary to ClickUp using `scripts/clickup.sh`. Pre-market and midday: silent unless urgent or a trade fires.

## Strategy (initial; will evolve)

- Long-only US equities, swing horizon (weeks to months), fundamentals-led.
- No options, no leveraged ETFs, no crypto, no margin.
- Universe: S&P 500 plus large-cap growth names with positive operating cash flow.
- Entry signals: positive earnings surprise plus raised guidance, durable secular thesis confirmed in research, technical breakout from a base (high level — no candle-pattern day trading).
- Exit signals: thesis break, −7% from cost (hard stop), 10% trailing stop on winners.
- Position sizing: 5% of portfolio equity per new position, max.
- Cadence: max 3 new positions per week.
- Cash floor: keep at least 10% in cash unless conviction is exceptional.
- North star: outperform SPY total return.

Treat the above as defaults. The agent may propose changes in the weekly review but cannot self-modify `strategy.md` mid-week; only the weekly-review routine may rewrite it.

## Guardrails (hard rules, encode in CLAUDE.md)

- Paper trading until the user flips a `LIVE_TRADING` env var to `true`.
- Max 5% of portfolio per position.
- Daily loss cap: if realised + unrealised intraday drawdown exceeds 3% of equity, halt new orders for the day and notify.
- Never short.
- Never use options.
- Never increase a losing position (no averaging down).
- Always read memory before acting. Always commit memory before exiting.
- If the run is uncertain, do nothing and journal the uncertainty.

## Secrets

All credentials live in the Claude Code remote routine's cloud environment, not in the repo, not in a `.env`. Required environment variables, exact spelling:

- `ALPACA_API_KEY`
- `ALPACA_API_SECRET`
- `ALPACA_BASE_URL` (paper: `https://paper-api.alpaca.markets`)
- `PERPLEXITY_API_KEY`
- `CLICKUP_API_TOKEN`
- `CLICKUP_LIST_ID`
- `LIVE_TRADING` (`false` until explicitly flipped)

Every routine prompt must explicitly tell the agent these are in the environment, not in any file.

## Deployment steps (the agent should do these, prompting the user when keys are needed)

1. Scaffold the repo layout above. Create the GitHub repo if it doesn't exist, push initial commit.
2. Write `CLAUDE.md` with identity, hard rules, and boot order.
3. Write the five routine prompt files in `routines/`. Each must (a) state the cron, (b) state the env vars it expects, (c) lay out the read-work-journal-commit-notify sequence.
4. Write the five skill files in `skills/`.
5. Write the three shell helpers in `scripts/` using `curl`, reading env vars.
6. In Claude Desktop, create a remote cloud environment called `trading` with full network access and the seven env vars above filled in.
7. Create five remote routines, one per file in `routines/`, all pointing at the same GitHub repo and the `trading` cloud environment. Model: Claude Opus 4.7.
8. In each routine's permissions, enable **Allow unrestricted branch pushes**.
9. Run each routine once via **Run Now** as a smoke test. Watch the run logs in real time. Confirm: memory was read, intended action taken (or correctly skipped), commit pushed, ClickUp notification received.

## Acceptance criteria

- All five routines run on schedule, weekdays only (weekly-review Friday only), without manual intervention.
- After each run, `git log origin/main` shows a commit from the agent describing what it did.
- `memory/portfolio.md` reflects current Alpaca positions after each market-close run.
- Friday weekly-review posts a ClickUp message containing: current equity, week's P&L, SPY return for the same period, list of trades, self-grade, proposed strategy changes.
- No API keys present anywhere in the repo.
- Paper trading mode active; `LIVE_TRADING=false`.

## Iteration plan

For the first week, the user will read every run's transcript and append corrections to `memory/learnings.md`. The weekly-review routine reads `learnings.md` and proposes edits to `strategy.md`. Strategy edits only land on Fridays.

## Things the user must supply before first run

- The GitHub repo URL (or permission for the agent to create one).
- Alpaca paper-trading key + secret.
- Perplexity API key.
- ClickUp API token and the list ID where notifications should land.
- Starting paper-trading balance, if non-default.
- Any pre-existing strategy notes or trade history to seed `memory/strategy.md` and `memory/trade-log.md`. If none, the agent should propose a starter strategy in plan mode and ask for approval before scaffolding.

## How to use this brief

Open Claude Code in an empty `trading-routine` directory. Paste this entire document as the first message. Ask Claude Code to enter plan mode, read the brief in full, ask any clarifying questions, then scaffold the project end to end. Do not let it exit plan mode until you are 95% confident it knows what to build.
