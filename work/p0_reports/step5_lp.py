"""Step 5 (fixed): decompose err(x) = A(x) + sum_j a_j b_j(x); pattern-compress; solve LP.

Precision note: B @ a_units in float64 has ~5e2-unit absolute error on A (large-angle taps
~2^62 units exceed 2^53 exactness). This is negligible for the LP (c ~ 5.9e7) but we
recompute A EXACTLY (Fraction/int) for the pinned set separately.
"""
import sys, json, time
from fractions import Fraction
import numpy as np
sys.path.insert(0, 'data/verifiers/invsqrt')
import verify_submission_invsqrt as V
from scipy.optimize import linprog

U64, I64 = np.uint64, np.int64
OUT = 'work/p0_reports/data'
N = 3 * (2**10 - 2)**2

spec = V.ProblemSpecInvSqrt.for_n_p(10, shots_per_x=1)
xs = np.arange(1, N + 1, dtype=U64)
target, tol = V.reference_values(spec, xs)
tolF = tol.astype(np.float64)

err = np.load(f'{OUT}/err_orig.npy')
B = np.stack([np.load(f'{OUT}/bcols/col_{j:02d}.npy') for j in range(41)], axis=1).astype(np.float64)
meta = json.load(open(f'{OUT}/meta.json'))
angs = [Fraction(a) for a in meta['angles_half_turns_frac']]     # half turns, exact
a_units = [float(a * 2**65) for a in angs]                        # units of 2^-64 turns
a_units_F = [a * 2**65 for a in angs]                              # exact Fractions

S = 2.0**20
A = err.astype(np.float64) - B @ np.array(a_units)
print('A stats: max|A|=%.4e' % np.abs(A).max())
err_rec = A + B @ np.array(a_units)
print('max |err_rec - err|:', np.abs(err_rec - err).max())

# ---- exact A for pinned set ----------------------------------------------
p0 = json.load(open('work/frontier_scan/p0_invsqrt_errors.json'))
pinned = [e['x'] for e in p0['top50_worst'] if 58597845 <= e['margin_units'] <= 58597860]
exact_A_pinned = {}
for x in pinned:
    i = int(x) - 1
    ssum = Fraction(err[i])
    for j in range(41):
        if B[i, j]:
            ssum -= a_units_F[j]
    exact_A_pinned[int(x)] = str(ssum)
json.dump(exact_A_pinned, open(f'{OUT}/A_exact_pinned.json', 'w'), indent=1)

# ---- pattern compression ---------------------------------------------------
keys = np.zeros(N, dtype=np.uint64)
for j in range(41):
    keys |= B[:, j].astype(np.uint64) << np.uint64(j)
uniq, inv = np.unique(keys, return_inverse=True)
print('num patterns:', len(uniq))
m1 = np.full(len(uniq), np.inf)
m2 = np.full(len(uniq), np.inf)
AS = A / S
np.minimum.at(m1, inv, (tolF - AS))
np.minimum.at(m2, inv, (tolF + AS))
P = np.zeros((len(uniq), 42))
for j in range(41):
    P[:, j] = ((uniq >> np.uint64(j)) & 1).astype(np.float64)
P[:, 41] = 1.0

# ---- LP --------------------------------------------------------------------
Amat = np.vstack([np.hstack([P[:, :41], P[:, 41:42]]),
                  np.hstack([-P[:, :41], P[:, 41:42]])])
bvec = np.concatenate([m1, m2])
cvec = np.zeros(42); cvec[41] = -1.0
# keep angles within +-0.25 turns of current (physically sane; prevents LP runaways)
ab = np.array(a_units) / S
half = 0.25 * 2**64 / S
bounds = [(max(-float('inf'), ab[j] - half), ab[j] + half) for j in range(41)] + \
         [(0.0, float(tolF.max()))]
t0 = time.time()
res = linprog(cvec, A_ub=Amat, b_ub=bvec, bounds=bounds, method='highs')
print('LP status:', res.status, res.message, f'{time.time()-t0:.0f}s')
c_opt = res.x[41] * S
print(f'c_optimal (current controls) = {c_opt:.1f} units of 2^-64 turns (current: 58597850)')
a_new = res.x[:41] * S
err_new = np.round(A + B @ a_new)
margin_new = tol.astype(np.int64) - np.abs(err_new).astype(np.int64)
print('achieved min margin with LP angles (rounded):', int(margin_new.min()),
      'at x=', int(xs[margin_new.argmin()])+1)
print('worst ratio:', float((np.abs(err_new).astype(np.float64) / tolF).max()))

json.dump({'c_opt': float(c_opt), 'lp_status': int(res.status),
           'a_current_units': a_units, 'a_opt_units': [float(v) for v in a_new],
           'achieved_min_margin_rounded': int(margin_new.min()),
           'n_patterns': int(len(uniq)), 'pinned': pinned},
          open(f'{OUT}/lp_result.json', 'w'), indent=1)
np.save(f'{OUT}/A_base.npy', A.astype(np.float64))
np.save(f'{OUT}/keys.npy', keys)
np.save(f'{OUT}/inv.npy', inv)
print('saved')
