#!/usr/bin/env python3
"""Fixed-word weight refit: min lambda_eff s.t. e1,e2<=target, E_gap>=floor.

Augmented Lagrangian; inner solver L-BFGS-B restricted to the current sign orthant (zeros released
by pseudo-gradient between rounds), plus exact Givens column-gauge sweeps. Own implementation.
Usage: refit.py <npz> <outdir> [--rounds N] [--inner K] [--t2 mHa] [--t1 mHa] [--w0 file.npz]
"""
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


def smooth_parts(eng, w, wB, want_grad=True):
    """Return metrics and per-term gradients wrt (w, wB)."""
    R, B, C = w.shape
    h = eng.h1prime(w, wB)
    ev, ec = np.linalg.eigh(h)
    sgn = np.sign(ev)
    W = wB - w.sum(axis=1)
    lam1 = float(np.abs(ev).sum())
    L = np.abs(w).sum(axis=1) + np.abs(wB)
    lam2 = float(0.25 * np.sum(L ** 2))
    Lam = lam1 + lam2
    Eg = eng.E_up - (eng.ecore - eng.eta * eng.beta1 - (lam1 - ev.sum()) - 0.5 * np.sum(W ** 2))
    e2s, ge2 = eng.e2sq(w)
    e1s, Me1 = eng.e1sq(h, ev, ec)
    out = dict(Lam=Lam, Eg=float(Eg), e2s=e2s, e1s=e1s, lam1=lam1, lam2=lam2, L=L, W=W)
    if not want_grad:
        return out
    Ps = (ec * sgn) @ ec.T

    def from_h(M):
        u = eng.u2
        m = np.einsum('rbp,pq,rbq->rb', u, M, u, optimize=True)
        s = np.einsum('rb,rbc->rc', m, w)
        gw = -(m[:, :, None] * W[:, None, :]) + s[:, None, :]
        gB = -s
        return gw, gB

    gw_s, gB_s = from_h(Ps)                    # d lam1
    gw_e, gB_e = from_h(Ps - np.eye(76))       # d (lam1 - tr)
    # E_gap gradient
    gEw = gw_e - W[:, None, :]
    gEB = gB_e + W
    # Lambda gradient (smooth part in-orthant handled via signs)
    sw, sB = np.sign(w), np.sign(wB)
    gLw = gw_s + 0.5 * L[:, None, :] * sw
    gLB = gB_s + 0.5 * L * sB
    g1w, g1B = from_h(Me1)
    out.update(gEw=gEw, gEB=gEB, gLw=gLw, gLB=gLB, ge2=ge2, g1w=g1w, g1B=g1B, gw_s=gw_s, gB_s=gB_s, gw_e=gw_e)
    return out


class AL:
    def __init__(self, eng, t2, t1, floor):
        self.eng, self.t2, self.t1, self.floor = eng, t2, t1, floor
        self.y2 = 0.0
        self.y1 = 0.0
        self.yg = 0.0
        self.rho = 1.0
        self.shape = None

    def cons(self, p):
        c2 = (p['e2s'] - self.t2 ** 2) * 1e6  # mHa^2
        c1 = (p['e1s'] - self.t1 ** 2) * 1e6
        cg = (self.floor - p['Eg']) * 1e3     # mHa
        return c2, c1, cg

    def fg(self, x, signs):
        eng = self.eng
        R, B, C = eng.R, eng.B, eng.C
        n = R * B * C
        if not np.all(np.isfinite(x)) or np.abs(x).max() > 5.0:
            return 1e9, np.zeros_like(x)
        w = x[:n].reshape(R, B, C)
        wB = x[n:].reshape(R, C)
        p = smooth_parts_orth(eng, w, wB, signs)
        rad = p['Eg'] * (2 * p['Lam'] - p['Eg'])
        if not (rad > 0):
            return 1e9, np.zeros_like(x)
        lam = np.sqrt(rad)
        c2, c1, cg = self.cons(p)
        val = lam
        a = (p['Lam'] - p['Eg']) / lam
        b = p['Eg'] / lam
        gw = a * p['gEw'] + b * p['gLw']
        gB = a * p['gEB'] + b * p['gLB']
        rho = self.rho
        m2 = max(0.0, self.y2 + rho * c2)
        val += (m2 ** 2 - self.y2 ** 2) / (2 * rho)
        gw = gw + m2 * p['ge2'] * 1e6
        m1 = max(0.0, self.y1 + rho * c1)
        val += (m1 ** 2 - self.y1 ** 2) / (2 * rho)
        gw = gw + m1 * p['g1w'] * 1e6
        gB = gB + m1 * p['g1B'] * 1e6
        mg = max(0.0, self.yg + rho * cg)
        val += (mg ** 2 - self.yg ** 2) / (2 * rho)
        gw = gw - mg * p['gEw'] * 1e3
        gB = gB - mg * p['gEB'] * 1e3
        return val, np.concatenate([gw.ravel(), gB.ravel()])

    def update(self, x):
        eng = self.eng
        R, B, C = eng.R, eng.B, eng.C
        n = R * B * C
        p = smooth_parts(eng, x[:n].reshape(R, B, C), x[n:].reshape(R, C), want_grad=False)
        c2, c1, cg = self.cons(p)
        self.y2 = max(0.0, self.y2 + self.rho * c2)
        self.y1 = max(0.0, self.y1 + self.rho * c1)
        self.yg = max(0.0, self.yg + self.rho * cg)
        return p, (c2, c1, cg)


def smooth_parts_orth(eng, w, wB, signs):
    """As smooth_parts, but L1 signs come from the fixed orthant, so zeros stay differentiable."""
    p = smooth_parts(eng, w, wB)
    sw, sB = signs
    L = p['L']
    p['gLw'] = p['gw_s'] + 0.5 * L[:, None, :] * sw
    p['gLB'] = p['gB_s'] + 0.5 * L * sB
    return p


def choose_signs(al, x):
    """Sign pattern for this round: keep nonzero signs; release zeros where the pseudo-gradient says so."""
    eng = al.eng
    R, B, C = eng.R, eng.B, eng.C
    n = R * B * C
    w, wB = x[:n].reshape(R, B, C), x[n:].reshape(R, C)
    sw0, sB0 = np.sign(w), np.sign(wB)
    val, g = al.fg(x, (sw0, sB0))  # L1 term zero at zero coordinate, so g is smooth part there
    gw = g[:n].reshape(R, B, C)
    L = np.abs(w).sum(axis=1) + np.abs(wB)
    kink = 0.5 * L[:, None, :] * (p_b(al, x))
    sw = sw0.copy()
    z = sw0 == 0
    sw[z & (gw + kink < 0)] = 1.0
    sw[z & (gw - kink > 0)] = -1.0
    released = int(np.sum(sw != sw0))
    return (sw, sB0), released, int(z.sum())


def p_b(al, x):
    eng = al.eng
    R, B, C = eng.R, eng.B, eng.C
    n = R * B * C
    p = smooth_parts(eng, x[:n].reshape(R, B, C), x[n:].reshape(R, C), want_grad=False)
    return (p['Eg'] / np.sqrt(p['Eg'] * (2 * p['Lam'] - p['Eg'])))


def bounds_from_signs(sw, sB):
    lo = np.where(sw > 0, 0.0, np.where(sw < 0, -np.inf, 0.0)).ravel()
    hi = np.where(sw < 0, 0.0, np.where(sw > 0, np.inf, 0.0)).ravel()
    loB = np.where(sB > 0, 0.0, np.where(sB < 0, -np.inf, 0.0)).ravel()
    hiB = np.where(sB < 0, 0.0, np.where(sB > 0, np.inf, 0.0)).ravel()
    return np.stack([np.concatenate([lo, loB]), np.concatenate([hi, hiB])], axis=1)


def gauge_sweep(w, wB, seed=0, npairs=None):
    """Exact column Givens gauge: per block rotate (w_c1, W_c1),(w_c2, W_c2). Minimizes Lambda_2 only."""
    rng = np.random.default_rng(seed)
    R, B, C = w.shape
    w = w.copy()
    wB = wB.copy()
    W = wB - w.sum(axis=1)
    thetas = np.concatenate([np.linspace(-0.5, 0.5, 65), np.array([0.0])]) * 0.25
    tot = 0.0
    n = 0
    for r in range(R):
        pairs = [(i, j) for i in range(C) for j in range(i + 1, C)]
        rng.shuffle(pairs)
        for (i, j) in pairs[:npairs]:
            a, b = w[r, :, i], w[r, :, j]
            Wa, Wb = W[r, i], W[r, j]
            cs, sn = np.cos(thetas), np.sin(thetas)
            na = cs[:, None] * a + sn[:, None] * b
            nb = -sn[:, None] * a + cs[:, None] * b
            nWa = cs * Wa + sn * Wb
            nWb = -sn * Wa + cs * Wb
            La = np.abs(na).sum(1) + np.abs(nWa + na.sum(1))
            Lb = np.abs(nb).sum(1) + np.abs(nWb + nb.sum(1))
            f = 0.25 * (La ** 2 + Lb ** 2)
            f0 = f[-1]
            k = int(np.argmin(f[:-1]))
            if f[k] < f0 - 1e-10:
                # refine by local golden
                lo, hi = thetas[max(k - 1, 0)], thetas[min(k + 1, 64)]
                gr = (np.sqrt(5) - 1) / 2

                def fv(t):
                    c, s = np.cos(t), np.sin(t)
                    A, Bb = c * a + s * b, -s * a + c * b
                    return 0.25 * ((np.abs(A).sum() + abs(c * Wa + s * Wb + A.sum())) ** 2 +
                                   (np.abs(Bb).sum() + abs(-s * Wa + c * Wb + Bb.sum())) ** 2)
                for _ in range(25):
                    t1, t2 = hi - gr * (hi - lo), lo + gr * (hi - lo)
                    if fv(t1) < fv(t2):
                        hi = t2
                    else:
                        lo = t1
                t = 0.5 * (lo + hi)
                if fv(t) < f0 - 1e-12:
                    tot += f0 - fv(t)
                    n += 1
                    c, s = np.cos(t), np.sin(t)
                    w[r, :, i], w[r, :, j] = c * a + s * b, -s * a + c * b
                    W[r, i], W[r, j] = c * Wa + s * Wb, -s * Wa + c * Wb
    return w, W + w.sum(axis=1), tot, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('npz')
    ap.add_argument('outdir')
    ap.add_argument('--rounds', type=int, default=40)
    ap.add_argument('--inner', type=int, default=400)
    ap.add_argument('--t2', type=float, default=19.99990)
    ap.add_argument('--t1', type=float, default=19.99990)
    ap.add_argument('--gap-margin', type=float, default=2e-7)
    ap.add_argument('--rho', type=float, default=0.05)
    ap.add_argument('--gauge-every', type=int, default=5)
    ap.add_argument('--resume', action='store_true')
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    ref = wcore.load_ref()
    eng, w, wB = wcore.load_engine(a.npz, ref=ref)
    ck = os.path.join(a.outdir, 'ck.npz')
    al = AL(eng, a.t2 * 1e-3, a.t1 * 1e-3, wcore.E_GAP_FLOOR + a.gap_margin)
    al.rho = a.rho
    if a.resume and os.path.exists(ck):
        d = np.load(ck)
        w, wB = d['w'], d['wB']
        al.y2, al.y1, al.yg, al.rho = float(d['y2']), float(d['y1']), float(d['yg']), float(d['rho'])
    R, B, C = w.shape
    n = R * B * C
    x = np.concatenate([w.ravel(), wB.ravel()])
    best = None
    m0 = eng.metrics(w, wB)
    print('start', json.dumps(m0), flush=True)
    for rd in range(a.rounds):
        t0 = time.time()
        if a.gauge_every and rd % a.gauge_every == 0:
            ww, bb, tot, cnt = gauge_sweep(x[:n].reshape(R, B, C), x[n:].reshape(R, C), seed=rd)
            print(f'gauge round {rd}: dLam2={tot:.6f} moved={cnt}', flush=True)
            x = np.concatenate([ww.ravel(), bb.ravel()])
        signs, rel, nz = choose_signs(al, x)
        bnd = bounds_from_signs(*signs)
        res = minimize(lambda z: al.fg(z, signs), np.clip(x, bnd[:, 0], bnd[:, 1]), jac=True, method='L-BFGS-B', bounds=bnd,
                       options=dict(maxiter=a.inner, maxcor=40, ftol=1e-15, gtol=1e-10, maxfun=a.inner + 50, maxls=30))
        x = res.x
        p, cs = al.update(x)
        wc, bc = x[:n].reshape(R, B, C), x[n:].reshape(R, C)
        m = eng.metrics(wc, bc)
        feas = m['e2'] <= 0.02 and m['e1'] <= 0.02 and m['Egap'] > wcore.E_GAP_FLOOR
        print(f"rd {rd} lam={m['lam_eff']:.7f} Lam={m['Lam']:.5f} Eg={m['Egap']:.7f} e2={m['e2']*1e3:.5f} e1={m['e1']*1e3:.5f} "
              f"y=({al.y2:.5f},{al.y1:.5f},{al.yg:.5f}) rho={al.rho} zeros={int(np.sum(wc==0))} rel={rel} nit={res.nit} {time.time()-t0:.0f}s feas={feas}", flush=True)
        if feas and (best is None or m['lam_eff'] < best):
            best = m['lam_eff']
            np.savez(os.path.join(a.outdir, 'best.npz'), w=wc, wB=bc, **{k: np.float64(v) for k, v in m.items()})
        np.savez(ck, w=wc, wB=bc, y2=al.y2, y1=al.y1, yg=al.yg, rho=al.rho)
    print('best feasible', best, flush=True)


if __name__ == '__main__':
    main()
