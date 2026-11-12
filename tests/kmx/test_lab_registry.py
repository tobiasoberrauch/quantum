"""Labor: Protokoll, Statusableitung (Modelltext kann nicht befördern), Bereinigung,
Altbefunde und Spec (kmx.lab.claims, kmx.lab.registry, kmx.lab.seeds, kmx.lab.spec)."""

import json
import os
import shlex
import sys
import tempfile

import kmx.cost
import kmx.layout
import kmx.score
from kmx.lab.claims import (
    EV_CLAIM,
    EV_EVALUATION,
    EV_HISTORICAL,
    EXPERIMENTAL,
    HYPOTHESIS,
    JUDGE_EVALUATOR,
    REFUTED,
    SEED_EVALUATOR,
    STATUSES,
    VERIFIED,
    safe_id,
    safe_id_list,
    safe_text,
)
from kmx.lab.official import verifier_pin
from kmx.lab.registry import LabError, Registry
from kmx.lab.seeds import SEED_SOURCE, SEEDS
from kmx.lab.spec import load_spec, spec_text
from kmx.lab.teams import parse_proposal
from tests.kmx.helpers import raises
from tests.kmx.lab_helpers import GOOD_TEXT, make_lab

# gepinnter "Verifier" der Tests: der Interpreter selbst (eine echte Datei)
PIN_CMD = shlex.quote(sys.executable) + " {out}"


def _official(sha, exit_code=0, verdict="PASS"):
    return {
        "verifier_status": verdict,
        "command": f"verify candidates/{sha}.kmx",
        "tool_sha256": verifier_pin(PIN_CMD),
        "exit_code": exit_code,
        "output_sha256": "0" * 64,
        "candidate_sha256": sha,
        "python_version": "3.13",
        "kmx_version": "5",
    }


def _evaluation(cid, sha, passed=True, official=None, evaluator=JUDGE_EVALUATOR):
    return {
        "kind": EV_EVALUATION,
        "evaluator": evaluator,
        "claim_id": cid,
        "eval_id": "e-1",
        "candidate_sha256": sha,
        "passed": passed,
        "official": official,
        "score": 10.0,
    }


def test_statuses_are_exactly_the_four():
    assert STATUSES == ("hypothesis", "experimental", "verified", "refuted")


def test_init_seeds_six_known_results_with_honest_status():
    with tempfile.TemporaryDirectory() as d:
        reg, _ = make_lab(d)
        claims = reg.claims()
        seeds = {s.claim_id: s for s in SEEDS}
        assert len(seeds) == 6 and set(seeds) <= set(claims)
        for cid, s in seeds.items():
            assert claims[cid].status == s.status in (EXPERIMENTAL, REFUTED)
            assert SEED_SOURCE in claims[cid].sources
        assert claims["seed-magnitude-shortcut"].status == REFUTED
        assert claims["seed-window-llm-rewrites"].status == EXPERIMENTAL
        # Regression: widerlegte Altbefunde sind die widerlegte POSITIVE Hypothese
        # (nicht "X is dead" mit Status refuted = doppelte Verneinung)
        for s in SEEDS:
            if s.status == REFUTED:
                text = s.claim.lower()
                assert "dead" not in text and "no-go" not in text, s.claim_id
                assert any(a.startswith("refuted by:") for a in s.assumptions)
        assert raises(LabError, Registry.create, reg.lab_dir, d + "/base.kmx", None)


def test_llm_status_field_cannot_promote_a_claim():
    with tempfile.TemporaryDirectory() as d:
        reg, _ = make_lab(d)
        obj = {
            "status": "verified",
            "claims": [{"claim": "x^-1/2 is free", "status": "verified"}],
        }
        p = parse_proposal("numerical", obj, reg.claim_ids())
        assert len(p.problems) == 2 and "Status" in p.problems[0]
        cid = reg.add_hypothesis(p.claims[0].claim, "team:numerical")
        reg.add_note(cid, "status: verified, formally proved!", "team:numerical")
        assert reg.claims()[cid].status == HYPOTHESIS
        # selbst ein eingeschmuggeltes Statusfeld im Ereignis zaehlt nicht
        reg.append({"kind": EV_CLAIM, "claim_id": "c-forged", "claim": "x"})
        reg.append({"kind": EV_CLAIM, "claim_id": "c-forged", "status": VERIFIED})
        reg.append(
            {
                "kind": EV_HISTORICAL,
                "claim_id": "c-forged",
                "status": VERIFIED,
                "evaluator": SEED_EVALUATOR,
            }
        )
        assert reg.claims()["c-forged"].status == HYPOTHESIS


def test_status_is_derived_from_judge_events_only():
    with tempfile.TemporaryDirectory() as d:
        reg, _ = make_lab(d, PIN_CMD)
        sha, _ = reg.store_candidate(GOOD_TEXT.encode(), ".kmx")
        cid = reg.add_hypothesis("candidate", "team:phase")

        def status():
            return reg.claims()[cid].status

        reg.append(_evaluation(cid, sha, evaluator="team:phase"))
        assert status() == HYPOTHESIS  # falscher Schreiber zaehlt nicht
        reg.append(_evaluation(cid, sha))
        assert status() == EXPERIMENTAL and reg.claims()[cid].best_score == 10.0
        incomplete = dict(_official(sha), output_sha256="")
        reg.append(_evaluation(cid, sha, official=incomplete))
        assert status() == EXPERIMENTAL
        reg.append(_evaluation(cid, sha, official=_official("f" * 64)))
        assert status() == EXPERIMENTAL  # Beleg passt nicht zum Kandidaten
        reg.append(_evaluation(cid, sha, official=_official(sha)))
        assert status() == VERIFIED
        assert reg.claims()[cid].proof_artifacts[-1]["exit_code"] == 0
        crashed = _official(sha, exit_code=2)  # kein lesbares Urteil: kein Beleg
        reg.append(_evaluation(cid, sha, official=crashed))
        assert status() == EXPERIMENTAL
        failed = dict(_official(sha, exit_code=1), verifier_status="FAIL")
        reg.append(_evaluation(cid, sha, official=failed))
        assert status() == REFUTED
        reg.append(_evaluation(cid, sha, official=_official(sha)))
        assert status() == VERIFIED
        # Regression: Exit 0 ohne PASS-Urteil (z. B. `| tail`, `true`) belegt nichts,
        # ein FAIL-Urteil mit Exit 0 widerlegt
        reg.append(_evaluation(cid, sha, official=_official(sha, verdict=None)))
        assert status() == EXPERIMENTAL
        reg.append(_evaluation(cid, sha, official=_official(sha, verdict="FAIL")))
        assert status() == REFUTED
        reg.append(_evaluation(cid, sha, passed=False))
        assert status() == REFUTED


def test_verified_requires_the_candidate_file_with_matching_hash():
    with tempfile.TemporaryDirectory() as d:
        reg, _ = make_lab(d, PIN_CMD)
        sha, path = reg.store_candidate(GOOD_TEXT.encode(), ".kmx")
        cid = reg.add_hypothesis("candidate", "team:phase")
        reg.append(_evaluation(cid, sha, official=_official(sha)))
        assert reg.claims()[cid].status == VERIFIED
        with open(path, "a", encoding="utf-8") as f:
            f.write("X q0\n")  # nachträglich manipuliert
        assert reg.claims()[cid].status == EXPERIMENTAL


def test_sanitising_ids_texts_and_paths():
    for bad in ("../etc/passwd", "a/b", "", ".hidden", "a..b", "x" * 65, 5, None):
        assert safe_id(bad) is None, bad
    assert safe_id("c-0123abcd") == "c-0123abcd"
    assert safe_id_list(["ok", "../x", 3, "missing"], {"ok"}) == ["ok"]
    assert safe_text("a\x00b\x1bc ") == "abc" and len(safe_text("y" * 9999)) == 2000
    with tempfile.TemporaryDirectory() as d:
        reg, _ = make_lab(d)
        assert raises(LabError, reg.store_candidate, b"x", "/../../evil")
        assert not reg.add_note("../seed-magnitude-shortcut", "x", "team:phase")
        assert not reg.add_note("c-unknown", "x", "team:phase")
        cid = reg.add_hypothesis(
            "c", "team:phase", supersedes=["seed-magnitude-shortcut", "../x", "nope"]
        )
        assert reg.claims()[cid].supersedes == ["seed-magnitude-shortcut"]
        assert reg.add_hypothesis("   ", "team:phase") is None
        assert not reg.candidate_ok("../" + "a" * 61)
        assert os.listdir(reg.candidate_dir) == []


def test_corrupt_log_lines_are_counted_not_fatal():
    with tempfile.TemporaryDirectory() as d:
        reg, _ = make_lab(d)
        with open(reg.events_path, "a", encoding="utf-8") as f:
            f.write("{kaputt\n[1,2]\n")
        assert len(reg.claims()) == 6 and reg.corrupt_lines == 1
        with open(reg.events_path, encoding="utf-8") as f:
            assert all(line.strip() for line in f)


def test_events_are_append_only_jsonl():
    with tempfile.TemporaryDirectory() as d:
        reg, _ = make_lab(d)
        with open(reg.events_path, encoding="utf-8") as f:
            before = f.read()
        reg.add_hypothesis("neu", "team:reversible")
        with open(reg.events_path, encoding="utf-8") as f:
            after = f.read()
        assert after.startswith(before)
        last = json.loads(after.splitlines()[-1])
        assert last["kind"] == EV_CLAIM and "ts" in last and "status" not in last


def test_spec_matches_the_code_constants():
    spec = load_spec("invsqrt")
    assert spec["register"]["width"] == kmx.layout.INVSQRT_WIDTH
    assert spec["domain"]["min_x"] == kmx.layout.INVSQRT_MIN_X
    assert spec["domain"]["max_x"] == kmx.layout.INVSQRT_MAX_X == 3 * (2**10 - 2) ** 2
    assert spec["cost"]["t_per_toffoli"] == kmx.cost.T_PER_TOFFOLI
    assert (
        spec["cost"]["rotation_t_per_log2_inv_eps"] == kmx.cost.ROT_T_PER_LOG2_INV_EPS
    )
    assert spec["cost"]["rotation_t_offset"] == kmx.cost.ROT_T_OFFSET
    assert spec["phase"]["fixed_point_bits"] == kmx.cost.VERIFIER_PHASE_BITS
    # Toleranz 2^-24/sqrt(x) Umdrehungen = 2^40/sqrt(x) in Einheiten von 2^-64
    assert (
        kmx.score._TOLERANCE_NUMERATOR / 2**64
        == 2.0 ** -spec["phase"]["precision_bits"]
    )
    assert "{out}" in spec["official_verifier"]["template"]
    assert "3133452" in spec_text(spec)
    assert raises(ValueError, load_spec, "../evil")


def test_spec_text_states_beta_and_prompts_use_one_tolerance_formula():
    """Regression: der Spec-Text nannte beta nicht, die Prompts eine andere Formel;
    der Kritiker erfand beta = 1e-4 und baute ein Veto darauf."""
    from kmx.lab.spec import load_spec, spec_text
    from kmx.lab.teams import PROMPT_FILES
    from kmx.prompts import load_prompt

    text = spec_text(load_spec("invsqrt"))
    assert "beta = 1" in text and "tol(x) = 2^-24 * beta / sqrt(x)" in text
    for name in PROMPT_FILES.values():
        prompt = load_prompt(name)
        assert "2^-24/sqrt(x)" not in prompt, name
        if "tol(x) =" in prompt:
            assert "2^-24 * beta/sqrt(x)" in prompt and "beta = 1" in prompt, name
