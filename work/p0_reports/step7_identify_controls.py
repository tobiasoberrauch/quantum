"""Step 7: identify each b_j(x) - match against candidate Boolean functions of x.

Candidates: address bits, s bits, bucket bits, case bits, y-bits (reference model output),
ANDs of two address bits, XORs. Report exact-match rates.
"""
import sys, json, math
from fractions import Fraction
import numpy as np
sys.path.insert(0, 'data/verifiers/invsqrt')
import verify_submission_invsqrt as V

U64, I64 = np.uint64, np.int64
OUT = 'work/p0_reports/data'
N = 3 * (2**10 - 2)**2
spec = V.ProblemSpecInvSqrt.for_n_p(10, shots_per_x=1)
xs = np.arange(1, N + 1, dtype=U64).astype(np.int64)
s_arr = np.load(f'{OUT}/s_arr.npy')
x_norm = xs << (2 * s_arr)

# reference model output y = p<<s (recompute quickly)
POLY_A = (0.99994132489119882162, 0.49609891915903542303, 0.33261112772430493331, 0.14876762006038398086)
POLY_B = (0.81648515205385221995, 0.27136515484240234115, 0.12756148214815175348, 0.044753028579153842218)
def ref_y(xs):
    width = 22
    def bit(v, i): return (v >> i) & 1
    def product(rows, operand, out_bits, operand_bits, limit):
        acc = np.zeros_like(xs)
        for ctl, wgt in rows:
            e = out_bits - operand_bits + wgt
            acc += ctl * (operand << e if e >= 0 else operand >> -e)
        return acc
    delta_bits, coef_bits, square_bits, product_bits, result_bits = 14, 17, 28, 28, 29
    s = (width - (np.floor(np.log2(xs)).astype(np.int64) + 1)) // 2
    xn = xs << (2 * s)
    top, second, third = bit(xn, width-1), bit(xn, width-2), bit(xn, width-3)
    cases = [POLY_A, POLY_B,
             [a/(2**j*math.sqrt(2)) for j,a in enumerate(POLY_A)],
             [b/(2**j*math.sqrt(2)) for j,b in enumerate(POLY_B)]]
    table = np.array([[round(c*2**coef_bits) for c in case] for case in cases], dtype=np.int64)
    c0, c1, c2, c3 = (table[np.where(top==0, third, 2+second), j] for j in range(4))
    delta = [(top & third, -1)] + [(bit(xn, width-2-m), -m) for m in range(2, delta_bits+1)]
    y0, mult = c0, c3
    for acc in (c2, c1, c0):
        y0 = mult = acc - product(delta, mult, coef_bits, coef_bits, coef_bits)
    wc = coef_bits
    yb = {k: bit(y0, wc-k) for k in range(1, wc+1)}
    square = np.zeros_like(xs)
    for k in range(1, wc+1):
        if 2*k <= square_bits: square += yb[k] << (square_bits - 2*k)
        for l in range(k+1, wc+1):
            if k+l-1 <= square_bits: square += (yb[k]&yb[l]) << (square_bits-(k+l-1))
    m_rows = [(bit(xn, i), i-width+2) for i in range(width)]
    z = product(m_rows, square, product_bits, square_bits, product_bits+2)
    correction = (3 << product_bits) - z
    p = product([(yb[k], -k) for k in range(1, wc+1)], correction, result_bits, product_bits, result_bits+1)
    return p << s, y0, square, z, correction, p

y, y0, square, z, correction, p = ref_y(xs)
print('y range:', int(y.min()), int(y.max()))

cands = {}
for i in range(22):
    cands[f'addr{i:02d}'] = ((xs >> i) & 1).astype(np.float64)
for k in range(4):
    cands[f'sbit{k}'] = ((s_arr >> k) & 1).astype(np.float64)
for k in range(7):
    cands[f'bkt{k}'] = ((x_norm >> (15+k)) & 1).astype(np.float64)
for i in range(40):
    cands[f'y{i:02d}'] = ((y >> i) & 1).astype(np.float64)
for i in range(17):
    cands[f'y0_{i}'] = ((y0 >> i) & 1).astype(np.float64)
for i in range(29):
    cands[f'p{i:02d}'] = ((p >> i) & 1).astype(np.float64)
# ANDs of adjacent address bits (cheap candidates)
for i in range(21):
    cands[f'and{i:02d}_{i+1:02d}'] = (((xs >> i) & 1) * ((xs >> (i+1)) & 1)).astype(np.float64)

B = np.stack([np.load(f'{OUT}/bcols/col_{j:02d}.npy') for j in range(41)], axis=1).astype(np.float64)
meta = json.load(open(f'{OUT}/meta.json'))
angs = [float(Fraction(a) / 2) for a in meta['angles_half_turns_frac']]  # turns

out = []
for j in range(41):
    bj = B[:, j]
    ones = int(bj.sum())
    best = []
    for name, g in cands.items():
        if abs(int(g.sum()) - ones) > max(ones, N-ones) * 0.02:
            continue
        match = float((g == bj).mean())
        if match > 0.999:
            best.append((match, name))
    best.sort(reverse=True)
    out.append({'j': j, 'line': None, 'angle_turns': angs[j], 'ones': ones,
                'exact_matches': [n for _, n in best[:5]],
                'best_partial': best[0][1] if best else None})
    print(f'rot {j:02d} ang={angs[j]:.6e} ones={ones:8d} matches={best[:3]}', file=sys.stderr)

json.dump(out, open(f'{OUT}/step7_control_ids.json', 'w'), indent=1)
print('saved', file=sys.stderr)
