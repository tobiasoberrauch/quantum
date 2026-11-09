# Phase-0 Live Confirmation + First Dry-Run

Date: 2026-11-09 (Mon) · Branch: `feat/qvc-agent-loop` · Interpreter: `.venv-qvc/bin/python` (Python 3.13.13)
Scope: confirm the LIVE wiring assumptions of the `qvc_agent` package (Tasks 1–8) and run one bounded end-to-end dry-run. Every live operation was bounded; failures were recorded, not looped/retried.

## (a) Current best invsqrt

Source: `work/frontier_1109/candidates_ranked.json` (top entry of `"invsqrt"`) + `work/constseed_build/REPORT.md`.

Best candidate (top of `"invsqrt"` list):
- `sha`   = `034c7c2a54d51e13aff6e62ec4c14997d3968b6c11122146c57290b1a1b8c7e2`
- `ratio` = `21.781557524769003`
- `score` = `95345.53400755058`  (score == official cost)
- `q`     = 62 · `status` = PASS
- top source: `d__heliosli__qcc-circuits-live`

constseed_build baseline (primary deliverable = lookup, all-persistent, per `REPORT.md`):
- `Q` = 384 · `C` = 8812 (mean Toffolis + T/4) · `ratio` = 0.614× · `score` = 3,383,896
- (raw Horner baseline: Q=509 / CCX=9434 / ratio 0.422×; official reference `ref_np10.kmb`: Q=260 / C=7988 / ratio 1.00×)

Note: the SOTA public candidate (ratio 21.78, q=62) is far ahead of our own constseed_build primary (ratio 0.614×, q=384). Phase-0 records this as the current frontier; the agent loop starts from `best_ratio_start = 21.781557524769003`.

## (b) Emitter interface

File read: `work/constseed_build/build_constseed_circuit.py` (512 lines).

Mechanism (precise): **argparse CLI + hardcoded module constants.** No env vars, no `overrides.json`.
- `main()` (lines 494–508): one optional positional `output` (default `<script_dir>/invsqrt_constseed.kmb`) and one `--hybrid` flag (`action='store_true'`).
- All circuit parameters are fixed module constants: widths `AB/SF/N1/G/OUT/F` (lines 42–47), per-multiply cutoffs `Q1_SH/Q1_L/Q1_W … P2_*` (lines 51–54), `COEFS` (lines 63–70), `ROM_TABLE` (line 92). The builder functions (`build()`, `build_hybrid()`) take no parameter arguments.
- So the ONLY thing an external caller can vary via CLI is the output path and the hybrid/all-persistent variant. There is no parameter-injection surface.

Ran once (bounded ≤ 600 s):
- `.venv-qvc/bin/python work/constseed_build/build_constseed_circuit.py` → **fails fast**: `ModuleNotFoundError: No module named 'kickmix'` (kickmix is not installed in `.venv-qvc`).
- `.venv-chem/bin/python work/constseed_build/build_constseed_circuit.py <temp-out.kmb>` → **exit 0**, ~0.14 s, wrote `/private/var/folders/ds/1bhl45857q78ws064zc_sb280000gn/T/opencode/phase0_emit_test.kmb` (714,688 bytes). Static cost printed: `num_qubits=384  static_CCX=8581  T=1  rot(h4+)=34  ops=75489  depth=4031` — matches the REPORT.md primary (Q=384 / CCX=8581). (Output was directed to a temp path to avoid clobbering the existing `work/constseed_build/invsqrt_constseed.kmb`.)
- Dependency: kickmix is a local build under `qualtran/kickmix/kickmix.cpython-313-darwin.so`, importable only from `.venv-chem`.

**Mismatch vs Task-6 default (documented, NOT changed):**
- `qvc_agent/research.py::apply_edit` (lines 27–50) assumes an `overrides.json` convention: `edit={"params": {...}}` writes `workdir/"overrides.json"` and the docstring claims "the emitter reads it." The real emitter does **not** read `overrides.json`; it takes CLI args + hardcoded constants. The default convention is therefore wrong for this emitter.
- `qvc_agent/cli.py::_default_emit` (lines 38–52) is also a placeholder: it runs `[sys.executable, EMITTER]` (i.e. `.venv-qvc`, which lacks kickmix) with `cwd=workdir` and returns `workdir/"invsqrt.kmb"`, but the emitter's default output is its own-dir `invsqrt_constseed.kmb` and it needs `.venv-chem`.
- Fixing this properly is **non-trivial**: it requires changing `apply_edit` to emit CLI args (and/or wiring `_default_emit` to `.venv-chem` + correct output path) AND updating `test_qvc_agent.py::TestResearch.test_apply_edit_writes_overrides` (lines 230–235), which explicitly asserts `overrides.json` is written. Per Task-9 scope this is documented here for a later task; `research.py` was left unchanged so its tests stay green.

## (c) Endpoint reachable

Command: `.venv-qvc/bin/python -m qvc_agent check-endpoint` (bounded ≤ 120 s)
- Output: `OK model=qwen3.8-27b base=http://192.168.212.81:8000/v1`
- Exit code: `0`
- No API key printed (the `audius-we` provider config has `apiKey = None`, i.e. keyless; `resolve_endpoint()` returns `api_key=None` and no `Authorization` header is sent). Matches the expected line exactly.

## (d) Precheck adapter accepts a bare .kmb

Answer: **YES.**
- argv is `<candidate.kmb> <salt>`: `qvc_ui/adapters/adapter_invsqrt_precheck.json` lines 4–9 → command = `[.venv-chem/bin/python, invsqrt_precheck.py, "{candidate}", "{salt}"]`, `salts=["notebook-verification"]`, `timeout_seconds=600`.
- The circuit is loaded from a bare `.kmb` file path via `km.Circuit.from_file(candidate, format="kmb")`: `qvc_ui/adapters/invsqrt_precheck.py:74`.
- So a bare `.kmb` file path is exactly the expected `{candidate}`. No directory layout is required.

## First dry-run (plumbing smoke test)

Command: `.venv-qvc/bin/python -m qvc_agent run --task invsqrt --mode curate --rounds 1 --dry-run` (bounded ≤ 300 s)
- Exit code: `0` (summary JSON printed at `cli.py:168`, then `return 0` at `cli.py:169`). Duration ≈ 24 s.
- Summary JSON (stdout):
  ```json
  {"task": "invsqrt", "mode": "curate", "rounds": 1, "kept": 0, "best_ratio_start": 21.781557524769003, "best_ratio_end": 21.781557524769003, "log_path": "runs/agent/20261109T221319Z/loop.jsonl"}
  ```
- `loop.jsonl` contents (1 line):
  ```json
  {"round": 1, "verdict": "DISCARD_BAD_JSON"}
  ```
- Verdict: **DISCARD_BAD_JSON**. Exactly ONE live LLM call was made (`propose_fn` → `WeinstadtClient.chat`, transport succeeded and returned a string); the returned content did not parse into a valid proposal object, so `proposal.parse_proposal` raised `ProposalError`, caught at `loop.py:83`, logged as `DISCARD_BAD_JSON`, and the round continued. Per the Phase-0 success bar this is a **PASSING** plumbing result (we are testing plumbing, not finding an improvement).
- No API key appeared in the summary or the log. ✓
- Precheck was **not reached**: the round stopped at the JSON-parse step, before `materialize_fn`/`precheck_fn` (`loop.py:89–90`). Recorded finding, not a failure. The live kickmix precheck/emitter dependency (`.venv-chem`) was separately confirmed working in step (b).

Success bar met: ≥1 round completed without crashing · `loop.jsonl` written with ≥1 line · summary JSON printed · no API key leaked.

## Secret check

Command: `grep -rn "sk-" runs/agent/phase0/ qvc_agent/ test_qvc_agent.py 2>/dev/null`
Result: **no real API keys.** All matches are either test placeholders (acceptable) or false positives:
- `test_qvc_agent.py`: `sk-test-secret` (19,40), `sk-override` (48,52), `sk-k` (58,65), `sk-topsecret` (80,81,84) — placeholders only; line 148 asserts `"sk-"` is absent from a captured raw log.
- `qvc_agent/cli.py:44` `Task-9 interface.` — false positive: the substring `sk-` occurs inside "**Tas**k**-**9".
- `qvc_agent/__pycache__/cli.cpython-313.pyc` — binary echo of the same `Task-9` string; not a key.

## Full suite

Command: `.venv-qvc/bin/python -m unittest test_qvc_agent -v`
Result: **Ran 37 tests … OK**, exit code `0`. All green (includes `TestResearch` which still asserts the `overrides.json` convention — unchanged in this task).

## Outcome

Phase-0 plumbing confirmed end-to-end: endpoint reachable & keyless (c), curate materialize data present (a/d), emitter runnable via `.venv-chem` (b), and one bounded dry-run completed a round without crashing and logged a verdict (dry-run). One open item carried to a later task: the research-mode `emit_fn`/`apply_edit` default assumes `overrides.json` + `.venv-qvc`, which does not match the real CLI-arg/`.venv-chem` emitter (b) — documented, not changed here.
