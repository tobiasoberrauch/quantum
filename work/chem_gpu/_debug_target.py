"""Debug the packed-pair target reconstruction against dfthc_math's authoritative error_2."""
import os, sys
import numpy as np
REPO = "/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum"
for p in (os.path.join(REPO, "data", "verifiers"), os.path.join(REPO, "work", "chem_lower_rank")):
    sys.path.insert(0, p)
from dfthcsos.scoreinfra.reference import check_fcidump, load_factorization, load_fixed_shifts, load_reference
from dfthcsos.scoreinfra.dfthc_math import reconstruct_x, reconstruct_h2, symmetric_from_lower
from metrics_np import continuous_vectors, evaluate_dfthc_vectors, native_inputs

BASELINE = os.path.join(REPO, "work/frontier_scan/mwa2_unpacked/dfthcsos/submission.npz")


def packed_pairs(N):
    ii, jj = [], []
    for high in range(N):
        for low in range(high + 1):
            ii.append(high); jj.append(low)
    return np.asarray(ii), np.asarray(jj)


def main():
    params = load_factorization(BASELINE); params.update(load_fixed_shifts())
    ref = load_reference(check_fcidump())
    N = int(ref["orbitals"])
    S = np.asarray(symmetric_from_lower(params["Hsym_lower"], N), float)
    ii, jj = packed_pairs(N)
    mult = np.where(ii == jj, 1.0, 2.0); d = np.sqrt(mult)

    # authoritative
    nat = native_inputs(params, ref)
    mv = evaluate_dfthc_vectors(continuous_vectors(nat, params["U"]), nat.w, nat.W, nat.S,
                                nat.beta_1, nat.ref, energy_upper=nat.energy_upper)
    print(f"dfthc_math error_2 = {1e3*mv['error_2']:.4f} mHa")

    # reconstruct sum_rc X_rc (x) X_rc (full N^4)
    w = np.asarray(params["W"], float)
    Wpaper = np.asarray(params["H2_I"], float) - np.sum(w, axis=1)
    u_b_rho = np.asarray(params["U"], float)
    X = reconstruct_x(u_b_rho, w)                       # (R,C,N,N)
    X = np.tril(X) + np.swapaxes(np.tril(X, k=-1), -1, -2)
    sumX = reconstruct_h2(X)                            # (N,N,N,N)

    # candidate targets
    tei = np.asarray(ref["tei"], float)
    idx = np.arange(N)
    Tfull = tei.copy()
    Tfull[:, :, idx, idx] += 0.5 * S[:, :, None]
    Tfull[idx, idx, :, :] += 0.5 * S[None, :, :]
    err_full = np.linalg.norm(sumX - Tfull)
    print(f"||sumX - (tei+Sshift)||_F (my target) = {1e3*err_full:.4f} mHa")

    # also try WITHOUT the S-shift (pure tei)
    err_tei = np.linalg.norm(sumX - tei)
    print(f"||sumX - tei||_F (no shift)            = {1e3*err_tei:.4f} mHa")

    # packed version of MY target
    Tpack = Tfull[ii[:, None], jj[None, :], ii[None, :], jj[None, :]]
    sumXpack = sumX[ii[:, None], jj[None, :], ii[None, :], jj[None, :]]
    Dpack = d[:, None] * (sumXpack - Tpack) * d[None, :]
    print(f"packed ||(d o d)(sumX-T)||_F           = {1e3*np.linalg.norm(Dpack):.4f} mHa")

    # what does the notebook A.T@A give for the current best?
    A = np.einsum("rbc,rbp->rcp", w, u_b_rho[:, :, ii] * u_b_rho[:, :, jj]).reshape(-1, len(ii)) * d
    Tw = d[:, None] * Tpack * d[None, :]
    print(f"notebook formula ||A.T@A - Tw||_F      = {1e3*np.linalg.norm(A.T @ A - Tw):.4f} mHa")


if __name__ == "__main__":
    main()
