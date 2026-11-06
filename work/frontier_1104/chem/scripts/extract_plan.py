#!/usr/bin/env python3
"""Extract rank-one term list (a(y)[76 bits], b(z)[15 bits], s[35 bits]) for a loader; check it equals the delta tensor.
Writes <out>/plan_k.txt: lines 'pid a_hex b s_hex', pid = product id. Output bits: 7 per word (bit 0..6) => 35; bit7 tied to bit6.
"""
from __future__ import annotations

import collections
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
import tensor_probe as tp  # noqa: E402

N = 1220
ADDR = np.arange(N)
Y = ADDR >> 4
Z = ADDR & 15


def to_ab(f):
    """f additive on legal addresses -> (a over y=1..76 relative to y=0), (b over z=1..15 relative to z=0), const."""
    ya = np.zeros(77, dtype=bool)
    zb = np.zeros(16, dtype=bool)
    # f(y,z) = A(y)+a(z); anchor via y=0 row and z=0 column
    zb[:] = f[Z == Z][:16]  # addresses 0..15 are y=0
    c0 = f[0]
    zb = zb ^ c0
    for y in range(77):
        ya[y] = f[16 * y] ^ c0
    return ya[1:], zb[1:], bool(c0)


def tensor_of_words(words, k):
    """Delta tensor X[y-1,z-1,o] with o in 0..34."""
    d = words[:, 5 * k:5 * k + 5].copy()
    if k > 0:
        d = d ^ words[:, 5 * (k - 1):5 * k]
    bits = np.zeros((N, 40), dtype=bool)
    for j in range(5):
        for b in range(8):
            bits[:, 8 * j + b] = (d[:, j] >> b) & 1
    tie = all((bits[:, 8 * j + 6] == bits[:, 8 * j + 7]).all() for j in range(5))
    grid = np.zeros((77, 16, 40), dtype=bool)
    known = np.zeros((77, 16), dtype=bool)
    grid[Y, Z] = bits
    known[Y, Z] = True
    # padding entries (y=76,z>=4) are don't care: mark by filling z-anchor-consistent zero
    X = grid[1:, 1:] ^ grid[:1, 1:] ^ grid[1:, :1] ^ grid[:1, :1]
    X[75, 3:] = False  # don't care cells cleared (compared with a mask)
    return X, tie


def main():
    base, k, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    words = np.load(base + '/submission.npz')['angle_words']
    ops, nq = tp.load_ops(f'{base}/angle_k_{k}.kmb')
    st, rec = tp.simulate(ops, nq, words, k)
    # symbolic fan-out: track product symbols through linear ops
    sym = [0] * nq
    pid = 0
    pids = {}
    rec_i = {r['i']: r for r in rec}
    for i, (op, q) in enumerate(ops):
        if op == 'CX':
            sym[q[1]] ^= sym[q[0]]
        elif op == 'R':
            sym[q[0]] = 0
        elif op == 'CCX':
            if 11 <= q[2] < 51:
                pids[i] = pid
                sym[q[2]] ^= (1 << pid)
                pid += 1
            else:
                pass
        elif op == 'HMR':
            sym[q[0]] = 0
    prods = []
    for r in rec:
        if r['i'] not in pids:
            continue
        pidx = pids[r['i']]
        s = 0
        s40 = []
        for w in range(40):
            if (sym[11 + w] >> pidx) & 1:
                s40.append(w)
        prods.append((pidx, r, s40))
    X, tie = tensor_of_words(words, k)
    print('tie b6=b7 on delta', tie, 'products', len(prods))
    # recon on 40 outputs
    R = np.zeros_like(X)
    terms = []
    bit7only = 0
    for pidx, r, s40 in prods:
        Aa, ab, _ = to_ab(r['fa'])
        Ba, bb, _ = to_ab(r['fb'])
        sv = np.zeros(40, dtype=bool)
        sv[s40] = True
        R ^= (Aa[:, None] & bb[None, :])[:, :, None] & sv[None, None, :]
        R ^= (Ba[:, None] & ab[None, :])[:, :, None] & sv[None, None, :]
        terms.append((pidx, Aa, bb, sv))
        terms.append((pidx, Ba, ab, sv))
    mask = np.ones(X.shape[:2], dtype=bool)
    mask[75, 3:] = False
    diff = (R ^ X)[mask]
    print('recon mismatch bits', int(diff.sum()), 'of', diff.size)
    per_o = (R ^ X)[mask].sum(axis=0)
    print('mismatch per output', per_o.tolist())
    with open(f'{out}/plan_{k}.txt', 'w') as f:
        n = 0
        for pidx, a, b, s in terms:
            if a.any() and b.any():
                ah = sum(1 << int(i) for i in np.flatnonzero(a))
                bh = sum(1 << int(i) for i in np.flatnonzero(b))
                sh = sum(1 << int(i) for i in np.flatnonzero(s))
                f.write(f'{pidx} {ah:x} {bh:x} {sh:x}\n')
                n += 1
    print('rank-1 terms nonzero', n, 'unique a', len({(t[1].tobytes()) for t in terms}), 'unique b', len({t[2].tobytes() for t in terms}), 'unique s', len({t[3].tobytes() for t in terms}))
    cnt = collections.Counter(t[3].tobytes() for t in terms)
    print('class size dist', collections.Counter(cnt.values()))
    print('b top', collections.Counter(t[2].tobytes() for t in terms).most_common(3)[0][1])


if __name__ == '__main__':
    main()
