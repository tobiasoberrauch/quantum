"""Exact linear matroid parity by the algebraic method (Lovasz; Cheung-Lau-Leung style extraction) over GF(2^16).

Each candidate is a pair of bit vectors (u, v) in F2^D; rank(sum x_i (u v^T + v u^T)) = 2*nu for random x_i.
"""
from __future__ import annotations

import numpy as np

PRIM = 0x1100B
EXP = np.zeros(2 * 65535, dtype=np.int64)
LOG = np.zeros(65536, dtype=np.int64)
_x = 1
for _i in range(65535):
    EXP[_i] = _x
    LOG[_x] = _i
    _x <<= 1
    if _x & 0x10000:
        _x ^= PRIM
EXP[65535:2 * 65535] = EXP[:65535]


def mul(a, b):
    a = np.asarray(a, dtype=np.int64)
    b = np.asarray(b, dtype=np.int64)
    out = EXP[LOG[a] + LOG[b]]
    return np.where((a == 0) | (b == 0), 0, out)


def inv(a):
    return int(EXP[65535 - LOG[a]]) if a else 0


def build(cands_uv, D, rng):
    A = np.zeros((D, D), dtype=np.int64)
    xs = rng.integers(1, 65536, size=len(cands_uv))
    for x, (u, v) in zip(xs, cands_uv):
        # u, v: boolean arrays
        iu = np.flatnonzero(u)
        iv = np.flatnonzero(v)
        A[np.ix_(iu, iv)] ^= int(x)
        A[np.ix_(iv, iu)] ^= int(x)
    np.fill_diagonal(A, 0)  # char 2 alternating form: x(u_i v_i + v_i u_i) = 0 on the diagonal
    return A, xs


def rank_and_inverse(A, want_inverse=True):
    n = A.shape[0]
    M = np.concatenate([A.copy(), np.eye(n, dtype=np.int64)], axis=1) if want_inverse else A.copy()
    r = 0
    piv_cols = []
    for c in range(n):
        nz = np.flatnonzero(M[r:, c])
        if len(nz) == 0:
            continue
        p = r + nz[0]
        if p != r:
            M[[r, p]] = M[[p, r]]
        M[r] = mul(M[r], inv(int(M[r, c])))
        col = M[:, c].copy()
        col[r] = 0
        idx = np.flatnonzero(col)
        if len(idx):
            M[idx] ^= mul(col[idx][:, None], M[r][None, :])
        piv_cols.append(c)
        r += 1
        if r == n:
            break
    return r, (M[:, n:] if (want_inverse and r == n) else None)


def extract(cands_uv, xs, Y, order, log=None):
    """Delete candidates keeping invertibility; returns surviving indices (a perfect parity basis)."""
    n = Y.shape[0]
    keep = np.ones(len(cands_uv), dtype=bool)
    for cnt, i in enumerate(order):
        u, v = cands_uv[i]
        iu, iv = np.flatnonzero(u), np.flatnonzero(v)
        x = int(xs[i])
        Yu = np.bitwise_xor.reduce(Y[:, iu], axis=1)
        Yv = np.bitwise_xor.reduce(Y[:, iv], axis=1)
        uYv = int(np.bitwise_xor.reduce(Yv[iu]))
        d = 1 ^ int(mul(x, uYv))
        if d == 0:
            continue  # essential
        keep[i] = False
        # Woodbury for A' = A + x(u v^T + v u^T); Y symmetric alternating in char 2
        c = int(mul(x, inv(d)))
        # Y' = Y + c (Yu Yv^T + Yv Yu^T)
        Y ^= mul(c, mul(Yu[:, None], Yv[None, :]) ^ mul(Yv[:, None], Yu[None, :]))
    return np.flatnonzero(keep)
