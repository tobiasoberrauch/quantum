"""Command-line entry point for the qvc_agent loop.

Wires the real collaborators — :class:`WeinstadtClient`, :mod:`qvc_agent.oracle`,
:mod:`qvc_agent.curate`, and :mod:`qvc_agent.research` — into
:func:`qvc_agent.loop.run_loop`. Two subcommands:

* ``check-endpoint`` — resolve the LLM endpoint and send a single ping.
* ``run`` — drive ``n_rounds`` of the agent loop.

The API key is never printed, logged, or written anywhere; every error message is
redacted before it reaches stdout.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# Module-level names so tests can patch them via mock.patch.object(CLI, ...).
from qvc_agent.client import WeinstadtClient, resolve_endpoint, WeinstadtError
from qvc_agent.loop import run_loop

import qvc_agent.curate as curate
import qvc_agent.oracle as oracle
import qvc_agent.proposal as proposal
import qvc_agent.research as research


def _utc_timestamp() -> str:
    """Return a UTC timestamp (``YYYYMMDDTHHMMSSZ``) for default run dirs."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _default_emit(workdir: Path) -> Path:
    """Best-effort DEFAULT emitter runner (convention finalized in Task 9).

    Runs the real emitter script (:data:`research.EMITTER`) with the current
    interpreter inside ``workdir`` and returns the conventional output path
    ``workdir/"invsqrt.kmb"``. This is a placeholder default, not the confirmed
    Task-9 interface.
    """
    workdir = Path(workdir)
    subprocess.run(
        [sys.executable, str(research.EMITTER)],
        cwd=workdir,
        check=True,
    )
    return workdir / "invsqrt.kmb"


def _redact(message: str, secret: Optional[str]) -> str:
    """Return ``message`` with ``secret`` replaced by ``[REDACTED]`` (defensive)."""
    if not secret or not str(secret).strip():
        return message
    return message.replace(str(secret), "[REDACTED]")


def _cmd_check_endpoint() -> int:
    """Resolve the endpoint and ping it once. Never prints the API key."""
    ep: Dict[str, Any] = {}
    try:
        ep = resolve_endpoint()
        client = WeinstadtClient(**ep)
        client.chat([{"role": "user", "content": "ping"}])
    except WeinstadtError as e:
        # The client already formats + redacts its own messages; redact again defensively.
        print(f"ERROR: {_redact(str(e), ep.get('api_key'))}")
        return 1
    except Exception as e:
        print(f"ERROR: {_redact(f'{type(e).__name__}: {e}', ep.get('api_key'))}")
        return 1
    print(f"OK model={ep['model']} base={ep['base_url']}")
    return 0


def _make_materialize_fn(
    mode: str, task: str, cands_plain_path: Path, workdir: Optional[Path]
) -> Callable[..., Path]:
    """Build the per-round materialize callable for ``mode``."""
    if mode == "research":
        def mat_research(p: Dict[str, Any], rd: Path) -> Path:
            # --workdir overrides the per-round work base when provided.
            work = (workdir / Path(rd).name) if workdir else (Path(rd) / "work")
            out = Path(rd) / "out"
            return research.materialize_research(p, work, out, emit_fn=_default_emit)
        return mat_research

    def mat_curate(p: Dict[str, Any], rd: Path) -> Path:
        return curate.materialize(p, rd, comp=task, candidates_path=cands_plain_path)
    return mat_curate


def _cmd_run(args: argparse.Namespace) -> int:
    """Drive ``n_rounds`` of the agent loop with the real collaborators."""
    dry_run = bool(args.dry_run)

    if args.mode == "research":
        print(
            "WARNING: research-mode emitter wiring is not yet matched to the real "
            "constseed_build argparse CLI (.venv-chem); see ledger KNOWN GAP. "
            "Curate mode is production-ready.",
            file=sys.stderr,
        )

    # run_dir: explicit flag wins, else runs/agent/<UTC-ts>.
    run_dir = Path(args.run_dir).expanduser() if args.run_dir else Path("runs") / "agent" / _utc_timestamp()

    # frontier_dir: point load_candidates + materialize at that dir's files.
    frontier_dir = Path(args.frontier_dir).expanduser() if args.frontier_dir else None
    cands_ranked_path = (frontier_dir / "candidates_ranked.json") if frontier_dir else curate.CANDIDATES_RANKED
    cands_plain_path = (frontier_dir / "candidates.json") if frontier_dir else curate.CANDIDATES

    # Derive best_ratio/best_cost from the top ranked candidate (defensive).
    cands = curate.load_candidates(args.task, path=cands_ranked_path)
    top = cands[0] if cands else {}
    best_ratio = float(top.get("ratio") or 0.0)
    best_cost = float(top.get("score") or float("inf"))

    client = WeinstadtClient(**resolve_endpoint())

    def propose_fn(ctx: Dict[str, Any]) -> str:
        return client.chat(
            [
                {
                    "role": "system",
                    "content": "You are a VQCC circuit-optimization agent. Return JSON only.",
                },
                {
                    "role": "user",
                    "content": proposal.build_proposal_prompt(
                        ctx["task"],
                        mode=ctx["mode"],
                        current_best={"ratio": ctx["best_ratio"], "cost": ctx["best_cost"]},
                        candidates=ctx["candidates"],
                        memory=ctx["memory"],
                    ),
                },
            ],
            temperature=0.4,
        )

    precheck_fn = lambda art: oracle.verify(art, "precheck", run_dir / "precheck")
    verify_lambda = lambda art: oracle.verify(art, "official", run_dir / "verify")
    verify_fn = None if dry_run else verify_lambda

    if args.autonomous:
        # Cost-Floor (spec HITL): autonomous keeps are bounded. A candidate whose
        # verified cost is BELOW the floor is refused unattended (would need HITL).
        # Default 0.0 = no floor = prior behavior. KEEP still requires official PASS
        # + strictly-lower cost (oracle.is_keep), independent of this approval.
        floor = float(args.min_cost) if args.min_cost else 0.0

        def approve_auto(p, f):
            c = oracle.extract_cost(f)
            if c is None:
                return False
            return c >= floor

        approve_fn = approve_auto
    else:
        approve_fn = lambda p, f: input(f"Keep {p.get('artifact_ref')}? [y/N] ").strip().lower() == "y"

    materialize_fn = _make_materialize_fn(
        args.mode, args.task, cands_plain_path,
        Path(args.workdir).expanduser() if args.workdir else None,
    )

    summary = run_loop(
        task=args.task,
        mode=args.mode,
        n_rounds=args.rounds,
        propose_fn=propose_fn,
        materialize_fn=materialize_fn,
        precheck_fn=precheck_fn,
        verify_fn=verify_fn,
        approve_fn=approve_fn,
        run_dir=run_dir,
        best_ratio=best_ratio,
        best_cost=best_cost,
        candidates_path=cands_ranked_path,
        memory_base=None,
    )

    print(json.dumps(summary))
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser with the ``run`` and ``check-endpoint`` subcommands."""
    parser = argparse.ArgumentParser(prog="qvc_agent", description="VQCC agent loop CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check-endpoint", help="Resolve the LLM endpoint and ping it once")

    run_p = sub.add_parser("run", help="Drive n_rounds of the agent loop")
    run_p.add_argument("--task", default="invsqrt")
    run_p.add_argument("--mode", choices=["curate", "research"], default="curate")
    run_p.add_argument("--rounds", type=int, default=5)
    run_p.add_argument("--autonomous", action="store_true")
    run_p.add_argument("--min-cost", type=float, default=0.0,
                       help="autonomous-only: refuse to auto-keep a candidate whose verified cost is below this floor (0.0 = no floor)")
    run_p.add_argument("--dry-run", action="store_true")
    run_p.add_argument("--frontier-dir", type=Path, default=None)
    run_p.add_argument("--workdir", type=Path, default=None)
    run_p.add_argument("--run-dir", type=Path, default=None)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point. Returns a process exit code (0 ok, 1 error, 2 usage)."""
    argv = sys.argv[1:] if argv is None else list(argv)
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "check-endpoint":
        return _cmd_check_endpoint()
    return _cmd_run(args)
