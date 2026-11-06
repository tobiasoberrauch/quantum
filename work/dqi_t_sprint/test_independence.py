"""Test outcome-independence of the ORIGINAL dqi.kmb on the real kickmix
simulator: run 256-shot batches with 3 different sim seeds; check
phase_flipped == p(s) for every shot."""
import hashlib
import sys
import time

import numpy as np
import kickmix as km

sys.path.insert(0, '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/work/dqi_t_sprint')
from sim3 import sample_shots, to_bits, initial_seed, make_batches

ROOT = '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum'
KMB = f'{ROOT}/work/frontier_scan/mwa_unpacked/dqi.kmb'


def main():
    h = hashlib.sha256()
    with open(KMB, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 22), b''):
            h.update(chunk)
    chash = h.hexdigest()
    base_seed = initial_seed(chash)
    circuit = km.Circuit.from_file(KMB, format='kmb')
    print(f'loaded circuit: {circuit.num_qubits} qubits, {len(circuit)} ops', file=sys.stderr)

    # syndrome qubit array in register order S0..S69 x 12
    syn_q = []
    mbuc_b = []
    for i in range(70):
        syn_q.extend(circuit.register_data[f'S{i}'])
    for i in range(4095):
        mbuc_b.extend(circuit.register_data[f'E{i}'])
    syn_arr = km.array(syn_q)
    mbuc_arr = km.array(mbuc_b)

    m, n, degree, r = 4095, 70, 12, 2016
    batches = make_batches(base_seed, 4)
    for bi in range(4):
        rng_seed, sim_seed = batches[bi]
        override = None
        if '--alt-seeds' in sys.argv:
            override = 0xBEEF0000 + bi * 777
        use_seed = override if override is not None else sim_seed
        t0 = time.time()
        rng = np.random.default_rng(rng_seed)
        synd, mbuc, phases, weights = sample_shots(m, n, degree, r, 256, rng)
        sim = km.Simulator(batch_size=256, seed=use_seed, counting_operations=True)
        sim.use_same_registers_as(circuit)
        sim.write_across_shots(syn_arr, to_bits(synd, degree))
        sim.write_across_shots(mbuc_arr, to_bits(mbuc, degree))
        sim.do(circuit)
        dt = time.time() - t0
        got_ph = np.asarray(sim.read_phase_flipped_across_shots()).astype(bool)
        diff = got_ph ^ phases
        # value check
        reg_diff = sim.read_across_shots(syn_arr) ^ to_bits(synd, degree)
        val_bad_shots = int(reg_diff.any(axis=0).sum())
        stats = sim.operation_statistics()
        ndiff = int(diff.sum())
        print(f'batch {bi}: seed={use_seed:#x} {dt:.1f}s phase_diff_popcount={ndiff}/256 '
              f'value_bad_shots={val_bad_shots} meanT={stats.num_toffoli_like/256:,.1f}', file=sys.stderr)
        if ndiff > 0:
            bad = np.flatnonzero(diff).tolist()
            print(f'   mismatching shots (first 10): {bad[:10]} weights={weights[bad[:10]].tolist()}', file=sys.stderr)


if __name__ == '__main__':
    main()
