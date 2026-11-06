"""Pebbling-pair detection: CCX triples (a,b,c) appearing twice with no reset of
c in between => deterministic init/del uncompute pair (2 Toffolis per logical
AND). Single occurrences => HMR-closed or accumulating contribution.

Per top-level block, report:
  - n_ccx total
  - pairs: triples occurring exactly twice, no HMR/R(c) between -> 2*pairs Toffolis,
    of which pairs are 'del' Toffolis (the removable half if HMR-converted)
  - singles_hmr: single occurrences followed (before any other target-use of c) by HMR/R(c)
  - accum: occurrences in runs of >=3 same-triple (product-tree accumulation)
Split by target class: syndrome (0..839) vs working (840..890).
"""
import importlib.util
import json
import sys
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
order = {name: i for i, name in enumerate(TOP)}
bounds = [(ranges[n][0], ranges[n][1], n) for n in TOP]
bounds.sort()
los = [b[0] for b in bounds]
import bisect


def top_block(p):
    i = bisect.bisect_right(los, p) - 1
    if i < 0:
        return '<pre>'
    lo, hi, name = bounds[i]
    return name if p < hi else '<post>'


# CCX ops (0x31 / 0xB1)
lccx = np.zeros(256, dtype=bool); lccx[[0x31, 0xB1]] = True
posc = np.flatnonzero(lccx[t]).astype(np.int64)
a = r.q3c[np.searchsorted(np.flatnonzero(l3 := np.zeros(256, dtype=bool)), 0)] if False else None

l3 = np.zeros(256, dtype=bool); l3[[0x30, 0xB0, 0x31, 0xB1, 0x32, 0xB2]] = True
pos3 = np.flatnonzero(l3[t]).astype(np.int64)
i3 = np.searchsorted(pos3, posc)
A = r.q3a[i3].astype(np.int32)
B = r.q3b[i3].astype(np.int32)
C = r.q3c[i3].astype(np.int32)
PC = posc
print(f'CCX(+IF) ops: {len(PC)}')

# resets per qubit: sorted positions of HMR/R on each qubit
lhmr = np.zeros(256, dtype=bool); lhmr[[0x50, 0xD0]] = True
lr = np.zeros(256, dtype=bool); lr[[0x12, 0x92]] = True
poshmr = np.flatnonzero(lhmr[t]).astype(np.int64)
posr = np.flatnonzero(lr[t]).astype(np.int64)
pos1 = np.flatnonzero(np.isin(t, [0x10, 0x90, 0x11, 0x91, 0x12, 0x92, 0x13, 0x93, 0x50, 0xD0])).astype(np.int64)
q1 = r.q1.astype(np.int64)
reset_pos_by_q = defaultdict(list)
for p, q in zip(poshmr.tolist(), q1[np.searchsorted(pos1, poshmr)].tolist()):
    reset_pos_by_q[q].append(p)
for p, q in zip(posr.tolist(), q1[np.searchsorted(pos1, posr)].tolist()):
    reset_pos_by_q[q].append(p)
for q in reset_pos_by_q:
    reset_pos_by_q[q].sort()

# group CCXs by triple
triples = defaultdict(list)
for idx in range(len(PC)):
    triples[(int(A[idx]), int(B[idx]), int(C[idx]))].append(int(PC[idx]))

by_block = defaultdict(Counter)
peb_by_class = Counter()


def runs_of(poss, rs):
    """split occurrence list into maximal runs with no reset of c between neighbors"""
    runs = [[poss[0]]]
    for i in range(len(poss) - 1):
        p1, p2 = poss[i], poss[i + 1]
        j = bisect.bisect_right(rs, p1)
        if j < len(rs) and rs[j] < p2:
            runs.append([p2])
        else:
            runs[-1].append(p2)
    return runs


for (a_, b_, c_), poss in triples.items():
    rs = reset_pos_by_q.get(c_, [])
    cls = 'syn' if c_ < 840 else 'work'
    for run in runs_of(poss, rs):
        blk = top_block(run[0])
        d = by_block[blk]
        m = len(run)
        pairs = m // 2
        singles = m % 2
        if pairs:
            d['peb_ccx'] += 2 * pairs
            peb_by_class[(blk, cls)] += pairs
        if singles:
            p = run[-1] if pairs else run[0]
            j = bisect.bisect_right(rs, p)
            if j < len(rs):
                d['single_then_reset'] += 1
            else:
                d['single_no_reset'] += 1

SYN = 840
print(f'\n{"block":14} {"ccx":>7} {"peb_pairs":>10} {"single_rst":>10} {"single_nr":>9}')
tot_ccx = 0
for blk in TOP + ['<pre>', '<post>']:
    d = by_block.get(blk, Counter())
    ccx = d['peb_ccx'] + d['single_then_reset'] + d['single_no_reset']
    tot_ccx += ccx
    print(f'{blk:14} {ccx:>7} {d["peb_ccx"]//2:>10} {d["single_then_reset"]:>10} {d["single_no_reset"]:>9}')
print(f'total ccx accounted: {tot_ccx} (expect {len(PC)})')

print('\npebbling pairs by block/target-class (del-Toffolis = same number):')
for (blk, cls), v in sorted(peb_by_class.items(), key=lambda kv: -kv[1]):
    print(f'  {blk:14} target={cls:4} pairs={v:>7}  ({100*v/397194:.2f}% of total T)')

with open(f'{ROOT}/work/dqi_t_sprint/pebbling.json', 'w') as f:
    json.dump({k: dict(v) for k, v in by_block.items()}, f, indent=1)
r.close()
