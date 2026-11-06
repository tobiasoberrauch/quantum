#!/usr/bin/env python3
"""Can two rare flag products be merged? Exclusive flags with every target a linear form of deterministic wires on the support."""
import sys
import numpy as np
import bsim
ops, _ = bsim.parse_kmx(sys.argv[1])
line = int(sys.argv[2]); f0, a, b = [int(v) for v in sys.argv[3].split(',')]
xs = np.tile(bsim.domain()[:262144], 1)
xs = np.tile(np.arange(1, 1 << 15, dtype=np.uint64), 4)
xs = xs[:len(xs) // 64 * 64]
states = []
for sd in (1, 2, 3):
    s = bsim.State(xs, sd)
    for op in ops:
        if op.line == line:
            break
        bsim.step(s, op)
    states.append(s)
s = states[0]
un = lambda p: s.unpack(p).astype(bool)
qa, qb, qf = un(s.q[a]), un(s.q[b]), un(s.q[f0])
Sa = qf & qa; Sb = qf & qb
print('|f&a| x:', sorted(set(xs[Sa].tolist()))[:40], 'n', len(set(xs[Sa].tolist())))
print('|f&b| x:', sorted(set(xs[Sb].tolist()))[:40], 'n', len(set(xs[Sb].tolist())))
print('f&a&b count', int((Sa & Sb).sum()))
sup = Sa | Sb
ux = sorted(set(xs[sup].tolist()))
first = {}
for i, x in enumerate(xs.tolist()):
    if x not in first:
        first[x] = i
idx = [first[x] for x in ux]
# deterministic wires on support across seeds and replicates
det = []
mat = []
for k in range(62):
    vals = [st.unpack(st.q[k]).astype(np.uint8) for st in states]
    ok = True
    for x in ux:
        pos = np.flatnonzero(xs == x)
        v = np.concatenate([vv[pos] for vv in vals])
        if v.min() != v.max():
            ok = False
            break
    if ok:
        det.append(k)
        mat.append(vals[0][idx])
print('deterministic wires', len(det), det)
M = np.array(mat)
def rk(M):
    rows = [int(''.join(map(str, r.tolist())), 2) for r in M]
    piv = {}; r = 0
    for v in rows:
        while v:
            h = v.bit_length() - 1
            if h in piv: v ^= piv[h]
            else: piv[h] = v; r += 1; break
    return r
print('support x', len(ux), 'rank of deterministic wires on support', rk(M), 'plus constant', rk(np.vstack([M, np.ones(len(ux), dtype=np.uint8)])))
W = [int(v) for v in sys.argv[4].split(',')] if len(sys.argv) > 4 else []
def reduce_basis(M):
    piv = {}
    for r in M:
        v = int(''.join(map(str, r.tolist())), 2)
        while v:
            h = v.bit_length() - 1
            if h in piv: v ^= piv[h]
            else: piv[h] = v; break
    return piv
def in_span(piv, t):
    v = int(''.join(map(str, t.tolist())), 2)
    while v:
        h = v.bit_length() - 1
        if h not in piv: return False
        v ^= piv[h]
    return True
mm = np.vstack([M, np.ones(len(ux), dtype=np.uint8)])
piv = reduce_basis(mm)
aa = np.array([un(s.q[a])[i] for i in idx], dtype=np.uint8)
bb = np.array([un(s.q[b])[i] for i in idx], dtype=np.uint8)
bad = []
for w in W:
    t = np.array([un(s.q[w])[i] for i in idx], dtype=np.uint8)
    ok1 = in_span(piv, t & aa); ok2 = in_span(piv, t & bb)
    if not (ok1 and ok2):
        bad.append((w, ok1, ok2))
print('targets not in span', bad, 'of', len(W))
print('dim complement', len(ux) - len(piv))
