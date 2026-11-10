"""Async job runner for discover / score / verify.

Copies the proven handler logic from qvc_ui/server.py and wraps
qvc_discovery.call_models so every LLM attempt/fallback/failure is traceable.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import qvc_discovery as q  # noqa: E402  (repo root is on sys.path via config)
from . import team as _team
from . import tracer
from .config import ROOT, RUNS_DIR

LOG = logging.getLogger("qvc")


# --------------------------------------------------------------------------- #
# Model-call tracing (wrap q.call_models once at import)                       #
# --------------------------------------------------------------------------- #
_ORIG_CALL_MODELS = q.call_models


def _traced_call_models(key: str, chain: list[str], prompt: str, schema: dict[str, Any],
                        schema_name: str, check: Any, retries: int = 2,
                        temperature: float = 0.6) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "schema": schema_name,
        "chain": list(dict.fromkeys(chain or [])),
        "prompt": (prompt or "")[:60000],
        "started": round(time.time(), 3),
        "ok": False,
        "attempts": [],
    }
    tracer.TRACE.append(rec)
    try:
        out = _ORIG_CALL_MODELS(key, chain, prompt, schema, schema_name, check, retries, temperature)
    except Exception as exc:  # record then re-raise; caller handles
        rec["ok"] = False
        rec["error"] = f"{type(exc).__name__}: {str(exc)[:600]}"
        rec["elapsed"] = round(time.time() - rec["started"], 3)
        raise
    rec["ok"] = True
    rec["served_model"] = out.get("served_model")
    rec["requested_model"] = out.get("requested_model")
    rec["response_mode"] = out.get("response_mode")
    rec["attempts"] = out.get("failures", []) or []
    rec["usage"] = out.get("usage")
    rec["elapsed"] = round(time.time() - rec["started"], 3)
    return out


q.call_models = _traced_call_models  # type: ignore[assignment]
tracer.install_log_capture("qvc")


# --------------------------------------------------------------------------- #
# Job runner                                                                   #
# --------------------------------------------------------------------------- #
JOBS: dict[str, dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()
_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="qvcjob")


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _int_bounded(value: Any, default: int, lo: int, hi: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = default
    return max(lo, min(hi, n))


def do_discover(p: dict[str, Any]) -> dict[str, Any]:
    task = (p.get("task") or "all")
    if task not in ("all", *q.TASKS):
        raise ValueError(f"task must be one of all/{'/'.join(q.TASKS)}")
    top = _int_bounded(p.get("top"), 3, 1, 9)
    workers = _int_bounded(p.get("workers"), 3, 1, 9)
    retries = _int_bounded(p.get("retries"), 2, 1, 4)

    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set. Copy .env.example to .env and add your key. "
                           "(score and verify still work without it.)")
    if q.OpenRouter is None:
        raise RuntimeError("openrouter SDK not installed in this venv.")

    tasks = list(q.TASKS) if task == "all" else [task]
    memory_path = p.get("memory")
    brief_path = p.get("brief")
    # Inline text (typed/pasted in the UI) takes precedence; otherwise read a file path.
    memory = (p.get("memory_text") or "").strip()
    if not memory and memory_path:
        mp = Path(memory_path)
        memory = mp.read_text(encoding="utf-8") if mp.exists() else ""
    brief = (p.get("brief_text") or "").strip()
    if not brief and brief_path:
        bp = Path(brief_path)
        brief = bp.read_text(encoding="utf-8") if bp.exists() else ""

    outdir = Path(p.get("output") or (RUNS_DIR / f"discover_{_ts()}"))
    debate = p.get("debate", True)
    if isinstance(debate, str):
        debate = debate.strip().lower() not in ("0", "false", "no", "off")
    tracer.TRACE.clear()
    tracer.LOGS.clear()
    data = q.discover(key, tasks, memory, brief, top, retries, workers, debate=bool(debate))
    q.write_json(outdir / "research.json", data)
    (outdir / "report.md").write_text(q.report(data), encoding="utf-8")
    snap = tracer.TRACE.snapshot()
    cost_usd = round(sum((it.get("usage") or {}).get("cost", 0.0) for it in snap), 6)
    tokens = sum((it.get("usage") or {}).get("total_tokens", 0) for it in snap)
    return {
        "data": data,
        "files": {"research_json": str(outdir / "research.json"),
                  "report_md": str(outdir / "report.md")},
        "cost_usd": cost_usd,
        "tokens": tokens,
        "trace": snap,
        "logs": tracer.LOGS.snapshot(),
    }


def do_score(p: dict[str, Any]) -> dict[str, Any]:
    costs = p.get("costs")
    payload: dict[str, Any] | None = None
    if isinstance(costs, dict):
        payload = costs
    elif p.get("costs_file"):
        cf = Path(p["costs_file"])
        if not cf.is_absolute():
            cf = ROOT / cf
        if not cf.exists():
            raise FileNotFoundError(f"costs_file not found: {cf}")
        payload = json.loads(cf.read_text(encoding="utf-8"))
    else:
        raise ValueError("Provide a 'costs' object or a 'costs_file' path.")
    return {"result": q.score_from_verified_costs(payload)}


def do_verify(p: dict[str, Any]) -> dict[str, Any]:
    adapter_file = Path(p.get("adapter_file") or "")
    if not adapter_file.is_absolute():
        adapter_file = ROOT / adapter_file
    if not adapter_file.exists():
        raise FileNotFoundError(f"adapter not found: {adapter_file}")
    task = p.get("task")
    if task not in q.TASKS:
        raise ValueError(f"task must be one of {'/'.join(q.TASKS)}")
    candidate = Path(p.get("candidate") or "")
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    if not candidate.exists():
        raise FileNotFoundError(f"candidate not found: {candidate}")
    execute = bool(p.get("execute", False))
    workers = _int_bounded(p.get("workers"), 2, 1, 16)
    shots = _int_bounded(p.get("shots"), 64, 64, 1024)   # official: multiple of 64
    pre_n = _int_bounded(p.get("preN"), 512, 64, 8192)   # pre-check stratified samples
    is_precheck = "precheck" in adapter_file.name.lower()

    outdir = Path(p.get("output") or (RUNS_DIR / f"verify_{_ts()}"))
    adapter = json.loads(adapter_file.read_text(encoding="utf-8"))
    if execute:
        tracer.LOGS.clear()
        os.environ["QVC_SHOTS"] = str(shots)
        os.environ["QVC_WORKERS"] = str(workers)
        os.environ["QVC_PRECHECK_N"] = str(pre_n)
    result = q.verify_candidate(adapter, task, candidate.resolve(), outdir, execute, workers)
    result["_precheck"] = is_precheck
    q.write_json(outdir / "verification.json", result)
    return {"result": result, "files": {"verification_json": str(outdir / "verification.json")}}


def do_team(p: dict[str, Any]) -> dict[str, Any]:
    tracer.TRACE.clear()
    tracer.LOGS.clear()
    result = _team.run_team(p)
    snap = tracer.TRACE.snapshot()
    cost_usd = round(sum((it.get("usage") or {}).get("cost", 0.0) for it in snap), 6)
    tokens = sum((it.get("usage") or {}).get("total_tokens", 0) for it in snap)
    return {
        "result": result,
        "cost_usd": cost_usd,
        "tokens": tokens,
        "trace": snap,
        "logs": tracer.LOGS.snapshot(),
    }


_HANDLERS = {"discover": do_discover, "score": do_score, "verify": do_verify,
             "team": do_team}


def submit_job(kind: str, params: dict[str, Any]) -> str:
    if kind not in _HANDLERS:
        raise ValueError(f"unknown kind '{kind}'; expected one of {list(_HANDLERS)}")
    jid = uuid.uuid4().hex[:12]
    job = {"id": jid, "kind": kind, "params": params, "status": "pending",
           "created": time.time(), "result": None, "error": None}
    with _JOBS_LOCK:
        JOBS[jid] = job
    _POOL.submit(_run_job, jid, kind, params)
    return jid


def _run_job(jid: str, kind: str, params: dict[str, Any]) -> None:
    job = JOBS.get(jid)
    if job is None:
        return
    job["status"] = "running"
    job["started"] = time.time()
    try:
        job["result"] = _HANDLERS[kind](params)
        job["status"] = "done"
    except Exception as exc:
        job["status"] = "error"
        job["error"] = f"{type(exc).__name__}: {exc}"
        LOG.error("job %s (%s) failed: %s", jid, kind, exc)
    finally:
        job["finished"] = time.time()
