"""P-A pre-experiment: corrected analysis.

1) Reproduce official fixed-point model -> p(x), s(x), y(x)=p<<s; verify A_ref vs saved.
2) s-distribution (normalization classes).
3) Bit-liveness audit: for each required y-bit i in 4..39, is it already an exact
   control column b_j in the current circuit? (correlate against work/p0_reports/data/bcols)
4) s-routing cost R for option (a) binary barrel-shift of p by s: EXACT mean-executed
   Toffoli count via numpy (a shift-link Toffoli fires iff its selector bit AND source bit are 1).
5) Corrected P-A economics with n_rot = 33 (NOT 0).
"""
import sys, json, math, time
import numpy as np

sys.path.insert(0, 'data/verifiers/invsqrt')
import verify_submission_invsqrt as V

U64, I64 = np.uint64, np.int64
N_P = 10
WIDTH = 2 * N_P + 2          # 22
MAX_X = 3 * (2**N_P - 2)**2  # 3,133,452
xs = np.arange(1, MAX_X + 1, dtype=np.int64)
spec = V.ProblemSpecInvSqrt.for_n_p(N_P, shots_per_x=1)
target, tol = V.reference_values(spec, xs.astype(U64))
N = MAX_X

# ---- reference fixed-point model (copied verbatim from step4a_reference_model.py) ----
POLY_A = (0.99994132489119882162, 0.49609891915903542303, 0.33261112772430493331, 0.14876762006038398086)
POLY_B = (0.81648515205385221995, 0.27136515484240234115, 0.12756148214815175348, 0.044753028579153842218)

def reference_fixed_point(n_p, delta_bits, coef_bits, square_bits, product_bits, result_bits, xs):
    width = 2 * n_p + 2
    xs = np.asarray(xs, dtype=np.int64)
    def bit(v, i): return (v >> i) & 1
    def product(rows, operand, out_bits, operand_bits, limit):
        acc = np.zeros_like(xs)
        for ctl, weight in rows:
            e = out_bits - operand_bits + weight
            acc += ctl * (operand << e if e >= 0 else operand >> -e)
        if (acc >= 2**limit).any(): raise OverflowError("intermediate overflow")
        return acc
    s = (width - (np.floor(np.log2(xs)).astype(np.int64) + 1)) // 2
    x_norm = xs << (2 * s)
    top, second, third = bit(x_norm, width-1), bit(x_norm, width-2), bit(x_norm, width-3)
    cases = [POLY_A, POLY_B,
             [a/(2**j*math.sqrt(2)) for j,a in enumerate(POLY_A)],
             [b/(2**j*math.sqrt(2)) for j,b in enumerate(POLY_B)]]
    table = np.array([[round(c*2**coef_bits) for c in case] for case in cases], dtype=np.int64)
    c0, c1, c2, c3 = (table[np.where(top==0, third, 2+second), j] for j in range(4))
    delta = [(top & third, -1)] + [(bit(x_norm, width-2-m), -m) for m in range(2, min(delta_bits, width-2)+1)]
    y0, mult = c0, c3
    for acc in (c2, c1, c0):
        y0 = mult = acc - product(delta, mult, coef_bits, coef_bits, coef_bits)
        if ((y0<=0)|(y0>=2**coef_bits)).any(): raise OverflowError("Horner overflow")
    wc = coef_bits
    y = {k: bit(y0, wc-k) for k in range(1, wc+1)}
    square = np.zeros_like(xs)
    for k in range(1, wc+1):
        if 2*k <= square_bits: square += y[k] << (square_bits - 2*k)
        for l in range(k+1, wc+1):
            if k+l-1 <= square_bits: square += (y[k]&y[l]) << (square_bits-(k+l-1))
    m_rows = [(bit(x_norm, i), i-width+2) for i in range(width)]
    z = product(m_rows, square, product_bits, square_bits, product_bits+2)
    correction = (3 << product_bits) - z
    p = product([(y[k], -k) for k in range(1, wc+1)], correction, result_bits, product_bits, result_bits+1)
    return p << s, s, x_norm, (top, second, third)

t0=time.time()
y, s, x_norm, (top, second, third) = reference_fixed_point(N_P, 14, 17, 28, 28, 29, xs)
p = y >> s
print(f'model computed in {time.time()-t0:.1f}s', file=sys.stderr)

# sanity: A_ref vs saved
A = (y.astype(I64) << 24) - target.astype(I64)
saved_A = np.load('work/p0_reports/data/A_ref.npy')
print('A_ref matches saved:', bool(np.array_equal(A, saved_A)), file=sys.stderr)
margin_A = tol.astype(I64) - np.abs(A)
print('model min margin:', int(margin_A.min()), 'at x=', int(xs[margin_A.argmin()])+1, file=sys.stderr)
print('model max |A|/tol:', float((np.abs(A)/tol.astype(float)).max()), file=sys.stderr)

# ---- s distribution ----
svals, scounts = np.unique(s, return_counts=True)
print('\ns distribution (s : count : frac):')
for sv, sc in zip(svals, scounts):
    print(f'  s={int(sv):2d} : {int(sc):8d} : {sc/N:.5f}')

# save p, s, y for other scripts
np.save('work/pa_prexperiment/data/p.npy', p.astype(I64))
np.save('work/pa_prexperiment/data/s.npy', s.astype(I64))
np.save('work/pa_prexperiment/data/y.npy', y.astype(I64))
print('\nsaved p,s,y to work/pa_prexperiment/data/', file=sys.stderr)
