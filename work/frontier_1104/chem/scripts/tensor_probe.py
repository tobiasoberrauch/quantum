#!/usr/bin/env python3
"""Truth-table simulation of a loader at its legal forward input; products as (f,g,s) over addresses."""
from __future__ import annotations

import pickle
import sys

import kickmix as km
import numpy as np

N = 1220


def load_ops(path):
    c = km.Circuit.from_file(path, format='kmb')
    ops = []
    for l in str(c).splitlines():
        p = l.split()
        if p[0] in ('APPEND_TO_REGISTER', 'REGISTER'):
            continue
        ops.append((p[0], [int(x[1:]) for x in p[1:] if x.startswith('q')]))
    return ops, c.num_qubits


def simulate(ops, nq, words, k):
    st = np.zeros((nq, N), dtype=bool)
    addr = np.arange(N)
    for i in range(11):
        st[i] = (addr >> i) & 1
    if k > 0:
        for j in range(5):
            for b in range(8):
                st[11 + 8 * j + b] = (words[:, 5 * (k - 1) + j] >> b) & 1
    rec = []
    for i, (op, q) in enumerate(ops):
        if op == 'CX':
            st[q[1]] ^= st[q[0]]
        elif op == 'X':
            st[q[0]] = ~st[q[0]]
        elif op == 'R':
            st[q[0]] = False
        elif op == 'CCX':
            rec.append(dict(i=i, a=q[0], b=q[1], t=q[2], fa=st[q[0]].copy(), fb=st[q[1]].copy()))
            st[q[2]] ^= st[q[0]] & st[q[1]]
        elif op == 'HMR':
            st[q[0]] = False
        elif op == 'CZ':
            pass
        else:
            raise ValueError(op)
    return st, rec


if __name__ == '__main__':
    base, k = sys.argv[1], int(sys.argv[2])
    words = np.load(base + '/submission.npz')['angle_words']
    ops, nq = load_ops(f'{base}/angle_k_{k}.kmb')
    st, rec = simulate(ops, nq, words, k)
    # check final
    cols = words[:, 5 * k:5 * k + 5]
    ok = all(((cols[:, j] >> b) & 1 == st[11 + 8 * j + b]).all() for j in range(5) for b in range(8))
    print('final words correct', ok, 'wk clean', st[51:].any())
    y = np.arange(N) >> 4
    z = np.arange(N) & 15
    # decomposition of controls into A(y)+a(z): check function f has zero interaction: f(y,z)+f(y,0)+f(0,z)+f(0,0)=0
    def additive(f):
        tab = -np.ones((77, 16), dtype=int)
        tab[y, z] = f.astype(int)
        v = tab[:76]
        d = v ^ v[:, :1] ^ v[:1, :] ^ v[0, 0]
        return not d.any()
    na = [(additive(r['fa']), additive(r['fb'])) for r in rec]
    import collections
    print(collections.Counter(na))
    words2 = [r for r in rec if 11 <= r['t'] < 51]
    print('word target', len(words2), collections.Counter((r['t'] - 11) % 8 for r in words2))
    print('non-additive sample', [(r['a'], r['b'], r['t']) for r, x in zip(rec, na) if not all(x)][:20])
