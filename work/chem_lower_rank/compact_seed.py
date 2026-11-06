"""Compact-group eigen seed -> concrete (9,M,G) DF-THC tables (no iterative training).

Clusters the top-K eigen-squares of the matricized target by orbital support
(balanced-ish k-means on row-energy profiles) so that each group's copies are
approximately simultaneously diagonalizable -> a good SHARED basis per group ->
low error_2 that respects the real grouped constraint. Measures error_2,
lambda_eff, E_gap and the cost-model ratio, and saves tables as training seeds.
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
OUTDIR = os.path.dirname(os.path.abspath(__file__))
R = 9


def symvec(X):
    n = X.shape[0]
    return X[np.tril_indices(n)]


def kmeans(X, k, iters=60, seed=0):
    rng = np.random.default_rng(seed)
    C = X[rng.choice(len(X), k, replace=False)]
    lab = np.zeros(len(X), int)
    for _ in range(iters):
        d = ((X[:, None, :] - C[None]) ** 2).sum(-1)
        lab = d.argmin(1)
        for j in range(k):
            m = lab == j
            if m.any():
                C[j] = X[m].mean(0)
    return lab, C


def build_compact(vals, vecs, M, G, N, seed=0):
    K = R * G
    Xs = []
    profs = []
    for k in range(K):
        lam = vals[k]
        X = np.zeros((N, N)) if lam <= 0 else (vecs[:, k] * np.sqrt(lam)).reshape(N, N)
        X = 0.5 * (X + X.T)
        Xs.append(X)
        profs.append(np.sqrt((X ** 2).sum(1)) + 1e-300)
    profs = np.array(profs)
    profs /= np.linalg.norm(profs, axis=1, keepdims=True)
    lab, _ = kmeans(profs, R, seed=seed)
    Mb = min(M, N)
    U = np.zeros((R, Mb, N)); W = np.zeros((R, Mb, G)); H2 = np.zeros((R, G))
    for r in range(R):
        members = [k for k in range(K) if lab[k] == r]
        members.sort(key=lambda k: -vals[k])
        members = members[:G]
        while len(members) < G:  # top up if a cluster was starved
            extra = [k for k in range(K) if k not in members]
            extra.sort(key=lambda k: -vals[k])
            members.append(extra[0])
        groupX = [Xs[k] for k in members]
        Xsum = sum(groupX)
        ev, evec = np.linalg.eigh(Xsum)
        o = np.argsort(ev)[::-1][:Mb]
        basis = evec[:, o]
        cols = np.stack([symvec(np.outer(basis[:, b], basis[:, b])) for b in range(Mb)], axis=1)
        U[r] = basis.T
        for ci, k in enumerate(members):
            w, *_ = np.linalg.lstsq(cols, symvec(groupX[ci]), rcond=None)
            W[r, :, ci] = w
    return {"U": U, "W": W, "H2_I": H2}


def main():
    params = load_factorization(SUB)
    params.update(load_fixed_shifts())
    ref = load_reference(check_fcidump())
    N = int(ref["orbitals"])
    e = np.load(EIG)
    vals, vecs = e["vals"], e["vecs"]

    print(f"{'M':>4} {'G':>3} {'K':>4} | {'err2':>9} {'lamEff':>8} {'Egap':>9} {'Lambda':>8} | {'T_heur':>7} {'Q_heur':>6} {'ratio_est':>9}")
    for M in [143, 134, 130, 126]:
        for G in [39, 36, 35]:
            tp = build_compact(vals, vecs, M, G, N)
            tp["Hsym_lower"] = params["Hsym_lower"]; tp["H1_I"] = params["H1_I"]
            nat = native_inputs(tp, ref)
            mv = evaluate_dfthc_vectors(continuous_vectors(nat, tp["U"]), nat.w, nat.W,
                                        nat.S, nat.beta_1, nat.ref, energy_upper=nat.energy_upper)
            le = mv["lambda_eff"]
            Mt = tp["U"].shape[1]
            ch = costs(R, Mt, G, N, brot=8)
            A = N + R * Mt; A_full = N + R * 143
            T_est = ch["toffolis"] + 8932.0 * (A / A_full)
            Q_tot = ch["qubits"] + 40
            ratio = REFERENCE_COST / score_from(le, int(T_est), Q_tot)
            flag = "" if 1e3 * mv["error_2"] <= 20 else "  <-- err2>20"
            print(f"{Mt:>4} {G:>3} {R*G:>4} | {1e3*mv['error_2']:>8.3f}m {le:>8.3f} "
                  f"{mv['E_gap']:>9.5f} {mv['Lambda']:>8.2f} | {ch['toffolis']:>7d} {ch['qubits']:>6d} {ratio:>9.3f}{flag}")
            np.savez(os.path.join(OUTDIR, f"seed_{M}_{G}.npz"),
                     U=tp["U"], W=tp["W"], H2_I=tp["H2_I"],
                     Hsym_lower=tp["Hsym_lower"], H1_I=tp["H1_I"])


if __name__ == "__main__":
    main()
