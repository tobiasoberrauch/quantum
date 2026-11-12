"""Syntaktische Pässe: Faltung, Auslöschung, Phasenfusion (kmx.passes.cancel)."""

import random

import kmx
import kmx.ops
from tests.kmx.helpers import (
    TINY,
    P,
    fmt,
)
from tests.kmx.reference import (
    brute_force,
    rand_gate,
)


def test_pass_fold_turns_cx_triple_into_swap():
    out, n = kmx.pass_fold(P("X q9", "CX q0 q1", "CX q1 q0", "CX q0 q1", "X q9"))
    assert n == 1 and fmt(out) == ["X q9", "SWAP q0 q1", "X q9"]
    assert (
        kmx.check_exact(P("CX q0 q1", "CX q1 q0", "CX q0 q1"), out[1:2], 0, set())[0]
        == "proved"
    )


def test_pass_fold_leaves_non_triples_and_conditional_cx_alone():
    for lines in (
        ["CX q0 q1", "CX q0 q1", "CX q0 q1"],
        ["CX q0 q1", "CX q1 q0", "CX q1 q0"],
        ["CX q0 q1", "CX q1 q0", "X q5", "CX q0 q1"],
        ["CX q0 q1", "CX q1 q2", "CX q0 q1"],
        ["CX q0 q1 if b0", "CX q1 q0", "CX q0 q1"],
        ["CX q0 q1", "CX q1 q0", "CX q0 q1 if b0"],
    ):
        out, n = kmx.pass_fold(P(*lines))
        assert n == 0 and fmt(out) == lines, lines


def test_pass_fold_removes_empty_push_pop_blocks_including_nested():
    out, n = kmx.pass_fold(
        P(
            "X q0",
            "PUSH_CONDITION if b0",
            "PUSH_CONDITION if b1",
            "POP_CONDITION",
            "POP_CONDITION",
            "X q1",
        )
    )
    kept, n2 = kmx.pass_fold(P("PUSH_CONDITION if b0", "X q0", "POP_CONDITION"))
    assert n == 2 and fmt(out) == ["X q0", "X q1"]
    assert n2 == 0 and len(kept) == 3


def _cancel(*lines, **kw):
    out, cancelled, merged = kmx.pass_cancel(P(*lines), **kw)
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
    assert kmx.check_exact(P(*lines), P(*out), 0, set())[0] == "proved"


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
        if kmx.ops.GATE_ARITY.get(mid.split()[0]) and mid.split()[0] != "R":
            # Sperre war noetig
            assert kmx.check_exact(P(*lines), P(mid), 0, set())[0] == "refuted", mid


def test_pass_cancel_blocked_by_hmr():
    for lines in (
        ["CX q0 q8", "HMR q8 b0", "CX q0 q8"],
        ["CX q0 q8", "HMR q0 b0", "CX q0 q8"],
        ["CZ q0 q8", "HMR q8 b0", "CZ q0 q8"],
        ["Z q8", "HMR q8 b0", "Z q8"],
    ):
        assert _cancel(*lines) == (lines, 0, 0), lines
    # fremdes Qubit stoert nicht
    assert _cancel("CX q0 q8", "HMR q5 b0", "CX q0 q8") == (
        ["HMR q5 b0"],
        1,
        0,
    )


def test_pass_cancel_blocked_by_writer_of_condition_bit():
    for mid in (
        "BIT_INVERT b0",
        "BIT_STORE1 b0",
        "BIT_STORE0 b0",
        "HMR q5 b0",
        "BIT_STORE1 b0 if b3",
    ):
        lines = ["X q0 if b0", mid, "X q0 if b0"]
        assert _cancel(*lines) == (lines, 0, 0), mid
    assert _cancel("X q0 if b0", "BIT_INVERT b1", "X q0 if b0") == (
        ["BIT_INVERT b1"],
        1,
        0,
    )
    assert _cancel("X q0 if b0", "X q0 if b1") == (["X q0 if b0", "X q0 if b1"], 0, 0)
    assert _cancel("X q0 if b0", "X q0") == (["X q0 if b0", "X q0"], 0, 0)


def test_pass_cancel_blocked_by_push_pop_barrier():
    lines = ["X q0", "PUSH_CONDITION if b0", "X q0", "POP_CONDITION", "X q0"]
    assert _cancel(*lines) == (lines, 0, 0)
    inside = ["PUSH_CONDITION if b0", "X q0", "CX q1 q2", "X q0", "POP_CONDITION"]
    assert _cancel(*inside) == (
        ["PUSH_CONDITION if b0", "CX q1 q2", "POP_CONDITION"],
        1,
        0,
    )


def test_pass_cancel_respects_search_depth():
    lines = ["X q0", "CX q1 q2", "CX q3 q4", "X q0"]
    assert _cancel(*lines, depth=1) == (lines, 0, 0)
    assert _cancel(*lines, depth=2) == (["CX q1 q2", "CX q3 q4"], 1, 0)
    assert _cancel("X q0", "X q0", depth=0) == ([], 1, 0)


def test_pass_cancel_merges_phases_exactly():
    assert _cancel(
        "Z_POW q0 0.0009765625",
        "CX q1 q2",
        "Z_POW q0 0.0009765625",
        "Z q3",
        "Z_POW q3 -0.75",
    ) == (
        ["Z_POW q0 0.001953125", "CX q1 q2", "Z_POW q3 0.25"],
        0,
        2,
    )
    # Z*Z = 1: beide weg
    assert _cancel("Z q0", "CZ q0 q1", "Z q0") == (
        ["CZ q0 q1"],
        0,
        1,
    )
    assert _cancel("Z_POW q0 0.25", "Z_POW q0 0.25", "Z_POW q0 0.5") == (["Z q0"], 0, 2)
    # q0 ist nur Kontrolle
    assert _cancel("Z_POW q0 1.5", "CX q0 q1", "Z_POW q0 0.5") == (
        ["CX q0 q1"],
        0,
        1,
    )
    assert _cancel("Z_POW q0 0.25 if b1", "Z_POW q0 0.5 if b1") == (
        ["Z_POW q0 0.75 if b1"],
        0,
        1,
    )


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
    assert _cancel("Z_POW q0 0.3", "Z_POW q0 0.3") == (
        ["Z_POW q0 0.3", "Z_POW q0 0.3"],
        0,
        0,
    )
    assert _cancel("Z_POW q0 0.25", TINY, "Z_POW q0 0.25") == (
        ["Z_POW q0 0.5", TINY],
        0,
        1,
    )


def test_pass_cancel_keeps_meta_ops_and_is_equivalent_on_random_circuits():
    assert _cancel("X q0", 'INFO_TAG "@enter:a"', "X q0") == (
        ['INFO_TAG "@enter:a"'],
        1,
        0,
    )
    rng = random.Random(7)
    changed = 0
    for _ in range(150):
        lines = [rand_gate(rng, [0, 1, 2, 3]) for _ in range(rng.randint(4, 14))]
        out, cancelled, merged = kmx.pass_cancel(P(*lines))
        changed += bool(cancelled or merged)
        assert brute_force(P(*lines), [0, 1, 2, 3]) == brute_force(out, [0, 1, 2, 3]), (
            lines,
            fmt(out),
        )
        assert len(out) <= len(lines) - cancelled * 2 - merged + 0
    assert changed >= 30
