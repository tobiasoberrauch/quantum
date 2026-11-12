"""Offizieller Verifier als externer Prüfer mit Beleg: Befehl, Exit-Code, SHA-256 der
Ausgabe und des Kandidaten, SHA-256 der Werkzeugdateien (Verifier-Skript,
Interpreter), Python- und kmx-Version. Nur so ein Beleg MIT JSON-Urteil "PASS" kann eine
Behauptung auf `verified` heben (siehe `kmx.lab.claims.evaluation_status`).

Ein formaler Beweiser (Lean, SMT) würde genauso angeschlossen: als aufgezeichneter
externer Werkzeuglauf mit Hashes, Version, Quelle und Annahmen in `proof_artifacts`.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shlex
import subprocess
import time
from typing import Any

from kmx.config import OFFICIAL_VERIFY_DEFAULT_TIMEOUT_S, env_int
from kmx.output import OFFICIAL_VERIFY_OUTPUT_TAIL, official_verifier_shell_command

OfficialRecord = dict[str, Any]
# Shell-Konstrukte, die den Exit-Code oder das Urteil des Verifiers verdecken können
SHELL_RISK_TOKENS = ("|", ";", "&&", "||", "`", "$(")
MAX_TOOL_FILES = 4
MAX_TOOL_BYTES = 64 << 20
# Platzhalter für den Kandidatenpfad beim Pinnen (zählt wie der Kandidat nicht mit)
PIN_CANDIDATE_PLACEHOLDER = "candidate.kmx"


def _sha256_path(path: str) -> str | None:
    try:
        if os.path.getsize(path) > MAX_TOOL_BYTES:
            return None
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def tool_hashes(command: str, candidate_path: str) -> dict[str, str]:
    """SHA-256 der Dateien im Befehl (Interpreter, Verifier-Skript) als
    Werkzeugversion; der Kandidat selbst zählt nicht."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return {}
    out: dict[str, str] = {}
    for tok in tokens:
        if len(out) >= MAX_TOOL_FILES or tok == candidate_path:
            continue
        if os.path.isfile(tok):
            sha = _sha256_path(tok)
            if sha:
                out[tok] = sha
    return out


def verifier_pin(command: str) -> dict[str, str]:
    """Pin des Verifiers bei `lab init`: dieselben Werkzeug-Hashes, die `run_official`
    als `tool_sha256` aufzeichnet (gleiche Einsetzung des Kandidatenpfads)."""
    placeholder = PIN_CANDIDATE_PLACEHOLDER
    cmd = official_verifier_shell_command(command, placeholder)
    return tool_hashes(cmd, placeholder)


def command_warnings(command: str) -> list[str]:
    """Warnungen zu Befehlen, die Exit-Code oder Urteil verdecken könnten."""
    risky = [t for t in SHELL_RISK_TOKENS if t in command]
    if not risky:
        return []
    return [
        f"Verifier-Befehl enthält Shell-Konstrukte {risky}: nur ein JSON-Urteil "
        "'PASS' zählt, der Exit-Code allein nicht"
    ]


def _parse_verifier_json(text: str) -> dict[str, Any] | None:
    """Das JSON-Objekt der Verifier-Ausgabe (status, score, ...), falls lesbar."""
    start = text.find("{")
    if start < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def kmx_version() -> str:
    """Version des Pakets (spät importiert: kmx/__init__ ist die Fassade darüber)."""
    from kmx import __version__

    return __version__


def run_official(command: str, candidate_path: str) -> OfficialRecord:
    """Führt den Verifier-Befehl ({out}/{candidate} = Kandidatenpfad) aus und liefert
    den Beleg. `exit_code` None heißt: lief nicht bis zum Ende (Timeout/OSError)."""
    with open(candidate_path, "rb") as f:
        candidate_sha = hashlib.sha256(f.read()).hexdigest()
    cmd = official_verifier_shell_command(command, candidate_path)
    t0 = time.time()
    record: OfficialRecord = {
        "tool": "official_verifier",
        "command": cmd,
        "candidate_sha256": candidate_sha,
        "python_version": platform.python_version(),
        "kmx_version": kmx_version(),
        "exit_code": None,
        "tool_sha256": tool_hashes(cmd, candidate_path),
        "warnings": command_warnings(command),
    }
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=env_int(
                "OFFICIAL_VERIFY_TIMEOUT", OFFICIAL_VERIFY_DEFAULT_TIMEOUT_S
            ),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        record.update(error=f"Verifier-Ausführung fehlgeschlagen: {exc}")
        record["duration_s"] = round(time.time() - t0, 2)
        return record
    output = proc.stdout + proc.stderr
    parsed = _parse_verifier_json(proc.stdout)
    record.update(
        exit_code=proc.returncode,
        output_sha256=hashlib.sha256(output.encode("utf-8")).hexdigest(),
        output_tail=output.strip()[-OFFICIAL_VERIFY_OUTPUT_TAIL:],
        verifier_status=(parsed or {}).get("status"),
        verifier_score=(parsed or {}).get("score"),
        duration_s=round(time.time() - t0, 2),
    )
    return record
