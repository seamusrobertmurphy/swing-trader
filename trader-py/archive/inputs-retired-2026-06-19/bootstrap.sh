#!/usr/bin/env bash
# scripts/bootstrap.sh — one-shot local setup the agent could not run itself.
#
# The Cowork sandbox could not write to /Users/seamus/repos/trader-swing/.git
# during the initial scaffold (host enforces immutability on .git/ from inside
# the sandbox). Run this from your host shell once to finish the local repo:
#
#   bash scripts/bootstrap.sh
#
# It is idempotent: re-running it is safe. The script:
#   1. removes any half-initialised .git directory
#   2. git init -b main
#   3. configures a local user.email / user.name (defaults below; override
#      with env vars GIT_USER_EMAIL / GIT_USER_NAME)
#   4. stages and commits the scaffold
#   5. prints next steps (remote, push, Claude Code Routine wiring)

set -euo pipefail

cd "$(dirname "$0")/.."

# 1. Clean a half-state .git if present and owned by us.
if [[ -d .git ]]; then
  echo "Removing existing .git directory…"
  rm -rf .git
fi

# 2. Initialise on main.
git init -b main >/dev/null

# 3. Local identity (does not touch global config).
git config user.email "${GIT_USER_EMAIL:-agent@trading-routine.local}"
git config user.name  "${GIT_USER_NAME:-trading-routine-agent}"

# 4. Stage and commit.
git add -A
if git diff --cached --quiet; then
  echo "Nothing to commit — working tree clean."
else
  git commit -m "initial scaffold: CLAUDE.md, INDEX.md, README, memory/, routines/, skills/, scripts/" >/dev/null
fi

echo
echo "Done. Current state:"
git log --oneline
echo
echo "Next steps:"
echo "  1. Create a private GitHub repo named 'trading-routine'."
echo "  2. git remote add origin git@github.com:<you>/trading-routine.git"
echo "  3. git push -u origin main"
echo "  4. In Claude Desktop, create the 'trading' cloud environment with the"
echo "     env vars listed in README.md, then wire up the five routines from"
echo "     routines/*.md. See README.md → Deployment."
