"""Constant-seed invsqrt numerical model — reconstruction of mrmeows' open direction.

Spec (sota_mrmeows/README.md, "Open direction"):
  "A constant-seed model (128 entry seed table, 8 fractional bits, degree 3,
   residual 24 plus 2 guard bits, output fraction 26) passes the full domain
   numerical check at worst error/tolerance 0.617."

Interpretation implemented here:
  1. Normalize: s leading zero pairs, M = x_norm/2^(WIDTH-2) in [1,4).
  2. Seed: 128-entry table over the top 7 bits of x_norm, 8 fractional bits
     (variants: center/left table, per-interval cubic in the 5 sub-bin bits).
     -> y_s ~ 1/sqrt(M), relative error eps0 ~ 2^-7..2^-8.
  3. Newton #1 (degree 3 in y_s): p1 = y_s (3 - M y_s^2) ~ 2/sqrt(M),
     truncated to n1_frac fractional bits. eps1 ~ eps0^2/2 ~ 2^-15.
  4. Newton #2 (degree 3 in p1): q2 = M p1^2 / 4 kept at g = n2_guard+2 bits,
     p2 = p1 (2 - q2) truncated to out_frac fractional bits.
     eps2 ~ eps1^2/2 + truncation ~ 2^-25..2^-26.
  5. Denormalize y1 = p2 2^s; F = out_frac + N_P + 1; phase y1/2^F ~ 1/sqrt(x).

All arithmetic is exact integer truncation (T(.) semantics of the reference),
matching kickmix bit-for-bit. Domain: all integers x = 1..3,133,452.
"""
from __future__ import annotations

import math
import sys

import numpy as np

N_P = 10
WIDTH = 2 * N_P + 2            # 22
MAX_X = 3 * (2**N_P - 2) ** 2  # 3,133,452
TOL_REL = 2.0 ** -24


# ---------------------------------------------------------------------------
# Reference model (from data/verifiers/invsqrt/nr_reference_circuit.py)
# ---------------------------------------------------------------------------

POLY_A = (0.99994132489119882162, 0.49609891915903542303, 0.33261112772430493331, 0.14876762006038398086)
POLY_B = (0.81648515205385221995, 0.27136515484240234115, 0.12756148214815175348, 0.044753028579153842218)


def reference_fixed_point(n_p: int, delta_bits: int, coef_bits: int, square_bits: int,
                          product_bits: int, result_bits: int, xs: np.ndarray) -> np.ndarray:
    """Exact copy of nr_reference_circuit.fixed_point_model (parameterized widths)."""
    width = 2 * n_p + 2
    xs = np.asarray(xs, dtype=np.int64)

    def bit(v, i):
        return (v >> i) & 1

    def product(rows, operand, out_bits, operand_bits, limit):
        acc = np.zeros_like(xs)
        for ctl, weight in rows:
            e = out_bits - operand_bits + weight
            acc += ctl * (operand << e if e >= 0 else operand >> -e)
        if (acc >= 2**limit).any():
            raise OverflowError('Intermediate register overflow.')
        return acc

    s = (width - (np.floor(np.log2(xs)).astype(np.int64) + 1)) // 2
    x_norm = xs << (2 * s)
    top, second, third = bit(x_norm, width - 1), bit(x_norm, width - 2), bit(x_norm, width - 3)

    cases = [POLY_A, POLY_B,
             [a / (2**j * math.sqrt(2)) for j, a in enumerate(POLY_A)],
             [b / (2**j * math.sqrt(2)) for j, b in enumerate(POLY_B)]]
    table = np.array([[round(c * 2**coef_bits) for c in case] for case in cases], dtype=np.int64)
    c0, c1, c2, c3 = (table[np.where(top == 0, third, 2 + second), j] for j in range(4))
    delta = [(top & third, -1)] + [(bit(x_norm, width - 2 - m), -m) for m in range(2, min(delta_bits, width - 2) + 1)]
    y0, mult = c0, c3
    for acc in (c2, c1, c0):
        y0 = mult = acc - product(delta, mult, coef_bits, coef_bits, coef_bits)
        if ((y0 <= 0) | (y0 >= 2**coef_bits)).any():
            raise OverflowError('Horner intermediate does not fit its register.')

    wc = coef_bits
    y = {k: bit(y0, wc - k) for k in range(1, wc + 1)}
    square = np.zeros_like(xs)
    for k in range(1, wc + 1):
        if 2 * k <= square_bits:
            square += y[k] << (square_bits - 2 * k)
        for l in range(k + 1, wc + 1):
            if k + l - 1 <= square_bits:
                square += (y[k] & y[l]) << (square_bits - (k + l - 1))
    m_rows = [(bit(x_norm, i), i - width + 2) for i in range(width)]
    z = product(m_rows, square, product_bits, square_bits, product_bits + 2)
    correction = (3 << product_bits) - z
    p = product([(y[k], -k) for k in range(1, wc + 1)], correction, result_bits, product_bits, result_bits + 1)
    return p << s


def reference_error(n_p, d, wc, wsq, wz, wp, xs):
    F = wp + n_p + 1
    approx = reference_fixed_point(n_p, d, wc, wsq, wz, wp, xs) / 2.0**F
    exact = 1 / np.sqrt(xs.astype(np.float64))
    return np.abs(approx - exact) / exact


# ---------------------------------------------------------------------------
# Constant-seed model
# ---------------------------------------------------------------------------

def normalize(xs: np.ndarray):
    s = (WIDTH - (np.floor(np.log2(xs)).astype(np.int64) + 1)) // 2
    return s, xs << (2 * s)


def seed_table(mode: str = 'center', frac: int = 8) -> np.ndarray:
    """128 entries over top 7 bits of x_norm; bin i covers M in [i/32, (i+1)/32)."""
    i = np.arange(128, dtype=np.float64)
    Mc = (i + (0.5 if mode == 'center' else 0.0)) / 32.0
    f = np.where(Mc > 0, 1.0 / np.sqrt(np.where(Mc > 0, Mc, 1.0)), 0.0)
    S = np.round(f * 2.0**frac).astype(np.int64)
    return S


def fit_cubics(frac: int = 12) -> list[list[int]]:
    """Per-interval minimax-ish cubic in sub-bin index j=0..31 for f on the interval.

    Interval k covers M in [m0, m0+w): k=0:[1,1.5), 1:[1.5,2), 2:[2,3), 3:[3,4).
    Fit c0..c3 (stored at `frac` fractional bits) minimizing max |cubic(j) - f(m0 + (j+0.5)*w/32)|
    over j=0..31 by simple LSQ then local polish (good enough for the model).
    """
    bounds = [(1.0, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 4.0)]
    out = []
    for m0, m1 in bounds:
        w = m1 - m0
        j = np.arange(32)
        M = m0 + (j + 0.5) * w / 32.0
        f = 1.0 / np.sqrt(M)
        # LSQ cubic in j (0..31); the circuit evaluates Horner in the 5 address bits j.
        A = np.vander(j.astype(np.float64), 4)[:, ::-1]
        coef, *_ = np.linalg.lstsq(A, f, rcond=None)
        # polish: nudge each coef by +/- 1 LSB until worst case improves (few rounds)
        best = coef.copy()
        for _ in range(60):
            improved = False
            for ci in range(4):
                for dv in (-1, 1):
                    cand = best.copy()
                    cand[ci] += dv / 2.0**frac
                    err = np.abs(A @ cand - f).max()
                    if err < np.abs(A @ best - f).max() - 1e-18:
                        best, improved = cand, True
            if not improved:
                break
        out.append([int(round(c * 2.0**frac)) for c in best])
    return out


def fit_pwq(sf: int = 8, ab: int = 12, bb: int = 7, cb: int = 6):
    """Per-interval quadratic in u = (M-m0)/w in [0,1), evaluated at u = k/64 (6 addr bits).

    seed = a + b*u + c*u^2  ->  seed_num = A + B*k + (C*k*k)>>cb   [units of 2^-ab]
      A = round(a*2^ab), B = round(b*2^(ab-6)), C = round(c*2^(ab-12+cb))
    Returns (A, B, C) lists per interval + params.
    """
    bounds = [(1.0, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 4.0)]
    As, Bs, Cs = [], [], []
    for m0, m1 in bounds:
        w = m1 - m0
        k = np.arange(64, dtype=np.float64)
        u = k / 64.0
        M = m0 + u * w
        f = 1.0 / np.sqrt(M)
        Acoef = np.vander(u, 3)[:, ::-1]
        coef, *_ = np.linalg.lstsq(Acoef, f, rcond=None)
        a, b, c = coef
        As.append(int(round(a * 2**ab)))
        Bs.append(int(round(b * 2**(ab - 6))))
        Cs.append(int(round(c * 2**(ab - 12 + cb))))
    return As, Bs, Cs


def fit_pwq3(ab: int = 12, cb: int = 10, db: int = 10):
    """Per-interval CUBIC in u=(M-m0)/w, evaluated at k = floor(u*128) (7 addr bits).

    seed = a + b*u + c*u^2 + d*u^3, u = k/128.
    Integer form: seed_num = A + B*k + (Cc*k*k)>>e2 + (Dd*k*k*k)>>e3   [units of 2^-ab]
      A  = round(a*2^ab)
      B  = round(b*2^(ab-7))
      Cc = round(c*2^(ab-14+cb))   -> (Cc*k^2) >> (cb)     gives c*k^2*2^(ab-14)
      Dd = round(d*2^(ab-21+db))   -> (Dd*k^3) >> (db)     gives d*k^3*2^(ab-21)
    Returns (A, B, Cc, Dd) lists per interval.
    """
    bounds = [(1.0, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 4.0)]
    As, Bs, Cs, Ds = [], [], [], []
    for m0, m1 in bounds:
        w = m1 - m0
        k = np.arange(128, dtype=np.float64)
        u = k / 128.0
        M = m0 + u * w
        f = 1.0 / np.sqrt(M)
        Acoef = np.vander(u, 4)[:, ::-1]
        coef, *_ = np.linalg.lstsq(Acoef, f, rcond=None)
        a, b, c, d = coef
        As.append(int(round(a * 2**ab)))
        Bs.append(int(round(b * 2**(ab - 7))))
        Cs.append(int(round(c * 2**(ab - 14 + cb))))
        Ds.append(int(round(d * 2**(ab - 21 + db))))
    return As, Bs, Cs, Ds


def fit_pwq3_float():
    """Per-interval cubic in u=(M-m0)/w, LSQ on the 128 grid points u=k/128. Returns float coefs."""
    bounds = [(1.0, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 4.0)]
    out = []
    for m0, m1 in bounds:
        w = m1 - m0
        k = np.arange(128, dtype=np.float64)
        u = k / 128.0
        M = m0 + u * w
        f = 1.0 / np.sqrt(M)
        Acoef = np.vander(u, 4)[:, ::-1]
        coef, *_ = np.linalg.lstsq(Acoef, f, rcond=None)
        out.append(tuple(coef))
    return out


_PWQ3_COEFS = fit_pwq3_float()


def constseed_error(xs: np.ndarray, *, seed_mode: str = 'table', seed_frac: int = 8,
                    n1_frac: int = 16, n2_guard: int = 24, out_frac: int = 26,
                    cubics: list[list[int]] | None = None) -> tuple[np.ndarray, dict]:
    """Exact integer model. Returns (relative_error, info)."""
    xs = np.asarray(xs, dtype=np.int64)
    s, x_norm = normalize(xs)
    idx = x_norm >> (WIDTH - 7)  # top 7 bits

    if seed_mode == 'table':
        S = seed_table('center', seed_frac)[idx]
    elif seed_mode == 'table_left':
        S = seed_table('left', seed_frac)[idx]
    elif seed_mode == 'pwq':
        # piecewise-quadratic in u=(M-m0)/w, evaluated at k = floor(u*64) (6 addr bits).
        #   inter via reference case logic; base = x_norm - m0*2^20 in [0, w*2^20)
        #   k = base >> (13 if w==0.5 else 14)
        #   seed_num = A + B*k + (C*k*k)>>cb   [units of 2^-ab]
        #   S = seed_num >> (ab - sf)          [units of 2^-sf]
        sf = seed_frac
        ab, bb, cb = 12, 7, 6
        As, Bs, Cs = fit_pwq(sf, ab, bb, cb)
        top = (x_norm >> (WIDTH - 1)) & 1
        second = (x_norm >> (WIDTH - 2)) & 1
        third = (x_norm >> (WIDTH - 3)) & 1
        inter = np.where(top == 0, third, 2 + second)   # 0..3
        m0_20 = np.array([1 * 2**20, int(1.5 * 2**20), 2 * 2**20, 3 * 2**20])
        base = x_norm - m0_20[inter]                    # in [0, w*2^20)
        shift = np.where(inter <= 1, 13, 14)
        k = (base >> shift) & 63
        A = np.array(As)[inter]
        B = np.array(Bs)[inter]
        C = np.array(Cs)[inter]
        seed_num = A + B * k + ((C * k * k) >> cb)
        S = seed_num >> (ab - sf)
    elif seed_mode == 'pwq3':
        # piecewise-CUBIC in u=(M-m0)/w, k = floor(u*128) (7 addr bits).
        # Model upper bound: exact float64 cubic, final truncation to seed_frac bits.
        sf = seed_frac
        top = (x_norm >> (WIDTH - 1)) & 1
        second = (x_norm >> (WIDTH - 2)) & 1
        third = (x_norm >> (WIDTH - 3)) & 1
        inter = np.where(top == 0, third, 2 + second)   # 0..3
        m0v = np.array([1.0, 1.5, 2.0, 3.0])[inter]
        wv = np.array([0.5, 0.5, 1.0, 1.0])[inter]
        Mv = x_norm.astype(np.float64) / 2.0**(WIDTH - 2)
        u = (Mv - m0v) / wv
        k = (u * 128.0).astype(np.int64)               # 0..127
        kk = k.astype(np.float64) / 128.0              # u_grid point used by circuit
        coefs = _PWQ3_COEFS                            # (a,b,c,d) per interval, float64
        a = np.array([c[0] for c in coefs])[inter]
        b = np.array([c[1] for c in coefs])[inter]
        c = np.array([c[2] for c in coefs])[inter]
        d = np.array([c[3] for c in coefs])[inter]
        seed = ((d * kk + c) * kk + b) * kk + a
        S = (seed * 2.0**sf).astype(np.int64)          # truncate to sf fractional bits
    elif seed_mode == 'cubic':
        # Horner in j (5 bits) per interval; interval = top 2 bits of idx
        cubics = cubics or fit_cubics(seed_frac + 4)
        cf = seed_frac + 4  # coefficient fractional bits
        inter = idx >> 5
        j = idx & 31
        c0 = np.array([c[0] for c in cubics])[inter]
        c1 = np.array([c[1] for c in cubics])[inter]
        c2 = np.array([c[2] for c in cubics])[inter]
        c3 = np.array([c[3] for c in cubics])[inter]
        # evaluate c3*j^3 + c2*j^2 + c1*j + c0 in units of 2^-cf, j in 0..31
        # (model: exact polynomial, then truncate to seed_frac fractional bits)
        val = ((c3 * j + c2) * j + c1) * j + c0  # units of 2^-cf
        S = (val >> (cf - seed_frac))  # truncate to seed_frac fractional bits
    else:
        raise ValueError(seed_mode)

    # y_s = S * 2^-seed_frac  (S in [2^(seed_frac-1), 2^seed_frac): f in [0.5,1])
    # Newton #1, units of 2^-n1_frac:
    #   Q1 = trunc(M*y_s^2 * 2^n1) = (x_norm*S^2) >> (WIDTH-2+2*seed_frac-n1)
    #   C1 = 3*2^n1 - Q1                          (corr1 = 3 - M*y_s^2)
    #   P1 = trunc(p1*2^n1) = (S*C1) >> seed_frac (p1 = y_s*corr1)
    Q1 = (x_norm * S * S) >> (WIDTH - 2 + 2 * seed_frac - n1_frac)
    C1 = (3 << n1_frac) - Q1
    P1 = (S * C1) >> seed_frac
    if (P1 <= 0).any() or (P1 >= (3 << n1_frac)).any():
        raise OverflowError('p1 out of range')

    # Newton #2, units of 2^-g, g = n2_guard + 2.  Targets z*=2/sqrt(M) from p1~z*:
    #   p2 = p1 * (3 - M*p1^2/4) / 2          (quadratic convergence, delta2 ~ -3 delta1^2/2)
    #   P1g = P1 * 2^(g-n1)                        (p1 in 2^-g units)
    #   Q2 = trunc(M*p1^2/4 * 2^g) = (x_norm*P1g^2) >> (WIDTH+g)
    #   C2 = ((3*2^g - Q2) >> 1)                    (corr2 = (3 - M*p1^2/4)/2)
    #   P2 = trunc(p2*2^out) = (P1g*C2) >> (2g-out)
    g = n2_guard + 2
    P1g = P1 << (g - n1_frac)
    Q2 = (x_norm * P1 * P1) >> (WIDTH - g + 2 * n1_frac)
    C2 = ((3 << g) - Q2) >> 1
    P2 = (P1g * C2) >> (2 * g - out_frac)
    if (P2 <= 0).any() or (P2 >= (3 << out_frac)).any():
        raise OverflowError('p2 out of range')

    # Denormalize: y1/2^F = p2/2^out_frac * 2^s, F = out_frac + N_P + 1
    approx = P2 * 2.0**(s - N_P - 1) / 2.0**out_frac
    exact = 1.0 / np.sqrt(xs.astype(np.float64))
    rel = np.abs(approx - exact) / exact
    info = {'idx_range': (int(idx.min()), int(idx.max())), 'P1_range': (int(P1.min()), int(P1.max())),
            'P2_range': (int(P2.min()), int(P2.max()))}
    return rel, info


def worst_ratio(rel: np.ndarray, xs: np.ndarray) -> tuple[float, int]:
    r = rel / TOL_REL
    i = int(r.argmax())
    return float(r.max()), int(xs[i])


def and_estimate(seed_mode: str, n1_frac: int, n2_guard: int, out_frac: int) -> dict:
    """Rough static AND counts mirroring the reference's column-truncated multipliers."""
    sf = 8
    g = n2_guard + 2
    # seed
    if seed_mode == 'table':
        seed_and = 700  # decision-tree QROM 128x9, smooth data (estimate)
    else:
        seed_and = 3 * 5 * (sf + 4)  # Horner: 3 steps x 5 j-bits x ~12-bit accumulator
    # Newton #1: y_s^2 (9x9 -> keep n1_frac), M*y_s^2 (22 x (2+n1_frac) -> n1_frac), y_s*corr (9 x (2+n1_frac) -> n1_frac)
    sq1 = sum(1 for k in range(1, 10) for l in range(k, 10) if (2 * k if l == k else k + l - 1) <= n1_frac)
    m1 = sum(max(0, WIDTH - (WIDTH - 2 - n1_frac + i)) for i in range(0, n1_frac + 3))
    p1m = sum(max(0, n1_frac - i + 1) for i in range(0, sf + 3))
    # Newton #2: p1^2 (keep g), M*p1^2/4 (keep g), p1*corr2 (keep out_frac)
    n1w = n1_frac + 1  # p1 width in bits (1 int + n1_frac)
    sq2 = sum(1 for k in range(1, n1w + 1) for l in range(k, n1w + 1) if (2 * k if l == k else k + l - 1) <= g)
    m2 = sum(max(0, WIDTH - (WIDTH - 2 - g + i)) for i in range(0, g + 3))
    p2m = sum(max(0, out_frac - i + 1) for i in range(0, n1w + 3))
    norm_and = 12  # leading-zero-pair flags
    total = seed_and + sq1 + m1 + p1m + sq2 + m2 + p2m + norm_and
    return {'seed': seed_and, 'newton1': sq1 + m1 + p1m, 'newton2': sq2 + m2 + p2m,
            'normalize': norm_and, 'total_static_AND': total}


def main():
    xs = np.arange(1, MAX_X + 1, dtype=np.int64)
    print(f'domain: x = 1..{MAX_X} ({len(xs):,} points)')

    # Validate harness against the reference (default widths): expect ~2.84e-8
    ref_rel = reference_error(N_P, 14, 17, 28, 28, 29, xs)
    print(f'REFERENCE (14,17,28,28,29): worst rel {ref_rel.max():.3e} = 2^{math.log2(ref_rel.max()):.2f} '
          f'(docstring says 2.84e-8)')

    configs = [
        # (name, kwargs)
        ('mrmeows-spec', dict(seed_mode='table', n1_frac=16, n2_guard=24, out_frac=26)),
        ('pwq', dict(seed_mode='pwq', n1_frac=16, n2_guard=24, out_frac=26)),
        ('pwq3', dict(seed_mode='pwq3', n1_frac=16, n2_guard=24, out_frac=26)),
        ('pwq3-n18', dict(seed_mode='pwq3', n1_frac=18, n2_guard=24, out_frac=26)),
        ('pwq-n18', dict(seed_mode='pwq', n1_frac=18, n2_guard=24, out_frac=26)),
        ('spec-cubic', dict(seed_mode='cubic', n1_frac=16, n2_guard=24, out_frac=26)),
        ('spec-left', dict(seed_mode='table_left', n1_frac=16, n2_guard=24, out_frac=26)),
        ('n1=14', dict(seed_mode='table', n1_frac=14, n2_guard=24, out_frac=26)),
        ('n1=18', dict(seed_mode='table', n1_frac=18, n2_guard=24, out_frac=26)),
        ('guard22', dict(seed_mode='table', n1_frac=16, n2_guard=22, out_frac=26)),
        ('guard26', dict(seed_mode='table', n1_frac=16, n2_guard=26, out_frac=26)),
        ('out24', dict(seed_mode='table', n1_frac=16, n2_guard=24, out_frac=24)),
        ('out28', dict(seed_mode='table', n1_frac=16, n2_guard=24, out_frac=28)),
        ('seed9bit', dict(seed_mode='table', seed_frac=9, n1_frac=16, n2_guard=24, out_frac=26)),
    ]
    print(f"\n{'config':<12} {'worst/tol':>10} {'at x':>9}  {'AND est':>8}")
    for name, kw in configs:
        try:
            rel, info = constseed_error(xs, **kw)
            ratio, wx = worst_ratio(rel, xs)
            est = and_estimate(kw.get('seed_mode', 'table'), kw.get('n1_frac', 16),
                               kw.get('n2_guard', 24), kw.get('out_frac', 26))
            print(f"{name:<12} {ratio:>10.4f} {wx:>9,}  {est['total_static_AND']:>8}")
        except Exception as e:
            print(f"{name:<12} FAILED: {type(e).__name__}: {str(e)[:60]}")

    # Detailed sweep around the spec for the table seed
    print('\nsweep (table seed):')
    print(f"{'n1':>4} {'guard':>6} {'out':>4} | {'worst/tol':>10} {'at x':>9}")
    for n1 in (14, 15, 16, 17, 18):
        for gr in (22, 23, 24, 25):
            for out in (25, 26, 27):
                rel, _ = constseed_error(xs, seed_mode='table', n1_frac=n1, n2_guard=gr, out_frac=out)
                ratio, wx = worst_ratio(rel, xs)
                flag = '  <-- spec' if (n1, gr, out) == (16, 24, 26) else ''
                print(f"{n1:>4} {gr:>6} {out:>4} | {ratio:>10.4f} {wx:>9,}{flag}")


if __name__ == '__main__':
    main()
