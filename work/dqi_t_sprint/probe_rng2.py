"""Identify kickmix Simulator's PRF: seed(256-bit) + counter -> 256 random bits."""
import hashlib
import struct

import numpy as np
import kickmix as km


def get_stream(seed, K=48):
    lines = ['X q0']
    for i in range(K):
        lines.append(f'HMR q0 b{i}')
        lines.append('X q0')
    c = km.Circuit('\n'.join(lines))
    sim = km.Simulator(batch_size=256, seed=seed)
    sim.use_same_registers_as(c)
    sim.do(c)
    # stream[i][j] = bit of op i, shot j
    cols = []
    for i in range(K):
        v = sim.read_across_shots(km.b(i), out=int)
        cols.append(np.array([(v >> j) & 1 for j in range(256)], dtype=np.uint8))
    return np.stack(cols)  # (K, 256)


def test_prf(name, F):
    """F(seed_int, counter_int) -> 256-bit int"""
    ok = True
    for seed in (0xDEADBEEF, 1, 2**255 + 7):
        stream = get_stream(seed, K=8)
        for i in range(8):
            got = stream[i]
            want = F(seed, i)
            wb = np.array([(want >> j) & 1 for j in range(256)], dtype=np.uint8)
            if not (got == wb).all():
                ok = False
                break
        if not ok:
            break
    print(f'{name}: {"MATCH" if ok else "no"}')
    return ok


seed32 = lambda s: s.to_bytes(32, 'little')
seed32be = lambda s: s.to_bytes(32, 'big')
c8 = lambda i: i.to_bytes(8, 'little')
c8be = lambda i: i.to_bytes(8, 'big')
c4 = lambda i: i.to_bytes(4, 'little')

cands = {
    'sha256(seed_le||c8le)': lambda s, i: int.from_bytes(hashlib.sha256(seed32(s) + c8(i)).digest(), 'big'),
    'sha256(seed_le||c8be)': lambda s, i: int.from_bytes(hashlib.sha256(seed32(s) + c8be(i)).digest(), 'big'),
    'sha256(seed_be||c8le)': lambda s, i: int.from_bytes(hashlib.sha256(seed32be(s) + c8(i)).digest(), 'big'),
    'sha256(c8le||seed_le)': lambda s, i: int.from_bytes(hashlib.sha256(c8(i) + seed32(s)).digest(), 'big'),
    'sha256(seed_le||c4le)': lambda s, i: int.from_bytes(hashlib.sha256(seed32(s) + c4(i)).digest(), 'big'),
    'sha256(c4le||seed_le)': lambda s, i: int.from_bytes(hashlib.sha256(c4(i) + seed32(s)).digest(), 'big'),
}
for name, F in cands.items():
    test_prf(name, F)

# splitmix64 over 4x64-bit words of seed, chained per counter
def sm64(x):
    x = (x + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    z = x
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
    return z, (z ^ (z >> 31))

def sm_chain(s, i):
    out = []
    x = s
    for _ in range(i * 4 + 4):
        x, z = sm64(x)
        if _ >= i * 4:
            out.append(z)
    return int.from_bytes(b''.join(struct.pack('<Q', w) for w in out), 'big')

test_prf('splitmix64 chain', sm_chain)

# maybe bits are little-endian packed
def sm_chain_le(s, i):
    out = []
    x = s
    for _ in range(i * 4 + 4):
        x, z = sm64(x)
        if _ >= i * 4:
            out.append(z)
    return int.from_bytes(b''.join(struct.pack('<Q', w) for w in out), 'little')

test_prf('splitmix64 chain LE', sm_chain_le)

# print actual first op bits for inspection
stream = get_stream(0xDEADBEEF, K=2)
print('\nop0 bits (shot0..15):', stream[0][:16].tolist())
print('op1 bits (shot0..15):', stream[1][:16].tolist())
v0 = int.from_bytes(stream[0], 'little')
print(f'op0 as LE int: {v0:#066x}')
print(f'op0 as BE int: {int.from_bytes(stream[0], "big"):#066x}')
