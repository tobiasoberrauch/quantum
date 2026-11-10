#!/bin/bash
# qvc_watchdog.sh — bounded autonomous curate re-harvest (scheduled via launchd).
#
# One pass: FORCE re-fetch the public DATASET sources (catches in-place updates
# such as the "live" circuit datasets), re-index downloads/, then officially
# verify any NEW invsqrt candidate against the persisted best bar and adopt a
# strict improvement. Fully bounded so it is safe to run unattended:
#   * --cycles 1          exactly one download+refresh+sweep pass per invocation
#   * --max-candidates 10 cap on new candidates verified this pass (~10 min each)
#   * --stop-on-keep      halt early the moment a genuine improvement is adopted
#   * --wall-time 7200    hard 2h cap on the whole pass
# No secrets are read or printed here; the Kaggle token stays in ~/.kaggle.
set -u

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO" || exit 1

# Ensure uvx (used by scripts/kg.sh) is reachable under launchd's minimal PATH.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

LOG="$REPO/runs/agent/scheduled.log"
mkdir -p "$REPO/runs/agent"

{
  echo "=== qvc_watchdog start $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  # Verifier thread-caps (Mac-overload gotcha): single-threaded official verify.
  OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
    "$REPO/.venv-qvc/bin/python" -m qvc_agent autonomous \
      --task invsqrt \
      --state runs/agent/watchdog-state.json \
      --download \
      --cycles 1 \
      --max-candidates 10 \
      --stop-on-keep \
      --wall-time 7200
  echo "=== qvc_watchdog end rc=$? $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
} >> "$LOG" 2>&1
