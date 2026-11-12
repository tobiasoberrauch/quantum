"""Wortparalleler Simulator: Wahrheitstabellen je Instruktion (kmx.simulator)."""

from fractions import Fraction

import kmx
from tests.kmx.helpers import (
    NHEAD,
    P,
    bit,
    circuit,
    phase_bit,
    run,
    tt_domain,
)


def test_sim_ccx_truth_table():
    st = run(["CCX q0 q1 q2"], [0, 1, 2])
    for lane in range(8):
        a, b, c = lane & 1, (lane >> 1) & 1, (lane >> 2) & 1
        assert (bit(st.q[0], lane), bit(st.q[1], lane), bit(st.q[2], lane)) == (
            a,
            b,
            c ^ (a & b),
        )
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
        # Phasengatter aendern keine Werte
        assert all(st.q[q] == kmx.pattern_bit(q, 8) for q in range(3))


def test_sim_zpow_accumulates_exactly():
    z = run(["Z q0"], [0, 1]).planes()
    assert run(["Z_POW q0 0.5", "Z_POW q0 0.5"], [0, 1]).planes() == z
    assert run(["Z_POW q0 0.25"] * 4, [0, 1]).planes() == z
    assert run(["Z_POW q0 0.125"] * 8, [0, 1]).planes() == z
    assert run(["Z_POW q0 1.0"], [0, 1]).planes() == z
    assert run(["Z_POW q0 0.25", "Z_POW q0 -0.25"], [0, 1]).planes() == [0] * 128
    # 2 Halbdrehungen = Identitaet
    assert run(["Z_POW q0 1.5", "Z_POW q0 0.5"], [0, 1]).planes() == [0] * 128
    assert run(["Z_POW q0 0.5"], [0, 1]).planes() != z
    assert (
        run(["Z_POW q0 0.25", "Z_POW q1 0.25"], [0, 1]).planes()
        != run(["Z_POW q0 0.5"], [0, 1]).planes()
    )


def test_sim_zpow_single_plane_per_power_of_two():
    st = run(["Z_POW q0 0.5"], [0])
    tiny = run([kmx.phase_op(0, Fraction(1, 1 << 127), None).fmt()], [0])
    assert [j for j, p in enumerate(st.planes()) if p] == [126] and st.planes()[
        126
    ] == 0b10
    assert [j for j, p in enumerate(tiny.planes()) if p] == [0]


def test_sim_hmr_writes_bit_resets_qubit_and_kicks_back_phase():
    r = 0b0110
    st = run(["HMR q0 b0"], [0, 1], meas={("H", 0, 0): r})
    assert st.q[0] == 0 and st.b[0] == r and st.q[1] == kmx.pattern_bit(1, 4)
    for lane in range(4):
        # (-1)^(Messbit * alter Wert)
        assert phase_bit(st, lane) == bit(r, lane) & (lane & 1)


def test_sim_hmr_kickback_is_cancelled_by_conditional_z_correction():
    r = 0b1010  # q2 ist Scratch und startet in |0>
    fixed = run(
        ["CCX q0 q1 q2", "HMR q2 b0", "CZ q0 q1 if b0"], [0, 1], meas={("H", 0, 0): r}
    )
    raw = run(["CCX q0 q1 q2", "HMR q2 b0"], [0, 1], meas={("H", 0, 0): r})
    assert fixed.q[2] == 0 and raw.q[2] == 0
    assert (
        fixed.planes()
        == run(["CCX q0 q1 q2", "CCX q0 q1 q2"], [0, 1]).planes()
        == [0] * 128
    )
    assert (
        raw.planes()[127] == r & kmx.pattern_bit(0, 4) & kmx.pattern_bit(1, 4) == 0b1000
    )


def test_sim_measurement_randomness_is_coupled_by_seed_bit_and_occurrence():
    a = run(["HMR q0 b3", "HMR q1 b3", "HMR q2 b4"], [0, 1, 2, 3, 4, 5], seed=5)
    b = run(["X q1", "HMR q2 b4", "HMR q0 b3"], [0, 1, 2, 3, 4, 5], seed=5)
    c = run(["HMR q0 b3"], [0, 1, 2, 3, 4, 5], seed=6)
    first = kmx.State(tt_domain(list(range(6))), 5).rand("H", 3)
    # gleicher Schluessel (Bit, wievieltes HMR) -> gleiches Ergebnis
    assert b.b[3] == first and b.b[4] == a.b[4]
    assert a.b[3] != first  # zweites HMR auf b3 zieht ein neues Ergebnis
    assert c.b[3] != first  # anderer Seed
    assert a.draw_counts == {("H", 3): 2, ("H", 4): 1}


def test_sim_conditional_gate_fires_only_where_bit_is_set():
    r = 0b1010_0101
    st = run(
        ["HMR q2 b0", "X q1 if b0", "CX q0 q1 if b1"], [0, 1, 2], meas={("H", 0, 0): r}
    )
    never = run(
        ["X q0 if b9", "CCX q0 q1 q2 if b9", "Z q0 if b9", "NEG if b9"], [0, 1, 2]
    )
    assert st.q[1] == kmx.pattern_bit(1, 8) ^ r  # b1 wurde nie gesetzt: CX feuert nicht
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
    assert (
        st.q[4] == A & B
        and st.q[5] == A
        and st.q[6] == A & B
        and st.q[7] == ALL
        and st.q[8] == ALL
    )
    # ueberzaehliges POP ist ein No-op
    assert st.b[2] == A and st.stack == [] and st.top is None


def test_sim_push_on_unset_bit_disables_block_including_measurement():
    st = run(
        ["PUSH_CONDITION if b0", "X q0", "HMR q1 b1", "NEG", "POP_CONDITION", "X q1"],
        [0, 1],
    )
    assert (
        st.q[0] == kmx.pattern_bit(0, 4) and st.q[1] == kmx.pattern_bit(1, 4) ^ 0b1111
    )
    # kein Messergebnis gezogen
    assert st.planes() == [0] * 128 and st.draw_counts == {} and st.b.get(1, 0) == 0


def test_sim_masked_hmr_only_measures_active_lanes():
    A, r = 0b0101, 0b0110
    st = run(["HMR q1 b1 if b0"], [0, 1], bits={0: A, 1: 0b1000}, meas={("H", 1, 0): r})
    assert st.b[1] == (0b1000 & ~A) | (r & A)
    assert st.q[1] == kmx.pattern_bit(1, 4) & ~A
    assert st.planes()[127] == r & kmx.pattern_bit(1, 4) & A


def test_sim_bit_ops_respect_mask():
    A = 0b0110
    st = run(
        [
            "BIT_STORE1 b1",
            "BIT_STORE0 b1 if b0",
            "BIT_INVERT b2 if b0",
            "BIT_INVERT b3",
            "BIT_STORE1 b4 if b0",
        ],
        [0, 1],
        bits={0: A},
    )
    assert (st.b[1], st.b[2], st.b[3], st.b[4]) == (0b1111 & ~A, A, 0b1111, A)


def test_sim_reset_clears_qubit_and_randomises_phase_only_if_set():
    r = 0b1001
    st = run(["R q0", "R q5"], [0, 1], meas={("R", 0, 0): r})
    assert st.q[0] == 0 and st.q.get(5, 0) == 0
    assert st.planes()[127] == r & kmx.pattern_bit(0, 4)
    assert st.draw_counts == {("R", 0): 1}  # R auf |0> zieht keinen Zufall


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
    assert (st.toffoli_lanes, st.t_lanes, st.rotation_lanes) == (8 + 3 + 0, 8, 3)
    sim = kmx.simulate(
        kmx.compile_ops(P("CCX q0 q1 q2", "CCX q0 q1 q2")),
        tt_domain([0, 1, 2]),
        count=True,
    )
    assert sim.toffoli_lanes == 16 and sim.q == tt_domain([0, 1, 2]).init_q


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
    depths = kmx.push_depths(ops)
    layout = kmx.analyze_layout(ops, "x", "0:63")
    assert depths[NHEAD:] == [0, 0, 1, 1, 0, 0, 0]  # Tiefe VOR der Instruktion
    # b0 wird ueberschrieben
    assert kmx.dead_bits_after(ops, NHEAD + 1, {0, 1, 2}, layout, depths) == {0}
    # PUSH liest b0 noch
    assert kmx.dead_bits_after(ops, NHEAD, {0}, layout, depths) == set()
    assert kmx.dead_bits_after(ops, len(ops) - 1, {0, 1, 2}, layout, depths) == {
        0,
        1,
        2,
    }
