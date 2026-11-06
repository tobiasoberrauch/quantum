"""Exact pairing for the plane model: returns chosen pairs given planes+cands. Odd total dim: fix one single feature first."""
from __future__ import annotations

import random

import numpy as np

import parity as Par
import planner as P


def coords_setup(planes):
    infos = []
    off = 0
    for pl in planes:
        ech = {}
        rows = pl.rows
        basis = []
        for r in rows:
            v, m = r, 0
            while v:
                h = v.bit_length() - 1
                p = ech.get(h)
                if p is None:
                    idx = len(basis)
                    basis.append(r)
                    ech[h] = (v, m | (1 << idx))
                    break
                v ^= p[0]
                m ^= p[1]
        infos.append((ech, off, len(basis)))
        off += len(basis)
    return infos, off


def vec_coords(v, info, D):
    ech, off, dim = info
    m = 0
    while v:
        h = v.bit_length() - 1
        p = ech.get(h)
        if p is None:
            raise ValueError('feature outside W')
        v ^= p[0]
        m ^= p[1]
    out = np.zeros(D, dtype=bool)
    for i in range(dim):
        if (m >> i) & 1:
            out[off + i] = True
    return out


def solve(planes, cands, seed=0, log=None, attempts=30):
    """Return (chosen pairs, singles) with products = len(pairs)+len(singles); or None."""
    infos, D = coords_setup(planes)
    rng = np.random.default_rng(seed)
    pyrng = random.Random(seed)
    uv = []
    for t1, b1, t2, b2, s in cands:
        uv.append((vec_coords(planes[t1].feature(b1, s), infos[t1], D), vec_coords(planes[t2].feature(b2, s), infos[t2], D)))
    A0, xs = Par.build(uv, D, rng)
    r, _ = Par.rank_and_inverse(A0, want_inverse=False)
    if log:
        log(f'D {D} rank {r} nu {r//2}; products lower bound {D - r//2}')
    best = None
    for att in range(attempts):
        # complement: pick singles so remaining dimension is perfectly matched
        singles = []
        A = A0.copy()
        keepdims = np.arange(D)
        defect = D - r
        if defect:
            # add singles by adding pairs (f, dummy) until full rank: use dummy dims
            n = D + defect + (0 if (D + defect) % 2 == 0 else 0)
            ext = np.zeros((D + defect, D + defect), dtype=np.int64)
            ext[:D, :D] = A0
            sing_list = []
            # candidate singles: all admissible features
            for t, pl in enumerate(planes):
                for b in range(1, 8):
                    sols = P.nullspace(pl.Vb[b], pl.O)
                    pyrng.shuffle(sols)
                    for s in sols[:4]:
                        sing_list.append((t, b, s))
            pyrng.shuffle(sing_list)
            uv2 = [(np.pad(u, (0, defect)), np.pad(v, (0, defect))) for u, v in uv]
            sidx = []
            for k, (t, b, s) in enumerate(sing_list):
                u = np.pad(vec_coords(planes[t].feature(b, s), infos[t], D), (0, defect))
                for dd in range(defect):
                    v = np.zeros(D + defect, dtype=bool)
                    v[D + dd] = True
                    sidx.append((t, b, s))
                    uv2.append((u, v))
            A2, xs2 = Par.build(uv2, D + defect, rng)
            r2, Y = Par.rank_and_inverse(A2)
            if Y is None:
                if log:
                    log(f'attempt {att}: not perfect with singles, rank {r2} of {D+defect}')
                continue
            base_n = len(uv)
            order = list(range(len(uv2)))
            pyrng.shuffle(order)
            # prefer keeping real pairs: delete singles first
            order = [i for i in order if i >= base_n] + [i for i in order if i < base_n]
            keep = Par.extract(uv2, xs2, Y.copy(), order)
            pairs = [cands[i] for i in keep if i < base_n]
            singles = [sidx[i - base_n] for i in keep if i >= base_n]
        else:
            r2, Y = Par.rank_and_inverse(A0)
            if Y is None:
                return None
            order = list(range(len(uv)))
            pyrng.shuffle(order)
            keep = Par.extract(uv, xs, Y.copy(), order)
            pairs = [cands[i] for i in keep]
        best = (pairs, singles)
        break
    return best
