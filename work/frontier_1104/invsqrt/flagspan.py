#!/usr/bin/env python3
"""For each CCZ/CCX pair of controls: is the pairwise AND a linear form of live wires on the full domain?"""
import sys
import numpy as np
import bsim
from census import in_span
ops, _ = bsim.parse_kmx(sys.argv[1])
xs = bsim.domain()
rng = np.random.default_rng(1)
sample = np.unique(np.concatenate([np.arange(32), rng.choice(len(xs) // 64, 48, replace=False)]))
col = lambda a: int.from_bytes(a.tobytes(), 'little')
hits = []
seen = set()
def hook(i, op, s):
    if op.kind not in ('CCZ', 'CCX', 'CSWAP'):
        return
    a = op.q
    if op.kind == 'CCX':
        pairs = [(a[0], a[1])]
    elif op.kind == 'CCZ':
        pairs = [(a[0], a[1]), (a[0], a[2]), (a[1], a[2])]
    else:
        return
    sub = s.q[:, sample]
    cols = [col(sub[j]) for j in range(62)]
    allset = col(np.full(len(sample), bsim.ONES, dtype=np.uint64))
    for u, v in pairs:
        m = s.q[u] & s.q[v]
        ok, sol = in_span(cols + [allset], col(m[sample]), allset)
        if not ok:
            continue
        w = np.zeros(s.w, dtype=np.uint64)
        for j in sol:
            w ^= s.q[j] if j < 62 else bsim.ONES
        if np.array_equal(w, m):
            hits.append((op.line, op.raw, u, v, sol, bsim.popcount(m) / s.n))
bsim.run(ops, xs, seed=3, hook=hook)
print('hits', len(hits))
for h in hits[:200]:
    print(h)
