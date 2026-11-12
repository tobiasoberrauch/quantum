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


class RoutingFakeClient:
    """Ersatz fuer LLMClient bei parallelen Aufrufen: waehlt die Antwort nach der
    Rolle (erstes Wort-Merkmal im Systemprompt), nicht nach der Reihenfolge.

    `routes` bildet einen Textausschnitt des Systemprompts auf eine Liste von
    Antworten ab (Text, dict mit "content" oder Exception); die letzte wiederholt
    sich. Threadsicher genug fuer die Tests (Listen werden nur gelesen)."""

    def __init__(self, routes, reachable=True):
        import threading

        self.routes, self._reachable = routes, reachable
        self.calls, self.seen, self.dead = 0, [], False
        self.api_url = "http://stub.invalid/v1/chat/completions"
        self._lock, self._count = threading.Lock(), {}

    def reachable(self):
        return self._reachable

    def default_models(self):
        return ["stub-model"]

    def chat(self, model, messages, tools=None):
        system = messages[0]["content"]
        key = next((k for k in self.routes if k in system), None)
        if key is None:
            raise AssertionError("keine Route fuer Systemprompt: " + system[:80])
        with self._lock:
            self.calls += 1
            self.seen.append((key, [dict(m) for m in messages]))
            i = self._count.get(key, 0)
            self._count[key] = i + 1
        replies = self.routes[key]
        reply = replies[min(i, len(replies) - 1)]
        if isinstance(reply, Exception):
            raise reply
        return reply if isinstance(reply, dict) else {"content": reply}
