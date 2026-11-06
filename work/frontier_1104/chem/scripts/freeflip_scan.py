#!/usr/bin/env python3
"""Scan free (Toffoli-neutral) word moves: flip bit `bit` of column j on a whole y-block (a=16y+z).

Any y-function is available in every loader (cache spans all y functions), so such moves cost 0 Toffoli
in loaders k and k+1. Exact metrics recomputed; merit priced with AL multipliers.
Usage: freeflip_scan.py <npz> <weights.npz> <out.json> --y2 .. --y1 .. --yg .. [--bit 0]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wcore  # noqa: E402
from wcore import dm  # noqa: E402


class WordEval:
    def __init__(self, npz, w, wB, ref):
        d = np.load(npz, allow_pickle=False)
        self.words = d['angle_words'].copy()
        self.edges = d['tree_edges']
        self.brot = int(d['brot'])
        self.eng, _, _ = wcore.load_engine(npz, ref=ref)
        self.w, self.wB = w, wB
        S, _ = wcore.shifts()
        self.T, rows, cols = wcore.packed_target(ref, S)
        self.rows, self.cols = rows, cols
        self.mult = np.where(rows == cols, 1.0, np.sqrt(2.0))
        e = self.eng
        self.Ub = e.u2.reshape(e.R * e.B, 76).copy()
        self.Phi = self.Ub[:, rows] * self.Ub[:, cols] * self.mult
        self.TPhi = self.T @ self.Phi.T  # (2926, RB)
        self.base = self.merit_parts()

    def merit_parts(self):
        e = self.eng
        return e.metrics(self.w, self.wB)

    def decode(self, words):
        u = dm.reconstruct_u_vectors(words / (1 << (self.brot - 1)), self.edges)
        return u / np.linalg.norm(u, axis=1, keepdims=True)

    def apply_rows(self, u_new, idx):
        """Temporarily install new row vectors idx (absolute row indices). Returns undo closure."""
        e = self.eng
        N = 76
        one = [i for i in idx if i < N]
        two = [i - N for i in idx if i >= N]
        saved = (e.V1[one].copy(), self.Ub[two].copy(), e.G[two].copy(), e.A[two].copy(), self.Phi[two].copy())
        e.V1[one] = u_new[one]
        if two:
            self.Ub[two] = u_new[[i + N for i in two]]
            e.u2[np.array(two) // e.B, np.array(two) % e.B] = self.Ub[two]
            G_row = (self.Ub[two] @ self.Ub.T) ** 2
            e.G[two] = G_row
            e.G[:, two] = G_row.T
            phi_new = self.Ub[two][:, self.rows] * self.Ub[two][:, self.cols] * self.mult
            # A = Phi T Phi^T: update rows then cols
            dphi = phi_new - self.Phi[two]
            TdP = self.T @ dphi.T                 # (2926, m)
            Aold_row = e.A[two].copy()
            Arow = Aold_row + dphi @ self.TPhi    # (m, RB) with old Phi on the right
            e.A[two] = Arow
            e.A[:, two] = Arow.T
            # correct the (two, two) block
            e.A[np.ix_(two, two)] = phi_new @ (self.T @ phi_new.T)
            self.Phi[two] = phi_new
        return one, two, saved

    def undo(self, st):
        e = self.eng
        one, two, (V, Ub, G, A, Phi) = st
        e.V1[one] = V
        if two:
            self.Ub[two] = Ub
            e.u2[np.array(two) // e.B, np.array(two) % e.B] = Ub
            e.G[two] = G
            e.G[:, two] = G.T
            e.A[two] = A
            e.A[:, two] = A.T
            self.Phi[two] = Phi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('npz')
    ap.add_argument('weights')
    ap.add_argument('out')
    ap.add_argument('--y2', type=float, default=0.005)
    ap.add_argument('--y1', type=float, default=0.0)
    ap.add_argument('--yg', type=float, default=0.0057)
    ap.add_argument('--bit', type=int, default=0)
    ap.add_argument('--blk', type=int, default=16)
    a = ap.parse_args()
    ref = wcore.load_ref()
    wd = np.load(a.weights)
    w, wB = wd['w'], wd['wB']
    ev = WordEval(a.npz, w, wB, ref)
    b = ev.base
    print('base', b, flush=True)

    def merit(m):
        return (m['lam_eff'] + a.y2 * (m['e2'] ** 2) * 1e6 + a.y1 * (m['e1'] ** 2) * 1e6 - a.yg * m['Egap'] * 1e3)
    m0 = merit(b)
    words = ev.words
    N_rows = words.shape[0]
    res = []
    t0 = time.time()
    uall = ev.decode(words)
    for j in range(words.shape[1]):
        wp = words.copy()
        wp[:, j] ^= (1 << a.bit)
        u_j = ev.decode(wp)
        for y in range((N_rows + a.blk - 1) // a.blk):
            idx = list(range(a.blk * y, min(a.blk * (y + 1), N_rows)))
            st = ev.apply_rows(u_j, idx)
            m = ev.eng.metrics(w, wB)
            ev.undo(st)
            res.append((merit(m) - m0, j, y, m['lam_eff'] - b['lam_eff'], (m['e2'] - b['e2']) * 1e3, (m['e1'] - b['e1']) * 1e3, (m['Egap'] - b['Egap']) * 1e3))
        res.sort()
        print(j, round(time.time() - t0), 'best', [tuple(round(float(x), 6) for x in r) for r in res[:3]], flush=True)
    json.dump(res, open(a.out, 'w'))
    print('negative merit moves:', sum(1 for r in res if r[0] < 0), 'of', len(res))


if __name__ == '__main__':
    main()
