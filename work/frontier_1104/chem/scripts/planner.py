#!/usr/bin/env python3
"""Plane-based relation planner (own code; idea from the public write-ups of iwanttorungemma9b, Lera, matousakura).

Tensor X[y,z,o] = sum a(y) b(z) s(o). z-function space F2^15 is split into 5 3-dim planes B_t. In plane t the rows live
in F2^(3*O); relations = annihilator of rows; a rank-one feature (b,s), b in B_t, is admissible if every kept relation
kills it. Two features with the same s (any planes) form one product. Greedy matroid-parity with local search.
"""
from __future__ import annotations

import itertools
import random
import sys
import time

import numpy as np


def rref_basis(vecs):
    """Return echelon dict pivot->vector."""
    piv = {}
    for v in vecs:
        v = reduce_v(v, piv)
        if v:
            piv[v.bit_length() - 1] = v
    return piv


def reduce_v(v, piv):
    while v:
        h = v.bit_length() - 1
        p = piv.get(h)
        if p is None:
            return v
        v ^= p
    return 0


def nullspace(rows, n):
    """Vectors x (ints over n bits) with parity(row & x)=0 for all rows."""
    # Gaussian elimination on rows
    piv = {}
    for r in rows:
        r = reduce_v(r, piv)
        if r:
            piv[r.bit_length() - 1] = r
    # back substitute
    pivs = sorted(piv)
    for p in pivs:
        for q in pivs:
            if q != p and (piv[q] >> p) & 1:
                piv[q] ^= piv[p]
    free = [i for i in range(n) if i not in piv]
    out = []
    for f in free:
        x = 1 << f
        for p, r in piv.items():
            if (r >> f) & 1:
                x |= 1 << p
        out.append(x)
    return out


def rows_to_plane(X, Binv_idx):
    """X (Y,15,O) bool; Binv (3,15) coordinate functionals -> rows ints over 3*O bits."""
    Y, _, O = X.shape
    C = (Binv_idx.astype(int) @ X.astype(int).transpose(0, 2, 1).reshape(-1, 15).T).T % 2  # placeholder
    return C


def plane_rows(X, coord):
    """coord: (3,15) bool functionals. Returns python ints r_y over bits (i*O+o)."""
    Y, Z, O = X.shape
    out = []
    for y in range(Y):
        v = 0
        xy = X[y]  # (15,O)
        for i in range(3):
            col = np.logical_xor.reduce(xy[coord[i]], axis=0) if coord[i].any() else np.zeros(O, bool)
            for o in np.flatnonzero(col):
                v |= 1 << (i * O + int(o))
        out.append(v)
    return out


def gf2_inv(M):
    n = M.shape[0]
    A = np.concatenate([M.astype(np.uint8), np.eye(n, dtype=np.uint8)], axis=1)
    r = 0
    for c in range(n):
        p = None
        for i in range(r, n):
            if A[i, c]:
                p = i
                break
        if p is None:
            raise ValueError('singular')
        A[[r, p]] = A[[p, r]]
        for i in range(n):
            if i != r and A[i, c]:
                A[i] ^= A[r]
        r += 1
    return A[:, n:]


class Plane:
    def __init__(self, rows, O, drop=0, rng=None):
        self.O = O
        self.rows = rows
        self.rank = len(rref_basis(rows))
        self.ann = nullspace(rows, 3 * O)
        self.mask = (1 << O) - 1
        self.Vb = {}
        ann = self.ann
        for b in range(1, 8):
            eq = []
            for R in ann:
                # s -> b^T R s : row vector over O
                v = 0
                for i in range(3):
                    if (b >> i) & 1:
                        v ^= (R >> (i * O)) & self.mask
                eq.append(v)
            self.Vb[b] = eq  # equations
        self.pivV = {b: rref_basis(self.Vb[b]) for b in self.Vb}

    def feature(self, b, s):
        v = 0
        for i in range(3):
            if (b >> i) & 1:
                v |= s << (i * self.O)
        return v


def cand_pairs(planes, O):
    """All (t1,b1,t2,b2,s) with s in V(t1,b1) cap V(t2,b2)."""
    cands = []
    idx = [(t, b) for t in range(len(planes)) for b in range(1, 8)]
    for (t1, b1), (t2, b2) in itertools.combinations(idx, 2):
        eq = planes[t1].Vb[b1] + planes[t2].Vb[b2]
        sols = nullspace(eq, O)
        if len(sols) > 8:
            sols = sols[:8]
        for c in range(1, 1 << len(sols)):
            s = 0
            for j, v in enumerate(sols):
                if c >> j & 1:
                    s ^= v
            cands.append((t1, b1, t2, b2, s))
    return cands


def greedy(planes, cands, rng, order=None, start=None):
    """Greedy parity; returns chosen list and per-plane echelons."""
    ech = [{} for _ in planes]
    chosen = []
    if start:
        for c in start:
            t1, b1, t2, b2, s = c
            v1 = reduce_v(planes[t1].feature(b1, s), ech[t1])
            if t1 == t2:
                if v1:
                    ech[t1][v1.bit_length() - 1] = v1
                v2 = reduce_v(planes[t2].feature(b2, s), ech[t2])
                if v1 and v2:
                    ech[t2][v2.bit_length() - 1] = v2
                    chosen.append(c)
                else:
                    if v1:
                        del ech[t1][v1.bit_length() - 1]
                continue
            v2 = reduce_v(planes[t2].feature(b2, s), ech[t2])
            if v1 and v2:
                ech[t1][v1.bit_length() - 1] = v1
                ech[t2][v2.bit_length() - 1] = v2
                chosen.append(c)
    order = list(cands) if order is None else order
    if order is cands or order == cands:
        order = list(cands)
    rng.shuffle(order)
    for c in order:
        t1, b1, t2, b2, s = c
        if len(ech[t1]) >= planes[t1].need or len(ech[t2]) >= planes[t2].need:
            continue
        v1 = reduce_v(planes[t1].feature(b1, s), ech[t1])
        if not v1:
            continue
        if t1 == t2:
            tmp = dict(ech[t1])
            tmp[v1.bit_length() - 1] = v1
            v2 = reduce_v(planes[t2].feature(b2, s), tmp)
            if not v2:
                continue
            ech[t1] = tmp
            ech[t1][v2.bit_length() - 1] = v2
        else:
            v2 = reduce_v(planes[t2].feature(b2, s), ech[t2])
            if not v2:
                continue
            ech[t1][v1.bit_length() - 1] = v1
            ech[t2][v2.bit_length() - 1] = v2
        chosen.append(c)
    return chosen, ech


def score(planes, chosen, ech):
    missing = sum(p.need - len(e) for p, e in zip(planes, ech))
    return len(chosen) + missing, missing


def search(planes, O, cands, seconds, seed=0, log=None):
    rng = random.Random(seed)
    best_c, best_e = greedy(planes, cands, rng)
    best = score(planes, best_c, best_e)
    t0 = time.time()
    it = 0
    if log:
        log(f'start products {best[0]} missing {best[1]} pairs {len(best_c)} cands {len(cands)}')
    while time.time() - t0 < seconds:
        it += 1
        k = rng.randint(1, max(2, len(best_c) // 8))
        keep = rng.sample(best_c, len(best_c) - k)
        c2, e2 = greedy(planes, cands, rng, start=keep)
        s2 = score(planes, c2, e2)
        if s2 <= best:
            if s2 < best and log:
                log(f'it {it} products {s2[0]} missing {s2[1]} pairs {len(c2)}  t={time.time()-t0:.0f}')
            best_c, best_e, best = c2, e2, s2
    return best_c, best_e, best
