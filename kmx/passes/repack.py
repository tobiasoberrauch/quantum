"""Scratch-Qubits: Zugriffe, Lebensdauern und Qubit-Repacking per Intervallfärbung."""

from __future__ import annotations

import heapq
from collections import defaultdict
from collections.abc import Sequence
from typing import TypedDict

from kmx.cost import compute_metrics
from kmx.domains import Domain
from kmx.layout import Layout
from kmx.ops import META_OPS, PHASE_GATES, X_TYPE, Op
from kmx.simulator import State, compile_ops, step
from kmx.taint import Taint

# (Op-Index, Rolle, 'danach auf allen Lanes |0>')
ScratchTouch = tuple[int, str, bool]
# Scratch-Qubit -> Zugriffe in Programmreihenfolge
ScratchTouches = dict[int, list[ScratchTouch]]
# (Start, Ende, Qubit, Indizes der Zugriffe)
ScratchLifetime = tuple[int, int, int, list[int]]
ROLE_X_TARGET, ROLE_CONTROL, ROLE_GENERAL = "xt", "c", "g"
_WIRE_INDEX_LIMIT = 10**9  # obere Schranke für die Suche nach freien Drähten
# Startwert der Simulation in trace_touches (Messergebnisse)
TRACE_SEED = "T"


class RepackStats(TypedDict):
    """Statistik von pass_repack (Reihenfolge der Schlüssel = Ausgabe im Audit)."""

    q_before: int
    q_after: int
    peak_scratch: int
    lifetimes: int
    dropped_idle_R: int


def trace_touches(
    ops: Sequence[Op], layout: Layout, dom: Domain, seed: int | str = TRACE_SEED
) -> ScratchTouches:
    """Für jedes Scratch-Qubit: (Index, Rolle, 'danach auf allen Lanes |0>'). Rollen:
    'xt' = Ziel eines X/CX/CCX, 'c' = nur gelesen, 'g' = sonstiges (SWAP, HMR, R).
    """
    cops = compile_ops(ops)
    st, taint = State(dom, seed), Taint()
    touches: ScratchTouches = defaultdict(list)
    for i, op in enumerate(ops):
        step(st, cops[i])
        taint.advance(op)
        n = op.name
        if not op.qs or n in META_OPS:
            continue
        for k, q in enumerate(op.qs):
            if q in layout.pinned:
                continue
            if n in X_TYPE:
                role = ROLE_X_TARGET if k == len(op.qs) - 1 else ROLE_CONTROL
            elif n in PHASE_GATES or (n == "CSWAP" and k == 0):
                role = ROLE_CONTROL
            else:
                role = ROLE_GENERAL
            zero = st.q.get(q, 0) == 0 and q not in taint.random_qubits
            touches[q].append((i, role, zero))
    return touches


def lifetimes_of(
    ops: Sequence[Op], touches: ScratchTouches
) -> tuple[list[ScratchLifetime], set[int]]:
    """Lebensdauern (Start, Ende, Qubit, Indizes) aller Scratch-Qubits und
    überflüssige R-Instruktionen.

    Eine Lebensdauer endet, sobald das Qubit nach echter Benutzung auf allen Lanes |0>
    ist. Ein R auf ein ohnehin leeres Qubit ('idle') ist überflüssig, solange darauf nur
    weitere solche R oder nichts mehr folgt.
    """
    lifetimes: list[ScratchLifetime] = []
    drop: set[int] = set()
    for q, qubit_touches in touches.items():
        idxs: list[int] = []  # Zugriffe der offenen Lebensdauer; leer = keine offen
        used = False  # enthält die offene Lebensdauer mehr als ein einzelnes Idle-R?
        for i, _, zero in qubit_touches:
            idle_r = ops[i].name == "R" and zero
            if not idxs:
                idxs, used = [i], not idle_r
            elif not used and idle_r:
                drop.update(idxs)
                idxs = [i]
            else:
                idxs.append(i)
                used = True
            if used and zero:
                lifetimes.append((idxs[0], i, q, idxs))
                idxs = []
        if idxs:
            if used:
                lifetimes.append((idxs[0], len(ops), q, idxs))
            else:
                drop.update(idxs)
    lifetimes.sort()
    return lifetimes, drop


def scratch_peak(lifetimes: Sequence[ScratchLifetime]) -> tuple[int, int]:
    """(größte Zahl gleichzeitig lebender Scratch-Qubits, erster Op-Index, an dem sie
    erreicht wird) per Sweep über Start- und Endereignisse der Lebensdauern. Bei
    gleichem Index sortiert das Ende (-1) vor dem Start (+1): ein frei gewordenes Qubit
    zählt nicht doppelt.
    """
    events = sorted(
        [(start, 1) for start, _, _, _ in lifetimes]
        + [(end + 1, -1) for _, end, _, _ in lifetimes]
    )
    live = peak = peak_index = 0
    for index, delta in events:
        live += delta
        if live > peak:
            peak, peak_index = live, index
    return peak, peak_index


def _assign_wires(
    lifetimes: Sequence[ScratchLifetime], pinned: set[int]
) -> tuple[dict[int, dict[int, int]], int]:
    """Intervallfärbung der (nach Start sortierten) Lebensdauern auf die kleinsten nicht
    gepinnten Drähte. Rückgabe: (Op-Index -> {altes Qubit: Draht}, höchste Zahl
    gleichzeitig belegter Drähte).
    """
    unused_wires = (w for w in range(_WIRE_INDEX_LIMIT) if w not in pinned)
    free: list[int] = []  # Heap wieder freigegebener Drähte
    active: list[tuple[int, int]] = []  # Heap (Ende, Draht) der laufenden Lebensdauern
    rename: dict[int, dict[int, int]] = defaultdict(dict)
    peak = 0
    for start, end, q, idxs in lifetimes:
        while active and active[0][0] < start:
            heapq.heappush(free, heapq.heappop(active)[1])
        wire = heapq.heappop(free) if free else next(unused_wires)
        heapq.heappush(active, (end, wire))
        peak = max(peak, len(active))
        for i in idxs:
            rename[i][q] = wire
    return rename, peak


def pass_repack(
    ops: Sequence[Op], layout: Layout, dom: Domain
) -> tuple[list[Op], RepackStats]:
    """Qubit-Repacking. Ein Draht ist frei, sobald das Qubit auf der ganzen Domäne |0>
    ist - egal ob durch HMR, R oder reversibles Uncompute. Die Lebensdauern werden per
    Intervallfärbung auf möglichst wenige Drähte mit den kleinsten Indizes gelegt
    (optimal bei fester Gatterreihenfolge). Q im Score ist max. Index + 1.
    """
    touches = trace_touches(ops, layout, dom)
    lifetimes, drop = lifetimes_of(ops, touches)
    old_q = compute_metrics(ops).num_qubits
    rename, peak = _assign_wires(lifetimes, layout.pinned)
    out = [
        op.renamed(rename[i]) if i in rename else op
        for i, op in enumerate(ops)
        if i not in drop
    ]
    new_q = compute_metrics(out).num_qubits
    stats: RepackStats = {
        "q_before": old_q,
        "q_after": new_q,
        "peak_scratch": peak,
        "lifetimes": len(lifetimes),
        "dropped_idle_R": len(drop),
    }
    if new_q >= old_q:
        return list(ops), stats
    return out, stats
