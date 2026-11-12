"""L1/L2: exakter und kontextueller Fenster-Verifier und Differenzkegel
(kmx.verify.window).
"""

import kmx
from tests.kmx.helpers import (
    CTX_BODY,
    TINY,
    P,
    circuit,
    fmt,
    setup,
)


def test_check_exact_proves_equivalent_windows():
    cases = [
        (["CCX q0 q1 q2", "CCX q0 q1 q2", "CX q0 q1"], ["CX q0 q1"]),
        (["CCX q0 q1 q2", "X q0", "CCX q0 q1 q2"], ["CX q1 q2", "X q0"]),
        (["CCX q0 q1 q3", "CCX q0 q2 q3"], ["CX q1 q2", "CCX q0 q2 q3", "CX q1 q2"]),
        (["CX q0 q1", "CX q1 q0", "CX q0 q1"], ["SWAP q0 q1"]),
        (["Z_POW q0 0.25", "Z_POW q0 0.25"], ["Z_POW q0 0.5"]),
        (["X q0 if b0", "X q0 if b0"], []),
        (
            ["HMR q2 b0", "CZ q0 q1 if b0"],
            ["HMR q2 b0", "PUSH_CONDITION if b0", "CZ q1 q0", "POP_CONDITION"],
        ),
    ]
    for a, b in cases:
        status, msg = kmx.check_exact(P(*a), P(*b), 0, set())
        assert status == "proved" and "exakt bewiesen" in msg, (a, b, msg)


def test_check_exact_refutes_inequivalent_windows_with_counterexample():
    # nur im Kontext gleich, nicht allgemein
    cases = [
        (["CCX q0 q1 q2"], ["CX q0 q2"]),
        (["X q0"], []),
        (["Z q0"], ["Z_POW q0 0.5"]),
        (["NEG"], []),
        (["CZ q0 q1"], ["CZ q0 q2"]),
        (["X q0 if b0"], ["X q0"]),
        (["X q0 if b0"], ["X q0 if b1"]),
        (
            ["CCX q0 q1 q2"],
            ["HMR q2 b0", "CZ q0 q1 if b0"],
        ),
        (["HMR q2 b0", "CZ q0 q1 if b0"], ["HMR q2 b0"]),
        (["BIT_STORE1 b0"], ["BIT_STORE0 b0"]),
    ]
    for a, b in cases:
        status, msg = kmx.check_exact(P(*a), P(*b), 0, set())
        assert status == "refuted" and "verletzt" in msg, (a, b, msg)
    _, msg = kmx.check_exact(P("CCX q0 q1 q2"), P("CX q0 q2"), 0, set())
    assert "q0=1" in msg and "q1=0" in msg and "Qubit q2" in msg


def test_check_exact_dead_bits_and_entry_depth_matter():
    store = (P("BIT_STORE1 b0"), P("BIT_STORE0 b0"))
    assert kmx.check_exact(*store, 0, set())[0] == "refuted"
    assert kmx.check_exact(*store, 0, {0})[0] == "proved"  # b0 wird danach nie gelesen
    # Im Inneren eines PUSH-Blocks ist die umgebende Maske eine zusaetzliche freie
    # Variable
    assert (
        kmx.check_exact(P("PUSH_CONDITION if b0", "POP_CONDITION"), P(), 1, set())[0]
        == "proved"
    )
    assert kmx.check_exact(P("X q0", "X q0"), P(), 1, set())[0] == "proved"
    assert kmx.check_exact(P("X q0"), P("X q0", "NEG", "NEG"), 1, set())[0] == "proved"
    assert kmx.check_exact(P("X q0"), P(), 1, set())[0] == "refuted"


def test_check_exact_is_na_for_too_many_variables():
    chain = [f"CX q{i} q{i + 1}" for i in range(20)]  # 21 verbundene Qubits
    status, msg = kmx.check_exact(P(*chain), P(), 0, set())
    small, msg2 = kmx.check_exact(
        P("CCX q0 q1 q2"), P("CX q0 q2"), 0, set(), max_vars=2
    )
    assert status == "na" and "21 Variablen > 20" in msg
    assert small == "na" and "3 Variablen > 2" in msg2
    # genau 20 passt noch
    assert kmx.check_exact(P(*chain[:19]), P(), 0, set())[0] == "refuted"


def test_check_exact_is_na_for_off_grid_zpow_angle():
    for a, b in (
        ([TINY], []),
        ([], [TINY]),
        ([TINY], [TINY]),
        (["Z_POW q0 0.3"], ["Z_POW q0 0.3"]),
    ):
        status, msg = kmx.check_exact(P(*a), P(*b), 0, set())
        assert status == "na" and "Phasenraster" in msg, (a, b)
    assert kmx.off_grid_phase(P("Z_POW q0 0.5", TINY, "Z q0")).fmt() == TINY
    assert kmx.off_grid_phase(P("Z_POW q0 0.5", "Z q0")) is None


def test_v3_verifier_interface_never_claims_unproved_equivalence():
    V = kmx.BitParallelKMXVerifier
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


# 25 unbeteiligte Qubits
SPECT = [f"CX q{i} q{i + 1}" for i in range(10, 34, 2)] + ["Z_POW q40 0.125"]


def test_difference_cone_proves_wide_window_with_many_spectators():
    wide = ["CCX q0 q1 q2", *SPECT, "X q0", "CCX q0 q1 q2"]
    cand = [*SPECT, "CX q1 q2", "X q0"]
    a, b = kmx.difference_cone(P(*wide), P(*cand))
    assert len({q for o in P(*wide) for q in o.qs}) == 28  # ohne Kegel > 20 Variablen
    assert fmt(a) == ["CCX q0 q1 q2", "X q0", "CCX q0 q1 q2"] and fmt(b) == [
        "CX q1 q2",
        "X q0",
    ]
    assert kmx.check_exact(P(*wide), P(*cand), 0, set())[0] == "proved"


def test_difference_cone_refutes_near_miss():
    wide = ["CCX q0 q1 q2", *SPECT, "X q0", "CCX q0 q1 q2"]
    assert (
        kmx.check_exact(P(*wide), P(*SPECT, "CX q0 q2", "X q0"), 0, set())[0]
        == "refuted"
    )
    assert (
        kmx.check_exact(
            P(*wide), P(*SPECT[:-1], "Z_POW q40 0.25", "CX q1 q2", "X q0"), 0, set()
        )[0]
        == "refuted"
    )
    # Zuschauer fehlt
    assert (
        kmx.check_exact(P(*wide), P(*SPECT[1:], "CX q1 q2", "X q0"), 0, set())[0]
        == "refuted"
    )


def test_difference_cone_keeps_global_phase_neg():
    a, b = kmx.difference_cone(P("NEG", *SPECT), P(*SPECT))
    assert fmt(a) == ["NEG"] and fmt(b) == []
    assert kmx.check_exact(P("NEG", *SPECT), P(*SPECT), 0, set())[0] == "refuted"
    assert kmx.check_exact(P(*SPECT, "NEG"), P("NEG", *SPECT), 0, set())[0] == "proved"
    assert kmx.check_exact(P("NEG", *SPECT, "NEG"), P(*SPECT), 0, set())[0] == "proved"


def test_difference_cone_strips_common_prefix_and_suffix_on_shared_qubits():
    pre, post = ["CCX q0 q1 q2", "CZ q2 q3"], ["CSWAP q3 q0 q1", "Z_POW q2 0.125"]
    a, b = kmx.difference_cone(
        P(*pre, "X q0", "X q0", "CX q4 q5", *post), P(*pre, "CX q4 q5", *post)
    )
    assert fmt(a) == ["X q0", "X q0"] and fmt(b) == []


def test_difference_cone_keeps_whole_component_when_order_inside_differs():
    orig, cand = P("CX q0 q1", "X q1", "CX q5 q6"), P("X q1", "CX q5 q6", "CX q0 q1")
    a, b = kmx.difference_cone(orig, cand)
    assert fmt(a) == ["CX q0 q1", "X q1"] and fmt(b) == ["X q1", "CX q0 q1"]
    # X auf dem Ziel kommutiert mit CX
    assert kmx.check_exact(orig, cand, 0, set())[0] == "proved"


def test_difference_cone_returns_conditional_or_measuring_windows_unchanged():
    for extra in (
        "X q0 if b0",
        "HMR q0 b0",
        "R q0",
        "PUSH_CONDITION if b0",
        "BIT_STORE1 b0",
    ):
        orig, cand = P("X q1", extra, "CX q5 q6"), P("X q1", "CX q5 q6")
        a, b = kmx.difference_cone(orig, cand)
        assert a is orig and b is cand, extra
        a, b = kmx.difference_cone(cand, orig)
        assert a is cand and b is orig, extra


def _ctx_entry(dom):
    ops = circuit(["CCX q0 q1 q8"])
    return kmx.simulate(kmx.compile_ops(ops), dom, "E")


def test_check_context_accepts_rewrite_valid_only_on_reachable_states():
    _, _, dom, _ = setup(CTX_BODY)
    orig_w, cand_w = P("CCX q0 q1 q8"), P("HMR q8 b0", "CZ q0 q1 if b0")
    ok, msg, cost = kmx.check_context(_ctx_entry(dom), orig_w, cand_w, {0}, dom, 4)
    assert ok and "4 Messrunde" in msg and cost == (1.0, 0.0)
    # allgemein falsch: q8 beliebig
    assert kmx.check_exact(orig_w, cand_w, 0, {0})[0] == "refuted"


def test_check_context_rejects_wrong_phase_dirty_qubit_and_live_bit():
    _, _, dom, _ = setup(CTX_BODY)
    entry = _ctx_entry(dom)
    no_fix = kmx.check_context(entry, P("CCX q0 q1 q8"), P("HMR q8 b0"), {0}, dom, 4)
    dirty = kmx.check_context(entry, P("CCX q0 q1 q8"), P("CX q0 q8"), set(), dom, 4)
    live = kmx.check_context(
        entry, P("CCX q0 q1 q8"), P("HMR q8 b0", "CZ q0 q1 if b0"), set(), dom, 4
    )
    assert not no_fix[0] and "Phase" in no_fix[1]
    assert (
        not dirty[0]
        and "Qubit q8" in dirty[1]
        and "x=1" in dirty[1]
        and "Fenstereingang" in dirty[1]
    )
    assert not live[0] and "Bit b0" in live[1]  # b0 gilt ohne dead_bits als lebendig


def test_check_context_does_not_mutate_entry_state_and_uses_one_round_without_randomness():  # noqa: E501
    _, _, dom, _ = setup(CTX_BODY)
    entry = _ctx_entry(dom)
    before = (dict(entry.q), dict(entry.b), entry.phase, list(entry.zpow_planes))
    ok, msg, cost = kmx.check_context(
        entry, P("CCX q0 q1 q8", "CCX q0 q1 q8"), P(), set(), dom, 7
    )
    assert ok and "x 1 Messrunde" in msg and cost == (2.0, 0.0)
    assert before == (entry.q, entry.b, entry.phase, entry.zpow_planes)


# Funde, behoben)
def test_check_exact_treats_written_bits_as_unknown():
    # Regression (Soundness): check_exact machte nur GELESENE Bits zu freien Variablen.
    # Ein Bit, das ein Fenster nur schreibt, startet stillschweigend bei 0 - "b0 := 0"
    # gilt dann als bewiesen gleich zu "b0 unveraendert", obwohl b0 vorher 1 sein kann.
    # Erwartet: 'refuted' (Startwert geschriebener, nicht toter Bits als Variable
    # aufnehmen).
    assert kmx.check_exact(P(), P("BIT_STORE0 b0"), 0, set())[0] == "refuted"
    assert (
        kmx.check_exact(
            P("BIT_INVERT b0", "BIT_INVERT b0"), P("BIT_STORE0 b0"), 0, set()
        )[0]
        == "refuted"
    )
