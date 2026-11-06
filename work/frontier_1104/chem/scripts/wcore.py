"""Fixed-word weight engine for DF-THC: objective/gradients in the (R*B)-dim leaf space.

Own implementation. All metrics are cross-checked against the official dfthc_math.
Variables: w (R,B,C) lowercase weights, wB (R,C) = W + sum_b w (stored as H2_I).
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import numpy as np

REPO = '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum'
sys.path.insert(0, REPO + '/data/verifiers')
from dfthcsos.scoreinfra import dfthc_math as dm  # noqa: E402
from dfthcsos.scoreinfra.reference import UPPER_ENERGY, check_fcidump, load_fixed_shifts, load_reference  # noqa: E402
from dfthcsos import verify as vf  # noqa: E402

E_GAP_FLOOR = vf.E_GAP_FLOOR
CACHE = '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/work/frontier_1104/chem/runs/_tgt.npz'


def load_ref() -> dict:
    return load_reference(check_fcidump())


def shifts() -> tuple[np.ndarray, float]:
    p = load_fixed_shifts()
    S = np.asarray(dm.symmetric_from_lower(p['Hsym_lower'], 76), dtype=np.float64)
    beta_1 = float(p['H1_I']) - 0.5 * float(np.trace(S))
    return S, beta_1


def packed_target(ref: dict, S: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Packed tei' = tei + (S x I + I x S)/2 with sqrt(2) off-diagonal metric."""
    n = 76
    tei = ref['tei']
    rows, cols = np.tril_indices(n)
    mult = np.where(rows == cols, 1.0, np.sqrt(2.0))
    T = tei[rows[:, None], cols[:, None], rows[None, :], cols[None, :]].copy()
    d = np.arange(n)
    Sp = S[rows, cols]
    dg = (rows == cols).astype(float)
    T += 0.5 * (Sp[:, None] * dg[None, :] + dg[:, None] * Sp[None, :])
    T = T * mult[:, None] * mult[None, :]
    return T, rows, cols


@dataclass
class Eng:
    R: int
    B: int
    C: int
    G: np.ndarray       # (RB,RB) Hadamard-square Gram
    A: np.ndarray       # (RB,RB) projected target
    T2: float           # ||T||^2
    u2: np.ndarray      # (R,B,N) two-body vectors
    V1: np.ndarray      # (N,N) one-body rows
    h1base: np.ndarray  # H1_THC - eta/2 S + beta_1 I
    ecore: float
    eta: int
    beta1: float
    E_up: float

    def h1prime(self, w: np.ndarray, wB: np.ndarray) -> np.ndarray:
        W = wB - w.sum(axis=1)
        # coefficient of u_b u_b^T: sum_c W_rc w_rbc
        coef = np.einsum('rc,rbc->rb', W, w)
        h = self.h1base - np.einsum('rbp,rb,rbq->pq', self.u2, coef, self.u2, optimize=True)
        return 0.5 * (h + h.T)

    def e2sq(self, w: np.ndarray) -> tuple[float, np.ndarray]:
        """error_2^2 and gradient wrt w."""
        R, B, C = self.R, self.B, self.C
        Wb = np.zeros((R * B, R * C))
        for r in range(R):
            Wb[r * B:(r + 1) * B, r * C:(r + 1) * C] = w[r]
        GW = self.G @ Wb
        M = Wb.T @ GW
        AW = self.A @ Wb
        val = float(np.sum(M * M) - 2.0 * np.sum(Wb * AW) + self.T2)
        grad = 4.0 * (GW @ M - AW)
        g = np.stack([grad[r * B:(r + 1) * B, r * C:(r + 1) * C] for r in range(R)])
        return val, g

    def metrics(self, w: np.ndarray, wB: np.ndarray) -> dict:
        h = self.h1prime(w, wB)
        ev, ec = np.linalg.eigh(h)
        lamh1 = float(np.abs(ev).sum())
        W = wB - w.sum(axis=1)
        lamh2 = float(0.25 * np.sum((np.abs(w).sum(axis=1) + np.abs(wB)) ** 2))
        Lam = lamh1 + lamh2
        Egap = self.E_up - (self.ecore - self.eta * self.beta1 - (lamh1 - ev.sum()) - 0.5 * np.sum(W ** 2))
        e2, _ = self.e2sq(w)
        e1, _ = self.e1sq(h, ev, ec)
        return dict(e2=float(np.sqrt(max(e2, 0.0))), e1=float(np.sqrt(e1)), Lam=Lam, Egap=float(Egap),
                    lam_eff=float(np.sqrt(Egap * (2 * Lam - Egap))), lamh1=lamh1, lamh2=lamh2)

    def e1sq(self, h: np.ndarray, ev: np.ndarray, ec: np.ndarray) -> tuple[float, np.ndarray]:
        """error_1^2 and gradient wrt h1_prime (assignment held fixed)."""
        from scipy.optimize import linear_sum_assignment
        ov = np.abs(self.V1 @ ec)
        qi, ii = linear_sum_assignment(-ov)
        lam = np.empty_like(ev)
        lam[qi] = ev[ii]
        Rm = (self.V1.T * lam) @ self.V1 - h
        val = float(np.sum(Rm * Rm))
        d = np.einsum('jp,pq,jq->j', self.V1, Rm, self.V1, optimize=True)  # v_j^T R v_j
        dmat = np.empty_like(d)
        dmat[ii] = d[qi]                                                    # per eigvec of h
        grad = 2.0 * ((ec * dmat) @ ec.T - Rm)
        return val, 0.5 * (grad + grad.T)


def load_engine(npz_path: str, C: int | None = None, ref: dict | None = None) -> tuple[Eng, np.ndarray, np.ndarray]:
    """Return engine + starting (w, wB) from a submission.npz."""
    d = np.load(npz_path, allow_pickle=False)
    words, edges, brot = d['angle_words'], d['tree_edges'], int(d['brot'])
    w, wB = np.array(d['W'], dtype=np.float64), np.array(d['H2_I'], dtype=np.float64)
    R, B, Cc = w.shape
    u = dm.reconstruct_u_vectors(words / (1 << (brot - 1)), edges)
    u = u / np.linalg.norm(u, axis=1, keepdims=True)
    V1, u2 = dm.split_u_vectors(u, w)
    ref = ref or load_ref()
    S, beta1 = shifts()
    T, rows, cols = packed_target(ref, S)
    mult = np.where(rows == cols, 1.0, np.sqrt(2.0))
    Ub = u2.reshape(R * B, 76)
    Phi = Ub[:, rows] * Ub[:, cols] * mult
    G = (Ub @ Ub.T) ** 2
    A = Phi @ (T @ Phi.T)
    T2 = float(np.sum(T * T))
    h1thc = ref['oei'] - 0.5 * np.einsum('prrq->pq', ref['tei'])
    h1base = h1thc - 0.5 * ref['electrons'] * S + beta1 * np.eye(76)
    eng = Eng(R, B, Cc, G, A, T2, u2, V1, h1base, float(ref['ecore']), int(ref['electrons']), beta1, UPPER_ENERGY)
    return eng, w, wB


def official_metrics(npz_path: str, w: np.ndarray, wB: np.ndarray, ref: dict) -> dict:
    d = np.load(npz_path, allow_pickle=False)
    S, beta1 = shifts()
    W = wB - w.sum(axis=1)
    return dm.evaluate_dfthc_angle_words(d['angle_words'], w, W, S, beta1, ref, brot=int(d['brot']),
                                         tree_edges=d['tree_edges'], energy_upper=UPPER_ENERGY)
