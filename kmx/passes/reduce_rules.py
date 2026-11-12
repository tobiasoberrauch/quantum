"""Bausteine der simulationsgeführten Reduktion: direkt ablesbare
Entscheidungen, Kandidatenarten und ihre Ersatzfolgen.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import NamedTuple

from kmx.domains import LaneVector
from kmx.ops import CONDITION_STACK_OPS, META_OPS, Op, qubit_token
from kmx.passes.xor_basis import ONE, XorTerm, lin_ops
from kmx.simulator import State

# Lesezugriff auf Qubit-Werte: st.q.get (Qubit, Standardwert) -> Lane-Vektor
LaneLookup = Callable[[int, int], LaneVector]

DIRECT_DEAD, DIRECT_CX, DIRECT_SWAP, DIRECT_CZ = "dead", "cx", "swap", "cz"


class DirectDecision(NamedTuple):
    """Entscheidung von direct_decision. `kind` ist zugleich der Statistik-Schlüssel;
    `arg` ist die verbleibende Kontrolle ("cx") bzw. das Kontrollpaar ("cz")."""

    kind: str
    arg: int | tuple[int, int] | None = None


_DECIDE_DEAD = DirectDecision(DIRECT_DEAD)  # feuert auf keiner Lane
_DECIDE_SWAP = DirectDecision(DIRECT_SWAP)  # CSWAP wirkt wie SWAP


def _decide_ccx(op: Op, g: LaneLookup, mm: LaneVector) -> DirectDecision | None:
    """CCX: nie feuernd, oder eine Kontrolle impliziert die andere (-> CX)."""
    va, vb = g(op.qs[0], 0) & mm, g(op.qs[1], 0) & mm
    v = va & vb
    if v == 0:
        return _DECIDE_DEAD
    if v == va:
        return DirectDecision(DIRECT_CX, op.qs[0])
    if v == vb:
        return DirectDecision(DIRECT_CX, op.qs[1])
    return None


def _decide_first_qubit_off(
    op: Op, g: LaneLookup, mm: LaneVector
) -> DirectDecision | None:
    """CX/Z/Z_POW: wirkungslos, wenn das (Kontroll-)Qubit nie 1 ist."""
    return _DECIDE_DEAD if g(op.qs[0], 0) & mm == 0 else None


def _decide_cswap(op: Op, g: LaneLookup, mm: LaneVector) -> DirectDecision | None:
    """CSWAP: nie wirksam, oder die Kontrolle ist überall 1, wo getauscht würde."""
    d = (g(op.qs[1], 0) ^ g(op.qs[2], 0)) & mm
    dc = d & g(op.qs[0], 0)
    if dc == 0:
        return _DECIDE_DEAD
    if dc == d:
        return _DECIDE_SWAP
    return None


def _decide_swap(op: Op, g: LaneLookup, mm: LaneVector) -> DirectDecision | None:
    """SWAP zweier überall gleicher Qubits ist wirkungslos."""
    return _DECIDE_DEAD if (g(op.qs[0], 0) ^ g(op.qs[1], 0)) & mm == 0 else None


def _decide_cz(op: Op, g: LaneLookup, mm: LaneVector) -> DirectDecision | None:
    """CZ, dessen Kontrollen nie gleichzeitig 1 sind, ist wirkungslos."""
    return _DECIDE_DEAD if g(op.qs[0], 0) & g(op.qs[1], 0) & mm == 0 else None


def _decide_ccz(op: Op, g: LaneLookup, mm: LaneVector) -> DirectDecision | None:
    """CCZ: nie wirksam, oder ein Paar der Kontrollen impliziert die dritte (-> CZ)."""
    a, b, c = (g(x, 0) & mm for x in op.qs)
    p = a & b & c
    if p == 0:
        return _DECIDE_DEAD
    for i, j, pair in ((0, 1, a & b), (0, 2, a & c), (1, 2, b & c)):
        if p == pair:
            return DirectDecision(DIRECT_CZ, (op.qs[i], op.qs[j]))
    return None


# Instruktionsname -> Regel; Instruktionen ohne Regel haben keine direkte Vereinfachung
_DIRECT_RULES: dict[
    str, Callable[[Op, LaneLookup, LaneVector], DirectDecision | None]
] = {
    "CCX": _decide_ccx,
    "CX": _decide_first_qubit_off,
    "Z": _decide_first_qubit_off,
    "Z_POW": _decide_first_qubit_off,
    "CSWAP": _decide_cswap,
    "SWAP": _decide_swap,
    "CZ": _decide_cz,
    "CCZ": _decide_ccz,
}


def direct_decision(
    op: Op, st: State, m: LaneVector | None, rnd: bool
) -> DirectDecision | None:
    """Vereinfachungen, die sich direkt an den simulierten Werten ablesen lassen. `m`
    ist die Ausführungsmaske (None = alle Lanes), `rnd` sagt, ob sie vom Messzufall
    abhängt (dann gilt konservativ jede Lane als aktiv)."""
    n = op.name
    if n in CONDITION_STACK_OPS or n in META_OPS:
        return None
    if m is not None and not rnd and m == 0:
        return _DECIDE_DEAD  # Bedingung ist (deterministisch) nie erfüllt
    rule = _DIRECT_RULES.get(n)
    if rule is None:
        return None
    return rule(op, st.q.get, st.all_lanes if (m is None or rnd) else m)


def apply_direct(op: Op, dec: DirectDecision) -> list[Op]:
    """Setzt eine Entscheidung von direct_decision in die
    Ersatz-Instruktionen für `op` um."""
    kind, arg = dec
    if kind == DIRECT_DEAD:
        return []
    if kind == DIRECT_CX:
        return [Op("CX", (qubit_token(arg), qubit_token(op.qs[2])), op.cond)]
    if kind == DIRECT_SWAP:
        return [Op("SWAP", (qubit_token(op.qs[1]), qubit_token(op.qs[2])), op.cond)]
    if kind == DIRECT_CZ:
        return [Op("CZ", (qubit_token(arg[0]), qubit_token(arg[1])), op.cond)]
    raise AssertionError(kind)


# Kandidaten aus Phase A; `kind` ist zugleich der Statistik-Schlüssel. Terme sind
# Qubit-Nummern oder ONE; `members` sind die CCX der Gruppe, der letzte ist der
# Kandidat selbst.
CAND_LINEAR = "lin"
CAND_GROUP_AFFINE = "grp0"
CAND_GROUP_PRODUCT = "grp1"
GROUP_CANDIDATES = (CAND_GROUP_AFFINE, CAND_GROUP_PRODUCT)


class LinearCandidate(NamedTuple):
    """("lin", Terme): Produkt des Toffoli = XOR(Terme)."""

    kind: str
    terms: list[XorTerm]


class GroupAffineCandidate(NamedTuple):
    """("grp0", Indizes, Terme): Summe der CCX-Produkte der Gruppe = XOR(Terme)."""

    kind: str
    members: list[int]
    terms: list[XorTerm]


class GroupProductCandidate(NamedTuple):
    """("grp1", Indizes, u, wset, lset): Summe = XOR(u) * XOR(wset) ^ XOR(lset)."""

    kind: str
    members: list[int]
    u: tuple[int, ...]
    wset: list[int]
    lset: list[XorTerm]


GroupCandidate = GroupAffineCandidate | GroupProductCandidate
ReduceCandidate = LinearCandidate | GroupCandidate


def toffoli_product_lanes(op: Op, g: LaneLookup, mm: LaneVector) -> LaneVector:
    """Lane-Vektor, auf dem ein CCX/CSWAP/CCZ tatsächlich etwas bewirkt
    (eingeschränkt auf die Maske `mm`)."""
    if op.name == "CCX":
        return g(op.qs[0], 0) & g(op.qs[1], 0) & mm
    if op.name == "CSWAP":
        return (g(op.qs[1], 0) ^ g(op.qs[2], 0)) & g(op.qs[0], 0) & mm
    return g(op.qs[0], 0) & g(op.qs[1], 0) & g(op.qs[2], 0) & mm


def xor_of_terms(terms: Sequence[XorTerm], g: LaneLookup, mm: LaneVector) -> LaneVector:
    """XOR der Lane-Vektoren der Terme (ONE = Konstante 1),
    eingeschränkt auf die Maske `mm`."""
    acc = 0
    for t in terms:
        acc ^= mm if t == ONE else (g(t, 0) & mm)
    return acc


def candidate_reads(cand: GroupCandidate) -> list[int]:
    """Qubits, die der Ersatz eines Gruppenkandidaten (zusätzlich) liest."""
    if isinstance(cand, GroupAffineCandidate):
        parts: tuple[Sequence[XorTerm], ...] = (cand.terms,)
    else:
        parts = (cand.u, cand.wset, cand.lset)
    return [x for part in parts for x in part if x != ONE]


def linear_replacement(op: Op, terms: Sequence[XorTerm]) -> list[Op]:
    """Toffoli-freier Ersatz eines CCX/CSWAP/CCZ, dessen
    Produkt gleich XOR(terms) ist."""
    if op.name == "CCX":
        return lin_ops(terms, op.qs[2], op.cond)
    if op.name == "CSWAP":
        return lin_ops(terms, op.qs[1], op.cond) + lin_ops(terms, op.qs[2], op.cond)
    return [
        Op("NEG", (), op.cond) if t == ONE else Op("Z", (qubit_token(t),), op.cond)
        for t in terms
    ]


def product_group_replacement(
    u: Sequence[int], wset: Sequence[int], lset: Sequence[XorTerm], target: int
) -> list[Op]:
    """target ^= XOR(u) * XOR(wset) ^ XOR(lset) mit EINEM Toffoli: die XOR-Summen werden
    per CX in u[0] bzw. wset[0] gesammelt, nach dem CCX wieder aufgelöst; der affine
    Rest folgt als CX-Kaskade.
    """
    piv = wset[0]
    pre = [Op("CX", (qubit_token(w), qubit_token(piv))) for w in wset[1:]]
    pre += [Op("CX", (qubit_token(c), qubit_token(u[0]))) for c in u[1:]]
    toffoli = Op("CCX", (qubit_token(u[0]), qubit_token(piv), qubit_token(target)))
    return pre + [toffoli] + pre[::-1] + lin_ops(lset, target, None)
