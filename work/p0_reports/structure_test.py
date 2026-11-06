"""Structural evidence for 'current ordering is co-designed':

1) ANF degree profile of every word bit as a function of the 11 address bits,
   current table vs 20 random permutations (compiler-independent).
   Low degree (<=1 => Reed-Muller RM(1), <=2 => RM(2)) = exploitable linearity.

2) Structured permutations (reverse-b, rho-pair-swap, b-reverse+rho-swap,
   affine-ish b -> (7*b mod 143)) through the same mrmeows planner config.
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path("/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum")
COMPILER = REPO / ("sota_mrmeows/sources/dfthcsos_8p5558_complete_with_compiler/"
                   "dfthcsos_verified_8p555840/compiler")
sys.path.insert(0, str(COMPILER))

import rank_parity as core  # noqa: E402
from borrowed_prefix import delta_batch  # noqa: E402
from recompile_rank_test import LB, J, MAX_KERNELS, plan_zeroed, zero_invalid  # noqa: E402

NPZ = REPO / "work/frontier_scan/mwa2_unpacked/dfthcsos/submission.npz"
OUT = REPO / "work/p0_reports/structure_results.json"
N_PERMS = 20
SEED = 20261103


def anf_degree_profile(words: np.ndarray) -> Counter:
    """Per word bit: degree of highest nonzero ANF monomial over 11 address bits."""
    D = len(words)
    n = (D - 1).bit_length()
    pad = 1 << n
    padded = np.zeros((pad, words.shape[1]), dtype=np.int64)
    padded[:D] = words
    # mobius transform over all n bits of the address axis (one call does all bits)
    t = core.mobius_axis(padded, 0)
    deg = Counter()
    nz = t != 0
    # weight of each monomial index
    w = np.array([i.bit_count() for i in range(pad)], dtype=np.int8)
    for j in range(words.shape[1]):
        cols = nz[:, j]
        if not cols.any():
            deg[0] += 1
            continue
        deg[int(w[cols].max())] += 1
    return deg


def main() -> None:
    z = np.load(NPZ, allow_pickle=False)
    words0 = z["angle_words"].copy()
    brot = int(z["brot"].item())
    edges = z["tree_edges"].copy()
    D, W = words0.shape
    R, B, N = 9, 143, 76

    print(f"== ANF degree profile (11 address bits, {W} word bits) ==")
    prof_cur = anf_degree_profile(words0)
    print("current:", dict(sorted(prof_cur.items())))

    rng = np.random.default_rng(SEED)
    profs = []
    for i in range(N_PERMS):
        pi = rng.permutation(B)
        wp = words0.copy()
        for r in range(R):
            block = N + r * B
            wp[block:block + B] = words0[block:block + B][pi]
        p = anf_degree_profile(wp)
        profs.append(p)
        if i < 3:
            print(f"perm{i}: {dict(sorted(p.items()))}")
    agg = Counter()
    for p in profs:
        agg.update(p)
    print("perm avg:", {k: v / N_PERMS for k, v in sorted(agg.items())})

    # fraction of bits with degree <= d
    def frac_le(prof, d):
        tot = sum(prof.values())
        return sum(v for k, v in prof.items() if k <= d) / tot
    print(f"\nfrac deg<=1: current={frac_le(prof_cur,1):.3f}  perm_avg={frac_le(agg,N_PERMS*1)/N_PERMS if False else sum(frac_le(p,1) for p in profs)/N_PERMS:.3f}")
    print(f"frac deg<=2: current={frac_le(prof_cur,2):.3f}  perm_avg={sum(frac_le(p,2) for p in profs)/N_PERMS:.3f}")

    print("\n== structured permutations through mrmeows planner (J=5, lb=5) ==")
    A = (D + (1 << LB) - 1) // (1 << LB)
    Blk = 1 << LB
    cache = sum(1 for m in range(1, A) if m.bit_count() > 1) + \
            sum(1 for m in range(1, Blk) if m.bit_count() > 1)
    fixed = 2 * cache

    def order_cost(words_gauged: np.ndarray) -> tuple[int, int]:
        total_content, kernels = 0, 0
        for k in range(75 // J):
            delta = delta_batch(words_gauged, J, k)
            ac = core.coefficients(delta, brot, LB)
            ac = zero_invalid(ac, D, LB)
            pl = plan_zeroed(delta, ac, brot, LB, MAX_KERNELS)
            total_content += pl["transformed_paired_products"]
            kernels += pl["kernels_found"]
        return total_content + (75 // J) * fixed, kernels

    cur_words, _ = core.canonical_gauge(words0, edges, brot)
    t0 = time.time()
    cur_static, cur_kern = order_cost(cur_words)
    print(f"current:      static={cur_static} kernels={cur_kern} [{time.time()-t0:.1f}s]")

    structured = {}
    structured["rev_b"] = [B - 1 - b for b in range(B)]
    structured["rho_swap"] = None  # special: swap whole groups 0<->1, 2<->3, ...
    structured["rev_b_rho_swap"] = None
    structured["b7mod"] = [(7 * b) % B for b in range(B)]

    def apply_structured(name: str) -> np.ndarray:
        wp = words0.copy()
        if name == "rev_b":
            for r in range(R):
                blk = N + r * B
                wp[blk:blk + B] = words0[blk:blk + B][::-1]
        elif name == "rho_swap":
            for r in range(0, R - 1, 2):
                b1, b2 = N + r * B, N + (r + 1) * B
                tmp = words0[b1:b1 + B].copy()
                wp[b1:b1 + B] = words0[b2:b2 + B]
                wp[b2:b2 + B] = tmp
        elif name == "rev_b_rho_swap":
            for r in range(0, R - 1, 2):
                b1, b2 = N + r * B, N + (r + 1) * B
                wp[b1:b1 + B] = words0[b2:b2 + B][::-1]
                wp[b2:b2 + B] = words0[b1:b1 + B][::-1]
        elif name == "b7mod":
            for r in range(R):
                blk = N + r * B
                wp[blk:blk + B] = words0[blk:blk + B][structured[name]]
        return wp

    results = {"current": {"static_ccx": cur_static, "kernels": cur_kern}}
    for name in ("rev_b", "rho_swap", "rev_b_rho_swap", "b7mod"):
        wg, _ = core.canonical_gauge(apply_structured(name), edges, brot)
        t0 = time.time()
        st, kn = order_cost(wg)
        dt = time.time() - t0
        results[name] = {"static_ccx": st, "kernels": kn, "delta": st - cur_static}
        print(f"{name:<16}: static={st} kernels={kn} d={st-cur_static:+d} [{dt:.1f}s]")

    OUT.write_text(json.dumps({
        "anf_current": dict(sorted(prof_cur.items())),
        "anf_perm_avg": {k: v / N_PERMS for k, v in sorted(agg.items())},
        "frac_deg_le1": {"current": frac_le(prof_cur, 1),
                         "perm_avg": sum(frac_le(p, 1) for p in profs) / N_PERMS},
        "frac_deg_le2": {"current": frac_le(prof_cur, 2),
                         "perm_avg": sum(frac_le(p, 2) for p in profs) / N_PERMS},
        "structured": results,
    }, indent=2))
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
