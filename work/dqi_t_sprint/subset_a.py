"""Subset-A quantification: pebbling pairs CCX(a,b,c);CCX(a,b,c) where BOTH
controls a,b are classically known at p1 (last R/HMR on each, no value op
since). Such a pair is eliminable: measure c (HMR -> m), drop both CCXs,
redirect c's in-interval uses to classical bit m (value-uses -> _IF CX free;
phase-uses -> _IF CCZ, saving P(m=1) on average), restore c with X^m (free).
Saves 2 Toffolis per pair (static), plus conditional-phase savings.

Also dumps example contexts for manual inspection.
"""
import importlib.util
import json
import sys
import bisect
from collections import Counter, defaultdict

import numpy as np

ROOT = '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum'
KMB = f'{ROOT}/work/frontier_scan/mwa_unpacked/dqi.kmb'

spec = importlib.util.spec_from_file_location('wl', f'{ROOT}/work/dqi_sources/width_liveness.py')
wl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wl)

r = wl.KmbReader(KMB)
t = r.types
N = r.num_ops
nq = r.num_qubits

TOP = ['extract', 'synthesis', 'convert', 'scan', 'unconvert', 'unsynthesis', 'unextract']
tagpos = np.flatnonzero(t == 0x06)
ranges = {}
for p, s in zip(tagpos.tolist(), r.tag_strings):
    name = s.split(':', 1)[1]
    if s.startswith('@enter:') and name in TOP:
        ranges[name] = [p, None]
    elif s.startswith('@exit:') and name in TOP and ranges[name][1] is None:
        ranges[name][1] = p + 1
bounds = sorted((ranges[n][0], ranges[n][1], n) for n in TOP)
los = [b[0] for b in bounds]


def top_block(p):
    i = bisect.bisect_right(los, p) - 1
    if i < 0:
        return '<pre>'
    lo, hi, name = bounds[i]
    return name if p < hi else '<post>'


VAL1Q = {0x11, 0x91}
RST1Q = {0x12, 0x92, 0x50, 0xD0}
pos1all = np.flatnonzero(np.isin(t, [0x10, 0x90, 0x11, 0x91, 0x12, 0x92, 0x13, 0x93, 0x50, 0xD0])).astype(np.int64)
q1all = r.q1.astype(np.int64)
pos1 = np.flatnonzero(np.isin(t, list(VAL1Q) + list(RST1Q))).astype(np.int64)
idx1 = np.searchsorted(pos1all, pos1)
q1 = q1all[idx1]
t1 = t[pos1].astype(np.int64)

val_by_q = [[] for _ in range(nq)]
know_by_q = [[] for _ in range(nq)]  # R/HMR positions (value becomes known)
for p, q, tt in zip(pos1.tolist(), q1.tolist(), t1.tolist()):
    if tt in RST1Q:
        know_by_q[q].append(p)
    else:
        val_by_q[q].append(p)

l2 = np.zeros(256, dtype=bool); l2[[0x21, 0xA1, 0x22, 0xA2]] = True
pos2 = np.flatnonzero(l2[t]).astype(np.int64)
q2a = r.q2a.astype(np.int64); q2b = r.q2b.astype(np.int64)
t2 = t[pos2].astype(np.int64)
for p, qa, qb, tt in zip(pos2.tolist(), q2a.tolist(), q2b.tolist(), t2.tolist()):
    if tt in (0x21, 0xA1):
        val_by_q[qb].append(p)
    else:
        val_by_q[qa].append(p)
        val_by_q[qb].append(p)

l3f = np.zeros(256, dtype=bool); l3f[[0x30, 0xB0, 0x31, 0xB1, 0x32, 0xB2]] = True
pos3 = np.flatnonzero(l3f[t]).astype(np.int64)
q3a = r.q3a.astype(np.int64); q3b = r.q3b.astype(np.int64); q3c = r.q3c.astype(np.int64)
t3 = t[pos3].astype(np.int64)
for p, qa, qb, qc, tt in zip(pos3.tolist(), q3a.tolist(), q3b.tolist(), q3c.tolist(), t3.tolist()):
    if tt in (0x31, 0xB1):
        val_by_q[qc].append(p)
    else:
        val_by_q[qb].append(p)
        val_by_q[qc].append(p)

for q in range(nq):
    val_by_q[q].sort()
    know_by_q[q].sort()


def known_at(q, p):
    """q's value is classically known at position p: last know-event < p with no
    value op between it and p."""
    ks = know_by_q[q]
    j = bisect.bisect_left(ks, p) - 1
    if j < 0:
        return False
    last_know = ks[j]
    vs = val_by_q[q]
    k = bisect.bisect_right(vs, last_know)
    return k >= len(vs) or vs[k] >= p


# pebbling pairs
lccx = np.zeros(256, dtype=bool); lccx[[0x31, 0xB1]] = True
posc = np.flatnonzero(lccx[t]).astype(np.int64)
i3 = np.searchsorted(pos3, posc)
A = r.q3a[i3].astype(np.int32); B = r.q3b[i3].astype(np.int32); C = r.q3c[i3].astype(np.int32)

triples = defaultdict(list)
for idx in range(len(posc)):
    triples[(int(A[idx]), int(B[idx]), int(C[idx]))].append(int(posc[idx]))

stats = Counter()
examples = defaultdict(list)
for (a_, b_, c_), poss in triples.items():
    rs = know_by_q[c_]  # resets of c split independent runs
    runs = [[poss[0]]]
    for i in range(len(poss) - 1):
        p1, p2 = poss[i], poss[i + 1]
        j = bisect.bisect_right(rs, p1)
        if j < len(rs) and rs[j] < p2:
            runs.append([p2])
        else:
            runs[-1].append(p2)
    for run in runs:
        m = len(run)
        for i in range(m // 2):
            p1, p2 = run[2 * i], run[2 * i + 1]
            blk = top_block(p1)
            ka = known_at(a_, p1)
            kb = known_at(b_, p1)
            kc = known_at(c_, p1)
            key = (blk, 'A' if (ka and kb) else 'B')
            stats[key] += 1
            if ka and kb and kc:
                stats[(blk, 'Akc')] += 1
            if ka and kb and len(examples[key]) < 6:
                examples[key].append((a_, b_, c_, p1, p2))

print('pebbling pairs by block / control-knownness:')
print('  A: both controls known at p1 (eliminable, 2 Toffolis each)')
print(f'{"block":14} {"A":>8} {"other":>8}')
totA = 0
for blk in TOP + ['<pre>', '<post>']:
    va = stats.get((blk, 'A'), 0)
    akc = stats.get((blk, 'Akc'), 0)
    vo = stats.get((blk, 'B'), 0)
    totA += va
    if va or vo:
        print(f'{blk:14} {va:>8} (target-known {akc}) {vo:>8}')
print(f'TOTAL eliminable pairs: {totA} -> static savings {2*totA} Toffolis = {100*2*totA/397194:.2f}% of T')

# how often are targets also known (fresh-ish data)?
print('\nexamples (a,b,c,p1,p2):')
for key, ex in examples.items():
    print(key)
    for e in ex[:4]:
        print('   ', e)

# interval analysis for subset A: what happens to c between p1 and p2?
# (uses of c as control: value vs phase) — sample up to 2000 pairs
lccz = np.zeros(256, dtype=bool); lccz[[0x30, 0xB0]] = True
poscz = np.flatnonzero(lccz[t]).astype(np.int64)
ic = np.searchsorted(pos3, poscz)
ZA = r.q3a[ic].astype(np.int64); ZB = r.q3b[ic].astype(np.int64); ZC = r.q3c[ic].astype(np.int64)
# index CCZ by qubit
ccz_by_q = defaultdict(list)
for i in range(len(poscz)):
    for q in (int(ZA[i]), int(ZB[i]), int(ZC[i])):
        ccz_by_q[q].append((int(poscz[i]), int(ZA[i]), int(ZB[i]), int(ZC[i])))
for q in ccz_by_q:
    ccz_by_q[q].sort()

# CCX control uses of c between p1,p2:
ccx_by_q_ctrl = defaultdict(list)
for idx in range(len(posc)):
    ccx_by_q_ctrl[int(A[idx])].append((int(posc[idx]), int(A[idx]), int(B[idx]), int(C[idx])))
    ccx_by_q_ctrl[int(B[idx])].append((int(posc[idx]), int(A[idx]), int(B[idx]), int(C[idx])))
for q in ccx_by_q_ctrl:
    ccx_by_q_ctrl[q].sort()

use_stats = Counter()
checked = 0
for (a_, b_, c_), poss in triples.items():
    if checked >= 2000:
        break
    rs = know_by_q[c_]
    runs = [[poss[0]]]
    for i in range(len(poss) - 1):
        p1, p2 = poss[i], poss[i + 1]
        j = bisect.bisect_right(rs, p1)
        if j < len(rs) and rs[j] < p2:
            runs.append([p2])
        else:
            runs[-1].append(p2)
    for run in runs:
        m = len(run)
        for i in range(m // 2):
            p1, p2 = run[2 * i], run[2 * i + 1]
            if not (known_at(a_, p1) and known_at(b_, p1)):
                continue
            checked += 1
            # c's uses in (p1,p2): CCX as control (value), CCZ as any leg (phase), CSWAP (value)
            nv = np = 0
            for (p, x, y, z) in ccx_by_q_ctrl.get(c_, []):
                if p1 < p < p2:
                    nv += 1
            for (p, x, y, z) in ccz_by_q.get(c_, []):
                if p1 < p < p2:
                    np += 1
            use_stats['value_uses'] += nv
            use_stats['phase_uses'] += np
            use_stats['pairs_checked'] += 1

print(f'\ninterval-use sample ({use_stats["pairs_checked"]} subset-A pairs):')
print(f'  avg value-uses of c in interval: {use_stats["value_uses"]/max(1,use_stats["pairs_checked"]):.2f}')
print(f'  avg phase-uses of c in interval: {use_stats["phase_uses"]/max(1,use_stats["pairs_checked"]):.2f}')
r.close()
