"""Full op-type census per top-level block + inspect initial/uninitial/
mask_projection/restore_masks structure (the 0-Toffoli glue)."""
import importlib.util
import json
import sys
import bisect
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

NAMES = {0x01: 'NOOP?', 0x06: 'INFO_TAG', 0x10: 'Z', 0x11: 'X', 0x12: 'R',
         0x20: 'CZ', 0x21: 'CX', 0x22: 'SWAP', 0x30: 'CCZ', 0x31: 'CCX', 0x32: 'CSWAP',
         0x40: 'BIT_STORE0', 0x50: 'HMR', 0x80: 'NOOP_IF?', 0x81: 'BARRIER_IF?',
         0x90: 'Z_IF', 0xA0: 'CZ_IF', 0xA1: 'CX_IF', 0xC2: 'BIT_INVERT_IF'}

ALLBLOCKS = ['mask_projection', 'initial', 'extract', 'synthesis', 'convert', 'scan',
             'unconvert', 'unsynthesis', 'unextract', 'uninitial', 'restore_masks']
tagpos = np.flatnonzero(t == 0x06)
ranges = {}
for p, s in zip(tagpos.tolist(), r.tag_strings):
    name = s.split(':', 1)[1]
    if s.startswith('@enter:') and name in ALLBLOCKS:
        ranges[name] = [p, None]
    elif s.startswith('@exit:') and name in ALLBLOCKS and ranges[name][1] is None:
        ranges[name][1] = p + 1
bounds = sorted((ranges[n][0], ranges[n][1], n) for n in ALLBLOCKS)
los = [b[0] for b in bounds]


def top_block(p):
    i = bisect.bisect_right(los, p) - 1
    if i < 0:
        return '<pre>'
    lo, hi, name = bounds[i]
    return name if p < hi else '<post>'


# vectorized per-block type counts
blk_id = np.full(N, -1, dtype=np.int32)
for bi, (lo, hi, name) in enumerate(bounds):
    blk_id[lo:hi] = bi
order = {name: i for i, (lo, hi, name) in enumerate(bounds)}

cnt = np.zeros((len(bounds) + 2, 256), dtype=np.int64)
for b in range(len(bounds)):
    seg = t[blk_id == b]
    cnt[b] = np.bincount(seg, minlength=256)
seg = t[blk_id == -1]
cnt[len(bounds)] = np.bincount(seg, minlength=256)

print(f'{"block":16} {"ops":>11} | ' + ' '.join(f'{NAMES[k]:>13}' for k in sorted(NAMES) if k != 0x06))
for b, (lo, hi, name) in enumerate(bounds):
    row = cnt[b]
    print(f'{name:16} {hi-lo:>11,} | ' + ' '.join(f'{int(row[k]):>13,}' for k in sorted(NAMES) if k != 0x06))
row = cnt[len(bounds)]
print(f'{"<outside>":16} {int(row.sum()):>11,} | ' + ' '.join(f'{int(row[k]):>13,}' for k in sorted(NAMES) if k != 0x06))

# ---- inspect mask_projection / initial / uninitial / restore_masks ----
P1 = np.flatnonzero(np.isin(t, [0x10, 0x90, 0x11, 0x91, 0x12, 0x92, 0x13, 0x93, 0x50, 0xD0]))
P2 = np.flatnonzero(np.isin(t, [0x20, 0xA0, 0x21, 0xA1, 0x22, 0xA2]))
P3 = np.flatnonzero(np.isin(t, [0x30, 0xB0, 0x31, 0xB1, 0x32, 0xB2]))
# b1 holds bit targets of BIT ops AND HMR ops (n1b = 2,927,068 + 79,399 = 3,006,467)
PB = np.flatnonzero(np.isin(t, [0x40, 0xC0, 0x41, 0xC1, 0x42, 0xC2, 0x50, 0xD0]))


def window(name, k=25):
    lo, hi = ranges[name]
    print(f'\n--- {name}: first {k} ops ---')
    for p in range(lo, min(lo + k, hi)):
        tt = int(t[p])
        nm = NAMES.get(tt, hex(tt))
        extra = ''
        if tt in (0x10, 0x11, 0x12, 0x13, 0x50, 0x90, 0x91, 0x92, 0x93, 0xD0):
            j = int(np.searchsorted(P1, p))
            extra = f' q={int(r.q1[j])}'
        elif tt in (0x20, 0x21, 0x22, 0xA0, 0xA1, 0xA2):
            j = int(np.searchsorted(P2, p))
            extra = f' q={int(r.q2a[j])},{int(r.q2b[j])}'
        elif tt in (0x30, 0x31, 0x32, 0xB0, 0xB1, 0xB2):
            j = int(np.searchsorted(P3, p))
            extra = f' q={int(r.q3a[j])},{int(r.q3b[j])},{int(r.q3c[j])}'
        elif tt in (0x40, 0x41, 0x42, 0xC0, 0xC1, 0xC2):
            j = int(np.searchsorted(PB, p))
            extra = f' b={int(r.b1[j])}'
        elif tt == 0x06:
            idx = int(np.searchsorted(tagpos, p))
            extra = f' "{r.tag_strings[idx]}"'
        print(f'  {p-lo:6d} {nm:14}{extra}')

window('mask_projection')
window('initial')
window('uninitial')
window('restore_masks')
r.close()
