"""Spot-check: for top repeated (c1,c2) CCX name-pairs, compare control values at the
first two occurrences via prefix simulation (same explicit seed + same x batch).
If controls ever differ -> NOT a true product repeat (pebbling / compute-uncompute symmetry).
"""
import sys, numpy as np
import kickmix as km
from collections import defaultdict

LINES = open('work/invsqrt_caching/invsqrt.kmx').read().splitlines()
N = len(LINES)

def prefix_circuit(n):
    return km.Circuit('\n'.join(LINES[:n]))

def read_controls(circuit, ctrl, xs, seed):
    sim = km.Simulator(batch_size=len(xs), seed=seed)
    sim.use_same_registers_as(circuit)
    def tb(v, w): return ((v[None, :] >> np.arange(w, dtype=np.uint64)[:, None]) & 1) == 1
    sim.write_across_shots(km.array([km.q(i) for i in range(22)]), tb(xs, 22))
    sim.do(circuit)
    return sim.read_across_shots(km.array([km.q(int(ctrl[0][1:])), km.q(int(ctrl[1][1:]))]))

# find CCX occurrences per sorted name-pair
pos = defaultdict(list)
for i, l in enumerate(LINES):
    t = l.split()
    if t[0] == 'CCX':
        pos[tuple(sorted((t[1], t[2])))].append(i)

top = sorted(pos.items(), key=lambda kv: -len(kv[1]))[:8]

# diverse x batch
xs = np.concatenate([
    np.arange(1, 200, dtype=np.uint64),
    np.array([1000, 4095, 65535, 100000, 500000, 1000000, 2000000, 3133451, 3133452], dtype=np.uint64),
    (np.arange(1, 128, dtype=np.uint64) * 7919) % 3133452 + 1,
]).astype(np.uint64)
xs = xs[np.argsort(xs)]
print(f'x batch size: {len(xs)}')

for (c1, c2), occ in top:
    if len(occ) < 2: continue
    L0, L1 = occ[0], occ[1]
    try:
        v0 = read_controls(prefix_circuit(L0), (c1, c2), xs, seed=12345)
        v1 = read_controls(prefix_circuit(L1), (c1, c2), xs, seed=12345)
        diff = int((v0 != v1).sum())
        # second seed for robustness
        v0b = read_controls(prefix_circuit(L0), (c1, c2), xs, seed=777)
        v1b = read_controls(prefix_circuit(L1), (c1, c2), xs, seed=777)
        diffb = int((v0b != v1b).sum())
        verdict = 'DIFFERENT (not a repeat)' if (diff or diffb) else 'IDENTICAL on sample (possible repeat)'
        print(f'{c1},{c2}: {len(occ)} occ | occ0@{L0} occ1@{L1} | diff(seed12345)={diff} diff(seed777)={diffb} -> {verdict}')
    except Exception as e:
        print(f'{c1},{c2}: ERROR {type(e).__name__}: {e}')
