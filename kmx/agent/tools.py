"""Tool-Schemata der Werkbank und der Systemprompt des Agenten (Text in
kmx/prompts/agent_system.txt)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from kmx.agent.hotspots import HOTSPOT_KINDS
from kmx.prompts import load_prompt

ToolResult = dict[str, Any]  # JSON-serialisierbare Antwort eines Werkbank-Tools

ToolSchema = dict[str, Any]  # Tool-Beschreibung im OpenAI-Function-Calling-Format


def _tool(
    name: str, desc: str, props: dict[str, Any], required: Sequence[str] = ()
) -> ToolSchema:
    """Tool-Beschreibung im OpenAI-Function-Calling-Format."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {
                "type": "object",
                "properties": props,
                "required": list(required),
            },
        },
    }


_INT = {"type": "integer"}
# Die Namen sind zugleich die Methodennamen der Workbench (siehe Workbench.dispatch).
TOOLS = [
    _tool(
        "overview",
        "Kennzahlen, Score-Schätzung, Register und Toffoli-Profil nach Abschnitten.",
        {},
    ),
    _tool(
        "read_lines",
        "Liest Instruktionen ab Index start "
        "(0-basiert, Kommentare/Leerzeilen sind entfernt).",
        {"start": _INT, "count": _INT},
        ["start"],
    ),
    _tool(
        "find_hotspots",
        "Sucht lohnende Stellen. kind: runs (mehrere CCX auf dasselbe Ziel), "
        "pairs (gleiche CCX-Tripel), dense (Toffoli-dichte Fenster), "
        "peak (wo die Qubit-Spitze liegt), conditional (klassisch bedingte Toffolis).",
        {
            "kind": {"type": "string", "enum": list(HOTSPOT_KINDS)},
            "limit": _INT,
        },
        ["kind"],
    ),
    _tool(
        "analyze_window",
        "Analysiert das Fenster [start, end]: Zeilen, Fakten über die Qubit-Werte am "
        "Eingang (Konstanten, lineare und AND-Beziehungen, nie gleichzeitig gesetzte "
        "Paare), Zahl erreichbarer Zustände, freie Ancillas.",
        {"start": _INT, "end": _INT},
        ["start", "end"],
    ),
    _tool(
        "propose_rewrite",
        "Ersetzt das Fenster [start, end] durch new_lines, WENN der Verifier "
        "Äquivalenz bestätigt und die Kosten sinken. "
        "Bei Ablehnung kommt ein konkretes Gegenbeispiel zurück.",
        {
            "start": _INT,
            "end": _INT,
            "new_lines": {"type": "array", "items": {"type": "string"}},
            "rationale": {"type": "string"},
            "neutral_ok": {
                "type": "boolean",
                "description": "true = auch kostengleiche Umordnung annehmen "
                "(z. B. um die Qubit-Spitze zu senken)",
            },
        },
        ["start", "end", "new_lines"],
    ),
    _tool(
        "run_passes",
        "Lässt die deterministischen Pässe laufen "
        "(Auslöschung, simulationsgeführte Reduktion, MBU, Repacking).",
        {},
    ),
    _tool(
        "full_check", "End-to-End-Prüfung gegen das Original auf der ganzen Domäne.", {}
    ),
    _tool("undo", "Nimmt die letzte angenommene Änderung zurück.", {}),
    _tool(
        "note",
        "Hält eine Erkenntnis fest; nachfolgende Modelle sehen sie.",
        {"text": {"type": "string"}},
        ["text"],
    ),
    _tool(
        "finish",
        "Beendet die Sitzung mit einer kurzen Zusammenfassung.",
        {"summary": {"type": "string"}},
    ),
]
TOOL_NAMES = frozenset(tool["function"]["name"] for tool in TOOLS)

AGENT_SYSTEM = load_prompt("agent_system.txt")
