#!/usr/bin/env python3
"""Replan a coded loader: keep shipped LSB products, plane-based planner for the 30 upper outputs, re-emit.
Usage: replan.py <basedir> <k> <partition plan file or 'random:<seed>'> <outdir> [--secs S] [--seed n]"""
from __future__ import annotations

import argparse
import collections
import json
import os
import random
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import emit  # noqa: E402
import extract_plan as ep  # noqa: E402
import planner as P  # noqa: E402
import padfill  # noqa: E402
import tensor_probe as tp  # noqa: E402
import triples  # noqa: E402

N = 1220
ADDR = np.arange(N)
Y = ADDR >> 4
Z = ADDR & 15
OUTS30 = [8 * j + b for j in range(5) for b in range(1, 7)]
LSB = [8 * j for j in range(5)]


def tt_from(a_bits, b_bits):
    """a over y=1..76 (int), b over z=1..15 (int) -> truth table of a(y)+b(z)."""
    ya = np.zeros(77, dtype=bool)
    for i in range(76):
        ya[i + 1] = (a_bits >> i) & 1
    zb = np.zeros(16, dtype=bool)
    for i in range(15):
        zb[i + 1] = (b_bits >> i) & 1
    return ya[Y] ^ zb[Z]


LINB = [int('101010101010101', 2), int('110011001100110', 2), int('111100001111000', 2), int('111111110000000', 2)]


def partition_basis(spec, rng):
    if spec.startswith('randlin'):
        # random partition with the four linear z-functionals placed (spec randlin:<two>: two of them share a plane)
        while True:
            vs = []
            two = spec.endswith(':2')
            if spec.endswith(':3'):
                vs = [LINB[0], LINB[1], LINB[2], LINB[3], rng.getrandbits(15), rng.getrandbits(15)]
                vs += [rng.getrandbits(15) for _ in range(9)]
            elif spec.endswith(':22'):
                vs = [LINB[0], LINB[1], rng.getrandbits(15), LINB[2], LINB[3], rng.getrandbits(15)]
                vs += [rng.getrandbits(15) for _ in range(9)]
            elif two:
                vs = [LINB[0], LINB[1], rng.getrandbits(15), LINB[2], rng.getrandbits(15), rng.getrandbits(15), LINB[3]]
                vs += [rng.getrandbits(15) for _ in range(8)]
            else:
                for i in range(4):
                    vs += [LINB[i], rng.getrandbits(15), rng.getrandbits(15)]
                vs += [rng.getrandbits(15) for _ in range(3)]
            B = np.array([[(v >> j) & 1 for j in range(15)] for v in vs], dtype=np.uint8)
            try:
                P.gf2_inv(B)
                break
            except ValueError:
                continue
        return [vs[3 * t:3 * t + 3] for t in range(5)]
    if spec.startswith('random'):
        while True:
            B = np.array([[rng.random() < .5 for _ in range(15)] for _ in range(15)], dtype=np.uint8)
            try:
                P.gf2_inv(B)
                break
            except ValueError:
                continue
        return [[sum(int(B[3 * t + i, j]) << j for j in range(15)) for i in range(3)] for t in range(5)]
    _, planes_b, _, _ = triples.triples_of(spec)
    basis = []
    for pl in planes_b:
        pb, piv = [], {}
        for x in pl:
            r = P.reduce_v(x, piv)
            if r:
                piv[r.bit_length() - 1] = r
                pb.append(x)
        basis.append(pb)
    return basis


def plan30(X30, basis, secs, seed, log, pad=True):
    """Returns list of (a1,b1,a2,b2,s_mask_over_30) real-b ints, products count."""
    O = X30.shape[2]
    Bm = np.array([[(v >> j) & 1 for j in range(15)] for pb in basis for v in pb], dtype=np.uint8)
    Inv = P.gf2_inv(Bm)
    planes = []
    if pad:
        X30, sel = padfill.fill_padding(X30, Inv, list(range(5)))
        log(f'padding satisfied planes {sel}')
    for t in range(5):
        coord = Inv[:, 3 * t:3 * t + 3].T.astype(bool)
        rows = P.plane_rows(X30, coord)
        pl = P.Plane(rows, O)
        pl.need = pl.rank
        planes.append(pl)
    cands = P.cand_pairs(planes, O)
    ch, ech, best = P.search(planes, O, cands, secs, seed=seed, log=log)
    log(f'plan best {best} pairs {len(ch)} filled {[len(e) for e in ech]} need {[p.need for p in planes]}')
    # coefficients: per plane, features list, then express rows
    feats = [[] for _ in planes]
    for idx, (t1, b1, t2, b2, s) in enumerate(ch):
        feats[t1].append((idx, 0, b1, s))
        feats[t2].append((idx, 1, b2, s))
    # singles to fill missing dims
    extra_singles = []
    for t, pl in enumerate(planes):
        e = {}
        for idx, side, b, s in feats[t]:
            v = P.reduce_v(pl.feature(b, s), e)
            assert v
            e[v.bit_length() - 1] = v
        # Find single features filling the remainder
        for b in range(1, 8):
            sols = P.nullspace(pl.Vb[b], O)
            for s in sols:
                if len(e) >= pl.need:
                    break
                v = P.reduce_v(pl.feature(b, s), e)
                if v:
                    e[v.bit_length() - 1] = v
                    extra_singles.append((t, b, s))
                    feats[t].append((1000 + len(extra_singles), 0, b, s))
    a_of = {}
    for t, pl in enumerate(planes):
        # echelon with tracking over features
        ech_t = {}
        for j, (idx, side, b, s) in enumerate(feats[t]):
            v = pl.feature(b, s)
            m = 1 << j
            while v:
                h = v.bit_length() - 1
                p = ech_t.get(h)
                if p is None:
                    ech_t[h] = (v, m)
                    break
                v ^= p[0]
                m ^= p[1]
        acoef = [0] * len(feats[t])
        for y, r in enumerate(pl.rows):
            v, m = r, 0
            while v:
                h = v.bit_length() - 1
                p = ech_t[h]
                v ^= p[0]
                m ^= p[1]
            for j in range(len(feats[t])):
                if (m >> j) & 1:
                    acoef[j] |= 1 << y
        for j, (idx, side, b, s) in enumerate(feats[t]):
            realb = 0
            for i in range(3):
                if (b >> i) & 1:
                    realb ^= basis[t][i]
            a_of[(idx, side)] = (acoef[j], realb, s)
    prods = []
    for idx in range(len(ch)):
        a1, b1, s = a_of[(idx, 0)]
        a2, b2, _ = a_of[(idx, 1)]
        prods.append((a1, b1, a2, b2, s))
    for j, (t, b, s) in enumerate(extra_singles):
        a1, b1, s_ = a_of[(1000 + j + 1, 0)]
        prods.append((a1, b1, 0, 0, s_))
    return prods


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('base')
    ap.add_argument('k', type=int)
    ap.add_argument('part')
    ap.add_argument('out')
    ap.add_argument('--secs', type=float, default=5)
    ap.add_argument('--seed', type=int, default=0)
    a = ap.parse_args()
    log = lambda s: print(f'[k{a.k}] {s}', flush=True)  # noqa: E731
    os.makedirs(a.out, exist_ok=True)
    words = np.load(a.base + '/submission.npz')['angle_words']
    X, tie = ep.tensor_of_words(words, a.k)
    rng = random.Random(a.seed)
    basis = partition_basis(a.part, rng)
    prods30 = plan30(X[:, :, OUTS30], basis, a.secs, a.seed, log)
    # shipped LSB products
    planf = os.path.join(a.out, f'plan_{a.k}.txt')
    import contextlib
    import io
    argv = sys.argv
    sys.argv = ['x', a.base, str(a.k), a.out]
    with contextlib.redirect_stdout(io.StringIO()):
        ep.main()
    sys.argv = argv
    terms = [(int(p), int(x, 16), int(b, 16), int(s, 16)) for p, x, b, s in (l.split() for l in open(planf))]
    byp = collections.defaultdict(list)
    for t in terms:
        byp[t[0]].append(t)
    lsbmask = sum(1 << l for l in LSB)
    allmask = (1 << 40) - 1
    keep = []
    for p, ts in byp.items():
        s = ts[0][3]
        if s & lsbmask:
            if s & ~lsbmask & allmask:
                log(f'WARNING shipped LSB product {p} also feeds upper outputs: s={s:x}')
            keep.append(ts)
    log(f'shipped LSB products kept: {len(keep)}')
    products = []
    for ts in keep:
        (p, a1, b1, s) = ts[0]
        if len(ts) > 1:
            (_, a2, b2, _) = ts[1]
        else:
            a2, b2 = 0, 0
        f, g = tt_from(a1, b2), tt_from(a2, b1)
        products.append((f, g, [11 + w for w in range(40) if s >> w & 1]))
    for a1, b1, a2, b2, s in prods30:
        f, g = tt_from(a1, b2), tt_from(a2, b1)
        wires = [11 + OUTS30[o] for o in range(30) if s >> o & 1]
        products.append((f, g, wires))
    log(f'total products {len(products)}')
    dst = os.path.join(a.out, f'angle_k_{a.k}.kmb')
    c = emit.rebuild(os.path.join(a.base, f'angle_k_{a.k}.kmb'), words, a.k, products, dst, log=log)
    stats = c.operation_statistics()
    log(f'emitted T={stats.num_toffoli_like} Q={c.num_qubits}')


if __name__ == '__main__':
    main()
