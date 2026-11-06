#!/bin/zsh
# Progressive rank reduction from the current best, refitting at each step.
# Tracks the solution manifold (small change per step -> easy convergence)
# instead of jumping from a far truncation.
set -e
cd /Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum
PY=.venv/bin/python
W=work/chem_lower_rank
BEST=work/frontier_scan/mwa2_unpacked/dfthcsos/submission.npz
EP=${EP:-1500}
LR=${LR:-1e-3}
RHO=${RHO:-1e-4}

step() { # $1=M $2=G $3=start $4=out $5=tag
  echo "=== $5 : ($1,$2) start=$(basename $3) ==="
  $PY $W/train_probe.py "$1" "$2" "$EP" --lr $LR --rho $RHO --gap-floor 3.9152 \
      --start "$3" --out "$4" --print-int 200 2>&1 | tee "$W/log_$5.txt"
}

# Stage 1: reduce G one copy at a time, keep M=143.
prev=$BEST
for G in 38 37 36 35; do
  out=$W/prog_143_$G.npz
  step 143 $G $prev $out g$G
  prev=$out
done

# Stage 2: from the lowest-G table, reduce M (overcomplete width) at fixed G.
base=$prev   # (9,143,35)
for M in 134 130 126; do
  out=$W/prog_${M}_35.npz
  step $M 35 $base $out m${M}
  base=$out
done

echo "ALL_PROGRESSIVE_DONE"
