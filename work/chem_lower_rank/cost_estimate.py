"""Precise T_total / Q_total / ratio for advisory shapes, mirroring verify.resource_costs.

heuristic part = SpinFreeData_V1 exactly as the verifier (validated: 388 qubits,
6653 toffoli at (9,143,39)). angles part = linear-in-A proxy anchored to the
current best's measured angles_toffoli=8932 / angles_qubits=128 at A=1363.
lambda_eff from the Lambda decomposition (lambda_H1 fixed, lambda_H2 scaled by G/C).
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/data/verifiers")
from metrics_np import REFERENCE_COST  # noqa: E402
from dfthcsos.scoreinfra.costs_prepare import SpinFreeData_V1  # noqa: E402

R, N, BROT = 9, 76, 8
C0, M0 = 39, 143
LAM_H1, LAM_H2 = 13.133, 271.260   # measured decomposition of the current best
EGAP_FLOOR = 3.9152
ANGLES_T0, ANGLES_Q0, A0 = 8932.0, 128, N + R * M0   # current-best anchors


def heuristic(B, C):
    m = SpinFreeData_V1(R=R, B=B, C=C, N=N, chi=10, beta=BROT)
    oq = m.outer_state_prep_qubit_cost(); iq = m.inner_state_prep_qubit_cost()
    op, ot = int(oq["persistent"]), int(oq["temporary"])
    ip, it = int(iq["persistent"]), int(iq["temporary"])
    T = int(m.outer_state_prep()) + int(m.inner_state_prep()) + int(m.givens_rotations())
    return {"T": T, "pers": op + ip, "temp": max(ot, it), "outer": int(m.outer_state_prep()),
            "inner": int(m.inner_state_prep()), "givens": int(m.givens_rotations())}


def lam_eff(G):
    L = LAM_H1 + LAM_H2 * (G / C0)
    return float(np.sqrt(EGAP_FLOOR * (2 * L - EGAP_FLOOR))), L


def main():
    # validate anchor
    h0 = heuristic(M0, C0)
    print(f"anchor (143,39): heur T={h0['T']} pers={h0['pers']} temp={h0['temp']} Q={h0['pers']+h0['temp']} "
          f"(verifier: T=6653 Q=388)\n")
    print(f"{'M':>4} {'G':>3} | {'lamEff':>7} {'Lambda':>7} | {'heurT':>6} {'angT':>6} {'Ttot':>6} | {'heurQ':>6} {'angQ':>5} {'Qtot':>5} | {'ratio':>6} {'dGM':>6}")
    gm_base = 24.467937861321357
    for M in [143, 134, 130, 126]:
        for G in [39, 36, 35]:
            le, L = lam_eff(G)
            h = heuristic(M, G)
            A = N + R * M
            angT = ANGLES_T0 * (A / A0)
            angQ = ANGLES_Q0   # angle register width ~ fixed (J*brot), capped 128
            Ttot = h["T"] + angT
            # Q_total = heuristic_pers + angles_pers + max(heuristic_temp, angles_temp)
            # angles_pers ~ J*brot; keep current-best split: pers=40, temp=77 (of 128)
            angP, angTemp = 40, 77
            Qtot = h["pers"] + angP + max(h["temp"], angTemp)
            score = le * Ttot * Qtot
            ratio = REFERENCE_COST / score
            gm = (21.0321 * 65.1066 * ratio) ** (1 / 3)
            print(f"{M:>4} {G:>3} | {le:>7.3f} {L:>7.2f} | {h['T']:>6d} {int(angT):>6d} {int(Ttot):>6d} | "
                  f"{h['pers']+h['temp']:>6d} {angQ:>5d} {Qtot:>5d} | {ratio:>6.3f} {gm-gm_base:>+6.2f}")


if __name__ == "__main__":
    main()
