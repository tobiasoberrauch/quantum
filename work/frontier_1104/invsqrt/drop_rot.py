#!/usr/bin/env python3
"""Refit base; then for each fine rotation drop it and refit; report break-even."""
from __future__ import annotations

import json
import sys

import numpy as np

import bsim
import lpfit


def main() -> None:
    ops, _ = bsim.parse_kmx(sys.argv[1])
    xs = bsim.domain()
    a0, b, meta, s, tol = lpfit.extract(ops, xs)
    ang = lpfit.angles_units(meta)
    print('fine rotations', len(meta), 'tof', s.tof / s.n, 't', s.t / s.n, 'rot', s.rot / s.n, 'lines', [m.line for m in meta][:5])
    print('conditional fine', [m.line for m in meta if m.cond >= 0][:10])
    aa, c = lpfit.fit(a0, b, tol, ang, verbose=False)
    base = bsim.cost(62, s.tof / s.n, s.t / s.n, s.rot / s.n, c)
    print('LP c', c, base)
    print('shipped margin', float((tol.astype(float) - np.abs(a0.astype(float) + 0)).min()))
    rows = []
    for j in range(len(meta)):
        if meta[j].angle > 1e-6:
            continue
        keep = [k for k in range(len(meta)) if k != j]
        # removing the rotation leaves the rest of a0; the dropped control no longer contributes
        ax, cx = lpfit.fit(a0, b[keep], tol, ang[keep], verbose=False, iters=25)
        cost = bsim.cost(62, s.tof / s.n, s.t / s.n, s.rot / s.n - 1, max(cx, 1))
        rows.append(dict(j=j, line=meta[j].line, angle=float(meta[j].angle), c=cx, f=c / cx if cx > 0 else None,
                         dC=cost['C'] - base['C']))
        print(rows[-1], flush=True)
    json.dump(rows, open(bsim.LANE + '/runs/drop_rot.json', 'w'), indent=1)


if __name__ == '__main__':
    main()
