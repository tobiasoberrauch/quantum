"""Diagnostic: is Simulator(num_toffoli_like) executed-based (data-dependent) or static?"""
import numpy as np
import kickmix as km

def run(circ_builder_fn, inputs):
    b = km.CircuitBuilder()
    qubits = circ_builder_fn(b)
    circ = b.finish_circuit()
    sim = km.Simulator(batch_size=len(inputs), debug_print=False, counting_operations=True, seed=0)
    sim.write_across_shots(km.array(qubits), np.array(inputs, dtype=bool).T)  # -> [n_qubits, n_shots]
    sim.do(circ)
    return int(sim.operation_statistics().num_toffoli_like), int(circ.operation_statistics().num_toffoli_like)

# Circuit: one CCX(control0, control1, target). Vary the two controls.
def ccx(b):
    reg = b.create_quantum_register(3, 'r')
    b.ccx(reg[0], reg[1], reg[2])
    return list(reg)

print('CCX executed vs static (inputs = [c0,c1,t]):')
for c0, c1 in [(0,0),(0,1),(1,0),(1,1)]:
    execd, stat = run(ccx, [[bool(c0), bool(c1), False]])
    print(f'  c0={c0} c1={c1}: executed={execd} static={stat}')

# Circuit: one CSWAP(ctrl, a, b). Vary ctrl.
def cswap(b):
    reg = b.create_quantum_register(3, 'r')
    b.cswap(reg[0], reg[1], reg[2])
    return list(reg)
print('CSWAP executed vs static (inputs=[ctrl,a,b]):')
for ctrl in [0,1]:
    execd, stat = run(cswap, [[bool(ctrl), True, False]])
    print(f'  ctrl={ctrl}: executed={execd} static={stat}')

# multi-shot: 4 shots with mixed controls -> executed should be the count of firing ones
def ccx_multi(b):
    reg = b.create_quantum_register(3, 'r')
    b.ccx(reg[0], reg[1], reg[2])
    return list(reg)
inputs = [[True,True,False],[False,True,False],[True,False,False],[False,False,False]]
execd, stat = run(ccx_multi, inputs)
print(f'CCX 4 mixed shots: executed={execd} (expect 1) static={stat} (expect 4)')
