#!/usr/bin/env python3
"""DAVID QVC Discovery Engine: OpenRouter-driven, verifier-grounded research.

Builds falsifiable optimization hypotheses for Google's Verifiable Quantum Circuit
Compilation Kaggle contest. Does NOT execute model-generated code or claim a
verified improvement. Optional `verify` runs only an operator-configured local
verifier wrapper against an existing candidate artifact.

Usage:
  python qvc_discovery.py discover --task invsqrt --output runs/invsqrt
  python qvc_discovery.py discover --task all --output runs/round_01
  python qvc_discovery.py score --costs verified_costs.example.json
  python qvc_discovery.py verify --adapter verifier_adapter.example.json \
       --task invsqrt --candidate /absolute/path/to/invsqrt.kmb --execute
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any

from jsonschema import validate

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from openrouter import OpenRouter
except ImportError:
    OpenRouter = None

LOG = logging.getLogger("qvc")
TASKS = ("invsqrt", "dqi", "dfthcsos")
REFERENCE_COSTS = {
    "invsqrt": 2_076_774.23,
    "dqi": 24_439_463_583_672.93,
    "dfthcsos": 3_355_599_588.32,
}
# These reference ratios come from the attached 2026-11-09 project brief.
# They are planning baselines, NOT a freshly verified cost measurement.
BASELINE_RATIOS = {"invsqrt": 21.78, "dqi": 65.23, "dfthcsos": 11.20}
# Frontier roster (Max-Novelty tier). All verified available on OpenRouter.
# gpt-4 / deepseek / qwen are DROPPED: they produced placeholder proposals and/or
# failed strict json_schema, wasting attempts and credits.
OPUS = os.getenv("QVC_OPUS", "anthropic/claude-opus-4.8")
GPT55 = os.getenv("QVC_GPT55", "openai/gpt-5.5")
GEMINI = os.getenv("QVC_GEMINI", "google/gemini-3.1-pro-preview")
GROK = os.getenv("QVC_GROK", "x-ai/grok-4.7")
SONNET5 = os.getenv("QVC_SONNET5", "anthropic/claude-sonnet-5")

# Family tag per model, used to route the adversarial debate across DIFFERENT
# model families (diverse priors -> less derivative ideas, sharper pro/con).
FAMILY = {OPUS: "anthropic", GPT55: "openai", GEMINI: "google", GROK: "xai", SONNET5: "anthropic"}
# Grok-4.7 is excluded from active routing: it is a heavy reasoner that took
# 150-376s per call in testing (a latency killer for the debate loop). It stays
# available as a constant for opt-in via env, but default chains do not use it.
FRONTIER = [(OPUS, "anthropic"), (GPT55, "openai"), (GEMINI, "google"), (SONNET5, "anthropic")]

# Reasoning models (opus/grok/gemini) need time on ~8k-char prompts; the SDK default
# read timeout is too short and cancels them. 5 min per call, env-overridable.
_TIMEOUT_MS = int(os.getenv("QVC_TIMEOUT_MS", "300000"))


def _foreign(origin_model: str, exclude: set | None = None, n: int = 2) -> list[str]:
    """Up to n frontier models preferring DIFFERENT families; top up with same-family
    (never the origin model) so a debate chain is never empty."""
    exclude = exclude or set()
    fam = FAMILY.get(origin_model)
    cross, same = [], []
    for m, f in FRONTIER:
        if m == origin_model or m in exclude:
            continue
        (cross if f != fam else same).append(m)
    picked = cross[:n]
    if len(picked) < n:
        picked += [m for m in same if m not in picked][: n - len(picked)]
    return picked


def _robust(primary: list[str]) -> list[str]:
    """De-dup and guarantee a reliable last-resort (Opus) at the end of the chain."""
    out = list(dict.fromkeys(primary))
    if OPUS not in out:
        out.append(OPUS)
    return out


# First position is the intended independent reasoning role. Fallbacks are tried
# when a model is unavailable OR produces invalid/placeholder JSON content.
# Generation: each lens is led by a DIFFERENT frontier family for idea diversity.
CHAINS = {
    "analogy": [OPUS, GEMINI, GPT55],
    "formal": [GPT55, OPUS, GEMINI],
    "outsider": [GEMINI, OPUS, GPT55],
    "selection": [OPUS, GPT55, GEMINI],
}

TASK_CONTEXT = {
    "invsqrt": """Fusion: implement phase proportional to 1/sqrt(x) for every integer
x from 1 to 3,133,452 with required precision (approximately 2^-24 relative).
Official cost Q*C; C includes Toffoli gates, T/4 and applicable rotation
cost according to verifier. Starting public circuit around Q=62 and ratio 21.78.
Research candidate ideas: reversible arithmetic, lower ancilla live range,
measurement-based uncomputation, phase-polynomial re-synthesis, safe gate
cancellation and more efficient approximation with rigorous worst-case error.
Rejected paths: naive precision shortcuts at large x, previously tried P-A/P-B
redesigns. Start from an already correct baseline; do not reinvent it blindly.
Target ratio >= 22.5 initially; ultimate goal is contribution to total score 30.
""",
    "dqi": """Decoded Quantum Interferometry: reversible Reed-Solomon syndrome
decoder over a finite field; correct phase and clean ancillas are mandatory.
Official objective R(epsilon_plus)*Q^2*T, NOT just minimum Toffolis.
R incorporates decoder failure confidence from 102,400 official test samples.
Baseline ~891 qubits, ratio 65.23; probe register allocation, polynomial
arithmetic, field inversion and reversible pebble scheduling. The original
decoder generator is currently unavailable to this project; therefore ideas
must explicitly distinguish changes possible in a .kmb from those requiring
generator source or a licensed collaboration.
Rejected: degree truncation, overwriting syndrome qubits, hash/seed fishing.
A candidate once exhibited a phase error under a different salt; require >=5
independent salts before considering submission. Target 66 without generator,
>=75 with legitimate generator access, according to project plan.
""",
    "dfthcsos": """Quantum chemistry FeMoCo, 76 orbitals/113 electrons. Co-optimize tensor
factorization, Givens tree and ANGLE/QROM loading circuits. Official cost
lambda_eff*T_total*Q_total with lambda_eff = sqrt(E_gap*(2*Lambda-E_gap));
use verifier's cost, not manually approximated loader-only costs.
Constraints from project brief: error_1 <=20 mHa, error_2 <=20 mHa;
Lambda >49.0, E_gap >3.914898 Ha; <=128 qubits PER ANGLE circuit.
Promising shapes M=130,G=35, then (130,36) then (132,35). Known cliffs:
M<=128 increases qubit cost; G<=32 cannot satisfy compression errors.
Start from known valid factorization. Research rate-distortion/bit allocation,
hierarchical QROM, low-rank parameter search, optimal reversible table lookup.
Previously rejected: naive row reorder, gauge permutation, random initial
factorization producing 188-250mHa errors. Tentative target ratio >=13.5.
GPU needed for serious joint-search iterations. No validity without official
chemical constraints and the complete verifier.
""",
}

SYSTEM = """You are a scientific algorithm-research agent specializing in verifiable
quantum circuit compilation. Generate novel, TESTABLE optimization candidates,
not purported breakthroughs. All novelty is unverified until prior-art checks.
Treat the official verifier as the sole authority for correctness and cost.
Never optimize a hash, salt, test subset or benchmark implementation; never
suggest seed fishing, invalid ancilla states, wrong phases, hardcoded answers,
or violations of licenses. Avoid invented references, invented instruction
syntax, ungrounded performance promises and executable shell instructions.
Return only a JSON object with the requested schema; be concise but precise.
"""

LENSES = {
    "analogy": "Cross-domain analogies from compiler dataflow, reversible pebble games, coding theory, cache hierarchies, circuit retiming and information theory. Map variables and prove where the analogy fails.",
    "formal": "Mathematical reformulation, exact identities, error bounds, resource lower bounds and asymptotic vs constant factors. Prioritize invariants and proof obligations.",
    "outsider": "Cross-domain mechanism transfer from tensor compression, rate-distortion, control theory, register allocation, communication-avoiding algorithms and multiobjective optimization. Resist familiar minor tweaks.",
}


def obj(props: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": list(props),
            "additionalProperties": False}

S = {"type": "string"}
STRINGS = {"type": "array", "items": S}
ANALOGY = obj({"source_domain": S, "transfer_principle": S,
               "formal_mapping": S, "breakdown_conditions": S})
PROPOSAL = obj({
    "title": S, "novel_mechanism": S, "analogy": ANALOGY,
    "change_to_existing_baseline": S, "needed_source_assets": STRINGS,
    "mathematical_invariants": STRINGS, "predicted_resource_tradeoff": S,
    "implementation_plan": STRINGS, "cheap_precheck": S,
    "official_verifier_plan": S, "falsification_condition": S,
    "prior_art_queries": STRINGS, "known_failure_avoidance": S,
    "blocking_risks": STRINGS,
})
GENERATION = obj({"proposals": {"type": "array", "items": PROPOSAL}})
REVIEW = obj({
    "proposal_id": S, "thesis": S, "antithesis": S, "synthesis": S,
    "hardest_counterexample": S, "invariant_violation_risk": S,
    "decisive_experiment": S, "feasibility": {"type": "integer"},
    "potential_impact": {"type": "integer"}, "novelty_status": S,
})
REVIEW_SCHEMA = obj({"reviews": {"type": "array", "items": REVIEW}})
SELECTED = obj({"proposal_id": S, "rationale": S,
                "first_implementation_step": S, "success_threshold": S,
                "abort_condition": S, "required_assets": STRINGS})
SELECTION = obj({"research_strategy": S,
                 "priority_queue": {"type": "array", "items": SELECTED},
                 "shared_falsification_risks": STRINGS})


def extract_content(response: Any) -> str:
    choices = getattr(response, "choices", None)
    if not choices:
        raise ValueError("empty choices")
    content = choices[0].message.content
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "".join(x.get("text", "") if isinstance(x, dict)
                       else getattr(x, "text", "") for x in content).strip()
    raise ValueError("empty or unsupported completion content")


def json_object(raw: str) -> dict[str, Any]:
    if raw.startswith("```"):
        lines = raw.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            raw = "\n".join(lines[1:-1]).strip()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("model must return a JSON object")
    return data


def _acc_usage(acc: dict[str, Any], response: Any) -> None:
    """Accumulate token usage + USD cost from an OpenRouter response.

    OpenRouter reports ``usage.cost`` directly (verified); we also keep raw token
    counts so the UI can show them even if cost is momentarily absent. Every attempt
    (including failed fallbacks) consumes tokens, so costs are summed across attempts.
    """
    u = getattr(response, "usage", None)
    if u is None:
        return

    def g(name: str, default: float = 0.0) -> float:
        v = u.get(name) if isinstance(u, dict) else getattr(u, name, None)
        return v if isinstance(v, (int, float)) and not isinstance(v, bool) else default

    pt, ct = g("prompt_tokens"), g("completion_tokens")
    tt = g("total_tokens") or (pt + ct)
    acc["prompt_tokens"] += int(pt)
    acc["completion_tokens"] += int(ct)
    acc["total_tokens"] += int(tt)
    acc["cost"] += float(g("cost"))


def call_models(key: str, chain: list[str], prompt: str, schema: dict[str, Any],
                schema_name: str, check: Any, retries: int = 2,
                temperature: float = 0.6) -> dict[str, Any]:
    """Use official SDK; validate response locally, also with JSON-only mode fallback."""
    if OpenRouter is None:
        raise RuntimeError("Missing OpenRouter SDK. Install: pip install openrouter")
    failures = []
    usage_acc = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost": 0.0}
    for model in dict.fromkeys(chain):
        # Frontier models enforce strict json_schema; json_object is the fallback mode.
        modes = ["json_schema", "json_object"]
        for mode in modes:
            fmt: dict[str, Any] = ({"type": "json_schema", "json_schema":
                                   {"name": schema_name, "strict": True, "schema": schema}}
                                   if mode == "json_schema" else {"type": "json_object"})
            for attempt in range(1, retries + 1):
                try:
                    LOG.info("OpenRouter model=%s format=%s attempt=%s", model, mode, attempt)
                    with OpenRouter(api_key=key, timeout_ms=_TIMEOUT_MS) as client:
                        response = client.chat.send(
                            model=model, stream=False,
                            messages=[{"role": "system", "content": SYSTEM},
                                      {"role": "user", "content": prompt}],
                            response_format=fmt, temperature=temperature,
                            max_tokens=8000,
                        )
                    _acc_usage(usage_acc, response)
                    data = json_object(extract_content(response))
                    validate(instance=data, schema=schema)
                    check(data)
                    return {"data": data, "requested_model": model,
                            "served_model": getattr(response, "model", model),
                            "response_mode": mode, "failures": failures,
                            "usage": usage_acc}
                except (KeyboardInterrupt, SystemExit):
                    raise
                except Exception as exc:
                    status = getattr(exc, "status_code", None)
                    detail = str(exc).replace(key, "[REDACTED]")[:200]
                    failures.append(f"{model} ({mode}, attempt {attempt}): {type(exc).__name__}: {detail}")
                    LOG.warning("%s", failures[-1])
                    if status in (401, 402, 403):
                        raise RuntimeError(f"OpenRouter credentials/credits error (HTTP {status})") from exc
                    if attempt < retries:
                        time.sleep(min(2**(attempt - 1), 4))
    raise RuntimeError("All model attempts failed: " + " / ".join(failures[-8:]))


def generation_prompt(task: str, role: str, memory: str, brief: str) -> str:
    return f"""COMPETITION: Google Verifiable Quantum Circuit Compilation.
TASK: {task}
REQUIRED CONSTRAINTS, BASELINE AND REJECTED IDEAS:
{TASK_CONTEXT[task]}

CROSS-DOMAIN RESEARCH LENS:
{LENSES[role]}

PREVIOUS LOCAL EXPERIMENTS AND EXTERNAL MEMORY (may be incomplete):
{memory[:11000] or 'Not supplied.'}

ADDITIONAL COMPETITION BRIEF (may contain unverified local estimates):
{brief[:12000]}

Invent exactly ONE substantially distinct algorithmic optimization idea for
this task. Do NOT merely remix a gate or claim an untestable benefit.
Explicitly include: source-domain analogy; formal mapping of source to quantum
reversible computation; how mapping breaks; invariants; the smallest practical
modification to a KNOWN VALID circuit/generator; required source assets;
resource tradeoff Q vs T vs lambda vs error; falsifiable experiment with
an official-verifier plan. Prefer a narrow hypothesis with high info gain.
No hypothetical benchmark results can be described as verified. JSON only.
"""


def review_prompt(task: str, proposal: dict[str, Any], memory: str) -> str:
    return f"""INDEPENDENT DIALECTICAL REVIEW. Competition task: {task}.
Official constraints and known rejected paths:
{TASK_CONTEXT[task]}
Evidence to consider: {memory[:6000] or 'none supplied'}
Proposed experiment:
{json.dumps(proposal, ensure_ascii=False)}

Return exactly one review of proposal_id = {proposal['id']}.
THESIS: best technical argument that this exact algorithmic change can help.
ANTITHESIS: most damaging mathematical counterexample, literature overlap,
quantum phase/ancilla bug, resource tradeoff or missing generator/source.
SYNTHESIS: a narrower proposal requiring measurable evidence, NOT a vote.
State decisive test using OFFICIAL verifier, including robust salts for dqi.
Give feasibility and impact (1..5) as ESTIMATES, never claimed measurements.
Novelty status must be 'UNVERIFIED'. Return JSON only.
"""


def select_prompt(proposals: list[dict[str, Any]], reviews: list[dict[str, Any]],
                  slots: int) -> str:
    slim = [{"id": p["id"], "task": p["task"], "title": p["title"],
             "mechanism": p["novel_mechanism"], "tradeoff": p["predicted_resource_tradeoff"],
             "implementation_plan": p["implementation_plan"],
             "survived_debate": p.get("survives"), "debate_scores": p.get("debate_scores")}
            for p in proposals]
    return f"""SELECT A COMPETITION RESEARCH BACKLOG, NOT THE MOST PERSUASIVE STORY.
Goal: Kaggle TOP-10 (overall geometric score ~24+; planning baseline ~25.15, stretch 30).
Only VERIFIED circuits score. Prioritize, in order: (1) ideas that SURVIVED the adversarial
debate with high debate_scores, (2) a cheap decisive precheck before any circuit work,
(3) credible source/asset access, (4) real official-verifier objective function.
Prefer candidates that survived the debate; pick a non-survivor only if no survivor exists
for that task. Do not misreport unknown chemistry scores, low-salt DQI tests or self-reported
novelty as verification. Avoid previously rejected methods.
CANDIDATES:
{json.dumps(slim, ensure_ascii=False)}
REVIEWS:
{json.dumps(reviews, ensure_ascii=False)}

Choose exactly {slots} different IDs, ordered by expected top-10 value. For each specify the
first executable implementation step, a measurable success threshold from the OFFICIAL verifier,
minimum quality gates (especially salts), and an objective abort criterion. Do NOT produce
executable code or shell commands. Include cross-task product-score impact. JSON only.
"""


_PLACEHOLDER_TOKENS = {
    "string", "step 1", "step 2", "step 3", "invariant 1", "invariant 2",
    "domain name", "optimization candidate title", "...", "concise description of the novel mechanism (1 sentence)",
    "concise description of the core idea", "mathematical mapping to reversible computation",
    "formal mapping to reversible gates", "when the analogy breaks",
    "conditions under which the analogy breaks", "if condition x, then candidate fails",
    "list invariants that must hold", "q: +Δq, t: +Δt, λ: +Δλ, error: +Δerror",
    "q: ±Δq, t: ±Δt, r(ε⁺): ±Δr", "condition that would falsify the idea",
}


def _looks_placeholder(value: Any) -> bool:
    """True for degenerate/echoed schema content (e.g. 'string', 'Step 1')."""
    if not isinstance(value, str):
        return True
    t = value.strip().lower()
    if len(t) < 12:
        return True
    if t in _PLACEHOLDER_TOKENS:
        return True
    return t.startswith(("step ", "invariant ", "concise description"))


def validate_generation(data: dict[str, Any]) -> None:
    if len(data["proposals"]) != 1:
        raise ValueError("Expected exactly one proposal per role and task")
    p = data["proposals"][0]
    if _looks_placeholder(p.get("title")) or _looks_placeholder(p.get("novel_mechanism")):
        raise ValueError("Proposal is a placeholder (title/novel_mechanism degenerate)")
    if not p["implementation_plan"] or not p["mathematical_invariants"]:
        raise ValueError("Proposal lacks implementation details or invariants")
    if any(_looks_placeholder(x) for x in list(p["implementation_plan"])[:2]):
        raise ValueError("implementation_plan is placeholder content")


def validate_review(data: dict[str, Any], candidate_id: str) -> None:
    if len(data["reviews"]) != 1 or data["reviews"][0]["proposal_id"] != candidate_id:
        raise ValueError(f"Review must cover only {candidate_id}")
    r = data["reviews"][0]
    if r["novelty_status"] != "UNVERIFIED":
        raise ValueError("Novelty must remain UNVERIFIED")
    if not all(1 <= r[k] <= 5 for k in ("feasibility", "potential_impact")):
        raise ValueError("Review ratings must be 1..5")


def validate_selection(data: dict[str, Any], ids: set[str], slots: int) -> None:
    selected = [r["proposal_id"] for r in data["priority_queue"]]
    if len(selected) != slots or len(set(selected)) != slots or not set(selected) <= ids:
        raise ValueError("Selection IDs invalid, duplicate or wrong count")


# --------------------------------------------------------------------------- #
# Adversarial debate (pro / con / judge) -> sharpened, verifiable top-10 ideas #
# --------------------------------------------------------------------------- #
PRO = obj({"proposal_id": S, "steelman": S, "best_refinement": S, "expected_delta": S})
PRO_SCHEMA = obj({"pro": PRO})
CON = obj({"proposal_id": S, "attacks": STRINGS, "kill_shot": S, "salvageable_alternative": S})
CON_SCHEMA = obj({"con": CON})
JUDGE = obj({"proposal_id": S, "feasibility": {"type": "integer"}, "impact": {"type": "integer"},
             "novelty": {"type": "integer"}, "survives": {"type": "boolean"},
             "verdict": S, "sharpened": PROPOSAL})
JUDGE_SCHEMA = obj({"judgement": JUDGE})


def _pro_prompt(p: dict[str, Any], memory: str) -> str:
    return f"""ADVERSARIAL DEBATE — PRO SIDE (steelman). Competition task: {p['task']}.
Official constraints / known rejected paths:
{TASK_CONTEXT[p['task']]}
Local evidence (may be incomplete): {memory[:4000] or 'none supplied'}
CANDIDATE IDEA {p['id']}:
{json.dumps(p, ensure_ascii=False)}

Argue the STRONGEST case that this idea is a credible path to a HIGHER official
verifier ratio on THIS benchmark, and therefore lifts the overall geometric score
toward Kaggle top-10. Be concrete about the mechanism and the expected Q/T/error
delta. Then give the single highest-value REFINEMENT that makes it more likely to
VERIFY (cheaper precheck, tighter error bound, smaller circuit change). Do NOT
invent verified results. JSON only.
"""


def _con_prompt(p: dict[str, Any], pro: dict[str, Any], memory: str) -> str:
    return f"""ADVERSARIAL DEBATE — CON SIDE (hostile attack). Competition task: {p['task']}.
Official constraints / known rejected paths:
{TASK_CONTEXT[p['task']]}
CANDIDATE IDEA {p['id']}:
{json.dumps(p, ensure_ascii=False)}
PRO steelman:
{json.dumps(pro, ensure_ascii=False)}

Attack it like a reviewer who has seen many failed submissions. Find the MOST LIKELY
fatal flaw for reaching top-10: (a) already prior art / present in the baseline;
(b) violates the official error budget or tolerance; (c) no real headroom (gain too
small to move the geometric score); (d) infeasible without generator source or assets
we do not have; (e) breaks a kickmix constraint (ancilla cleanliness, named registers,
Z_POW rules); (f) verifier-rejection risk (salt-dependent phase errors). Name the
single KILL SHOT. If the core is still salvageable, propose a sharper alternative;
otherwise set salvageable_alternative to 'none'. Be specific and falsifiable. JSON only.
"""


def _judge_prompt(p: dict[str, Any], pro: dict[str, Any], con: dict[str, Any], memory: str) -> str:
    return f"""ADVERSARIAL DEBATE — JUDGE (synthesis). Competition task: {p['task']}.
Goal: a VERIFIABLE improvement that helps reach Kaggle TOP-10 (overall geometric
score ~24+), within ~10 weeks, using only kickmix + the official verifier.
CANDIDATE IDEA {p['id']}:
{json.dumps(p, ensure_ascii=False)}
PRO: {json.dumps(pro, ensure_ascii=False)}
CON: {json.dumps(con, ensure_ascii=False)}

Weigh both sides. Score feasibility / impact / novelty (each integer 1..5) for THIS
idea as a top-10 contribution. Set survives=true only if a credible, verifiable path
to a real ratio gain exists. Write a crisp verdict explaining the top-10 call. Then
produce the SHARPENED proposal: incorporate the best refinement, address the kill shot
if salvageable, keep it HYPOTHESIS ONLY (no fabricated verification). The sharpened
object must be a complete proposal with concrete, non-placeholder fields. JSON only.
"""


def validate_pro(data: dict[str, Any], pid: str) -> None:
    p = data["pro"]
    if p["proposal_id"] != pid or _looks_placeholder(p.get("steelman")):
        raise ValueError(f"PRO must steelman {pid} with concrete content")


def validate_con(data: dict[str, Any], pid: str) -> None:
    c = data["con"]
    if c["proposal_id"] != pid or not c.get("attacks") or _looks_placeholder(c.get("kill_shot")):
        raise ValueError(f"CON must attack {pid} with a concrete kill shot")


def validate_judge(data: dict[str, Any], pid: str) -> None:
    j = data["judgement"]
    if j["proposal_id"] != pid:
        raise ValueError(f"JUDGE must cover {pid}")
    if not all(1 <= j[k] <= 5 for k in ("feasibility", "impact", "novelty")):
        raise ValueError("Judge scores must be 1..5")
    if type(j.get("survives")) is not bool:
        raise ValueError("Judge survives must be boolean")
    sh = j.get("sharpened", {})
    if _looks_placeholder(sh.get("title")) or _looks_placeholder(sh.get("novel_mechanism")) \
            or not sh.get("implementation_plan") or not sh.get("mathematical_invariants"):
        raise ValueError("Judge sharpened proposal is incomplete/placeholder")


def discover(api_key: str, tasks: list[str], memory: str, brief: str,
             slots: int, retries: int, workers: int, debate: bool = True) -> dict[str, Any]:
    specs = [(task, role) for task in tasks for role in LENSES]
    results: dict[tuple[str, str], dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(call_models, api_key, CHAINS[role],
                               generation_prompt(task, role, memory, brief),
                               GENERATION, "qvc_idea", validate_generation, retries, 0.7):
                   (task, role) for task, role in specs}
        for future in as_completed(futures):
            results[futures[future]] = future.result()

    proposals = []
    for task, role in specs:
        result = results[(task, role)]
        proposal = {"id": f"QVC-{len(proposals)+1:02d}", "task": task,
                    "origin_role": role, "origin_model": result["served_model"],
                    "verification_status": "HYPOTHESIS_ONLY",
                    **result["data"]["proposals"][0]}
        proposals.append(proposal)
    LOG.info("Generated %d ideas; adversarial debate begins", len(proposals))

    debates: dict[str, dict[str, Any]] = {}
    if debate:
        def _debate_one(p: dict[str, Any]) -> tuple[str, dict[str, Any]]:
            pid, origin = p["id"], p["origin_model"]
            pro_primary = _foreign(origin, n=2)
            con_primary = _foreign(origin, exclude=set(pro_primary), n=2)
            pro_chain = _robust(pro_primary)
            con_chain = _robust(con_primary)
            judge_chain = _robust([GPT55, GEMINI]) if FAMILY.get(origin) == "anthropic" else [OPUS, GPT55]
            pro_r = call_models(api_key, pro_chain, _pro_prompt(p, memory), PRO_SCHEMA,
                                "qvc_debate_pro", lambda o, pid=pid: validate_pro(o, pid), retries, 0.4)
            con_r = call_models(api_key, con_chain, _con_prompt(p, pro_r["data"]["pro"], memory), CON_SCHEMA,
                                "qvc_debate_con", lambda o, pid=pid: validate_con(o, pid), retries, 0.4)
            judge_r = call_models(api_key, judge_chain,
                                  _judge_prompt(p, pro_r["data"]["pro"], con_r["data"]["con"], memory),
                                  JUDGE_SCHEMA, "qvc_debate_judge",
                                  lambda o, pid=pid: validate_judge(o, pid), retries, 0.3)
            return pid, {"pro": pro_r["data"]["pro"], "con": con_r["data"]["con"],
                         "judge": judge_r["data"]["judgement"],
                         "models": {"pro": pro_r["served_model"], "con": con_r["served_model"],
                                    "judge": judge_r["served_model"]}}

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_debate_one, p): p["id"] for p in proposals}
            for future in as_completed(futures):
                pid, d = future.result()
                debates[pid] = d

    # Sharpen surviving ideas + derive back-compat reviews from the debate.
    final_proposals: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    for p in proposals:
        d = debates.get(p["id"])
        if not d:
            final_proposals.append(p)
            continue
        j, sh = d["judge"], (d["judge"].get("sharpened") or {})
        sharpened = {**p, **{k: v for k, v in sh.items() if v not in (None, "", [])},
                     "survives": j.get("survives", False),
                     "debate_scores": {"feasibility": j.get("feasibility"),
                                       "impact": j.get("impact"), "novelty": j.get("novelty")}}
        final_proposals.append(sharpened)
        reviews.append({
            "proposal_id": p["id"], "thesis": d["pro"].get("steelman", ""),
            "antithesis": d["con"].get("kill_shot", ""), "synthesis": j.get("verdict", ""),
            "hardest_counterexample": "; ".join(d["con"].get("attacks", [])),
            "invariant_violation_risk": d["con"].get("salvageable_alternative", ""),
            "decisive_experiment": d["pro"].get("best_refinement", ""),
            "feasibility": j.get("feasibility", 3), "potential_impact": j.get("impact", 3),
            "novelty_status": "UNVERIFIED"})

    slots = min(slots, len(final_proposals))
    synthesis = call_models(api_key, CHAINS["selection"],
                            select_prompt(final_proposals, reviews, slots),
                            SELECTION, "qvc_selection",
                            lambda x: validate_selection(x, {p["id"] for p in final_proposals}, slots),
                            retries, 0.2)
    return {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "contest": "google-verifiable-quantum-circuit-compilation",
        "baseline_ratios_from_local_brief": BASELINE_RATIOS,
        "baseline_score_approx": score_ratios(BASELINE_RATIOS),
        "target_score": 30,
        "top10_target": 24.0,
        "novelty_status": "UNVERIFIED",
        "experiment_status": "NO CANDIDATE BUILT OR VERIFIED BY DISCOVER COMMAND",
        "scope": tasks, "proposals": final_proposals, "reviews": reviews,
        "debates": debates,
        "selection": synthesis["data"],
        "generation_provenance": {f"{k[0]}:{k[1]}":
                                  {"model": v["served_model"], "fallback_failures": v["failures"]}
                                  for k, v in results.items()},
        "debate_provenance": {pid: d["models"] for pid, d in debates.items()},
        "synthesis_model": synthesis["served_model"],
    }


def score_ratios(ratios: dict[str, float]) -> float:
    if set(ratios) != set(TASKS) or any(v <= 0 for v in ratios.values()):
        raise ValueError("Ratios must contain all three tasks with positive values")
    prod = 1.0
    for k in TASKS:
        prod *= float(ratios[k])
    return prod**(1 / 3)


def score_from_verified_costs(payload: dict[str, Any]) -> dict[str, Any]:
    """Only costs from an explicitly official, PASS verifier manifest."""
    ratios = {}
    for task in TASKS:
        record = payload.get(task, {})
        if record.get("source") != "official_verifier" or record.get("passed") is not True:
            raise ValueError(f"{task}: require source=official_verifier and passed=true")
        cost = record.get("cost")
        if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not (0 < cost < float("inf")):
            raise ValueError(f"{task}: official verifier cost must be finite and > 0")
        if task == "dqi":
            if int(record.get("shots", -1)) != 102400:
                raise ValueError("dqi: official verification needs 102400 samples")
            if len(set(record.get("independent_salts", []))) < 5:
                raise ValueError("dqi: at least 5 independent salt checks required by project policy")
        ratios[task] = REFERENCE_COSTS[task] / cost
    return {"ratios": ratios, "score": score_ratios(ratios),
            "target": 30, "above_target": score_ratios(ratios) >= 30}


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def report(data: dict[str, Any]) -> str:
    by_id = {p["id"]: p for p in data["proposals"]}
    critiques = {r["proposal_id"]: r for r in data["reviews"]}
    debates = data.get("debates", {}) or {}
    t10 = data.get("top10_target", 24.0)
    lines = ["# DAVID QVC Scientific Discovery", "",
             f"Created: {data['created_utc']}", "",
             f"Planning baseline: **{data['baseline_score_approx']:.4f}**; Top-10 bar **~{t10:.0f}**, stretch **{data['target_score']:.0f}**.",
             "", "**No ideas have been compiled or officially verified.**", "",
             "## Strategy", data["selection"]["research_strategy"], "",
             "## Priority backlog", ""]
    for i, entry in enumerate(data["selection"]["priority_queue"], 1):
        p = by_id.get(entry["proposal_id"], {})
        r = critiques.get(entry["proposal_id"], {})
        debates.get(entry["proposal_id"])  # presence check; transcript shown via reviews mapping
        an = p.get("analogy") or {}
        sc = p.get("debate_scores") or {}
        lines += [f"### {i}. {p.get('id')} [{p.get('task')}]: {p.get('title')}", "",
                  f"- Origin: {p.get('origin_model')} ({p.get('origin_role')})",
                  f"- Survived debate: {'YES' if p.get('survives') else 'no'} · feas/impact/novelty = {sc.get('feasibility')}/{sc.get('impact')}/{sc.get('novelty')}",
                  f"- Idea: {p.get('novel_mechanism')}",
                  f"- Cross-domain transfer: {an.get('source_domain','')} — {an.get('formal_mapping','')}",
                  f"- Breakdown conditions: {an.get('breakdown_conditions','')}",
                  f"- PRO (steelman): {r.get('thesis','')}",
                  f"- CON (kill shot): {r.get('antithesis','')}",
                  f"- JUDGE (verdict): {r.get('synthesis','')}",
                  f"- First step: {entry['first_implementation_step']}",
                  f"- Official success test: {entry['success_threshold']}",
                  f"- Abort: {entry['abort_condition']}",
                  f"- Required assets: {', '.join(entry['required_assets'])}",
                  "- Status: **HYPOTHESIS ONLY**", ""]
    lines += ["## Shared falsification risks", ""]
    lines += [f"- {x}" for x in data["selection"]["shared_falsification_risks"]]
    return "\n".join(lines) + "\n"


def hash_artifact(path: Path) -> str:
    """Content hash including nested chemistry angle circuits and npz."""
    if not path.exists():
        raise FileNotFoundError(path)
    sha = hashlib.sha256()
    root = path.resolve()
    files = sorted(root.rglob("*")) if root.is_dir() else [root]
    regular_files = [f for f in files if f.is_file() and not f.is_symlink()]
    if not regular_files:
        raise ValueError("Candidate artifact has no regular files")
    for f in regular_files:
        sha.update((str(f.relative_to(root)) if root.is_dir() else f.name).encode())
        with f.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024*1024), b""):
                sha.update(chunk)
    return sha.hexdigest()


def verify_candidate(adapter: dict[str, Any], task: str, artifact: Path,
                     out: Path, execute: bool, max_workers: int = 2) -> dict[str, Any]:
    """Execute ONLY a human-supplied trusted verifier command, never LLM code.

    The configured wrapper must emit one JSON object to stdout:
    {"source":"official_verifier","passed":true,"cost":123.4,
     "shots":102400,"salt":"saltA"}.  The wrapper, not this module,
    must actually invoke Google's official verifier and correctly check it.
    """
    config = adapter.get("tasks", {}).get(task)
    if not isinstance(config, dict):
        raise ValueError(f"Missing trusted adapter.tasks.{task} configuration")
    cmd_template = config.get("command")
    if not isinstance(cmd_template, list) or not cmd_template or not all(isinstance(x, str) for x in cmd_template):
        raise ValueError("adapter command must be an explicit argv list")
    salts = config.get("salts", [])
    if not isinstance(salts, list) or not all(isinstance(x, str) and x for x in salts):
        raise ValueError("adapter salts must be a list of non-empty strings")
    if task == "dqi" and len(set(salts)) < 5:
        raise ValueError("dqi requires >= 5 independent salts in adapter")
    if not salts:
        salts = ["default"]
    if max_workers < 1 or max_workers > 16:
        raise ValueError("max_workers must be 1..16")
    allowed_tokens = {"{candidate}", "{task}", "{salt}"}
    def expand(salt: str) -> list[str]:
        argv = []
        for item in cmd_template:
            fragments = re.findall(r"\{[^{}]+\}", item)
            if any(frag not in allowed_tokens for frag in fragments):
                raise ValueError("Unknown placeholder in trusted command")
            argv.append(item.replace("{candidate}", str(artifact.resolve()))
                        .replace("{task}", task).replace("{salt}", salt))
        return argv
    commands = [expand(s) for s in salts]
    base = {"task": task, "candidate": str(artifact.resolve()),
            "sha256": hash_artifact(artifact), "command_preview": commands,
            "source": "operator_supplied_adapter", "executed": execute}
    if not execute:
        return {**base, "status": "DRY_RUN_ONLY"}
    cache_path = out / "verifier_cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    work_env = os.environ.copy()
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        work_env[key] = "1"
    timeout = int(config.get("timeout_seconds", 3600))
    if timeout < 10 or timeout > 86400:
        raise ValueError("timeout_seconds must be within 10..86400")

    def one(salt: str, argv: list[str]) -> dict[str, Any]:
        cache_key = hashlib.sha256(json.dumps([base["sha256"], argv, timeout]).encode()).hexdigest()
        if cache_key in cache:
            return {**cache[cache_key], "cached": True}
        try:
            result = subprocess.run(argv, cwd=config.get("cwd", None),
                                    capture_output=True, text=True, timeout=timeout,
                                    env=work_env, shell=False, check=False)
            if result.returncode != 0:
                value = {"passed": False, "salt": salt, "status": "PROCESS_FAILED",
                         "exit_code": result.returncode, "stderr_tail": result.stderr[-1000:]}
            else:
                payload = json_object(result.stdout.strip())
                if payload.get("source") != "official_verifier":
                    raise ValueError("Trusted wrapper did not assert official_verifier source")
                if type(payload.get("passed")) is not bool:
                    raise ValueError("Trusted wrapper must supply a boolean passed field")
                if payload.get("salt") != salt:
                    raise ValueError("Salt mismatch between request and wrapper output")
                if task == "dqi" and int(payload.get("shots", -1)) != 102400:
                    raise ValueError("DQI wrapper did not run 102400 shots")
                cost = payload.get("cost")
                if payload["passed"] and (isinstance(cost, bool) or not isinstance(cost, (int,float)) or not 0 < cost < float("inf")):
                    raise ValueError("Official cost must be finite and > 0")
                value = {"passed": payload["passed"], "salt": salt,
                         "cost": cost, "status": "PASS" if payload["passed"] else "FAIL",
                         "source": "official_verifier", "shots": payload.get("shots")}
                # Preserve extra adapter fields (error, precheck, cost_is_estimate, ...)
                # so failures are debuggable; the contract above is unchanged.
                value.update({k: v for k, v in payload.items() if k not in value})
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as exc:
            value = {"passed": False, "salt": salt, "status": "ADAPTER_ERROR",
                     "error": f"{type(exc).__name__}: {exc}"[:500]}
        return {**value, "cache_key": cache_key, "cached": False}

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(one, salt, cmd) for salt, cmd in zip(salts, commands)]
        runs = [f.result() for f in futures]
    for r in runs:
        if r["status"] == "PASS":
            cache[r["cache_key"]] = {k: v for k, v in r.items() if k != "cached"}
    write_json(cache_path, cache)
    passed = all(x.get("passed") is True for x in runs)
    costs = [x.get("cost") for x in runs if x.get("passed")]
    # Under salt-dependent sampling, identical costs are not guaranteed.
    # Never synthesize a single official cost unless all runs agree.
    same_cost = len(costs) == len(runs) and len(set(costs)) == 1
    return {**base, "status": "ALL_CHECKS_PASS" if passed else "NOT_VERIFIED",
            "runs": runs, "all_passed": passed,
            "official_cost_if_identical_across_salts": costs[0] if passed and same_cost else None,
            "warning": "Only the actual official verifier establishes validity. Confirm the trusted wrapper is correct."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    d = sub.add_parser("discover", help="OpenRouter hypothesis generation and dialectical review")
    d.add_argument("--task", choices=[*TASKS, "all"], default="all")
    d.add_argument("--brief", type=Path, default=Path(__file__).with_name("competition_brief.md"))
    d.add_argument("--memory", type=Path, help="Optional local negative-results / failed-ideas memo")
    d.add_argument("--top", type=int, default=3)
    d.add_argument("--retries", type=int, default=2)
    d.add_argument("--workers", type=int, default=3)
    d.add_argument("--no-debate", action="store_true", help="Skip the adversarial debate (single-pass, cheaper)")
    d.add_argument("--output", type=Path, default=Path("runs/round_01"))
    s = sub.add_parser("score", help="Compute score from manually imported verified costs")
    s.add_argument("--costs", type=Path, required=True)
    s.add_argument("--output", type=Path)
    v = sub.add_parser("verify", help="Run a trusted local official verifier wrapper")
    v.add_argument("--adapter", type=Path, required=True)
    v.add_argument("--task", choices=TASKS, required=True)
    v.add_argument("--candidate", type=Path, required=True)
    v.add_argument("--output", type=Path, default=Path("runs/verifications"))
    v.add_argument("--workers", type=int, default=2)
    v.add_argument("--execute", action="store_true", help="Without this: print safe command preview only")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(message)s")
    try:
        if args.command == "discover":
            if not 1 <= args.top <= 9 or not 1 <= args.workers <= 9 or not 1 <= args.retries <= 4:
                parser.error("top 1..9, workers 1..9, retries 1..4")
            key = os.getenv("OPENROUTER_API_KEY", "").strip()
            if not key:
                parser.error("OPENROUTER_API_KEY missing; see .env.example")
            if OpenRouter is None:
                parser.error("Official SDK missing: pip install -r requirements.txt")
            tasks = list(TASKS) if args.task == "all" else [args.task]
            memory = args.memory.read_text(encoding="utf-8") if args.memory else ""
            brief = args.brief.read_text(encoding="utf-8") if args.brief.exists() else ""
            data = discover(key, tasks, memory, brief, args.top, args.retries, args.workers, debate=not args.no_debate)
            write_json(args.output / "research.json", data)
            (args.output / "report.md").write_text(report(data), encoding="utf-8")
            print(f"Saved {len(data['proposals'])} ideas, {len(data['reviews'])} independent critiques to {args.output}")
        elif args.command == "score":
            costs = json.loads(args.costs.read_text(encoding="utf-8"))
            value = score_from_verified_costs(costs)
            print(json.dumps(value, ensure_ascii=False, indent=2))
            if args.output:
                write_json(args.output, value)
        elif args.command == "verify":
            adapter = json.loads(args.adapter.read_text(encoding="utf-8"))
            result = verify_candidate(adapter, args.task, args.candidate,
                                      args.output, args.execute, args.workers)
            write_json(args.output / "verification.json", result)
            print(json.dumps({k: v for k, v in result.items() if k != "command_preview"},
                             ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        key = os.getenv("OPENROUTER_API_KEY", "")
        LOG.error("%s", str(exc).replace(key, "[REDACTED]") if key else str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
