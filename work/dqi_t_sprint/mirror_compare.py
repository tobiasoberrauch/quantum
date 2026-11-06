"""Compare forward vs reverse block gate sequences (3q + reset events).

For pairs (extract,unextract), (synthesis,unsynthesis), (convert,unconvert):
  - extract the sequence of 3q-op triples (type,a,b,c) and 1q reset events
    (HMR/R on qubit q) within each block's op range.
  - test whether reverse-seq == mirror(forward-seq) on a prefix; report
    longest matching prefix length and where they diverge.
Also: verify scan's n3==nhmr==nr coincidence and dump a sample window.
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
l3 = np.zeros(256, dtype=bool); l3[[0x30, 0xB0, 0x31, 0xB1, 0x32, 0xB2]] = True
lhmr = np.zeros(256, dtype=bool); lhmr[[0x50, 0xD0]] = True
lr = np.zeros(256, dtype=bool); lr[[0x12, 0x92]] = True

pos3 = np.flatnonzero(l3[t]).astype(np.int64)
poshmr = np.flatnonzero(lhmr[t]).astype(np.int64)
posr = np.flatnonzero(lr[t]).astype(np.int64)
pos1 = np.flatnonzero(np.isin(t, [0x10, 0x90, 0x11, 0x91, 0x12, 0x92, 0x13, 0x93, 0x50, 0xD0])).astype(np.int64)

# block ranges from previous analysis (op_lo inclusive, op_hi exclusive = exit tag pos +1)
BLOCKS = {
    'extract':     (int(0.045 * N), int(0.113 * N)),
    'synthesis':   (int(0.113 * N), int(0.206 * N)),
    'convert':     (int(0.206 * N), int(0.304 * N)),
    'scan':        (int(0.304 * N), int(0.706 * N)),
    'unconvert':   (int(0.706 * N), int(0.796 * N)),
    'unsynthesis': (int(0.796 * N), int(0.894 * N)),
    'unextract':   (int(0.894 * N), int(0.994 * N)),
}
# refine using actual tag positions
tagpos = np.flatnonzero(t == 0x06)
ranges = {}
for p, s in zip(tagpos.tolist(), r.tag_strings):
    if s == '@enter:extract': ranges['extract'] = [p, None]
    if s == '@exit:extract': ranges['extract'][1] = p + 1
    if s == '@enter:synthesis': ranges['synthesis'] = [p, None]
    if s == '@exit:synthesis': ranges['synthesis'][1] = p + 1
    if s == '@enter:convert': ranges['convert'] = [p, None]
    if s == '@exit:convert': ranges['convert'][1] = p + 1
    if s == '@enter:scan': ranges['scan'] = [p, None]
    if s == '@exit:scan': ranges['scan'][1] = p + 1
    if s == '@enter:unconvert': ranges['unconvert'] = [p, None]
    if s == '@exit:unconvert': ranges['unconvert'][1] = p + 1
    if s == '@enter:unsynthesis': ranges['unsynthesis'] = [p, None]
    if s == '@exit:unsynthesis': ranges['unsynthesis'][1] = p + 1
    if s == '@enter:unextract': ranges['unextract'] = [p, None]
    if s == '@exit:unextract': ranges['unextract'][1] = p + 1


def seq3(lo, hi):
    """sequence of 3q events as packed ints: type<<40 | a<<27 | b<<13 | c"""
    i0, i1 = np.searchsorted(pos3, lo, 'left'), np.searchsorted(pos3, hi, 'left')
    seg = pos3[i0:i1]
    tt = t[seg].astype(np.int64)
    a = r.q3a[i0:i1].astype(np.int64)
    b = r.q3b[i0:i1].astype(np.int64)
    c = r.q3c[i0:i1].astype(np.int64)
    return (tt << 40) | (a << 27) | (b << 13) | c, seg


def seqresets(lo, hi):
    """sequence of reset events: kind<<32 | qubit ; kind 1=HMR 2=R"""
    out = []
    i0, i1 = np.searchsorted(poshmr, lo, 'left'), np.searchsorted(poshmr, hi, 'left')
    li = np.searchsorted(pos1, poshmr[i0:i1])
    out += [(1 << 32) | int(r.q1[x]) for x in li]
    i0, i1 = np.searchsorted(posr, lo, 'left'), np.searchsorted(posr, hi, 'left')
    li = np.searchsorted(pos1, posr[i0:i1])
    out += [(2 << 32) | int(r.q1[x]) for x in li]
    return out


def decode3(x):
    return (int(x >> 40 & 0xFF), int(x >> 27 & 0x1FFF), int(x >> 13 & 0x1FFF), int(x & 0x1FFF))


def compare(name_f, name_r):
    lo_f, hi_f = ranges[name_f]
    lo_r, hi_r = ranges[name_r]
    sf, pf = seq3(lo_f, hi_f)
    sr, pr = seq3(lo_r, hi_r)
    print(f'\n=== {name_f} ({len(sf)} 3q) vs {name_r} ({len(sr)} 3q) ===')
    # merge resets into comparable interleaved stream? First do 3q-only mirror test.
    revf = sf[::-1]
    n = min(len(revf), len(sr))
    # longest common prefix
    eq = revf[:n] == sr[:n]
    m = int(eq.argmax() ^ 1) if not eq.all() else n  # first mismatch index
    m = n if eq.all() else int(np.argmax(~eq))
    print(f'mirror-prefix match: {m}/{min(len(sf), len(sr))} (forward len {len(sf)}, reverse len {len(sr)})')
    if m < min(len(sf), len(sr)):
        a = decode3(revf[m]); b = decode3(sr[m])
        print(f'first divergence @ {m}: mirror={a} reverse={b}')
        # context
        for i in range(max(0, m - 3), min(n, m + 4)):
            print(f'  {i}: mirror={decode3(revf[i])} reverse={decode3(sr[i])}')
    # what fraction of reverse is NOT explained by mirror of forward
    extra = len(sr) - m
    print(f'unexplained reverse 3q: {extra} ({100*extra/len(sr):.1f}% of reverse)')
    # type histogram of the unexplained tail
    tail = sr[m:]
    tc = Counter(int(x >> 40 & 0xFF) for x in tail)
    names = {0x30: 'CCZ', 0xB0: 'CCZ_IF', 0x31: 'CCX', 0xB1: 'CCX_IF', 0x32: 'CSWAP', 0xB2: 'CSWAP_IF'}
    print('tail types:', {names[k]: v for k, v in sorted(tc.items())})
    # resets comparison
    rf, rr_ = seqresets(lo_f, hi_f), seqresets(lo_r, hi_r)
    print(f'resets: forward HMR/R events={len(rf)}, reverse={len(rr_)}')
    return dict(fwd=len(sf), rev=len(sr), match=m, extra=int(extra),
                tail_types={names[k]: v for k, v in sorted(tc.items())},
                fwd_pos=(int(pf[0]), int(pf[-1])) if len(pf) else None,
                rev_pos=(int(pr[0]), int(pr[-1])) if len(pr) else None)


res = {}
res['eu'] = compare('extract', 'unextract')
res['sy'] = compare('synthesis', 'unsynthesis')
res['co'] = compare('convert', 'unconvert')

# ---- scan verification ----
lo, hi = ranges['scan']
i0, i1 = np.searchsorted(pos3, lo, 'left'), np.searchsorted(pos3, hi, 'left')
i0h, i1h = np.searchsorted(poshmr, lo, 'left'), np.searchsorted(poshmr, hi, 'left')
i0r, i1r = np.searchsorted(posr, lo, 'left'), np.searchsorted(posr, hi, 'left')
print(f'\n=== scan: 3q={i1-i0:,} HMR={i1h-i0h:,} R={i1r-i0r:,} ===')
tt = t[pos3[i0:i1]]
tc = Counter(int(x) for x in tt)
names = {0x30: 'CCZ', 0xB0: 'CCZ_IF', 0x31: 'CCX', 0xB1: 'CCX_IF', 0x32: 'CSWAP', 0xB2: 'CSWAP_IF'}
print('scan 3q types:', {names[k]: v for k, v in sorted(tc.items())})
# interleave scan 3q + HMR + R events in stream order, show first 40
ev = []
for p in pos3[i0:i0 + 20000]:
    ev.append((p, '3q' + names[int(t[p])], decode3((int(t[p]) << 40) | (int(r.q3a[np.searchsorted(pos3, p)]) << 27) | (int(r.q3b[np.searchsorted(pos3, p)]) << 13) | int(r.q3c[np.searchsorted(pos3, p)]))))
for p in poshmr[i0h:i0h + 20000]:
    li = np.searchsorted(pos1, p)
    ev.append((p, 'HMR', int(r.q1[li])))
for p in posr[i0r:i0r + 20000]:
    li = np.searchsorted(pos1, p)
    ev.append((p, 'R', int(r.q1[li])))
ev.sort(key=lambda x: x[0])
print('first 40 scan events:')
for e in ev[:40]:
    print('  ', e)
# gap structure between consecutive 3q ops in scan
d3 = np.diff(pos3[i0:i1])
gc = Counter(int(x) for x in d3)
print('gap histogram (ops between consecutive 3q) top:', gc.most_common(10))
print('median gap:', int(np.median(d3)), 'mean:', float(d3.mean()))

import json
with open(f'{ROOT}/work/dqi_t_sprint/mirror_compare.json', 'w') as f:
    json.dump(res, f, indent=1)
r.close()
