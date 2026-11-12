"""Konkrete Gegenbeispiele: das erste x, an dem ein Kandidat den Kontrakt verletzt,
und welche Eigenschaft (register, scratch, phase, condition_stack).

Rein lesend: simuliert Basis und Kandidat auf der Hauptdomäne der Sitzung und vergleicht
Lane für Lane. Bei invsqrt wird die Phase gegen 1/sqrt(x) mit der offiziellen Toleranz
geprüft (über `invsqrt_score`), sonst gegen die Phase der Basis.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from kmx._optional import np
from kmx.domains import Domain, first_lane
from kmx.ops import Op
from kmx.score import invsqrt_score
from kmx.session import Session
from kmx.simulator import State, compile_ops, simulate

PROP_PARSE, PROP_Q, PROP_REGISTER = "parse", "Q", "register"
PROP_SCRATCH, PROP_PHASE, PROP_STACK = "scratch", "phase", "condition_stack"
PROP_OTHER, PROP_SANDBOX, PROP_MEASUREMENT = "other", "sandbox", "measurement"
# Feste Messergebnis-Muster (Bitindex -> Ergebnis 1?), zusätzlich zu Zufallsrunden
OUTCOME_PATTERNS: tuple[tuple[str, Callable[[int], bool]], ...] = (
    ("alle Messbits 0", lambda i: False),
    ("alle Messbits 1", lambda i: True),
    ("gerade Messbits 1", lambda i: i % 2 == 0),
    ("ungerade Messbits 1", lambda i: i % 2 == 1),
)
Counterexample = dict[str, Any]


def make_counterexample(
    prop: str, detail: str, x: int | None = None, where: str = "", lanes: int = 0
) -> Counterexample:
    """Gegenbeispiel als JSON-fähiges Wörterbuch (so steht es im Protokoll)."""
    return {
        "property": prop,
        "x": x,
        "where": where or (f"x={x}" if x is not None else ""),
        "affected_lanes": lanes,
        "detail": detail,
    }


def _lane_x(session: Session, lane: int) -> int | None:
    """Eingabewert einer Lane, wenn die Domäne vollständig ist (Lane i = lo + i)."""
    lo = session.layout.lo
    return lo + lane if session.dom.exhaustive and lo is not None else None


def _at(session: Session, prop: str, lanes: int, detail: str) -> Counterexample:
    lane = first_lane(lanes)
    return make_counterexample(
        prop,
        detail,
        _lane_x(session, lane),
        session.dom.describe(lane),
        lanes.bit_count(),
    )


def _register_diff(session: Session, st: State, ref: State) -> int:
    diff = 0
    for q in session.layout.pinned:
        diff |= st.q.get(q, 0) ^ ref.q.get(q, 0)
    for b in session.layout.reg_bits:
        diff |= st.b.get(b, 0) ^ ref.b.get(b, 0)
    return diff


def _scratch_diff(session: Session, st: State, ref: State) -> int:
    diff = 0
    for q in set(st.q) | set(ref.q):
        if q not in session.layout.pinned:
            diff |= st.q.get(q, 0) ^ ref.q.get(q, 0)
    return diff


def _plane_diff(a: State, b: State) -> int:
    diff = 0
    for x, y in zip(a.planes(), b.planes(), strict=True):
        diff |= x ^ y
    return diff


def _tolerance_problem(
    session: Session, ops: Sequence[Op], seed: int
) -> Counterexample | None:
    """Erstes x, dessen Phasenfehler die Toleranz erreicht (nur invsqrt)."""
    rep = invsqrt_score(ops, session.layout, session.dom, seed, detail=True)
    if rep is None:
        return None
    err = np.abs(rep.diff.astype(np.float64))
    bad = np.flatnonzero(err >= rep.tol)
    if not len(bad):
        return None
    lane = int(bad[0])
    ratio = float(err[lane] / rep.tol[lane])
    return make_counterexample(
        PROP_PHASE,
        f"Phasenfehler = {ratio:.3f} x Toleranz 2^-24 * beta/sqrt(x), beta = 1",
        _lane_x(session, lane),
        session.dom.describe(lane),
        len(bad),
    )


def _phase_problem(
    session: Session, ops: Sequence[Op], st: State, ref: State, seed: int
) -> Counterexample | None:
    if session.layout.invsqrt and np is not None:
        return _tolerance_problem(session, ops, seed)
    diff = _plane_diff(st, ref)
    return (
        _at(session, PROP_PHASE, diff, "Phase weicht von der Basis ab")
        if diff
        else None
    )


def locate(
    session: Session, ops: Sequence[Op], seeds: Sequence[int]
) -> Counterexample | None:
    """Erstes Gegenbeispiel über die Messrunden `seeds` (Reihenfolge der Prüfung:
    Register, Scratch, Bedingungsstapel, Phase, Messzufall) oder None."""
    cops, first_planes = compile_ops(ops), None
    for seed in seeds:
        st = simulate(cops, session.dom, seed)
        ref = simulate(session.oracle.orig_c, session.dom, seed)
        diff = _register_diff(session, st, ref)
        if diff:
            return _at(session, PROP_REGISTER, diff, "Register nicht wie in der Basis")
        diff = _scratch_diff(session, st, ref)
        if diff:
            return _at(session, PROP_SCRATCH, diff, "Scratch-Qubit endet nicht in |0>")
        if st.stack:
            return _at(
                session, PROP_STACK, session.dom.all_lanes, "Bedingungsstapel offen"
            )
        problem = _phase_problem(session, ops, st, ref, seed)
        if problem:
            return problem
        planes = st.planes()
        if first_planes is not None and planes != first_planes:
            diff = 0
            for x, y in zip(planes, first_planes, strict=True):
                diff |= x ^ y
            return _at(session, PROP_PHASE, diff, "Phase hängt vom Messzufall ab")
        first_planes = planes
    return None


class _FixedOutcomes(dict):  # type: ignore[type-arg]
    """Wahrheitstabelle für den Simulator: jedes Messergebnis folgt `rule(Bit)` auf
    allen Lanes (statt Zufall)."""

    def __init__(self, rule: Callable[[int], bool], all_lanes: int) -> None:
        super().__init__()
        self.rule, self.all_lanes = rule, all_lanes

    def __missing__(self, key: tuple[str, int, int]) -> int:
        return self.all_lanes if self.rule(key[1]) else 0


def _fixed_domain(dom: Domain, rule: Callable[[int], bool]) -> Domain:
    table = _FixedOutcomes(rule, dom.all_lanes)
    return Domain(dom.n, dom.init_q, dom.exhaustive, dom.label, dom.describe, table)


def measurement_problem(session: Session, ops: Sequence[Op]) -> Counterexample | None:
    """Messunabhängigkeit mit festen Ergebnismustern (OUTCOME_PATTERNS): Ein korrekter
    Kandidat endet für JEDES Messergebnis mit gleichem Register, Scratch und gleicher
    Phase. Zufallsrunden treffen eine Bedingung auf k Messbits nur mit
    Wahrscheinlichkeit ~2^-k je x; die Muster fangen z. B. "alle k Bits = 1".
    Gemischte Muster bleiben gestichprobt (Endurteil: offizieller Verifier)."""
    if not any(o.name == "HMR" for o in ops):
        return None
    cops = compile_ops(ops)
    ref = simulate(cops, session.dom, "measure-ref")
    for label, rule in OUTCOME_PATTERNS:
        st = simulate(cops, _fixed_domain(session.dom, rule))
        checks = (
            ("Register", _register_diff(session, st, ref)),
            ("Scratch", _scratch_diff(session, st, ref)),
            ("Phase", _plane_diff(st, ref)),
        )
        for what, diff in checks:
            if diff:
                detail = f"{what} hängt vom Messergebnis ab ({label} vs. Zufallsrunde)"
                return _at(session, PROP_MEASUREMENT, diff, detail)
    return None
