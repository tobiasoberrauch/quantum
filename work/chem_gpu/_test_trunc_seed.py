"""Test: truncate the known-good current-best (9,143,39) to (9,M,G) as the seed.

Rationale: we already have a trained 20 mHa solution. A lower-rank seed that is a
consistent subset of it is guaranteed to be in the right basin (unlike rebuilding
from the Hamiltonian via Cholesky+kmeans+OMP, which lands far away on CPU).
Ranking: copies by ||W[r,:,c]||^2 + H2_I[r,c]^2; basis by ||W[r,b,kept]||^2.
"""
import os, sys
import numpy as np
REPO = "/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum"
for p in (os.path.join(REPO, "data", "verifiers"), os.path.join(REPO, "work", "chem_lower_rank")):
    sys.path.insert(0, p)
from dfthcsos.scoreinfra.reference import (check_fcidump, load_factorization,
                                           load_fixed_shifts, load_reference)
from metrics_np import native_inputs, evaluate, costs, ratio, score_from

B = os.path.join(REPO, "work/frontier_scan/mwa2_unpacked/dfthcsos/submission.npz")
params = load_factorization(B); params.update(load_fixed_shifts())
ref = load_reference(check_fcidump()); N = int(ref["orbitals"])
U0 = np.asarray(params["U"], float); W0 = np.asarray(params["W"], float)
H2 = np.asarray(params["H2_I"], float); H1 = params["H1_I"]; Hs = params["Hsym_lower"]
R, Bn, Cn = W0.shape
print(f"current best: R,B,C,N = {R},{Bn},{Cn},{N}")


def truncate(U, W, H2, M, G, iters=3):
    """Return (U,W,H2) of shape (R,M,G) keeping the most important copies/basis."""
    U = U.copy(); W = W.copy(); H2 = H2.copy()
    for _ in range(iters):
        keep_c = []
        for r in range(R):
            imp = (W[r] ** 2).sum(0) + H2[r] ** 2          # (C,)
            idx = np.argsort(-imp)[:G]
            keep_c.append(np.sort(idx))
        W = W[:, :, keep_c]; H2 = H2[:, keep_c]
        keep_b = []
        for r in range(R):
            imp = (W[r] ** 2).sum(1)                        # (B,)
            idx = np.argsort(-imp)[:M]
            keep_b.append(np.sort(idx))
        U = U[:, keep_b, :]; W = W[:, keep_b, :]
    return U, W, H2


for M, G in [(134, 36), (130, 36), (134, 35), (130, 35), (132, 36), (132, 35), (129, 35), (129, 36)]:
    Ut, Wt, H2t = truncate(U0, W0, H2, M, G)
    tp = {"U": Ut, "W": Wt, "H2_I": H2t, "H1_I": H1, "Hsym_lower": Hs}
    nat = native_inputs(tp, ref)
    mv = evaluate(nat, Ut)
    c = costs(R, M, G, N, brot=8)
    sc = score_from(mv["lambda_eff"], c["toffolis"], c["qubits"])
    print(f"M={M:>3} G={G:>2} | err2={1e3*mv['error_2']:>7.2f}m lamEff={mv['lambda_eff']:>7.3f} "
          f"Egap={mv['E_gap']:>8.5f} Lam={mv['Lambda']:>7.2f} | T={c['toffolis']:>6} Q={c['qubits']:>3} "
          f"ratio={ratio(sc):>6.3f}x")
