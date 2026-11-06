#!/usr/bin/env python3
"""For each full ladder: rank of its cubic terms modulo quadratic forms of live wires at the ladder's start."""
import sys
import numpy as np
import bsim
from deltest import parse_ladders, MONO, to_int
ops, _ = bsim.parse_kmx(sys.argv[1])
lads = parse_ladders(ops)
seen = set()
rng = np.random.default_rng(3)
xs = np.concatenate([np.arange(1, 16385, dtype=np.uint64), rng.integers(1, bsim.MAX_X + 1, 16384, dtype=np.uint64)])
xs = xs[:len(xs) // 64 * 64]
for L in lads:
    key = (L['f1'], L['f2'], L['line'] // 1000)
    if key in seen:
        continue
    seen.add(key)
    s = bsim.State(xs, 7)
    for op in ops:
        if op.line == L['line']:
            break
        bsim.step(s, op)
    wires = [to_int(s.q[k]) for k in range(62)]
    allset = to_int(np.full(s.w, bsim.ONES, dtype=np.uint64))
    piv = {}
    def add(v):
        while v:
            h = v.bit_length() - 1
            p = piv.get(h)
            if p is None:
                piv[h] = v
                return True
            v ^= p
        return False
    add(allset)
    for a in range(62):
        if wires[a]:
            add(wires[a])
    for a in range(62):
        for b in range(a + 1, 62):
            if wires[a] and wires[b]:
                add(wires[a] & wires[b])
    q = len(piv)
    ff = wires[L['f1']] & wires[L['f2']]
    r = 0
    for w, beta in L['betas']:
        if add(ff & wires[w]):
            r += 1
    print('ladder', L['line'], (L['f1'], L['f2']), 'wires', len(L['betas']), 'flag pop', bin(ff).count('1'), 'quad dim', q, 'quotient rank', r, flush=True)
