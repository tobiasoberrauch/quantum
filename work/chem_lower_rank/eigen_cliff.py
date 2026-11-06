"""Rank-cliff via the matricized-target eigen floor (no iterative training).

error_2 = || sum_{rc} X_rc (x) X_rc - T ||_F,  T = tei + S-shift.
Matricizing (pq)|(rs) makes M_T = T.reshape(N^2, N^2) symmetric and (near) PSD,
and sum_{rc} vec(X_rc) vec(X_rc)^T is a sum of rank-1 PSD terms. Hence the best
achievable error_2 using K = R*C squares, ignoring the per-group rank-M limit,
is the tail energy  sqrt( ||T||_F^2 - sum_{k<=K} lambda_k^2 ).

This gives a HARD floor per K=R*C: if the floor > 20 mHa, NO (9,*,G) table with
that many squares reaches error_2 <= 20, whatever M is. We also build one
concrete (9,M,G) table from the top eigenvectors to confirm the floor is tight.
"""
from __future__ import annotations

import os
import sys
import time

import numpy as np
from scipy.sparse.linalg import eigsh

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from metrics_np import REFERENCE_COST, costs, score_from  # noqa: E402
from dfthcsos.scoreinfra.reference import (  # noqa: E402
    check_fcidump, load_factorization, load_fixed_shifts, load_reference,
)
from dfthcsos.scoreinfra.dfthc_math import symmetric_from_lower  # noqa: E402

REPO = "/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum"
SUB = os.path.join(REPO, "work/frontier_scan/mwa2_unpacked/dfthcsos/submission.npz")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eig_top.npz")


def build_target(ref, S):
    N = int(ref["orbitals"])
    tei = np.asarray(ref["tei"], float)
    T = tei.copy()
    idx = np.arange(N)
    T[:, :, idx, idx] += 0.5 * S[:, :, None]
    T[idx, idx, :, :] += 0.5 * S[None, :, :]
    return T


def main():
    t0 = time.time()
    params = load_factorization(SUB)
    params.update(load_fixed_shifts())
    ref = load_reference(check_fcidump())
    N = int(ref["orbitals"])
    S = np.asarray(symmetric_from_lower(params["Hsym_lower"], N), float)
    T = build_target(ref, S)
    fT2 = float(np.sum(T * T))
    print(f"[{time.time()-t0:.0f}s] N={N}  ||T||_F^2={fT2:.6f}  ||T||_F={np.sqrt(fT2):.6f} Ha", flush=True)

    M_T = T.reshape(N * N, N * N)
    M_T = 0.5 * (M_T + M_T.T)  # enforce exact symmetry for eigh/eigsh
    Kmax = 400
    print(f"[{time.time()-t0:.0f}s] eigsh top {Kmax} of {M_T.shape[0]}...", flush=True)
    vals, vecs = eigsh(M_T, k=Kmax, which="LA", maxiter=200000, tol=1e-9)
    order = np.argsort(vals)[::-1]
    vals = vals[order]; vecs = vecs[:, order]
    np.savez(OUT, vals=vals, vecs=vecs, fT2=fT2, N=N)
    print(f"[{time.time()-t0:.0f}s] done. top val={vals[0]:.4f} val[{Kmax-1}]={vals[-1]:.4f}", flush=True)

    R = 9
    print(f"\n{'G':>3} {'K=R*C':>6} {'floor_err2':>11} {'>20mHa?':>8}")
    for G in [40, 39, 38, 37, 36, 35, 34, 33]:
        K = R * G
        if K > len(vals):
            continue
        tail = fT2 - float(np.sum(vals[:K] ** 2))
        floor = np.sqrt(max(0.0, tail))
        print(f"{G:>3} {K:>6} {1e3*floor:>10.3f}mHa {'YES' if 1e3*floor>20 else 'no':>8}")

    # Concrete (9,M,G) table from top eigenvectors: confirm floor is tight.
    print(f"\nConcrete tables (per-group rank-M factorization of top-K eigenvectors):")
    print(f"{'M':>4} {'G':>3} {'K':>4} | {'err2_table':>11} {'floor':>9} | {'lambda_eff':>10} {'T_heur':>7} {'Q_heur':>6} {'ratio_est':>9}")
    for M in [143, 134, 130, 126]:
        for G in [39, 36, 35]:
            K = R * G
            if K > len(vals):
                continue
            tail = fT2 - float(np.sum(vals[:K] ** 2))
            floor = np.sqrt(max(0.0, tail))
            # build table
            U = np.zeros((R, M, N)); W = np.zeros((R, M, G)); H2 = np.zeros((R, G))
            for k in range(K):
                r, c = divmod(k, G)
                lam = vals[k]
                if lam <= 0:
                    continue
                X = (vecs[:, k] * np.sqrt(lam)).reshape(N, N)
                X = 0.5 * (X + X.T)
                ev, evec = np.linalg.eigh(X)
                o = np.argsort(ev)[::-1][:M]
                for b, j in enumerate(o):
                    sgn = 1.0 if ev[j] >= 0 else -1.0
                    U[r, b] = evec[:, j]
                    W[r, b, c] = sgn * np.sqrt(abs(ev[j]))
            # measure error_2 of this concrete table (reuse metrics path)
            from metrics_np import continuous_vectors, native_inputs, evaluate_dfthc_vectors
            tp = {"U": U, "W": W, "H2_I": H2, "Hsym_lower": params["Hsym_lower"], "H1_I": params["H1_I"]}
            nat = native_inputs(tp, ref)
            mv = evaluate_dfthc_vectors(continuous_vectors(nat, U), nat.w, nat.W, nat.S,
                                        nat.beta_1, nat.ref, energy_upper=nat.energy_upper)
            le = mv["lambda_eff"]
            ch = costs(R, M, G, N, brot=8)
            A = N + R * M; A_full = N + R * 143
            T_est = ch["toffolis"] + 8932.0 * (A / A_full)
            Q_tot = ch["qubits"] + 40
            ratio = REFERENCE_COST / score_from(le, int(T_est), Q_tot)
            flag = "" if 1e3*mv["error_2"] <= 20 else "  <-- err2>20"
            print(f"{M:>4} {G:>3} {K:>4} | {1e3*mv['error_2']:>10.3f}mHa {1e3*floor:>8.3f} | {le:>10.3f} {ch['toffolis']:>7d} {ch['qubits']:>6d} {ratio:>9.3f}{flag}")


if __name__ == "__main__":
    main()
