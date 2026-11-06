"""Bit-parallel basis-state simulator with phase tracking for dqi.kmb.

Replicates the verifier's shot sampling (same RNG logic) and simulates the
circuit on basis-state inputs: per-qubit/per-bit values as uint32 masks over
32 shots, plus a per-shot phase bit. Verifies:
  (1) original circuit: phase == expected p(s), syndromes restored, ancillas |0>
  (2) un* region net phase == 0 (precondition for deletion)
  (3) modified circuit (after surgery): same checks
"""
import importlib.util
import json
import sys
import time
from collections import Counter

import numpy as np

ROOT = '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum'
KMB = f'{ROOT}/work/frontier_scan/mwa_unpacked/dqi.kmb'

# ---------------- shot sampling (copied logic from verifier) ----------------
import math


def field_tables(degree):
    # replicate km.GF2Field primitive element behavior: kickmix GF2Field(b)
    # uses primitive polynomial; we need pow tables. Use kickmix itself.
    import kickmix as km
    f = km.GF2Field(degree)
    order = (1 << degree) - 1
    prim = f.primitive_element
    antilog = np.array([f.pow(prim, k) for k in range(order)], dtype=np.int64)
    log = np.zeros(1 << degree, dtype=np.int64)
    log[antilog] = np.arange(order)
    return f, log, antilog


def optimal_dqi_weights(m, max_errors, degree, r):
    q = 1 << degree
    k = np.arange(max_errors + 1, dtype=np.float64)
    off = np.sqrt(k[1:] * (m - k[1:] + 1))
    d = (q - 2 * r) / math.sqrt(r * (q - r))
    _, vecs = np.linalg.eigh(np.diag(k * d) + np.diag(off, 1) + np.diag(off, -1))
    w = np.abs(vecs[:, -1])
    return w / np.linalg.norm(w)


def sample_shots(spec_m, spec_n, degree, r, num_shots, rng):
    f, log, antilog = field_tables(degree)
    l = spec_n // 2
    wp = optimal_dqi_weights(spec_m, l, degree, r) ** 2
    max_value = (1 << degree) - 1
    weights = rng.choice(len(wp), size=num_shots, p=wp)
    mbuc = rng.integers(0, max_value, size=(num_shots, spec_m), endpoint=True, dtype=np.int64)
    syndromes = np.zeros((num_shots, spec_n), dtype=np.int64)
    phases = np.zeros(num_shots, dtype=bool)
    rows = np.arange(1, spec_n + 1, dtype=np.int64)[:, None]
    for shot in np.flatnonzero(weights):
        k = int(weights[shot])
        pos = rng.choice(spec_m, size=k, replace=False)
        vals = rng.integers(1, max_value, size=k, endpoint=True, dtype=np.int64)
        exps = (log[vals][None, :] + rows * pos[None, :]) % (max_value)
        syndromes[shot] = np.bitwise_xor.reduce(antilog[exps], axis=1)
        phases[shot] = sum(int(x).bit_count() for x in vals & mbuc[shot, pos]) & 1 == 1
    return syndromes, mbuc, phases, weights


def to_bits(values, degree):
    bits = (values[:, :, None] >> np.arange(degree)) & 1 == 1
    return bits.transpose(1, 2, 0).reshape(-1, len(values))


# ---------------- circuit loading ----------------
spec = importlib.util.spec_from_file_location('wl', f'{ROOT}/work/dqi_sources/width_liveness.py')
wl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wl)


def load(path):
    r = wl.KmbReader(path)
    return r


def simulate(r, syndromes_bits, mbuc_bits, num_shots, batch=32, progress=True):
    """syndromes_bits: (840, num_shots) bool; mbuc_bits: (49140, num_shots) bool."""
    t = r.types
    N = r.num_ops
    nq = r.num_qubits
    nb = r.num_bits
    VQ = np.zeros((nq, batch), dtype=np.uint32)  # qubit values per shot-lane
    VB = np.zeros((nb, batch), dtype=np.uint32)
    PH = np.zeros(batch, dtype=np.uint32)       # phase bit per lane
    # initialize: syndrome qubits (ids 0..839 in register order S0..S69 x 12)
    # map: bit row i of syndromes_bits -> qubit id? Registers S{i} = 12 qubits.
    # KmbReader.registers gives name->qubit ids. Build id->row.
    qid_row = {}
    for i in range(70):
        qs = r.registers[f'S{i}']
        for j, q in enumerate(qs):
            qid_row[q] = i * 12 + j
    for q, row in qid_row.items():
        VQ[q] = syndromes_bits[row].astype(np.uint32)
    # E bits: bit id 0..49139 = E0..E4094 x 12 (verify: E bits were ids 0..49139)
    for i in range(4095):
        bs = r.registers[f'E{i}']
        for j, b in enumerate(bs):
            VB[b] = mbuc_bits[i * 12 + j].astype(np.uint32)

    # precompute per-type index arrays
    def pos_of(typeset):
        lut = np.zeros(256, dtype=bool)
        lut[list(typeset)] = True
        return np.flatnonzero(lut[t]).astype(np.int64)

    P1 = pos_of([0x10, 0x90, 0x11, 0x91, 0x12, 0x92, 0x13, 0x93, 0x50, 0xD0])
    P2 = pos_of([0x20, 0xA0, 0x21, 0xA1, 0x22, 0xA2])
    P3 = pos_of([0x30, 0xB0, 0x31, 0xB1, 0x32, 0xB2])
    PB = pos_of([0x40, 0xC0, 0x41, 0xC1, 0x42, 0xC2, 0x50, 0xD0])
    PC = pos_of([0xB0, 0xB1, 0xB2, 0xA0, 0xA1, 0xA2, 0x90, 0x91, 0x92, 0x93,
                 0xC0, 0xC1, 0xC2, 0xD0, 0x80, 0x81])
    PT = pos_of([0x06])

    q1 = r.q1.astype(np.int32)
    q2a = r.q2a.astype(np.int32); q2b = r.q2b.astype(np.int32)
    q3a = r.q3a.astype(np.int32); q3b = r.q3b.astype(np.int32); q3c = r.q3c.astype(np.int32)
    b1 = r.b1.astype(np.int32)
    bc = r.bcond.astype(np.int32)

    t1 = t[P1].astype(np.int32)
    t2 = t[P2].astype(np.int32)
    t3 = t[P3].astype(np.int32)
    tb = t[PB].astype(np.int32)
    tc = t[PC].astype(np.int32)

    # process ops in stream order: merge all position arrays with type
    # We'll iterate per-class with pointers (classes are sorted by position).
    n1, n2, n3, nb_, nc, nt = len(P1), len(P2), len(P3), len(PB), len(PC), len(PT)
    i1 = i2 = i3 = ib = ic = it = 0
    p1 = P1[i1] if n1 else N
    p2 = P2[i2] if n2 else N
    p3 = P3[i3] if n3 else N
    pb = PB[ib] if nb_ else N
    pc = PC[ic] if nc else N
    pt = PT[it] if nt else N

    toff_exec = 0
    t0 = time.time()
    for p in range(N):
        if p == p1:
            tt = int(t1[i1]); q = int(q1[i1])
            if tt == 0x11:
                VQ[q] ^= 0xFFFFFFFF
            elif tt == 0x91:
                VQ[q] &= ~VB[bc[ic - 1]] if False else VQ[q]  # placeholder
            i1 += 1
            p1 = P1[i1] if i1 < n1 else N
        # ... (full dispatch below)
    raise NotImplementedError('use vectorized dispatch version')


if __name__ == '__main__':
    print('run sim2.py for the vectorized version')
