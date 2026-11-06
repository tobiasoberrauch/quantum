#!/bin/bash
# fetch_set.sh <dataset> <remote_dir> <local_name>: download chem set member by member into its own dir
K=/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/.venv/bin/kaggle
D=/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/work/frontier_1104/downloads/f__$3
mkdir -p "$D"
for m in submission.npz $(seq -f 'angle_k_%g.kmb' 0 14); do
  [ -s "$D/$m" ] && continue
  for try in 1 2 3 4 5 6 7 8; do
    out=$(timeout 300 "$K" datasets download -d "$1" -f "$2/$m" -p "$D" -o -q 2>&1)
    [ -s "$D/$m" ] && break
    [ -s "$D/$m.zip" ] && { /usr/bin/unzip -qo "$D/$m.zip" -d "$D"; rm -f "$D/$m.zip"; break; }
    echo "retry $m $try: $(echo "$out" | tail -1 | cut -c1-120)"; sleep $((30*try))
  done
  sleep 3
done
ls "$D" | wc -l
