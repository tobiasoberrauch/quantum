#!/usr/bin/env python3
"""Tabulate the official chemistry heuristic costs over (R,B,C,brot). Static arithmetic only; no circuits run."""
import sys
sys.path.insert(0, "/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/data/verifiers")
from dfthcsos.verify import heuristic_costs

BASE_T_ANG = 8854  # HW-16 angle toffolis (15427 minus the C=45 heuristic part, recomputed below)
base = heuristic_costs(76, 8, 143, 45, 8)
base_ang = 15427 - base["toffoli"]
print("base", base, "angle_T", base_ang)
rows = []
for R in (2, 3, 4, 5, 6, 7, 8, 9, 10):
    for B in (129, 135, 143, 159, 191, 207, 239, 255):
        for C in (30, 33, 36, 39, 40, 42, 45, 50, 60, 75, 90, 100, 109, 128):
            for brot in (8,):
                h = heuristic_costs(76, R, B, C, brot)
                addr = 76 + R * B
                ang = base_ang * (addr / 1220) ** 0.72
                q = h["qubits"] + 0
                total = (h["toffoli"] + ang) * q
                rows.append((total / (15427 * 427), R, B, C, R * C, addr, h["toffoli"], round(ang), q))
rows.sort()
print("rel_T*Q R B C RC addr heurT estAngT Q(heur)")
for r in rows[:40]:
    print(f"{r[0]:.3f}", *r[1:])
print("--- with R*C>=290 (Eckart-Young floor) and R*C<=360")
for r in [x for x in rows if 290 <= x[4] <= 400][:25]:
    print(f"{r[0]:.3f}", *r[1:])
