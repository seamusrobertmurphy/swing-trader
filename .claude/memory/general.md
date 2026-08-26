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
