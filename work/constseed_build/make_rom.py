#!/usr/bin/env python3
"""Determine the k->S mapping for the lookup-table seed.

Replicates the CURRENT circuit's exact integer arithmetic (AB=18 magnitude+subtraction
Horner, _mul_kk = (X*k)>>7, S = r0>>10) for every (interval, k) pair, and checks whether
S is a pure function of k alone or depends on the interval too. Cross-checks against the
validated model's float64 pwq3 seed.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import numpy as np
from invsqrt_constseed_model import _PWQ3_COEFS, N_P, WIDTH, MAX_X

AB = 18
SF = 8
M18 = (1 << AB) - 1

# Circuit coefficient magnitudes (same as build_constseed_circuit.py)
COEFS = []
for (a, b, c, d) in _PWQ3_COEFS:
    COEFS.append({'A': int(round(a * 2**AB)), 'B': int(round(-b * 2**AB)),
                  'C': int(round(c * 2**AB)), 'D': int(round(-d * 2**AB))})


def S_circuit(inter, k):
    """Exact circuit integer arithmetic for one (interval, k)."""
    A, B, C, D = (COEFS[inter][n] for n in 'ABCD')
    td = (D * k) >> 7
    r2 = (C - td) & M18
    tr2 = (r2 * k) >> 7
    r1 = (B - tr2) & M18
    tr1 = (r1 * k) >> 7
    r0 = (A - tr1) & M18
    return r0 >> 10


def S_model_float(inter, k):
    """Model's float64 pwq3 seed for (interval, k)."""
    a, b, c, d = _PWQ3_COEFS[inter]
    kk = k / 128.0
    seed = ((d * kk + c) * kk + b) * kk + a
    return int(seed * 2.0**SF)


def main():
    # Build the full (inter, k) -> S table via circuit arithmetic.
    tab = np.zeros((4, 128), dtype=np.int64)
    for i in range(4):
        for k in range(128):
            tab[i, k] = S_circuit(i, k)

    # Does S depend on interval? For each k, are tab[0,k]==tab[1,k]==tab[2,k]==tab[3,k]?
    same_across_inter = np.all(tab == tab[0:1, :], axis=0)
    n_diff = int((~same_across_inter).sum())
    print(f'S constant across intervals for {int(same_across_inter.sum())}/128 k; '
          f'{n_diff} k differ by interval')

    # Cross-check circuit vs model-float for all 512 pairs.
    mismatch = 0
    for i in range(4):
        for k in range(128):
            if S_circuit(i, k) != S_model_float(i, k):
                mismatch += 1
    print(f'circuit-vs-model-float mismatches: {mismatch}/512')

    # Now verify against ACTUAL x values: for each x, derive (inter, k) the way the
    # circuit does, compute S_circuit, and compare to the model's S over the domain.
    xs = np.arange(1, MAX_X + 1, dtype=np.int64)
    s, x_norm = (None, None)
    s = (WIDTH - (np.floor(np.log2(xs)).astype(np.int64) + 1)) // 2
    x_norm = xs << (2 * s)
    top = (x_norm >> (WIDTH - 1)) & 1
    second = (x_norm >> (WIDTH - 2)) & 1
    third = (x_norm >> (WIDTH - 3)) & 1
    inter = np.where(top == 0, third, 2 + second)
    # circuit k: top=0 -> x_norm[12:19]; top=1 -> x_norm[13:20]
    k_lo = (x_norm >> 12) & 127
    k_hi = (x_norm >> 13) & 127
    k = np.where(top == 0, k_lo, k_hi)

    # model S (float) over domain
    m0v = np.array([1.0, 1.5, 2.0, 3.0])[inter]
    wv = np.array([0.5, 0.5, 1.0, 1.0])[inter]
    Mv = x_norm.astype(np.float64) / 2.0**(WIDTH - 2)
    u = (Mv - m0v) / wv
    k_model = (u * 128.0).astype(np.int64)
    a = np.array([c[0] for c in _PWQ3_COEFS])[inter]
    b = np.array([c[1] for c in _PWQ3_COEFS])[inter]
    c = np.array([c[2] for c in _PWQ3_COEFS])[inter]
    d = np.array([c[3] for c in _PWQ3_COEFS])[inter]
    seed = ((d * (k_model / 128.0) + c) * (k_model / 128.0) + b) * (k_model / 128.0) + a
    S_model = (seed * 2.0**SF).astype(np.int64)

    # circuit S over domain (vectorized via table lookup)
    S_circ_dom = tab[inter, k]

    # (1) does circuit k == model k everywhere?
    k_mismatch = int((k != k_model).sum())
    print(f'circuit-k vs model-k mismatches over domain: {k_mismatch}/{len(xs)}')
    # (2) does circuit S == model S everywhere?
    S_mismatch = int((S_circ_dom != S_model).sum())
    print(f'circuit-S vs model-S mismatches over domain: {S_mismatch}/{len(xs)}')
    # (3) unique S values overall and per-key
    print(f'distinct S values (all 512 inter,k): {len(np.unique(tab))}')
    print(f'distinct S values (k-only, tab[0]): {len(np.unique(tab[0]))}')

    # Save the table(s) for the builder.
    np.save('rom_4x128.npy', tab)
    np.save('rom_128.npy', tab[0])  # placeholder if k-only
    print('saved rom_4x128.npy (4,128) and rom_128.npy (128,)')


if __name__ == '__main__':
    main()
