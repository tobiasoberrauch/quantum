"""Confirm the row-index gauge symmetry (C's proof) holds for Strategy-4 orderings.

Evaluates the verifier's own metric function on the NN-TSP / popcount / random
permuted word tables (weights permuted consistently) and checks that
error_1, error_2, Lambda, E_SOS, E_gap, lambda_eff are invariant to float noise.
Reuses the exact metric wiring from work/p0_reports/gauge_test.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path("/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum")
COMPILER = REPO / ("sota_mrmeows/sources/dfthcsos_8p5558_complete_with_compiler/"
                   "dfthcsos_verified_8p555840/compiler")
sys.path.insert(0, str(REPO / "data" / "verifiers"))
sys.path.insert(0, str(COMPILER))

from dfthcsos.scoreinfra.dfthc_math import evaluate_dfthc_angle_words, symmetric_from_lower  # noqa: E402
from dfthcsos.scoreinfra.reference import (ORBITALS, UPPER_ENERGY, check_fcidump,  # noqa: E402
                                           load_fixed_shifts, load_reference)
import rank_parity as core  # noqa: E402

NPZ = REPO / "work/frontier_scan/mwa2_unpacked/dfthcsos/submission.npz"
RES = REPO / "work/chem_ordering/ordering_results.json"
N = ORBITALS
R, B = 9, 143


def main():
    z = np.load(NPZ, allow_pickle=False)
    W = np.array(z["W"], dtype=np.float64)
    H2_I = np.array(z["H2_I"], dtype=np.float64)
    words0 = np.array(z["angle_words"])
    edges = np.array(z["tree_edges"])
    brot = int(z["brot"].item())

    fixed = load_fixed_shifts()
    S = symmetric_from_lower(fixed["Hsym_lower"], N).astype(np.float64)
    beta_1 = float(fixed["H1_I"]) - 0.5 * float(np.trace(S))
    ref = load_reference(check_fcidump())

    def metrics(words, w):
        wn, Wn = w, H2_I - w.sum(axis=1)
        return evaluate_dfthc_angle_words(words, wn, Wn, S, beta_1, ref,
                                          brot=brot, tree_edges=edges,
                                          energy_upper=UPPER_ENERGY)

    KEY = ("error_1", "error_2", "Lambda", "E_SOS", "E_gap", "lambda_eff")
    base = metrics(words0, W)
    print("BASELINE (shipped):")
    for k in KEY:
        print(f"  {k:10s} = {base[k]!r}")

    res = json.loads(RES.read_text())
    by_tag = {r["tag"]: r for r in res["results"]}
    rng = np.random.default_rng(20261103)
    pi_rand = rng.permutation(B)

    def permute(words, pi):
        wp = words.copy()
        for r in range(R):
            block = N + r * B
            wp[block:block + B] = words[block:block + B][pi]
        return wp

    cases = {
        "nn_tsp": np.array(res["nn_order_full"], dtype=np.int64),
        "random_ref": pi_rand,
    }
    # popcount order (recompute deterministically)
    wg_id, _ = core.canonical_gauge(words0, edges, brot)
    sig = np.stack([wg_id[N + r * B:N + (r + 1) * B] for r in range(R)], axis=1)
    shifts = np.arange(brot)[None, None, None, :]
    sig_bits = ((sig[:, :, :, None] >> shifts) & 1).astype(np.uint8)
    pop_full = sig_bits.sum(axis=(1, 2, 3), dtype=np.int64)
    cases["sort_popcount"] = np.argsort(pop_full, kind="stable").astype(np.int64)

    print("\nGAUGE INVARIANCE (max |delta| vs baseline per metric):")
    out = {"baseline": {k: float(base[k]) for k in KEY}, "cases": {}}
    for tag, pi in cases.items():
        wp = permute(words0, pi)
        w_p = np.take(W, pi, axis=1)
        m = metrics(wp, w_p)
        d = {k: float(m[k]) - float(base[k]) for k in KEY}
        out["cases"][tag] = {"delta": d, "metrics": {k: float(m[k]) for k in KEY}}
        print(f"  {tag:14s}: " + " ".join(f"{k}={d[k]:+.2e}" for k in KEY))

    (REPO / "work/chem_ordering/gauge_check_results.json").write_text(json.dumps(out, indent=2))
    print("\n-> work/chem_ordering/gauge_check_results.json")


if __name__ == "__main__":
    main()
