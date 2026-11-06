"""One-Newton invsqrt family probe (exact integer, full domain).

Motivation: the RAW two-Newton constseed build landed at 509Q/9434CCX (~0.42x).
The REPORT names "two Newton steps ~= double the multiply work" as the #1 cost
driver. This probe asks: does a SINGLE Newton step, fed by a higher-precision
seed (13-16 bit), still pass the full-domain tolerance with usable margin?

Newton for 1/sqrt(M): z' = z(3 - M z^2)/2, relative error e' ~= 1.5 e^2.
So a seed with worst rel error e_max yields output error ~1.5 e_max^2.
We sweep seed precision and seed family and report worst err/tolerance.

Imported from the validated model so the normalization / seed math is identical.
"""
from __future__ import annotations

import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from invsqrt_constseed_model import (  # noqa: E402
    N_P, WIDTH, MAX_X, TOL_REL, normalize, seed_table, _PWQ3_COEFS,
)


def _seed_pure(x_norm: np.ndarray, inter: np.ndarray, idx: np.ndarray,
               seed_mode: str, sf: int) -> np.ndarray:
    """S in units of 2^-sf, matching the model's seed definitions exactly."""
    if seed_mode == 'table':
        return seed_table('center', sf)[idx]
    if seed_mode == 'pwq3':
        m0v = np.array([1.0, 1.5, 2.0, 3.0])[inter]
        wv = np.array([0.5, 0.5, 1.0, 1.0])[inter]
        Mv = x_norm.astype(np.float64) / 2.0 ** (WIDTH - 2)
        u = (Mv - m0v) / wv
        k = (u * 128.0).astype(np.int64)
        kk = k.astype(np.float64) / 128.0
        coefs = _PWQ3_COEFS
        a = np.array([c[0] for c in coefs])[inter]
        b = np.array([c[1] for c in coefs])[inter]
        c = np.array([c[2] for c in coefs])[inter]
        d = np.array([c[3] for c in coefs])[inter]
        seed = ((d * kk + c) * kk + b) * kk + a
        return (seed * 2.0 ** sf).astype(np.int64)
    raise ValueError(seed_mode)


def onewton_error(xs: np.ndarray, *, seed_mode: str = 'pwq3', seed_frac: int = 14,
                  out_frac: int = 26, n1_guard: int = 4):
    """Single Newton step straight to out_frac. Returns relative error array."""
    xs = np.asarray(xs, dtype=np.int64)
    if xs.size == 0:
        return np.zeros(0)
    s, x_norm = normalize(xs)
    idx = x_norm >> (WIDTH - 7)
    top = (x_norm >> (WIDTH - 1)) & 1
    second = (x_norm >> (WIDTH - 2)) & 1
    third = (x_norm >> (WIDTH - 3)) & 1
    inter = np.where(top == 0, third, 2 + second)
    sf = seed_frac
    S = _seed_pure(x_norm, inter, idx, seed_mode, sf)

    n1 = out_frac + n1_guard  # internal precision of the single Newton step
    # M*y_s^2 * 2^n1 = x_norm*S^2 * 2^n1 / (2^(WIDTH-2) * 2^(2 sf))
    Q1 = (x_norm * S * S) >> (WIDTH - 2 + 2 * sf - n1)
    C1 = (3 << n1) - Q1
    P1 = (S * C1) >> sf  # p1 in 2^-n1 units
    if (P1 <= 0).any() or (P1 >= (3 << n1)).any():
        raise OverflowError('p1 out of range')
    approx = P1 * 2.0 ** (s - N_P - 1) / 2.0 ** n1
    exact = 1.0 / np.sqrt(xs.astype(np.float64))
    return np.abs(approx - exact) / exact


def worst(rel: np.ndarray, xs: np.ndarray):
    r = rel / TOL_REL
    i = int(r.argmax())
    return float(r.max()), int(xs[i])


def main():
    xs = np.arange(1, MAX_X + 1, dtype=np.int64)
    print(f'domain: x = 1..{MAX_X} ({len(xs):,})  TOL_REL=2^-24')
    print(f"{'seed':<8} {'sf':>3} {'guard':>5} {'out':>4} | {'worst/tol':>10} {'at x':>9}")
    for seed_mode in ('table', 'pwq3'):
        for sf in (12, 13, 14, 15, 16):
            for guard in (2, 4, 6):
                try:
                    rel = onewton_error(xs, seed_mode=seed_mode, seed_frac=sf,
                                        out_frac=26, n1_guard=guard)
                    wr, wx = worst(rel, xs)
                    flag = ''
                    if wr < 0.9:
                        flag = '  <-- PASS(<0.9)'
                    elif wr < 1.0:
                        flag = '  (pass, thin)'
                    else:
                        flag = '  FAIL'
                    print(f"{seed_mode:<8} {sf:>3} {guard:>5} {26:>4} | {wr:>10.4f} {wx:>9,}{flag}")
                except Exception as e:
                    print(f"{seed_mode:<8} {sf:>3} {guard:>5} {26:>4} | FAILED: {type(e).__name__}: {str(e)[:40]}")


if __name__ == '__main__':
    main()
