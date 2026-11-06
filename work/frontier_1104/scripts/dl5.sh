#!/bin/bash
# Sequential, rate-limit-friendly downloader. Each source gets its own new dir.
ROOT=/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum
K=$ROOT/.venv/bin/kaggle
DL=$ROOT/work/frontier_1104/downloads
PAT='^(submission\.zip|[^/]*\.json|[^/]*\.sha256|[^/]*\.md|[^/]*\.txt)$'
kout() { # ref
  local ref=$1; local s=${ref//\//__}; local d=$DL/k5__$s
  [ -f "$d/.done" ] && return
  mkdir -p "$d"
  for try in 1 2 3 4 5 6; do
    out=$(timeout 900 "$K" kernels output "$ref" -p "$d" --page-size 200 --file-pattern "$PAT" -q -o 2>&1); rc=$?
    if echo "$out" | grep -qi 'rate limit\|429'; then echo "RATE $ref try $try"; sleep $((60*try)); continue; fi
    echo "kernel $ref rc=$rc $(du -sh "$d" | cut -f1) :: $(echo "$out" | tail -1 | cut -c1-150)"
    [ $rc -eq 0 ] && touch "$d/.done"
    break
  done
  sleep 8
}
dset() { # ref
  local ref=$1; local s=${ref//\//__}; local d=$DL/d5__$s
  [ -f "$d/.done" ] && return
  mkdir -p "$d"
  for try in 1 2 3 4 5 6; do
    out=$(timeout 1500 "$K" datasets download -d "$ref" -p "$d" -q -o 2>&1); rc=$?
    if echo "$out" | grep -qi 'rate limit\|429'; then echo "RATE $ref try $try"; sleep $((60*try)); continue; fi
    echo "dataset $ref rc=$rc $(du -sh "$d" | cut -f1) :: $(echo "$out" | tail -1 | cut -c1-150)"
    [ $rc -eq 0 ] && touch "$d/.done"
    break
  done
  sleep 8
}
while read -r kind ref; do
  [ -z "$kind" ] && continue
  case "$kind" in k) kout "$ref";; d) dset "$ref";; esac
  df -g "$DL" | tail -1 | awk '{print "free GB:", $4}'
done < "$1"
echo ALLDONE
