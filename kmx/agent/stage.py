"""LLM-Stufe der Pipeline: wählt Tool-Calling oder JSON-Modus und überspringt nicht
erreichbare Endpunkte.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from kmx.agent.client import LLMClient
from kmx.agent.json_mode import JsonMemo, run_json_llm
from kmx.agent.relay import AGENT_DEFAULT_RELAY_ROUNDS, AGENT_DEFAULT_STEPS, run_agent
from kmx.agent.workbench import Workbench
from kmx.config import env_text
from kmx.session import Session

LLM_MODE_AUTO, LLM_MODE_TOOLS, LLM_MODE_JSON = "auto", "tools", "json"


@dataclass(frozen=True)
class LLMStageOptions:
    """Einstellungen der LLM-Stufe (Kommandozeile). None heißt: Umgebungsvariable
    bzw. Standard des Clients (siehe LLMClient)."""

    api_url: str | None = None
    timeout: float | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    models: str | None = None  # kommagetrennte Modell-IDs
    steps: int = AGENT_DEFAULT_STEPS
    relay: int = AGENT_DEFAULT_RELAY_ROUNDS
    playbook_path: str | None = None  # Textdatei mit Recherche-Ergebnissen
    exact_only: bool = False


def _llm_mode() -> str:
    """LLM_MODE (auto|tools|json), leer oder ungesetzt = auto."""
    return (env_text("LLM_MODE") or LLM_MODE_AUTO).strip().lower() or LLM_MODE_AUTO


def _read_playbook(path: str | None) -> str:
    if not path:
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read()


def llm_stage(
    s: Session, opts: LLMStageOptions, log: Callable[[str], None] = print
) -> None:
    """LLM-Stufe: Tool-Calling-Agent, wo das Modell es kann; sonst JSON-Modus.
    LLM_MODE=auto|tools|json."""
    mode = _llm_mode()
    client = LLMClient(
        opts.api_url,
        timeout=opts.timeout,
        temperature=opts.temperature,
        max_tokens=opts.max_tokens,
    )
    models = [
        m.strip() for m in (opts.models or "").split(",") if m.strip()
    ] or client.default_models()
    if not models:
        log("LLM-Stufe übersprungen: kein Modell angegeben (--models oder LLM_MODEL).")
        return
    if not env_text("LLM_MAX_CALLS"):
        client.max_calls = max(1, opts.steps * len(models) * opts.relay)
    if not client.reachable():
        log(f"LLM-Stufe übersprungen: {client.api_url} ist nicht erreichbar.")
        return
    playbook = _read_playbook(opts.playbook_path)
    wb = Workbench(s, exact_only=opts.exact_only)
    rest = (
        list(models)
        if mode == LLM_MODE_JSON
        else run_agent(wb, client, models, opts.steps, opts.relay, playbook, log)
    )
    if mode != LLM_MODE_TOOLS:
        memo: JsonMemo = {}
        for model in rest:
            run_json_llm(wb, client, model, log, memo)
    if wb.accepted:
        wb.run_passes()
    res = wb.full_check()
    log(f"  Abschlussprüfung nach der LLM-Stufe: {res['meldung']}")
