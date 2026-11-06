"""Recompile yoyobar's dfthcsos angle family with mrmeows' rank_parity compiler.

Baseline (yoyobar/Heliosli V28 loader): 15 circuits (J=5), 4168 static CCX total
(= 8336 counted Toffolis, forward+reverse), Q_total 430, score 337,780,213.

For each (J, lowbits) config: build every batch circuit, prove it symbolically,
sum static CCX, check the 128-qubit cap. Print comparison table. Optionally
assemble a candidate family dir for the official verifier.

Run: .venv/bin/python work/chem_recompile.py [--assemble best_config]
"""
import argparse
import importlib.util
import json
import math
import os
import shutil
import sys
from pathlib import Path

import numpy as np

REPO = Path("/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum")
COMPILER = REPO / "sota_mrmeows/sources/dfthcsos_8p5558_complete_with_compiler/dfthcsos_verified_8p555840/compiler"
sys.path.insert(0, str(COMPILER))

import rank_parity as core  # noqa: E402
from borrowed_prefix import symbolic_check  # noqa: E402

YOYOBAR_NPZ = REPO / "sota_yoyobar/submission/dfthcsos/submission.npz"
OUT_ROOT = REPO / "work/chem_recompile_out"


def load_words():
    with np.load(YOYOBAR_NPZ, allow_pickle=False) as z:
        return z["angle_words"].copy(), int(z["brot"]), z["tree_edges"].copy()


def zero_invalid(ac, D, lowbits):
    """Zero ANF coefficients whose (h,l) monomial address is invalid (>= D)."""
    for h in range(ac.shape[0]):
        for l in range(ac.shape[1]):
            if (h << lowbits) | l >= D:
                ac[h, l] = 0
    return ac


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--J", type=int, default=None)
    ap.add_argument("--lowbits", type=int, default=None)
    ap.add_argument("--max-kernels", type=int, default=32767)
    args = ap.parse_args()

    words, brot, edges = load_words()
    D = len(words)
    n = (D - 1).bit_length()
    print(f"words {words.shape}, brot {brot}, D={D}, n={n}")
    print(f"baseline: J=5, 15 circuits, 4168 CCX total, Q_total 430")

    configs = []
    Js = [args.J] if args.J else [3, 4, 5, 6]
    lbs = [args.lowbits] if args.lowbits else [5]
    for J in Js:
        for lb in lbs:
            K = math.ceil(75 // J)
            A = math.ceil(D / (1 << lb))
            B = 1 << lb
            q_circuit = n + J * brot + (A - 1) + (B - 1)
            tag = f"J{J}_lb{lb}"
            if q_circuit > 128:
                print(f"{tag:<10} SKIP: circuit qubits {q_circuit} > 128 (n={n} words={J*brot} cache={A-1+B-1})")
                continue
            outdir = OUT_ROOT / tag
            if outdir.exists():
                shutil.rmtree(outdir)
            outdir.mkdir(parents=True)
            total_ccx = 0
            ok = True
            for k in range(K):
                delta = core.delta_batch(words, J, k)
                ac = core.coefficients(delta, brot, lb)
                ac = zero_invalid(ac, D, lb)
                terms, planning, stats = plan_zeroed(delta, ac, brot, lb, args.max_kernels)
                circuit, trace, report = core.build(delta, brot, lb, ac, terms)
                sym = symbolic_check(trace, delta, brot, circuit.num_qubits)
                assert sym["status"] == "PASS", f"symbolic check failed J={J} lb={lb} k={k}"
                ccx = report["toffoli_count"]
                total_ccx += ccx
                cp = outdir / f"angle_k_{k}.kmb"
                circuit.to_file(cp, format="kmb")
                (outdir / f"plan_{k}.json").write_text(json.dumps({"planning": planning, "ccx": ccx, "q": report["num_qubits"]}))
            angle_T = 2 * total_ccx
            heur_T = 7930
            heur_pers = 86
            temp = max(304, n + (A - 1) + (B - 1))  # selection+cache as workspace
            Q_total = heur_pers + J * brot + temp
            T_total = heur_T + angle_T
            score_factor = T_total * Q_total
            base_factor = 16266 * 430
            print(f"{tag:<10} K={K:<3} CCX={total_ccx:<5} angle_T={angle_T:<6} T_total={T_total:<7} Q_total={Q_total:<4} T*Q={score_factor:>10,}  vs baseline {100*(base_factor-score_factor)/base_factor:+.2f}%")
            configs.append((tag, J, lb, total_ccx, score_factor))

    if configs:
        best = min(configs, key=lambda c: c[4])
        print(f"\nBEST: {best[0]} (CCX {best[3]}, T*Q {best[4]:,})")
        if best[4] < 16266 * 430:
            assemble(best)


def plan_zeroed(delta, ac, brot, lowbits, max_kernels):
    """core.plan() but starting from pre-zeroed coefficients."""
    tensor = ac[1:, 1:, :]
    H, L, O = tensor.shape
    columns = [[sum(int(tensor[h, k, j]) << h for h in range(H)) for k in range(L)] for j in range(O)]
    original_rank = [len(core.factor_matrix(cols)) for cols in columns]
    chosen = core.BinaryBasis()
    certificates = []
    for j, r in sorted(enumerate(original_rank), key=lambda item: (item[1] + 1) // 2):
        if r < min(H, L) or r % 2 == 0:
            if chosen.add(1 << j):
                certificates.append({"direction": 1 << j, "kernel": None, "rank": r})
    packed_low = [[sum(int(tensor[h, k, j]) << j for j in range(O)) for h in range(H)] for k in range(L)]
    current = [0] * H
    previous = 0
    searched = 0
    for counter in range(1, min((1 << L) - 1, max_kernels) + 1):
        mask = counter ^ (counter >> 1)
        changed = (mask ^ previous).bit_length() - 1
        current = [a ^ b for a, b in zip(current, packed_low[changed])]
        previous = mask
        searched += 1
        for direction in core.nullspace(current, O):
            if chosen.solve(direction) is not None:
                continue
            mixture = [0] * L
            for j in core.set_bits(direction):
                mixture = [a ^ b for a, b in zip(mixture, columns[j])]
            rank = len(core.factor_matrix(mixture))
            if (rank + 1) // 2 < (min(H, L) + 1) // 2:
                assert chosen.add(direction)
                certificates.append({"direction": direction, "kernel": mask, "rank": rank})
        if len(chosen.vectors) == O:
            break
    for j in range(O):
        if chosen.add(1 << j):
            certificates.append({"direction": 1 << j, "kernel": None, "rank": original_rank[j]})
    assert len(chosen.vectors) == O
    output_directions = [0] * O
    for j in range(O):
        inverse_column = chosen.solve(1 << j)
        assert inverse_column is not None
        for i in core.set_bits(inverse_column):
            output_directions[i] |= 1 << j
    terms = []
    reconstructed = [[0] * L for _ in range(O)]
    products = 0
    for i, vector in enumerate(chosen.vectors):
        mixture = [0] * L
        for j in core.set_bits(vector):
            mixture = [a ^ b for a, b in zip(mixture, columns[j])]
        factors = core.factor_matrix(mixture)
        assert len(factors) == certificates[i]["rank"]
        terms.append({"input_output_basis": vector, "target_direction": output_directions[i], "factors": factors})
        products += (len(factors) + 1) // 2
        for j in core.set_bits(output_directions[i]):
            reconstructed[j] = [a ^ b for a, b in zip(reconstructed[j], mixture)]
    assert reconstructed == columns
    planning = {"H": H, "L": L, "O": O, "searched_nonzero_low_kernels": searched,
                "original_matrix_ranks": original_rank, "output_basis_certificates": certificates,
                "untransformed_paired_products": sum((r + 1) // 2 for r in original_rank),
                "transformed_paired_products": products, "exact_mixed_tensor_reconstruction": True}
    return terms, planning, {"products": products}


def assemble(best):
    tag, J, lb, total_ccx, _ = best
    src = OUT_ROOT / tag
    dst = REPO / f"work/chem_candidate_{tag}"
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    shutil.copyfile(YOYOBAR_NPZ, dst / "submission.npz")
    for f in sorted(src.glob("angle_k_*.kmb")):
        shutil.copyfile(f, dst / f.name)
    print(f"assembled {dst} ({len(list(dst.glob('angle_k_*.kmb')))} circuits)")
    print("verify with:")
    print(f"  cd {REPO}/data/verifiers && {REPO}/.venv/bin/python dfthcsos/verify.py {dst}")


if __name__ == "__main__":
    main()
