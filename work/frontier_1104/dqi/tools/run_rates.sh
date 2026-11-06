#!/bin/zsh
# run_rates.sh <proc> <nbatches> — accumulates counts in out/rates_<proc>.u32, failures in out/rates_<proc>.log
cd /Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/work/frontier_1104/dqi
P=$1; N=$2; PY=/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/.venv/bin/python
for ((i=0;i<N;i++)); do
  S=$((910000+P*100000+i))
  $PY tools/gen_shots.py base.kmb out/tmp_$P.bin 4096 $S 0.0 >/dev/null
  tools/rates base.kmb out/tmp_$P.bin out/rates_$P.u32 $S >> out/rates_$P.log
done
rm -f out/tmp_$P.bin
echo done > out/rates_$P.done
