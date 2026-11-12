"""Gemeinsame Helfer der Tests: Testschaltkreise, Sitzungen, saubere Umgebung,
CLI-Aufruf ohne Netzwerk."""

import contextlib
import io
import os
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path

import kmx
import kmx.cli

HEAD = "".join(f"APPEND_TO_REGISTER q{i} r0\n" for i in range(6)) + 'REGISTER r0 "x"\n'
NHEAD = 7  # Instruktionen im Kopf; der Rumpf beginnt bei Index 7
MBU_BODY = [
    "CCX q0 q1 q8",
    "CX q8 q7",
    "CCX q7 q2 q9",
    "CZ q9 q3",
    "CCX q7 q2 q9",
    "CX q8 q7",
    "CCX q0 q1 q8",
]
GROUP_BODY = [
    "CCX q0 q1 q8",
    "CCX q0 q2 q8",
    "CCX q1 q2 q8",
    "CZ q8 q3",
    "CCX q1 q2 q8",
    "CCX q0 q2 q8",
    "CCX q0 q1 q8",
]
DIFF_BODY = [
    "CCX q0 q1 q8",
    "CX q2 q0",
    "X q0",
    "CCX q0 q1 q8",
    "X q0",
    "CX q2 q0",
    "CZ q8 q4",
    "CCX q2 q1 q8",
    "CX q1 q8",
]
CANCEL_BODY = [
    "CCX q0 q1 q8",
    "CX q2 q8",
    "CX q3 q4",
    "CCX q0 q1 q8",
    "CX q2 q8",
    "CX q3 q4",
]
# sauber: q8 endet in |0>
WB_BODY = [
    "CCX q0 q1 q8",
    "X q0",
    "CCX q0 q1 q8",
    "CX q1 q8",
    "X q0",
]
CTX_BODY = ["CCX q0 q1 q8", "CZ q8 q2", "CCX q0 q1 q8"]
TINY = "Z_POW q0 0." + "0" * 45 + "1"  # unter 2^-128: nicht auf dem Raster
ENV_KEYS = (
    "LLM_API_URL",
    "LLM_MODEL",
    "LLM_API_KEY",
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "LLM_MAX_TOKENS",
    "LLM_MAX_CALLS",
    "LLM_TIMEOUT",
    "LLM_EXTRA_BODY",
    "LLM_EXTRA_HEADERS",
    "LLM_TEMPERATURE",
    "LLM_MODE",
    "OFFICIAL_VERIFY_CMD",
    "REQUIRE_OFFICIAL_VERIFY",
    "OFFICIAL_VERIFY_TIMEOUT",
    "ALLOW_PROBABILISTIC_REWRITES",
    "TRIM_ROTATIONS",
    "EXACT_ONLY",
    "OPT_MODE",
    "LEGACY_UNSAFE_PASSES",
)


def quiet(*_):
    return None


def P(*lines):
    return kmx.parse_lines(list(lines))


def fmt(ops):
    return [o.fmt() for o in ops]


def raises(exc, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc as e:
        return e
    raise AssertionError(
        f"{exc.__name__} erwartet, aber nichts geworfen: {fn.__name__}{args}"
    )


def bit(v, lane):
    return (v >> lane) & 1


def tt_domain(qubits, meas=None):
    """Wahrheitstabellen-Domaene: Lane i belegt qubits[k] mit Bit k von i."""
    n = 1 << len(qubits)
    return kmx.Domain(
        n,
        {q: kmx.pattern_bit(i, n) for i, q in enumerate(qubits)},
        True,
        "tt",
        lambda lane: f"lane {lane}",
        truth_table=meas,
    )


def run(lines, qubits, bits=None, meas=None, seed=0, count=False):
    st = kmx.State(tt_domain(qubits, meas), seed, count)
    st.b.update(bits or {})
    for c in kmx.compile_ops(P(*lines)):
        kmx.step(st, c)
    return st


def phase_bit(st, lane):
    return bit(st.planes()[127], lane)


def circuit(body):
    return kmx.parse_text(HEAD + "\n".join(body) + "\n")


def setup(body, value_range="0:63"):
    ops = circuit(body)
    layout = kmx.analyze_layout(ops, "x", value_range)
    dom, sample_dom = kmx.build_domains(layout, 1 << 20, 64, 64)
    return ops, layout, dom, sample_dom


def make_session(body, value_range="0:63", opts=None):
    ops, layout, dom, sample_dom = setup(body, value_range)
    s = kmx.Session(
        ops, layout, dom, sample_dom, opts or kmx.Options(final_rounds=4), log=quiet
    )
    s.run_baseline()
    return s


def toffoli(ops):
    return kmx.compute_metrics(ops).toffoli


@contextlib.contextmanager
def env(**overrides):
    """Saubere Umgebung: alle fuer main.py relevanten Variablen entfernt,
    dann `overrides` gesetzt."""
    saved = {k: os.environ.get(k) for k in set(ENV_KEYS) | set(overrides)}
    try:
        for k in saved:
            os.environ.pop(k, None)
        for k, v in overrides.items():
            if v is not None:
                os.environ[k] = v
        yield
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v


@contextlib.contextmanager
def patched(obj, name, value):
    old = getattr(obj, name)
    setattr(obj, name, value)
    try:
        yield
    finally:
        setattr(obj, name, old)


def _network_forbidden(*_a, **_k):
    raise AssertionError("Test hat versucht, das Netzwerk zu benutzen")


@contextlib.contextmanager
def no_network():
    with (
        patched(socket, "create_connection", _network_forbidden),
        patched(urllib.request, "urlopen", _network_forbidden),
    ):
        yield


def cli(*argv, **environ):
    """kmx.cli.main(...) mit sauberer Umgebung, ohne Netzwerk, stdout eingefangen."""
    buf = io.StringIO()
    with env(**environ), no_network(), contextlib.redirect_stdout(buf):
        rc = kmx.cli.main(list(argv))
    return rc, buf.getvalue()


def write_input(directory, body=MBU_BODY, name="in.kmx"):
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(HEAD + "\n".join(body) + "\n")
    return path


def make_wb(body=WB_BODY, value_range="0:63", **kw):
    return kmx.Workbench(make_session(body, value_range), **kw)


PROJECT_DIR = Path(__file__).resolve().parents[2]  # Verzeichnis mit main.py und kmx/
MAIN_PY = str(PROJECT_DIR / "main.py")
DATA_DIR = Path(__file__).resolve().parent / "data"


def run_main(*argv, **environ):
    """main.py als eigener Prozess mit sauberer Umgebung (LLM aus)."""
    env_vars = {k: v for k, v in os.environ.items() if k not in ENV_KEYS}
    env_vars.update(LLM_MAX_CALLS="0", **environ)
    return subprocess.run(
        [sys.executable, MAIN_PY, *argv],
        capture_output=True,
        text=True,
        env=env_vars,
        timeout=600,
    )
