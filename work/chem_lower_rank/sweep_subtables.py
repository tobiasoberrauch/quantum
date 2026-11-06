"""Fast lower-rank landscape sweep (NO training).

Truncates the current-best (9,143,39) factorization to (9,M,G) by keeping the
most important basis vectors / copies (top-k by |W| / |H2_I|+|W|), then measures
the CONTINUOUS metric (error_2, lambda_eff) and the SpinFreeData_V1 cost model.

A sub-table is a subset of the existing terms, so its error_2 >= the full table's
(19.9997 mHa). This is therefore an UPPER bound on the achievable min_error_2 for
each shape: real training can only do better. Used to (a) locate the rank cliff
coarsely and (b) generate good seeds for the short training runs.
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from metrics_np import (  # noqa: E402
    REFERENCE_COST,
    Native,
    continuous_vectors,
    costs,
    evaluate_dfthc_vectors,
    native_inputs,
    score_from,
)
from dfthcsos.scoreinfra.reference import (  # noqa: E402
    check_fcidump,
    load_factorization,
    load_fixed_shifts,
    load_reference,
)

REPO = "/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum"
SUB = os.path.join(REPO, "work/frontier_scan/mwa2_unpacked/dfthcsos/submission.npz")


def topk_truncate(params, M, G):
    """Keep top-M basis vectors and top-G copies per group by importance."""
    U = np.asarray(params["U"], float)          # (R,B,N)
    W = np.asarray(params["W"], float)          # (R,B,C)
    H2 = np.asarray(params["H2_I"], float)      # (R,C)
    R, B, N = U.shape
    C = W.shape[2]
    Uo, Wo, Ho = [], [], []
    for r in range(R):
        b_imp = np.sum(np.abs(W[r]), axis=1)            # (B,)
        keep_b = np.argsort(-b_imp)[:M]
        c_imp = np.abs(H2[r]) + np.sum(np.abs(W[r]), axis=0)  # (C,)
        keep_c = np.argsort(-c_imp)[:G]
        Uo.append(U[r, keep_b])                          # (M,N)
        Wo.append(W[r, keep_b][:, keep_c])               # (M,G)
        Ho.append(H2[r, keep_c])                         # (G,)
    out = {"U": np.stack(Uo), "W": np.stack(Wo), "H2_I": np.stack(Ho)}
    out["Hsym_lower"] = params["Hsym_lower"]   # fixed shift, unchanged
    out["H1_I"] = params["H1_I"]
    return out


def main():
    params = load_factorization(SUB)
    params.update(load_fixed_shifts())
    ref = load_reference(check_fcidump())
    nat_full = native_inputs(params, ref)
    R, B, C, N = params["W"].shape[0], params["U"].shape[1], params["W"].shape[2], int(ref["orbitals"])
    print(f"full shape R,B,C,N = {R},{B},{C},{N}")

    # Full-table continuous metrics (sanity).
    mf = evaluate_dfthc_vectors(continuous_vectors(nat_full, params["U"]),
                                nat_full.w, nat_full.W, nat_full.S, nat_full.beta_1,
                                nat_full.ref, energy_upper=nat_full.energy_upper)
    print(f"FULL  error_2={1e3*mf['error_2']:.3f}mHa lambda_eff={mf['lambda_eff']:.3f} "
          f"E_gap={mf['E_gap']:.6f} Lambda={mf['Lambda']:.2f}\n")

    brot = 8
    # Validate cost model against the verifier's reported heuristic numbers.
    cf = costs(R, B, C, N, brot=brot)
    print(f"COST-MODEL full ({R},{B},{C}): outer={cf['outer_toffoli']} inner={cf['inner_toffoli']} "
          f"givens={cf['givens_toffoli']} heur_T={cf['toffolis']} heur_Q={cf['qubits']} "
          f"(verifier: outer=317 inner=4086 givens=2250 heur_T=6653 heur_Q=388)\n")

    header = f"{'M':>4} {'G':>4} | {'err2_sub':>9} {'lamEff_sub':>10} {'Egap_sub':>9} | {'T_heur':>7} {'Q_heur':>6} | {'T_est':>7} {'Q_tot':>6} {'ratio_est':>9}"
    print(header); print("-"*len(header))
    for M in [143, 138, 134, 130, 126]:
        for G in [39, 36, 35]:
            if M > B or G > C:
                continue
            tp = topk_truncate(params, M, G)
            nat = native_inputs(tp, ref)
            mv = evaluate_dfthc_vectors(continuous_vectors(nat, tp["U"]),
                                        nat.w, nat.W, nat.S, nat.beta_1, nat.ref,
                                        energy_upper=nat.energy_upper)
            e2 = 1e3*mv["error_2"]; le = mv["lambda_eff"]; eg = mv["E_gap"]
            c = costs(R, M, G, N, brot=brot)
            # Estimate total Toffolis: heuristic state-prep + Givens, plus an
            # angles-QROM estimate scaling with the number of loaded vectors A=N+R*M.
            A = N + R*M
            A_full = N + R*B
            angles_est = 8932.0 * (A/A_full)          # linear-in-data proxy
            T_est = c["toffolis"] + angles_est
            # Qubit total: heuristic persistent+temp + angles persistent (J*brot) + temp proxy
            angles_pers = 40  # J*brot for the current build (batch_size*brot)
            Q_tot = c["qubits"] + angles_pers
            score = score_from(le, int(T_est), Q_tot)
            ratio = REFERENCE_COST/score
            flag = "" if e2 <= 20.0 else "  <-- err2>20"
            print(f"{M:>4} {G:>4} | {e2:>9.3f} {le:>10.3f} {eg:>9.6f} | {c['toffolis']:>7d} {c['qubits']:>6d} | {int(T_est):>7d} {Q_tot:>6d} {ratio:>9.3f}{flag}")


if __name__ == "__main__":
    main()
