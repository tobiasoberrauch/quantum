"""Teams des Labors (Forscher mit eigener Weltsicht, Kritiker, Direktor): Prompts aus
`kmx/prompts/lab_*.txt` und das Bereinigen ihrer Antworten zu Vorschlägen.

Forscher schlagen vor; entschieden wird nur durch den Richter. Ein Statusfeld in einer
Antwort wird verworfen, Kennungen und Texte werden bereinigt.
"""

from __future__ import annotations

import itertools
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from kmx.lab.claims import MAX_LIST_ITEMS, safe_id_list, safe_text, safe_text_list
from kmx.lab.judge import CANDIDATE_KINDS, KIND_GENERATOR, MAX_GENERATOR_CHARS
from kmx.prompts import load_prompt

RESEARCH_TEAMS = ("numerical", "reversible", "phase", "architecture")
CRITIC, DIRECTOR = "critic", "director"
PROMPT_FILES = {
    "director": "lab_director.txt",
    "numerical": "lab_numerical.txt",
    "reversible": "lab_reversible.txt",
    "phase": "lab_phase.txt",
    "architecture": "lab_architecture.txt",
    "critic": "lab_critic.txt",
}
FORMAT_PROMPT = "lab_kmx_format.txt"
GENERATOR_START, GENERATOR_END = "<<<GENERATOR", "GENERATOR>>>"
MAX_CLAIMS_PER_PROPOSAL = 5
MAX_KMX_SOURCE_CHARS = 4_000_000
MIN_VETO_REASON_CHARS = 15
# Parameterraster eines Generators (deterministische Suche ohne LLM)
MAX_PARAM_KEYS, MAX_PARAM_VALUES, MAX_VARIANTS = 4, 8, 16
MAX_PARAM_TEXT_CHARS = 64
_PARAM_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,31}")
ParamValue = int | float | str | bool
ParamGrid = dict[str, list[ParamValue]]


def system_prompt(role: str) -> str:
    """Systemprompt einer Rolle (nur bekannte Rollen); Forschungsteams und Kritiker
    bekommen den .kmx/Op-Spickzettel (Format, API, Beispielgenerator) dazu."""
    text = load_prompt(PROMPT_FILES[role])
    if role in RESEARCH_TEAMS or role == CRITIC:
        text += load_prompt(FORMAT_PROMPT)
    return text


def example_generator() -> str:
    """Der Beispielgenerator aus dem Spickzettel (im Test gegen den Richter
    geprüft)."""
    text = load_prompt(FORMAT_PROMPT)
    start = text.index(GENERATOR_START) + len(GENERATOR_START)
    return text[start : text.index(GENERATOR_END)].strip("\n") + "\n"


def parse_team_list(raw: str | None) -> tuple[str, ...]:
    """'numerical,phase' -> gültige Forschungsteams; unbekannte Namen: ValueError."""
    if not raw:
        return RESEARCH_TEAMS
    names = tuple(t.strip() for t in raw.split(",") if t.strip())
    unknown = [t for t in names if t not in RESEARCH_TEAMS]
    if unknown:
        raise ValueError(
            f"unbekannte Teams {unknown}; erlaubt: {', '.join(RESEARCH_TEAMS)}"
        )
    return names


@dataclass
class ClaimDraft:
    claim: str
    assumptions: list[str]
    supersedes: list[str]


@dataclass
class CandidateDraft:
    kind: str
    source: str
    rationale: str
    params: ParamGrid | None = None  # nur bei Generatoren: Raster für params.json


@dataclass
class Proposal:
    """Bereinigte Antwort eines Forschungsteams."""

    team: str
    claims: list[ClaimDraft] = field(default_factory=list)
    candidate: CandidateDraft | None = None
    notes: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def _claims(raw: object, known: set[str], problems: list[str]) -> list[ClaimDraft]:
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw[:MAX_CLAIMS_PER_PROPOSAL]:
        if isinstance(item, str):
            item = {"claim": item}
        if not isinstance(item, dict):
            continue
        if "status" in item:
            problems.append("Statusfeld ignoriert (nur der Richter entscheidet)")
        text = safe_text(item.get("claim"))
        if text:
            out.append(
                ClaimDraft(
                    text,
                    safe_text_list(item.get("assumptions")),
                    safe_id_list(item.get("supersedes"), known),
                )
            )
    return out


def _candidate(raw: object, problems: list[str]) -> CandidateDraft | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        problems.append("candidate ist kein Objekt")
        return None
    kind, source = raw.get("kind"), raw.get("source")
    if kind not in CANDIDATE_KINDS or not isinstance(source, str) or not source.strip():
        problems.append(f"candidate verworfen (kind={kind!r}, source fehlt/leer)")
        return None
    limit = MAX_GENERATOR_CHARS if kind == "generator" else MAX_KMX_SOURCE_CHARS
    if len(source) > limit:
        problems.append(f"candidate zu lang ({len(source)} > {limit} Zeichen)")
        return None
    params = _candidate_params(kind, raw.get("params"), problems)
    return CandidateDraft(kind, source, safe_text(raw.get("rationale")), params)


def _param_value_ok(v: object) -> bool:
    """JSON-Skalar: Zahl (endlich), Wahrheitswert oder kurzer Text ohne
    Steuerzeichen."""
    if isinstance(v, bool | int):
        return True
    if isinstance(v, float):
        return math.isfinite(v)
    return (
        isinstance(v, str)
        and len(v) <= MAX_PARAM_TEXT_CHARS
        and safe_text(v, MAX_PARAM_TEXT_CHARS) == v
    )


def parse_param_grid(raw: object) -> tuple[ParamGrid | None, str]:
    """(Raster, Problem): höchstens MAX_PARAM_KEYS Bezeichner mit je 1 bis
    MAX_PARAM_VALUES Skalaren und höchstens MAX_VARIANTS Varianten; sonst kein
    Raster und eine Begründung."""
    if not isinstance(raw, dict) or not raw:
        return None, "kein nicht-leeres Objekt"
    if len(raw) > MAX_PARAM_KEYS:
        return None, f"mehr als {MAX_PARAM_KEYS} Schlüssel"
    grid: ParamGrid = {}
    for key, values in raw.items():
        if not isinstance(key, str) or not _PARAM_KEY.fullmatch(key):
            return None, "Schlüssel ist kein Bezeichner"
        if not isinstance(values, list) or not 1 <= len(values) <= MAX_PARAM_VALUES:
            return None, f"je Schlüssel 1 bis {MAX_PARAM_VALUES} Werte als Liste"
        if not all(_param_value_ok(v) for v in values):
            return None, "Werte müssen JSON-Skalare sein (Zahl, Text, bool)"
        grid[key] = list(values)
    if math.prod(len(v) for v in grid.values()) > MAX_VARIANTS:
        return None, f"mehr als {MAX_VARIANTS} Varianten"
    return grid, ""


def _candidate_params(kind: str, raw: object, problems: list[str]) -> ParamGrid | None:
    if raw is None:
        return None
    if kind != KIND_GENERATOR:
        problems.append("params verworfen: nur für kind 'generator'")
        return None
    grid, problem = parse_param_grid(raw)
    if grid is None:
        problems.append(f"params verworfen: {problem}")
    return grid


def param_variants(grid: ParamGrid) -> list[dict[str, ParamValue]]:
    """Kartesisches Produkt in fester Reihenfolge (Schlüssel wie angegeben, der
    letzte läuft am schnellsten)."""
    keys = list(grid)
    return [
        dict(zip(keys, combo, strict=True))
        for combo in itertools.product(*(grid[k] for k in keys))
    ]


def parse_proposal(team: str, obj: dict[str, Any], known: set[str]) -> Proposal:
    """Bereinigt eine Team-Antwort (Schema in den Prompts)."""
    problems: list[str] = []
    if "status" in obj:
        problems.append("Statusfeld ignoriert (nur der Richter entscheidet)")
    return Proposal(
        team,
        _claims(obj.get("claims"), known, problems),
        _candidate(obj.get("candidate"), problems),
        safe_text_list(obj.get("notes")),
        problems,
    )


@dataclass
class Critique:
    veto: bool
    reason: str
    counterexample: str
    ignored_veto: bool = False
    notes: list[str] = field(default_factory=list)


def parse_critique(obj: dict[str, Any]) -> Critique:
    """Ein Veto zählt nur mit konkreter Begründung (MIN_VETO_REASON_CHARS)."""
    reason = safe_text(obj.get("reason"))
    counter = safe_text(obj.get("counterexample"))
    wants_veto = obj.get("veto") is True
    concrete = len(reason) >= MIN_VETO_REASON_CHARS
    return Critique(
        wants_veto and concrete,
        reason,
        counter,
        wants_veto and not concrete,
        safe_text_list(obj.get("notes")),
    )


def parse_focus(obj: dict[str, Any], teams: tuple[str, ...]) -> dict[str, str]:
    """Schwerpunkte des Direktors je Team (fehlende Teams: leer)."""
    raw = obj.get("focus")
    raw = raw if isinstance(raw, dict) else {}
    return {t: safe_text(raw.get(t), 800) for t in teams}


def _supports(
    raw: object, known: set[str], aliases: Mapping[str, list[str]]
) -> tuple[list[str], list[str]]:
    """(Kennungen, verworfene Angaben): Teamnamen werden auf die Behauptungen des
    Teams in dieser Runde abgebildet, Unbekanntes wird verworfen (nicht still)."""
    items = raw[:MAX_LIST_ITEMS] if isinstance(raw, list) else []
    ids: list[str] = []
    dropped: list[str] = []
    for item in items:
        name = safe_text(item, 64)
        if name in known:
            ids.append(name)
        elif name in aliases:
            ids += aliases[name]
        elif name:
            dropped.append(name)
    return list(dict.fromkeys(ids))[:MAX_LIST_ITEMS], dropped


def parse_insights(
    obj: dict[str, Any],
    known: set[str],
    aliases: Mapping[str, list[str]] | None = None,
) -> list[tuple[str, list[str], list[str]]]:
    """Konferenz-Einsichten: (Text, gestützte Kennungen, verworfene Angaben)."""
    raw = obj.get("insights")
    out = []
    for item in raw[:MAX_CLAIMS_PER_PROPOSAL] if isinstance(raw, list) else []:
        if isinstance(item, str):
            item = {"insight": item}
        if isinstance(item, dict):
            text = safe_text(item.get("insight"))
            if text:
                ids, dropped = _supports(item.get("supports"), known, aliases or {})
                out.append((text, ids, dropped))
    return out
