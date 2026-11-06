#!/usr/bin/env python3
"""Long-inner AL continuation at near-fixed multipliers, from a checkpoint (smooth y updates, rho small)."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
from scipy.optimize import minimize

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wcore  # noqa: E402
import refit  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('npz')
    ap.add_argument('start')
    ap.add_argument('outdir')
    ap.add_argument('--rounds', type=int, default=30)
    ap.add_argument('--inner', type=int, default=1500)
    ap.add_argument('--rho', type=float, default=0.004)
    ap.add_argument('--y2', type=float, default=0.0052)
    ap.add_argument('--y1', type=float, default=0.0)
    ap.add_argument('--yg', type=float, default=0.0058)
    ap.add_argument('--t2', type=float, default=19.9999)
    ap.add_argument('--t1', type=float, default=19.9999)
    ap.add_argument('--resume', action='store_true')
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    ref = wcore.load_ref()
    eng, w, wB = wcore.load_engine(a.npz, ref=ref)
    d = np.load(a.start)
    w, wB = d['w'], d['wB']
    al = refit.AL(eng, a.t2 * 1e-3, a.t1 * 1e-3, wcore.E_GAP_FLOOR + 2e-7)
    al.rho, al.y2, al.y1, al.yg = a.rho, a.y2, a.y1, a.yg
    ck = os.path.join(a.outdir, 'ck.npz')
    if a.resume and os.path.exists(ck):
        d = np.load(ck)
        w, wB, al.y2, al.y1, al.yg, al.rho = d['w'], d['wB'], float(d['y2']), float(d['y1']), float(d['yg']), float(d['rho'])
    R, B, C = w.shape
    n = R * B * C
    x = np.concatenate([w.ravel(), wB.ravel()])
    best = None
    bp = os.path.join(a.outdir, 'best.npz')
    if os.path.exists(bp) and a.resume:
        best = float(np.load(bp)['lam_eff'])
    print('start', json.dumps(eng.metrics(w, wB)), flush=True)
    for rd in range(a.rounds):
        t0 = time.time()
        signs, rel, nz = refit.choose_signs(al, x)
        bnd = refit.bounds_from_signs(*signs)
        res = minimize(lambda z: al.fg(z, signs), np.clip(x, bnd[:, 0], bnd[:, 1]), jac=True, method='L-BFGS-B', bounds=bnd,
                       options=dict(maxiter=a.inner, maxcor=60, ftol=1e-16, gtol=1e-11, maxfun=a.inner + 100, maxls=30))
        x = res.x
        p, cs = al.update(x)
        wc, bc = x[:n].reshape(R, B, C), x[n:].reshape(R, C)
        m = eng.metrics(wc, bc)
        feas = m['e2'] <= 0.02 and m['e1'] <= 0.02 and m['Egap'] > wcore.E_GAP_FLOOR
        print(f"rd {rd} lam={m['lam_eff']:.7f} Lam={m['Lam']:.5f} Eg={m['Egap']:.7f} e2={m['e2']*1e3:.5f} e1={m['e1']*1e3:.5f} "
              f"y=({al.y2:.5f},{al.y1:.5f},{al.yg:.5f}) zeros={int(np.sum(wc==0))} rel={rel} nit={res.nit} {time.time()-t0:.0f}s feas={feas} {res.message}", flush=True)
        if feas and (best is None or m['lam_eff'] < best):
            best = m['lam_eff']
            np.savez(bp, w=wc, wB=bc, **{k: np.float64(v) for k, v in m.items()})
        np.savez(ck, w=wc, wB=bc, y2=al.y2, y1=al.y1, yg=al.yg, rho=al.rho)
    print('best', best, flush=True)


if __name__ == '__main__':
    main()
