"""Verifier oracle for the qvc_agent loop.

Wraps the EXISTING official-verifier machinery (:mod:`qvc_discovery`) so the
agent loop can gate KEEP decisions on real verifier results instead of trusting
model-claimed costs.

Two trusted adapter JSONs (under ``qvc_ui/adapters/``) are reused:

* :data:`PRECHECK_ADAPTER` — fast stratified-subset precheck (<1s).
* :data:`OFFICIAL_ADAPTER` — the official 64-shot verifier.

Nothing here executes model-generated code: it only invokes the operator-supplied
trusted verifier command via :func:`qvc_discovery.verify_candidate`. A cost is
never synthesized — :func:`extract_cost` returns ``None`` unless the verifier
reported a passing, finite, positive official cost.

This module imports :mod:`qvc_discovery` as a module and calls
``qvc_discovery.verify_candidate(...)`` at call time (NOT a pre-bound
``from ... import``), so callers can patch ``qvc_discovery.verify_candidate``
via :func:`unittest.mock.patch.object`.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Optional

import qvc_discovery

REPO = Path(__file__).resolve().parents[1]
PRECHECK_ADAPTER = REPO / "qvc_ui/adapters/adapter_invsqrt_precheck.json"
OFFICIAL_ADAPTER = REPO / "qvc_ui/adapters/adapter_invsqrt.json"


def _clean(value: Any) -> str:
    """Normalize a possibly-None value to a stripped string ('' for None/blank)."""
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return value.strip()


def _resolve_path(value: Any) -> Optional[Path]:
    """Resolve a path argument to a Path, or None when it is unusable (None/blank)."""
    s = _clean(value)
    if not s:
        return None
    return Path(s).expanduser()


def verify(artifact: Any, level: Any, out_dir: Any, *, execute: bool = True) -> dict:
    """Run the trusted verifier for ``level`` against ``artifact``.

    ``level`` selects the adapter: ``"precheck"`` loads :data:`PRECHECK_ADAPTER`,
    anything else loads :data:`OFFICIAL_ADAPTER`. The adapter JSON is read from
    disk and handed to :func:`qvc_discovery.verify_candidate` with the task
    hardcoded to ``"invsqrt"`` (this oracle only handles invsqrt for now).

    ``execute`` is forwarded as a keyword argument so dry-run vs. real execution
    is explicit to the caller (and observable in tests). Returns the dict produced
    by ``verify_candidate`` unchanged.

    Raises ``ValueError`` when ``level``, ``artifact``, or ``out_dir`` is missing
    or blank.
    """
    lvl = _clean(level)
    if not lvl:
        raise ValueError("level is required")
    art = _resolve_path(artifact)
    if art is None:
        raise ValueError("artifact is required")
    out = _resolve_path(out_dir)
    if out is None:
        raise ValueError("out_dir is required")

    adapter_path = PRECHECK_ADAPTER if lvl == "precheck" else OFFICIAL_ADAPTER
    adapter = json.loads(adapter_path.read_text(encoding="utf-8"))
    return qvc_discovery.verify_candidate(
        adapter, "invsqrt", art, out, execute=execute, max_workers=2
    )


def extract_cost(result: Any) -> Optional[float]:
    """Return the verified official cost from a ``verify_candidate`` result, or None.

    A cost is only trusted when the result reports ``all_passed`` truthy AND
    ``official_cost_if_identical_across_salts`` is a finite number > 0. Booleans,
    non-numbers, NaN/inf, zero, and negatives all yield ``None`` — a cost is never
    synthesized.
    """
    if not isinstance(result, dict):
        return None
    if not result.get("all_passed"):
        return None
    c = result.get("official_cost_if_identical_across_salts")
    if isinstance(c, bool) or not isinstance(c, (int, float)):
        return None
    if not math.isfinite(c) or c <= 0:
        return None
    return float(c)


def is_keep(result: Any, best_cost: Any) -> bool:
    """True iff ``result`` yields a verified cost strictly lower than ``best_cost``.

    Returns False when no cost can be extracted, or when ``best_cost`` is not a
    usable number (None/blank/non-numeric) — a KEEP decision is never made without
    a valid reference cost to beat.
    """
    c = extract_cost(result)
    if c is None:
        return False
    if isinstance(best_cost, bool) or not isinstance(best_cost, (int, float)):
        return False
    return c < best_cost


def cost_to_ratio(cost: Any) -> float:
    """Return ``REFERENCE_COSTS["invsqrt"] / cost``.

    Raises ``ValueError`` when ``cost`` is not a finite number > 0, since a ratio
    is undefined for zero/negative/non-numeric/None input.
    """
    if isinstance(cost, bool) or not isinstance(cost, (int, float)):
        raise ValueError("cost must be a positive finite number")
    if not math.isfinite(cost) or cost <= 0:
        raise ValueError("cost must be a positive finite number")
    return qvc_discovery.REFERENCE_COSTS["invsqrt"] / cost
