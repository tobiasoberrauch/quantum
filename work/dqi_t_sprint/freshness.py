"""Freshness analysis of pebbling pairs.

A pebbling pair CCX(a,b,c)@p1 ; CCX(a,b,c)@p2 (no reset of c between) is
HMR-convertible iff c is provably |0> just before p1, i.e. no value-modifying
op touched c since its last R/HMR. On basis-state inputs (verifier contract),
conversion = replace p2 by nothing, measure c after p1 (HMR, free), replay
c's control-uses as _IF ops on the measured bit, and (fresh case) no restore
needed. Saves exactly 1 Toffoli per converted pair (plus any conditional
phase-fixup _IF ops that may not execute on average).

Value-modifying ops on q (besides resets R/HMR):
  1q: X, X_IF
  2q: CX where q==target(q2b); SWAP where q in {q2a,q2b}
  3q: CCX where q==c3; CSWAP where q in {q3b,q3c}
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


# ---- collect value-op positions and reset positions per qubit ----
lut = lambda keys: np.frombuffer(bytes(keys).ljust(256, b'\x00'), dtype=np.uint8).astype(bool)
VAL1Q = {0x11, 0x91}
RST1Q = {0x12, 0x92, 0x50, 0xD0}

pos1all = np.flatnonzero(np.isin(t, [0x10, 0x90, 0x11, 0x91, 0x12, 0x92, 0x13, 0x93, 0x50, 0xD0])).astype(np.int64)
q1all = r.q1.astype(np.int64)
pos1 = np.flatnonzero(np.isin(t, list(VAL1Q) + list(RST1Q))).astype(np.int64)
idx1 = np.searchsorted(pos1all, pos1)
q1 = q1all[idx1]
t1 = t[pos1].astype(np.int64)

val_by_q = [[] for _ in range(nq)]   # value-modifying op positions (excl resets)
rst_by_q = [[] for _ in range(nq)]  # reset positions
for p, q, tt in zip(pos1.tolist(), q1.tolist(), t1.tolist()):
    if tt in RST1Q:
        rst_by_q[q].append(p)
    else:
        val_by_q[q].append(p)

l2 = np.zeros(256, dtype=bool); l2[[0x21, 0xA1, 0x22, 0xA2]] = True
pos2 = np.flatnonzero(l2[t]).astype(np.int64)
q2a = r.q2a.astype(np.int64); q2b = r.q2b.astype(np.int64)
t2 = t[pos2].astype(np.int64)
for p, qa, qb, tt in zip(pos2.tolist(), q2a.tolist(), q2b.tolist(), t2.tolist()):
    if tt in (0x21, 0xA1):          # CX: target qb changes
        val_by_q[qb].append(p)
    else:                            # SWAP: both change
        val_by_q[qa].append(p)
        val_by_q[qb].append(p)

l3 = np.zeros(256, dtype=bool); l3[[0x31, 0xB1, 0x32, 0xB2]] = True
pos3 = np.flatnonzero(l3[t]).astype(np.int64)
q3a = r.q3a.astype(np.int64); q3b = r.q3b.astype(np.int64); q3c = r.q3c.astype(np.int64)
t3 = t[pos3].astype(np.int64)
for p, qa, qb, qc, tt in zip(pos3.tolist(), q3a.tolist(), q3b.tolist(), q3c.tolist(), t3.tolist()):
    if tt in (0x31, 0xB1):           # CCX: target qc changes
        val_by_q[qc].append(p)
    else:                            # CSWAP: qb,qc change
        val_by_q[qb].append(p)
        val_by_q[qc].append(p)

for q in range(nq):
    val_by_q[q].sort()
    rst_by_q[q].sort()


def is_fresh(q, p):
    """q is |0> at position p iff no value op on q since its last reset < p."""
    rs = rst_by_q[q]
    j = bisect.bisect_left(rs, p) - 1
    last_rst = rs[j] if j >= 0 else -1
    vs = val_by_q[q]
    k = bisect.bisect_right(vs, last_rst)
    return k >= len(vs) or vs[k] >= p


# ---- pebbling pairs again (same logic as pebbling.py) ----
lccx = np.zeros(256, dtype=bool); lccx[[0x31, 0xB1]] = True
posc = np.flatnonzero(lccx[t]).astype(np.int64)
l3f = np.zeros(256, dtype=bool); l3f[[0x30, 0xB0, 0x31, 0xB1, 0x32, 0xB2]] = True
pos3f = np.flatnonzero(l3f[t]).astype(np.int64)
i3 = np.searchsorted(pos3f, posc)
A = r.q3a[i3].astype(np.int32); B = r.q3b[i3].astype(np.int32); C = r.q3c[i3].astype(np.int32)

triples = defaultdict(list)
for idx in range(len(posc)):
    triples[(int(A[idx]), int(B[idx]), int(C[idx]))].append(int(posc[idx]))

resets_all = defaultdict(list)
for q in range(nq):
    resets_all[q] = sorted(resets_all[q] + rst_by_q[q])

stats = Counter()
pair_detail = []
for (a_, b_, c_), poss in triples.items():
    rs = resets_all[c_]
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
            cls = 'syn' if c_ < 840 else 'work'
            fresh = is_fresh(c_, p1)
            key = (blk, cls, 'fresh' if fresh else 'data')
            stats[key] += 1
            if fresh and len(pair_detail) < 200000:
                pair_detail.append((blk, cls, a_, b_, c_, p1, p2))

print('pebbling pairs by (block, target-class, freshness):')
print(f'{"block":14} {"cls":5} {"fresh":6} {"pairs":>8}')
tot_fresh = 0
for blk in TOP + ['<pre>', '<post>']:
    for cls in ('syn', 'work'):
        for fr in ('fresh', 'data'):
            v = stats.get((blk, cls, fr), 0)
            if v:
                print(f'{blk:14} {cls:5} {fr:6} {v:>8}')
                if fr == 'fresh':
                    tot_fresh += v
print(f'\nTOTAL fresh-target pebbling pairs (HMR-convertible, 1 Toffoli each): {tot_fresh} '
      f'= {100*tot_fresh/397194:.2f}% of total T')
print(f'data-target pairs (not directly convertible): {sum(v for k, v in stats.items() if k[2]=="data")}')

with open(f'{ROOT}/work/dqi_t_sprint/fresh_pairs.json', 'w') as f:
    json.dump(dict(stats), f, indent=1)
r.close()
