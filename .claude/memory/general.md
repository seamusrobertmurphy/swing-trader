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

