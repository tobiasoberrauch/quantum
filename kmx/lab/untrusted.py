"""Umgang mit Text aus nicht vertrauenswürdigen Quellen (Generator-Ausgaben).

Ein Generator läuft unter derselben Benutzerkennung wie das Labor. Die Sandbox sperrt
Netz, Dateien und Prozesse, aber nicht jede Lesequelle: über
`sysctl(KERN_PROCARGS2)` kann er die Start-Umgebung des Elternprozesses und anderer
Prozesse desselben Benutzers lesen (API-Schlüssel). Deshalb geht KEIN Rohtext eines
Generators (stdout, stderr, Inhalt seiner Ausgabedatei) in Protokoll, Prompts oder
Gegenbeispiele, sondern nur:

- Hash und Länge der Ströme (`stream_digest`),
- der Name einer Ausnahme, wenn er eine eingebaute Ausnahme ist (`exception_name`),
- die Zeilennummer im Generator aus dem Traceback (`generator_line`),
- bei Formatfehlern nur Zeilennummer und Fehlerart (`parse_error_summary`).

Zusätzlich ersetzt `redact` die Werte geheimer Umgebungsvariablen des Labors in
allem, was ins Protokoll geht (zweite Verteidigungslinie). Verbleibende schmale Kanäle
(Exit-Code, Zeilennummer, Kennzahlen des Schaltkreises) sind dokumentiert; voll
geschlossen wird das Leck erst mit eigener Benutzerkennung oder VM für Generatoren.
"""

from __future__ import annotations

import builtins
import hashlib
import os
import re
from collections.abc import Mapping
from typing import Any

GENERATOR_FILE = "generator.py"
REDACTED = "[ENTFERNT]"
MIN_SECRET_CHARS = 8
MAX_LINE_NO = 10_000_000
_SECRET_NAME = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH", re.I)
_EXC_LINE = re.compile(r"^([A-Za-z_][\w.]{0,120})(?::|$)")
_TB_LINE = re.compile(r'File "[^"\n]*' + re.escape(GENERATOR_FILE) + r'", line (\d+)')
_PARSE_WHERE = re.compile(r"^(Zeile \d+|Eintrag \d+): ")
_PARSE_PROBLEM = re.compile(r"""['"]: ([A-Za-zÄÖÜäöüß ,()/-]{1,80})$""")
# eingebaute Ausnahmen plus die Formatausnahme des Pakets
KNOWN_EXCEPTIONS = frozenset(
    name
    for name, obj in vars(builtins).items()
    if isinstance(obj, type) and issubclass(obj, BaseException)
) | {"KmxError"}


def stream_digest(data: bytes) -> dict[str, Any]:
    """Nur Länge und SHA-256 eines Ausgabestroms (kein Inhalt)."""
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def exception_name(stderr: str) -> str:
    """Name der Ausnahme aus der letzten Zeile eines Tracebacks, nur wenn es eine
    bekannte (eingebaute) ist; sonst ''. Eigene Klassennamen wären ein Kanal."""
    lines = [x for x in stderr.strip().splitlines() if x.strip()]
    if not lines:
        return ""
    hit = _EXC_LINE.match(lines[-1].strip())
    name = hit.group(1).rsplit(".", 1)[-1] if hit else ""
    return name if name in KNOWN_EXCEPTIONS else ""


def generator_line(stderr: str) -> int | None:
    """Zeilennummer des letzten Traceback-Rahmens in generator.py (oder None)."""
    hits = _TB_LINE.findall(stderr)
    if not hits:
        return None
    line = int(hits[-1])
    return line if 0 < line <= MAX_LINE_NO else None


def parse_error_summary(message: str) -> str:
    """Formatfehler ohne den zitierten Zeilentext: 'Zeile N: Fehlerart'."""
    where = _PARSE_WHERE.match(message)
    problem = _PARSE_PROBLEM.search(message)
    parts = [where.group(1) if where else "", problem.group(1) if problem else ""]
    text = ": ".join(p for p in parts if p)
    return text or "unlesbare Ausgabe"


def secret_values(environ: Mapping[str, str] | None = None) -> list[str]:
    """Werte geheimer Umgebungsvariablen (Name enthält KEY, TOKEN, ...), längste
    zuerst."""
    env = os.environ if environ is None else environ
    vals = {
        v
        for k, v in env.items()
        if _SECRET_NAME.search(k) and len(v) >= MIN_SECRET_CHARS
    }
    return sorted(vals, key=len, reverse=True)


def redact(value: Any, secrets: list[str] | None = None) -> Any:
    """Ersetzt geheime Werte in allen Texten einer (verschachtelten) Struktur."""
    secrets = secret_values() if secrets is None else secrets
    if not secrets:
        return value
    if isinstance(value, str):
        for s in secrets:
            value = value.replace(s, REDACTED)
        return value
    if isinstance(value, dict):
        return {k: redact(v, secrets) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v, secrets) for v in value]
    return value
