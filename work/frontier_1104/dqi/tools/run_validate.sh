#!/bin/zsh
# run_validate.sh <cands.tsv> <tagprefix> <proc> <nbatches> <frac_uni> <seedbase>
cd /Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/work/frontier_1104/dqi
CANDS=$1; TAG=$2; P=$3; N=$4; FR=$5; SB=$6; PY=/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/.venv/bin/python
for ((i=0;i<N;i++)); do
  S=$((SB+P*10000+i))
  $PY tools/gen_shots.py base.kmb out/tmpv_$TAG$P.bin 4096 $S $FR >/dev/null
  tools/validate base.kmb out/tmpv_$TAG$P.bin $CANDS out/${TAG}_mis_$P.u32 out/${TAG}_fires_$P.u32
done
rm -f out/tmpv_$TAG$P.bin
