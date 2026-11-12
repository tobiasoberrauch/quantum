"""Labor: Generator-Sandbox (kmx.lab.sandbox). Ohne /usr/bin/sandbox-exec werden die
Ausführungstests mit Meldung übersprungen; dann muss die Sandbox die Ausführung
verweigern."""

import hashlib
import os
import tempfile

import kmx.lab.sandbox as sandbox
from kmx.lab.sandbox import SandboxLimits, SandboxUnavailable, run_generator
from tests.kmx.helpers import env, patched, raises

FAST = SandboxLimits(timeout_s=20, cpu_s=20)


def _skip():
    if sandbox.sandbox_available():
        return False
    print("ÜBERSPRUNGEN: /usr/bin/sandbox-exec fehlt (kein macOS?)")
    return True


def _run(body, limits=FAST):
    src = "import sys, os\nout = sys.argv[1]\n" + body
    return run_generator(src, limits)


def test_generator_writes_output_and_may_import_kmx():
    if _skip():
        return
    res = _run(
        "from kmx.ops import parse_text, format_ops\n"
        "open(out, 'w').write(format_ops(parse_text('X q0\\nCX q0 q1\\n')))\n"
        "print('hallo')\n"
    )
    assert res.ok and res.exit_code == 0, res
    assert res.output == b"X q0\nCX q0 q1\n"
    # stdout nur als Hash und Länge, nie als Text
    digest = hashlib.sha256(b"hallo\n").hexdigest()
    assert res.stdout == {"bytes": 6, "sha256": digest}, res


def test_network_is_blocked():
    if _skip():
        return
    res = _run(
        "import socket\n"
        "try:\n"
        "    socket.create_connection(('1.1.1.1', 80), timeout=3)\n"
        "    open(out, 'w').write('NETZ OFFEN')\n"
        "except OSError as e:\n"
        "    open(out, 'w').write('blocked ' + str(e.errno))\n"
    )
    assert res.ok and res.output.startswith(b"blocked"), res


def test_writes_outside_the_temp_dir_are_blocked():
    if _skip():
        return
    with tempfile.TemporaryDirectory(dir="/tmp") as d:
        target = os.path.join(os.path.realpath(d), "escape.txt")
        res = _run(
            "try:\n"
            f"    open({target!r}, 'w').write('x')\n"
            "    open(out, 'w').write('ESCAPED')\n"
            "except OSError:\n"
            "    open(out, 'w').write('blocked')\n"
        )
        assert res.output == b"blocked", res
        assert not os.path.exists(target)


def test_subprocesses_are_blocked():
    if _skip():
        return
    res = _run(
        "import subprocess\n"
        "try:\n"
        "    subprocess.run(['/bin/echo', 'x'])\n"
        "    open(out, 'w').write('FORKED')\n"
        "except OSError:\n"
        "    open(out, 'w').write('blocked')\n"
    )
    assert res.output == b"blocked", res


def test_environment_is_scrubbed():
    if _skip():
        return
    with env(LLM_API_KEY="geheim-123", OPENAI_API_KEY="geheim-456"):
        res = _run("open(out, 'w').write(repr(sorted(os.environ.items())))\n")
    text = res.output.decode()
    assert "geheim" not in text and "LLM_API_KEY" not in text, text
    assert "'HOME'" in text and "/Users/" not in text.split("'HOME', ")[1][:12]


def test_timeout_kills_the_generator():
    if _skip():
        return
    res = _run("while True:\n    pass\n", SandboxLimits(timeout_s=1, cpu_s=30))
    assert not res.ok and res.timed_out and "Zeitlimit" in res.error


def test_failures_are_reported_not_raised():
    if _skip():
        return
    res = _run("raise SystemExit(3)\n")
    assert not res.ok and res.exit_code == 3
    res = _run("print('nichts geschrieben')\n")
    assert not res.ok and "keine Ausgabedatei" in res.error
    res = _run(
        "open(out, 'w').write('x' * 5000)\n", SandboxLimits(20, 20, 1 << 20, 100)
    )
    assert not res.ok and "zu groß" in res.error


def test_refuses_to_run_without_sandbox():
    with patched(sandbox, "sandbox_available", lambda: False):
        e = raises(SandboxUnavailable, run_generator, "print(1)")
    assert "nicht" in str(e)


def test_profile_quotes_paths_and_denies_by_default():
    prof = sandbox.sandbox_profile('/tmp/a"b')
    assert '(subpath "/tmp/a\\"b")' in prof and "(deny default)" in prof
    assert "(allow default)" not in prof and "mach-lookup" not in prof
    assert "network" not in prof and "process-fork" not in prof


def test_other_programs_cannot_be_executed():
    """Regression: `open`/`defaults`/`launchctl` per exec ließen launchd Code
    außerhalb der Sandbox starten."""
    if _skip():
        return
    for prog in ("/usr/bin/open", "/usr/bin/defaults", "/bin/launchctl", "/bin/sh"):
        res = _run(
            "try:\n"
            f"    os.execv({prog!r}, [{prog!r}, '-h'])\n"
            "except OSError:\n"
            "    open(out, 'w').write('blocked')\n"
        )
        assert res.ok and res.output == b"blocked", (prog, res)


def test_mach_services_are_unreachable():
    """Regression: Mach-Lookup (cfprefsd, launchd) war erlaubt."""
    if _skip():
        return
    res = _run(
        "import ctypes\n"
        "lib = ctypes.CDLL('/usr/lib/libSystem.B.dylib')\n"
        "port = ctypes.c_uint(0)\n"
        "bp = ctypes.c_uint.in_dll(lib, 'bootstrap_port')\n"
        "kr = lib.bootstrap_look_up(bp, b'com.apple.cfprefsd.daemon', "
        "ctypes.byref(port))\n"
        "open(out, 'w').write('kr=%d' % kr)\n"
    )
    assert res.ok and res.output != b"kr=0", res


def test_home_and_lab_files_are_unreadable():
    """Regression: Credentials im Home (z. B. ~/.claude, Shell-Historie) waren
    lesbar; jetzt ist nur System, Python, kmx/ und das Arbeitsverzeichnis lesbar."""
    if _skip():
        return
    with tempfile.TemporaryDirectory(dir=os.path.expanduser("~")) as d:
        secret = os.path.join(d, "secret.txt")
        with open(secret, "w") as f:
            f.write("TOP-SECRET")
        main_py = os.path.join(sandbox.PACKAGE_ROOT, "main.py")
        res = _run(
            "res = []\n"
            f"for p in [{secret!r}, '/etc/passwd', {main_py!r}]:\n"
            "    try:\n"
            "        res.append('READ ' + open(p).read(20))\n"
            "    except OSError:\n"
            "        res.append('blocked')\n"
            "open(out, 'w').write(','.join(res))\n"
        )
    assert res.ok and res.output == b"blocked,blocked,blocked", res


def test_symlinked_output_is_rejected():
    """Regression: candidate.kmx als Symlink auf eine fremde Datei wurde vom
    Elternprozess gelesen (Ausleitung am Sandbox-Leseverbot vorbei)."""
    if _skip():
        return
    with tempfile.TemporaryDirectory(dir=os.path.expanduser("~")) as d:
        secret = os.path.join(d, "secret.txt")
        with open(secret, "w") as f:
            f.write("TOP-SECRET")
        res = _run(f"os.symlink({secret!r}, out)\n")
        assert not res.ok and res.output is None and "abgelehnt" in res.error, res
        res = _run(
            f"os.symlink({secret!r}, 'stdout.txt.x')\n"
            "os.replace('stdout.txt.x', 'stdout.txt')\n"
            "open(out, 'w').write('X q0')\n"
        )
        assert "TOP-SECRET" not in repr(res) and res.stdout["bytes"] == 0, res


def test_fifo_output_is_rejected_without_blocking():
    if _skip():
        return
    res = _run("os.mkfifo(out)\n")
    assert not res.ok and "abgelehnt" in res.error, res


def test_inputs_are_readable_read_only_files():
    if _skip():
        return
    res = run_generator(
        "import sys\n"
        "data = open('baseline.kmx').read()\n"
        "try:\n"
        "    open('baseline.kmx', 'w')\n"
        "    data += 'WRITABLE'\n"
        "except OSError:\n"
        "    pass\n"
        "open(sys.argv[1], 'w').write(data)\n",
        FAST,
        inputs={"baseline.kmx": b"X q0\n"},
    )
    assert res.ok and res.output == b"X q0\n", res
    assert raises(ValueError, run_generator, "1", FAST, None, {"../x": b""})


def test_crash_reports_only_exception_name_and_line():
    """Regression (Leck über KERN_PROCARGS2): Rohtext von stdout/stderr ging in
    Gegenbeispiele, Protokoll und Prompts."""
    if _skip():
        return
    res = _run("print('GEHEIM-OUT')\nraise ValueError('GEHEIM-ERR')\n")
    assert not res.ok and res.exit_code == 1, res
    assert res.exception == "ValueError" and res.line == 4, res
    assert "GEHEIM" not in repr(res) and "GEHEIM" not in res.failure()
    assert res.failure() == "Exit-Code 1, ValueError in generator.py Zeile 4"
    res = _run("class GEHEIMError(Exception):\n    pass\nraise GEHEIMError()\n")
    assert res.exception == "" and "GEHEIM" not in repr(res), res


def test_memory_disk_and_file_count_are_limited():
    """Regression: weder Speicher (RLIMIT_AS wirkt auf macOS nicht) noch die
    Summe der Dateien im Arbeitsverzeichnis war begrenzt."""
    if _skip():
        return
    limits = SandboxLimits(
        timeout_s=30, cpu_s=30, memory_bytes=512 << 20, disk_bytes=20 << 20
    )
    res = _run(
        "b = bytearray(3 << 30)\nfor i in range(0, len(b), 4096):\n    b[i] = 1\n",
        limits,
    )
    assert not res.ok and res.stopped == "memory" and "Speicher" in res.error, res
    res = _run(
        "for i in range(400):\n    open('f%d' % i, 'wb').write(b'x' * (1 << 20))\n",
        limits,
    )
    assert not res.ok and res.stopped == "disk" and "Plattenplatz" in res.error, res
    res = _run(
        "for i in range(100000):\n    open('f%d' % i, 'w').close()\n",
        SandboxLimits(timeout_s=30, cpu_s=30, max_files=500),
    )
    assert not res.ok and res.stopped == "files", res
    res = _run(
        "fs = [open('g%d' % i, 'w') for i in range(200)]\n",
        SandboxLimits(timeout_s=30, cpu_s=30, open_files=32),
    )
    assert not res.ok and res.exception == "OSError", res
