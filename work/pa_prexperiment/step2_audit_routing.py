"""Step 2: bit-liveness audit + s-routing (barrel-shift) cost R, exact numpy counting.

Bit-liveness: for each required y-bit i in 4..39, is y_i(x) EXACTLY equal to one of the
41 existing control columns b_j(x) of the current circuit? If yes -> already a live
control (computation exists; phasing cost depends only on the weight's hierarchy level).

Routing R (option a, binary barrel-shift of p by s): a shift-link Toffoli in stage m
(active iff s_m=1) at source position j fires iff s_m(x)=1 AND p_j(x)=1. p occupies bits
0..29 and the register is W=40 wide, so every stage's links cover all of p's bits and the
per-x executed-link count = popcount(s(x)) * popcount(p(x)). Hence
    R_A1 = E[ popcount(s) * popcount(p) ]        (one-way; HMR-clears the register, no reverse)
    R_A1_rev = 2 * R_A1                          (conservative if the shift must be reversed)
Computed exactly on the full domain from the real p(x), s(x).
"""
import sys, time
import numpy as np

U64, I64 = np.uint64, np.int64
N = 3 * (2**10 - 2)**2
p = np.load('work/pa_prexperiment/data/p.npy')
s = np.load('work/pa_prexperiment/data/s.npy')
y = np.load('work/pa_prexperiment/data/y.npy')
print('p max:', int(p.max()), ' p bits needed:', int(p.max()).bit_length(), file=sys.stderr)
print('y max:', int(y.max()), ' y bits needed:', int(y.max()).bit_length(), file=sys.stderr)

# ---------- popcount helpers (vectorized) ----------
def popcount(a, bits):
    a = np.asarray(a, dtype=np.int64)
    c = np.zeros(a.shape, dtype=np.int64)
    for b in range(bits):
        c += (a >> b) & 1
    return c

pc_p = popcount(p, 30)     # p < 2^30
pc_s = popcount(s, 4)      # s < 16

R_A1 = float((pc_s * pc_p).mean())
print(f'\n=== s-routing, option (a) binary barrel-shift of p by s ===')
print(f'E[popcount(p)] = {pc_p.mean():.3f}   E[popcount(s)] = {pc_s.mean():.3f}')
print(f'R_A1 (one-way, HMR clear)      = {R_A1:.2f} mean executed Toffolis')
print(f'R_A1_rev (if shift reversed)   = {2*R_A1:.2f}')
# per-s-class breakdown
print('\nper s-class (s : frac : E[popcount(p)|s] : contrib to R):')
for sv in range(11):
    m = s == sv
    if m.sum() == 0: continue
    fr = m.mean()
    epp = pc_p[m].mean()
    print(f'  s={sv:2d} : {fr:.5f} : {epp:.3f} : {fr*bin(sv).count("1")*epp:.3f}')

# ---------- bit-liveness audit ----------
print('\n=== bit-liveness audit: y_i vs the 41 existing control columns ===')
bcols = np.stack([np.load(f'work/p0_reports/data/bcols/col_{j:02d}.npy') for j in range(41)], axis=1).astype(np.uint8)  # [N,41]
ybits = ((y.astype(U64)[:, None] >> np.arange(40, dtype=U64)[None, :]) & 1).astype(np.uint8)  # [N,40]

# also simple candidate functions for context
def bit(v, i): return ((v.astype(U64) >> i) & 1).astype(np.uint8)
x = np.arange(1, N+1, dtype=I64)
cands = {'xbit': None}
simple = {}
for i in range(22):
    simple[f'x{i}'] = bit(x, i)
for k in range(4):
    simple[f's{k}'] = bit(s, k)

results = []
for i in range(4, 40):
    yi = ybits[:, i]
    matches_b = [j for j in range(41) if np.array_equal(yi, bcols[:, j])]
    matches_s = [name for name, arr in simple.items() if np.array_equal(yi, arr)]
    # near-match (>=99.9%) against bcols
    near = []
    for j in range(41):
        agree = float((yi == bcols[:, j]).mean())
        if agree >= 0.999 and j not in matches_b:
            near.append((j, agree))
    lvl = 40 - i if i <= 37 else (3 if i == 37 else (2 if i == 38 else 1))
    free = lvl <= 3
    results.append({'i': i, 'weight_turns': f'2^{i-40}', 'level': lvl, 'free': free,
                    'exact_bcol': matches_b, 'exact_simple': matches_s, 'near_bcol': near,
                    'frac_ones': float(yi.mean())})

print(f'{"i":>3} {"wt(turns)":>10} {"lvl":>3} {"free":>5} | exact bcol j | exact simple | near(>=99.9%) | frac1')
for r in results:
    eb = ','.join(str(j) for j in r['exact_bcol']) or '-'
    es = ','.join(r['exact_simple']) or '-'
    en = ','.join(f'{j}:{a:.4f}' for j, a in r['near_bcol']) or '-'
    print(f'{r["i"]:>3} {r["weight_turns"]:>10} {r["level"]:>3} {str(r["free"]):>5} | {eb:>14} | {es:>12} | {en:>22} | {r["frac_ones"]:.3f}')

n_free_exact = sum(1 for r in results if r['exact_bcol'])
n_rot_bits = sum(1 for r in results if not r['free'])
print(f'\ny-bits that are EXACT existing controls: {n_free_exact}/36')
print(f'y-bits needing synthesized rotation (level>=4, i<=36): {n_rot_bits}/36  -> n_rot(P-A) = {n_rot_bits}')

import json
json.dump({'R_A1_one_way': R_A1, 'R_A1_reverse': 2*R_A1,
           'E_popcount_p': float(pc_p.mean()), 'E_popcount_s': float(pc_s.mean()),
           'n_rot_PA': n_rot_bits,
           'bits': results},
          open('work/pa_prexperiment/data/step2_results.json', 'w'), indent=1)
print('saved work/pa_prexperiment/data/step2_results.json', file=sys.stderr)
