#!/bin/bash
# Verhaltens-Referenztest:  golden.sh <main.py> <outdir> [ref-dir]
# Ohne ref-dir: erzeugt die Referenz. Mit ref-dir: vergleicht (Exit 0 = identisch).
MAIN=$(cd "$(dirname "$1")" && pwd)/$(basename "$1"); OUT=$2; REF=$3
R=/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum
A15=$R/runs/agent/autonomous/20261110T145822Z/cycle1/artifacts/a15b0d73f720/invsqrt.kmx
CK2=$R/work/kmx_verify/ck2_in.kmx
CHEM=$R/work/chem_del_and/kmx/angle_k_13.kmx
PY=$R/.venv-chem/bin/python
export LLM_MAX_CALLS=0 LLM_API_URL=http://127.0.0.1:9/x
unset OFFICIAL_VERIFY_CMD REQUIRE_OFFICIAL_VERIFY TRIM_ROTATIONS OPT_MODE
mkdir -p "$OUT" && cd "$OUT" || exit 9
norm() { sed -E 's/[0-9]+\.[0-9]+s/Ns/g; s/\([0-9]+ Simulationsläufe\)//; s#/[^ ]*/##g'; }
run() { name=$1; shift; "$PY" "$MAIN" "$@" 2>&1 | norm > "$name.log"; echo "exit=${PIPESTATUS[0]}" >> "$name.log"; }
S=$(date +%s)
run selftest --selftest
run a15 optimize "$A15" -o a15.kmx --diff a15.diff
run a15_trim optimize "$A15" -o a15_trim.kmx --trim-rotations --no-kickmix --no-deep
run ck2 "$CK2" ck2.kmx ck2.diff
run chem optimize "$CHEM" -o chem.kmx --no-kickmix
run chem_sampled optimize "$CHEM" -o chem_s.kmx --no-kickmix --allow-sampled-facts
run info info "$A15"
run check check "$A15" a15.kmx
run check_bad check "$A15" ck2.kmx
echo "laufzeit=$(( $(date +%s) - S ))s" > timing.txt
[ -z "$REF" ] && { echo "Referenz erzeugt in $OUT ($(cat timing.txt))"; exit 0; }
fail=0
for f in "$REF"/*.log "$REF"/*.kmx "$REF"/*.diff; do
  b=$(basename "$f")
  if ! cmp -s "$f" "$b"; then echo "ABWEICHUNG: $b"; diff "$f" "$b" | head -6; fail=1; fi
done
echo "ref $(cat "$REF/timing.txt") | neu $(cat timing.txt)"
[ $fail = 0 ] && echo "GOLDEN OK" || echo "GOLDEN FAIL"
exit $fail
