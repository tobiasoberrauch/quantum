#!/usr/bin/env python3
"""Plain-loader relation search: Rel_t = random c-dim subspace of the annihilator (general) with hill climbing on exact parity."""
from __future__ import annotations

import argparse
import os
import random
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import emit  # noqa: E402
import extract_plan as ep  # noqa: E402
import padfill  # noqa: E402
import plan35 as Q  # noqa: E402
import planner as P  # noqa: E402
import replan as rp  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('base')
    ap.add_argument('k', type=int)
    ap.add_argument('part')
    ap.add_argument('out')
    ap.add_argument('--c', type=int, default=18)
    ap.add_argument('--secs', type=float, default=200)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--mode', default='general')
    ap.add_argument('--addevery', type=int, default=5)
    a = ap.parse_args()
    log = lambda s: print(f'[k{a.k}] {s}', flush=True)  # noqa: E731
    os.makedirs(a.out, exist_ok=True)
    words = np.load(a.base + '/submission.npz')['angle_words']
    X, _ = ep.tensor_of_words(words, a.k)
    X35 = X[:, :, Q.OUTS35].copy()
    rng = random.Random(a.seed)
    basis = rp.partition_basis(a.part, rng)
    Bm = np.array([[(v >> j) & 1 for j in range(15)] for pb in basis for v in pb], dtype=np.uint8)
    Inv = P.gf2_inv(Bm)
    Xf, sel = padfill.fill_padding(X35, Inv, list(range(5)))
    rows_t = []
    anns = []
    for t in range(5):
        coord = Inv[:, 3 * t:3 * t + 3].T.astype(bool)
        rows_t.append(P.plane_rows(Xf, coord))
        anns.append(P.nullspace(rows_t[-1], 3 * Q.O))
    Q.CAP['k'] = 4

    def rand_rel(t, c):
        ann = anns[t]
        out = []
        piv = {}
        while len(out) < c:
            v = 0
            for R in ann:
                if rng.random() < 0.5:
                    v ^= R
            r = P.reduce_v(v, piv)
            if r:
                piv[r.bit_length() - 1] = r
                out.append(v)
        return out

    rels = [rand_rel(t, a.c) for t in range(5)]
    if a.mode == 'pure':
        for t in range(5):
            ann, pu, pl_, mix = Q.rel_pieces(rows_t[t])
            rels[t] = pu + rand_rel(t, a.c)[:max(0, a.c - len(pu))]
    planes = [Q.PlaneR(rows_t[t], rels[t]) for t in range(5)]
    cands = Q.cand_list(planes)
    nu, D, uv = Q.nu_of(planes, cands, a.seed)
    best = D - nu
    log(f'start c={a.c} D {D} nu {nu} products {best} cands {len(cands)}')
    t0 = time.time()
    it = 0
    while time.time() - t0 < a.secs:
        it += 1
        t = rng.randrange(5)
        # replace one relation by another annihilator element (keep count)
        old = rels[t]
        new = list(old)
        j = rng.randrange(len(new))
        v = 0
        for R in anns[t]:
            if rng.random() < 0.5:
                v ^= R
        new[j] = v
        if len(P.rref_basis(new)) < len(new):
            continue
        p2 = planes[:t] + [Q.PlaneR(rows_t[t], new)] + planes[t + 1:]
        c2 = Q.cand_list(p2)
        nu2, D2, _ = Q.nu_of(p2, c2, a.seed)
        val = D2 - nu2
        if val <= best:
            if val < best:
                log(f'it {it} products {val} nu {nu2} D {D2} cands {len(c2)} t={time.time()-t0:.0f}')
            best = val
            planes, rels[t] = p2, new
        # try adding one relation when the current D is odd-perfect or even-perfect
        if it % a.addevery == 0:
            t2 = rng.randrange(5)
            v = 0
            for R in anns[t2]:
                if rng.random() < 0.5:
                    v ^= R
            newr = rels[t2] + [v]
            if len(P.rref_basis(newr)) == len(newr):
                p3 = planes[:t2] + [Q.PlaneR(rows_t[t2], newr)] + planes[t2 + 1:]
                c3 = Q.cand_list(p3)
                nu3, D3, _ = Q.nu_of(p3, c3, a.seed)
                val3 = D3 - nu3
                if val3 <= best and (val3 < best or D3 % 2 == 1):
                    if val3 < best:
                        log(f'add-rel it {it} products {val3} nu {nu3} D {D3} cands {len(c3)} t={time.time()-t0:.0f}')
                    best = val3
                    planes, rels[t2] = p3, newr
    log(f'best {best}')
    cands = Q.cand_list(planes)
    nu, D, uv = Q.nu_of(planes, cands, a.seed)
    pairs, singles = Q.extract_pairs(planes, cands, uv, D, a.seed)
    prods = Q.build_products(planes, basis, pairs, singles)
    log(f'final products {len(prods)} pairs {len(pairs)} singles {len(singles)} D {D} nu {nu}')
    products = []
    for a1, b1, a2, b2, s in prods:
        f, g = rp.tt_from(a1, b2), rp.tt_from(a2, b1)
        products.append((f, g, [11 + Q.OUTS35[o] for o in range(35) if s >> o & 1]))
    dst = os.path.join(a.out, f'angle_k_{a.k}.kmb')
    c = emit.rebuild(os.path.join(a.base, f'angle_k_{a.k}.kmb'), words, a.k, products, dst, log=log)
    log(f'emitted T={c.operation_statistics().num_toffoli_like} Q={c.num_qubits}')


if __name__ == '__main__':
    main()
