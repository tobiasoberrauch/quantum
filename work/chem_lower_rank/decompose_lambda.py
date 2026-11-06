"""Decompose Lambda = lambda_H1 + lambda_H2 for a factorization (numpy, no training).

lambda_H1 (one-body, from h1_prime spectrum) is only weakly affected by lowering
G; lambda_H2 (two-body LCU one-norm) scales with the number of (r,c) terms. This
tells us how much of lambda_eff = sqrt(E_gap*(2*Lambda-E_gap)) is even reducible
by shrinking G/M, independent of any optimization quality.
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/data/verifiers")
from metrics_np import native_inputs, REFERENCE_COST, costs, score_from  # noqa: E402
from dfthcsos.scoreinfra.reference import check_fcidump, load_factorization, load_fixed_shifts, load_reference  # noqa: E402
from dfthcsos.scoreinfra.dfthc_math import build_h1_prime, reconstruct_x  # noqa: E402

REPO = "/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum"


def decompose(params, ref):
    nat = native_inputs(params, ref)
    w, W, S, beta_1 = nat.w, nat.W, nat.S, nat.beta_1
    N = int(ref["orbitals"])
    u_b_rho = np.asarray(params["U"], float)
    X = reconstruct_x(u_b_rho, w)
    X = np.tril(X) + np.swapaxes(np.tril(X, k=-1), -1, -2)
    h1_thc = np.array(ref["oei"] - 0.5 * np.einsum("pqqs->ps", ref["tei"]))
    h1p = build_h1_prime(h1_thc, S, beta_1, ref["electrons"], W, X)
    ev = np.linalg.eigvalsh(h1p)
    lam_h1 = float(np.sum(np.abs(ev)))
    # lambda_h2 = 0.25 sum_rc (||w_rc||_1 + |H2_I_rc|)^2 ; H2_I = W + sum_b w
    H2I = W + np.sum(w, axis=1)
    lam_h2 = float(0.25 * np.sum((np.linalg.norm(w, 1, axis=1) + np.abs(H2I)) ** 2))
    return lam_h1, lam_h2, lam_h1 + lam_h2


def main():
    params = load_factorization(os.path.join(REPO, "work/frontier_scan/mwa2_unpacked/dfthcsos/submission.npz"))
    params.update(load_fixed_shifts())
    ref = load_reference(check_fcidump())
    R, B, C, N = params["W"].shape[0], params["U"].shape[1], params["W"].shape[2], int(ref["orbitals"])
    l1, l2, L = decompose(params, ref)
    print(f"current best ({R},{B},{C}): lambda_H1={l1:.3f}  lambda_H2={l2:.3f}  Lambda={L:.3f}")
    print(f"  two-body fraction of Lambda = {100*l2/L:.1f}%")
    # If we could scale lambda_H2 by (G'/C) while keeping lambda_H1 fixed,
    # estimate lambda_eff at each target G (E_gap held at floor 3.9152).
    Egap_floor = 3.9152
    print(f"\n{'G':>3} {'K=R*C':>6} | {'Lambda_est':>10} {'lamEff_est':>10} {'T_heur':>7} {'ratio_est':>9}  (lambda_H1 fixed, lambda_H2 scaled by G/C)")
    for G in [39, 38, 37, 36, 35, 34]:
        Lest = l1 + l2 * (G / C)
        le = np.sqrt(Egap_floor * (2 * Lest - Egap_floor))
        ch = costs(R, min(B, 76), G, N, brot=8)
        A = N + R * min(B, 76); A_full = N + R * B
        T_est = ch["toffolis"] + 8932.0 * (A / A_full)
        Q_tot = ch["qubits"] + 40
        ratio = REFERENCE_COST / score_from(le, int(T_est), Q_tot)
        print(f"{G:>3} {R*G:>6} | {Lest:>10.2f} {le:>10.3f} {ch['toffolis']:>7d} {ratio:>9.3f}")


if __name__ == "__main__":
    main()
