"""Labor: der offizielle Verifier wird bei `lab init` gepinnt; `verified` nur mit
gepinnten Werkzeug-Hashes und einem Befehl, der den Kandidaten nennt
(kmx.lab.official.verifier_pin, kmx.lab.claims.official_pinned)."""

import json
import os
import shlex
import sys
import tempfile

from kmx.lab.claims import EXPERIMENTAL, VERIFIED, official_pinned
from kmx.lab.official import verifier_pin
from kmx.lab.report import UNPINNED_MARKER, status_report
from tests.kmx.helpers import MBU_BODY, cli, write_input
from tests.kmx.lab_helpers import GOOD_TEXT, RANGE, fake_verifier_cmd, make_lab

ALWAYS_PASS = 'import json\nprint(json.dumps({"status": "PASS", "score": 1.0}))\n'


def _write(d, name, text):
    path = os.path.join(d, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def _eval(lab, cmd, path):
    return cli("lab", "eval", "--lab-dir", lab, "--verify-cmd", cmd, path)


def test_lab_init_pins_the_verifier_and_pinned_pass_is_verified():
    with tempfile.TemporaryDirectory() as d:
        cmd = fake_verifier_cmd(d)
        base = write_input(d, MBU_BODY, "base.kmx")
        lab = os.path.join(d, "lab")
        rc, out = cli(
            "lab", "init", "--lab-dir", lab, "--baseline", base, "--range", RANGE,
            "--verify-cmd", cmd,
        )  # fmt: skip
        assert rc == 0 and "Verifier gepinnt" in out, out
        with open(os.path.join(lab, "lab.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        script = os.path.join(d, "fake_verify.py")
        assert cfg["verifier_pin"] == verifier_pin(cmd)
        assert len(cfg["verifier_pin"][script]) == 64
        good = _write(d, "g.kmx", GOOD_TEXT)
        rc, out = _eval(lab, cmd, good)
        assert rc == 0 and "Status der Behauptung: verified" in out, out
        rc, out = cli("lab", "status", "--lab-dir", lab)
        prefix = cfg["verifier_pin"][script][:12]
        line = next(x for x in out.splitlines() if "Verifier sha256" in x)
        assert prefix in line and UNPINNED_MARKER not in out, out
        # Verifier-Skript nachträglich geändert (meldet weiter PASS): nur experimental
        with open(script, "a", encoding="utf-8") as f:
            f.write("# geändert\n")
        rc, out = _eval(lab, cmd, good)
        assert "offiziell PASS" in out and "Status der Behauptung: experimental" in out
        rc, out = cli("lab", "status", "--lab-dir", lab)
        assert UNPINNED_MARKER in out and "verified 1" in out, out


def test_pass_without_candidate_in_command_is_not_verified():
    with tempfile.TemporaryDirectory() as d:
        script = _write(d, "always.py", ALWAYS_PASS)
        py = shlex.quote(sys.executable)
        pinned = f"{py} {shlex.quote(script)} {{out}}"
        reg, judge = make_lab(d, pinned)
        assert reg.config().verifier_pin == verifier_pin(pinned)
        # gleiche Werkzeuge, aber der Kandidatenpfad landet im Kommentar
        judge.verify_cmd = f"{py} {shlex.quote(script)} #"
        ev = judge.evaluate("kmx", GOOD_TEXT)
        cid = reg.add_hypothesis("candidate", "team:phase")
        judge.record(cid, ev)
        assert ev.official["verifier_status"] == "PASS"
        assert ev.official["tool_sha256"] == verifier_pin(pinned)
        assert reg.claims()[cid].status == EXPERIMENTAL
        judge.verify_cmd = pinned
        ev = judge.evaluate("kmx", GOOD_TEXT)
        judge.record(cid, ev)
        assert reg.claims()[cid].status == VERIFIED


def test_lab_without_pin_counts_official_pass_as_experimental():
    with tempfile.TemporaryDirectory() as d:
        cmd = fake_verifier_cmd(d)
        reg, judge = make_lab(d, cmd, pin=False)
        assert reg.config().verifier_pin is None
        ev = judge.evaluate("kmx", GOOD_TEXT)
        cid = reg.add_hypothesis("candidate", "team:phase")
        judge.record(cid, ev)
        assert ev.official["verifier_status"] == "PASS"
        assert reg.claims()[cid].status == EXPERIMENTAL
        report = status_report(reg)
        line = next(x for x in report.splitlines() if x.strip().startswith(cid))
        assert UNPINNED_MARKER in line and "nicht gepinnt" in report


def test_official_pinned_rules():
    sha = "a" * 64
    pin = {"/usr/bin/python3": "1" * 64, "/v.py": "2" * 64}
    off = {"tool_sha256": dict(pin), "command": f"python3 /v.py lab/{sha}.kmx"}
    assert official_pinned(off, sha, pin)
    assert not official_pinned(off, sha, None) and not official_pinned(off, sha, {})
    assert not official_pinned(dict(off, command="echo PASS"), sha, pin)
    assert not official_pinned(dict(off, command=f"v.py # {sha}.kmx"), sha, pin)
    other = dict(off, tool_sha256={"/v.py": "3" * 64, "/usr/bin/python3": "1" * 64})
    assert not official_pinned(other, sha, pin)
    moved = dict(off, tool_sha256={"/elsewhere/v.py": "2" * 64, "py": "1" * 64})
    assert official_pinned(moved, sha, pin)  # gleiche Bytes, anderer Pfad
