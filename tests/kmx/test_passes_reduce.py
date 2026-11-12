"""Simulationsgeführte Reduktion, MBU und Repacking (kmx.passes)."""

import kmx
from tests.kmx.helpers import (
    CTX_BODY,
    NHEAD,
    fmt,
    quiet,
    setup,
    toffoli,
)


# Paesse, direkt
def test_pass_sim_reduce_drops_gates_that_never_fire_on_the_domain():
    body = ["CCX q5 q0 q8", "CZ q8 q1", "CCX q5 q0 q8"]
    ops, layout, dom, sample_dom = setup(body, "0:31")  # q5 ist auf der Domaene immer 0
    out, stats = kmx.pass_sim_reduce(ops, layout, dom, sample_dom)
    full_ops, full_layout, full_dom, full_sample_dom = setup(body, "0:63")
    kept, _ = kmx.pass_sim_reduce(full_ops, full_layout, full_dom, full_sample_dom)
    assert (
        fmt(out) == fmt(ops[:NHEAD])
        and stats["dead"] == 3
        and stats["toffoli_saved"] == 2
    )
    assert kmx.Oracle(ops, layout, dom, quiet).check(out)[0]
    assert toffoli(kept) == 2  # ohne Don't-Care bleibt alles


def test_pass_sim_reduce_replaces_implied_control_by_cx():
    ops, layout, dom, sample_dom = setup(
        ["CX q0 q8", "CCX q0 q8 q9", "CZ q9 q1", "CCX q0 q8 q9", "CX q0 q8"]
    )
    out, stats = kmx.pass_sim_reduce(ops, layout, dom, sample_dom)
    assert toffoli(out) == 0 and stats["toffoli_saved"] == 2 and stats["cx"] == 2
    assert kmx.Oracle(ops, layout, dom, quiet).check(out)[0]


def test_pass_sim_reduce_returns_same_ops_when_nothing_applies():
    ops, layout, dom, sample_dom = setup(["CCZ q0 q1 q2"])
    out, stats = kmx.pass_sim_reduce(ops, layout, dom, sample_dom)
    assert (
        all(a is b for a, b in zip(out, ops, strict=False))
        and len(out) == len(ops)
        and not stats.get("toffoli_saved")
    )


def test_pass_mbu_replaces_uncompute_chain_by_measurement_and_correction():
    ops, layout, dom, _ = setup(CTX_BODY)
    out, stats = kmx.pass_mbu(ops, layout, dom)
    assert stats == {"chains": 1, "toffoli_saved": 1}
    assert fmt(out[NHEAD:]) == [
        "CCX q0 q1 q8",
        "CZ q8 q2",
        "HMR q8 b0",
        "CZ q0 q1 if b0",
    ]
    assert kmx.Oracle(ops, layout, dom, quiet).check(out, range(6))[0]


def test_pass_mbu_ignores_dirty_or_toffoli_free_chains_and_register_targets():
    # Ziel ist ein Register-Qubit
    for body in (
        ["CCX q0 q1 q8", "CZ q8 q2"],  # q8 wird nie |0>
        ["CX q0 q8", "CZ q8 q2", "CX q0 q8"],  # kein CCX in der Kette: nichts zu sparen
        ["CCX q0 q1 q2", "CCX q0 q1 q2"],
    ):
        ops, layout, dom, _ = setup(body)
        out, stats = kmx.pass_mbu(ops, layout, dom)
        assert stats == {} and fmt(out) == fmt(ops), body


def test_pass_mbu_picks_fresh_measurement_bit():
    ops, layout, dom, _ = setup(
        ["BIT_STORE1 b0", "X q0 if b3", "X q0 if b3", "BIT_STORE0 b0", *CTX_BODY]
    )
    out, stats = kmx.pass_mbu(ops, layout, dom)
    assert (
        stats["chains"] == 1
        and "HMR q8 b4" in fmt(out)
        and "CZ q0 q1 if b4" in fmt(out)
    )
    assert kmx.Oracle(ops, layout, dom, quiet).check(out, range(4))[0]


def test_pass_repack_reuses_freed_wires_with_lowest_indices():
    ops, layout, dom, _ = setup(
        ["CX q0 q20", "CZ q20 q1", "CX q0 q20", "CX q1 q30", "CZ q30 q2", "CX q1 q30"]
    )
    out, stats = kmx.pass_repack(ops, layout, dom)
    assert fmt(out[NHEAD:]) == [
        "CX q0 q6",
        "CZ q6 q1",
        "CX q0 q6",
        "CX q1 q6",
        "CZ q6 q2",
        "CX q1 q6",
    ]
    assert (
        stats["q_before"],
        stats["q_after"],
        stats["peak_scratch"],
        stats["lifetimes"],
    ) == (31, 7, 1, 2)
    assert kmx.Oracle(ops, layout, dom, quiet).check(out)[0]


def test_pass_repack_keeps_overlapping_lifetimes_apart_and_reports_no_gain():
    ops, layout, dom, _ = setup(
        ["CX q0 q20", "CX q1 q30", "CZ q20 q30", "CX q1 q30", "CX q0 q20"]
    )
    out, stats = kmx.pass_repack(ops, layout, dom)
    again, stats2 = kmx.pass_repack(out, layout, dom)
    assert fmt(out[NHEAD:]) == [
        "CX q0 q6",
        "CX q1 q7",
        "CZ q6 q7",
        "CX q1 q7",
        "CX q0 q6",
    ]
    assert stats["peak_scratch"] == 2 and stats["q_after"] == 8
    assert stats2["q_after"] == stats2["q_before"] == 8 and fmt(again) == fmt(out)
    assert kmx.Oracle(ops, layout, dom, quiet).check(out)[0]
