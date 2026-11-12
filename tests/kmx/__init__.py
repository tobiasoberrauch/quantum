"""Tests für das Paket kmx: je Modul bzw. Bereich eine Datei test_*.py.

Alle Tests laufen ohne pytest und ohne Netzwerk (LLM-Aufrufe gehen an Stubs); alle
Schaltkreise sind winzig (6-Bit-Register, --range 0:63). Aus dem Projektverzeichnis:

    python -m tests.kmx            alle Tests
    python -m tests.kmx cli llm    nur Module, deren Name einen der Begriffe enthält
    python -m tests.kmx --bugs     zusätzlich vermutete, noch offene Fehler (bug_*)

Unter pytest werden dieselben test_*-Funktionen gesammelt. Vermutete Fehler kommen als
Funktionen mit Präfix `bug_` hinzu; sie zählen nicht zur bestandenen Menge. Derzeit gibt
es keine.
"""
