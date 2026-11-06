"""Direct Forney phase, replacing conversion, scan and reverse conversion.

The coefficient banks are restored exactly.  At each point beta this phases
    [B(beta)=0] dot(M_beta, A(beta)/(beta P(beta) B'(beta))),
with inv0 for a vanishing derivative.  All measurements are X measurements
of values still recoverable from retained sources; their signs close locally.
"""
from functools import lru_cache
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'playbook/kit'), str(ROOT/'playbook/kit/decoder')]
from exp.decoder.common import ar, gf, mul, inv, power, scale, zero_hold, zero_free
from exp.jet24.kernel import phase_inverse12_quantum64


def classical_zero(b, n):
    out = b.alloc_bits(n)
    b.bit_store(out, False)
    return out


def classical_product(b, x, y):
    """Pure classical field product, using only legal bit operations."""
    n = len(x)
    assert len(y) == n
    out = classical_zero(b, n)
    left, right = classical_zero(b, 2)
    for mask, value in ar.tensor(n):
        ids = tuple(ar.bits(mask))
        for i in ids:
            b.cx(x[i], left)
            b.cx(y[i], right)
        # CCX has a quantum target in the builder.  This classical AND is
        # instead a classical condition around classical CNOTs.
        b.push_condition(left)
        for i in ar.bits(value):
            b.cx(right, out[i])
        b.pop_condition()
        for i in reversed(ids):
            b.cx(y[i], right)
            b.cx(x[i], left)
    b.free([left, right])
    return out


@lru_cache(None)
def frobenius_columns(exponent):
    return tuple(power(1 << i, exponent) for i in range(12))


def classical_frobenius(b, x, exponent):
    out = classical_zero(b, 12)
    ar.linear_xor(b, x, out, frobenius_columns(exponent))
    return out


@lru_cache(None)
def inverse3_anf():
    f = ar.field(3)
    values = [f.invert(x) if x else 0 for x in range(8)]
    for bit in range(3):
        for mask in range(8):
            if mask & (1 << bit):
                values[mask] ^= values[mask ^ (1 << bit)]
    assert values[0] == values[7] == 0
    return tuple(values)


def classical_inverse(b, x):
    """inv0(x), wholly classical, in a 12/6/3 quadratic tower.

    The 66 Boolean products are classical controls around classical CNOTs;
    they allocate no qubit and perform no measurement.
    """
    n = len(x)
    if n == 3:
        out = classical_zero(b, 3)
        for mask, value in enumerate(inverse3_anf()):
            ids = tuple(ar.bits(mask))
            if not value:
                continue
            if len(ids) == 1:
                for j in ar.bits(value):
                    b.cx(x[ids[0]], out[j])
            else:
                assert len(ids) == 2
                b.push_condition(x[ids[0]])
                for j in ar.bits(value):
                    b.cx(x[ids[1]], out[j])
                b.pop_condition()
        return out
    assert n in (6, 12)
    k = n // 2
    to, frm, K = ar.tower(n)
    coordinates = classical_zero(b, n)
    ar.linear_xor(b, x, coordinates, to)
    low, high = coordinates[:k], coordinates[k:]
    norm = classical_zero(b, k)
    squares = ar.square_columns(k)
    ar.linear_xor(b, low, norm, squares)
    subfield = ar.field(k)
    ar.linear_xor(b, high, norm, [subfield.mul(K, v) for v in squares])
    product = classical_product(b, low, high)
    b.cx(product, norm)
    b.free(product)
    reciprocal = classical_inverse(b, norm)
    b.free(norm)
    summed = classical_zero(b, k)
    b.cx(low, summed)
    b.cx(high, summed)
    outlow = classical_product(b, summed, reciprocal)
    outhigh = classical_product(b, high, reciprocal)
    out = classical_zero(b, n)
    ar.linear_xor(b, list(outlow) + list(outhigh), out, frm)
    for reg in (outlow, outhigh, summed, reciprocal, coordinates):
        b.free(reg)
    return out


@lru_cache(None)
def trace_columns():
    def trace(x):
        out = 0
        for _ in range(12):
            out ^= x
            x = mul(x, x)
        assert out in (0, 1)
        return out
    return tuple(sum(trace(mul(1 << i, 1 << j)) << j for j in range(12))
                 for i in range(12))


def scale_public(b, x, factor, inverse):
    """x <- factor*x with factor classical and nonzero on active shots.

    Both field products have a classical source and cost no Toffolis.
    Measuring old x gives m.old_x, repaid by m.(inverse*new_x).
    """
    out = b.alloc_qubits(12)
    ar.mul_xor(b, x, factor, out)
    mask = b.alloc_bits(12)
    b.hmr(x, mask)
    ar.phase_product(b, inverse, out, mask)
    b.swap(x, out)
    b.free(out)
    b.free(mask)


def root_character(b, numerator, derivative, root_value, mask):
    """Closed phase [root_value=0] dot(mask,numerator*inv0(derivative)).

    The public nonzero mask supplies an invertible change of numerator
    coordinates.  Its zero case is skipped using a classical condition.
    This avoids retaining a separate transposed-mask bank.
    """
    active = classical_zero(b, 1)[0]
    for bit in mask:
        b.bit_store(active, True, control=bit)
    dual = classical_zero(b, 12)
    trace = trace_columns()
    trace_inverse = ar.inverse_columns(trace)
    ar.linear_xor(b, mask, dual, trace_inverse)
    dual_inverse = classical_inverse(b, dual)
    b.push_condition(active)
    scale_public(b, numerator, dual, dual_inverse)
    ar.linear_inplace(b, numerator, trace)
    ladder = zero_hold(b, root_value)
    masked = b.alloc_qubits(12)
    for u, v in zip(numerator, masked):
        b.init_and(ladder[-1], u, v)
    phase_inverse12_quantum64(b, derivative, masked)
    for u, v in reversed(list(zip(numerator, masked))):
        b.del_and(ladder[-1], u, v)
    b.free(masked)
    zero_free(b, root_value, ladder)
    ar.linear_inplace(b, numerator, trace_inverse)
    scale_public(b, numerator, dual_inverse, dual)
    b.pop_condition()
    b.free(dual_inverse)
    b.free(dual)
    b.free(active)


def scan(b, A, B, E, *, points=4095, skip_points=(), node_polynomial=None):
    """Forney scan in the existing coefficient banks; no conversion token."""
    from exp.decoder.extract import constants
    if len(A) != 35 or len(B) != 35 or len(E) < points:
        raise ValueError('need 35+35 words and one mask per point')
    if points != 4095:
        raise ValueError('full cycle needed for coefficient restoration')
    P = constants()[2] if node_polynomial is None else node_polynomial
    skip_points = frozenset(skip_points)
    assert all(0 <= j < points for j in skip_points)
    alpha = gf.primitive_element
    powers = tuple(power(alpha, k) for k in range(35))
    beta = lead = 1
    leadstep = power(alpha, 35)
    mask = classical_zero(b, 12)
    for j in range(points):
        if j not in skip_points:
            # Expose values first, then beta*B'(beta) in the independent
            # odd-coefficient pivot B[1].  This order preserves B(beta).
            for k in range(1, 35):
                b.cx(A[k], A[0])
                b.cx(B[k], B[0])
            b.gf2_iadd(lead, target=B[0])
            for k in range(3, 35, 2):
                b.cx(B[k], B[1])
            b.gf2_iadd(lead, target=B[1])
            pv = 0
            for coefficient in reversed(P):
                pv = mul(pv, beta) ^ coefficient
            c = inv(pv)
            assert c
            b.bit_store(mask, False)
            for t in range(12):
                for i in ar.bits(mul(c, 1 << t)):
                    b.cx(E[j][i], mask[t])
            root_character(b, A[0], B[1], B[0], mask)
            b.gf2_iadd(lead, target=B[1])
            for k in reversed(range(3, 35, 2)):
                b.cx(B[k], B[1])
            b.gf2_iadd(lead, target=B[0])
            for k in reversed(range(1, 35)):
                b.cx(B[k], B[0])
                b.cx(A[k], A[0])
        for k in range(1, 35):
            scale(b, A[k], powers[k])
            scale(b, B[k], powers[k])
        beta = mul(beta, alpha)
        lead = mul(lead, leadstep)
    assert beta == lead == 1
    b.free(mask)
