# QVC Discovery — Web App (Next.js + FastAPI)

Debug-Oberfläche für `qvc_discovery.py` (Google Verifiable Quantum Circuit Compilation).
Volle Funktionsparität zur alten `qvc_ui/`: **Runs / Live / Results / Artifacts / Config**.

## Starten
```bash
./qvc_web/start.sh
```
- Frontend: **http://127.0.0.1:3000**
- Backend:  **http://127.0.0.1:8791** (wird vom Frontend per Next-Rewrite unter `/api/*` geproxyt — kein CORS)

Voraussetzungen:
- `.venv-qvc` (Python 3.13): `uv venv .venv-qvc --python 3.13 && uv pip install --python .venv-qvc/bin/python -r requirements-qvc.txt`
- `.venv-chem` (kickmix) für die Verifier-Adapter
- Node 18+ für das Frontend

## Funktionen
- **Discover** — OpenRouter-Hypothesen + dialektische Review (braucht `OPENROUTER_API_KEY` in `.env`).
- **Score** — Score aus importierten offiziellen Verifier-Kosten.
- **Verify** — vertrauenswürdiger Adapter (nie LLM-Code):
  - *PRE-CHECK*: Stratified-x-Subset in ~1 s (Kostenschätzung, kein Claim).
  - *OFFIZIELL*: unveränderter Verifier, 64 Shots/x (~10 Min).
- **Live** — Model-Call-Trace (chain, served model, Fallbacks, Fehler, Latenz, Prompt) + Log-Stream.
- **Results** — Vorschläge/Reviews/Selection als Karten, Score-Tabelle, Verify-Runs je Salt.
- **Artifacts** — Browser für `runs/` (JSON/Markdown/Text).
- **Config** — Env-Status, Modell-Chains, Referenzkosten, Baseline.

## Layout
```
qvc_web/
  start.sh                 # startet Backend + Frontend
  backend/                 # FastAPI (Python, .venv-qvc)
    main.py                # App + REST-Endpunkte (/api/*)
    jobs.py                # async Job-Runner (discover/score/verify) + Model-Call-Tracer
    tracer.py              # thread-sichere Ring-Buffer (Trace + Logs)
    config.py              # Pfade
    adapters/              # vertrauenswürdige Verifier-Wrapper (invsqrt official/precheck)
    examples/              # Beispiel-Kosten für score
  frontend/                # Next.js 15 (App Router, TypeScript)
    app/                   # layout, page, globals.css
    components/            # Dashboard + Tabs
    lib/                   # api, types, markdown, useQvc (Polling-State)
```

## Hinweise
- Nur lokal (`127.0.0.1`). `runs/`, `.venv-qvc/`, `.env`, `node_modules/`, `.next/` sind gitignored.
- Offizieller invsqrt-Claim erfordert 64 Shots/x (Verifier verlangt `shots_per_x·max_x % 256 == 0`; da `max_x = 4·(ungerade)` ⇒ `shots_per_x` Vielfaches von 64).
