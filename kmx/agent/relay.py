"""Tool-Calling-Agent: Staffellauf über mehrere Modelle mit gekürzter Historie."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from typing import Any

from kmx.agent.client import ChatMessage, LLMClient, LLMError
from kmx.agent.tools import AGENT_SYSTEM, TOOLS
from kmx.agent.workbench import Workbench

AGENT_DEFAULT_STEPS = 40  # Tool-Schritte je Modell und Runde (--steps)
AGENT_DEFAULT_RELAY_ROUNDS = 1  # Staffelrunden über alle Modelle (--relay)
AGENT_HISTORY_CHARS = 400_000  # ab dieser Verlaufsgröße werden alte Ergebnisse gekürzt
AGENT_PLAYBOOK_MAX_CHARS = 30000
AGENT_NOTEBOOK_ENTRIES = 30  # so viele Notizen und ...
AGENT_AUDIT_ENTRIES = 8  # ... so viele Audit-Einträge bekommt ein Modell zum Start
AGENT_TOOL_RESULT_MAX_CHARS = 9000
AGENT_REJECTION_LOG_CHARS = 110
AGENT_NUDGE = "Arbeite mit den Tools weiter oder rufe finish auf."
AGENT_ASSIGNMENT = "Senke den Score. Beginne mit overview."
PLAYBOOK_HEADER = "\n\nPLAYBOOK AUS DER RECHERCHE (Hypothesen, nicht geprüft):\n"
# so lehnen Server den 'tools'-Parameter ab
TOOLS_UNSUPPORTED_HTTP = (400, 404, 422, 501)
HISTORY_KEEP_HEAD = 2  # System-Prompt und Auftrag werden nie gekürzt
HISTORY_KEEP_TAIL = 6  # die jüngsten Nachrichten ebenfalls nicht
HISTORY_TRIM_MIN_CHARS = 200  # kürzere Tool-Ergebnisse lohnen das Kürzen nicht
HISTORY_PLACEHOLDER = '{"hinweis": "älteres Tool-Ergebnis gekürzt"}'
# angesetzte Länge des Platzhalters in der Größenschätzung
HISTORY_PLACEHOLDER_COST = 40


def _trim_history(messages: list[ChatMessage], budget_chars: int) -> None:
    """Ersetzt alte Tool-Ergebnisse durch Platzhalter, wenn der Verlauf zu lang wird
    (Struktur bleibt gültig)."""
    size = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)
    for m in messages[HISTORY_KEEP_HEAD:-HISTORY_KEEP_TAIL]:
        if size <= budget_chars:
            return
        if (
            m.get("role") == "tool"
            and len(m.get("content") or "") > HISTORY_TRIM_MIN_CHARS
        ):
            size -= len(m["content"]) - HISTORY_PLACEHOLDER_COST
            m["content"] = HISTORY_PLACEHOLDER


def _agent_system_prompt(playbook: str) -> str:
    """System-Prompt des Agenten, auf Wunsch um das (gekürzte)
    Recherche-Playbook ergänzt."""
    if not playbook:
        return AGENT_SYSTEM
    return AGENT_SYSTEM + PLAYBOOK_HEADER + playbook[:AGENT_PLAYBOOK_MAX_CHARS]


def _agent_opening_messages(wb: Workbench, system: str) -> list[ChatMessage]:
    """Frischer Verlauf für ein Modell: System-Prompt plus Auftrag mit Stand, Notizbuch
    und letzten Audit-Einträgen."""
    brief = {
        "auftrag": AGENT_ASSIGNMENT,
        "stand": wb.session.current_status_line,
        "notizbuch": wb.notes[-AGENT_NOTEBOOK_ENTRIES:],
        "letzte_audit_einträge": wb.session.audit[-AGENT_AUDIT_ENTRIES:],
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(brief, ensure_ascii=False)},
    ]


def _answer_tool_call(
    wb: Workbench, tool_call: dict[str, Any]
) -> tuple[str, ChatMessage]:
    """Führt einen Tool-Aufruf des Modells aus. Rückgabe: (Kurztext fürs Protokoll,
    Tool-Nachricht für den Verlauf). Zu lange Ergebnisse werden abgeschnitten, damit ein
    einzelnes Tool den Kontext nicht sprengt.
    """
    fn = tool_call.get("function", {})
    try:
        raw_args = fn.get("arguments") or "{}"
        args = raw_args if isinstance(raw_args, dict) else json.loads(raw_args)
        if not isinstance(args, dict):
            raise ValueError("Argumente müssen ein JSON-Objekt sein")
        result = wb.dispatch(str(fn.get("name", "")), args)
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        result = {"fehler": f"Argumente nicht lesbar: {e}"}
    text = json.dumps(result, ensure_ascii=False)
    if len(text) > AGENT_TOOL_RESULT_MAX_CHARS:
        text = text[:AGENT_TOOL_RESULT_MAX_CHARS] + ' ...[gekürzt]"}'
    label = fn.get("name", "?")
    if label == "propose_rewrite":
        if result.get("accepted"):
            label += " -> angenommen"
        else:
            label += (
                " -> abgelehnt: "
                + str(result.get("reason"))[:AGENT_REJECTION_LOG_CHARS]
            )
    return label, {
        "role": "tool",
        "tool_call_id": tool_call.get("id", ""),
        "content": text,
    }


def _agent_session(
    wb: Workbench,
    client: LLMClient,
    model: str,
    messages: list[ChatMessage],
    steps: int,
    log: Callable[[str], None],
    history_chars: int,
) -> bool:
    """Eine Sitzung eines Modells: bis zu `steps` Antworten, jede mit
    beliebig vielen Tool-Aufrufen.

    Rückgabe False, wenn das Modell kein Tool-Calling beherrscht: Der Server lehnt den
    'tools'-Parameter gleich beim ersten Aufruf ab, oder das Modell antwortet beim
    ersten Schritt in Prosa. Spätere Fehler beenden nur die Sitzung.
    """
    for stepno in range(steps):
        try:
            msg = client.chat(model, messages, TOOLS)
        except LLMError as e:
            log(f"  {e}")
            return not (stepno == 0 and e.code in TOOLS_UNSUPPORTED_HTTP)
        msg.setdefault("role", "assistant")
        messages.append(msg)
        calls = msg.get("tool_calls") or []
        if not calls:
            if stepno == 0:
                return False
            if wb.finished:
                return True
            messages.append({"role": "user", "content": AGENT_NUDGE})
            continue
        for tool_call in calls:
            label, tool_message = _answer_tool_call(wb, tool_call)
            messages.append(tool_message)
            log(f"  [{stepno + 1:02d}] {label}")
        if wb.finished:
            return True
        _trim_history(messages, history_chars)
    return True


def run_agent(
    wb: Workbench,
    client: LLMClient,
    models: Sequence[str],
    steps: int,
    relay_rounds: int,
    playbook: str = "",
    log: Callable[[str], None] = print,
    history_chars: int = AGENT_HISTORY_CHARS,
) -> list[str]:
    """Staffellauf: jedes Modell bekommt eine frische Sitzung auf dem aktuellen Stand
    plus das gemeinsame Notizbuch. Was ein Modell verifiziert einbringt, bleibt; die
    nächsten bauen darauf auf. Rückgabe: Modelle, die kein Tool-Calling beherrschen (für
    sie gibt es den JSON-Modus).
    """
    no_tools: list[str] = []
    system = _agent_system_prompt(playbook)
    for rnd in range(relay_rounds):
        for model in models:
            if model in no_tools or client.exhausted():
                continue
            wb.finished = None
            start_accept = wb.accepted
            messages = _agent_opening_messages(wb, system)
            log(f"\n--- Agent {model} (Runde {rnd + 1}/{relay_rounds}) ---")
            if _agent_session(wb, client, model, messages, steps, log, history_chars):
                log(
                    f"  {model}: {wb.accepted - start_accept} verifizierte Rewrites"
                    + (f" | {wb.finished}" if wb.finished else "")
                )
            else:
                no_tools.append(model)
                log(f"  {model}: kein Tool-Calling verfügbar -> JSON-Modus")
    return no_tools
