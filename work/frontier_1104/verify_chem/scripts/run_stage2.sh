#!/bin/bash
Q=/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum
V=$Q/work/frontier_1104/verify_chem
T=$(cat $V/stamp)
cd $V
PC=$V/pyc_$T
PY=($Q/.venv/bin/python -I -B -X pycache_prefix=$PC)
PC2=$V/pyc2_$T; mkdir -p $PC2
PY2=($Q/.venv-chem/bin/python -I -B -X pycache_prefix=$PC2)
S=scripts/verify_fresh.py; R=results; FD=copy_final_$T; BD=copy_base_$T
"${PY[@]}" $S $FD adversarial-check-2 "" $R/final_adv2.json >/dev/null 2>$R/final_adv2.err &
"${PY[@]}" $S $FD "" "" $R/final_empty.json >/dev/null 2>$R/final_empty.err &
"${PY[@]}" $S $FD adversarial-check-3 1024 $R/final_adv3_1024.json >/dev/null 2>$R/final_adv3_1024.err &
VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 "${PY[@]}" $S $FD notebook-verification "" $R/final_nb_1thread.json >/dev/null 2>$R/final_nb_1thread.err &
"${PY2[@]}" $S $FD notebook-verification "" $R/final_nb_py313.json >/dev/null 2>$R/final_nb_py313.err &
"${PY[@]}" scripts/exact_branch.py $FD 3 20261105 > $R/exact_final.txt 2>&1 &
wait
"${PY[@]}" scripts/indep_sim.py $FD 64 1234 $R/indep_final_64.json >/dev/null 2>$R/indep_final_64.err &
"${PY[@]}" scripts/indep_sim.py $FD 256 98765 $R/indep_final_256.json >/dev/null 2>$R/indep_final_256.err &
"${PY[@]}" scripts/indep_sim.py $BD 64 555 $R/indep_base_64.json >/dev/null 2>$R/indep_base_64.err &
"${PY[@]}" scripts/exact_branch.py $BD 1 7 > $R/exact_base.txt 2>&1 &
wait
