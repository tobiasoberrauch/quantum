"""Weinstadt-Qwen3.8 LLM client + endpoint resolution for the qvc_agent loop.

Stdlib-only HTTP (urllib). The live Weinstadt endpoint is keyless: when the
provider config has no ``apiKey`` (or it resolves to nothing) ``api_key`` is
``None`` and no ``Authorization`` header is sent.

The API key is never printed, logged, or written anywhere; every error message
is passed through :func:`redact` before being raised.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_MODEL = "qwen3.8-27b"
DEFAULT_PROVIDER = "audius-we"  # live, keyless
FALLBACK_PROVIDER = "audius-dev-gw"
DEFAULT_MAX_TOKENS = 32000


class WeinstadtError(RuntimeError):
    """Raised for any client-side failure (network, HTTP, empty/malformed reply)."""


def redact(value: Any, secret: Optional[str]) -> Any:
    """Return ``value`` with ``secret`` replaced by ``[REDACTED]``.

    Defensive: ``None``/empty/whitespace secrets leave the value unchanged so a
    keyless client never corrupts its own messages.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    if secret is None:
        return value
    s = str(secret)
    if not s.strip():
        return value
    return value.replace(s, "[REDACTED]")


def opencode_config_path() -> Path:
    """Path to the opencode config: ``$QVC_OPENCODE_CONFIG`` or the default."""
    p = os.getenv("QVC_OPENCODE_CONFIG")
    if p and p.strip():
        return Path(p).expanduser()
    return Path.home() / ".config" / "opencode" / "opencode.json"


def resolve_endpoint(*, provider: str = DEFAULT_PROVIDER) -> Dict[str, Any]:
    """Resolve ``{"base_url", "api_key", "model"}`` from config + env overrides.

    ``api_key`` is ``None`` for a keyless endpoint. Env vars
    ``QVC_LLM_BASE_URL`` / ``QVC_LLM_API_KEY`` / ``QVC_LLM_MODEL`` take
    precedence over the config file.
    """
    if not provider or not str(provider).strip():
        provider = DEFAULT_PROVIDER
    provider = str(provider).strip()

    cfg_path = opencode_config_path()
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    opts = cfg["provider"][provider]["options"]
    base_url = opts["baseURL"]

    raw = opts.get("apiKey")
    if raw is None or not str(raw).strip():
        api_key: Optional[str] = None
    elif isinstance(raw, str) and raw.startswith("{env:") and raw.endswith("}"):
        name = raw[5:-1].strip()
        api_key = os.getenv(name) if name else None
    else:
        api_key = raw

    # Env overrides win; ignore empty/whitespace values so they don't clobber.
    b = os.getenv("QVC_LLM_BASE_URL")
    if b and b.strip():
        base_url = b
    k = os.getenv("QVC_LLM_API_KEY")
    if k and k.strip():
        api_key = k
    m = os.getenv("QVC_LLM_MODEL")
    model = m if (m and m.strip()) else DEFAULT_MODEL

    return {"base_url": base_url, "api_key": api_key, "model": model}


class WeinstadtClient:
    """Minimal OpenAI-compatible chat client for the Weinstadt Qwen3.8 gateway."""

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        timeout: float = 180,
    ) -> None:
        self.base_url = base_url.rstrip("/") if isinstance(base_url, str) else ""
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout

    def chat(
        self, messages: List[Dict[str, str]], *, temperature: float = 0.4
    ) -> str:
        """POST ``/chat/completions`` and return the assistant message content."""
        if messages is None:
            messages = []
        if not self.base_url:
            raise WeinstadtError(redact("NoBaseURL: base_url is empty", self.api_key))

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": temperature,
        }
        url = self.base_url + "/chat/completions"
        req = urllib.request.Request(
            url, data=json.dumps(body).encode(), headers=headers, method="POST"
        )

        try:
            resp = urllib.request.urlopen(req, timeout=self.timeout)
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            raise WeinstadtError(
                redact(f"{type(e).__name__}: {e}", self.api_key)
            ) from e

        try:
            data = json.loads(resp.read())
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise WeinstadtError(
                redact(f"{type(e).__name__}: {e}", self.api_key)
            ) from e

        if content is None or (isinstance(content, str) and not content.strip()):
            raise WeinstadtError(
                redact("EmptyResponse: empty or missing content", self.api_key)
            )
        return content
