#!/bin/zsh
# Auto-evaluation chain for the 1h all-market frame. Lives in tasks/; logs to tasks/.
# Waits for the full-market download to finish, then aggregates flow, builds the full
# dataset, and trains (LightGBM only for the first full pass, since RandomForest does not
# scale to millions of rows). Runs from the project .venv. All steps logged to tasks/auto_eval.log.
# Re-runnable; each step is resumable/idempotent.

cd /Volumes/PortableSSD/Github/day-trader || exit 1
PY=.venv/bin/python
LOG=tasks/auto_eval.log

echo "[wait]      $(date)  waiting for the download to finish..." >> $LOG
while pgrep -f "flow_data.py --interval 1h --all-market" >/dev/null; do sleep 60; done
echo "[wait]      $(date)  download process gone; proceeding." >> $LOG

echo "[aggregate] $(date)  building flow_1h.csv from the archives" >> $LOG
$PY inputs/binance-data/flow_data.py --interval 1h --all-market --skip-download >> $LOG 2>&1
echo "[aggregate] $(date)  exit $?" >> $LOG

echo "[build]     $(date)  building dataset_1h_allmarket.csv (full market)" >> $LOG
$PY inputs/build_dataset_1h.py >> $LOG 2>&1
echo "[build]     $(date)  exit $?" >> $LOG

echo "[train]     $(date)  training (LightGBM) + AA-evals record" >> $LOG
$PY inputs/train_model_1h.py --models LightGBM >> $LOG 2>&1
echo "[train]     $(date)  exit $?" >> $LOG

echo "[done]      $(date)  auto-evaluation complete. See outputs/AA-evals/evaluation-scores.md" >> $LOG
