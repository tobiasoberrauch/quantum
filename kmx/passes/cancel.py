"""Rein syntaktische Pässe: Faltung, Auslöschung kommutierender Paare und exakte
Z/Z_POW-Phasenfusion (bit-, bedingungs- und HMR-bewusst).
"""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction

from kmx.cost import phase_exponent, phase_op
from kmx.ops import (
    BIT_OPS,
    CONDITION_STACK_OPS,
    META_OPS,
    PHASE_GATES,
    SELF_INVERSE,
    X_TYPE,
    Op,
    qubit_token,
)

# (X-Maske, Z-Maske, allgemeine Maske, gelesene Bits, geschriebene Bits, Barriere),
# siehe _deps
OpDeps = tuple[int, int, int, int, int, bool]
# so viele kommutierende Operationen sucht pass_cancel höchstens nach einem Partner ab
CANCEL_DEFAULT_DEPTH = 200


def pass_fold(ops: Sequence[Op]) -> tuple[list[Op], int]:
    """Syntaktische Aufräumarbeiten: CX-Tripel -> SWAP, leere
    PUSH/POP-Blöcke entfernen."""
    out: list[Op] = []
    folded = 0
    for o in ops:
        out.append(o)
        if o.name == "CX" and o.cond is None and len(out) >= 3:
            a, b, c = out[-3], out[-2], out[-1]
            if (
                a.name == b.name == "CX"
                and a.cond is None
                and b.cond is None
                and a.qs == c.qs
                and b.qs == (a.qs[1], a.qs[0])
            ):
                del out[-3:]
                out.append(Op("SWAP", (qubit_token(a.qs[0]), qubit_token(a.qs[1]))))
                folded += 1
        elif (
            o.name == "POP_CONDITION"
            and len(out) >= 2
            and out[-2].name == "PUSH_CONDITION"
        ):
            del out[-2:]
            folded += 1
    return out, folded


def _deps(op: Op) -> OpDeps:
    """(X-Maske, Z-Maske, allgemeine Maske, gelesene Bits,
    geschriebene Bits, Barriere)."""
    n, qs = op.name, op.qs
    x = z = g = br = bw = 0
    if op.cond is not None:
        br |= 1 << op.cond
    if n in CONDITION_STACK_OPS:
        return 0, 0, 0, br, 0, True
    if n in X_TYPE:
        x = 1 << qs[-1]
        for c in qs[:-1]:
            z |= 1 << c
    elif n in PHASE_GATES:
        for c in qs:
            z |= 1 << c
    elif n == "SWAP":
        g = (1 << qs[0]) | (1 << qs[1])
    elif n == "CSWAP":
        z, g = 1 << qs[0], (1 << qs[1]) | (1 << qs[2])
    elif n in ("HMR", "R"):
        g = 1 << qs[0]
        if n == "HMR":
            bw = 1 << op.bit
    elif n in BIT_OPS:
        bw = 1 << op.bit
    return x, z, g, br, bw, False


def _commute(a: OpDeps, b: OpDeps) -> bool:
    """Kommutieren zwei Operationen (als _deps-Tupel)? Barrieren nie; 'allgemeine'
    Qubits vertragen keinen weiteren Zugriff; X-artig gegen Z-artig nur auf
    verschiedenen Qubits; Bit-Schreiber blockieren Leser/Schreiber.
    """
    if a[5] or b[5]:
        return False
    if a[2] & (b[0] | b[1] | b[2]) or b[2] & (a[0] | a[1] | a[2]):
        return False
    if a[0] & b[1] or a[1] & b[0]:
        return False
    return not (a[4] & (b[3] | b[4]) or b[4] & a[3])


def _find_partner(
    op: Op,
    exp: Fraction | None,
    op_deps: OpDeps,
    kept: Sequence[Op],
    deps: Sequence[OpDeps | None],
    depth: int,
) -> int:
    """Rückwärtssuche nach dem Partner von `op` in `kept`: dasselbe selbstinverse Gatter
    bzw. (bei einem Phasengatter mit Exponent `exp`) ein Phasengatter auf denselben
    Qubits mit derselben Bedingung. Dazwischen darf nur Kommutierendes liegen, höchstens
    `depth` Operationen; Meta-Instruktionen zählen nicht. -1 = kein Partner.
    """
    key, seen = op.key(), 0
    for j in range(len(kept) - 1, -1, -1):
        other_deps = deps[j]
        if other_deps is None:
            continue
        o = kept[j]
        if exp is not None:
            if o.qs == op.qs and o.cond == op.cond and phase_exponent(o) is not None:
                return j
        elif o.name == op.name and o.key() == key:
            return j
        seen += 1
        if seen > depth or not _commute(op_deps, other_deps):
            return -1
    return -1


def pass_cancel(
    ops: Sequence[Op], depth: int = CANCEL_DEFAULT_DEPTH
) -> tuple[list[Op], int, int]:
    """Löscht Paare identischer selbstinverser Gatter und fasst Z/Z_POW auf demselben
    Qubit (gleiche Bedingung) exakt zusammen, wenn dazwischen nur kommutierende
    Operationen liegen. Gleiches Ziel kommutiert (CX a t / CCX b c t); Messungen und
    Bit-Schreiber blockieren ihre Leser. Rückgabe: (Ops, gelöschte Paare,
    zusammengefasste Phasengatter)."""
    kept: list[Op] = []
    # parallel zu kept; None = Meta-Instruktion (wird übersprungen)
    deps: list[OpDeps | None] = []
    cancelled = merged = 0
    for op in ops:
        if op.name in META_OPS:
            kept.append(op)
            deps.append(None)
            continue
        op_deps = _deps(op)
        exp = phase_exponent(op)
        hit = -1
        if exp is not None or op.name in SELF_INVERSE:
            hit = _find_partner(op, exp, op_deps, kept, deps, depth)
        if hit < 0:
            kept.append(op)
            deps.append(op_deps)
        elif exp is None:
            del kept[hit], deps[hit]
            cancelled += 1
        else:
            both = phase_op(op.qs[0], exp + phase_exponent(kept[hit]), op.cond)
            if both is None:
                del kept[hit], deps[hit]
            else:
                kept[hit], deps[hit] = both, _deps(both)
            merged += 1
    return kept, cancelled, merged
