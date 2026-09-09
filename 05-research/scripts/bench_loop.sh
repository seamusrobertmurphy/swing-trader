#!/bin/bash
# Run the bench eval and the configuration sweep, over and over, across
# conditions, so a difference between configurations is tested against more than
# one slice of the market.
#
#     05-research/scripts/bench_loop.sh              # one full pass over every condition
#     05-research/scripts/bench_loop.sh --cycles 4   # four passes
#     05-research/scripts/bench_loop.sh --list       # show the conditions and exit
#
# Each cycle runs the acceptance checks first and stops the cycle if they fail,
# because a sweep whose metrics have regressed is worse than no sweep: it writes
# a record that looks the same and means something else.
#
# The conditions vary the things the sweep cannot vary on its own, the symbols
# and the rows and the feature families, because six configurations agreeing on
# one slice of one panel is one observation, not six.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="$REPO/.venv/bin/python"
CYCLES=1
LIST=0

while [ $# -gt 0 ]; do
  case "$1" in
    --cycles) CYCLES="$2"; shift 2 ;;
    --list)   LIST=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

# name | symbols | rows | families | repeats
CONDITIONS=(
  "three-coins-wide|LINK/USDT LTC/USDT MATIC/USDT|12000|f_btc_ f_st_ f_wc_|3"
  "three-coins-all|LINK/USDT LTC/USDT MATIC/USDT|12000||3"
  "one-coin|LINK/USDT|6000|f_btc_ f_st_ f_wc_|3"
  "eight-coins|LINK/USDT LTC/USDT MATIC/USDT MANA/USDT MASK/USDT MINA/USDT MAGIC/USDT MBOX/USDT|30000|f_btc_ f_st_ f_wc_|3"
  "btc-family-only|LINK/USDT LTC/USDT MATIC/USDT|12000|f_btc_|3"
  "no-btc-family|LINK/USDT LTC/USDT MATIC/USDT|12000|f_st_ f_wc_ f_hr_|3"
)

if [ "$LIST" = "1" ]; then
  echo "Conditions, each swept over all six forest configurations:"
  for c in "${CONDITIONS[@]}"; do
    IFS='|' read -r name syms rows fams reps <<< "$c"
    echo "  $name"
    echo "    symbols  ${syms}"
    echo "    rows     ${rows}, families ${fams:-all}, repeats ${reps}"
  done
  exit 0
fi

[ -x "$PY" ] || { echo "no interpreter at $PY" >&2; exit 1; }
cd "$REPO" || exit 1
LOG="$REPO/04-outputs/AA-evals/logs/bench-loop.log"
mkdir -p "$(dirname "$LOG")"

say () { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

say "loop starting: $CYCLES cycle(s) over ${#CONDITIONS[@]} conditions"

for cycle in $(seq 1 "$CYCLES"); do
  say "cycle $cycle: acceptance checks"
  if ! "$PY" 03-inputs/bench_eval.py >> "$LOG" 2>&1; then
    say "cycle $cycle: ACCEPTANCE CHECKS FAILED, skipping this cycle's sweeps"
    say "  see $LOG and 04-outputs/AA-evals/logs/bench-eval.json"
    continue
  fi
  say "cycle $cycle: checks passed"

  for c in "${CONDITIONS[@]}"; do
    IFS='|' read -r name syms rows fams reps <<< "$c"
    say "cycle $cycle: $name"

    CFG="$REPO/04-outputs/AA-evals/bench/loop-$name.json"
    "$PY" - "$CFG" "$syms" "$rows" "$fams" <<'PYEOF' || { say "  config failed"; continue; }
import sys, pathlib
sys.path.insert(0, "03-inputs")
import bench_config as bc
out, syms, rows, fams = sys.argv[1:5]
cfg = bc.defaults()
cfg["data"].update(market="crypto", frame="slice_4h_40k", bundle="all",
                   symbols=syms, rows=int(rows))
cfg["features"]["families"] = fams.split() if fams.strip() else []
cfg["label"]["horizon_bars"] = 12
cfg["model"].update(estimators=["RF"], class_weight="none")
cfg["split"].update(holdout_days=365, folds=3, scheme="expanding")
cfg["calibration"]["run_calibration"] = False
bc.save(cfg, pathlib.Path(out))
PYEOF

    start=$(date +%s)
    if "$PY" 03-inputs/bench_sweep.py --config "$CFG" --repeats "$reps" >> "$LOG" 2>&1; then
      say "  done in $(( $(date +%s) - start ))s"
    else
      say "  SWEEP FAILED after $(( $(date +%s) - start ))s, see $LOG"
    fi
  done
  say "cycle $cycle complete"
done

say "loop finished"
echo
echo "Records written:"
ls -t "$REPO/04-outputs/AA-evals"/*/bench-sweep-*.md 2>/dev/null | head -12
