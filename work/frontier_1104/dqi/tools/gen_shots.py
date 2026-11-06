#!/usr/bin/env python3
"""Dump bit-sliced initial states for the C analyser.

Usage: gen_shots.py <kmb> <out.bin> <num_shots(multiple of 64)> <seed> <frac_uniform_weight>
Layout: header 4 x u64 (num_qubits, num_bits, W, num_shots), then qubit words, then bit words.
Shots use the verifier's own sampler; a fraction uses uniform weight over 0..35 to require
identities to hold on low-weight inputs too (not just the distribution's bulk).
"""
import struct
import sys

import numpy as np

ROOT = '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum'
sys.path.insert(0, ROOT + '/data/verifiers')
import kickmix as km
from dqi import verify_submission_dqi as v


def main() -> None:
    path, out, n, seed, frac = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), float(sys.argv[5])
    if n % 64:
        raise SystemExit('num_shots must be a multiple of 64')
    spec = v.ProblemSpecDQI.benchmark_instance()
    c = km.Circuit.from_file(path, format='kmb')
    tables = v.FieldTables(km.GF2Field(spec.degree))
    rng = np.random.default_rng(seed)
    probs = v.optimal_dqi_weights(spec.m, spec.max_errors, spec.degree, spec.r) ** 2
    n_uni = int(n * frac)
    parts = []
    if n - n_uni:
        parts.append(v.sample_shots(spec, tables, rng, n - n_uni, probs))
    if n_uni:
        parts.append(v.sample_shots(spec, tables, rng, n_uni, np.full(36, 1 / 36)))
    syn = np.concatenate([p[0] for p in parts])
    mbuc = np.concatenate([p[1] for p in parts])
    phases = np.concatenate([p[2] for p in parts])
    perm = rng.permutation(n)
    syn, mbuc, phases = syn[perm], mbuc[perm], phases[perm]
    regs = c.register_data
    W = n // 64
    nq, nb = c.num_qubits, c.num_bits
    q = np.zeros((nq, W), dtype=np.uint64)
    b = np.zeros((nb, W), dtype=np.uint64)

    def pack(arr: np.ndarray) -> np.ndarray:
        return np.packbits(arr.astype(np.uint8), bitorder='little').reshape(-1, 8).copy().view(np.uint64).reshape(-1)

    for i in range(spec.n):
        for k, x in enumerate(regs[f'S{i}']):
            q[x.id] = pack((syn[:, i] >> k) & 1)
    for j in range(spec.m):
        for k, x in enumerate(regs[f'E{j}']):
            b[x.id] = pack((mbuc[:, j] >> k) & 1)
    with open(out, 'wb') as f:
        f.write(struct.pack('<4Q', nq, nb, W, n))
        f.write(q.tobytes())
        f.write(b.tobytes())
        f.write(pack(phases).tobytes())
    print('wrote', out, nq, nb, W, n)


if __name__ == '__main__':
    main()
