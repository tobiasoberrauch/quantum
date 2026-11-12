"""Domänen und Registerlayout (kmx.domains, kmx.layout)."""

import tempfile

import kmx
import kmx.layout
from tests.kmx.helpers import (
    CTX_BODY,
    HEAD,
    P,
    bit,
    circuit,
    cli,
    raises,
    setup,
    write_input,
)


# Domaenen
def test_pattern_bit_lane_i_carries_bit_k_of_i():
    for m in (1, 5, 8, 37, 64):
        for k in range(7):
            v = kmx.pattern_bit(k, m)
            assert v < (1 << m)
            assert all(bit(v, i) == (i >> k) & 1 for i in range(m)), (k, m)


def test_exhaustive_domain_enumerates_the_value_range():
    ops, layout, _, _ = setup([], "3:10")
    dom = kmx.exhaustive_domain(layout)
    assert dom.n == 8 and dom.exhaustive and dom.all_lanes == 0xFF
    for lane in range(8):
        x = sum(
            bit(dom.init_q[q], lane) << k for k, q in enumerate(layout.input_qubits)
        )
        assert x == 3 + lane
    assert dom.describe(2) == "x=5"


def test_sample_domain_is_seeded_and_stays_in_range():
    _, layout, _, _ = setup([], "5:40")
    a, b, c = (
        kmx.sample_domain(layout, 32, 1),
        kmx.sample_domain(layout, 32, 1),
        kmx.sample_domain(layout, 32, 2),
    )
    values = [
        sum(bit(a.init_q[q], lane) << k for k, q in enumerate(layout.input_qubits))
        for lane in range(32)
    ]
    assert a.init_q == b.init_q and a.init_q != c.init_q
    assert not a.exhaustive and a.n == 32
    assert all(5 <= v <= 40 for v in values) and 5 in values and 40 in values


def test_build_domains_exhaustive_only_when_range_is_small_enough():
    _, layout, dom, sample_dom = setup([], "0:63")
    assert (
        dom.exhaustive
        and dom.n == 64
        and not sample_dom.exhaustive
        and sample_dom.n == 64
    )
    too_big, _ = kmx.build_domains(layout, 32, 16, 48)  # max_exhaustive < 64
    assert not too_big.exhaustive and too_big.n == 48
    _, no_range, _, _ = setup([], None)
    unknown, _ = kmx.build_domains(no_range, 1 << 20, 16, 48)
    assert no_range.lo is None and not unknown.exhaustive


def test_analyze_layout_register_names_and_fallbacks():
    ops = kmx.parse_text(
        HEAD + 'APPEND_TO_REGISTER q9 r1\nAPPEND_TO_REGISTER b4 r1\nREGISTER r1 "out"\n'
    )
    by_name = kmx.analyze_layout(ops, "x", "0:63")
    other = kmx.analyze_layout(ops, "nope", "0:63")
    bare = kmx.analyze_layout(P("CX q0 q1"))
    assert by_name.input_qubits == [0, 1, 2, 3, 4, 5] and by_name.pinned == {
        0,
        1,
        2,
        3,
        4,
        5,
        9,
    }
    assert (
        by_name.reg_bits == [4]
        and by_name.names == {0: "x", 1: "out"}
        and not by_name.invsqrt
    )
    assert (by_name.lo, by_name.hi) == (0, 63) and not by_name.notes
    assert other.input_qubits == [0, 1, 2, 3, 4, 5] and any(
        "nope" in n for n in other.notes
    )
    assert (
        bare.input_qubits == list(range(22))
        and (bare.lo, bare.hi) == (1, kmx.layout.INVSQRT_MAX_X)
        and bare.invsqrt
    )


def test_malformed_range_gives_clean_error():
    # Regression: `--range abc` (oder LO > HI wie 5:2) fuehrt zu einem
    # ValueError-Traceback statt Exit-Code 1.
    with tempfile.TemporaryDirectory() as d:
        for rng in ("abc", "5:2"):
            rc, _ = cli("info", write_input(d), "--range", rng, "--no-kickmix")
            assert rc == 1


def test_range_wider_than_register_is_rejected():
    # Regression: --range 0:127 bei 6-Bit-Register lieferte eine "vollständige" Domäne,
    # deren Lanes x mod 64 wiederholen.
    ops = circuit(CTX_BODY)
    raises(kmx.KmxError, kmx.analyze_layout, ops, "x", "0:127")
