"""Bounded autonomous curate driver for the qvc_agent loop.

Turns the one-shot :func:`qvc_agent.watchdog.sweep_pool` into a self-running
"catch a new public best" operation. Per cycle (up to ``max_cycles``):

1. (optional ``--download``) best-effort re-fetch of existing public source slugs
   via ``kg.sh`` (non-fatal; catches in-place updates such as the "live" dataset).
2. ``refresh_local``: re-run ``index_frontier.py`` over ``downloads/`` (idempotent,
   local, treats circuit data as data — nothing executed).
3. Plan: seed state if absent (bar = ranked top, seen = all ranked SHAs) then
   compute the *unseen* universe candidates (indexed but not yet verified/adopted).
4. Sweep the unseen pool via :func:`watchdog.sweep_pool` (precheck -> official
   verify -> adopt if strictly below the bar and at/above the floor).
5. Stop on a keep (``stop_on_keep``) or on budget (``max_cycles`` /
   ``total_wall_time_s``).

Deterministic and safe: only strict improvements are adopted, already-seen
candidates are never re-verified, and every decision is logged. The LLM is not
required. Heavy collaborators (precheck/verify/materialize/refresh) are injected
so the orchestration is unit-testable offline.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import qvc_agent.watchdog as watchdog

REPO = Path(__file__).resolve().parents[1]
DEFAULT_FRONTIER = REPO / "work" / "frontier_1109"


def _paths(frontier_dir: Path):
    fd = Path(frontier_dir)
    return (
        fd,
        fd / "candidates.json",
        fd / "candidates_ranked.json",
        fd / "shacache.json",
        fd / "downloads",
        fd / "scripts" / "index_frontier.py",
        fd / "scripts" / "kg.sh",
    )


def refresh_local(frontier_dir: Path) -> int:
    """Re-index ``downloads/`` into ``candidates.json`` (idempotent, local).

    Returns the indexer's exit code (0 on success). A missing indexer is a
    non-fatal 1 (the driver continues with the existing pool).
    """
    fd, cands, ranked, cache, dl, idx, kg = _paths(frontier_dir)
    if not idx.is_file():
        return 1
    try:
        r = subprocess.run(
            [sys.executable, "-I", str(idx), str(dl), str(cands), str(cache)],
            capture_output=True, text=True, timeout=1800,
        )
        return r.returncode
    except (OSError, subprocess.SubprocessError):
        return 1


def download_sources(frontier_dir: Path) -> int:
    """Best-effort re-fetch of existing public source slugs via ``kg.sh``.

    Opt-in and non-fatal: any failure (no network, rate limit, missing token) is
    swallowed and the driver proceeds with whatever is already local. Re-fetching
    existing slugs catches in-place updates (e.g. the ``qcc-circuits-live``
    dataset); discovering brand-new slugs is a separate, heavier step.
    """
    fd, cands, ranked, cache, dl, idx, kg = _paths(frontier_dir)
    if not (kg.is_file() and dl.is_dir()):
        return 1
    token = Path.home() / ".kaggle" / "access_token"
    if not token.is_file():
        return 1
    ok = 0
    for name in sorted(os.listdir(dl)):
        if not name.startswith(("k__", "d__", "f__")):
            continue
        kind, _, rest = name.partition("__")
        if not rest:
            continue
        api = "kernels" if kind == "k" else "datasets"
        try:
            r = subprocess.run(
                ["bash", str(kg), api, "download", "--force", rest],
                capture_output=True, text=True, timeout=3600,
                cwd=str(dl.parent),
            )
            ok += 1 if r.returncode == 0 else 0
        except (OSError, subprocess.SubprocessError):
            continue
    return 0 if ok else 1


def seed_state_if_absent(frontier_dir: Path, task: str, state_path: Path) -> Dict[str, Any]:
    """On first run, establish the bar from the ranked top and mark every ranked
    SHA as seen (they are already verified and none beats the top). Returns state."""
    st = watchdog.load_state(state_path)
    if st["best_cost"] is not None:
        return st
    fd, cands, ranked, cache, dl, idx, kg = _paths(frontier_dir)
    try:
        rows = json.loads(ranked.read_text())[task]
    except (OSError, ValueError, KeyError, TypeError):
        rows = []
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        top = rows[0]
        st["best_cost"] = watchdog._num(top.get("score"))
        st["best_ratio"] = watchdog._num(top.get("ratio"))
        st["best_sha"] = top.get("sha") if isinstance(top.get("sha"), str) else None
        st["seen"] = [r["sha"] for r in rows
                      if isinstance(r, dict) and isinstance(r.get("sha"), str)]
    watchdog.save_state(state_path, st)
    return st


def unseen_shas(frontier_dir: Path, task: str, state_path: Path) -> List[str]:
    """Universe candidates (indexed) not yet seen and not the current best."""
    fd, cands, ranked, cache, dl, idx, kg = _paths(frontier_dir)
    st = watchdog.load_state(state_path)
    try:
        uni = json.loads(cands.read_text())[task]
    except (OSError, ValueError, KeyError, TypeError):
        return []
    if isinstance(uni, dict):
        shas = [s for s in uni.keys() if isinstance(s, str)]
    elif isinstance(uni, list):
        shas = [c.get("sha") for c in uni
                if isinstance(c, dict) and isinstance(c.get("sha"), str)]
    else:
        shas = []
    seen = set(st["seen"])
    best = st.get("best_sha")
    return [s for s in shas if s not in seen and s != best]


def run_autonomous(
    *,
    frontier_dir: Path,
    task: str,
    state_path: Path,
    out_dir: Path,
    precheck_fn: Callable[[Path], Dict[str, Any]],
    verify_fn: Optional[Callable[[Path], Dict[str, Any]]],
    materialize_fn: Optional[Callable[[str, Path], Path]] = None,
    floor: float = 0.0,
    max_candidates: Optional[int] = None,
    max_cycles: int = 1,
    total_wall_time_s: Optional[float] = None,
    stop_on_keep: bool = False,
    dry_run: bool = False,
    download: bool = False,
    memory_base: Optional[Path] = None,
    refresh: Callable[[Path], int] = refresh_local,
    downloader: Callable[[Path], int] = download_sources,
) -> Dict[str, Any]:
    """Run bounded autonomous cycles; return a summary with per-cycle detail."""
    t = "" if task is None else str(task).strip()
    start = time.monotonic()
    cycles: List[Dict[str, Any]] = []
    total_kept = 0
    n_cycles = max(1, int(max_cycles))

    for cyc in range(1, n_cycles + 1):
        if total_wall_time_s is not None and (time.monotonic() - start) >= total_wall_time_s:
            break
        if download:
            downloader(frontier_dir)
        refresh(frontier_dir)
        seed_state_if_absent(frontier_dir, t, state_path)
        unseen = unseen_shas(frontier_dir, t, state_path)
        rd = Path(out_dir) / f"cycle{cyc}"
        rd.mkdir(parents=True, exist_ok=True)

        if not unseen:
            cycles.append({"cycle": cyc, "unseen": 0, "kept": 0})
            if not download:
                break  # nothing new locally; looping without downloads is pointless
            continue

        pool_file = rd / "pool_unseen.json"
        pool_file.write_text(json.dumps({t: [{"sha": s} for s in unseen]}))
        s = watchdog.sweep_pool(
            task=t, pool_path=pool_file, state_path=state_path,
            out_dir=Path(out_dir) / "adopt",
            precheck_fn=precheck_fn, verify_fn=(None if dry_run else verify_fn),
            run_dir=rd, materialize_fn=materialize_fn,
            floor=floor, max_candidates=max_candidates,
            dry_run=dry_run, memory_base=memory_base, stop_on_keep=stop_on_keep,
        )
        total_kept += s["kept"]
        cycles.append({"cycle": cyc, "unseen": len(unseen), "scanned": s["scanned"],
                       "verified": s["verified"], "kept": s["kept"],
                       "new_best_sha": s["new_best_sha"]})
        if stop_on_keep and s["kept"]:
            break

    return {
        "task": t, "cycles": cycles, "kept": total_kept,
        "best": watchdog.load_state(state_path), "state_path": str(state_path),
    }
