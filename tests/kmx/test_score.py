"""Exakter invsqrt-Score und Rotations-Trimmen (kmx.score)."""

import kmx
import kmx.score
from tests.kmx.helpers import make_session, patched, quiet

INVSQRT_HEAD = (
    "".join(f"APPEND_TO_REGISTER q{i} r0\n" for i in range(22)) + 'REGISTER r0 "x"\n'
)
# zwei sich aufhebende Toffolis auf Scratch q22 und ein T-artiges Z_POW
INVSQRT_BODY = "CCX q0 q1 q22\nCCX q0 q1 q22\nZ_POW q0 0.25\n"


def invsqrt_setup(body=INVSQRT_BODY):
    """22-Bit-Register: invsqrt-Kontrakt x in [1, 3133452], vollständige Domäne."""
    ops = kmx.parse_text(INVSQRT_HEAD + body)
    layout = kmx.analyze_layout(ops, "x")
    dom, _ = kmx.build_domains(layout, 1 << 23, 64, 64)
    assert layout.invsqrt and dom.exhaustive and dom.n == 3133452
    return ops, layout, dom


def test_invsqrt_score_exact_value_on_small_contract_circuit():
    ops, layout, dom = invsqrt_setup()
    rep = kmx.invsqrt_score(ops, layout, dom)
    assert (rep.q, rep.toffoli, rep.t, rep.rot) == (23, 2.0, 1.0, 0.0)
    assert rep.cost == 2.25 and rep.score == 51.75  # Q x (Toffoli + T/4)
    assert rep.eps == float("inf") and rep.rot_t == 0.0  # keine feine Rotation
    # die Phase ist weit weg von 1/sqrt(x): Fehler/Toleranz deterministisch
    assert rep.worst_x == 3133451 and round(rep.worst_ratio, 3) == 3695508230.765
    assert rep.diff is None and rep.rots is None
    detailed = kmx.invsqrt_score(ops, layout, dom, detail=True)
    assert detailed.score == rep.score and detailed.rots == []
    assert len(detailed.diff) == dom.n


def test_invsqrt_score_is_none_without_numpy():
    ops, layout, dom = invsqrt_setup()
    with patched(kmx.score, "np", None):
        assert kmx.invsqrt_score(ops, layout, dom) is None
        session = kmx.Session(ops, layout, dom, dom, kmx.Options(), log=quiet)
        assert session.exact_score(ops) is None


def test_invsqrt_score_is_none_without_invsqrt_layout():
    s = make_session(["CCX q0 q1 q8", "CCX q0 q1 q8"])  # 6-Bit-Register, 0:63
    assert not s.layout.invsqrt and s.dom.exhaustive
    assert kmx.invsqrt_score(s.ops, s.layout, s.dom) is None
    assert s.exact_score(s.ops) is None


def test_trim_rotations_reports_removed_zero_when_nothing_can_be_trimmed():
    s = make_session(["Z_POW q0 0.0001", "Z_POW q0 -0.0001"])
    ops, st = kmx.trim_rotations(s.ops, s.layout, s.dom)  # kein invsqrt-Layout
    assert st == {"removed": 0} and ops == s.ops and ops is not s.ops
    inv_ops, layout, dom = invsqrt_setup()
    ops, st = kmx.trim_rotations(inv_ops, layout, dom)  # keine feine Rotation
    assert st == {"removed": 0} and ops == inv_ops
    with patched(kmx.score, "np", None):  # ohne numpy kein exakter Score
        ops, st = kmx.trim_rotations(inv_ops, layout, dom)
    assert st == {"removed": 0} and ops == inv_ops
    assert s.trim_rotations_step() is None and s.trimmed is None
