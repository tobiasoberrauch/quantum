import json, os, tempfile, unittest
from datetime import date
from pathlib import Path
from unittest import mock

import qvc_agent.client as C
import qvc_agent.memory as M
import qvc_agent.oracle as O
import qvc_agent.proposal as P

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


VALID = {"mode": "curate", "target_task": "invsqrt", "action": "adopt sha abc",
         "rationale": "tip", "expected_delta": "+0.02 ratio", "artifact_ref": "abc123",
         "precheck_plan": "stratified subset", "verify_plan": "official 64-shot",
         "abort_condition": "cost up"}


class TestProposal(unittest.TestCase):
    def test_parse_valid(self):
        d = P.parse_proposal(json.dumps(VALID))
        self.assertEqual(d["mode"], "curate")

    def test_parse_fenced(self):
        d = P.parse_proposal("```json\n" + json.dumps(VALID) + "\n```")
        self.assertEqual(d["target_task"], "invsqrt")

    def test_parse_bad_mode(self):
        bad = dict(VALID, mode="hack")
        with self.assertRaises(P.ProposalError):
            P.parse_proposal(json.dumps(bad))

    def test_parse_missing_field(self):
        bad = dict(VALID); del bad["abort_condition"]
        with self.assertRaises(P.ProposalError):
            P.parse_proposal(json.dumps(bad))

    def test_build_prompt_contains_context(self):
        s = P.build_proposal_prompt("invsqrt", mode="curate",
                                    current_best={"ratio": 21.0},
                                    candidates=[{"sha": "deadbeef", "ratio": 21.7}],
                                    memory="NEG: lookup-hybrid worse")
        self.assertIn("invsqrt", s); self.assertIn("deadbeef", s)
        self.assertIn("lookup-hybrid worse", s)


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
