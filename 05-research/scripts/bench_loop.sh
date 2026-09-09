#!/bin/bash
# Sweep the forest configurations across every axis, until a deadline.
#
#     05-research/scripts/bench_loop.sh --hours 12
#     05-research/scripts/bench_loop.sh --list      # the schedule, then exit
#     05-research/scripts/bench_loop.sh --hours 1 --digest-every 5
#
# WHY THIS IS NOT A REPEAT LOOP. The first version ran the same six conditions
# three times over. The sweep is deterministic to ten decimals, proved by
# bench_eval check 7 on 8 September, so cycles two and three reproduced cycle one
# exactly and added nothing but three seconds of checks. Time spent running is
# only worth anything if each run asks something the last one did not.
#
# So the schedule is a grid over the axes the sweep cannot vary on its own:
#
#   condition    the symbols, the rows and the feature families
#   folds        3, 5 and 8. On 8 September the fold count moved held-out error
#                more than any hyperparameter in the grid did, 0.4840 against
#                0.4894, while the whole grid spanned 0.033. It has never been
#                varied alongside the configurations.
#   holdout      365 and 545 days. A single blind year is one regime.
#   weight       balanced and none. The balanced weight cost two thirds of the
#                calibration error in September and nobody has asked what it
#                costs the ranking.
#
# Six by three by two by two is 72 sweeps of six configurations each. The order
# is interleaved rather than nested, so an early stop still leaves every axis
# represented instead of six conditions at one fold count.
#
# A digest is written every few sweeps, so there is one readable table at any
# moment rather than 72 records nobody will open.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="$REPO/.venv/bin/python"
HOURS=12
DIGEST_EVERY=6
LIST=0

while [ $# -gt 0 ]; do
  case "$1" in
    --hours)        HOURS="$2"; shift 2 ;;
    --digest-every) DIGEST_EVERY="$2"; shift 2 ;;
    --list)         LIST=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

# name | symbols | rows | families
CONDITIONS=(
  "three-wide|LINK/USDT LTC/USDT MATIC/USDT|12000|f_btc_ f_st_ f_wc_"
  "three-all|LINK/USDT LTC/USDT MATIC/USDT|12000|"
  "one-coin|LINK/USDT|6000|f_btc_ f_st_ f_wc_"
  "eight-coins|LINK/USDT LTC/USDT MATIC/USDT MANA/USDT MASK/USDT MINA/USDT MAGIC/USDT MBOX/USDT|30000|f_btc_ f_st_ f_wc_"
  "btc-only|LINK/USDT LTC/USDT MATIC/USDT|12000|f_btc_"
  "no-btc|LINK/USDT LTC/USDT MATIC/USDT|12000|f_st_ f_wc_ f_hr_"
)
FOLDS=(3 5 8)
HOLDOUTS=(365 545)
WEIGHTS=(none balanced)

# Interleaved: the slowest-moving axis is the condition, so stopping early still
# leaves every fold count, every holdout and both weights represented.
SCHEDULE=()
for f in "${FOLDS[@]}"; do
  for h in "${HOLDOUTS[@]}"; do
    for w in "${WEIGHTS[@]}"; do
      for c in "${CONDITIONS[@]}"; do
        SCHEDULE+=("$c|$f|$h|$w")
      done
    done
  done
done

if [ "$LIST" = "1" ]; then
  echo "${#SCHEDULE[@]} sweeps of six configurations each."
  echo "  conditions ${#CONDITIONS[@]}, folds ${FOLDS[*]}, holdouts ${HOLDOUTS[*]} days, weights ${WEIGHTS[*]}"
  echo
  i=0
  for s in "${SCHEDULE[@]}"; do
    IFS='|' read -r name syms rows fams f h w <<< "$s"
    i=$((i+1))
    printf '  %2d  %-12s folds %s  holdout %s  weight %-8s  rows %s  families %s\n' \
      "$i" "$name" "$f" "$h" "$w" "$rows" "${fams:-all}"
    [ "$i" -ge 12 ] && { echo "  ... and $(( ${#SCHEDULE[@]} - 12 )) more"; break; }
  done
  exit 0
fi

[ -x "$PY" ] || { echo "no interpreter at $PY" >&2; exit 1; }
cd "$REPO" || exit 1
LOG="$REPO/04-outputs/AA-evals/logs/bench-loop.log"
mkdir -p "$(dirname "$LOG")"
DEADLINE=$(( $(date +%s) + $(printf '%.0f' "$(echo "$HOURS * 3600" | bc)") ))

say () { echo "[$(date '+%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

say "loop starting: ${#SCHEDULE[@]} sweeps, deadline $(date -r "$DEADLINE" '+%m-%d %H:%M')"

if ! "$PY" 03-inputs/bench_eval.py >> "$LOG" 2>&1; then
  say "ACCEPTANCE CHECKS FAILED before anything ran. Nothing swept."
  say "  see $LOG and 04-outputs/AA-evals/logs/bench-eval.json"
  exit 1
fi
say "acceptance checks passed"

done_n=0; failed=0; pass=1
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  say "pass $pass over the schedule"
  for s in "${SCHEDULE[@]}"; do
    [ "$(date +%s)" -ge "$DEADLINE" ] && break
    IFS='|' read -r name syms rows fams f h w <<< "$s"
    tag="${name}-f${f}-h${h}-${w}"
    say "$tag"

    CFG="$REPO/04-outputs/AA-evals/bench/loop-$tag.json"
    if ! "$PY" - "$CFG" "$syms" "$rows" "$fams" "$f" "$h" "$w" "$pass" <<'PYEOF' >> "$LOG" 2>&1
import sys, pathlib
sys.path.insert(0, "03-inputs")
import bench_config as bc
out, syms, rows, fams, folds, holdout, weight, seed = sys.argv[1:9]
cfg = bc.defaults()
cfg["data"].update(market="crypto", frame="slice_4h_40k", bundle="all",
                   symbols=syms, rows=int(rows))
cfg["features"]["families"] = fams.split() if fams.strip() else []
cfg["label"]["horizon_bars"] = 12
cfg["model"].update(estimators=["RF"], class_weight=weight)
cfg["split"].update(holdout_days=int(holdout), folds=int(folds), scheme="expanding")
cfg["calibration"]["run_calibration"] = False
bc.save(cfg, pathlib.Path(out))
PYEOF
    then say "  config failed"; failed=$((failed+1)); continue; fi

    start=$(date +%s)
    if "$PY" 03-inputs/bench_sweep.py --config "$CFG" --repeats 3 >> "$LOG" 2>&1; then
      done_n=$((done_n+1))
      say "  done in $(( $(date +%s) - start ))s  [$done_n done, $failed failed]"
    else
      failed=$((failed+1))
      say "  SWEEP FAILED after $(( $(date +%s) - start ))s  [$done_n done, $failed failed]"
    fi

    if [ "$DIGEST_EVERY" -gt 0 ] && [ $(( done_n % DIGEST_EVERY )) -eq 0 ] && [ "$done_n" -gt 0 ]; then
      "$PY" 03-inputs/bench_digest.py >> "$LOG" 2>&1 && say "  digest updated"
    fi
  done
  pass=$((pass+1))
  # A second pass over the same schedule would repeat deterministic work, so
  # stop rather than burn the remaining hours on it.
  say "schedule exhausted after $done_n sweeps; nothing left that has not been asked"
  break
done

"$PY" 03-inputs/bench_digest.py >> "$LOG" 2>&1 && say "final digest written"
say "loop finished: $done_n sweeps, $failed failed"
