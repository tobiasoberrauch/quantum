# Design: QVC Agenten-Loop (Ebene A) — Weinstadt-Qwen3.8 + Verifier-Oracle

**Datum:** 2026-11-09 · **Status:** Entwurf zur Freigabe · **Repo:** `quantum` (Google VQCC)
**Entscheidungen des Users:** Ebene A (Agentic Search, CPU, 9 Wochen) · Gehirn = lokales Weinstadt-Qwen3.8 · Fokus invsqrt-first (Default) · HITL (Default)

---

## Intent / Why

Score im VQCC-Wettbewerb innerhalb der 9 Wochen bis 2027-01-13 bewegen, ohne GPU und ohne
eigene Circuit-Bytes zu erfinden. Der Loop nutzt ein LLM (Weinstadt-Qwen3.8) als
Forschungs-/Kurations-Gehirn und den **offiziellen kickmix-Verifier als einzige Wahrheit**
für Korrektheit und Kosten. Das ist die inference-only-Version der späteren RL-Ebene (B):
dieser Loop wird dort exakt die `Env` sein (Aktion = Vorschlag, Reward = Verifier-Cost).

Ausgangslage (aus `~/.agent-memory/kaggle-qvc/`):
- qvc-008 = 24.54651, qvc-009 = 24.78668 lokal → **am Public-Tip (~24.55)**.
- DQI: kein Solo-Hebel, Generator privat (Shadow-Builder-Befund 11-04) → nur via Merge.
- Chem: Stage 1 GPU-blockiert auf host2.
- invsqrt: einziger Task mit echtem Solo-Hebel + lauffähiger Source + schnellem Precheck.

## Goals

1. **G1 — Public-Tip halten/adoptieren (Curate):** Jede neue öffentliche Verbesserung wird
   vom Agenten erkannt, lokal verifiziert und ins Portfolio übernommen (same-day, RezOps-Äquivalent).
2. **G2 — invsqrt-Edge ausbauen (Research):** Agent schlägt Source-Edits am invsqrt-Generator vor,
   die den verifizierten Cost senken (Ziel: über 21.78 hin zu 22.5, pwq3-Edge nutzen).
3. **G3 — nachvollziehbarer Memory-Spur:** Jeder Vorschlag + Verifier-Verdict + Cost-Delta wird
   strukturiert geloggt (positiv UND negativ) → wiederverwendbar, Merge-fähig, Layer-B-ready.

## Non-Goals / Anti-Goals

- **Kein rohes Byte-Mutieren von `.kmb`** (kickmix-Schema unbekannt; `docs/strategy/TOP.md`: „no trustworthy way
  to mutate arbitrary quantum-circuit bytes“). Aktionen sind entweder *Kuration* (fertige `.kmb`
  auswählen/verblenden) oder *Source-Edit* (Generator-Code, nicht Bytes).
- **Kein „verified“-Claim ohne offiziellen Verifier-Run.** Precheck (<1 s) ist nur ein Filter.
- **DQI nicht solo optimieren** (kein Hebel, Generator privat).
- **Chem nicht ohne host2-GPU** (Stage 1 blockiert).
- **Nr. 1 allein mit A wird nicht versprochen.** A hält am Public-Tip + invsqrt-Edge (~25–27 realistisch).
  Nr. 1 (29.30) braucht private DQI/Chem via Merge. A ist der Score-Mover für die 9 Wochen
  und das Fundament für Ebene B.

## Constraints

- 100 % CPU (kein GPU/TPU) — kombinatorisches Problem, kein ML-Problem.
- Verifier = offizieller kickmix; DQI bräuchte 102.400 Shots + ≥5 Salze (hier aber nicht Ziel).
- Secrets: Weinstadt-API-Key **niemals** hartkodieren/committen/drucken.
- Repo ist PUBLIC auf GitHub → Loop-Logs/Docs dürfen keine Secrets + keine fremden
  scraped Competitor-Assets enthalten (bestehendes Exclusions-Schema beibehalten).

## Approaches (betrachtet → gewählt)

| Ansatz | Idee | Urteil |
|---|---|---|
| A1 | `qvc_discovery.py` erweitern (Weinstadt-Backend + `search`-Subkommando) | **Verworfen** — kämpft gegen dessen bewussten Vertrag („discover = Hypothesen nur, keine Ausführung“) und ist auf OpenRouter/Cloud-JSON geformt, nicht auf einen engen edit→verify→keep-Loop. |
| **A2** | Neues dediziertes `qvc_agent.py`: Loop, der `qvc_discovery.verify_candidate` + `qvc_ui`-Adapter + `frontier_1109`-Pipeline + `invsqrt_constseed_model` wiederverwendet | **Gewählt** — sauber, testbar, CPU-only, baut auf dem was schon läuft. |
| A3 | UI-first via `qvc_ui` („agent-run“-Jobtyp) | **Als Wrapper** in Phase 3 (Observability/HITL), nicht als Kern. |

**Wahl: A2 als Kern, A3 als Observability-/HITL-Wrapper.**

## Architektur (der Loop)

```
for round in 1..N:
    ctx      = load(current_best, candidates_ranked.json, memory, TASK_CONTEXT[task])
    proposal = qwen38.propose(ctx)            # strukturiert: Curate- ODER Research-Aktion
    artifact = materialize(proposal)          # Curate: .kmb wählen/verblenden
                                                 # Research: Source editieren → .kmb neu emittieren
    pre      = precheck(artifact)             # invsqrt: <1 s Adapter (Stratified Subset)
    full     = verify_candidate(artifact) if pre.passed else None   # offizieller kickmix
    verdict  = KEEP if (full and full.passed and full.cost < current_best.cost) else DISCARD
    record(loop_log, memory, proposal, pre, full, verdict, cost_delta)
    if verdict == KEEP and hitl.approve():    # W2-Default: HITL
        current_best = artifact
```

**Zwei Aktionsmodi, ein Oracle, ein Memory:**
- **Curate (Phase 1):** `proposal` = öffentlichen Kandidaten aus `candidates_ranked.json`
  adoptieren/verblenden/neu ranken. `materialize` = `.kmb` in das Submission-Set legen.
  `verify` = bestehende `frontier_1109/scripts/verify_one.py` / `run_verify.py`.
- **Research (Phase 2):** `proposal` = konkreter Edit am invsqrt-Generator
  (`work/invsqrt_constseed_model.py` / `work/constseed_build/`). `materialize` = `.kmb` neu emittieren.
  Gate = Precheck, dann voller Verifier.

## Model Client (Weinstadt-Qwen3.8)

- **Endpunkt:** OpenAI-kompatibel.
  - Live: `http://192.168.212.81:8000/v1` (Provider `audius-we`) — Default, **keyless**
  - Fallback: `https://dev-ai.audiusintelligence.com/v1` (Provider `audius-dev-gw`, `{env:AUDIUS_GW_KEY}`)
  - Modell-ID: `qwen3.8-27b`
  - (litellm `.60`/`.61` sind vom Mac aus nicht erreichbar → nicht Default)
- **Auth:** `baseURL` + optional `apiKey` **zur Laufzeit** aus `~/.config/opencode/opencode.json` lesen
  (Provider `audius-we` ist keyless; `audius-dev-gw` nutzt `{env:AUDIUS_GW_KEY}`), Override per Env
  `QVC_LLM_BASE_URL` / `QVC_LLM_API_KEY`. **Nie hartkodiert, nie committed, nie gedruckt.**
- **Reasoning-Modell:** `max_tokens ≥ 32000`; Thinking-Blöcke parsen, dann finales JSON extrahieren.
- **Strukturierte Ausgabe:** Proposal als JSON mit lokalem Schema-Check (Muster aus
  `qvc_discovery.py` wiederverwenden: `json_object` + `validate`).

### Proposal-Schema (klein)

```json
{
  "mode": "curate|research",
  "target_task": "invsqrt",
  "action": "kurzer Befehlswas",
  "rationale": "warum (mit Bezug zu Memory/Kandidaten)",
  "expected_delta": "geschätzte Cost-/Ratio-Änderung (SCHAETZUNG, keine Messung)",
  "artifact_ref": "Pfad/SHA des betroffenen .kmb bzw. der Source-Datei",
  "precheck_plan": "wie <1 s Precheck läuft",
  "verify_plan": "wie offizieller Verifier läuft",
  "abort_condition": "wann aufhören/verwerfen"
}
```

## Memory & Logging

- **Loop-Log:** `runs/agent/<UTC-ts>/loop.jsonl` — eine Zeile pro Vorschlag
  (round, mode, rationale, artifact_sha256, precheck, verify_result, cost, verdict, cost_delta, model).
- **Wissens-Memory:** `~/.agent-memory/kaggle-qvc/YYYY-MM-DD-agent-loop-<task>.md`
  (positiv/negativ, je AGENTS.md-Konvention) + `INDEX.md` aktualisieren. Git-Commit nur am Ende.
- **Cost-Cache:** `shacache.json`-Muster beibehalten (nur erfolgreiche Runs cachen, inkl. SHA + Salt).

## HITL (W2-Default)

- **Default:** Loop läuft autonom propose→precheck→verify, aber **current_best fortschreiben und
  `submission.zip` bauen nur nach expliziter User-Freigabe** (CLI-Prompt oder `qvc_ui`).
- `--autonomous`: erlaubt unbeaufsichtigte Keeps innerhalb eines Cost-Floors + Salt-Policy.

## Phasen

- **Phase 0 (Builder-Task, Abhängigkeiten bestätigen):**
  (a) aktuellen besten invsqrt-`.kmb` + verifizierten Cost lokalisieren,
  (b) Emissions-Pfad „editierte Parameter → neue `.kmb`“ in `work/constseed_build/` als lauffähig bestätigen,
  (c) Weinstadt-Endpunkt von diesem Host erreichbar testen (1 Request, kein Key-Druck).
- **Phase 1 — Curate live:** `frontier_1109` um qwen3.8-Proposer + Memory erweitern.
  Deliverable: Agent wählt/verblendet → verifiziertes `submission.zip` + Cost-Delta-Report.
- **Phase 2 — Research invsqrt:** qwen3.8 editiert Generator → re-emit → precheck → verify → keep.
  Ziel: invsqrt > 21.78 Richtung 22.5.
- **Phase 3 (optional) — `qvc_ui`-Wrapper:** Live-Trace + Approve/Reject pro Runde.
  Setzt Ebene B auf (Loop = Molt-`Env`, Verifier = Reward).

## Offene Builder-Entscheidungen (meine Calls, bei Veto sagen)

- Neues Modul `qvc_agent.py` im Repo-Root (nicht in `frontier_1109`), importiert geteilte
  Verify-Logik aus `qvc_discovery.py`.
- N Vorschläge/Runde Default = 5; Precheck-gated, voller Verifier nur für Survivors.
- Config via `.env` (`QVC_LLM_*`) + opencode.json-Fallback.
- Phase 1 startet mit Curate (definitiv lauffähig), Research kommt, sobald Phase 0(b) grün ist.

## Verifikation

- **Offline:** Unit-Tests für Proposal-Parsing, Cost-Delta-Logik, Memory-Write (kein LLM, kein Verifier)
  — Muster aus `tests/test_qvc.py` erweitern.
- **Integration:** Dry-Run-Loop gegen bestehende `constseed_build/*.kmb` + `frontier_1109/results/`
  (keine neuen Submissions).
- **Live:** ein HITL-freigegebener Curate-Run → verifiziertes `submission.zip` mit gemeldetem Delta.
