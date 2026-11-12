"""Behauptungen (Claims) des Forschungslabors: die vier Status, das Bereinigen von
Eingaben aus Modellantworten und die Ableitung des Status aus Prüfer-Ereignissen.

Der Status einer Behauptung wird NIE gespeichert, sondern bei jedem Lesen aus den
Ereignissen des Protokolls abgeleitet (`derive_status`). Nur zwei Ereignisarten zählen:
`evaluation` (vom Richter `kmx.lab.judge` geschrieben) und `historical` (beim Anlegen
übernommene, belegte Altbefunde; nie `verified`). Alles, was ein Sprachmodell liefert,
wird als `claim` (Hypothese) oder `note` abgelegt; ein Statusfeld darin wird ignoriert.
"""

from __future__ import annotations

import os
import re
import shlex
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

HYPOTHESIS, EXPERIMENTAL, VERIFIED, REFUTED = (
    "hypothesis",
    "experimental",
    "verified",
    "refuted",
)
STATUSES = (HYPOTHESIS, EXPERIMENTAL, VERIFIED, REFUTED)

# Ereignisarten des Protokolls
EV_CLAIM, EV_NOTE, EV_EVALUATION, EV_HISTORICAL = (
    "claim",
    "note",
    "evaluation",
    "historical",
)
EV_CRITIQUE, EV_ATTEMPT, EV_ROUND, EV_LAB = "critique", "attempt", "round", "lab"

# Wer Status-relevante Ereignisse schreiben darf
JUDGE_EVALUATOR = "kmx.lab.judge"
SEED_EVALUATOR = "seed:agent-memory"
HISTORICAL_STATUSES = frozenset({EXPERIMENTAL, REFUTED})

# Felder, die ein offizieller Lauf belegen muss, damit "verified" gilt
OFFICIAL_EVIDENCE_FIELDS = (
    "command",
    "exit_code",
    "output_sha256",
    "candidate_sha256",
    "python_version",
    "kmx_version",
)
OFFICIAL_FAIL, OFFICIAL_PASS = "FAIL", "PASS"  # "status" im JSON des Verifiers

_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
MAX_CLAIM_CHARS = 2000
MAX_ASSUMPTION_CHARS = 500
MAX_LIST_ITEMS = 12


def safe_id(raw: object) -> str | None:
    """Gültige Kennung (Buchstaben, Ziffern, `_.-`, höchstens 64 Zeichen, kein `..`)
    oder None. Schützt vor Pfadtricks in Kennungen aus Modellantworten."""
    if not isinstance(raw, str) or not _SAFE_ID.fullmatch(raw) or ".." in raw:
        return None
    return raw


def is_sha256(raw: object) -> bool:
    """Ob `raw` ein SHA-256 in Kleinbuchstaben-Hex ist (Dateiname im Labor)."""
    return isinstance(raw, str) and bool(_SHA256.fullmatch(raw))


def safe_text(raw: object, limit: int = MAX_CLAIM_CHARS) -> str:
    """Text ohne Steuerzeichen, gekürzt auf `limit` Zeichen ('' für Nicht-Text)."""
    if not isinstance(raw, str):
        return ""
    return _CONTROL.sub("", raw).strip()[:limit]


def safe_text_list(raw: object, limit: int = MAX_ASSUMPTION_CHARS) -> list[str]:
    """Liste bereinigter, nicht leerer Texte (höchstens MAX_LIST_ITEMS)."""
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    items = (safe_text(x, limit) for x in raw[:MAX_LIST_ITEMS])
    return [x for x in items if x]


def safe_id_list(raw: object, known: Iterable[str] | None = None) -> list[str]:
    """Gültige Kennungen aus `raw`; mit `known` nur solche, die es dort gibt."""
    if not isinstance(raw, list):
        return []
    ids = [i for i in (safe_id(x) for x in raw[:MAX_LIST_ITEMS]) if i]
    if known is None:
        return ids
    known_set = set(known)
    return [i for i in ids if i in known_set]


@dataclass
class Claim:
    """Sicht auf eine Behauptung, aus dem Protokoll zusammengesetzt."""

    claim_id: str
    claim: str
    status: str = HYPOTHESIS
    assumptions: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    proof_artifacts: list[dict[str, Any]] = field(default_factory=list)
    experiments: list[str] = field(default_factory=list)
    counterexamples: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    introduced_by: str = ""
    supersedes: list[str] = field(default_factory=list)
    created: str = ""
    updated: str = ""
    best_score: float | None = None


def official_evidence_complete(official: Mapping[str, Any] | None) -> bool:
    """Ob ein offizieller Lauf vollständig belegt ist (Befehl, Exit-Code, Hashes,
    Werkzeugversionen)."""
    if not isinstance(official, Mapping):
        return False
    return all(official.get(k) not in (None, "") for k in OFFICIAL_EVIDENCE_FIELDS)


def official_passed(official: Mapping[str, Any] | None) -> bool:
    """Ob ein offizieller Lauf belegt bestanden hat: vollständiger Beleg, Exit 0 und
    das JSON-Urteil des Verifiers lautet PASS (Exit 0 allein reicht nicht, ein
    `| tail` oder `|| true` im Befehl verschluckt den Exit-Code)."""
    return (
        official_evidence_complete(official)
        and official is not None
        and official.get("exit_code") == 0
        and official.get("verifier_status") == OFFICIAL_PASS
    )


def references_candidate(command: object, candidate_sha: object) -> bool:
    """Ob der (eingesetzte) Verifier-Befehl die Kandidatendatei `<sha>.kmx|.kmb`
    als Argument nennt (Kommentare zählen nicht)."""
    if not isinstance(command, str) or not is_sha256(candidate_sha):
        return False
    try:
        tokens = shlex.split(command, comments=True)
    except ValueError:
        return False
    names = {f"{candidate_sha}.kmx", f"{candidate_sha}.kmb"}
    return any(os.path.basename(t) in names for t in tokens)


def official_pinned(
    official: Mapping[str, Any] | None,
    candidate_sha: object,
    pin: Mapping[str, str] | None,
) -> bool:
    """Ob ein offizieller Lauf mit dem bei `lab init` gepinnten Verifier lief: dieselben
    Werkzeug-Hashes (Bytes, nicht Pfade; Pin nicht leer) UND der Befehl nennt den
    Kandidaten. Ohne Pin: False."""
    if not isinstance(official, Mapping) or not isinstance(pin, Mapping) or not pin:
        return False
    tools = official.get("tool_sha256")
    if not isinstance(tools, Mapping):
        return False
    if sorted(map(str, tools.values())) != sorted(map(str, pin.values())):
        return False
    return references_candidate(official.get("command"), candidate_sha)


def evaluation_status(
    event: Mapping[str, Any],
    candidate_ok: Callable[[str], bool],
    pin: Mapping[str, str] | None = None,
) -> str | None:
    """Status, den ein einzelnes Richter-Ereignis belegt (None = zählt nicht).

    verified: Kontrakt bestanden UND offizieller Verifier mit Exit 0 UND lesbarem
    Urteil "status": "PASS", vollständig belegt, und der geprüfte Kandidat liegt mit
    genau diesem Hash im Labor UND der Lauf nutzte den gepinnten Verifier
    (`official_pinned`; ohne Pin im Labor bleibt ein PASS experimental).
    experimental: Kontrakt lokal über die ganze Domäne bestanden (Messzufall nur
    gestichprobt).
    refuted: Kontrakt verletzt (mit Gegenbeispiel) oder offizieller Verifier hat
    ausdrücklich FAIL gemeldet (unabhängig vom Exit-Code). Ein Lauf ohne lesbares
    PASS-Urteil (Absturz, falscher Befehl, Timeout, Exit 0 ohne JSON) ist kein Beleg;
    dann bleibt es bei experimental. Ein Kandidat identisch mit der Basis
    (`no_change`) zählt nicht.
    """
    if event.get("evaluator") != JUDGE_EVALUATOR or event.get("no_change"):
        return None
    if not event.get("passed"):
        return REFUTED
    official = event.get("official")
    if official is None:
        return EXPERIMENTAL
    if official.get("verifier_status") == OFFICIAL_FAIL:
        return REFUTED
    if not official_passed(official):
        return EXPERIMENTAL
    sha = official.get("candidate_sha256")
    if sha != event.get("candidate_sha256") or not candidate_ok(sha):
        return EXPERIMENTAL
    if not official_pinned(official, sha, pin):
        return EXPERIMENTAL
    return VERIFIED


def derive_status(
    events: Iterable[Mapping[str, Any]],
    candidate_ok: Callable[[str], bool],
    pin: Mapping[str, str] | None = None,
) -> str:
    """Status aus den Ereignissen einer Behauptung (chronologisch; das jüngste
    zählende Ereignis gewinnt). Ohne zählendes Ereignis: hypothesis."""
    status = HYPOTHESIS
    for e in events:
        kind = e.get("kind")
        if kind == EV_EVALUATION:
            status = evaluation_status(e, candidate_ok, pin) or status
        elif (
            kind == EV_HISTORICAL
            and e.get("evaluator") == SEED_EVALUATOR
            and e.get("status") in HISTORICAL_STATUSES
        ):
            status = e["status"]
    return status
