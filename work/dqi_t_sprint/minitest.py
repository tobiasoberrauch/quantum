"""Minimal single-gate tests vs kickmix, no RNG ops."""
import numpy as np
import kickmix as km

BATCH = 32


def km_run(kmx, nq, nb, init_q=None, init_b=None, seed=1):
    circuit = km.Circuit(kmx)
    sim = km.Simulator(batch_size=BATCH, seed=seed)
    sim.use_same_registers_as(circuit)
    for q, v in (init_q or {}).items():
        sim.write_across_shots(km.q(q), int.from_bytes(np.packbits(v).tobytes(), 'little'))
    for b, v in (init_b or {}).items():
        sim.read = None
        sim.write_across_shots(km.b(b), int.from_bytes(np.packbits(v).tobytes(), 'little'))
    sim.do(circuit)
    oq = {q: sim.read_across_shots(km.q(q), out=int) for q in range(nq)}
    ob = {b: sim.read_across_shots(km.b(b), out=int) for b in range(nb)}
    ph = sim.read_phase_flipped_across_shots(out=int)
    return oq, ob, ph


def to_int(arr):
    return int.from_bytes(np.packbits(arr.astype(bool)).tobytes(), 'little')


def check(name, got, want):
    ok = got == want
    print(f'{"OK " if ok else "FAIL"} {name}: got={got:#x} want={want:#x}')
    return ok


# all-ones mask
O = np.ones(BATCH, dtype=bool)
Z = np.zeros(BATCH, dtype=bool)

# CX q0->q1, q0=1 q1=0 => q1=1
oq, ob, ph = km_run('CX q0 q1', 2, 0, init_q={0: O, 1: Z})
print('CX 1,0 ->', 'q1=', bin(oq[1]), '(want all ones)')

# CX q0->q1, q0=0 => q1 unchanged
oq, ob, ph = km_run('CX q0 q1', 2, 0, init_q={0: Z, 1: O})
print('CX 0,1 ->', 'q1=', bin(oq[1]), '(want all ones)')

# X q0
oq, ob, ph = km_run('X q0', 1, 0, init_q={0: Z})
print('X 0 ->', 'q0=', bin(oq[0]), '(want all ones)')

# CZ phase: q0=q1=1 => phase flipped on all shots
oq, ob, ph = km_run('CZ q0 q1', 2, 0, init_q={0: O, 1: O})
print('CZ 1,1 phase=', bin(ph), '(want all ones)')

# Z phase: q0=1 => phase
oq, ob, ph = km_run('Z q0', 1, 0, init_q={0: O})
print('Z 1 phase=', bin(ph), '(want all ones)')

# CCX: q0=q1=1 -> q2 flips
oq, ob, ph = km_run('CCX q0 q1 q2', 3, 0, init_q={0: O, 1: O, 2: Z})
print('CCX 1,1,0 ->', 'q2=', bin(oq[2]), '(want all ones)')

# CCZ: 1,1,1 -> phase
oq, ob, ph = km_run('CCZ q0 q1 q2', 3, 0, init_q={0: O, 1: O, 2: O})
print('CCZ 1,1,1 phase=', bin(ph), '(want all ones)')

# SWAP
oq, ob, ph = km_run('SWAP q0 q1', 2, 0, init_q={0: O, 1: Z})
print('SWAP 1,0 ->', 'q0=', bin(oq[0]), 'q1=', bin(oq[1]), '(want 0,1)')

# CSWAP ctrl=1
oq, ob, ph = km_run('CSWAP q0 q1 q2', 3, 0, init_q={0: O, 1: O, 2: Z})
print('CSWAP 1;1,0 ->', 'q1=', bin(oq[1]), 'q2=', bin(oq[2]), '(want 0,1)')

# BIT ops
oq, ob, ph = km_run('BIT_INVERT b0', 0, 1, init_b={0: Z})
print('BIT_INVERT 0 ->', 'b0=', bin(ob[0]), '(want all ones)')
oq, ob, ph = km_run('BIT_STORE1 b0', 0, 1, init_b={0: Z})
print('BIT_STORE1 ->', 'b0=', bin(ob[0]), '(want all ones)')

# X_IF b0=1
oq, ob, ph = km_run('X q0 if b0', 1, 1, init_b={0: O})
print('X_IF b=1 ->', 'q0=', bin(oq[0]), '(want all ones)')

# Z_IF b0=1, q0=1 -> phase
oq, ob, ph = km_run('Z q0 if b0', 1, 1, init_q={0: O}, init_b={0: O})
print('Z_IF b=1 q=1 phase=', bin(ph), '(want all ones)')

# PUSH_CONDITION if b0=1 then X q0
oq, ob, ph = km_run('PUSH_CONDITION if b0\nX q0\nPOP_CONDITION', 1, 1, init_b={0: O})
print('PUSH(b=1) X ->', 'q0=', bin(oq[0]), '(want all ones)')
oq, ob, ph = km_run('PUSH_CONDITION if b0\nX q0\nPOP_CONDITION', 1, 1, init_b={0: Z})
print('PUSH(b=0) X ->', 'q0=', bin(oq[0]), '(want all zeros)')

# NEG_IF b0=1 -> phase
oq, ob, ph = km_run('NEG if b0', 0, 1, init_b={0: O})
print('NEG_IF b=1 phase=', bin(ph), '(want all ones)')
