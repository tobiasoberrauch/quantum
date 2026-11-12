#!/usr/bin/env bash
# Launch the QVC discovery debug UI on localhost.
#   ./qvc_ui/run.sh            -> http://127.0.0.1:8790
#   QVC_UI_PORT=9000 ./qvc_ui/run.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.venv-qvc/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Missing $PY — create it first:" >&2
  echo "  uv venv .venv-qvc --python 3.13 && uv pip install --python .venv-qvc/bin/python -r requirements-qvc.txt" >&2
  exit 1
fi
cd "$ROOT"
exec "$PY" qvc_ui/server.py
