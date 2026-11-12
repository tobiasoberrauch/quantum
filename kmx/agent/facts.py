"""Fakten am Fenstereingang (Konstanten, lineare und paarweise Relationen) und
erreichbare Zustände für `analyze_window`.
"""

from __future__ import annotations

from collections.abc import Sequence

from kmx.domains import LaneVector
from kmx.ops import Op, qubit_token
from kmx.passes.xor_basis import ONE, XorBasis
from kmx.taint import Taint

# Qubit -> Lane-Vektor (Bit i = Wert des Qubits in Trajektorie i)
LaneVectors = dict[int, LaneVector]

# AND-/Disjunktheitsfakten nur bis zu so vielen nichtkonstanten Qubits (kubisch)
WINDOW_PAIRWISE_FACT_QUBITS = 18
WINDOW_REACHABLE_CAP = 4096  # Zählung erreichbarer Zustände bricht darüber ab


def taint_before(ops: Sequence[Op], pos: int) -> Taint:
    """Statische Messabhängigkeit unmittelbar vor Instruktion `pos`."""
    taint = Taint()
    for o in ops[:pos]:
        taint.advance(o)
    return taint


def _constant_value_facts(
    qubits: Sequence[int], vec: LaneVectors, tainted: set[int], all_lanes: int
) -> list[str]:
    """Fakten über messabhängige und über konstante Qubits (0 bzw.
    1 in jeder Trajektorie)."""
    facts: list[str] = []
    for q in qubits:
        if q in tainted:
            facts.append(f"{qubit_token(q)} hängt von Messergebnissen ab")
        elif vec[q] == 0:
            facts.append(f"{qubit_token(q)} = 0 (auf allen Stichproben)")
        elif vec[q] == all_lanes:
            facts.append(f"{qubit_token(q)} = 1")
    return facts


def _linear_relation_facts(
    varying: Sequence[int], vec: LaneVectors, all_lanes: int
) -> list[str]:
    """XOR-Beziehungen: jedes Qubit, das in der GF(2)-Hülle der Konstanten 1 und der
    vorherigen Qubits liegt."""
    facts: list[str] = []
    basis = XorBasis()
    basis.add(ONE, all_lanes)
    for q in varying:
        combination = basis.solve(vec[q])
        if combination is not None:
            terms = ("1" if t == ONE else qubit_token(t) for t in combination)
            facts.append(f"{qubit_token(q)} = " + " ^ ".join(terms))
        else:
            basis.add(q, vec[q])
    return facts


def _pairwise_relation_facts(varying: Sequence[int], vec: LaneVectors) -> list[str]:
    """AND-Beziehungen qT = qA & qB und Paare, die nie gleichzeitig 1 sind."""
    facts: list[str] = []
    for t in varying:
        for i, a in enumerate(varying):
            for b in varying[i + 1 :]:
                if t not in (a, b) and vec[a] & vec[b] == vec[t]:
                    facts.append(
                        f"{qubit_token(t)} = {qubit_token(a)} & {qubit_token(b)}"
                    )
    for i, a in enumerate(varying):
        for b in varying[i + 1 :]:
            if vec[a] & vec[b] == 0:
                facts.append(
                    f"{qubit_token(a)} & {qubit_token(b)} = 0 (nie gleichzeitig 1)"
                )
    return facts


def window_entry_facts(
    qubits: Sequence[int], vec: LaneVectors, tainted: set[int], all_lanes: int
) -> list[str]:
    """Alle Fakten über die Fenster-Qubits am Eingang: Konstanten, lineare, AND- und
    Disjunktheitsbeziehungen. Beziehungen werden nur zwischen messunabhängigen,
    nichtkonstanten Qubits gesucht."""
    facts = _constant_value_facts(qubits, vec, tainted, all_lanes)
    varying = [q for q in qubits if q not in tainted and vec[q] not in (0, all_lanes)]
    facts += _linear_relation_facts(varying, vec, all_lanes)
    if len(varying) <= WINDOW_PAIRWISE_FACT_QUBITS:
        facts += _pairwise_relation_facts(varying, vec)
    return facts


def reachable_lane_groups(
    qubits: Sequence[int], vec: LaneVectors, all_lanes: LaneVector
) -> list[LaneVector]:
    """Zerlegt die Lanes in Gruppen gleicher Belegung der Fenster-Qubits (eine
    Lane-Maske je erreichbarem Zustand). Bricht ab, sobald mehr als WINDOW_REACHABLE_CAP
    Gruppen entstehen; die Liste ist dann nur eine untere Schranke.
    """
    groups = [all_lanes]
    for q in qubits:
        refined = []
        for group in groups:
            for part in (group & vec[q], group & ~vec[q]):
                if part:
                    refined.append(part)
        groups = refined
        if len(groups) > WINDOW_REACHABLE_CAP:
            break
    return groups
