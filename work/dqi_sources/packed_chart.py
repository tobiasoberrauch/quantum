"""Exact low-width source-coordinate components, not a whole decoder.

All helpers allocate no qubits. Caller-provided dirty wires, where needed,
are returned pointwise. No helper measures or applies a phase.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'exp/new/a16'), str(ROOT / 'exp/new/a10'),
               str(ROOT / 'exp/new/a07')]
from lowclean_norm5 import permutation3, ar
import logscale7

_f3 = ar.field(3)
_K = ar.tower(6)[2]
_logs = {_f3.pow(2, j): j for j in range(7)}
_logq = tuple(_logs[_f3.square(r) ^ r ^ _K] for r in range(8))
# Multiplication by4 modulo7 is a free rotation of a three-bit residue.
PHI_TABLE = tuple(((v << 2) & 7) | (v >> 1) for v in _logq)
PHI_CONSTANT = PHI_TABLE[0]
PHI_COLUMNS = tuple(PHI_TABLE[1 << j] ^ PHI_CONSTANT for j in range(3))
assert all(PHI_TABLE[r] == PHI_CONSTANT ^ ar.apply(PHI_COLUMNS, r) for r in range(8))


def negate_mod7(b, target):
    """Negate residues0..6 and fix code7, in one local Toffoli."""
    b.x(target)
    # Exchange codes0 and7 after complementation.
    b.cx(target[0], target[1]); b.cx(target[0], target[2])
    b.x(target[1:])
    b.ccx(target[1], target[2], target[0])
    b.x(target[1:])
    b.cx(target[0], target[2]); b.cx(target[0], target[1])


def add_norm_residue(b, target, ratio, inverse=False):
    """Add4log(r²+r+K) modulo7 without allocating that affine key."""
    permutation3(b, target, 'log', True)
    gates = tuple(zip(logscale7.GATES, logscale7.COMPILED))
    for (c, _, _), (_, cols, back) in reversed(gates) if inverse else gates:
        constant = (c & PHI_CONSTANT).bit_count() & 1
        mask = sum(((c & col).bit_count() & 1) << j for j, col in enumerate(PHI_COLUMNS))
        bits = [j for j in range(3) if mask >> j & 1]
        if bits:
            control = ratio[bits[0]]
            for j in bits[1:]: b.cx(ratio[j], control)
            if constant: b.x(control)
            ar.linear_inplace(b, target, cols)
            b.ccx(control, target[0], target[1])
            ar.linear_inplace(b, target, back)
            if constant: b.x(control)
            for j in reversed(bits[1:]): b.cx(ratio[j], control)
        elif constant:
            ar.linear_inplace(b, target, cols)
            b.cx(target[0], target[1])
            ar.linear_inplace(b, target, back)
    permutation3(b, target, 'log')


def residue_chart6(b, source, reverse=False):
    """Full six-bit permutation: regular (ratio,e mod7), pure (raw low,7).

    Generator2 of the supplied GF64 field has norm7, whose GF8 log is5.
    Thus e mod7 = -(log(high)+4log(r²+r+K)) mod7. Code7 stays fixed.
    The complete preparation costs21 local Toffolis with no ancilla.
    It is not the final six-bit binary log and cannot yet replace apply.
    """
    ratio, key = source[:3], source[3:]
    if not reverse:
        ratio_chart6(b, source)
        add_norm_residue(b, key, ratio)
        negate_mod7(b, key)
    else:
        negate_mod7(b, key)
        add_norm_residue(b, key, ratio, True)
        ratio_chart6(b, source, True)


def ratio_chart6(b, source, reverse=False):
    """(a,b) -> (a/(b+[b=0]), log(b)), zero-log code7.

    The source uses the supplied GF64 polynomial basis on entry/exit and
    the GF8 tower coordinates between the two directions. This is a full
    six-bit permutation: no nonzero promise or chart flag is required.
    """
    assert len(source) == 6
    to, back, _ = ar.tower(6)
    ratio, key = source[:3], source[3:]
    if not reverse:
        ar.linear_inplace(b, source, to)
        permutation3(b, key, 'log')
        logscale7.scale(b, ratio, key, True)
    else:
        logscale7.scale(b, ratio, key)
        permutation3(b, key, 'log', True)
        ar.linear_inplace(b, source, back)


def dirty_mcx(b, controls, target, dirty):
    """XOR the product of n>=3 controls using n-2 borrowed dirty wires.

    Four n minus eight Toffolis. Both ladder passes return every borrowed
    bit. The difference between their target contributions is the desired
    complete control product, independently of every dirty input bit.
    """
    n = len(controls)
    assert n >= 3 and len(dirty) >= n-2
    def suffix():
        for j in range(1, n-2):
            b.ccx(controls[j+1], dirty[j-1], dirty[j])
    def unsuffix():
        for j in reversed(range(1, n-2)):
            b.ccx(controls[j+1], dirty[j-1], dirty[j])
    suffix()
    b.ccx(controls[-1], dirty[n-3], target)
    unsuffix()
    b.ccx(controls[0], controls[1], dirty[0])
    suffix()
    b.ccx(controls[-1], dirty[n-3], target)
    unsuffix()
    b.ccx(controls[0], controls[1], dirty[0])


def pack_nonzero(b, ratio, coefficient, flag, reverse=False):
    """Pack p in0..8 and b in0..6 from (p.low3,b,p.high) into six bits.

    p<8 -> (p,b); p=8 -> (b,7). The flag clears on all63 allowed inputs.
    This seven-Toffoli component alone does not complete a zero source.
    """
    assert len(ratio) == len(coefficient) == 3
    def predicate(reverse=False):
        gates = ((coefficient[0], coefficient[1], ratio[0]),
                 (ratio[0], coefficient[2], flag),
                 (coefficient[0], coefficient[1], ratio[0]),
                 (ratio[0], coefficient[2], flag))
        for args in reversed(gates) if reverse else gates:
            b.ccx(*args)
    if not reverse:
        b.cswap(flag, ratio, coefficient)
        for wire in coefficient:
            b.cx(flag, wire)
        predicate()
    else:
        predicate(True)
        for wire in coefficient:
            b.cx(flag, wire)
        b.cswap(flag, ratio, coefficient)


def swap_zero_corner(b, ratio, coefficient, flag, dirty):
    """Swap the two post-pack states (r0,g7,F1) and (r7,g7,F0).

    Four borrowed wires permit a16-Toffoli six-controlled transposition.
    The affine basis change maps their difference to the flag direction.
    """
    for wire in ratio:
        b.cx(flag, wire)
    dirty_mcx(b, [*ratio, *coefficient], flag, dirty)
    for wire in ratio:
        b.cx(flag, wire)


def pack_complete(b, ratio, coefficient, flag, dirty, reverse=False):
    """The63 nonzero states plus (p0,b7) -> all64 six-bit codes, flag0.

    The extra input is the conventional zero source. Its output is code63.
    This costs23 local Toffolis and borrows four dirty wires, with no new
    clean qubit. The physical chart flag is still an input to this helper.
    """
    if not reverse:
        pack_nonzero(b, ratio, coefficient, flag)
        swap_zero_corner(b, ratio, coefficient, flag, dirty)
    else:
        swap_zero_corner(b, ratio, coefficient, flag, dirty)
        pack_nonzero(b, ratio, coefficient, flag, True)
