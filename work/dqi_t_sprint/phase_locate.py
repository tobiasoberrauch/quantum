"""Locate the MBUC phase kickback: CZ/CZ_IF ops touching E-register (classical)
bits, per block. Also map which bit ids belong to E registers vs working bits.
"""
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
nb = r.num_bits

# registers: which are bits? KmbReader.registers only keeps qubit ids (high-bit filtered).
# Re-parse register packets to get bit ids too.
import struct
mm = r.mm
off = 104
reginfo = {}
for _ in range(r.num_registers):
    ptype, plen = struct.unpack_from('<QQ', mm, off)
    off += 16
    nlen, rlen = struct.unpack_from('<II', mm, off)
    name = mm[off + 8:off + 8 + nlen].decode()
    ids = struct.unpack_from(f'<{rlen}I', mm, off + 8 + nlen)
    reginfo[name] = ids
    off += plen
e_bits = set()
for i in range(4095):
    e_bits.update(x & 0x7FFFFFFF for x in reginfo[f'E{i}'])
print(f'E bits: {len(e_bits)} ids {min(e_bits)}..{max(e_bits)}')
allbits = set()
for name, ids in reginfo.items():
    if not (name.startswith('S') and name[1:].isdigit()):
        allbits.update(x & 0x7FFFFFFF for x in ids)
print(f'non-S register bit ids: {len(allbits)}')
print('register names sample:', list(reginfo)[:10], '...', list(reginfo)[-5:])
# any bits not in any register?
unassigned = set(range(nb)) - allbits - e_bits
print(f'unassigned bit ids: {len(unassigned)}')

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


# CZ / CZ_IF ops: type 0x20 (CZ), 0xA0 (CZ_IF: cond bit + target qubit)
lcz = np.zeros(256, dtype=bool); lcz[[0x20, 0xA0]] = True
poscz = np.flatnonzero(lcz[t]).astype(np.int64)
print(f'\nCZ/CZ_IF ops total: {len(poscz)}')
# For 0xA0 (CZ_IF): q2a/q2b arrays hold... which is the bit? Check header counts:
# ncond = 3,910,695 cond-flag ops; bcond array length = ncond.
# CZ_IF has one qubit + one bit. In SOA, 2q ops store qubits in q2a/q2b; the bit
# for _IF variants is in bcond indexed by class-order among cond ops.
# Determine empirically: for 0xA0 ops, q2a vs q2b — one should be < nq always.
t_cz = t[poscz]
is_if = t_cz == 0xA0
q2a = r.q2a.astype(np.int64); q2b = r.q2b.astype(np.int64)
ia = np.searchsorted(np.flatnonzero(lcz[t]), poscz)  # identity
qa = q2a[ia]; qb = q2b[ia]
# which leg is the bit for _IF?
ifcnt_a = int((qa >= r.num_qubits).sum()) if False else None
# q2a/q2b for non-IF 2q ops are both qubits. For IF ops, one entry may be >= nq? No—
# bits live in bcond. Instead: CZ_IF(0xA0) semantics: control bit (bcond) + two qubits? 
# Actually CZ is 2-qubit; CZ_IF = CZ conditioned on a bit -> still 2 qubits + 1 bit.
# So both qa,qb are qubits; the condition bit is in bcond.
ncond_lut = np.zeros(256, dtype=bool)
COND_TYPES = [0xB0, 0xB1, 0xB2, 0xA0, 0xA1, 0xA2, 0x90, 0x91, 0x92, 0x93, 0xC0, 0xC1, 0xC2, 0xD0, 0x80, 0x81]
ncond_lut[COND_TYPES] = True
poscond = np.flatnonzero(ncond_lut[t]).astype(np.int64)
assert len(poscond) == r.ncond, (len(poscond), r.ncond)
bcz_idx = np.searchsorted(poscond, poscz[is_if])
cond_bits = r.bcond[bcz_idx]
print(f'CZ_IF ops: {int(is_if.sum())}, plain CZ: {int((~is_if).sum())}')

# classify CZ legs by E-bit membership
def legclass(v):
    if v < r.num_qubits:
        return 'q'
    return 'bit?'

# For plain CZ (0x20): both legs qubits. For CZ_IF: both legs qubits + cond bit.
# Phase kickback signature: CZ(qubit, qubit) where one qubit holds e_{j,t} and the
# cond bit (CZ_IF) is M_{j,t}; OR CZ between two qubits both in working set.
stat = Counter()
examples = []
for p, tt, a, b in zip(poscz.tolist(), t_cz.tolist(), qa.tolist(), qb.tolist()):
    blk = top_block(p)
    if tt == 0xA0:
        # find its cond bit
        j = np.searchsorted(poscz, p)
        cb = int(cond_bits[np.searchsorted(is_if[:j+1].cumsum(), j) - 1]) if False else None
    stat[(blk, 'CZ' if tt == 0x20 else 'CZ_IF')] += 1

# simpler: per-block counts
per_blk = Counter(top_block(p) for p in poscz.tolist())
per_blk_if = Counter(top_block(p) for p, tt in zip(poscz.tolist(), t_cz.tolist()) if tt == 0xA0)
print('\nCZ-family ops per block (total / CZ_IF):')
for blk in ['<pre>'] + TOP + ['<post>']:
    print(f'  {blk:14} {per_blk.get(blk,0):>8} / {per_blk_if.get(blk,0):>8}')

# Now: which qubits do CZ_IF touch? If phase kickback is CZ_IF(M_bit, e_qubit, ?) -- 
# CZ is 2-qubit so CZ_IF needs 2 qubits + 1 bit. Let's see qubit-class distribution.
synmask = np.zeros(r.num_qubits, dtype=bool)
for i in range(70):
    for x in reginfo[f'S{i}']:
        synmask[x & 0x7FFFFFFF] = True
qa_if = qa[is_if]; qb_if = qb[is_if]
print('\nCZ_IF leg classes:')
print('  q2a syndrome:', int(synmask[qa_if].sum()), 'working:', int((~synmask[qa_if]).sum()))
print('  q2b syndrome:', int(synmask[qb_if].sum()), 'working:', int((~synmask[qb_if]).sum()))
# cond bit distribution: E bits vs others
cb_all = r.bcond.astype(np.int64)
# cond bits used by CZ_IF specifically:
# rebuild: for each cond op position, its type
tcond = t[poscond]
cz_if_cond_pos = poscz[is_if]
j2 = np.searchsorted(poscond, cz_if_cond_pos)
cbs = r.bcond[j2]
in_e = np.isin(cbs, np.fromiter(e_bits, dtype=np.int64, count=len(e_bits)))
print(f'CZ_IF cond bits in E registers: {int(in_e.sum())}/{len(cbs)}')
if in_e.any():
    blk_e = Counter(top_block(p) for p, ok in zip(cz_if_cond_pos.tolist(), in_e.tolist()) if ok)
    print('  per block:', dict(blk_e))
r.close()
