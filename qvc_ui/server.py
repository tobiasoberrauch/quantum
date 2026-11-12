#!/usr/bin/env python3
"""Debug surface for qvc_discovery.py.

Wraps the three subcommands (discover / score / verify) as async jobs and
streams every model call, fallback, failure and log line to a local web UI so
all outputs can be inspected and debugged. Binds to 127.0.0.1 only.

Run:  .venv-qvc/bin/python qvc_ui/server.py            (default port 8790)
      QVC_UI_PORT=9000 .venv-qvc/bin/python qvc_ui/server.py

Design notes:
  * discover/score/verify execute in-process by importing qvc_discovery, so the
    UI sees full structured results (not just stdout).
  * q.call_models is wrapped to record a per-call trace (chain, served model,
    response mode, per-attempt failures, latency, prompt). This is the primary
    debug signal for "which models were tried and why did it fall back".
  * verify runs ONLY an operator-supplied trusted adapter (see qvc_ui/adapters/),
    never LLM-generated code. Default is dry-run (command preview); execution is
    an explicit opt-in.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Imported at module level (not inside _build_app) so PEP 563 string
# annotations like `request: Request` resolve against module globals.
from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import qvc_discovery as q  # noqa: E402
from qvc_ui import tracer  # noqa: E402

RUNS_DIR = ROOT / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR = Path(__file__).resolve().parent / "static"
ADAPTERS_DIR = Path(__file__).resolve().parent / "adapters"
EXAMPLES_DIR = Path(__file__).resolve().parent / "examples"

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
    memory = Path(memory_path).read_text(encoding="utf-8") if memory_path else ""
    brief = ""
    if brief_path:
        bp = Path(brief_path)
        brief = bp.read_text(encoding="utf-8") if bp.exists() else ""

    outdir = Path(p.get("output") or (RUNS_DIR / f"discover_{_ts()}"))
    tracer.TRACE.clear()
    tracer.LOGS.clear()
    data = q.discover(key, tasks, memory, brief, top, retries, workers)
    q.write_json(outdir / "research.json", data)
    (outdir / "report.md").write_text(q.report(data), encoding="utf-8")
    return {
        "data": data,
        "files": {"research_json": str(outdir / "research.json"),
                  "report_md": str(outdir / "report.md")},
        "trace": tracer.TRACE.snapshot(),
        "logs": tracer.LOGS.snapshot(),
    }


def do_score(p: dict[str, Any]) -> dict[str, Any]:
    costs = p.get("costs")
    payload: dict[str, Any] | None = None
    if isinstance(costs, dict):
        payload = costs
    elif p.get("costs_file"):
        cf = Path(p["costs_file"])
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
    shots = _int_bounded(p.get("shots"), 64, 64, 1024)   # official: must be a multiple of 64
    pre_n = _int_bounded(p.get("preN"), 512, 64, 8192)   # pre-check stratified samples
    is_precheck = "precheck" in adapter_file.name.lower()

    outdir = Path(p.get("output") or (RUNS_DIR / f"verify_{_ts()}"))
    adapter = json.loads(adapter_file.read_text(encoding="utf-8"))
    if execute:
        tracer.LOGS.clear()
        # The trusted adapter reads these from its environment (verify_candidate
        # copies os.environ into the subprocess env). shots=64 is the only value
        # that constitutes an official claim for invsqrt.
        os.environ["QVC_SHOTS"] = str(shots)
        os.environ["QVC_WORKERS"] = str(workers)
        os.environ["QVC_PRECHECK_N"] = str(pre_n)
    result = q.verify_candidate(adapter, task, candidate.resolve(), outdir, execute, workers)
    result["_precheck"] = is_precheck
    q.write_json(outdir / "verification.json", result)
    return {"result": result, "files": {"verification_json": str(outdir / "verification.json")}}


_HANDLERS = {"discover": do_discover, "score": do_score, "verify": do_verify}


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


# --------------------------------------------------------------------------- #
# FastAPI app                                                                  #
# --------------------------------------------------------------------------- #
def _build_app():
    app = FastAPI(title="QVC Discovery Debug UI", version="1.0")
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(str(STATIC_DIR / "index.html"))

    @app.get("/api/status")
    def status() -> JSONResponse:
        return JSONResponse({
            "key_present": bool(os.getenv("OPENROUTER_API_KEY", "").strip()),
            "openrouter_installed": q.OpenRouter is not None,
            "jsonschema_installed": True,
            "chains": q.CHAINS,
            "reference_costs": q.REFERENCE_COSTS,
            "baseline_ratios": q.BASELINE_RATIOS,
            "baseline_score": q.score_ratios(q.BASELINE_RATIOS),
            "venv_qvc": str(ROOT / ".venv-qvc" / "bin" / "python"),
            "venv_chem": str(ROOT / ".venv-chem" / "bin" / "python"),
            "runs_dir": str(RUNS_DIR),
            "adapters_dir": str(ADAPTERS_DIR),
            "examples_dir": str(EXAMPLES_DIR),
        })

    @app.post("/api/jobs")
    async def create_job(request: Request) -> JSONResponse:
        body = await _json_body(request)
        kind = body.get("kind")
        params = body.get("params") or {}
        if not isinstance(params, dict):
            raise HTTPException(400, "params must be an object")
        try:
            jid = submit_job(kind, params)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        return JSONResponse({"job_id": jid})

    @app.get("/api/jobs")
    def list_jobs() -> JSONResponse:
        with _JOBS_LOCK:
            items = sorted(JOBS.values(), key=lambda j: j.get("created", 0), reverse=True)[:50]
        slim = [{"id": j["id"], "kind": j["kind"], "status": j["status"],
                 "created": j.get("created"), "finished": j.get("finished"),
                 "error": j.get("error")} for j in items]
        return JSONResponse({"jobs": slim})

    @app.get("/api/jobs/{jid}")
    def get_job(jid: str) -> JSONResponse:
        job = JOBS.get(jid)
        if job is None:
            raise HTTPException(404, "unknown job")
        return JSONResponse(job)

    @app.get("/api/trace")
    def trace() -> JSONResponse:
        return JSONResponse({"trace": tracer.TRACE.snapshot()})

    @app.get("/api/logs")
    def logs() -> JSONResponse:
        return JSONResponse({"logs": tracer.LOGS.snapshot()})

    @app.get("/api/artifacts")
    def artifacts() -> JSONResponse:
        base = RUNS_DIR.resolve()
        files = []
        for f in sorted(base.rglob("*")):
            if f.is_file():
                try:
                    rel = f.relative_to(base).as_posix()
                except ValueError:
                    continue
                files.append({"path": rel, "size": f.stat().st_size})
                if len(files) >= 2000:
                    break
        return JSONResponse({"root": str(base), "files": files})

    @app.get("/api/artifact")
    def read_artifact(request: Request) -> JSONResponse:
        rel = request.query_params.get("path", "")
        if not rel:
            raise HTTPException(400, "missing ?path=")
        base = RUNS_DIR.resolve()
        target = (base / rel).resolve()
        if target != base and base not in target.parents:
            raise HTTPException(400, "path escapes runs/")
        if not target.is_file():
            raise HTTPException(404, "not a file")
        raw = target.read_bytes()
        text = raw.decode("utf-8", errors="replace")
        truncated = len(text) > 2_000_000
        parsed = None
        if target.suffix == ".json":
            try:
                parsed = json.loads(text)
            except Exception:
                parsed = None
        return JSONResponse({"path": rel, "size": len(raw), "truncated": truncated,
                             "text": text[:2_000_000], "json": parsed})

    @app.get("/api/examples")
    def examples() -> JSONResponse:
        out = {}
        for name in ("verified_costs_example.json", "adapter_invsqrt.json"):
            fp = EXAMPLES_DIR / name
            if fp.exists():
                out[name] = json.loads(fp.read_text(encoding="utf-8"))
        return JSONResponse({"examples": out})

    return app


async def _json_body(request: Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("QVC_UI_HOST", "127.0.0.1")
    port = int(os.getenv("QVC_UI_PORT", "8790"))
    app = _build_app()
    print(f"QVC debug UI on http://{host}:{port}  (Ctrl-C to stop)")
    uvicorn.run(app, host=host, port=port, log_level="warning")
