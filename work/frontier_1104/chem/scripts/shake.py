#!/usr/bin/env python3
"""Basin hopping for the weight refit: exact random column-gauge rotations (metrics e1,e2,E_gap unchanged, only Lambda moves),
then long-inner AL rounds; keep the best feasible."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
from scipy.optimize import minimize

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refit  # noqa: E402
import wcore  # noqa: E402


def rotate(w, wB, rng, pairs, amp):
    R, B, C = w.shape
    w, wB = w.copy(), wB.copy()
    W = wB - w.sum(axis=1)
    for r in range(R):
        for _ in range(pairs):
            i, j = rng.choice(C, 2, replace=False)
            t = rng.normal() * amp
            c, s = np.cos(t), np.sin(t)
            wi, wj = w[r, :, i].copy(), w[r, :, j].copy()
            w[r, :, i], w[r, :, j] = c * wi + s * wj, -s * wi + c * wj
            Wi, Wj = W[r, i], W[r, j]
            W[r, i], W[r, j] = c * Wi + s * Wj, -s * Wi + c * Wj
    return w, W + w.sum(axis=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('npz')
    ap.add_argument('start')
    ap.add_argument('out')
    ap.add_argument('--hops', type=int, default=20)
    ap.add_argument('--rounds', type=int, default=6)
    ap.add_argument('--inner', type=int, default=1000)
    ap.add_argument('--pairs', type=int, default=60)
    ap.add_argument('--amp', type=float, default=0.03)
    ap.add_argument('--seed', type=int, default=0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    ref = wcore.load_ref()
    eng, _, _ = wcore.load_engine(a.npz, ref=ref)
    d = np.load(a.start)
    w, wB = d['w'], d['wB']
    R, B, C = w.shape
    n = R * B * C
    rng = np.random.default_rng(a.seed)
    best = eng.metrics(w, wB)['lam_eff']
    bw, bB = w.copy(), wB.copy()
    print('start', best, flush=True)
    for hop in range(a.hops):
        t0 = time.time()
        w1, b1 = rotate(bw, bB, rng, a.pairs, a.amp)
        al = refit.AL(eng, 19.9999e-3, 19.9999e-3, wcore.E_GAP_FLOOR + 2e-7)
        al.rho, al.y2, al.y1, al.yg = 0.003, 0.0036, 0.0, 0.00578
        x = np.concatenate([w1.ravel(), b1.ravel()])
        hopbest = None
        for rd in range(a.rounds):
            signs, rel, nz = refit.choose_signs(al, x)
            bnd = refit.bounds_from_signs(*signs)
            res = minimize(lambda z: al.fg(z, signs), np.clip(x, bnd[:, 0], bnd[:, 1]), jac=True, method='L-BFGS-B', bounds=bnd,
                           options=dict(maxiter=a.inner, maxcor=60, ftol=1e-16, gtol=1e-11, maxfun=a.inner + 100, maxls=30))
            x = res.x
            al.update(x)
            wc, bc = x[:n].reshape(R, B, C), x[n:].reshape(R, C)
            m = eng.metrics(wc, bc)
            feas = m['e2'] <= 0.02 and m['e1'] <= 0.02 and m['Egap'] > wcore.E_GAP_FLOOR
            if feas and (hopbest is None or m['lam_eff'] < hopbest):
                hopbest = m['lam_eff']
                if hopbest < best:
                    best = hopbest
                    bw, bB = wc.copy(), bc.copy()
                    np.savez(os.path.join(a.out, 'best.npz'), w=wc, wB=bc, **{k: np.float64(v) for k, v in m.items()})
        print(f'hop {hop} hopbest {hopbest} best {best} last lam {m["lam_eff"]:.6f} e2 {m["e2"]*1e3:.5f} e1 {m["e1"]*1e3:.5f} Eg {m["Egap"]:.7f} {time.time()-t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
