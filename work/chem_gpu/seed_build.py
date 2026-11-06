"""Compact Cholesky-clustered DF-THC seed (reimplementation of notebook §2).

Rebuilds Lera's zero-training seed from the Hamiltonian alone:
  1. packed-pair target T (tei + fixed S-shift), multiplicity weighting d=sqrt(mult);
  2. pivoted Cholesky of Tw=D T D -> K=R*G LOCAL leaves;
  3. balanced k-means on the leaves' orbital profiles -> R compact groups of G;
  4. per group: shared basis = top-M eigenvectors of the group's summed leaves,
     weights = mult-weighted least squares of each leaf onto {u_b u_b^T};
  5. assemble dfthc-schema params (U,W,H2_I=0,H1_I,Hsym_lower=frozen) and measure
     the authoritative metrics (dfthc_math) to confirm the seed is in a sane basin.

VALIDATION: the notebook's packed-pair error_2 formula is checked against the
authoritative dfthc_math error_2 on the current best (must agree ~19.99965 mHa),
which confirms T / ii / jj / d are reconstructed correctly.

Writes seeds under work/chem_gpu/seed/. Guards nullable/empty inputs.
"""
from __future__ import annotations

import os
import sys
from typing import Any

import numpy as np

REPO = "/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum"
SK = os.path.join(REPO, "starter_kit", "starter_kit")
CL = os.path.join(REPO, "work", "chem_lower_rank")
for p in (SK, os.path.join(REPO, "data", "verifiers"), CL):
    if p not in sys.path:
        sys.path.insert(0, p)

from dfthcsos.scoreinfra.reference import (  # noqa: E402
    check_fcidump, load_factorization, load_fixed_shifts, load_reference,
)
from dfthcsos.scoreinfra.dfthc_math import reconstruct_x, symmetric_from_lower  # noqa: E402
from metrics_np import continuous_vectors, evaluate_dfthc_vectors, native_inputs  # noqa: E402

OUTDIR = os.path.join(REPO, "work", "chem_gpu", "seed")
BASELINE = os.path.join(REPO, "work/frontier_scan/mwa2_unpacked/dfthcsos/submission.npz")
R = 9


# ---------------------------------------------------------------------------
# Defensive input guards (nullable / empty / whitespace)
# ---------------------------------------------------------------------------
def _require_str(name: str, value: Any) -> str:
    if value is None or not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string, got {value!r}")
    return value.strip()


def _require_int(name: str, value: Any, lo: int, hi: int) -> int:
    if value is None:
        raise ValueError(f"{name} is required (got None)")
    try:
        iv = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be an integer, got {value!r}")
    if not (lo <= iv <= hi):
        raise ValueError(f"{name} must be in [{lo},{hi}], got {iv}")
    return iv


# ---------------------------------------------------------------------------
# Packed-pair target
# ---------------------------------------------------------------------------
def packed_pairs(N: int):
    """Row-major lower-triangle pair indices (high, low), high>=low."""
    ii, jj = [], []
    for high in range(N):
        for low in range(high + 1):
            ii.append(high); jj.append(low)
    ii = np.asarray(ii); jj = np.asarray(jj)
    mult = np.where(ii == jj, 1.0, 2.0)
    return ii, jj, mult


def build_target_full(ref, S):
    """tei + fixed S-shift, full N^4 chemist order (matches dfthc_math target)."""
    N = int(ref["orbitals"])
    tei = np.asarray(ref["tei"], float)
    T = tei.copy()
    idx = np.arange(N)
    T[:, :, idx, idx] += 0.5 * S[:, :, None]
    T[idx, idx, :, :] += 0.5 * S[None, :, :]
    return T


def notebook_error2(U, W, T, ii, jj, mult):
    """The notebook's packed-pair error_2 (mHa). U (R,B,N) normalized rows."""
    d = np.sqrt(mult)
    Uu = U / np.linalg.norm(U, axis=2, keepdims=True)
    A = np.einsum("rbc,rbp->rcp", W, Uu[:, :, ii] * Uu[:, :, jj]).reshape(-1, len(ii)) * d
    Tw = d[:, None] * T * d[None, :]
    return 1e3 * float(np.linalg.norm(A.T @ A - Tw))


def pivoted_cholesky(Tw, K):
    diag = np.diag(Tw).copy()
    L = np.zeros((len(Tw), K))
    for k in range(K):
        q = int(np.argmax(diag))
        if diag[q] <= 0:
            break
        L[:, k] = (Tw[:, q] - L[:, :k] @ L[q, :k]) / np.sqrt(diag[q])
        diag = np.maximum(diag - L[:, k] ** 2, 0)
    return L


def unpack(v, ii, jj, N):
    l = np.zeros((N, N))
    l[ii, jj] = v
    return 0.5 * (l + l.T)


def balanced_kmeans(profile, Rn, C, weight, iters=80, seed=0):
    """k-means with exactly C points per cluster (greedy rebalance)."""
    rng = np.random.default_rng(seed)
    K = len(profile)
    # k-means++ style init
    cents = np.empty((Rn, profile.shape[1]))
    cents[0] = profile[rng.integers(K)]
    for j in range(1, Rn):
        d2 = ((profile[:, None, :] - cents[None, :j]) ** 2).sum(-1).min(1)
        probs = d2 / max(d2.sum(), 1e-300)
        cents[j] = profile[rng.choice(K, p=probs)]
    lab = np.zeros(K, int)
    for _ in range(iters):
        d = ((profile[:, None, :] - cents[None]) ** 2).sum(-1)
        lab = d.argmin(1)
        # rebalance to exactly C per cluster
        counts = np.bincount(lab, minlength=Rn)
        for _ in range(20):
            over = [j for j in range(Rn) if counts[j] > C]
            under = [j for j in range(Rn) if counts[j] < C]
            if not over or not under:
                break
            src = over[0]; dst = under[0]
            members = np.flatnonzero(lab == src)
            dm = ((profile[members] - cents[dst]) ** 2).sum(1)
            move = members[int(np.argmax(dm))]
            lab[move] = dst; counts[src] -= 1; counts[dst] += 1
        for j in range(Rn):
            m = lab == j
            if m.any():
                cents[j] = profile[m].mean(0)
    return lab


def _group_pool(gX, N, cap=320):
    """Candidate orbital vectors for one group: top eigenvectors of the group sum
    plus top eigenvectors of each leaf, normalized and deduped by cosine similarity.
    Returns (N, npool) with npool >= requested M (guarded by caller)."""
    Xsum = sum(gX)
    ev, evec = np.linalg.eigh(Xsum)
    cand = [evec[:, i] for i in np.argsort(ev)[::-1][:N]]
    for Xc in gX:
        evc, evec_c = np.linalg.eigh(Xc)
        cand.extend(evec_c[:, i] for i in np.argsort(evc)[::-1][:4])
    vecs = []
    for v in cand:
        v = v / (np.linalg.norm(v) + 1e-300)
        if any(abs(float(v @ w)) > 0.999 for w in vecs):
            continue
        vecs.append(v)
        if len(vecs) >= cap:
            break
    return np.stack(vecs, axis=1)


def omp_select(Fpool, targets, M):
    """Orthogonal matching pursuit: pick M columns of Fpool (P,npool) minimizing
    ||targets - Fpool[:,sel] @ W||_F. Gram-based (precomputes Fpool^T Fpool).
    Returns (sel (M,), W (M,G))."""
    npool = Fpool.shape[1]
    G = targets.shape[1]
    M = int(min(M, npool))
    Fgram = Fpool.T @ Fpool                 # (npool, npool)
    Ftarget = Fpool.T @ targets             # (npool, G)
    sel = []
    corr = Ftarget.copy()                   # <f_j, residual>, updated incrementally
    for _ in range(M):
        j = int(np.argmax(np.linalg.norm(corr, axis=1)))
        sel.append(j)
        A = Fgram[np.ix_(sel, sel)]
        W, *_ = np.linalg.lstsq(A, Ftarget[sel], rcond=None)
        corr = Ftarget - Fgram[:, sel] @ W
        corr[sel] = -np.inf
    sel = np.asarray(sel)
    A = Fgram[np.ix_(sel, sel)]
    W, *_ = np.linalg.lstsq(A, Ftarget[sel], rcond=None)
    return sel, W


def build_compact_seed(T, ii, jj, mult, M, G, N, seed=0):
    """Compact grouped seed (Lera's Cholesky-clustered method, notebook §2):
      1. pivoted Cholesky of the mult-weighted packed target -> K=R*G local leaves;
      2. balanced k-means on leaves' orbital profiles -> R groups of G leaves;
      3. per group: OMP over a candidate-orbital pool -> shared M-vector basis +
         mult-weighted LSQ weights fitting the group's G leaves.
    Returns dict with U (R,M,N), W (R,M,G), H2_I (R,G)=0.
    """
    K = R * G
    d = np.sqrt(mult)
    Tw = d[:, None] * T * d[None, :]
    L = pivoted_cholesky(Tw, K)
    leaves = [unpack(L[:, k] / d, ii, jj, N) for k in range(K)]
    profile = np.array([np.sqrt((l ** 2).sum(1)) + 1e-300 for l in leaves])
    profile /= np.linalg.norm(profile, axis=1, keepdims=True)
    weight = np.array([(l ** 2).sum() for l in leaves])
    lab = balanced_kmeans(profile, R, G, weight, seed=seed)
    groups = [list(np.flatnonzero(lab == r)) for r in range(R)]
    U = np.zeros((R, M, N)); W = np.zeros((R, M, G))
    for r in range(R):
        mem = sorted(groups[r], key=lambda k: -weight[k])[:G]
        while len(mem) < G:
            mem.append(next(k for k in range(K) if k not in mem))
        gX = [leaves[k] for k in mem]
        pool = _group_pool(gX, N)
        if pool.shape[1] < M:                      # pad with random orthogonal vectors
            rng = np.random.default_rng(seed + r)
            pad = np.zeros((N, M - pool.shape[1]))
            for c in range(M - pool.shape[1]):
                v = rng.standard_normal(N); v /= np.linalg.norm(v); pad[:, c] = v
            pool = np.concatenate([pool, pad], axis=1)
        Fpool = np.stack([(pool[:, b][ii] * pool[:, b][jj]) * mult for b in range(pool.shape[1])], axis=1)
        targets = np.stack([gX[c][ii, jj] * mult for c in range(G)], axis=1)     # (P, G)
        sel, Wg = omp_select(Fpool, targets, M)
        basis = pool[:, sel] / (np.linalg.norm(pool[:, sel], axis=0, keepdims=True) + 1e-300)
        U[r] = basis.T
        W[r] = Wg
    return {"U": U, "W": W, "H2_I": np.zeros((R, G))}


def truncate_seed(U0, W0, H2_0, M, G, iters=3):
    """Stage-2b warm-start: importance-prune a known-valid factorization
    (R,B0,C0) down to (R,M,G). Copies ranked by ||W[r,:,c]||^2 + H2_I[r,c]^2;
    basis ranked by ||W[r,b,kept]||^2; alternate a few times to settle coupling.
    """
    U = np.asarray(U0, float).copy(); W = np.asarray(W0, float).copy()
    H2 = np.asarray(H2_0, float).copy()
    Rn = W.shape[0]
    for _ in range(max(1, int(iters))):
        kc = []
        for r in range(Rn):
            imp = (W[r] ** 2).sum(0) + H2[r] ** 2
            kc.append(np.sort(np.argsort(-imp)[:G]))
        W = W[:, :, kc]; H2 = H2[:, kc]
        kb = []
        for r in range(Rn):
            imp = (W[r] ** 2).sum(1)
            kb.append(np.sort(np.argsort(-imp)[:M]))
        U = U[:, kb, :]; W = W[:, kb, :]
    return {"U": U, "W": W, "H2_I": H2}


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--shapes", default="134,36 130,36 134,35 130,35 132,36 132,35 129,35 129,36",
                    help="space-separated 'M,G' pairs")
    args = ap.parse_args(argv)
    targets = []
    for tok in _require_str("shapes", args.shapes).split():
        m, g = tok.split(",")
        targets.append((int(m), int(g)))
    params = load_factorization(BASELINE)
    params.update(load_fixed_shifts())
    ref = load_reference(check_fcidump())
    N = int(ref["orbitals"])
    S = np.asarray(symmetric_from_lower(params["Hsym_lower"], N), float)
    Tfull = build_target_full(ref, S)
    ii, jj, mult = packed_pairs(N)
    T = Tfull[ii[:, None], jj[:, None], ii[None, :], jj[None, :]]   # (P,P) packed target

    # ---- VALIDATION: notebook error_2 vs authoritative dfthc_math on current best
    U0 = np.asarray(params["U"], float); W0 = np.asarray(params["W"], float)
    e_nb = notebook_error2(U0, W0, T, ii, jj, mult)
    nat0 = native_inputs(params, ref)
    mv0 = evaluate_dfthc_vectors(continuous_vectors(nat0, U0), nat0.w, nat0.W, nat0.S,
                                 nat0.beta_1, nat0.ref, energy_upper=nat0.energy_upper)
    print(f"VALIDATION current-best error_2: notebook-packed={e_nb:.4f} mHa  "
          f"dfthc_math={1e3*mv0['error_2']:.4f} mHa  (must agree ~19.9997)")
    assert abs(e_nb - 1e3 * mv0["error_2"]) < 0.5, "target reconstruction mismatch"

    os.makedirs(OUTDIR, exist_ok=True)
    U0 = np.asarray(params["U"], float); W0 = np.asarray(params["W"], float)
    H2_0 = np.asarray(params["H2_I"], float)

    def _metrics(tp):
        nat = native_inputs(tp, ref)
        return evaluate_dfthc_vectors(continuous_vectors(nat, tp["U"]), nat.w, nat.W, nat.S,
                                      nat.beta_1, nat.ref, energy_upper=nat.energy_upper)

    def _orbital_spread(tp):
        imp = (tp["W"] ** 2).sum(2)
        prof = np.array([(imp[r][:, None] * tp["U"][r] ** 2).sum(0) for r in range(R)])
        prof = np.clip(prof, 1e-300, None); prof /= prof.sum(1, keepdims=True)
        return float(np.exp(-(prof * np.log(prof)).sum(1)).mean())

    print(f"\n{'M':>4} {'G':>3} | {'chol_err2':>10} {'lamEff':>8} {'Egap':>9} {'Lam':>7} {'orb':>5}"
          f" | {'trunc_err2':>11} {'lamEff':>8} {'Egap':>9}")
    for M, G in targets:
        M = _require_int("M", M, 1, 200); G = _require_int("G", G, 1, 60)
        # --- Cholesky-clustered seed (Stage 1 primary) ---
        tc = build_compact_seed(T, ii, jj, mult, M, G, N)
        tc["Hsym_lower"] = params["Hsym_lower"]; tc["H1_I"] = params["H1_I"]
        mc = _metrics(tc)
        name_c = _require_str("out", f"chol_seed_{M}_{G}.npz")
        np.savez(os.path.join(OUTDIR, name_c), U=tc["U"], W=tc["W"], H2_I=tc["H2_I"],
                 Hsym_lower=tc["Hsym_lower"], H1_I=tc["H1_I"])
        # --- Truncation warm-start seed (Stage 2b) ---
        tt = truncate_seed(U0, W0, H2_0, M, G)
        tt["Hsym_lower"] = params["Hsym_lower"]; tt["H1_I"] = params["H1_I"]
        mt = _metrics(tt)
        name_t = _require_str("out", f"trunc_seed_{M}_{G}.npz")
        np.savez(os.path.join(OUTDIR, name_t), U=tt["U"], W=tt["W"], H2_I=tt["H2_I"],
                 Hsym_lower=tt["Hsym_lower"], H1_I=tt["H1_I"])
        print(f"{M:>4} {G:>3} | {1e3*mc['error_2']:>9.2f}m {mc['lambda_eff']:>8.2f} "
              f"{mc['E_gap']:>9.4f} {mc['Lambda']:>7.1f} {_orbital_spread(tc):>5.1f}"
              f" | {1e3*mt['error_2']:>10.2f}m {mt['lambda_eff']:>8.2f} {mt['E_gap']:>9.4f}")
    print("\nseeds written to", OUTDIR)


if __name__ == "__main__":
    main()
