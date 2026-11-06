#!/bin/bash
# Replan coded loaders in parallel with own-k partition.
cd /Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/work/frontier_1104/chem
OUT=$1; SECS=${2:-30}; SEED=${3:-0}
mkdir -p $OUT
run() { OMP_NUM_THREADS=1 ../../../.venv/bin/python scripts/replan.py base $1 runs/plans0bd8/plan_$1.txt $OUT --secs $SECS --seed $SEED > $OUT/log_$1.txt 2>&1; }
for k in 4 5 6 7 8 9 10 11 12 13 14; do
  while [ $(jobs -r | wc -l) -ge 5 ]; do sleep 1; done
  run $k &
done
wait
