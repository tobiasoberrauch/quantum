"""Sitzung: Pässe bis zum Fixpunkt und commit (kmx.session)."""

import kmx
from tests.kmx.helpers import (
    CANCEL_BODY,
    CTX_BODY,
    DIFF_BODY,
    GROUP_BODY,
    MBU_BODY,
    NHEAD,
    P,
    circuit,
    fmt,
    make_session,
    quiet,
    toffoli,
)


# auf den Selftest-Schaltkreisen
def _run_case(body, opts=None, value_range="0:63"):
    s = make_session(body, value_range, opts or kmx.Options(final_rounds=8))
    summary = s.run_passes()
    return s, summary


def test_session_mbu_case_drops_to_two_toffolis_and_repacks():
    s, summary = _run_case(MBU_BODY)
    ok, msg = s.final_check()
    assert toffoli(s.orig) == 4 and toffoli(s.ops) <= 2 and ok and "8 Messrunde" in msg
    assert (
        summary["mbu"]["toffoli_saved"] == 2
        and kmx.compute_metrics(s.ops).counts["HMR"] == 2
    )
    # 6 + 3 Scratch
    assert (
        kmx.compute_metrics(s.orig).num_qubits == 10
        and kmx.compute_metrics(s.ops).num_qubits == 9
    )
    assert any(a.startswith("[OK] Measurement-Based Uncomputation") for a in s.audit)
    assert any(a.startswith("[OK] Qubit-Repacking") for a in s.audit)
    assert (
        s.sig.tof_mean == 2.0
        and kmx.Oracle(s.orig, s.layout, s.dom, quiet).self_check() == []
    )


def test_session_group_case_drops_to_one_toffoli():
    s, summary = _run_case(GROUP_BODY)
    assert toffoli(s.orig) == 6 and toffoli(s.ops) <= 1 and s.final_check()[0]
    assert summary["sim"]["toffoli_saved"] >= 2
    assert kmx.compute_metrics(s.ops).num_qubits <= 7


def test_session_difference_control_case_drops_to_one_toffoli():
    s, _ = _run_case(DIFF_BODY)
    assert toffoli(s.orig) == 3 and toffoli(s.ops) <= 1 and s.final_check()[0]


def test_session_cancellation_case_drops_to_zero_toffolis():
    s, summary = _run_case(CANCEL_BODY)
    assert toffoli(s.orig) == 2 and toffoli(s.ops) == 0 and s.final_check()[0]
    assert summary["cancelled"] == 3 and fmt(s.ops) == fmt(s.orig[:NHEAD])


def test_session_merges_rotations_on_value_equal_qubits():
    s, _ = _run_case(
        ["CX q0 q8", "Z_POW q8 0.125", "Z_POW q0 0.0625", "CX q0 q8"],
        kmx.Options(final_rounds=4),
    )
    assert (
        kmx.compute_metrics(s.orig).rotations == 2
        and kmx.compute_metrics(s.ops).rotations == 1
    )
    assert s.final_check()[0] and "Z_POW q0 0.1875" in fmt(s.ops)


def test_session_pass_switches_disable_mbu_and_repack():
    no_mbu, summary = _run_case(CTX_BODY, kmx.Options(mbu=False, repack=False))
    with_mbu, _ = _run_case(CTX_BODY)
    assert "mbu" not in summary and "repack" not in summary
    assert toffoli(no_mbu.ops) == 2 and kmx.compute_metrics(no_mbu.ops).num_qubits == 9
    assert (
        toffoli(with_mbu.ops) == 1 and kmx.compute_metrics(with_mbu.ops).num_qubits == 7
    )
    assert no_mbu.final_check()[0] and with_mbu.final_check()[0]


def test_session_without_full_domain_runs_only_syntactic_passes():
    # keine --range: nur Stichprobe
    sampled, summary = _run_case(MBU_BODY, value_range=None)
    cancel, _ = _run_case(CANCEL_BODY, value_range=None)
    allowed, _ = _run_case(MBU_BODY, kmx.Options(sampled_facts=True), value_range=None)
    assert not sampled.dom.exhaustive and toffoli(sampled.ops) == 4 and summary == {}
    assert toffoli(cancel.ops) == 0  # Ausloeschung ist rein syntaktisch
    assert toffoli(allowed.ops) <= 2 and allowed.final_check()[0]


def test_session_skips_mbu_and_repack_when_original_violates_contract():
    # q20 endet schmutzig
    s, summary = _run_case(["CCX q0 q1 q8", "CZ q8 q2", "CCX q0 q1 q8", "CX q0 q20"])
    assert not s.clean and "mbu" not in summary and "repack" not in summary
    assert toffoli(s.ops) == 2 and s.final_check()[0]


def test_session_commit_rejects_wrong_candidate_and_keeps_state():
    s = make_session(CTX_BODY)
    before, sig = list(s.ops), s.sig
    rejected = s.commit("Test", s.ops + P("X q0"), "absichtlich falsch")
    assert rejected is False and s.ops == before and s.sig is sig
    assert (
        s.audit[-1].startswith("[VERWORFEN] Test: absichtlich falsch")
        and "Registerinhalt" in s.audit[-1]
    )


def test_session_commit_accepts_equivalent_candidate():
    s = make_session(CTX_BODY)
    cand = circuit(["CCZ q0 q1 q2"])
    assert s.commit("Test", cand, "CCX-Sandwich = CCZ") is True
    assert (
        s.ops is cand and s.audit[-1].startswith("[OK] Test") and s.sig.tof_mean == 1.0
    )
    assert s.final_check()[0]


def test_session_final_check_fails_after_tampering():
    s = make_session(CTX_BODY)
    s.ops = s.ops + P("Z q0")
    ok, msg = s.final_check()
    assert not ok and "Phase" in msg
