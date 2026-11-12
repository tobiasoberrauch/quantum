"""LLM-Client, Tool-Calling-Agent und JSON-Modus ohne Netzwerk (kmx.agent)."""

import io
import json
import socket
import time
import urllib.error
import urllib.request

import kmx
import kmx.agent.client
import kmx.agent.json_mode
import kmx.agent.relay
from tests.kmx.fakes import (
    FakeClient,
    FakeResponse,
    tool_call,
)
from tests.kmx.helpers import (
    NHEAD,
    _network_forbidden,
    env,
    make_wb,
    no_network,
    patched,
    quiet,
    raises,
    toffoli,
)


# Netzwerk
def test_json_array_extracts_string_arrays():
    assert kmx.agent.json_mode.json_array('["CX q0 q1", "X q0"]') == [
        "CX q0 q1",
        "X q0",
    ]
    assert kmx.agent.json_mode.json_array('Text ```json\n["CX q0 q1"]\n```') == [
        "CX q0 q1"
    ]
    assert kmx.agent.json_mode.json_array('Erst das: ["  X q0  ", ""] fertig.') == [
        "X q0"
    ]
    assert kmx.agent.json_mode.json_array('nimm ["A"] oder ["B"]') == ["A"]
    assert (
        kmx.agent.json_mode.json_array("[]") == []
        and kmx.agent.json_mode.json_array("Geht nicht: []") == []
    )


def test_json_array_rejects_everything_else():
    for text in ("", "keine Liste", "[1, 2]", '["x", 3]', '["unterminated', "[[1]]"):
        assert kmx.agent.json_mode.json_array(text) is None, text


def test_llm_client_budget_is_enforced_without_network():
    seen = []

    def fake_urlopen(req, timeout=None):
        seen.append(json.loads(req.data.decode("utf-8")))
        return FakeResponse(
            {"choices": [{"message": {"role": "assistant", "content": "hi"}}]}
        )

    with (
        env(),
        patched(socket, "create_connection", _network_forbidden),
        patched(urllib.request, "urlopen", fake_urlopen),
    ):
        client = kmx.LLMClient(
            api_url="http://127.0.0.1:9/v1/chat/completions", api_key="k", max_calls=2
        )
        first = client.chat("m", [{"role": "user", "content": "x"}], tools=kmx.TOOLS)
        second = client.chat("m", [{"role": "user", "content": "y"}])
        assert (
            not client.local_default
            and client.temperature is None
            and client.default_models() == []
        )
        assert (
            first == {"role": "assistant", "content": "hi"}
            and second["content"] == "hi"
        )
        assert client.exhausted() and client.calls == 2
        e = raises(kmx.LLMError, client.chat, "m", [])
        assert "Budget" in str(e) and len(seen) == 2 and not client.dead
        assert (
            seen[0]["tool_choice"] == "auto"
            and "tools" not in seen[1]
            and "temperature" not in seen[0]
        )
        # fremdem Endpunkt wird nichts untergeschoben
        assert "chat_template_kwargs" not in seen[0]


def test_llm_client_zero_budget_never_calls_out():
    with env(LLM_MAX_CALLS="0"), no_network():
        client = kmx.LLMClient(api_url="http://127.0.0.1:9/x")
        assert client.max_calls == 0 and client.exhausted()
        assert "Budget" in str(raises(kmx.LLMError, client.chat, "m", []))
        assert client.calls == 0


def test_llm_client_dead_endpoint_trips_circuit_breaker():
    attempts = []

    def refused(req, timeout=None):
        attempts.append(req.full_url)
        raise urllib.error.URLError("Connection refused")

    with (
        env(),
        patched(urllib.request, "urlopen", refused),
        patched(time, "sleep", _network_forbidden),
    ):
        client = kmx.LLMClient(api_url="http://127.0.0.1:9/x", max_calls=10)
        e1 = raises(kmx.LLMError, client.chat, "m", [])
        e2 = raises(kmx.LLMError, client.chat, "m", [])
        assert "nicht erreichbar" in str(e1) and "nicht erreichbar" in str(e2)
        assert (
            client.dead
            and client.exhausted()
            and len(attempts) == 1
            and client.calls == 1
        )


def test_llm_client_reachable_probe_marks_client_dead():
    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    targets = []

    def refuse(addr, timeout=None):
        targets.append(addr)
        raise ConnectionRefusedError("nope")

    with env():
        down = kmx.LLMClient(api_url="https://example.invalid/v1/chat")
        up = kmx.LLMClient()
        with patched(socket, "create_connection", refuse):
            assert down.reachable() is False and down.dead and down.exhausted()
        with (
            patched(socket, "create_connection", lambda addr, timeout=None: Conn()),
            patched(urllib.request, "urlopen", _network_forbidden),
        ):
            assert up.reachable() is True and not up.dead
        assert targets == [("example.invalid", 443)]
        assert (
            up.local_default
            and up.api_url == kmx.agent.client.LOCAL_LLM_URL
            and up.default_models() == [kmx.agent.client.LOCAL_LLM_MODEL]
        )
        assert up.temperature == 0.1 and up.extra_body == {
            "chat_template_kwargs": {"enable_thinking": False}
        }


def test_llm_client_non_retryable_http_error_reports_status_code():
    def bad_request(req, timeout=None):
        raise urllib.error.HTTPError(
            req.full_url,
            400,
            "Bad Request",
            {},
            io.BytesIO(b'{"error": "tools unsupported"}'),
        )

    with (
        env(),
        patched(urllib.request, "urlopen", bad_request),
        patched(time, "sleep", _network_forbidden),
    ):
        client = kmx.LLMClient(api_url="http://127.0.0.1:9/x", max_calls=3)
        e = raises(kmx.LLMError, client.chat, "m", [])
        assert e.code == 400 and "tools unsupported" in str(e) and not client.dead


def test_run_agent_applies_verified_tool_calls_from_fake_model():
    wb = make_wb()
    client = FakeClient(
        [
            tool_call(
                "propose_rewrite",
                start=NHEAD,
                end=NHEAD + 2,
                new_lines=["CX q0 q8", "X q0"],
            ),
            tool_call("propose_rewrite", raw="{kaputt"),
            tool_call(
                "propose_rewrite",
                start=NHEAD,
                end=NHEAD + 2,
                new_lines=["CX q1 q8", "X q0"],
            ),
            tool_call("finish", summary="erledigt"),
        ]
    )
    no_tools = kmx.run_agent(wb, client, ["fake"], steps=10, relay_rounds=1, log=quiet)
    tool_msgs = [m["content"] for m in client.seen[-1] if m.get("role") == "tool"]
    assert (
        no_tools == []
        and wb.accepted == 1
        and wb.finished == "erledigt"
        and client.calls == 4
    )
    assert toffoli(wb.session.ops) == 0 and wb.full_check()["ok"]
    assert (
        '"accepted": false' in tool_msgs[0]
        and "Argumente nicht lesbar" in tool_msgs[1]
        and '"accepted": true' in tool_msgs[2]
    )


def test_run_agent_reports_models_without_tool_calling():
    wb = make_wb()
    prose = kmx.run_agent(
        wb,
        FakeClient([{"content": "Ich würde CCX streichen."}]),
        ["plauderer"],
        5,
        1,
        log=quiet,
    )
    refused = kmx.run_agent(
        wb, FakeClient([kmx.LLMError("HTTP 400", 400)]), ["alt"], 5, 1, log=quiet
    )
    flaky = kmx.run_agent(
        wb, FakeClient([kmx.LLMError("HTTP 500", 500)]), ["wackelig"], 5, 1, log=quiet
    )
    assert (
        prose == ["plauderer"]
        and refused == ["alt"]
        and flaky == []
        and wb.accepted == 0
    )


def test_run_json_llm_accepts_verified_answer_and_retries_once_with_counterexample():
    good, bad = '```json\n["CX q1 q8", "X q0"]\n```', '["CX q0 q8", "X q0"]'
    wb = make_wb()
    assert kmx.json_windows(wb) == [(NHEAD, NHEAD + 2)]
    client = FakeClient([{"content": bad}, {"content": good}])
    accepted = kmx.run_json_llm(wb, client, "fake", log=quiet)
    assert accepted == 1 and client.calls == 2 and toffoli(wb.session.ops) == 0
    assert "Abgelehnt: Verifier-Ablehnung" in client.seen[1][-1]["content"]
    assert (
        "q8" in client.seen[0][0]["content"]
        and "CCX q0 q1 q8" in client.seen[0][0]["content"]
    )

    wb2, memo = make_wb(), {}
    stubborn = FakeClient([{"content": bad}, {"content": "[]"}, {"content": good}])
    assert (
        kmx.run_json_llm(wb2, stubborn, "fake", log=quiet, memo=memo) == 0
        and toffoli(wb2.session.ops) == 2
    )
    # memoisiert
    assert (
        kmx.run_json_llm(wb2, stubborn, "fake", log=quiet, memo=memo) == 0
        and stubborn.calls == 2
    )
    assert list(memo.values()) == [False]


def test_trim_history_shortens_only_old_tool_results():
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
    msgs += [
        {"role": "tool", "tool_call_id": str(i), "content": "x" * 1000}
        for i in range(10)
    ]
    kmx.agent.relay._trim_history(msgs, 3000)
    # die letzten sechs bleiben
    assert [len(m["content"]) for m in msgs[-6:]] == [1000] * 6
    assert (
        msgs[2]["content"] == '{"hinweis": "älteres Tool-Ergebnis gekürzt"}'
        and msgs[0]["content"] == "s"
    )
    untouched = [{"role": "tool", "content": "x" * 1000} for _ in range(10)]
    kmx.agent.relay._trim_history(untouched, 10**6)
    assert all(len(m["content"]) == 1000 for m in untouched)


def test_tool_call_with_already_parsed_arguments_is_answered():
    # Regression: manche Server liefern function.arguments als Objekt statt als
    # JSON-String -> TypeError-Absturz.
    wb = make_wb()
    _, msg = kmx.agent.relay._answer_tool_call(
        wb,
        {
            "id": "1",
            "function": {"name": "read_lines", "arguments": {"start": 0, "count": 2}},
        },
    )
    assert "fehler" not in json.loads(msg["content"])


def test_json_mode_llm_error_does_not_memoise_window():
    # Regression: ein transienter LLM-Fehler sperrte das Fenster auch fuer alle
    # spaeteren Modelle.
    class BrokenClient:
        calls = 0

        def exhausted(self):
            return self.calls >= 3

        def chat(self, model, messages, tools=None):
            self.calls += 1
            raise kmx.LLMError("HTTP 503")

    wb = make_wb(["CCX q0 q1 q8", "CX q2 q3", "CCX q0 q1 q8"])
    memo = {}
    assert kmx.run_json_llm(wb, BrokenClient(), "m", quiet, memo) == 0
    assert memo == {}
