#!/usr/bin/env python3
"""Full 35-output plane planner with chosen relation sets, exact parity, re-emission. Own code.

Rel_t = pure-upper + pure-LSB annihilators + m_t mixed relations. dim W_t = 105 - |Rel_t|; products >= sum dim W / 2.
Usage: plan35.py <base> <k> <partition-plan> <out> [--tries N] [--seed S] [--emit-only-if-better T]
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import random
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import emit  # noqa: E402
import extract_plan as ep  # noqa: E402
import padfill  # noqa: E402
import parity as Par  # noqa: E402
import planner as P  # noqa: E402
import replan as rp  # noqa: E402

O = 35
OUTS35 = [8 * j + b for j in range(5) for b in range(7)]
LSB_IDX = [7 * j for j in range(5)]
UP_IDX = [i for i in range(35) if i % 7 != 0]


class PlaneR:
    def __init__(self, rows, rel):
        self.rows = rows
        self.O = O
        self.set_rel(rel)

    def set_rel(self, rel):
        self.rel = rel
        mask = (1 << O) - 1
        self.Vb = {}
        for b in range(1, 8):
            eq = []
            for R in rel:
                v = 0
                for i in range(3):
                    if (b >> i) & 1:
                        v ^= (R >> (i * O)) & mask
                eq.append(v)
            self.Vb[b] = eq
        self.W = P.nullspace(rel, 3 * O)
        self.need = len(self.W)
        self._ech = None

    def feature(self, b, s):
        v = 0
        for i in range(3):
            if (b >> i) & 1:
                v |= s << (i * O)
        return v

    def ech(self):
        if self._ech is None:
            e = {}
            for idx, r in enumerate(self.W):
                v, m = r, 1 << idx
                while v:
                    h = v.bit_length() - 1
                    p = e.get(h)
                    if p is None:
                        e[h] = (v, m)
                        break
                    v ^= p[0]
                    m ^= p[1]
            self._ech = e
        return self._ech


def to_coords(v, pl, off, D):
    e = pl.ech()
    m = 0
    while v:
        h = v.bit_length() - 1
        p = e[h]
        v ^= p[0]
        m ^= p[1]
    out = np.zeros(D, dtype=bool)
    i = 0
    while m:
        if m & 1:
            out[off + i] = True
        m >>= 1
        i += 1
    return out


def uv_all(planes, cands):
    offs = np.cumsum([0] + [p.need for p in planes])
    D = int(offs[-1])
    uv = [(to_coords(planes[t1].feature(b1, s), planes[t1], offs[t1], D), to_coords(planes[t2].feature(b2, s), planes[t2], offs[t2], D)) for t1, b1, t2, b2, s in cands]
    return uv, D, offs


def nu_of(planes, cands, seed):
    uv, D, _ = uv_all(planes, cands)
    if not uv:
        return 0, D, uv
    rng = np.random.default_rng(seed)
    A, xs = Par.build(uv, D, rng)
    r, _ = Par.rank_and_inverse(A, want_inverse=False)
    return r // 2, D, uv


def products_lb(nu, D):
    return D - nu


def extract_pairs(planes, cands, uv, D, seed):
    """Max parity set + singles; returns (pairs, singles)."""
    rng = np.random.default_rng(seed)
    pyr = random.Random(seed)
    A, xs = Par.build(uv, D, rng)
    r, Y = Par.rank_and_inverse(A)
    if Y is not None:
        order = list(range(len(uv)))
        pyr.shuffle(order)
        keep = Par.extract(uv, xs, Y.copy(), order)
        return [cands[i] for i in keep], []
    defect = D - r
    # add single candidates through dummy dimensions
    offs = np.cumsum([0] + [p.need for p in planes])
    uv2 = [(np.pad(u, (0, defect)), np.pad(v, (0, defect))) for u, v in uv]
    sing = []
    for t, pl in enumerate(planes):
        for b in range(1, 8):
            sols = P.nullspace(pl.Vb[b], O)
            pyr.shuffle(sols)
            for s in sols[:5]:
                sing.append((t, b, s))
    n0 = len(uv2)
    tags = []
    for (t, b, s) in sing:
        u = np.pad(to_coords(planes[t].feature(b, s), planes[t], offs[t], D), (0, defect))
        for dd in range(defect):
            v = np.zeros(D + defect, dtype=bool)
            v[D + dd] = True
            uv2.append((u, v))
            tags.append((t, b, s))
    for att in range(20):
        A2, xs2 = Par.build(uv2, D + defect, rng)
        r2, Y2 = Par.rank_and_inverse(A2)
        if Y2 is None:
            continue
        order = list(range(len(uv2)))
        pyr.shuffle(order)
        order = [i for i in order if i >= n0] + [i for i in order if i < n0]
        keep = Par.extract(uv2, xs2, Y2.copy(), order)
        return [cands[i] for i in keep if i < n0], [tags[i - n0] for i in keep if i >= n0]
    return None, None


def build_products(planes, basis, pairs, singles):
    """Coefficient a(y) for each chosen feature, returns list of (a1,b1,a2,b2,s)."""
    feats = [[] for _ in planes]
    for idx, (t1, b1, t2, b2, s) in enumerate(pairs):
        feats[t1].append((idx, 0, b1, s))
        feats[t2].append((idx, 1, b2, s))
    for j, (t, b, s) in enumerate(singles):
        feats[t].append((10000 + j, 0, b, s))
    a_of = {}
    for t, pl in enumerate(planes):
        e = {}
        for j, (idx, side, b, s) in enumerate(feats[t]):
            v, m = pl.feature(b, s), 1 << j
            while v:
                h = v.bit_length() - 1
                p = e.get(h)
                if p is None:
                    e[h] = (v, m)
                    break
                v ^= p[0]
                m ^= p[1]
        ac = [0] * len(feats[t])
        for y, r in enumerate(pl.rows):
            v, m = r, 0
            while v:
                h = v.bit_length() - 1
                p = e[h]
                v ^= p[0]
                m ^= p[1]
            j = 0
            while m:
                if m & 1:
                    ac[j] |= 1 << y
                m >>= 1
                j += 1
        for j, (idx, side, b, s) in enumerate(feats[t]):
            realb = 0
            for i in range(3):
                if (b >> i) & 1:
                    realb ^= basis[t][i]
            a_of[(idx, side)] = (ac[j], realb, s)
    prods = []
    for idx in range(len(pairs)):
        a1, b1, s = a_of[(idx, 0)]
        a2, b2, _ = a_of[(idx, 1)]
        prods.append((a1, b1, a2, b2, s))
    for j in range(len(singles)):
        a1, b1, s = a_of[(10000 + j, 0)]
        prods.append((a1, b1, 0, 0, s))
    return prods


def rel_pieces(rows):
    """Pure-upper, pure-LSB and mixed relation bases of a plane (3*35 bit)."""
    def col_mask(idx):
        m = 0
        for i in range(3):
            for o in idx:
                m |= 1 << (i * O + o)
        return m
    mU, mL = col_mask(UP_IDX), col_mask(LSB_IDX)
    ann = P.nullspace(rows, 3 * O)
    # pure-upper: annihilator elements supported on upper columns
    def sub_ann(mask, other):
        # relations R supported on mask only: R in ann with R & other == 0
        eq = []
        for bit in range(3 * O):
            if (other >> bit) & 1:
                e = 0
                for j, R in enumerate(ann):
                    if (R >> bit) & 1:
                        e |= 1 << j
                eq.append(e)
        sols = P.nullspace(eq, len(ann))
        out = []
        for c in sols:
            v = 0
            for j, R in enumerate(ann):
                if (c >> j) & 1:
                    v ^= R
            out.append(v)
        return out
    pure_u = sub_ann(mU, mL)
    pure_l = sub_ann(mL, mU)
    piv = P.rref_basis(pure_u + pure_l)
    mixed = []
    for R in ann:
        v = P.reduce_v(R, piv)
        if v:
            piv[v.bit_length() - 1] = v
            mixed.append(R)
    return ann, pure_u, pure_l, mixed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('base')
    ap.add_argument('k', type=int)
    ap.add_argument('part')
    ap.add_argument('out')
    ap.add_argument('--tries', type=int, default=40)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--maxsteps', type=int, default=8)
    ap.add_argument('--tmax', type=float, default=1e9)
    ap.add_argument('--init-mix', type=int, default=0)
    ap.add_argument('--capk', type=int, default=6)
    a = ap.parse_args()
    log = lambda s: print(f'[k{a.k}] {s}', flush=True)  # noqa: E731
    os.makedirs(a.out, exist_ok=True)
    words = np.load(a.base + '/submission.npz')['angle_words']
    X, tie = ep.tensor_of_words(words, a.k)
    X35 = X[:, :, OUTS35].copy()
    rng = random.Random(a.seed)
    basis = rp.partition_basis(a.part, rng)
    Bm = np.array([[(v >> j) & 1 for j in range(15)] for pb in basis for v in pb], dtype=np.uint8)
    Inv = P.gf2_inv(Bm)
    Xf, sel = padfill.fill_padding(X35, Inv, list(range(5)))
    log(f'padding planes {sel}')
    rows_t = []
    for t in range(5):
        coord = Inv[:, 3 * t:3 * t + 3].T.astype(bool)
        rows_t.append(P.plane_rows(Xf, coord))
    planes = []
    pieces = []
    for t in range(5):
        ann, pu, pl_, mix = rel_pieces(rows_t[t])
        pieces.append((pu, pl_, mix))
        planes.append(PlaneR(rows_t[t], pu + pl_))
    log('rel sizes (u,l,mixed) ' + str([(len(p[0]), len(p[1]), len(p[2])) for p in pieces]) + f' dims {[p.need for p in planes]}')
    t0 = time.time()
    CAP['k'] = a.capk
    cur_rel_init = [list(p[0] + p[1]) for p in pieces]
    if a.init_mix:
        for t in range(5):
            mix = pieces[t][2]
            if not mix:
                continue
            piv = P.rref_basis(cur_rel_init[t])
            added = 0
            while added < a.init_mix:
                v = 0
                for R in mix:
                    if rng.random() < 0.5:
                        v ^= R
                vr = P.reduce_v(v, piv)
                if vr:
                    piv[vr.bit_length() - 1] = vr
                    cur_rel_init[t].append(v)
                    added += 1
            planes[t] = PlaneR(rows_t[t], cur_rel_init[t])
    cands = cand_list(planes)
    nu, D, uv = nu_of(planes, cands, a.seed)
    best_val = products_lb(nu, D)
    log(f'base D {D} nu {nu} products {best_val} cands {len(cands)} t={time.time()-t0:.0f}')
    cur_rel = cur_rel_init
    used_mix = [[] for _ in range(5)]
    for step in range(a.maxsteps):
        options = []
        for t in range(5):
            mix = pieces[t][2]
            if not mix:
                continue
            # candidates: combination of mixed basis not already in span
            piv = P.rref_basis(cur_rel[t])
            combos = []
            crange = range(1, 1 << len(mix)) if len(mix) <= 6 else [rng.randrange(1, 1 << len(mix)) for _ in range(120)]
            for c in crange:
                v = 0
                for j in range(len(mix)):
                    if (c >> j) & 1:
                        v ^= mix[j]
                if P.reduce_v(v, piv):
                    combos.append((t, v))
            options += combos
        if not options:
            break
        rng.shuffle(options)
        improved = None
        for (t, v) in options[:a.tries]:
            if time.time() - t0 > a.tmax:
                break
            old = planes[t]
            trial = PlaneR(rows_t[t], cur_rel[t] + [v])
            planes2 = planes[:t] + [trial] + planes[t + 1:]
            c2 = cand_list(planes2)
            nu2, D2, _ = nu_of(planes2, c2, a.seed)
            val = products_lb(nu2, D2)
            if val < best_val or (val == best_val and improved is None and D2 % 2 == 1):
                if improved is None or val < improved[0]:
                    improved = (val, t, v, nu2, D2)
                if val < best_val:
                    break
        if improved is None:
            log(f'step {step}: no improving mixed relation in {min(a.tries, len(options))} tries')
            break
        val, t, v, nu2, D2 = improved
        cur_rel[t] = cur_rel[t] + [v]
        planes = planes[:t] + [PlaneR(rows_t[t], cur_rel[t])] + planes[t + 1:]
        best_val = val
        log(f'step {step}: plane {t} extra relation -> D {D2} nu {nu2} products {val} t={time.time()-t0:.0f}')
    cands = cand_list(planes)
    nu, D, uv = nu_of(planes, cands, a.seed)
    pairs, singles = extract_pairs(planes, cands, uv, D, a.seed)
    prods = build_products(planes, basis, pairs, singles)
    log(f'final products {len(prods)} pairs {len(pairs)} singles {len(singles)} D {D} nu {nu}')
    products = []
    for a1, b1, a2, b2, s in prods:
        f, g = rp.tt_from(a1, b2), rp.tt_from(a2, b1)
        products.append((f, g, [11 + OUTS35[o] for o in range(35) if s >> o & 1]))
    dst = os.path.join(a.out, f'angle_k_{a.k}.kmb')
    c = emit.rebuild(os.path.join(a.base, f'angle_k_{a.k}.kmb'), words, a.k, products, dst, log=log)
    log(f'emitted T={c.operation_statistics().num_toffoli_like} Q={c.num_qubits}')


CAP = {'k': 6}


def cand_list(planes):
    cands = []
    idx = [(t, b) for t in range(len(planes)) for b in range(1, 8)]
    for (t1, b1), (t2, b2) in itertools.combinations(idx, 2):
        sols = P.nullspace(planes[t1].Vb[b1] + planes[t2].Vb[b2], O)
        if not sols:
            continue
        sols = sols[:CAP['k']]
        for c in range(1, 1 << len(sols)):
            s = 0
            for j, v in enumerate(sols):
                if (c >> j) & 1:
                    s ^= v
            cands.append((t1, b1, t2, b2, s))
    return cands


if __name__ == '__main__':
    main()
