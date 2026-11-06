"""Pin down executed-vs-static Toffoli counting: full stats attrs + real-circuit seed test."""
import numpy as np
import kickmix as km

# 1) full attribute dump of simulator stats for a CCX with 4 mixed shots
b = km.CircuitBuilder()
reg = b.create_quantum_register(3, 'r')
b.ccx(reg[0], reg[1], reg[2])
circ = b.finish_circuit()
inputs = [[True,True,False],[False,True,False],[True,False,False],[False,False,False]]
sim = km.Simulator(batch_size=4, debug_print=False, counting_operations=True, seed=0)
sim.write_across_shots(km.array(list(reg)), np.array(inputs, dtype=bool).T)
sim.do(circ)
st = sim.operation_statistics()
print('simulator stats attributes:')
for a in dir(st):
    if a.startswith('_'): continue
    try:
        v = getattr(st, a)
        if callable(v): continue
        print(f'  {a} = {v}')
    except Exception as e:
        print(f'  {a} = <err {e}>')
print('circuit stats num_toffoli_like =', circ.operation_statistics().num_toffoli_like)

# 2) GROUND TRUTH: shipped circuit, toffoli_count under two seeds (few x for speed)
import sys
sys.path.insert(0, 'data/verifiers/invsqrt')
import verify_submission_invsqrt as V
U64 = np.uint64
c = km.Circuit.from_file('work/frontier_scan/mwa_unpacked/invsqrt.kmb')
spec = V.ProblemSpecInvSqrt(width=22, max_x=4000, beta=__import__('fractions').Fraction(1),
                            precision_bits=24, shots_per_x=1, system_qubits=3*V.ETA*10)
x_reg, scratch = V.validate_registers(c, spec)
def toff_for(seed):
    sim = km.Simulator(batch_size=1000, debug_print=False, counting_operations=True, seed=seed)
    xs = np.arange(1, 4001, dtype=U64)
    for start in range(0, 4000, 1000):
        xx = xs[start:start+1000]
        sim.clear_for_shot()
        sim.write_across_shots(x_reg, V.to_bits(xx, 22))
        sim.do(c)
    return int(sim.operation_statistics().num_toffoli_like)/4000
for seed in [0, 12345]:
    print(f'shipped circuit mean toffoli_like (x=1..4000, seed={seed}) = {toff_for(seed):.4f}')
