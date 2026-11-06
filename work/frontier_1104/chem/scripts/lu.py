"""LSB-product sharing: extend a kept LSB product by upper outputs x so that both its planes lose one row rank.

A product (a1,b1),(a2,b2) with output s contributes a1 b1 x + a2 b2 x when s gets the extra outputs x. In plane(b1) pick a
y-functional l1 with l1.rows = b1 (x) and l1.a1 = 1, likewise in plane(b2); then the corrected rows lose rank in both planes.
"""
from __future__ import annotations

import random

import numpy as np

import planner as P


def b_to_plane(b, Inv):
    """b int over 15 bits -> (t, b3) if b lies in one plane, else None."""
    v = np.array([(b >> j) & 1 for j in range(15)], dtype=np.uint8)
    c = (v @ Inv) % 2
    ts = {i // 3 for i in np.flatnonzero(c)}
    if len(ts) != 1:
        return None
    t = ts.pop()
    return t, sum(int(c[3 * t + i]) << i for i in range(3))


def lb_maps(rows, b3, O):
    """Basis of (l, x) with sum_y l_y rows_y = b3 tensor x. l over bits of rows index."""
    mask = (1 << O) - 1
    n = len(rows)
    eq = []  # each equation: bitmask over y
    idx1 = [i for i in range(3) if (b3 >> i) & 1]
    idx0 = [i for i in range(3) if not (b3 >> i) & 1]
    for o in range(O):
        for i in idx0:
            e = 0
            for y, r in enumerate(rows):
                if (r >> (i * O + o)) & 1:
                    e |= 1 << y
            eq.append(e)
        for i in idx1[1:]:
            e = 0
            for y, r in enumerate(rows):
                if ((r >> (i * O + o)) ^ (r >> (idx1[0] * O + o))) & 1:
                    e |= 1 << y
            eq.append(e)
    sols = P.nullspace(eq, n)
    out = []
    for l in sols:
        v = 0
        for y in range(n):
            if (l >> y) & 1:
                v ^= rows[y]
        out.append((l, (v >> (idx1[0] * O)) & mask))
    return out


def find_x(rows1, rows2, b3_1, b3_2, a1, a2, O, rng):
    """Nonzero x and (l1,l2) for the same x with l1.a1 = 1 and l2.a2 = 1."""
    M1 = lb_maps(rows1, b3_1, O)
    M2 = lb_maps(rows2, b3_2, O)
    n1 = len(M1)
    vecs = [m[1] for m in M1] + [m[1] for m in M2]
    # nullspace over combos: columns = vecs; equations per output bit
    eq = []
    for o in range(O):
        e = 0
        for j, v in enumerate(vecs):
            if (v >> o) & 1:
                e |= 1 << j
        eq.append(e)
    sols = P.nullspace(eq, len(vecs))
    if not sols:
        return None
    rng.shuffle(sols)
    res = []
    limit = min(len(sols), 8)
    for c in range(1, 1 << limit):
        z = 0
        for j in range(limit):
            if (c >> j) & 1:
                z ^= sols[j]
        l1 = 0
        x1 = 0
        for j in range(n1):
            if (z >> j) & 1:
                l1 ^= M1[j][0]
                x1 ^= M1[j][1]
        l2 = 0
        for j in range(len(M2)):
            if (z >> (n1 + j)) & 1:
                l2 ^= M2[j][0]
        if not x1:
            continue
        if bin(l1 & a1).count('1') & 1 and bin(l2 & a2).count('1') & 1:
            return x1
    return None


def apply_ext(X30, a, b, x):
    """X ^= a(y) b(z) x(o); a over y index bits, b over z index bits, x over outputs."""
    ay = np.array([(a >> i) & 1 for i in range(X30.shape[0])], dtype=bool)
    bz = np.array([(b >> i) & 1 for i in range(15)], dtype=bool)
    xo = np.array([(x >> i) & 1 for i in range(X30.shape[2])], dtype=bool)
    X30 ^= (ay[:, None] & bz[None, :])[:, :, None] & xo[None, None, :]
