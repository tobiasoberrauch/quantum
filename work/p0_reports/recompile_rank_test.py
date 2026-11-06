"""Rank leaf-index permutations by recompiling all 15 angle loaders with the
mrmeows rank_parity compiler (plan only, no circuit build).

Pipeline per ordering (identical to work/chem_recompile.py):
  words -> canonical_gauge -> per loader k: delta_batch(J=5) ->
  coefficients(brot=8, lb=5) -> zero_invalid -> plan_zeroed(max_kernels)
Content-dependent static CCX per loader = transformed_paired_products.
Fixed overhead per loader = 2 * cache, cache = nonsingleton masks in
1..A-1 (high) + 1..B-1 (low); A=ceil(D/2**lb), B=2**lb.
Predicted verifier angles_toffoli = 2 * sum(static CCX) (forward+reverse).

Calibration: current ordering must reproduce mwa2's measured 8932 if mwa2
was compiled with this compiler/config.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path("/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum")
COMPILER = REPO / ("sota_mrmeows/sources/dfthcsos_8p5558_complete_with_compiler/"
                   "dfthcsos_verified_8p555840/compiler")
sys.path.insert(0, str(COMPILER))

import rank_parity as core  # noqa: E402
from borrowed_prefix import delta_batch  # noqa: E402

NPZ = REPO / "work/frontier_scan/mwa2_unpacked/dfthcsos/submission.npz"
OUT = REPO / "work/p0_reports/recompile_rank_results.json"

J = 5          # angles per loader
LB = 5         # lowbits
MAX_KERNELS = 32767
N_PERMS = 20
SEED = 20261103


def plan_zeroed(delta, ac, brot, lowbits, max_kernels):
    """core.plan starting from pre-zeroed coefficients (copy of chem_recompile)."""
    tensor = ac[1:, 1:, :]
    H, L, O = tensor.shape
    columns = [[sum(int(tensor[h, k, j]) << h for h in range(H)) for k in range(L)]
               for j in range(O)]
    original_rank = [len(core.factor_matrix(cols)) for cols in columns]
    chosen = core.BinaryBasis()
    certificates = []
    for j, r in sorted(enumerate(original_rank), key=lambda item: (item[1] + 1) // 2):
        if r < min(H, L) or r % 2 == 0:
            if chosen.add(1 << j):
                certificates.append({"direction": 1 << j, "kernel": None, "rank": r})
    packed_low = [[sum(int(tensor[h, k, j]) << j for j in range(O)) for h in range(H)]
                  for k in range(L)]
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
            certificates.append({"direction": 1 << j, "kernel": None,
                                 "rank": original_rank[j]})
    assert len(chosen.vectors) == O
    products = 0
    for cert in certificates:
        mixture = [0] * L
        for j in core.set_bits(cert["direction"]):
            mixture = [a ^ b for a, b in zip(mixture, columns[j])]
        factors = core.factor_matrix(mixture)
        assert len(factors) == cert["rank"]
        products += (len(factors) + 1) // 2
    return {
        "H": H, "L": L, "O": O,
        "searched_nonzero_low_kernels": searched,
        "original_matrix_ranks": original_rank,
        "untransformed_paired_products": sum((r + 1) // 2 for r in original_rank),
        "transformed_paired_products": products,
        "kernels_found": sum(1 for c in certificates if c["kernel"] is not None),
        "certificates": len(certificates),
    }


def zero_invalid(ac, D, lowbits):
    for h in range(ac.shape[0]):
        for l in range(ac.shape[1]):
            if (h << lowbits) | l >= D:
                ac[h, l] = 0
    return ac


def main() -> None:
    z = np.load(NPZ, allow_pickle=False)
    words0 = z["angle_words"].copy()
    brot = int(z["brot"].item())
    edges = z["tree_edges"].copy()
    D = len(words0)
    R, B = 9, 143
    N = 76
    assert D == N + R * B and brot == 8

    A = (D + (1 << LB) - 1) // (1 << LB)
    Blk = 1 << LB
    n_sel = (D - 1).bit_length()
    cache = sum(1 for m in range(1, A) if m.bit_count() > 1) + \
            sum(1 for m in range(1, Blk) if m.bit_count() > 1)
    fixed_ccx_per_loader = 2 * cache
    q_circuit = n_sel + J * brot + (A - 1) + (Blk - 1)
    print(f"D={D} A={A} B={Blk} n_sel={n_sel} cache={cache} "
          f"fixed_ccx/loader={fixed_ccx_per_loader} q_circuit={q_circuit}")

    def order_cost(words_gauged: np.ndarray, tag: str) -> dict:
        t0 = time.time()
        per_loader = []
        total_content = 0
        for k in range(75 // J):
            delta = delta_batch(words_gauged, J, k)
            ac = core.coefficients(delta, brot, LB)
            ac = zero_invalid(ac, D, LB)
            pl = plan_zeroed(delta, ac, brot, LB, MAX_KERNELS)
            content = pl["transformed_paired_products"]
            total_content += content
            per_loader.append({
                "k": k,
                "content_ccx": content,
                "static_ccx": content + fixed_ccx_per_loader,
                "kernels_found": pl["kernels_found"],
                "untransformed": pl["untransformed_paired_products"],
                "searched": pl["searched_nonzero_low_kernels"],
            })
        dt = time.time() - t0
        angles_toffoli = 2 * (total_content + (75 // J) * fixed_ccx_per_loader)
        return {"tag": tag, "total_content_ccx": total_content,
                "total_static_ccx": total_content + (75 // J) * fixed_ccx_per_loader,
                "predicted_angles_toffoli": angles_toffoli,
                "seconds": round(dt, 1), "per_loader": per_loader}

    # --- calibration on current ordering ---
    cur_words, cur_signs = core.canonical_gauge(words0, edges, brot)
    cur = order_cost(cur_words, "current")
    print(f"\nCURRENT: static CCX={cur['total_static_ccx']} "
          f"predicted angles_toffoli={cur['predicted_angles_toffoli']} "
          f"(measured by verifier: 8932)  [{cur['seconds']}s]")
    print("per-loader kernels:", [p["kernels_found"] for p in cur["per_loader"]])

    # --- 20 random permutations (same seed/sequence as gauge_test.py) ---
    rng = np.random.default_rng(SEED)
    results = [cur]
    for i in range(N_PERMS):
        pi = rng.permutation(B)
        wp = words0.copy()
        for r in range(R):
            block = N + r * B
            wp[block:block + B] = words0[block:block + B][pi]
        wg, _ = core.canonical_gauge(wp, edges, brot)
        res = order_cost(wg, f"perm{i}")
        d = res["predicted_angles_toffoli"] - cur["predicted_angles_toffoli"]
        results.append(res)
        print(f"perm{i:2d}: static={res['total_static_ccx']:5d} "
              f"angles_T={res['predicted_angles_toffoli']:5d} (d={d:+5d}) "
              f"kernels={sum(p['kernels_found'] for p in res['per_loader']):3d} "
              f"[{res['seconds']}s]")

    OUT.write_text(json.dumps(results, indent=2))
    best = min(results[1:], key=lambda r: r["predicted_angles_toffoli"])
    print(f"\nBEST perm: {best['tag']} angles_T={best['predicted_angles_toffoli']} "
          f"(d={best['predicted_angles_toffoli']-cur['predicted_angles_toffoli']:+d})")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
