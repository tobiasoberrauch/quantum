"""Research materialization for the qvc_agent loop.

The *research* path lets the agent EDIT the invsqrt generator source and
re-emit a new ``.kmb``. To keep this unit-testable without the real (slow,
GPU-free-but-heavy) emitter, the emitter is INJECTED as a callable
``emit_fn(workdir) -> Path``. The real emitter is
``work/constseed_build/build_constseed_circuit.py``; its exact parameter
interface is confirmed later in Task 9 (Phase 0). This module only builds the
injectable seam + the default edit-application convention.

NOTE (KNOWN GAP — follow-up): the DEFAULT edit/emitter convention here
(`apply_edit` writing ``overrides.json`` + ``cli._default_emit`` running the
emitter under the current interpreter) does NOT match the real
``work/constseed_build/build_constseed_circuit.py``, which takes argparse CLI
args (``output``, ``--hybrid``) + hardcoded constants and runs under
``.venv-chem``. Research mode is therefore NOT production-ready; curate mode
is. See the SDD ledger KNOWN GAP ruling.

This module is standalone: it imports stdlib only and does not import
:mod:`qvc_discovery` or other :mod:`qvc_agent` modules.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict

REPO = Path(__file__).resolve().parents[1]

EMITTER = REPO / "work" / "constseed_build" / "build_constseed_circuit.py"


def apply_edit(workdir: Path, edit: Dict[str, Any]) -> None:
    """Apply an edit to the generator source in ``workdir``.

    Default convention: ``edit={"params": {...}}`` writes
    ``workdir/"overrides.json"`` = ``json.dumps(edit["params"])`` (the emitter
    reads it). Fallback: ``edit={"patch": "..."}`` runs ``patch -p0`` with the
    patch text as stdin in ``workdir``. Anything else (non-dict, or a dict with
    neither key) raises ``ValueError``.
    """
    if not isinstance(edit, dict):
        raise ValueError("edit must be a dict")
    workdir = Path(workdir)
    if "params" in edit:
        (workdir / "overrides.json").write_text(json.dumps(edit["params"]))
    elif "patch" in edit:
        subprocess.run(
            ["patch", "-p0"],
            cwd=workdir,
            input=edit["patch"],
            text=True,
            check=True,
        )
    else:
        raise ValueError("edit must contain 'params' or 'patch'")


def materialize_research(
    proposal: Dict[str, Any],
    workdir: Path,
    out_dir: Path,
    *,
    emit_fn: Callable[[Path], Path],
) -> Path:
    """Materialize a research proposal into ``out_dir/invsqrt.kmb``.

    Requires ``proposal["edit"]`` (a non-dict proposal or one without ``edit``
    raises ``ValueError``). Applies the edit to ``workdir``, calls
    ``emit_fn(workdir)`` to produce a new ``.kmb``, verifies the produced path
    exists, copies it to ``out_dir/invsqrt.kmb`` (creating ``out_dir`` if
    needed), and returns that destination path.
    """
    if not isinstance(proposal, dict) or "edit" not in proposal:
        raise ValueError("proposal must contain 'edit'")
    workdir = Path(workdir)
    apply_edit(workdir, proposal["edit"])
    produced = Path(emit_fn(workdir))
    if not produced.exists():
        raise FileNotFoundError(f"emitter produced no artifact: {produced}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / "invsqrt.kmb"
    shutil.copyfile(produced, dst)
    return dst
