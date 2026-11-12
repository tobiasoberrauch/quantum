"""Exakter invsqrt-Score, gerechnet wie der offizielle Verifier, und das Trimmen feiner
Rotationen innerhalb der Toleranz.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, TypedDict

from kmx._optional import np
from kmx.cost import (
    COST_CLASS_ROTATION,
    COST_RELATIVE_NOISE,
    PHASE_PLANES,
    ROT_T_OFFSET,
    ROT_T_PER_LOG2_INV_EPS,
    T_PER_TOFFOLI,
    VERIFIER_PHASE_BITS,
    compute_metrics,
    zpow_full,
)
from kmx.domains import Domain
from kmx.layout import Layout
from kmx.ops import Op
from kmx.simulator import (
    C_ZPOW,
    COP_CODE,
    COP_COND,
    COP_COST_CLASS,
    COP_Q0,
    State,
    compile_ops,
    cur_mask,
    step,
)

# numpy-Array (numpy ist optional, daher ohne echte Typangabe)
NDArray = Any

# Die Phase liegt im Simulator in PHASE_PLANES Bit-Ebenen vor (Einheit 2^-128
# Umdrehungen). Der offizielle Verifier vergleicht nur die oberen VERIFIER_PHASE_BITS
# Ebenen (das "Phasenwort").
_PHASE_WORD_MASK = (1 << VERIFIER_PHASE_BITS) - 1
_PHASE_WORD_SCALE = 2.0**VERIFIER_PHASE_BITS  # Phasenwort -> Umdrehungen

# Toleranz des Benchmarks: 2^-24/sqrt(x) Umdrehungen, in Phasenworten also 2^40/sqrt(x).
_TOLERANCE_NUMERATOR = 2.0**40
# Sollphase round(2^64/sqrt(x)) über die Ganzzahlwurzel von 2^130/x (ein Bit Reserve zum
# Runden).
_IDEAL_RADICAND = 1 << 130

# nur Winkel unter 2^-14 Umdrehungen (in 2^-64 Umdrehungen) kommen fürs Streichen in
# Frage
_TRIM_MAX_ANGLE = 1 << 50
TRIM_DEFAULT_MAX_RATIO = 0.95  # höchstens dieser Anteil der Toleranz wird ausgeschöpft

# (Index der Instruktion, Lanes auf denen die Rotation wirkt, unbedingt?)
RotationTrace = tuple[int, int, bool]
# (Score, Kosten C, eps, T je Rotation, schlechtestes Fehler/Toleranz-Verhältnis, dessen
# Index in der Domäne)
ScoreTerms = tuple[float, float, float, float, float, int]

_IDEAL_CACHE: dict[tuple[int, int], tuple[NDArray, NDArray]] = {}


class TrimStats(TypedDict, total=False):
    """Ergebnis von trim_rotations; ohne Streichung nur {"removed": 0}."""

    removed: int
    score_before: float
    score_after: float
    lines: list[str]


def _lane_bits(v: int, n: int) -> NDArray:
    """Zerlegt eine Lane-Ganzzahl in ein numpy-Array aus n Bits (Lane 0 zuerst)."""
    raw = np.frombuffer(v.to_bytes((n + 7) // 8, "little"), dtype=np.uint8)
    return np.unpackbits(raw, bitorder="little")[:n]


def _invsqrt_ideal(lo: int, hi: int) -> tuple[NDArray, NDArray]:
    """Sollphase 1/sqrt(x) und Toleranz 2^-24/sqrt(x), beide in
    Einheiten von 2^-64 Umdrehungen."""
    if (lo, hi) not in _IDEAL_CACHE:
        ideal = np.array(
            [
                ((math.isqrt(_IDEAL_RADICAND // x) + 1) >> 1) & _PHASE_WORD_MASK
                for x in range(lo, hi + 1)
            ],
            dtype=np.uint64,
        )
        tol = _TOLERANCE_NUMERATOR / np.sqrt(np.arange(lo, hi + 1, dtype=np.float64))
        _IDEAL_CACHE[(lo, hi)] = (ideal, tol)
    return _IDEAL_CACHE[(lo, hi)]


@dataclass
class ScoreReport:
    """Exakter Benchmark-Score eines invsqrt-Schaltkreises samt der Größen, aus
    denen er sich zusammensetzt."""

    q: int
    toffoli: float  # Mittel pro Shot
    t: float
    rot: float
    eps: float  # Syntheseschranke je Rotation: pi * min_x(tol - |Fehler|) / n_rot
    rot_t: float  # T-Gatter je feiner Rotation: 0.56*log2(1/eps) + 5.3
    cost: float  # Toffoli-Äquivalente C
    score: float  # Q x C
    worst_ratio: float  # max_x |Fehler| / Toleranz  (muss < 1 sein)
    worst_x: int
    diff: NDArray = None  # vorzeichenbehafteter Phasenfehler je x (2^-64 Umdrehungen)
    tol: NDArray = None
    rots: list[RotationTrace] | None = None

    def line(self) -> str:
        """Einzeilige Zusammenfassung für Protokoll und Audit."""
        return (
            f"Score={self.score:,.2f} = Q {self.q} x C {self.cost:.3f} "
            f"(Toffoli {self.toffoli:.2f} + T {self.t:g}/4 + {self.rot:g} Rot. x "
            f"{self.rot_t / T_PER_TOFFOLI:.3f}) | "
            f"Fehler/Toleranz max. {self.worst_ratio:.4f} bei x={self.worst_x} | "
            f"eps={self.eps:.3e}"
        )


def _score_terms(
    q: int, tof: float, t: float, nrot: float, diff: NDArray, tol: NDArray
) -> ScoreTerms:
    """Score aus Qubits, mittleren Gatterzahlen und dem Phasenfehler je x.

    Die Reserve min_x(tol - |Fehler|) wird gleichmäßig auf die Rotationen verteilt; je
    kleiner sie ist, desto genauer (teurer) muss jede Rotation synthetisiert werden.
    Ohne Reserve sind die Kosten unendlich.
    """
    err = np.abs(diff.astype(np.float64))
    ratio = err / tol
    worst_index = int(ratio.argmax())
    margin = float((tol - err).min()) / _PHASE_WORD_SCALE
    if nrot <= 0:
        eps, rot_t = float("inf"), 0.0
    elif margin <= 0:
        eps, rot_t = 0.0, float("inf")
    else:
        eps = math.pi * margin / nrot
        rot_t = ROT_T_PER_LOG2_INV_EPS * math.log2(1.0 / eps) + ROT_T_OFFSET
    cost = tof + (t + (nrot * rot_t if nrot > 0 else 0.0)) / T_PER_TOFFOLI
    return q * cost, cost, eps, rot_t, float(ratio[worst_index]), worst_index


def _simulate_tracing_fine_rotations(
    ops: Sequence[Op], dom: Domain, seed: int | str, trace: bool
) -> tuple[State, list[RotationTrace]]:
    """Zählender Simulationslauf; mit `trace` wird zu jeder feinen Z_POW-Rotation
    festgehalten, auf welchen Lanes sie wirkt (Wert des Qubits unter der aktiven
    Bedingung) und ob sie unbedingt ist.
    """
    cops = compile_ops(ops)
    st = State(dom, seed, count=True)
    rots: list[RotationTrace] = []
    for i, c in enumerate(cops):
        if trace and c[COP_CODE] == C_ZPOW and c[COP_COST_CLASS] == COST_CLASS_ROTATION:
            m = cur_mask(st, c[COP_COND])
            v = st.q.get(c[COP_Q0], 0)
            rots.append((i, v if m is None else v & m, m is None))
        step(st, c)
    return st, rots


def _phase_words(planes: Sequence[int], n: int) -> NDArray:
    """Obere 64 Phasenebenen je Lane als uint64 (Phase in 2^-64 Umdrehungen), so wie
    der Verifier sie liest."""
    theta = np.zeros(n, dtype=np.uint64)
    for j in range(PHASE_PLANES - VERIFIER_PHASE_BITS, PHASE_PLANES):
        if planes[j]:
            theta |= _lane_bits(planes[j], n).astype(np.uint64) << np.uint64(
                j - VERIFIER_PHASE_BITS
            )
    return theta


def invsqrt_score(
    ops: Sequence[Op],
    layout: Layout,
    dom: Domain,
    seed: int | str = 0,
    detail: bool = False,
) -> ScoreReport | None:
    """Rechnet den Benchmark-Score aus wie der offizielle Verifier: Phase jedes x gegen
    1/sqrt(x), Toleranz 2^-24/sqrt(x), Rotationskosten aus der verbleibenden Reserve. An
    den veröffentlichten Verifier-Zahlen zweier Schaltkreise auf 9-12 Stellen
    nachgerechnet. Braucht numpy und die vollständige invsqrt-Domäne.
    """
    if np is None or not layout.invsqrt or not dom.exhaustive:
        return None
    st, rots = _simulate_tracing_fine_rotations(ops, dom, seed, detail)
    n = dom.n
    theta = _phase_words(st.planes(), n)
    ideal, tol = _invsqrt_ideal(layout.lo, layout.hi)
    # uint64-Differenz modulo 2^64, als int64 vorzeichenrichtig
    diff = (theta - ideal).astype(np.int64)
    q = compute_metrics(ops).num_qubits
    tof, t, nrot = st.toffoli_lanes / n, st.t_lanes / n, st.rotation_lanes / n
    score, cost, eps, rot_t, worst, worst_index = _score_terms(
        q, tof, t, nrot, diff, tol
    )
    return ScoreReport(
        q,
        tof,
        t,
        nrot,
        eps,
        rot_t,
        cost,
        score,
        worst,
        layout.lo + worst_index,
        diff if detail else None,
        tol if detail else None,
        rots if detail else None,
    )


def _signed_rotation_angle(op: Op) -> int:
    """Winkel einer Z_POW-Rotation in 2^-64 Umdrehungen, vorzeichenbehaftet
    und kaufmännisch gerundet."""
    e = zpow_full(op.args[1])[2]
    signed = e - (1 << PHASE_PLANES) if e >= 1 << (PHASE_PLANES - 1) else e
    return (signed + (1 << (VERIFIER_PHASE_BITS - 1))) >> VERIFIER_PHASE_BITS


def trim_rotations(
    ops: Sequence[Op],
    layout: Layout,
    dom: Domain,
    max_ratio: float = TRIM_DEFAULT_MAX_RATIO,
) -> tuple[list[Op], TrimStats]:
    """Streicht feine Z_POW-Rotationen, deren Beitrag kleiner ist als die Phasenreserve
    - aber nur, wenn der exakt gerechnete Score dadurch sinkt (weniger Rotationen, dafür
    teurere restliche, weil die Reserve schrumpft). Das ändert die Phase innerhalb der
    offiziellen Toleranz, ist also KEINE äquivalente Umformung. Ohne exakten Score oder
    ohne passende Rotation: unveränderte Kopie und {"removed": 0}.
    """
    rep = invsqrt_score(ops, layout, dom, detail=True)
    if rep is None or not rep.rots:
        return list(ops), {"removed": 0}
    diff, tol, nrot, best, n = rep.diff, rep.tol, rep.rot, rep.score, dom.n
    removed: list[int] = []
    # Gierig, kleinste Winkel zuerst: jede Streichung zehrt an der Reserve, die allen
    # übrigen bleibt.
    for i, lanes, unconditional in sorted(
        rep.rots, key=lambda r: abs(_signed_rotation_angle(ops[r[0]]))
    ):
        angle = _signed_rotation_angle(ops[i])
        # nur unbedingte Rotationen mit winzigem Winkel
        if not unconditional or abs(angle) >= _TRIM_MAX_ANGLE:
            continue
        trial_diff = diff - np.int64(angle) * _lane_bits(lanes, n).astype(np.int64)
        trial_score, _, _, _, worst, _ = _score_terms(
            rep.q, rep.toffoli, rep.t, nrot - 1, trial_diff, tol
        )
        if worst <= max_ratio and trial_score < best * (1 - COST_RELATIVE_NOISE):
            diff, nrot, best = trial_diff, nrot - 1, trial_score
            removed.append(i)
    if not removed:
        return list(ops), {"removed": 0}
    gone = set(removed)
    return [o for i, o in enumerate(ops) if i not in gone], {
        "removed": len(removed),
        "score_before": rep.score,
        "score_after": best,
        "lines": [ops[i].fmt() for i in sorted(removed)],
    }
