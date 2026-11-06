"""Debug the SpinFreeData_V1 qubit discontinuity around M=126."""
import sys
sys.path.insert(0, "/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/data/verifiers")
from dfthcsos.scoreinfra.costs_prepare import SpinFreeData_V1

R, N, BROT, C = 9, 76, 8, 35
print(f"{'M':>4} | {'b2':>3} {'k2opt':>5} | {'inner_pers':>10} {'inner_temp':>10} {'outer_pers':>10} {'outer_temp':>10} | {'Qtot':>5}")
for M in range(120, 145):
    m = SpinFreeData_V1(R=R, B=M, C=C, N=N, chi=10, beta=BROT)
    oq = m.outer_state_prep_qubit_cost(); iq = m.inner_state_prep_qubit_cost()
    b2 = __import__("math").ceil(__import__("math").log2(M)) + 10 + 1
    k2 = m.find_qroam_size_to_minimize_global_temp_ancilla(b2)
    Qtot = int(oq["persistent"]) + int(iq["persistent"]) + max(int(oq["temporary"]), int(iq["temporary"]))
    print(f"{M:>4} | {b2:>3} {k2:>5} | {int(iq['persistent']):>10} {int(iq['temporary']):>10} "
          f"{int(oq['persistent']):>10} {int(oq['temporary']):>10} | {Qtot:>5}")
