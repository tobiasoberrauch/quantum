"""Kennzahlen, Z_POW-Klassifikation und Phasenarithmetik (kmx.cost)."""

import random
from fractions import Fraction

import kmx
from tests.kmx.helpers import (
    TINY,
    P,
)


def test_compute_metrics_q_is_max_index_plus_one():
    m = kmx.compute_metrics(P("X q3", "CX q61 q2"))
    assert m.num_qubits == 62 and m.distinct_qubits == 3 and m.ops == 2
    assert kmx.compute_metrics([]).num_qubits == 0
    # Bits zaehlen nicht als Qubits
    assert kmx.compute_metrics(P("NEG", "BIT_STORE1 b9")).num_qubits == 0


def test_compute_metrics_accepts_text_lines_and_ignores_comments():
    m = kmx.compute_metrics(
        ["# q999 nur Kommentar", "CSWAP q3 q61 q2", "CCX q3 q61 q2", "Z_POW q3 0.25"]
    )
    assert (m.num_qubits, m.ops, m.toffoli, m.toffoli_cost, m.t_like, m.rotations) == (
        62,
        3,
        2,
        2,
        1,
        0,
    )


def test_compute_metrics_counts_toffoli_like_gates_only():
    m = kmx.compute_metrics(
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
    assert (
        kmx.compute_metrics(
            ["CX q0 q1", "CZ q0 q1", "SWAP q0 q1", "X q0", "Z q0"]
        ).toffoli
        == 0
    )


def test_zpow_classification_clifford_t_like_fine():
    def level(e):
        return kmx.zpow_info(e)[1]

    # Clifford: frei
    assert [level(e) for e in ("0.5", "1.0", "-0.5", "1.5", "2.0")] == [0] * 5
    assert [level(e) for e in ("0.25", "-0.25", "0.75", "1.25")] == [2] * 4  # T-artig
    # feine Rotation
    assert [level(e) for e in ("0.125", "0.0625", "0.3", "-0.001")] == [3] * 4
    m = kmx.compute_metrics(
        ["Z_POW q0 0.5", "Z_POW q0 0.25", "Z_POW q0 0.75", "Z_POW q0 0.125", "Z q0"]
    )
    assert (m.t_like, m.rotations) == (2, 1)


def test_circuit_cost_is_q_times_inner_cost():
    assert kmx.circuit_cost([]) == 0.0
    assert (
        kmx.circuit_cost(["CX q0 q1", "SWAP q0 q1", "X q0", "CZ q0 q1", "Z_POW q0 0.5"])
        == 0.0
    )
    assert kmx.circuit_cost(["CCX q0 q1 q2"]) == 3.0  # Q=3 x 1 Toffoli
    assert kmx.circuit_cost(["CCX q0 q1 q9", "CCZ q0 q1 q2"]) == 20.0  # Q=10 x 2
    assert abs(kmx.circuit_cost(["Z_POW q0 0.25"]) - 0.25) < 1e-12  # 1 T = 1/4 Toffoli
    assert abs(kmx.circuit_cost(["Z_POW q1 0.125"]) - 2 * kmx.ROT_WEIGHT) < 1e-9
    assert kmx.circuit_cost(P("CCX q0 q1 q2")) == kmx.circuit_cost(["CCX q0 q1 q2"])
    assert abs(kmx.score_estimate(10, 2.0, 4.0, 1.0, 7.0) - 10 * (2 + 1 + 7)) < 1e-12


def test_phase_exponent_exact_on_grid_only():
    assert kmx.phase_exponent(kmx.parse_line("Z q0")) == Fraction(1)
    assert kmx.phase_exponent(kmx.parse_line("Z_POW q0 0.25")) == Fraction(1, 4)
    assert kmx.phase_exponent(kmx.parse_line("Z_POW q0 -1.5")) == Fraction(-3, 2)
    on_grid = kmx.phase_op(0, Fraction(1, 1 << 127), None)
    assert kmx.phase_exponent(on_grid) == Fraction(1, 1 << 127)
    # 10^-46 liegt nicht auf dem Raster
    assert kmx.phase_exponent(kmx.parse_line(TINY)) is None
    assert kmx.phase_exponent(kmx.parse_line("Z_POW q0 0.3")) is None
    assert (
        kmx.phase_exponent(kmx.parse_line("CZ q0 q1")) is None
        and kmx.phase_exponent(kmx.parse_line("X q0")) is None
    )


def test_phase_op_zero_gives_none_and_one_gives_z():
    assert kmx.phase_op(0, Fraction(0), None) is None
    assert (
        kmx.phase_op(0, Fraction(2), None) is None
        and kmx.phase_op(0, Fraction(-4), None) is None
    )
    assert kmx.phase_op(3, Fraction(1), None).fmt() == "Z q3"
    assert kmx.phase_op(3, Fraction(3), 7).fmt() == "Z q3 if b7"
    assert kmx.phase_op(3, Fraction(-1), None).fmt() == "Z q3"


def test_phase_op_wraps_mod_two_with_exact_decimal():
    def text(a, b):
        return kmx.phase_op(0, Fraction(a, b), None).fmt()

    assert text(7, 4) == "Z_POW q0 -0.25"
    assert text(3, 2) == "Z_POW q0 -0.5"
    assert text(9, 4) == "Z_POW q0 0.25"
    assert text(-1, 8) == "Z_POW q0 -0.125"
    assert text(1, 1 << 40) == "Z_POW q0 0.0000000000009094947017729282379150390625"
    assert kmx.phase_op(5, Fraction(1, 4), 2).fmt() == "Z_POW q5 0.25 if b2"


def test_phase_op_output_is_valid_kmx_and_exact_for_random_grid_angles():
    rng = random.Random(11)
    for _ in range(300):
        fr = Fraction(rng.randrange(-(1 << 20), 1 << 20), 1 << rng.randrange(0, 128))
        op = kmx.phase_op(1, fr, None)
        if op is None:
            assert fr % 2 == 0
            continue
        assert kmx.parse_line(op.fmt()).key() == op.key()  # keine Brueche, kein 1e-5
        assert "e" not in op.fmt().lower() and "/" not in op.fmt()
        assert (kmx.phase_exponent(op) - fr) % 2 == 0, (fr, op)
