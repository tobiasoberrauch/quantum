"""Wortparalleler Simulator für das volle Instruktionsset: Kompilieren, Zustand und
`step` (heißer Pfad). Die statische Zufalls-Analyse steht in kmx.taint.
"""

from __future__ import annotations

import random
from collections.abc import Sequence

from kmx.cost import (
    COST_CLASS_NONE,
    COST_CLASS_TOFFOLI,
    PHASE_PLANES,
    SIGN_PLANE,
    zpow_info,
)
from kmx.domains import Domain, LaneVector
from kmx.ops import TOFFOLI_LIKE, Op

# Kompilierte Instruktion, siehe compile_op: (Code, q0, q1, q2, Bit, Bedingungsbit,
# Z_POW-Ebenen, Kostenklasse).
CompiledOp = tuple[
    int,
    int | None,
    int | None,
    int | None,
    int | None,
    int | None,
    tuple[int, ...] | None,
    int,
]
# Feldindizes von CompiledOp für Code außerhalb von `step` (step selbst nutzt aus
# Tempogründen die Literale).
(
    COP_CODE,
    COP_Q0,
    COP_Q1,
    COP_Q2,
    COP_BIT,
    COP_COND,
    COP_PLANES,
    COP_COST_CLASS,
) = range(8)

(
    C_X,
    C_CX,
    C_CCX,
    C_SWAP,
    C_CSWAP,
    C_Z,
    C_CZ,
    C_CCZ,
    C_NEG,
    C_ZPOW,
    C_HMR,
    C_R,
    C_B0,
    C_B1,
    C_BI,
    C_PUSH,
    C_POP,
    C_META,
) = range(18)
_CODE = {
    "X": C_X,
    "CX": C_CX,
    "CCX": C_CCX,
    "SWAP": C_SWAP,
    "CSWAP": C_CSWAP,
    "Z": C_Z,
    "CZ": C_CZ,
    "CCZ": C_CCZ,
    "NEG": C_NEG,
    "Z_POW": C_ZPOW,
    "HMR": C_HMR,
    "R": C_R,
    "BIT_STORE0": C_B0,
    "BIT_STORE1": C_B1,
    "BIT_INVERT": C_BI,
    "PUSH_CONDITION": C_PUSH,
    "POP_CONDITION": C_POP,
}
# Art eines Messergebnisses im MeasurementKey: HMR-Bit bzw. R-Qubit
DRAW_HMR, DRAW_RESET = "H", "R"


def compile_op(op: Op) -> CompiledOp:
    """Übersetzt eine Instruktion in das flache Tupel, das step interpretiert:
    (Code, q0, q1, q2, Bit, Bedingungsbit, Z_POW-Ebenen, Kostenklasse).
    Fehlende Qubits sind None.
    """
    code = _CODE.get(op.name, C_META)
    q = op.qs + (None, None, None)
    planes, cost_class = None, COST_CLASS_NONE
    if op.name in TOFFOLI_LIKE:
        cost_class = COST_CLASS_TOFFOLI
    elif op.name == "Z_POW":
        planes, cost_class = zpow_info(op.args[1])
    return (code, q[0], q[1], q[2], op.bit, op.cond, planes, cost_class)


def compile_ops(ops: Sequence[Op]) -> list[CompiledOp]:
    """Kompiliert eine Instruktionsfolge (siehe compile_op)."""
    return [compile_op(o) for o in ops]


class State:
    """Simulatorzustand: Qubits, Bits, Bedingungsstapel und Phase (128 Bit-Ebenen,
    Einheit 2^-127 Halbdrehung)."""

    __slots__ = (
        "n",
        "all_lanes",
        "q",
        "b",
        "top",
        "stack",
        "phase",
        "zpow_planes",
        "draw_counts",
        "seed",
        "truth_table",
        "count",
        "toffoli_lanes",
        "t_lanes",
        "rotation_lanes",
    )

    def __init__(self, dom: Domain, seed: int | str = 0, count: bool = False) -> None:
        self.n, self.all_lanes = dom.n, dom.all_lanes
        self.q: dict[int, LaneVector] = dict(dom.init_q)
        self.b: dict[int, LaneVector] = {}
        self.top: LaneVector | None = None  # None = alle Lanes aktiv
        self.stack: list[LaneVector | None] = []
        self.phase = 0  # Parität von Z/CZ/CCZ/NEG/HMR-Kickback
        self.zpow_planes = [0] * PHASE_PLANES  # bitgeslicter Phasenakkumulator (Z_POW)
        # Anzahl bisheriger Ziehungen je (Art, Bit bzw. Qubit)
        self.draw_counts: dict[tuple[str, int], int] = {}
        self.seed, self.truth_table, self.count = seed, dom.truth_table, count
        # ausgeführte Toffolis / T-artige / feine Rotationen, summiert über die Lanes
        self.toffoli_lanes = self.t_lanes = self.rotation_lanes = 0

    def copy(self) -> State:
        """Unabhängige Kopie (die Wahrheitstabelle wird geteilt, sie ist
        unveränderlich)."""
        s = State.__new__(State)
        s.n, s.all_lanes, s.top = self.n, self.all_lanes, self.top
        s.q, s.b = dict(self.q), dict(self.b)
        s.stack, s.phase = list(self.stack), self.phase
        s.zpow_planes, s.draw_counts = list(self.zpow_planes), dict(self.draw_counts)
        s.seed, s.truth_table, s.count = self.seed, self.truth_table, self.count
        s.toffoli_lanes, s.t_lanes = self.toffoli_lanes, self.t_lanes
        s.rotation_lanes = self.rotation_lanes
        return s

    def rand(self, tag: str, ident: int) -> LaneVector:
        """Messergebnis je Lane. Gleicher Schlüssel (Bit, wievieltes HMR) -> gleiche
        Ergebnisse, damit Original und Kandidat gekoppelt verglichen werden können."""
        k = self.draw_counts.get((tag, ident), 0)
        self.draw_counts[(tag, ident)] = k + 1
        if self.truth_table is not None:
            return self.truth_table[(tag, ident, k)]
        return random.Random(f"{self.seed}/{tag}{ident}/{k}").getrandbits(self.n)

    def planes(self) -> list[LaneVector]:
        """Gesamtphase als 128 Bit-Ebenen: Z_POW-Akkumulator, die Paritätsphase auf
        der Vorzeichen-Ebene."""
        p = list(self.zpow_planes)
        p[SIGN_PLANE] ^= self.phase
        return p


def cur_mask(st: State, cond: int | None) -> LaneVector | None:
    """Lanes, auf denen eine Instruktion mit Bedingungsbit `cond`
    jetzt wirkt (None = alle)."""
    mask = st.top
    if cond is not None:
        cond_lanes = st.b.get(cond, 0)
        mask = cond_lanes if mask is None else (mask & cond_lanes)
    return mask


def step(st: State, cop: CompiledOp) -> None:
    """Führt EINE kompilierte Instruktion auf allen Lanes zugleich aus (heißer Pfad).

    Bewusst eine einzige flache Funktion ohne Hilfsaufrufe; die Zweige stehen nach
    Häufigkeit sortiert. `mask` sind die aktiven Lanes (None = alle, das spart die
    Maskierung riesiger Ganzzahlen). Feldindizes von `cop` siehe compile_op; cop[7] ist
    die Kostenklasse (1 Toffoli, 2 T-artig, 3 Rotation).
    """
    code = cop[0]
    if code == C_META:
        return
    mask = st.top
    if code == C_PUSH:
        st.stack.append(mask)
        cond_lanes = st.b.get(cop[5], 0)
        st.top = cond_lanes if mask is None else (mask & cond_lanes)
        return
    if code == C_POP:
        if st.stack:
            st.top = st.stack.pop()
        return
    if cop[5] is not None:
        cond_lanes = st.b.get(cop[5], 0)
        mask = cond_lanes if mask is None else (mask & cond_lanes)
    q = st.q
    a = cop[1]
    if st.count and cop[7]:
        active = st.n if mask is None else mask.bit_count()
        if cop[7] == 1:
            st.toffoli_lanes += active
        elif cop[7] == 2:
            st.t_lanes += active
        elif cop[7] == 3:
            st.rotation_lanes += active
    if code == C_CX:
        v = q.get(a, 0)
        if mask is not None:
            v &= mask
        if v:
            q[cop[2]] = q.get(cop[2], 0) ^ v
    elif code == C_CCX:
        v = q.get(a, 0) & q.get(cop[2], 0)
        if mask is not None:
            v &= mask
        if v:
            q[cop[3]] = q.get(cop[3], 0) ^ v
    elif code == C_X:
        q[a] = q.get(a, 0) ^ (st.all_lanes if mask is None else mask)
    elif code == C_HMR:
        if mask is not None and mask == 0:
            # nie ausgeführt: kein Messergebnis ziehen (hält die Kopplung stabil)
            return
        outcome = st.rand(DRAW_HMR, cop[4])
        v = q.get(a, 0)
        if mask is None:
            st.phase ^= outcome & v
            st.b[cop[4]] = outcome
            if v:
                q[a] = 0
        else:
            st.phase ^= outcome & v & mask
            st.b[cop[4]] = (st.b.get(cop[4], 0) & ~mask) | (outcome & mask)
            q[a] = v & ~mask
    elif code == C_R:
        v = q.get(a, 0)
        v_active = v if mask is None else (v & mask)
        if v_active:  # Reset eines gesetzten Qubits würfelt die Phase
            st.phase ^= st.rand(DRAW_RESET, a) & v_active
            q[a] = v ^ v_active
    elif code == C_CZ:
        v = q.get(a, 0) & q.get(cop[2], 0)
        st.phase ^= v if mask is None else (v & mask)
    elif code == C_Z:
        v = q.get(a, 0)
        st.phase ^= v if mask is None else (v & mask)
    elif code == C_CCZ:
        v = q.get(a, 0) & q.get(cop[2], 0) & q.get(cop[3], 0)
        st.phase ^= v if mask is None else (v & mask)
    elif code == C_CSWAP:
        swapped = (q.get(cop[2], 0) ^ q.get(cop[3], 0)) & q.get(a, 0)
        if mask is not None:
            swapped &= mask
        if swapped:
            q[cop[2]] = q.get(cop[2], 0) ^ swapped
            q[cop[3]] = q.get(cop[3], 0) ^ swapped
    elif code == C_SWAP:
        swapped = q.get(a, 0) ^ q.get(cop[2], 0)
        if mask is not None:
            swapped &= mask
        if swapped:
            q[a] = q.get(a, 0) ^ swapped
            q[cop[2]] = q.get(cop[2], 0) ^ swapped
    elif code == C_ZPOW:
        v = q.get(a, 0)
        if mask is not None:
            v &= mask
        if v:
            # Bitgeslicte Addition: je gesetzter Ebene des Exponenten ein Übertragslauf;
            # Überlauf über Ebene 127 hinaus entfällt (Phase modulo zwei Halbdrehungen).
            zp = st.zpow_planes
            for j in cop[6]:
                carry = v
                while carry and j < 128:
                    plane = zp[j]
                    zp[j] = plane ^ carry
                    carry &= plane
                    j += 1
    elif code == C_NEG:
        st.phase ^= st.all_lanes if mask is None else mask
    elif code == C_B0:
        st.b[cop[4]] = 0 if mask is None else (st.b.get(cop[4], 0) & ~mask)
    elif code == C_B1:
        st.b[cop[4]] = st.all_lanes if mask is None else (st.b.get(cop[4], 0) | mask)
    elif code == C_BI:
        st.b[cop[4]] = st.b.get(cop[4], 0) ^ (st.all_lanes if mask is None else mask)


def simulate(
    cops: Sequence[CompiledOp], dom: Domain, seed: int | str = 0, count: bool = False
) -> State:
    """Simuliert ein kompiliertes Programm von Anfang an auf der ganzen Domäne."""
    st = State(dom, seed, count)
    for cop in cops:
        step(st, cop)
    return st


def push_depths(ops: Sequence[Op]) -> list[int]:
    """Tiefe des Bedingungsstapels VOR jeder Instruktion (überzählige
    POP_CONDITION zählen nicht)."""
    depths, depth = [], 0
    for o in ops:
        depths.append(depth)
        if o.name == "PUSH_CONDITION":
            depth += 1
        elif o.name == "POP_CONDITION" and depth:
            depth -= 1
    return depths
