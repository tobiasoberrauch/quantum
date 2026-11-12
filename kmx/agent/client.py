"""OpenAI-kompatibler Chat-Client (Standard: lokale Weinstadt-KI) mit Wiederholungen
und Erreichbarkeitstest.
"""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from kmx.agent.tools import ToolSchema
from kmx.config import (
    LLM_DEFAULT_MAX_CALLS,
    LLM_DEFAULT_MAX_TOKENS,
    LOCAL_LLM_EXTRA_BODY,
    LOCAL_LLM_MODEL,
    LOCAL_LLM_TEMPERATURE,
    LOCAL_LLM_TIMEOUT_S,
    LOCAL_LLM_URL,
    REMOTE_LLM_TIMEOUT_S,
    env_text,
)

ChatMessage = dict[str, Any]  # Nachricht im OpenAI-Chat-Format

# Die Standardwerte (lokaler Endpunkt, Timeouts, Budgets) stehen in kmx.config und
# sind hier unter denselben Namen erreichbar (kmx.agent.client.LOCAL_LLM_URL).
LLM_ATTEMPTS = 4
LLM_RETRYABLE_HTTP = (408, 409, 429, 500, 502, 503, 504)
# Wartezeit nach Versuch n (ab 0): min(LLM_BACKOFF_MAX_S, 2^n * Basis)
LLM_BACKOFF_BASE_S = 2
LLM_BACKOFF_MAX_S = 30
LLM_ERROR_BODY_CHARS = 300
REACHABILITY_TIMEOUT_S = 3.0  # TCP-Test vor der LLM-Stufe


class LLMError(RuntimeError):
    """Fehlgeschlagener LLM-Aufruf; `code` ist der HTTP-Status, falls es einen gab."""

    def __init__(self, msg: str, code: int | None = None) -> None:
        super().__init__(msg)
        self.code = code


class LLMClient:
    """Client für OpenAI-kompatible Chat-Completions. Ohne Konfiguration spricht er die
    lokale Weinstadt-KI an (kein Schlüssel nötig); mit LLM_API_URL / --api-url jeden
    anderen Endpunkt (OpenRouter, OpenAI, LiteLLM, vLLM). Aufrufbudget (LLM_MAX_CALLS)
    und Circuit-Breaker: Ist der Server weg, wird nicht weiter probiert.
    """

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        max_calls: int | None = None,
    ) -> None:
        self.api_url = api_url or env_text("LLM_API_URL") or LOCAL_LLM_URL
        self.local_default = self.api_url == LOCAL_LLM_URL
        self.api_key = (
            api_key
            or env_text("LLM_API_KEY")
            or env_text("OPENROUTER_API_KEY")
            or env_text("OPENAI_API_KEY")
        )
        default_timeout = (
            LOCAL_LLM_TIMEOUT_S if self.local_default else REMOTE_LLM_TIMEOUT_S
        )
        self.timeout = float(timeout or env_text("LLM_TIMEOUT") or default_timeout)
        self.max_tokens = int(
            max_tokens or env_text("LLM_MAX_TOKENS") or LLM_DEFAULT_MAX_TOKENS
        )
        self.max_calls = int(
            max_calls
            if max_calls is not None
            else env_text("LLM_MAX_CALLS") or LLM_DEFAULT_MAX_CALLS
        )
        temp = temperature if temperature is not None else env_text("LLM_TEMPERATURE")
        default_temperature = LOCAL_LLM_TEMPERATURE if self.local_default else None
        self.temperature = (
            float(temp) if temp not in (None, "") else default_temperature
        )
        default_extra_body = LOCAL_LLM_EXTRA_BODY if self.local_default else "{}"
        self.extra_body = json.loads(env_text("LLM_EXTRA_BODY") or default_extra_body)
        self.extra_headers = json.loads(env_text("LLM_EXTRA_HEADERS", "{}"))
        self.calls = 0
        self.dead = False

    def default_models(self) -> list[str]:
        """Modelle aus LLM_MODEL (kommagetrennt); ohne Angabe das lokale Standardmodell
        (nur am lokalen Endpunkt)."""
        listed = [m for m in (env_text("LLM_MODEL") or "").split(",") if m.strip()]
        return listed or ([LOCAL_LLM_MODEL] if self.local_default else [])

    def reachable(self, timeout: float = REACHABILITY_TIMEOUT_S) -> bool:
        """Kurzer TCP-Test, damit ein nicht erreichbarer Server nicht erst nach dem
        vollen Timeout auffällt."""
        u = urllib.parse.urlparse(self.api_url)
        port = u.port or (443 if u.scheme == "https" else 80)
        try:
            with socket.create_connection((u.hostname, port), timeout=timeout):
                return True
        except OSError:
            self.dead = True
            return False

    def exhausted(self) -> bool:
        """Kein weiterer Aufruf möglich: Server weg oder Aufrufbudget verbraucht."""
        return self.dead or self.calls >= self.max_calls

    def _request_body(
        self, model: str, messages: list[ChatMessage], tools: list[ToolSchema] | None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": self.max_tokens,
        }
        if tools:
            body["tools"], body["tool_choice"] = tools, "auto"
        if self.temperature is not None:
            body["temperature"] = self.temperature
        if isinstance(self.extra_body, dict):
            body.update(self.extra_body)
        return body

    def _request_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", **self.extra_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def chat(
        self,
        model: str,
        messages: list[ChatMessage],
        tools: list[ToolSchema] | None = None,
    ) -> ChatMessage:
        """Ein Chat-Completion-Aufruf; liefert die Antwortnachricht des Modells.

        Vorübergehende Fehler (Timeout, unlesbare Antwort, LLM_RETRYABLE_HTTP) werden
        mit wachsender Wartezeit wiederholt. Ein Verbindungsfehler schaltet den
        Client dauerhaft ab (`dead`). Jeder Aufruf zählt gegen das Budget, unabhängig
        von der Zahl der Versuche."""
        if self.dead:
            raise LLMError("LLM-Endpunkt nicht erreichbar")
        if self.calls >= self.max_calls:
            raise LLMError(f"LLM-Budget erschöpft (LLM_MAX_CALLS={self.max_calls})")
        self.calls += 1
        body = self._request_body(model, messages, tools)
        headers = self._request_headers()
        last, code = "", None
        for attempt in range(LLM_ATTEMPTS):
            req = urllib.request.Request(
                self.api_url, data=json.dumps(body).encode("utf-8"), headers=headers
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                if not data.get("choices"):
                    raise LLMError(
                        "Antwort ohne 'choices': "
                        f"{json.dumps(data)[:LLM_ERROR_BODY_CHARS]}"
                    )
                return data["choices"][0]["message"]
            except urllib.error.HTTPError as e:
                last = (
                    f"HTTP {e.code}: "
                    f"{e.read().decode('utf-8', 'replace')[:LLM_ERROR_BODY_CHARS]}"
                )
                code = e.code
                if e.code not in LLM_RETRYABLE_HTTP:
                    break
            except urllib.error.URLError as e:
                self.dead = True
                raise LLMError(f"LLM-Endpunkt nicht erreichbar: {e.reason}") from e
            except (TimeoutError, json.JSONDecodeError) as e:
                last = f"{type(e).__name__}: {e}"
            time.sleep(min(LLM_BACKOFF_MAX_S, 2**attempt * LLM_BACKOFF_BASE_S))
        raise LLMError(f"LLM-Aufruf fehlgeschlagen ({model}): {last}", code)
