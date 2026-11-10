#!/usr/bin/env bash
# Start the QVC Discovery web app:
#   FastAPI backend  -> http://127.0.0.1:8791
#   Next.js frontend -> http://127.0.0.1:3000  (proxies /api/* to the backend)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # repo root (.../quantum)
PY="$ROOT/.venv-qvc/bin/python"
API_PORT="${QVC_API_PORT:-8791}"
WEB_PORT="${QVC_WEB_PORT:-3000}"

if [[ ! -x "$PY" ]]; then
  echo "Missing $PY — create it first:" >&2
  echo "  uv venv .venv-qvc --python 3.13 && uv pip install --python .venv-qvc/bin/python -r requirements-qvc.txt" >&2
  exit 1
fi
cd "$ROOT"

# --- backend ---
OMP_NUM_THREADS=1 "$PY" -m uvicorn qvc_web.backend.main:app --host 127.0.0.1 --port "$API_PORT" &
API_PID=$!
trap 'kill "$API_PID" "$WEB_PID" 2>/dev/null || true' EXIT INT TERM
echo "Backend:  http://127.0.0.1:$API_PORT  (pid $API_PID)"
for _ in $(seq 1 40); do curl -sf "http://127.0.0.1:$API_PORT/api/health" >/dev/null 2>&1 && break; sleep 0.5; done

# --- frontend ---
cd "$ROOT/qvc_web/frontend"
export QVC_API_URL="http://127.0.0.1:$API_PORT"
if [[ ! -d node_modules ]]; then echo "Installing frontend deps (npm install)…"; npm install; fi
echo "Frontend: http://127.0.0.1:$WEB_PORT"
npm run dev &
WEB_PID=$!
wait
