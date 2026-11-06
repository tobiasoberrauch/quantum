"""Task 2a: BOUND P-B's table-lookup cost using kickmix's native QROM init_lookup.

P-B (constant-seed) uses a 128-entry x 8-bit seed table addressed by 7 mantissa bits.
Measure the APPLIED toffoli-like cost of init_lookup (+ del_lookup to uncompute) for
generic (unstructured) table values = an UPPER bound; a structured 'threshold-predicate'
table (Report B's note) would be <= this.
"""
import numpy as np
import kickmix as km

def qrom_cost(n_entries, out_bits, seed=0):
    rng = np.random.default_rng(seed)
    table = [int(v) for v in rng.integers(0, 1<<out_bits, size=n_entries)]
    addr_bits = (n_entries-1).bit_length()
    b = km.CircuitBuilder()
    addr = b.create_quantum_register(addr_bits, 'addr')
    tgt  = b.create_quantum_register(out_bits, 'tgt')
    b.init_lookup(table=table, address=addr, target=tgt)
    b.del_lookup(table=table, address=addr, target=tgt)   # uncompute (scratch must clear)
    circ = b.finish_circuit()
    st = circ.operation_statistics()
    # init_lookup is unconditional -> static == applied. Confirm with one shot (batch=1).
    a = n_entries - 1
    sim = km.Simulator(batch_size=1, debug_print=False, counting_operations=True, seed=0)
    sim.write_across_shots(km.array(list(addr)), np.array([[(a>>j)&1 for j in range(addr_bits)]],dtype=bool).T)
    sim.do(circ)
    mean_applied = int(sim.operation_statistics().num_toffoli_like)   # 1 shot
    return dict(n_entries=n_entries, out_bits=out_bits, addr_bits=addr_bits,
                static_toffoli_like=int(st.num_toffoli_like), mean_applied=mean_applied,
                num_qubits=circ.num_qubits, num_ops=len(circ))

for ne, ob in [(128,8),(128,7),(64,8),(256,8),(128,16)]:
    r = qrom_cost(ne, ob)
    print(f"QROM {ne}x{ob} (addr {r['addr_bits']}b): static_toffoli={r['static_toffoli_like']} "
          f"applied(1shot)={r['mean_applied']} qubits={r['num_qubits']} ops={r['num_ops']}")
