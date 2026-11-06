"""Choose don't-care cells (y=76, z>=4) so row 76 lies in the span of the other rows in the selected planes."""
from __future__ import annotations

import numpy as np

import planner as P


def fill_padding(X30, Inv, planes_q, rng=None):
    """Return copy of X30 with row 75, z-index >=3 chosen; list of planes actually satisfied."""
    Y, Z, O = X30.shape
    X = X30.copy()
    X[75, 3:, :] = False
    nvar = 12 * O
    eqs = []
    tags = []
    for t in planes_q:
        coord = Inv[:, 3 * t:3 * t + 3].T.astype(bool)
        rows = P.plane_rows(X[:75], coord)
        ann = P.nullspace(rows, 3 * O)
        for R in ann:
            lhs = 0
            rhs = 0
            for i in range(3):
                Ri = (R >> (i * O)) & ((1 << O) - 1)
                if not Ri:
                    continue
                for z in range(15):
                    if coord[i, z]:
                        if z < 3:
                            for o in range(O):
                                if (Ri >> o) & 1 and X[75, z, o]:
                                    rhs ^= 1
                        else:
                            lhs ^= Ri << ((z - 3) * O)
            eqs.append((lhs, rhs, t))
    # solve incrementally; a plane whose equations conflict is dropped entirely
    def solve(selected):
        piv = {}
        for lhs, rhs, t in eqs:
            if t not in selected:
                continue
            v = lhs | (rhs << nvar)
            while v & ((1 << nvar) - 1):
                h = (v & ((1 << nvar) - 1)).bit_length() - 1
                p = piv.get(h)
                if p is None:
                    piv[h] = v
                    break
                v ^= p
            else:
                if v >> nvar:
                    return None
        x = 0
        for h in sorted(piv):
            v = piv[h]
            bit = (v >> nvar) & 1
            low = v & ((1 << nvar) - 1) & ~(1 << h)
            bit ^= bin(low & x).count('1') & 1
            if bit:
                x |= 1 << h
        return x

    sel = list(planes_q)
    x = solve(set(sel))
    while x is None and sel:
        sel = sel[:-1]
        x = solve(set(sel))
    if x is None:
        return X, []
    for z in range(12):
        for o in range(O):
            X[75, 3 + z, o] = bool((x >> (z * O + o)) & 1)
    return X, sel
