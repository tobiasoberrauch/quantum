"""Multi-agent team discussion for qvc_web.

Lets a user define a TEAM of agents — each agent is a (role, model) pair — and run
a role-based conversation from a single starting prompt. The team can mix LOCAL
models (own hardware, keyless) and CLOUD models (OpenRouter / any OpenAI-compatible
endpoint). After N rounds a SYNTHESIS step produces the single best solution that
emerges from the discussion.

Design goals:
- One uniform model primitive: every model is just ``{base_url, model, api_key_env?}``
  and is called over the OpenAI-compatible ``/chat/completions`` API. Adding a new
  model (e.g. a freshly released one) is a registry entry, not a code change.
- No secrets on disk: keys are referenced by ENV VAR NAME only (``api_key_env``);
  local models are keyless. Custom models persist to a gitignored JSON that holds no
  key material.
- Stdlib-only HTTP (urllib) so it runs in ``.venv-qvc`` with no new dependencies.
- Every LLM call is traced to :data:`tracer.TRACE` so it appears in the Live tab.

The heavy collaborator (the HTTP layer) is injectable so the orchestrator is
unit-testable offline.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import qvc_discovery as q  # noqa: E402  reuse known-good cloud model IDs + write_json
from . import tracer
from .config import RUNS_DIR, TEAM_MODELS_FILE

# Per-call timeout (seconds). Reasoning models can generate long chains; env-overridable.
TIMEOUT_S = int(os.getenv("QVC_TEAM_TIMEOUT_S", "900"))
DEFAULT_MAX_TOKENS = int(os.getenv("QVC_TEAM_MAX_TOKENS", "4096"))


# --------------------------------------------------------------------------- #
# HTTP layer (injectable for tests)                                           #
# --------------------------------------------------------------------------- #
def _http_post_json(url: str, payload: Dict[str, Any], headers: Dict[str, str],
                    timeout: float) -> Dict[str, Any]:
    """POST ``payload`` as JSON to ``url``; return the parsed JSON response."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:  # surface status + short body for debugging
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code} from {url}: {body}") from None


DEFAULT_HTTP: Callable[..., Dict[str, Any]] = _http_post_json


# --------------------------------------------------------------------------- #
# Model registry                                                              #
# --------------------------------------------------------------------------- #
def _env_str(name: str, default: str) -> str:
    """Read an env var; fall back to ``default`` when unset/empty/whitespace."""
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip()
    return v if v else default


def _preset_models() -> List[Dict[str, Any]]:
    local_base = _env_str("QVC_LOCAL_BASE_URL", "http://192.168.212.81:8000/v1")
    local_model = _env_str("QVC_LOCAL_MODEL", "qwen3.8-27b")
    or_base = "https://openrouter.ai/api/v1"
    # FreeToken (FlashML): self-hosted MoE engine, OpenAI-compatible, keyless.
    # Point FREETOKEN_BASE_URL at the GPU host running `ft serve` (default localhost).
    ft_base = _env_str("FREETOKEN_BASE_URL", "http://127.0.0.1:1919/v1").rstrip("/")
    ft_model = _env_str("FREETOKEN_MODEL", "Qwen3.6-35B-A3B")
    ft_host = ft_base.split("//", 1)[-1].split("/", 1)[0]
    # Ollama (Apple Silicon / local): OpenAI-compatible at :11434/v1, keyless.
    # FreeToken needs NVIDIA+Linux, so Ollama is the Mac-native way to run local
    # models as team colleagues. Point OLLAMA_BASE_URL/OLLAMA_MODEL at any Ollama model.
    ol_base = _env_str("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1").rstrip("/")
    ol_model = _env_str("OLLAMA_MODEL", "qwen3.5:27b")
    ol_host = ol_base.split("//", 1)[-1].split("/", 1)[0]
    return [
        {"id": "local-qwen", "label": f"Qwen · lokal ({local_model})", "kind": "local",
         "base_url": local_base, "model": local_model, "api_key_env": "",
         "max_tokens": 4096,
         # Qwen3 reasoning model: disable private thinking so it emits direct, fast
         # content (a team discussion externalizes the reasoning across agents anyway).
         "extra_body": {"chat_template_kwargs": {"enable_thinking": False}}},
        {"id": "freetoken", "label": f"FreeToken · {ft_model} @ {ft_host}", "kind": "local",
         "base_url": ft_base, "model": ft_model, "api_key_env": ""},
        {"id": "ollama", "label": f"Ollama · {ol_model} @ {ol_host}", "kind": "local",
         "base_url": ol_base, "model": ol_model, "api_key_env": "",
         # Ollama's Qwen3.x are thinking models: they emit `content` only after burning
         # reasoning tokens, so give a large budget (harmless for non-thinking models,
         # which stop early). Ollama ignores options.think via its OpenAI endpoint.
         "max_tokens": 16000},
        {"id": "cloud-opus", "label": "Claude Opus · Cloud", "kind": "cloud",
         "base_url": or_base, "model": q.OPUS, "api_key_env": "OPENROUTER_API_KEY"},
        {"id": "cloud-gpt", "label": "GPT-5.5 · Cloud", "kind": "cloud",
         "base_url": or_base, "model": q.GPT55, "api_key_env": "OPENROUTER_API_KEY"},
        {"id": "cloud-gemini", "label": "Gemini 3.1 · Cloud", "kind": "cloud",
         "base_url": or_base, "model": q.GEMINI, "api_key_env": "OPENROUTER_API_KEY"},
        {"id": "cloud-sonnet", "label": "Claude Sonnet 5 · Cloud", "kind": "cloud",
         "base_url": or_base, "model": q.SONNET5, "api_key_env": "OPENROUTER_API_KEY"},
    ]


def _load_custom_models() -> List[Dict[str, Any]]:
    try:
        data = json.loads(TEAM_MODELS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    out: List[Dict[str, Any]] = []
    for m in data:
        if not isinstance(m, dict):
            continue
        mid = m.get("id")
        base = m.get("base_url")
        model = m.get("model")
        if not (isinstance(mid, str) and mid.strip()
                and isinstance(base, str) and base.strip()
                and isinstance(model, str) and model.strip()):
            continue
        kind = str(m.get("kind") or "custom").strip()
        if kind not in ("local", "cloud"):
            kind = "custom"
        entry: Dict[str, Any] = {
            "id": mid.strip(), "label": str(m.get("label") or mid).strip(),
            "kind": kind, "base_url": base.strip(), "model": model.strip(),
            "api_key_env": str(m.get("api_key_env") or "").strip(),
        }
        mt = m.get("max_tokens")
        if isinstance(mt, (int, float)) and mt > 0:
            entry["max_tokens"] = int(mt)
        eb = m.get("extra_body")
        if isinstance(eb, dict):
            entry["extra_body"] = eb
        out.append(entry)
    return out


def list_models() -> List[Dict[str, Any]]:
    """Preset + custom models. Entries expose NO secret (keys are env-var names)."""
    seen: set = set()
    out: List[Dict[str, Any]] = []
    for m in _preset_models() + _load_custom_models():
        if m["id"] in seen:
            continue
        seen.add(m["id"])
        out.append(m)
    return out


def get_model(model_id: Any) -> Dict[str, Any]:
    mid = str(model_id or "").strip()
    for m in list_models():
        if m["id"] == mid:
            return m
    raise KeyError(f"unknown model id '{mid}'")


def add_model(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Persist a custom model (env-var key reference only). Returns the stored entry."""
    if not isinstance(cfg, dict):
        raise ValueError("model config must be an object")
    mid = str(cfg.get("id") or "").strip()
    base = str(cfg.get("base_url") or "").strip()
    model = str(cfg.get("model") or "").strip()
    if not mid or not base or not model:
        raise ValueError("id, base_url and model are all required")
    if not (base.startswith("http://") or base.startswith("https://")):
        raise ValueError("base_url must start with http:// or https://")
    kind = str(cfg.get("kind") or "custom").strip()
    if kind not in ("local", "cloud"):
        kind = "custom"
    entry: Dict[str, Any] = {
        "id": mid, "label": str(cfg.get("label") or mid).strip(),
        "kind": kind, "base_url": base, "model": model,
        "api_key_env": str(cfg.get("api_key_env") or "").strip(),
    }
    mt = _to_int(cfg.get("max_tokens"), None)
    if mt and mt > 0:
        entry["max_tokens"] = mt
    eb = cfg.get("extra_body")
    if isinstance(eb, dict):
        entry["extra_body"] = eb
    customs = [c for c in _load_custom_models() if c["id"] != mid]
    customs.append(entry)
    TEAM_MODELS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TEAM_MODELS_FILE.write_text(json.dumps(customs, ensure_ascii=False, indent=2),
                                encoding="utf-8")
    return entry


# --------------------------------------------------------------------------- #
# Unified OpenAI-compatible chat client                                       #
# --------------------------------------------------------------------------- #
def _resolve_api_key(model: Dict[str, Any]) -> Optional[str]:
    env_name = str(model.get("api_key_env") or "").strip()
    if not env_name:
        return None
    val = os.getenv(env_name, "").strip()
    return val or None


def _assert_http_url(url: str) -> None:
    """Only http/https endpoints are allowed (blocks file://, gopher://, …)."""
    if not (url.startswith("http://") or url.startswith("https://")):
        raise ValueError(f"base_url must be http(s), got: {url[:80]!r}")


def _to_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """Coerce to int; return ``default`` for None/empty/garbage."""
    try:
        if value is None or (isinstance(value, str) and not value.strip()):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float) -> float:
    """Coerce to float; return ``default`` for None/empty/garbage."""
    try:
        if value is None or (isinstance(value, str) and not value.strip()):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def chat(model: Dict[str, Any], messages: List[Dict[str, str]], *,
         temperature: float = 0.7, max_tokens: Optional[int] = None,
         http: Callable[..., Dict[str, Any]] = DEFAULT_HTTP,
         schema_name: str = "team", _allow_retry: bool = True) -> Dict[str, Any]:
    """One chat completion against an OpenAI-compatible endpoint.

    Returns ``{"content": str, "model": str, "usage": dict}``. Raises on transport
    or parse failure. Every call is appended to :data:`tracer.TRACE` (Live tab).
    """
    base = str((model or {}).get("base_url") or "").strip().rstrip("/")
    if not base:
        raise ValueError("model.base_url is required")
    url = base + "/chat/completions"
    _assert_http_url(url)
    headers = {"Content-Type": "application/json"}
    key = _resolve_api_key(model)
    if key:
        headers["Authorization"] = f"Bearer {key}"
    mt = _to_int(max_tokens, None) or _to_int(model.get("max_tokens"), None) or DEFAULT_MAX_TOKENS
    # extra_body carries provider-specific params only; core fields are applied AFTER
    # so a model entry can never override `model`/`messages`/`temperature`/`max_tokens`.
    extra = model.get("extra_body")
    payload: Dict[str, Any] = {}
    if isinstance(extra, dict):
        payload.update(extra)
    payload.update({
        "model": model.get("model"), "messages": messages,
        "temperature": temperature, "max_tokens": mt,
    })
    rec: Dict[str, Any] = {
        "schema": schema_name, "chain": [model.get("model")],
        "prompt": json.dumps(messages)[:60000], "started": round(time.time(), 3),
        "ok": False, "attempts": [], "requested_model": model.get("model"),
    }
    tracer.TRACE.append(rec)
    t0 = time.time()
    try:
        resp = http(url, payload, headers, TIMEOUT_S)
    except Exception as exc:
        rec["ok"] = False
        rec["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        rec["elapsed"] = round(time.time() - t0, 3)
        raise
    try:
        content = resp["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        rec["ok"] = False
        rec["error"] = "malformed response (missing choices[0].message.content)"
        rec["elapsed"] = round(time.time() - t0, 3)
        raise RuntimeError(rec["error"]) from None
    usage = resp.get("usage") or {}
    rec["ok"] = True
    rec["served_model"] = resp.get("model") or model.get("model")
    rec["usage"] = {"prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0), "cost": 0.0}
    rec["elapsed"] = round(time.time() - t0, 3)
    if not (content or "").strip() and _allow_retry:
        # Reasoning model consumed the whole budget on thinking -> empty content.
        # Retry once, decisively: lower temperature (shorter reasoning) + more headroom.
        rec["note"] = "empty content; auto-retry (lower temp, higher max_tokens)"
        return chat(model, messages, temperature=min(temperature, 0.2),
                    max_tokens=min(mt * 2, 32768), http=http,
                    schema_name=schema_name, _allow_retry=False)
    return {"content": content or "", "model": resp.get("model") or model.get("model"),
            "usage": usage}


# --------------------------------------------------------------------------- #
# Team discussion orchestrator                                                #
# --------------------------------------------------------------------------- #
def _agent_system(role: str, name: str) -> str:
    return (f"You are '{name}', one member of a small expert team collaborating on a "
            f"shared goal. Your role/perspective: {role or 'general expert'}. "
            f"Contribute concretely: add new signal, build on others, and challenge "
            f"weak points. Be direct and focused; do not pad.")


def run_team(params: Dict[str, Any], *,
             http: Callable[..., Dict[str, Any]] = DEFAULT_HTTP) -> Dict[str, Any]:
    """Run a bounded multi-agent discussion + synthesis. Returns the result dict.

    ``params``:
      - starting_prompt (str, required)
      - agents: [{name, role, model_id}, ...] (required, >=1 valid)
      - rounds (int, 1..6, default 1)
      - synthesis_model_id (str, optional; defaults to the last agent's model)
      - temperature (float, default 0.7), max_tokens (int, optional global cap)
    """
    if not isinstance(params, dict):
        raise ValueError("params must be an object")
    starting = str(params.get("starting_prompt") or "").strip()
    if not starting:
        raise ValueError("starting_prompt is required")

    agents: List[Dict[str, Any]] = []
    for a in (params.get("agents") or []):
        if not isinstance(a, dict):
            continue
        name = str(a.get("name") or "").strip()
        role = str(a.get("role") or "").strip()
        mid = str(a.get("model_id") or "").strip()
        if not name or not mid:
            continue
        agents.append({"name": name, "role": role, "model": get_model(mid)})
    if not agents:
        raise ValueError("at least one agent with a name and model_id is required")

    rounds = max(1, min(6, _to_int(params.get("rounds"), 1) or 1))
    temperature = _to_float(params.get("temperature"), 0.7)
    synthesis_temp = _to_float(params.get("synthesis_temperature"), 0.3)
    global_mt = _to_int(params.get("max_tokens"), None)

    synth_mid = str(params.get("synthesis_model_id") or "").strip()
    synth_model = get_model(synth_mid) if synth_mid else agents[-1]["model"]

    transcript: List[Dict[str, Any]] = []
    history: List[Dict[str, str]] = [
        {"role": "user", "content": f"Shared goal / starting prompt:\n{starting}"}
    ]
    for r in range(1, rounds + 1):
        for ag in agents:
            msgs = [{"role": "system", "content": _agent_system(ag["role"], ag["name"])},
                    *history,
                    {"role": "user",
                     "content": f"(Round {r}/{rounds}) As {ag['name']}, respond to the "
                                f"discussion so far."}]
            # One flaky/failed agent must not kill the whole team: record the error,
            # leave it out of the shared history, and let the others + synthesis proceed.
            try:
                out = chat(ag["model"], msgs, temperature=temperature,
                           max_tokens=global_mt,
                           http=http, schema_name=f"team:{ag['name']}")
                content = out["content"].strip()
                status = "ok"
            except Exception as exc:  # noqa: BLE001 - degrade, don't abort the team
                content = (f"[{ag['name']}] konnte nicht antworten "
                           f"({type(exc).__name__}: {str(exc)[:120]})")
                status = "error"
            transcript.append({"round": r, "agent": ag["name"], "role": ag["role"],
                               "model": ag["model"].get("model"), "content": content,
                               "status": status})
            if status == "ok":
                history.append({"role": "assistant", "content": f"{ag['name']}: {content}"})

    synth_msgs = [
        {"role": "system",
         "content": "You are the team synthesizer. Read the full discussion and produce "
                    "the single best solution/answer that emerges from it. Be concrete "
                    "and decisive; state where the team agreed and how you resolved "
                    "conflicts."},
        {"role": "user",
         "content": f"Starting prompt:\n{starting}\n\nFull team discussion:\n" +
                    "\n\n".join(f"[r{t['round']}] {t['agent']} ({t['model']}):\n{t['content']}"
                                for t in transcript)},
    ]
    synth_out = chat(synth_model, synth_msgs,
                     temperature=synthesis_temp,
                     max_tokens=global_mt,
                     http=http, schema_name="team:synthesis")
    final_solution = synth_out["content"].strip()

    outdir = RUNS_DIR / f"team_{time.strftime('%Y%m%d_%H%M%S')}"
    outdir.mkdir(parents=True, exist_ok=True)
    result: Dict[str, Any] = {
        "starting_prompt": starting,
        "agents": [{"name": a["name"], "role": a["role"], "model": a["model"].get("model")}
                   for a in agents],
        "rounds": rounds,
        "transcript": transcript,
        "final_solution": final_solution,
        "synthesis_model": synth_model.get("model"),
    }
    q.write_json(outdir / "team.json", result)
    (outdir / "solution.md").write_text(final_solution, encoding="utf-8")
    result["files"] = {"team_json": str(outdir / "team.json"),
                       "solution_md": str(outdir / "solution.md")}
    return result
