"""Locate the error_2 rank cliff: where the matricized-target floor crosses 20 mHa."""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
EIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eig_top.npz")
R = 9


def main():
    e = np.load(EIG)
    vals, fT2 = e["vals"], float(e["fT2"])
    print(f"||T||_F = {np.sqrt(fT2):.6f} Ha   (Kmax available = {len(vals)})")
    print(f"\n{'G':>3} {'K=R*C':>6} {'floor_err2':>11}  {'crosses 20mHa?'}")
    crossed = False
    for G in range(40, 24, -1):
        K = R * G
        if K >= len(vals):
            continue
        tail = fT2 - float(np.sum(vals[:K] ** 2))
        floor = np.sqrt(max(0.0, tail))
        mark = ""
        if not crossed and 1e3 * floor > 20.0:
            mark = "  <-- first G (descending) whose floor > 20 mHa"
            crossed = True
        print(f"{G:>3} {K:>6} {1e3*floor:>10.3f}m{mark}")


if __name__ == "__main__":
    main()
