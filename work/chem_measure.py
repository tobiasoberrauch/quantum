"""Measure the official angle-family Toffoli metric (simulated mean, forward+reverse)
for yoyobar's current circuits and for rank_parity-recompiled candidates.

Uses the verifier's own recover_words_from_circuits so numbers are directly comparable.
"""
import importlib.util
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path("/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum")
sys.path.insert(0, str(REPO / "data/verifiers"))
sys.path.insert(0, str(REPO / "work"))

from dfthcsos.scoreinfra.circuits import recover_words_from_circuits, read_circuit_family  # noqa: E402
from chem_recompile import load_words, zero_invalid, plan_zeroed  # noqa: E402
import rank_parity as core  # noqa: E402

SEED = 12345  # arbitrary; the mean is over addresses, seed only affects HMR outcomes


def measure_family(directory, num_vectors, num_angles, shots_per_address=64):
    circuits = read_circuit_family(directory)
    words, layout, toffoli = recover_words_from_circuits(
        circuits, num_vectors=num_vectors, num_angles=num_angles,
        shots_per_address=shots_per_address, seed=SEED,
    )
    return toffoli, layout, len(circuits)


def main():
    words, brot, edges = load_words()
    D, n_angles = words.shape

    # 1) baseline: yoyobar's shipped family
    base_dir = REPO / "sota_yoyobar/submission/dfthcsos"
    t_base, lay, K_base = measure_family(base_dir, D, n_angles)
    print(f"BASELINE yoyobar: {K_base} circuits, J={lay.batch_size}, brot={lay.brot}, "
          f"angle_T(mean,fwd+rev)={t_base:.1f}  (expect ~8336)")

    # 2) rank_parity candidates
    for J, lb in [(5, 5), (4, 5), (6, 5), (3, 5)]:
        K = math.ceil(n_angles / J)
        outdir = REPO / f"work/measure_J{J}_lb{lb}"
        outdir.mkdir(parents=True, exist_ok=True)
        for old in outdir.glob("angle_k_*.kmb"):
            old.unlink()
        total_static = 0
        for k in range(K):
            delta = core.delta_batch(words, J, k)
            ac = core.coefficients(delta, brot, lb)
            ac = zero_invalid(ac, D, lb)
            terms, planning, stats = plan_zeroed(delta, ac, brot, lb, 32767)
            circuit, trace, report = core.build(delta, brot, lb, ac, terms)
            total_static += report["toffoli_count"]
            circuit.to_file(outdir / f"angle_k_{k}.kmb", format="kmb")
        t_cand, lay2, K2 = measure_family(outdir, D, n_angles)
        heur_T, heur_pers, temp_floor = 7930, 86, 304
        A = math.ceil(D / (1 << lb))
        B = 1 << lb
        n = (D - 1).bit_length()
        Q_total = heur_pers + J * brot + max(temp_floor, n + (A - 1) + (B - 1))
        T_total = heur_T + t_cand
        print(f"J={J} lb={lb}: {K2} circuits, static_CCX={total_static}, "
              f"angle_T={t_cand:.1f}, T_total={T_total:.0f}, Q_total={Q_total}, "
              f"T*Q={T_total*Q_total:,.0f}  (baseline T*Q={16266*430:,.0f})")


if __name__ == "__main__":
    main()
