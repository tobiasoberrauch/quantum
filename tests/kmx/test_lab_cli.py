"""Labor: Unterbefehl `lab` (init, run, status, eval) über kmx.cli.main."""

import os
import tempfile

import kmx.lab.commands as lab_commands
from kmx.agent.client import LLMError
from tests.kmx.fakes import RoutingFakeClient
from tests.kmx.helpers import MBU_BODY, cli, patched, write_input
from tests.kmx.lab_helpers import (
    BAD_PHASE_TEXT,
    GOOD_TEXT,
    RANGE,
    TEAM_KEYS,
    fake_verifier_cmd,
    proposal,
    reply,
)

K = TEAM_KEYS


def _init(d, *extra):
    base = write_input(d, MBU_BODY, "base.kmx")
    lab = os.path.join(d, "lab")
    rc, out = cli(
        "lab", "init", "--lab-dir", lab, "--baseline", base, "--range", RANGE, *extra
    )
    assert rc == 0 and "Labor angelegt" in out and "6 Altbefunde" in out, out
    return lab


def _write(d, name, text):
    path = os.path.join(d, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def test_lab_init_status_eval():
    with tempfile.TemporaryDirectory() as d:
        lab = _init(d, "--verify-cmd", fake_verifier_cmd(d))  # Verifier gepinnt
        assert sorted(os.listdir(lab)) == [
            "baseline.kmx",
            "candidates",
            "events.jsonl",
            "lab.json",
        ]
        rc, out = cli("lab", "init", "--lab-dir", lab, "--baseline", d + "/base.kmx")
        assert rc == 1 and "existiert bereits" in out
        rc, out = cli("lab", "eval", "--lab-dir", lab, _write(d, "g.kmx", GOOD_TEXT))
        assert rc == 0 and "BESTANDEN (equivalent)" in out and "experimental" in out
        rc, out = cli(
            "lab", "eval", "--lab-dir", lab, _write(d, "b.kmx", BAD_PHASE_TEXT)
        )
        assert rc == 2 and "Gegenbeispiel: [phase] x=1" in out and "refuted" in out
        rc, out = cli(
            "lab", "eval", "--lab-dir", lab, "--verify-cmd", "true", d + "/g.kmx"
        )
        assert rc == 2 and "offiziell FAIL" in out, out
        assert "verified" not in out.split("Status")[-1]
        rc, out = cli(
            "lab",
            "eval",
            "--lab-dir",
            lab,
            "--verify-cmd",
            fake_verifier_cmd(d),
            d + "/g.kmx",
        )
        assert rc == 0 and "offiziell PASS" in out and "verified" in out
        rc, out = cli("lab", "status", "--lab-dir", lab)
        assert rc == 0 and "verified 1" in out and "refuted 4" in out, out
        assert "Bester Score verified: 40.00" in out and "[phase] x=1" in out


def test_lab_errors_are_clean_messages():
    with tempfile.TemporaryDirectory() as d:
        rc, out = cli("lab", "status", "--lab-dir", os.path.join(d, "fehlt"))
        assert rc == 1 and "Kein Labor" in out
        rc, out = cli("lab", "status", "--name", "../../etc")
        assert rc == 1 and "ungültiger Laborname" in out
        rc, out = cli("lab", "init", "--lab-dir", d + "/l", "--baseline", d + "/x.kmx")
        assert rc == 1 and "Datei nicht gefunden" in out
        base = write_input(d, MBU_BODY, "base.kmx")
        rc, out = cli("lab", "init", "--lab-dir", d + "/l", "--baseline", base)
        assert rc == 1 and "vollständige Domäne" in out  # ohne --range
        dirty = write_input(d, MBU_BODY + ["CX q2 q9"], "dirty.kmx")
        rc, out = cli(
            "lab", "init", "--lab-dir", d + "/l", "--baseline", dirty, "--range", RANGE
        )
        assert rc == 1 and "Kontrakt" in out and not os.path.exists(d + "/l")


def test_lab_run_with_stub_llm():
    routes = {
        K["director"]: [reply({"focus": {"phase": "try a phase trick"}})],
        K["phase"]: [proposal(BAD_PHASE_TEXT)],
        K["critic"]: [reply({"veto": False, "reason": ""})],
    }
    with tempfile.TemporaryDirectory() as d:
        lab = _init(d)
        with patched(
            lab_commands, "make_client", lambda **_: RoutingFakeClient(routes)
        ):
            rc, out = cli("lab", "run", "--lab-dir", lab, "--teams", "phase")
        assert rc == 0 and "Runden 1/1" in out and "Bewertungen 1" in out, out
        assert "[phase] x=1" in out
        with patched(
            lab_commands,
            "make_client",
            lambda **_: RoutingFakeClient(routes, reachable=False),
        ):
            rc, out = cli("lab", "run", "--lab-dir", lab, "--teams", "phase")
        assert rc == 1 and "nicht erreichbar" in out
        down = {K["director"]: [LLMError("HTTP 502: Upstream", 502)]}
        with patched(lab_commands, "make_client", lambda **_: RoutingFakeClient(down)):
            rc, out = cli("lab", "run", "--lab-dir", lab, "--teams", "phase")
        assert rc == 1 and "Vorschläge 0" in out and "Infrastruktur" in out, out
        rc, out = cli("lab", "run", "--lab-dir", lab, LLM_MAX_CALLS="0")
        assert rc == 0 and "LLM_MAX_CALLS=0" in out
        rc, out = cli("lab", "run", "--lab-dir", lab, "--teams", "magic")
        assert rc == 1 and "unbekannte Teams" in out
