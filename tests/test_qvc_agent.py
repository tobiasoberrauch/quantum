import json, os, tempfile, unittest
from pathlib import Path
from unittest import mock
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root (direct run)
import qvc_agent.client as C  # noqa: E402
import qvc_agent.curate as CU
import qvc_agent.loop as L
import qvc_agent.memory as M
import qvc_agent.oracle as O
import qvc_agent.proposal as P
import qvc_agent.research as R
import qvc_agent.watchdog as W
import qvc_agent.driver as driver
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

    def test_parse_mode_case_insensitive(self):
        # live finding: model emitted "CURATE"; parser must normalize, not reject
        d = P.parse_proposal(json.dumps(dict(VALID, mode="CURATE")))
        self.assertEqual(d["mode"], "curate")

    def test_parse_target_task_case_insensitive(self):
        d = P.parse_proposal(json.dumps(dict(VALID, target_task="INVSQRT")))
        self.assertEqual(d["target_task"], "invsqrt")

    def test_parse_mode_still_rejects_invalid(self):
        with self.assertRaises(P.ProposalError):
            P.parse_proposal(json.dumps(dict(VALID, mode="hack")))


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

    def test_malformed_candidates_file_degrades(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            bad = Path(tmp) / "bad_ranked.json"
            bad.write_text("[1, 2, 3]")  # valid JSON but not a dict -> TypeError in load_candidates
            s = L.run_loop("invsqrt", "curate", 1,
                propose_fn=self._props([self._valid_prop()]),
                materialize_fn=lambda p, *a, **k: Path(tmp) / "x.kmb",
                precheck_fn=lambda a: {"all_passed": True},
                verify_fn=lambda a: {"all_passed": True, "official_cost_if_identical_across_salts": 95000.0},
                approve_fn=lambda *a, **k: True,
                run_dir=rd, best_ratio=21.0, best_cost=100000.0, memory_base=Path(tmp) / "mem",
                candidates_path=bad)
            self.assertEqual(s["rounds"], 1)
            self.assertEqual(s["kept"], 1)  # round proceeded despite empty candidates


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


class TestWatchdog(unittest.TestCase):
    A = "a" * 64
    B = "b" * 64

    def _pool(self, tmp, entries):
        p = Path(tmp) / "pool.json"
        p.write_text(json.dumps({"invsqrt": entries}))
        return p

    def _run(self, tmp, entries, verify_costs, **kw):
        pool = self._pool(tmp, entries)
        state = Path(tmp) / "state.json"
        out = Path(tmp) / "out"
        rd = Path(tmp) / "rd"
        mem = Path(tmp) / "mem"

        def mat(sha, dest):
            p = Path(tmp) / f"{sha}.kmb"; p.write_bytes(b"x"); return p

        def pre(art):
            return {"all_passed": True}

        def ver(art):
            c = verify_costs.get(art.stem)
            if c is None:
                return {"all_passed": False}
            return {"all_passed": True, "official_cost_if_identical_across_salts": c}

        s = W.sweep_pool(task="invsqrt", pool_path=pool, state_path=state, out_dir=out,
                         precheck_fn=pre, verify_fn=ver, materialize_fn=mat,
                         run_dir=rd, memory_base=mem, **kw)
        return s, state, out, rd, mem

    def test_adopt_beats_bar(self):
        with tempfile.TemporaryDirectory() as tmp:
            entries = [{"sha": self.A, "ratio": 20.0, "score": 100000.0},
                       {"sha": self.B, "ratio": 23.0, "score": 90000.0}]
            s, state, out, rd, mem = self._run(tmp, entries, {self.A: 100000.0, self.B: 90000.0})
            self.assertEqual(s["kept"], 1)
            self.assertEqual(s["new_best_sha"], self.B)
            self.assertEqual(W.load_state(state)["best_sha"], self.B)
            self.assertTrue((out / "invsqrt.kmb").exists())  # adopted artifact copied
            self.assertTrue(any(mem.glob("*.md")))           # memory note written on keep

    def test_discard_worse(self):
        with tempfile.TemporaryDirectory() as tmp:
            entries = [{"sha": self.A, "ratio": 23.0, "score": 90000.0},
                       {"sha": self.B, "ratio": 20.0, "score": 100000.0}]
            s, state, out, rd, mem = self._run(tmp, entries, {self.A: 90000.0, self.B: 100000.0})
            self.assertEqual(s["kept"], 0)
            self.assertEqual(W.load_state(state)["best_sha"], self.A)
            self.assertFalse((out / "invsqrt.kmb").exists())

    def test_skip_seen_on_second_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            entries = [{"sha": self.A, "ratio": 20.0, "score": 100000.0},
                       {"sha": self.B, "ratio": 23.0, "score": 90000.0}]
            s1, state, *_ = self._run(tmp, entries, {self.A: 100000.0, self.B: 90000.0})
            self.assertEqual(s1["verified"], 1)  # only B verified (A is the baseline)
            s2, *_ = self._run(tmp, entries, {self.A: 100000.0, self.B: 90000.0})
            self.assertEqual(s2["verified"], 0)   # both now seen -> skipped
            self.assertEqual(s2["scanned"], 2)

    def test_dry_run_no_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            entries = [{"sha": self.A, "ratio": 20.0, "score": 100000.0},
                       {"sha": self.B, "ratio": 23.0, "score": 90000.0}]
            calls = {"n": 0}

            def ver(art):
                calls["n"] += 1
                return {"all_passed": True, "official_cost_if_identical_across_salts": 1.0}

            def mat(sha, dest):
                p = Path(tmp) / f"{sha}.kmb"; p.write_bytes(b"x"); return p

            s = W.sweep_pool(task="invsqrt", pool_path=self._pool(tmp, entries),
                             state_path=Path(tmp) / "s.json", out_dir=Path(tmp) / "o",
                             precheck_fn=lambda a: {"all_passed": True}, verify_fn=ver,
                             materialize_fn=mat,
                             run_dir=Path(tmp) / "rd", memory_base=Path(tmp) / "m", dry_run=True)
            self.assertEqual(calls["n"], 0)
            self.assertEqual(s["kept"], 0)
            rows = M.read_loop_log(Path(tmp) / "rd")
            self.assertTrue(any(r.get("verdict") == "DRY_RUN" for r in rows))

    def test_floor_refuses_subfloor(self):
        with tempfile.TemporaryDirectory() as tmp:
            entries = [{"sha": self.A, "ratio": 20.0, "score": 100000.0},
                       {"sha": self.B, "ratio": 23.0, "score": 90000.0}]
            # B beats the bar (90000 < 100000) but is below the floor (95000) -> refused
            s, state, *_ = self._run(tmp, entries, {self.A: 100000.0, self.B: 90000.0}, floor=95000.0)
            self.assertEqual(s["kept"], 0)
            self.assertEqual(W.load_state(state)["best_sha"], self.A)

    def test_max_candidates_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            entries = [{"sha": self.A, "ratio": 20.0, "score": 100000.0},
                       {"sha": self.B, "ratio": 23.0, "score": 90000.0},
                       {"sha": "c" * 64, "ratio": 24.0, "score": 80000.0}]
            s, *_ = self._run(tmp, entries, {self.A: 100000.0, self.B: 90000.0, "c" * 64: 80000.0},
                              max_candidates=1)
            self.assertEqual(s["scanned"], 1)

    def test_wall_time_zero_stops_immediately(self):
        with tempfile.TemporaryDirectory() as tmp:
            entries = [{"sha": self.A, "ratio": 20.0, "score": 100000.0},
                       {"sha": self.B, "ratio": 23.0, "score": 90000.0}]
            s, *_ = self._run(tmp, entries, {self.A: 100000.0, self.B: 90000.0}, wall_time_s=0.0)
            self.assertEqual(s["scanned"], 0)

    def test_state_roundtrip_and_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "st.json"
            W.save_state(p, {"best_ratio": 21.0, "best_cost": 95000.0, "best_sha": "x", "seen": ["a", "b"]})
            st = W.load_state(p)
            self.assertEqual(st["best_cost"], 95000.0)
            self.assertEqual(st["seen"], ["a", "b"])
            missing = W.load_state(Path(tmp) / "nope.json")
            self.assertIsNone(missing["best_cost"])
            self.assertEqual(missing["seen"], [])


class TestWatchCli(unittest.TestCase):
    def test_watch_calls_sweep_with_kwargs(self):
        with mock.patch.object(CLI.watchdog, "sweep_pool", return_value={"kept": 0}) as sw:
            rc = CLI.main(["watch", "--task", "invsqrt", "--max-candidates", "3",
                           "--min-cost", "50000", "--dry-run"])
        self.assertEqual(rc, 0)
        kwargs = sw.call_args.kwargs
        self.assertEqual(kwargs["task"], "invsqrt")
        self.assertEqual(kwargs["max_candidates"], 3)
        self.assertEqual(kwargs["floor"], 50000.0)
        self.assertTrue(kwargs["dry_run"])
        self.assertIsNone(kwargs["verify_fn"])  # dry-run


class TestDriver(unittest.TestCase):
    A = "a" * 64
    C = "c" * 64

    def _frontier(self, tmp, ranked_rows, universe_shas):
        fd = Path(tmp) / "frontier"
        (fd / "scripts").mkdir(parents=True)
        (fd / "downloads").mkdir()
        (fd / "candidates_ranked.json").write_text(json.dumps({"invsqrt": ranked_rows}))
        (fd / "candidates.json").write_text(json.dumps(
            {"invsqrt": {s: {"size": 1, "ext": "kmb", "locs": [], "sources": ["x"]} for s in universe_shas}}))
        return fd

    def _fakes(self, tmp, verify_costs):
        def mat(sha, dest):
            p = Path(tmp) / f"{sha}.kmb"; p.write_bytes(b"x"); return p
        def pre(art):
            return {"all_passed": True}
        def ver(art):
            c = verify_costs.get(art.stem)
            return {"all_passed": c is not None, "official_cost_if_identical_across_salts": c}
        return mat, pre, ver

    def test_seed_and_unseen(self):
        with tempfile.TemporaryDirectory() as tmp:
            fd = self._frontier(tmp, [{"sha": self.A, "ratio": 20.0, "score": 100000.0},
                                      {"sha": "b" * 64, "ratio": 19.0, "score": 110000.0}],
                                [self.A, "b" * 64, self.C])
            st = Path(tmp) / "state.json"
            driver.seed_state_if_absent(fd, "invsqrt", st)
            state = W.load_state(st)
            self.assertEqual(state["best_sha"], self.A)          # bar = ranked top
            self.assertEqual(set(state["seen"]), {self.A, "b" * 64})  # all ranked marked seen
            self.assertEqual(driver.unseen_shas(fd, "invsqrt", st), [self.C])

    def test_run_autonomous_adopts_new_best(self):
        with tempfile.TemporaryDirectory() as tmp:
            fd = self._frontier(tmp, [{"sha": self.A, "ratio": 20.0, "score": 100000.0}],
                                [self.A, self.C])
            mat, pre, ver = self._fakes(tmp, {self.A: 100000.0, self.C: 90000.0})
            s = driver.run_autonomous(frontier_dir=fd, task="invsqrt",
                state_path=Path(tmp) / "state.json", out_dir=Path(tmp) / "out",
                precheck_fn=pre, verify_fn=ver, materialize_fn=mat,
                refresh=lambda d: 0, downloader=lambda d: 0)
            self.assertEqual(s["kept"], 1)
            self.assertEqual(s["best"]["best_sha"], self.C)      # adopted the better circuit
            self.assertTrue((Path(tmp) / "out" / "adopt" / "invsqrt.kmb").exists())

    def test_run_autonomous_no_unseen_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            fd = self._frontier(tmp, [{"sha": self.A, "ratio": 20.0, "score": 100000.0}], [self.A])
            mat, pre, ver = self._fakes(tmp, {self.A: 100000.0})
            s = driver.run_autonomous(frontier_dir=fd, task="invsqrt",
                state_path=Path(tmp) / "state.json", out_dir=Path(tmp) / "out",
                precheck_fn=pre, verify_fn=ver, materialize_fn=mat,
                refresh=lambda d: 0, downloader=lambda d: 0)
            self.assertEqual(s["kept"], 0)
            self.assertEqual(len(s["cycles"]), 1)
            self.assertEqual(s["cycles"][0]["unseen"], 0)

    def test_run_autonomous_max_cycles_with_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            fd = self._frontier(tmp, [{"sha": self.A, "ratio": 20.0, "score": 100000.0}], [self.A])
            mat, pre, ver = self._fakes(tmp, {self.A: 100000.0})
            s = driver.run_autonomous(frontier_dir=fd, task="invsqrt",
                state_path=Path(tmp) / "state.json", out_dir=Path(tmp) / "out",
                precheck_fn=pre, verify_fn=ver, materialize_fn=mat,
                refresh=lambda d: 0, downloader=lambda d: 2, download=True, max_cycles=3)
            # with downloads enabled and no new unseen, it loops all cycles
            self.assertEqual(len(s["cycles"]), 3)
            # downloader count is reported per cycle and summed (observability)
            self.assertEqual(s["downloaded"], 6)
            self.assertTrue(all(c.get("downloaded") == 2 for c in s["cycles"]))

    def _frontier_with_downloads(self, tmp, slug_dirs):
        fd = Path(tmp) / "frontier"
        (fd / "scripts").mkdir(parents=True)
        (fd / "downloads").mkdir()
        (fd / "scripts" / "kg.sh").write_text("#!/bin/bash\necho ok\n")
        for sd in slug_dirs:
            (fd / "downloads" / sd).mkdir(parents=True)
        home = Path(tmp) / "home"
        (home / ".kaggle").mkdir(parents=True)
        (home / ".kaggle" / "access_token").write_text("tok")
        return fd, home

    def test_slug_ref(self):
        self.assertEqual(driver._slug_ref("d__heliosli__qcc-circuits-live"),
                         "heliosli/qcc-circuits-live")
        self.assertEqual(
            driver._slug_ref("k__prvsiyan__verifier-guided-quantum-circuit-optimization"),
            "prvsiyan/verifier-guided-quantum-circuit-optimization")
        self.assertIsNone(driver._slug_ref("own__qvc009"))   # no owner/slug split
        self.assertIsNone(driver._slug_ref("d__onlyowner"))  # missing slug
        self.assertIsNone(driver._slug_ref(""))              # empty
        self.assertIsNone(driver._slug_ref(None))            # non-str

    def test_download_sources_dataset_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            fd, home = self._frontier_with_downloads(tmp, ["d__heliosli__qcc-circuits-live"])
            with mock.patch.object(driver.Path, "home", return_value=home), \
                    mock.patch.object(driver.subprocess, "run") as run, \
                    mock.patch.object(driver.time, "sleep"):
                run.return_value = mock.Mock(returncode=0)
                n = driver.download_sources(fd)
            self.assertEqual(n, 1)
            args = run.call_args.args[0]
            self.assertEqual(args[:3], ["bash", str(fd / "scripts" / "kg.sh"), "datasets"])
            self.assertIn("download", args)
            self.assertIn("-d", args)
            self.assertIn("heliosli/qcc-circuits-live", args)
            self.assertIn("--force", args)
            self.assertTrue((fd / "downloads" / "d__heliosli__qcc-circuits-live" / ".done").exists())

    def test_download_sources_kernel_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            fd, home = self._frontier_with_downloads(
                tmp, ["k__prvsiyan__verifier-guided-quantum-circuit-optimization"])
            with mock.patch.object(driver.Path, "home", return_value=home), \
                    mock.patch.object(driver.subprocess, "run") as run, \
                    mock.patch.object(driver.time, "sleep"):
                run.return_value = mock.Mock(returncode=0)
                n = driver.download_sources(fd, kinds=("k",))
            self.assertEqual(n, 1)
            args = run.call_args.args[0]
            self.assertEqual(args[2], "kernels")
            self.assertIn("output", args)
            self.assertIn("prvsiyan/verifier-guided-quantum-circuit-optimization", args)
            self.assertIn("--file-pattern", args)
            self.assertIn("--force", args)

    def test_download_sources_default_skips_kernels(self):
        with tempfile.TemporaryDirectory() as tmp:
            fd, home = self._frontier_with_downloads(tmp, ["d__a__b", "k__c__d"])
            with mock.patch.object(driver.Path, "home", return_value=home), \
                    mock.patch.object(driver.subprocess, "run") as run, \
                    mock.patch.object(driver.time, "sleep"):
                run.return_value = mock.Mock(returncode=0)
                n = driver.download_sources(fd)   # default kinds=("d",)
            self.assertEqual(n, 1)                # only the dataset re-fetched
            self.assertEqual(run.call_count, 1)

    def test_download_sources_failure_not_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            fd, home = self._frontier_with_downloads(tmp, ["d__a__b"])
            with mock.patch.object(driver.Path, "home", return_value=home), \
                    mock.patch.object(driver.subprocess, "run") as run, \
                    mock.patch.object(driver.time, "sleep"):
                run.return_value = mock.Mock(returncode=1)
                n = driver.download_sources(fd)
            self.assertEqual(n, 0)
            self.assertFalse((fd / "downloads" / "d__a__b" / ".done").exists())

    def test_download_sources_guards_bad_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            fd, home = self._frontier_with_downloads(tmp, ["d__a__b"])
            with mock.patch.object(driver.subprocess, "run") as run:
                self.assertEqual(driver.download_sources(None), 0)
                self.assertEqual(driver.download_sources(""), 0)
                self.assertEqual(driver.download_sources("   "), 0)
                self.assertEqual(run.call_count, 0)
            # kinds=None falls back to datasets; missing token -> 0
            with mock.patch.object(driver.Path, "home", return_value=Path(tmp) / "nohome"):
                self.assertEqual(driver.download_sources(fd, kinds=None), 0)


class TestAutonomousCli(unittest.TestCase):
    def test_autonomous_calls_driver(self):
        with mock.patch.object(CLI.driver, "run_autonomous", return_value={"kept": 0}) as ra:
            rc = CLI.main(["autonomous", "--task", "invsqrt", "--cycles", "2",
                           "--max-candidates", "4", "--min-cost", "50000", "--download"])
        self.assertEqual(rc, 0)
        k = ra.call_args.kwargs
        self.assertEqual(k["task"], "invsqrt")
        self.assertEqual(k["max_cycles"], 2)
        self.assertEqual(k["max_candidates"], 4)
        self.assertEqual(k["floor"], 50000.0)
        self.assertTrue(k["download"])
        self.assertFalse(k["dry_run"])
