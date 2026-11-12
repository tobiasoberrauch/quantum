"""Sandbox für Generator-Kandidaten (Python-Quelltext, der einen Schaltkreis nach
argv[1] schreibt).

Ausgeführt wird nur unter macOS `/usr/bin/sandbox-exec` mit einem Profil, das ALLES
verbietet (`deny default`) und nur das Nötige erlaubt: Ausführen genau des einen
Python-Interpreters, Lesen von Systembibliotheken, Python-Installation, `kmx/` und dem
Arbeitsverzeichnis, Schreiben nur im Arbeitsverzeichnis. Damit sind Netzwerk, Forks,
fremde Programme (`open`, `defaults`, `launchctl`, Shells), Mach-/XPC-Dienste
(launchd, LaunchServices, cfprefsd) und das Lesen des Home-Verzeichnisses gesperrt.
Dazu: bereinigte Umgebung (keine API-Schlüssel), `python -I -B`, `ulimit -t` (CPU),
`ulimit -f` (Dateigröße), `ulimit -n` (offene Dateien), eine Obergrenze der Ausgabe und
ein Wächter (`kmx.lab.watchdog`), der bei Wanduhr-Timeout, zu viel Speicher, zu viel
Plattenplatz oder zu vielen Dateien im Arbeitsverzeichnis die ganze Prozessgruppe
beendet. Fehlt sandbox-exec, wird NICHT ungeschützt ausgeführt (`SandboxUnavailable`).

`sysctl-read` muss erlaubt bleiben (sonst startet der Interpreter nicht); damit kann ein
Generator per KERN_PROCARGS2 die Start-Umgebung anderer Prozesse desselben Benutzers
lesen. Deshalb liefert `run_generator` KEINEN Rohtext von stdout/stderr zurück, nur
Hash, Länge, eine bekannte Ausnahmeart und die Zeilennummer (`kmx.lab.untrusted`).

Der (nicht sandboxierte) Elternprozess liest Ausgabe und Logs nur als reguläre Dateien
ohne Symlinks und harte Links (`_open_regular`), damit ein Generator keine fremden
Dateien über den Richter ausleiten kann.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kmx.lab.untrusted import exception_name, generator_line, stream_digest
from kmx.lab.watchdog import STOP_TIMEOUT, Budget, watch

SANDBOX_EXEC = "/usr/bin/sandbox-exec"
PACKAGE_ROOT = str(Path(__file__).resolve().parents[2])  # Verzeichnis mit kmx/
GENERATOR_FILE, OUTPUT_FILE = "generator.py", "candidate.kmx"
STDOUT_FILE, STDERR_FILE = "stdout.txt", "stderr.txt"
_RESERVED = (GENERATOR_FILE, OUTPUT_FILE, STDOUT_FILE, STDERR_FILE)
DEFAULT_TIMEOUT_S = 120
DEFAULT_CPU_S = 120
DEFAULT_FSIZE_BYTES = 64 << 20
DEFAULT_OUTPUT_CAP = 32 << 20
DEFAULT_MEMORY_BYTES = 2 << 30
DEFAULT_DISK_BYTES = 256 << 20
DEFAULT_MAX_FILES = 2000
DEFAULT_OPEN_FILES = 64
LOG_TAIL_CHARS = 2000
STOP_MESSAGES = {
    STOP_TIMEOUT: "Zeitlimit überschritten",
    "memory": "Speicherlimit überschritten",
    "disk": "Plattenplatz-Limit im Arbeitsverzeichnis überschritten",
    "files": "zu viele Dateien im Arbeitsverzeichnis",
}
_ULIMIT_BLOCK = 512  # Einheit von `ulimit -f` in /bin/sh
SANDBOX_PATH = "/usr/bin:/bin"
# Systempfade, die der Interpreter zum Starten lesen muss (dyld, libSystem, Locale)
SYSTEM_READ_SUBPATHS = ("/usr/lib", "/usr/share", "/System", "/private/var/db/timezone")
SYSTEM_READ_LITERALS = ("/", "/dev/null", "/dev/urandom", "/dev/random")


class SandboxUnavailable(RuntimeError):
    """Keine Sandbox verfügbar: Generatoren werden dann gar nicht ausgeführt."""


@dataclass(frozen=True)
class SandboxLimits:
    timeout_s: float = DEFAULT_TIMEOUT_S
    cpu_s: int = DEFAULT_CPU_S
    fsize_bytes: int = DEFAULT_FSIZE_BYTES
    output_cap: int = DEFAULT_OUTPUT_CAP
    memory_bytes: int = DEFAULT_MEMORY_BYTES
    disk_bytes: int = DEFAULT_DISK_BYTES
    max_files: int = DEFAULT_MAX_FILES
    open_files: int = DEFAULT_OPEN_FILES


@dataclass
class SandboxResult:
    """Ergebnis eines Generatorlaufs; `output` ist der geschriebene Schaltkreis.
    stdout/stderr nur als Hash und Länge (`stdout`, `stderr`), dazu die erkannte
    eingebaute Ausnahme und die Zeilennummer im Generator; kein Rohtext."""

    ok: bool
    exit_code: int | None
    timed_out: bool
    output: bytes | None
    stdout: dict[str, Any]
    stderr: dict[str, Any]
    error: str = ""
    exception: str = ""
    line: int | None = None
    stopped: str = ""

    def failure(self) -> str:
        """Kurzbeschreibung ohne Rohtext, z. B. 'Exit-Code 1, ValueError in
        generator.py Zeile 7'."""
        parts = [self.error]
        if self.exception:
            where = f" in generator.py Zeile {self.line}" if self.line else ""
            parts.append(self.exception + where)
        return ", ".join(p for p in parts if p)


def sandbox_available() -> bool:
    return sys.platform == "darwin" and os.access(SANDBOX_EXEC, os.X_OK)


def _sb_quote(path: str) -> str:
    """Pfad als String-Literal der Sandbox-Profilsprache."""
    return '"' + path.replace("\\", "\\\\").replace('"', '\\"') + '"'


def interpreter_paths(python: str) -> tuple[list[str], list[str]]:
    """(ausführbare Dateien, lesbare Installationsverzeichnisse) des Interpreters:
    der Pfad selbst, sein Symlink-Ziel und die Präfixe (venv und Basisinstallation)."""
    exes = sorted({os.path.abspath(python), os.path.realpath(python)})
    roots = {os.path.dirname(os.path.dirname(p)) for p in exes}
    if os.path.realpath(python) == os.path.realpath(sys.executable):
        roots |= {sys.prefix, sys.base_prefix, sys.exec_prefix, sys.base_exec_prefix}
    roots |= {os.path.realpath(r) for r in roots}
    return exes, sorted(r for r in roots if r and r != "/")


def sandbox_profile(work_dir: str, python: str = sys.executable) -> str:
    """Profil nach dem Prinzip "alles verboten, nur das Nötige erlaubt": exec nur des
    Interpreters, Lesen nur von System, Python, `kmx/` und `work_dir`, Schreiben nur
    in `work_dir` (und /dev/null); kein Netzwerk, kein Fork, keine Mach-Dienste."""
    exes, roots = interpreter_paths(python)
    pkg = os.path.join(PACKAGE_ROOT, "kmx")
    read_sub = [*SYSTEM_READ_SUBPATHS, *roots, pkg, os.path.realpath(pkg), work_dir]
    read_lit = [*SYSTEM_READ_LITERALS, PACKAGE_ROOT, os.path.realpath(PACKAGE_ROOT)]

    def paths(kind: str, items: list[str]) -> str:
        return " ".join(f"({kind} {_sb_quote(p)})" for p in dict.fromkeys(items))

    return (
        "(version 1)\n(deny default)\n"
        f"(allow process-exec {paths('literal', exes)})\n"
        "(allow file-read-metadata)\n"
        f"(allow file-read* {paths('subpath', read_sub)} "
        f"{paths('literal', read_lit)})\n"
        f'(allow file-write* (subpath {_sb_quote(work_dir)}) (literal "/dev/null"))\n'
        "(allow sysctl-read)\n"
    )


def scrubbed_env(work_dir: str) -> dict[str, str]:
    """Minimale Umgebung: keine Schlüssel, HOME und TMPDIR = Arbeitsverzeichnis."""
    return {
        "PATH": SANDBOX_PATH,
        "HOME": work_dir,
        "TMPDIR": work_dir,
        "LANG": "en_US.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
    }


def _bootstrap(generator: str, output: str) -> str:
    """Python-Startcode: Paket lesbar machen, argv setzen, Generator ausführen."""
    return (
        "import runpy, sys; "
        f"sys.path.insert(0, {PACKAGE_ROOT!r}); "
        f"sys.argv = [{generator!r}, {output!r}]; "
        f"runpy.run_path({generator!r}, run_name='__main__')"
    )


def _command(work_dir: str, limits: SandboxLimits, python: str) -> list[str]:
    generator = os.path.join(work_dir, GENERATOR_FILE)
    output = os.path.join(work_dir, OUTPUT_FILE)
    blocks = max(1, limits.fsize_bytes // _ULIMIT_BLOCK)
    profile = sandbox_profile(work_dir, python)
    # ulimit setzt die Grenzen in der Shell, exec ersetzt sie durch sandbox-exec
    script = (
        f"ulimit -t {int(limits.cpu_s)}; ulimit -f {blocks}; "
        f'ulimit -n {int(limits.open_files)}; exec "$@"'
    )
    return [
        "/bin/sh",
        "-c",
        script,
        "sh",
        SANDBOX_EXEC,
        "-p",
        profile,
        python,
        "-I",
        "-B",
        "-c",
        _bootstrap(generator, output),
    ]


def _open_regular(path: str) -> tuple[int | None, str]:
    """Öffnet `path` nur als reguläre Datei mit genau einem Link, ohne Symlinks zu
    folgen und ohne auf FIFOs zu blockieren: (Deskriptor, Problem)."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None, "fehlt"
    except OSError as e:
        return None, f"nicht als reguläre Datei lesbar ({e.strerror})"
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
        os.close(fd)
        return None, "keine reguläre Datei (Symlink, Gerät, FIFO oder harter Link)"
    return fd, ""


def _tail(path: str) -> bytes:
    fd, _ = _open_regular(path)
    if fd is None:
        return b""
    with os.fdopen(fd, "rb") as f:
        f.seek(0, os.SEEK_END)
        f.seek(max(0, f.tell() - LOG_TAIL_CHARS))
        return f.read()


def _read_output(path: str, cap: int) -> tuple[bytes | None, str]:
    fd, problem = _open_regular(path)
    if fd is None:
        if problem == "fehlt":
            return None, "Generator hat keine Ausgabedatei geschrieben (argv[1])"
        return None, f"Ausgabedatei abgelehnt: {problem}"
    with os.fdopen(fd, "rb") as f:
        data = f.read(cap + 1)
    if len(data) > cap:
        return None, f"Ausgabe zu groß (> {cap} Bytes)"
    return data, ""


def _write_inputs(work_dir: str, inputs: Mapping[str, bytes] | None) -> None:
    """Legt schreibgeschützte Eingabedateien (z. B. die Basis) ins Arbeitsverzeichnis;
    nur einfache Dateinamen."""
    for name, data in (inputs or {}).items():
        if os.path.basename(name) != name or name in _RESERVED or name.startswith("."):
            raise ValueError(f"ungültiger Eingabename {name!r}")
        path = os.path.join(work_dir, name)
        with open(path, "wb") as f:
            f.write(data)
        os.chmod(path, 0o444)


def _budget(limits: SandboxLimits) -> Budget:
    return Budget(
        limits.timeout_s, limits.memory_bytes, limits.disk_bytes, limits.max_files
    )


def _result(
    work_dir: str, limits: SandboxLimits, code: int | None, stopped: str
) -> SandboxResult:
    """Ergebnis ohne Rohtext: Ströme nur als Hash/Länge, Ausnahme nur als Name."""
    out = _tail(os.path.join(work_dir, STDOUT_FILE))
    err = _tail(os.path.join(work_dir, STDERR_FILE))
    err_text = err.decode("utf-8", "replace")
    res = SandboxResult(
        False,
        code,
        stopped == STOP_TIMEOUT,
        None,
        stream_digest(out),
        stream_digest(err),
        exception=exception_name(err_text),
        line=generator_line(err_text),
        stopped=stopped,
    )
    if stopped:
        res.error = STOP_MESSAGES.get(stopped, stopped)
        return res
    if code != 0:
        res.error = f"Exit-Code {code}"
        return res
    res.output, res.error = _read_output(
        os.path.join(work_dir, OUTPUT_FILE), limits.output_cap
    )
    res.ok = res.output is not None
    return res


def run_generator(
    source: str,
    limits: SandboxLimits | None = None,
    python: str | None = None,
    inputs: Mapping[str, bytes] | None = None,
) -> SandboxResult:
    """Führt `source` in der Sandbox aus und liefert die geschriebene Ausgabe.
    `inputs` (Dateiname -> Inhalt) liegen schreibgeschützt im Arbeitsverzeichnis
    (= aktuelles Verzeichnis des Generators)."""
    if not sandbox_available():
        raise SandboxUnavailable(
            "sandbox-exec nicht verfügbar: Generator-Kandidaten werden nicht "
            "ausgeführt (kein ungeschützter Fallback)"
        )
    limits = limits or SandboxLimits()
    work_dir = os.path.realpath(tempfile.mkdtemp(prefix="kmx-lab-gen-"))
    try:
        with open(os.path.join(work_dir, GENERATOR_FILE), "w", encoding="utf-8") as f:
            f.write(source)
        _write_inputs(work_dir, inputs)
        with (
            open(os.path.join(work_dir, STDOUT_FILE), "wb") as out,
            open(os.path.join(work_dir, STDERR_FILE), "wb") as err,
        ):
            proc = subprocess.Popen(
                _command(work_dir, limits, python or sys.executable),
                cwd=work_dir,
                env=scrubbed_env(work_dir),
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                start_new_session=True,
            )
            code, stopped = watch(proc, work_dir, _budget(limits))
        return _result(work_dir, limits, code, stopped)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
