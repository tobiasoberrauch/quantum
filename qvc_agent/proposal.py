"""Proposal schema + strict parsing for the qvc_agent loop.

A *proposal* is the single JSON object the model must return when asked to
decide what to do next for a task (curate an existing candidate or research a
new one). This module owns the field contract (:data:`PROPOSAL_REQUIRED`), a
strict parser that rejects anything malformed (:func:`parse_proposal`), and the
prompt builder that asks for exactly that object (:func:`build_proposal_prompt`).

The prompt never asks the model to emit executable shell commands or raw circuit
bytes; actions are described in words and artifacts are referenced by ``sha``.

This module has no dependency on :mod:`qvc_agent.client`. It imports the task
tuple from the repo-root :mod:`qvc_discovery` module.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from qvc_discovery import TASKS


class ProposalError(ValueError):
    """Raised when a model reply is not a valid proposal object."""


PROPOSAL_REQUIRED: Tuple[str, ...] = (
    "mode",
    "target_task",
    "action",
    "rationale",
    "expected_delta",
    "artifact_ref",
    "precheck_plan",
    "verify_plan",
    "abort_condition",
)

_VALID_MODES = ("curate", "research")


def _strip_fences(text: str) -> str:
    """Strip a single markdown code fence, mirroring ``qvc_discovery.json_object``."""
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1]).strip()
    return text


def parse_proposal(raw: Any) -> Dict[str, Any]:
    """Parse and strictly validate a raw model reply into a proposal dict.

    Raises :class:`ProposalError` on any violation: non-string/None/empty input,
    unparseable JSON, a non-object top level, any missing required key, a ``mode``
    outside ``("curate","research")``, or a ``target_task`` outside ``TASKS``.
    """
    if raw is None:
        raise ProposalError("proposal is None")
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "replace")
    if not isinstance(raw, str):
        raw = str(raw)

    text = raw.strip()
    if not text:
        raise ProposalError("proposal is empty")

    text = _strip_fences(text)

    try:
        data = json.loads(text)
    except ValueError as e:
        raise ProposalError(f"invalid JSON: {e}") from e

    if not isinstance(data, dict):
        raise ProposalError("model must return a JSON object")

    missing = [k for k in PROPOSAL_REQUIRED if k not in data]
    if missing:
        raise ProposalError(f"missing fields: {', '.join(missing)}")

    # Normalize enum-like fields to lowercase so trivial model variation
    # ("CURATE" vs "curate") does not discard an otherwise-valid proposal.
    # The error message below reports the ORIGINAL value for debuggability.
    mode = data["mode"]
    if isinstance(mode, str):
        mode = mode.strip().lower()
    if mode not in _VALID_MODES:
        raise ProposalError(f"bad mode: {data['mode']!r} (expected one of {_VALID_MODES})")
    data["mode"] = mode

    target_task = data["target_task"]
    if isinstance(target_task, str):
        target_task = target_task.strip().lower()
    if target_task not in TASKS:
        raise ProposalError(f"bad target_task: {data['target_task']!r} (expected one of {TASKS})")
    data["target_task"] = target_task

    return data


def build_proposal_prompt(
    task: Optional[str],
    *,
    mode: Optional[str],
    current_best: Optional[Dict[str, Any]],
    candidates: Optional[List[Dict[str, Any]]],
    memory: Optional[str],
) -> str:
    """Build the prompt asking the model for exactly the :data:`PROPOSAL_REQUIRED` JSON.

    Names the task, states the operating mode (curate vs research), shows the
    current best, lists candidate ``sha``+``ratio`` pairs, includes the memory
    excerpt, and demands the required keys. Never instructs the model to emit
    executable shell commands or raw circuit bytes.

    Every parameter is normalized defensively before use so ``None``/empty/
    whitespace inputs degrade gracefully instead of crashing.
    """
    t = "" if task is None else str(task).strip()
    m = "" if mode is None else str(mode).strip()
    cb = current_best if isinstance(current_best, dict) else {}
    cands = candidates if isinstance(candidates, list) else []
    mem = "" if memory is None else str(memory)

    directive = (
        "You are in RESEARCH mode: propose a new candidate circuit that could beat "
        "the current best."
        if m == "research"
        else "You are in CURATE mode: propose adopting or refining an existing "
             "candidate."
    )

    lines: List[str] = []
    lines.append(f"Task: {t}")
    lines.append(directive)
    lines.append("")

    lines.append("Current best:")
    if cb:
        for k, v in cb.items():
            lines.append(f"  - {k}: {v}")
    else:
        lines.append("  - (none recorded)")
    lines.append("")

    lines.append("Top candidates:")
    listed = False
    for c in cands:
        if not isinstance(c, dict):
            continue
        lines.append(f"  - sha={c.get('sha', '?')} ratio={c.get('ratio', '?')}")
        listed = True
    if not listed:
        lines.append("  - (none)")
    lines.append("")

    lines.append("Memory (what worked / what did not):")
    if mem.strip():
        lines.append(mem)
    else:
        lines.append("  - (empty)")
    lines.append("")

    lines.append("Respond with ONLY a single JSON object with exactly these keys:")
    lines.append(", ".join(PROPOSAL_REQUIRED))
    lines.append("")
    lines.append(
        "Do not emit shell commands, scripts, or raw circuit bytes; describe the "
        "action in words and reference artifacts by sha only."
    )

    return "\n".join(lines)
