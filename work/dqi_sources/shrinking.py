"""A complete 16-pivot homogeneous sweep with a six-word coefficient tail.

The sweep is an all-input permutation and is phase closed in each direction.
Its rational Schur meaning requires the documented nonzero charts; no claim
is made that this alone reconstructs the original Hermite syndromes.

The W variant emits the second continued-fraction coordinate inv0(V+Tr(U))
and keeps it during the generator update.  This removes one closed complex
inverse per forward pivot and one per inverse pivot versus retaining V.
"""
from pathlib import Path
from functools import lru_cache
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT/'exp/next/a27'), str(ROOT/'exp/next/a26'),
               str(ROOT/'exp/next/a22')]
import homogeneous_pivot as first
import homogeneous_update as h
from pivot_bridge import divide_pair, rotated_affine_conjugate, divide_zero_bridge414
from pivot_rotate import divide_pair as projective_scale
from exp.decoder.common import linear_words, mul, inv, emul, einv, eev, pmul

ar = h.ar
K = 2048
CENTERS = tuple(64 + 2*j for j in range(17))


@lru_cache(None)
def real_columns(center):
    z = einv(center | 4096)
    return tuple(emul(z, 1 << j) for j in range(12))


def expose(b, bank, real, offsets, center, reverse=False):
    """Expose the full outside row into its first supplied complex word."""
    assert len(bank) == len(offsets) and bank
    target = bank[0]
    if not reverse:
        ar.linear_inplace(b, target, first.k_columns(offsets[0]))
    for word, t in zip(bank[1:], offsets[1:]):
        ar.linear_xor(b, word, target, first.k_columns(t))
    ar.linear_xor(b, real, target, real_columns(center))
    if reverse:
        ar.linear_inplace(b, target,
                          tuple(ar.inverse_columns(first.k_columns(offsets[0]))))


def pivot(b, A, ra, B, rb, centers, reverse=False):
    """Emit U,V, retaining the old selected denominator in A[1]."""
    assert len(A) == len(B) == len(centers) and len(A) >= 2
    center = centers[0]
    offsets = [center ^ c for c in centers[1:]]
    U, Z, C, E = A[0], B[0], A[1], B[1]
    if not reverse:
        divide_pair(b, Z, U)
        expose(b, A[1:], ra, offsets, center)
        expose(b, B[1:], rb, offsets, center)
        h.mul24_xor99_zero(b, U, E, C, K)
        b.cx(U, C)
        rotated_affine_conjugate(b, U[12:], Z, C)
        expose(b, B[1:], rb, offsets, center, True)
    else:
        expose(b, B[1:], rb, offsets, center)
        rotated_affine_conjugate(b, U[12:], Z, C, True)
        b.cx(U, C)
        h.mul24_xor99_zero(b, U, E, C, K)
        expose(b, B[1:], rb, offsets, center, True)
        expose(b, A[1:], ra, offsets, center, True)
        divide_pair(b, Z, U, True)


def rebalance(b, U, W, A, B, ra, rb, offsets, center, reverse=False):
    """Generalized narrow A26 rebalance, with W supplied in its output bank."""
    assert len(A) == len(B) == len(offsets) and A
    target = A[0]

    def scalar(divide):
        delta = b.alloc_qubits(12)
        b.x(delta[0])
        ar.mul_xor0(b, U[12:], W[12:], delta)
        h.inverse_apply(b, delta,
            lambda di: h.scale(b, target[12:], delta, di, divide))
        ar.mul_xor0(b, U[12:], W[12:], delta)
        b.x(delta[0])
        b.free(delta)

    def pi(undo=False):
        if undo:
            projective_scale(b, W, target, True)
            scalar(True)
        temp = b.alloc_qubits(12)
        ar.mul_xor0(b, U[12:], target[12:], temp)
        ar.mul_xor0(b, W[:12], temp, target[:12])
        ar.erase_product(b, U[12:], target[12:], temp)
        b.free(temp)
        if not undo:
            scalar(False)
            divide_zero_bridge414(b, target, W, K)

    def affine():
        expose(b, B, rb, offsets, center)
        h.mul24_xor99_zero(b, U, B[0], target, K)
        expose(b, B, rb, offsets, center, True)
        b.cx(U, target)
        for word, t in zip(A[1:], offsets[1:]):
            ar.linear_xor(b, word, target, first.k_columns(t))
        ar.linear_xor(b, ra, target, real_columns(center))

    if not reverse:
        pi()
        affine()
        ar.linear_inplace(b, target,
                          tuple(ar.inverse_columns(first.k_columns(offsets[0]))))
    else:
        ar.linear_inplace(b, target, first.k_columns(offsets[0]))
        affine()
        pi(True)


def update_with_w(b, U, W, A, B, ra, rb, offsets, center, reverse=False):
    """Three homogeneous shears; U and W are preserved, including zeros."""
    rows = list(zip(A, B, offsets, [True] * len(A)))
    rows.append((ra, rb, center, False))
    field = ar.field(12)

    def first_shears():
        for aa, bb, t, pair in rows:
            h.source_product(b, U, bb, aa, t, pair)

    if not reverse:
        rebalance(b, U, W, A, B, ra, rb, offsets, center)
        first_shears()
    delta = b.alloc_qubits(12)
    b.x(delta[0])
    ar.mul_xor0(b, U[12:], W[12:], delta)

    def action(di):
        h.gamma_xor(b, U, W)
        h.scale(b, U[:12], delta, di, True)
        for aa, bb, t, pair in (reversed(rows) if reverse else rows):
            q = field.square(t) ^ t ^ (0 if pair else K)
            assert q
            if reverse:
                h.source_product(b, U, bb, aa, t, pair)
                if pair:
                    h.scale(b, bb[:12], delta, di, False)
                    h.scale(b, bb[12:], delta, di, False)
                else:
                    h.scale(b, bb, delta, di, False)
            h.source_product(b, W, aa, bb, t, pair, field.invert(q))
            if not reverse:
                if pair:
                    h.scale(b, bb[:12], delta, di, True)
                    h.scale(b, bb[12:], delta, di, True)
                else:
                    h.scale(b, bb, delta, di, True)
                h.source_product(b, U, bb, aa, t, pair)
        h.scale(b, U[:12], delta, di, False)
        h.gamma_xor(b, U, W)

    h.inverse_apply(b, delta, action)
    ar.mul_xor0(b, U[12:], W[12:], delta)
    b.x(delta[0])
    b.free(delta)
    if reverse:
        first_shears()
        rebalance(b, U, W, A, B, ra, rb, offsets, center, True)


def v_to_w(b, U, V, reverse=False):
    if reverse:
        h.closed_inverse(b, V)
        b.cx(U[12:], V[:12])
    else:
        b.cx(U[12:], V[:12])
        h.closed_inverse(b, V)


@lru_cache(None)
def tail_geometry(center):
    node = center | 4096
    q = [mul(center, center) ^ center ^ K, 1, 1]
    Q = pmul([0, 1], q)
    derivative = [Q[j] if j & 1 else 0 for j in range(1, len(Q))]
    powers = [1, node, emul(node, node)]
    rows = (tuple(x & 4095 for x in powers),
            tuple(x >> 12 for x in powers), (1, 0, 0))
    top = emul(powers[-1], node)
    leads = (top & 4095, top >> 12, 0)
    return rows, leads, (eev(derivative, node), eev(derivative, 0))


def tail_frame(b, A, B, center, reverse=False):
    """Coefficient tail to homogeneous tail, or its exact linear inverse."""
    rows, leads, norms = tail_geometry(center)
    def normalize(undo=False):
        for bank in (A, B):
            pair = list(bank[0]) + list(bank[1])
            k = norms[0] if undo else einv(norms[0])
            ar.linear_inplace(b, pair, tuple(emul(k, 1 << j) for j in range(24)))
            k = norms[1] if undo else inv(norms[1])
            ar.linear_inplace(b, bank[2], tuple(mul(k, 1 << j) for j in range(12)))
    if not reverse:
        linear_words(b, A, rows)
        linear_words(b, B, rows)
        for word, k in zip(B, leads):
            b.gf2_iadd(k, target=word)
        normalize()
    else:
        normalize(True)
        for word, k in zip(B, leads):
            b.gf2_iadd(k, target=word)
        linear_words(b, B, rows, True)
        linear_words(b, A, rows, True)


@lru_cache(None)
def coefficient_geometry(centers):
    n=2*len(centers)+1
    Q=[0,1]
    for c in centers:Q=pmul(Q,[mul(c,c)^c^K,1,1])
    derivative=[Q[j] if j&1 else 0 for j in range(1,len(Q))]
    rows=[];leads=[];norms=[]
    for c in centers:
        z=c|4096;p=1;values=[]
        for _ in range(n):values.append(p);p=emul(p,z)
        rows.extend((tuple(x&4095 for x in values),tuple(x>>12 for x in values)))
        leads.extend((p&4095,p>>12));norms.append(eev(derivative,z))
    rows.append(tuple([1]+[0]*(n-1)));leads.append(0);norms.append(eev(derivative,0))
    return tuple(rows),tuple(leads),tuple(norms)


def coefficient_frame(b,A,B,centers,reverse=False):
    rows,leads,norms=coefficient_geometry(tuple(centers))
    def normalize(undo=False):
        for bank in (A,B):
            for j,norm in enumerate(norms[:-1]):
                pair=list(bank[2*j])+list(bank[2*j+1])
                k=norm if undo else einv(norm)
                ar.linear_inplace(b,pair,tuple(emul(k,1<<i) for i in range(24)))
            k=norms[-1] if undo else inv(norms[-1])
            ar.linear_inplace(b,bank[-1],tuple(mul(k,1<<i) for i in range(12)))
    if not reverse:
        linear_words(b,A,rows);linear_words(b,B,rows)
        for w,k in zip(B,leads):b.gf2_iadd(k,target=w)
        normalize()
    else:
        normalize(True)
        for w,k in zip(B,leads):b.gf2_iadd(k,target=w)
        linear_words(b,B,rows,True);linear_words(b,A,rows,True)


def sweep(b, A, B, reverse=False, emitted_w=True, centers=CENTERS):
    """Monic 35/35 coefficient banks <-> 16 jets and a degree-three tail.

    For emitted_w=True each jet is (U,inv0(V+Tr(U))); for False it is
    (U,V).  The tail occupies the last three words of each bank.  No
    classical or quantum token survives a completed leg.
    """
    assert len(A) == len(B) == 35 and len(centers)==17
    ap, ra, bp, rb = first.view(A, B)
    if not reverse:
        coefficient_frame(b,A,B,centers)
    else:
        tail_frame(b, A[-3:], B[-3:], centers[-1])
    indices = reversed(range(16)) if reverse else range(16)
    for i in indices:
        suffix = centers[i:]
        offsets = [suffix[0] ^ c for c in suffix[1:]]
        U, V = ap[i], bp[i]
        if not reverse:
            pivot(b, ap[i:], ra, bp[i:], rb, suffix)
            v_to_w(b, U, V)
            update_with_w(b, U, V, ap[i+1:], bp[i+1:], ra, rb,
                          offsets, suffix[0])
            if not emitted_w:
                v_to_w(b, U, V, True)
        else:
            if not emitted_w:
                v_to_w(b, U, V)
            update_with_w(b, U, V, ap[i+1:], bp[i+1:], ra, rb,
                          offsets, suffix[0], True)
            v_to_w(b, U, V, True)
            pivot(b, ap[i:], ra, bp[i:], rb, suffix, True)
    if not reverse:
        tail_frame(b, A[-3:], B[-3:], centers[-1], True)
    else:
        coefficient_frame(b,A,B,centers,True)
