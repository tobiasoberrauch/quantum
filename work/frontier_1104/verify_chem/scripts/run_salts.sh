#!/bin/bash
# Fresh process per verifier call, existing __pycache__ bypassed (compiled from source into an empty prefix).
Q=/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum
V=$Q/work/frontier_1104/verify_chem
T=$(cat $V/stamp)
cd $V
PC=$V/pyc_$T; mkdir -p $PC
PY=($Q/.venv/bin/python -I -B -X pycache_prefix=$PC)
S=scripts/verify_fresh.py; R=results; FD=copy_final_$T; BD=copy_base_$T
"${PY[@]}" $S $FD notebook-verification "" $R/final_nb.json >/dev/null 2>$R/final_nb.err &
"${PY[@]}" $S $FD adversarial-check-1 "" $R/final_adv1.json >/dev/null 2>$R/final_adv1.err &
"${PY[@]}" $S $BD notebook-verification "" $R/base_nb.json >/dev/null 2>$R/base_nb.err &
"${PY[@]}" $S $BD adversarial-check-1 "" $R/base_adv1.json >/dev/null 2>$R/base_adv1.err &
"${PY[@]}" $S $Q/.kaggle_data/competition/sample_submission/dfthcsos notebook-verification "" $R/sample_nb.json >/dev/null 2>$R/sample_nb.err &
wait
