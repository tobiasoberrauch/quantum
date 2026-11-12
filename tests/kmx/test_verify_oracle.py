"""L3: End-to-End-Prüfer (kmx.verify.oracle)."""

from fractions import Fraction

import kmx
from tests.kmx.helpers import (
    CANCEL_BODY,
    CTX_BODY,
    DIFF_BODY,
    GROUP_BODY,
    MBU_BODY,
    WB_BODY,
    P,
    circuit,
    quiet,
    setup,
)


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
        assert kmx.Oracle(ops, layout, dom, quiet).self_check() == [], body


def test_oracle_self_check_flags_uncorrected_hmr_kickback():
    ops, layout, dom, _ = setup(["CCX q0 q1 q8", "CZ q8 q3", "HMR q8 b0"])
    issues = kmx.Oracle(ops, layout, dom, quiet).self_check()
    assert len(issues) == 1 and "Messzufall" in issues[0]


def test_oracle_self_check_flags_dirty_scratch_changed_register_and_open_stack():
    def issues(body):
        ops, layout, dom, _ = setup(body)
        return " | ".join(kmx.Oracle(ops, layout, dom, quiet).self_check())

    assert "Scratch" in issues(["CCX q0 q1 q8"])
    assert "Register" in issues(["X q0"])
    assert "Bedingungsstapel" in issues(["PUSH_CONDITION if b0"])


def test_oracle_check_accepts_equivalent_rewrite():
    ops, layout, dom, _ = setup(CTX_BODY)
    oracle = kmx.Oracle(ops, layout, dom, quiet)
    mbu = circuit(["CCX q0 q1 q8", "CZ q8 q2", "HMR q8 b0", "CZ q0 q1 if b0"])
    ccz = circuit(["CCZ q0 q1 q2"])
    ok1, msg1, sig1 = oracle.check(mbu, range(4))
    ok2, _, sig2 = oracle.check(ccz, range(2))
    assert ok1 and "identisch" in msg1 and ok2
    assert (
        sig1.tof_mean == 1.0
        and sig2.tof_mean == 1.0
        and oracle.orig_sig(0).tof_mean == 2.0
    )


def test_oracle_check_rejects_wrong_register():
    ops, layout, dom, _ = setup(CTX_BODY)
    ok, msg, _ = kmx.Oracle(ops, layout, dom, quiet).check(ops + P("X q0"))
    assert not ok and "Registerinhalt" in msg and "64 betroffene Lanes" in msg


def test_oracle_check_rejects_wrong_phase():
    ops, layout, dom, _ = setup(CTX_BODY)
    oracle = kmx.Oracle(ops, layout, dom, quiet)
    ok, msg, _ = oracle.check(ops + P("CZ q0 q5"))
    ok2, msg2, _ = oracle.check(
        ops + P("Z_POW q0 " + kmx.phase_op(0, Fraction(1, 1 << 127), None).args[1])
    )
    ok3, msg3, _ = oracle.check(ops + P("NEG"))
    # kleinstes x mit Bit 0 und Bit 5
    assert not ok and "Phase" in msg and "x=33" in msg
    assert not ok2 and "Phase" in msg2  # selbst 2^-127 Halbdrehung faellt auf
    assert not ok3 and "Phase" in msg3


def test_oracle_check_rejects_dirty_scratch_and_unbalanced_stack():
    ops, layout, dom, _ = setup(CTX_BODY)
    oracle = kmx.Oracle(ops, layout, dom, quiet)
    ok, msg, _ = oracle.check(ops + P("CX q0 q8"))
    ok2, msg2, _ = oracle.check(ops + P("BIT_STORE1 b0", "PUSH_CONDITION if b0"))
    ok3, msg3, _ = oracle.check(ops[:-1])  # Uncompute fehlt
    assert not ok and "Scratch" in msg
    assert not ok2 and "Bedingungsstapel" in msg2
    assert not ok3 and "Scratch" in msg3


def test_oracle_check_rejects_missing_hmr_correction_on_some_seed():
    ops, layout, dom, _ = setup(CTX_BODY)
    ok, msg, _ = kmx.Oracle(ops, layout, dom, quiet).check(
        circuit(["CCX q0 q1 q8", "CZ q8 q2", "HMR q8 b0"]), range(4)
    )
    assert not ok and "Phase" in msg
