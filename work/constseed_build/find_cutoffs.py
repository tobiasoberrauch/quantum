#!/usr/bin/env python3
"""Comprehensive circuit emulator + joint cutoff optimizer (target worst/tol <= 0.6)."""
import numpy as np, sys, itertools
sys.path.insert(0, 'work')
import invsqrt_constseed_model as M

xs = np.arange(1, M.MAX_X + 1, dtype=np.int64)
sf, n1, g, out, N_P, AB = 8, 16, 26, 26, 10, 18
s, xn = M.normalize(xs)
top = (xn >> (M.WIDTH - 1)) & 1; second = (xn >> (M.WIDTH - 2)) & 1; third = (xn >> (M.WIDTH - 3)) & 1
inter = np.where(top == 0, third, 2 + second)
k = np.where(inter <= 1, (xn >> 12) & 0x7F, (xn >> 13) & 0x7F)
m0v = np.array([1., 1.5, 2., 3.])[inter]; wv = np.array([.5, .5, 1., 1.])[inter]
Mv = xn.astype(np.float64) / 2.0**(M.WIDTH - 2); u = (Mv - m0v) / wv
kk = ((u * 128.).astype(np.int64)).astype(np.float64) / 128.
co = M._PWQ3_COEFS
a = np.array([c[0] for c in co])[inter]; b = np.array([c[1] for c in co])[inter]
cc = np.array([c[2] for c in co])[inter]; d = np.array([c[3] for c in co])[inter]
S_model = ((((d * kk + cc) * kk + b) * kk + a) * 2.0**sf).astype(np.int64)

# coefficient magnitudes (units 2^-AB)
A = np.round(a * 2**AB).astype(np.int64); Bm = np.round(-b * 2**AB).astype(np.int64)
C = np.round(cc * 2**AB).astype(np.int64); Dm = np.round(-d * 2**AB).astype(np.int64)


def emul(Av, Bv, L, W, na):
    res = np.zeros_like(Av, dtype=np.int64); mask = (1 << W) - 1
    for i in range(na):
        abit = (Av >> i) & 1; shift = i - L
        contrib = (Bv << shift) if shift >= 0 else (Bv >> (-shift))
        res = (res + abit * (contrib & mask)) & mask
    return res


def mul_kk(X, L, W):
    # (X*k)>>7 with k as 7-bit control; keep cols>=L, width W
    res = np.zeros_like(X, dtype=np.int64); mask = (1 << W) - 1
    for j in range(7):
        kb = (k >> j) & 1
        shift = j - L
        contrib = (X << shift) if shift >= 0 else (X >> (-shift))
        res = (res + kb * (contrib & mask)) & mask
    return res


def pipeline(Ltd, Lr2, Lr1, Lq1, Lp1, Lq2, Lp2,
             Wtd, Wr2, Wr1, Wq1, Wp1, Wq2, Wp2):
    # seed
    td = mul_kk(Dm, Ltd, Wtd) >> (7 - Ltd)
    r2 = C - td
    tr2 = mul_kk(r2, Lr2, Wr2) >> (7 - Lr2)
    r1 = Bm - tr2
    tr1 = mul_kk(r1, Lr1, Wr1) >> (7 - Lr1)
    r0 = A - tr1
    S = r0 >> (AB - sf)
    # newton1
    SS = S * S
    Q1 = emul(xn, SS, Lq1, Wq1, M.WIDTH) >> (20 - Lq1)
    C1 = (3 << n1) - Q1
    P1 = emul(S, C1, Lp1, Wp1, sf) >> (8 - Lp1)
    # newton2
    P1g = P1 << (g - n1)
    sq2 = P1 * P1
    Q2 = emul(xn, sq2, Lq2, Wq2, M.WIDTH) >> (28 - Lq2)
    C2 = ((3 << g) - Q2) >> 1
    P2 = emul(P1g, C2, Lp2, Wp2, g - n1 + n1 + 1) >> (26 - Lp2)
    return S, P2


def worst_ratio(P2):
    y1 = P2 << s; F = out + N_P + 1
    approx = y1 / 2.0**F; exact = 1.0 / np.sqrt(xs.astype(np.float64))
    rel = np.abs(approx - exact) / exact
    r = rel / M.TOL_REL
    return float(r.max()), int(xs[int(r.argmax())])


def cost(Ltd, Lr2, Lr1, Lq1, Lp1, Lq2, Lp2, Wtd, Wr2, Wr1, Wq1, Wp1, Wq2, Wp2):
    # iadd Toffolis (forward) ~ sum na*(W-1); init_and ~ sum na*nb_kept
    c = 0
    c += 7 * (Wtd - 1) + 7 * (Wtd)        # seed td (k control, 7 rows)
    c += 7 * (Wr2 - 1) + 7 * (Wr2)
    c += 7 * (Wr1 - 1) + 7 * (Wr1)
    c += M.WIDTH * (Wq1 - 1) + M.WIDTH * 16   # Q1
    c += sf * (Wp1 - 1) + sf * 18              # P1
    c += 16 * (34 - 1) + 136                   # sq2 square
    c += M.WIDTH * (Wq2 - 1) + M.WIDTH * 34    # Q2
    c += (g - n1 + n1 + 1) * (Wp2 - 1) + (g - n1 + n1 + 1) * 27  # P2
    return c


# FINAL CONFIG: seed L=7(W=18), Q1 L=3(W=34), P1 L=1(W=24), Q2 L=26(W=29), P2 L=22(W=31)
cfg = dict(Ltd=7, Lr2=7, Lr1=7, Lq1=3, Lp1=1, Lq2=26, Lp2=22,
           Wtd=18, Wr2=18, Wr1=18, Wq1=34, Wp1=24, Wq2=29, Wp2=31)
S, P2 = pipeline(**cfg)
r, wx = worst_ratio(P2)
print(f"FINAL: worst/tol={r:.4f} at x={wx}  S_match={bool((S==S_model).all())}")
print(f"  est forward iadd+and cost = {cost(**cfg)}  (x2 both dirs)")

# also try pushing Q2/P2/seed L higher for more savings while ratio<=0.6
print('\nsweep Q2 L (others fixed):')
for Lq2 in range(20, 30):
    c2 = dict(cfg); c2['Lq2'] = Lq2; c2['Wq2'] = 28 + 27 - Lq2
    _, P2b = pipeline(**c2); rb, wxb = worst_ratio(P2b)
    print(f'  Q2 L={Lq2} W={c2["Wq2"]}: {rb:.4f}')
print('sweep P2 L (others fixed):')
for Lp2 in range(18, 28):
    c2 = dict(cfg); c2['Lp2'] = Lp2; c2['Wp2'] = 26 + 27 - Lp2
    _, P2b = pipeline(**c2); rb, wxb = worst_ratio(P2b)
    print(f'  P2 L={Lp2} W={c2["Wp2"]}: {rb:.4f}')
