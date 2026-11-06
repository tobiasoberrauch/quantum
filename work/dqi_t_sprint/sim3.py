"""Bit-parallel basis-state simulator for dqi.kmb (32 lanes), faithful to
kickmix Sim semantics (src/kickmix/sim/sim.h). Representation: VQ[q] / VB[b]
are length-32 uint32 arrays (value per shot-lane, 0/1). base = per-lane
condition mask from PUSH_CONDITION stack. HMR/R random source: 'zero' tests
outcome-independence; 'rand' draws PRNG bits.

mean Toffolis per shot = (counted toffoli-like executions in batch) / 32,
where plain CCX/CCZ/CSWAP count 1 per lane (32) and _IF variants count
popcount(cond).
"""
import importlib.util
import math
import sys
import time

import numpy as np

ROOT = '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum'

spec = importlib.util.spec_from_file_location('wl', f'{ROOT}/work/dqi_sources/width_liveness.py')
wl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wl)


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
    return [(int.from_bytes(seeds[i, 0], 'little'), int.from_bytes(seeds[i, 1], 'little'))
            for i in range(num_batches)]


class Sim:
    def __init__(self, kmb_path):
        self.r = wl.KmbReader(kmb_path)
        self.t = self.r.types
        self.N = self.r.num_ops
        self.nq = self.r.num_qubits
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
        self.PUSH = pos_of([0x81])
        self.POP = pos_of([0x01])
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
        self.qid_row = {}
        for i in range(70):
            for j, q in enumerate(self.r.registers[f'S{i}']):
                self.qid_row[int(q)] = i * 12 + j
        self.e_bit_row = {}
        for i in range(4095):
            for j, b in enumerate(self.r.registers[f'E{i}']):
                self.e_bit_row[int(b)] = i * 12 + j

    def run_batch(self, syn_bits, mbuc_bits, marks=None, hmr_mode='zero'):
        VQ = np.zeros((self.nq, 32), dtype=np.uint32)
        VB = np.zeros((self.nb, 32), dtype=np.uint32)
        PH = np.zeros(32, dtype=np.uint32)
        for q, row in self.qid_row.items():
            VQ[q] = syn_bits[row]
        for b, row in self.e_bit_row.items():
            VB[b] = mbuc_bits[row]

        P1, P2, P3, PB, PC, PUSH, POP = self.P1, self.P2, self.P3, self.PB, self.PC, self.PUSH, self.POP
        n1, n2, n3, nb_, nc, npu, npo = len(P1), len(P2), len(P3), len(PB), len(PC), len(PUSH), len(POP)
        i1 = i2 = i3 = ib = ic = ipu = ipo = 0
        p1 = P1[0] if n1 else self.N
        p2 = P2[0] if n2 else self.N
        p3 = P3[0] if n3 else self.N
        pb = PB[0] if nb_ else self.N
        pc = PC[0] if nc else self.N
        pp = PUSH[0] if npu else self.N
        po = POP[0] if npo else self.N
        t1, t2, t3, tb, tc = self.t1, self.t2, self.t3, self.tb, self.tc
        q1, q2a, q2b = self.q1, self.q2a, self.q2b
        q3a, q3b, q3c = self.q3a, self.q3b, self.q3c
        b1, bc = self.b1, self.bc
        N = self.N
        toff = 0
        base = np.ones(32, dtype=np.uint32)
        stack = []
        rs = np.random.RandomState(12345)
        if hmr_mode == 'zero':
            def draw():
                return ZERO
        else:
            def draw():
                return (rs.rand(32) < 0.5).astype(np.uint32)
        mark_out = {}
        ZERO = np.zeros(32, dtype=np.uint32)
        ONE = np.ones(32, dtype=np.uint32)
        for p in range(N):
            if p == p1:
                tt = int(t1[i1]); q = int(q1[i1]); cond = base
                if tt == 0x10:
                    PH ^= VQ[q] & cond
                elif tt == 0x90:
                    PH ^= VQ[q] & VB[bc[ic]] & cond
                elif tt == 0x11:
                    VQ[q] ^= cond
                elif tt == 0x91:
                    VQ[q] ^= VB[bc[ic]] & cond
                elif tt == 0x12:
                    m = draw() & cond
                    PH ^= VQ[q] & m
                    VQ[q] &= ~cond
                elif tt == 0x92:
                    cm = VB[bc[ic]] & cond
                    m = draw() & cm
                    PH ^= VQ[q] & m
                    VQ[q] &= ~cm
                elif tt == 0x50:
                    m = draw() & cond
                    VB[b1[ib]] = (VB[b1[ib]] & ~cond) ^ m
                    PH ^= VQ[q] & m
                    VQ[q] &= ~cond
                elif tt == 0xD0:
                    cm = VB[bc[ic]] & cond
                    m = draw() & cm
                    VB[b1[ib]] = (VB[b1[ib]] & ~cm) ^ m
                    PH ^= VQ[q] & m
                    VQ[q] &= ~cm
                i1 += 1; p1 = P1[i1] if i1 < n1 else N
            if p == p2:
                tt = int(t2[i2]); a = int(q2a[i2]); b = int(q2b[i2]); cond = base
                if tt == 0x20:
                    PH ^= VQ[a] & VQ[b] & cond
                elif tt == 0xA0:
                    PH ^= VQ[a] & VQ[b] & VB[bc[ic]] & cond
                elif tt == 0x21:
                    VQ[b] ^= VQ[a] & cond
                elif tt == 0xA1:
                    VQ[b] ^= VQ[a] & VB[bc[ic]] & cond
                elif tt == 0x22:
                    d = VQ[a] ^ VQ[b]; VQ[a] ^= d & cond; VQ[b] ^= d & cond
                elif tt == 0xA2:
                    cm = VB[bc[ic]] & cond
                    d = VQ[a] ^ VQ[b]; VQ[a] ^= d & cm; VQ[b] ^= d & cm
                i2 += 1; p2 = P2[i2] if i2 < n2 else N
            if p == p3:
                tt = int(t3[i3]); a = int(q3a[i3]); b = int(q3b[i3]); c = int(q3c[i3]); cond = base
                if tt == 0x30:
                    PH ^= VQ[a] & VQ[b] & VQ[c] & cond
                    toff += 32
                elif tt == 0xB0:
                    cm = VB[bc[ic]] & cond
                    PH ^= VQ[a] & VQ[b] & VQ[c] & cm
                    toff += int(cm.sum())
                elif tt == 0x31:
                    VQ[c] ^= VQ[a] & VQ[b] & cond
                    toff += 32
                elif tt == 0xB1:
                    cm = VB[bc[ic]] & cond
                    VQ[c] ^= VQ[a] & VQ[b] & cm
                    toff += int(cm.sum())
                elif tt == 0x32:
                    cm = VQ[a] & cond
                    d = VQ[b] ^ VQ[c]; VQ[b] ^= d & cm; VQ[c] ^= d & cm
                    toff += 32
                elif tt == 0xB2:
                    cm = VQ[a] & VB[bc[ic]] & cond
                    d = VQ[b] ^ VQ[c]; VQ[b] ^= d & cm; VQ[c] ^= d & cm
                    toff += int(cm.sum())
                i3 += 1; p3 = P3[i3] if i3 < n3 else N
            if p == pb:
                tt = int(tb[ib]); b = int(b1[ib]); cond = base
                if tt == 0x40:
                    VB[b] &= ~cond
                elif tt == 0xC0:
                    VB[b] &= ~(VB[bc[ic]] & cond)
                elif tt == 0x41:
                    VB[b] |= cond
                elif tt == 0xC1:
                    VB[b] |= VB[bc[ic]] & cond
                elif tt == 0x42:
                    VB[b] ^= cond
                elif tt == 0xC2:
                    VB[b] ^= VB[bc[ic]] & cond
                ib += 1; pb = PB[ib] if ib < nb_ else N
            if p == pp:
                stack.append(base)
                base = base & VB[bc[ic]]
                ipu += 1; pp = PUSH[ipu] if ipu < npu else N
            if p == pc:
                if tc[ic] == 0x80:
                    PH ^= VB[bc[ic]] & base
                ic += 1; pc = PC[ic] if ic < nc else N
            if p == po:
                base = stack.pop()
                ipo += 1; po = POP[ipo] if ipo < npo else N
            if marks and p in marks:
                mark_out[marks[p]] = (PH.copy(), VQ.copy())
        return dict(VQ=VQ, VB=VB, PH=PH, toff=toff, marks=mark_out)


def main():
    args = sys.argv[1:]
    kmb = args[0]
    shots = 512
    if '--shots' in args:
        shots = int(args[args.index('--shots') + 1])
    hmr_mode = 'zero'
    if '--hmr-rand' in args:
        hmr_mode = 'rand'
    region_mode = '--region-phase' in args

    import hashlib
    h = hashlib.sha256()
    with open(kmb, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 22), b''):
            h.update(chunk)
    chash = h.hexdigest()
    print(f'[sim] {kmb}\n[sim] sha256={chash} hmr_mode={hmr_mode}', file=sys.stderr)

    sim = Sim(kmb)
    print(f'[sim] ops={sim.N:,} nq={sim.nq} nb={sim.nb}', file=sys.stderr)

    base_seed = initial_seed(chash)
    nbatches = shots // 32
    batches = make_batches(base_seed, nbatches)
    m, n, degree, r = 4095, 70, 12, 2016

    tot_phase_ok = 0
    tot_bad_syn = 0
    tot_junk = 0
    tot_toff = 0
    region_deltas = []
    weights_seen = set()
    for bi in range(nbatches):
        rng_seed, sim_seed = batches[bi]
        rng = np.random.default_rng(rng_seed)
        synd, mbuc, phases, weights = sample_shots(m, n, degree, r, 32, rng)
        weights_seen.update(weights.tolist())
        sb = to_bits(synd, degree).astype(np.uint32)
        mb = to_bits(mbuc, degree).astype(np.uint32)
        t0 = time.time()
        marks = None
        if region_mode:
            tagpos = np.flatnonzero(sim.t == 0x06)
            marks = {}
            for p, s in zip(tagpos.tolist(), sim.r.tag_strings):
                if s == '@enter:unconvert':
                    marks[p] = 'unconv_in'
                if s == '@exit:unextract':
                    marks[p] = 'unext_out'
        res = sim.run_batch(sb, mb, marks, hmr_mode)
        dt = time.time() - t0
        ph_ok = int((res['PH'] == phases.astype(np.uint32)).sum())
        bad_syn = 0
        for q, row in sim.qid_row.items():
            if not (res['VQ'][q] == sb[row]).all():
                bad_syn += 1
        junk = int(sum(1 for q in range(840, sim.nq) if res['VQ'][q].any()))
        tot_phase_ok += ph_ok
        tot_bad_syn += bad_syn
        tot_junk += junk
        tot_toff += res['toff']
        print(f'[sim] batch {bi}: {dt:.1f}s phase_ok={ph_ok}/32 bad_syn={bad_syn} junk={junk} '
              f'meanT={res["toff"]/32:,.1f}', file=sys.stderr)
        if region_mode and marks and 'unconv_in' in res['marks']:
            d = res['marks']['unext_out'][0] ^ res['marks']['unconv_in'][0]
            region_deltas.append(int(d.sum()))
    print(f'\n[sim] TOTAL: phase_ok={tot_phase_ok}/{shots} bad_syn_qubit-batches={tot_bad_syn} '
          f'junk_batches={tot_junk} meanT={tot_toff/(nbatches*32):,.1f} weights_seen={sorted(weights_seen)}',
          file=sys.stderr)
    if region_deltas:
        print(f'[sim] un* net phase flips per batch (lanes): {region_deltas}', file=sys.stderr)
    sim.r.close()


if __name__ == '__main__':
    main()
