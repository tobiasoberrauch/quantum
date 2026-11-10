"""Bounded curate watchdog for the qvc_agent loop.

Sweeps a ranked candidate pool against a PERSISTED current-best "bar", verifying
each not-yet-seen candidate (fast precheck -> official verifier) and adopting any
genuine improvement (strictly lower cost, at or above an optional floor). It is
deterministic (no LLM required) so it is safe to run unattended within its bounds.

Safety / bounds:
- Only strict improvements are adopted: ``oracle.is_keep`` (official PASS + finite
  cost strictly below the bar) AND ``cost >= floor``.
- Already-seen candidates are never re-verified (state file tracks SHAs), so a
  repeated sweep only spends verifier compute on genuinely new circuits.
- Bounded by ``max_candidates`` and ``wall_time_s``; optional ``stop_on_keep``.
- Every decision (KEEP / DISCARD / SKIP_SEEN / DRY_RUN / errors) is written to
  ``loop.jsonl``; a KEEP also writes a memory note. Error records carry only the
  exception TYPE name, never the message (public-repo secret hygiene).
- ``dry_run`` stops after the fast precheck (no official verify, no adoption).

This module reuses :mod:`qvc_agent.curate` (materialize / load), :mod:`qvc_agent.oracle`
(verify / extract_cost / is_keep / cost_to_ratio) and :mod:`qvc_agent.memory`
(log / note). It does not import client or research. Ratio math is invsqrt-scoped
(inherited from :func:`qvc_agent.oracle.cost_to_ratio`), matching the agent today.
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import qvc_agent.curate as curate
import qvc_agent.memory as memory
import qvc_agent.oracle as oracle

REPO = Path(__file__).resolve().parents[1]
DEFAULT_STATE = REPO / "runs" / "agent" / "watchdog-state.json"


def _num(value: Any) -> Optional[float]:
    """Coerce to float; None/NaN-ish junk -> None."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if f == f else None  # reject NaN


def load_state(path: Path) -> Dict[str, Any]:
    """Load watchdog state; return a clean skeleton when missing/malformed.

    Shape: ``{"best_ratio": float|None, "best_cost": float|None,
    "best_sha": str|None, "seen": [str, ...]}``.
    """
    p = Path(path)
    try:
        data = json.loads(p.read_text())
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    raw_seen = data.get("seen")
    seen = [s for s in raw_seen if isinstance(s, str)] if isinstance(raw_seen, list) else []
    best_sha = data.get("best_sha")
    return {
        "best_ratio": _num(data.get("best_ratio")),
        "best_cost": _num(data.get("best_cost")),
        "best_sha": best_sha if isinstance(best_sha, str) else None,
        "seen": seen,
    }


def save_state(path: Path, state: Dict[str, Any]) -> None:
    """Persist state (creating parent dirs). Never raises on a read-only parent."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def _default_materialize(task: str, candidates_path: Path) -> Callable[[str, Path], Path]:
    """Build the real materialize callable (extract a pool candidate by SHA)."""
    def mat(sha: str, dest_dir: Path) -> Path:
        return curate.materialize(
            {"artifact_ref": sha}, dest_dir, comp=task, candidates_path=candidates_path
        )
    return mat


def sweep_pool(
    *,
    task: str,
    pool_path: Path,
    state_path: Path,
    out_dir: Path,
    precheck_fn: Callable[[Path], Dict[str, Any]],
    verify_fn: Optional[Callable[[Path], Dict[str, Any]]],
    run_dir: Optional[Path] = None,
    candidates_path: Optional[Path] = None,
    materialize_fn: Optional[Callable[[str, Path], Path]] = None,
    floor: float = 0.0,
    max_candidates: Optional[int] = None,
    wall_time_s: Optional[float] = None,
    stop_on_keep: bool = False,
    dry_run: bool = False,
    memory_base: Optional[Path] = None,
    seed_best_ratio: Optional[float] = None,
    seed_best_cost: Optional[float] = None,
    seed_best_sha: Optional[str] = None,
) -> Dict[str, Any]:
    """Sweep the pool against the persisted bar; adopt genuine improvements.

    Returns a summary dict::

        {"task","scanned","verified","kept","best_ratio_start","best_ratio_end",
         "new_best_sha","state_path","log_path"}

    ``dry_run`` (or ``verify_fn is None``) verifies nothing past the precheck and
    never adopts. On the first run (no persisted bar) the bar is seeded from the
    explicit ``seed_best_*`` args, else from the pool's top entry (baseline).
    """
    t = "" if task is None else str(task).strip()
    cands_path = Path(candidates_path) if candidates_path is not None else curate.CANDIDATES
    mat_fn = materialize_fn if materialize_fn is not None else _default_materialize(t, cands_path)
    rd = Path(run_dir) if run_dir is not None else (Path(state_path).parent / "sweep")
    rd.mkdir(parents=True, exist_ok=True)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    state = load_state(state_path)

    # Load the pool defensively (a bad pool must not crash the watchdog).
    try:
        pool: List[Dict[str, Any]] = curate.load_candidates(t, path=Path(pool_path))
    except (KeyError, OSError, ValueError, TypeError):
        pool = []
    if not isinstance(pool, list):
        pool = []

    # Establish the bar on first run.
    if state["best_cost"] is None:
        if seed_best_cost is not None:
            state["best_cost"] = _num(seed_best_cost)
            state["best_ratio"] = _num(seed_best_ratio)
            state["best_sha"] = seed_best_sha if isinstance(seed_best_sha, str) else None
        elif pool:
            top = pool[0] if isinstance(pool[0], dict) else {}
            state["best_cost"] = _num(top.get("score"))
            state["best_ratio"] = _num(top.get("ratio"))
            state["best_sha"] = top.get("sha") if isinstance(top.get("sha"), str) else None
        # Mark the baseline best as seen so it (and any later superseded best) is
        # never re-verified on subsequent sweeps.
        if isinstance(state.get("best_sha"), str) and state["best_sha"] not in state["seen"]:
            state["seen"].append(state["best_sha"])
        save_state(state_path, state)

    bar_start_ratio = state["best_ratio"]
    bar_cost = state["best_cost"]
    if bar_cost is None:
        # No pool and no seed: nothing to compare against. Record and stop.
        save_state(state_path, state)
        return {
            "task": t, "scanned": 0, "verified": 0, "kept": 0,
            "best_ratio_start": None, "best_ratio_end": None, "new_best_sha": None,
            "state_path": str(state_path), "log_path": str(rd / "loop.jsonl"),
        }

    dry = dry_run or verify_fn is None
    start = time.monotonic()
    scanned = verified = kept = 0
    new_best_sha: Optional[str] = None

    for cand in pool:
        if max_candidates is not None and scanned >= max_candidates:
            break
        if wall_time_s is not None and (time.monotonic() - start) >= wall_time_s:
            break
        if not isinstance(cand, dict):
            continue
        sha = cand.get("sha")
        if not isinstance(sha, str) or not sha:
            continue
        scanned += 1

        if sha in state["seen"] or sha == state["best_sha"]:
            memory.append_loop_log(rd, {"sha": sha[:12], "verdict": "SKIP_SEEN"})
            continue

        try:
            artifact = mat_fn(sha, rd / "artifacts" / sha[:12])
        except Exception as e:  # noqa: BLE001 - record + continue, never crash the sweep
            memory.append_loop_log(rd, {"sha": sha[:12], "verdict": "MATERIALIZE_ERROR",
                                        "error": type(e).__name__})
            state["seen"].append(sha)
            save_state(state_path, state)
            continue

        pre = precheck_fn(artifact)

        if dry:
            state["seen"].append(sha)
            memory.append_loop_log(rd, {"sha": sha[:12], "verdict": "DRY_RUN",
                                        "precheck_passed": bool(pre.get("all_passed"))})
            save_state(state_path, state)
            continue

        if not pre.get("all_passed"):
            state["seen"].append(sha)
            memory.append_loop_log(rd, {"sha": sha[:12], "verdict": "DISCARD_PRECHECK"})
            save_state(state_path, state)
            continue

        full = verify_fn(artifact)
        verified += 1
        cost = oracle.extract_cost(full)
        ratio = oracle.cost_to_ratio(cost) if cost is not None else None

        if oracle.is_keep(full, bar_cost) and cost is not None and cost >= floor:
            dst = out / f"{t}.kmb"
            shutil.copyfile(artifact, dst)
            state["best_cost"] = cost
            state["best_ratio"] = ratio
            state["best_sha"] = sha
            state["seen"].append(sha)
            kept += 1
            new_best_sha = sha
            memory.append_loop_log(rd, {"sha": sha[:12], "verdict": "KEEP",
                                        "cost": cost, "ratio": ratio})
            memory.write_memory_note(t, f"watchdog KEEP {sha[:12]} ratio={ratio} cost={cost}",
                                     base=memory_base)
            save_state(state_path, state)
            if stop_on_keep:
                break
        else:
            state["seen"].append(sha)
            memory.append_loop_log(rd, {"sha": sha[:12], "verdict": "DISCARD",
                                        "cost": cost, "ratio": ratio})
            save_state(state_path, state)

    save_state(state_path, state)
    return {
        "task": t, "scanned": scanned, "verified": verified, "kept": kept,
        "best_ratio_start": bar_start_ratio, "best_ratio_end": state["best_ratio"],
        "new_best_sha": new_best_sha, "state_path": str(state_path),
        "log_path": str(rd / "loop.jsonl"),
    }
