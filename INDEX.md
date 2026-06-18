# INDEX.md

File index and build log for the trading-routine repo. Updated at the start and end of every working session.

## Files

| Path                              | Purpose                                                          |
|-----------------------------------|------------------------------------------------------------------|
| `CLAUDE.md`                       | Agent identity, hard rules, boot order, env var contract         |
| `INDEX.md`                        | This file                                                        |
| `README.md`                       | Human-facing project overview, layout, deployment steps          |
| `tasks/TASK_trading-routine-setup-task.md` | Original task brief; do not edit                        |
| `tasks/TASK_quant-principles-addendum.md`  | Extends the original brief with the twelve quant principles |
| `research/synthesis-quant-methods.md` | Distilled quant operating principles, with citations          |
| `research/authoritative-references.md` | Curated reading list for the synthesis                       |
| `research/AQR Words from the Wise Ed Thorp.pdf` | Source: AQR interview with Ed Thorp, January 2018 |
| `research/Ed Thorp's Trading Strategy Explained - Macro Ops.pdf` | Source: Macro Ops profile of Thorp's strategy |
| `research/DynamicRepDerman.pdf`       | Source: Derman and Taleb, Illusions of Dynamic Replication (2005) |
| `research/Black–Scholes model - Wikipedia.pdf` | Source: Wikipedia reference on Black-Scholes              |
| `research/How the Black Scholes Formula uses probability theory ... LinkedIn.pdf` | Source: LinkedIn post on BS probability theory |
| `research/black-scholes-formula-tutorial-01.txt` | Source: BS tutorial video transcript                  |
| `research/black-scholes-formula-tutorial-02.txt` | Source: BS / Thorp documentary transcript             |
| `research/rl-applicability-assessment.md` | Memo: which parts of the imported RL repo map to the brief and which do not |
| `research/equity-feature-adaptation.md`   | Translation of the source indicator design to a US-equity swing feature set |
| `research/rl_reference/README.md`         | Provenance and boundary note for the imported RL source            |
| `research/rl_reference/indicators.py`     | Imported: pandas-ta feature pipeline (RSI, ATR, MA slopes, distances, spread) |
| `research/rl_reference/trading_env.py`    | Imported: Gymnasium env, position-persistent, discrete OPEN/CLOSE/HOLD with SL/TP grid |
| `research/rl_reference/train_agent.py`    | Imported: PPO training, checkpointing, OOS-equity-based selection  |
| `research/rl_reference/test_agent.py`     | Imported: deterministic OOS evaluation harness                     |
| `research/rl_reference/requirements.txt`  | Imported: pinned upstream dependencies, re-encoded UTF-8           |
| `research/rl_reference/transcript-notes.md` | Author's video walkthrough distilled into study notes            |
| `.gitignore`                      | Block secrets, OS cruft, editor files                            |
| `memory/strategy.md`              | Rule set: signals, sizing, exits. Rewritten only on Fridays.     |
| `memory/portfolio.md`             | Current holdings, cash, last-known equity                        |
| `memory/trade-log.md`             | Append-only ledger of every trade with rationale and outcome     |
| `memory/research-log.md`          | Dated research notes from pre-market and ad hoc                  |
| `memory/learnings.md`             | Carry-forward insights and mistakes to avoid                     |
| `memory/weekly-review.md`         | Latest Friday review                                             |
| `routines/pre-market.md`          | 6:00 AM CT — research and draft trade ideas                      |
| `routines/market-open.md`         | 8:30 AM CT — execute drafted trades, set stops                   |
| `routines/midday.md`              | 12:00 PM CT — cut losers, tighten winners                        |
| `routines/market-close.md`        | 3:00 PM CT — mark-to-market, EOD summary to ClickUp              |
| `routines/weekly-review.md`       | 4:00 PM Fri — week review, self-grade, strategy edits            |
| `skills/research.md`              | How to use Perplexity, what to look for                          |
| `skills/trade-decision.md`        | Buy/sell/hold criteria, position-sizing math                     |
| `skills/trade-execute.md`         | Alpaca order placement contract                                  |
| `skills/journal.md`               | How to write back to memory files                                |
| `skills/notify.md`                | ClickUp post format                                              |
| `scripts/alpaca.sh`               | curl wrappers for the Alpaca REST API                            |
| `scripts/perplexity.sh`           | curl wrapper for Perplexity                                      |
| `scripts/clickup.sh`              | curl wrapper for ClickUp                                         |
| `scripts/bootstrap.sh`            | One-shot host-shell setup: git init + first commit               |

## Build log

A running record of work done on this repo. Newest at the top.

### 2026-05-11 — RL repo scanned, imported as reference, integrated by memo

- Scanned `~/repos/ReinforcementTrading_Part_1`: four-file PPO-on-Gymnasium project trained on EURUSD hourly bars with discrete OPEN/CLOSE/HOLD actions across an SL/TP grid.
- Imported the four source files plus a re-encoded `requirements.txt` to `research/rl_reference/`. Wrote a `README.md` documenting provenance and boundary — the runtime does not read this code.
- Wrote `research/rl-applicability-assessment.md`: a memo mapping the source against the twelve principles and the hard rules. The trained agent itself does not belong in the runtime (it shorts, leverages, day-trades, and reward-shapes against the entry price). Three method patterns survive translation: the relative-feature design in `indicators.py`, the OOS-equity-based model selection in `train_agent.py`, and the friction model in `trading_env.py`. Two Friday-review candidates surfaced for the user to pursue or refuse: a backtest harness modelled on the train/test split pattern, and a relative-feature library for the research skill.
- Wrote `research/equity-feature-adaptation.md`: the relative-feature design translated to US equities. Eight technical features expressed as percent or unitless quantities, five fundamental features expressed as within-sub-industry z-scores or differentials against the 10-year Treasury, four market-context features tying to the existing VIX noise filter and the 60-day correlation budget. The note is research-grade, not yet runtime.
- Wrote `research/rl_reference/transcript-notes.md`: distillation of the author's video walkthrough at https://www.youtube.com/watch?v=oW4hgB1vIoY. Connects the spoken explanation to the actual imported files, flags where the spoken parameters (50k timesteps, 60/90/120 SL grid) differ from the current code (600k timesteps, 5–120 SL grid), and preserves the author's own list of limitations.
- No changes to `routines/`, `skills/`, `scripts/`, `memory/`, or the boot order. The integration is research-grade only.

### 2026-05-11 — Quant principles layered onto the brief

- Read the four primary sources in `research/`: the AQR interview with Ed Thorp, the Macro Ops profile, Derman and Taleb's 2005 paper on the illusions of dynamic replication, and the two Black-Scholes tutorial transcripts.
- Wrote `research/synthesis-quant-methods.md`: twelve operating principles distilled from the sources and the canonical literature they rest on (Kelly, Markowitz, Fama-French, Jegadeesh-Titman, Carhart, Asness-Moskowitz-Pedersen, Ilmanen, Taleb, Mandelbrot, Tversky-Kahneman, Damodaran, Pedersen). Each principle states the source, the mechanism, and the application to this long-only swing book.
- Wrote `research/authoritative-references.md`: curated reading list, full citations, organised by sub-area (sizing, portfolio theory, market efficiency, derivatives, risk, practitioner accounts, data sources).
- Wrote `tasks/TASK_quant-principles-addendum.md`: extension of the original task brief recording what changes in CLAUDE.md, what changes (proposed) in strategy.md via the next Friday weekly review, and what does not change.
- Edited `CLAUDE.md`: added a Principles section between the identity preamble and the hard rules, and refined the hard rules to encode half-Kelly default sizing inside the 5% cap, the rolling-week drawdown ramp, the 15% gap-risk sizing margin, the anchoring prohibition, the 20% correlation-cluster cap, the VIX noise filter, and the 10% fat-pitch exception with its three required conditions. The original ceilings (5%, 3%, 7%, 10%, 10%) are preserved.
- `memory/strategy.md` deliberately left untouched. The convention reserves it for the Friday weekly-review routine; the addendum sketches the expected translation for that routine to adopt, refine, or reject.

### 2026-05-11 — Strategy seeded

- Filled `memory/strategy.md` with brief-default rules: universe, entry signals (with negative overrides), exit signals, sizing, risk, disallowed list, benchmarks. Change log opened inside the file.

### 2026-05-11 — Repo reorganisation

- User moved `TASK_trading-routine-setup-task.md` from the repo root into a new `tasks/` subfolder. File table above updated.
- No other structural changes. Memory, routine, skill, and script files all in place at original paths.

### 2026-05-11 — Initial scaffold

- Created `CLAUDE.md` with agent identity, hard rules, boot order, env-var contract, commit and notification discipline.
- Created `INDEX.md` (this file).
- Created `README.md` covering layout, env vars by name, routine schedule, deployment steps for Claude Desktop.
- Created `memory/` with starter templates for `strategy.md`, `portfolio.md`, `trade-log.md`, `research-log.md`, `learnings.md`, `weekly-review.md`. Strategy is a skeleton with placeholders, awaiting user fill-in.
- Created `routines/` with five prompt files matching the cron table in the brief.
- Created `skills/` with `research.md`, `trade-decision.md`, `trade-execute.md`, `journal.md`, `notify.md`.
- Created `scripts/` with `alpaca.sh`, `perplexity.sh`, `clickup.sh` as thin curl wrappers reading env vars.
- Added `.gitignore`.
- Attempted local `git init`. The Cowork bash sandbox cannot write to `.git/` on this mount (host enforces immutability). Wrote `scripts/bootstrap.sh` as a one-shot for the user to run from the host shell.

What remains, owned by the user:
- Run `bash scripts/bootstrap.sh` from the host shell to finalise the local git repo.
- Provide Alpaca paper key + secret, Perplexity key, ClickUp token + list ID.
- Fill in `memory/strategy.md` or approve a starter strategy in a future session.
- Create a private GitHub repo, push `main`, wire up Claude Code Routines per the README.
- Smoke-test each of the five routines with **Run Now** before letting cron drive.

## Working agreement

At the start of every session in this repo, the working agent:
1. Reads `CLAUDE.md` and this file end-to-end.
2. Skims the latest entries in `memory/trade-log.md` and `memory/learnings.md` if the user's request touches strategy or trade behaviour.
3. Updates the relevant task list if work is non-trivial.

At the end of every session, the working agent:
1. Updates this file's build log with what was done.
2. Updates `CLAUDE.md`'s build-log section with the same date entry.
3. Commits.
