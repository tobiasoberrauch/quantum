"""Task 1, prong B: IN-CIRCUIT prototype of the generic s-routing for new y-bit taps.

y_i = p_{i-s} = OR_{k=0..10} [ (s==k) AND p_{i-k} ]  (terms mutually exclusive).
Build: shared s-decode eq_k=(s==k) for k=0..10, then per bit i: term_k=eq_k AND p_{i-k}
(1 CCX), accumulate A_i ^= term_k (free CX). Measure MARGINAL APPLIED toffolis
(num_toffoli_like, validated applied-counting). Scratch ancillas HMR-cleared (free).
Test bits i in {10,22,25} (all >=10 -> i-k in 0..29, no clamping).
"""
import sys, json
import numpy as np
import kickmix as km

U64, I64 = np.uint64, np.int64
N = 3 * (2**10 - 2)**2
p_all = np.load('work/pa_prexperiment/data/p.npy')
s_all = np.load('work/pa_prexperiment/data/s.npy')
P_W, S_W = 30, 4
KS = list(range(0, 11))

def build_router(test_bits):
    b = km.CircuitBuilder()
    P = b.create_quantum_register(P_W, 'P')
    S = b.create_quantum_register(S_W, 'S')
    Snot = b.alloc_qubits(S_W)
    for m in range(S_W):
        b.x(Snot[m]); b.cx(S[m], Snot[m])          # Snot[m] = NOT S[m] (free)
    def literal(m, val): return S[m] if val else Snot[m]
    eq = {}
    for k in KS:
        e = b.alloc_qubits(1)[0]
        b.cx(literal(0, k & 1), e)                 # e = lit_0 (free CNOT into |0>)
        for m in range(1, S_W):                    # e := e AND lit_m  (3 CCX)
            t = b.alloc_qubits(1)[0]
            b.ccx(e, literal(m, (k >> m) & 1), t)
            b.hmr(e, b.alloc_bits(1)[0])           # clear old e (scratch)
            e = t
        eq[k] = e
    accs = {}
    for i in test_bits:
        A = b.alloc_qubits(1)[0]                   # accumulator (|0>)
        for k in KS:
            ik = i - k
            if ik < 0 or ik >= P_W: continue
            t = b.alloc_qubits(1)[0]
            b.ccx(eq[k], P[ik], t)                 # t = eq_k AND p_{i-k}
            b.cx(t, A)                             # A ^= t (mutually exclusive -> OR)
            b.hmr(t, b.alloc_bits(1)[0])
        accs[i] = A
    return b.finish_circuit(), P, S, accs

def measure(circ, P, S, accs, idx):
    pp = p_all[idx]; ss = s_all[idx]
    inq = km.array(list(P) + list(S))
    pin = np.zeros((P_W + S_W, len(idx)), dtype=bool)
    for j in range(P_W): pin[j] = ((pp >> j) & 1).astype(bool)
    for m in range(S_W): pin[P_W + m] = ((ss >> m) & 1).astype(bool)
    BS = 1024
    sim = km.Simulator(batch_size=BS, debug_print=False, counting_operations=True, seed=0)
    ok = True
    for st in range(0, len(idx), BS):
        en = min(st + BS, len(idx))
        sim.clear_for_shot()
        sim.write_across_shots(inq, pin[:, st:en])
        sim.do(circ)
        for i, A in accs.items():
            got = sim.read_across_shots(km.array([A]))[0]
            want = ((pp[st:en] >> (i - ss[st:en])) & 1).astype(bool)
            ok = ok and bool(np.array_equal(got, want))
    return int(sim.operation_statistics().num_toffoli_like) / len(idx), ok

rng = np.random.default_rng(0)
sel = []
for sv in range(11):
    cls = np.flatnonzero(s_all == sv)
    sel.append(rng.choice(cls, size=min(len(cls), max(30, int(0.05 * len(cls)))), replace=False))
idx = np.concatenate(sel); rng.shuffle(idx)
BS = 1024
target = int(np.ceil(len(idx)/BS))*BS
if len(idx) < target:
    idx = np.concatenate([idx, rng.choice(idx, size=target-len(idx), replace=True)])
idx = idx[:target]
print(f'sample n={len(idx)}', file=sys.stderr)

c0, P0, S0, a0 = build_router([])
t0, ok0 = measure(c0, P0, S0, {}, idx)
print(f'T_decode (shared s-decode, no bits) = {t0:.2f} applied toffolis  correct={ok0}')

margs = {}
for i in [10, 22, 25]:
    ci, Pi, Si, ai = build_router([i])
    ti, oki = measure(ci, Pi, Si, ai, idx)
    margs[i] = ti - t0
    print(f'bit i={i}: total={ti:.2f}  marginal={ti-t0:.2f}  correct={oki}')

c3, P3, S3, a3 = build_router([10, 22, 25])
t3, ok3 = measure(c3, P3, S3, a3, idx)
per_bit_avg = (t3 - t0) / 3
print(f'bits {{10,22,25}} together: total={t3:.2f}  over-decode={t3-t0:.2f}  correct={ok3}')
print(f'\nEXTRAPOLATION to 19 new bits: R_total ~= T_decode + 19*per_bit = {t0:.1f} + 19*{per_bit_avg:.1f} = {t0 + 19*per_bit_avg:.1f}')
json.dump({'T_decode': round(t0,2), 'marginals': {str(k): round(v,2) for k,v in margs.items()},
           'per_bit_avg': round(per_bit_avg,2), 'three_total': round(t3,2),
           'R_extrap_19': round(t0+19*per_bit_avg,1), 'correct': bool(ok0 and ok3)},
          open('work/pa_prexperiment/data/task1_proto.json','w'), indent=1)
print('saved work/pa_prexperiment/data/task1_proto.json')
