"""Bit-parallel basis-state simulator with phase tracking for dqi.kmb (32 lanes).

Validates against the original circuit first (must reproduce expected phase
p(s), syndrome restoration, ancilla |0>), then measures the un* region's net
phase, then validates the surgically modified circuit.

Usage:
  sim2.py <kmb> [--shots 512] [--check-original]   # full validation
  sim2.py <kmb> [--shots 512] --region-phase       # print un* net phase per shot
"""
import importlib.util
import json
import math
import sys
import time

import numpy as np

ROOT = '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum'

spec = importlib.util.spec_from_file_location('wl', f'{ROOT}/work/dqi_sources/width_liveness.py')
wl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wl)

ALL = np.uint32(0xFFFFFFFF)


def field_tables(degree):
    import kickmix as km
    f = km.GF2Field(degree)
    order = (1 << degree) - 1
    prim = f.primitive_element
    antilog = np.array([f.pow(prim, k) for k in range(order)], dtype=np.int64)
    log = np.zeros(1 << degree, dtype=np.int64)
    log[antilog] = np.arange(order)
    return log, antilog


def optimal_dqi_weights(m, max_errors, degree, r):
    q = 1 << degree
    k = np.arange(max_errors + 1, dtype=np.float64)
    off = np.sqrt(k[1:] * (m - k[1:] + 1))
    d = (q - 2 * r) / math.sqrt(r * (q - r))
    _, vecs = np.linalg.eigh(np.diag(k * d) + np.diag(off, 1) + np.diag(off, -1))
    w = np.abs(vecs[:, -1])
    return w / np.linalg.norm(w)


def sample_shots(m, n, degree, r, num_shots, rng):
    log, antilog = field_tables(degree)
    l = n // 2
    wp = optimal_dqi_weights(m, l, degree, r) ** 2
    max_value = (1 << degree) - 1
    weights = rng.choice(len(wp), size=num_shots, p=wp)
    mbuc = rng.integers(0, max_value, size=(num_shots, m), endpoint=True, dtype=np.int64)
    syndromes = np.zeros((num_shots, n), dtype=np.int64)
    phases = np.zeros(num_shots, dtype=bool)
    rows = np.arange(1, n + 1, dtype=np.int64)[:, None]
    for shot in np.flatnonzero(weights):
        k = int(weights[shot])
        pos = rng.choice(m, size=k, replace=False)
        vals = rng.integers(1, max_value, size=k, endpoint=True, dtype=np.int64)
        exps = (log[vals][None, :] + rows * pos[None, :]) % max_value
        syndromes[shot] = np.bitwise_xor.reduce(antilog[exps], axis=1)
        phases[shot] = sum(int(x).bit_count() for x in vals & mbuc[shot, pos]) & 1 == 1
    return syndromes, mbuc, phases, weights


def to_bits(values, degree):
    bits = (values[:, :, None] >> np.arange(degree)) & 1 == 1
    return bits.transpose(1, 2, 0).reshape(-1, len(values))


def initial_seed(circuit_hash, salt=''):
    if not salt:
        return int(circuit_hash, 16)
    import hashlib
    return int(hashlib.sha256(f'{circuit_hash}{salt}'.encode()).hexdigest(), 16)


def make_batches(base_seed, num_batches):
    ss = np.random.SeedSequence(base_seed, pool_size=8)
    seeds = ss.generate_state(8 * num_batches, dtype=np.uint64).reshape(-1, 2, 4)
    out = []
    for i in range(num_batches):
        out.append((int.from_bytes(seeds[i, 0], 'little'), int.from_bytes(seeds[i, 1], 'little')))
    return out


class Sim:
    def __init__(self, kmb_path, nq_override=None):
        self.r = wl.KmbReader(kmb_path)
        self.t = self.r.types
        self.N = self.r.num_ops
        self.nq = self.r.num_qubits if nq_override is None else nq_override
        self.nb = self.r.num_bits
        t = self.t
        def pos_of(typeset):
            lut = np.zeros(256, dtype=bool)
            lut[list(typeset)] = True
            return np.flatnonzero(lut[t]).astype(np.int64)
        self.P1 = pos_of([0x10, 0x90, 0x11, 0x91, 0x12, 0x92, 0x13, 0x93, 0x50, 0xD0])
        self.P2 = pos_of([0x20, 0xA0, 0x21, 0xA1, 0x22, 0xA2])
        self.P3 = pos_of([0x30, 0xB0, 0x31, 0xB1, 0x32, 0xB2])
        self.PB = pos_of([0x40, 0xC0, 0x41, 0xC1, 0x42, 0xC2, 0x50, 0xD0])
        self.PC = pos_of([0xB0, 0xB1, 0xB2, 0xA0, 0xA1, 0xA2, 0x90, 0x91, 0x92, 0x93,
                          0xC0, 0xC1, 0xC2, 0xD0, 0x80, 0x81])
        self.PT = pos_of([0x06])
        self.q1 = self.r.q1.astype(np.int32)
        self.q2a = self.r.q2a.astype(np.int32); self.q2b = self.r.q2b.astype(np.int32)
        self.q3a = self.r.q3a.astype(np.int32); self.q3b = self.r.q3b.astype(np.int32)
        self.q3c = self.r.q3c.astype(np.int32)
        self.b1 = self.r.b1.astype(np.int32)
        self.bc = self.r.bcond.astype(np.int32)
        self.t1 = t[self.P1].astype(np.int32)
        self.t2 = t[self.P2].astype(np.int32)
        self.t3 = t[self.P3].astype(np.int32)
        self.tb = t[self.PB].astype(np.int32)
        self.tc = t[self.PC].astype(np.int32)
        # syndrome qubit id -> input row
        self.qid_row = {}
        for i in range(70):
            qs = self.r.registers[f'S{i}']
            for j, q in enumerate(qs):
                self.qid_row[int(q)] = i * 12 + j
        self.e_bit_row = {}
        for i in range(4095):
            bs = self.r.registers[f'E{i}']
            for j, b in enumerate(bs):
                self.e_bit_row[int(b)] = i * 12 + j

    def run_batch(self, syn_bits, mbuc_bits, region_marks=None):
        """syn_bits: (840,32) uint32 masks; mbuc_bits: (49140,32) uint32.
        Returns dict with final values, phase, toffoli count, optional region phases."""
        VQ = np.zeros((self.nq, 32), dtype=np.uint32)
        VB = np.zeros((self.nb, 32), dtype=np.uint32)
        PH = np.zeros(32, dtype=np.uint32)
        for q, row in self.qid_row.items():
            VQ[q] = syn_bits[row]
        for b, row in self.e_bit_row.items():
            VB[b] = mbuc_bits[row]

        P1, P2, P3, PB, PC, PT = self.P1, self.P2, self.P3, self.PB, self.PC, self.PT
        n1, n2, n3, nb_, nc, nt = len(P1), len(P2), len(P3), len(PB), len(PC), len(PT)
        i1 = i2 = i3 = ib = ic = it = 0
        p1 = P1[0] if n1 else self.N
        p2 = P2[0] if n2 else self.N
        p3 = P3[0] if n3 else self.N
        pb = PB[0] if nb_ else self.N
        pc = PC[0] if nc else self.N
        pt = PT[0] if nt else self.N
        t1, t2, t3, tb, tc = self.t1, self.t2, self.t3, self.tb, self.tc
        q1, q2a, q2b = self.q1, self.q2a, self.q2b
        q3a, q3b, q3c = self.q3a, self.q3b, self.q3c
        b1, bc = self.b1, self.bc
        toff = 0
        region_phases = {}
        N = self.N
        for p in range(N):
            if p == p1:
                tt = t1[i1]; q = q1[i1]
                if tt == 0x10:
                    PH ^= VQ[q]
                elif tt == 0x90:
                    PH ^= VB[bc[ic]] & VQ[q]
                elif tt == 0x11:
                    VQ[q] ^= ALL
                elif tt == 0x91:
                    VQ[q] ^= VB[bc[ic]]
                elif tt == 0x12:
                    VQ[q] = 0
                elif tt == 0x92:
                    VQ[q] &= ~VB[bc[ic]]
                elif tt == 0x50:
                    VB[b1[ib]] = VQ[q]; VQ[q] = 0
                elif tt == 0xD0:
                    m = VB[bc[ic]]; VB[b1[ib]] = VQ[q] & m; VQ[q] &= ~m
                i1 += 1; p1 = P1[i1] if i1 < n1 else N
            if p == p2:
                tt = t2[i2]; a = q2a[i2]; b = q2b[i2]
                if tt == 0x20:
                    PH ^= VQ[a] & VQ[b]
                elif tt == 0xA0:
                    PH ^= VB[bc[ic]] & VQ[a] & VQ[b]
                elif tt == 0x21:
                    VQ[b] ^= VQ[a]
                elif tt == 0xA1:
                    VQ[b] ^= VB[bc[ic]] & VQ[a]
                elif tt == 0x22:
                    va = VQ[a].copy(); VQ[a] = VQ[b]; VQ[b] = va
                elif tt == 0xA2:
                    m = VB[bc[ic]]; d = VQ[a] ^ VQ[b]; VQ[a] ^= d & m; VQ[b] ^= d & m
                i2 += 1; p2 = P2[i2] if i2 < n2 else N
            if p == p3:
                tt = t3[i3]; a = q3a[i3]; b = q3b[i3]; c = q3c[i3]
                if tt == 0x30:
                    PH ^= VQ[a] & VQ[b] & VQ[c]
                elif tt == 0xB0:
                    PH ^= VB[bc[ic]] & VQ[a] & VQ[b] & VQ[c]
                elif tt == 0x31:
                    VQ[c] ^= VQ[a] & VQ[b]; toff += 1
                elif tt == 0xB1:
                    VQ[c] ^= VB[bc[ic]] & VQ[a] & VQ[b]; toff += int(np.count_nonzero(VB[bc[ic]]))
                elif tt == 0x32:
                    m = VQ[a]; d = VQ[b] ^ VQ[c]; VQ[b] ^= d & m; VQ[c] ^= d & m; toff += 1
                elif tt == 0xB2:
                    m = VQ[a] & VB[bc[ic]]; d = VQ[b] ^ VQ[c]; VQ[b] ^= d & m; VQ[c] ^= d & m
                    toff += int(np.count_nonzero(m))
                i3 += 1; p3 = P3[i3] if i3 < n3 else N
            if p == pb:
                tt = tb[ib]; b = b1[ib]
                if tt == 0x40:
                    VB[b] = 0
                elif tt == 0xC0:
                    VB[b] &= ~VB[bc[ic]]
                elif tt == 0x41:
                    VB[b] = ALL
                elif tt == 0xC1:
                    VB[b] |= VB[bc[ic]]
                elif tt == 0x42:
                    VB[b] ^= ALL
                elif tt == 0xC2:
                    VB[b] ^= VB[bc[ic]]
                ib += 1; pb = PB[ib] if ib < nb_ else N
            if p == pc:
                ic += 1; pc = PC[ic] if ic < nc else N
            if p == pt:
                it += 1; pt = PT[it] if it < nt else N
            if region_marks:
                for name, mark_p in region_marks.items():
                    if p == mark_p:
                        region_phases[name] = PH.copy()
        return dict(VQ=VQ, VB=VB, PH=PH, toff=toff, region_phases=region_phases)


def main():
    args = sys.argv[1:]
    kmb = args[0]
    shots = 512
    if '--shots' in args:
        shots = int(args[args.index('--shots') + 1])
    region_mode = '--region-phase' in args

    import hashlib
    h = hashlib.sha256()
    with open(kmb, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 22), b''):
            h.update(chunk)
    chash = h.hexdigest()
    print(f'[sim] {kmb}\n[sim] sha256={chash}', file=sys.stderr)

    sim = Sim(kmb)
    print(f'[sim] ops={sim.N:,} nq={sim.nq} nb={sim.nb}', file=sys.stderr)

    base_seed = initial_seed(chash)
    nbatches = shots // 32
    batches = make_batches(base_seed, nbatches)

    m, n, degree, r = 4095, 70, 12, 2016
    all_syn = np.zeros((840, shots), dtype=np.uint32)
    all_mbuc = np.zeros((49140, shots), dtype=np.uint32)
    all_phase_exp = np.zeros(shots, dtype=np.uint32)
    all_weights = np.zeros(shots, dtype=np.int64)
    for bi, (rng_seed, sim_seed) in enumerate(batches):
        rng = np.random.default_rng(rng_seed)
        synd, mbuc, phases, weights = sample_shots(m, n, degree, r, 32, rng)
        sb = to_bits(synd, degree)      # (840, 32)
        mb = to_bits(mbuc, degree)      # (49140, 32)
        all_syn[:, bi * 32:(bi + 1) * 32] = sb.astype(np.uint32)
        all_mbuc[:, bi * 32:(bi + 1) * 32] = mb.astype(np.uint32)
        all_phase_exp[bi * 32:(bi + 1) * 32] = phases.astype(np.uint32)
        all_weights[bi * 32:(bi + 1) * 32] = weights
        t0 = time.time()
        marks = None
        if region_mode:
            # find un* region marks
            tagpos = np.flatnonzero(sim.t == 0x06)
            mp = {}
            for p, s in zip(tagpos.tolist(), sim.r.tag_strings):
                if s == '@enter:unconvert':
                    mp['unconv_in'] = p
                if s == '@exit:unextract':
                    mp['unext_out'] = p
            marks = mp
        res = sim.run_batch(all_syn[:, bi * 32:(bi + 1) * 32],
                            all_mbuc[:, bi * 32:(bi + 1) * 32], marks)
        dt = time.time() - t0
        # checks
        ph_ok = int((res['PH'] == all_phase_exp[bi * 32:(bi + 1) * 32]).sum())
        syn_back = np.zeros_like(res['VQ'][:840])
        bad_syn = 0
        for q, row in sim.qid_row.items():
            if not (res['VQ'][q] == all_syn[row, bi * 32:(bi + 1) * 32]).all():
                bad_syn += 1
        junk = 0
        for q in range(840, sim.nq):
            if res['VQ'][q].any():
                junk += 1
        print(f'[sim] batch {bi}: {dt:.1f}s phase_ok={ph_ok}/32 bad_syn_qubits={bad_syn} '
              f'junk_working_qubits={junk} toff={res["toff"]:,}', file=sys.stderr)
        if region_mode and 'unconv_in' in res['region_phases']:
            rp = res['region_phases']
            delta = rp['unext_out'] ^ rp['unconv_in']
            print(f'[sim]   un* net phase flipped lanes: {int(delta.sum())}/32', file=sys.stderr)
        if ph_ok < 32 or bad_syn or junk:
            print(f'[sim] *** MISMATCH in batch {bi} ***', file=sys.stderr)
            if ph_ok < 32:
                bad = np.flatnonzero(res['PH'] != all_phase_exp[bi * 32:(bi + 1) * 32])
                print(f'[sim]   phase mismatch lanes: {[int(b)+bi*32 for b in bad]}', file=sys.stderr)
                for b in bad[:4]:
                    g = int(b) + bi * 32
                    print(f'[sim]   shot {g}: weight={all_weights[g]} exp_phase={all_phase_exp[g]} got={res["PH"][b]}', file=sys.stderr)
    sim.r.close()
    print('[sim] done', file=sys.stderr)


if __name__ == '__main__':
    main()
