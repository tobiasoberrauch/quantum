"""Real-circuit confirmation of the ordering ranking via kickmix builds.

The plan-only proxy (ordering_test.py) is validated against build() by C and
reproduces C's calibrated numbers exactly. This script upgrades the top
candidates to [FAKT]: it actually builds all 15 loader circuits with the
mrmeows rank_parity compiler + kickmix, runs the symbolic oracle check on each,
and counts NATIVE Toffolis (circuit.operation_statistics().num_toffoli_like).

Pipeline per loader = EXACTLY work/chem_recompile.py:
  delta_batch -> coefficients -> zero_invalid -> plan_zeroed(terms) -> build -> symbolic_check
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path("/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum")
sys.path.insert(0, str(REPO / "work"))
import chem_recompile as cr          # noqa: E402  (sets COMPILER on sys.path; plan_zeroed/zero_invalid)
import rank_parity as core           # noqa: E402
from borrowed_prefix import delta_batch, symbolic_check  # noqa: E402

J, LB, MAXK = 5, 5, 32767
BROT = 8
R, B, N = 9, 143, 76
NPZ = REPO / "work/frontier_scan/mwa2_unpacked/dfthcsos/submission.npz"
RES = REPO / "work/chem_ordering/ordering_results.json"


def permute_words(words, pi):
    wp = words.copy()
    for r in range(R):
        block = N + r * B
        wp[block:block + B] = words[block:block + B][pi]
    return wp


def build_family(words_gauged, tag):
    total_native = 0
    per = []
    t0 = time.time()
    for k in range(75 // J):
        delta = delta_batch(words_gauged, J, k)
        ac = core.coefficients(delta, BROT, LB)
        ac = cr.zero_invalid(ac, len(words_gauged), LB)
        terms, planning, stats = cr.plan_zeroed(delta, ac, BROT, LB, MAXK)
        circuit, trace, report = core.build(delta, BROT, LB, ac, terms)
        sym = symbolic_check(trace, delta, BROT, circuit.num_qubits)
        assert sym["status"] == "PASS", f"{tag} k={k} symbolic {sym['status']}"
        ccx = report["toffoli_count"]
        total_native += ccx
        per.append(ccx)
    dt = time.time() - t0
    print(f"{tag:12s}: native Toffoli sum={total_native}  qubits<=128  [{dt:.1f}s]")
    print(f"{'':12s}  per-loader native CCX: {per}")
    return total_native, per


def main():
    z = np.load(NPZ, allow_pickle=False)
    words0 = z["angle_words"].copy()
    brot = int(z["brot"].item())
    edges = z["tree_edges"].copy()
    assert brot == 8

    res = json.loads(RES.read_text())
    nn_order = np.array(res["nn_order_full"], dtype=np.int64)

    # popcount order (recompute deterministically, matches ordering_test)
    wg_id, _ = core.canonical_gauge(words0, edges, brot)
    sig = np.stack([wg_id[N + r * B:N + (r + 1) * B] for r in range(R)], axis=1)
    shifts = np.arange(brot)[None, None, None, :]
    sig_bits = ((sig[:, :, :, None] >> shifts) & 1).astype(np.uint8)
    pop_full = sig_bits.sum(axis=(1, 2, 3), dtype=np.int64)
    pi_pop = np.argsort(pop_full, kind="stable").astype(np.int64)

    print("=== REAL KICKMIX BUILDS (mrmeows rank_parity compiler) ===")
    sh = build_family(wg_id, "SHIPPED")
    wn, _ = core.canonical_gauge(permute_words(words0, nn_order), edges, brot)
    nn = build_family(wn, "NN_TSP")
    wp, _ = core.canonical_gauge(permute_words(words0, pi_pop), edges, brot)
    pp = build_family(wp, "SORT_POPCNT")

    print("\n=== SUMMARY (native counted Toffoli, forward+reverse = 2x) ===")
    print(f"{'ordering':12s} {'native_CCX':>10s} {'counted_T':>10s} {'d_vs_shipped':>13s}")
    for tag, (tot, _) in [("SHIPPED", sh), ("NN_TSP", nn), ("SORT_POPCNT", pp)]:
        d = tot - sh[0]
        print(f"{tag:12s} {tot:10d} {2*tot:10d} {d:+13d}")

    out = {"shipped_native_ccx": sh[0], "shipped_per_loader": sh[1],
           "nn_tsp_native_ccx": nn[0], "nn_tsp_per_loader": nn[1],
           "sort_popcount_native_ccx": pp[0], "sort_popcount_per_loader": pp[1]}
    (REPO / "work/chem_ordering/build_confirm_results.json").write_text(json.dumps(out, indent=2))
    print("\n-> work/chem_ordering/build_confirm_results.json")


if __name__ == "__main__":
    main()
