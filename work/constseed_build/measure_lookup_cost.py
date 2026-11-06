#!/usr/bin/env python3
"""Measure the static CCX / T / ops cost of kickmix init_lookup+del_lookup on the
real 512x8 seed table (9-bit address, 8-bit target), standalone."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import numpy as np
import kickmix as km

AB, SF = 18, 8
M18 = (1 << AB) - 1
from invsqrt_constseed_model import _PWQ3_COEFS
COEFS = [{'A': int(round(a*2**AB)), 'B': int(round(-b*2**AB)),
          'C': int(round(c*2**AB)), 'D': int(round(-d*2**AB))} for (a,b,c,d) in _PWQ3_COEFS]


def S_circuit(inter, k):
    A, B, C, D = (COEFS[inter][n] for n in 'ABCD')
    td = (D*k) >> 7; r2 = (C - td) & M18; tr2 = (r2*k) >> 7
    r1 = (B - tr2) & M18; tr1 = (r1*k) >> 7; r0 = (A - tr1) & M18
    return r0 >> 10


def main():
    # 512-entry table: index = inter*128 + k
    table = [S_circuit(i, k) for i in range(4) for k in range(128)]
    print(f'table: {len(table)} entries, distinct={len(set(table))}, '
          f'min={min(table)}, max={max(table)}')

    for n_addr in (9,):
        b = km.CircuitBuilder()
        addr = b.alloc_qubits(n_addr)
        tgt = b.alloc_qubits(SF)
        b.init_lookup(table=table, address=addr, target=tgt)
        b.del_lookup(table=table, address=addr, target=tgt)
        b.free(addr); b.free(tgt)
        c = b.finish_circuit()
        st = c.operation_statistics()
        print(f'lookup {n_addr}-bit addr x {SF}-bit tgt: Q={c.num_qubits} '
              f'static_CCX={st.num_toffoli_like} T={st.num_t_like} '
              f'rot(h4+)={st.num_z_pow(min_clifford_hierarchy_level=4)} ops={len(c)}')


if __name__ == '__main__':
    main()
