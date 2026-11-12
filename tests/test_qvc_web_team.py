"""Hermetic tests for the qvc_web multi-agent team backend (no network, no keys)."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root (direct run)
from qvc_web.backend import team  # noqa: E402


def _ok_response(content="hello", model="m"):
    return {"choices": [{"message": {"content": content}}], "model": model,
            "usage": {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12}}


class TestChat(unittest.TestCase):
    def test_keyless_no_auth_header(self):
        captured = {}

        def fake_http(url, payload, headers, timeout):
            captured.update(url=url, headers=headers, payload=payload)
            return _ok_response("hi")

        m = {"id": "x", "base_url": "http://h/v1", "model": "qwen", "api_key_env": ""}
        out = team.chat(m, [{"role": "user", "content": "yo"}], http=fake_http)
        self.assertEqual(out["content"], "hi")
        self.assertNotIn("Authorization", captured["headers"])
        self.assertTrue(captured["url"].endswith("/chat/completions"))
        self.assertEqual(captured["payload"]["model"], "qwen")

    def test_keyed_sends_bearer(self):
        captured = {}

        def fake_http(url, payload, headers, timeout):
            captured["headers"] = headers
            return _ok_response()

        m = {"id": "x", "base_url": "http://h/v1/", "model": "gpt", "api_key_env": "MY_KEY"}
        with mock.patch.dict(os.environ, {"MY_KEY": "sekret123"}):
            team.chat(m, [{"role": "user", "content": "yo"}], http=fake_http)
        self.assertEqual(captured["headers"].get("Authorization"), "Bearer sekret123")

    def test_malformed_raises(self):
        def fake_http(url, payload, headers, timeout):
            return {"choices": []}
        m = {"id": "x", "base_url": "http://h/v1", "model": "gpt", "api_key_env": ""}
        with self.assertRaises(RuntimeError):
            team.chat(m, [{"role": "user", "content": "yo"}], http=fake_http)

    def test_missing_base_url_raises(self):
        with self.assertRaises(ValueError):
            team.chat({"id": "x", "model": "gpt"}, [], http=lambda *a, **k: {})

    def test_empty_content_retries_once_with_lower_temp(self):
        temps = []

        def fake_http(url, payload, headers, timeout):
            temps.append(payload["temperature"])
            if len(temps) == 1:
                return _ok_response(content="   ")   # whitespace-only -> triggers retry
            return _ok_response(content="recovered")

        m = {"id": "x", "base_url": "http://h/v1", "model": "qwen", "api_key_env": ""}
        out = team.chat(m, [{"role": "user", "content": "yo"}], temperature=0.7, http=fake_http)
        self.assertEqual(out["content"], "recovered")
        self.assertEqual(len(temps), 2)              # retried exactly once
        self.assertLess(temps[1], 0.7)               # retry used a lower temperature

    def test_extra_body_cannot_override_core_fields(self):
        captured = {}

        def fake_http(url, payload, headers, timeout):
            captured.update(payload)
            return _ok_response("ok")

        m = {"id": "x", "base_url": "http://h/v1", "model": "qwen", "api_key_env": "",
             "extra_body": {"model": "EVIL", "temperature": 0.99, "max_tokens": 1,
                            "chat_template_kwargs": {"enable_thinking": False}}}
        team.chat(m, [{"role": "user", "content": "yo"}], temperature=0.5,
                  max_tokens=1234, http=fake_http)
        self.assertEqual(captured["model"], "qwen")          # core wins over extra_body
        self.assertEqual(captured["temperature"], 0.5)       # core wins
        self.assertEqual(captured["max_tokens"], 1234)       # core wins
        self.assertIn("chat_template_kwargs", captured)      # extra keys still pass through

    def test_non_http_base_url_rejected(self):
        m = {"id": "x", "base_url": "file:///etc/passwd", "model": "qwen", "api_key_env": ""}
        with self.assertRaises(ValueError):
            team.chat(m, [{"role": "user", "content": "yo"}], http=lambda *a, **k: {})


class TestRegistry(unittest.TestCase):
    def setUp(self):
        self._orig_file = team.TEAM_MODELS_FILE
        self._orig_runs = team.RUNS_DIR

    def tearDown(self):
        team.TEAM_MODELS_FILE = self._orig_file
        team.RUNS_DIR = self._orig_runs

    def test_presets_present(self):
        ids = [m["id"] for m in team.list_models()]
        self.assertIn("local-qwen", ids)
        self.assertIn("cloud-gpt", ids)

    def test_freetoken_preset_env_driven(self):
        saved = {k: os.environ.get(k) for k in ("FREETOKEN_BASE_URL", "FREETOKEN_MODEL")}
        try:
            # unset -> defaults
            os.environ.pop("FREETOKEN_BASE_URL", None)
            os.environ.pop("FREETOKEN_MODEL", None)
            m = {x["id"]: x for x in team.list_models()}["freetoken"]
            self.assertEqual(m["base_url"], "http://127.0.0.1:1919/v1")
            self.assertEqual(m["model"], "Qwen3.6-35B-A3B")
            # set -> reflected (trailing slash stripped), label carries the model
            os.environ["FREETOKEN_BASE_URL"] = "http://10.0.0.5:1919/v1/"
            os.environ["FREETOKEN_MODEL"] = "GLM-5.2"
            m = {x["id"]: x for x in team.list_models()}["freetoken"]
            self.assertEqual(m["base_url"], "http://10.0.0.5:1919/v1")
            self.assertEqual(m["model"], "GLM-5.2")
            self.assertIn("GLM-5.2", m["label"])
            # empty/whitespace -> fall back to defaults (defensive)
            os.environ["FREETOKEN_BASE_URL"] = "   "
            os.environ["FREETOKEN_MODEL"] = ""
            m = {x["id"]: x for x in team.list_models()}["freetoken"]
            self.assertEqual(m["base_url"], "http://127.0.0.1:1919/v1")
            self.assertEqual(m["model"], "Qwen3.6-35B-A3B")
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_add_model_rejects_non_http_base_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            team.TEAM_MODELS_FILE = Path(tmp) / "team_models.json"
            with self.assertRaises(ValueError):
                team.add_model({"id": "x", "base_url": "ftp://host/v1", "model": "m"})
            with self.assertRaises(ValueError):
                team.add_model({"id": "x", "base_url": "file:///etc/passwd", "model": "m"})

    def test_ollama_preset_env_driven(self):
        saved = {k: os.environ.get(k) for k in ("OLLAMA_BASE_URL", "OLLAMA_MODEL")}
        try:
            os.environ.pop("OLLAMA_BASE_URL", None)
            os.environ.pop("OLLAMA_MODEL", None)
            m = {x["id"]: x for x in team.list_models()}["ollama"]
            self.assertEqual(m["base_url"], "http://127.0.0.1:11434/v1")
            self.assertEqual(m["model"], "qwen3.5:27b")
            os.environ["OLLAMA_BASE_URL"] = "http://127.0.0.1:11434/v1/"
            os.environ["OLLAMA_MODEL"] = "qwen3:30b-a3b"
            m = {x["id"]: x for x in team.list_models()}["ollama"]
            self.assertEqual(m["base_url"], "http://127.0.0.1:11434/v1")
            self.assertEqual(m["model"], "qwen3:30b-a3b")
            self.assertIn("qwen3:30b-a3b", m["label"])
            os.environ["OLLAMA_BASE_URL"] = "   "
            os.environ["OLLAMA_MODEL"] = ""
            m = {x["id"]: x for x in team.list_models()}["ollama"]
            self.assertEqual(m["base_url"], "http://127.0.0.1:11434/v1")
            self.assertEqual(m["model"], "qwen3.5:27b")
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_custom_roundtrip_and_get(self):
        with tempfile.TemporaryDirectory() as tmp:
            team.TEAM_MODELS_FILE = Path(tmp) / "team_models.json"
            entry = team.add_model({"id": "fable-52", "label": "Fable 5.2",
                                    "base_url": "https://openrouter.ai/api/v1",
                                    "model": "vendor/fable-5.2",
                                    "api_key_env": "OPENROUTER_API_KEY"})
            self.assertEqual(entry["kind"], "custom")
            self.assertIn("fable-52", [m["id"] for m in team.list_models()])
            self.assertEqual(team.get_model("fable-52")["model"], "vendor/fable-5.2")
            raw = team.TEAM_MODELS_FILE.read_text()
            self.assertIn('"api_key_env": "OPENROUTER_API_KEY"', raw)  # env NAME stored
            self.assertNotIn("sk-", raw)                               # no secret material

    def test_add_model_requires_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            team.TEAM_MODELS_FILE = Path(tmp) / "team_models.json"
            with self.assertRaises(ValueError):
                team.add_model({})
            with self.assertRaises(ValueError):
                team.add_model({"id": "x"})
            with self.assertRaises(ValueError):
                team.add_model({"id": "x", "base_url": "b"})
            ok = team.add_model({"id": "x", "base_url": "http://h/v1", "model": "m"})
            self.assertEqual(ok["id"], "x")

    def test_get_model_unknown_raises(self):
        with self.assertRaises(KeyError):
            team.get_model("does-not-exist")


class TestRunTeam(unittest.TestCase):
    def setUp(self):
        self._orig_runs = team.RUNS_DIR

    def tearDown(self):
        team.RUNS_DIR = self._orig_runs

    def _fake_http(self, calls):
        def fake(url, payload, headers, timeout):
            calls.append({"url": url, "payload": payload})
            last = payload["messages"][-1]["content"]
            return _ok_response(content=f"resp:{last[:20]}", model=payload["model"])
        return fake

    def test_two_agents_one_round_plus_synthesis(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            team.RUNS_DIR = Path(tmp)
            res = team.run_team({
                "starting_prompt": "Build the best X.",
                "agents": [
                    {"name": "A", "role": "builder", "model_id": "local-qwen"},
                    {"name": "B", "role": "critic", "model_id": "cloud-gpt"},
                ],
                "rounds": 1,
            }, http=self._fake_http(calls))
            self.assertEqual(len(calls), 3)             # 2 agent turns + 1 synthesis
            self.assertEqual([t["agent"] for t in res["transcript"]], ["A", "B"])
            self.assertTrue(res["final_solution"].startswith("resp:"))
            self.assertEqual(res["synthesis_model"], "openai/gpt-5.5")  # last agent's model
            self.assertTrue(Path(res["files"]["team_json"]).exists())
            self.assertTrue(Path(res["files"]["solution_md"]).exists())

    def test_multiple_rounds(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            team.RUNS_DIR = Path(tmp)
            res = team.run_team({
                "starting_prompt": "Go.",
                "agents": [{"name": "A", "role": "r", "model_id": "local-qwen"},
                           {"name": "B", "role": "r", "model_id": "cloud-gpt"}],
                "rounds": 2,
            }, http=self._fake_http(calls))
        self.assertEqual(len(res["transcript"]), 4)     # 2 rounds x 2 agents
        self.assertEqual(len(calls), 5)                 # + synthesis

    def test_explicit_synthesis_model(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            team.RUNS_DIR = Path(tmp)
            res = team.run_team({
                "starting_prompt": "Go.",
                "agents": [{"name": "A", "role": "r", "model_id": "local-qwen"}],
                "rounds": 1, "synthesis_model_id": "cloud-gemini",
            }, http=self._fake_http(calls))
        self.assertEqual(res["synthesis_model"], "google/gemini-3.1-pro-preview")

    def test_missing_prompt_raises(self):
        with self.assertRaises(ValueError):
            team.run_team({"agents": [{"name": "A", "model_id": "local-qwen"}]},
                          http=lambda *a, **k: _ok_response())

    def test_no_valid_agents_raises(self):
        with self.assertRaises(ValueError):
            team.run_team({"starting_prompt": "x", "agents": [{"name": "", "model_id": ""}]},
                          http=lambda *a, **k: _ok_response())

    def test_skips_incomplete_agents(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            team.RUNS_DIR = Path(tmp)
            res = team.run_team({
                "starting_prompt": "x",
                "agents": [{"name": "A", "model_id": "local-qwen"},
                           {"name": "", "model_id": "cloud-gpt"},
                           {"name": "C", "model_id": ""}],
            }, http=self._fake_http(calls))
        self.assertEqual([t["agent"] for t in res["transcript"]], ["A"])

    def test_failed_agent_does_not_abort_team(self):
        def fake(url, payload, headers, timeout):
            if payload["model"] == "openai/gpt-5.5":      # the "Bad" agent's model
                raise RuntimeError("HTTP 500 from cloud")
            return _ok_response(content="ok-content", model=payload["model"])
        with tempfile.TemporaryDirectory() as tmp:
            team.RUNS_DIR = Path(tmp)
            res = team.run_team({
                "starting_prompt": "Go.",
                "agents": [
                    {"name": "Good", "role": "r", "model_id": "local-qwen"},
                    {"name": "Bad", "role": "r", "model_id": "cloud-gpt"},   # raises
                ],
                "rounds": 1, "synthesis_model_id": "local-qwen",
            }, http=fake)
        by_agent = {t["agent"]: t for t in res["transcript"]}
        self.assertEqual(by_agent["Good"]["status"], "ok")
        self.assertEqual(by_agent["Bad"]["status"], "error")
        self.assertIn("konnte nicht antworten", by_agent["Bad"]["content"])
        self.assertTrue(res["final_solution"].startswith("ok-content"))  # synthesis still ran

    def test_garbage_numeric_params_do_not_crash(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            team.RUNS_DIR = Path(tmp)
            res = team.run_team({
                "starting_prompt": "Go.",
                "agents": [{"name": "A", "role": "r", "model_id": "local-qwen"}],
                "rounds": "abc", "temperature": "xyz", "max_tokens": "!!",
            }, http=self._fake_http(calls))
        self.assertEqual(res["rounds"], 1)          # fell back to default
        self.assertEqual(len(calls), 2)             # 1 agent turn + 1 synthesis


class TestCors(unittest.TestCase):
    def test_only_local_frontend_origin_allowed(self):
        from fastapi.testclient import TestClient
        from qvc_web.backend import main
        client = TestClient(main.app)
        # A drive-by origin must never be reflected (the point of the CORS fix).
        bad = client.get("/api/models", headers={"Origin": "http://evil.example"})
        self.assertNotIn("access-control-allow-origin", bad.headers)
        if not os.getenv("QVC_WEB_CORS_ORIGINS"):
            ok = client.get("/api/models", headers={"Origin": "http://localhost:3000"})
            self.assertEqual(ok.headers.get("access-control-allow-origin"), "http://localhost:3000")


if __name__ == "__main__":
    unittest.main()
