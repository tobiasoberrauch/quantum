# DAVID QVC Discovery Engine

A Python research workflow specifically for **Google Quantum AI — Verifiable Quantum Circuit Compilation**, targeting a combined score of 30 (as of the attached November 9, 2026 project brief). It uses the **official OpenRouter Python SDK**, model fallback chains, structured JSON, cross-domain analogy generation, and dialectical (thesis/antithesis/synthesis) critiques.

**Crucial distinction:** `discover` produces **hypotheses**, not executable circuits, discoveries, or verified improvements. It does not claim to have optimized any `.kmb` or `.npz` file. `verify` is an interface for a trusted, operator-supplied wrapper around Google's *real official verifiers*. It cannot independently establish that an arbitrary wrapper is honest.

## Project files

- `qvc_discovery.py` — standalone Python CLI with three subcommands.
- `competition_brief.md` — exact task context copied from the user-provided plan; treat estimates as provisional.
- `.env.example` — key and model overrides.
- `verifier_adapter.example.json` — human-supplied command templates; **must be configured**.
- `verified_costs.example.json` — deliberately invalid example to prevent fake successful scoring.
- `tests/test_qvc.py` — offline deterministic tests, no API calls.

## Installation

Requires Python 3.11+, network access and a funded OpenRouter API key for discovery:

```bash
cd qvc_discovery
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# Edit .env and replace OPENROUTER_API_KEY
```

**Do not use your competition's `.venv`** if it has broken kickmix dependencies; keep model orchestration isolated. Official verifiers on your system should use the separate, working `.venv-chem` environment mentioned in the brief.

## Run research discovery

Generate three independently produced ideas for `invsqrt`:

```bash
python qvc_discovery.py discover --task invsqrt --top 2 --output runs/invsqrt
```

Generate nine proposals across all three tasks (3 per task; 1 per generator role), followed by nine independently assigned reviews and a ranked backlog:

```bash
python qvc_discovery.py discover --task all --top 5 --workers 3 --output runs/first_round
```

To avoid rediscovering eliminated approaches, supply a UTF-8 memo copied or summarized from your actual QVC agent memory (`~/.agent-memory/kaggle-qvc/`). The script does not access that path on its own:

```bash
python qvc_discovery.py discover --task dfthcsos \
  --memory my_negative_results.md \
  --output runs/chem_round_2
```

Output:
- `runs/.../research.json` — schema-validated hypotheses, critiques, and model provenance.
- `runs/.../report.md` — short human-readable prioritized research backlog.

These outputs are **not verified improvements**. There is no live literature/patent search in this edition. Novelty claims stay `UNVERIFIED`.

## How models are assigned

| Research role | First model | Fallbacks |
| --- | --- | --- |
| Cross-domain analogy | `anthropic/claude-sonnet-4.6` | Qwen → DeepSeek → GPT-4 |
| Formal derivation | `openai/gpt-4` | DeepSeek → Claude → Qwen |
| Outside-the-box search | `deepseek/deepseek-r1-0528` | Qwen → Claude → GPT-4 |
| Dialectical peer review | A model **different from the originating model** | remaining models |
| Prioritization | Claude Sonnet | GPT-4 → Qwen → DeepSeek |

The actual model may change after fallback. Outputs record the model actually returned by OpenRouter.

If an identifier is unavailable, override using `QVC_SONNET`, `QVC_GPT4`, `QVC_DEEPSEEK`, `QVC_QWEN`. `json_schema` is attempted first for compatible models; local JSON Schema validation is always applied. Classic GPT-4 uses `json_object` mode. A malformed response is retried, then another model is tried.

## Connecting official verifiers

Because the Kaggle repository, kickmix objects and official verifier CLI are **not mounted in this project**, it would be misleading to invent a runnable `verify_submission_*.py` command or claim that submitting generic `.kmb` mutations is safe.

Instead, configure a trusted wrapper implementing the following contract. A wrapper is a small Python program you supply from your actual repository; it must call the official verifier through its documented real entrypoint and emit **only** one JSON object to stdout:

```json
{
  "source": "official_verifier",
  "passed": true,
  "cost": 123456.78,
  "salt": "audit-a",
  "shots": 102400
}
```

For `dqi`, it **must** run the required 102,400 test trials for each salt and verify the correct phase. For chemistry it must check factorization errors, Lambda, gap, ANGLE width and full block-encoding resource cost. For `invsqrt` it must check the complete required input domain/precision according to official rules, not merely the fast prefilter.

Make a local copy of `verifier_adapter.example.json`, replace `/ABSOLUTE/PATH/TO/TRUSTED_VERIFIER_WRAPPER` and its flags with your **tested and audited** command. Only the config file (not LLM output) supplies the command and arguments.

Run dry preview first:

```bash
python qvc_discovery.py verify \
  --adapter verifier_adapter.local.json \
  --task invsqrt \
  --candidate /absolute/path/to/invsqrt.kmb
```

Then explicitly opt into execution:

```bash
python qvc_discovery.py verify \
  --adapter verifier_adapter.local.json \
  --task invsqrt \
  --candidate /absolute/path/to/invsqrt.kmb \
  --execute
```

The verifier orchestration hashes candidate contents with SHA-256, caches successful checks, enforces one CPU thread per verifier process, captures process errors, times out, and requires at least five distinct `dqi` salts. It **does not automatically submit to Kaggle**, run model-generated shell commands, or download/execute arbitrary Kaggle assets.

Caveats: An external wrapper that lies or uses the wrong verifier can still produce a false result; audit it. Some salted verification costs may differ across runs; the code does not invent a stable cost in that case. Cache only stores successful runs and includes the command and salt, but if you change the implementation behind an unchanged wrapper path, clear `runs/verifications/verifier_cache.json` to invalidate stale entries.

## Scoring from real official verifier outputs

`score` accepts a manifest with exactly three tasks, each with `source: official_verifier`, `passed: true`, and a **full official cost**. For DQI the manifest also requires `shots: 102400` and a list of at least five independently checked salts. Example schema:

```json
{
  "invsqrt": {"source":"official_verifier","passed":true,"cost":123.4},
  "dqi": {"source":"official_verifier","passed":true,"cost":567.8,"shots":102400,"independent_salts":["a","b","c","d","e"]},
  "dfthcsos": {"source":"official_verifier","passed":true,"cost":999.0}
}
```

**All the numeric values above are dummy placeholders, not actual results.** The score command refuses `example_only` or `passed: false` records. Import actual verified outputs into your own manifest, then:

```bash
python qvc_discovery.py score --costs /path/to/real_verified_costs.json
```

Formula: `score = (reference_invsqrt/cost_invsqrt * reference_dqi/cost_dqi * reference_chem/cost_chem) ** (1/3)`.

## Specific competitive constraints embedded in prompts

- `invsqrt`: Q×C, 1/√x, precision and clean ancilla, start at public valid ratio ~21.78; do not repeat previously rejected P-A/P-B redesigns or unsafe precision shortcuts.
- `dqi`: R×Q²×T, 102,400 official trials, five independent salts, avoid seed/hash fishing and invalid syndrome overwrites; generator access is a hard dependency for source-level changes.
- `dfthcsos`: lambda_eff×T×Q, 20mHa error thresholds, Lambda and gap checks, 128-qubit per-ANGLE limit; focus on coupled factorization, Givens and QROM optimization; shape trial schedule (130,35) → (130,36) → (132,35).

## Validation

```bash
python -m unittest -v tests/test_qvc.py
python -m py_compile qvc_discovery.py
```

All offline tests use synthetic inputs and never call OpenRouter or official verifiers.

## What is missing for a truly autonomous optimization loop

There is no trustworthy way to mutate arbitrary quantum-circuit bytes without first understanding the real `kickmix` schema and your specific generator source. The next integration must connect **approved transformations** in your actual repository to a staged evaluation pipeline (`fast precheck → full official verifier → independent salts → measured score → evidence memory`). Replaying LLM-proposed code without audit is both unreliable and risky. `discover` provides hypotheses and test plans to drive that next phase, not a fictional complete automatic quantum optimizer.
