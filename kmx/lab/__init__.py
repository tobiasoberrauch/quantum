"""Forschungslabor: Forscher (LLM-Teams) schlagen vor, ein deterministischer Richter
entscheidet.

Module, von unten nach oben:
  claims, seeds, spec        Status (hypothesis | experimental | verified | refuted),
                             Bereinigung, Altbefunde, Aufgabenbeschreibung (Paketdaten)
  registry                   append-only Protokoll (events.jsonl) im Laborverzeichnis
  sandbox, counterexample,   Generator-Sandbox (sandbox-exec), konkretes Gegenbeispiel,
  official, judge            offizieller Verifier mit Beleg, Richter
  llm_json, teams, report    Antwort-Parser, Rollen und Prompts, Lesesichten
  paramsearch, dossier       Parametersuche über ein Raster (ohne LLM), Dossier für
                             die Teams (Basis-Kennzahlen, Hotspots, bester Stand)
  rounds, commands           CEGIS-Runden, Unterbefehl `lab`

Der Status einer Behauptung wird aus Prüfer-Ereignissen ABGELEITET; kein Codepfad lässt
Modelltext einen Status setzen. `verified` heißt: der offizielle Verifier hat mit Exit 0
UND dem JSON-Urteil "PASS" bestanden, belegt mit Befehl, Exit-Code, SHA-256 von Ausgabe,
Kandidat und Werkzeugdateien sowie Python- und kmx-Version, mit dem bei
`lab init --verify-cmd` gepinnten Verifier (gleiche Werkzeug-Hashes wie in lab.json) und
einem Befehl, der den Kandidaten nennt (`kmx.lab.claims.official_pinned`). Ohne Pin
(auch in älteren Laboren) zählt ein offizielles PASS nur als `experimental`. Eine
vollständige Kontraktprüfung über die endliche Domäne allein ist `experimental` (der
Messzufall ist dabei nur gestichprobt: Zufallsrunden plus feste Ergebnismuster). Ein
Kritiker-Veto ist nur beratend; der Richter läuft immer.

Parametersuche: ein Generator mit Raster `params` läuft je Variante mit `params.json`;
eine Kostenschätzung ordnet nur, voll bewertet werden die besten
`paramsearch.FULL_JUDGE_TOP_K` verschiedenen Ausgaben (je eine eigene Behauptung), der
Rest bleibt ohne Status (Notiz "nicht voll geprüft (Budget)").

Formale Beweiser (Lean, SMT) sind bewusst NICHT eingebaut. Ein echter Beweiser würde wie
der offizielle Verifier angeschlossen: als aufgezeichneter externer Werkzeuglauf
(Befehl, Exit-Code, Hash von Eingabe und Ausgabe, Werkzeugversion, Quelle, Annahmen) in
`proof_artifacts`, ausgewertet von `kmx.lab.claims.evaluation_status` - nie durch eine
Behauptung des Modells.
"""
