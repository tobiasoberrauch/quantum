"""Robustes Auslesen von JSON aus Modellantworten: Denkblöcke und Code-Zäune werden
entfernt, dann das erste vollständige JSON-Objekt gesucht. Nie eine Ausnahme."""

from __future__ import annotations

import json
import re
from typing import Any

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE = re.compile(r"```[A-Za-z0-9_-]*\s*\n?(.*?)```", re.DOTALL)
MAX_SCAN_STARTS = 200


def message_text(message: object) -> str:
    """Textinhalt einer Chat-Antwortnachricht ('' bei None oder fremder Form)."""
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):  # manche Endpunkte liefern Teile
            return "".join(p.get("text", "") for p in content if isinstance(p, dict))
    return ""


def _first_object(text: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    start, tries = text.find("{"), 0
    while start >= 0 and tries < MAX_SCAN_STARTS:
        try:
            obj, _ = decoder.raw_decode(text, start)
        except ValueError:
            obj = None
        if isinstance(obj, dict):
            return obj
        start, tries = text.find("{", start + 1), tries + 1
    return None


def extract_json(text: str) -> tuple[dict[str, Any] | None, str]:
    """(Objekt, '') oder (None, Fehlergrund)."""
    if not text or not text.strip():
        return None, "leere Antwort"
    cleaned = _THINK.sub("", text)
    candidates = [m.group(1) for m in _FENCE.finditer(cleaned)] + [cleaned]
    for chunk in candidates:
        obj = _first_object(chunk)
        if obj is not None and _starts_at_first_brace(chunk, obj):
            return obj, ""
        if obj is not None:
            # Das äußere Objekt ist kaputt (meist am Token-Limit abgeschnitten); ein
            # inneres Teilobjekt wäre ein falscher Vorschlag.
            return None, "JSON unvollständig (Antwort abgeschnitten?)"
    return None, "kein gültiges JSON-Objekt in der Antwort"


def _starts_at_first_brace(chunk: str, obj: dict[str, Any]) -> bool:
    """Ob das gefundene Objekt beim ersten '{' des Abschnitts beginnt."""
    start = chunk.find("{")
    try:
        first, _ = json.JSONDecoder().raw_decode(chunk, start)
    except ValueError:
        return False
    return first is obj or first == obj
