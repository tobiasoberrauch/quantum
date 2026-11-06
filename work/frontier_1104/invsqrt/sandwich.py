#!/usr/bin/env python3
"""Find conditional CCZ gates that can become CZ sandwiches around an unconditional Toffoli.

Conditional CCZ(a,c,z) if b equals CZ(z,u) if b; CCX(a,c,u); CZ(z,u) if b when the CCX runs after b is known
and a*c matches the CCX's AND modulo linear forms. Search over the whole circuit, on the shots of the block.
"""
import json, sys
import numpy as np
import bsim
ops, _ = bsim.parse_kmx(sys.argv[1])
rng = np.random.default_rng(11)
xs = np.concatenate([np.arange(1, 4097, dtype=np.uint64), rng.integers(1, bsim.MAX_X + 1, 20480, dtype=np.uint64)])
xs = xs[:len(xs) // 64 * 64]
to_int = lambda a: int.from_bytes(a.tobytes(), 'little')
hmr_line = {}
for o in ops:
    if o.kind == 'HMR':
        hmr_line.setdefault(o.bit, []).append(o.line)
# pass 1: collect conditional CCZ data
tasks = []
s = bsim.State(xs, 31)
top_bit = []
for i, op in enumerate(ops):
    if op.kind == 'PUSH_CONDITION':
        top_bit.append(op.cond)
    elif op.kind == 'POP_CONDITION':
        top_bit.pop()
    if op.kind == 'CCZ':
        mask = s.base
        if op.cond >= 0:
            b = s.bits.get(op.cond, s.zero)
            mask = b if mask is None else mask & b
        if mask is not None and bsim.popcount(mask) / s.n >= 0.05:
            bits = list(top_bit) + ([op.cond] if op.cond >= 0 else [])
            a = op.q
            for (u, w, z) in ((a[0], a[1], a[2]), (a[0], a[2], a[1]), (a[1], a[2], a[0])):
                tasks.append(dict(i=i, line=op.line, raw=op.raw, fire=bsim.popcount(mask) / s.n, bits=bits,
                                  v=to_int((s.q[u] & s.q[w]) & mask), z=to_int(s.q[z] & mask), mask=mask.copy(), pair=(u, w), third=z))
    bsim.step(s, op)
print('ccz tasks', len(tasks), flush=True)
# pass 2
s = bsim.State(xs, 31)
hits = []
for i, op in enumerate(ops):
    if op.kind in ('CCX', 'CSWAP') and s.base is None and op.cond < 0 and i % 1 == 0:
        a = op.q
        ve = s.q[a[0]] & (s.q[a[1]] if op.kind == 'CCX' else s.q[a[1]] ^ s.q[a[2]])
        for t in tasks:
            latest = max((max(hmr_line.get(b, [-1])) for b in t['bits']), default=-1)
            if op.line <= latest:
                continue
            m = t['mask']
            basis = {}
            for v in [to_int(s.q[k] & m) for k in range(62)] + [to_int(m)]:
                while v:
                    h = v.bit_length() - 1
                    p = basis.get(h)
                    if p is None:
                        basis[h] = v
                        break
                    v ^= p
            def red(v):
                while True:
                    done = True
                    for h in sorted(basis, reverse=True):
                        if (v >> h) & 1:
                            v ^= basis[h]
                    return v
            if red(t['z']) != 0:
                continue
            d = t['v'] ^ to_int(ve & m)
            if red(d) == 0:
                hits.append((t['line'], t['raw'], round(t['fire'], 3), t['pair'], t['third'], op.line, op.raw))
                print(hits[-1], flush=True)
    bsim.step(s, op)
print('hits', len(hits))
