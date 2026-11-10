"""FastAPI backend for the QVC Discovery debug UI.

Run:  .venv-qvc/bin/python -m uvicorn qvc_web.backend.main:app --host 127.0.0.1 --port 8791
or:   .venv-qvc/bin/python qvc_web/backend/main.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import qvc_discovery as q  # noqa: E402  (already patched by jobs import below)
from . import jobs
from . import team
from .config import ADAPTERS_DIR, EXAMPLES_DIR, ROOT, RUNS_DIR, VENV_CHEM, VENV_QVC

app = FastAPI(title="QVC Discovery API", version="2.0")
# CORS: the browser reaches the API same-origin via the Next.js /api proxy, so the app
# never needs cross-origin access. We deliberately do NOT use "*": only the local
# frontend origin(s) are allowed, which blocks drive-by exfil from arbitrary web pages.
# Override with QVC_WEB_CORS_ORIGINS (comma-separated) if you host the UI elsewhere.
_cors_origins = [o.strip() for o in os.getenv("QVC_WEB_CORS_ORIGINS", "").split(",") if o.strip()] \
    or ["http://localhost:3000", "http://127.0.0.1:3000"]
app.add_middleware(CORSMiddleware, allow_origins=_cors_origins, allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health() -> JSONResponse:
    return JSONResponse({"ok": True, "service": "qvc-discovery-api"})


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
        "venv_qvc": VENV_QVC,
        "venv_chem": VENV_CHEM,
        "runs_dir": str(RUNS_DIR),
        "adapters_dir": str(ADAPTERS_DIR),
        "examples_dir": str(EXAMPLES_DIR),
    })


async def _json_body(request: Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


@app.post("/api/jobs")
async def create_job(request: Request) -> JSONResponse:
    body = await _json_body(request)
    kind = body.get("kind")
    params = body.get("params") or {}
    if not isinstance(params, dict):
        raise HTTPException(400, "params must be an object")
    try:
        jid = jobs.submit_job(kind, params)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return JSONResponse({"job_id": jid})


@app.get("/api/jobs")
def list_jobs() -> JSONResponse:
    with jobs._JOBS_LOCK:
        items = sorted(jobs.JOBS.values(), key=lambda j: j.get("created", 0), reverse=True)[:50]
    slim = [{"id": j["id"], "kind": j["kind"], "status": j["status"],
             "created": j.get("created"), "finished": j.get("finished"),
             "error": j.get("error")} for j in items]
    return JSONResponse({"jobs": slim})


@app.get("/api/jobs/{jid}")
def get_job(jid: str) -> JSONResponse:
    job = jobs.JOBS.get(jid)
    if job is None:
        raise HTTPException(404, "unknown job")
    return JSONResponse(job)


@app.get("/api/trace")
def trace() -> JSONResponse:
    from .tracer import TRACE
    return JSONResponse({"trace": TRACE.snapshot()})


@app.get("/api/logs")
def logs() -> JSONResponse:
    from .tracer import LOGS
    return JSONResponse({"logs": LOGS.snapshot()})


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
    out: dict[str, Any] = {}
    for name in ("verified_costs_example.json",):
        fp = EXAMPLES_DIR / name
        if fp.exists():
            out[name] = json.loads(fp.read_text(encoding="utf-8"))
    return JSONResponse({"examples": out})


@app.get("/api/models")
def list_models() -> JSONResponse:
    return JSONResponse({"models": team.list_models()})


@app.post("/api/models")
async def add_model(request: Request) -> JSONResponse:
    body = await _json_body(request)
    try:
        m = team.add_model(body)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return JSONResponse({"model": m})


@app.get("/api/competition-brief")
def competition_brief() -> JSONResponse:
    """Return the curated official competition prompt (repo-root competition_brief.md)."""
    fp = ROOT / "competition_brief.md"
    if not fp.is_file():
        raise HTTPException(404, "competition_brief.md not found at repo root")
    text = fp.read_text(encoding="utf-8").strip()
    return JSONResponse({"path": "competition_brief.md", "chars": len(text), "text": text})


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("QVC_API_HOST", "127.0.0.1")
    port = int(os.getenv("QVC_API_PORT", "8791"))
    print(f"QVC Discovery API on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")
