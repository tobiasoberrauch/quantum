"""Gauge-symmetry test: permutations of the M=143 THC leaf index (b axis).

Tests the claim that permuting the b index consistently in W (weights) and in
the two-body rows of the angle-word table leaves error_1, error_2, Lambda,
E_SOS, E_gap, lambda_eff unchanged, by calling the verifier's own metric
function dfthcsos.scoreinfra.dfthc_math.evaluate_dfthc_angle_words directly
(no circuit simulation needed).

Gauge consistency: X^(rc) = sum_b w_b u_b u_b^T is invariant iff
w'_t = w_{sigma(t)} AND u'_t = u_{sigma(t)} for the same sigma.
Two-body row of vector u_b^(rho) lives at table row N + rho*B + b.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path("/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum")
sys.path.insert(0, str(REPO / "data" / "verifiers"))

import numpy as np

from dfthcsos.scoreinfra.dfthc_math import (
    evaluate_dfthc_angle_words,
    symmetric_from_lower,
)
from dfthcsos.scoreinfra.reference import (
    ORBITALS,
    UPPER_ENERGY,
    check_fcidump,
    load_fixed_shifts,
    load_reference,
)

NPZ = REPO / "work/frontier_scan/mwa2_unpacked/dfthcsos/submission.npz"
OUT = REPO / "work/p0_reports/gauge_test_results.json"

N = ORBITALS  # 76


def main() -> None:
    z = np.load(NPZ, allow_pickle=False)
    U = np.array(z["U"], dtype=np.float64)        # (R, B, N)
    W = np.array(z["W"], dtype=np.float64)        # (R, B, C) lowercase w
    H2_I = np.array(z["H2_I"], dtype=np.float64)  # (R, C) w_B = W + sum_b w
    angle_words = np.array(z["angle_words"])       # (N + R*B, N-1) int64
    tree_edges = np.array(z["tree_edges"])         # (N-1, 2)
    brot = int(z["brot"].item())

    R, B, C = W.shape
    assert U.shape == (R, B, N), U.shape
    assert angle_words.shape == (N + R * B, N - 1), angle_words.shape
    print(f"schema: R={R} B={B} C={C} N={N} brot={brot} "
          f"rows={angle_words.shape[0]} (= {N} one-body + {R*B} two-body)")

    # Fixed competition shift (submitted H1_I/Hsym_lower are ignored by verifier)
    fixed = load_fixed_shifts()
    S = symmetric_from_lower(fixed["Hsym_lower"], N).astype(np.float64)
    beta_1 = float(fixed["H1_I"]) - 0.5 * float(np.trace(S))
    ref = load_reference(check_fcidump())
    print(f"ref: electrons={ref['electrons']} ecore={ref['ecore']:.6f} "
          f"beta_1={beta_1:.6f} E_upper={UPPER_ENERGY}")

    def native(w: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        # w = lowercase (R,B,C); W_native = H2_I - sum_b w  (identity offsets)
        return w, H2_I - w.sum(axis=1)

    def metrics(words: np.ndarray, w: np.ndarray) -> dict[str, float | bool]:
        wn, Wn = native(w)
        return evaluate_dfthc_angle_words(
            words, wn, Wn, S, beta_1, ref,
            brot=brot, tree_edges=tree_edges, energy_upper=UPPER_ENERGY,
        )

    KEY = ("error_1", "error_2", "Lambda", "E_SOS", "E_gap", "lambda_eff")

    t0 = time.time()
    base = metrics(angle_words, W)
    t_base = time.time() - t0
    print(f"\nBASELINE (direct, from npz angle_words; {t_base:.1f}s):")
    for k in (*KEY, "gap_in_domain"):
        v = base[k]
        print(f"  {k:12s} = {v!r}" + (f"  ({1e3*v:.5f} mHa)" if k.startswith("error") else ""))

    rng = np.random.default_rng(20261103)
    rows = []
    max_delta = {k: 0.0 for k in KEY}
    bit_exact = 0
    for i in range(20):
        pi = rng.permutation(B)
        # consistent gauge: sigma = pi for BOTH weights and vectors
        w_p = np.take(W, pi, axis=1)                    # w_p[:, t] = W[:, pi[t]]
        words_p = angle_words.copy()
        for r in range(R):
            block = N + r * B
            words_p[block:block + B] = angle_words[block:block + B][pi]
        t0 = time.time()
        m = metrics(words_p, w_p)
        dt = time.time() - t0
        d = {k: float(m[k]) - float(base[k]) for k in KEY}
        exact = all(m[k] == base[k] for k in KEY)
        bit_exact += int(exact)
        for k in KEY:
            max_delta[k] = max(max_delta[k], abs(d[k]))
        rows.append({
            "i": i, "seed_pi_head": pi[:8].tolist(), "dt_s": round(dt, 2),
            "bit_exact": exact,
            "delta": {k: d[k] for k in KEY},
            "metrics": {k: (m[k] if isinstance(m[k], bool) else float(m[k])) for k in (*KEY, "gap_in_domain")},
        })
        print(f"perm {i:2d}: " + " ".join(f"{k}={d[k]:+.2e}" for k in KEY)
              + f"  [{'EXACT' if exact else 'ulp'} {dt:.1f}s]")

    out = {
        "baseline": {k: (base[k] if isinstance(base[k], bool) else float(base[k]))
                     for k in (*KEY, "gap_in_domain")},
        "bit_exact_count": bit_exact,
        "max_abs_delta": max_delta,
        "permutations": rows,
    }
    OUT.write_text(json.dumps(out, indent=2))
    print(f"\nmax |delta| over 20 perms: "
          + " ".join(f"{k}={max_delta[k]:.3e}" for k in KEY))
    print(f"bit-exact: {bit_exact}/20  ->  {OUT}")


if __name__ == "__main__":
    main()
