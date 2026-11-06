#!/usr/bin/env python3
"""Is any CCZ's cubic value a quadratic form of live wires, so that it can become Clifford?"""
import json, sys
import numpy as np
import bsim
from deltest import solve_quad, phase_value
ops, _ = bsim.parse_kmx(sys.argv[1])
rng = np.random.default_rng(5)
xs = np.concatenate([np.tile(np.arange(1, 1025, dtype=np.uint64), 3), rng.integers(1, bsim.MAX_X + 1, 6400, dtype=np.uint64)])
xs = xs[:len(xs) // 64 * 64]
s = bsim.State(xs, 8)
hits = 0
n = 0
for op in ops:
    if op.kind == 'CCZ':
        v = phase_value(s, op)
        sol = solve_quad(s.q, v, None)
        n += 1
        if sol is not None:
            hits += 1
            print(op.line, op.raw, 'pop', bsim.popcount(v), 'sol', sol[:12], flush=True)
    bsim.step(s, op)
print('ccz', n, 'hits', hits)
