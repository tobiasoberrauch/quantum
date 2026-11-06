#!/usr/bin/env python3
"""Additive phase effect of each q21 gate deletion on x<64; find largest deletable subset."""
import itertools, json, sys
import numpy as np
import bsim
ops, _ = bsim.parse_kmx('inputs/base.kmx')
idx = {o.line: i for i, o in enumerate(ops)}
cands = [25880,25891,25902,25912,25922,25933,25944,25955,25967,25980,25993,26005,26016]
cands = [l for l in cands if ops[idx[l]].kind == 'CCX']
xs = np.tile(np.arange(1, 65, dtype=np.uint64), 16)
def phase(g):
    s = bsim.State(xs, 5)
    for i, op in enumerate(ops):
        if i == g:
            continue
        if op.kind == 'Z_POW' or True:
            bsim.step(s, op)
    return s
s0 = phase(-1)
u0 = s0.units[:64].copy()
tgt, tol = bsim.reference(xs[:64])
err0 = (u0 + s0.unpack(s0.sign)[:64].astype(np.uint64) * np.uint64(0) - tgt).view(np.int64)
# use the sign-free part only: the sign part in the base is zero mod Clifford consistency, so take full phase from check
from_full = (bsim.phase_units(s0)[:64] - tgt).view(np.int64)
D = {}
for l in cands:
    s = phase(idx[l])
    D[l] = (s.units[:64] - u0).view(np.int64).astype(np.float64)
    print(l, ops[idx[l]].raw, 'nonzero', int((D[l] != 0).sum()), 'maxabs %.3e' % np.abs(D[l]).max())
E = from_full.astype(np.float64)
T = tol.astype(np.float64)
C = 58597850
print('base min margin on x<=64', (T - np.abs(E)).min())
best = []
for r in range(1, len(cands) + 1):
    for sub in itertools.combinations(cands, r):
        e = E + sum(D[l] for l in sub)
        m = (T - np.abs(e)).min()
        if m >= C:
            best.append((r, sub, m))
best.sort(key=lambda t: (-t[0], -t[2]))
print('feasible subsets', len(best))
for b in best[:30]:
    print(b)
