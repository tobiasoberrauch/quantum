# quantum — Google Verifiable Quantum Circuit Compilation (VQCC)

Arbeits-Repo für den Kaggle-Wettbewerb: Schaltkreis-Optimierung (kickmix `.kmx`/`.kmb`),
Discovery-Agenten, Debug-UIs und Notizen.

## Einstiegspunkte

- **`main.py`** — Einstieg des kmx-Optimizers (`.venv-chem/bin/python main.py --help`);
  die Logik steht im Paket `kmx/` (Parser, Simulator, Pässe, Verifier, LLM-Stufe).
  Tests: `.venv-chem/bin/python -m tests.kmx`
  Forschungslabor: `main.py lab init|run|status|eval` (KI-Teams schlagen vor, Prüfer entscheidet; `kmx/lab/`).
  Doku: `docs/kmx/index.html`, Architektur: `docs/kmx/kmx-architektur.html`, Status: `docs/kmx/status-archify.html`
- **`qvc_agent/`** — autonomer Discovery-/Curate-Agent (`.venv-qvc/bin/python -m qvc_agent …`);
  launchd-Watchdog unter `qvc_agent/schedule/`.
- **`qvc_web/`** — Web-Oberfläche (FastAPI-Backend + Next.js-Frontend), inkl. Multi-Agent-Team.
- **`qvc_ui/`** — Debug-UI für die Discovery-Engine.
- **`qvc_discovery.py`** — Discovery-Engine (liest `competition_brief.md`).
- **`tests/`** — qvc-Tests: `.venv-qvc/bin/python -m unittest discover -s tests -t .`
- **`docs/`** — Strategie, Lernmaterial, Recherche, Übersichten.

## Struktur

| Eintrag | Inhalt |
|---|---|
| `main.py`, `kmx/` | kmx-Optimizer (siehe oben) |
| `qvc_agent/` | Discovery-/Curate-Agent + launchd-Scheduling |
| `qvc_web/` | Web-App (Backend + Frontend) |
| `qvc_ui/` | Debug-UI |
| `qvc_discovery.py` | Discovery-Engine |
| `competition_brief.md` | kuratierter Wettbewerbs-Prompt (wird von Code im Root erwartet) |
| `requirements-qvc.txt` | Abhängigkeiten für `.venv-qvc` |
| `tests/` | `test_qvc*.py` (qvc-Apps), `tests/kmx/` (kmx-Optimizer) |
| `docs/strategy/` | Kampagne, TOP-Liste, VQCC-Strategie und -Reports |
| `docs/learn/` | Lernpfad (Notebooks, Deep-Dives, Build-Skripte) |
| `docs/research/` | gescrapte Wettbewerbsseiten, Paper-Text, Hilfsskripte |
| `docs/overview/` | Advisor-/Research-Prompts, Statusseite |
| `docs/team/`, `docs/superpowers/` | Team-Konzept, Specs und Pläne |
| `notebooks/` | öffentliche Kaggle-Notebooks + `sandbox.ipynb` |
| `work/` | Experimente und Zwischenstände (`work/kmx_verify/`: Fuzz-/Golden-Prüfskripte des Optimizers) (`work/archive/` lokal, nicht im Git) |
| `runs/` | Laufzeit-Artefakte der Agenten (nicht im Git) |
| `external/` | Referenzmaterial (`refs/`), nicht im Git |
| `qualtran/` | Google Qualtran (kickmix-Build), nicht im Git; bleibt vorerst im Root, weil `.venv-chem` darauf zeigt |
| `data`, `starter_kit`, `sota_*` | Symlinks auf heruntergeladene Wettbewerbs-/Datensatz-Daten (nicht im Git) |
