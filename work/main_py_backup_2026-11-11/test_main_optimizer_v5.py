#!/usr/bin/env python3
"""Tests fuer main.py (v5): verifier-gestuetzter Optimierer fuer kickmix-Schaltkreise (.kmx).

Laufbar OHNE pytest und OHNE Netzwerk (LLM wird per Stub/Fake ersetzt):
    KMX_MAIN=/pfad/zu/main.py python test_main_optimizer.py
Unter pytest laufen dieselben test_*-Funktionen. Alle Schaltkreise sind winzig (6-Bit-Register, --range 0:63).

Vermutete, noch offene Fehler kommen als Funktionen mit Praefix `bug_` (Kommentar "BUG?") hinzu; sie gehoeren NICHT
zur bestandenen Menge, `python test_main_optimizer.py --bugs` fuehrt sie zusaetzlich aus. Derzeit gibt es keine.
"""

import contextlib
import importlib.util
import io
import json
import os
import random
import sys
import tempfile
import time
import urllib.error
from fractions import Fraction

_path = os.environ.get("KMX_MAIN", os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py"))
_spec = importlib.util.spec_from_file_location("M", _path)
M = importlib.util.module_from_spec(_spec)
sys.modules["M"] = M  # vor exec_module: das Modul benutzt dataclasses
_spec.loader.exec_module(M)


# ------------------------------------------------------------------ Helfer
HEAD = "".join(f"APPEND_TO_REGISTER q{i} r0\n" for i in range(6)) + 'REGISTER r0 "x"\n'
NHEAD = 7  # Instruktionen im Kopf; der Rumpf beginnt bei Index 7
MBU_BODY = ["CCX q0 q1 q8", "CX q8 q7", "CCX q7 q2 q9", "CZ q9 q3", "CCX q7 q2 q9", "CX q8 q7", "CCX q0 q1 q8"]
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
CANCEL_BODY = ["CCX q0 q1 q8", "CX q2 q8", "CX q3 q4", "CCX q0 q1 q8", "CX q2 q8", "CX q3 q4"]
WB_BODY = ["CCX q0 q1 q8", "X q0", "CCX q0 q1 q8", "CX q1 q8", "X q0"]  # sauber: q8 endet in |0>
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
    return M.parse_lines(list(lines))


def fmt(ops):
    return [o.fmt() for o in ops]


def raises(exc, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc as e:
        return e
    raise AssertionError(f"{exc.__name__} erwartet, aber nichts geworfen: {fn.__name__}{args}")


def bit(v, lane):
    return (v >> lane) & 1


def tt_domain(qubits, meas=None):
    """Wahrheitstabellen-Domaene: Lane i belegt qubits[k] mit Bit k von i."""
    n = 1 << len(qubits)
    return M.Domain(
        n, {q: M.pattern_bit(i, n) for i, q in enumerate(qubits)}, True, "tt", lambda lane: f"lane {lane}", tt=meas
    )


def run(lines, qubits, bits=None, meas=None, seed=0, count=False):
    st = M.State(tt_domain(qubits, meas), seed, count)
    st.b.update(bits or {})
    for c in M.compile_ops(P(*lines)):
        M.step(st, c)
    return st


def phase_bit(st, lane):
    return bit(st.planes()[127], lane)


def circuit(body):
    return M.parse_text(HEAD + "\n".join(body) + "\n")


def setup(body, value_range="0:63"):
    ops = circuit(body)
    layout = M.analyze_layout(ops, "x", value_range)
    dom, smp = M.build_domains(layout, 1 << 20, 64, 64)
    return ops, layout, dom, smp


def make_session(body, value_range="0:63", opts=None):
    ops, layout, dom, smp = setup(body, value_range)
    s = M.Session(ops, layout, dom, smp, opts or M.Options(final_rounds=4), log=quiet)
    s.baseline()
    return s


def toffoli(ops):
    return M.compute_metrics(ops).toffoli


@contextlib.contextmanager
def env(**overrides):
    """Saubere Umgebung: alle fuer main.py relevanten Variablen entfernt, dann `overrides` gesetzt."""
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
        patched(M.socket, "create_connection", _network_forbidden),
        patched(M.urllib.request, "urlopen", _network_forbidden),
    ):
        yield


def cli(*argv, **environ):
    """M.main(...) mit sauberer Umgebung, ohne Netzwerk, stdout eingefangen."""
    buf = io.StringIO()
    with env(**environ), no_network(), contextlib.redirect_stdout(buf):
        rc = M.main(list(argv))
    return rc, buf.getvalue()


def write_input(directory, body=MBU_BODY, name="in.kmx"):
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(HEAD + "\n".join(body) + "\n")
    return path


# ============================================================ 1. Parser
def test_parser_accepts_plain_gate_lines():
    op = M.parse_line("CCX q0 q1 q2")
    assert (op.name, op.args, op.qs, op.cond, op.bit, op.text) == (
        "CCX",
        ("q0", "q1", "q2"),
        (0, 1, 2),
        None,
        None,
        None,
    )
    assert M.parse_line("HMR q4 b7").bit == 7 and M.parse_line("HMR q4 b7").qs == (4,)
    assert M.parse_line("NEG").args == () and M.parse_line("POP_CONDITION").name == "POP_CONDITION"
    assert M.parse_line("Z_POW q3 -0.125").args == ("q3", "-0.125")
    assert M.parse_line("BIT_STORE1 b2").bit == 2


def test_parser_reads_trailing_condition():
    op = M.parse_line("CZ q0 q1 if b3")
    assert op.cond == 3 and op.qs == (0, 1) and op.fmt() == "CZ q0 q1 if b3"
    assert M.parse_line("Z_POW q0 0.5 if b0").cond == 0
    assert M.parse_line("PUSH_CONDITION if b5").cond == 5


def test_parser_tolerates_v1_push_condition_and_emits_v2():
    op = M.parse_line("PUSH_CONDITION b3")
    assert op.cond == 3 and op.args == () and op.fmt() == "PUSH_CONDITION if b3"


def test_parser_skips_comments_and_blank_lines():
    assert M.parse_line("# nur Kommentar") is None and M.parse_line("   ") is None
    assert M.parse_line("X q0   # danach").fmt() == "X q0"
    ops = M.parse_text("# a\n\nX q0\n  CX q0 q1 # b\n")
    assert fmt(ops) == ["X q0", "CX q0 q1"]


def test_parser_keeps_quoted_text():
    reg = M.parse_line('REGISTER r0 "x"')
    tag = M.parse_line('INFO_TAG "@enter:adder stage"')
    assert reg.text == '"x"' and reg.args == ("r0",) and reg.fmt() == 'REGISTER r0 "x"'
    assert tag.text == '"@enter:adder stage"' and tag.args == ()


def test_parser_rejects_duplicate_qubits():
    for line in ("CX q0 q0", "CCX q0 q1 q0", "SWAP q2 q2", "CSWAP q1 q1 q2", "CZ q3 q3"):
        e = raises(M.KmxError, M.parse_line, line)
        assert "mehrfach" in str(e), line


def test_parser_rejects_unknown_ops_and_wrong_arity():
    assert "unbekannte Instruktion" in str(raises(M.KmxError, M.parse_line, "T q0"))
    assert "unbekannte Instruktion" in str(raises(M.KmxError, M.parse_line, "x q0"))
    for line in (
        "X",
        "X q0 q1",
        "CX q0",
        "CX q0 b1",
        "HMR q0 q1",
        "HMR q0",
        "NEG q0",
        "BIT_STORE0 q0",
        "PUSH_CONDITION",
        "POP_CONDITION if b0",
        "X b0",
    ):
        raises(M.KmxError, M.parse_line, line)


def test_parser_rejects_fraction_and_exponent_notation_angles():
    for angle in ("1/4", "1e-3", "2.5E-1", ".5", "5.", "0x1", "pi"):
        e = raises(M.KmxError, M.parse_line, f"Z_POW q0 {angle}")
        assert "Z_POW" in str(e), angle
    for angle in ("0.25", "-0.75", "+0.5", "12.000390625"):
        assert M.parse_line(f"Z_POW q0 {angle}").args[1] == angle


def test_parser_rejects_bad_conditions():
    assert "Bedingung" in str(raises(M.KmxError, M.parse_line, "X q0 if q1"))
    assert "Bedingung" in str(raises(M.KmxError, M.parse_line, "X q0 if 1"))
    raises(M.KmxError, M.parse_line, "X q0 if")
    raises(M.KmxError, M.parse_line, "X q0 if b1 if b2")


def test_parse_errors_carry_line_number_and_non_strings_are_rejected():
    e = raises(M.KmxError, M.parse_text, "X q0\nCX q1 q1\n")
    assert "Zeile 2" in str(e)
    e = raises(M.KmxError, M.parse_lines, ["X q0", 5])
    assert "Eintrag 1" in str(e)


def test_format_ops_roundtrips_through_parser():
    text = HEAD + "CCX q0 q1 q8\nHMR q8 b0\nCZ q0 q1 if b0\nPUSH_CONDITION if b0\nZ_POW q2 -0.25\nPOP_CONDITION\nNEG\n"
    assert M.format_ops(M.parse_text(text)) == text


# ============================================================ 2. Op.key / Op.renamed
def test_op_key_canonicalises_symmetric_arguments():
    key = lambda s: M.parse_line(s).key()
    assert key("CZ q1 q0") == key("CZ q0 q1")
    assert key("CCZ q2 q0 q1") == key("CCZ q0 q1 q2")
    assert key("SWAP q4 q3") == key("SWAP q3 q4")
    assert key("CCX q1 q0 q2") == key("CCX q0 q1 q2")
    assert key("CSWAP q0 q2 q1") == key("CSWAP q0 q1 q2")


def test_op_key_keeps_order_where_it_matters():
    key = lambda s: M.parse_line(s).key()
    assert key("CX q0 q1") != key("CX q1 q0")
    assert key("CCX q0 q2 q1") != key("CCX q0 q1 q2")  # anderes Ziel
    assert key("CSWAP q1 q0 q2") != key("CSWAP q0 q1 q2")  # andere Kontrolle
    assert key("CZ q0 q1 if b0") != key("CZ q0 q1")
    assert key("CZ q0 q1 if b0") != key("CZ q0 q1 if b1")
    assert key("Z_POW q0 0.25") != key("Z_POW q0 0.5")


def test_op_renamed_maps_qubits_only():
    op = M.parse_line("HMR q8 b8 if b3")
    zp = M.parse_line("Z_POW q8 0.125")
    assert op.renamed({8: 6}).fmt() == "HMR q6 b8 if b3"  # Bit b8 bleibt, nur q8 wandert
    assert zp.renamed({8: 2}).fmt() == "Z_POW q2 0.125"
    assert M.parse_line("CCX q1 q2 q3").renamed({1: 3, 3: 1}).fmt() == "CCX q3 q2 q1"
    assert op.renamed({5: 6}) is op  # nichts betroffen: dasselbe Objekt
    assert op.fmt() == "HMR q8 b8 if b3"  # Original unveraendert


# ============================================================ 3. Metriken und Kosten
def test_compute_metrics_q_is_max_index_plus_one():
    m = M.compute_metrics(P("X q3", "CX q61 q2"))
    assert m.num_qubits == 62 and m.distinct_qubits == 3 and m.ops == 2
    assert M.compute_metrics([]).num_qubits == 0
    assert M.compute_metrics(P("NEG", "BIT_STORE1 b9")).num_qubits == 0  # Bits zaehlen nicht als Qubits


def test_compute_metrics_accepts_text_lines_and_ignores_comments():
    m = M.compute_metrics(["# q999 nur Kommentar", "CSWAP q3 q61 q2", "CCX q3 q61 q2", "Z_POW q3 0.25"])
    assert (m.num_qubits, m.ops, m.toffoli, m.toffoli_cost, m.t_like, m.rotations) == (62, 3, 2, 2, 1, 0)


def test_compute_metrics_counts_toffoli_like_gates_only():
    m = M.compute_metrics(
        [
            "CCX q0 q1 q2",
            "CCZ q0 q1 q2",
            "CSWAP q0 q1 q2",
            "CCX q0 q1 q2 if b0",
            "CX q0 q1",
            "CZ q0 q1",
            "SWAP q0 q1",
            "X q0",
            "Z q0",
            "HMR q2 b0",
            "NEG",
        ]
    )
    assert m.toffoli == 4 and m.counts["CCX"] == 2 and m.counts["CX"] == 1
    assert M.compute_metrics(["CX q0 q1", "CZ q0 q1", "SWAP q0 q1", "X q0", "Z q0"]).toffoli == 0


def test_zpow_classification_clifford_t_like_fine():
    level = lambda e: M.zpow_info(e)[1]
    assert [level(e) for e in ("0.5", "1.0", "-0.5", "1.5", "2.0")] == [0] * 5  # Clifford: frei
    assert [level(e) for e in ("0.25", "-0.25", "0.75", "1.25")] == [2] * 4  # T-artig
    assert [level(e) for e in ("0.125", "0.0625", "0.3", "-0.001")] == [3] * 4  # feine Rotation
    m = M.compute_metrics(["Z_POW q0 0.5", "Z_POW q0 0.25", "Z_POW q0 0.75", "Z_POW q0 0.125", "Z q0"])
    assert (m.t_like, m.rotations) == (2, 1)


def test_circuit_cost_is_q_times_inner_cost():
    assert M.circuit_cost([]) == 0.0
    assert M.circuit_cost(["CX q0 q1", "SWAP q0 q1", "X q0", "CZ q0 q1", "Z_POW q0 0.5"]) == 0.0
    assert M.circuit_cost(["CCX q0 q1 q2"]) == 3.0  # Q=3 x 1 Toffoli
    assert M.circuit_cost(["CCX q0 q1 q9", "CCZ q0 q1 q2"]) == 20.0  # Q=10 x 2
    assert abs(M.circuit_cost(["Z_POW q0 0.25"]) - 0.25) < 1e-12  # 1 T = 1/4 Toffoli
    assert abs(M.circuit_cost(["Z_POW q1 0.125"]) - 2 * M.ROT_WEIGHT) < 1e-9
    assert M.circuit_cost(P("CCX q0 q1 q2")) == M.circuit_cost(["CCX q0 q1 q2"])
    assert abs(M.score_estimate(10, 2.0, 4.0, 1.0, 7.0) - 10 * (2 + 1 + 7)) < 1e-12


# ============================================================ 4. Phasen-Arithmetik
def test_phase_exponent_exact_on_grid_only():
    assert M.phase_exponent(M.parse_line("Z q0")) == Fraction(1)
    assert M.phase_exponent(M.parse_line("Z_POW q0 0.25")) == Fraction(1, 4)
    assert M.phase_exponent(M.parse_line("Z_POW q0 -1.5")) == Fraction(-3, 2)
    on_grid = M.phase_op(0, Fraction(1, 1 << 127), None)
    assert M.phase_exponent(on_grid) == Fraction(1, 1 << 127)
    assert M.phase_exponent(M.parse_line(TINY)) is None  # 10^-46 liegt nicht auf dem Raster
    assert M.phase_exponent(M.parse_line("Z_POW q0 0.3")) is None
    assert M.phase_exponent(M.parse_line("CZ q0 q1")) is None and M.phase_exponent(M.parse_line("X q0")) is None


def test_phase_op_zero_gives_none_and_one_gives_z():
    assert M.phase_op(0, Fraction(0), None) is None
    assert M.phase_op(0, Fraction(2), None) is None and M.phase_op(0, Fraction(-4), None) is None
    assert M.phase_op(3, Fraction(1), None).fmt() == "Z q3"
    assert M.phase_op(3, Fraction(3), 7).fmt() == "Z q3 if b7"
    assert M.phase_op(3, Fraction(-1), None).fmt() == "Z q3"


def test_phase_op_wraps_mod_two_with_exact_decimal():
    text = lambda a, b: M.phase_op(0, Fraction(a, b), None).fmt()
    assert text(7, 4) == "Z_POW q0 -0.25"
    assert text(3, 2) == "Z_POW q0 -0.5"
    assert text(9, 4) == "Z_POW q0 0.25"
    assert text(-1, 8) == "Z_POW q0 -0.125"
    assert text(1, 1 << 40) == "Z_POW q0 0.0000000000009094947017729282379150390625"
    assert M.phase_op(5, Fraction(1, 4), 2).fmt() == "Z_POW q5 0.25 if b2"


def test_phase_op_output_is_valid_kmx_and_exact_for_random_grid_angles():
    rng = random.Random(11)
    for _ in range(300):
        fr = Fraction(rng.randrange(-(1 << 20), 1 << 20), 1 << rng.randrange(0, 128))
        op = M.phase_op(1, fr, None)
        if op is None:
            assert fr % 2 == 0
            continue
        assert M.parse_line(op.fmt()).key() == op.key()  # keine Brueche, kein 1e-5
        assert "e" not in op.fmt().lower() and "/" not in op.fmt()
        assert (M.phase_exponent(op) - fr) % 2 == 0, (fr, op)


# ============================================================ 5. pattern_bit und Domaenen
def test_pattern_bit_lane_i_carries_bit_k_of_i():
    for m in (1, 5, 8, 37, 64):
        for k in range(7):
            v = M.pattern_bit(k, m)
            assert v < (1 << m)
            assert all(bit(v, i) == (i >> k) & 1 for i in range(m)), (k, m)


def test_exhaustive_domain_enumerates_the_value_range():
    ops, layout, _, _ = setup([], "3:10")
    dom = M.exhaustive_domain(layout)
    assert dom.n == 8 and dom.exhaustive and dom.ALL == 0xFF
    for lane in range(8):
        x = sum(bit(dom.init_q[q], lane) << k for k, q in enumerate(layout.input_qubits))
        assert x == 3 + lane
    assert dom.describe(2) == "x=5"


def test_sample_domain_is_seeded_and_stays_in_range():
    _, layout, _, _ = setup([], "5:40")
    a, b, c = M.sample_domain(layout, 32, 1), M.sample_domain(layout, 32, 1), M.sample_domain(layout, 32, 2)
    values = [sum(bit(a.init_q[q], lane) << k for k, q in enumerate(layout.input_qubits)) for lane in range(32)]
    assert a.init_q == b.init_q and a.init_q != c.init_q
    assert not a.exhaustive and a.n == 32
    assert all(5 <= v <= 40 for v in values) and 5 in values and 40 in values


def test_build_domains_exhaustive_only_when_range_is_small_enough():
    _, layout, dom, smp = setup([], "0:63")
    assert dom.exhaustive and dom.n == 64 and not smp.exhaustive and smp.n == 64
    too_big, _ = M.build_domains(layout, 32, 16, 48)  # max_exhaustive < 64
    assert not too_big.exhaustive and too_big.n == 48
    _, no_range, _, _ = setup([], None)
    unknown, _ = M.build_domains(no_range, 1 << 20, 16, 48)
    assert no_range.lo is None and not unknown.exhaustive


def test_analyze_layout_register_names_and_fallbacks():
    ops = M.parse_text(HEAD + 'APPEND_TO_REGISTER q9 r1\nAPPEND_TO_REGISTER b4 r1\nREGISTER r1 "out"\n')
    by_name = M.analyze_layout(ops, "x", "0:63")
    other = M.analyze_layout(ops, "nope", "0:63")
    bare = M.analyze_layout(P("CX q0 q1"))
    assert by_name.input_qubits == [0, 1, 2, 3, 4, 5] and by_name.pinned == {0, 1, 2, 3, 4, 5, 9}
    assert by_name.reg_bits == [4] and by_name.names == {0: "x", 1: "out"} and not by_name.invsqrt
    assert (by_name.lo, by_name.hi) == (0, 63) and not by_name.notes
    assert other.input_qubits == [0, 1, 2, 3, 4, 5] and any("nope" in n for n in other.notes)
    assert bare.input_qubits == list(range(22)) and (bare.lo, bare.hi) == (1, M.INVSQRT_MAX_X) and bare.invsqrt


# ============================================================ 6. Simulator
def test_sim_ccx_truth_table():
    st = run(["CCX q0 q1 q2"], [0, 1, 2])
    for lane in range(8):
        a, b, c = lane & 1, (lane >> 1) & 1, (lane >> 2) & 1
        assert (bit(st.q[0], lane), bit(st.q[1], lane), bit(st.q[2], lane)) == (a, b, c ^ (a & b))
    assert st.planes() == [0] * 128


def test_sim_x_cx_swap_cswap_truth_tables():
    st = run(["CSWAP q0 q1 q2"], [0, 1, 2])
    sw = run(["SWAP q0 q1", "X q2", "CX q2 q3"], [0, 1, 2, 3])
    for lane in range(8):
        a, b, c = lane & 1, (lane >> 1) & 1, (lane >> 2) & 1
        want = (a, c, b) if a else (a, b, c)
        assert (bit(st.q[0], lane), bit(st.q[1], lane), bit(st.q[2], lane)) == want
    for lane in range(16):
        a, b, c, d = (bit(lane, k) for k in range(4))
        got = tuple(bit(sw.q[q], lane) for q in range(4))
        assert got == (b, a, c ^ 1, d ^ c ^ 1)


def test_sim_z_cz_ccz_neg_phases():
    for lines, want in (
        (["Z q0"], lambda a, b, c: a),
        (["CZ q0 q1"], lambda a, b, c: a & b),
        (["CCZ q0 q1 q2"], lambda a, b, c: a & b & c),
        (["NEG"], lambda a, b, c: 1),
        (["CZ q0 q1", "CZ q1 q0"], lambda a, b, c: 0),
        (["Z q2", "NEG"], lambda a, b, c: c ^ 1),
    ):
        st = run(lines, [0, 1, 2])
        for lane in range(8):
            a, b, c = lane & 1, (lane >> 1) & 1, (lane >> 2) & 1
            assert phase_bit(st, lane) == want(a, b, c), (lines, lane)
        assert all(st.q[q] == M.pattern_bit(q, 8) for q in range(3))  # Phasengatter aendern keine Werte


def test_sim_zpow_accumulates_exactly():
    z = run(["Z q0"], [0, 1]).planes()
    assert run(["Z_POW q0 0.5", "Z_POW q0 0.5"], [0, 1]).planes() == z
    assert run(["Z_POW q0 0.25"] * 4, [0, 1]).planes() == z
    assert run(["Z_POW q0 0.125"] * 8, [0, 1]).planes() == z
    assert run(["Z_POW q0 1.0"], [0, 1]).planes() == z
    assert run(["Z_POW q0 0.25", "Z_POW q0 -0.25"], [0, 1]).planes() == [0] * 128
    assert run(["Z_POW q0 1.5", "Z_POW q0 0.5"], [0, 1]).planes() == [0] * 128  # 2 Halbdrehungen = Identitaet
    assert run(["Z_POW q0 0.5"], [0, 1]).planes() != z
    assert run(["Z_POW q0 0.25", "Z_POW q1 0.25"], [0, 1]).planes() != run(["Z_POW q0 0.5"], [0, 1]).planes()


def test_sim_zpow_single_plane_per_power_of_two():
    st = run(["Z_POW q0 0.5"], [0])
    tiny = run([M.phase_op(0, Fraction(1, 1 << 127), None).fmt()], [0])
    assert [j for j, p in enumerate(st.planes()) if p] == [126] and st.planes()[126] == 0b10
    assert [j for j, p in enumerate(tiny.planes()) if p] == [0]


def test_sim_hmr_writes_bit_resets_qubit_and_kicks_back_phase():
    r = 0b0110
    st = run(["HMR q0 b0"], [0, 1], meas={("H", 0, 0): r})
    assert st.q[0] == 0 and st.b[0] == r and st.q[1] == M.pattern_bit(1, 4)
    for lane in range(4):
        assert phase_bit(st, lane) == bit(r, lane) & (lane & 1)  # (-1)^(Messbit * alter Wert)


def test_sim_hmr_kickback_is_cancelled_by_conditional_z_correction():
    r = 0b1010  # q2 ist Scratch und startet in |0>
    fixed = run(["CCX q0 q1 q2", "HMR q2 b0", "CZ q0 q1 if b0"], [0, 1], meas={("H", 0, 0): r})
    raw = run(["CCX q0 q1 q2", "HMR q2 b0"], [0, 1], meas={("H", 0, 0): r})
    assert fixed.q[2] == 0 and raw.q[2] == 0
    assert fixed.planes() == run(["CCX q0 q1 q2", "CCX q0 q1 q2"], [0, 1]).planes() == [0] * 128
    assert raw.planes()[127] == r & M.pattern_bit(0, 4) & M.pattern_bit(1, 4) == 0b1000


def test_sim_measurement_randomness_is_coupled_by_seed_bit_and_occurrence():
    a = run(["HMR q0 b3", "HMR q1 b3", "HMR q2 b4"], [0, 1, 2, 3, 4, 5], seed=5)
    b = run(["X q1", "HMR q2 b4", "HMR q0 b3"], [0, 1, 2, 3, 4, 5], seed=5)
    c = run(["HMR q0 b3"], [0, 1, 2, 3, 4, 5], seed=6)
    first = M.State(tt_domain(list(range(6))), 5).rand("H", 3)
    assert b.b[3] == first and b.b[4] == a.b[4]  # gleicher Schluessel (Bit, wievieltes HMR) -> gleiches Ergebnis
    assert a.b[3] != first  # zweites HMR auf b3 zieht ein neues Ergebnis
    assert c.b[3] != first  # anderer Seed
    assert a.cnt == {("H", 3): 2, ("H", 4): 1}


def test_sim_conditional_gate_fires_only_where_bit_is_set():
    r = 0b1010_0101
    st = run(["HMR q2 b0", "X q1 if b0", "CX q0 q1 if b1"], [0, 1, 2], meas={("H", 0, 0): r})
    never = run(["X q0 if b9", "CCX q0 q1 q2 if b9", "Z q0 if b9", "NEG if b9"], [0, 1, 2])
    assert st.q[1] == M.pattern_bit(1, 8) ^ r  # b1 wurde nie gesetzt: CX feuert nicht
    assert never.q == tt_domain([0, 1, 2]).init_q and never.planes() == [0] * 128


def test_sim_push_pop_masks_nest_and_restore():
    A, B, ALL = 0b0011, 0b0101, 0b1111
    st = run(
        [
            "PUSH_CONDITION if b0",
            "PUSH_CONDITION if b1",
            "X q4",
            "POP_CONDITION",
            "X q5",
            "X q6 if b1",
            "BIT_STORE1 b2",
            "POP_CONDITION",
            "X q7",
            "POP_CONDITION",
            "X q8",
        ],
        [0, 1],
        bits={0: A, 1: B},
    )
    assert st.q[4] == A & B and st.q[5] == A and st.q[6] == A & B and st.q[7] == ALL and st.q[8] == ALL
    assert st.b[2] == A and st.stack == [] and st.top is None  # ueberzaehliges POP ist ein No-op


def test_sim_push_on_unset_bit_disables_block_including_measurement():
    st = run(["PUSH_CONDITION if b0", "X q0", "HMR q1 b1", "NEG", "POP_CONDITION", "X q1"], [0, 1])
    assert st.q[0] == M.pattern_bit(0, 4) and st.q[1] == M.pattern_bit(1, 4) ^ 0b1111
    assert st.planes() == [0] * 128 and st.cnt == {} and st.b.get(1, 0) == 0  # kein Messergebnis gezogen


def test_sim_masked_hmr_only_measures_active_lanes():
    A, r = 0b0101, 0b0110
    st = run(["HMR q1 b1 if b0"], [0, 1], bits={0: A, 1: 0b1000}, meas={("H", 1, 0): r})
    assert st.b[1] == (0b1000 & ~A) | (r & A)
    assert st.q[1] == M.pattern_bit(1, 4) & ~A
    assert st.planes()[127] == r & M.pattern_bit(1, 4) & A


def test_sim_bit_ops_respect_mask():
    A = 0b0110
    st = run(
        ["BIT_STORE1 b1", "BIT_STORE0 b1 if b0", "BIT_INVERT b2 if b0", "BIT_INVERT b3", "BIT_STORE1 b4 if b0"],
        [0, 1],
        bits={0: A},
    )
    assert (st.b[1], st.b[2], st.b[3], st.b[4]) == (0b1111 & ~A, A, 0b1111, A)


def test_sim_reset_clears_qubit_and_randomises_phase_only_if_set():
    r = 0b1001
    st = run(["R q0", "R q5"], [0, 1], meas={("R", 0, 0): r})
    assert st.q[0] == 0 and st.q.get(5, 0) == 0
    assert st.planes()[127] == r & M.pattern_bit(0, 4)
    assert st.cnt == {("R", 0): 1}  # R auf |0> zieht keinen Zufall


def test_sim_counts_toffolis_and_rotations_per_executed_lane():
    st = run(
        [
            "CCX q0 q1 q2",
            "CSWAP q0 q1 q2 if b0",
            "CCZ q0 q1 q2 if b9",
            "Z_POW q0 0.25",
            "Z_POW q0 0.125 if b0",
            "Z_POW q0 0.5",
            "CX q0 q1",
        ],
        [0, 1, 2],
        bits={0: 0b0000_0111},
        count=True,
    )
    assert (st.tof, st.tl, st.rot) == (8 + 3 + 0, 8, 3)
    sim = M.simulate(M.compile_ops(P("CCX q0 q1 q2", "CCX q0 q1 q2")), tt_domain([0, 1, 2]), count=True)
    assert sim.tof == 16 and sim.q == tt_domain([0, 1, 2]).init_q


def test_push_depths_and_dead_bits_after():
    ops = circuit(
        [
            "HMR q8 b0",
            "PUSH_CONDITION if b0",
            "BIT_STORE1 b1",
            "POP_CONDITION",
            "Z q0 if b1",
            "HMR q9 b0",
            "BIT_INVERT b2",
        ]
    )
    depths = M.push_depths(ops)
    layout = M.analyze_layout(ops, "x", "0:63")
    assert depths[NHEAD:] == [0, 0, 1, 1, 0, 0, 0]  # Tiefe VOR der Instruktion
    assert M.dead_bits_after(ops, NHEAD + 1, {0, 1, 2}, layout, depths) == {0}  # b0 wird ueberschrieben
    assert M.dead_bits_after(ops, NHEAD, {0}, layout, depths) == set()  # PUSH liest b0 noch
    assert M.dead_bits_after(ops, len(ops) - 1, {0, 1, 2}, layout, depths) == {0, 1, 2}


# ============================================================ 7. Oracle (End-to-End)
def test_oracle_self_check_accepts_clean_contract():
    for body in (
        MBU_BODY,
        GROUP_BODY,
        DIFF_BODY,
        CANCEL_BODY,
        WB_BODY,
        CTX_BODY,
        ["CCX q0 q1 q8", "CZ q8 q2", "HMR q8 b0", "CZ q0 q1 if b0"],
    ):
        ops, layout, dom, _ = setup(body)
        assert M.Oracle(ops, layout, dom, quiet).self_check() == [], body


def test_oracle_self_check_flags_uncorrected_hmr_kickback():
    ops, layout, dom, _ = setup(["CCX q0 q1 q8", "CZ q8 q3", "HMR q8 b0"])
    issues = M.Oracle(ops, layout, dom, quiet).self_check()
    assert len(issues) == 1 and "Messzufall" in issues[0]


def test_oracle_self_check_flags_dirty_scratch_changed_register_and_open_stack():
    def issues(body):
        ops, layout, dom, _ = setup(body)
        return " | ".join(M.Oracle(ops, layout, dom, quiet).self_check())

    assert "Scratch" in issues(["CCX q0 q1 q8"])
    assert "Register" in issues(["X q0"])
    assert "Bedingungsstapel" in issues(["PUSH_CONDITION if b0"])


def test_oracle_check_accepts_equivalent_rewrite():
    ops, layout, dom, _ = setup(CTX_BODY)
    oracle = M.Oracle(ops, layout, dom, quiet)
    mbu = circuit(["CCX q0 q1 q8", "CZ q8 q2", "HMR q8 b0", "CZ q0 q1 if b0"])
    ccz = circuit(["CCZ q0 q1 q2"])
    ok1, msg1, sig1 = oracle.check(mbu, range(4))
    ok2, _, sig2 = oracle.check(ccz, range(2))
    assert ok1 and "identisch" in msg1 and ok2
    assert sig1.tof_mean == 1.0 and sig2.tof_mean == 1.0 and oracle.orig_sig(0).tof_mean == 2.0


def test_oracle_check_rejects_wrong_register():
    ops, layout, dom, _ = setup(CTX_BODY)
    ok, msg, _ = M.Oracle(ops, layout, dom, quiet).check(ops + P("X q0"))
    assert not ok and "Registerinhalt" in msg and "64 betroffene Lanes" in msg


def test_oracle_check_rejects_wrong_phase():
    ops, layout, dom, _ = setup(CTX_BODY)
    oracle = M.Oracle(ops, layout, dom, quiet)
    ok, msg, _ = oracle.check(ops + P("CZ q0 q5"))
    ok2, msg2, _ = oracle.check(ops + P("Z_POW q0 " + M.phase_op(0, Fraction(1, 1 << 127), None).args[1]))
    ok3, msg3, _ = oracle.check(ops + P("NEG"))
    assert not ok and "Phase" in msg and "x=33" in msg  # kleinstes x mit Bit 0 und Bit 5
    assert not ok2 and "Phase" in msg2  # selbst 2^-127 Halbdrehung faellt auf
    assert not ok3 and "Phase" in msg3


def test_oracle_check_rejects_dirty_scratch_and_unbalanced_stack():
    ops, layout, dom, _ = setup(CTX_BODY)
    oracle = M.Oracle(ops, layout, dom, quiet)
    ok, msg, _ = oracle.check(ops + P("CX q0 q8"))
    ok2, msg2, _ = oracle.check(ops + P("BIT_STORE1 b0", "PUSH_CONDITION if b0"))
    ok3, msg3, _ = oracle.check(ops[:-1])  # Uncompute fehlt
    assert not ok and "Scratch" in msg
    assert not ok2 and "Bedingungsstapel" in msg2
    assert not ok3 and "Scratch" in msg3


def test_oracle_check_rejects_missing_hmr_correction_on_some_seed():
    ops, layout, dom, _ = setup(CTX_BODY)
    ok, msg, _ = M.Oracle(ops, layout, dom, quiet).check(circuit(["CCX q0 q1 q8", "CZ q8 q2", "HMR q8 b0"]), range(4))
    assert not ok and "Phase" in msg


# ============================================================ 8. check_exact (L1)
def test_check_exact_proves_equivalent_windows():
    cases = [
        (["CCX q0 q1 q2", "CCX q0 q1 q2", "CX q0 q1"], ["CX q0 q1"]),
        (["CCX q0 q1 q2", "X q0", "CCX q0 q1 q2"], ["CX q1 q2", "X q0"]),
        (["CCX q0 q1 q3", "CCX q0 q2 q3"], ["CX q1 q2", "CCX q0 q2 q3", "CX q1 q2"]),
        (["CX q0 q1", "CX q1 q0", "CX q0 q1"], ["SWAP q0 q1"]),
        (["Z_POW q0 0.25", "Z_POW q0 0.25"], ["Z_POW q0 0.5"]),
        (["X q0 if b0", "X q0 if b0"], []),
        (["HMR q2 b0", "CZ q0 q1 if b0"], ["HMR q2 b0", "PUSH_CONDITION if b0", "CZ q1 q0", "POP_CONDITION"]),
    ]
    for a, b in cases:
        status, msg = M.check_exact(P(*a), P(*b), 0, set())
        assert status == "proved" and "exakt bewiesen" in msg, (a, b, msg)


def test_check_exact_refutes_inequivalent_windows_with_counterexample():
    cases = [
        (["CCX q0 q1 q2"], ["CX q0 q2"]),
        (["X q0"], []),
        (["Z q0"], ["Z_POW q0 0.5"]),
        (["NEG"], []),
        (["CZ q0 q1"], ["CZ q0 q2"]),
        (["X q0 if b0"], ["X q0"]),
        (["X q0 if b0"], ["X q0 if b1"]),
        (["CCX q0 q1 q2"], ["HMR q2 b0", "CZ q0 q1 if b0"]),  # nur im Kontext gleich, nicht allgemein
        (["HMR q2 b0", "CZ q0 q1 if b0"], ["HMR q2 b0"]),
        (["BIT_STORE1 b0"], ["BIT_STORE0 b0"]),
    ]
    for a, b in cases:
        status, msg = M.check_exact(P(*a), P(*b), 0, set())
        assert status == "refuted" and "verletzt" in msg, (a, b, msg)
    _, msg = M.check_exact(P("CCX q0 q1 q2"), P("CX q0 q2"), 0, set())
    assert "q0=1" in msg and "q1=0" in msg and "Qubit q2" in msg


def test_check_exact_dead_bits_and_entry_depth_matter():
    store = (P("BIT_STORE1 b0"), P("BIT_STORE0 b0"))
    assert M.check_exact(*store, 0, set())[0] == "refuted"
    assert M.check_exact(*store, 0, {0})[0] == "proved"  # b0 wird danach nie gelesen
    # Im Inneren eines PUSH-Blocks ist die umgebende Maske eine zusaetzliche freie Variable
    assert M.check_exact(P("PUSH_CONDITION if b0", "POP_CONDITION"), P(), 1, set())[0] == "proved"
    assert M.check_exact(P("X q0", "X q0"), P(), 1, set())[0] == "proved"
    assert M.check_exact(P("X q0"), P("X q0", "NEG", "NEG"), 1, set())[0] == "proved"
    assert M.check_exact(P("X q0"), P(), 1, set())[0] == "refuted"


def test_check_exact_is_na_for_too_many_variables():
    chain = [f"CX q{i} q{i + 1}" for i in range(20)]  # 21 verbundene Qubits
    status, msg = M.check_exact(P(*chain), P(), 0, set())
    small, msg2 = M.check_exact(P("CCX q0 q1 q2"), P("CX q0 q2"), 0, set(), max_vars=2)
    assert status == "na" and "21 Variablen > 20" in msg
    assert small == "na" and "3 Variablen > 2" in msg2
    assert M.check_exact(P(*chain[:19]), P(), 0, set())[0] == "refuted"  # genau 20 passt noch


def test_check_exact_is_na_for_off_grid_zpow_angle():
    for a, b in (([TINY], []), ([], [TINY]), ([TINY], [TINY]), (["Z_POW q0 0.3"], ["Z_POW q0 0.3"])):
        status, msg = M.check_exact(P(*a), P(*b), 0, set())
        assert status == "na" and "Phasenraster" in msg, (a, b)
    assert M.off_grid_phase(P("Z_POW q0 0.5", TINY, "Z q0")).fmt() == TINY
    assert M.off_grid_phase(P("Z_POW q0 0.5", "Z q0")) is None


def test_v3_verifier_interface_never_claims_unproved_equivalence():
    V = M.BitParallelKMXVerifier
    same = V.verify_equivalence(["CCX q0 q1 q2"], ["CCX q0 q1 q2"])
    diff = V.verify_equivalence(["X q0"], [])
    bad = V.verify_equivalence(["FOO q0"], [])
    na = V.verify_equivalence([TINY], [TINY])
    ok, message = same
    assert ok and same.exact and message == same.message
    assert not diff.ok and not diff.exact
    assert not bad.ok and "ungültig" in bad.message
    assert not na.ok and "kein exakter Beweis" in na.message
    assert V.can_verify_window(["CCX q0 q1 q2"]) == (True, "OK")
    assert V.can_verify_window(['REGISTER r0 "x"'])[0] is False
    assert V.can_verify_window([f"X q{i}" for i in range(21)])[0] is False


# ============================================================ 9. difference_cone
SPECT = [f"CX q{i} q{i + 1}" for i in range(10, 34, 2)] + ["Z_POW q40 0.125"]  # 25 unbeteiligte Qubits


def test_difference_cone_proves_wide_window_with_many_spectators():
    wide = ["CCX q0 q1 q2", *SPECT, "X q0", "CCX q0 q1 q2"]
    cand = [*SPECT, "CX q1 q2", "X q0"]
    a, b = M.difference_cone(P(*wide), P(*cand))
    assert len({q for o in P(*wide) for q in o.qs}) == 28  # ohne Kegel > 20 Variablen
    assert fmt(a) == ["CCX q0 q1 q2", "X q0", "CCX q0 q1 q2"] and fmt(b) == ["CX q1 q2", "X q0"]
    assert M.check_exact(P(*wide), P(*cand), 0, set())[0] == "proved"


def test_difference_cone_refutes_near_miss():
    wide = ["CCX q0 q1 q2", *SPECT, "X q0", "CCX q0 q1 q2"]
    assert M.check_exact(P(*wide), P(*SPECT, "CX q0 q2", "X q0"), 0, set())[0] == "refuted"
    assert M.check_exact(P(*wide), P(*SPECT[:-1], "Z_POW q40 0.25", "CX q1 q2", "X q0"), 0, set())[0] == "refuted"
    assert M.check_exact(P(*wide), P(*SPECT[1:], "CX q1 q2", "X q0"), 0, set())[0] == "refuted"  # Zuschauer fehlt


def test_difference_cone_keeps_global_phase_neg():
    a, b = M.difference_cone(P("NEG", *SPECT), P(*SPECT))
    assert fmt(a) == ["NEG"] and fmt(b) == []
    assert M.check_exact(P("NEG", *SPECT), P(*SPECT), 0, set())[0] == "refuted"
    assert M.check_exact(P(*SPECT, "NEG"), P("NEG", *SPECT), 0, set())[0] == "proved"
    assert M.check_exact(P("NEG", *SPECT, "NEG"), P(*SPECT), 0, set())[0] == "proved"


def test_difference_cone_strips_common_prefix_and_suffix_on_shared_qubits():
    pre, post = ["CCX q0 q1 q2", "CZ q2 q3"], ["CSWAP q3 q0 q1", "Z_POW q2 0.125"]
    a, b = M.difference_cone(P(*pre, "X q0", "X q0", "CX q4 q5", *post), P(*pre, "CX q4 q5", *post))
    assert fmt(a) == ["X q0", "X q0"] and fmt(b) == []


def test_difference_cone_keeps_whole_component_when_order_inside_differs():
    orig, cand = P("CX q0 q1", "X q1", "CX q5 q6"), P("X q1", "CX q5 q6", "CX q0 q1")
    a, b = M.difference_cone(orig, cand)
    assert fmt(a) == ["CX q0 q1", "X q1"] and fmt(b) == ["X q1", "CX q0 q1"]
    assert M.check_exact(orig, cand, 0, set())[0] == "proved"  # X auf dem Ziel kommutiert mit CX


def test_difference_cone_returns_conditional_or_measuring_windows_unchanged():
    for extra in ("X q0 if b0", "HMR q0 b0", "R q0", "PUSH_CONDITION if b0", "BIT_STORE1 b0"):
        orig, cand = P("X q1", extra, "CX q5 q6"), P("X q1", "CX q5 q6")
        a, b = M.difference_cone(orig, cand)
        assert a is orig and b is cand, extra
        a, b = M.difference_cone(cand, orig)
        assert a is cand and b is orig, extra


# ---- Eigenschaftstest: check_exact gegen eine unabhaengige Brute-Force-Referenz
def brute_force(ops, qubits):
    """Referenz: jedes Gatter ist Permutation x Diagonalphase; Wirkung je Basiszustand als (Bits, Phase mod 2)."""
    idx = {q: i for i, q in enumerate(qubits)}
    table = []
    for s in range(1 << len(qubits)):
        v = [(s >> i) & 1 for i in range(len(qubits))]
        ph = Fraction(0)
        for o in ops:
            q = [idx[x] for x in o.qs]
            n = o.name
            if n == "X":
                v[q[0]] ^= 1
            elif n == "CX":
                v[q[1]] ^= v[q[0]]
            elif n == "CCX":
                v[q[2]] ^= v[q[0]] & v[q[1]]
            elif n == "SWAP":
                v[q[0]], v[q[1]] = v[q[1]], v[q[0]]
            elif n == "CSWAP":
                if v[q[0]]:
                    v[q[1]], v[q[2]] = v[q[2]], v[q[1]]
            elif n == "Z":
                ph += v[q[0]]
            elif n == "CZ":
                ph += v[q[0]] & v[q[1]]
            elif n == "CCZ":
                ph += v[q[0]] & v[q[1]] & v[q[2]]
            elif n == "Z_POW":
                ph += v[q[0]] * Fraction(o.args[1])
            elif n == "NEG":
                ph += 1
            else:
                raise AssertionError(n)
        table.append((tuple(v), ph % 2))
    return table


ARITY = {"X": 1, "CX": 2, "CCX": 3, "SWAP": 2, "CSWAP": 3, "Z": 1, "CZ": 2, "CCZ": 3}
HALF = {"0.5": "0.25", "0.25": "0.125", "1.5": "0.75", "-0.25": "-0.125", "0.125": "0.0625", "0.75": "0.375"}
ANGLES = sorted(HALF) + ["-0.125", "1.0", M.phase_op(0, Fraction(1, 1 << 127), None).args[1]]


def rand_gate(rng, qubits, self_inverse=False):
    roll = rng.random()
    if roll < 0.06:
        return "NEG"
    if roll < 0.22 and not self_inverse:
        return f"Z_POW q{rng.choice(qubits)} {rng.choice(ANGLES)}"
    name = rng.choice(sorted(ARITY))
    return " ".join([name] + [f"q{q}" for q in rng.sample(qubits, ARITY[name])])


def mutate(rng, lines, qubits):
    """Zufaellige Bearbeitung; ob sie aequivalent ist, entscheidet allein die Brute-Force-Referenz."""
    out = list(lines)
    kind = rng.choice(
        ["pair", "pair", "sym", "sym", "split", "swap3", "commute", "commute", "delete", "insert", "replace", "noop"]
    )
    pos = rng.randrange(len(out) + 1)
    pick = lambda pred: rng.choice([i for i, g in enumerate(out) if pred(g.split())] or [None])
    if kind == "pair":
        g = rand_gate(rng, qubits, self_inverse=True)
        out[pos:pos] = [g, g]
    elif kind == "sym":
        i = pick(lambda t: t[0] in ("CZ", "CCZ", "SWAP", "CCX", "CSWAP"))
        if i is not None:
            t = out[i].split()
            lo, hi = {"CCX": (1, 3), "CSWAP": (2, 4)}.get(t[0], (1, len(t)))
            mid = t[lo:hi]
            rng.shuffle(mid)
            out[i] = " ".join(t[:lo] + mid + t[hi:])
    elif kind == "split":
        i = pick(lambda t: t[0] == "Z" or (t[0] == "Z_POW" and t[2] in HALF))
        if i is not None:
            t = out[i].split()
            out[i : i + 1] = [f"Z_POW {t[1]} {'0.5' if t[0] == 'Z' else HALF[t[2]]}"] * 2
    elif kind == "swap3":
        i = pick(lambda t: t[0] == "SWAP")
        if i is not None:
            _, a, b = out[i].split()
            out[i : i + 1] = [f"CX {a} {b}", f"CX {b} {a}", f"CX {a} {b}"]
    elif kind == "commute":
        ok = [i for i in range(len(out) - 1) if not set(out[i].split()[1:]) & set(out[i + 1].split()[1:])]
        if ok:
            i = rng.choice(ok)
            out[i], out[i + 1] = out[i + 1], out[i]
    elif kind == "delete" and out:
        del out[rng.randrange(len(out))]
    elif kind == "insert":
        out.insert(pos, rand_gate(rng, qubits))
    elif kind == "replace" and out:
        out[rng.randrange(len(out))] = rand_gate(rng, qubits)
    return out


def interleave(rng, main, extra):
    """Mischt `extra` in `main`, beide Reihenfolgen bleiben erhalten."""
    main, extra, out = list(main), list(extra), []
    while main or extra:
        take_extra = extra and (not main or rng.random() < len(extra) / (len(extra) + len(main)))
        out.append((extra if take_extra else main).pop(0))
    return out


def test_property_check_exact_matches_brute_force_on_random_unitary_windows():
    rng = random.Random(20261111)
    active, verdicts, wide_runs = [0, 1, 2, 3], {"proved": 0, "refuted": 0}, 0
    for trial in range(300):
        base = [rand_gate(rng, active) for _ in range(rng.randint(3, 9))]
        cand = base
        for _ in range(rng.randint(1, 3)):
            cand = mutate(rng, cand, active)
        wide = trial % 2 == 1
        if wide:  # > 20 Zuschauer-Qubits: nur der Differenzkegel macht das Fenster beweisbar
            pairs = [f"CX q{i} q{i + 1}" for i in range(10, 34, 2)]
            rng.shuffle(pairs)
            spect = pairs + [rand_gate(rng, list(range(10, 41))) for _ in range(rng.randint(0, 6))]
            ref_qubits, ref_a, ref_b = active, P(*base), P(*cand)  # A (x) S == B (x) S  <=>  A == B (S unitaer)
            wide_runs += 1
        else:  # wenige Zuschauer: Referenz rechnet den GANZEN Schaltkreis inklusive Zuschauer
            spect = [rand_gate(rng, [10, 11, 12]) for _ in range(rng.randint(0, 5))]
            ref_qubits = active + [10, 11, 12]
        orig_w, cand_w = P(*interleave(rng, base, spect)), P(*interleave(rng, cand, spect))
        if not wide:
            ref_a, ref_b = orig_w, cand_w
        expected = "proved" if brute_force(ref_a, ref_qubits) == brute_force(ref_b, ref_qubits) else "refuted"

        status, msg = M.check_exact(orig_w, cand_w, 0, set())

        assert status == expected, (trial, fmt(orig_w), fmt(cand_w), msg)
        verdicts[status] += 1
    assert wide_runs == 150 and verdicts["proved"] >= 60 and verdicts["refuted"] >= 60, verdicts


# ============================================================ 10. check_context (L2)
def _ctx_entry(dom):
    ops = circuit(["CCX q0 q1 q8"])
    return M.simulate(M.compile_ops(ops), dom, "E")


def test_check_context_accepts_rewrite_valid_only_on_reachable_states():
    _, _, dom, _ = setup(CTX_BODY)
    orig_w, cand_w = P("CCX q0 q1 q8"), P("HMR q8 b0", "CZ q0 q1 if b0")
    ok, msg, cost = M.check_context(_ctx_entry(dom), orig_w, cand_w, {0}, dom, 4)
    assert ok and "4 Messrunde" in msg and cost == (1.0, 0.0)
    assert M.check_exact(orig_w, cand_w, 0, {0})[0] == "refuted"  # allgemein falsch: q8 beliebig


def test_check_context_rejects_wrong_phase_dirty_qubit_and_live_bit():
    _, _, dom, _ = setup(CTX_BODY)
    entry = _ctx_entry(dom)
    no_fix = M.check_context(entry, P("CCX q0 q1 q8"), P("HMR q8 b0"), {0}, dom, 4)
    dirty = M.check_context(entry, P("CCX q0 q1 q8"), P("CX q0 q8"), set(), dom, 4)
    live = M.check_context(entry, P("CCX q0 q1 q8"), P("HMR q8 b0", "CZ q0 q1 if b0"), set(), dom, 4)
    assert not no_fix[0] and "Phase" in no_fix[1]
    assert not dirty[0] and "Qubit q8" in dirty[1] and "x=1" in dirty[1] and "Fenstereingang" in dirty[1]
    assert not live[0] and "Bit b0" in live[1]  # b0 gilt ohne dead_bits als lebendig


def test_check_context_does_not_mutate_entry_state_and_uses_one_round_without_randomness():
    _, _, dom, _ = setup(CTX_BODY)
    entry = _ctx_entry(dom)
    before = (dict(entry.q), dict(entry.b), entry.phase, list(entry.zp))
    ok, msg, cost = M.check_context(entry, P("CCX q0 q1 q8", "CCX q0 q1 q8"), P(), set(), dom, 7)
    assert ok and "x 1 Messrunde" in msg and cost == (2.0, 0.0)
    assert before == (entry.q, entry.b, entry.phase, entry.zp)


# ============================================================ 11. pass_fold
def test_pass_fold_turns_cx_triple_into_swap():
    out, n = M.pass_fold(P("X q9", "CX q0 q1", "CX q1 q0", "CX q0 q1", "X q9"))
    assert n == 1 and fmt(out) == ["X q9", "SWAP q0 q1", "X q9"]
    assert M.check_exact(P("CX q0 q1", "CX q1 q0", "CX q0 q1"), out[1:2], 0, set())[0] == "proved"


def test_pass_fold_leaves_non_triples_and_conditional_cx_alone():
    for lines in (
        ["CX q0 q1", "CX q0 q1", "CX q0 q1"],
        ["CX q0 q1", "CX q1 q0", "CX q1 q0"],
        ["CX q0 q1", "CX q1 q0", "X q5", "CX q0 q1"],
        ["CX q0 q1", "CX q1 q2", "CX q0 q1"],
        ["CX q0 q1 if b0", "CX q1 q0", "CX q0 q1"],
        ["CX q0 q1", "CX q1 q0", "CX q0 q1 if b0"],
    ):
        out, n = M.pass_fold(P(*lines))
        assert n == 0 and fmt(out) == lines, lines


def test_pass_fold_removes_empty_push_pop_blocks_including_nested():
    out, n = M.pass_fold(
        P("X q0", "PUSH_CONDITION if b0", "PUSH_CONDITION if b1", "POP_CONDITION", "POP_CONDITION", "X q1")
    )
    kept, n2 = M.pass_fold(P("PUSH_CONDITION if b0", "X q0", "POP_CONDITION"))
    assert n == 2 and fmt(out) == ["X q0", "X q1"]
    assert n2 == 0 and len(kept) == 3


# ============================================================ 12. pass_cancel
def _cancel(*lines, **kw):
    out, cancelled, merged = M.pass_cancel(P(*lines), **kw)
    return fmt(out), cancelled, merged


def test_pass_cancel_removes_pair_across_commuting_gates():
    assert _cancel("CCX q0 q1 q8", "CX q3 q4", "Z q0", "CZ q1 q5", "CCX q1 q0 q8") == (
        ["CX q3 q4", "Z q0", "CZ q1 q5"],
        1,
        0,
    )
    assert _cancel("CZ q0 q1", "CCZ q0 q1 q2", "CZ q1 q0") == (["CCZ q0 q1 q2"], 1, 0)
    assert _cancel("SWAP q0 q1", "X q2", "SWAP q1 q0") == (["X q2"], 1, 0)
    assert _cancel("CSWAP q0 q1 q2", "Z q0", "CSWAP q0 q2 q1") == (["Z q0"], 1, 0)
    assert _cancel("NEG", "X q0", "NEG") == (["X q0"], 1, 0)
    assert _cancel("X q0 if b0", "CX q1 q2", "X q0 if b0") == (["CX q1 q2"], 1, 0)


def test_pass_cancel_same_target_xor_gates_commute():
    lines = ["CCX q0 q1 q8", "CX q2 q8", "X q8", "CCX q3 q4 q8", "CCX q0 q1 q8"]
    out, cancelled, merged = _cancel(*lines)
    assert (out, cancelled, merged) == (["CX q2 q8", "X q8", "CCX q3 q4 q8"], 1, 0)
    assert M.check_exact(P(*lines), P(*out), 0, set())[0] == "proved"


def test_pass_cancel_blocked_by_reader_or_writer_of_involved_qubits():
    for mid in (
        "CX q8 q3",
        "CZ q8 q3",
        "Z q8",
        "Z_POW q8 0.25",
        "CX q5 q0",
        "X q1",
        "SWAP q8 q9",
        "SWAP q0 q9",
        "CSWAP q8 q5 q6",
        "CSWAP q5 q0 q6",
        "R q8",
        "R q0",
    ):
        lines = ["CCX q0 q1 q8", mid, "CCX q0 q1 q8"]
        assert _cancel(*lines) == (lines, 0, 0), mid
        if M.GATE_ARITY.get(mid.split()[0]) and mid.split()[0] != "R":
            assert M.check_exact(P(*lines), P(mid), 0, set())[0] == "refuted", mid  # Sperre war noetig


def test_pass_cancel_blocked_by_hmr():
    for lines in (
        ["CX q0 q8", "HMR q8 b0", "CX q0 q8"],
        ["CX q0 q8", "HMR q0 b0", "CX q0 q8"],
        ["CZ q0 q8", "HMR q8 b0", "CZ q0 q8"],
        ["Z q8", "HMR q8 b0", "Z q8"],
    ):
        assert _cancel(*lines) == (lines, 0, 0), lines
    assert _cancel("CX q0 q8", "HMR q5 b0", "CX q0 q8") == (["HMR q5 b0"], 1, 0)  # fremdes Qubit stoert nicht


def test_pass_cancel_blocked_by_writer_of_condition_bit():
    for mid in ("BIT_INVERT b0", "BIT_STORE1 b0", "BIT_STORE0 b0", "HMR q5 b0", "BIT_STORE1 b0 if b3"):
        lines = ["X q0 if b0", mid, "X q0 if b0"]
        assert _cancel(*lines) == (lines, 0, 0), mid
    assert _cancel("X q0 if b0", "BIT_INVERT b1", "X q0 if b0") == (["BIT_INVERT b1"], 1, 0)
    assert _cancel("X q0 if b0", "X q0 if b1") == (["X q0 if b0", "X q0 if b1"], 0, 0)
    assert _cancel("X q0 if b0", "X q0") == (["X q0 if b0", "X q0"], 0, 0)


def test_pass_cancel_blocked_by_push_pop_barrier():
    lines = ["X q0", "PUSH_CONDITION if b0", "X q0", "POP_CONDITION", "X q0"]
    assert _cancel(*lines) == (lines, 0, 0)
    inside = ["PUSH_CONDITION if b0", "X q0", "CX q1 q2", "X q0", "POP_CONDITION"]
    assert _cancel(*inside) == (["PUSH_CONDITION if b0", "CX q1 q2", "POP_CONDITION"], 1, 0)


def test_pass_cancel_respects_search_depth():
    lines = ["X q0", "CX q1 q2", "CX q3 q4", "X q0"]
    assert _cancel(*lines, depth=1) == (lines, 0, 0)
    assert _cancel(*lines, depth=2) == (["CX q1 q2", "CX q3 q4"], 1, 0)
    assert _cancel("X q0", "X q0", depth=0) == ([], 1, 0)


def test_pass_cancel_merges_phases_exactly():
    assert _cancel("Z_POW q0 0.0009765625", "CX q1 q2", "Z_POW q0 0.0009765625", "Z q3", "Z_POW q3 -0.75") == (
        ["Z_POW q0 0.001953125", "CX q1 q2", "Z_POW q3 0.25"],
        0,
        2,
    )
    assert _cancel("Z q0", "CZ q0 q1", "Z q0") == (["CZ q0 q1"], 0, 1)  # Z*Z = 1: beide weg
    assert _cancel("Z_POW q0 0.25", "Z_POW q0 0.25", "Z_POW q0 0.5") == (["Z q0"], 0, 2)
    assert _cancel("Z_POW q0 1.5", "CX q0 q1", "Z_POW q0 0.5") == (["CX q0 q1"], 0, 1)  # q0 ist nur Kontrolle
    assert _cancel("Z_POW q0 0.25 if b1", "Z_POW q0 0.5 if b1") == (["Z_POW q0 0.75 if b1"], 0, 1)


def test_pass_cancel_merges_phases_only_for_same_condition_and_qubit():
    for lines in (
        ["Z_POW q0 0.25 if b0", "Z_POW q0 0.25"],
        ["Z_POW q0 0.25 if b0", "Z_POW q0 0.25 if b1"],
        ["Z q0 if b0", "Z q0"],
        ["Z_POW q0 0.25", "Z_POW q1 0.25"],
        ["Z_POW q0 0.25", "X q0", "Z_POW q0 0.25"],
        ["Z_POW q0 0.25", "CX q1 q0", "Z_POW q0 0.25"],
        ["Z q0 if b0", "BIT_INVERT b0", "Z q0 if b0"],
        ["Z_POW q0 0.25", "HMR q0 b0", "Z_POW q0 0.25"],
    ):
        assert _cancel(*lines) == (lines, 0, 0), lines


def test_pass_cancel_never_merges_off_grid_angles():
    assert _cancel(TINY, TINY) == ([TINY, TINY], 0, 0)
    assert _cancel("Z_POW q0 0.3", "Z_POW q0 0.3") == (["Z_POW q0 0.3", "Z_POW q0 0.3"], 0, 0)
    assert _cancel("Z_POW q0 0.25", TINY, "Z_POW q0 0.25") == (["Z_POW q0 0.5", TINY], 0, 1)


def test_pass_cancel_keeps_meta_ops_and_is_equivalent_on_random_circuits():
    assert _cancel("X q0", 'INFO_TAG "@enter:a"', "X q0") == (['INFO_TAG "@enter:a"'], 1, 0)
    rng = random.Random(7)
    changed = 0
    for _ in range(150):
        lines = [rand_gate(rng, [0, 1, 2, 3]) for _ in range(rng.randint(4, 14))]
        out, cancelled, merged = M.pass_cancel(P(*lines))
        changed += bool(cancelled or merged)
        assert brute_force(P(*lines), [0, 1, 2, 3]) == brute_force(out, [0, 1, 2, 3]), (lines, fmt(out))
        assert len(out) <= len(lines) - cancelled * 2 - merged + 0
    assert changed >= 30


# ============================================================ 13. Simulationsgefuehrte Paesse, direkt
def test_pass_sim_reduce_drops_gates_that_never_fire_on_the_domain():
    body = ["CCX q5 q0 q8", "CZ q8 q1", "CCX q5 q0 q8"]
    ops, layout, dom, smp = setup(body, "0:31")  # q5 ist auf der Domaene immer 0
    out, stats = M.pass_sim_reduce(ops, layout, dom, smp)
    full_ops, full_layout, full_dom, full_smp = setup(body, "0:63")
    kept, _ = M.pass_sim_reduce(full_ops, full_layout, full_dom, full_smp)
    assert fmt(out) == fmt(ops[:NHEAD]) and stats["dead"] == 3 and stats["toffoli_saved"] == 2
    assert M.Oracle(ops, layout, dom, quiet).check(out)[0]
    assert toffoli(kept) == 2  # ohne Don't-Care bleibt alles


def test_pass_sim_reduce_replaces_implied_control_by_cx():
    ops, layout, dom, smp = setup(["CX q0 q8", "CCX q0 q8 q9", "CZ q9 q1", "CCX q0 q8 q9", "CX q0 q8"])
    out, stats = M.pass_sim_reduce(ops, layout, dom, smp)
    assert toffoli(out) == 0 and stats["toffoli_saved"] == 2 and stats["cx"] == 2
    assert M.Oracle(ops, layout, dom, quiet).check(out)[0]


def test_pass_sim_reduce_returns_same_ops_when_nothing_applies():
    ops, layout, dom, smp = setup(["CCZ q0 q1 q2"])
    out, stats = M.pass_sim_reduce(ops, layout, dom, smp)
    assert all(a is b for a, b in zip(out, ops)) and len(out) == len(ops) and not stats.get("toffoli_saved")


def test_pass_mbu_replaces_uncompute_chain_by_measurement_and_correction():
    ops, layout, dom, _ = setup(CTX_BODY)
    out, stats = M.pass_mbu(ops, layout, dom)
    assert stats == {"chains": 1, "toffoli_saved": 1}
    assert fmt(out[NHEAD:]) == ["CCX q0 q1 q8", "CZ q8 q2", "HMR q8 b0", "CZ q0 q1 if b0"]
    assert M.Oracle(ops, layout, dom, quiet).check(out, range(6))[0]


def test_pass_mbu_ignores_dirty_or_toffoli_free_chains_and_register_targets():
    for body in (
        ["CCX q0 q1 q8", "CZ q8 q2"],  # q8 wird nie |0>
        ["CX q0 q8", "CZ q8 q2", "CX q0 q8"],  # kein CCX in der Kette: nichts zu sparen
        ["CCX q0 q1 q2", "CCX q0 q1 q2"],
    ):  # Ziel ist ein Register-Qubit
        ops, layout, dom, _ = setup(body)
        out, stats = M.pass_mbu(ops, layout, dom)
        assert stats == {} and fmt(out) == fmt(ops), body


def test_pass_mbu_picks_fresh_measurement_bit():
    ops, layout, dom, _ = setup(["BIT_STORE1 b0", "X q0 if b3", "X q0 if b3", "BIT_STORE0 b0", *CTX_BODY])
    out, stats = M.pass_mbu(ops, layout, dom)
    assert stats["chains"] == 1 and "HMR q8 b4" in fmt(out) and "CZ q0 q1 if b4" in fmt(out)
    assert M.Oracle(ops, layout, dom, quiet).check(out, range(4))[0]


def test_pass_repack_reuses_freed_wires_with_lowest_indices():
    ops, layout, dom, _ = setup(["CX q0 q20", "CZ q20 q1", "CX q0 q20", "CX q1 q30", "CZ q30 q2", "CX q1 q30"])
    out, stats = M.pass_repack(ops, layout, dom)
    assert fmt(out[NHEAD:]) == ["CX q0 q6", "CZ q6 q1", "CX q0 q6", "CX q1 q6", "CZ q6 q2", "CX q1 q6"]
    assert (stats["q_before"], stats["q_after"], stats["peak_scratch"], stats["lifetimes"]) == (31, 7, 1, 2)
    assert M.Oracle(ops, layout, dom, quiet).check(out)[0]


def test_pass_repack_keeps_overlapping_lifetimes_apart_and_reports_no_gain():
    ops, layout, dom, _ = setup(["CX q0 q20", "CX q1 q30", "CZ q20 q30", "CX q1 q30", "CX q0 q20"])
    out, stats = M.pass_repack(ops, layout, dom)
    again, stats2 = M.pass_repack(out, layout, dom)
    assert fmt(out[NHEAD:]) == ["CX q0 q6", "CX q1 q7", "CZ q6 q7", "CX q1 q7", "CX q0 q6"]
    assert stats["peak_scratch"] == 2 and stats["q_after"] == 8
    assert stats2["q_after"] == stats2["q_before"] == 8 and fmt(again) == fmt(out)
    assert M.Oracle(ops, layout, dom, quiet).check(out)[0]


# ============================================================ 14. Session.run_passes auf den Selftest-Schaltkreisen
def _run_case(body, opts=None, value_range="0:63"):
    s = make_session(body, value_range, opts or M.Options(final_rounds=8))
    summary = s.run_passes()
    return s, summary


def test_session_mbu_case_drops_to_two_toffolis_and_repacks():
    s, summary = _run_case(MBU_BODY)
    ok, msg = s.final_check()
    assert toffoli(s.orig) == 4 and toffoli(s.ops) <= 2 and ok and "8 Messrunde" in msg
    assert summary["mbu"]["toffoli_saved"] == 2 and M.compute_metrics(s.ops).counts["HMR"] == 2
    assert M.compute_metrics(s.orig).num_qubits == 10 and M.compute_metrics(s.ops).num_qubits == 9  # 6 + 3 Scratch
    assert any(a.startswith("[OK] Measurement-Based Uncomputation") for a in s.audit)
    assert any(a.startswith("[OK] Qubit-Repacking") for a in s.audit)
    assert s.sig.tof_mean == 2.0 and M.Oracle(s.orig, s.layout, s.dom, quiet).self_check() == []


def test_session_group_case_drops_to_one_toffoli():
    s, summary = _run_case(GROUP_BODY)
    assert toffoli(s.orig) == 6 and toffoli(s.ops) <= 1 and s.final_check()[0]
    assert summary["sim"]["toffoli_saved"] >= 2
    assert M.compute_metrics(s.ops).num_qubits <= 7


def test_session_difference_control_case_drops_to_one_toffoli():
    s, _ = _run_case(DIFF_BODY)
    assert toffoli(s.orig) == 3 and toffoli(s.ops) <= 1 and s.final_check()[0]


def test_session_cancellation_case_drops_to_zero_toffolis():
    s, summary = _run_case(CANCEL_BODY)
    assert toffoli(s.orig) == 2 and toffoli(s.ops) == 0 and s.final_check()[0]
    assert summary["cancelled"] == 3 and fmt(s.ops) == fmt(s.orig[:NHEAD])


def test_session_merges_rotations_on_value_equal_qubits():
    s, _ = _run_case(["CX q0 q8", "Z_POW q8 0.125", "Z_POW q0 0.0625", "CX q0 q8"], M.Options(final_rounds=4))
    assert M.compute_metrics(s.orig).rotations == 2 and M.compute_metrics(s.ops).rotations == 1
    assert s.final_check()[0] and "Z_POW q0 0.1875" in fmt(s.ops)


def test_session_pass_switches_disable_mbu_and_repack():
    no_mbu, summary = _run_case(CTX_BODY, M.Options(mbu=False, repack=False))
    with_mbu, _ = _run_case(CTX_BODY)
    assert "mbu" not in summary and "repack" not in summary
    assert toffoli(no_mbu.ops) == 2 and M.compute_metrics(no_mbu.ops).num_qubits == 9
    assert toffoli(with_mbu.ops) == 1 and M.compute_metrics(with_mbu.ops).num_qubits == 7
    assert no_mbu.final_check()[0] and with_mbu.final_check()[0]


def test_session_without_full_domain_runs_only_syntactic_passes():
    sampled, summary = _run_case(MBU_BODY, value_range=None)  # keine --range: nur Stichprobe
    cancel, _ = _run_case(CANCEL_BODY, value_range=None)
    allowed, _ = _run_case(MBU_BODY, M.Options(sampled_facts=True), value_range=None)
    assert not sampled.dom.exhaustive and toffoli(sampled.ops) == 4 and summary == {}
    assert toffoli(cancel.ops) == 0  # Ausloeschung ist rein syntaktisch
    assert toffoli(allowed.ops) <= 2 and allowed.final_check()[0]


def test_session_skips_mbu_and_repack_when_original_violates_contract():
    s, summary = _run_case(["CCX q0 q1 q8", "CZ q8 q2", "CCX q0 q1 q8", "CX q0 q20"])  # q20 endet schmutzig
    assert not s.clean and "mbu" not in summary and "repack" not in summary
    assert toffoli(s.ops) == 2 and s.final_check()[0]


def test_session_commit_rejects_wrong_candidate_and_keeps_state():
    s = make_session(CTX_BODY)
    before, sig = list(s.ops), s.sig
    rejected = s.commit("Test", s.ops + P("X q0"), "absichtlich falsch")
    assert rejected is False and s.ops == before and s.sig is sig
    assert s.audit[-1].startswith("[VERWORFEN] Test: absichtlich falsch") and "Registerinhalt" in s.audit[-1]


def test_session_commit_accepts_equivalent_candidate():
    s = make_session(CTX_BODY)
    cand = circuit(["CCZ q0 q1 q2"])
    assert s.commit("Test", cand, "CCX-Sandwich = CCZ") is True
    assert s.ops is cand and s.audit[-1].startswith("[OK] Test") and s.sig.tof_mean == 1.0
    assert s.final_check()[0]


def test_session_final_check_fails_after_tampering():
    s = make_session(CTX_BODY)
    s.ops = s.ops + P("Z q0")
    ok, msg = s.final_check()
    assert not ok and "Phase" in msg


# ============================================================ 15. Workbench
def make_wb(body=WB_BODY, value_range="0:63", **kw):
    return M.Workbench(make_session(body, value_range), **kw)


def test_propose_rewrite_accepts_cost_reducing_equivalent_rewrite():
    wb = make_wb()
    res = wb.propose_rewrite(NHEAD, NHEAD + 2, ["CX q1 q8", "X q0"], rationale="CCX X CCX = CX X")
    assert res["accepted"] is True and "exakt bewiesen" in res["message"] and res["neue_länge"] == NHEAD + 4
    assert fmt(wb.s.ops[NHEAD:]) == ["CX q1 q8", "X q0", "CX q1 q8", "X q0"]
    assert wb.accepted == 1 and wb.s.audit[-1].startswith("[REWRITE]") and "Toffoli 2 -> 0" in wb.s.audit[-1]
    assert wb.full_check()["ok"] is True


def test_propose_rewrite_rejects_non_equivalent_candidate_with_counterexample():
    wb = make_wb()
    before = list(wb.s.ops)
    res = wb.propose_rewrite(NHEAD, NHEAD + 2, ["CX q0 q8", "X q0"])
    assert res["accepted"] is False and "Verifier-Ablehnung" in res["reason"] and "Fenstereingang" in res["reason"]
    assert "allgemeine Belegung verletzt" in res["hinweis"]
    assert wb.s.ops == before and wb.accepted == 0 and wb.undo_stack == []


def test_propose_rewrite_rejects_cost_neutral_unless_neutral_ok():
    wb = make_wb()
    swapped = ["X q0", "CX q1 q8"]
    strict = wb.propose_rewrite(NHEAD + 3, NHEAD + 4, swapped)
    same = wb.propose_rewrite(NHEAD, NHEAD + 2, WB_BODY[:3])
    worse = wb.propose_rewrite(
        NHEAD + 3, NHEAD + 4, ["CX q1 q8", "X q0", "CCZ q0 q1 q2", "CCZ q0 q1 q2"], neutral_ok=True
    )
    relaxed = wb.propose_rewrite(NHEAD + 3, NHEAD + 4, swapped, neutral_ok=True)
    assert strict["accepted"] is False and "keine Kostensenkung" in strict["reason"]
    assert same["accepted"] is False and "keine Kostensenkung" in same["reason"]
    assert worse["accepted"] is False and "keine Kostensenkung" in worse["reason"]  # teurer geht nie durch
    assert relaxed["accepted"] is True and fmt(wb.s.ops[NHEAD + 3 :]) == swapped


def test_propose_rewrite_rejects_syntax_errors_and_bad_indices():
    wb = make_wb()
    n = len(wb.s.ops)
    for lines in (["FOO q0"], ["CX q0 q0"], ["Z_POW q0 1/4"], ["CX q1 q8", 5]):
        res = wb.propose_rewrite(NHEAD, NHEAD + 2, lines)
        assert res["accepted"] is False and "Syntaxfehler" in res["reason"], lines
    for start, end in ((-1, 3), (5, 4), (0, n), (n, n)):
        res = wb.propose_rewrite(start, end, ["X q0"])
        assert res["accepted"] is False and "Indizes außerhalb" in res["reason"], (start, end)
    assert len(wb.s.ops) == n


def test_propose_rewrite_rejects_qubits_that_would_raise_q():
    wb = make_wb()
    res = wb.propose_rewrite(NHEAD, NHEAD + 2, ["CX q1 q8", "X q0", "X q9", "X q9"])
    ok = wb.propose_rewrite(NHEAD, NHEAD + 2, ["CX q1 q8", "X q0", "X q7", "X q7"])  # q7 < Q=9 ist erlaubt
    assert res["accepted"] is False and "Q erhöhen" in res["reason"] and "q9" in res["reason"]
    assert ok["accepted"] is True


def test_propose_rewrite_rejects_unbalanced_push_pop():
    wb = make_wb()
    opened = wb.propose_rewrite(NHEAD, NHEAD + 2, ["PUSH_CONDITION if b0", "CX q1 q8", "X q0"])
    closed = wb.propose_rewrite(NHEAD, NHEAD + 2, ["POP_CONDITION", "CX q1 q8", "X q0", "PUSH_CONDITION if b0"])
    assert opened["accepted"] is False and "nicht ausgeglichen" in opened["reason"] and "Kandidat" in opened["reason"]
    assert closed["accepted"] is False and "ohne passendes PUSH" in closed["reason"]
    wb2 = make_wb(["PUSH_CONDITION if b0", "CCZ q0 q1 q2", "POP_CONDITION"])
    orig_side = wb2.propose_rewrite(NHEAD, NHEAD + 1, [])
    assert orig_side["accepted"] is False and "Originalfenster" in orig_side["reason"]


def test_propose_rewrite_rejects_register_declarations():
    wb = make_wb()
    cand = wb.propose_rewrite(NHEAD, NHEAD + 2, ["CX q1 q8", "X q0", "APPEND_TO_REGISTER q8 r0"])
    cand2 = wb.propose_rewrite(NHEAD, NHEAD + 2, ["CX q1 q8", "X q0", 'REGISTER r1 "y"'])
    orig = wb.propose_rewrite(NHEAD - 1, NHEAD + 2, ["CX q1 q8", "X q0"])
    assert cand["accepted"] is False and "Kandidat enthält Register-Deklarationen" in cand["reason"]
    assert cand2["accepted"] is False and "Register-Deklarationen" in cand2["reason"]
    assert orig["accepted"] is False and "Originalfenster enthält Register-Deklarationen" in orig["reason"]


def test_propose_rewrite_rejects_off_grid_zpow_on_either_side():
    wb = make_wb()
    cand = wb.propose_rewrite(NHEAD, NHEAD + 2, ["CX q1 q8", "X q0", TINY])
    wb2 = make_wb(["CCZ q0 q1 q2", TINY, "CCZ q0 q1 q2"])
    orig = wb2.propose_rewrite(NHEAD, NHEAD + 2, [TINY])
    assert cand["accepted"] is False and "Phasenraster" in cand["reason"]
    assert orig["accepted"] is False and "Phasenraster" in orig["reason"] and toffoli(wb2.s.ops) == 2


def test_propose_rewrite_contextual_proof_unless_exact_only():
    mbu = ["HMR q8 b0", "CZ q0 q1 if b0"]
    wb, strict = make_wb(CTX_BODY), make_wb(CTX_BODY, exact_only=True)
    res = wb.propose_rewrite(NHEAD + 2, NHEAD + 2, mbu)
    res_strict = strict.propose_rewrite(NHEAD + 2, NHEAD + 2, mbu)
    assert res["accepted"] is True and res["message"].startswith("kontextuell verifiziert")
    assert wb.full_check()["ok"] is True and toffoli(wb.s.ops) == 1
    assert res_strict["accepted"] is False and "--exact-only" in res_strict["reason"] and toffoli(strict.s.ops) == 2


def test_propose_rewrite_rejects_measurement_without_phase_correction():
    wb = make_wb(CTX_BODY)
    res = wb.propose_rewrite(NHEAD + 2, NHEAD + 2, ["HMR q8 b0"])
    assert res["accepted"] is False and "Phase" in res["reason"] and toffoli(wb.s.ops) == 2


def test_propose_rewrite_treats_later_read_bit_as_live():
    body = ["BIT_STORE1 b0", "CCZ q0 q1 q2", "CCZ q0 q1 q2", "Z q0 if b0"]
    flipped = make_wb(body).propose_rewrite(NHEAD + 1, NHEAD + 2, ["BIT_INVERT b0"])  # spart 2 Toffoli, kippt aber b0
    same = make_wb(body)
    kept = same.propose_rewrite(NHEAD + 1, NHEAD + 2, ["BIT_STORE1 b0"])  # b0 ist hier ohnehin 1
    assert flipped["accepted"] is False and "Bit b0" in flipped["reason"]
    assert kept["accepted"] is True and kept["message"].startswith("kontextuell") and same.full_check()["ok"]


def test_workbench_undo_restores_previous_circuit():
    wb = make_wb()
    before = fmt(wb.s.ops)
    assert wb.undo() == {"ok": False, "meldung": "nichts zum Zurücknehmen"}
    wb.propose_rewrite(NHEAD, NHEAD + 2, ["CX q1 q8", "X q0"])
    assert fmt(wb.s.ops) != before
    assert wb.undo() == {"ok": True, "länge": len(before)} and fmt(wb.s.ops) == before
    assert wb.undo()["ok"] is False


def test_workbench_run_passes_is_undoable_and_reports_state():
    wb = make_wb(MBU_BODY)
    res = wb.run_passes()
    after = toffoli(wb.s.ops)
    assert after <= 2 and "mbu" in res["zusammenfassung"] and "Q=9" in res["stand"]
    assert wb.undo()["ok"] and toffoli(wb.s.ops) == 4


def test_workbench_dispatch_unknown_tool_and_bad_arguments():
    wb = make_wb()
    assert wb.dispatch("nope", {}) == {"fehler": "unbekanntes Tool nope"}
    assert "falsche Argumente für propose_rewrite" in wb.dispatch("propose_rewrite", {"start": NHEAD})["fehler"]
    assert "falsche Argumente für read_lines" in wb.dispatch("read_lines", {"start": 0, "bogus": 1})["fehler"]
    assert "fehler" in wb.dispatch("analyze_window", {"start": "a", "end": "b"})  # Tool-Fehler statt Absturz
    assert wb.dispatch("note", {"text": "x" * 900}) == {"ok": True} and len(wb.notes[0]) == 500
    assert wb.dispatch("finish", {}) == {"ok": True} and wb.finished == "fertig"
    assert set(t["function"]["name"] for t in M.TOOLS) == {
        "overview",
        "read_lines",
        "find_hotspots",
        "analyze_window",
        "propose_rewrite",
        "run_passes",
        "full_check",
        "undo",
        "note",
        "finish",
    }


def test_workbench_read_lines_and_overview():
    wb = make_wb()
    rows = wb.dispatch("read_lines", {"start": NHEAD, "count": 2})
    clamp = wb.read_lines(999)
    over = wb.dispatch("overview", {})
    assert rows == {"gesamt": NHEAD + 5, "zeilen": [f"{NHEAD}: CCX q0 q1 q8", f"{NHEAD + 1}: X q0"]}
    assert clamp["zeilen"] == []
    assert over["register"] == {"x": 6} and over["angenommene_rewrites"] == 0 and "64" in over["domäne"]
    assert "Toffoli-artig=2" in over["original"] and sum(r["toffoli"] for r in over["profil_top"]) == 2


def test_analyze_window_reports_facts_from_entry_state():
    wb = make_wb(CTX_BODY)
    res = wb.analyze_window(NHEAD + 1, NHEAD + 2)
    assert res["zeilen"] == [f"{NHEAD + 1}: CZ q8 q2", f"{NHEAD + 2}: CCX q0 q1 q8"]
    assert res["qubits"] == ["q0", "q1", "q2", "q8"] and res["toffoli"] == 1
    assert "q8 = q0 & q1" in res["fakten_am_eingang"]
    assert res["freie_saubere_ancillas"] == ["q6", "q7"] and res["exakter_beweis_möglich"] is True
    assert res["bedingungstiefe_am_eingang"] == 0 and res["von_möglichen"] == "2^4"
    assert isinstance(res["erreichbare_zustände"], int) and res["erreichbare_zustände"] <= 8  # q8 ist abhaengig


def test_analyze_window_uses_domain_dont_cares_and_measurement_taint():
    wb = make_wb(["CCX q5 q0 q8", "CX q0 q8", "HMR q8 b0", "Z q0 if b0", "X q8 if b0", "X q8 if b0"], "0:31")
    facts = wb.analyze_window(NHEAD, NHEAD + 1)["fakten_am_eingang"]
    late = wb.analyze_window(NHEAD + 4, NHEAD + 5)
    assert "q5 = 0 (auf allen Stichproben)" in facts and "q8 = 0 (auf allen Stichproben)" in facts
    assert late["fakten_am_eingang"] == ["q8 = 0 (auf allen Stichproben)"]
    wb2 = make_wb(["BIT_STORE1 b0", "PUSH_CONDITION if b0", "HMR q8 b1", "X q8", "X q8", "POP_CONDITION"])
    tainted = wb2.analyze_window(NHEAD + 3, NHEAD + 4)
    assert tainted["fakten_am_eingang"] == ["q8 hängt von Messergebnissen ab"]
    assert tainted["bedingungstiefe_am_eingang"] == 1


def test_analyze_window_rejects_bad_ranges():
    wb = make_wb()
    n = len(wb.s.ops)
    assert "fehler" in wb.analyze_window(-1, 2) and "fehler" in wb.analyze_window(3, 2)
    assert "fehler" in wb.analyze_window(0, n)
    big = M.Workbench(make_session(["X q0"] * 400))
    assert "zu groß" in big.analyze_window(0, 350)["fehler"]


def test_find_hotspots_runs_pairs_dense():
    wb = make_wb()
    runs, pairs, dense = (wb.find_hotspots(k) for k in ("runs", "pairs", "dense"))
    assert runs == {
        "art": "runs",
        "treffer": 1,
        "liste": [{"ziel": "q8", "ccx_indizes": [NHEAD, NHEAD + 2], "anzahl": 2, "spanne": 3}],
    }
    assert pairs["liste"] == [{"gatter": "CCX q0 q1 q8", "start": NHEAD, "ende": NHEAD + 2, "distanz": 2}]
    assert dense["liste"] == [{"start": 0, "ende": NHEAD + 4, "toffoli": 2}]
    no_run = make_wb(["CCX q0 q1 q8", "CX q8 q9", "CCX q0 q1 q8", "CX q8 q9"])  # Ziel wird dazwischen gelesen
    assert no_run.find_hotspots("runs")["treffer"] == 0 and no_run.find_hotspots("pairs")["treffer"] == 1


def test_find_hotspots_conditional_peak_and_invalid_kind():
    wb = make_wb(
        [
            "CCX q0 q1 q8",
            "CX q0 q9",
            "CX q0 q9",
            "CCX q0 q1 q8",
            "PUSH_CONDITION if b0",
            "CCZ q0 q1 q2",
            "POP_CONDITION",
            "CSWAP q0 q1 q2 if b1",
            "CSWAP q0 q1 q2 if b1",
        ]
    )
    cond, peak = wb.find_hotspots("conditional"), wb.find_hotspots("peak")
    assert cond["treffer"] == 3 and cond["liste"][0] == {"idx": NHEAD + 5, "gatter": "CCZ q0 q1 q2", "tiefe": 1}
    assert cond["liste"][1] == {"idx": NHEAD + 7, "gatter": "CSWAP q0 q1 q2 if b1", "tiefe": 0}
    assert peak["treffer"] == 1 and peak["liste"][0]["scratch_gleichzeitig"] == 2
    assert {d["qubit"] for d in peak["liste"][0]["längste_lebensdauern"]} == {"q8", "q9"}
    assert wb.find_hotspots("cond", limit=1)["fehler"].startswith("kind muss")
    assert len(wb.find_hotspots("conditional", limit=1)["liste"]) == 1
    assert make_wb().find_hotspots("conditional")["treffer"] == 0


def test_profile_segments_follows_info_tags():
    ops = P(
        'INFO_TAG "@enter:mul"',
        "CCX q0 q1 q2",
        "CCZ q0 q1 q2",
        'INFO_TAG "@exit:mul"',
        'INFO_TAG "@enter:add"',
        "CCX q0 q1 q2",
        "CX q0 q1",
        'INFO_TAG "@exit:add"',
        "X q0",
    )
    rows = M.profile_segments(ops)
    assert [(r["segment"], r["toffoli"], r["instruktionen"]) for r in rows] == [
        ("mul", 2, 2),
        ("add", 1, 2),
        ("(oberste Ebene)", 0, 1),
    ]


# ============================================================ 16. LLM-Schicht ohne Netzwerk
def test_json_array_extracts_string_arrays():
    assert M._json_array('["CX q0 q1", "X q0"]') == ["CX q0 q1", "X q0"]
    assert M._json_array('Text ```json\n["CX q0 q1"]\n```') == ["CX q0 q1"]
    assert M._json_array('Erst das: ["  X q0  ", ""] fertig.') == ["X q0"]
    assert M._json_array('nimm ["A"] oder ["B"]') == ["A"]
    assert M._json_array("[]") == [] and M._json_array("Geht nicht: []") == []


def test_json_array_rejects_everything_else():
    for text in ("", "keine Liste", "[1, 2]", '["x", 3]', '["unterminated', "[[1]]"):
        assert M._json_array(text) is None, text


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_llm_client_budget_is_enforced_without_network():
    seen = []

    def fake_urlopen(req, timeout=None):
        seen.append(json.loads(req.data.decode("utf-8")))
        return FakeResponse({"choices": [{"message": {"role": "assistant", "content": "hi"}}]})

    with (
        env(),
        patched(M.socket, "create_connection", _network_forbidden),
        patched(M.urllib.request, "urlopen", fake_urlopen),
    ):
        client = M.LLMClient(api_url="http://127.0.0.1:9/v1/chat/completions", api_key="k", max_calls=2)
        first = client.chat("m", [{"role": "user", "content": "x"}], tools=M.TOOLS)
        second = client.chat("m", [{"role": "user", "content": "y"}])
        assert not client.local_default and client.temperature is None and client.default_models() == []
        assert first == {"role": "assistant", "content": "hi"} and second["content"] == "hi"
        assert client.exhausted() and client.calls == 2
        e = raises(M.LLMError, client.chat, "m", [])
        assert "Budget" in str(e) and len(seen) == 2 and not client.dead
        assert seen[0]["tool_choice"] == "auto" and "tools" not in seen[1] and "temperature" not in seen[0]
        assert "chat_template_kwargs" not in seen[0]  # fremdem Endpunkt wird nichts untergeschoben


def test_llm_client_zero_budget_never_calls_out():
    with env(LLM_MAX_CALLS="0"), no_network():
        client = M.LLMClient(api_url="http://127.0.0.1:9/x")
        assert client.max_calls == 0 and client.exhausted()
        assert "Budget" in str(raises(M.LLMError, client.chat, "m", []))
        assert client.calls == 0


def test_llm_client_dead_endpoint_trips_circuit_breaker():
    attempts = []

    def refused(req, timeout=None):
        attempts.append(req.full_url)
        raise urllib.error.URLError("Connection refused")

    with env(), patched(M.urllib.request, "urlopen", refused), patched(M.time, "sleep", _network_forbidden):
        client = M.LLMClient(api_url="http://127.0.0.1:9/x", max_calls=10)
        e1 = raises(M.LLMError, client.chat, "m", [])
        e2 = raises(M.LLMError, client.chat, "m", [])
        assert "nicht erreichbar" in str(e1) and "nicht erreichbar" in str(e2)
        assert client.dead and client.exhausted() and len(attempts) == 1 and client.calls == 1


def test_llm_client_reachable_probe_marks_client_dead():
    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    targets = []

    def refuse(addr, timeout=None):
        targets.append(addr)
        raise ConnectionRefusedError("nope")

    with env():
        down = M.LLMClient(api_url="https://example.invalid/v1/chat")
        up = M.LLMClient()
        with patched(M.socket, "create_connection", refuse):
            assert down.reachable() is False and down.dead and down.exhausted()
        with (
            patched(M.socket, "create_connection", lambda addr, timeout=None: Conn()),
            patched(M.urllib.request, "urlopen", _network_forbidden),
        ):
            assert up.reachable() is True and not up.dead
        assert targets == [("example.invalid", 443)]
        assert up.local_default and up.api_url == M.LOCAL_LLM_URL and up.default_models() == [M.LOCAL_LLM_MODEL]
        assert up.temperature == 0.1 and up.extra_body == {"chat_template_kwargs": {"enable_thinking": False}}


def test_llm_client_non_retryable_http_error_reports_status_code():
    def bad_request(req, timeout=None):
        raise urllib.error.HTTPError(
            req.full_url, 400, "Bad Request", {}, io.BytesIO(b'{"error": "tools unsupported"}')
        )

    with env(), patched(M.urllib.request, "urlopen", bad_request), patched(M.time, "sleep", _network_forbidden):
        client = M.LLMClient(api_url="http://127.0.0.1:9/x", max_calls=3)
        e = raises(M.LLMError, client.chat, "m", [])
        assert e.code == 400 and "tools unsupported" in str(e) and not client.dead


class FakeClient:
    """Ersatz fuer LLMClient: spielt vorbereitete Antworten ab."""

    def __init__(self, replies):
        self.replies, self.calls, self.seen = list(replies), 0, []

    def exhausted(self):
        return not self.replies

    def chat(self, model, messages, tools=None):
        self.calls += 1
        self.seen.append([dict(m) for m in messages])
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def tool_call(name, raw=None, **args):
    return {
        "content": None,
        "tool_calls": [
            {
                "id": f"call_{name}",
                "type": "function",
                "function": {"name": name, "arguments": raw if raw is not None else json.dumps(args)},
            }
        ],
    }


def test_run_agent_applies_verified_tool_calls_from_fake_model():
    wb = make_wb()
    client = FakeClient(
        [
            tool_call("propose_rewrite", start=NHEAD, end=NHEAD + 2, new_lines=["CX q0 q8", "X q0"]),
            tool_call("propose_rewrite", raw="{kaputt"),
            tool_call("propose_rewrite", start=NHEAD, end=NHEAD + 2, new_lines=["CX q1 q8", "X q0"]),
            tool_call("finish", summary="erledigt"),
        ]
    )
    no_tools = M.run_agent(wb, client, ["fake"], steps=10, relay_rounds=1, log=quiet)
    tool_msgs = [m["content"] for m in client.seen[-1] if m.get("role") == "tool"]
    assert no_tools == [] and wb.accepted == 1 and wb.finished == "erledigt" and client.calls == 4
    assert toffoli(wb.s.ops) == 0 and wb.full_check()["ok"]
    assert (
        '"accepted": false' in tool_msgs[0]
        and "Argumente nicht lesbar" in tool_msgs[1]
        and '"accepted": true' in tool_msgs[2]
    )


def test_run_agent_reports_models_without_tool_calling():
    wb = make_wb()
    prose = M.run_agent(wb, FakeClient([{"content": "Ich würde CCX streichen."}]), ["plauderer"], 5, 1, log=quiet)
    refused = M.run_agent(wb, FakeClient([M.LLMError("HTTP 400", 400)]), ["alt"], 5, 1, log=quiet)
    flaky = M.run_agent(wb, FakeClient([M.LLMError("HTTP 500", 500)]), ["wackelig"], 5, 1, log=quiet)
    assert prose == ["plauderer"] and refused == ["alt"] and flaky == [] and wb.accepted == 0


def test_run_json_llm_accepts_verified_answer_and_retries_once_with_counterexample():
    good, bad = '```json\n["CX q1 q8", "X q0"]\n```', '["CX q0 q8", "X q0"]'
    wb = make_wb()
    assert M.json_windows(wb) == [(NHEAD, NHEAD + 2)]
    client = FakeClient([{"content": bad}, {"content": good}])
    accepted = M.run_json_llm(wb, client, "fake", log=quiet)
    assert accepted == 1 and client.calls == 2 and toffoli(wb.s.ops) == 0
    assert "Abgelehnt: Verifier-Ablehnung" in client.seen[1][-1]["content"]
    assert "q8" in client.seen[0][0]["content"] and "CCX q0 q1 q8" in client.seen[0][0]["content"]

    wb2, memo = make_wb(), {}
    stubborn = FakeClient([{"content": bad}, {"content": "[]"}, {"content": good}])
    assert M.run_json_llm(wb2, stubborn, "fake", log=quiet, memo=memo) == 0 and toffoli(wb2.s.ops) == 2
    assert M.run_json_llm(wb2, stubborn, "fake", log=quiet, memo=memo) == 0 and stubborn.calls == 2  # memoisiert
    assert list(memo.values()) == [False]


def test_trim_history_shortens_only_old_tool_results():
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
    msgs += [{"role": "tool", "tool_call_id": str(i), "content": "x" * 1000} for i in range(10)]
    M._trim_history(msgs, 3000)
    assert [len(m["content"]) for m in msgs[-6:]] == [1000] * 6  # die letzten sechs bleiben
    assert msgs[2]["content"] == '{"hinweis": "älteres Tool-Ergebnis gekürzt"}' and msgs[0]["content"] == "s"
    untouched = [{"role": "tool", "content": "x" * 1000} for _ in range(10)]
    M._trim_history(untouched, 10**6)
    assert all(len(m["content"]) == 1000 for m in untouched)


# ============================================================ 17. Offizieller Verifier (Shell-Befehl)
def test_run_official_verifier_substitutes_placeholders():
    with tempfile.TemporaryDirectory() as d:
        cand = os.path.join(d, "mit leerzeichen.kmx")
        with open(cand, "w", encoding="utf-8") as f:
            f.write("X q0\n")
        assert M.run_official_verifier("test -f {candidate}", cand) == (True, "Exit-Code 0")
        assert M.run_official_verifier("test -f {out} && cat {out}", cand) == (True, "X q0")
        assert M.run_official_verifier("cat", cand) == (True, "X q0")  # ohne Platzhalter: angehaengt
        assert M.run_official_verifier("echo {candidate} {out}", cand) == (True, f"{cand} {cand}")


def test_run_official_verifier_reports_non_zero_exit():
    with tempfile.TemporaryDirectory() as d:
        missing = os.path.join(d, "fehlt.kmx")
        assert M.run_official_verifier("false", missing) == (False, "Exit-Code 1")
        assert M.run_official_verifier("test -f {candidate}", missing) == (False, "Exit-Code 1")
        ok, out = M.run_official_verifier("sh -c 'echo abgelehnt; echo grund >&2; exit 7' --", missing)
        assert ok is False and "abgelehnt" in out and "grund" in out
        with env(OFFICIAL_VERIFY_TIMEOUT="1"):
            ok, out = M.run_official_verifier("sleep 5 #", missing)
        assert ok is False and "fehlgeschlagen" in out


# ============================================================ 18. Kommandozeile
def test_cli_optimize_writes_output_equivalent_to_input():
    with tempfile.TemporaryDirectory() as d:
        inp, out, diff = write_input(d), os.path.join(d, "out.kmx"), os.path.join(d, "out.diff")
        rc, text = cli("optimize", inp, "-o", out, "--diff", diff, "--range", "0:63", "--no-kickmix")
        assert rc == 0 and "BESTANDEN" in text and f"Geschrieben: {out}" in text
        orig, cand = M.read_circuit(inp), M.read_circuit(out)
        layout = M.analyze_layout(orig, "x", "0:63")
        dom, _ = M.build_domains(layout, 1 << 20, 64, 64)
        ok, msg, sig = M.Oracle(orig, layout, dom, quiet).check(cand, range(4))  # Vergleich wie cmd_check
        assert ok, msg
        assert toffoli(orig) == 4 and toffoli(cand) <= 2 and M.compute_metrics(cand).num_qubits == 9
        assert sorted(os.listdir(d)) == ["in.kmx", "out.diff", "out.kmx"]  # keine Temporaerdateien
        with open(diff, encoding="utf-8") as f:
            assert "-CCX q0 q1 q8" in f.read()
        rc_check, check_text = cli("check", inp, out, "--range", "0:63", "--no-kickmix")
        assert rc_check == 0 and "ÄQUIVALENT" in check_text and "NICHT" not in check_text


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
        assert toffoli(M.read_circuit(os.path.join(d, "c_optimized.kmx"))) == 0


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
        rc, text = cli("optimize", inp, "-o", os.path.join(d, "o.kmx"), "--range", "0:63", "--no-kickmix")
        assert rc == 1 and "Formatfehler" in text and "Zeile 9" in text and os.listdir(d) == ["in.kmx"]


def test_cli_legacy_positional_form_with_llm_disabled():
    with tempfile.TemporaryDirectory() as d:
        inp, out, diff = write_input(d), os.path.join(d, "legacy_out.kmx"), os.path.join(d, "legacy.diff")
        rc, text = cli(inp, out, diff, "--range", "0:63", "--no-kickmix", LLM_MAX_CALLS="0")  # no_network() aktiv
        assert rc == 0 and os.path.exists(out) and os.path.exists(diff) and "LLM" not in text
        assert toffoli(M.read_circuit(out)) <= 2
        rc_check, _ = cli("check", inp, out, "--range", "0:63", "--no-kickmix")
        assert rc_check == 0


def test_cli_require_official_verify_without_command_returns_3_and_writes_nothing():
    with tempfile.TemporaryDirectory() as d:
        inp, out = write_input(d), os.path.join(d, "out.kmx")
        rc, text = cli("optimize", inp, "-o", out, "--range", "0:63", "--no-kickmix", REQUIRE_OFFICIAL_VERIFY="1")
        assert rc == 3 and "REQUIRE_OFFICIAL_VERIFY=1" in text
        assert os.listdir(d) == ["in.kmx"]


def test_cli_official_verifier_gates_the_write():
    with tempfile.TemporaryDirectory() as d:
        inp, out = write_input(d), os.path.join(d, "out.kmx")
        with open(out, "w", encoding="utf-8") as f:
            f.write("ALT\n")
        rc_fail, text_fail = cli("optimize", inp, "-o", out, "--range", "0:63", "--no-kickmix", "--verify-cmd", "false")
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
        assert rc_fail == 3 and "OFFIZIELLER VERIFIER: FAIL" in text_fail and kept == "ALT\n"
        assert rc_env == 3
        assert rc_ok == 0 and "OFFIZIELLER VERIFIER: PASS" in text_ok and toffoli(M.read_circuit(out)) <= 2
        assert sorted(os.listdir(d)) == ["in.kmx", "out.kmx"]  # Kandidaten-Datei aufgeraeumt


def test_cli_info_and_builtin_selftest():
    with tempfile.TemporaryDirectory() as d:
        inp = write_input(d)
        rc, text = cli("info", inp, "--range", "0:63", "--no-kickmix")
        assert rc == 0 and "Toffoli-artig=4" in text and "Q=10" in text and os.listdir(d) == ["in.kmx"]
    rc, text = cli("--selftest")
    assert rc == 0 and "FAIL" not in text and text.count("OK  ") >= 8


def test_cli_agent_skips_llm_stage_when_endpoint_is_down():
    def refuse(addr, timeout=None):
        raise ConnectionRefusedError("down")

    with tempfile.TemporaryDirectory() as d:
        inp, out, buf = write_input(d), os.path.join(d, "out.kmx"), io.StringIO()
        with (
            env(),
            patched(M.socket, "create_connection", refuse),
            patched(M.urllib.request, "urlopen", _network_forbidden),
            contextlib.redirect_stdout(buf),
        ):
            rc = M.main(["agent", inp, "-o", out, "--models", "fake", "--range", "0:63", "--no-kickmix"])
        assert rc == 0 and "LLM-Stufe übersprungen" in buf.getvalue() and toffoli(M.read_circuit(out)) <= 2


def test_cli_agent_runs_stubbed_llm_stage_end_to_end():
    script = [
        tool_call("propose_rewrite", start=NHEAD, end=NHEAD + 2, new_lines=["CX q1 q8", "X q0"]),
        tool_call("full_check"),
        tool_call("finish", summary="ok"),
    ]
    calls = []

    def fake_chat(self, model, messages, tools=None):
        calls.append(model)
        return script.pop(0)

    # WB_BODY ohne die Kuerzung durch die Paesse: --iters 0 laesst dem "Modell" etwas uebrig
    with tempfile.TemporaryDirectory() as d:
        inp, out, buf = write_input(d, WB_BODY), os.path.join(d, "out.kmx"), io.StringIO()
        with (
            env(),
            no_network(),
            patched(M.LLMClient, "reachable", lambda self, timeout=3.0: True),
            patched(M.LLMClient, "chat", fake_chat),
            contextlib.redirect_stdout(buf),
        ):
            rc = M.main(
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
        assert rc == 0 and calls == ["fake"] * 3 and "propose_rewrite -> angenommen" in text
        assert "1 verifizierte Rewrites | ok" in text and toffoli(M.read_circuit(out)) == 0


# ============================================================ Regressionen (frühere Funde, behoben)
def test_check_exact_treats_written_bits_as_unknown():
    # Regression (Soundness): check_exact machte nur GELESENE Bits zu freien Variablen. Ein Bit, das ein Fenster
    # nur schreibt,
    # startet stillschweigend bei 0 - "b0 := 0" gilt dann als bewiesen gleich zu "b0 unveraendert", obwohl b0 vorher
    # 1 sein kann. Erwartet: 'refuted' (Startwert geschriebener, nicht toter Bits als Variable aufnehmen).
    assert M.check_exact(P(), P("BIT_STORE0 b0"), 0, set())[0] == "refuted"
    assert M.check_exact(P("BIT_INVERT b0", "BIT_INVERT b0"), P("BIT_STORE0 b0"), 0, set())[0] == "refuted"


def test_propose_rewrite_rejects_clearing_a_live_bit():
    # Regression: Folge davon: propose_rewrite nimmt den (falschen) L1-"Beweis" und ignoriert, dass check_context die
    # Abweichung "Bit b0" bereits gefunden hat. Der Rewrite loescht b0, das danach von "Z q0 if b0" gelesen wird;
    # erst full_check (L3) faellt durch und rollt zurueck ("sollte nie passieren").
    wb = make_wb(["BIT_STORE1 b0", "CCZ q0 q1 q2", "CCZ q0 q1 q2", "Z q0 if b0"])
    res = wb.propose_rewrite(NHEAD + 1, NHEAD + 2, ["BIT_STORE0 b0"])
    assert res["accepted"] is False, (res, wb.s.final_check())


def test_check_with_missing_candidate_returns_1():
    # Regression: main() prueft nur args.input; `check ORIG fehlend.kmx` endet mit einem FileNotFoundError-Traceback.
    with tempfile.TemporaryDirectory() as d:
        rc, _ = cli("check", write_input(d), os.path.join(d, "fehlt.kmx"), "--range", "0:63", "--no-kickmix")
        assert rc == 1


def test_malformed_range_gives_clean_error():
    # Regression: `--range abc` (oder LO > HI wie 5:2) fuehrt zu einem ValueError-Traceback statt Exit-Code 1.
    with tempfile.TemporaryDirectory() as d:
        for rng in ("abc", "5:2"):
            rc, _ = cli("info", write_input(d), "--range", rng, "--no-kickmix")
            assert rc == 1


def test_parser_rejects_integer_zpow_exponent():
    # Regression: kickmix verlangt [-+]?[0-9]+\.[0-9]+ (siehe Docstring von phase_op);
    # _EXP_RE liess "Z_POW q0 1" durch.
    # Ueber propose_rewrite kann so eine Zeile verifiziert in die Ausgabedatei gelangen, die kickmix nicht parst.
    raises(M.KmxError, M.parse_line, "Z_POW q0 1")


def test_workbench_rejects_integer_zpow_exponent():
    # Regression: Folge des Parser-Befunds: der Rewrite wird angenommen, die Datei waere fuer kickmix ungueltig.
    wb = make_wb(["CCZ q0 q1 q2", "Z q0", "CCZ q0 q1 q2"])
    res = wb.propose_rewrite(NHEAD, NHEAD + 2, ["Z_POW q0 1"])
    assert res["accepted"] is False, res


def test_parser_keeps_hash_inside_quoted_text():
    # Regression: '#' im Text schnitt die Zeile ab und hinterliess einen offenen String; kickmix liest es als Zeichen.
    assert M.parse_line('INFO_TAG "a # b"  # Kommentar').text == '"a # b"'
    raises(M.KmxError, M.parse_line, 'INFO_TAG "a')
    raises(M.KmxError, M.parse_line, 'INFO_TAG "a"b"')


def test_range_wider_than_register_is_rejected():
    # Regression: --range 0:127 bei 6-Bit-Register lieferte eine "vollständige" Domäne,
    # deren Lanes x mod 64 wiederholen.
    ops = circuit(CTX_BODY)
    raises(M.KmxError, M.analyze_layout, ops, "x", "0:127")


def test_tool_call_with_already_parsed_arguments_is_answered():
    # Regression: manche Server liefern function.arguments als Objekt statt als JSON-String -> TypeError-Absturz.
    wb = make_wb()
    _, msg = M._answer_tool_call(
        wb, {"id": "1", "function": {"name": "read_lines", "arguments": {"start": 0, "count": 2}}}
    )
    assert "fehler" not in json.loads(msg["content"])


def test_json_mode_llm_error_does_not_memoise_window():
    # Regression: ein transienter LLM-Fehler sperrte das Fenster auch fuer alle spaeteren Modelle.
    class BrokenClient:
        calls = 0

        def exhausted(self):
            return self.calls >= 3

        def chat(self, model, messages, tools=None):
            self.calls += 1
            raise M.LLMError("HTTP 503")

    wb = make_wb(["CCX q0 q1 q8", "CX q2 q3", "CCX q0 q1 q8"])
    memo = {}
    assert M.run_json_llm(wb, BrokenClient(), "m", quiet, memo) == 0
    assert memo == {}


def test_written_outputs_get_default_permissions():
    # Regression: mkstemp legte .kmx und .diff mit 0600 an.
    umask = os.umask(0)
    os.umask(umask)
    with tempfile.TemporaryDirectory() as d:
        inp, out, diff = write_input(d), os.path.join(d, "out.kmx"), os.path.join(d, "out.diff")
        rc, _ = cli("optimize", inp, "-o", out, "--diff", diff, "--range", "0:63", "--no-kickmix")
        assert rc == 0
        for path in (out, diff):
            assert os.stat(path).st_mode & 0o777 == 0o666 & ~umask, oct(os.stat(path).st_mode)


# ------------------------------------------------------------------ Runner (ohne pytest)
def _run_all(include_bugs=False):
    tests = [(n, f) for n, f in globals().items() if callable(f) and n.startswith("test_")]
    bugs = [(n, f) for n, f in globals().items() if callable(f) and n.startswith("bug_")] if include_bugs else []
    failed, t_all = 0, time.time()
    for name, fn in tests + bugs:
        buf, t0 = io.StringIO(), time.time()
        try:
            with contextlib.redirect_stdout(buf):
                fn()
            status, note = "PASS", ""
        except BaseException as e:  # auch SystemExit aus argparse soll als Fehlschlag zaehlen
            if isinstance(e, KeyboardInterrupt):
                raise
            is_bug = name.startswith("bug_")
            status, note = ("BUG?" if is_bug else "FAIL"), f"  {type(e).__name__}: {str(e)[:300]}"
            failed += not is_bug
        print(f"{status} {name} ({time.time() - t0:.2f}s){note}")
    print(
        f"{len(tests) - failed}/{len(tests)} Tests bestanden in {time.time() - t_all:.1f}s"
        + (f" | {len(bugs)} BUG?-Faelle zusaetzlich ausgefuehrt" if bugs else "")
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_all("--bugs" in sys.argv[1:]))
