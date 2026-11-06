"""Step 4a: official reference fixed-point model error A_ref(x) = theta_model - target.

theta_model(x) = y(x) * 2^24 units of 2^-64 turns, y = p << s from the official
nr_reference_circuit fixed-point model (14 delta bits, 17 coef bits, 28/28/29 widths).
Compares structure against measured err(x) and tol(x).
"""
import sys, json, math
import numpy as np
sys.path.insert(0, 'data/verifiers/invsqrt')
import verify_submission_invsqrt as V

U64, I64 = np.uint64, np.int64
N_P = 10
WIDTH = 2 * N_P + 2
MAX_X = 3 * (2**N_P - 2)**2
xs = np.arange(1, MAX_X + 1, dtype=np.int64)
spec = V.ProblemSpecInvSqrt.for_n_p(N_P, shots_per_x=1)
target, tol = V.reference_values(spec, xs.astype(U64))

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

y, s, x_norm, (top, second, third) = reference_fixed_point(N_P, 14, 17, 28, 28, 29, xs)
theta_model = y.astype(I64) << 24          # units of 2^-64 turns
A = theta_model - target.astype(I64)       # base arithmetic error (signed)
used_A = np.abs(A)
margin_A = tol.astype(I64) - used_A

print('model min margin:', int(margin_A.min()), 'at x=', int(xs[margin_A.argmin()])+1)
print('model max |A|/tol:', float((used_A/ tol.astype(float)).max()))
r = used_A / tol.astype(float)
edges = [0,.1,.2,.3,.4,.5,.6,.7,.8,.9,.95,.99,.999,1.000001]
for lo,hi in zip(edges[:-1], edges[1:]):
    print(f'  {lo}-{hi}: {int(((r>=lo)&(r<hi)).sum())}')

# correlation of A with tol
corr = np.corrcoef(A.astype(float), tol.astype(float))[0,1]
print('corr(A, tol):', corr)
# A/tol distribution
rat = A.astype(float)/tol.astype(float)
print('A/tol quantiles:', np.quantile(rat, [0, .001, .01, .5, .99, .999, 1.0]).round(4))

# check pinned x from p0 json: what is A there?
p0 = json.load(open('work/frontier_scan/p0_invsqrt_errors.json'))
pinned = [e['x'] for e in p0['top50_worst'] if 58597845 <= e['margin_units'] <= 58597860]
print('pinned count in top50:', len(pinned))
for x in pinned[:25]:
    i = x-1
    print(f'x={x:7d} s={int(s[i]):2d} A={int(A[i]):>14d} tol={int(tol[i]):>14d} '
          f'A/tol={float(rat[i]):+.4f} measured_err={p0["top50_worst"][i-x+1]["signed_err_units"] if False else ""}')

np.save('work/p0_reports/data/A_ref.npy', A)
np.save('work/p0_reports/data/s_arr.npy', s)
json.dump({'pinned_from_top50': pinned}, open('work/p0_reports/data/pinned_top50.json','w'))
print('saved')
