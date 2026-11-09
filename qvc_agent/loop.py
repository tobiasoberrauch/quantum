"""Loop orchestrator for the qvc_agent loop.

Ties together proposal parsing, materialization, precheck, verification, and
human-in-the-loop approval into a single dependency-injected driver. Every
collaborator is passed in as a callable so the loop is unit-testable with fakes
(no LLM, no verifier).

This module imports the qvc_agent sibling modules (proposal, oracle, memory,
curate) but NOT client or research — those are wired in by the CLI.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional

import qvc_agent.curate as curate
import qvc_agent.memory as memory
import qvc_agent.oracle as oracle
import qvc_agent.proposal as proposal


def _clean(value: Any) -> str:
    """Normalize a possibly-None value to a stripped string ('' for None/blank)."""
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return value.strip()


def run_loop(
    task: Any,
    mode: Any,
    n_rounds: Any,
    *,
    propose_fn: Callable[[Dict[str, Any]], str],
    materialize_fn: Callable[..., Path],
    precheck_fn: Callable[[Path], Dict[str, Any]],
    verify_fn: Optional[Callable[[Path], Dict[str, Any]]],
    approve_fn: Callable[..., bool],
    run_dir: Any,
    best_ratio: float,
    best_cost: float,
    memory_base: Optional[Path] = None,
) -> Dict[str, Any]:
    """Drive ``n_rounds`` of the agent loop with fully-injected collaborators.

    Returns ``{"task","mode","rounds","kept","best_ratio_start","best_ratio_end",
    "log_path"}`` where ``log_path = str(run_dir/"loop.jsonl")``. A round counts
    toward ``kept`` only when its verdict is KEEP and ``approve_fn`` returns
    truthy. ``dry_run`` (``verify_fn is None``) never runs the full verifier and
    never keeps.
    """
    if run_dir is None or not str(run_dir).strip():
        raise ValueError("run_dir must be a non-empty path")
    rd = Path(run_dir)
    dry_run = verify_fn is None
    kept = 0
    start_ratio = best_ratio
    t = _clean(task)
    m = _clean(mode)

    try:
        rounds = int(n_rounds)
    except (TypeError, ValueError):
        rounds = 0
    if rounds < 0:
        rounds = 0

    for rnd in range(1, rounds + 1):
        ctx = {
            "task": t,
            "mode": m,
            "best_ratio": best_ratio,
            "best_cost": best_cost,
            "candidates": curate.load_candidates(t) if (m == "curate" and t) else [],
            "memory": memory.load_memory(t, base=memory_base),
        }

        raw = propose_fn(ctx)
        try:
            prop = proposal.parse_proposal(raw)
        except proposal.ProposalError:
            memory.append_loop_log(rd, {"round": rnd, "verdict": "DISCARD_BAD_JSON"})
            continue

        round_dir = rd / "artifacts" / f"r{rnd}"
        round_dir.mkdir(parents=True, exist_ok=True)
        artifact = materialize_fn(prop, round_dir)
        pre = precheck_fn(artifact)

        if dry_run:
            verdict = "DRY_RUN"
            full = None
        elif pre.get("all_passed"):
            full = verify_fn(artifact)
            verdict = "KEEP" if oracle.is_keep(full, best_cost) else "DISCARD"
        else:
            verdict = "DISCARD_PRECHECK"
            full = None

        cost = oracle.extract_cost(full) if full else None
        record = {
            "round": rnd,
            "mode": m,
            "artifact_ref": prop.get("artifact_ref"),
            "verdict": verdict,
            "cost": cost,
            "ratio": oracle.cost_to_ratio(cost) if cost else None,
        }
        memory.append_loop_log(rd, record)

        if verdict == "KEEP" and approve_fn(prop, full):
            best_cost = cost
            best_ratio = oracle.cost_to_ratio(cost)
            kept += 1

        if t:
            memory.write_memory_note(t, f"round {rnd}: {verdict}", base=memory_base)

    return {
        "task": t,
        "mode": m,
        "rounds": rounds,
        "kept": kept,
        "best_ratio_start": start_ratio,
        "best_ratio_end": best_ratio,
        "log_path": str(rd / "loop.jsonl"),
    }
