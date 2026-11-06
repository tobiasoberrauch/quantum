"""Strategy 4 — similarity-sorted reordering of the 143 THC leaf indices (b axis).

Hypothesis (untested by Subagent C): arranging the 143 b-indices so consecutive
rows are maximally similar (NN-TSP / similarity sort on Hamming distance) makes
the QROM/loader pay fewer Toffolis, because adjacent rows differ in few bits.

Method = EXACTLY C's pipeline (work/p0_reports/recompile_rank_test.py):
  words -> canonical_gauge -> per loader k: delta_batch(J=5) ->
  coefficients(brot=8, lb=5) -> zero_invalid -> plan_zeroed(max_kernels)
Content-dependent static CCX per loader = transformed_paired_products.
Fixed overhead per loader = 2 * cache.
Predicted verifier angles_toffoli = 2 * sum(static CCX).

The permutation pi is applied CONSISTENTLY to all R=9 rho-blocks of the two-body
rows (row N + rho*B + b -> N + rho*B + pi[b]) and is gauge-invariant (C proved
metrics invariant to float noise). We do NOT touch the one-body rows 0..N-1.

plan_zeroed / zero_invalid are copied VERBATIM from recompile_rank_test.py so the
numbers are directly comparable to C's report (current=9185 static / 7325 content;
scrambled attractor ~7875 content).
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

import rank_parity as core          # noqa: E402
from borrowed_prefix import delta_batch  # noqa: E402

NPZ = REPO / "work/frontier_scan/mwa2_unpacked/dfthcsos/submission.npz"
OUT = REPO / "work/chem_ordering/ordering_results.json"

J = 5            # angles per loader
LB = 5           # lowbits
MAX_KERNELS = 32767
R, B, N = 9, 143, 76


# ---- copied VERBATIM from work/p0_reports/recompile_rank_test.py ----
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
# ---- end verbatim copy ----


def permute_words(words, pi):
    """Apply leaf permutation pi to all R rho-blocks (one-body rows untouched)."""
    wp = words.copy()
    for r in range(R):
        block = N + r * B
        wp[block:block + B] = words[block:block + B][pi]
    return wp


def order_cost(words_gauged, tag):
    t0 = time.time()
    per_loader = []
    total_content = 0
    for k in range(75 // J):
        delta = delta_batch(words_gauged, J, k)
        ac = core.coefficients(delta, BROT, LB)
        ac = zero_invalid(ac, D, LB)
        pl = plan_zeroed(delta, ac, BROT, LB, MAX_KERNELS)
        content = pl["transformed_paired_products"]
        total_content += content
        per_loader.append({"k": k, "content_ccx": content,
                           "static_ccx": content + FIXED_CCX_PER_LOADER,
                           "kernels_found": pl["kernels_found"],
                           "untransformed": pl["untransformed_paired_products"]})
    dt = time.time() - t0
    nloaders = 75 // J
    angles_toffoli = 2 * (total_content + nloaders * FIXED_CCX_PER_LOADER)
    return {"tag": tag, "total_content_ccx": total_content,
            "total_static_ccx": total_content + nloaders * FIXED_CCX_PER_LOADER,
            "predicted_angles_toffoli": angles_toffoli,
            "seconds": round(dt, 1), "per_loader": per_loader}


def nn_path(dist, seeds):
    """Nearest-neighbour PATH (not cycle) over B nodes; returns best order (list of
    old-indices in new-position order) and its total tour length."""
    best_order, best_len = None, float("inf")
    for s in seeds:
        visited = [False] * B
        cur = s
        visited[cur] = True
        order = [cur]
        total = 0
        for _ in range(B - 1):
            row = dist[cur]
            nxt = -1
            nd = float("inf")
            for j in range(B):
                if not visited[j] and row[j] < nd:
                    nd = row[j]; nxt = j
            visited[nxt] = True
            order.append(nxt)
            total += nd
            cur = nxt
        if total < best_len:
            best_len = total
            best_order = order[:]
    return best_order, best_len


def two_opt(order, dist, passes=3):
    """Improve a path by 2-opt reversals (path, not cycle)."""
    def seg_len(a, b):
        return dist[order[a], order[b]]
    cur = order[:]
    improved = True
    p = 0
    while improved and p < passes:
        improved = False
        p += 1
        for i in range(B - 1):
            for j in range(i + 1, B):
                # reverse cur[i..j]; recompute affected edges
                a = cur[i - 1] if i > 0 else None
                b = cur[i]
                c = cur[j]
                d = cur[j + 1] if j + 1 < B else None
                old = (dist[a, b] if a is not None else 0) + \
                      (dist[c, d] if d is not None else 0)
                new = (dist[a, c] if a is not None else 0) + \
                      (dist[b, d] if d is not None else 0)
                if new < old - 1e-9:
                    cur[i:j + 1] = cur[i:j + 1][::-1]
                    improved = True
    return cur


def main():
    global D, FIXED_CCX_PER_LOADER, BROT
    z = np.load(NPZ, allow_pickle=False)
    words0 = z["angle_words"].copy()
    brot = int(z["brot"].item())
    BROT = brot
    edges = z["tree_edges"].copy()
    D = len(words0)
    assert D == N + R * B and brot == 8, (D, brot)

    A = (D + (1 << LB) - 1) // (1 << LB)
    Blk = 1 << LB
    n_sel = (D - 1).bit_length()
    cache = sum(1 for m in range(1, A) if m.bit_count() > 1) + \
            sum(1 for m in range(1, Blk) if m.bit_count() > 1)
    FIXED_CCX_PER_LOADER = 2 * cache
    q_circuit = n_sel + J * brot + (A - 1) + (Blk - 1)
    print(f"D={D} A={A} B={Blk} n_sel={n_sel} cache={cache} "
          f"fixed_ccx/loader={FIXED_CCX_PER_LOADER} q_circuit={q_circuit}")

    # ---- gauge identity once to build the distance matrix on the ENCODED bits ----
    words_g_id, _ = core.canonical_gauge(words0, edges, brot)
    # two-body signature per leaf b: stack the R rows (each 75 word-values, 8-bit)
    sig = np.stack([words_g_id[N + r * B:N + (r + 1) * B] for r in range(R)], axis=1)
    # sig[b, r, word] shape (B, R, 75); entries are 8-bit word VALUES (0..255)
    # expand each word value to its brot bits -> sig_bits[b, r, word, bitpos] (B,R,75,brot)
    shifts = np.arange(brot)[None, None, None, :]
    sig_bits = ((sig[:, :, :, None] >> shifts) & 1).astype(np.uint8)
    nbits = R * 75 * brot
    # aggregate Hamming distance d[b,b'] = sum over r,word,bitpos of XOR
    dist = np.zeros((B, B), dtype=np.int64)
    for r in range(R):
        sb = sig_bits[:, r, :, :]                       # (B,75,brot)
        x = sb[:, None, :, :] ^ sb[None, :, :, :]       # (B,B,75,brot)
        dist += x.sum(axis=(2, 3), dtype=np.int64)
    np.fill_diagonal(dist, 0)
    mean_offdiag = dist[~np.eye(B, dtype=bool)].mean()
    print(f"distance matrix: mean off-diag = {mean_offdiag:.2f} / {nbits} bits "
          f"(min={dist.min()}, max={dist.max()})")

    results = []

    # ---- (c) SHIPPED baseline (identity) ----
    cur = order_cost(words_g_id, "shipped")
    results.append(cur)
    print(f"\nSHIPPED: static CCX={cur['total_static_ccx']} "
          f"content={cur['total_content_ccx']} "
          f"angles_T={cur['predicted_angles_toffoli']} [{cur['seconds']}s]")
    print("  (C reported current=9185 static / 7325 content -- must match)")

    # ---- reference random perm (confirm ~7875 scrambled attractor) ----
    rng = np.random.default_rng(20261103)
    pi_rand = rng.permutation(B)
    wr, _ = core.canonical_gauge(permute_words(words0, pi_rand), edges, brot)
    rr = order_cost(wr, "random_ref")
    results.append(rr)
    print(f"\nRANDOM_REF: static={rr['total_static_ccx']} content={rr['total_content_ccx']} "
          f"(C attractor ~7875 content) [{rr['seconds']}s]")

    # ---- (a) NN-TSP multi-seed on aggregate Hamming distance ----
    t0 = time.time()
    nn_order, nn_len = nn_path(dist, seeds=list(range(B)))  # all 143 seeds
    nn_order = two_opt(nn_order, dist, passes=4)
    nn_len_final = sum(int(dist[nn_order[i], nn_order[i + 1]]) for i in range(B - 1))
    dt_nn = time.time() - t0
    pi_nn = np.array(nn_order, dtype=np.int64)
    wn, _ = core.canonical_gauge(permute_words(words0, pi_nn), edges, brot)
    rn = order_cost(wn, "nn_tsp")
    results.append(rn)
    print(f"\nNN_TSP: tour_len={nn_len_final} (raw NN {nn_len}) [{dt_nn:.1f}s] "
          f"static={rn['total_static_ccx']} content={rn['total_content_ccx']} "
          f"angles_T={rn['predicted_angles_toffoli']} [{rn['seconds']}s]")

    # ---- (b) deterministic similarity sorts (on expanded bits) ----
    def evaluate_pi(pi, tag):
        wp = permute_words(words0, pi)
        wg, _ = core.canonical_gauge(wp, edges, brot)
        res = order_cost(wg, tag)
        results.append(res)
        print(f"{tag:16s}: static={res['total_static_ccx']:5d} "
              f"content={res['total_content_ccx']:5d} "
              f"angles_T={res['predicted_angles_toffoli']:5d} [{res['seconds']}s]")
        return res

    # popcount of full signature (all R blocks)
    pop_full = sig_bits.sum(axis=(1, 2, 3), dtype=np.int64)
    pi_pop = np.argsort(pop_full, kind="stable").astype(np.int64)
    evaluate_pi(pi_pop, "sort_popcount")

    # popcount of first block only (rho=0)
    pop0 = sig_bits[:, 0, :, :].sum(axis=(1, 2), dtype=np.int64)
    pi_pop0 = np.argsort(pop0, kind="stable").astype(np.int64)
    evaluate_pi(pi_pop0, "sort_popcount_r0")

    # integer value of first-block signature (bit 0 = LSB), packed over first 64 bits
    flat_r0 = sig_bits[:, 0, :, :].reshape(B, -1)          # (B, 75*brot)=(B,600)
    v64 = (flat_r0[:, :64].astype(np.int64) * (1 << np.arange(64))).sum(axis=1)
    pi_val = np.argsort(v64, kind="stable").astype(np.int64)
    evaluate_pi(pi_val, "sort_value_r0")

    # Gray-code projection: order by gray code of the first-block value
    g = v64 ^ (v64 >> 1)
    pi_gray = np.argsort(g, kind="stable").astype(np.int64)
    evaluate_pi(pi_gray, "sort_gray_r0")

    # leading-bit run: sort by index of highest set bit of first block, then value
    # highest set-bit position within the 600-bit first-block signature
    hi_pos = np.full(B, -1, dtype=np.int64)
    for b in range(B):
        idx = np.flatnonzero(flat_r0[b])
        hi_pos[b] = int(idx.max()) if idx.size else -1
    order_key = hi_pos.astype(np.float64) * 1e6 + (v64 % 1000000)
    pi_hi = np.argsort(order_key, kind="stable").astype(np.int64)
    evaluate_pi(pi_hi, "sort_leadbit_run")

    # ---- summary table ----
    print("\n" + "=" * 78)
    print(f"{'ordering':16s} {'static':>7s} {'content':>8s} {'angles_T':>9s} {'d_static':>9s}")
    print("-" * 78)
    base_static = cur["total_static_ccx"]
    for r in results:
        ds = r["total_static_ccx"] - base_static
        print(f"{r['tag']:16s} {r['total_static_ccx']:7d} {r['total_content_ccx']:8d} "
              f"{r['predicted_angles_toffoli']:9d} {ds:+9d}")
    print("=" * 78)

    best = min(results, key=lambda r: r["total_static_ccx"])
    print(f"\nBEST: {best['tag']} static={best['total_static_ccx']} "
          f"content={best['total_content_ccx']} "
          f"d_static_vs_shipped={best['total_static_ccx']-base_static:+d}")

    OUT.write_text(json.dumps({
        "config": {"J": J, "LB": LB, "MAX_KERNELS": MAX_KERNELS, "R": R, "B": B, "N": N,
                   "A": A, "cache": cache, "fixed_ccx_per_loader": FIXED_CCX_PER_LOADER,
                   "q_circuit": q_circuit},
        "distance_mean_offdiag": float(mean_offdiag),
        "identity_path_len": int(sum(dist[i, i + 1] for i in range(B - 1))),
        "random_path_len": int(sum(dist[pi_rand[i], pi_rand[i + 1]] for i in range(B - 1))),
        "nn_tour_len_final": int(nn_len_final),
        "nn_order_head": nn_order[:16],
        "nn_order_full": nn_order,
        "results": results,
    }, indent=2))
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
