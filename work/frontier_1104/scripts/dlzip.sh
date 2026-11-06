#!/bin/bash
# Download a dataset's archive WITHOUT unzipping; circuits are read via zipfile.
K=/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/.venv/bin/kaggle
DL=/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/work/frontier_1104/downloads
for ref in "$@"; do
  d=$DL/d__${ref//\//__}; mkdir -p "$d"
  for try in 1 2 3 4 5 6 7 8; do
    out=$(timeout 3000 "$K" datasets download -d "$ref" -p "$d" -q 2>&1); rc=$?
    if echo "$out" | grep -qi 'rate limit\|429'; then echo "RATE $ref $try"; sleep $((60*try)); continue; fi
    echo "$ref rc=$rc $(du -sh "$d" | cut -f1) :: $(echo "$out" | tail -1 | cut -c1-200)"; break
  done
  df -g "$DL" | tail -1 | awk '{print "free GB:", $4}'
done
echo ALLDONE
