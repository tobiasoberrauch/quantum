"""Prompt- und Vorlagentexte als Paketdaten, je eine UTF-8-Datei in diesem Verzeichnis.

Der Inhalt wird byte-genau übernommen. Jede Datei endet mit genau einem Zeilenumbruch,
der nur der Dateikonvention dient und nicht zum Text gehört; `load_prompt` entfernt ihn.
Platzhalter in geschweiften Klammern ({facts}, {rot:.1f}, ...) füllt der Aufrufer per
str.format.
"""

from __future__ import annotations

from pathlib import Path

PROMPT_DIR = Path(__file__).parent


def load_prompt(name: str) -> str:
    """Liest den Text `name` (z. B. "agent_system.txt") ohne den abschließenden
    Zeilenumbruch der Datei."""
    return (PROMPT_DIR / name).read_text(encoding="utf-8").removesuffix("\n")
