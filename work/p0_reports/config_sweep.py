"""Config sweep: does any (J, lb) config flip the permutation verdict?

J = angles per loader (num circuits = ceil(75/J)), lb = lowbits split.
Feasibility: q_circuit = n_sel + J*brot + (A-1) + (B-1) <= 128,
A = ceil(D/2**lb), B = 2**lb, n_sel = 11, brot = 8, D = 1363.
Orderings compared: current, perm0 (random), rho_swap (structured).
"""
from __future__ import annotations

import sys
import time
from math import ceil
from pathlib import Path

import numpy as np

REPO = Path("/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum")
COMPILER = REPO / ("sota_mrmeows/sources/dfthcsos_8p5558_complete_with_compiler/"
                   "dfthcsos_verified_8p555840/compiler")
sys.path.insert(0, str(COMPILER))
sys.path.insert(0, str(REPO / "work" / "p0_reports"))

import rank_parity as core  # noqa: E402
from borrowed_prefix import delta_batch  # noqa: E402
from recompile_rank_test import MAX_KERNELS, plan_zeroed, zero_invalid  # noqa: E402

NPZ = REPO / "work/frontier_scan/mwa2_unpacked/dfthcsos/submission.npz"


def main() -> None:
    z = np.load(NPZ, allow_pickle=False)
    words0 = z["angle_words"].copy()
    brot = int(z["brot"].item())
    edges = z["tree_edges"].copy()
    D = len(words0)
    R, B, N = 9, 143, 76
    n_sel = (D - 1).bit_length()

    rng = np.random.default_rng(20261103)
    pi = rng.permutation(B)  # same first permutation as the other tests
    wp = words0.copy()
    for r in range(R):
        block = N + r * B
        wp[block:block + B] = words0[block:block + B][pi]
    ws = words0.copy()
    for r in range(0, R - 1, 2):
        b1, b2 = N + r * B, N + (r + 1) * B
        tmp = words0[b1:b1 + B].copy()
        ws[b1:b1 + B] = words0[b2:b2 + B]
        ws[b2:b2 + B] = tmp

    orderings = {
        "current": core.canonical_gauge(words0, edges, brot)[0],
        "perm0": core.canonical_gauge(wp, edges, brot)[0],
        "rho_swap": core.canonical_gauge(ws, edges, brot)[0],
    }

    def cost(words_g: np.ndarray, J: int, lb: int) -> int | None:
        A = ceil(D / (1 << lb))
        Blk = 1 << lb
        q = n_sel + J * brot + (A - 1) + (Blk - 1)
        if q > 128:
            return None
        cache = sum(1 for m in range(1, A) if m.bit_count() > 1) + \
                sum(1 for m in range(1, Blk) if m.bit_count() > 1)
        K = ceil(75 // J)
        total = K * 2 * cache
        for k in range(K):
            delta = delta_batch(words_g, J, k)
            ac = core.coefficients(delta, brot, lb)
            ac = zero_invalid(ac, D, lb)
            pl = plan_zeroed(delta, ac, brot, lb, MAX_KERNELS)
            total += pl["transformed_paired_products"]
        return total

    print(f"{'config':<12} {'q':>4} | {'current':>8} {'perm0':>8} {'d':>6} | {'rho_swap':>9} {'d':>6}")
    for J in (3, 4, 5):
        for lb in (3, 4, 5):
            row = []
            q = None
            for name, wg in orderings.items():
                c = cost(wg, J, lb)
                if c is None:
                    row.append(None)
                else:
                    row.append(c)
                    q = n_sel + J * brot + (ceil(D / (1 << lb)) - 1) + ((1 << lb) - 1)
            if row[0] is None:
                print(f"J{J}_lb{lb:<6} {'INFEASIBLE':>14}")
                continue
            d0 = row[1] - row[0] if row[1] else 0
            d1 = row[2] - row[0] if row[2] else 0
            print(f"J{J}_lb{lb:<6} {q:>4} | {row[0]:>8} {row[1]:>8} {d0:>+6} | {row[2]:>9} {d1:>+6}")


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"[{time.time()-t0:.0f}s]")
