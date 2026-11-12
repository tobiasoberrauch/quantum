"""Gemeinsame Helfer der Labortests: winziges Labor (6-Bit-Register, --range 0:63)."""

import json
import os
import shlex
import sys

from kmx.lab.judge import Judge
from kmx.lab.official import verifier_pin
from kmx.lab.registry import LabConfig, Registry, sha256_file
from tests.kmx.helpers import HEAD, MBU_BODY, make_session, write_input

RANGE = "0:63"
BASE_TEXT = HEAD + "\n".join(MBU_BODY) + "\n"  # Byte für Byte die Basis
# äquivalent zur Basis, aber nicht identisch (X q4 X q4 hebt sich auf)
GOOD_TEXT = HEAD + "\n".join(MBU_BODY + ["X q4", "X q4"]) + "\n"
BAD_PHASE_TEXT = HEAD + "\n".join(MBU_BODY + ["Z q0"]) + "\n"  # x ungerade: Phase -1
DIRTY_TEXT = HEAD + "\n".join(MBU_BODY + ["CX q2 q9"]) + "\n"  # x mit Bit 2: q9 = 1
CLOBBER_TEXT = HEAD + "\n".join(MBU_BODY + ["CX q1 q3"]) + "\n"  # Register geaendert

TEAM_KEYS = {
    "numerical": "Numerical approximation team",
    "reversible": "Reversible computing team",
    "phase": "Phase synthesis team",
    "architecture": "Architecture inventor team",
    "critic": "mathematical critic",
    "director": "research director",
}


def make_lab(directory, verify_cmd=None, check_rounds=2, pin=True):
    """(Registry, Judge) eines frischen Labors mit MBU_BODY als Basis; mit
    `verify_cmd` ist der Verifier wie bei `lab init --verify-cmd` gepinnt (pin=False:
    ungepinnt wie ein Labor ohne Verifier beim Anlegen)."""
    base = write_input(directory, MBU_BODY, "base.kmx")
    cfg = LabConfig(
        name="t",
        baseline_file="baseline.kmx",
        baseline_sha256=sha256_file(base),
        value_range=RANGE,
        verifier_pin=(verifier_pin(verify_cmd) or None) if verify_cmd and pin else None,
    )
    reg = Registry.create(directory + "/lab", base, cfg)
    judge = Judge(
        make_session(MBU_BODY),
        reg,
        check_rounds,
        verify_cmd,
        log=lambda *_: None,
        value_range=RANGE,
    )
    return reg, judge


def reply(obj):
    """Antwort eines Modells mit JSON in einem Code-Zaun (wie Modelle es oft tun)."""
    return {"content": "Here you go:\n```json\n" + json.dumps(obj) + "\n```"}


def proposal(source=None, kind="kmx", claim="a claim", **extra):
    obj = {"claims": [{"claim": claim, "assumptions": ["small domain"]}], **extra}
    if source is not None:
        obj["candidate"] = {"kind": kind, "source": source, "rationale": "because"}
    return reply(obj)


FAKE_VERIFIER = """import json, sys
text = open(sys.argv[1]).read()
if "CCX" in text:
    print(json.dumps({"status": "PASS", "score": 40.0}))
else:
    print(json.dumps({"status": "FAIL", "error": "x=5: no CCX"}))
    sys.exit(1)
"""


def fake_verifier_cmd(directory):
    """Befehl eines kleinen Verifiers mit JSON-Urteil wie der offizielle."""
    path = os.path.join(directory, "fake_verify.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(FAKE_VERIFIER)
    return f"{shlex.quote(sys.executable)} {shlex.quote(path)} {{out}}"
