#!/usr/bin/env python3
"""Exact checks of two tail CCZ-to-CZ identities with block conditions forced open, full domain, many seeds."""
import sys
import numpy as np
import bsim
ops, _ = bsim.parse_kmx(sys.argv[1])
line_of = {}
for o in ops:
    if o.kind == 'HMR':
        line_of.setdefault(o.bit, []).append(o.line)
print({b: line_of[b] for b in (8045, 319, 320, 322, 8149, 8046) if b in line_of})
xs = bsim.domain()
tests = [
    ('CCZ q24 q11 q10 if b8149', (10, 23), {8045: 1, 319: 1, 8149: 1}),
    ('CCZ q19 q11 q10 if b8245', (10, 19), {8045: 1, 319: 0, 320: 1, 322: 0}),
]
for raw, pair, want in tests:
    force = {}
    for b, v in want.items():
        for ln in line_of.get(b, []):
            force[ln] = v
    g = next(i for i, o in enumerate(ops) if o.raw == raw)
    mism = 0
    fired = 0
    for sd in range(1, 9):
        s = bsim.State(xs, sd * 17)
        for i, op in enumerate(ops[:g]):
            bsim.step(s, op, None, force)
        a = ops[g].q
        v = s.q[a[0]] & s.q[a[1]] & s.q[a[2]]
        w = s.q[pair[0]] & s.q[pair[1]]
        mask = s.base if s.base is not None else np.full(s.w, bsim.ONES, dtype=np.uint64)
        c = s.bits[ops[g].cond]
        fired += bsim.popcount(mask & c)
        mism += bsim.popcount((v ^ w) & mask & c)
        print(raw, 'seed', sd, 'fired', bsim.popcount(mask & c), 'pop', bsim.popcount(v & mask & c), 'mismatch', bsim.popcount((v ^ w) & mask & c), flush=True)
    print('TOTAL', raw, 'fired', fired, 'mismatch', mism, flush=True)
