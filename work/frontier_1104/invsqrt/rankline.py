#!/usr/bin/env python3
"""GF(2) rank of live wire columns plus constant at each op, to find linear redundancy among wires."""
import sys
import numpy as np
import bsim
ops, _ = bsim.parse_kmx(sys.argv[1])
rng = np.random.default_rng(1)
xs = np.concatenate([np.tile(np.arange(1, 8193, dtype=np.uint64), 1), rng.integers(1, bsim.MAX_X + 1, 16384, dtype=np.uint64)])
xs = xs[:len(xs) // 64 * 64]
s = bsim.State(xs, 12)
col = lambda a: int.from_bytes(a.tobytes(), 'little')
allset = col(np.full(s.w, bsim.ONES, dtype=np.uint64))
rows = []
def rank():
    piv = {}
    r = 0
    for v in [allset] + [col(s.q[k]) for k in range(62)]:
        while v:
            h = v.bit_length() - 1
            p = piv.get(h)
            if p is None:
                piv[h] = v; r += 1; break
            v ^= p
    return r - 1
for i, op in enumerate(ops):
    bsim.step(s, op)
    if i % 10 == 0:
        live = int(s.q.any(axis=1).sum())
        rows.append((op.line, live, rank()))
rows = np.array(rows)
np.save(sys.argv[2], rows)
print('max rank', rows[:, 2].max(), 'max live', rows[:, 1].max())
for t in (62, 61, 60, 59):
    m = rows[:, 2] >= t
    print('rank>=', t, 'samples', int(m.sum()), 'first/last lines', rows[m, 0][:1], rows[m, 0][-1:])
ms = rows[:, 2] >= 61
runs = []
st = None
for i, v in enumerate(ms):
    if v and st is None:
        st = i
    if not v and st is not None:
        runs.append((int(rows[st, 0]), int(rows[i - 1, 0]))); st = None
print('rank>=61 windows', runs[:60])
print('live-rank gap at live>=61:', np.unique((rows[:, 1] - rows[:, 2])[rows[:, 1] >= 61], return_counts=True))
