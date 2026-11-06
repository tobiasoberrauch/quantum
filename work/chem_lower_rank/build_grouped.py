"""Build concrete grouped (9,M,G) DF-THC tables from the matricized-target eigenvectors.

Respects the real constraint: group r shares ONE basis {u_b^r, b<M}; every copy c
in the group uses that basis with weights w_b^rc, so X_rc = sum_b w_b^rc u_b^r u_b^r^T.

Per group: shared basis = top-M eigenvectors of the group's summed target matrix;
weights = least-squares fit of each copy's matrix onto the {u_b u_b^T} design.
Measures the true (constraint-respecting) error_2, lambda_eff, E_gap, and the
cost-model ratio. No iterative training -> fast, decisive cliff evidence.
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from metrics_np import (  # noqa: E402
    REFERENCE_COST, continuous_vectors, costs, evaluate_dfthc_vectors,
    native_inputs, score_from,
)
from dfthcsos.scoreinfra.reference import (  # noqa: E402
    check_fcidump, load_factorization, load_fixed_shifts, load_reference,
)
from dfthcsos.scoreinfra.dfthc_math import symmetric_from_lower  # noqa: E402

REPO = "/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum"
SUB = os.path.join(REPO, "work/frontier_scan/mwa2_unpacked/dfthcsos/submission.npz")
EIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eig_top.npz")
R = 9


def symvec(X):
    """Pack a symmetric (N,N) matrix to its N(N+1)/2 unique entries."""
    n = X.shape[0]
    return X[np.tril_indices(n)]


def unvec_sym(v, n):
    X = np.zeros((n, n))
    X[np.tril_indices(n)] = v
    return X + X.T - np.diag(np.diag(X))


def build_table(vals, vecs, M, G, N, grouping="contiguous"):
    K = R * G
    Mb = min(M, N)  # shared basis per group lives in R^N -> at most N independent vectors
    # assign the top-K eigenvectors to (r,c) slots
    order = list(range(K))
    if grouping == "contiguous":
        slots = [(r, c) for r in range(R) for c in range(G)]
    elif grouping == "roundrobin":
        slots = [(c // G, c % G) for c in range(K)]  # spread magnitudes across groups
    else:
        raise ValueError(grouping)
    Xg = {}
    for k, (r, c) in enumerate(slots):
        lam = vals[k]
        if lam <= 0:
            Xg[(r, c)] = np.zeros((N, N))
            continue
        X = (vecs[:, k] * np.sqrt(lam)).reshape(N, N)
        Xg[(r, c)] = 0.5 * (X + X.T)
    U = np.zeros((R, Mb, N)); W = np.zeros((R, Mb, G)); H2 = np.zeros((R, G))
    for r in range(R):
        groupX = [Xg[(r, c)] for c in range(G)]
        Xsum = sum(groupX)
        ev, evec = np.linalg.eigh(Xsum)
        o = np.argsort(ev)[::-1][:Mb]
        basis = evec[:, o]                       # (N, Mb) shared basis for group r
        # design columns: u_b u_b^T packed symmetric
        cols = np.stack([symvec(np.outer(basis[:, b], basis[:, b])) for b in range(Mb)], axis=1)  # (nnz, Mb)
        for c in range(G):
            tgt = symvec(groupX[c])              # (nnz,)
            w, *_ = np.linalg.lstsq(cols, tgt, rcond=None)   # (Mb,)
            U[r] = basis.T                                   # (Mb, N): U[r,b,p]=basis[p,b]
            W[r, :, c] = w
    return {"U": U, "W": W, "H2_I": H2}


def main():
    params = load_factorization(SUB)
    params.update(load_fixed_shifts())
    ref = load_reference(check_fcidump())
    N = int(ref["orbitals"])
    S = np.asarray(symmetric_from_lower(params["Hsym_lower"], N), float)
    e = np.load(EIG)
    vals, vecs, fT2 = e["vals"], e["vecs"], float(e["fT2"])

    print(f"{'grp':>10} {'Mtbl':>5} {'G':>3} {'K':>4} | {'err2':>9} {'lamEff':>8} {'Egap':>9} {'Lambda':>8} | {'T_heur':>7} {'Q_heur':>6} {'ratio_est':>9}")
    for grouping in ["contiguous", "roundrobin"]:
        for M in [143, 134, 130, 126]:
            for G in [39, 36, 35]:
                tp = build_table(vals, vecs, M, G, N, grouping)
                tp["Hsym_lower"] = params["Hsym_lower"]; tp["H1_I"] = params["H1_I"]
                nat = native_inputs(tp, ref)
                mv = evaluate_dfthc_vectors(continuous_vectors(nat, tp["U"]), nat.w, nat.W,
                                            nat.S, nat.beta_1, nat.ref, energy_upper=nat.energy_upper)
                le = mv["lambda_eff"]
                Mt = tp["U"].shape[1]  # actual basis width used (=min(M,76))
                ch = costs(R, Mt, G, N, brot=8)
                A = N + R * Mt; A_full = N + R * 143
                T_est = ch["toffolis"] + 8932.0 * (A / A_full)
                Q_tot = ch["qubits"] + 40
                ratio = REFERENCE_COST / score_from(le, int(T_est), Q_tot)
                flag = "" if 1e3 * mv["error_2"] <= 20 else "  <-- err2>20"
                print(f"{grouping:>10} {Mt:>5} {G:>3} {R*G:>4} | {1e3*mv['error_2']:>8.3f}m {le:>8.3f} "
                      f"{mv['E_gap']:>9.5f} {mv['Lambda']:>8.2f} | {ch['toffolis']:>7d} {ch['qubits']:>6d} {ratio:>9.3f}{flag}")


if __name__ == "__main__":
    main()
