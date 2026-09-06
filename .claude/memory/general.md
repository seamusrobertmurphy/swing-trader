# General

- 2026-08-25: Alpaca keys are in the macOS Keychain and reached through
  `inputs/config.py`, not through environment variables. `ALPACA_API_KEY` and
  friends read empty in a plain shell and that is normal; `alpaca_check.py`
  falls back to the Keychain. Matters because a missing-variable check on the
  environment alone will wrongly abort.

- 2026-08-25: Every report under `outputs/AA-evals/` opens with the "Where the
  money actually is" block and holds its plain-word density throughout.
  Operator instruction; spec and figure provenance in
  `outputs/AA-evals/REPORT-TEMPLATE.md`. Matters because the previous house
  style used internal shorthand (`spread %/mo`, `abs`, `sel`, SURVIVES) that
  the person making the decision could not read.

- 2026-08-26: Scheduling on this machine must use launchd user agents, never
  cron. A cron probe run at 15:55 PDT returned rc=44 from `security
  find-generic-password` and `config.ALPACA_API_KEY` came back an empty string:
  cron runs outside the login session and cannot read the login Keychain, where
  every Alpaca key lives. The failure is silent, so a cron schedule would have
  looked installed and never traded. launchd agents run in the GUI session and
  read the Keychain fine (verified). Installer, both plists and a verifier are
  in `scripts/install_schedule.sh` and `scripts/launchd/`.

- 2026-08-26: macOS privacy control (TCC) blocks background jobs from READING
  the portable SSD, which is where this repo lives. Measured precisely under
  launchd: stat a directory OK, list a directory BLOCKED, read a file BLOCKED,
  execute a binary OK, Keychain OK. So a scheduled agent dies with "Operation
  not permitted" (exit 126) before running a line of our code. The one fix is
  a manual grant: System Settings > Privacy & Security > Full Disk Access, add
  `/bin/bash`. Until that is done the schedule is installed and inert. The
  durable fix is moving the repo to the internal disk, which also removes the
  exFAT AppleDouble problem in CLAUDE.md. Check state with
  `./scripts/install_schedule.sh verify`.

- 2026-08-26: A verifier that tests the wrong operation is worse than none. The
  first version of the TCC probe used `ls` on a repo file and PASSED while the
  agents were dying, because stat is permitted and read is not. It now attempts
  a real read (`head -c 1`). Any future permission check must exercise the
  operation the real job performs.

- 2026-08-26: The repo is portable as of this date and the claim was tested,
  not asserted: a shallow clone (251MB) with a fresh venv built from
  `requirements.txt` alone (261MB, against 44GB on the Mac), no Keychain on the
  PATH, and credentials supplied as environment variables, ran
  `schedule_tick.py` and reached Alpaca. Blockers removed were a gitignored
  `inputs/config.py`, an unconditional `security` call that raises on Linux, a
  missing requirements file, and hard-coded `/Volumes/PortableSSD` paths in
  every script. Steps in `MIGRATE.md`.

- 2026-08-26: Scheduling is now ONE tick (`scripts/tick.sh` ->
  `inputs/schedule_tick.py`) every 20 minutes, which asks Alpaca's clock and
  calendar what is due, rather than wall-clock cron/launchd entries. A
  wall-clock schedule encodes a timezone, and moving the machine breaks it
  silently: the job runs, the market is shut, nothing trades, no error appears.
  `install_schedule.sh` fills launchd or systemd templates per OS and verifies.

- 2026-08-26: Two timing traps in the Alpaca clock, both hit while building the
  tick. `clock.next_close` is TOMORROW's close while the market is shut, so any
  "minutes since the close" test built on it can never fire. And a hard-coded
  390-minute session is three hours wrong on a half day. Both must come from
  `get_calendar`. Separately, the daily report must be keyed on the EXCHANGE
  date: after 20:00 New York the UTC date has already rolled and the report is
  misfiled, then written again the next evening.


- 2026-09-05: the daily and execution reports were filed under the UTC date, so
  anything written after 20:00 New York landed in the next day's folder and
  carried the next day's stamp in its filename. The dashboard reads that date
  out of the filename (`inputs/dashboard_data.py:401`, `:610`), so Friday
  evening's report was drawn on a Saturday the market was shut. Both stamps now
  come from `America/New_York` (`inputs/alpaca_daily_report.py` main,
  `inputs/alpaca_execution_report.py` line 114). The 2026-08-26 note predicted
  this failure and it had not in fact been fixed; predicting a bug is not
  fixing it.

- 2026-09-05: dead-code audit. Seventeen files removed, none reachable: three
  near-identical notebook runners in `tasks/` carrying the hard-coded
  `/Volumes/PortableSSD` path and the two executed notebooks they wrote,
  `dynamicRenko.py` (imports `stocktrends`, in no requirements file and not
  installed), `tasks/notes.py` (uses `Path`, `subprocess`, `sys` with none
  imported), two scratch files whose own first line said "safe to delete", the
  `archive/` R prototypes, `future_a.html` and `future_b.html` (orphan Quarto
  renders with no source), and a nested directory holding only a backup of the
  docx above it. Plus 20 unused imports and 9 unused locals; `ruff check
  --select F401,F841` is now clean across `inputs/` and `scripts/`. Matters
  because the reference sweep alone would have condemned the pre-registered
  evidence scripts (`equity_weekly_factors.py` and friends show zero inbound
  references because they are run by hand), so unreferenced is not the test;
  cannot-run and self-declared-scratch are.

- 2026-09-05: `.git` was carrying 1.25 GiB of orphaned pack garbage,
  `tmp_pack_LPFaR1` dated 17 August, from an interrupted operation.
  `git gc --prune=now` cleared it and the store went 1.62 to 1.51 GiB packed.
  Worth checking with `git count-objects -vH` after any interrupted push.

- 2026-09-05: `inputs/backtest.py` runs its whole backtest at module top level
  with no `if __name__ == "__main__"` guard, so merely importing it hits the
  live Binance API and writes `breakout_events.csv` into the current directory.
  Nothing imports it and its +10%/-5%/20-day label is the one CLAUDE.md records
  as replaced, so it is a deletion candidate rather than a bug to fix. Kept
  pending the operator's call, along with `inputs/supertrend.py`, the 585-line
  crypto bot that cannot run because `schedule` is not installed.
