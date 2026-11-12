"""JSON-Modus für Modelle ohne Tool-Calling: ein Fenster je Anfrage, Fakten und
eine Nachbesserung per Gegenbeispiel.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence

from kmx.agent.client import ChatMessage, LLMClient, LLMError
from kmx.agent.workbench import HOTSPOT_LIMIT_MAX, Workbench
from kmx.prompts import load_prompt
from kmx.simulator import push_depths

WindowSpan = tuple[int, int]  # Fenster [start, ende], beide Grenzen eingeschlossen
# Antwort je Fenstertext: True = Rewrite angenommen, False = nichts brauchbares
JsonMemo = dict[tuple[str, ...], bool]

JSON_OPS = ("X", "CX", "CCX", "SWAP", "CSWAP", "Z", "CZ", "CCZ", "Z_POW")
# so viele Hotspots, wie find_hotspots herausgibt
JSON_HOTSPOT_LIMIT = HOTSPOT_LIMIT_MAX
JSON_FACTS_MAX = 30
JSON_ATTEMPTS = 2  # erste Antwort plus genau eine Nachbesserung
JSON_RATIONALE = "LLM im JSON-Modus"
# Anfrage je Fenster; Platzhalter {rot:.1f}, {facts}, {block}
JSON_PROMPT = load_prompt("json_window.txt")
JSON_RETRY_TEMPLATE = "Abgelehnt: {reason} Korrigiere gezielt oder antworte mit []."
JSON_NO_FACTS = "(keine besonderen)"
JSON_DEFAULT_MAX_SPAN = 60  # längstes Fenster, das der JSON-Modus anfragt


def json_array(text: str) -> list[str] | None:
    """Holt ein JSON-Array aus einer Modellantwort (auch wenn Prosa oder
    Code-Zäune drumherum stehen)."""
    for chunk in [text.strip()] + re.findall(r"\[[^\[\]]*\]", text, re.DOTALL):
        try:
            val = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        if isinstance(val, list) and all(isinstance(x, str) for x in val):
            return [x.strip() for x in val if x.strip()]
    return None


def json_windows(
    wb: Workbench, max_span: int = JSON_DEFAULT_MAX_SPAN
) -> list[WindowSpan]:
    """Kandidatenfenster für den JSON-Modus: CCX-Gruppen auf einem Ziel und gleiche
    CCX-Paare, nur unbedingte Gatter; absteigend sortiert und überlappungsfrei, damit
    angenommene Rewrites spätere Indizes nicht verschieben.
    """
    ops = wb.session.ops
    depths = push_depths(ops)
    raw = [
        (h["ccx_indizes"][0], h["ccx_indizes"][0] + h["spanne"] - 1)
        for h in wb.find_hotspots("runs", JSON_HOTSPOT_LIMIT)["liste"]
    ]
    raw += [
        (h["start"], h["ende"])
        for h in wb.find_hotspots("pairs", JSON_HOTSPOT_LIMIT)["liste"]
    ]
    out: list[WindowSpan] = []
    for a, b in sorted(set(raw), reverse=True):
        if b - a > max_span or (out and b >= out[-1][0]):
            continue
        if all(
            ops[i].name in JSON_OPS and ops[i].cond is None and depths[i] == 0
            for i in range(a, b + 1)
        ):
            out.append((a, b))
    return out


def _json_window_prompt(
    wb: Workbench, start: int, end: int, window: Sequence[str]
) -> str:
    """Anfrage für ein Fenster: Kostenmodell, Regeln, Fakten am
    Fenstereingang und der Block selbst."""
    facts = wb.analyze_window(start, end).get("fakten_am_eingang") or [JSON_NO_FACTS]
    return JSON_PROMPT.format(
        rot=wb.session.opts.rot_weight,
        facts="\n".join(f"- {f}" for f in facts[:JSON_FACTS_MAX]),
        block="\n".join(window),
    )


def _json_rewrite_window(
    wb: Workbench,
    client: LLMClient,
    model: str,
    start: int,
    end: int,
    window: Sequence[str],
    log: Callable[[str], None],
) -> bool | None:
    """Fragt das Modell nach einem Ersatz für ein Fenster; bei Ablehnung gibt es eine
    Nachbesserung mit dem Gegenbeispiel des Verifiers. True, wenn ein Rewrite angenommen
    wurde; None bei einem LLM-Fehler.
    """
    messages: list[ChatMessage] = [
        {"role": "user", "content": _json_window_prompt(wb, start, end, window)}
    ]
    for _ in range(JSON_ATTEMPTS):
        try:
            content = client.chat(model, messages).get("content") or ""
        except LLMError as e:
            log(f"  {e}")
            # nicht memoisieren: das nächste Modell darf es erneut versuchen
            return None
        cand = json_array(content)
        if not cand:
            return False
        res = wb.propose_rewrite(start, end, cand, JSON_RATIONALE)
        if res.get("accepted"):
            return True
        messages += [
            {"role": "assistant", "content": content},
            {
                "role": "user",
                "content": JSON_RETRY_TEMPLATE.format(reason=res.get("reason")),
            },
        ]
    return False


def run_json_llm(
    wb: Workbench,
    client: LLMClient,
    model: str,
    log: Callable[[str], None] = print,
    memo: JsonMemo | None = None,
) -> int:
    """Ein-Schuss-Modus für Modelle ohne Tool-Calling: je Fenster eine Anfrage mit den
    Fakten des Fensters, bei Ablehnung genau eine Nachbesserung mit dem Gegenbeispiel
    des Verifiers. Antworten werden memoisiert.
    """
    memo = {} if memo is None else memo
    accepted = 0
    for a, b in json_windows(wb):
        if client.exhausted():
            break
        window = [o.fmt() for o in wb.session.ops[a : b + 1]]
        if tuple(window) in memo:
            continue
        done = _json_rewrite_window(wb, client, model, a, b, window, log)
        if done is None:
            continue
        accepted += done
        memo[tuple(window)] = done
    log(
        f"  {model} (JSON-Modus): {accepted} verifizierte Rewrites, {client.calls} "
        "LLM-Aufrufe insgesamt"
    )
    return accepted
