"""Per-block AND lifecycle state machine: how each CCX-created AND on target c
is closed — by HMR/R (measurement-based, 0 extra Toffolis) or by a repeat
CCX(a,b,c) (deterministic uncompute, +1 Toffoli), or left open across the
block boundary (carried into another block).

Per-qubit model: at most one open AND target at a time (ripple-ladder style).
"""
import importlib.util
import json
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
nq = r.num_qubits

tagpos = np.flatnonzero(t == 0x06)
ranges = {}
for p, s in zip(tagpos.tolist(), r.tag_strings):
    name = s.split(':', 1)[1]
    if s.startswith('@enter:'):
        ranges[name] = [p, None]
    elif s.startswith('@exit:') and name in ranges and ranges[name][1] is None:
        ranges[name][1] = p + 1
blocks_sorted = sorted((lo, hi, name) for name, (lo, hi) in ranges.items() if lo is not None)
los = [b[0] for b in blocks_sorted]
import bisect


def top_block(p):
    i = bisect.bisect_right(los, p) - 1
    if i < 0:
        return '<pre>'
    lo, hi, name = blocks_sorted[i]
    return name if p < hi else '<gap>'


l3 = np.zeros(256, dtype=bool); l3[[0x30, 0xB0, 0x31, 0xB1, 0x32, 0xB2]] = True
pos3 = np.flatnonzero(l3[t]).astype(np.int64)
a3 = r.q3a.astype(np.int64); b3 = r.q3b.astype(np.int64); c3 = r.q3c.astype(np.int64)
t3 = t[pos3].astype(np.int64)
lhmr = np.zeros(256, dtype=bool); lhmr[[0x50, 0xD0]] = True
lr = np.zeros(256, dtype=bool); lr[[0x12, 0x92]] = True
poshmr = np.flatnonzero(lhmr[t]).astype(np.int64)
posr = np.flatnonzero(lr[t]).astype(np.int64)
pos1 = np.flatnonzero(np.isin(t, [0x10, 0x90, 0x11, 0x91, 0x12, 0x92, 0x13, 0x93, 0x50, 0xD0])).astype(np.int64)
q1 = r.q1.astype(np.int64)
hmr_q = q1[np.searchsorted(pos1, poshmr)]
r_q = q1[np.searchsorted(pos1, posr)]

# per-qubit event list: (pos, kind, payload) kind: 'T' target-CCX (payload=(a,b)),
# 'H' hmr, 'R' r
evs = [[] for _ in range(nq)]
for i in range(len(pos3)):
    tt = int(t3[i])
    if tt in (0x31, 0xB1):
        evs[int(c3[i])].append((int(pos3[i]), 'T', (int(a3[i]), int(b3[i]))))
    elif tt in (0x32, 0xB2):
        # CSWAP touches all three as data legs; treat as barrier (resets open state? no—)
        # CSWAP swaps b<->c controlled on a: c's value changes -> any open AND on c is destroyed
        evs[int(c3[i])].append((int(pos3[i]), 'C', None))
    # CCZ: phase only, c unchanged -> ignore for lifecycle
for p, q in zip(poshmr.tolist(), hmr_q.tolist()):
    evs[q].append((p, 'H', None))
for p, q in zip(posr.tolist(), r_q.tolist()):
    evs[q].append((p, 'R', None))
for q in range(nq):
    evs[q].sort()

stats = Counter()
by_block = {}
open_at_start = 0
for q in range(nq):
    open_triple = None
    open_pos = None
    for p, kind, payload in evs[q]:
        blk = top_block(p)
        d = by_block.setdefault(blk, Counter())
        if kind == 'T':
            if open_triple is None:
                open_triple, open_pos = payload, p
                d['opened'] += 1
            elif open_triple == payload:
                d['closed_del'] += 1
                open_triple = None
            else:
                d['conflict_new_target'] += 1
                open_triple, open_pos = payload, p  # previous AND leaked (shouldn't happen)
        elif kind in ('H', 'R'):
            if open_triple is not None:
                d['closed_hmr'] += 1
                open_triple = None
            else:
                d['bare_reset'] += 1
        elif kind == 'C':
            if open_triple is not None:
                d['destroyed_by_cswap'] += 1
                open_triple = None
    if open_triple is not None:
        stats['unclosed_at_end'] += 1

print(f'{"block":14} {"opened":>8} {"closed_hmr":>11} {"closed_del":>11} {"bare_reset":>11} {"conflict":>9} {"cswap_dest":>10}')
tot = Counter()
for blk, d in sorted(by_block.items(), key=lambda kv: -kv[1]['opened']):
    tot.update(d)
    print(f'{blk:14} {d["opened"]:>8} {d["closed_hmr"]:>11} {d["closed_del"]:>11} {d["bare_reset"]:>11} '
          f'{d["conflict_new_target"]:>9} {d["destroyed_by_cswap"]:>10}')
print(f'{"TOTAL":14} {tot["opened"]:>8} {tot["closed_hmr"]:>11} {tot["closed_del"]:>11} {tot["bare_reset"]:>11} '
      f'{tot["conflict_new_target"]:>9} {tot["destroyed_by_cswap"]:>10}')
print(f'unclosed at stream end: {stats["unclosed_at_end"]}')

# Toffoli accounting: each opened CCX = 1 Toffoli; each closed_del = 1 extra Toffoli.
# HMR-able savings upper bound = closed_del count (if every del could become HMR+phase).
print('\nSavings potential (closed_del -> HMR):')
for blk, d in sorted(by_block.items(), key=lambda kv: -kv[1]['closed_del']):
    if d['closed_del']:
        print(f'  {blk:14} {d["closed_del"]:>8}  ({100*d["closed_del"]/397194:.2f}% of total T)')

with open(f'{ROOT}/work/dqi_t_sprint/and_lifecycle.json', 'w') as f:
    json.dump({k: dict(v) for k, v in by_block.items()}, f, indent=1)
r.close()
