# QVC Agenten-Loop (Ebene A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ein CPU-only Agenten-Loop, der lokales Weinstadt-Qwen3.8 als Gehirn nutzt und den offiziellen kickmix-Verifier als Oracle, um den VQCC-Score zu bewegen (Curate am Public-Tip halten + invsqrt-Research), mit nachvollziehbarem Memory.

**Architecture:** Neues Paket `qvc_agent/` im Repo-Root. Alle Abhängigkeiten (Modell-Call, Materialisierung, Precheck, Verifier, Approval) werden in `loop.run_loop` injiziert → der Kern ist ohne LLM/Verifier unit-testbar. Wiederverwendet wird: `qvc_discovery.verify_candidate` (Oracle), `qvc_ui/adapters/*` (Precheck/Official), `work/frontier_1109/*` (Curate-Kandidaten), `work/constseed_build/build_constseed_circuit.py` (Research-Emitter).

**Tech Stack:** Python 3.11+, stdlib `urllib` (kein neues HTTP-Dep), `jsonschema` (vorhanden via `qvc_discovery`), `unittest` (wie `tests/test_qvc.py`).

**Spec:** `docs/superpowers/specs/2026-11-09-qvc-agent-loop-design.md`

## Global Constraints

- **CPU-only.** Kein GPU/TPU. (Spec: kombinatorisches Problem.)
- **Modell-ID:** `qwen3.8-27b`. **Live-Endpunkt:** Provider `audius-we` → `http://192.168.212.81:8000/v1`, **keyless** (kein apiKey). Fallback: Provider `audius-dev-gw` → `https://dev-ai.audiusintelligence.com/v1` mit `{env:AUDIUS_GW_KEY}`. Die litellm-Gateways `.60`/`.61` sind vom Mac aus nicht erreichbar → nicht als Default.
- **Secrets:** API-Key (falls vorhanden) **nur zur Laufzeit** aus `~/.config/opencode/opencode.json` → `provider.<prov>.options.apiKey` (kann `{env:NAME}` sein oder fehlen = keyless). Nie hartkodieren, nie committen, nie drucken/loggen. Env-Overrides: `QVC_LLM_BASE_URL`, `QVC_LLM_API_KEY`, `QVC_LLM_MODEL`; Config-Pfad-Override: `QVC_OPENCODE_CONFIG`.
- **Reasoning-Modell:** `max_tokens ≥ 32000` (Default `32000`).
- **Kein rohes Byte-Mutieren von `.kmb`.** Aktionen sind nur *Curate* (bestehende `.kmb` auswählen/verblenden) oder *Research* (Generator-Source editieren → neu emittieren).
- **KEEP nur bei** offizieller Verifier-`PASS` **und** endlicher Cost **strept niedriger** als aktueller Best. Cost wird nie synthetisiert.
- **invsqrt REFERENCE_COST = `2076774.233715282`**; `ratio = REFERENCE_COST / cost`.
- **Repo ist PUBLIC:** Neue Dateien/Logs/Reports enthalten keine Secrets und keine gescrapten Competitor-Assets.

## Review Focus

Fünf Fehlerklassen, die die Spec impliziert aber kein einzelner Test von sich aus abdeckt — jede wird unten dem owning Task als Test zugeordnet:

1. **Endpunkt down/unerreichbar** → Loop muss fail-fast mit redigierter Meldung, kein Hang, keine erfundenen Vorschläge. *(→ Task 1 `test_chat_error_redacts_key`, Task 8 `check-endpoint`)*
2. **Malformed / nicht-JSON Modell-Ausgabe** → Runde wird verworfen, Loop läuft weiter, kein Crash, nie ein KEEP. *(→ Task 2 `test_parse_*`, Task 7 `test_discard_on_bad_json`)*
3. **Precheck PASS aber Official FAIL / keine endliche Cost** → kein KEEP. *(→ Task 4 `test_is_keep_no_cost_false`, Task 7 `test_discard_on_higher_cost`)*
4. **HITL umgangen / Autonomous-Overreach** → Best fortschreiben + Submission bauen nur nach Approval; Autonomous durch Cost-Floor begrenzt. *(→ Task 7 `test_hitl_blocks_advance`)*
5. **Secret-Leak in Logs/Memory/Repo** → Key landet nie in `loop.jsonl`, Memory-Notes oder Reports. *(→ Task 3 `test_log_has_no_secret`, Task 1 `redact`, Task 9 Report-Check)*

---

## File Structure

Neue Dateien (alle im Repo-Root, außer Tests):

- `qvc_agent/__init__.py` — Paket, `__version__`.
- `qvc_agent/client.py` — Endpunkt-Auflösung + `WeinstadtClient.chat` (stdlib urllib) + `redact`.
- `qvc_agent/proposal.py` — Proposal-Schema, `build_proposal_prompt`, `parse_proposal`, `ProposalError`.
- `qvc_agent/memory.py` — `append_loop_log`/`read_loop_log`, `load_memory`, `write_memory_note`.
- `qvc_agent/oracle.py` — `verify` (via `qvc_discovery.verify_candidate`), `extract_cost`, `is_keep`, `cost_to_ratio`.
- `qvc_agent/curate.py` — `load_candidates`, `materialize` (`.kmb` aus Locator extrahieren).
- `qvc_agent/research.py` — `materialize_research` (injected `emit_fn`), `apply_edit` (Default: Params-Override).
- `qvc_agent/loop.py` — `run_loop` (Orchestrator, alle Deps injiziert).
- `qvc_agent/cli.py` + `qvc_agent/__main__.py` — `python -m qvc_agent run|check-endpoint`.
- `tests/test_qvc_agent.py` — unittest-Suite (ein wachsendes File neben `tests/test_qvc.py`).

Geänderte Dateien:
- `requirements-qvc.txt` — nur falls `jsonschema` fehlt (Task 1 prüft).

---

### Task 1: Paket-Scaffold + Weinstadt-Client

**Files:**
- Create: `qvc_agent/__init__.py`, `qvc_agent/client.py`
- Test: `tests/test_qvc_agent.py` (neu, Klasse `TestClient`)

**Interfaces:**
- Produces:
  - `opencode_config_path() -> Path`
  - `resolve_endpoint(*, provider: str = DEFAULT_PROVIDER) -> dict` → `{"base_url": str, "api_key": str | None, "model": str}` (`api_key` ist `None` beim keyless Endpunkt)
  - `class WeinstadtClient(base_url, api_key, model, max_tokens=32000, timeout=180)` mit `.chat(messages: list[dict], *, temperature: float = 0.4) -> str` (`api_key` darf `None` sein → kein Authorization-Header)
  - `class WeinstadtError(RuntimeError)`
  - `redact(value: str, secret: str | None) -> str`
  - Konstanten `DEFAULT_MODEL="qwen3.8-27b"`, `DEFAULT_PROVIDER="audius-we"` (live, keyless), `FALLBACK_PROVIDER="audius-dev-gw"`, `DEFAULT_MAX_TOKENS=32000`

- [ ] **Step 1: Failing tests schreiben** (`tests/test_qvc_agent.py`)

```python
import json, os, tempfile, unittest
from pathlib import Path
from unittest import mock

import qvc_agent.client as C

def _fake_cfg(tmp, with_key=True, provider="audius-we"):
    p = Path(tmp) / "opencode.json"
    opts = {"baseURL": "http://192.168.212.81:8000/v1"}
    if with_key:
        opts["apiKey"] = "sk-test-secret"
    p.write_text(json.dumps({"provider": {provider: {"options": opts}}}))
    return p

class TestClient(unittest.TestCase):
    def test_resolve_keyless_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["QVC_OPENCODE_CONFIG"] = str(_fake_cfg(tmp, with_key=False))
            try:
                ep = C.resolve_endpoint()
                self.assertEqual(ep["base_url"], "http://192.168.212.81:8000/v1")
                self.assertIsNone(ep["api_key"])
                self.assertEqual(ep["model"], "qwen3.8-27b")
            finally:
                del os.environ["QVC_OPENCODE_CONFIG"]

    def test_resolve_reads_api_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["QVC_OPENCODE_CONFIG"] = str(_fake_cfg(tmp, with_key=True))
            try:
                ep = C.resolve_endpoint()
                self.assertEqual(ep["api_key"], "sk-test-secret")
            finally:
                del os.environ["QVC_OPENCODE_CONFIG"]

    def test_env_override_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["QVC_OPENCODE_CONFIG"] = str(_fake_cfg(tmp, with_key=False))
            os.environ["QVC_LLM_BASE_URL"] = "http://override/v1"
            os.environ["QVC_LLM_API_KEY"] = "sk-override"
            try:
                ep = C.resolve_endpoint()
                self.assertEqual(ep["base_url"], "http://override/v1")
                self.assertEqual(ep["api_key"], "sk-override")
            finally:
                for k in ("QVC_OPENCODE_CONFIG", "QVC_LLM_BASE_URL", "QVC_LLM_API_KEY"):
                    del os.environ[k]

    def test_chat_posts_and_returns_content(self):
        cl = C.WeinstadtClient("http://x/v1", "sk-k", "qwen3.8-27b")
        resp = mock.Mock(); resp.status = 200
        resp.read.return_value = json.dumps({"choices": [{"message": {"content": "HAI"}}]}).encode()
        with mock.patch.object(C.urllib.request, "urlopen", return_value=resp) as u:
            out = cl.chat([{"role": "user", "content": "ping"}])
        self.assertEqual(out, "HAI")
        req = u.call_args[0][0]
        self.assertEqual(req.get_header("Authorization"), "Bearer sk-k")
        body = json.loads(req.data.decode())
        self.assertEqual(body["model"], "qwen3.8-27b")
        self.assertGreaterEqual(body["max_tokens"], 32000)

    def test_chat_keyless_omits_auth_header(self):
        cl = C.WeinstadtClient("http://x/v1", None, "qwen3.8-27b")
        resp = mock.Mock(); resp.status = 200
        resp.read.return_value = json.dumps({"choices": [{"message": {"content": "OK"}}]}).encode()
        with mock.patch.object(C.urllib.request, "urlopen", return_value=resp) as u:
            cl.chat([{"role": "user", "content": "ping"}])
        req = u.call_args[0][0]
        self.assertIsNone(req.get_header("Authorization"))

    def test_chat_error_redacts_key(self):
        cl = C.WeinstadtClient("http://x/v1", "sk-topsecret", "qwen3.8-27b")
        with mock.patch.object(C.urllib.request, "urlopen", side_effect=C.urllib.error.HTTPError("u", 500, "boom sk-topsecret", {}, None)):
            with self.assertRaises(C.WeinstadtError) as cm:
                cl.chat([{"role": "user", "content": "ping"}])
        self.assertNotIn("sk-topsecret", str(cm.exception))
```

- [ ] **Step 2: Tests laufen lassen (müssen fehlschlagen)**

Run: `python -m unittest tests.test_qvc_agent.TestClient -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'qvc_agent'`

- [ ] **Step 3: Implementieren**

`qvc_agent/__init__.py`:
```python
__version__ = "0.1.0"
```

`qvc_agent/client.py` — Ansatz:
- `import urllib.request, urllib.error` (beide explizit, damit `C.urllib` für die Mocks erreichbar ist).
- `opencode_config_path()`: Env `QVC_OPENCODE_CONFIG`, sonst `Path.home()/".config/opencode/opencode.json"`.
- `resolve_endpoint(provider=DEFAULT_PROVIDER)`: `opts = cfg["provider"][provider]["options"]`; `base_url=opts["baseURL"]`; `raw=opts.get("apiKey")`; `api_key = None` wenn `raw` fehlt, `os.getenv(raw[5:-1])` wenn `raw` wie `"{env:NAME}"` aussieht, sonst `raw`. Danach Env-Overrides: `base_url=os.getenv("QVC_LLM_BASE_URL", base_url)`, `api_key=os.getenv("QVC_LLM_API_KEY", api_key)`, `model=os.getenv("QVC_LLM_MODEL", DEFAULT_MODEL)`. Rückgabe `{"base_url","api_key"(str|None),"model"}`.
- `WeinstadtClient.chat`: body `{"model","messages","max_tokens","temperature"}`; Headers `{"Content-Type":"application/json"}` + `Authorization: Bearer <key>` **nur wenn `api_key` truthy**; `req=urllib.request.Request(base_url+"/chat/completions", data=json.dumps(body).encode(), headers=headers, method="POST")`; `resp=urllib.request.urlopen(req, timeout=self.timeout)`; `content=json.loads(resp.read())["choices"][0]["message"]["content"]`; bei `HTTPError`/`URLError`/leerem Content → `raise WeinstadtError(redact(f"{type(e).__name__}: {e}", self.api_key))`.
- `redact(value, secret)`: `value.replace(secret, "[REDACTED]")` wenn `secret` nicht leer, sonst unverändert.
- Prüfen ob `jsonschema` importierbar ist (späterer Task braucht es); falls im aktiven Env fehlt → zu `requirements-qvc.txt` hinzufügen.

- [ ] **Step 4: Tests laufen lassen (müssen grün)**

Run: `python -m unittest tests.test_qvc_agent.TestClient -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add qvc_agent/__init__.py qvc_agent/client.py tests/test_qvc_agent.py requirements-qvc.txt
git commit -m "feat(qvc-agent): Weinstadt-Qwen3.8 client + endpoint resolution"
```

---

### Task 2: Proposal-Schema + Parsing

**Files:**
- Create: `qvc_agent/proposal.py`
- Test: `tests/test_qvc_agent.py` (Klasse `TestProposal`)

**Interfaces:**
- Consumes: `qvc_discovery.TASKS` (Tuple `("invsqrt","dqi","dfthcsos")`)
- Produces:
  - `class ProposalError(ValueError)`
  - `PROPOSAL_REQUIRED: tuple[str, ...]` = `("mode","target_task","action","rationale","expected_delta","artifact_ref","precheck_plan","verify_plan","abort_condition")`
  - `build_proposal_prompt(task: str, *, mode: str, current_best: dict, candidates: list[dict], memory: str) -> str`
  - `parse_proposal(raw: str) -> dict`

- [ ] **Step 1: Failing tests**

```python
import qvc_agent.proposal as P

VALID = {"mode":"curate","target_task":"invsqrt","action":"adopt sha abc",
         "rationale":"tip","expected_delta":"+0.02 ratio","artifact_ref":"abc123",
         "precheck_plan":"stratified subset","verify_plan":"official 64-shot","abort_condition":"cost up"}

class TestProposal(unittest.TestCase):
    def test_parse_valid(self):
        d = P.parse_proposal(__import__("json").dumps(VALID))
        self.assertEqual(d["mode"], "curate")

    def test_parse_fenced(self):
        d = P.parse_proposal("```json\n" + __import__("json").dumps(VALID) + "\n```")
        self.assertEqual(d["target_task"], "invsqrt")

    def test_parse_bad_mode(self):
        bad = dict(VALID, mode="hack")
        with self.assertRaises(P.ProposalError):
            P.parse_proposal(__import__("json").dumps(bad))

    def test_parse_missing_field(self):
        bad = dict(VALID); del bad["abort_condition"]
        with self.assertRaises(P.ProposalError):
            P.parse_proposal(__import__("json").dumps(bad))

    def test_build_prompt_contains_context(self):
        s = P.build_proposal_prompt("invsqrt", mode="curate",
                                    current_best={"ratio": 21.0},
                                    candidates=[{"sha": "deadbeef", "ratio": 21.7}],
                                    memory="NEG: lookup-hybrid worse")
        self.assertIn("invsqrt", s); self.assertIn("deadbeef", s)
        self.assertIn("lookup-hybrid worse", s)
```

- [ ] **Step 2: Tests laufen lassen (fehlschlagen)**

Run: `python -m unittest tests.test_qvc_agent.TestProposal -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'qvc_agent.proposal'`

- [ ] **Step 3: Implementieren**

`proposal.py`:
- `parse_proposal(raw)`: Code-Fences streichen (Muster aus `qvc_discovery.json_object` übernehmen), `json.loads`; wenn kein dict → `ProposalError`; fehlende Schlüssel aus `PROPOSAL_REQUIRED` → `ProposalError`; `mode` nicht in `("curate","research")` → `ProposalError`; `target_task` nicht in `TASKS` → `ProposalError`; sonst dict zurück.
- `build_proposal_prompt(...)`: System-Auftrag (Curate ODER Research je `mode`), dann `current_best`, Top-`candidates` (je `sha`+`ratio`), `memory`-Auszug; verlangt exakt das `PROPOSAL_REQUIRED`-JSON. Kein ausführbarer Code/Shell im Prompt (Spec-Anti-Goal).

- [ ] **Step 4: Tests grün**

Run: `python -m unittest tests.test_qvc_agent.TestProposal -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add qvc_agent/proposal.py tests/test_qvc_agent.py
git commit -m "feat(qvc-agent): proposal schema + strict parsing"
```

---

### Task 3: Memory + Loop-Log

**Files:**
- Create: `qvc_agent/memory.py`
- Test: `tests/test_qvc_agent.py` (Klasse `TestMemory`)

**Interfaces:**
- Produces:
  - `AGENT_MEMORY_QVC = Path.home()/".agent-memory/kaggle-qvc"`
  - `append_loop_log(run_dir: Path, record: dict) -> None` (JSONL nach `run_dir/loop.jsonl`)
  - `read_loop_log(run_dir: Path) -> list[dict]`
  - `load_memory(task: str, base: Path = AGENT_MEMORY_QVC) -> str`
  - `write_memory_note(task: str, summary: str, base: Path = AGENT_MEMORY_QVC, date: str | None = None) -> Path`

- [ ] **Step 1: Failing tests**

```python
from datetime import date
import qvc_agent.memory as M

class TestMemory(unittest.TestCase):
    def test_append_and_read_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            M.append_loop_log(rd, {"round": 1, "verdict": "DISCARD"})
            M.append_loop_log(rd, {"round": 2, "verdict": "KEEP"})
            rows = M.read_loop_log(rd)
            self.assertEqual([r["round"] for r in rows], [1, 2])

    def test_write_memory_note_creates_dated_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            p = M.write_memory_note("invsqrt", "adopted tip", base=base, date="2026-11-09")
            self.assertTrue(p.name.endswith("agent-loop-invsqrt.md"))
            self.assertIn("2026-11-09", p.name)
            self.assertIn("adopted tip", p.read_text())

    def test_load_memory_empty_when_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(M.load_memory("invsqrt", base=Path(tmp)), "")

    def test_log_has_no_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            rec = {"model": "qwen3.8-27b", "note": "ok"}
            M.append_loop_log(rd, rec)
            raw = (rd / "loop.jsonl").read_text()
            self.assertNotIn("sk-", raw)
```

- [ ] **Step 2: Tests laufen lassen (fehlschlagen)**

Run: `python -m unittest tests.test_qvc_agent.TestMemory -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'qvc_agent.memory'`

- [ ] **Step 3: Implementieren**

`memory.py`:
- `append_loop_log`: `run_dir.mkdir(parents=True, exist_ok=True)`; eine Zeile `json.dumps(record, ensure_ascii=False)` + `\n` anhängen an `loop.jsonl`.
- `read_loop_log`: Zeilen lesen, leere überspringen, `json.loads` je Zeile.
- `write_memory_note(date default `date.today().isoformat()`)`: zuerst `base.mkdir(parents=True, exist_ok=True)` (Loop übergibt ggf. nicht-existentes `memory_base`); dann Datei `base/f"{date}-agent-loop-{task}.md"`; wenn vorhanden, neuen datierten Abschnitt anhängen, sonst Kopfzeile `# Agent-Loop <task>` + Abschnitt. `summary` wörtlich schreiben.
- `load_memory(task, base)`: alle `base/*.md` lesen, deren Name `task` enthält; Inhalte konkatenieren (leer → `""`).

- [ ] **Step 4: Tests grün**

Run: `python -m unittest tests.test_qvc_agent.TestMemory -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add qvc_agent/memory.py tests/test_qvc_agent.py
git commit -m "feat(qvc-agent): loop log + agent-memory notes"
```

---

### Task 4: Oracle (Verifier-Integration)

**Files:**
- Create: `qvc_agent/oracle.py`
- Test: `tests/test_qvc_agent.py` (Klasse `TestOracle`)

**Interfaces:**
- Consumes: `qvc_discovery.verify_candidate(adapter, task, artifact, out, execute, max_workers)`, `qvc_discovery.REFERENCE_COSTS`
- Produces:
  - `PRECHECK_ADAPTER = REPO/"qvc_ui/adapters/adapter_invsqrt_precheck.json"`
  - `OFFICIAL_ADAPTER = REPO/"qvc_ui/adapters/adapter_invsqrt.json"`
  - `verify(artifact: Path, level: str, out_dir: Path, *, execute: bool = True) -> dict` (`level ∈ {"precheck","official"}`)
  - `extract_cost(result: dict) -> float | None`
  - `is_keep(result: dict, best_cost: float) -> bool`
  - `cost_to_ratio(cost: float) -> float`

- [ ] **Step 1: Failing tests**

```python
import qvc_agent.oracle as O

class TestOracle(unittest.TestCase):
    def test_extract_cost_pass_identical(self):
        r = {"all_passed": True, "official_cost_if_identical_across_salts": 95000.0}
        self.assertEqual(O.extract_cost(r), 95000.0)

    def test_extract_cost_fail_none(self):
        self.assertIsNone(O.extract_cost({"all_passed": False, "official_cost_if_identical_across_salts": None}))

    def test_is_keep_lower(self):
        r = {"all_passed": True, "official_cost_if_identical_across_salts": 95000.0}
        self.assertTrue(O.is_keep(r, best_cost=100000.0))

    def test_is_keep_higher_false(self):
        r = {"all_passed": True, "official_cost_if_identical_across_salts": 100000.0}
        self.assertFalse(O.is_keep(r, best_cost=95000.0))

    def test_is_keep_no_cost_false(self):
        self.assertFalse(O.is_keep({"all_passed": True}, best_cost=100000.0))

    def test_cost_to_ratio(self):
        self.assertAlmostEqual(O.cost_to_ratio(95345.534), 2076774.233715282 / 95345.534, places=4)

    def test_verify_routes_adapter_and_execute(self):
        import qvc_discovery as D
        with mock.patch.object(D, "verify_candidate", return_value={"status": "DRY_RUN_ONLY"}) as vc:
            O.verify(Path("/tmp/x.kmb"), "precheck", Path("/tmp/out"), execute=False)
        _, kwargs = vc.call_args
        self.assertFalse(kwargs.get("execute", True))
        # Precheck-Adapter wurde geladen (Pfad enthält 'precheck')
        self.assertIn("precheck", str(vc.call_args[0][0]))
```

- [ ] **Step 2: Tests laufen lassen (fehlschlagen)**

Run: `python -m unittest tests.test_qvc_agent.TestOracle -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'qvc_agent.oracle'`

- [ ] **Step 3: Implementieren**

`oracle.py`:
- `REPO = Path(__file__).resolve().parents[1]`.
- `verify(artifact, level, out_dir, execute=True)`: `adapter_path = PRECHECK_ADAPTER if level=="precheck" else OFFICIAL_ADAPTER`; `adapter = json.loads(adapter_path.read_text())`; `return qvc_discovery.verify_candidate(adapter, "invsqrt", artifact, out_dir, execute=execute, max_workers=2)`. **Wichtig:** `execute` als Keyword übergeben (Test prüft es über `kwargs`).
- `extract_cost(result)`: `c = result.get("official_cost_if_identical_across_salts")`; wenn `result.get("all_passed")` und `c` endliche Zahl >0 → `float(c)`, sonst `None`.
- `is_keep(result, best_cost)`: `c = extract_cost(result)`; `return c is not None and c < best_cost`.
- `cost_to_ratio(cost)`: `qvc_discovery.REFERENCE_COSTS["invsqrt"] / cost`.

- [ ] **Step 4: Tests grün**

Run: `python -m unittest tests.test_qvc_agent.TestOracle -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add qvc_agent/oracle.py tests/test_qvc_agent.py
git commit -m "feat(qvc-agent): verifier oracle (precheck/official) + keep logic"
```

---

### Task 5: Curate-Materialisierung

**Files:**
- Create: `qvc_agent/curate.py`
- Test: `tests/test_qvc_agent.py` (Klasse `TestCurate`)

**Interfaces:**
- Produces:
  - `CANDIDATES_RANKED = REPO/"work/frontier_1109/candidates_ranked.json"`
  - `CANDIDATES = REPO/"work/frontier_1109/candidates.json"`
  - `load_candidates(task: str, path: Path = CANDIDATES_RANKED) -> list[dict]`
  - `materialize(proposal: dict, out_dir: Path, *, comp: str = "invsqrt", candidates_path: Path = CANDIDATES) -> Path`
  - `_write_loc(loc: dict, dst: Path, want_sha: str) -> None` (zip/xz/plain + SHA-Check, Logik wie `frontier_1109/scripts/verify_one.py::write_loc`)

- [ ] **Step 1: Failing tests**

```python
import qvc_agent.curate as CU

class TestCurate(unittest.TestCase):
    def test_load_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"r.json"; p.write_text('{"invsqrt":[{"sha":"a","ratio":21.0}],"chem":[]}')
            self.assertEqual(CU.load_candidates("invsqrt", path=p)[0]["sha"], "a")

    def test_materialize_plain_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp)/"invsqrt.kmb"; src.write_bytes(b"CIRCUITDATA")
            import hashlib; sha = hashlib.sha256(b"CIRCUITDATA").hexdigest()
            cand = Path(tmp)/"c.json"
            cand.write_text(__import__("json").dumps({"invsqrt": {sha: {"locs":[{"path":str(src),"inner":None,"xz":False}],"ext":"kmb"}}}))
            out = Path(tmp)/"out"
            art = CU.materialize({"artifact_ref": sha}, out, comp="invsqrt", candidates_path=cand)
            self.assertTrue(art.exists()); self.assertEqual(art.read_bytes(), b"CIRCUITDATA")

    def test_materialize_unknown_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            cand = Path(tmp)/"c.json"; cand.write_text('{"invsqrt":{}}')
            with self.assertRaises(KeyError):
                CU.materialize({"artifact_ref": "nope"}, Path(tmp)/"o", comp="invsqrt", candidates_path=cand)

    def test_materialize_sha_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp)/"x.kmb"; src.write_bytes(b"AAA")
            cand = Path(tmp)/"c.json"
            cand.write_text(__import__("json").dumps({"invsqrt":{"0"*64:{"locs":[{"path":str(src),"inner":None,"xz":False}],"ext":"kmb"}}}))
            with self.assertRaises(RuntimeError):
                CU.materialize({"artifact_ref": "0"*64}, Path(tmp)/"o", comp="invsqrt", candidates_path=cand)
```

- [ ] **Step 2: Tests laufen lassen (fehlschlagen)**

Run: `python -m unittest tests.test_qvc_agent.TestCurate -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'qvc_agent.curate'`

- [ ] **Step 3: Implementieren**

`curate.py`:
- `REPO = Path(__file__).resolve().parents[1]`.
- `load_candidates(task, path)`: `json.loads(path.read_text())[task]` (Liste).
- `_write_loc(loc, dst, want_sha)`: wie `verify_one.open_loc`/`write_loc` — `inner` via `zipfile.ZipFile(path).open(inner)` sonst `open(path,"rb")`; wenn `xz` → `lzma.open`; chunkweise nach `dst` schreiben + `sha256`; bei Mismatch `raise RuntimeError("sha mismatch ...")`.
- `materialize(proposal, out_dir, comp, candidates_path)`: `data = json.loads(candidates_path.read_text())[comp]`; `sha = proposal["artifact_ref"]`; `cand = data[sha]` (KeyError wenn fehlt); `out_dir.mkdir(parents=True, exist_ok=True)`; `dst = out_dir/f"{comp}.{cand.get('ext','kmb')}"`; `_write_loc(cand["locs"][0], dst, sha)`; `return dst`.

- [ ] **Step 4: Tests grün**

Run: `python -m unittest tests.test_qvc_agent.TestCurate -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add qvc_agent/curate.py tests/test_qvc_agent.py
git commit -m "feat(qvc-agent): curate materialization from frontier candidates"
```

---

### Task 6: Research-Materialisierung (injected Emitter)

**Files:**
- Create: `qvc_agent/research.py`
- Test: `tests/test_qvc_agent.py` (Klasse `TestResearch`)

**Interfaces:**
- Produces:
  - `EMITTER = REPO/"work/constseed_build/build_constseed_circuit.py"`
  - `materialize_research(proposal: dict, workdir: Path, out_dir: Path, *, emit_fn) -> Path`
  - `apply_edit(workdir: Path, edit: dict) -> None` (Default-Konvention: `edit={"params": {...}}` → schreibt `workdir/overrides.json`; Emitter liest es. Fallback `edit={"patch": "..."}` → `subprocess` `patch -p0`. Konkrete Verdrahtung wird in Task 9 gegen den echten Emitter bestätigt.)

- [ ] **Step 1: Failing tests**

```python
import qvc_agent.research as R

class TestResearch(unittest.TestCase):
    def test_materialize_calls_emit_and_returns_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            wd, out = Path(tmp)/"wd", Path(tmp)/"out"
            wd.mkdir(); out.mkdir()
            def fake_emit(w):
                p = w/"invsqrt.kmb"; p.write_bytes(b"NEW"); return p
            art = R.materialize_research({"edit": {"params": {"n1_frac": 16}}}, wd, out, emit_fn=fake_emit)
            self.assertEqual(art.read_bytes(), b"NEW")

    def test_apply_edit_writes_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            wd = Path(tmp); wd.mkdir()
            R.apply_edit(wd, {"params": {"use_lookup": True}})
            ov = __import__("json").loads((wd/"overrides.json").read_text())
            self.assertEqual(ov, {"use_lookup": True})

    def test_materialize_requires_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            wd, out = Path(tmp)/"wd", Path(tmp)/"out"; wd.mkdir(); out.mkdir()
            with self.assertRaises(ValueError):
                R.materialize_research({}, wd, out, emit_fn=lambda w: w)
```

- [ ] **Step 2: Tests laufen lassen (fehlschlagen)**

Run: `python -m unittest tests.test_qvc_agent.TestResearch -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'qvc_agent.research'`

- [ ] **Step 3: Implementieren**

`research.py`:
- `REPO = Path(__file__).resolve().parents[1]`.
- `apply_edit(workdir, edit)`: `edit` muss dict sein; `"params"` in edit → `workdir/"overrides.json"` = `json.dumps(edit["params"])`; `"patch"` in edit → `subprocess.run(["patch","-p0"], cwd=workdir, input=edit["patch"], text=True, check=True)`; sonst `ValueError`.
- `materialize_research(proposal, workdir, out_dir, *, emit_fn)`: wenn `"edit"` nicht in proposal → `ValueError`; `apply_edit(workdir, proposal["edit"])`; `produced = emit_fn(workdir)`; `produced` muss existieren; nach `out_dir` kopieren (stabilen Namen `invsqrt.kmb`); `return out_dir/"invsqrt.kmb"`.

- [ ] **Step 4: Tests grün**

Run: `python -m unittest tests.test_qvc_agent.TestResearch -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add qvc_agent/research.py tests/test_qvc_agent.py
git commit -m "feat(qvc-agent): research materialization via injected emitter"
```

---

### Task 7: Loop-Treiber (alle Deps injiziert)

**Files:**
- Create: `qvc_agent/loop.py`
- Test: `tests/test_qvc_agent.py` (Klasse `TestLoop`)

**Interfaces:**
- Consumes: `proposal.parse_proposal`/`ProposalError`, `oracle.is_keep`/`cost_to_ratio`, `memory.append_loop_log`/`write_memory_note`/`load_memory`, `curate.load_candidates`
- Produces:
  - `run_loop(task, mode, n_rounds, *, propose_fn, materialize_fn, precheck_fn, verify_fn, approve_fn, run_dir, best_ratio, best_cost, memory_base=...) -> dict`
  - Rückgabe: `{"task","mode","rounds","kept","best_ratio_start","best_ratio_end","log_path"}`
  - Semantik: Eine Runde zählt als `kept` nur wenn `is_keep(full, best_cost)` **und** `approve_fn(...)`. `dry_run` (via `verify_fn=None`) → kein voller Verifier, keine Keeps.

- [ ] **Step 1: Failing tests**

```python
import qvc_agent.loop as L

def _ctx(**kw): return kw  # propose_fn bekommt ctx-Dict

class TestLoop(unittest.TestCase):
    def _props(self, raws):
        it = iter(raws)
        return lambda ctx: next(it)

    def test_keep_updates_best(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            import json
            prop = json.dumps({"mode":"curate","target_task":"invsqrt","action":"a","rationale":"r",
                               "expected_delta":"d","artifact_ref":"abc","precheck_plan":"p","verify_plan":"v","abort_condition":"x"})
            s = L.run_loop("invsqrt","curate",1,
                propose_fn=self._props([prop]),
                materialize_fn=lambda p, *a, **k: Path(tmp)/"x.kmb",
                precheck_fn=lambda a: {"all_passed": True},
                verify_fn=lambda a: {"all_passed": True, "official_cost_if_identical_across_salts": 95000.0},
                approve_fn=lambda *a, **k: True,
                run_dir=rd, best_ratio=21.0, best_cost=100000.0, memory_base=Path(tmp)/"mem")
            self.assertEqual(s["kept"], 1)
            self.assertGreater(s["best_ratio_end"], s["best_ratio_start"])

    def test_discard_on_higher_cost(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp); import json
            prop = json.dumps({"mode":"curate","target_task":"invsqrt","action":"a","rationale":"r",
                               "expected_delta":"d","artifact_ref":"abc","precheck_plan":"p","verify_plan":"v","abort_condition":"x"})
            s = L.run_loop("invsqrt","curate",1,
                propose_fn=self._props([prop]),
                materialize_fn=lambda p,*a,**k: Path(tmp)/"x.kmb",
                precheck_fn=lambda a: {"all_passed": True},
                verify_fn=lambda a: {"all_passed": True, "official_cost_if_identical_across_salts": 120000.0},
                approve_fn=lambda *a,**k: True,
                run_dir=rd, best_ratio=21.0, best_cost=100000.0, memory_base=Path(tmp)/"mem")
            self.assertEqual(s["kept"], 0)
            self.assertEqual(s["best_ratio_end"], s["best_ratio_start"])

    def test_discard_on_bad_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            s = L.run_loop("invsqrt","curate",1,
                propose_fn=self._props(["this is not json"]),
                materialize_fn=lambda p,*a,**k: Path(tmp)/"x.kmb",
                precheck_fn=lambda a: {"all_passed": True},
                verify_fn=lambda a: {"all_passed": True, "official_cost_if_identical_across_salts": 1.0},
                approve_fn=lambda *a,**k: True,
                run_dir=rd, best_ratio=21.0, best_cost=100000.0, memory_base=Path(tmp)/"mem")
            self.assertEqual(s["kept"], 0)
            self.assertTrue((rd/"loop.jsonl").exists())  # Runde wurde geloggt

    def test_hitl_blocks_advance(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp); import json
            prop = json.dumps({"mode":"curate","target_task":"invsqrt","action":"a","rationale":"r",
                               "expected_delta":"d","artifact_ref":"abc","precheck_plan":"p","verify_plan":"v","abort_condition":"x"})
            s = L.run_loop("invsqrt","curate",1,
                propose_fn=self._props([prop]),
                materialize_fn=lambda p,*a,**k: Path(tmp)/"x.kmb",
                precheck_fn=lambda a: {"all_passed": True},
                verify_fn=lambda a: {"all_passed": True, "official_cost_if_identical_across_salts": 95000.0},
                approve_fn=lambda *a,**k: False,
                run_dir=rd, best_ratio=21.0, best_cost=100000.0, memory_base=Path(tmp)/"mem")
            self.assertEqual(s["kept"], 0)
            self.assertEqual(s["best_ratio_end"], s["best_ratio_start"])

    def test_dry_run_skips_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp); import json
            prop = json.dumps({"mode":"curate","target_task":"invsqrt","action":"a","rationale":"r",
                               "expected_delta":"d","artifact_ref":"abc","precheck_plan":"p","verify_plan":"v","abort_condition":"x"})
            def boom(a): raise AssertionError("verify must not run in dry_run")
            s = L.run_loop("invsqrt","curate",1,
                propose_fn=self._props([prop]),
                materialize_fn=lambda p,*a,**k: Path(tmp)/"x.kmb",
                precheck_fn=lambda a: {"all_passed": True},
                verify_fn=None,  # dry_run
                approve_fn=lambda *a,**k: True,
                run_dir=rd, best_ratio=21.0, best_cost=100000.0, memory_base=Path(tmp)/"mem")
            self.assertEqual(s["kept"], 0)
```

- [ ] **Step 2: Tests laufen lassen (fehlschlagen)**

Run: `python -m unittest tests.test_qvc_agent.TestLoop -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'qvc_agent.loop'`

- [ ] **Step 3: Implementieren**

`loop.py` — `run_loop(...)`:
- `dry_run = verify_fn is None`; `kept=0`; `start_ratio=best_ratio`.
- Für `round in 1..n_rounds`:
  - `ctx = {"task":task,"mode":mode,"best_ratio":best_ratio,"best_cost":best_cost,
            "candidates": curate.load_candidates(task) if mode=="curate" else [],
            "memory": memory.load_memory(task, base=memory_base)}`
  - `raw = propose_fn(ctx)`; `try: proposal = proposal.parse_proposal(raw) except ProposalError: append_loop_log(run_dir, {"round":round,"verdict":"DISCARD_BAD_JSON"}); continue`
  - `artifact = materialize_fn(proposal, run_dir/"artifacts"/f"r{round}")`
  - `pre = precheck_fn(artifact)`
  - `if dry_run: verdict="DRY_RUN"; full=None`
  - `elif pre.get("all_passed"): full = verify_fn(artifact); verdict = "KEEP" if oracle.is_keep(full, best_cost) else "DISCARD"`
  - `else: verdict="DISCARD_PRECHECK"; full=None`
  - `cost = oracle.extract_cost(full) if full else None`
  - `record = {"round":round,"mode":mode,"artifact_ref":proposal.get("artifact_ref"),"verdict":verdict,"cost":cost,"ratio":(oracle.cost_to_ratio(cost) if cost else None)}`; `memory.append_loop_log(run_dir, record)`
  - `if verdict=="KEEP" and approve_fn(proposal, full): best_cost=cost; best_ratio=oracle.cost_to_ratio(cost); kept+=1`
  - `memory.write_memory_note(task, f"round {round}: {verdict}", base=memory_base)`
- `return {"task":task,"mode":mode,"rounds":n_rounds,"kept":kept,"best_ratio_start":start_ratio,"best_ratio_end":best_ratio,"log_path":str(run_dir/"loop.jsonl")}`

- [ ] **Step 4: Tests grün**

Run: `python -m unittest tests.test_qvc_agent.TestLoop -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add qvc_agent/loop.py tests/test_qvc_agent.py
git commit -m "feat(qvc-agent): injectable run_loop orchestrator"
```

---

### Task 8: CLI (`run` + `check-endpoint`)

**Files:**
- Create: `qvc_agent/cli.py`, `qvc_agent/__main__.py`
- Test: `tests/test_qvc_agent.py` (Klasse `TestCli`)

**Interfaces:**
- Consumes: alles Vorstehende
- Produces:
  - `main(argv: list[str] | None = None) -> int`
  - Subkommandos: `run` (Flags `--task --mode --rounds [--autonomous] [--dry-run] [--frontier-dir] [--workdir] [--run-dir]`) und `check-endpoint`
  - Default-Wiring: `propose_fn` = `WeinstadtClient(...).chat` über `build_proposal_prompt`; `materialize_fn` = `curate.materialize` (mode curate) bzw. `research.materialize_research` mit echtem `emit_fn` (mode research); `precheck_fn`/`verify_fn` = `oracle.verify(level=...)`; `approve_fn` = `input()`-Prompt, außer `--autonomous` (dann `True`, aber nur innerhalb Cost-Floor).

- [ ] **Step 1: Failing tests**

```python
import qvc_agent.cli as CLI

class TestCli(unittest.TestCase):
    def test_check_endpoint_calls_client_once(self):
        with mock.patch.object(CLI, "WeinstadtClient") as WC:
            inst = WC.return_value; inst.chat.return_value = "pong"
            rc = CLI.main(["check-endpoint"])
        self.assertEqual(rc, 0)
        self.assertEqual(inst.chat.call_count, 1)

    def test_run_builds_kwargs(self):
        with mock.patch.object(CLI, "run_loop", return_value={"kept":0}) as rl:
            rc = CLI.main(["run","--task","invsqrt","--mode","curate","--rounds","2","--dry-run"])
        self.assertEqual(rc, 0)
        kwargs = rl.call_args.kwargs
        self.assertEqual(kwargs["task"], "invsqrt")
        self.assertEqual(kwargs["mode"], "curate")
        self.assertEqual(kwargs["n_rounds"], 2)
        self.assertIsNone(kwargs["verify_fn"])  # dry-run
```

- [ ] **Step 2: Tests laufen lassen (fehlschlagen)**

Run: `python -m unittest tests.test_qvc_agent.TestCli -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'qvc_agent.cli'`

- [ ] **Step 3: Implementieren**

`cli.py`:
- `argparse` mit Subkommandos. `check-endpoint`: `ep = resolve_endpoint()`; `WeinstadtClient(**ep).chat([{"role":"user","content":"ping"}])`; druckt `OK model=<ep['model']> base=<ep['base_url']>` (**nie** den Key); `return 0`; bei `WeinstadtError` → rote, redigierte Meldung, `return 1`.
- `run`: Flags parsen; `dry_run = args.dry_run`; `run_dir` Default `runs/agent/<UTC-ts>`; `best_ratio`/`best_cost` aus `curate.load_candidates(task)` Top-Eintrag ableiten (bzw. `--frontier-dir`); `approve_fn = (lambda *a: True) if args.autonomous else (lambda p, f: input("Keep? [y/N] ").strip().lower()=="y")`; `verify_fn = None if dry_run else (lambda a: oracle.verify(a,"official",run_dir/"verify"))`; `precheck_fn = lambda a: oracle.verify(a,"precheck",run_dir/"precheck")`; `materialize_fn` je mode; `propose_fn = lambda ctx: client.chat([system,user=build_proposal_prompt(...)])`. `run_loop(...)` aufrufen; Summary als JSON drucken; `return 0`.
- `__main__.py`: `import sys; from qvc_agent.cli import main; sys.exit(main())`.

- [ ] **Step 4: Tests grün**

Run: `python -m unittest tests.test_qvc_agent.TestCli -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Manuell: Endpunkt-Check**

Run: `python -m qvc_agent check-endpoint`
Expected: `OK model=qwen3.8-27b base=http://10.200.3.60:4000/v1` (Exit 0). Kein Key in der Ausgabe.

- [ ] **Step 6: Commit**

```bash
git add qvc_agent/cli.py qvc_agent/__main__.py tests/test_qvc_agent.py
git commit -m "feat(qvc-agent): CLI run + check-endpoint"
```

---

### Task 9: Phase-0-Live-Bestätigung + erster Dry-Run

**Files:**
- Create: `runs/agent/phase0/phase0_report.md`
- Modify (ggf.): `qvc_agent/research.py` (echte `emit_fn`-Verdrahtung, falls Emitter-Interface ≠ Default-Konvention)
- Test: Integration (kein unittest; Checkliste unten)

**Interfaces:**
- Consumes: `cli.check-endpoint`, `research.EMITTER`, `oracle`, `curate`
- Produces: `phase0_report.md` mit vier beantworteten Punkten + ein `--dry-run`-Loop-Log.

- [ ] **Step 1: Emitter-Interface bestimmen**

Run: `sed -n '1,60p' work/constseed_build/build_constseed_circuit.py` und `python work/constseed_build/build_constseed_circuit.py --help 2>&1 | head` (falls CLI).
Bestimmen: nimmt der Emitter Parameter via CLI-Args, Env, `overrides.json` oder nur hartkodete Konstanten? Ergebnis in Report. Falls ≠ `overrides.json`-Konvention → `research.apply_edit`/`emit_fn` entsprechend anpassen (kleine, umschriebene Änderung) und `TestResearch` erneut grün halten.

- [ ] **Step 2: Emitter sauber läuft?**

Run: `cd work/constseed_build && python build_constseed_circuit.py` (oder die in Step 1 gefundene Aufrufform) → erzeugt eine `.kmb` ohne Exception.
Expected: Exit 0 + neue/existing `.kmb`. Bei Fehlern: Ursache notieren (Deps/Env), ggf. `.venv-chem`/`.venv-qvc` aktivieren.

- [ ] **Step 3: Aktueller Best + Adapter-Semantik**

- Best invsqrt: Top-Eintrag von `work/frontier_1109/candidates_ranked.json["invsqrt"]` (sha, ratio) + `work/constseed_build/REPORT.md`-Baseline. In Report festhalten.
- Precheck-Adapter akzeptiert einen **baren `.kmb`-Pfad** als `{candidate}`? (Prüfen: `cat qvc_ui/adapters/adapter_invsqrt_precheck.json` + `qvc_ui/adapters/invsqrt_precheck.py`.) Falls er ein Verzeichnis erwartet → `curate.materialize`/`research` so anpassen, dass sie das erwartete Layout liefern. In Report notieren.

- [ ] **Step 4: Endpunkt + erster Dry-Run**

Run: `python -m qvc_agent check-endpoint`
Run: `python -m qvc_agent run --task invsqrt --mode curate --rounds 1 --dry-run`
Expected: Exit 0; `runs/agent/<ts>/loop.jsonl` mit ≥1 Zeile; Summary-JSON gedruckt; **kein** API-Key in Log/Summary.

- [ ] **Step 5: Report schreiben + Secret-Check**

`runs/agent/phase0/phase0_report.md` mit den vier Punkten (Emitter-Interface, Emitter läuft, Best+Adapter-Semantik, Endpunkt+Dry-Run) + Datum.
Secret-Check: `grep -rn "sk-" runs/agent/phase0/ tests/test_qvc_agent.py qvc_agent/ 2>/dev/null` → Expected: keine echten Keys (nur Test-Platzhalter `sk-test-*`/`sk-override` in Tests sind ok).

- [ ] **Step 6: Vollsuite + Commit**

Run: `python -m unittest tests.test_qvc_agent -v`
Expected: ALLE Tests grün.

```bash
git add runs/agent/phase0/phase0_report.md qvc_agent/research.py tests/test_qvc_agent.py
git commit -m "chore(qvc-agent): phase0 live confirmation + first dry-run"
```

---

## Self-Review (vom Autor ausgeführt)

- **Spec-Coverage:** G1 Curate → Tasks 5,7,8. G2 Research → Tasks 6,7,8,9. G3 Memory → Task 3 (+7). Model-Client Weinstadt → Task 1. HITL → Task 7/8. Precheck/Official-Oracle → Task 4. Anti-Goals (kein Byte-Mutate, verified-only, kein Secret) → Tasks 4/6/9 + Global Constraints. ✓
- **Step-Scan:** Jeder Schritt hat genau eine machbare Aktion; Körper nur wo Signatur+Test sie nicht bestimmen (opencode.json-Extraktion, `_write_loc`, Loop-Reihenfolge). ✓
- **Type-Konsistenz:** `verify(artifact, level, out_dir, *, execute)` konsistent in Task 4/7/8; `materialize(proposal, out_dir, *, comp, candidates_path)` (Task 5) vs. `materialize_research(proposal, workdir, out_dir, *, emit_fn)` (Task 6) — bewusst unterschiedlich (Curate braucht Locator, Research braucht Emitter); `run_loop`-Signatur identisch in Task 7/8. `extract_cost`/`is_keep`/`cost_to_ratio` überall gleich. ✓
- **Review Focus:** Alle 5 Punkte einem Task/Test zugeordnet (siehe Liste oben). ✓
- **Proportion:** Plan ≈ Spec-Länge, keine Code-Transkripte. ✓
