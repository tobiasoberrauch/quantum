#!/bin/bash
# Sequential fresh processes, 6 workers each. Results append to results/runs.jsonl.
V=/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/work/frontier_1104/verify_invsqrt
PY=/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/.venv/bin/python
cd "$V/results"
A=$V/artifact_copy/invsqrt.kmb
B=$V/artifact_copy/baseline_af469847.kmb
for s in notebook-verification adversarial-check-1; do "$PY" -I -B "$V/fresh_verify.py" "$A" "$s" >> runs.jsonl 2>> err.log; done
"$PY" -I -B "$V/fresh_verify.py" "$A" adversarial-stress-small 65536 1024 >> runs.jsonl 2>> err.log
for s in notebook-verification adversarial-check-1; do "$PY" -I -B "$V/fresh_verify.py" "$B" "$s" >> runs.jsonl 2>> err.log; done
for s in adversarial-check-2 adversarial-check-3; do "$PY" -I -B "$V/fresh_verify.py" "$A" "$s" >> runs.jsonl 2>> err.log; done
echo done >> runs.jsonl.done
