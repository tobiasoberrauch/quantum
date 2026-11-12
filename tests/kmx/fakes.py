"""Netzwerkfreie Ersatzobjekte für den LLM-Client."""

import json


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class FakeClient:
    """Ersatz fuer LLMClient: spielt vorbereitete Antworten ab."""

    def __init__(self, replies):
        self.replies, self.calls, self.seen = list(replies), 0, []

    def exhausted(self):
        return not self.replies

    def chat(self, model, messages, tools=None):
        self.calls += 1
        self.seen.append([dict(m) for m in messages])
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def tool_call(name, raw=None, **args):
    return {
        "content": None,
        "tool_calls": [
            {
                "id": f"call_{name}",
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": raw if raw is not None else json.dumps(args),
                },
            }
        ],
    }
