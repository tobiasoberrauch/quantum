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
