"""Path + environment configuration for the QVC Discovery backend."""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent          # .../qvc_web/backend
QVC_WEB_DIR = BACKEND_DIR.parent                        # .../qvc_web
ROOT = QVC_WEB_DIR.parent                               # repo root (.../quantum)

# Make qvc_discovery.py (repo root) importable.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RUNS_DIR = ROOT / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)
ADAPTERS_DIR = BACKEND_DIR / "adapters"
EXAMPLES_DIR = BACKEND_DIR / "examples"
# User-added team models (gitignored). Stores env-var KEY NAMES only, never secrets.
TEAM_MODELS_FILE = BACKEND_DIR / "team_models.json"

VENV_QVC = str(ROOT / ".venv-qvc" / "bin" / "python")
VENV_CHEM = str(ROOT / ".venv-chem" / "bin" / "python")
