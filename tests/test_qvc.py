"""Offline tests: mocks are NOT official verifier results."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root (direct run)
import qvc_discovery as q  # noqa: E402


class TestQVC(unittest.TestCase):
    def test_baseline_score(self):
        value = q.score_ratios(q.BASELINE_RATIOS)
        self.assertAlmostEqual(value, 25.15, delta=0.03)
        with self.assertRaises(ValueError):
            q.score_ratios({"invsqrt": 1})

    def test_score_rejects_fake_or_insufficient_salts(self):
        payload = {
            k: {"source": "example_only", "passed": False, "cost": v / q.BASELINE_RATIOS[k]}
            for k, v in q.REFERENCE_COSTS.items()
        }
        with self.assertRaisesRegex(ValueError, "official_verifier"):
            q.score_from_verified_costs(payload)
        for x in payload.values():
            x["source"] = "official_verifier"
            x["passed"] = True
        payload["dqi"]["shots"] = 102400
        payload["dqi"]["independent_salts"] = ["a", "b"]
        with self.assertRaisesRegex(ValueError, "5 independent"):
            q.score_from_verified_costs(payload)
        payload["dqi"]["independent_salts"] = list("abcde")
        scored = q.score_from_verified_costs(payload)
        self.assertAlmostEqual(scored["score"], q.score_ratios(q.BASELINE_RATIOS), places=9)

    def test_json_and_review_validation(self):
        with self.assertRaises(ValueError):
            q.validate_generation({"proposals": []})
        review = {"reviews": [{"proposal_id": "QVC-01", "novelty_status": "UNVERIFIED",
                                "feasibility": 3, "potential_impact": 4}]}
        q.validate_review(review, "QVC-01")
        review["reviews"][0]["novelty_status"] = "PROVEN"
        with self.assertRaises(ValueError):
            q.validate_review(review, "QVC-01")
        q.validate_selection({"priority_queue": [{"proposal_id": "QVC-01"}]}, {"QVC-01"}, 1)

    def test_offline_dry_run(self):
        with TemporaryDirectory() as root:
            artifact = Path(root) / "invsqrt.kmb"
            artifact.write_bytes(b"fake-circuit-not-for-verification")
            adapter = {"tasks": {"invsqrt": {
                "command": ["/not/actually/a/real/verifier", "{candidate}", "{salt}"],
                "salts": ["audit-a"]}}}
            result = q.verify_candidate(adapter, "invsqrt", artifact, Path(root), execute=False)
            self.assertEqual(result["status"], "DRY_RUN_ONLY")
            self.assertFalse(result["executed"])
            self.assertEqual(len(result["sha256"]), 64)
            self.assertIn(str(artifact.resolve()), result["command_preview"][0])

    def test_dqi_requires_five_salts_before_execution(self):
        with TemporaryDirectory() as root:
            artifact = Path(root) / "dqi.kmb"
            artifact.write_bytes(b"not-an-actual-circuit")
            adapter = {"tasks": {"dqi": {
                "command": ["echo", "{candidate}", "{salt}"],
                "salts": ["a", "b", "c", "d"]}}}
            with self.assertRaisesRegex(ValueError, "five|5"):
                q.verify_candidate(adapter, "dqi", artifact, Path(root), execute=True)

    def test_mocked_full_discovery_workflow(self):
        def fake_call(key, chain, prompt, schema, schema_name, check, retries=2, temperature=0.6):
            if schema_name == "qvc_idea":
                proposal = {
                    "title": "Reversible test candidate", "novel_mechanism": "Replace a reversible operation",
                    "analogy": {"source_domain": "register allocation", "transfer_principle": "liveness",
                                "formal_mapping": "ancilla lifetime to register lifetime",
                                "breakdown_conditions": "phase corrections can break equivalence"},
                    "change_to_existing_baseline": "Modify one local section",
                    "needed_source_assets": ["known valid generator"],
                    "mathematical_invariants": ["clean ancilla", "correct phase"],
                    "predicted_resource_tradeoff": "potential lower Q at larger T",
                    "implementation_plan": ["derive equivalence", "build candidate", "verify"],
                    "cheap_precheck": "fuzz selected inputs", "official_verifier_plan": "full check",
                    "falsification_condition": "no valid reduction", "prior_art_queries": ["reversible pebbling"],
                    "known_failure_avoidance": "retain all phase corrections", "blocking_risks": ["unknown source"]}
                data = {"proposals": [proposal]}
            elif schema_name == "qvc_critique":
                import re
                pid = re.search(r"QVC-\d+", prompt).group()
                data = {"reviews": [{"proposal_id": pid, "thesis": "could work",
                                     "antithesis": "may fail", "synthesis": "test a narrow form",
                                     "hardest_counterexample": "phase mismatch",
                                     "invariant_violation_risk": "ancilla not clean",
                                     "decisive_experiment": "full official verifier",
                                     "feasibility": 3, "potential_impact": 3,
                                     "novelty_status": "UNVERIFIED"}]}
            elif schema_name == "qvc_selection":
                data = {"research_strategy": "test simplest candidates first",
                        "priority_queue": [{"proposal_id": "QVC-01", "rationale": "cheap",
                                            "first_implementation_step": "build reversible circuit",
                                            "success_threshold": "official PASS and lower Q*C",
                                            "abort_condition": "no safe gain",
                                            "required_assets": ["reference circuit"]}],
                        "shared_falsification_risks": ["silent phase errors"]}
            else:
                raise AssertionError(schema_name)
            q.validate(data, schema)
            check(data)
            return {"data": data, "served_model": chain[0], "failures": []}

        with patch.object(q, "call_models", side_effect=fake_call):
            result = q.discover("fake", ["invsqrt"], "", "", 1, 1, 2)
        self.assertEqual(len(result["proposals"]), 3)
        self.assertEqual(len(result["reviews"]), 3)
        self.assertIn("No ideas", q.report(result))
        self.assertEqual(result["experiment_status"], "NO CANDIDATE BUILT OR VERIFIED BY DISCOVER COMMAND")

    def test_sdk_fallback_recovers_from_bad_json(self):
        calls = []
        response_data = {"ok": "yes"}

        class FakeClient:
            def __init__(self, api_key):
                self.api_key = api_key
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return None
            @property
            def chat(self):
                return self
            def send(self, **kwargs):
                calls.append(kwargs["model"])
                content = "not valid json" if kwargs["model"] == "first" else json.dumps(response_data)
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                                       model=kwargs["model"])

        with patch.object(q, "OpenRouter", FakeClient):
            result = q.call_models("dummy-test-key", ["first", "second"],
                                   "test", q.obj({"ok": q.S}), "test_schema",
                                   lambda x: None, retries=1)
        self.assertEqual(result["served_model"], "second")
        self.assertEqual(result["data"], response_data)
        self.assertGreaterEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
