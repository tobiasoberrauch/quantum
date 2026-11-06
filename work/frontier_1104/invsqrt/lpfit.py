#!/usr/bin/env python3
"""Exact-column extraction and minimax angle refit for fine rotations.

err(x) = A(x) + sum_j a_j b_j(x), where a_j are rotation angles and b_j the (outcome
independent) control columns. Maximises c s.t. |err(x)| <= tol(x) - c over the full
domain by constraint generation with HiGHS. All values in 2^-64 turn units.
"""
from __future__ import annotations

import math
import time
from fractions import Fraction

import numpy as np
from scipy.optimize import linprog

import bsim


def extract(ops: list[bsim.Op], xs: np.ndarray, seed: int = 5, nq: int = 62):
    """Runs the circuit; returns (A, B, units_list, op_index_list, state). A excludes fine rotations."""
    cols: list[np.ndarray] = []
    meta: list[bsim.Op] = []

    def rotcol(op: bsim.Op, mb: np.ndarray) -> None:
        cols.append(mb.copy())
        meta.append(op)

    s = bsim.run(ops, xs, seed=seed, rotcol=rotcol, nq=nq)
    tgt, tol = bsim.reference(xs)
    a0 = (bsim.phase_units(s) - tgt).view(np.int64)
    return a0, np.array(cols, dtype=np.uint8), meta, s, tol


def fit(a0: np.ndarray, b: np.ndarray, tol: np.ndarray, angles: np.ndarray | None = None,
        tol_gap: float = 1.0, iters: int = 60, verbose: bool = False) -> tuple[np.ndarray, float]:
    """Solve max c near the given angles. a0 int64 residual (mod 2^64), b (n_rot, N) uint8.

    Variables are deltas from `angles`, scaled by SCALE, so HiGHS sees small numbers.
    Returns (angles in units of 2^-64 turns as float, c).
    """
    if angles is None:
        raise ValueError('initial angles required (seed from the current circuit)')
    SCALE = 2.0**26
    n_rot, n = b.shape
    bt = b.T  # (N, n_rot)
    a_int = np.rint(angles).astype(np.int64)
    r0 = (a0 + (bt.astype(np.int64) @ a_int)).astype(np.int64)  # exact mod 2^64, signed
    r0f = r0.astype(np.float64)
    tolf = tol.astype(np.float64)
    pool: set[int] = set()
    d = np.zeros(n_rot)
    btf = bt.astype(np.float32)

    def margin(dd: np.ndarray) -> np.ndarray:
        return tolf - np.abs(r0f + (btf @ dd.astype(np.float32)).astype(np.float64) * SCALE)

    best_d, best_c = d.copy(), float(margin(d).min())
    for it in range(iters):
        m = margin(d)
        cur = float(m.min())
        if cur > best_c:
            best_d, best_c = d.copy(), cur
        idx = np.argpartition(m, 400)[:400]
        new = [int(i) for i in idx if int(i) not in pool]
        pool.update(new)
        ids = np.fromiter(pool, dtype=np.int64)
        rows = bt[ids].astype(np.float64)
        one = np.ones((len(ids), 1))
        A_ub = np.vstack([np.hstack([rows, one]), np.hstack([-rows, one])])
        b_ub = np.concatenate([(tolf[ids] - r0f[ids]) / SCALE, (tolf[ids] + r0f[ids]) / SCALE])
        cost = np.zeros(n_rot + 1)
        cost[-1] = -1
        res = linprog(cost, A_ub=A_ub, b_ub=b_ub, bounds=[(None, None)] * (n_rot + 1), method='highs-ds')
        if not res.success:
            raise RuntimeError(res.message)
        d, c_lp = res.x[:-1], res.x[-1] * SCALE
        ok = float(margin(d).min())
        if verbose:
            print(f'  iter {it} margin {cur:.1f} lp {c_lp:.1f} eval {ok:.1f} pool {len(pool)}', flush=True)
        if ok > best_c:
            best_d, best_c = d.copy(), ok
        if c_lp - best_c <= tol_gap * 64:
            break
    return a_int.astype(np.float64) + best_d * SCALE, best_c


def angles_units(ops_meta: list[bsim.Op]) -> np.ndarray:
    return np.array([float(op.angle) * 2**63 for op in ops_meta])


def units_to_decimal(u: float) -> str:
    """Rotation angle in half turns as an exact finite decimal (dyadic rational with 2^-127 grid)."""
    q = int(round(u)) * (1 << 40)  # u is in units of 2^-63 half turns; put on a 2^-103 grid
    fr = Fraction(q, 1 << 103)
    num, den = fr.numerator, fr.denominator
    # den is a power of 2, so the decimal terminates.
    k = den.bit_length() - 1
    val = num * 5**k
    s = str(val).rjust(k + 1, '0')
    return (s[:-k] + '.' + s[-k:]).rstrip('0').rstrip('.') if k else s


def cost_line(tof: float, t: float, rot: float, margin: float) -> dict:
    return bsim.cost(62, tof, t, rot, margin)
