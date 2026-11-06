#!/bin/bash
cd /Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/work/frontier_1104/chem
OUT=$1; TRIES=${2:-60}; SEED=${3:-0}; KS=${4:-"4 5 6 7 8 9 10 11 12 13 14"}; TMAX=${5:-400}
mkdir -p $OUT
run() { OMP_NUM_THREADS=1 ../../../.venv/bin/python scripts/plan35.py base $1 runs/plans0bd8/plan_$1.txt $OUT --tries $TRIES --seed $SEED --maxsteps 8 --tmax $TMAX > $OUT/log_$1.txt 2>&1; }
for k in $KS; do
  while [ $(jobs -r | wc -l) -ge 5 ]; do sleep 1; done
  run $k &
done
wait
