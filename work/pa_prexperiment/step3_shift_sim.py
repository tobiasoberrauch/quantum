"""Step 3: REAL kickmix simulation of the s-routing barrel shift (option a, in-place).

Circuit: 40-qubit register `pin` holds p (bits 0..29; bits 30..39 = 0), 4-qubit `selin`
holds s. Barrel-shift pin left by s using d=2^m rounds of adjacent-CSWAP cascades per
stage m (active iff sel[m]=1). Because p<2^30 and s<=8<10, the top bits stay 0 through
every intermediate shift -> no wrap contamination -> exact y = p << s.

Measure on a reduced domain (stratified sample over all s-classes):
  - correctness: read(pin) == p<<s  for every shot
  - R = mean executed Toffolis attributable to the shift (num_toffoli_like / shots)
  - num_qubits (Q_peak contribution of the routing workspace)
"""
import sys, time
import numpy as np
import kickmix as km

U64, I64 = np.uint64, np.int64
N = 3 * (2**10 - 2)**2
p_all = np.load('work/pa_prexperiment/data/p.npy')
s_all = np.load('work/pa_prexperiment/data/s.npy')

W = 40          # pin width
SEL = 4         # s selector bits
# ---- stratified sample: cover every s-class, weight ~ natural frequency ----
rng = np.random.default_rng(0)
sample_idx = []
for sv in range(11):
    cls = np.flatnonzero(s_all == sv)
    if len(cls) == 0: continue
    k = max(40, int(0.20 * len(cls)))          # >=40 per class, up to 20% of class
    sample_idx.append(rng.choice(cls, size=min(k, len(cls)), replace=False))
sample_idx = np.concatenate(sample_idx)
rng.shuffle(sample_idx)
BS_target = 1024
need = int(np.ceil(len(sample_idx) / BS_target)) * BS_target
if len(sample_idx) < need:
    sample_idx = np.concatenate([sample_idx, rng.choice(sample_idx, size=need - len(sample_idx), replace=True)])
sample_idx = sample_idx[:need]
xs = sample_idx + 1
p_s = p_all[sample_idx]
s_s = s_all[sample_idx]
print(f'reduced domain: {len(xs)} x, s-class coverage: {sorted(set(int(v) for v in s_s))}', file=sys.stderr)

# ---- build the barrel-shift circuit ----
b = km.CircuitBuilder()
pin = b.create_quantum_register(W, 'pin')
selin = b.create_quantum_register(SEL, 'selin')

def csel(m, j):
    # controlled adjacent swap: CSWAP(sel[m], pin[j-1], pin[j])
    b.cswap(selin[m], pin[j-1], pin[j])

# stage m: shift by d=2^m, active iff sel[m]=1 -> d rounds of (W-1) adjacent CSWAP cascades
for m in range(SEL):
    d = 2**m
    for _round in range(d):
        for j in range(W-1, 0, -1):      # top-to-bottom cascade = left-shift-by-1
            csel(m, j)

circ = b.finish_circuit()
stats_static = circ.operation_statistics()
print(f'circuit: num_qubits={circ.num_qubits} static toffoli_like={stats_static.num_toffoli_like} '
      f'swap/cswap ops present', file=sys.stderr)

# ---- sanity: num_toffoli_like counts APPLIED (reached) gates, not data-firings ----
def _cswap_counts():
    bb = km.CircuitBuilder()
    a = bb.create_quantum_register(1, 'a')
    t1 = bb.alloc_qubits(1); t2 = bb.alloc_qubits(1)
    bb.x(a[0]); bb.cswap(a[0], t1[0], t2[0])     # control=1
    bb2 = km.CircuitBuilder()
    a2 = bb2.create_quantum_register(1, 'a')
    t3 = bb2.alloc_qubits(1); t4 = bb2.alloc_qubits(1)
    bb2.cswap(a2[0], t3[0], t4[0])               # control=0
    s1 = km.Simulator(batch_size=1, counting_operations=True, seed=0)
    s1.write_across_shots(km.array([a[0]]), np.array([[True]])); s1.do(bb.finish_circuit())
    n1 = int(s1.operation_statistics().num_toffoli_like)
    s2 = km.Simulator(batch_size=1, counting_operations=True, seed=0)
    s2.write_across_shots(km.array([a2[0]]), np.array([[False]])); s2.do(bb2.finish_circuit())
    n2 = int(s2.operation_statistics().num_toffoli_like)
    print(f'CSWAP applied-count sanity: ctrl=1 -> {n1}, ctrl=0 -> {n2}  (both 1 => APPLIED, not firing)', file=sys.stderr)
    assert n1 == 1 and n2 == 1, 'expected applied-counting semantics'
_cswap_counts()

# ---- simulate (operation_statistics is cumulative; read once at the end) ----
BS = 1024
sim = km.Simulator(batch_size=BS, debug_print=False, counting_operations=True, seed=0)
all_ok = True
n = len(xs)
for start in range(0, n, BS):
    stop = min(start+BS, n)
    cnt = stop-start
    pp = p_s[start:stop]; ss = s_s[start:stop]
    pin_bits = np.zeros((W, cnt), dtype=bool)
    for j in range(30):
        pin_bits[j] = ((pp >> j) & 1).astype(bool)
    sel_bits = np.zeros((SEL, cnt), dtype=bool)
    for m in range(SEL):
        sel_bits[m] = ((ss >> m) & 1).astype(bool)
    in_qubits = km.array(list(pin) + list(selin))
    in_bits = np.vstack([pin_bits, sel_bits])
    sim.clear_for_shot()
    sim.write_across_shots(in_qubits, in_bits)
    sim.do(circ)
    out = sim.read_across_shots(km.array(list(pin)))          # [W, cnt]
    got = (out.astype(np.uint64) << np.arange(W, dtype=np.uint64)[:, None]).sum(axis=0)
    want = (pp.astype(U64) << ss.astype(U64))
    bad = np.flatnonzero(got != want)
    if len(bad):
        all_ok = False
        print(f'MISMATCH at {len(bad)} shots, e.g. idx {bad[0]}: got {got[bad[0]]} want {want[bad[0]]} '
              f'(p={pp[bad[0]]}, s={ss[bad[0]]})', file=sys.stderr)

tot_toff = int(sim.operation_statistics().num_toffoli_like)
R = tot_toff / n
print(f'\ncorrectness (y==p<<s all shots): {all_ok}')
print(f'R_option_a (mean APPLIED toffoli-like, data-controlled barrel shift) = {R:.3f}')
print(f'  static toffoli-like in circuit = {stats_static.num_toffoli_like} (all unconditional -> applied every shot)')
print(f'  GATE: R <= 200 ?  {"PASS" if R <= 200 else "FAIL"}')
print(f'num_qubits used by prototype = {circ.num_qubits}  (pin {W} + selin {SEL})')
print(f'  -> in the real circuit these reuse existing p-register + s bits; no NEW persistent qubits expected')

import json
json.dump({'n_sample': int(n), 'correct': bool(all_ok),
           'R_option_a_applied': float(R),
           'gate_R_le_200': bool(R <= 200),
           'num_qubits_prototype': int(circ.num_qubits),
           'static_toffoli_like': int(stats_static.num_toffoli_like)},
          open('work/pa_prexperiment/data/step3_shift_sim.json', 'w'), indent=1)
print('saved work/pa_prexperiment/data/step3_shift_sim.json', file=sys.stderr)
