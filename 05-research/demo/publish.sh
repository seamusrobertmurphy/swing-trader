#!/usr/bin/env bash
# Add a run's record to the gh-pages branch, settle due tickets, rebuild the
# index, and push. Several runs can finish at once, so a rejected push starts
# again from the branch as it now stands rather than merging.
#
#   bash 05-research/demo/publish.sh <folder of new data, or ""> "<commit message>"
set -euo pipefail
SRC="${1:-}"; MSG="${2:-demo data}"
ROOT="$(git rev-parse --show-toplevel)"
PAGES="$ROOT/../pages"
git config --global user.name "swing-trader demo"
git config --global user.email "41898282+github-actions[bot]@users.noreply.github.com"
git fetch -q origin gh-pages
git worktree add -q --detach "$PAGES" origin/gh-pages
cd "$PAGES"
for i in 1 2 3 4 5 6; do
  git fetch -q origin gh-pages
  git reset -q --hard origin/gh-pages
  mkdir -p data/runs
  if [ -n "$SRC" ] && ls "$ROOT/$SRC"/runs/*.json >/dev/null 2>&1; then
    cp "$ROOT/$SRC"/runs/*.json data/runs/
  fi
  # The newest scan, which replaces the one before.
  if [ -n "$SRC" ] && [ -f "$ROOT/$SRC/scan/latest.json" ]; then
    mkdir -p data/scan
    cp "$ROOT/$SRC/scan/latest.json" data/scan/latest.json
  fi
  # Each run's own model pictures, one folder a run.
  for d in "$ROOT/$SRC"/runs/*/; do
    if [ -d "$d" ]; then cp -R "$d" data/runs/; fi
  done
  python "$ROOT/03-inputs/demo_mark.py" settle data
  git add -A data
  if git diff --cached --quiet; then echo "nothing to publish"; exit 0; fi
  git commit -q -m "$MSG"
  if git push -q origin HEAD:gh-pages; then echo "published"; exit 0; fi
  sleep $((i * 7))
done
echo "could not push after six tries" >&2
exit 1
