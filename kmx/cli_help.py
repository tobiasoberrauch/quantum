"""Beschreibungstext von --help: was das Paket tut, Aufrufformen und (aus
`kmx.config.ENV_VARS` erzeugt) die Umgebungsvariablen."""

from __future__ import annotations

import textwrap

from kmx.config import ENV_VARS

HELP_WIDTH = 88
_ENV_NAME_COLUMN = 2 + max(len(v.name) for v in ENV_VARS) + 2

CLI_OVERVIEW = """\
Verifier-gestützter Optimierer und KI-Agent für kickmix-Schaltkreise (.kmx / .kmb).

Paket kmx, Python >= 3.10, nur Standardbibliothek; Einstiegspunkte sind main.py und
python -m kmx. Optional: numpy (exakter invsqrt-Score) und kickmix (Gegenprüfung, .kmb).

Was das Paket tut
  1. Parser für das kickmix-Textformat v2 (inkl. CSWAP, Z_POW, R, INFO_TAG,
     PUSH_CONDITION if bN). T/TDAG gibt es in kickmix nicht; Phasen sind Z und Z_POW
     mit dezimalem Exponenten.
  2. Wortparalleler Simulator für das volle Instruktionsset. Für invsqrt läuft die
     GESAMTE gültige Eingabedomäne (x in [1, 3133452]) in einem Durchlauf, jede Lane
     ein Bit einer Python-Ganzzahl.
  3. Verifier in drei Stufen:
       L1  exakt:       Wahrheitstabelle eines Fensters über alle Belegungen (inkl.
                        Messergebnisse), bis 20 Variablen
       L2  kontextuell: Fenster auf den tatsächlich erreichbaren Zuständen (nutzt
                        Don't-Cares der Domäne)
       L3  End-to-End:  Original gegen Ergebnis auf der ganzen Domäne (Register,
                        Scratch, 128-Bit-Phase)
     Breite unitäre Fenster werden vor der Wahrheitstabelle auf ihren Differenzkegel
     reduziert; Z_POW-Winkel außerhalb des 2^-127-Rasters gelten nie als bewiesen.
  4. Deterministische Pässe bis zum Fixpunkt, jeder einzeln End-to-End geprüft:
       - Auslöschung kommutierender Paare und exakte Z/Z_POW-Phasenfusion (bit-,
         bedingungs- und HMR-bewusst)
       - simulationsgeführte Reduktion: nie feuernde Toffolis, implizierte Kontrollen,
         Toffoli -> CX-Kaskade, Toffoli-Gruppen auf einem Ziel, Rotationen auf
         wertgleichen Qubits
       - Measurement-Based Uncomputation für reversible Uncompute-Ketten
       - Qubit-Repacking per Intervallfärbung (Q = größter Index + 1)
  5. Exakter invsqrt-Score, gerechnet wie der offizielle Verifier (Phase je x gegen
     1/sqrt(x), Rotationskosten aus der Reserve). Optional --trim-rotations: feine
     Rotationen streichen, wenn der exakte Score dadurch sinkt.
  6. LLM-Stufe: Tool-Calling-Agent (mehrere Modelle im Staffellauf) oder, für Modelle
     ohne Tool-Calling, ein JSON-Modus je Fenster mit Fakten und einer Nachbesserung
     per Gegenbeispiel. Standard-Endpunkt ist die lokale Weinstadt-KI; ist sie nicht
     erreichbar, wird die Stufe übersprungen.
  7. Offizielles Gate (OFFICIAL_VERIFY_CMD / --verify-cmd) VOR dem atomaren Schreiben;
     steigen die Kosten, wird nichts geschrieben.
  8. Research-Brief für Deep-Research-Werkzeuge; das Ergebnis geht per --playbook an
     den Agenten.
  9. Forschungslabor (lab): LLM-Teams mit eigener Weltsicht schlagen Behauptungen und
     Kandidaten vor, ein Kritiker kommentiert (Veto nur beratend), ein
     deterministischer Richter prüft JEDEN Kandidaten über die ganze Domäne und
     liefert ein konkretes Gegenbeispiel. Status (hypothesis | experimental |
     verified | refuted) entsteht nur aus Prüfer-Ereignissen; verified verlangt das
     Urteil PASS des offiziellen Verifiers. Generatoren laufen nur in der
     macOS-Sandbox (alles verboten außer Python, kmx/ und Temp-Ordner).

Aufruf
  python main.py invsqrt.kmx [OUT] [DIFF]          alte Form: Pässe + LLM-Stufe + Gate
  python main.py optimize invsqrt.kmx -o out.kmx   nur deterministische Pässe
  python main.py agent invsqrt.kmx -o out.kmx --models MODELL_A,MODELL_B --api-url URL
  python main.py research invsqrt.kmx --out research_brief.md
  python main.py check original.kmx kandidat.kmx   zwei Dateien End-to-End vergleichen
  python main.py info invsqrt.kmx                  Kennzahlen, Score, Toffoli-Profil
  python main.py --selftest
  python main.py lab init --lab-dir runs/lab/invsqrt --baseline invsqrt.kmx
  python main.py lab run --lab-dir runs/lab/invsqrt --rounds 2   LLM-Teams + Richter
  python main.py lab status --lab-dir runs/lab/invsqrt
  python main.py lab eval --lab-dir runs/lab/invsqrt kandidat.kmx  nur der Richter"""


def env_help_section() -> str:
    """Abschnitt "Umgebungsvariablen": je Variable eine (umbrochene) Zeile."""
    lines = ["Umgebungsvariablen (Kommandozeile hat Vorrang)"]
    for var in ENV_VARS:
        lines += textwrap.wrap(
            var.meaning,
            width=HELP_WIDTH,
            initial_indent=f"  {var.name}".ljust(_ENV_NAME_COLUMN),
            subsequent_indent=" " * _ENV_NAME_COLUMN,
        )
    return "\n".join(lines)


CLI_DESCRIPTION = f"{CLI_OVERVIEW}\n\n{env_help_section()}\n"
