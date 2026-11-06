#!/usr/bin/env python3
"""Per-op count of wires that are nonzero on any shot, so free wires can be located."""
import sys
import numpy as np
import bsim
ops, _ = bsim.parse_kmx(sys.argv[1])
rng = np.random.default_rng(1)
xs = np.concatenate([np.tile(np.arange(1, 4097, dtype=np.uint64), 4), rng.integers(1, bsim.MAX_X + 1, 49152, dtype=np.uint64)])
xs = xs[:len(xs) // 64 * 64]
s = bsim.State(xs, 12)
lines = []
counts = []
for op in ops:
    bsim.step(s, op)
    lines.append(op.line)
    counts.append(int(s.q.any(axis=1).sum()))
counts = np.array(counts); lines = np.array(lines)
np.save(sys.argv[2], np.stack([lines, counts]))
print('peak', counts.max(), 'ops at peak', int((counts == counts.max()).sum()))
for t in (62, 61, 60):
    m = counts >= t
    runs = []
    st = None
    for i, v in enumerate(m):
        if v and st is None:
            st = i
        if not v and st is not None:
            runs.append((int(lines[st]), int(lines[i - 1]))); st = None
    if st is not None:
        runs.append((int(lines[st]), int(lines[-1])))
    print('>=', t, 'windows', len(runs), runs[:40])
for a, b in [(0, 1800), (1800, 15270), (15270, 15800), (15800, 23800), (23800, 25800), (25800, 26200), (26200, 29000), (29000, 31200), (31200, 36000), (36000, 44000), (44000, 48400)]:
    sel = (lines >= a) & (lines < b)
    print(a, b, 'min', counts[sel].min(), 'mean %.1f' % counts[sel].mean(), 'max', counts[sel].max())
