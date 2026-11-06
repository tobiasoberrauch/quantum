"""P1.1b (vectorized): structural probe of gf_iadd blocks in dqi.kmb."""
import importlib.util
import numpy as np
from collections import Counter

spec = importlib.util.spec_from_file_location('wl', 'work/dqi_sources/width_liveness.py')
wl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wl)

r = wl.KmbReader('work/frontier_scan/mwa_unpacked/dqi.kmb')
t = r.types
N = r.num_ops
TAG = 0x06
Q3C = [0x30, 0xB0, 0x31, 0xB1, 0x32, 0xB2]
Q2C = [0x20, 0xA0, 0x21, 0xA1, 0x22, 0xA2]
Q1C = [0x10, 0x90, 0x11, 0x91, 0x12, 0x92, 0x13, 0x93, 0x50, 0xD0]

syn_q = set()
for name, qs in r.registers.items():
    if name.startswith('S'):
        syn_q.update(qs)
print(f'syndrome qubits: {len(syn_q)} | ancilla: {r.num_qubits - len(syn_q)}')

pos_q3 = np.flatnonzero(np.isin(t, Q3C))
pos_q2 = np.flatnonzero(np.isin(t, Q2C))
pos_q1 = np.flatnonzero(np.isin(t, Q1C))
print(f'3q={len(pos_q3)} 2q={len(pos_q2)} 1q={len(pos_q1)}')

# gf_iadd segments via tag walk (17k tags - cheap)
tagpos = np.flatnonzero(t == TAG)
segs = []
ti = 0
for p in tagpos:
    s = r.tag_strings[ti]; ti += 1
    if s == '@enter:gf_iadd':
        segs.append([int(p), None])
    elif s == '@exit:gf_iadd' and segs and segs[-1][1] is None:
        segs[-1][1] = int(p)
segs = [(a, b) for a, b in segs if b is not None]
print(f'gf_iadd segments: {len(segs)}, total span ops: {sum(b - a for a, b in segs)}')

# op mix inside segments (vectorized via masks)
in_seg = np.zeros(N, dtype=bool)
for a, b in segs:
    in_seg[a:b] = True
mix = Counter(t[in_seg].tolist())
names = {0x30: 'CCZ', 0xB0: 'CCZ_IF', 0x31: 'CCX', 0xB1: 'CCX_IF', 0x32: 'CSWAP', 0xB2: 'CSWAP_IF',
         0x20: 'CZ', 0xA0: 'CZ_IF', 0x21: 'CX', 0xA1: 'CX_IF', 0x22: 'SWAP', 0xA2: 'SWAP_IF',
         0x10: 'Z', 0x90: 'Z_IF', 0x11: 'X', 0x91: 'X_IF', 0x12: 'R', 0x92: 'R_IF',
         0x13: 'Z_POW', 0x93: 'Z_POW_IF', 0x50: 'HMR', 0xD0: 'HMR_IF', 0x40: 'BIT_STORE0',
         0xC0: 'BIT_STORE0_IF', 0x41: 'BIT_STORE1', 0xC1: 'BIT_STORE1_IF', 0x42: 'BIT_INVERT',
         0xC2: 'BIT_INVERT_IF', 0x06: 'INFO_TAG'}
print('\nop mix in gf_iadd:')
for code, n in mix.most_common():
    print(f'  {names.get(code, hex(code)):14} {n}')

# qubits touched by 3q ops inside segments
i3 = np.searchsorted(pos_q3, np.arange(N)[in_seg.nonzero()[0]]) if False else None
seg_starts = np.array([a for a, b in segs])
seg_ends = np.array([b for a, b in segs])
lo = np.searchsorted(pos_q3, seg_starts, side='left')
hi = np.searchsorted(pos_q3, seg_ends, side='left')
idx3 = np.concatenate([np.arange(lo[i], hi[i]) for i in range(len(segs))]) if len(segs) else np.array([], dtype=int)
qs3 = np.concatenate([r.q3a[idx3], r.q3b[idx3], r.q3c[idx3]])
c = Counter(qs3.tolist())
n_syn = sum(v for q, v in c.items() if q in syn_q)
n_anc = sum(v for q, v in c.items() if q not in syn_q)
print(f'\n3q-op qubit touches in gf_iadd: syndrome={n_syn} ancilla={n_anc} distinct={len(c)}')
print('top 15 touched:', sorted(((q, n, 'SYN' if q in syn_q else 'ANC') for q, n in c.most_common(15)), key=lambda x: x[0]))

# which syndrome registers? S{i} = 12 consecutive qubits? check register layout
reg_layout = {name: (min(qs), max(qs), len(qs)) for name, qs in list(r.registers.items())[:8]}
print('\nregister layout sample:', reg_layout)

# smallest instance dump
smallest = min(segs, key=lambda s: s[1] - s[0])
a, b = smallest
print(f'\n=== smallest gf_iadd instance [{a},{b}) len={b-a} ===')
# map stream pos -> qubits for this small range using searchsorted per class
def dump_range(a, b):
    events = []
    for p in pos_q3[pos_q3 >= a][:b - a]:
        if p >= b: break
        i = int(np.searchsorted(pos_q3, p))
        ty = int(t[p])
        events.append((p, names.get(ty, hex(ty)), [int(r.q3a[i]), int(r.q3b[i]), int(r.q3c[i])]))
    for p in pos_q2[pos_q2 >= a]:
        if p >= b: break
        i = int(np.searchsorted(pos_q2, p))
        ty = int(t[p])
        events.append((p, names.get(ty, hex(ty)), [int(r.q2a[i]), int(r.q2b[i])]))
    for p in pos_q1[pos_q1 >= a]:
        if p >= b: break
        i = int(np.searchsorted(pos_q1, p))
        ty = int(t[p])
        events.append((p, names.get(ty, hex(ty)), [int(r.q1[i])]))
    for p in np.flatnonzero((t[a:b] == 0x40) | (t[a:b] == 0xC0) | (t[a:b] == 0x41) | (t[a:b] == 0xC1) | (t[a:b] == 0x42) | (t[a:b] == 0xC2)):
        pp = a + p
        events.append((pp, names.get(int(t[pp]), hex(int(t[pp]))), []))
    events.sort()
    return events
for p, nm, qs in dump_range(a, b)[:100]:
    print(f'{p - a:4d} {nm:12} {qs}')
