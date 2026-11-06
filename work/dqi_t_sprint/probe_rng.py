"""Probe kickmix Simulator HMR/R randomness:
1. Is HMR outcome random (X-basis) or deterministic (Z-basis)?
2. Phase contribution of HMR on |1> vs |0>.
3. Does R consume a random bit?
4. Identify the PRF mapping seed -> bitstream.
"""
import hashlib

import numpy as np
import kickmix as km


def run(circuit_src, seed, nbits_read=0):
    c = km.Circuit(circuit_src)
    sim = km.Simulator(batch_size=256, seed=seed)
    sim.use_same_registers_as(c)
    sim.do(c)
    out = {}
    for i in range(nbits_read):
        out[f'b{i}'] = sim.read_across_shots(km.b(i), out=int)
    out['phase'] = sim.read_phase_flipped_across_shots(out=int)
    for i in range(c.num_qubits):
        out[f'q{i}'] = sim.read_across_shots(km.q(i), out=int)
    return out


# 1. HMR on |1>: random or deterministic?
r = run('X q0\nHMR q0 b0', seed=12345, nbits_read=1)
b0 = r['b0']
print(f'HMR on |1>: popcount(b0)={b0.bit_count()}/256  phase_popcount={r["phase"].bit_count()}/256')
print(f'  phase == b0? {r["phase"] == b0}')

# HMR on |0>
r = run('HMR q0 b0', seed=12345, nbits_read=1)
print(f'HMR on |0>: popcount(b0)={r["b0"].bit_count()}/256  phase_popcount={r["phase"].bit_count()}/256')

# 2. R on |1>: phase effect?
r = run('X q0\nR q0', seed=12345)
print(f'R on |1>: phase_popcount={r["phase"].bit_count()}/256  q0={r["q0"].bit_count()}/256')

# 3. Does R consume a random bit? Compare HMR-after-R vs HMR-alone with same seed:
rA = run('R q0\nHMR q1 b0', seed=999, nbits_read=1)   # q1 = |0>
rB = run('HMR q1 b0', seed=999, nbits_read=1)         # q1 = |0>
print(f'R consumes random bit? HMR after R: pop={rA["b0"].bit_count()} vs HMR alone: pop={rB["b0"].bit_count()} equal={rA["b0"]==rB["b0"]}')

# 4. Long HMR stream to identify PRF: alternate X/HMR on q0 (value stays |1>)
K = 64
lines = ['X q0']
for i in range(K):
    lines.append(f'HMR q0 b{i}')
    lines.append('X q0')
src = '\n'.join(lines)
r = run(src, seed=0xDEADBEEF, nbits_read=K)
stream = np.array([(r[f'b{i}'] >> j) & 1 for i in range(K) for j in range(256)], dtype=np.uint8)
# stream[i*256 + j] = bit i, shot j
print(f'\nPRF probe: seed=0xDEADBEEF, first 16 bits of shot 0: {stream[::256][:16]}')

seed_bytes = (0xDEADBEEF).to_bytes(8, 'little')
# candidate 1: sha256(seed || counter)
cand_sha = []
for i in range(K):
    d = hashlib.sha256(seed_bytes + i.to_bytes(8, 'little')).digest()
    cand_sha.append(d[0] & 1)
print('sha256(seed||i) match:', cand_sha == list(stream[::256][:K]))

# candidate 2: sha256(counter || seed)
cand_sha2 = []
for i in range(K):
    d = hashlib.sha256(i.to_bytes(8, 'little') + seed_bytes).digest()
    cand_sha2.append(d[0] & 1)
print('sha256(i||seed) match:', cand_sha2 == list(stream[::256][:K]))

# candidate 3: splitmix64 chain
def splitmix64(x):
    x = (x + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    z = x
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
    return z, (z ^ (z >> 31))
x = 0xDEADBEEF
cand_sm = []
for i in range(K):
    x, z = splitmix64(x)
    cand_sm.append(z & 1)
print('splitmix64 chain match:', cand_sm == list(stream[::256][:K]))

# candidate 4: each shot independent? check bit i across shots: is stream[i][j] a function of (i,j)?
# test: does shot j use seed-derived per-shot value? e.g. sha256(seed || j)
cand_shot = []
for j in range(8):
    col = [stream[i * 256 + j] for i in range(K)]
    d = hashlib.sha256(seed_bytes + j.to_bytes(8, 'little')).digest()
    cand_shot.append(col[:len(d) * 8] == [(d[k] >> (k % 8)) & 1 for k in range(len(d) * 8)])
print('per-shot sha256(seed||j) match (first 8 shots):', cand_shot)
