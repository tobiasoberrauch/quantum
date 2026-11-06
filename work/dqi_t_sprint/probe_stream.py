"""Extract kickmix's exact HMR/R random bitstream for a given seed via a probe
circuit (K HMR ops on q0 -> bits b0..bK-1). The stream depends only on the
seed and the HMR/R op index, not on circuit content.

Usage:
  probe_stream.py <seed_hex> <K> <out.npy>
Reads back: (K,) array of uint64 (low 64 bits of each 256-bit word suffice;
store full 256-bit as 4 uint64? we only need lane 0 = low 32 bits -> store uint32).
"""
import sys
import time

import numpy as np
import kickmix as km


def main():
    seed = int(sys.argv[1], 16) if sys.argv[1].startswith('0x') else int(sys.argv[1])
    K = int(sys.argv[2])
    out_path = sys.argv[3]
    t0 = time.time()
    lines = [f'HMR q0 b{i}' for i in range(K)]
    circuit = km.Circuit('\n'.join(lines))
    print(f'[probe] circuit built: {len(circuit)} ops, {time.time()-t0:.1f}s', file=sys.stderr)
    t0 = time.time()
    sim = km.Simulator(batch_size=256, seed=seed)
    sim.use_same_registers_as(circuit)
    sim.do(circuit)
    print(f'[probe] simulated: {time.time()-t0:.1f}s', file=sys.stderr)
    t0 = time.time()
    bits = km.array([km.b(i) for i in range(K)])
    arr = sim.read_across_shots(bits)  # (K, 256) bool
    arr = np.asarray(arr)
    # lane 0 = shots 0..31 = low 32 bits of each word
    lane0 = np.frombuffer(arr[:, :32].astype(np.uint8).tobytes(), dtype=np.uint8)
    packed = np.zeros(K, dtype=np.uint32)
    for j in range(32):
        packed |= arr[:, j].astype(np.uint32) << j
    packed.tofile(out_path)
    print(f'[probe] read+packed: {time.time()-t0:.1f}s; saved {out_path} ({K} x uint32)', file=sys.stderr)
    print(f'[probe] sanity: popcounts first 4: {[int(packed[i].bit_count()) for i in range(4)]}', file=sys.stderr)


if __name__ == '__main__':
    main()
