#!/usr/bin/env python3
"""Official heuristic cost at brot 6/7/8 for shapes of interest; angle Toffolis scaled by word bits. Static arithmetic only."""
import sys
sys.path.insert(0, "/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/data/verifiers")
from dfthcsos.verify import heuristic_costs

ANG8, Q_J = 8686, {8: 40, 7: 35, 6: 30}
BASE = 15427 * 427
for shape in [(8,143,45),(9,143,39),(8,143,50),(8,143,60),(8,159,45),(8,129,50),(9,129,46),(10,129,46),(8,120,50),(8,127,50),(8,70,60),(8,71,60),(8,64,60)]:
    for brot in (8, 7, 6):
        h = heuristic_costs(76, *shape, brot)
        addr = 76 + shape[0]*shape[1]
        ang = ANG8 * (brot/8) * (addr/1220)**0.72
        q = h["qubits"] + Q_J[brot]
        t = h["toffoli"] + ang
        print(shape, "brot", brot, "heurT", h["toffoli"], "temp", h["temporary_qubits"], "Q", q, "estT", round(t), "chem_factor", round(BASE/(t*q), 3))
