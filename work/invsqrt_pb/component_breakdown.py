"""Per-component CCX breakdown of the P-B PRIMARY build, measured directly.

Imports the prior build module's low-level functions and constructs minimal
circuits that run ONLY (a) the seed lookup, (b) Newton#1, (c) Newton#2, so each
component's static CCX (== applied, since cond==0) is [FAKT]-measured rather than
derived. Widths are fixed by the validated spec, so the CCX counts are data-independent.
"""
import os, sys, json
import numpy as np
import kickmix as km

HERE = os.path.dirname(os.path.abspath(__file__))
CONST = os.path.abspath(os.path.join(HERE, '..', 'constseed_build'))
sys.path.insert(0, CONST)
import build_constseed_circuit as B   # noqa: E402

def ccx(circ):
    return int(circ.operation_statistics().num_toffoli_like)

# ---- (a) seed lookup: 512-entry ROM, 9-bit address, 8-bit target ----
b = km.CircuitBuilder()
addr = b.create_quantum_register(9, 'addr')
S = b.create_quantum_register(B.SF, 'S')
b.init_lookup(table=B.ROM_TABLE, address=addr, target=S)
b.del_lookup(table=B.ROM_TABLE, address=addr, target=S)
lookup_ccx = ccx(b.finish_circuit())

# ---- shared input registers for the Newton steps ----
def newton_harness(do_n1, do_n2):
    b = km.CircuitBuilder()
    x = b.create_quantum_register(B.WIDTH, 'x')          # 22
    scratch = b.alloc_qubits(B.PROD_W)                   # 34
    S = b.alloc_qubits(B.SF)                             # 8
    SS = b.alloc_qubits(B.SS_W)                          # 16
    C1reg = b.alloc_qubits(B.N1 + 2)                     # 18
    P1 = b.alloc_qubits(B.N1 + 1)                        # 17
    prod_q1 = b.alloc_qubits(B.Q1_W)                     # 34
    prod_p1 = b.alloc_qubits(B.P1_W)                     # 24
    y1 = b.alloc_qubits(B.F)                             # 37
    sq2 = b.alloc_qubits(B.SQ2_W)                        # 34
    C2reg = b.alloc_qubits(B.G + 2)                      # 28
    prod_q2 = b.alloc_qubits(B.Q2_W)                     # 29
    prod_p2 = b.alloc_qubits(B.P2_W)                     # 31
    if do_n1:
        B._newton1(b, False, x, S, SS, C1reg, P1, prod_q1, prod_p1, scratch)
        B._newton1(b, True, x, S, SS, C1reg, P1, prod_q1, prod_p1, scratch)
    if do_n2:
        B._newton2(b, False, x, P1, y1, sq2, C2reg, prod_q2, prod_p2, scratch)
        B._newton2(b, True, x, P1, y1, sq2, C2reg, prod_q2, prod_p2, scratch)
    return ccx(b.finish_circuit())

n1_ccx = newton_harness(True, False)
n2_ccx = newton_harness(False, True)
both_ccx = newton_harness(True, True)

print(f'(a) seed lookup (512x8, 9-bit addr): {lookup_ccx} CCX')
print(f'(b) Newton#1 (n1=16):                {n1_ccx} CCX')
print(f'(c) Newton#2 (g=26):                 {n2_ccx} CCX')
print(f'    N1+N2 together:                  {both_ccx} CCX')
print(f'    lookup + N1 + N2 =               {lookup_ccx + both_ccx} CCX  (rest of 8581 = normalize/select/build_k/denorm/phase-adj)')

json.dump({'lookup': lookup_ccx, 'newton1': n1_ccx, 'newton2': n2_ccx,
           'newton_both': both_ccx, 'total_official': 8581},
          open(os.path.join(HERE, 'data', 'pb_components.json'), 'w'), indent=1)
print('saved work/invsqrt_pb/data/pb_components.json')
