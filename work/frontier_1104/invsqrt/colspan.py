#!/usr/bin/env python3
"""For each cluster 1 rotation control column, at which program points is it a linear form of live wires?"""
import sys
import numpy as np
import bsim, lpfit
from census import in_span
ops, _ = bsim.parse_kmx(sys.argv[1])
xs = bsim.domain()
a0, b, meta, s0, tol = lpfit.extract(ops, xs, seed=9)
packed = [np.packbits(b[j], bitorder='little').view(np.uint64) for j in range(b.shape[0])]
rng = np.random.default_rng(3)
sample = np.unique(np.concatenate([np.arange(260), rng.choice(len(xs) // 64, 60, replace=False)]))
col = lambda a: int.from_bytes(a.tobytes(), 'little')
tcols = {j: col(packed[j][sample]) for j in range(len(meta))}
hits = {j: [] for j in range(len(meta))}
step = int(sys.argv[2]) if len(sys.argv) > 2 else 40
def hook(i, op, s):
    if i % step:
        return
    sub = s.q[:, sample]
    cols = [col(sub[k]) for k in range(62)]
    allset = col(np.full(len(sample), bsim.ONES, dtype=np.uint64))
    # shared elimination
    piv = {}
    for idx, v in enumerate(cols + [allset]):
        tag = 1 << idx
        while v:
            h = v.bit_length() - 1
            if h in piv:
                v ^= piv[h][0]; tag ^= piv[h][1]
            else:
                piv[h] = (v, tag); break
    for j, t in tcols.items():
        v, tag = t, 0
        ok = True
        while v:
            h = v.bit_length() - 1
            if h not in piv:
                ok = False; break
            v ^= piv[h][0]; tag ^= piv[h][1]
        if ok:
            sol = [k for k in range(63) if (tag >> k) & 1]
            w = np.zeros(s.w, dtype=np.uint64)
            for k in sol:
                w ^= s.q[k] if k < 62 else bsim.ONES
            if np.array_equal(w, packed[j]):
                hits[j].append((op.line, sol))
bsim.run(ops, xs, seed=9, hook=hook)
for j, h in hits.items():
    if not h:
        print(j, meta[j].line, 'never'); continue
    runs = []
    st = prev = h[0][0]
    for ln, _ in h[1:]:
        if ln - prev > step * 3:
            runs.append((st, prev)); st = ln
        prev = ln
    runs.append((st, prev))
    print(j, meta[j].line, runs[:6], h[0][1], h[-1][1])
