import json, os, tempfile, unittest
from pathlib import Path
from unittest import mock

import qvc_agent.client as C
import qvc_agent.curate as CU
import qvc_agent.loop as L
import qvc_agent.memory as M
import qvc_agent.oracle as O
import qvc_agent.proposal as P
import qvc_agent.research as R
import qvc_agent.cli as CLI

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


class TestCurate(unittest.TestCase):
    def test_load_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "r.json"
            p.write_text('{"invsqrt":[{"sha":"a","ratio":21.0}],"chem":[]}')
            self.assertEqual(CU.load_candidates("invsqrt", path=p)[0]["sha"], "a")

    def test_materialize_plain_file(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "invsqrt.kmb"
            src.write_bytes(b"CIRCUITDATA")
            sha = hashlib.sha256(b"CIRCUITDATA").hexdigest()
            cand = Path(tmp) / "c.json"
            cand.write_text(json.dumps({"invsqrt": {sha: {"locs": [{"path": str(src), "inner": None, "xz": False}], "ext": "kmb"}}}))
            out = Path(tmp) / "out"
            art = CU.materialize({"artifact_ref": sha}, out, comp="invsqrt", candidates_path=cand)
            self.assertTrue(art.exists())
            self.assertEqual(art.read_bytes(), b"CIRCUITDATA")

    def test_materialize_unknown_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            cand = Path(tmp) / "c.json"
            cand.write_text('{"invsqrt":{}}')
            with self.assertRaises(KeyError):
                CU.materialize({"artifact_ref": "nope"}, Path(tmp) / "o", comp="invsqrt", candidates_path=cand)

    def test_materialize_sha_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "x.kmb"
            src.write_bytes(b"AAA")
            cand = Path(tmp) / "c.json"
            cand.write_text(json.dumps({"invsqrt": {"0" * 64: {"locs": [{"path": str(src), "inner": None, "xz": False}], "ext": "kmb"}}}))
            with self.assertRaises(RuntimeError):
                CU.materialize({"artifact_ref": "0" * 64}, Path(tmp) / "o", comp="invsqrt", candidates_path=cand)


class TestResearch(unittest.TestCase):
    def test_materialize_calls_emit_and_returns_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            wd, out = Path(tmp) / "wd", Path(tmp) / "out"
            wd.mkdir(); out.mkdir()
            def fake_emit(w):
                p = w / "invsqrt.kmb"; p.write_bytes(b"NEW"); return p
            art = R.materialize_research({"edit": {"params": {"n1_frac": 16}}}, wd, out, emit_fn=fake_emit)
            self.assertEqual(art.read_bytes(), b"NEW")

    def test_apply_edit_writes_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            wd = Path(tmp) / "wd"; wd.mkdir()
            R.apply_edit(wd, {"params": {"use_lookup": True}})
            ov = json.loads((wd / "overrides.json").read_text())
            self.assertEqual(ov, {"use_lookup": True})

    def test_materialize_requires_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            wd, out = Path(tmp) / "wd", Path(tmp) / "out"; wd.mkdir(); out.mkdir()
            with self.assertRaises(ValueError):
                R.materialize_research({}, wd, out, emit_fn=lambda w: w)


class TestLoop(unittest.TestCase):
    def _props(self, raws):
        it = iter(raws)
        return lambda ctx: next(it)

    @staticmethod
    def _valid_prop():
        return json.dumps({"mode": "curate", "target_task": "invsqrt", "action": "a",
                           "rationale": "r", "expected_delta": "d", "artifact_ref": "abc",
                           "precheck_plan": "p", "verify_plan": "v", "abort_condition": "x"})

    def test_keep_updates_best(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            s = L.run_loop("invsqrt", "curate", 1,
                propose_fn=self._props([self._valid_prop()]),
                materialize_fn=lambda p, *a, **k: Path(tmp) / "x.kmb",
                precheck_fn=lambda a: {"all_passed": True},
                verify_fn=lambda a: {"all_passed": True, "official_cost_if_identical_across_salts": 95000.0},
                approve_fn=lambda *a, **k: True,
                run_dir=rd, best_ratio=21.0, best_cost=100000.0, memory_base=Path(tmp) / "mem")
            self.assertEqual(s["kept"], 1)
            self.assertGreater(s["best_ratio_end"], s["best_ratio_start"])

    def test_discard_on_higher_cost(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            s = L.run_loop("invsqrt", "curate", 1,
                propose_fn=self._props([self._valid_prop()]),
                materialize_fn=lambda p, *a, **k: Path(tmp) / "x.kmb",
                precheck_fn=lambda a: {"all_passed": True},
                verify_fn=lambda a: {"all_passed": True, "official_cost_if_identical_across_salts": 120000.0},
                approve_fn=lambda *a, **k: True,
                run_dir=rd, best_ratio=21.0, best_cost=100000.0, memory_base=Path(tmp) / "mem")
            self.assertEqual(s["kept"], 0)
            self.assertEqual(s["best_ratio_end"], s["best_ratio_start"])

    def test_discard_on_bad_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            s = L.run_loop("invsqrt", "curate", 1,
                propose_fn=self._props(["this is not json"]),
                materialize_fn=lambda p, *a, **k: Path(tmp) / "x.kmb",
                precheck_fn=lambda a: {"all_passed": True},
                verify_fn=lambda a: {"all_passed": True, "official_cost_if_identical_across_salts": 1.0},
                approve_fn=lambda *a, **k: True,
                run_dir=rd, best_ratio=21.0, best_cost=100000.0, memory_base=Path(tmp) / "mem")
            self.assertEqual(s["kept"], 0)
            self.assertTrue((rd / "loop.jsonl").exists())  # Runde wurde geloggt

    def test_hitl_blocks_advance(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            s = L.run_loop("invsqrt", "curate", 1,
                propose_fn=self._props([self._valid_prop()]),
                materialize_fn=lambda p, *a, **k: Path(tmp) / "x.kmb",
                precheck_fn=lambda a: {"all_passed": True},
                verify_fn=lambda a: {"all_passed": True, "official_cost_if_identical_across_salts": 95000.0},
                approve_fn=lambda *a, **k: False,
                run_dir=rd, best_ratio=21.0, best_cost=100000.0, memory_base=Path(tmp) / "mem")
            self.assertEqual(s["kept"], 0)
            self.assertEqual(s["best_ratio_end"], s["best_ratio_start"])

    def test_dry_run_skips_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            s = L.run_loop("invsqrt", "curate", 1,
                propose_fn=self._props([self._valid_prop()]),
                materialize_fn=lambda p, *a, **k: Path(tmp) / "x.kmb",
                precheck_fn=lambda a: {"all_passed": True},
                verify_fn=None,  # dry_run
                approve_fn=lambda *a, **k: True,
                run_dir=rd, best_ratio=21.0, best_cost=100000.0, memory_base=Path(tmp) / "mem")
            self.assertEqual(s["kept"], 0)

    def test_run_dir_blank_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            for bad in ("", None):
                with self.assertRaises(ValueError):
                    L.run_loop("invsqrt", "curate", 1,
                        propose_fn=self._props([self._valid_prop()]),
                        materialize_fn=lambda p, *a, **k: Path(tmp) / "x.kmb",
                        precheck_fn=lambda a: {"all_passed": True},
                        verify_fn=None,
                        approve_fn=lambda *a, **k: True,
                        run_dir=bad, best_ratio=21.0, best_cost=100000.0, memory_base=Path(tmp) / "mem")

    def test_propose_error_discards_and_continues(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            def boom(ctx):
                raise RuntimeError("llm down sk-topsecret")
            s = L.run_loop("invsqrt", "curate", 1,
                propose_fn=boom,
                materialize_fn=lambda p, *a, **k: Path(tmp) / "x.kmb",
                precheck_fn=lambda a: {"all_passed": True},
                verify_fn=lambda a: {"all_passed": True, "official_cost_if_identical_across_salts": 1.0},
                approve_fn=lambda *a, **k: True,
                run_dir=rd, best_ratio=21.0, best_cost=100000.0, memory_base=Path(tmp) / "mem")
            self.assertEqual(s["kept"], 0)
            rows = M.read_loop_log(rd)
            self.assertEqual(rows[0]["verdict"], "DISCARD_PROPOSE_ERROR")
            # the secret in the exception message must NOT leak into the public log
            self.assertNotIn("sk-topsecret", (rd / "loop.jsonl").read_text())


class TestCli(unittest.TestCase):
    def test_check_endpoint_calls_client_once(self):
        with mock.patch.object(CLI, "WeinstadtClient") as WC:
            inst = WC.return_value; inst.chat.return_value = "pong"
            rc = CLI.main(["check-endpoint"])
        self.assertEqual(rc, 0)
        self.assertEqual(inst.chat.call_count, 1)

    def test_run_builds_kwargs(self):
        with mock.patch.object(CLI, "run_loop", return_value={"kept": 0}) as rl, \
             mock.patch.object(CLI, "resolve_endpoint",
                               return_value={"base_url": "http://x/v1", "api_key": None, "model": "qwen3.8-27b"}), \
             mock.patch.object(CLI.curate, "load_candidates",
                               return_value=[{"ratio": 21.0, "score": 100000.0}]):
            rc = CLI.main(["run", "--task", "invsqrt", "--mode", "curate", "--rounds", "2", "--dry-run"])
        self.assertEqual(rc, 0)
        kwargs = rl.call_args.kwargs
        self.assertEqual(kwargs["task"], "invsqrt")
        self.assertEqual(kwargs["mode"], "curate")
        self.assertEqual(kwargs["n_rounds"], 2)
        self.assertIsNone(kwargs["verify_fn"])  # dry-run
        self.assertEqual(kwargs["candidates_path"], CU.CANDIDATES_RANKED)  # threaded, default dir

    def test_autonomous_min_cost_floor(self):
        with mock.patch.object(CLI, "run_loop") as rl, \
             mock.patch.object(CLI, "resolve_endpoint",
                               return_value={"base_url": "http://x/v1", "api_key": None, "model": "qwen3.8-27b"}), \
             mock.patch.object(CLI.curate, "load_candidates",
                               return_value=[{"ratio": 21.0, "score": 100000.0}]):
            rl.return_value = {"kept": 0}
            rc = CLI.main(["run", "--task", "invsqrt", "--mode", "curate", "--rounds", "1",
                           "--autonomous", "--min-cost", "90000"])
        self.assertEqual(rc, 0)
        approve = rl.call_args.kwargs["approve_fn"]
        # cost above floor -> auto-keep
        self.assertTrue(approve({}, {"all_passed": True, "official_cost_if_identical_across_salts": 95000.0}))
        # cost below floor -> refused unattended
        self.assertFalse(approve({}, {"all_passed": True, "official_cost_if_identical_across_salts": 80000.0}))
        # no usable cost -> refused
        self.assertFalse(approve({}, {"all_passed": False}))
