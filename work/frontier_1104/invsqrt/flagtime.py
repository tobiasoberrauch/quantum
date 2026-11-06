#!/usr/bin/env python3
"""For each CCZ ladder's flag pair, find every program point where the flag AND is a linear form of live wires."""
import json, sys
import numpy as np
import bsim
from census import in_span
ops, _ = bsim.parse_kmx(sys.argv[1])
xs = bsim.domain()
rng = np.random.default_rng(2)
sample = np.unique(np.concatenate([np.arange(280), rng.choice(len(xs) // 64, 40, replace=False)]))
col = lambda a: int.from_bytes(a.tobytes(), 'little')
groups = {}
for o in ops:
    if o.kind == 'CCZ' and 15700 < o.line < 31000:
        k = o.q[:2]
        groups.setdefault(k, []).append(o.line)
# split groups by contiguity
seq = []
for k, ls in groups.items():
    ls.sort()
    cur = [ls[0]]
    for l in ls[1:]:
        if l - cur[-1] > 200:
            seq.append((k, cur)); cur = [l]
        else:
            cur.append(l)
    seq.append((k, cur))
seq = [s for s in seq if len(s[1]) >= 4]
print('ladders', [(k, l[0], l[-1], len(l)) for k, l in seq])
flags = {}
first = {l[0]: (k, l[0]) for k, l in seq}
hits = {k_l: [] for k_l in first.values()}
def hook(i, op, s):
    if op.line in first:
        k, l0 = first[op.line]
        flags[(k, l0)] = s.q[k[0]] & s.q[k[1]]
    if i % 12 == 0 and op.line > 200:
        pass
s = bsim.run(ops, xs, seed=4, hook=hook)
print('flag popcounts', {k: bsim.popcount(v) for k, v in flags.items()})
def hook2(i, op, s):
    if i % 10 or op.line < 60:
        return
    sub = s.q[:, sample]
    cols = [col(sub[j]) for j in range(62)]
    allset = col(np.full(len(sample), bsim.ONES, dtype=np.uint64))
    for key, v in flags.items():
        ok, sol = in_span(cols + [allset], col(v[sample]), allset)
        if ok:
            w = np.zeros(s.w, dtype=np.uint64)
            for j in sol:
                w ^= s.q[j] if j < 62 else bsim.ONES
            if np.array_equal(w, v):
                hits[key].append((op.line, sol))
s = bsim.run(ops, xs, seed=4, hook=hook2)
for key, h in hits.items():
    if not h:
        print(key, 'NO HIT'); continue
    runs = []
    st = h[0][0]; prev = h[0][0]
    for ln, _ in h[1:]:
        if ln - prev > 40:
            runs.append((st, prev)); st = ln
        prev = ln
    runs.append((st, prev))
    print(key, 'runs', runs, 'example', h[0], h[-1])
