#!/usr/bin/env bash
# =============================================================================
# DF-THC lower-rank GPU run — staged, gated launcher (see ALGO_PLAN.md).
#
#   ./run.sh              # full gated pipeline: Stage0 -> Stage1 -> [2 if invalid] -> [3 if valid]
#   ./run.sh --quick      # fastest decision: Stage0 -> Stage1 only  ((130,35) primary)
#   ./run.sh --stage 3    # pass through any train_gpu.py flag after the mode word
#
# Self-contained: detects the repo root two levels up, picks a Python with JAX,
# runs a metrics self-test gate, then the staged trainer. Results land in results/.
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
export QUANTUM_REPO="$REPO"
cd "$HERE"

# --- pick a Python interpreter that has jax ---------------------------------
pick_python() {
  local cand
  for cand in "$REPO/.venv/bin/python" "$(command -v python3 || true)" "$(command -v python || true)"; do
    [ -n "$cand" ] && [ -x "$cand" ] || continue
    if "$cand" -c "import jax" >/dev/null 2>&1; then echo "$cand"; return 0; fi
  done
  return 1
}
PY="$(pick_python)" || { echo "ERROR: no Python with JAX found. pip install -r requirements.txt first." >&2; exit 3; }
echo "[run.sh] python=$PY  repo=$REPO"
echo "[run.sh] JAX backend: $("$PY" -c 'import jax; print(jax.default_backend())' 2>/dev/null || echo '?')"

MODE="${1:-all}"
shift || true

# --- gate: metrics self-test (JAX must match the authoritative numpy path) --
echo "[run.sh] === SELF-TEST GATE ==="
"$PY" train_gpu.py --stage selftest
echo "[run.sh] self-test passed"

case "$MODE" in
  --quick|quick)
    echo "[run.sh] === STAGE 0 (anchor) ==="
    "$PY" train_gpu.py --stage 0 "$@"
    echo "[run.sh] === STAGE 1 (primary 130,35) ==="
    "$PY" train_gpu.py --stage 1 "$@"
    ;;
  --stage)   # explicit single stage passthrough: ./run.sh --stage <n> [flags]
    N="$1"; shift
    echo "[run.sh] === STAGE $N ==="
    "$PY" train_gpu.py --stage "$N" "$@"
    ;;
  all|"")
    echo "[run.sh] === FULL GATED PIPELINE (Stage0 -> 1 -> [2] -> [3]) ==="
    "$PY" train_gpu.py --stage all "$@"
    ;;
  *)
    echo "unknown mode '$MODE' (use: all | quick | --stage <n>)" >&2; exit 4 ;;
esac

echo ""
echo "[run.sh] === DECISION ==="
if [ -f results/DECISION.json ]; then
  "$PY" - <<'EOF'
import json
d = json.load(open("results/DECISION.json"))
print("DECISION:", d.get("decision"))
for k in ("best_shape", "best_ratio", "dGM", "recipe", "reason", "valid_count"):
    if k in d:
        print(f"  {k}: {d[k]}")
EOF
else
  echo "  (no results/DECISION.json yet)"
fi
echo "[run.sh] results dir: $HERE/results"
