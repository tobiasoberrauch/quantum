"""Per-block AND-ladder clearing analysis: HMR-cleared vs del_and-paired CCXs.

For every CCX op (a,b,c) [c = target leg], classify the fate of c:
  - 'hmr'    : next op touching c is HMR(c)  -> 1 Toffoli per logical AND (optimal)
  - 'del'    : next op touching c is CCX(a,b,c) again -> deterministic uncompute
  - 'other'  : anything else (c reused for different AND, kept alive, ...)
Also: CCZ ops (phase-only 3q) counted separately; CSWAP separately.
"""
import importlib.util
import sys
from collections import Counter

import numpy as np

ROOT = '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum'
KMB = f'{ROOT}/work/frontier_scan/mwa_unpacked/dqi.kmb'

spec = importlib.util.spec_from_file_location('wl', f'{ROOT}/work/dqi_sources/width_liveness.py')
wl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wl)

r = wl.KmbReader(KMB)
t = r.types
N = r.num_ops

tagpos = np.flatnonzero(t == 0x06)
ranges = {}
for p, s in zip(tagpos.tolist(), r.tag_strings):
    name = s.split(':', 1)[1]
    if s.startswith('@enter:'):
        ranges[name] = [p, None]
    elif s.startswith('@exit:') and name in ranges and ranges[name][1] is None:
        ranges[name][1] = p + 1

# all 3q positions and their triples
l3 = np.zeros(256, dtype=bool); l3[[0x30, 0xB0, 0x31, 0xB1, 0x32, 0xB2]] = True
pos3 = np.flatnonzero(l3[t]).astype(np.int64)
a3 = r.q3a.astype(np.int64); b3 = r.q3b.astype(np.int64); c3 = r.q3c.astype(np.int64)
t3 = t[pos3].astype(np.int64)

# for each qubit, sorted list of (pos, kind, payload) where kind in {ccx, ccz, cswap, hmr, r, other}
# Build per-qubit event lists restricted to 3q + reset ops (enough to classify AND fates)
lhmr = np.zeros(256, dtype=bool); lhmr[[0x50, 0xD0]] = True
lr = np.zeros(256, dtype=bool); lr[[0x12, 0x92]] = True
poshmr = np.flatnonzero(lhmr[t]).astype(np.int64)
posr = np.flatnonzero(lr[t]).astype(np.int64)
pos1 = np.flatnonzero(np.isin(t, [0x10, 0x90, 0x11, 0x91, 0x12, 0x92, 0x13, 0x93, 0x50, 0xD0])).astype(np.int64)
q1 = r.q1.astype(np.int64)
hmr_q = q1[np.searchsorted(pos1, poshmr)]
r_q = q1[np.searchsorted(pos1, posr)]

nq = r.num_qubits
events_by_q = [[] for _ in range(nq)]
# 3q events
for i in range(len(pos3)):
    tt = int(t3[i])
    kind = {0x30: 'ccz', 0xB0: 'ccz_if', 0x31: 'ccx', 0xB1: 'ccx_if', 0x32: 'cswap', 0xB2: 'cswap_if'}[tt]
    for q in (int(a3[i]), int(b3[i]), int(c3[i])):
        events_by_q[q].append((int(pos3[i]), kind, i))
# reset events
for p, q in zip(poshmr.tolist(), hmr_q.tolist()):
    events_by_q[q].append((p, 'hmr', -1))
for p, q in zip(posr.tolist(), r_q.tolist()):
    events_by_q[q].append((p, 'r', -1))
for q in range(nq):
    events_by_q[q].sort()

# classify each ccx op by fate of its target leg c
fate = Counter()
fate_by_block = {}
block_of_pos = {}
# assign each 3q op to top-level block
order = sorted(ranges.items(), key=lambda kv: kv[1][0])
import bisect
blocks_sorted = [(lo, hi, name) for name, (lo, hi) in ranges.items() if lo is not None]
blocks_sorted.sort()
los = [b[0] for b in blocks_sorted]

def top_block(p):
    i = bisect.bisect_right(los, p) - 1
    if i < 0:
        return '<pre>'
    lo, hi, name = blocks_sorted[i]
    return name if p < hi else '<gap>'

ccx_idx = np.where((t3 == 0x31) | (t3 == 0xB1))[0]
print(f'total CCX(+IF): {len(ccx_idx)}')

res = {}
for bi in ccx_idx:
    p = int(pos3[bi]); a = int(a3[bi]); b = int(b3[bi]); c = int(c3[bi])
    evs = events_by_q[c]
    # find position of this event in evs (search by pos)
    # evs sorted; binary search for (p, kind containing ccx)
    lo_i, hi_i = 0, len(evs)
    while lo_i < hi_i:
        mid = (lo_i + hi_i) // 2
        if evs[mid][0] < p:
            lo_i = mid + 1
        else:
            hi_i = mid
    idx = lo_i
    # next event on c after p
    nxt = None
    for j in range(idx, len(evs)):
        if evs[j][0] > p:
            nxt = evs[j]
            break
    blk = top_block(p)
    d = res.setdefault(blk, Counter())
    if nxt is None:
        f = 'end'
    elif nxt[1] in ('hmr', 'r'):
        f = 'hmr'
    elif nxt[1] in ('ccx', 'ccx_if'):
        # same triple?
        k = nxt[2]
        if k >= 0 and int(a3[k]) == a and int(b3[k]) == b and int(c3[k]) == c:
            f = 'del_same'
        else:
            f = 'ccx_other'
    elif nxt[1] in ('ccz', 'ccz_if'):
        f = 'ccz'
    elif nxt[1] in ('cswap', 'cswap_if'):
        f = 'cswap'
    else:
        f = 'other:' + nxt[1]
    d[f] += 1

tot = Counter()
print(f'\n{"block":14} {"ccx":>7} {"hmr":>7} {"del_same":>9} {"ccx_oth":>8} {"ccz":>6} {"cswap":>6} {"end":>5} {"other":>7}')
for blk, d in sorted(res.items(), key=lambda kv: -sum(kv[1].values())):
    s = sum(d.values())
    tot.update(d)
    print(f'{blk:14} {s:>7} {d.get("hmr",0):>7} {d.get("del_same",0):>9} {d.get("ccx_other",0):>8} '
          f'{d.get("ccz",0)+d.get("ccz_if",0):>6} {d.get("cswap",0)+d.get("cswap_if",0):>6} {d.get("end",0):>5} '
          f'{s-d.get("hmr",0)-d.get("del_same",0)-d.get("ccx_other",0)-d.get("ccz",0)-d.get("ccz_if",0)-d.get("cswap",0)-d.get("cswap_if",0)-d.get("end",0):>7}')
print(f'{"TOTAL":14} {sum(tot.values()):>7} {tot.get("hmr",0):>7} {tot.get("del_same",0):>9} {tot.get("ccx_other",0):>8}')

import json
with open(f'{ROOT}/work/dqi_t_sprint/and_fates.json', 'w') as f:
    json.dump({k: dict(v) for k, v in res.items()}, f, indent=1)
r.close()
