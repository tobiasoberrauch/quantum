"""Defer a norm-zero flag character across the multiplication peak.

The source's GF64 norm is zero exactly when the GF(2^24) source is zero.
Compute the12-bit norm first, retire its zero flag across the24-bit
product, then recreate that flag from the required6-bit subnorm. The two
flag characters combine with the old forward zero mask.  The original owner's arithmetic and all phase masks
are retained.  This is a refinement of A06's complete stage replacement.
"""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT / 'exp/round7/a06')]
import padded_fused_return as previous
from exp.arithmetic.division import zero_flag


def divide_from_norms(b, x, y, fm, before, after, owner, K=None):
    g = owner.__globals__
    ar = g['ar']
    norm = g['norm_xor_noscratch']
    to, frm, k6 = ar.tower(12)

    N = b.alloc_qubits(12)
    norm(b, y, N, K)
    F = zero_flag(b, N)
    before(F)
    b.cx(F, y[0])
    early = b.alloc_bits(1)
    b.hmr(F, early[0])
    b.free(F)
    # The original norm remains unmodified and therefore retains the exact
    # zero predicate while the safe denominator and target are multiplied.
    b.cx(y[12:], y[:12])
    oldmask = g['multiply_forward99'](b, x, y, K)
    b.cx(y[12:], y[:12])
    ar.linear_inplace(b, N, to)
    M = b.alloc_qubits(6)
    norm(b, N, M, k6)
    ar.linear_inplace(b, N, frm)
    F = zero_flag(b, M)
    b.cx(F, N[0])
    b.cx(F, M[0])
    conj = [ar.field(12).frobenius(1 << j, 6) for j in range(12)]
    ar.linear_inplace(b, N, conj)
    masks = []
    for off in (0, 12):
        half = x[off:off + 12]
        out = b.alloc_qubits(12)
        ar.mul_xor0(b, half, N, out)
        m = b.alloc_bits(12)
        b.hmr(half, m)
        b.swap(half, out)
        b.free(out)
        masks.append(m)
    ar.linear_inplace(b, N, conj)
    streamed = 'produce_retained' in g or 'norm_keep2' in g
    if 'produce_retained' in g:
        inverse_mask, kept_M = g['produce_retained'](b, M)
        t = M
    elif 'norm_keep2' in g:
        kept_M = g['norm_keep2'].keep(b, M)
        inverse_mask = g['inverse_stream_noscratch'](b, M)
        t = M
    else:
        t = g['inverse6_xor20'](b, M)
    part_masks = []
    for off in (0, 12):
        half = x[off:off + 12]
        ar.linear_inplace(b, half, to)
        for j in (0, 6):
            part = half[j:j + 6]
            out = b.alloc_qubits(6)
            g['mul_xor_noscratch'](b, part, t, out)
            if streamed:
                pm = b.alloc_bits(6)
                b.hmr(part, pm)
                part_masks.append(pm)
            else:
                ar.erase_product(b, out, M, part)
            b.swap(part, out)
            b.free(out)
        ar.linear_inplace(b, half, frm)
    if streamed:
        ar.linear_inplace(b, N, to)
        if 'produce_retained' in g:
            M = g['rebuild_retained'](b, N, kept_M, k6)
        else:
            M = g['norm_keep2'].rebuild(b, N, kept_M, k6)
        ar.linear_inplace(b, N, frm)
        b.cz(M, inverse_mask)
        b.free(inverse_mask)
        for off in (0, 12):
            half = x[off:off + 12]
            ar.linear_inplace(b, half, to)
            for j in (0, 6):
                pm = part_masks.pop(0)
                ar.phase_product(b, half[j:j + 6], M, pm)
                b.free(pm)
            ar.linear_inplace(b, half, frm)
        assert not part_masks
    for off, m in zip((0, 12), masks):
        ar.phase_product(b, x[off:off + 12], N, m)
        b.free(m)
    g['phase_product24'](b, x, y, oldmask, K)
    b.free(oldmask)

    b.cx(F, y[0])
    b.cx(F, N[0])
    b.cx(F, M[0])
    after()
    fmask = b.alloc_bits(1)
    b.hmr(F, fmask[0])
    b.free(F)
    b.cx(fm[0], fmask[0])
    b.cx(early[0], fmask[0])
    b.free(fm)
    b.free(early)
    b.z(fmask[0])
    pm = b.alloc_bits(6)
    b.bit_store(pm, False)
    b.cx(fmask[0], pm[0])
    ar.phase_product(b, M, t, pm)
    b.free(pm)
    b.free(fmask)
    tm = b.alloc_bits(6)
    b.hmr(t, tm)
    b.free(t)
    g['phase_inverse6_classical6'](b, M, tm, zero_mask=tm[0])
    b.free(tm)
    ar.linear_inplace(b, N, to)
    ar._erase_norm(b, N, M, k6)
    b.free(M)
    ar.linear_inplace(b, N, frm)
    ar._erase_norm(b, y, N, K)
    b.free(N)


def sweep(b, C, B, folds, divide):
    previous.qadic(b, C, B, k=previous.K)
    beta = b.alloc_qubits(12)
    b.x(beta[0])
    leaders = [C[-2], C[-1], beta]
    H = b.alloc_qubits(24)
    h0 = [H[:12], H[12:]]
    b.free(H)
    A = h0 + list(C[:-2])
    heads = previous.prior.rr.tail.heads_from_banks(A, B)
    frames, _, _ = previous.frames_for(A, B)
    for j, (a, d, k) in enumerate(frames):
        n = len(a)
        a1, a2, beta = leaders
        U = previous.combine(a[:2])
        W = previous.combine(d[:2])
        first, second, _ = previous.rank.bodies(b, a, d, leaders, k)
        if j:
            previous.qframe(b, a, d, leaders, frames[j-1][2], True)
            previous.qframe(b, a, d, leaders, k)
            def correct_first(F):
                target = a + [a1, a2]
                previous.controlled_linear_xor(
                    b, F, a2, target,
                    previous.prior.constant_qadic(k, n+1, len(target)))
            divide_from_norms(b, U, W, folds[2*j][1],
                              correct_first, first, divide, K=k)
        source = previous.combine(a[2:4]) if n > 3 else previous.combine([a[-1], a1])
        def correct_second(F):
            target = d + [beta]
            previous.controlled_linear_xor(
                b, F, beta, target,
                previous.prior.constant_qadic(k, n, len(target)))
        divide_from_norms(b, W, source, folds[2*j+1][1],
                          correct_second, second, divide, K=k)
    return A, heads, leaders


consume_synthesis = previous.prior.rr.clone(previous.consume_synthesis, sweep=sweep)
route_words = previous.route_words
