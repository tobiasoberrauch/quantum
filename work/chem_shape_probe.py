"""Chemistry shape probe: truncate yoyobar's (8,143,60) factorization to cheaper
shapes (importance-sorted), save as starter-kit NPZs, and report the CONTINUOUS
two-body error via the competition verifier (no angle rounding).

Run from starter_kit/starter_kit/:
    .venv-chem/bin/python ../../work/chem_shape_probe.py
"""
import os
import sys

import numpy as np

REPO_ROOT = "/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum"
SK = os.path.join(REPO_ROOT, "starter_kit", "starter_kit")
sys.path.insert(0, SK)

from starter.task1_factorization.solution_io import save_solution_npz  # noqa: E402
from starter.task1_factorization.check_factorization import check_factorization  # noqa: E402

YOYOBAR = os.path.join(REPO_ROOT, "sota_yoyobar", "submission", "dfthcsos", "submission.npz")
RUNS = os.path.join(SK, "starter", "task1_factorization", "runs")
os.makedirs(RUNS, exist_ok=True)


def load_params(path):
    with np.load(path, allow_pickle=False) as a:
        return {k: a[k] for k in ("U", "W", "H2_I", "H1_I", "Hsym_lower")}


def reorder_and_truncate(p, R, B, C):
    """Keep the R most important rhos, B most important bases per rho,
    C most important ensemble copies. Importance:
      rho r: sum_c |H2_I[r,c]| * ||U_r||_F * ||W_r||_F
      copy c: ||H2_I[:,c]||_2
      base b (per rho): ||W[r,b,:]||_F (after copy selection)
    """
    U, W, H2 = p["U"], p["W"], p["H2_I"]
    r0, b0, c0 = W.shape
    assert U.shape == (r0, b0, p["U"].shape[2])

    u_norm = np.linalg.norm(U, axis=(1, 2))
    w_norm = np.linalg.norm(W, axis=(1, 2))
    rho_imp = np.sum(np.abs(H2), axis=1) * u_norm * w_norm
    c_imp = np.linalg.norm(H2, axis=0)

    r_keep = np.argsort(-rho_imp)[:R]
    c_keep = np.argsort(-c_imp)[:C]
    r_keep = np.sort(r_keep)
    c_keep = np.sort(c_keep)

    U2 = U[r_keep]
    W2 = W[r_keep][:, :, c_keep]
    H22 = H2[np.ix_(r_keep, c_keep)]

    if B < b0:
        b_norm = np.linalg.norm(W2, axis=(1, 2))
        new_W = np.zeros((R, B, C), dtype=W2.dtype)
        new_U = np.zeros((R, B, U.shape[2]), dtype=U2.dtype)
        for i in range(R):
            bk = np.argsort(-b_norm[i])[:B]
            bk = np.sort(bk)
            new_U[i] = U2[i][bk]
            new_W[i] = W2[i][bk]
        U2, W2 = new_U, new_W

    return {
        "U": U2,
        "W": W2,
        "H2_I": H22,
        "H1_I": p["H1_I"].copy(),
        "Hsym_lower": p["Hsym_lower"].copy(),
    }


def main():
    p = load_params(YOYOBAR)
    print(f"yoyobar loaded: U{p['U'].shape} W{p['W'].shape} H2{p['H2_I'].shape} dtype={p['U'].dtype}")

    cases = [
        ("as-is", None),
        ("C60to48", (8, 143, 48)),
        ("R8to7", (7, 143, 60)),
        ("B143to129", (8, 129, 60)),
        ("B143to120", (8, 120, 60)),
        ("RC_C48_B129", (8, 129, 48)),
        ("RC_R7_B129", (7, 129, 60)),
    ]
    results = []
    for name, shape in cases:
        if shape is None:
            q = p
            out = None
        else:
            q = reorder_and_truncate(p, *shape)
            out = os.path.join(RUNS, f"probe_{name}.npz")
            save_solution_npz(out, q, metadata={"probe": name, "seed": "yoyobar-8-143-60"})
        res = check_factorization("FeMoCo76o113e", out or YOYOBAR, verbose=False)
        err_mHa = 1e3 * res["error_2"]
        ok = "PASS" if err_mHa <= 20.0 else "FAIL"
        results.append((name, shape, err_mHa, res["Lambda"], res["E_gap"], res["lambda_eff"], ok))
        print(f"{name:<14} {str(shape):<14} err2={err_mHa:8.4f} mHa [{ok}]  Lambda={res['Lambda']:.4f}  E_gap={res['E_gap']:.6f}  lambda_eff={res['lambda_eff']:.4f}")

    print("\nSaved probes to:", RUNS)


if __name__ == "__main__":
    main()
