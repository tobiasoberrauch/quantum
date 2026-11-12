"""Kommandozeile und Einstiegspunkt main.py (kmx.cli, kmx.commands, kmx.output)."""

import contextlib
import io
import os
import socket
import tempfile
import urllib.request

import kmx
import kmx.cli
import kmx.selftest
from tests.kmx.fakes import (
    tool_call,
)
from tests.kmx.helpers import (
    CANCEL_BODY,
    MBU_BODY,
    NHEAD,
    WB_BODY,
    _network_forbidden,
    cli,
    env,
    no_network,
    patched,
    quiet,
    run_main,
    toffoli,
    write_input,
)


# (Shell-Befehl)
def test_run_official_verifier_substitutes_placeholders():
    with tempfile.TemporaryDirectory() as d:
        cand = os.path.join(d, "mit leerzeichen.kmx")
        with open(cand, "w", encoding="utf-8") as f:
            f.write("X q0\n")
        assert kmx.run_official_verifier("test -f {candidate}", cand) == (
            True,
            "Exit-Code 0",
        )
        assert kmx.run_official_verifier("test -f {out} && cat {out}", cand) == (
            True,
            "X q0",
        )
        # ohne Platzhalter: angehaengt
        assert kmx.run_official_verifier("cat", cand) == (
            True,
            "X q0",
        )
        assert kmx.run_official_verifier("echo {candidate} {out}", cand) == (
            True,
            f"{cand} {cand}",
        )


def test_run_official_verifier_reports_non_zero_exit():
    with tempfile.TemporaryDirectory() as d:
        missing = os.path.join(d, "fehlt.kmx")
        assert kmx.run_official_verifier("false", missing) == (False, "Exit-Code 1")
        assert kmx.run_official_verifier("test -f {candidate}", missing) == (
            False,
            "Exit-Code 1",
        )
        ok, out = kmx.run_official_verifier(
            "sh -c 'echo abgelehnt; echo grund >&2; exit 7' --", missing
        )
        assert ok is False and "abgelehnt" in out and "grund" in out
        with env(OFFICIAL_VERIFY_TIMEOUT="1"):
            ok, out = kmx.run_official_verifier("sleep 5 #", missing)
        assert ok is False and "fehlgeschlagen" in out


def test_cli_optimize_writes_output_equivalent_to_input():
    with tempfile.TemporaryDirectory() as d:
        inp, out, diff = (
            write_input(d),
            os.path.join(d, "out.kmx"),
            os.path.join(d, "out.diff"),
        )
        rc, text = cli(
            "optimize",
            inp,
            "-o",
            out,
            "--diff",
            diff,
            "--range",
            "0:63",
            "--no-kickmix",
        )
        assert rc == 0 and "BESTANDEN" in text and f"Geschrieben: {out}" in text
        orig, cand = kmx.read_circuit(inp), kmx.read_circuit(out)
        layout = kmx.analyze_layout(orig, "x", "0:63")
        dom, _ = kmx.build_domains(layout, 1 << 20, 64, 64)
        # Vergleich wie cmd_check
        ok, msg, sig = kmx.Oracle(orig, layout, dom, quiet).check(cand, range(4))
        assert ok, msg
        assert (
            toffoli(orig) == 4
            and toffoli(cand) <= 2
            and kmx.compute_metrics(cand).num_qubits == 9
        )
        # keine Temporaerdateien
        assert sorted(os.listdir(d)) == [
            "in.kmx",
            "out.diff",
            "out.kmx",
        ]
        with open(diff, encoding="utf-8") as f:
            assert "-CCX q0 q1 q8" in f.read()
        rc_check, check_text = cli("check", inp, out, "--range", "0:63", "--no-kickmix")
        assert (
            rc_check == 0 and "ÄQUIVALENT" in check_text and "NICHT" not in check_text
        )


def test_cli_check_rejects_non_equivalent_candidate():
    with tempfile.TemporaryDirectory() as d:
        inp, wrong = write_input(d), write_input(d, MBU_BODY + ["Z q0"], "wrong.kmx")
        rc, text = cli("check", inp, wrong, "--range", "0:63", "--no-kickmix")
        assert rc == 2 and "NICHT ÄQUIVALENT" in text and "Phase" in text


def test_cli_optimize_default_output_name():
    with tempfile.TemporaryDirectory() as d:
        inp = write_input(d, CANCEL_BODY, "c.kmx")
        rc, _ = cli("optimize", inp, "--range", "0:63", "--no-kickmix")
        assert rc == 0 and sorted(os.listdir(d)) == ["c.kmx", "c_optimized.kmx"]
        assert toffoli(kmx.read_circuit(os.path.join(d, "c_optimized.kmx"))) == 0


def test_cli_missing_input_returns_1():
    with tempfile.TemporaryDirectory() as d:
        missing = os.path.join(d, "gibtsnicht.kmx")
        for argv in (
            ["optimize", missing, "-o", os.path.join(d, "o.kmx")],
            ["info", missing],
            [missing],
            ["check", missing, missing],
        ):
            rc, text = cli(*argv, "--no-kickmix", LLM_MAX_CALLS="0")
            assert rc == 1 and "Datei nicht gefunden" in text, argv
        assert os.listdir(d) == []


def test_cli_format_error_returns_1_and_writes_nothing():
    with tempfile.TemporaryDirectory() as d:
        inp = write_input(d, ["CCX q0 q1 q8", "CX q3 q3"])
        rc, text = cli(
            "optimize",
            inp,
            "-o",
            os.path.join(d, "o.kmx"),
            "--range",
            "0:63",
            "--no-kickmix",
        )
        assert (
            rc == 1
            and "Formatfehler" in text
            and "Zeile 9" in text
            and os.listdir(d) == ["in.kmx"]
        )


def test_cli_legacy_positional_form_with_llm_disabled():
    with tempfile.TemporaryDirectory() as d:
        inp, out, diff = (
            write_input(d),
            os.path.join(d, "legacy_out.kmx"),
            os.path.join(d, "legacy.diff"),
        )
        # no_network() aktiv
        rc, text = cli(
            inp, out, diff, "--range", "0:63", "--no-kickmix", LLM_MAX_CALLS="0"
        )
        assert (
            rc == 0
            and os.path.exists(out)
            and os.path.exists(diff)
            and "LLM" not in text
        )
        assert toffoli(kmx.read_circuit(out)) <= 2
        rc_check, _ = cli("check", inp, out, "--range", "0:63", "--no-kickmix")
        assert rc_check == 0


def test_cli_require_official_verify_without_command_returns_3_and_writes_nothing():
    with tempfile.TemporaryDirectory() as d:
        inp, out = write_input(d), os.path.join(d, "out.kmx")
        rc, text = cli(
            "optimize",
            inp,
            "-o",
            out,
            "--range",
            "0:63",
            "--no-kickmix",
            REQUIRE_OFFICIAL_VERIFY="1",
        )
        assert rc == 3 and "REQUIRE_OFFICIAL_VERIFY=1" in text
        assert os.listdir(d) == ["in.kmx"]


def test_cli_official_verifier_gates_the_write():
    with tempfile.TemporaryDirectory() as d:
        inp, out = write_input(d), os.path.join(d, "out.kmx")
        with open(out, "w", encoding="utf-8") as f:
            f.write("ALT\n")
        rc_fail, text_fail = cli(
            "optimize",
            inp,
            "-o",
            out,
            "--range",
            "0:63",
            "--no-kickmix",
            "--verify-cmd",
            "false",
        )
        with open(out, encoding="utf-8") as f:
            kept = f.read()
        rc_env, _ = cli(
            "optimize",
            inp,
            "-o",
            out,
            "--range",
            "0:63",
            "--no-kickmix",
            OFFICIAL_VERIFY_CMD="false",
            REQUIRE_OFFICIAL_VERIFY="1",
        )
        rc_ok, text_ok = cli(
            "optimize",
            inp,
            "-o",
            out,
            "--range",
            "0:63",
            "--no-kickmix",
            "--verify-cmd",
            "grep -q HMR {out}",
            REQUIRE_OFFICIAL_VERIFY="1",
        )
        assert (
            rc_fail == 3
            and "OFFIZIELLER VERIFIER: FAIL" in text_fail
            and kept == "ALT\n"
        )
        assert rc_env == 3
        assert (
            rc_ok == 0
            and "OFFIZIELLER VERIFIER: PASS" in text_ok
            and toffoli(kmx.read_circuit(out)) <= 2
        )
        # Kandidaten-Datei aufgeraeumt
        assert sorted(os.listdir(d)) == [
            "in.kmx",
            "out.kmx",
        ]


def test_cli_info_and_builtin_selftest():
    with tempfile.TemporaryDirectory() as d:
        inp = write_input(d)
        rc, text = cli("info", inp, "--range", "0:63", "--no-kickmix")
        assert (
            rc == 0
            and "Toffoli-artig=4" in text
            and "Q=10" in text
            and os.listdir(d) == ["in.kmx"]
        )
    rc, text = cli("--selftest")
    assert rc == 0 and "FAIL" not in text and text.count("OK  ") >= 8


def test_cli_agent_skips_llm_stage_when_endpoint_is_down():
    def refuse(addr, timeout=None):
        raise ConnectionRefusedError("down")

    with tempfile.TemporaryDirectory() as d:
        inp, out, buf = write_input(d), os.path.join(d, "out.kmx"), io.StringIO()
        with (
            env(),
            patched(socket, "create_connection", refuse),
            patched(urllib.request, "urlopen", _network_forbidden),
            contextlib.redirect_stdout(buf),
        ):
            rc = kmx.cli.main(
                [
                    "agent",
                    inp,
                    "-o",
                    out,
                    "--models",
                    "fake",
                    "--range",
                    "0:63",
                    "--no-kickmix",
                ]
            )
        assert (
            rc == 0
            and "LLM-Stufe übersprungen" in buf.getvalue()
            and toffoli(kmx.read_circuit(out)) <= 2
        )


def test_cli_agent_runs_stubbed_llm_stage_end_to_end():
    script = [
        tool_call(
            "propose_rewrite",
            start=NHEAD,
            end=NHEAD + 2,
            new_lines=["CX q1 q8", "X q0"],
        ),
        tool_call("full_check"),
        tool_call("finish", summary="ok"),
    ]
    calls = []

    def fake_chat(self, model, messages, tools=None):
        calls.append(model)
        return script.pop(0)

    # WB_BODY ohne die Kuerzung durch die Paesse: --iters 0 laesst dem "Modell" etwas
    # uebrig
    with tempfile.TemporaryDirectory() as d:
        inp, out, buf = (
            write_input(d, WB_BODY),
            os.path.join(d, "out.kmx"),
            io.StringIO(),
        )
        with (
            env(),
            no_network(),
            patched(kmx.LLMClient, "reachable", lambda self, timeout=3.0: True),
            patched(kmx.LLMClient, "chat", fake_chat),
            contextlib.redirect_stdout(buf),
        ):
            rc = kmx.cli.main(
                [
                    "agent",
                    inp,
                    "-o",
                    out,
                    "--models",
                    "fake",
                    "--iters",
                    "0",
                    "--no-repack",
                    "--range",
                    "0:63",
                    "--no-kickmix",
                    "--api-url",
                    "http://127.0.0.1:9/x",
                ]
            )
        text = buf.getvalue()
        assert (
            rc == 0
            and calls == ["fake"] * 3
            and "propose_rewrite -> angenommen" in text
        )
        assert (
            "1 verifizierte Rewrites | ok" in text
            and toffoli(kmx.read_circuit(out)) == 0
        )


def test_check_with_missing_candidate_returns_1():
    # Regression: main() prueft nur args.input; `check ORIG fehlend.kmx` endet mit einem
    # FileNotFoundError-Traceback.
    with tempfile.TemporaryDirectory() as d:
        rc, _ = cli(
            "check",
            write_input(d),
            os.path.join(d, "fehlt.kmx"),
            "--range",
            "0:63",
            "--no-kickmix",
        )
        assert rc == 1


def test_written_outputs_get_default_permissions():
    # Regression: mkstemp legte .kmx und .diff mit 0600 an.
    umask = os.umask(0)
    os.umask(umask)
    with tempfile.TemporaryDirectory() as d:
        inp, out, diff = (
            write_input(d),
            os.path.join(d, "out.kmx"),
            os.path.join(d, "out.diff"),
        )
        rc, _ = cli(
            "optimize",
            inp,
            "-o",
            out,
            "--diff",
            diff,
            "--range",
            "0:63",
            "--no-kickmix",
        )
        assert rc == 0
        for path in (out, diff):
            assert os.stat(path).st_mode & 0o777 == 0o666 & ~umask, oct(
                os.stat(path).st_mode
            )


def test_main_py_selftest_subprocess():
    proc = run_main("--selftest")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    lines = proc.stdout.splitlines()
    assert len(lines) == len(kmx.selftest.SELFTEST_CHECKS), proc.stdout
    assert all(line.startswith("OK   ") for line in lines), proc.stdout
