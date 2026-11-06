"""Numpy-only DF-THC metric path (no JAX).

Reproduces the official verifier's continuous metrics for a factorization:
error_1, error_2, Lambda, E_SOS, E_gap, lambda_eff, plus the SpinFreeData_V1
cost model (Toffolis, Q) and the ratio vs the sample-submission reference cost.

Used to (a) validate the baseline-repro gate against the published numbers and
(b) cheaply probe lower-rank truncations for the rank cliff without training.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any

import numpy as np

REPO = "/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum"
sys.path.insert(0, os.path.join(REPO, "data", "verifiers"))

from dfthcsos.scoreinfra.reference import (  # noqa: E402
    UPPER_ENERGY,
    check_fcidump,
    load_factorization,
    load_fixed_shifts,
    load_reference,
)
from dfthcsos.scoreinfra.dfthc_math import (  # noqa: E402
    build_h1_prime,
    evaluate_dfthc_vectors,
    reconstruct_x,
    symmetric_from_lower,
)
from dfthcsos.scoreinfra.costs_prepare import SpinFreeData_V1  # noqa: E402

# The sample submission's dfthcsos cost; ratio = REFERENCE_COST / score.
REFERENCE_COST = 3355599588.3155365


@dataclass
class Native:
    w: np.ndarray      # (R, B, C) lowercase weights
    W: np.ndarray      # (R, C) identity offsets (paper coords)
    S: np.ndarray      # (N, N) fixed symmetry shift
    beta_1: float      # fixed particle-number shift
    ref: dict          # oei, tei, ecore, electrons, orbitals, h1_thc
    energy_upper: float


def native_inputs(params: dict[str, np.ndarray], ref: dict[str, Any]) -> Native:
    """Optimizer coords -> native Qaggle (w, W, S, beta_1), fixed shifts."""
    w = np.asarray(params["W"], dtype=np.float64)
    W = np.asarray(params["H2_I"], dtype=np.float64) - np.sum(w, axis=1)
    N = int(np.shape(params["U"])[-1])
    S = np.asarray(symmetric_from_lower(params["Hsym_lower"], N), dtype=np.float64)
    beta_1 = float(params["H1_I"]) - 0.5 * float(np.trace(S))
    return Native(w=w, W=W, S=S, beta_1=beta_1, ref=ref, energy_upper=UPPER_ENERGY)


def continuous_vectors(nat: Native, U: np.ndarray) -> np.ndarray:
    """u_all = [one-body eigenvectors of h1_prime ; two-body vectors U] (N+RB, N).

    The one-body rows are the exact eigenvectors of h1_prime built from the
    (continuous) two-body part, so error_1 ~ 0 in this limit. error_2 and
    lambda_eff are independent of the one-body rows.
    """
    w, W, S, beta_1, ref = nat.w, nat.W, nat.S, nat.beta_1, nat.ref
    N = int(ref["orbitals"])
    u_b_rho = np.asarray(U, dtype=np.float64)          # (R, B, N)
    X = reconstruct_x(u_b_rho, w)                       # (R, C, N, N)
    X = np.tril(X) + np.swapaxes(np.tril(X, k=-1), -1, -2)
    h1_thc = np.array(ref["oei"] - 0.5 * np.einsum("pqqs->ps", ref["tei"]))
    h1p = build_h1_prime(h1_thc, S, beta_1, ref["electrons"], W, X)
    _, evec = np.linalg.eigh(h1p)                        # columns are eigenvectors
    one_body = evec.T                                    # (N, N) rows
    two_body = u_b_rho.reshape(-1, N)                    # (R*B, N)
    return np.vstack([one_body, two_body])


def evaluate(nat: Native, U: np.ndarray) -> dict[str, float]:
    u_all = continuous_vectors(nat, U)
    out = evaluate_dfthc_vectors(
        u_all, nat.w, nat.W, nat.S, nat.beta_1, nat.ref,
        energy_upper=nat.energy_upper,
    )
    return out


def costs(R: int, B: int, C: int, N: int, brot: int = 8) -> dict[str, int]:
    """State-prep + Givens Toffolis/Q exactly as the verifier's heuristic_costs."""
    m = SpinFreeData_V1(R=R, B=B, C=C, N=N, chi=10, beta=brot)  # defaults, as verifier
    oq = m.outer_state_prep_qubit_cost()
    iq = m.inner_state_prep_qubit_cost()
    op, ot = int(oq["persistent"]), int(oq["temporary"])
    ip, it = int(iq["persistent"]), int(iq["temporary"])
    toffoli = int(m.outer_state_prep()) + int(m.inner_state_prep()) + int(m.givens_rotations())
    qubits = (op + ip) + max(ot, it)
    return {
        "outer_toffoli": int(m.outer_state_prep()),
        "inner_toffoli": int(m.inner_state_prep()),
        "givens_toffoli": int(m.givens_rotations()),
        "toffolis": toffoli,
        "persistent": op + ip,
        "temporary": max(ot, it),
        "qubits": qubits,
    }


def ratio(score: float) -> float:
    return REFERENCE_COST / score


def score_from(lambda_eff: float, toffolis: int, qubits: int) -> float:
    return lambda_eff * toffolis * qubits


if __name__ == "__main__":
    # Validate on the current best submission.
    sub = os.path.join(REPO, "work/frontier_scan/mwa2_unpacked/dfthcsos/submission.npz")
    params = load_factorization(sub)
    params.update(load_fixed_shifts())
    ref = load_reference(check_fcidump())
    nat = native_inputs(params, ref)
    R, B, C = params["W"].shape
    N = int(ref["orbitals"])
    m = evaluate(nat, params["U"])
    print(f"shape R,B,C,N = {R},{B},{C},{N}")
    print(f"error_1   = {1e3*m['error_1']:.4f} mHa")
    print(f"error_2   = {1e3*m['error_2']:.4f} mHa")
    print(f"Lambda    = {m['Lambda']:.4f} Ha")
    print(f"E_SOS     = {m['E_SOS']:.6f} Ha")
    print(f"E_gap     = {m['E_gap']:.7f} Ha")
    print(f"lambda_eff= {m['lambda_eff']:.4f} Ha")
    print(f"gap_in_domain = {m['gap_in_domain']}")
