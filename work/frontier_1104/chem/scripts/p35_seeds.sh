#!/bin/bash
# multi-seed, keep per-k best by emitted T. usage: p35_seeds.sh <root> <seedlist> <tries> <tmax> <ks> [partition k override]
cd /Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/work/frontier_1104/chem
ROOT=$1; SEEDS=$2; TRIES=$3; TMAX=$4; KS=$5; NP=${6:-5}
for s in $SEEDS; do
for k in $KS; do
  while [ $(jobs -r | wc -l) -ge $NP ]; do sleep 1; done
  OUT=$ROOT/s$s
  mkdir -p $OUT
  (OMP_NUM_THREADS=1 ../../../.venv/bin/python scripts/plan35.py base $k runs/plans0bd8/plan_$k.txt $OUT --tries $TRIES --seed $s --maxsteps 10 --tmax $TMAX > $OUT/log_$k.txt 2>&1) &
done
done
wait
